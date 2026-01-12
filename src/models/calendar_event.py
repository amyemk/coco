"""
Calendar Event Data Models

Pydantic models for calendar event data validation and serialization.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class CalendarEvent(BaseModel):
    """Calendar event model"""

    id: str  # Google Calendar event ID
    summary: str  # Event title
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    attendees: List[str] = Field(default_factory=list)
    organizer: Optional[str] = None
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    status: str = "confirmed"  # confirmed, tentative, cancelled
    is_recurring: bool = False
    recurrence_rule: Optional[str] = None
    extracted_action_items: List[str] = Field(default_factory=list)
    preparation_notes: Optional[str] = None
    follow_up_tasks: List[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "event123abc",
                "summary": "Product Roadmap Review",
                "description": "Q1 planning session",
                "start_time": "2026-01-15T14:00:00Z",
                "end_time": "2026-01-15T15:00:00Z",
                "attendees": ["ceo@company.com", "cto@company.com"],
                "organizer": "cpo@company.com",
                "location": "Conference Room A",
                "meeting_link": "https://meet.google.com/abc-defg-hij",
                "status": "confirmed",
            }
        }
