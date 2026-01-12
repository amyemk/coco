"""
Google Calendar Sync Service

Manages synchronization of calendar events to local database.
"""

from typing import List, Optional
from datetime import datetime, timedelta

import structlog

from src.integrations.calendar.client import CalendarClient
from src.integrations.calendar.parser import CalendarParser
from src.repositories.calendar_repository import CalendarRepository
from src.models.calendar_event import CalendarEvent
from src.db.connection import get_db

logger = structlog.get_logger()


class CalendarSyncService:
    """
    Service for syncing Google Calendar events to database
    """

    def __init__(
        self,
        client: Optional[CalendarClient] = None,
        repository: Optional[CalendarRepository] = None,
    ):
        """
        Initialize Calendar sync service.

        Args:
            client: Calendar API client (creates new if None)
            repository: Calendar repository (creates new if None)
        """
        self.client = client or CalendarClient()
        self.repository = repository or CalendarRepository()
        self.parser = CalendarParser()
        self.db = get_db()

    def sync_upcoming(
        self, days_ahead: int = 7, calendar_id: str = "primary"
    ) -> int:
        """
        Sync upcoming events for the next N days.

        Args:
            days_ahead: Number of days to sync ahead
            calendar_id: Calendar ID to sync

        Returns:
            Number of events synced
        """
        logger.info(
            "calendar_upcoming_sync_started",
            days_ahead=days_ahead,
            calendar_id=calendar_id,
        )

        try:
            # Get upcoming events from Google Calendar
            calendar_events = self.client.get_upcoming_events(
                days_ahead=days_ahead,
                calendar_id=calendar_id,
            )

            # Parse and save events
            synced_count = 0

            for calendar_event in calendar_events:
                try:
                    parsed_data = self.parser.parse_event(calendar_event)
                    event = CalendarEvent(**parsed_data)
                    self.repository.save(event)
                    synced_count += 1

                except Exception as e:
                    logger.error(
                        "calendar_event_sync_error",
                        error=str(e),
                        event_id=calendar_event.get("id", "unknown"),
                    )

            # Update sync status
            self._update_sync_status(
                status="success",
                items_synced=synced_count,
            )

            logger.info("calendar_upcoming_sync_complete", count=synced_count)

            return synced_count

        except Exception as e:
            logger.error("calendar_upcoming_sync_error", error=str(e))
            self._update_sync_status(
                status="failure",
                items_synced=0,
                error_message=str(e),
            )
            return 0

    def sync_recent(
        self, days_back: int = 1, calendar_id: str = "primary"
    ) -> int:
        """
        Sync recent past events (for extracting action items).

        Args:
            days_back: Number of days to look back
            calendar_id: Calendar ID to sync

        Returns:
            Number of events synced
        """
        logger.info(
            "calendar_recent_sync_started",
            days_back=days_back,
            calendar_id=calendar_id,
        )

        try:
            # Get recent events from Google Calendar
            calendar_events = self.client.get_recent_events(
                days_back=days_back,
                calendar_id=calendar_id,
            )

            # Parse and save events
            synced_count = 0

            for calendar_event in calendar_events:
                try:
                    parsed_data = self.parser.parse_event(calendar_event)
                    event = CalendarEvent(**parsed_data)
                    self.repository.save(event)
                    synced_count += 1

                except Exception as e:
                    logger.error(
                        "calendar_recent_event_sync_error",
                        error=str(e),
                        event_id=calendar_event.get("id", "unknown"),
                    )

            logger.info("calendar_recent_sync_complete", count=synced_count)

            return synced_count

        except Exception as e:
            logger.error("calendar_recent_sync_error", error=str(e))
            return 0

    def sync_today(self, calendar_id: str = "primary") -> int:
        """
        Sync today's events.

        Args:
            calendar_id: Calendar ID to sync

        Returns:
            Number of events synced
        """
        logger.info("calendar_today_sync_started", calendar_id=calendar_id)

        try:
            # Get today's events
            calendar_events = self.client.get_todays_events(calendar_id=calendar_id)

            # Parse and save
            synced_count = 0

            for calendar_event in calendar_events:
                try:
                    parsed_data = self.parser.parse_event(calendar_event)
                    event = CalendarEvent(**parsed_data)
                    self.repository.save(event)
                    synced_count += 1

                except Exception as e:
                    logger.error(
                        "calendar_today_event_sync_error",
                        error=str(e),
                        event_id=calendar_event.get("id"),
                    )

            logger.info("calendar_today_sync_complete", count=synced_count)

            return synced_count

        except Exception as e:
            logger.error("calendar_today_sync_error", error=str(e))
            return 0

    def full_sync(
        self,
        days_back: int = 1,
        days_ahead: int = 7,
        calendar_ids: Optional[List[str]] = None,
    ) -> int:
        """
        Perform full sync of past and upcoming events.

        Args:
            days_back: Days to sync in the past
            days_ahead: Days to sync in the future
            calendar_ids: List of calendar IDs (default: ["primary"])

        Returns:
            Total number of events synced
        """
        logger.info(
            "calendar_full_sync_started",
            days_back=days_back,
            days_ahead=days_ahead,
        )

        if calendar_ids is None:
            calendar_ids = ["primary"]

        total_synced = 0

        for calendar_id in calendar_ids:
            try:
                # Sync recent events (for action items)
                recent_count = self.sync_recent(
                    days_back=days_back,
                    calendar_id=calendar_id,
                )

                # Sync upcoming events
                upcoming_count = self.sync_upcoming(
                    days_ahead=days_ahead,
                    calendar_id=calendar_id,
                )

                total_synced += recent_count + upcoming_count

                logger.info(
                    "calendar_full_sync_calendar_complete",
                    calendar_id=calendar_id,
                    recent=recent_count,
                    upcoming=upcoming_count,
                )

            except Exception as e:
                logger.error(
                    "calendar_full_sync_calendar_error",
                    error=str(e),
                    calendar_id=calendar_id,
                )

        # Update sync status
        self._update_sync_status(
            status="success",
            items_synced=total_synced,
        )

        logger.info("calendar_full_sync_complete", total=total_synced)

        return total_synced

    def _update_sync_status(
        self,
        status: str,
        items_synced: int,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update sync status in database.

        Args:
            status: Sync status (success, failure, partial)
            items_synced: Number of items synced
            error_message: Error message if failed
        """
        import json

        self.db.execute(
            """
            INSERT INTO sync_status (
                source, last_sync_time, last_sync_status,
                items_synced, error_message, metadata
            ) VALUES (?, datetime('now'), ?, ?, ?, ?)
            """,
            (
                "calendar",
                status,
                items_synced,
                error_message,
                json.dumps({}),
            ),
        )

        logger.debug("calendar_sync_status_updated", status=status, items=items_synced)

    def get_sync_stats(self) -> dict:
        """
        Get synchronization statistics.

        Returns:
            Dictionary with sync stats
        """
        total_events = self.repository.get_count()

        # Get last sync info
        row = self.db.fetchone(
            """
            SELECT * FROM sync_status
            WHERE source = 'calendar'
            ORDER BY last_sync_time DESC
            LIMIT 1
            """
        )

        stats = {
            "total_events": total_events,
            "last_sync_time": row["last_sync_time"] if row else None,
            "last_sync_status": row["last_sync_status"] if row else None,
            "last_items_synced": row["items_synced"] if row else 0,
        }

        return stats
