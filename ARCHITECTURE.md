# AI Chief of Staff – System Architecture

## Architecture Overview

The AI Chief of Staff is designed as a modular, extensible system built around three core principles:

1. **Context Continuity**: Maintain deep, ongoing understanding of the product organization
2. **Intelligent Synthesis**: Reason over disparate data sources to surface insights
3. **Actionable Output**: Generate high-value, ready-to-use artifacts

---

## System Components

### 1. Core Engine Layer

#### Daily Briefing Orchestrator
```
Purpose: Coordinate the generation and delivery of daily briefings
Responsibilities:
  - Schedule daily execution at configured time
  - Orchestrate data collection from all sources
  - Invoke AI synthesis pipeline
  - Format and deliver final briefing
  - Track metrics and user feedback

Key Classes:
  - BriefingOrchestrator
  - BriefingScheduler
  - BriefingFormatter
  - DeliveryManager
```

#### Context Engine
```
Purpose: Build and maintain organizational context
Responsibilities:
  - Index all documents and communications
  - Generate and store embeddings for semantic search
  - Track changes and deltas over time
  - Build knowledge graph of decisions and dependencies
  - Provide context retrieval for AI prompts

Key Classes:
  - ContextIndexer
  - EmbeddingGenerator
  - ChangeDetector
  - KnowledgeGraph
  - SemanticSearchEngine
```

#### Action Engine
```
Purpose: Generate actionable insights and artifacts
Responsibilities:
  - Score and prioritize emails/tasks
  - Generate email reply drafts
  - Extract action items from meetings
  - Identify delegation opportunities
  - Surface decision points

Key Classes:
  - PriorityScorer
  - EmailDraftGenerator
  - ActionItemExtractor
  - DecisionDetector
  - DelegationAnalyzer
```

---

### 2. AI/LLM Integration Layer

#### Claude Client
```python
class ClaudeClient:
    """
    Wrapper around Anthropic Claude API with:
    - Automatic retry logic
    - Rate limiting
    - Cost tracking
    - Response caching
    - Error handling
    """

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        stop_sequences: Optional[List[str]] = None
    ) -> str:
        """Generate text completion"""

    async def generate_structured(
        self,
        prompt: str,
        schema: dict,
        **kwargs
    ) -> dict:
        """Generate JSON output matching schema"""

    async def batch_generate(
        self,
        prompts: List[str],
        **kwargs
    ) -> List[str]:
        """Process multiple prompts efficiently"""
```

#### Prompt Templates
```python
class PromptLibrary:
    """
    Centralized repository of prompt templates
    Categories:
    - Email reply generation
    - Priority scoring
    - Task extraction
    - Context synthesis
    - Decision analysis
    - Delegation suggestions
    """

    @staticmethod
    def email_reply_prompt(
        original_email: Email,
        thread_context: List[Email],
        user_profile: UserProfile,
        relevant_decisions: List[Decision]
    ) -> str:
        """Generate prompt for email reply"""

    @staticmethod
    def priority_scoring_prompt(
        email: Email,
        calendar_context: List[CalendarEvent],
        current_priorities: List[Task]
    ) -> str:
        """Generate prompt for priority scoring"""

    # ... additional prompt templates
```

---

### 3. Data Integration Layer

#### Integration Architecture
```
┌─────────────────────────────────────────────────────────┐
│              Integration Coordinator                     │
│  (Manages sync schedule and coordination)               │
└────────────┬──────────────┬─────────────┬───────────────┘
             │              │             │
             │              │             │
    ┌────────▼──────┐  ┌───▼────────┐  ┌▼──────────────┐
    │ Gmail Sync    │  │ Calendar   │  │ Coda Sync     │
    │ Service       │  │ Sync Svc   │  │ Service       │
    └────────┬──────┘  └───┬────────┘  └┬──────────────┘
             │              │             │
             │              │             │
    ┌────────▼──────────────▼─────────────▼──────────────┐
    │          Data Normalization Layer                  │
    │  (Convert external formats to internal models)     │
    └────────────────────────┬───────────────────────────┘
                             │
                    ┌────────▼──────────┐
                    │  Local Data Store │
                    │  (SQLite + Vector)│
                    └───────────────────┘
```

