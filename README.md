# AI Chief of Staff

A personal AI assistant designed for Chief Product Officers that delivers intelligent daily briefings, helps prioritize work, drafts email replies, and maintains continuous understanding of your product organization.

## Overview

The AI Chief of Staff sits across strategy, execution, and communication—translating vision into action while reducing cognitive load and context switching. It synthesizes information from Gmail, Google Calendar, and Coda to provide:

- **Daily Briefings**: Smart morning digests with priorities, email drafts, and key updates
- **Email Assistance**: AI-generated reply drafts that match your tone and context
- **Meeting Intelligence**: Automated follow-ups and action item extraction
- **Strategic Context**: Continuous tracking of decisions, roadmaps, and OKRs

## Key Features

### Daily Briefing (7 AM delivery)
- 🗂️ **Today's Priorities**: Synthesized from calendar, emails, and Coda docs
- 📬 **Smart Email Drafts**: Suggested replies for high-priority messages
- 🎙️ **Meeting Follow-ups**: Action items from recent meetings
- 📊 **Product Org Updates**: Key changes to roadmaps, OKRs, strategy docs

### Intelligent Assistance
- **Priority Scoring**: AI-powered email and task prioritization
- **Context Awareness**: Semantic understanding of your org's decisions and "why"
- **Change Detection**: Alerts when important documents are modified
- **Inconsistency Flagging**: Surfaces tensions between decisions and commitments

## Architecture

```
AI Chief of Staff
├── Daily Briefing Generator
├── Context Engine (maintains org knowledge)
├── Action Engine (prioritizes and generates drafts)
└── AI/LLM Layer (powered by Claude)

Integrations:
├── Gmail (OAuth 2.0)
├── Google Calendar (OAuth 2.0)
└── Coda (API token)

Storage:
├── SQLite (structured data)
└── ChromaDB (vector embeddings)
```

## Technology Stack

- **Language**: Python 3.11+
- **AI**: Anthropic Claude API
- **Database**: SQLite with FTS5
- **Vector Store**: ChromaDB
- **Scheduler**: APScheduler
- **APIs**: Gmail, Google Calendar, Coda

## Quick Start

### Prerequisites
- Python 3.11 or higher
- Google Cloud account (for Gmail/Calendar APIs)
- Anthropic API key
- Coda account (optional)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd coco

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up configuration
cp .env.example .env
cp config/config.example.yaml config/config.yaml

# Edit .env and add your API keys
# Edit config.yaml with your preferences

# Initialize database
python scripts/init_db.py

# Authenticate with Google
python scripts/authenticate.py
```

### Configuration

1. **Google Cloud Setup**:
   - Create a project at https://console.cloud.google.com
   - Enable Gmail API and Google Calendar API
   - Create OAuth 2.0 credentials
   - Add credentials to `.env`

2. **Anthropic API**:
   - Get API key from https://console.anthropic.com
   - Add to `.env` as `ANTHROPIC_API_KEY`

3. **Coda** (optional):
   - Generate API token at https://coda.io/account
   - Add to `.env` as `CODA_API_TOKEN`
   - Configure tracked docs in `config.yaml`

### Usage

```bash
# Run manual sync
python scripts/sync_all.py

# Generate briefing manually (for testing)
python scripts/trigger_briefing.py

# Start the scheduler (runs daily at 7 AM)
python src/main.py
```

## Project Structure

```
coco/
├── src/                      # Source code
│   ├── ai/                   # AI/LLM integration
│   ├── auth/                 # Authentication
│   ├── briefing/             # Daily briefing generation
│   ├── config/               # Configuration management
│   ├── db/                   # Database setup and migrations
│   ├── delivery/             # Email/Slack delivery
│   ├── engine/               # Core logic (scoring, generation)
│   ├── integrations/         # External API integrations
│   │   ├── gmail/
│   │   ├── calendar/
│   │   └── coda/
│   ├── models/               # Data models
│   ├── repositories/         # Data access layer
│   ├── scheduler/            # Job scheduling
│   ├── sync/                 # Data synchronization
│   └── utils/                # Utilities
├── tests/                    # Test suite
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
├── scripts/                  # Utility scripts
├── docs/                     # Documentation
├── data/                     # Local data storage
├── logs/                     # Application logs
├── config/                   # Configuration files
├── requirements.txt          # Python dependencies
├── PRD.md                    # Product requirements
├── TECHNICAL_SPEC.md         # Technical specification
├── ARCHITECTURE.md           # System architecture
├── IMPLEMENTATION_ROADMAP.md # Development roadmap
└── README.md                 # This file
```

## Documentation

- [Product Requirements Document](PRD.md)
- [Technical Specification](TECHNICAL_SPEC.md)
- [System Architecture](ARCHITECTURE.md)
- [Implementation Roadmap](IMPLEMENTATION_ROADMAP.md)
- [User Guide](docs/USER_GUIDE.md) *(coming soon)*
- [Configuration Guide](docs/CONFIGURATION.md) *(coming soon)*

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run specific test suite
pytest tests/unit/
pytest tests/integration/

# Run with coverage
pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type checking
mypy src/
```

## Roadmap

### ✅ Phase 1: Foundation (Weeks 1-2)
- Project setup and configuration
- OAuth authentication
- Database initialization

### 🚧 Phase 2: Data Integration (Weeks 2-3)
- Gmail sync
- Calendar sync
- Coda sync

### ⏳ Phase 3: AI Integration (Weeks 3-4)
- Claude API client
- Priority scoring
- Email draft generation
- Task extraction

### ⏳ Phase 4: Daily Briefing MVP (Weeks 4-5)
- Briefing generation
- Email delivery
- Scheduled jobs

### ⏳ Phase 5: Polish & Testing (Weeks 5-6)
- Real data testing
- UX improvements
- Performance optimization

### ⏳ Phase 6: Iteration (Weeks 6+)
- Feedback-based improvements
- Advanced features
- Optional web UI

See [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) for detailed timeline.

## Security & Privacy

- **Local Storage**: All data stored locally in encrypted SQLite database
- **No Third-Party Sharing**: Data only sent to APIs you explicitly configure
- **Secure Credentials**: OAuth tokens and API keys encrypted at rest
- **Data Retention**: Configurable retention policies for emails, events, docs
- **Privacy First**: No telemetry, no usage tracking, full user control

## Success Metrics

- >80% briefing open rate within first hour
- >50% of AI-generated replies used or edited
- At least 3 actionable tasks surfaced per day
- Subjective: "Saves me >1 hour per day"

## Contributing

This is currently a personal project. If you'd like to contribute or adapt for your own use, please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

[To be determined]

## Support

For issues, questions, or feedback:
- Open an issue on GitHub
- Email: [your-email]

## Acknowledgments

- Built with [Anthropic Claude](https://www.anthropic.com/claude)
- Inspired by the need for better executive productivity tools
- Thanks to the open-source community

---

**Status**: In active development (Phase 1)

**Last Updated**: 2026-01-09
