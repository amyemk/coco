"""
Email Classifier

Classifies emails into one of five triage categories:
  JUNK | NEWSLETTER | SYSTEM_NOTIFICATION | ACTION_REQUIRED | FYI

Two-pass approach:
  Pass 1 — Heuristics (no API call, fast and free)
  Pass 2 — Claude (ambiguous emails only, uses claude-haiku for cost efficiency)

Results are persisted to the emails table for downstream processors.
"""

import json
from datetime import datetime
from typing import List, Optional

import structlog

from src.ai.claude_client import ClaudeClient
from src.ai.prompts.classify import build_classify_prompt, SYSTEM
from src.config.settings import Settings
from src.db.connection import get_db
from src.models.email import Email, EmailCategory, EmailClassification

logger = structlog.get_logger()

# Gmail category labels that indicate newsletter / promotional content
_PROMO_LABELS = {"CATEGORY_PROMOTIONS", "CATEGORY_UPDATES", "CATEGORY_FORUMS"}

# Common unsubscribe indicators in headers / metadata
_NEWSLETTER_KEYWORDS = {
    "unsubscribe",
    "newsletter",
    "digest",
    "weekly",
    "daily roundup",
    "edition",
    "issue #",
}

# Common junk / marketing signals in subjects
_JUNK_SUBJECT_KEYWORDS = {
    "% off",
    "sale",
    "deal",
    "offer",
    "discount",
    "limited time",
    "free shipping",
    "buy now",
    "shop now",
    "flash sale",
    "exclusive offer",
    "unsubscribe",
    "opt out",
}

# Heuristic confidence thresholds
_HEURISTIC_HIGH_CONFIDENCE = 0.90
_HEURISTIC_MEDIUM_CONFIDENCE = 0.75
_CLAUDE_FALLBACK_THRESHOLD = 0.70  # Below this, fall back to Claude


