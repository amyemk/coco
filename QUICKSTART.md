# Quick Start Guide

Get your AI Chief of Staff up and running in minutes.

## Prerequisites

Before you begin, ensure you have:

- **Python 3.11+** installed
- A **Google account** with Gmail and Calendar
- An **Anthropic API key** ([get one here](https://console.anthropic.com))
- (Optional) A **Coda account** and API token

## Step 1: Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd coco

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Configure Google Cloud

### 2.1 Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services > Library**
4. Enable the following APIs:
   - Gmail API
   - Google Calendar API

### 2.2 Create OAuth Credentials

1. Go to **APIs & Services > Credentials**
2. Click **Create Credentials > OAuth client ID**
3. Choose **Desktop app** as the application type
4. Download the credentials JSON file
5. Note the **Client ID** and **Client Secret**

## Step 3: Get API Keys

### 3.1 Anthropic API Key

1. Sign up at [Anthropic Console](https://console.anthropic.com)
2. Create a new API key
3. Copy the key (it starts with `sk-ant-`)

### 3.2 Coda API Token (Optional)

1. Go to [Coda Account Settings](https://coda.io/account)
2. Generate a new API token
3. Copy the token

## Step 4: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your credentials
nano .env  # or use your preferred editor
```

Add your credentials to `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret-here
CODA_API_TOKEN=your-coda-token-here
DATABASE_ENCRYPTION_KEY=<generate-with-command-below>
```

Generate a database encryption key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Step 5: Configure Application

```bash
# Copy configuration template
cp config/config.example.yaml config/config.yaml

# Edit configuration
nano config/config.yaml
```

Update these key settings:

```yaml
user:
  name: "Your Name"
  email: "your.email@company.com"
  timezone: "America/Los_Angeles"  # Your timezone

briefing:
  delivery_time: "07:00"  # When to receive daily briefing

integrations:
  coda:
    tracked_docs:
      - id: "your-coda-doc-id"
        name: "Product Roadmap"
        type: "roadmap"
```

## Step 6: Initialize Database

```bash
python scripts/init_db.py
```

This creates the SQLite database and necessary tables.

## Step 7: Authenticate with Google

```bash
python scripts/authenticate.py
```

This will:
1. Open a browser window
2. Ask you to sign in to Google
3. Request permissions for Gmail and Calendar
4. Save your OAuth tokens locally

## Step 8: Test the Setup

### Sync your data

```bash
# Sync Gmail
python scripts/sync_gmail.py

# Sync Calendar
python scripts/sync_calendar.py

# Sync Coda (if configured)
python scripts/sync_coda.py
```

### Generate a test briefing

```bash
python scripts/trigger_briefing.py
```

This generates a briefing and sends it to your email.

## Step 9: Run the Application

```bash
python src/main.py
```

This starts the scheduler that will:
- Generate daily briefings at your configured time (default: 7 AM)
- Sync Gmail every 15 minutes
- Sync Calendar every 30 minutes
- Sync Coda every 60 minutes

## Step 10: Keep It Running

### Run in background (Linux/Mac)

```bash
# Using nohup
nohup python src/main.py &

# Or using screen
screen -S ai-chief-of-staff
python src/main.py
# Press Ctrl+A then D to detach
```

### Run as a service (Linux)

Create `/etc/systemd/system/ai-chief-of-staff.service`:

```ini
[Unit]
Description=AI Chief of Staff
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/coco
Environment="PATH=/path/to/coco/venv/bin"
ExecStart=/path/to/coco/venv/bin/python src/main.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-chief-of-staff
sudo systemctl start ai-chief-of-staff
sudo systemctl status ai-chief-of-staff
```

## Troubleshooting

### Google Authentication Fails

**Problem**: Browser doesn't open or authentication fails

**Solution**:
- Ensure your OAuth credentials are correct in `.env`
- Check that Gmail and Calendar APIs are enabled
- Try using an incognito/private browser window
- Make sure redirect URI is configured correctly

### Database Permission Error

**Problem**: Cannot create or write to database

**Solution**:
```bash
# Ensure data directory exists and is writable
mkdir -p data
chmod 755 data
```

### API Rate Limits

**Problem**: Hitting Gmail or Calendar API limits

**Solution**:
- Increase sync intervals in `config/config.yaml`
- Use incremental sync instead of full sync
- Check your API quota in Google Cloud Console

### Daily Briefing Not Sending

**Problem**: Briefing doesn't arrive at scheduled time

**Solution**:
- Check application logs: `tail -f logs/app.log`
- Verify timezone in config matches your location
- Ensure application is running
- Check SMTP settings in `.env`
- Test manual trigger: `python scripts/trigger_briefing.py`

### Claude API Errors

**Problem**: AI-generated content fails or is low quality

**Solution**:
- Verify your Anthropic API key is valid
- Check API quota/credits at Anthropic Console
- Review prompts in `src/ai/prompts/`
- Adjust temperature settings in config

## Next Steps

Once your AI Chief of Staff is running:

1. **Review your first briefing** - Check email at your configured time
2. **Provide feedback** - Use thumbs up/down on suggestions
3. **Customize configuration** - Adjust priorities, filters, and sections
4. **Monitor performance** - Check logs and metrics
5. **Iterate** - Fine-tune based on your workflow

## Getting Help

- Check the [User Guide](docs/USER_GUIDE.md) for detailed documentation
- Review [Configuration Guide](docs/CONFIGURATION.md) for advanced settings
- See [Troubleshooting Guide](docs/TROUBLESHOOTING.md) for common issues
- Open an issue on GitHub for bugs or questions

## Security Reminders

- **Never commit** `.env` or `config/config.yaml` to version control
- **Keep API keys secure** - treat them like passwords
- **Rotate credentials** periodically
- **Use app-specific passwords** for Gmail SMTP (not your main password)
- **Enable 2FA** on all accounts (Google, Anthropic, Coda)

---

**Congratulations!** Your AI Chief of Staff is now ready to help you stay on top of your product organization. 🎉
