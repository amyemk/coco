"""
Gmail API Client

Wrapper around Google Gmail API for fetching and managing emails.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import base64
import email
from email.mime.text import MIMEText

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError
import structlog

from src.auth.google_oauth import get_oauth

logger = structlog.get_logger()


class GmailClient:
    """
    Gmail API client for email operations
    """

    def __init__(self, service: Optional[Resource] = None):
        """
        Initialize Gmail client.

        Args:
            service: Optional pre-configured Gmail API service.
                    If None, will get from OAuth.
        """
        self.service = service or get_oauth().get_gmail_service()
        logger.info("gmail_client_initialized")

    def get_profile(self) -> Dict[str, Any]:
        """
        Get the user's Gmail profile.

        Returns:
            Profile information including email address
        """
        try:
            profile = self.service.users().getProfile(userId="me").execute()
            logger.info("gmail_profile_retrieved", email=profile.get("emailAddress"))
            return profile
        except HttpError as e:
            logger.error("gmail_profile_error", error=str(e))
            raise

    def list_messages(
        self,
        query: str = "",
        max_results: int = 100,
        page_token: Optional[str] = None,
        label_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        List messages matching query.

        Args:
            query: Gmail search query (e.g., "is:unread", "from:example@gmail.com")
            max_results: Maximum number of messages to return
            page_token: Token for pagination
            label_ids: List of label IDs to filter by

        Returns:
            Dictionary with 'messages' list and optional 'nextPageToken'
        """
        try:
            params = {
                "userId": "me",
                "maxResults": max_results,
            }

            if query:
                params["q"] = query
            if page_token:
                params["pageToken"] = page_token
            if label_ids:
                params["labelIds"] = label_ids

            result = self.service.users().messages().list(**params).execute()

            message_count = len(result.get("messages", []))
            logger.info(
                "gmail_messages_listed",
                count=message_count,
                query=query,
                has_next_page=bool(result.get("nextPageToken")),
            )

            return result

        except HttpError as e:
            logger.error("gmail_list_messages_error", error=str(e), query=query)
            raise

    def get_message(
        self, message_id: str, format: str = "full"
    ) -> Dict[str, Any]:
        """
        Get a specific message by ID.

        Args:
            message_id: Gmail message ID
            format: Message format (full, metadata, minimal, raw)

        Returns:
            Message object with full details
        """
        try:
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format=format)
                .execute()
            )

            logger.debug("gmail_message_retrieved", message_id=message_id)
            return message

        except HttpError as e:
            logger.error("gmail_get_message_error", error=str(e), message_id=message_id)
            raise

    def get_thread(self, thread_id: str) -> Dict[str, Any]:
        """
        Get all messages in a thread.

        Args:
            thread_id: Gmail thread ID

        Returns:
            Thread object with all messages
        """
        try:
            thread = (
                self.service.users()
                .threads()
                .get(userId="me", id=thread_id, format="full")
                .execute()
            )

            message_count = len(thread.get("messages", []))
            logger.info(
                "gmail_thread_retrieved",
                thread_id=thread_id,
                message_count=message_count,
            )

            return thread

        except HttpError as e:
            logger.error("gmail_get_thread_error", error=str(e), thread_id=thread_id)
            raise

    def modify_message(
        self,
        message_id: str,
        add_label_ids: Optional[List[str]] = None,
        remove_label_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Modify message labels.

        Args:
            message_id: Gmail message ID
            add_label_ids: Labels to add
            remove_label_ids: Labels to remove

        Returns:
            Modified message
        """
        try:
            body = {}
            if add_label_ids:
                body["addLabelIds"] = add_label_ids
            if remove_label_ids:
                body["removeLabelIds"] = remove_label_ids

            message = (
                self.service.users()
                .messages()
                .modify(userId="me", id=message_id, body=body)
                .execute()
            )

            logger.info(
                "gmail_message_modified",
                message_id=message_id,
                added=add_label_ids,
                removed=remove_label_ids,
            )

            return message

        except HttpError as e:
            logger.error("gmail_modify_message_error", error=str(e), message_id=message_id)
            raise

    def mark_as_read(self, message_id: str) -> Dict[str, Any]:
        """
        Mark message as read.

        Args:
            message_id: Gmail message ID

        Returns:
            Modified message
        """
        return self.modify_message(message_id, remove_label_ids=["UNREAD"])

    def mark_as_unread(self, message_id: str) -> Dict[str, Any]:
        """
        Mark message as unread.

        Args:
            message_id: Gmail message ID

        Returns:
            Modified message
        """
        return self.modify_message(message_id, add_label_ids=["UNREAD"])

    def get_history(
        self, start_history_id: str, max_results: int = 100
    ) -> Dict[str, Any]:
        """
        Get history of changes since a specific history ID.
        Used for incremental sync.

        Args:
            start_history_id: History ID to start from
            max_results: Maximum number of history records

        Returns:
            History records
        """
        try:
            history = (
                self.service.users()
                .history()
                .list(
                    userId="me",
                    startHistoryId=start_history_id,
                    maxResults=max_results,
                )
                .execute()
            )

            logger.info(
                "gmail_history_retrieved",
                start_history_id=start_history_id,
                records=len(history.get("history", [])),
            )

            return history

        except HttpError as e:
            # 404 means history ID is too old
            if e.resp.status == 404:
                logger.warning(
                    "gmail_history_id_too_old",
                    start_history_id=start_history_id,
                )
                return {"history": []}

            logger.error("gmail_get_history_error", error=str(e))
            raise

    def send_message(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Send an email message.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body (plain text)
            cc: CC recipients
            bcc: BCC recipients

        Returns:
            Sent message
        """
        try:
            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject

            if cc:
                message["cc"] = ", ".join(cc)
            if bcc:
                message["bcc"] = ", ".join(bcc)

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

            sent_message = (
                self.service.users()
                .messages()
                .send(userId="me", body={"raw": raw_message})
                .execute()
            )

            logger.info("gmail_message_sent", to=to, subject=subject)
            return sent_message

        except HttpError as e:
            logger.error("gmail_send_message_error", error=str(e), to=to)
            raise

    def list_labels(self) -> List[Dict[str, Any]]:
        """
        List all labels.

        Returns:
            List of label objects
        """
        try:
            result = self.service.users().labels().list(userId="me").execute()
            labels = result.get("labels", [])

            logger.info("gmail_labels_listed", count=len(labels))
            return labels

        except HttpError as e:
            logger.error("gmail_list_labels_error", error=str(e))
            raise

    def get_messages_since(
        self, since: datetime, max_results: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Get all messages since a specific date.

        Args:
            since: Get messages after this date
            max_results: Maximum number of messages to return

        Returns:
            List of message IDs and thread IDs
        """
        # Convert datetime to Gmail query format
        query = f"after:{since.strftime('%Y/%m/%d')}"

        all_messages = []
        page_token = None

        while True:
            result = self.list_messages(
                query=query, max_results=min(100, max_results), page_token=page_token
            )

            messages = result.get("messages", [])
            all_messages.extend(messages)

            # Check if we've hit the limit
            if len(all_messages) >= max_results:
                all_messages = all_messages[:max_results]
                break

            # Check for next page
            page_token = result.get("nextPageToken")
            if not page_token:
                break

        logger.info(
            "gmail_messages_since_retrieved",
            since=since.isoformat(),
            count=len(all_messages),
        )

        return all_messages