#### Gmail Sync Service
```python
class GmailSyncService:
    """
    Manages Gmail data synchronization
    """

    async def initial_sync(self, lookback_days: int = 30):
        """Perform initial full sync of emails"""

    async def incremental_sync(self):
        """Sync only new/modified emails since last sync"""

    async def fetch_thread(self, thread_id: str) -> List[Email]:
        """Fetch complete email thread"""

    async def update_labels(self, email_id: str, labels: List[str]):
        """Update Gmail labels for an email"""

    def _parse_email_message(self, raw_message: dict) -> Email:
        """Convert Gmail API format to internal Email model"""
```

#### Calendar Sync Service
```python
class CalendarSyncService:
    """
    Manages Google Calendar synchronization
    """

    async def sync_upcoming_events(self, days_ahead: int = 7):
        """Sync upcoming calendar events"""

    async def get_todays_events(self) -> List[CalendarEvent]:
        """Get all events for today"""

    async def get_yesterdays_meetings(self) -> List[CalendarEvent]:
        """Get yesterday's meetings for follow-up extraction"""

    def _parse_calendar_event(self, raw_event: dict) -> CalendarEvent:
        """Convert Calendar API format to internal model"""
```

#### Coda Sync Service
```python
class CodaSyncService:
    """
    Manages Coda document synchronization
    """

    async def sync_tracked_docs(self):
        """Sync all configured Coda documents"""

    async def detect_changes(self, doc_id: str) -> Optional[CodaDocChange]:
        """Detect and summarize changes to a document"""

    async def extract_okrs(self, doc_id: str) -> List[OKR]:
        """Extract OKRs from a structured Coda table"""

    async def extract_roadmap_items(self, doc_id: str) -> List[RoadmapItem]:
        """Extract roadmap items from Coda doc"""
```

---

### 4. Data Storage Layer

#### Database Architecture

```
┌───────────────────────────────────────────────────────┐
│                  Storage Layer                         │
├───────────────────────────────────────────────────────┤
│                                                        │
│  ┌─────────────────────┐    ┌────────────────────┐   │
│  │   SQLite Database   │    │  Vector Store      │   │
│  │   (Structured Data) │    │  (Embeddings)      │   │
│  │                     │    │                    │   │
│  │  - Emails           │    │  - Email vectors   │   │
│  │  - Calendar events  │    │  - Doc vectors     │   │
│  │  - Coda docs        │    │  - Decision vectors│   │
│  │  - Tasks            │    │                    │   │
│  │  - Decisions        │    │  Search: ChromaDB  │   │
│  │  - Briefings        │    │  or FAISS          │   │
│  │                     │    │                    │   │
│  │  FTS5: Full-text    │    │                    │   │
│  │  search             │    │                    │   │
│  └─────────────────────┘    └────────────────────┘   │
│                                                        │
└───────────────────────────────────────────────────────┘
```

#### Repository Pattern
```python
class EmailRepository:
    """Data access layer for emails"""

    async def save(self, email: Email) -> None:
        """Save email to database"""

    async def get_by_id(self, email_id: str) -> Optional[Email]:
        """Retrieve email by ID"""

    async def get_thread(self, thread_id: str) -> List[Email]:
        """Get all emails in a thread"""

    async def search(self, query: str, limit: int = 50) -> List[Email]:
        """Full-text search across emails"""

    async def get_unread(self, limit: int = 50) -> List[Email]:
        """Get unread emails sorted by priority"""

    async def get_flagged(self) -> List[Email]:
        """Get flagged emails"""

    async def semantic_search(
        self,
        query_embedding: List[float],
        limit: int = 10
    ) -> List[Email]:
        """Semantic similarity search using embeddings"""
```

Similar repositories for:
- `CalendarEventRepository`
- `CodaDocumentRepository`
- `TaskRepository`
- `DecisionRepository`
- `DailyBriefingRepository`

---

### 5. Delivery Layer

#### Email Delivery Service
```python
class EmailDeliveryService:
    """
    Send daily briefings via email
    """

    async def send_briefing(
        self,
        briefing: DailyBriefing,
        recipient: str
    ) -> bool:
        """Send formatted briefing email"""

    def format_html_email(self, briefing: DailyBriefing) -> str:
        """Format briefing as rich HTML email"""

    def format_plain_text(self, briefing: DailyBriefing) -> str:
        """Format briefing as plain text fallback"""

    async def track_open(self, briefing_id: str) -> None:
        """Track when briefing email is opened"""
```

