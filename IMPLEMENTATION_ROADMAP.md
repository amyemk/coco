# Coco – Implementation Roadmap

## Status Summary

| Phase | Status | Description |
|---|---|---|
| Phase 1: Foundation | ✅ Complete | DB schema, OAuth, config system |
| Phase 2: Data Integration | ✅ Complete | Gmail, Calendar, Coda sync |
| Phase 3: Email Intelligence | 🔜 Next | Classifier, processors, draft/task generation |
| Phase 4: Triage Infrastructure | ⬜ Planned | Pre-processing jobs, Obsidian writer, session state |
| Phase 5: Triage Session | ⬜ Planned | Claude Code interactive interface |
| Phase 6: Polish & Feedback | ⬜ Planned | Memory, feedback loop, weekly summary |

---

## Phase 1: Foundation ✅

Database schema (10+ tables), OAuth 2.0 for Gmail + Calendar, YAML configuration system with Pydantic validation, structured logging. All tests pass.

Key files: `src/db/`, `src/auth/`, `src/config/`, `src/models/`

---

## Phase 2: Data Integration ✅

Full sync implemented for Gmail (initial + incremental via history API), Google Calendar (multi-calendar, recurring events), and Coda (document tracking + change detection). SyncCoordinator orchestrates all sources. Data stored in SQLite with FTS5 indexing.

Key files: `src/integrations/`, `src/repositories/`, `src/sync/coordinator.py`

---

## Phase 3: Email Intelligence 🔜

### Goal
Classify every email and pre-process each category so triage sessions are fast and information-dense.

### 3.1 Claude API Client

**File**: `src/ai/claude_client.py`

Anthropic SDK wrapper with retry logic, rate limiting, token tracking, and response caching.

```python
class ClaudeClient:
    async def complete(self, prompt: str, model: str, max_tokens: int) -> str
    async def complete_with_cache(self, prompt: str, cache_key: str) -> str
    def get_usage_stats(self) -> UsageStats
```

Supporting files:
- `src/ai/cache_manager.py` — SQLite-backed prompt/response cache
- `src/ai/rate_limiter.py` — token bucket rate limiter
- `src/ai/prompts/` — versioned prompt templates

Models by task (configured in `config.yaml`):
- Classification: `claude-haiku-4-5` (fast, cheap, runs on every email)
- Summarisation, drafts, synthesis: `claude-sonnet-4-6`

---

### 3.2 Email Classifier

**File**: `src/engine/email_classifier.py`

Runs immediately after each Gmail sync on any unclassified emails. Two-pass approach:

**Pass 1 — Heuristics** (no API call):
- Known sender domains → SYSTEM_NOTIFICATION (concur.com, sap.com, hibob.com, app.asana.com)
- Gmail labels CATEGORY_PROMOTIONS / CATEGORY_UPDATES → likely JUNK or NEWSLETTER
- List-Unsubscribe header present → NEWSLETTER
- Sender in `priority_senders` config → ACTION_REQUIRED candidate

**Pass 2 — Claude** (ambiguous emails only):
- Single-shot classification prompt with the email subject, sender, snippet
- Returns category + confidence score
- Uses `claude-haiku-4-5` for cost efficiency

```python
class EmailClassifier:
    async def classify(self, email: Email) -> EmailClassification
    async def classify_batch(self, emails: List[Email]) -> List[EmailClassification]

class EmailClassification:
    category: EmailCategory  # JUNK | NEWSLETTER | SYSTEM_NOTIFICATION | ACTION_REQUIRED | FYI
    confidence: float
    reasoning: str
```

Classification stored in `emails` table. Re-classification runs if sender patterns change.

---

### 3.3 Junk Detector

**File**: `src/engine/junk_detector.py`

For emails classified as JUNK: scores deletion confidence and determines whether to suggest delete vs unsubscribe.

```python
class JunkDetector:
    async def analyze(self, email: Email) -> JunkAnalysis

class JunkAnalysis:
    suggestion: Literal["delete", "unsubscribe", "review"]
    confidence: float
    reason: str  # e.g. "Unsolicited marketing from unknown sender"
    sender_history: SenderHistory  # How many times this sender has appeared
```

Sender memory: tracks per-sender junk history so known junk senders are auto-classified in future without an API call.

---

### 3.4 System Notification Parser

**File**: `src/engine/system_notification_parser.py`

Pattern-matching parsers for each Digital Science system. Extracts structured data before any Claude call, keeping costs minimal.

```python
class SystemNotificationParser:
    def parse(self, email: Email) -> SystemNotification | None

class SystemNotification:
    system: str          # "Concur" | "SAP" | "Bob" | "Asana" | "Other"
    action_type: str     # "approval_required" | "status_update" | "assignment" | ...
    entity_name: str     # e.g. "EXP-2891" or "Q2 Roadmap Review"
    status: str          # e.g. "pending_approval" | "approved" | "rejected"
    deadline: date | None
    requires_action: bool
    deep_link: str | None  # Link back to the system if available in email
```

