"""
Action Processor

Orchestrates processing of ACTION_REQUIRED emails:
  1. Detects whether the email needs a reply, a task, or both
  2. Generates draft replies (3 options) when needed
  3. Creates Obsidian tasks when needed

This is the main entry point for the action email category during
the triage pre-processing run.
"""

import json
from datetime import date, datetime
from typing import List, Optional

import structlog

from src.ai.claude_client import ClaudeClient
from src.ai.prompts.draft import build_action_detection_prompt, ACTION_DETECTION_SYSTEM
from src.config.settings import Settings
from src.engine.email_draft_generator import EmailDraftGenerator
from src.engine.obsidian_task_writer import ObsidianTaskWriter, make_task_from_email
from src.models.email import ActionPlan, Email, ObsidianTask

logger = structlog.get_logger()


class ActionProcessor:
    """
    Processes ACTION_REQUIRED emails into drafts and/or Obsidian tasks.

    Called during the pre-processing triage run. Results are held in memory
    and presented during the interactive triage session.
    """

    def __init__(
        self,
        settings: Settings,
        claude_client: ClaudeClient,
    ):
        self.settings = settings
        self.claude = claude_client
        self._draft_generator = EmailDraftGenerator(settings, claude_client)
        self._task_writer = ObsidianTaskWriter(settings)
        self._model = settings.config.ai.models.classification  # Haiku is fine for detection

    async def process(
        self,
        email: Email,
        thread: Optional[List[Email]] = None,
    ) -> ActionPlan:
        """
        Analyse an action email and produce a plan (drafts + task).

        Args:
            email: An email classified as ACTION_REQUIRED
            thread: Full email thread for draft context

        Returns:
            ActionPlan with draft_set and/or task populated
        """
        # Step 1: Detect what kind of action is needed
        detection = await self._detect_action(email)
        action_type = detection.get("action_type", "both")
        needs_reply = detection.get("needs_reply", True)
        needs_task = detection.get("needs_task", False)
        task_title = detection.get("task_title")
        task_due_str = detection.get("task_due_date")
        task_tags = detection.get("task_tags", [])

        # Ensure action_type is valid
        if action_type not in ("reply_only", "task_only", "both"):
            action_type = "both"

        # Step 2: Generate draft if needed
        draft_set = None
        if needs_reply and self.settings.config.features.email_draft_generation:
            draft_set = await self._draft_generator.generate(email, thread)

        # Step 3: Build task if needed
        task = None
        if needs_task:
            due_date = self._parse_date(task_due_str)
            task = make_task_from_email(
                title=task_title or f"Action: {email.subject or 'email from ' + email.from_address}",
                email_id=email.id,
                from_address=email.from_address,
                subject=email.subject,
                due_date=due_date,
                extra_tags=task_tags,
            )

        logger.info(
            "action_processed",
            email_id=email.id,
            action_type=action_type,
            has_draft=draft_set is not None,
            has_task=task is not None,
        )

        return ActionPlan(
            email_id=email.id,
            action_type=action_type,
            draft_set=draft_set,
            task=task,
        )

    async def process_batch(
        self,
        emails: List[Email],
        threads: Optional[dict[str, List[Email]]] = None,
    ) -> List[ActionPlan]:
        """
        Process multiple action emails. threads maps thread_id → email list.
        """
        plans = []
        for email in emails:
            thread = (threads or {}).get(email.thread_id)
            try:
                plan = await self.process(email, thread)
                plans.append(plan)
            except Exception as e:
                logger.error("action_process_error", email_id=email.id, error=str(e))
        return plans

    def write_task_to_obsidian(self, task: ObsidianTask) -> bool:
        """
        Write a confirmed task to the Obsidian vault.
        Called during the triage session when the user confirms.
        """
        return self._task_writer.write_task(task)

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    async def _detect_action(self, email: Email) -> dict:
        """
        Ask Claude to determine what kind of action this email requires.
        Returns parsed JSON dict.
        """
        prompt = build_action_detection_prompt(
            from_address=email.from_address,
            subject=email.subject or "",
            body=email.body or email.snippet or "",
        )
        try:
            raw = await self.claude.complete_json(
                prompt=prompt,
                model=self._model,
                system=ACTION_DETECTION_SYSTEM,
            )
            return json.loads(raw)
        except Exception as e:
            logger.warning("action_detection_failed", email_id=email.id, error=str(e))
            # Safe default: treat as needs-reply
            return {
                "action_type": "reply_only",
                "needs_reply": True,
                "needs_task": False,
                "task_title": None,
                "task_due_date": None,
                "task_tags": [],
            }

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None
