"""
Google Calendar Event Parser

Parses Google Calendar API event format into our internal CalendarEvent model.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import re

import structlog

logger = structlog.get_logger()


class CalendarParser:
    """
    Parser for Google Calendar API events
    """

    @staticmethod
    def parse_event(calendar_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Google Calendar event into our internal format.

        Args:
            calendar_event: Raw event from Calendar API

        Returns:
            Parsed event data
        """
        event_id = calendar_event["id"]
        summary = calendar_event.get("summary", "(No title)")
        description = calendar_event.get("description", "")

        # Parse start and end times
        start_time = CalendarParser._parse_datetime(calendar_event.get("start", {}))
        end_time = CalendarParser._parse_datetime(calendar_event.get("end", {}))

        # Parse attendees
        attendees = CalendarParser._parse_attendees(calendar_event.get("attendees", []))

        # Parse organizer
        organizer_data = calendar_event.get("organizer", {})
        organizer = organizer_data.get("email", "")

        # Get location and meeting link
        location = calendar_event.get("location", "")
        meeting_link = CalendarParser._extract_meeting_link(
            calendar_event.get("hangoutLink") or description or ""
        )

        # Get status
        status = calendar_event.get("status", "confirmed")

        # Check if recurring
        is_recurring = "recurringEventId" in calendar_event or "recurrence" in calendar_event
        recurrence_rule = None
        if "recurrence" in calendar_event:
            recurrence_rule = ", ".join(calendar_event["recurrence"])

        parsed = {
            "id": event_id,
            "summary": summary,
            "description": description,
            "start_time": start_time,
            "end_time": end_time,
            "attendees": attendees,
            "organizer": organizer,
            "location": location,
            "meeting_link": meeting_link,
            "status": status,
            "is_recurring": is_recurring,
            "recurrence_rule": recurrence_rule,
            "extracted_action_items": [],  # Will be populated by AI
            "preparation_notes": None,  # Will be populated by AI
            "follow_up_tasks": [],  # Will be populated by AI
            "metadata": {
                "html_link": calendar_event.get("htmlLink", ""),
                "created": calendar_event.get("created"),
                "updated": calendar_event.get("updated"),
                "creator": calendar_event.get("creator", {}).get("email", ""),
                "event_type": calendar_event.get("eventType", "default"),
            },
        }

        logger.debug(
            "calendar_event_parsed",
            event_id=event_id,
            summary=summary[:50],
            start=start_time.isoformat() if start_time else None,
        )

        return parsed

    @staticmethod
    def _parse_datetime(time_dict: Dict[str, Any]) -> Optional[datetime]:
        """
        Parse datetime from Calendar API format.

        Args:
            time_dict: Time dictionary from Calendar API
                      Contains either 'dateTime' or 'date'

        Returns:
            Parsed datetime or None
        """
        if not time_dict:
            return None

        # Try dateTime first (includes time)
        if "dateTime" in time_dict:
            dt_str = time_dict["dateTime"]
            # Parse ISO 8601 format
            try:
                # Remove timezone suffix if present and parse
                dt_str = dt_str.replace("Z", "+00:00")
                return datetime.fromisoformat(dt_str).replace(tzinfo=None)
            except Exception as e:
                logger.warning("datetime_parse_error", error=str(e), value=dt_str)
                return None

        # Fall back to date (all-day event)
        if "date" in time_dict:
            date_str = time_dict["date"]
            try:
                return datetime.strptime(date_str, "%Y-%m-%d")
            except Exception as e:
                logger.warning("date_parse_error", error=str(e), value=date_str)
                return None

        return None

    @staticmethod
    def _parse_attendees(attendees_list: List[Dict[str, Any]]) -> List[str]:
        """
        Extract email addresses from attendees list.

        Args:
            attendees_list: List of attendee objects

        Returns:
            List of email addresses
        """
        emails = []

        for attendee in attendees_list:
            email = attendee.get("email")
            if email:
                emails.append(email)

        return emails

    @staticmethod
    def _extract_meeting_link(text: str) -> Optional[str]:
        """
        Extract meeting link from text (Zoom, Meet, Teams, etc.).

        Args:
            text: Text that might contain a meeting link

        Returns:
            Meeting link or None
        """
        if not text:
            return None

        # Common meeting link patterns
        patterns = [
            r"https://meet\.google\.com/[a-z-]+",
            r"https://zoom\.us/j/\d+",
            r"https://teams\.microsoft\.com/[^\s]+",
            r"https://[^\s]*\.webex\.com/[^\s]+",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)

        return None

    @staticmethod
    def extract_meeting_type(summary: str, description: str = "") -> str:
        """
        Determine meeting type from title and description.

        Args:
            summary: Event title
            description: Event description

        Returns:
            Meeting type (e.g., "1:1", "team", "planning", "review")
        """
        text = (summary + " " + description).lower()

        # Common meeting types
        if any(word in text for word in ["1:1", "one-on-one", "1-on-1"]):
            return "1:1"
        elif any(word in text for word in ["team meeting", "team sync", "standup", "stand-up"]):
            return "team"
        elif any(word in text for word in ["planning", "roadmap", "strategy"]):
            return "planning"
        elif any(word in text for word in ["review", "retrospective", "retro"]):
            return "review"
        elif any(word in text for word in ["interview", "candidate"]):
            return "interview"
        elif any(word in text for word in ["all hands", "town hall"]):
            return "all-hands"

        return "other"

    @staticmethod
    def should_extract_actions(event: Dict[str, Any]) -> bool:
        """
        Determine if we should extract action items from this event.

        Args:
            event: Parsed event data

        Returns:
            True if we should extract actions
        """
        meeting_type = CalendarParser.extract_meeting_type(
            event.get("summary", ""),
            event.get("description", ""),
        )

        # Extract actions from these meeting types
        extract_types = ["1:1", "team", "planning", "review"]

        return meeting_type in extract_types
