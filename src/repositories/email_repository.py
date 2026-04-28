"""
Email Repository

Data access layer for email operations.
"""

import json
from typing import List, Optional
from datetime import datetime

import structlog

from src.db.connection import get_db
from src.models.email import Email

logger = structlog.get_logger()


class EmailRepository:
    """
    Repository for email data access
    """

    def __init__(self):
        self.db = get_db()

    def save(self, email: Email) -> None:
        """
        Save or update an email in the database.

        Args:
            email: Email object to save
        """
        try:
            self.db.execute(
                """
                INSERT INTO emails (
                    id, thread_id, from_address, to_addresses, cc_addresses,
                    subject, body, snippet, timestamp, labels,
                    is_flagged, is_read, has_attachments,
                    priority_score, requires_response, suggested_reply, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    from_address = excluded.from_address,
                    to_addresses = excluded.to_addresses,
                    cc_addresses = excluded.cc_addresses,
                    subject = excluded.subject,
                    body = excluded.body,
                    snippet = excluded.snippet,
                    timestamp = excluded.timestamp,
                    labels = excluded.labels,
                    is_flagged = excluded.is_flagged,
                    is_read = excluded.is_read,
                    has_attachments = excluded.has_attachments,
                    priority_score = excluded.priority_score,
                    requires_response = excluded.requires_response,
                    suggested_reply = excluded.suggested_reply,
                    metadata = excluded.metadata,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    email.id,
                    email.thread_id,
                    email.from_address,
                    json.dumps(email.to_addresses),
                    json.dumps(email.cc_addresses),
                    email.subject,
                    email.body,
                    email.snippet,
                    email.timestamp.isoformat(),
                    json.dumps(email.labels),
                    email.is_flagged,
                    email.is_read,
                    email.has_attachments,
                    email.priority_score,
                    email.requires_response,
                    email.suggested_reply,
                    json.dumps(email.metadata),
                ),
            )

            logger.debug("email_saved", email_id=email.id)

        except Exception as e:
            logger.error("email_save_error", error=str(e), email_id=email.id)
            raise

    def save_many(self, emails: List[Email]) -> int:
        """
        Save multiple emails in a batch.

        Args:
            emails: List of emails to save

        Returns:
            Number of emails saved
        """
        count = 0
        for email in emails:
            try:
                self.save(email)
                count += 1
            except Exception as e:
                logger.error("batch_email_save_error", error=str(e), email_id=email.id)

        logger.info("emails_batch_saved", count=count, total=len(emails))
        return count

    def get_by_id(self, email_id: str) -> Optional[Email]:
        """
        Get an email by ID.

        Args:
            email_id: Email ID

        Returns:
            Email object or None
        """
        row = self.db.fetchone("SELECT * FROM emails WHERE id = ?", (email_id,))

        if row:
            return self._row_to_email(row)
        return None

    def get_thread(self, thread_id: str) -> List[Email]:
        """
        Get all emails in a thread.

        Args:
            thread_id: Thread ID

        Returns:
            List of emails in thread, ordered by timestamp
        """
        rows = self.db.fetchall(
            "SELECT * FROM emails WHERE thread_id = ? ORDER BY timestamp ASC",
            (thread_id,),
        )

        return [self._row_to_email(row) for row in rows]

    def get_unread(self, limit: int = 50) -> List[Email]:
        """
        Get unread emails, ordered by priority.

        Args:
            limit: Maximum number of emails to return

        Returns:
            List of unread emails
        """
        rows = self.db.fetchall(
            """
            SELECT * FROM emails
            WHERE is_read = 0
            ORDER BY priority_score DESC, timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )

        return [self._row_to_email(row) for row in rows]

    def get_flagged(self) -> List[Email]:
        """
        Get flagged/starred emails.

        Returns:
            List of flagged emails
        """
        rows = self.db.fetchall(
            """
            SELECT * FROM emails
            WHERE is_flagged = 1
            ORDER BY timestamp DESC
            """
        )

        return [self._row_to_email(row) for row in rows]

    def get_requiring_response(self, limit: int = 20) -> List[Email]:
        """
        Get emails that require a response.

        Args:
            limit: Maximum number to return

        Returns:
            List of emails requiring response
        """
        rows = self.db.fetchall(
            """
            SELECT * FROM emails
            WHERE requires_response = 1
            ORDER BY priority_score DESC, timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )

        return [self._row_to_email(row) for row in rows]

    def get_recent(
        self, since: datetime, limit: Optional[int] = None
    ) -> List[Email]:
        """
        Get emails since a specific date.

        Args:
            since: Get emails after this date
            limit: Optional limit on results

        Returns:
            List of recent emails
        """
        query = """
            SELECT * FROM emails
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        rows = self.db.fetchall(query, (since.isoformat(),))

        return [self._row_to_email(row) for row in rows]

    def search(self, query: str, limit: int = 50) -> List[Email]:
        """
        Full-text search across emails.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching emails
        """
        rows = self.db.fetchall(
            """
            SELECT emails.* FROM emails
            JOIN emails_fts ON emails.id = emails_fts.id
            WHERE emails_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        )

        return [self._row_to_email(row) for row in rows]

    def get_high_priority(self, threshold: float = 0.7, limit: int = 20) -> List[Email]:
        """
        Get high-priority emails.

        Args:
            threshold: Minimum priority score
            limit: Maximum number to return

        Returns:
            List of high-priority emails
        """
        rows = self.db.fetchall(
            """
            SELECT * FROM emails
            WHERE priority_score >= ?
            ORDER BY priority_score DESC, timestamp DESC
            LIMIT ?
            """,
            (threshold, limit),
        )

        return [self._row_to_email(row) for row in rows]

    def update_priority_score(self, email_id: str, score: float) -> None:
        """
        Update priority score for an email.

        Args:
            email_id: Email ID
            score: New priority score (0.0 to 1.0)
        """
        self.db.execute(
            "UPDATE emails SET priority_score = ? WHERE id = ?",
            (score, email_id),
        )

        logger.debug("email_priority_updated", email_id=email_id, score=score)

    def mark_requires_response(self, email_id: str, requires: bool) -> None:
        """
        Mark email as requiring response.

        Args:
            email_id: Email ID
            requires: Whether response is required
        """
        self.db.execute(
            "UPDATE emails SET requires_response = ? WHERE id = ?",
            (requires, email_id),
        )

    def set_suggested_reply(self, email_id: str, reply: str) -> None:
        """
        Set AI-generated reply for an email.

        Args:
            email_id: Email ID
            reply: Suggested reply text
        """
        self.db.execute(
            "UPDATE emails SET suggested_reply = ? WHERE id = ?",
            (reply, email_id),
        )

    def get_count(self) -> int:
        """
        Get total number of emails in database.

        Returns:
            Email count
        """
        result = self.db.fetchone("SELECT COUNT(*) as count FROM emails")
        return result["count"] if result else 0

    def get_unread_count(self) -> int:
        """
        Get number of unread emails.

        Returns:
            Unread count
        """
        result = self.db.fetchone(
            "SELECT COUNT(*) as count FROM emails WHERE is_read = 0"
        )
        return result["count"] if result else 0

    def get_oldest_unread_timestamp(self) -> Optional[datetime]:
        """Return the timestamp of the oldest unread email, or None."""
        result = self.db.fetchone(
            "SELECT MIN(timestamp) as ts FROM emails WHERE is_read = 0"
        )
        if result and result["ts"]:
            return datetime.fromisoformat(result["ts"])
        return None

    def mark_as_read(self, email_id: str) -> None:
        """Mark a single email as read locally and in Gmail."""
        self.db.execute(
            "UPDATE emails SET is_read = 1, updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), email_id),
        )
        try:
            from src.integrations.gmail.client import GmailClient
            gmail = GmailClient()
            # Remove UNREAD and INBOX labels so email is read + archived
            gmail.modify_message(email_id, remove_label_ids=["UNREAD", "INBOX"])
        except Exception as e:
            logger.warning("gmail_mark_as_read_failed", email_id=email_id, error=str(e))

    def delete_old_emails(self, before: datetime) -> int:
        """
        Delete emails older than a specific date.

        Args:
            before: Delete emails before this date

        Returns:
            Number of emails deleted
        """
        cursor = self.db.execute(
            "DELETE FROM emails WHERE timestamp < ?",
            (before.isoformat(),),
        )

        count = cursor.rowcount
        logger.info("old_emails_deleted", count=count, before=before.isoformat())

        return count

    def _row_to_email(self, row) -> Email:
        """
        Convert database row to Email object.

        Args:
            row: SQLite row

        Returns:
            Email object
        """
        from src.models.email import EmailCategory
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
            metadata=json.loads(row["metadata"] or "{}"),
        )
