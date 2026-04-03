"""
Triage Notification Email

Sends a short plain-text notification email when pre-processing completes,
so you know a triage session is ready without having to check manually.

Example email:
    Subject: Coco – Triage ready (noon) · 14 emails

    Processed 14 emails since midnight:
      · 5 junk (suggest delete/unsubscribe)
      · 3 newsletters (2 unique stories)
      · 4 system notifications (2 need your approval)
      · 2 action required (drafts + tasks ready)

    Open Claude Code and say "let's triage" to start.
"""

import base64
from email.mime.text import MIMEText

import structlog

from src.config.settings import Settings
from src.triage.pre_processor import TriageSessionResult

logger = structlog.get_logger()


class TriageNotificationSender:
    """
    Sends the "triage ready" notification via the Gmail API.
    Uses the same OAuth credentials already configured — no SMTP needed.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, result: TriageSessionResult) -> bool:
        """
        Send a notification email summarising the pre-processing run.

        Args:
            result: The completed TriageSessionResult

        Returns:
            True if sent successfully
        """
        if not self.settings.config.triage.notification_email.enabled:
            logger.debug("triage_notification_disabled")
            return False

        recipient = self.settings.config.triage.notification_email.recipient
        if not recipient:
            recipient = self.settings.config.user.email

        subject = self._build_subject(result)
        body = self._build_body(result)

        try:
            from src.integrations.gmail.client import GmailClient
            gmail = GmailClient()
            gmail.send_message(
                to=recipient,
                subject=subject,
                body=body,
            )
            logger.info(
                "triage_notification_sent",
                recipient=recipient,
                run_type=result.run_type,
                total=result.total_processed,
            )
            return True
        except Exception as e:
            logger.error("triage_notification_failed", error=str(e))
            return False

    def _build_subject(self, result: TriageSessionResult) -> str:
        run_label = "noon" if result.run_type == "noon" else "4pm"
        return f"Coco – Triage ready ({run_label}) · {result.total_processed} emails"

    def _build_body(self, result: TriageSessionResult) -> str:
        run_label = "noon" if result.run_type == "noon" else "4pm"
        since_label = (
            "midnight" if result.run_type == "noon"
            else result.window_start.strftime("%-I:%M %p")
        )

        lines = [
            f"Processed {result.total_processed} email{'s' if result.total_processed != 1 else ''} since {since_label}:",
            "",
        ]

        if result.junk:
            lines.append(f"  · {len(result.junk)} junk (suggest delete/unsubscribe)")

        if result.newsletter_summaries:
            story_count = (
                len(result.newsletter_digest.stories)
                if result.newsletter_digest
                else len(result.newsletter_summaries)
            )
            lines.append(
                f"  · {len(result.newsletter_summaries)} newsletters ({story_count} unique {'story' if story_count == 1 else 'stories'})"
            )

        if result.system_notifications:
            action_count = sum(1 for n in result.system_notifications if n.requires_action)
            fyi_count = len(result.system_notifications) - action_count
            parts = []
            if action_count:
                parts.append(f"{action_count} need your approval")
            if fyi_count:
                parts.append(f"{fyi_count} FYI")
            detail = f" ({', '.join(parts)})" if parts else ""
            lines.append(f"  · {len(result.system_notifications)} system notifications{detail}")

        if result.actions:
            lines.append(f"  · {len(result.actions)} action required (drafts + tasks ready)")

        if result.eod_urgent_email_ids:
            lines.append(
                f"\n⚠️  {len(result.eod_urgent_email_ids)} item{'s' if len(result.eod_urgent_email_ids) != 1 else ''} flagged as EOD-urgent."
            )

        if result.total_processed == 0:
            lines = ["No new emails to triage in this window."]
        else:
            lines += [
                "",
                'Open Claude Code and say "let\'s triage" to start.',
            ]

        return "\n".join(lines)