Per-system patterns:
- **Concur**: subject regex for `Expense Report`, status from body, ref number extraction
- **SAP**: PO number, workflow step, approval chain position
- **Bob/HiBob**: event type (leave / new joiner / policy), employee name
- **Asana**: task name, project, assignee, due date from structured email body

Aggregation logic merges multiple system notifications into a single readable paragraph for the triage session.

---

### 3.5 Newsletter Summariser

**File**: `src/engine/newsletter_summarizer.py`

Summarises each newsletter email individually, then deduplicates across all newsletters in the same session window.

```python
class NewsletterSummarizer:
    async def summarize(self, email: Email) -> NewsletterSummary
    async def deduplicate(self, summaries: List[NewsletterSummary]) -> DeduplicatedDigest

class NewsletterSummary:
    source: str              # Newsletter name/sender
    key_points: List[str]   # 3–5 bullet points
    full_content: str        # Full email body kept for follow-up questions

class DeduplicatedDigest:
    stories: List[Story]     # Unique stories across all newsletters
    # Each story lists which newsletters covered it
```

Session-aware: each pre-processing run records which newsletter editions were processed. The 4pm run skips anything already surfaced at noon.

Full email content is retained in memory during the triage session so you can ask follow-up questions ("tell me more about that story", "is this relevant to our roadmap?") without re-fetching.

---

### 3.6 Action Processor

**File**: `src/engine/action_processor.py`

For ACTION_REQUIRED emails: determines whether the action is a reply, a non-email task, or both. Then generates accordingly.

```python
class ActionProcessor:
    async def process(self, email: Email, thread: List[Email]) -> ActionPlan

class ActionPlan:
    action_type: Literal["reply", "task", "both"]
    draft_reply: EmailDraft | None
    task: ObsidianTask | None
```

**Draft generation** (`src/engine/email_draft_generator.py`):
- Reads full thread for context
- Generates three options: short ACK, full reply, decline/defer
- Tone-matched to user profile from `config.yaml`
- Uses thread history to avoid repeating context already stated

**Task generation** (`src/engine/obsidian_task_writer.py`):
- Creates task in Obsidian Tasks plugin format
- Infers due date from email content where possible
- Tags: `#coco` always, plus `#email`, `#system`, or `#research` as appropriate
- Appends to `tasks/Backlog.md` — never overwrites existing content

```python
class ObsidianTaskWriter:
    def write_task(self, task: ObsidianTask) -> None
    def format_task(self, task: ObsidianTask) -> str
    # Output: - [ ] Task description 📅 2026-04-04 #email #coco
```

Vault path is read from `config.yaml → storage.obsidian_vault_path`.

---

### Phase 3 Success Criteria
- Classifier correctly categorises >90% of emails (validated against manual sample)
- System notifications parsed correctly for Concur, Bob, Asana (SAP if available)
- Newsletter summaries are accurate and cross-source dedup works
- Drafts are usable without heavy editing
- Tasks written to Obsidian correctly with right format and tags
- All processing for a 6-hour email window completes in under 60 seconds

---

## Phase 4: Triage Infrastructure

### Goal
Wire up the scheduled pre-processing runs, output writers, and session state so Phase 5 has clean data to work with.

### 4.1 Pre-processing Jobs

**File**: `src/scheduler/triage_jobs.py`

Two scheduled jobs replacing the single 7am briefing:

```yaml
# config.yaml
scheduler:
  jobs:
    noon_triage:
      enabled: true
      time: "12:00"
      window_start: "00:00"   # Covers midnight → noon
    afternoon_triage:
      enabled: true
      time: "16:00"
      window_start: "12:00"   # Covers noon → 4pm
      flag_eod_urgency: true  # Marks items that need same-day action
```

Each job:
1. Fetches emails classified since `window_start`
2. Runs category-specific processors in parallel
3. Stores results in `triage_sessions` table
4. Sends notification email

### 4.2 Session State

**File**: `src/triage/session_store.py`

Tracks what has been reviewed so the 4pm run doesn't repeat noon content and carry-forward works across days.

```python
class TriageSession:
    id: str
    run_time: datetime
    window_start: datetime
    window_end: datetime
    emails_processed: List[str]     # email IDs
    emails_reviewed: List[str]      # confirmed in triage session
    emails_deferred: List[str]      # explicitly deferred to next run
    tasks_created: List[str]        # Obsidian task references
    drafts_saved: List[str]         # Gmail draft IDs
```

### 4.3 Notification Email

**File**: `src/delivery/triage_notification.py`

Short, plain-text email sent when pre-processing completes:

```
Subject: Coco – Triage ready (noon run) · 14 emails

Processed 14 emails since midnight:
  · 5 junk (suggest delete)
  · 3 newsletters (2 unique stories)
  · 4 system notifications (2 need your approval)
  · 2 action required (drafts ready)

Open Claude Code and say "let's triage" to start.
```

### 4.4 Gmail Draft Saver

**File**: `src/delivery/gmail_draft_saver.py`

Saves confirmed drafts to Gmail Drafts via the existing Gmail client. Uses `create_draft` API endpoint — no SMTP required.

