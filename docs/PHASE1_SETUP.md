# Phase 1 Setup Guide

This guide walks you through setting up the foundational components of the AI Chief of Staff: database, configuration, and OAuth authentication.

## Prerequisites

- Python 3.11 or higher
- A Google account with Gmail and Calendar
- Basic familiarity with command line

## Step-by-Step Setup

### 1. Install Dependencies

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

Expected output:
```
Successfully installed anthropic google-auth google-api-python-client ...
```

### 2. Configure Environment Variables

```bash
# Copy the environment template
cp .env.example .env

# Edit the .env file
nano .env  # or your preferred editor
```

**Required variables:**

```env
# Get from https://console.anthropic.com
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Get from Google Cloud Console (see below)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret

# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
DATABASE_ENCRYPTION_KEY=<generated-key>
```

#### Getting Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project:
   - Click "Select a project" → "New Project"
   - Name it "AI Chief of Staff"
   - Click "Create"

3. Enable APIs:
   - Go to "APIs & Services" → "Library"
   - Search for and enable:
     - Gmail API
     - Google Calendar API

4. Create OAuth credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Click "Configure Consent Screen" (if prompted):
     - Select "External"
     - Fill in app name: "AI Chief of Staff"
     - Add your email as developer contact
     - Click "Save and Continue"
   - Application type: "Desktop app"
   - Name: "AI Chief of Staff Desktop"
   - Click "Create"
   - Copy the **Client ID** and **Client Secret**
   - Paste into your `.env` file

### 3. Configure Application Settings

```bash
# Copy the configuration template
cp config/config.example.yaml config/config.yaml

# Edit your configuration
nano config/config.yaml
```

**Key settings to update:**

```yaml
user:
  name: "Your Name"
  email: "your.email@company.com"
  timezone: "America/Los_Angeles"  # Your timezone
  title: "Chief Product Officer"

briefing:
  delivery_time: "07:00"  # When you want daily briefings (24-hour format)
  delivery_method: "email"

integrations:
  gmail:
    enabled: true
    sync_interval_minutes: 15
    priority_senders:
      - "ceo@company.com"
      - "important@company.com"

  calendar:
    enabled: true
    sync_interval_minutes: 30

  coda:
    enabled: true
    tracked_docs:
      # Add your Coda document IDs here
      # - id: "abc123"
      #   name: "Product Roadmap"
      #   type: "roadmap"
```

### 4. Initialize Database

```bash
python scripts/init_db.py
```

Expected output:
```
============================================================
AI Chief of Staff - Database Initialization
============================================================

📋 Loading configuration...
✓ Configuration loaded from config.yaml

📁 Database path: ./data/ai_chief_of_staff.db
🔧 Initializing database connection...
✓ Database connection established

🏗️  Creating database schema...
✓ Database schema created

🔍 Verifying database setup...
   Database size: 20480 bytes
   Tables created:
      ✓ emails: 0 rows
      ✓ calendar_events: 0 rows
      ✓ coda_documents: 0 rows
      ✓ tasks: 0 rows
      ✓ decisions: 0 rows
      ✓ daily_briefings: 0 rows

============================================================
✅ Database initialization complete!
============================================================
```

### 5. Authenticate with Google

```bash
python scripts/authenticate.py
```

This will:
1. Open your browser automatically
2. Ask you to sign in to Google
3. Show a permissions screen
4. You may see "Google hasn't verified this app" - click "Advanced" → "Go to AI Chief of Staff (unsafe)"
5. Grant permissions for Gmail and Calendar
6. Close the browser when done

Expected output:
```
============================================================
AI Chief of Staff - Google OAuth Authentication
============================================================

📋 Loading configuration...
✓ Configuration loaded

🔐 Initializing OAuth...
🌐 Starting OAuth authentication flow...

A browser window will open for you to authorize the application.
...

============================================================
✅ Authentication successful!
============================================================

🧪 Testing API access...
   ✓ Gmail: Connected as your.email@gmail.com
   ✓ Calendar: Access confirmed
```

### 6. Verify Setup

```bash
python scripts/check_status.py
```

This comprehensive check verifies:
- Environment variables are set
- Configuration is valid
- Database is initialized
- OAuth authentication works
- API access is functional

