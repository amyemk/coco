"""
Gmail Draft Saver

Saves confirmed email drafts to the Gmail Drafts folder via the API.
No SMTP credentials required — uses the existing OAuth service.

Drafts appear in Gmail's Drafts folder and can be reviewed, edited,
and sent from any Gmail client. Nothing is sent automatically.
"""

import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import structlog

from src.config.settings import Settings
from src.models.email import DraftOption

logger = structlog.get_logger()


class GmailDraftSaver:
    """
    Creates Gmail drafts from DraftOption objects using the Gmail API.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def save_draft(
        self,
        draft_option: DraftOption,
        to_address: str,
        thread_id: Optional[str] = None,
        in_reply_to_message_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Save a draft reply to Gmail Drafts.

        Args:
            draft_option: The draft to save (subject + body)
            to_address: The recipient email address
            thread_id: Gmail thread ID to attach the draft to
            in_reply_to_message_id: Gmail message ID being replied to

        Returns:
            Gmail draft ID if successful, None on failure
        """
        if not self.settings.config.features.gmail_draft_saving:
            logger.debug("gmail_draft_saving_disabled")
            return None

        try:
            from src.auth.google_oauth import get_oauth
            service = get_oauth().get_gmail_service()

            mime_message = self._build_mime(
                to_address=to_address,
                from_address=self.settings.config.user.email,
                subject=draft_option.subject,
                body=draft_option.body,
                in_reply_to=in_reply_to_message_id,
            )

            raw = base64.urlsafe_b64encode(mime_message.as_bytes()).decode("utf-8")
            draft_body: dict = {"message": {"raw": raw}}
            if thread_id:
                draft_body["message"]["threadId"] = thread_id

            draft = service.users().drafts().create(userId="me", body=draft_body).execute()
            draft_id = draft.get("id")

            logger.info(
                "gmail_draft_saved",
                draft_id=draft_id,
                to=to_address,
                subject=draft_option.subject,
                style=draft_option.style,
            )
            return draft_id

        except Exception as e:
            logger.error("gmail_draft_save_failed", error=str(e), to=to_address)
            return None

    def _build_mime(
        self,
        to_address: str,
        from_address: str,
        subject: str,
        body: str,
        in_reply_to: Optional[str] = None,
    ) -> MIMEText:
        message = MIMEText(body, "plain", "utf-8")
        message["To"] = to_address
        message["From"] = from_address
        message["Subject"] = subject
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
            message["References"] = in_reply_to
        return message
