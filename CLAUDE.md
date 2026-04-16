# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AI Chief of Staff** — a personal Python application for Chief Product Officers that syncs Gmail, Google Calendar, and Coda, then generates daily AI-powered briefings (priorities, email drafts, meeting follow-ups). Powered by Claude via the Anthropic API.

Current status: Phase 1 (Foundation) and Phase 2 (Data Integration) complete. Phase 3 (AI integration) is next.

## Commands

### Setup
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then fill in API keys
cp config/config.example.yaml config/config.yaml  # then edit preferences
python scripts/init_db.py     # initialize SQLite database
python scripts/authenticate.py  # OAuth flow for Google
```

### Run
```bash
python src/main.py            # start scheduler (runs syncs + 7AM briefing)
python scripts/sync_all.py    # one-shot sync all sources
python scripts/check_status.py  # check auth and DB status
```

### Tests
```bash
pytest                        # all tests
pytest tests/unit/            # unit tests only
pytest tests/integration/     # integration tests only
pytest -m "not slow"          # skip slow tests
pytest tests/unit/test_config.py::test_load_config  # single test
pytest --cov=src --cov-report=html  # with coverage
```

### Code Quality
```bash
black src/ tests/             # format (line length 100)
ruff check src/ tests/        # lint
mypy src/                     # type-check (strict mode)
```

## Architecture

### Initialization chain
`src/main.py` → `init_settings()` → `init_db()` → `init_oauth()` → `SyncCoordinator` → APScheduler jobs. Each subsystem uses a module-level singleton (`_settings_instance`, `_db_instance`, `_oauth_instance`) retrieved via `get_settings()` / `get_db()` / `get_oauth()`. Always call the `init_*` functions before `get_*`.

### Configuration
Two-layer config: `config/config.yaml` (YAML, validated via Pydantic `AppConfig`) merged with `.env` (loaded via `pydantic-settings` `EnvSettings`). Access via `get_settings()` which returns a `Settings` object exposing both `.config` (AppConfig) and `.env` (EnvSettings). The `AppConfig` model hierarchy lives in `src/config/settings.py`.

### Database
SQLite with WAL mode, FTS5 virtual tables for full-text search, and triggers to keep FTS indexes in sync. Schema is defined in `src/db/schema.sql` and applied via `Database.initialize_schema()`. Key tables: `emails`, `calendar_events`, `coda_documents`, `tasks`, `decisions`, `daily_briefings`, `email_drafts`, `feedback`, `sync_status`. JSON arrays are stored as TEXT columns. The `Database` class in `src/db/connection.py` is the low-level wrapper; `src/repositories/` provides the data-access layer per entity.

### Data flow
`SyncCoordinator` (`src/sync/coordinator.py`) dispatches to `GmailSyncService`, `CalendarSyncService`, and `CodaSyncService` (all under `src/integrations/`). Services normalize external API responses into internal models (`src/models/`), then persist via repositories. The scheduler in `src/main.py` triggers these on intervals (Gmail: 15 min, Calendar: 30 min, Coda: 60 min).

### Design patterns
- **Repository pattern**: `src/repositories/` abstracts all DB access; swap real repos with mocks in tests.
- **Dependency injection**: Services accept optional injected dependencies (defaulting to `None` → auto-constructed), enabling clean unit testing.
- **Global singletons with explicit init**: settings, DB, and OAuth are module-level singletons initialized once in `main.py`; tests must call `init_*` or pass deps directly.

### Planned but not yet implemented
- `src/ai/` — Claude API client (`ClaudeClient`) and `PromptLibrary`
- `src/briefing/` — `BriefingOrchestrator`, formatter, delivery
- `src/engine/` — `PriorityScorer`, `EmailDraftGenerator`, `ActionItemExtractor`
- `src/delivery/` — email/Slack delivery services
- `src/feedback/` — feedback loop handling
- `src/scheduler/` — may be expanded beyond the inline scheduler in `main.py`
- Vector store (ChromaDB) for semantic search — storage path configured but not yet wired up

## Key Conventions

- **Logging**: `structlog` throughout; log with structured key=value pairs (e.g., `logger.info("event_name", key=value)`). JSON format in production.
- **Async**: `asyncio` is used in `main.py` and planned for AI/delivery layers; sync services currently use sync I/O. `pytest-asyncio` with `asyncio_mode = auto`.
- **Type hints**: Required everywhere (`mypy` strict). Third-party libs without stubs (google, chromadb, apscheduler) are exempted in `pyproject.toml`.
- **Models**: Pydantic v2 for config validation. Data models for emails/events are in `src/models/` as dataclasses or Pydantic models.
- **AI models**: Per-task model selection is configured in `AIModelsConfig` — use `claude-3-5-sonnet-20241022` for drafts/synthesis, `claude-3-haiku-20240307` for cheaper scoring tasks.