#### Slack Delivery Service (Future)
```python
class SlackDeliveryService:
    """
    Send daily briefings via Slack DM
    """

    async def send_briefing(
        self,
        briefing: DailyBriefing,
        user_id: str
    ) -> bool:
        """Send formatted briefing to Slack"""

    def format_slack_blocks(self, briefing: DailyBriefing) -> List[dict]:
        """Format briefing as Slack Block Kit"""
```

---

## Data Flow

### Daily Briefing Generation Flow

```
1. Trigger (Scheduled at 7 AM)
   │
   ▼
2. Data Collection Phase
   ├─ Sync latest emails (past 24 hours)
   ├─ Sync calendar events (today + upcoming)
   └─ Check Coda docs for changes
   │
   ▼
3. Analysis Phase
   ├─ Score email priorities
   ├─ Identify emails requiring response
   ├─ Extract action items from yesterday's meetings
   ├─ Detect Coda doc changes
   └─ Build context from decisions/history
   │
   ▼
4. AI Synthesis Phase
   ├─ Generate email reply drafts (top 5 priority)
   ├─ Synthesize daily priorities from all sources
   ├─ Create meeting prep notes for today
   ├─ Summarize Coda changes with impact analysis
   └─ Identify inconsistencies or tensions
   │
   ▼
5. Briefing Assembly
   ├─ Format sections (priorities, drafts, follow-ups, updates)
   ├─ Add context links and metadata
   └─ Generate final HTML/text
   │
   ▼
6. Delivery
   ├─ Send via email (or Slack)
   ├─ Save briefing to database
   └─ Track delivery metrics
   │
   ▼
7. Post-Delivery
   ├─ Monitor for user feedback
   └─ Track which suggestions are used
```

### Email Reply Generation Flow

```
1. User Request (from briefing or UI)
   │
   ▼
2. Context Gathering
   ├─ Fetch full email thread
   ├─ Get related calendar events
   ├─ Retrieve relevant decisions (semantic search)
   └─ Load user communication preferences
   │
   ▼
3. AI Generation
   ├─ Build prompt with full context
   ├─ Generate reply using Claude
   └─ Extract key points addressed
   │
   ▼
4. Quality Check
   ├─ Verify tone matches user preferences
   ├─ Check for completeness
   └─ Score confidence level
   │
   ▼
5. Presentation
   ├─ Format reply for display
   ├─ Add edit/send buttons
   └─ Track usage
```

---

## Key Design Patterns

### 1. Repository Pattern
- Abstraction layer over data access
- Enables easy testing with mock repositories
- Consistent interface for all data entities

### 2. Service Layer Pattern
- Business logic encapsulated in service classes
- Services orchestrate between repositories and AI layer
- Clear separation of concerns

### 3. Dependency Injection
```python
class BriefingOrchestrator:
    def __init__(
        self,
        email_repo: EmailRepository,
        calendar_repo: CalendarEventRepository,
        coda_repo: CodaDocumentRepository,
        task_repo: TaskRepository,
        claude_client: ClaudeClient,
        delivery_service: EmailDeliveryService
    ):
        self.email_repo = email_repo
        self.calendar_repo = calendar_repo
        # ... inject all dependencies
```

### 4. Command Pattern
- Each major operation (sync, generate, deliver) as a command
- Enables undo/redo, logging, and async execution

### 5. Observer Pattern
- Events emitted on significant actions
- Enable extensibility and monitoring
- Example: `briefing_generated`, `email_drafted`, `sync_completed`

---

## Scalability Considerations

### Vertical Scaling
- SQLite with WAL mode for concurrent reads
- Connection pooling for API clients
- In-memory caching for frequently accessed data

### Horizontal Scaling (Future)
- Move to PostgreSQL for multi-user support
- Separate workers for sync, analysis, and delivery
- Message queue (Redis/RabbitMQ) for async tasks

### Performance Optimization
1. **Lazy Loading**: Only generate email drafts when accessed
2. **Caching**: Cache AI responses for similar queries
3. **Batch Processing**: Process multiple emails in single AI call
4. **Incremental Sync**: Only fetch changed data
5. **Database Indexing**: Optimize common queries

---

## Security Architecture

### Authentication Flow
```
1. User initiates OAuth flow for Gmail/Calendar
   │
   ▼
2. Redirect to Google consent screen
   │
   ▼
3. User grants permissions
   │
   ▼
4. Receive authorization code
   │
   ▼
5. Exchange for access + refresh tokens
   │
   ▼
6. Store tokens encrypted locally
   │
   ▼
7. Auto-refresh tokens as needed
```