class EmailClassifier:
    """
    Classifies emails into triage categories using heuristics + Claude fallback.

    After classification, results are written back to the emails table.
    """

    def __init__(self, settings: Settings, claude_client: ClaudeClient):
        self.settings = settings
        self.claude = claude_client
        self.db = get_db()
        self._system_sender_map = self._build_system_sender_map()

    def _build_system_sender_map(self) -> dict[str, str]:
        """Build a lookup of sender pattern → system name from config."""
        senders = self.settings.config.integrations.gmail.system_notification_senders
        result: dict[str, str] = {}
        for system, patterns in {
            "Concur": senders.concur,
            "SAP": senders.sap,
            "Bob": senders.bob,
            "Asana": senders.asana,
        }.items():
            for pattern in patterns:
                result[pattern.lower()] = system
        return result

    async def classify(self, email: Email) -> EmailClassification:
        """
        Classify a single email. Tries heuristics first, falls back to Claude.
        """
        # Pass 1: heuristics
        result = self._heuristic_classify(email)

        # Pass 2: Claude for ambiguous results
        if result is None or result.confidence < _CLAUDE_FALLBACK_THRESHOLD:
            result = await self._claude_classify(email)

        # Persist to DB
        self._save_classification(email.id, result)

        logger.debug(
            "email_classified",
            email_id=email.id,
            category=result.category,
            confidence=result.confidence,
            classified_by=result.classified_by,
        )
        return result

    async def classify_batch(
        self, emails: List[Email], skip_already_classified: bool = True
    ) -> List[EmailClassification]:
        """
        Classify a list of emails. Skips already-classified emails by default.
        """
        if skip_already_classified:
            emails = [e for e in emails if e.email_category is None]

        results = []
        for email in emails:
            try:
                result = await self.classify(email)
                results.append(result)
            except Exception as e:
                logger.error("classify_error", email_id=email.id, error=str(e))
        return results

    def get_unclassified(self, since: datetime, limit: int = 500) -> List[Email]:
        """Fetch emails that haven't been classified yet."""
        from src.models.email import Email as EmailModel
        rows = self.db.fetchall(
            """
            SELECT * FROM emails
            WHERE classified_at IS NULL
              AND timestamp >= ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (since.isoformat(), limit),
        )
        return [self._row_to_email(row) for row in rows]

    # -------------------------------------------------------------------------
    # Heuristic classification
    # -------------------------------------------------------------------------

    def _heuristic_classify(self, email: Email) -> Optional[EmailClassification]:
        """
        Rule-based classification. Returns None if email is ambiguous.
        """
        from_lower = email.from_address.lower()
        subject_lower = (email.subject or "").lower()
        snippet_lower = (email.snippet or "").lower()
        labels = set(email.labels or [])

        # 1. System notification — check sender domains first (highest confidence)
        for pattern, system_name in self._system_sender_map.items():
            if pattern in from_lower:
                return EmailClassification(
                    email_id=email.id,
                    category=EmailCategory.SYSTEM_NOTIFICATION,
                    confidence=_HEURISTIC_HIGH_CONFIDENCE,
                    reasoning=f"Sender matches known {system_name} domain pattern",
                    classified_by="heuristic",
                )

        # 2. Gmail's own category labels are reliable signals
        if labels & _PROMO_LABELS:
            # Could be newsletter (subscribed) or junk — need snippet to distinguish
            if any(kw in snippet_lower or kw in subject_lower for kw in _NEWSLETTER_KEYWORDS):
                return EmailClassification(
                    email_id=email.id,
                    category=EmailCategory.NEWSLETTER,
                    confidence=_HEURISTIC_MEDIUM_CONFIDENCE,
                    reasoning="Gmail PROMOTIONS/UPDATES label + newsletter keywords detected",
                    classified_by="heuristic",
                )
            if any(kw in subject_lower for kw in _JUNK_SUBJECT_KEYWORDS):
                return EmailClassification(
                    email_id=email.id,
                    category=EmailCategory.JUNK,
                    confidence=_HEURISTIC_MEDIUM_CONFIDENCE,
                    reasoning="Gmail PROMOTIONS label + marketing subject keywords",
                    classified_by="heuristic",
                )
            # Promotional label but unclear — fall through to Claude

        # 3. Priority senders from config → likely ACTION_REQUIRED
        priority_senders = self.settings.config.integrations.gmail.priority_senders
        if any(sender.lower() in from_lower for sender in priority_senders):
            return EmailClassification(
                email_id=email.id,
                category=EmailCategory.ACTION_REQUIRED,
                confidence=_HEURISTIC_HIGH_CONFIDENCE,
                reasoning="Sender is in configured priority_senders list",
                classified_by="heuristic",
            )

        # 4. Unsubscribe link in snippet → likely newsletter or junk
        if "unsubscribe" in snippet_lower:
            if any(kw in subject_lower for kw in _JUNK_SUBJECT_KEYWORDS):
                return EmailClassification(
                    email_id=email.id,
                    category=EmailCategory.JUNK,
                    confidence=_HEURISTIC_MEDIUM_CONFIDENCE,
                    reasoning="Unsubscribe link + promotional subject",
                    classified_by="heuristic",
                )
            return EmailClassification(
                email_id=email.id,
                category=EmailCategory.NEWSLETTER,
                confidence=_HEURISTIC_MEDIUM_CONFIDENCE,
                reasoning="Unsubscribe link detected in email snippet",
                classified_by="heuristic",
            )

        # Ambiguous — return None to trigger Claude
        return None

    # -------------------------------------------------------------------------
    # Claude classification
    # -------------------------------------------------------------------------

    async def _claude_classify(self, email: Email) -> EmailClassification:
        """Fall back to Claude for ambiguous emails."""
        model = self.settings.config.ai.models.classification
        prompt = build_classify_prompt(
            from_address=email.from_address,
            subject=email.subject or "",
            snippet=email.snippet or "",
        )
        try:
            raw = await self.claude.complete_json(prompt=prompt, model=model, system=SYSTEM)
            data = json.loads(raw)
            return EmailClassification(
                email_id=email.id,
                category=EmailCategory(data["category"]),
                confidence=float(data["confidence"]),
                reasoning=data.get("reasoning", ""),
                classified_by="claude",
            )
        except Exception as e:
            logger.warning("claude_classify_failed", email_id=email.id, error=str(e))
            # Safe fallback: treat as FYI rather than losing the email
            return EmailClassification(
                email_id=email.id,
                category=EmailCategory.FYI,
                confidence=0.5,
                reasoning=f"Classification failed, defaulting to FYI: {e}",
                classified_by="claude",
            )

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def _save_classification(self, email_id: str, result: EmailClassification) -> None:
        self.db.execute(
            """
            UPDATE emails
            SET email_category = ?,
                category_confidence = ?,
                category_reasoning = ?,
                classified_by = ?,
                classified_at = ?
            WHERE id = ?
            """,
            (
                result.category.value,
                result.confidence,
                result.reasoning,
                result.classified_by,
                datetime.utcnow().isoformat(),
                email_id,
            ),
        )

    def _row_to_email(self, row) -> Email:
        return Email(
            id=row["id"],
            thread_id=row["thread_id"],
            from_address=row["from_address"],
            to_addresses=json.loads(row["to_addresses"]),
            cc_addresses=json.loads(row["cc_addresses"] or "[]"),
            subject=row["subject"],
            body=row["body"],
            snippet=row["snippet"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            labels=json.loads(row["labels"]),
            is_flagged=bool(row["is_flagged"]),
            is_read=bool(row["is_read"]),
            has_attachments=bool(row["has_attachments"]),
            priority_score=float(row["priority_score"]),
            requires_response=bool(row["requires_response"]),
            suggested_reply=row["suggested_reply"],
            email_category=EmailCategory(row["email_category"]) if row["email_category"] else None,
            category_confidence=row["category_confidence"],
            category_reasoning=row["category_reasoning"],
            classified_by=row["classified_by"],
            classified_at=datetime.fromisoformat(row["classified_at"]) if row["classified_at"] else None,
            metadata=json.loads(row["metadata"] or "{}"),
        )
