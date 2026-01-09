"""
Email Data Models

Pydantic models for email data validation and serialization.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr


class Email(BaseModel):
    """Email message model"""

    id: str  # Gmail message ID
    thread_id: str
    from_address: str
    to_addresses: List[str]
    cc_addresses: List[str] = Field(default_factory=list)
    subject: Optional[str] = None
    body: Optional[str] = None
    snippet: Optional[str] = None
    timestamp: datetime
    labels: List[str] = Field(default_factory=list)
    is_flagged: bool = False
    is_read: bool = False
    has_attachments: bool = False
    priority_score: float = 0.0
    requires_response: bool = False
    suggested_reply: Optional[str] = None
    metadata: dict = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "18c1f2a3b4d5e6f7",
                "thread_id": "18c1f2a3b4d5e6f7",
                "from_address": "ceo@company.com",
                "to_addresses": ["cpo@company.com"],
                "cc_addresses": [],
                "subject": "Q1 Product Roadmap Review",
                "snippet": "Let's discuss the Q1 roadmap priorities...",
                "timestamp": "2026-01-09T10:30:00Z",
                "labels": ["INBOX", "IMPORTANT"],
                "is_flagged": True,
                "is_read": False,
                "priority_score": 0.85,
            }
        }


class EmailDraft(BaseModel):
    """AI-generated email draft"""

    id: str
    original_email_id: str
    suggested_reply: str
    tone: str = "professional"
    key_points: List[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    used: bool = False
    user_feedback: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "draft_abc123",
                "original_email_id": "18c1f2a3b4d5e6f7",
                "suggested_reply": "Thank you for bringing this up...",
                "tone": "professional",
                "key_points": ["Acknowledge timeline", "Propose next steps"],
                "confidence_score": 0.82,
            }
        }
