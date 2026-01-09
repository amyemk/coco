# AI Chief of Staff – Technical Specification

## Overview

This document provides the technical architecture and implementation specifications for the AI Chief of Staff application, a personal AI assistant designed for a Chief Product Officer.

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AI Chief of Staff                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Daily      │    │   Context    │    │   Action     │  │
│  │   Briefing   │───▶│   Engine     │───▶│   Engine     │  │
│  │   Generator  │    │              │    │              │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                    │                    │          │
│         └────────────────────┴────────────────────┘          │
│                              │                                │
│                    ┌─────────▼─────────┐                     │
│                    │   AI/LLM Layer    │                     │
│                    │  (Claude API)     │                     │
│                    └───────────────────┘                     │
│                              │                                │
├──────────────────────────────┼────────────────────────────────┤
│                              │                                │
│  ┌──────────────────────────▼────────────────────────────┐  │
│  │              Data & Integration Layer                  │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │                                                         │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │  │
│  │  │   Gmail     │  │   Google    │  │    Coda     │   │  │
│  │  │   Client    │  │   Calendar  │  │    Client   │   │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘   │  │
│  │                                                         │  │
│  │  ┌──────────────────────────────────────────────────┐ │  │
│  │  │         Local Knowledge Store                    │ │  │
│  │  │  (SQLite + Vector Embeddings)                    │ │  │
│  │  └──────────────────────────────────────────────────┘ │  │
│  │                                                         │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
├───────────────────────────────────────────────────────────────┤
│                     Delivery Layer                            │
│  ┌──────────────┐              ┌──────────────┐              │
│  │    Email     │              │   Web UI     │              │
│  │   Sender     │              │  (Optional)  │              │
│  └──────────────┘              └──────────────┘              │
└───────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. Daily Briefing Generator
**Responsibility**: Orchestrate the creation of the daily briefing
**Key Functions**:
- Schedule and trigger daily briefing at 7 AM
- Coordinate data collection from all sources
- Synthesize information using AI
- Format and deliver briefing via email

#### 2. Context Engine
**Responsibility**: Maintain continuous understanding of the product org
**Key Functions**:
- Index and embed all documents (emails, calendar events, Coda docs)
- Track changes and deltas over time
- Build semantic search capabilities
- Maintain decision history and "why" context
- Detect inconsistencies and tensions

#### 3. Action Engine
**Responsibility**: Generate actionable insights and drafts
**Key Functions**:
- Prioritize tasks based on context
- Generate email reply drafts
- Extract action items from meetings
- Surface key decisions requiring attention
- Suggest delegation opportunities

#### 4. AI/LLM Layer
**Responsibility**: Power intelligent reasoning and generation
**Key Functions**:
- Text generation (email drafts, summaries)
- Semantic understanding and reasoning
- Context synthesis
- Priority scoring
- Tone and style matching

---

## Technology Stack

### Core Technologies

```yaml
Language: Python 3.11+
AI/LLM: Anthropic Claude API (claude-3-5-sonnet-20241022)
Database: SQLite with FTS5 (full-text search)
Vector Store: ChromaDB or FAISS (for embeddings)
Task Scheduler: APScheduler
Web Framework: FastAPI (for optional web UI and webhooks)
```

### External Integrations

```yaml
Gmail: Google Gmail API (OAuth 2.0)
Calendar: Google Calendar API (OAuth 2.0)
Coda: Coda API (API token authentication)
Email Delivery: SMTP (Gmail SMTP) or SendGrid
```

### Development Tools

```yaml
Package Manager: Poetry or pip-tools
Code Quality: Black, Ruff, mypy
Testing: pytest, pytest-asyncio
Environment: python-dotenv
Logging: structlog
```

---

## Data Models

### Core Entities

#### Email
```python
class Email:
    id: str  # Gmail message ID
    thread_id: str
    from_address: str
    to_addresses: List[str]
    cc_addresses: List[str]
    subject: str
    body: str  # Plain text or HTML
    snippet: str
    timestamp: datetime
    labels: List[str]  # Gmail labels
    is_flagged: bool
    is_read: bool
    has_attachments: bool
    priority_score: float  # AI-generated
    requires_response: bool  # AI-determined
    suggested_reply: Optional[str]
    embedding: Optional[List[float]]  # Vector embedding
    metadata: dict
```

