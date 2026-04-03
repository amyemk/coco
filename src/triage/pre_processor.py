"""
Triage Pre-Processor

Orchestrates the full pre-processing run for a triage window (noon or afternoon).

Steps:
  1. Determine the time window
  2. Classify any unclassified emails in the window
  3. Fetch emails by category
  4. Run category-specific processors in parallel where safe
  5. Store results in the triage session
  6. Send notification email

The output (TriageSessionResult) is persisted to the DB and loaded
during the interactive triage session.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

import structlog

from src.ai.claude_client import ClaudeClient
from src.config.settings import Settings, get_settings
from src.db.connection import get_db
from src.engine.action_processor import ActionProcessor
from src.engine.email_classifier import EmailClassifier
from src.engine.junk_detector import JunkDetector
from src.engine.newsletter_summarizer import NewsletterSummarizer
from src.engine.system_notification_parser import (
    SystemNotificationParser,
    aggregate_notifications,
)
from src.models.email import (
    ActionPlan,
    DeduplicatedDigest,
    Email,
    EmailCategory,
    JunkAnalysis,
    NewsletterSummary,
    SystemNotification,
)
from src.triage.session_store import TriageSessionStore

logger = structlog.get_logger()


@dataclass
class TriageSessionResult:
    """Complete output of a pre-processing run, ready for the triage session."""

    session_id: str
    run_type: str  # "noon" | "afternoon"
    window_start: datetime
    window_end: datetime

    # Per-category results
    junk: List[JunkAnalysis] = field(default_factory=list)
    newsletter_summaries: List[NewsletterSummary] = field(default_factory=list)
    newsletter_digest: Optional[DeduplicatedDigest] = None
    system_notifications: List[SystemNotification] = field(default_factory=list)
    system_notification_aggregate: str = ""
    actions: List[ActionPlan] = field(default_factory=list)
    fyi_emails: List[Email] = field(default_factory=list)

    # Flag for afternoon run
    eod_urgent_email_ids: List[str] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        return (
            len(self.junk)
            + len(self.newsletter_summaries)
            + len(self.system_notifications)
            + len(self.actions)
            + len(self.fyi_emails)
        )

    @property
    def action_items_count(self) -> int:
        """Items needing user input: action emails + system notifications requiring action."""
        system_actions = sum(1 for n in self.system_notifications if n.requires_action)
        return len(self.actions) + system_actions

    def to_metadata_dict(self) -> dict:
        """
        Serialise pre-processed data to a dict for DB storage.
        Loaded back during the triage session.
        """
        return {
            "junk": [
                {
                    "email_id": a.email_id,
                    "suggestion": a.suggestion.value,
                    "confidence": a.confidence,
                    "reason": a.reason,
                    "sender_history_count": a.sender_history_count,
                }
                for a in self.junk
            ],
            "newsletter_digest": (
                {
                    "stories": [
                        {
                            "headline": s.headline,
                            "summary": s.summary,
                            "sources": s.sources,
                        }
                        for s in self.newsletter_digest.stories
                    ],
                    "processed_email_ids": self.newsletter_digest.processed_email_ids,
                }
                if self.newsletter_digest
                else None
            ),
            "newsletter_full_content": {
                s.email_id: s.full_content for s in self.newsletter_summaries
            },
            "system_notifications": [
                {
                    "email_id": n.email_id,
                    "system": n.system,
                    "action_type": n.action_type,
                    "entity_name": n.entity_name,
                    "status": n.status,
                    "requires_action": n.requires_action,
                    "deep_link": n.deep_link,
                    "raw_summary": n.raw_summary,
                    "deadline": n.deadline.isoformat() if n.deadline else None,
                }
                for n in self.system_notifications
            ],
            "system_notification_aggregate": self.system_notification_aggregate,
            "actions": [
                {
                    "email_id": a.email_id,
                    "action_type": a.action_type,
                    "draft_set": (
                        {
                            "original_email_id": a.draft_set.original_email_id,
                            "thread_summary": a.draft_set.thread_summary,
                            "options": [
                                {
                                    "style": o.style,
                                    "subject": o.subject,
                                    "body": o.body,
                                }
                                for o in a.draft_set.options
                            ],
                        }
                        if a.draft_set
                        else None
                    ),
                    "task": (
                        {
                            "title": a.task.title,
                            "due_date": a.task.due_date.isoformat() if a.task.due_date else None,
                            "tags": a.task.tags,
                            "source_ref": a.task.source_ref,
                            "email_id": a.task.email_id,
                        }
                        if a.task
                        else None
                    ),
                }
                for a in self.actions
            ],
            "eod_urgent_email_ids": self.eod_urgent_email_ids,
        }


class TriagePreProcessor:
    """
    Runs the full pre-processing pipeline for a triage window.

    Instantiated fresh for each run. Engines are created with shared
    ClaudeClient for rate limiting and caching across the run.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.db = get_db()
        self.session_store = TriageSessionStore()

        # Build shared Claude client
        self.claude = ClaudeClient(
            api_key=settings.env.anthropic_api_key,
            default_model=settings.config.ai.model,
            max_tokens=settings.config.ai.max_tokens,
            temperature=settings.config.ai.temperature,
            cache_db_path=str(settings.get_database_path()).replace(".db", "_cache.db"),
            cache_ttl_hours=settings.config.ai.cache_ttl_hours,
            enable_cache=settings.config.ai.enable_caching,
        )

        # Instantiate engines
        self.classifier = EmailClassifier(settings, self.claude)
        self.junk_detector = JunkDetector(settings, self.claude)
        self.newsletter_summarizer = NewsletterSummarizer(settings, self.claude)
        self.system_parser = SystemNotificationParser()
        self.action_processor = ActionProcessor(settings, self.claude)

    async def run(self, run_type: str) -> TriageSessionResult:
        """
        Execute the full pre-processing pipeline for a triage run.

        Args:
            run_type: "noon" or "afternoon"

        Returns:
            TriageSessionResult with all processed data
        """
        window_start, window_end = self._get_window(run_type)
        logger.info(
            "triage_preprocessing_started",
            run_type=run_type,
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
        )

        # Create session record
        session_id = self.session_store.create_session(run_type, window_start, window_end)
        result = TriageSessionResult(
            session_id=session_id,
            run_type=run_type,
            window_start=window_start,
            window_end=window_end,
        )

        try:
            # Step 1: Classify any unclassified emails in the window
            unclassified = self.classifier.get_unclassified(since=window_start)
            if unclassified:
                logger.info("classifying_emails", count=len(unclassified))
                await self.classifier.classify_batch(unclassified)

            # Step 2: Fetch emails by category
            emails_by_category = self._fetch_emails_by_category(window_start, window_end)

            # Step 3: Process each category (newsletter and junk can run concurrently)
            junk_emails = emails_by_category.get(EmailCategory.JUNK, [])
            newsletter_emails = emails_by_category.get(EmailCategory.NEWSLETTER, [])
            system_emails = emails_by_category.get(EmailCategory.SYSTEM_NOTIFICATION, [])
            action_emails = emails_by_category.get(EmailCategory.ACTION_REQUIRED, [])
            fyi_emails = emails_by_category.get(EmailCategory.FYI, [])

            # Apply session-awareness: skip newsletters already shown
            already_seen = self.session_store.get_reviewed_newsletter_email_ids()
            newsletter_emails = [e for e in newsletter_emails if e.id not in already_seen]

            # Cap lists per triage config
            triage_cfg = self.settings.config.triage
            junk_emails = junk_emails[: triage_cfg.max_junk_suggestions]
            newsletter_emails = newsletter_emails[: triage_cfg.max_newsletter_summaries]
            action_emails = action_emails[: triage_cfg.max_action_emails]

            # Run junk and newsletter in parallel; system and action sequentially after
            junk_task = self.junk_detector.analyze_batch(junk_emails)
            newsletter_task = self.newsletter_summarizer.summarize_batch(newsletter_emails)

            result.junk, result.newsletter_summaries = await asyncio.gather(
                junk_task, newsletter_task
            )

            # Deduplicate newsletters
            if result.newsletter_summaries:
                result.newsletter_digest = await self.newsletter_summarizer.deduplicate(
                    result.newsletter_summaries
                )

            # System notifications (pure regex, no async needed but keep pattern consistent)
            result.system_notifications = [
                self.system_parser.parse(e) for e in system_emails
            ]
            result.system_notification_aggregate = aggregate_notifications(
                result.system_notifications
            )

            # Action emails — fetch threads for better draft context
            threads = self._fetch_threads(action_emails)
            result.actions = await self.action_processor.process_batch(action_emails, threads)

            result.fyi_emails = fyi_emails

            # Afternoon-specific: flag EOD-urgent items
            if run_type == "afternoon" and triage_cfg.afternoon_run.flag_eod_urgency:
                result.eod_urgent_email_ids = self._detect_eod_urgent(action_emails)

            # Persist results
            self.session_store.save_results(session_id, result)

            logger.info(
                "triage_preprocessing_complete",
                session_id=session_id,
                total=result.total_processed,
                action_items=result.action_items_count,
                junk=len(result.junk),
                newsletters=len(result.newsletter_summaries),
                system=len(result.system_notifications),
                actions=len(result.actions),
                fyi=len(result.fyi_emails),
            )

        except Exception as e:
            logger.error("triage_preprocessing_error", session_id=session_id, error=str(e))
            raise

        return result

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_window(self, run_type: str) -> tuple[datetime, datetime]:
        """
        Determine the email window for this run.
        Noon: midnight → now
        Afternoon: last noon → now
        """
        now = datetime.utcnow()
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if run_type == "noon":
            return today_midnight, now
        else:  # afternoon
            noon = today_midnight.replace(hour=12)
            return noon, now

    def _fetch_emails_by_category(
        self, since: datetime, until: datetime
    ) -> dict[EmailCategory, List[Email]]:
        """Fetch classified emails in the window, grouped by category."""
        from src.repositories.email_repository import EmailRepository
        repo = EmailRepository()
        all_emails = repo.get_recent(since=since)
        # Filter to within window
        all_emails = [e for e in all_emails if e.timestamp <= until]

        by_category: dict[EmailCategory, List[Email]] = {}
        for email in all_emails:
            if email.email_category:
                cat = email.email_category
                by_category.setdefault(cat, []).append(email)
        return by_category

    def _fetch_threads(self, emails: List[Email]) -> dict[str, List[Email]]:
        """Fetch full thread context for a list of emails."""
        from src.repositories.email_repository import EmailRepository
        repo = EmailRepository()
        threads: dict[str, List[Email]] = {}
        seen_threads = set()
        for email in emails:
            if email.thread_id not in seen_threads:
                seen_threads.add(email.thread_id)
                threads[email.thread_id] = repo.get_thread(email.thread_id)
        return threads

    def _detect_eod_urgent(self, action_emails: List[Email]) -> List[str]:
        """
        Flag emails that need to be handled before end of day.
        Simple heuristic: keywords in subject/body.
        """
        eod_keywords = {"today", "eod", "end of day", "by close", "before 5", "asap", "urgent"}
        urgent_ids = []
        for email in action_emails:
            text = ((email.subject or "") + " " + (email.snippet or "")).lower()
            if any(kw in text for kw in eod_keywords):
                urgent_ids.append(email.id)
        return urgent_ids
