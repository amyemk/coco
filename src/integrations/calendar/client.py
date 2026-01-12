"""
Google Calendar API Client

Wrapper around Google Calendar API for fetching events.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError
import structlog

from src.auth.google_oauth import get_oauth

logger = structlog.get_logger()


class CalendarClient:
    """
    Google Calendar API client
    """

    def __init__(self, service: Optional[Resource] = None):
        """
        Initialize Calendar client.

        Args:
            service: Optional pre-configured Calendar API service.
                    If None, will get from OAuth.
        """
        self.service = service or get_oauth().get_calendar_service()
        logger.info("calendar_client_initialized")

    def list_calendars(self) -> List[Dict[str, Any]]:
        """
        List all calendars accessible to the user.

        Returns:
            List of calendar objects
        """
        try:
            calendar_list = self.service.calendarList().list().execute()
            calendars = calendar_list.get("items", [])

            logger.info("calendars_listed", count=len(calendars))
            return calendars

        except HttpError as e:
            logger.error("calendar_list_error", error=str(e))
            raise

    def get_events(
        self,
        calendar_id: str = "primary",
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 250,
        single_events: bool = True,
        order_by: str = "startTime",
    ) -> List[Dict[str, Any]]:
        """
        Get events from a calendar.

        Args:
            calendar_id: Calendar ID (default: 'primary')
            time_min: Start time for event search
            time_max: End time for event search
            max_results: Maximum number of events to return
            single_events: Expand recurring events into instances
            order_by: Order results (startTime or updated)

        Returns:
            List of event objects
        """
        try:
            params = {
                "calendarId": calendar_id,
                "maxResults": max_results,
                "singleEvents": single_events,
            }

            if time_min:
                params["timeMin"] = time_min.isoformat() + "Z"
            if time_max:
                params["timeMax"] = time_max.isoformat() + "Z"
            if single_events:
                params["orderBy"] = order_by

            events_result = self.service.events().list(**params).execute()
            events = events_result.get("items", [])

            logger.info(
                "calendar_events_retrieved",
                calendar_id=calendar_id,
                count=len(events),
                time_min=time_min.isoformat() if time_min else None,
                time_max=time_max.isoformat() if time_max else None,
            )

            return events

        except HttpError as e:
            logger.error("calendar_get_events_error", error=str(e))
            raise

    def get_event(
        self, event_id: str, calendar_id: str = "primary"
    ) -> Dict[str, Any]:
        """
        Get a specific event by ID.

        Args:
            event_id: Event ID
            calendar_id: Calendar ID

        Returns:
            Event object
        """
        try:
            event = (
                self.service.events()
                .get(calendarId=calendar_id, eventId=event_id)
                .execute()
            )

            logger.debug("calendar_event_retrieved", event_id=event_id)
            return event

        except HttpError as e:
            logger.error("calendar_get_event_error", error=str(e), event_id=event_id)
            raise

    def get_upcoming_events(
        self, days_ahead: int = 7, calendar_id: str = "primary"
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming events for the next N days.

        Args:
            days_ahead: Number of days to look ahead
            calendar_id: Calendar ID

        Returns:
            List of upcoming events
        """
        now = datetime.utcnow()
        future = now + timedelta(days=days_ahead)

        return self.get_events(
            calendar_id=calendar_id,
            time_min=now,
            time_max=future,
        )

    def get_todays_events(self, calendar_id: str = "primary") -> List[Dict[str, Any]]:
        """
        Get all events for today.

        Args:
            calendar_id: Calendar ID

        Returns:
            List of today's events
        """
        now = datetime.utcnow()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        return self.get_events(
            calendar_id=calendar_id,
            time_min=start_of_day,
            time_max=end_of_day,
        )

    def get_recent_events(
        self, days_back: int = 1, calendar_id: str = "primary"
    ) -> List[Dict[str, Any]]:
        """
        Get recent past events.

        Args:
            days_back: Number of days to look back
            calendar_id: Calendar ID

        Returns:
            List of recent events
        """
        now = datetime.utcnow()
        past = now - timedelta(days=days_back)

        return self.get_events(
            calendar_id=calendar_id,
            time_min=past,
            time_max=now,
        )

    def get_events_in_range(
        self,
        start: datetime,
        end: datetime,
        calendar_id: str = "primary",
    ) -> List[Dict[str, Any]]:
        """
        Get events in a specific date range.

        Args:
            start: Start datetime
            end: End datetime
            calendar_id: Calendar ID

        Returns:
            List of events in range
        """
        return self.get_events(
            calendar_id=calendar_id,
            time_min=start,
            time_max=end,
        )