#### CalendarEvent
```python
class CalendarEvent:
    id: str
    summary: str
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    attendees: List[str]
    organizer: str
    location: Optional[str]
    meeting_link: Optional[str]
    status: str  # confirmed, tentative, cancelled
    is_recurring: bool
    extracted_action_items: List[str]
    preparation_notes: Optional[str]  # AI-generated
    follow_up_tasks: List[str]  # AI-extracted
    embedding: Optional[List[float]]
    metadata: dict
```

#### CodaDocument
```python
class CodaDocument:
    id: str
    name: str
    doc_type: str  # roadmap, OKR, strategy, etc.
    content: str
    last_modified: datetime
    modified_by: str
    url: str
    change_summary: Optional[str]  # AI-generated delta
    key_decisions: List[str]  # AI-extracted
    embedding: Optional[List[float]]
    metadata: dict
```

#### Task
```python
class Task:
    id: str
    title: str
    description: str
    source: str  # email, calendar, coda
    source_id: str  # ID of source entity
    priority: str  # high, medium, low
    priority_score: float
    due_date: Optional[datetime]
    status: str  # pending, in_progress, completed
    created_at: datetime
    context: str  # Why this matters
    suggested_action: Optional[str]
    metadata: dict
```

#### DailyBriefing
```python
class DailyBriefing:
    id: str
    date: date
    generated_at: datetime
    priorities: List[Task]
    email_drafts: List[EmailDraft]
    meeting_followups: List[MeetingFollowup]
    coda_updates: List[CodaUpdate]
    delivered: bool
    opened: bool
    feedback_score: Optional[int]
    metadata: dict
```

#### EmailDraft
```python
class EmailDraft:
    id: str
    original_email_id: str
    suggested_reply: str
    tone: str  # professional, casual, urgent
    key_points: List[str]
    confidence_score: float
    used: Optional[bool]
    user_feedback: Optional[str]
```

#### Decision
```python
class Decision:
    id: str
    title: str
    description: str
    rationale: str  # The "why"
    made_on: datetime
    made_by: str
    source: str  # email, meeting, coda
    source_id: str
    impact_areas: List[str]  # e.g., roadmap, team, strategy
    related_decisions: List[str]  # IDs of related decisions
    is_active: bool  # False if reversed or superseded
    embedding: Optional[List[float]]
```

---

## Database Schema

### SQLite Tables

```sql
-- Core data tables
CREATE TABLE emails (
    id TEXT PRIMARY KEY,
    thread_id TEXT,
    from_address TEXT,
    to_addresses TEXT,  -- JSON array
    cc_addresses TEXT,  -- JSON array
    subject TEXT,
    body TEXT,
    snippet TEXT,
    timestamp DATETIME,
    labels TEXT,  -- JSON array
    is_flagged BOOLEAN,
    is_read BOOLEAN,
    has_attachments BOOLEAN,
    priority_score REAL,
    requires_response BOOLEAN,
    suggested_reply TEXT,
    metadata TEXT,  -- JSON
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE calendar_events (
    id TEXT PRIMARY KEY,
    summary TEXT,
    description TEXT,
    start_time DATETIME,
    end_time DATETIME,
    attendees TEXT,  -- JSON array
    organizer TEXT,
    location TEXT,
    meeting_link TEXT,
    status TEXT,
    is_recurring BOOLEAN,
    extracted_action_items TEXT,  -- JSON array
    preparation_notes TEXT,
    follow_up_tasks TEXT,  -- JSON array
    metadata TEXT,  -- JSON
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE coda_documents (
    id TEXT PRIMARY KEY,
    name TEXT,
    doc_type TEXT,
    content TEXT,
    last_modified DATETIME,
    modified_by TEXT,
    url TEXT,
    change_summary TEXT,
    key_decisions TEXT,  -- JSON array
    metadata TEXT,  -- JSON
    synced_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    title TEXT,
    description TEXT,
    source TEXT,
    source_id TEXT,
    priority TEXT,
    priority_score REAL,
    due_date DATETIME,
    status TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    context TEXT,
    suggested_action TEXT,
    metadata TEXT  -- JSON
);

CREATE TABLE decisions (
    id TEXT PRIMARY KEY,
    title TEXT,
    description TEXT,
    rationale TEXT,
    made_on DATETIME,
    made_by TEXT,
    source TEXT,
    source_id TEXT,
    impact_areas TEXT,  -- JSON array
    related_decisions TEXT,  -- JSON array
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE daily_briefings (
    id TEXT PRIMARY KEY,
    date DATE UNIQUE,
    generated_at DATETIME,
    priorities TEXT,  -- JSON array of task IDs
    email_drafts TEXT,  -- JSON array
    meeting_followups TEXT,  -- JSON array
    coda_updates TEXT,  -- JSON array
    delivered BOOLEAN,
    opened BOOLEAN,
    feedback_score INTEGER,
    metadata TEXT  -- JSON
);

-- Full-text search tables
CREATE VIRTUAL TABLE emails_fts USING fts5(
    id UNINDEXED,
    subject,
    body,
    snippet
);

CREATE VIRTUAL TABLE coda_documents_fts USING fts5(
    id UNINDEXED,
    name,
    content
);

-- Indexes for performance
CREATE INDEX idx_emails_timestamp ON emails(timestamp DESC);
CREATE INDEX idx_emails_thread ON emails(thread_id);
CREATE INDEX idx_emails_priority ON emails(priority_score DESC);
CREATE INDEX idx_calendar_start ON calendar_events(start_time);
CREATE INDEX idx_tasks_priority ON tasks(priority_score DESC);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_decisions_made_on ON decisions(made_on DESC);
```

