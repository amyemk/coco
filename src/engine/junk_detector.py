"""
Junk Detector

Analyses JUNK-classified emails and determines whether to suggest:
  - delete  — Spam, cold outreach, fraudulent email
  - unsubscribe — Legitimate marketing the user no longer wants
  - review  — Ambiguous, show to user

Maintains a sender memory table so known junk senders are handled
without an API call and auto-classified in future syncs.
"""

import json
from datetime import datetime
from typing import List

import structlog

from src.ai.claude_client import ClaudeClient
from src.ai.prompts.junk import build_junk_prompt, JUNK_SYSTEM
from src.config.settings import Settings
from src.db.connection import get_db
from src.models.email import Email, JunkAnalysis, JunkSuggestion

logger = structlog.get_logger()

_AUTO_CLASSIFY_THRESHOLD = 3  # Confirm junk N times → auto-classify sender


class JunkDetector:
    """
    Scores junk emails and maintains sender memory for future auto-classification.
    """

    def __init__(self, settings: Settings, claude_client: ClaudeClient):
        self.settings = settings
        self.claude = claude_client
        self.db = get_db()
        self._model = settings.config.ai.models.junk_detection

    async def analyze(self, email: Email) -> JunkAnalysis:
        """
        Determine what to do with a junk email.

        Args:
            email: An email classified as JUNK

        Returns:
            JunkAnalysis with suggestion, confidence, and reason
        """
        sender_count = self._get_sender_junk_count(email.from_address)

        # If sender is in auto-classify memory, return high-confidence delete
        if self._is_auto_classify_sender(email.from_address):
            return JunkAnalysis(
                email_id=email.id,
                suggestion=JunkSuggestion.DELETE,
                confidence=0.98,
                reason="Known junk sender (auto-classified from memory)",
                sender_history_count=sender_count,
            )

        # Otherwise ask Claude
        prompt = build_junk_prompt(
            from_address=email.from_address,
            subject=email.subject or "",
            snippet=email.snippet or "",
            sender_count=sender_count,
        )

        try:
            raw = await self.claude.complete_json(
                prompt=prompt,
                model=self._model,
                system=JUNK_SYSTEM,
            )
            data = json.loads(raw)
            return JunkAnalysis(
                email_id=email.id,
                suggestion=JunkSuggestion(data["suggestion"]),
                confidence=float(data["confidence"]),
                reason=data.get("reason", ""),
                sender_history_count=sender_count,
            )
        except Exception as e:
            logger.warning("junk_analysis_failed", email_id=email.id, error=str(e))
            return JunkAnalysis(
                email_id=email.id,
                suggestion=JunkSuggestion.REVIEW,
                confidence=0.5,
                reason=f"Analysis failed: {e}",
                sender_history_count=sender_count,
            )

    async def analyze_batch(self, emails: List[Email]) -> List[JunkAnalysis]:
        results = []
        for email in emails:
            try:
                result = await self.analyze(email)
                results.append(result)
            except Exception as e:
                logger.error("junk_batch_error", email_id=email.id, error=str(e))
        return results

    def confirm_junk(self, email: Email) -> None:
        """
        Record that the user confirmed an email as junk.
        Updates sender memory — after threshold, enables auto-classification.
        """
        if not self.settings.config.triage.junk.sender_memory:
            return

        domain = self._extract_domain(email.from_address)
        existing = self.db.fetchone(
            "SELECT confirmed_junk_count FROM junk_sender_memory WHERE sender_domain = ?",
            (domain,),
        )

        if existing:
            new_count = existing["confirmed_junk_count"] + 1
            auto = new_count >= _AUTO_CLASSIFY_THRESHOLD
            self.db.execute(
                """
                UPDATE junk_sender_memory
                SET confirmed_junk_count = ?,
                    last_confirmed = ?,
                    auto_classify = ?
                WHERE sender_domain = ?
                """,
                (new_count, datetime.utcnow().isoformat(), auto, domain),
            )
            if auto:
                logger.info("junk_sender_auto_classify_enabled", domain=domain, count=new_count)
        else:
            self.db.execute(
                """
                INSERT INTO junk_sender_memory
                    (sender_domain, sender_email, confirmed_junk_count, auto_classify)
                VALUES (?, ?, 1, 0)
                """,
                (domain, email.from_address),
            )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_sender_junk_count(self, from_address: str) -> int:
        domain = self._extract_domain(from_address)
        row = self.db.fetchone(
            "SELECT confirmed_junk_count FROM junk_sender_memory WHERE sender_domain = ?",
            (domain,),
        )
        return row["confirmed_junk_count"] if row else 0

    def _is_auto_classify_sender(self, from_address: str) -> bool:
        if not self.settings.config.triage.junk.sender_memory:
            return False
        domain = self._extract_domain(from_address)
        row = self.db.fetchone(
            "SELECT auto_classify FROM junk_sender_memory WHERE sender_domain = ?",
            (domain,),
        )
        return bool(row and row["auto_classify"])

    def _extract_domain(self, from_address: str) -> str:
        address = from_address.lower()
        if "<" in address:
            address = address.split("<")[1].rstrip(">")
        if "@" in address:
            return address.split("@")[1]
        return address