Expected output (all green checkmarks):
```
============================================================
AI Chief of Staff - System Status Check
============================================================

🔍 Checking environment variables...
   ✓ ANTHROPIC_API_KEY: **********
   ✓ GOOGLE_CLIENT_ID: **********
   ✓ GOOGLE_CLIENT_SECRET: **********
   ...

📋 Checking configuration...
   ✓ Config file loaded
   ✓ User: Your Name (your.email@company.com)
   ...

🗄️  Checking database...
   ✓ Database file exists
   ✓ Table 'emails': 0 rows
   ...

🔐 Checking OAuth authentication...
   ✓ Gmail: your.email@gmail.com
   ✓ Calendar: 1 calendar(s)

============================================================
Summary
============================================================
   ✓ Environment: OK
   ✓ Configuration: OK
   ✓ Database: OK
   ✓ OAuth: OK

✅ All systems ready!
```

### 7. Test the Application

```bash
python src/main.py
```

Expected output:
```
✅ Application initialized successfully!
📋 Phase 1 (Foundation) complete - Database and OAuth ready
⏳ Phase 2 (Data Integration) - Coming next

Press Ctrl+C to stop
```

If you see this, **Phase 1 is complete!** 🎉

## Troubleshooting

### Problem: "config.yaml not found"

**Solution:**
```bash
cp config/config.example.yaml config/config.yaml
# Then edit config/config.yaml with your settings
```

### Problem: "GOOGLE_CLIENT_ID not set"

**Solution:**
1. Make sure you copied `.env.example` to `.env`
2. Add your Google OAuth credentials to `.env`
3. Verify the file is in the project root directory

### Problem: "Google hasn't verified this app"

**Solution:**
This is expected for personal projects. Click:
1. "Advanced"
2. "Go to AI Chief of Staff (unsafe)"
3. This is safe - you're authorizing your own app

### Problem: OAuth authentication fails

**Solution:**
1. Verify Gmail and Calendar APIs are enabled in Google Cloud Console
2. Check that OAuth credentials are for "Desktop app" type
3. Try using an incognito/private browser window
4. Make sure redirect URI includes `http://localhost`

### Problem: Database permission error

**Solution:**
```bash
# Ensure data directory exists and is writable
mkdir -p data
chmod 755 data
```

### Problem: Import errors

**Solution:**
```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt

# Verify Python version
python --version  # Should be 3.11 or higher
```

## Running Tests

Verify everything works:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_database.py
```

Expected output:
```
======================== test session starts =========================
collected 15 items

tests/unit/test_config.py ........                          [ 53%]
tests/unit/test_database.py .......                         [100%]

======================== 15 passed in 2.34s ==========================
```

## What You've Accomplished

✅ **Database Setup**
- SQLite database initialized with full schema
- Full-text search enabled
- 10+ tables ready for data

✅ **Configuration Management**
- YAML-based configuration
- Environment variable support
- Type-safe settings with validation

✅ **OAuth Authentication**
- Google OAuth 2.0 flow working
- Gmail API access
- Calendar API access
- Automatic token refresh

✅ **Development Tools**
- Comprehensive test suite
- Code quality tools (Black, Ruff, MyPy)
- Logging infrastructure

## Next Steps

Now that Phase 1 is complete, you're ready for:

**Phase 2: Data Integration** (Weeks 2-3)
- Sync emails from Gmail
- Sync calendar events
- Sync Coda documents
- Incremental updates

See [IMPLEMENTATION_ROADMAP.md](../IMPLEMENTATION_ROADMAP.md) for details.

## File Structure Created

```
coco/
├── data/
│   ├── ai_chief_of_staff.db       # SQLite database
│   └── tokens/
│       └── google_token.json       # OAuth tokens (encrypted)
├── logs/
│   └── app.log                     # Application logs
├── config/
│   └── config.yaml                 # Your configuration
├── .env                            # Environment variables
└── src/
    ├── db/                         # Database utilities
    ├── config/                     # Configuration management
    └── auth/                       # OAuth authentication
```

## Security Notes

🔒 **Keep these files secure (never commit to git):**
- `.env` - Contains API keys
- `config/config.yaml` - Contains personal settings
- `data/tokens/` - Contains OAuth tokens
- `data/ai_chief_of_staff.db` - Contains your data

All sensitive files are already in `.gitignore`.

## Getting Help

- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) (coming in Phase 2)
- Review [TECHNICAL_SPEC.md](../TECHNICAL_SPEC.md) for architecture details
- Open an issue on GitHub

---

**Congratulations on completing Phase 1!** 🚀

Your AI Chief of Staff now has a solid foundation. The database is ready to store emails, calendar events, and documents. OAuth authentication is configured to securely access your Gmail and Calendar. Everything is set up for the next phase where we'll start syncing real data.
