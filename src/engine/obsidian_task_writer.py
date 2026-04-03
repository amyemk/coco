"""
Obsidian Task Writer

Appends tasks to the Obsidian vault Backlog.md file in Obsidian Tasks plugin format.

Format:
  - [ ] Task title 📅 2026-04-04 #email #coco

All Coco-created tasks are tagged with the configured coco tag (#coco by default)
so they can be filtered in Obsidian independently of other tasks.
"""

import fcntl
from datetime import date
from pathlib import Path
from typing import Optional

import structlog

from src.config.settings import Settings
from src.models.email import ObsidianTask

logger = structlog.get_logger()

# Obsidian Tasks plugin emoji markers
_DUE_DATE_EMOJI = "📅"
_PRIORITY_HIGH = "⏫"
_PRIORITY_MEDIUM = "🔼"
_PRIORITY_LOW = "🔽"


class ObsidianTaskWriter:
    """
    Appends tasks to the Obsidian Backlog.md file using the Tasks plugin format.

    Writes are file-locked to prevent corruption if Coco ever runs concurrent jobs.
    Each task includes a source reference and the #coco tag for filtering.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._backlog_path = Path(settings.get_obsidian_backlog_path())
        self._coco_tag = settings.config.storage.obsidian_task_tag

    def write_task(self, task: ObsidianTask) -> bool:
        """
        Append a single task to the Obsidian backlog file.

        Args:
            task: The task to write

        Returns:
            True if written successfully, False on error
        """
        if not self.settings.config.features.obsidian_task_writing:
            logger.debug("obsidian_task_writing_disabled")
            return False

        if not self._backlog_path.parent.exists():
            logger.error(
                "obsidian_vault_not_found",
                path=str(self._backlog_path),
            )
            return False

        line = self.format_task(task)
        try:
            self._append_line(line)
            logger.info(
                "obsidian_task_written",
                title=task.title,
                path=str(self._backlog_path),
            )
            return True
        except Exception as e:
            logger.error("obsidian_write_error", error=str(e), path=str(self._backlog_path))
            return False

    def write_tasks(self, tasks: list[ObsidianTask]) -> int:
        """
        Append multiple tasks. Returns number successfully written.
        """
        written = 0
        for task in tasks:
            if self.write_task(task):
                written += 1
        return written

    def format_task(self, task: ObsidianTask) -> str:
        """
        Format a task as an Obsidian Tasks plugin checkbox line.

        Example output:
          - [ ] Reply to Sarah Chen re: Budget sign-off 📅 2026-04-04 #email #coco
        """
        parts = [f"- [ ] {task.title}"]

        if task.due_date:
            parts.append(f"{_DUE_DATE_EMOJI} {task.due_date.isoformat()}")

        # Add tags — ensure #coco is always present
        tags = list(task.tags)
        coco_tag = self._coco_tag.lstrip("#")
        if coco_tag not in [t.lstrip("#") for t in tags]:
            tags.append(self._coco_tag)

        # Normalise tag format (ensure # prefix)
        normalised_tags = [t if t.startswith("#") else f"#{t}" for t in tags]
        parts.append(" ".join(normalised_tags))

        line = " ".join(parts)

        # Append source reference as a Obsidian comment (not shown in task view)
        if task.source_ref:
            line += f"\n  <!-- source: {task.source_ref} -->"

        return line

    def _append_line(self, line: str) -> None:
        """Append a line to the backlog file with a file lock."""
        # Create file if it doesn't exist
        self._backlog_path.touch(exist_ok=True)

        with open(self._backlog_path, "a", encoding="utf-8") as f:
            # File-level lock so concurrent writes don't corrupt the file
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                # Ensure we start on a new line
                f.seek(0, 2)  # seek to end
                pos = f.tell()
                if pos > 0:
                    f.seek(pos - 1)
                    last_char = f.read(1)
                    if last_char != "\n":
                        f.write("\n")
                f.write(line + "\n")
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


def make_task_from_email(
    title: str,
    email_id: str,
    from_address: str,
    subject: Optional[str],
    due_date: Optional[date] = None,
    extra_tags: Optional[list[str]] = None,
) -> ObsidianTask:
    """
    Convenience constructor for email-sourced tasks.

    Args:
        title: Task description
        email_id: Gmail message ID (for reference)
        from_address: Sender email address
        subject: Email subject line
        due_date: Optional due date inferred from email content
        extra_tags: Additional tags (e.g. ["budget", "hiring"])

    Returns:
        ObsidianTask ready to be written
    """
    tags = ["email"] + (extra_tags or [])
    source_ref = f"email from {from_address}"
    if subject:
        source_ref += f' re: "{subject}"'

    return ObsidianTask(
        title=title,
        due_date=due_date,
        tags=tags,
        source_ref=source_ref,
        email_id=email_id,
    )
