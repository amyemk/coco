"""
Calendar Event Repository

Data access layer for calendar event operations.
"""

import json
from typing import List, Optional
from datetime import datetime

import structlog

from src.db.connection import get_db
from src.models.calendar_event import CalendarEvent

logger = structlog.get_logger()


class CalendarRepository:
    """
    Repository for calendar event data access
    """

    def __init__(self):
        self.db = get_db()

    def save(self, event: CalendarEvent) -> None:
        """
        Save or update a calendar event in the database.

        Args:
            event: CalendarEvent object to save
        """
        try:
            self.db.execute(
                """
                INSERT INTO calendar_events (
                    id, summary, description, start_time, end_time,
                    attendees, organizer, location, meeting_link, status,
                    is_recurring, recurrence_rule, extracted_action_items,
                    preparation_notes, follow_up_tasks, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    summary = excluded.summary,
                    description = excluded.description,
                    start_time = excluded.start_time,
                    end_time = excluded.end_time,
                    attendees = excluded.attendees,
                    organizer = excluded.organizer,
                    location = excluded.location,
                    meeting_link = excluded.meeting_link,
                    status = excluded.status,
                    is_recurring = excluded.is_recurring,
                    recurrence_rule = excluded.recurrence_rule,
                    extracted_action_items = excluded.extracted_action_items,
                    preparation_notes = excluded.preparation_notes,
                    follow_up_tasks = excluded.follow_up_tasks,
                    metadata = excluded.metadata,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    event.id,
                    event.summary,
                    event.description,
                    event.start_time.isoformat(),
                    event.end_time.isoformat(),
                    json.dumps(event.attendees),
                    event.organizer,
                    event.location,
                    event.meeting_link,
                    event.status,
                    event.is_recurring,
                    event.recurrence_rule,
                    json.dumps(event.extracted_action_items),
                    event.preparation_notes,
                    json.dumps(event.follow_up_tasks),
                    json.dumps(event.metadata),
                ),
            )

            logger.debug("calendar_event_saved", event_id=event.id)

        except Exception as e:
            logger.error("calendar_event_save_error", error=str(e), event_id=event.id)
            raise

    def save_many(self, events: List[CalendarEvent]) -> int:
        """
        Save multiple events in a batch.

        Args:
            events: List of events to save

        Returns:
            Number of events saved
        """
        count = 0
        for event in events:
            try:
                self.save(event)
                count += 1
            except Exception as e:
                logger.error("batch_event_save_error", error=str(e), event_id=event.id)

        logger.info("calendar_events_batch_saved", count=count, total=len(events))
        return count

    def get_by_id(self, event_id: str) -> Optional[CalendarEvent]:
        """
        Get an event by ID.

        Args:
            event_id: Event ID

        Returns:
            CalendarEvent object or None
        """
        row = self.db.fetchone(
            "SELECT * FROM calendar_events WHERE id = ?", (event_id,)
        )

        if row:
            return self._row_to_event(row)
        return None

    def get_upcoming(
        self, from_time: Optional[datetime] = None, limit: int = 50
    ) -> List[CalendarEvent]:
        """
        Get upcoming events.

        Args:
            from_time: Start time (default: now)
            limit: Maximum number of events

        Returns:
            List of upcoming events
        """
        if from_time is None:
            from_time = datetime.now()

        rows = self.db.fetchall(
            """
            SELECT * FROM calendar_events
            WHERE start_time >= ?
            AND status != 'cancelled'
            ORDER BY start_time ASC
            LIMIT ?
            """,
            (from_time.isoformat(), limit),
        )

        return [self._row_to_event(row) for row in rows]

    def get_todays_events(self) -> List[CalendarEvent]:
        """
        Get all events for today.

        Returns:
            List of today's events
        """
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day.replace(hour=23, minute=59, second=59)

        rows = self.db.fetchall(
            """
            SELECT * FROM calendar_events
            WHERE start_time >= ? AND start_time <= ?
            AND status != 'cancelled'
            ORDER BY start_time ASC
            """,
            (start_of_day.isoformat(), end_of_day.isoformat()),
        )

        return [self._row_to_event(row) for row in rows]

    def get_recent(
        self, since: datetime, until: Optional[datetime] = None
    ) -> List[CalendarEvent]:
        """
        Get recent past events.

        Args:
            since: Start time
            until: End time (default: now)

        Returns:
            List of recent events
        """
        if until is None:
            until = datetime.now()

        rows = self.db.fetchall(
            """
            SELECT * FROM calendar_events
            WHERE start_time >= ? AND start_time <= ?
            ORDER BY start_time DESC
            """,
            (since.isoformat(), until.isoformat()),
        )

        return [self._row_to_event(row) for row in rows]

    def get_in_range(
        self, start: datetime, end: datetime
    ) -> List[CalendarEvent]:
        """
        Get events in a specific date range.

        Args:
            start: Start datetime
            end: End datetime

        Returns:
            List of events in range
        """
        rows = self.db.fetchall(
            """
            SELECT * FROM calendar_events
            WHERE start_time >= ? AND start_time <= ?
            ORDER BY start_time ASC
            """,
            (start.isoformat(), end.isoformat()),
        )

        return [self._row_to_event(row) for row in rows]

    def update_action_items(self, event_id: str, action_items: List[str]) -> None:
        """
        Update extracted action items for an event.

        Args:
            event_id: Event ID
            action_items: List of action items
        """
        self.db.execute(
            "UPDATE calendar_events SET extracted_action_items = ? WHERE id = ?",
            (json.dumps(action_items), event_id),
        )

    def update_preparation_notes(self, event_id: str, notes: str) -> None:
        """
        Update AI-generated preparation notes.

        Args:
            event_id: Event ID
            notes: Preparation notes
        """
        self.db.execute(
            "UPDATE calendar_events SET preparation_notes = ? WHERE id = ?",
            (notes, event_id),
        )

    def update_follow_up_tasks(self, event_id: str, tasks: List[str]) -> None:
        """
        Update follow-up tasks for an event.

        Args:
            event_id: Event ID
            tasks: List of follow-up tasks
        """
        self.db.execute(
            "UPDATE calendar_events SET follow_up_tasks = ? WHERE id = ?",
            (json.dumps(tasks), event_id),
        )

    def get_count(self) -> int:
        """
        Get total number of events in database.

        Returns:
            Event count
        """
        result = self.db.fetchone("SELECT COUNT(*) as count FROM calendar_events")
        return result["count"] if result else 0

    def delete_old_events(self, before: datetime) -> int:
        """
        Delete events older than a specific date.

        Args:
            before: Delete events before this date

        Returns:
            Number of events deleted
        """
        cursor = self.db.execute(
            "DELETE FROM calendar_events WHERE end_time < ?",
            (before.isoformat(),),
        )

        count = cursor.rowcount
        logger.info("old_events_deleted", count=count, before=before.isoformat())

        return count

    def _row_to_event(self, row) -> CalendarEvent:
        """
        Convert database row to CalendarEvent object.

        Args:
            row: SQLite row

        Returns:
            CalendarEvent object
        """
        return CalendarEvent(
            id=row["id"],
            summary=row["summary"],
            description=row["description"],
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=datetime.fromisoformat(row["end_time"]),
            attendees=json.loads(row["attendees"] or "[]"),
            organizer=row["organizer"],
            location=row["location"],
            meeting_link=row["meeting_link"],
            status=row["status"],
            is_recurring=bool(row["is_recurring"]),
            recurrence_rule=row["recurrence_rule"],
            extracted_action_items=json.loads(row["extracted_action_items"] or "[]"),
            preparation_notes=row["preparation_notes"],
            follow_up_tasks=json.loads(row["follow_up_tasks"] or "[]"),
            metadata=json.loads(row["metadata"] or "{}"),
        )
