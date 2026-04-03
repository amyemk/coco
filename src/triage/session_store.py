"""
Triage Session Store

Manages triage session records in the database.

Each pre-processing run (noon or afternoon) creates a session record that:
- Tracks which emails were processed in each category
- Records which emails were reviewed/deferred during the triage session
- Prevents the 4pm run from re-surfacing content already shown at noon
- Allows carry-forward of deferred items across sessions

Sessions are stored in the triage_sessions table created in schema.sql.
Pre-processed data (junk scores, newsletter digest, action plans, etc.)
is stored as JSON in the session metadata for retrieval during the triage session.
"""

import json
import uuid
from datetime import datetime
from typing import List, Optional
from typing import TYPE_CHECKING

import structlog

from src.db.connection import get_db

if TYPE_CHECKING:
    from src.triage.pre_processor import TriageSessionResult

logger = structlog.get_logger()


class TriageSessionStore:
    """
    Creates and manages triage session records.
    """

    def __init__(self):
        self.db = get_db()

    def create_session(
        self,
        run_type: str,
        window_start: datetime,
        window_end: datetime,
    ) -> str:
        """
        Create a new triage session record. Returns the session ID.

        Args:
            run_type: "noon" or "afternoon"
            window_start: Start of the email window for this run
            window_end: End of the email window for this run

        Returns:
            New session ID (UUID)
        """
        session_id = str(uuid.uuid4())
        self.db.execute(
            """
            INSERT INTO triage_sessions (
                id, run_type, window_start, window_end, status, created_at
            ) VALUES (?, ?, ?, ?, 'processing', ?)
            """,
            (
                session_id,
                run_type,
                window_start.isoformat(),
                window_end.isoformat(),
                datetime.utcnow().isoformat(),
            ),
        )
        logger.info("triage_session_created", session_id=session_id, run_type=run_type)
        return session_id

    def save_results(self, session_id: str, result: "TriageSessionResult") -> None:
        """
        Persist the pre-processing results to the session record.
        Stores email ID lists and serialised pre-processed data.
        """
        self.db.execute(
            """
            UPDATE triage_sessions SET
                status = 'ready',
                emails_processed = ?,
                junk_count = ?,
                newsletter_count = ?,
                system_notification_count = ?,
                action_required_count = ?,
                fyi_count = ?,
                junk_email_ids = ?,
                newsletter_email_ids = ?,
                system_notification_ids = ?,
                action_email_ids = ?,
                fyi_email_ids = ?,
                metadata = ?
            WHERE id = ?
            """,
            (
                result.total_processed,
                len(result.junk),
                len(result.newsletter_summaries),
                len(result.system_notifications),
                len(result.actions),
                len(result.fyi_emails),
                json.dumps([a.email_id for a in result.junk]),
                json.dumps([s.email_id for s in result.newsletter_summaries]),
                json.dumps([n.email_id for n in result.system_notifications]),
                json.dumps([a.email_id for a in result.actions]),
                json.dumps([e.id for e in result.fyi_emails]),
                json.dumps(result.to_metadata_dict()),
                session_id,
            ),
        )
        logger.info(
            "triage_session_results_saved",
            session_id=session_id,
            total=result.total_processed,
        )

    def mark_notification_sent(self, session_id: str) -> None:
        self.db.execute(
            """
            UPDATE triage_sessions
            SET notification_sent = 1, notification_sent_at = ?
            WHERE id = ?
            """,
            (datetime.utcnow().isoformat(), session_id),
        )

    def mark_email_reviewed(self, session_id: str, email_id: str) -> None:
        """Record that an email was reviewed during the triage session."""
        row = self.db.fetchone(
            "SELECT reviewed_email_ids, emails_reviewed FROM triage_sessions WHERE id = ?",
            (session_id,),
        )
        if not row:
            return
        reviewed = json.loads(row["reviewed_email_ids"] or "[]")
        if email_id not in reviewed:
            reviewed.append(email_id)
        self.db.execute(
            """
            UPDATE triage_sessions
            SET reviewed_email_ids = ?, emails_reviewed = ?
            WHERE id = ?
            """,
            (json.dumps(reviewed), len(reviewed), session_id),
        )

    def defer_email(self, session_id: str, email_id: str) -> None:
        """Record that an email was explicitly deferred to the next session."""
        row = self.db.fetchone(
            "SELECT deferred_email_ids FROM triage_sessions WHERE id = ?",
            (session_id,),
        )
        if not row:
            return
        deferred = json.loads(row["deferred_email_ids"] or "[]")
        if email_id not in deferred:
            deferred.append(email_id)
        self.db.execute(
            "UPDATE triage_sessions SET deferred_email_ids = ? WHERE id = ?",
            (json.dumps(deferred), session_id),
        )

    def record_task_created(self, session_id: str, task_ref: str) -> None:
        row = self.db.fetchone(
            "SELECT tasks_created FROM triage_sessions WHERE id = ?", (session_id,)
        )
        if not row:
            return
        tasks = json.loads(row["tasks_created"] or "[]")
        tasks.append(task_ref)
        self.db.execute(
            "UPDATE triage_sessions SET tasks_created = ? WHERE id = ?",
            (json.dumps(tasks), session_id),
        )

    def record_draft_saved(self, session_id: str, draft_id: str) -> None:
        row = self.db.fetchone(
            "SELECT drafts_saved FROM triage_sessions WHERE id = ?", (session_id,)
        )
        if not row:
            return
        drafts = json.loads(row["drafts_saved"] or "[]")
        drafts.append(draft_id)
        self.db.execute(
            "UPDATE triage_sessions SET drafts_saved = ? WHERE id = ?",
            (json.dumps(drafts), session_id),
        )

    def mark_session_complete(self, session_id: str) -> None:
        self.db.execute(
            """
            UPDATE triage_sessions
            SET status = 'reviewed', completed_at = ?
            WHERE id = ?
            """,
            (datetime.utcnow().isoformat(), session_id),
        )

    def get_pending_session(self) -> Optional[dict]:
        """
        Return the most recent session that is 'ready' but not yet reviewed.
        Used at the start of an interactive triage session.
        """
        return self.db.fetchone(
            """
            SELECT * FROM triage_sessions
            WHERE status = 'ready'
            ORDER BY created_at DESC
            LIMIT 1
            """
        )

    def get_deferred_email_ids(self) -> List[str]:
        """
        Return all email IDs deferred across all previous sessions
        that haven't been reviewed yet.
        """
        rows = self.db.fetchall(
            """
            SELECT deferred_email_ids FROM triage_sessions
            WHERE status IN ('ready', 'reviewed')
            ORDER BY created_at DESC
            LIMIT 5
            """
        )
        seen = set()
        deferred = []
        for row in rows:
            for eid in json.loads(row["deferred_email_ids"] or "[]"):
                if eid not in seen:
                    seen.add(eid)
                    deferred.append(eid)
        return deferred

    def get_reviewed_newsletter_email_ids(self, lookback_sessions: int = 2) -> List[str]:
        """
        Return newsletter email IDs already surfaced in recent sessions.
        Used by the pre-processor to avoid repeating content.
        """
        rows = self.db.fetchall(
            """
            SELECT newsletter_email_ids FROM triage_sessions
            WHERE status IN ('ready', 'reviewed')
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (lookback_sessions,),
        )
        seen = []
        for row in rows:
            seen.extend(json.loads(row["newsletter_email_ids"] or "[]"))
        return seen