### Data Encryption
```
┌──────────────────────────────────┐
│  Application Layer               │
│  (Plain text in memory)          │
└────────────┬─────────────────────┘
             │
             ▼
┌──────────────────────────────────┐
│  Encryption Layer                │
│  (SQLCipher, AES-256)            │
└────────────┬─────────────────────┘
             │
             ▼
┌──────────────────────────────────┐
│  File System                     │
│  (Encrypted database file)       │
└──────────────────────────────────┘
```

### Secrets Management
- Environment variables for API keys
- Encrypted credential store for OAuth tokens
- Separate encryption keys per data type
- Key rotation support

---

## Error Handling Strategy

### Retry Logic
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(APIError)
)
async def sync_gmail():
    """Retry on API failures"""
```

### Circuit Breaker
```python
class CircuitBreaker:
    """
    Prevent cascading failures
    Open circuit after N failures
    Allow recovery attempts after timeout
    """
```

### Graceful Degradation
- If Gmail sync fails: Use cached emails for briefing
- If AI generation fails: Use heuristic-based prioritization
- If Coda sync fails: Skip that section of briefing
- Always deliver something, even if incomplete

---

## Monitoring & Observability

### Metrics to Track
```python
metrics = {
    # Performance
    "briefing_generation_time_seconds",
    "email_draft_generation_time_seconds",
    "sync_duration_seconds",

    # Quality
    "email_drafts_used_ratio",
    "priority_scoring_accuracy",
    "task_extraction_completeness",

    # Reliability
    "sync_failure_rate",
    "api_error_rate",
    "daily_briefing_delivery_success_rate",

    # Usage
    "briefings_delivered_count",
    "briefings_opened_count",
    "email_drafts_generated_count",
    "tasks_surfaced_count"
}
```

### Logging Strategy
```python
# Structured logging with context
logger.info(
    "daily_briefing_generated",
    briefing_id=briefing.id,
    date=briefing.date,
    priorities_count=len(briefing.priorities),
    email_drafts_count=len(briefing.email_drafts),
    generation_time_seconds=elapsed_time,
    data_sources=["gmail", "calendar", "coda"]
)
```

### Health Dashboard
- Last successful sync timestamps
- API quota usage
- Database size and growth
- Scheduled job status
- Error rates and trends

---

## Testing Strategy

### Unit Testing
```python
# Test email priority scoring
def test_priority_scorer():
    email = create_test_email(
        from_address="ceo@company.com",
        subject="Urgent: Product roadmap decision needed"
    )

    score = priority_scorer.score(email)
    assert score > 0.8  # High priority

# Test email reply generation
async def test_email_draft_generator():
    email = create_test_email(...)
    context = create_test_thread(...)

    draft = await draft_generator.generate(email, context)

    assert draft.suggested_reply is not None
    assert len(draft.key_points) > 0
    assert draft.confidence_score > 0.5
```

### Integration Testing
```python
# Test end-to-end briefing generation
async def test_daily_briefing_generation():
    # Setup test data
    setup_test_emails()
    setup_test_calendar()
    setup_test_coda_docs()

    # Generate briefing
    orchestrator = BriefingOrchestrator(...)
    briefing = await orchestrator.generate_daily_briefing()

    # Assertions
    assert briefing is not None
    assert len(briefing.priorities) > 0
    assert len(briefing.email_drafts) > 0
```

### Mock Services
```python
class MockClaudeClient:
    """Mock AI client for testing"""

    async def generate_text(self, prompt, **kwargs):
        # Return deterministic responses for tests
        if "priority" in prompt:
            return "0.75"
        elif "reply" in prompt:
            return "Thank you for the update..."
```

---

## Configuration Management

### Config File Structure
```yaml
# config.yaml
app:
  name: "AI Chief of Staff"
  version: "1.0.0"
  environment: "production"  # or "development"

user:
  name: "Jane Doe"
  email: "jane.doe@company.com"
  timezone: "America/Los_Angeles"
  title: "Chief Product Officer"

briefing:
  delivery_time: "07:00"
  delivery_method: "email"  # "email" or "slack"
  include_sections:
    - priorities
    - email_drafts
    - meeting_followups
    - coda_updates

