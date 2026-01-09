#!/usr/bin/env python3
"""
System Status Check Script

Verifies that all components are properly configured and working.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from dotenv import load_dotenv

from src.config.settings import init_settings
from src.db.connection import init_db
from src.auth.google_oauth import init_oauth

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.ConsoleRenderer(),
    ]
)

logger = structlog.get_logger()


def check_environment():
    """Check environment variables"""
    print("🔍 Checking environment variables...")

    load_dotenv()

    required_vars = [
        "ANTHROPIC_API_KEY",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
    ]

    optional_vars = [
        "CODA_API_TOKEN",
        "DATABASE_ENCRYPTION_KEY",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
    ]

    all_ok = True

    for var in required_vars:
        import os
        value = os.getenv(var)
        if value:
            print(f"   ✓ {var}: {'*' * 10}")
        else:
            print(f"   ✗ {var}: NOT SET (required)")
            all_ok = False

    for var in optional_vars:
        import os
        value = os.getenv(var)
        if value:
            print(f"   ✓ {var}: {'*' * 10}")
        else:
            print(f"   ⚠ {var}: not set (optional)")

    print()
    return all_ok


def check_configuration():
    """Check configuration file"""
    print("📋 Checking configuration...")

    try:
        settings = init_settings()
        print(f"   ✓ Config file loaded")
        print(f"   ✓ User: {settings.config.user.name} ({settings.config.user.email})")
        print(f"   ✓ Timezone: {settings.config.user.timezone}")
        print(f"   ✓ Briefing time: {settings.config.briefing.delivery_time}")
        print(f"   ✓ Database path: {settings.get_database_path()}")
        print()
        return True
    except FileNotFoundError as e:
        print(f"   ✗ Config file not found: {e}")
        print(f"   → Run: cp config/config.example.yaml config/config.yaml")
        print()
        return False
    except Exception as e:
        print(f"   ✗ Error loading config: {e}")
        print()
        return False


def check_database():
    """Check database"""
    print("🗄️  Checking database...")

    try:
        settings = init_settings()
        db_path = settings.get_database_path()
        db = init_db(db_path)

        if not Path(db_path).exists():
            print(f"   ✗ Database file does not exist")
            print(f"   → Run: python scripts/init_db.py")
            print()
            return False

        # Check tables
        info = db.get_db_info()
        print(f"   ✓ Database file exists ({info['size_bytes']} bytes)")

        tables = ["emails", "calendar_events", "coda_documents", "tasks", "decisions"]
        all_tables_ok = True

        for table in tables:
            count = info['table_counts'].get(table, -1)
            if count >= 0:
                print(f"   ✓ Table '{table}': {count} rows")
            else:
                print(f"   ✗ Table '{table}': missing")
                all_tables_ok = False

        if not all_tables_ok:
            print(f"   → Run: python scripts/init_db.py")

        print()
        return all_tables_ok

    except Exception as e:
        print(f"   ✗ Database error: {e}")
        print()
        return False


def check_oauth():
    """Check OAuth authentication"""
    print("🔐 Checking OAuth authentication...")

    try:
        settings = init_settings()
        oauth = init_oauth(
            settings.env.google_client_id,
            settings.env.google_client_secret,
        )

        if not oauth.is_authenticated():
            print(f"   ✗ Not authenticated with Google")
            print(f"   → Run: python scripts/authenticate.py")
            print()
            return False

        # Test API access
        try:
            gmail = oauth.get_gmail_service()
            profile = gmail.users().getProfile(userId='me').execute()
            print(f"   ✓ Gmail: {profile.get('emailAddress')}")

            calendar = oauth.get_calendar_service()
            calendar_list = calendar.calendarList().list(maxResults=1).execute()
            print(f"   ✓ Calendar: {len(calendar_list.get('items', []))} calendar(s)")

            print()
            return True

        except Exception as e:
            print(f"   ⚠  OAuth token exists but API test failed: {e}")
            print(f"   → You may need to re-authenticate: python scripts/authenticate.py")
            print()
            return False

    except Exception as e:
        print(f"   ✗ OAuth error: {e}")
        print()
        return False


def main():
    """Run all status checks"""
    print("=" * 60)
    print("AI Chief of Staff - System Status Check")
    print("=" * 60)
    print()

    results = {
        "Environment": check_environment(),
        "Configuration": check_configuration(),
        "Database": check_database(),
        "OAuth": check_oauth(),
    }

    print("=" * 60)
    print("Summary")
    print("=" * 60)

    all_ok = True
    for component, status in results.items():
        if status:
            print(f"   ✓ {component}: OK")
        else:
            print(f"   ✗ {component}: NEEDS ATTENTION")
            all_ok = False

    print()

    if all_ok:
        print("✅ All systems ready!")
        print()
        print("You can now:")
        print("  • Run the application: python src/main.py")
        print("  • Generate a test briefing: python scripts/trigger_briefing.py (Phase 2)")
        print()
    else:
        print("⚠️  Some components need attention. Please review the issues above.")
        print()

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
