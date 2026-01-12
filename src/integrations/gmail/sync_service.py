"""
Gmail Sync Service

Manages synchronization of emails from Gmail to local database.
"""

from typing import List, Optional
from datetime import datetime, timedelta

import structlog

from src.integrations.gmail.client import GmailClient
from src.integrations.gmail.parser import GmailParser
from src.repositories.email_repository import EmailRepository
from src.models.email import Email
from src.db.connection import get_db

logger = structlog.get_logger()


class GmailSyncService:
    """
    Service for syncing Gmail emails to database
    """

    def __init__(
        self,
        client: Optional[GmailClient] = None,
        repository: Optional[EmailRepository] = None,
    ):
        """
        Initialize Gmail sync service.

        Args:
            client: Gmail API client (creates new if None)
            repository: Email repository (creates new if None)
        """
        self.client = client or GmailClient()
        self.repository = repository or EmailRepository()
        self.parser = GmailParser()
        self.db = get_db()

    def initial_sync(self, days_back: int = 30, max_emails: int = 500) -> int:
        """
        Perform initial sync of emails from the last N days.

        Args:
            days_back: Number of days to sync back
            max_emails: Maximum number of emails to sync

        Returns:
            Number of emails synced
        """
        logger.info(
            "gmail_initial_sync_started",
            days_back=days_back,
            max_emails=max_emails,
        )

        # Calculate start date
        since = datetime.now() - timedelta(days=days_back)

        # Get messages from Gmail
        gmail_messages = self.client.get_messages_since(since, max_results=max_emails)

        logger.info(
            "gmail_messages_fetched",
            count=len(gmail_messages),
            since=since.isoformat(),
        )

        # Fetch full details and parse each message
        synced_count = 0

        for i, msg_ref in enumerate(gmail_messages, 1):
            try:
                # Get full message details
                message_id = msg_ref["id"]
                full_message = self.client.get_message(message_id)

                # Parse message
                parsed_data = self.parser.parse_message(full_message)

                # Convert to Email model
                email = Email(**parsed_data)

                # Save to database
                self.repository.save(email)

                synced_count += 1

                if i % 50 == 0:
                    logger.info("gmail_sync_progress", synced=i, total=len(gmail_messages))

            except Exception as e:
                logger.error(
                    "gmail_sync_message_error",
                    error=str(e),
                    message_id=msg_ref.get("id", "unknown"),
                )

        # Update sync status
        self._update_sync_status(
            status="success",
            items_synced=synced_count,
            error_message=None,
        )

        logger.info("gmail_initial_sync_complete", count=synced_count)

        return synced_count

    def incremental_sync(self) -> int:
        """
        Perform incremental sync using Gmail history API.
        Only fetches changes since last sync.

        Returns:
            Number of emails updated
        """
        logger.info("gmail_incremental_sync_started")

        # Get last sync info
        last_sync = self._get_last_sync_status()

        if not last_sync or not last_sync.get("metadata"):
            logger.warning("no_previous_sync_running_initial_sync")
            return self.initial_sync()

        # Get history ID from last sync
        metadata = last_sync.get("metadata", {})
        start_history_id = metadata.get("history_id")

        if not start_history_id:
            logger.warning("no_history_id_running_initial_sync")
            return self.initial_sync()

        # Get changes from Gmail
        try:
            history = self.client.get_history(start_history_id)
        except Exception as e:
            logger.error("gmail_history_fetch_error", error=str(e))
            # Fall back to time-based sync
            since = datetime.fromisoformat(last_sync["last_sync_time"])
            return self._sync_since(since)

        history_records = history.get("history", [])

        if not history_records:
            logger.info("gmail_no_changes_since_last_sync")
            self._update_sync_status(status="success", items_synced=0)
            return 0

        # Collect all affected message IDs
        message_ids = set()

        for record in history_records:
            # Messages added
            for msg in record.get("messagesAdded", []):
                message_ids.add(msg["message"]["id"])

            # Messages deleted
            for msg in record.get("messagesDeleted", []):
                # Note: We could delete these from our DB
                # For now, we'll just log
                logger.debug("message_deleted", message_id=msg["message"]["id"])

            # Labels added/removed
            for msg in record.get("labelsAdded", []):
                message_ids.add(msg["message"]["id"])

            for msg in record.get("labelsRemoved", []):
                message_ids.add(msg["message"]["id"])

        # Fetch and update affected messages
        synced_count = 0

        for message_id in message_ids:
            try:
                full_message = self.client.get_message(message_id)
                parsed_data = self.parser.parse_message(full_message)
                email = Email(**parsed_data)
                self.repository.save(email)
                synced_count += 1

            except Exception as e:
                logger.error(
                    "gmail_incremental_sync_message_error",
                    error=str(e),
                    message_id=message_id,
                )

        # Update sync status
        self._update_sync_status(
            status="success",
            items_synced=synced_count,
            metadata={"history_id": history.get("historyId")},
        )

        logger.info("gmail_incremental_sync_complete", count=synced_count)

        return synced_count

    def _sync_since(self, since: datetime, max_emails: int = 100) -> int:
        """
        Sync emails since a specific datetime.
        Fallback when history API fails.

        Args:
            since: Sync emails after this time
            max_emails: Maximum number to sync

        Returns:
            Number of emails synced
        """
        gmail_messages = self.client.get_messages_since(since, max_results=max_emails)

        synced_count = 0

        for msg_ref in gmail_messages:
            try:
                message_id = msg_ref["id"]
                full_message = self.client.get_message(message_id)
                parsed_data = self.parser.parse_message(full_message)
                email = Email(**parsed_data)
                self.repository.save(email)
                synced_count += 1

            except Exception as e:
                logger.error(
                    "gmail_sync_since_error",
                    error=str(e),
                    message_id=msg_ref.get("id"),
                )

        return synced_count

    def sync_thread(self, thread_id: str) -> int:
        """
        Sync a specific email thread.

        Args:
            thread_id: Gmail thread ID

        Returns:
            Number of messages synced
        """
        logger.info("gmail_thread_sync_started", thread_id=thread_id)

        try:
            # Get thread from Gmail
            thread = self.client.get_thread(thread_id)

            # Parse all messages in thread
            parsed_messages = self.parser.parse_thread(thread)

            # Save all messages
            synced_count = 0
            for parsed_data in parsed_messages:
                email = Email(**parsed_data)
                self.repository.save(email)
                synced_count += 1

            logger.info("gmail_thread_synced", thread_id=thread_id, count=synced_count)

            return synced_count

        except Exception as e:
            logger.error("gmail_thread_sync_error", error=str(e), thread_id=thread_id)
            return 0

    def _get_last_sync_status(self) -> Optional[dict]:
        """
        Get the last sync status from database.

        Returns:
            Last sync status or None
        """
        import json

        row = self.db.fetchone(
            """
            SELECT * FROM sync_status
            WHERE source = 'gmail'
            ORDER BY last_sync_time DESC
            LIMIT 1
            """
        )

        if row:
            return {
                "last_sync_time": row["last_sync_time"],
                "last_sync_status": row["last_sync_status"],
                "items_synced": row["items_synced"],
                "error_message": row["error_message"],
                "metadata": json.loads(row["metadata"] or "{}"),
            }

        return None

    def _update_sync_status(
        self,
        status: str,
        items_synced: int,
        error_message: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Update sync status in database.

        Args:
            status: Sync status (success, failure, partial)
            items_synced: Number of items synced
            error_message: Error message if failed
            metadata: Additional metadata (e.g., history_id)
        """
        import json

        # Get current history ID from profile if not provided
        if not metadata or "history_id" not in metadata:
            try:
                profile = self.client.get_profile()
                metadata = metadata or {}
                metadata["history_id"] = profile.get("historyId")
            except Exception as e:
                logger.warning("failed_to_get_history_id", error=str(e))

        self.db.execute(
            """
            INSERT INTO sync_status (
                source, last_sync_time, last_sync_status,
                items_synced, error_message, metadata
            ) VALUES (?, datetime('now'), ?, ?, ?, ?)
            """,
            (
                "gmail",
                status,
                items_synced,
                error_message,
                json.dumps(metadata or {}),
            ),
        )

        logger.debug("gmail_sync_status_updated", status=status, items=items_synced)

    def get_sync_stats(self) -> dict:
        """
        Get synchronization statistics.

        Returns:
            Dictionary with sync stats
        """
        total_emails = self.repository.get_count()
        unread_count = self.repository.get_unread_count()
        last_sync = self._get_last_sync_status()

        stats = {
            "total_emails": total_emails,
            "unread_count": unread_count,
            "last_sync_time": last_sync["last_sync_time"] if last_sync else None,
            "last_sync_status": last_sync["last_sync_status"] if last_sync else None,
            "last_items_synced": last_sync["items_synced"] if last_sync else 0,
        }

        return stats
