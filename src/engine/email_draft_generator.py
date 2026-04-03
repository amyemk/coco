"""
Email Draft Generator

Generates three reply options for ACTION_REQUIRED emails:
  1. short_ack  — Brief acknowledgement, buys time
  2. full_reply — Substantive response addressing key points
  3. decline    — Polite decline, defer, or redirect

Uses thread context to avoid repeating what's already been said,
and tone-matches to the user's configured communication style.
"""

import json
from typing import List, Optional

import structlog

from src.ai.claude_client import ClaudeClient
from src.ai.prompts.draft import build_draft_prompt
from src.config.settings import Settings
from src.models.email import DraftOption, Email, EmailDraftSet

logger = structlog.get_logger()

_MAX_THREAD_CHARS = 4000  # Truncation limit for thread context


class EmailDraftGenerator:
    """
    Generates three draft reply options for a given email thread.

    Thread context is included so Claude doesn't repeat information
    already stated or ask questions already answered.
    """

    def __init__(self, settings: Settings, claude_client: ClaudeClient):
        self.settings = settings
        self.claude = claude_client
        self._model = settings.config.ai.models.email_draft

    async def generate(
        self,
        email: Email,
        thread: Optional[List[Email]] = None,
    ) -> EmailDraftSet:
        """
        Generate three draft reply options for an email.

        Args:
            email: The email to reply to
            thread: Full thread context (oldest first). If None, uses email alone.

        Returns:
            EmailDraftSet with 3 draft options
        """
        thread = thread or [email]
        thread_text = self._format_thread(thread)
        user = self.settings.config.user

        system_prompt, user_prompt = build_draft_prompt(
            thread_text=thread_text,
            from_address=email.from_address,
            subject=email.subject or "",
            tone=user.communication.tone,
            style=user.communication.style,
            signature=user.communication.signature.strip(),
        )

        try:
            raw = await self.claude.complete_json(
                prompt=user_prompt,
                model=self._model,
                system=system_prompt,
            )
            data = json.loads(raw)
            options = [
                DraftOption(
                    style=opt["style"],
                    subject=opt["subject"],
                    body=opt["body"],
                )
                for opt in data.get("options", [])
            ]
            thread_summary = data.get("thread_summary", "")
        except Exception as e:
            logger.error("draft_generation_failed", email_id=email.id, error=str(e))
            options = self._fallback_options(email)
            thread_summary = f"(Draft generation failed: {e})"

        logger.info(
            "email_draft_generated",
            email_id=email.id,
            options=len(options),
        )

        return EmailDraftSet(
            original_email_id=email.id,
            options=options,
            thread_summary=thread_summary,
        )

    def _format_thread(self, thread: List[Email]) -> str:
        """
        Format a thread as a readable conversation for the prompt.
        Oldest emails first. Truncated if too long.
        """
        parts = []
        for email in thread:
            ts = email.timestamp.strftime("%Y-%m-%d %H:%M")
            header = f"[{ts}] From: {email.from_address}"
            if email.subject:
                header += f" | Subject: {email.subject}"
            body = (email.body or email.snippet or "").strip()
            parts.append(f"{header}\n{body}")

        full = "\n\n---\n\n".join(parts)

        if len(full) > _MAX_THREAD_CHARS:
            # Keep the most recent messages (end of thread is most relevant)
            full = "... [earlier thread truncated]\n\n---\n\n" + full[-_MAX_THREAD_CHARS:]

        return full

    def _fallback_options(self, email: Email) -> List[DraftOption]:
        """Return placeholder options when Claude fails."""
        subject = f"Re: {email.subject or '(no subject)'}"
        return [
            DraftOption(
                style="short_ack",
                subject=subject,
                body="Thanks for your message — I'll follow up shortly.",
            ),
            DraftOption(
                style="full_reply",
                subject=subject,
                body="[Draft generation failed — please write this reply manually.]",
            ),
            DraftOption(
                style="decline",
                subject=subject,
                body="Thanks for reaching out. I'm not able to take this on right now, but I'll keep it in mind.",
            ),
        ]