---

## AI/LLM Integration

### Claude API Usage Patterns

#### 1. Email Reply Generation
```python
async def generate_email_reply(
    original_email: Email,
    context: List[Email],  # Thread context
    user_profile: dict
) -> EmailDraft:
    """
    Generate a suggested reply to an email.

    Prompt structure:
    - System: CPO persona, tone guidelines, organizational context
    - Context: Email thread, related decisions, calendar commitments
    - Task: Generate reply that addresses key points
    """
    prompt = f"""
    You are a Chief Product Officer responding to this email.

    Original email from {original_email.from_address}:
    Subject: {original_email.subject}
    {original_email.body}

    Context:
    - Previous emails in thread: {format_thread(context)}
    - Your tone preferences: {user_profile['tone']}
    - Relevant decisions: {get_related_decisions(original_email)}

    Generate a professional reply that:
    1. Addresses the key points
    2. Maintains appropriate context
    3. Matches the expected tone
    4. Is concise and actionable
    """

    response = await claude_client.generate(
        prompt=prompt,
        max_tokens=500,
        temperature=0.7
    )

    return EmailDraft(...)
```

#### 2. Priority Scoring
```python
async def score_email_priority(email: Email) -> float:
    """
    Score email priority on 0-1 scale.

    Factors:
    - Sender importance
    - Subject urgency indicators
    - Content analysis
    - Thread context
    - Deadline mentions
    """
    prompt = f"""
    Analyze this email and score its priority for a CPO on a scale of 0-1.

    From: {email.from_address}
    Subject: {email.subject}
    Content: {email.snippet}

    Consider:
    - Urgency indicators
    - Sender's role
    - Potential impact on product decisions
    - Presence of questions requiring response

    Return ONLY a number between 0 and 1.
    """

    response = await claude_client.generate(
        prompt=prompt,
        max_tokens=10,
        temperature=0.3
    )

    return float(response.strip())
```

#### 3. Task Extraction
```python
async def extract_tasks_from_meeting(event: CalendarEvent) -> List[Task]:
    """
    Extract action items from meeting notes or description.
    """
    prompt = f"""
    Extract action items from this meeting.

    Meeting: {event.summary}
    Notes: {event.description}
    Attendees: {', '.join(event.attendees)}

    For each action item, provide:
    1. Clear task description
    2. Who should own it (if mentioned)
    3. Priority level
    4. Context/why it matters

    Return as structured JSON.
    """

    response = await claude_client.generate(
        prompt=prompt,
        max_tokens=1000,
        temperature=0.5
    )

    tasks_data = json.loads(response)
    return [Task(**task) for task in tasks_data]
```

#### 4. Context Synthesis
```python
async def synthesize_daily_context(
    emails: List[Email],
    events: List[CalendarEvent],
    coda_docs: List[CodaDocument]
) -> str:
    """
    Create a coherent narrative of what's happening.
    """
    prompt = f"""
    You are synthesizing a day's worth of information for a CPO.

    Today's calendar: {format_events(events)}
    Priority emails: {format_emails(emails)}
    Key doc changes: {format_coda_changes(coda_docs)}

    Create a brief narrative (3-4 paragraphs) that:
    1. Highlights what matters most today
    2. Surfaces any tensions or inconsistencies
    3. Connects decisions across sources
    4. Provides strategic context

    Be concise but insightful.
    """

    response = await claude_client.generate(
        prompt=prompt,
        max_tokens=800,
        temperature=0.7
    )

    return response
```