integrations:
  gmail:
    enabled: true
    sync_interval_minutes: 15
    initial_sync_days: 30
    max_results_per_sync: 100

  calendar:
    enabled: true
    sync_interval_minutes: 30
    lookahead_days: 7

  coda:
    enabled: true
    sync_interval_minutes: 60
    tracked_docs:
      - id: "abc123"
        name: "Product Roadmap Q1 2025"
        type: "roadmap"
      - id: "def456"
        name: "Engineering OKRs"
        type: "okrs"

ai:
  provider: "anthropic"
  model: "claude-3-5-sonnet-20241022"
  max_tokens: 4000
  temperature: 0.7
  enable_caching: true
  cache_ttl_hours: 24

storage:
  database_path: "./data/ai_chief_of_staff.db"
  vector_store_path: "./data/vectors"
  enable_encryption: true
  backup_enabled: true
  backup_interval_hours: 24

logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  format: "json"
  output: "file"  # "file", "console", or "both"
  file_path: "./logs/app.log"
  rotation: "daily"
  retention_days: 30

monitoring:
  enable_metrics: true
  metrics_port: 9090
```

---

## Deployment Architecture

### Local Development
```
Developer Machine
├─ Python application
├─ SQLite database (local file)
├─ Vector store (local directory)
├─ Logs (local directory)
└─ Config files (.env, config.yaml)
```

### Production (Self-Hosted)
```
Personal Server / Cloud VM
├─ Systemd service (auto-restart)
├─ APScheduler (cron jobs)
├─ SQLite + Vector store (persistent volume)
├─ Nginx (optional, for web UI)
├─ Log rotation (logrotate)
└─ Automated backups (cron + rsync/rclone)
```

### Container Deployment (Optional)
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "src/main.py"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  ai-chief-of-staff:
    build: .
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./config.yaml:/app/config.yaml
    env_file:
      - .env
    restart: unless-stopped
```

---

## Maintenance & Operations

### Backup Strategy
```bash
# Daily backup script
#!/bin/bash

DATE=$(date +%Y%m%d)
BACKUP_DIR="./backups/$DATE"

mkdir -p $BACKUP_DIR

# Backup database
sqlite3 ./data/ai_chief_of_staff.db ".backup $BACKUP_DIR/database.db"

# Backup vector store
cp -r ./data/vectors $BACKUP_DIR/

# Backup config
cp config.yaml $BACKUP_DIR/

# Upload to cloud storage (optional)
rclone copy $BACKUP_DIR remote:ai-chief-of-staff-backups/

# Cleanup old backups (keep 30 days)
find ./backups -mtime +30 -delete
```

### Update Procedure
1. Pull latest code
2. Backup database
3. Install new dependencies
4. Run migrations (if any)
5. Restart service
6. Verify health checks

### Monitoring Checklist
- [ ] Daily briefing delivered on time
- [ ] All sync jobs completed successfully
- [ ] No API quota issues
- [ ] Database size within limits
- [ ] Logs show no critical errors
- [ ] Backup completed successfully

---

## Extension Points

### Plugin Architecture (Future)
```python
class DataSourcePlugin(ABC):
    """
    Abstract base class for new data source plugins
    """

    @abstractmethod
    async def sync(self) -> None:
        """Sync data from source"""

    @abstractmethod
    async def extract_tasks(self) -> List[Task]:
        """Extract tasks from source"""

    @abstractmethod
    async def get_recent_changes(self) -> List[Change]:
        """Get recent changes"""

# Example: Slack plugin
class SlackDataSourcePlugin(DataSourcePlugin):
    async def sync(self):
        # Sync Slack messages and channels

    async def extract_tasks(self):
        # Extract action items from Slack threads

    async def get_recent_changes(self):
        # Get new messages, mentions, etc.
```

### Custom AI Providers
```python
class AIProvider(ABC):
    """Abstract interface for AI providers"""

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        pass

# Can swap Claude for OpenAI, local models, etc.
class OpenAIProvider(AIProvider):
    async def generate(self, prompt: str, **kwargs) -> str:
        # Use OpenAI API
```

---

## Summary

This architecture provides:

1. **Modularity**: Clear separation between components
2. **Extensibility**: Easy to add new data sources and features
3. **Testability**: All components can be tested independently
4. **Reliability**: Robust error handling and retry logic
5. **Security**: Encrypted storage, secure API access
6. **Performance**: Optimized for fast response times
7. **Maintainability**: Clean code structure, comprehensive logging

The system is designed to start simple (single user, local deployment) but scale up to support multiple users, cloud deployment, and additional integrations as needed.
