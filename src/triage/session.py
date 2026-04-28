"""
Triage Session

Loads a pre-processed triage session from the database and provides
all the action methods needed during an interactive triage session.

This is the single object Claude Code works with during a session:
  - Exposes queues per category (junk, newsletters, system notifications, actions)
  - Keeps full email content in memory for follow-up questions
  - Executes confirmed actions (write task, save draft, archive, mark reviewed)
  - Persists state as you work through the queue
"""

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional

import structlog

from src.config.settings import Settings, get_settings
from src.models.email import (
    ActionPlan,
    DeduplicatedDigest,
    DraftOption,
    EmailDraftSet,
    JunkAnalysis,
    JunkSuggestion,
    ObsidianTask,
    Story,
    SystemNotification,
)
from src.triage.session_store import TriageSessionStore

logger = structlog.get_logger()


@dataclass
class DeferredItem:
    """An email deferred from a previous session."""
    email_id: str
    subject: str
    from_address: str
    original_category: str
    deferred_at: str


class TriageSession:
    """
    The interactive triage session object.

    Load with TriageSession.load_latest(settings) at the start of a session.
    All queues are pre-populated from the DB. Actions persist state immediately.
    """

    def __init__(self, session_id: str, session_row: dict, settings: Settings):
        self.session_id = session_id
        self.run_type = session_row["run_type"]
        self.window_start = session_row["window_start"]
        self.window_end = session_row["window_end"]
        self.settings = settings
        self._store = TriageSessionStore()
        self._meta = json.loads(session_row.get("metadata") or "{}")

        # Queues (populated by _load_queues)
        self.junk: List[JunkAnalysis] = []
        self.newsletter_digest: Optional[DeduplicatedDigest] = None
        self._newsletter_full_content: dict[str, str] = {}  # email_id → body
        self.system_notifications: List[SystemNotification] = []
        self.system_notification_aggregate: str = ""
        self.actions: List[ActionPlan] = []
        self.deferred: List[DeferredItem] = []

        # Reviewed / deferred tracking (in-memory for this session)
        self._reviewed: set[str] = set()
        self._session_deferred: set[str] = set()

        self._load_queues()

    # -------------------------------------------------------------------------
    # Factory
    # -------------------------------------------------------------------------

    @classmethod
    def load_latest(cls, settings: Optional[Settings] = None) -> Optional["TriageSession"]:
        """
        Load the most recent 'ready' triage session from the database.
        Returns None if no session is pending review.
        """
        if settings is None:
            settings = get_settings()
        store = TriageSessionStore()
        row = store.get_pending_session()
        if not row:
            return None
        return cls(session_id=row["id"], session_row=dict(row), settings=settings)

    # -------------------------------------------------------------------------
    # Queue loading
    # -------------------------------------------------------------------------

    def _load_queues(self) -> None:
        """Deserialise pre-processed data from session metadata."""

        # Junk
        for item in self._meta.get("junk", []):
            self.junk.append(
                JunkAnalysis(
                    email_id=item["email_id"],
                    suggestion=JunkSuggestion(item["suggestion"]),
                    confidence=item["confidence"],
                    reason=item["reason"],
                    sender_history_count=item.get("sender_history_count", 0),
                )
            )

        # Newsletter digest
        digest_data = self._meta.get("newsletter_digest")
        if digest_data:
            self.newsletter_digest = DeduplicatedDigest(
                stories=[
                    Story(
                        headline=s["headline"],
                        summary=s["summary"],
                        sources=s["sources"],
                    )
                    for s in digest_data.get("stories", [])
                ],
                processed_email_ids=digest_data.get("processed_email_ids", []),
            )
        self._newsletter_full_content = self._meta.get("newsletter_full_content", {})

        # System notifications
        self.system_notification_aggregate = self._meta.get(
            "system_notification_aggregate", ""
        )
        for item in self._meta.get("system_notifications", []):
            deadline = None
            if item.get("deadline"):
                try:
                    deadline = date.fromisoformat(item["deadline"])
                except ValueError:
                    pass
            self.system_notifications.append(
                SystemNotification(
                    email_id=item["email_id"],
                    system=item["system"],
                    action_type=item["action_type"],
                    entity_name=item["entity_name"],
                    status=item["status"],
                    deadline=deadline,
                    requires_action=item["requires_action"],
                    deep_link=item.get("deep_link"),
                    raw_summary=item["raw_summary"],
                )
            )

        # Action plans
        for item in self._meta.get("actions", []):
            draft_set = None
            if item.get("draft_set"):
                ds = item["draft_set"]
                draft_set = EmailDraftSet(
                    original_email_id=ds["original_email_id"],
                    thread_summary=ds["thread_summary"],
                    options=[
                        DraftOption(
                            style=o["style"],
                            subject=o["subject"],
                            body=o["body"],
                        )
                        for o in ds.get("options", [])
                    ],
                )
            task = None
            if item.get("task"):
                t = item["task"]
                due_date = None
                if t.get("due_date"):
                    try:
                        due_date = date.fromisoformat(t["due_date"])
                    except ValueError:
                        pass
                task = ObsidianTask(
                    title=t["title"],
                    due_date=due_date,
                    tags=t.get("tags", []),
                    source_ref=t.get("source_ref", ""),
                    email_id=t.get("email_id"),
                )
            self.actions.append(
                ActionPlan(
                    email_id=item["email_id"],
                    action_type=item["action_type"],
                    draft_set=draft_set,
                    task=task,
                )
            )

        # EOD urgent IDs
        self._eod_urgent_ids = set(self._meta.get("eod_urgent_email_ids", []))

        # Load deferred items from prior sessions
        self._load_deferred()

    def _load_deferred(self) -> None:
        """Load email IDs deferred from prior sessions."""
        deferred_ids = self._store.get_deferred_email_ids()
        if not deferred_ids:
            return
        from src.repositories.email_repository import EmailRepository
        repo = EmailRepository()
        for eid in deferred_ids:
            email = repo.get_by_id(eid)
            if email:
                self.deferred.append(
                    DeferredItem(
                        email_id=eid,
                        subject=email.subject or "(no subject)",
                        from_address=email.from_address,
                        original_category=email.email_category.value if email.email_category else "UNKNOWN",
                        deferred_at="previous session",
                    )
                )

    # -------------------------------------------------------------------------
    # Accessors for follow-up questions
    # -------------------------------------------------------------------------

    def get_newsletter_full_content(self, email_id: str) -> Optional[str]:
        """Return the full email body for a newsletter — used for follow-up questions."""
        return self._newsletter_full_content.get(email_id)

    def get_email_body(self, email_id: str) -> Optional[str]:
        """Fetch the full email body from DB for any email in the session."""
        from src.repositories.email_repository import EmailRepository
        email = EmailRepository().get_by_id(email_id)
        return email.body if email else None

    def is_eod_urgent(self, email_id: str) -> bool:
        return email_id in self._eod_urgent_ids

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def confirm_junk(self, email_id: str) -> None:
        """
        User confirmed a junk classification. Updates sender memory
        and marks the email reviewed.
        """
        from src.engine.junk_detector import JunkDetector
        from src.repositories.email_repository import EmailRepository

        email = EmailRepository().get_by_id(email_id)
        if email:
            detector = JunkDetector(self.settings, None)  # type: ignore[arg-type]
            detector.confirm_junk(email)

        self.mark_reviewed(email_id)
        logger.info("junk_confirmed", email_id=email_id)

    def write_task(self, task: ObsidianTask) -> bool:
        """
        Write a task to the Obsidian vault and record it in the session.
        """
        from src.engine.obsidian_task_writer import ObsidianTaskWriter
        writer = ObsidianTaskWriter(self.settings)
        success = writer.write_task(task)
        if success:
            self._store.record_task_created(self.session_id, task.title)
            logger.info("session_task_written", title=task.title)
        return success

    def save_draft(self, email_id: str, style: str) -> Optional[str]:
        """
        Save the selected draft option to Gmail Drafts.
        Returns the Gmail draft ID if successful.
        """
        plan = self._get_action_plan(email_id)
        if not plan or not plan.draft_set:
            logger.warning("no_draft_set_for_email", email_id=email_id)
            return None

        option = next((o for o in plan.draft_set.options if o.style == style), None)
        if not option:
            logger.warning("draft_style_not_found", email_id=email_id, style=style)
            return None

        from src.delivery.gmail_draft_saver import GmailDraftSaver
        from src.repositories.email_repository import EmailRepository

        email = EmailRepository().get_by_id(email_id)
        if not email:
            return None

        saver = GmailDraftSaver(self.settings)
        draft_id = saver.save_draft(
            draft_option=option,
            to_address=email.from_address,
            thread_id=email.thread_id,
            in_reply_to_message_id=email_id,
        )
        if draft_id:
            self._store.record_draft_saved(self.session_id, draft_id)
            EmailRepository().mark_as_read(email_id)
        return draft_id

    def mark_reviewed(self, email_id: str) -> None:
        """Mark an email as reviewed in this session and as read in the database."""
        self._reviewed.add(email_id)
        self._store.mark_email_reviewed(self.session_id, email_id)
        from src.repositories.email_repository import EmailRepository
        EmailRepository().mark_as_read(email_id)

    def defer(self, email_id: str) -> None:
        """Defer an email to the next session."""
        self._session_deferred.add(email_id)
        self._store.defer_email(self.session_id, email_id)
        logger.info("email_deferred", email_id=email_id)

    def complete(self) -> None:
        """Mark the session as fully reviewed."""
        self._store.mark_session_complete(self.session_id)
        logger.info("triage_session_complete", session_id=self.session_id)

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------

    def get_summary(self) -> dict:
        """Return a summary dict for display at session start."""
        return {
            "session_id": self.session_id,
            "run_type": self.run_type,
            "window": f"{self.window_start} → {self.window_end}",
            "totals": {
                "junk": len(self.junk),
                "newsletters": (
                    len(self.newsletter_digest.stories) if self.newsletter_digest else 0
                ),
                "system_notifications": len(self.system_notifications),
                "actions": len(self.actions),
                "deferred_from_prior": len(self.deferred),
                "eod_urgent": len(self._eod_urgent_ids),
            },
        }

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_action_plan(self, email_id: str) -> Optional[ActionPlan]:
        return next((a for a in self.actions if a.email_id == email_id), None)