### Prompt Engineering Guidelines

1. **System Prompts**: Establish CPO persona with consistent tone and priorities
2. **Context Windows**: Use extended context (100K+ tokens) for comprehensive understanding
3. **Structured Outputs**: Request JSON when extracting structured data
4. **Temperature Settings**:
   - 0.3-0.5 for factual tasks (priority scoring, extraction)
   - 0.7-0.9 for creative tasks (email drafting, synthesis)
5. **Few-shot Examples**: Include examples of good replies, task descriptions, etc.

---

## Integration Specifications

### Gmail Integration

#### Authentication
- OAuth 2.0 with offline access
- Scopes required:
  - `gmail.readonly` (read emails)
  - `gmail.send` (send drafts via link)
  - `gmail.modify` (update labels)

#### API Operations
```python
# Fetch recent emails
emails = gmail_service.users().messages().list(
    userId='me',
    maxResults=50,
    q='is:unread OR is:flagged'
).execute()

# Get full email content
message = gmail_service.users().messages().get(
    userId='me',
    id=email_id,
    format='full'
).execute()

# Update email labels
gmail_service.users().messages().modify(
    userId='me',
    id=email_id,
    body={'addLabelIds': ['INBOX'], 'removeLabelIds': ['UNREAD']}
).execute()
```

#### Sync Strategy
- Initial sync: Last 30 days of emails
- Incremental: Poll every 15 minutes for new/modified emails
- Use `history_id` for efficient incremental sync
- Store last sync timestamp and history ID

### Google Calendar Integration

#### Authentication
- OAuth 2.0 with offline access
- Scopes: `calendar.readonly`

#### API Operations
```python
# Fetch today's and upcoming events
events = calendar_service.events().list(
    calendarId='primary',
    timeMin=datetime.utcnow().isoformat() + 'Z',
    maxResults=50,
    singleEvents=True,
    orderBy='startTime'
).execute()

# Get event details
event = calendar_service.events().get(
    calendarId='primary',
    eventId=event_id
).execute()
```

#### Sync Strategy
- Sync events: Today + next 7 days
- Poll every 30 minutes
- Extract action items from past day's meetings each morning

### Coda Integration

#### Authentication
- API token (stored securely)
- Token scoped to specific docs

#### API Operations
```python
# List accessible docs
docs = coda_client.list_docs()

# Get doc content
doc = coda_client.get_doc(doc_id)

# Get doc tables
tables = coda_client.list_tables(doc_id)

# Get table rows (for OKRs, roadmaps, etc.)
rows = coda_client.list_rows(doc_id, table_id)
```

#### Sync Strategy
- Track list of "key docs" (configured by user)
- Check for changes every 1 hour
- Compute diffs to detect roadmap/OKR changes
- Store change summaries for historical context

---

## Security & Privacy

### Data Storage
- All data stored locally (SQLite database)
- Database encrypted at rest using SQLCipher
- Vector embeddings stored separately, also encrypted

### Credentials Management
```
.env file (gitignored):
GMAIL_CLIENT_ID=...
GMAIL_CLIENT_SECRET=...
CODA_API_TOKEN=...
ANTHROPIC_API_KEY=...
DATABASE_ENCRYPTION_KEY=...
```

- Use `python-dotenv` to load environment variables
- Never commit credentials to git
- OAuth tokens stored in encrypted local file

### API Security
- All external API calls use HTTPS
- Implement rate limiting to avoid quota issues
- OAuth token refresh handled automatically
- API keys rotated periodically

### Data Retention
- Emails: Keep for 90 days
- Calendar events: Keep for 30 days past event date
- Coda docs: Keep latest version + change history for 90 days
- Tasks: Archive completed tasks after 30 days
- Decisions: Keep indefinitely (core knowledge)

### Privacy Principles
- No data sent to third parties except:
  - Anthropic (for AI processing)
  - Google/Coda APIs (for data sync)
- No telemetry or usage tracking
- User has full control to delete all data

---

## Performance Considerations

### Response Times
- Daily briefing generation: < 2 minutes
- Email reply generation: < 5 seconds
- Priority scoring: < 1 second per email
- Incremental sync: < 30 seconds

