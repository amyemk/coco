"""
Email Data Models

Pydantic models for email data validation and serialization.
"""

from datetime import datetime, date
from enum import Enum
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class EmailCategory(str, Enum):
    """Email triage categories"""
    JUNK = "JUNK"
    NEWSLETTER = "NEWSLETTER"
    SYSTEM_NOTIFICATION = "SYSTEM_NOTIFICATION"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    FYI = "FYI"


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
    # Triage classification
    email_category: Optional[EmailCategory] = None
    category_confidence: Optional[float] = None
    category_reasoning: Optional[str] = None
    classified_by: Optional[str] = None  # "heuristic" | "claude"
    classified_at: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)


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


class EmailClassification(BaseModel):
    """Result of classifying an email into a triage category"""

    email_id: str
    category: EmailCategory
    confidence: float
    reasoning: str
    classified_by: str  # "heuristic" | "claude"


class SystemNotification(BaseModel):
    """Parsed system notification from a DS tool"""

    email_id: str
    system: str  # "Concur" | "SAP" | "Bob" | "Asana" | "Other"
    action_type: str  # "approval_required" | "status_update" | "assignment" | ...
    entity_name: str  # e.g. "EXP-2891" or "Q2 Roadmap Review"
    status: str  # e.g. "pending_approval" | "approved" | "rejected"
    deadline: Optional[date] = None
    requires_action: bool = False
    deep_link: Optional[str] = None
    raw_summary: str  # One-liner for display, e.g. "Expense report EXP-2891 pending your approval"


class NewsletterSummary(BaseModel):
    """Summary of a single newsletter email"""

    email_id: str
    source: str  # Newsletter name / sender
    key_points: List[str]  # 3-5 bullet points
    full_content: str  # Full body kept in memory for follow-up questions


class Story(BaseModel):
    """A deduplicated story appearing across multiple newsletters"""

    headline: str
    summary: str
    sources: List[str]  # Which newsletters covered this


class DeduplicatedDigest(BaseModel):
    """Cross-source deduplicated newsletter digest for a triage session"""

    stories: List[Story]
    processed_email_ids: List[str]


class DraftOption(BaseModel):
    """A single draft reply option"""

    style: Literal["short_ack", "full_reply", "decline"]
    subject: str
    body: str


class EmailDraftSet(BaseModel):
    """Three draft options generated for an action-required email"""

    original_email_id: str
    options: List[DraftOption]  # Always 3: short_ack, full_reply, decline
    thread_summary: str  # Brief context for display during triage


class ObsidianTask(BaseModel):
    """A task to be written to the Obsidian vault"""

    title: str
    due_date: Optional[date] = None
    tags: List[str] = Field(default_factory=list)  # Always includes "coco"
    source_ref: str  # e.g. "email from Sarah Chen re: Budget sign-off"
    email_id: Optional[str] = None


class ActionPlan(BaseModel):
    """Processing plan for an ACTION_REQUIRED email"""

    email_id: str
    action_type: Literal["reply_only", "task_only", "both"]
    draft_set: Optional[EmailDraftSet] = None
    task: Optional[ObsidianTask] = None


class JunkSuggestion(str, Enum):
    DELETE = "delete"
    UNSUBSCRIBE = "unsubscribe"
    REVIEW = "review"


class JunkAnalysis(BaseModel):
    """Junk detection result for a single email"""

    email_id: str
    suggestion: JunkSuggestion
    confidence: float
    reason: str
    sender_history_count: int = 0  # How many prior junk emails from this sender