---

### Phase 4 Success Criteria
- Pre-processing jobs run reliably at noon and 4pm
- Notification email arrives within 2 minutes of job completion
- Session state correctly prevents re-surfacing reviewed content
- Obsidian writes are idempotent (no duplicate tasks on retry)
- Gmail drafts appear correctly in Drafts folder

---

## Phase 5: Triage Session

### Goal
Build the conversational Claude Code triage interface that presents pre-processed results and handles follow-up questions.

### 5.1 Triage Command

**File**: `src/triage/session.py`

Triggered when you say "let's triage" (or "triage", "inbox", etc.) in Claude Code. Loads the latest unreviewed triage session from the store and begins the category-by-category walkthrough.

Presentation order:
1. System notifications (often time-sensitive — Concur approvals, etc.)
2. Action required (drafts + tasks)
3. Newsletters (summaries + dedup)
4. Junk (suggest delete/unsubscribe)
5. FYI (brief summary, batch acknowledge)

### 5.2 Conversational Follow-up

Full email content is loaded into context at session start. This means you can ask:
- "Tell me more about that EU AI Act story" → Claude elaborates from the full email
- "Is this Asana task related to the Q2 roadmap?" → Claude cross-references with Coda context
- "Make that draft more direct and shorter" → Claude revises inline
- "Why did you flag that as junk?" → Claude explains the classification reasoning

No re-fetching required — everything is in context.

### 5.3 Carry-Forward

If you close the session mid-way, deferred items are stored in session state and surfaced at the start of the next session: *"You have 3 items from the noon run you deferred — want to start with those?"*

---

### Phase 5 Success Criteria
- Triage session completes a typical inbox in under 15 minutes
- Follow-up questions work without re-fetching email content
- Deferred items carry forward correctly
- Actions (task write, draft save, archive) execute reliably during session

---

## Phase 6: Polish & Feedback

### Junk Sender Memory
After you confirm a junk classification, that sender is remembered. Future emails from the same sender are auto-classified without an API call and don't appear in the triage queue — they're batched into a weekly "auto-archived junk" summary.

### Newsletter Subscription Quality
Track which newsletters you actually engage with vs skip every week. After 4 weeks of consistent skipping, Coco surfaces: *"You haven't engaged with [Newsletter] in 4 weeks — want to unsubscribe?"*

### Draft Quality Feedback
After a triage session, track which drafts were used as-is, which were edited, and which were discarded. Feed this back into prompt tuning over time.

### Weekly Summary
Every Monday morning: inbox trends from the past week, response rate, tasks created vs completed, newsletters worth keeping vs dropping.

---

## Build Order (within Phase 3)

```
1. src/ai/claude_client.py              — Foundation for all AI calls
2. src/engine/email_classifier.py       — Unlocks all downstream processing
3. src/engine/system_notification_parser.py  — High value, no AI cost
4. src/engine/obsidian_task_writer.py   — Needed by action processor
5. src/engine/newsletter_summarizer.py  — Self-contained, testable
6. src/engine/email_draft_generator.py  — Depends on Claude client
7. src/engine/action_processor.py       — Orchestrates draft + task
8. src/engine/junk_detector.py          — Lowest priority in Phase 3
```

---

## Configuration Changes from Original Plan

The following additions are needed in `config.yaml`:

```yaml
# Triage schedule (replaces single daily_briefing)
scheduler:
  jobs:
    noon_triage:
      enabled: true
      time: "12:00"
    afternoon_triage:
      enabled: true
      time: "16:00"

# Obsidian integration
storage:
  obsidian_vault_path: "/Users/akenall/Documents/Obsidian Vault"
  obsidian_backlog_file: "tasks/Backlog.md"
  obsidian_task_tag: "#coco"

# System notification senders
integrations:
  gmail:
    system_notification_senders:
      concur: ["@concur.com", "noreply@concursolutions.com"]
      sap: ["@sap.com"]
      bob: ["@hibob.com", "noreply@hibob.com"]
      asana: ["noreply@asana.com", "mail@asana.com"]

# AI model updates
ai:
  models:
    classification: "claude-haiku-4-5-20251001"
    email_draft: "claude-sonnet-4-6"
    newsletter_summary: "claude-sonnet-4-6"
    system_notification: "claude-haiku-4-5-20251001"
    context_synthesis: "claude-sonnet-4-6"
```

---

## Risk Register

| Risk | Mitigation |
|---|---|
| Classifier puts action email in junk | Confidence threshold — low-confidence JUNK always shown for review |
| System notification patterns break on email format change | Fallback to Claude classification; patterns are versioned |
| Obsidian write fails (vault path wrong, file locked) | Write to temp file first, log failure, surface in next session |
| Newsletter dedup misses related stories | Conservative — prefer showing twice over missing once |
| Triage session context window overflows | Cap emails per session; prioritise by score; summarise older items |
| API costs exceed budget | Haiku for classification (cheap), Sonnet only for drafts/summaries; monthly budget alert in config |