### Scalability
- Handle up to 1000 emails in inbox
- Process up to 50 calendar events per week
- Monitor up to 20 Coda documents
- Vector database: Up to 100K embeddings

### Optimization Strategies
1. **Caching**: Cache AI responses for similar queries
2. **Batch Processing**: Process multiple emails in single AI call when possible
3. **Incremental Sync**: Only fetch changed data
4. **Lazy Loading**: Generate email drafts on-demand, not all at once
5. **Indexing**: Proper database indexes for fast queries

---

## Error Handling & Resilience

### Error Categories

1. **API Failures**
   - Retry with exponential backoff
   - Fallback to cached data if available
   - Log errors for debugging

2. **Authentication Issues**
   - Detect token expiration
   - Auto-refresh OAuth tokens
   - Notify user if manual re-auth needed

3. **AI/LLM Failures**
   - Retry with different prompt if needed
   - Fallback to simpler heuristics
   - Never block briefing generation on AI failure

4. **Data Corruption**
   - Validate all data before storage
   - Implement database integrity checks
   - Keep backups of critical data

### Monitoring & Logging

```python
import structlog

logger = structlog.get_logger()

# Log all significant events
logger.info("daily_briefing_generated",
           briefing_id=briefing.id,
           email_count=len(emails),
           task_count=len(tasks))

# Log errors with context
logger.error("gmail_sync_failed",
            error=str(e),
            last_successful_sync=last_sync_time)
```

### Health Checks
- Database connectivity
- API quota remaining
- Last successful sync times
- Scheduled job status

---

## Testing Strategy

### Unit Tests
- Test individual components (parsers, scorers, generators)
- Mock external API calls
- Test data models and validation

### Integration Tests
- Test API integrations with test accounts
- Test end-to-end briefing generation
- Test email draft generation quality

### Test Data
- Create fixtures for emails, calendar events, Coda docs
- Build test corpus of realistic CPO communications
- Include edge cases (long emails, complex threads, etc.)

### Quality Metrics
- Email draft acceptance rate
- Priority scoring accuracy
- Task extraction completeness
- Response time SLAs

---

## Deployment

### Local Development
```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your credentials

# Initialize database
python scripts/init_db.py

# Run
python src/main.py
```

### Production (Self-Hosted)
- Run on always-on machine (personal server, cloud VM)
- Use systemd or supervisor for process management
- Schedule daily briefing job using APScheduler
- Set up log rotation
- Configure automated backups

### Configuration Management
```yaml
# config.yaml
user:
  name: "Chief Product Officer"
  email: "cpo@example.com"
  timezone: "America/Los_Angeles"

briefing:
  delivery_time: "07:00"
  delivery_method: "email"  # or "slack"

integrations:
  gmail:
    sync_interval_minutes: 15
    lookback_days: 30

  calendar:
    sync_interval_minutes: 30
    lookahead_days: 7

  coda:
    sync_interval_minutes: 60
    tracked_docs:
      - doc_id: "abc123"
        type: "roadmap"
      - doc_id: "def456"
        type: "okrs"

ai:
  model: "claude-3-5-sonnet-20241022"
  max_tokens: 4000
  temperature: 0.7
```

---

## Future Enhancements (Post-V1)

### Potential Features
1. **Slack Integration**: Deliver briefing via Slack DM
2. **Meeting Transcript Analysis**: Integrate with Gong/Dovetail
3. **Mobile Companion App**: Quick access to briefing on mobile
4. **Voice Interface**: "Read me today's briefing"
5. **Team Insights**: Aggregate patterns across product org
6. **Predictive Analytics**: Forecast upcoming bottlenecks
7. **Integration Hub**: Connect to Jira, Notion, Linear, etc.
8. **Learning System**: Improve over time based on user feedback

### Scalability Path
- Multi-user support (team version)
- Cloud deployment option
- Real-time websocket updates
- Advanced analytics dashboard
- API for third-party integrations

---

## Appendix

### Glossary
- **Context Window**: The amount of text the AI model can process at once
- **Embedding**: Vector representation of text for semantic search
- **OAuth 2.0**: Industry-standard protocol for authorization
- **Incremental Sync**: Fetching only changed data since last sync
- **RAG**: Retrieval-Augmented Generation (using stored context with AI)

### References
- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [Google Calendar API](https://developers.google.com/calendar)
- [Coda API Documentation](https://coda.io/developers/apis/v1)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [SQLite FTS5](https://www.sqlite.org/fts5.html)
