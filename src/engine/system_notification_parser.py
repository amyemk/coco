"""
System Notification Parser

Parses structured notifications from Digital Science business systems:
Concur, SAP, Bob/HiBob, Asana — using regex patterns before any Claude call.

This keeps costs near-zero for system emails while still producing
clean, structured data for the triage session.
"""

import re
from datetime import date, datetime
from typing import Optional

import structlog

from src.models.email import Email, SystemNotification

logger = structlog.get_logger()


class SystemNotificationParser:
    """
    Pattern-based parser for DS system notification emails.

    Falls back gracefully: if no pattern matches, returns a generic
    SystemNotification derived from subject + sender.
    """

    def parse(self, email: Email) -> SystemNotification:
        """
        Parse a system notification email into structured data.

        Args:
            email: An email already classified as SYSTEM_NOTIFICATION

        Returns:
            Structured SystemNotification
        """
        from_lower = email.from_address.lower()
        subject = email.subject or ""
        body = email.body or ""

        if self._is_concur(from_lower):
            return self._parse_concur(email, subject, body)
        if self._is_sap(from_lower):
            return self._parse_sap(email, subject, body)
        if self._is_bob(from_lower):
            return self._parse_bob(email, subject, body)
        if self._is_asana(from_lower):
            return self._parse_asana(email, subject, body)

        return self._parse_generic(email, subject)

    # -------------------------------------------------------------------------
    # System detection
    # -------------------------------------------------------------------------

    def _is_concur(self, from_lower: str) -> bool:
        return "concur" in from_lower or "concursolutions" in from_lower

    def _is_sap(self, from_lower: str) -> bool:
        return "sap.com" in from_lower and "concur" not in from_lower

    def _is_bob(self, from_lower: str) -> bool:
        return "hibob" in from_lower or "bob.com" in from_lower

    def _is_asana(self, from_lower: str) -> bool:
        return "asana" in from_lower

    # -------------------------------------------------------------------------
    # Concur
    # -------------------------------------------------------------------------

    def _parse_concur(self, email: Email, subject: str, body: str) -> SystemNotification:
        subject_lower = subject.lower()
        body_lower = body.lower()

        # Extract reference number
        ref = self._extract_pattern(
            r"(?:report|expense|EXP)[- ]?(?:#\s*)?([A-Z0-9\-]{4,})", subject + " " + body[:500]
        )

        # Determine action type and status
        if "approval" in subject_lower or "approve" in subject_lower:
            action_type = "approval_required"
            status = "pending_approval"
            requires_action = True
            summary = f"Expense report {ref or ''} pending your approval in Concur"
        elif "approved" in subject_lower:
            action_type = "status_update"
            status = "approved"
            requires_action = False
            summary = f"Expense report {ref or ''} has been approved"
        elif "rejected" in subject_lower or "returned" in subject_lower:
            action_type = "status_update"
            status = "rejected"
            requires_action = True
            summary = f"Expense report {ref or ''} was rejected and needs attention"
        elif "submitted" in subject_lower:
            action_type = "status_update"
            status = "submitted"
            requires_action = False
            summary = f"Expense report {ref or ''} was submitted"
        else:
            action_type = "status_update"
            status = "unknown"
            requires_action = False
            summary = subject

        deep_link = self._extract_url(body)

        return SystemNotification(
            email_id=email.id,
            system="Concur",
            action_type=action_type,
            entity_name=ref or subject,
            status=status,
            deadline=None,
            requires_action=requires_action,
            deep_link=deep_link,
            raw_summary=summary,
        )

    # -------------------------------------------------------------------------
    # SAP
    # -------------------------------------------------------------------------

    def _parse_sap(self, email: Email, subject: str, body: str) -> SystemNotification:
        subject_lower = subject.lower()

        ref = self._extract_pattern(
            r"(?:PO|order|invoice|document)[:\s#-]*([A-Z0-9\-]{4,})",
            subject + " " + body[:500],
        )

        if "approval" in subject_lower or "approve" in subject_lower:
            action_type = "approval_required"
            status = "pending_approval"
            requires_action = True
            summary = f"SAP workflow requires your approval: {ref or subject}"
        elif "invoice" in subject_lower:
            action_type = "invoice"
            status = "received"
            requires_action = True
            summary = f"SAP invoice {ref or ''} received"
        else:
            action_type = "status_update"
            status = "unknown"
            requires_action = False
            summary = subject

        return SystemNotification(
            email_id=email.id,
            system="SAP",
            action_type=action_type,
            entity_name=ref or subject,
            status=status,
            requires_action=requires_action,
            raw_summary=summary,
        )

    # -------------------------------------------------------------------------
    # Bob / HiBob
    # -------------------------------------------------------------------------

    def _parse_bob(self, email: Email, subject: str, body: str) -> SystemNotification:
        subject_lower = subject.lower()

        if "leave" in subject_lower or "time off" in subject_lower:
            name = self._extract_name_from_body(body)
            if "request" in subject_lower or "submitted" in subject_lower:
                action_type = "leave_request"
                status = "pending_approval"
                requires_action = True
                summary = f"Leave request from {name or 'a team member'} needs approval in Bob"
            else:
                action_type = "leave_update"
                status = "updated"
                requires_action = False
                summary = f"Leave update for {name or 'a team member'}"
        elif "new" in subject_lower and ("employee" in subject_lower or "joiner" in subject_lower or "hire" in subject_lower):
            name = self._extract_name_from_body(body)
            action_type = "new_joiner"
            status = "onboarding"
            requires_action = False
            summary = f"New team member {name or ''} joining — update Bob profile if needed"
        elif "policy" in subject_lower:
            action_type = "policy_update"
            status = "updated"
            requires_action = False
            summary = f"Bob policy update: {subject}"
        elif "birthday" in subject_lower or "anniversary" in subject_lower:
            action_type = "celebration"
            status = "reminder"
            requires_action = False
            summary = subject
        else:
            action_type = "status_update"
            status = "unknown"
            requires_action = False
            summary = subject

        return SystemNotification(
            email_id=email.id,
            system="Bob",
            action_type=action_type,
            entity_name=self._extract_name_from_body(body) or subject,
            status=status,
            requires_action=requires_action,
            raw_summary=summary,
        )

    # -------------------------------------------------------------------------
    # Asana
    # -------------------------------------------------------------------------

    def _parse_asana(self, email: Email, subject: str, body: str) -> SystemNotification:
        subject_lower = subject.lower()

        # Extract task/project name — Asana subjects are usually well-structured
        task_name = self._extract_pattern(r"(?:Task:|Re:)\s*(.+?)(?:\s*-\s*|$)", subject)
        if not task_name:
            task_name = subject

        # Detect due date from body
        due_date = self._extract_date(body)

        if "assigned" in subject_lower:
            action_type = "task_assigned"
            status = "assigned"
            requires_action = True
            summary = f"Asana task assigned to you: {task_name}"
        elif "due" in subject_lower or "overdue" in subject_lower:
            action_type = "deadline"
            status = "due_soon" if "due" in subject_lower else "overdue"
            requires_action = True
            summary = f"Asana task due: {task_name}"
        elif "completed" in subject_lower or "done" in subject_lower:
            action_type = "task_completed"
            status = "completed"
            requires_action = False
            summary = f"Asana task completed: {task_name}"
        elif "comment" in subject_lower or "mentioned" in subject_lower:
            action_type = "mention"
            status = "mentioned"
            requires_action = True
            summary = f"You were mentioned in Asana: {task_name}"
        elif "project" in subject_lower:
            action_type = "project_update"
            status = "updated"
            requires_action = False
            summary = f"Asana project update: {task_name}"
        else:
            action_type = "status_update"
            status = "unknown"
            requires_action = False
            summary = subject

        deep_link = self._extract_url(body)

        return SystemNotification(
            email_id=email.id,
            system="Asana",
            action_type=action_type,
            entity_name=task_name,
            status=status,
            deadline=due_date,
            requires_action=requires_action,
            deep_link=deep_link,
            raw_summary=summary,
        )

    # -------------------------------------------------------------------------
    # Generic fallback
    # -------------------------------------------------------------------------

    def _parse_generic(self, email: Email, subject: str) -> SystemNotification:
        return SystemNotification(
            email_id=email.id,
            system="Other",
            action_type="status_update",
            entity_name=subject,
            status="unknown",
            requires_action=False,
            raw_summary=subject,
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _extract_pattern(self, pattern: str, text: str) -> Optional[str]:
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _extract_url(self, body: str) -> Optional[str]:
        match = re.search(r"https://[^\s\"'<>]+", body)
        return match.group(0) if match else None

    def _extract_name_from_body(self, body: str) -> Optional[str]:
        # Look for patterns like "Hi [Name]" or "for [First Last]"
        match = re.search(r"(?:for|about|from)\s+([A-Z][a-z]+ [A-Z][a-z]+)", body)
        return match.group(1) if match else None

    def _extract_date(self, text: str) -> Optional[date]:
        patterns = [
            r"(\d{4}-\d{2}-\d{2})",           # 2026-04-03
            r"(\w+ \d{1,2},?\s+\d{4})",        # April 3, 2026
            r"(\d{1,2}/\d{1,2}/\d{2,4})",      # 4/3/2026
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    raw = match.group(1)
                    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%B %d %Y", "%m/%d/%Y", "%m/%d/%y"):
                        try:
                            return datetime.strptime(raw, fmt).date()
                        except ValueError:
                            continue
                except Exception:
                    pass
        return None


def aggregate_notifications(notifications: list[SystemNotification]) -> str:
    """
    Produce a single human-readable paragraph summarising all system notifications.
    Used in the triage session to present system emails as one block.

    Example output:
      "3 items need your attention: 2 expense reports pending approval in Concur
       (EXP-2891, EXP-2892), and 1 leave request from Alex Kim in Bob."
    """
    if not notifications:
        return "No system notifications."

    action_items = [n for n in notifications if n.requires_action]
    info_items = [n for n in notifications if not n.requires_action]

    parts = []

    if action_items:
        by_system: dict[str, list[SystemNotification]] = {}
        for n in action_items:
            by_system.setdefault(n.system, []).append(n)

        system_parts = []
        for system, items in by_system.items():
            if len(items) == 1:
                system_parts.append(items[0].raw_summary)
            else:
                refs = ", ".join(i.entity_name for i in items[:3])
                system_parts.append(f"{len(items)} items in {system} ({refs})")

        action_text = "; ".join(system_parts)
        parts.append(f"{len(action_items)} item{'s' if len(action_items) > 1 else ''} need your attention: {action_text}.")

    if info_items:
        info_text = "; ".join(n.raw_summary for n in info_items[:3])
        if len(info_items) > 3:
            info_text += f" (+{len(info_items) - 3} more)"
        parts.append(f"FYI: {info_text}.")

    return " ".join(parts)
