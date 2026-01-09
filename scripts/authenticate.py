#!/usr/bin/env python3
"""
Google OAuth Authentication Script

Guides the user through OAuth authentication for Gmail and Calendar APIs.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from dotenv import load_dotenv

from src.config.settings import init_settings, get_settings
from src.auth.google_oauth import init_oauth, get_oauth

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.ConsoleRenderer(),
    ]
)

logger = structlog.get_logger()


def main():
    """Run OAuth authentication flow"""
    print("=" * 60)
    print("AI Chief of Staff - Google OAuth Authentication")
    print("=" * 60)
    print()

    # Load environment variables
    load_dotenv()

    try:
        # Initialize settings
        print("📋 Loading configuration...")
        settings = init_settings()
        print("✓ Configuration loaded")
        print()

        # Get OAuth credentials from environment
        client_id = settings.env.google_client_id
        client_secret = settings.env.google_client_secret

        if not client_id or not client_secret:
            print("❌ Error: Google OAuth credentials not found in .env file")
            print()
            print("Please add the following to your .env file:")
            print("  GOOGLE_CLIENT_ID=your_client_id_here")
            print("  GOOGLE_CLIENT_SECRET=your_client_secret_here")
            print()
            print("To get these credentials:")
            print("  1. Go to https://console.cloud.google.com")
            print("  2. Create a project or select an existing one")
            print("  3. Enable Gmail API and Google Calendar API")
            print("  4. Create OAuth 2.0 credentials (Desktop app)")
            print("  5. Copy the Client ID and Client Secret")
            print()
            sys.exit(1)

        # Initialize OAuth
        print("🔐 Initializing OAuth...")
        oauth = init_oauth(client_id, client_secret)

        # Check if already authenticated
        if oauth.is_authenticated():
            print("✓ You are already authenticated!")
            print()
            response = input("Do you want to re-authenticate? (y/N): ")
            if response.lower() != 'y':
                print("Keeping existing authentication.")
                return

            print()
            print("Revoking existing credentials...")
            oauth.revoke()
            print("✓ Existing credentials revoked")
            print()

        # Run authentication flow
        print("🌐 Starting OAuth authentication flow...")
        print()
        print("A browser window will open for you to authorize the application.")
        print("Please:")
        print("  1. Sign in to your Google account")
        print("  2. Grant permissions for Gmail and Calendar access")
        print("  3. You may see a warning that the app is unverified - click 'Advanced' then 'Go to app'")
        print()
        input("Press Enter to continue...")
        print()

        # Authenticate
        creds = oauth.authenticate(force=True)

        print()
        print("=" * 60)
        print("✅ Authentication successful!")
        print("=" * 60)
        print()

        # Test the authentication
        print("🧪 Testing API access...")

        try:
            # Test Gmail
            gmail = oauth.get_gmail_service()
            profile = gmail.users().getProfile(userId='me').execute()
            print(f"   ✓ Gmail: Connected as {profile.get('emailAddress')}")

            # Test Calendar
            calendar = oauth.get_calendar_service()
            calendar_list = calendar.calendarList().list(maxResults=1).execute()
            print(f"   ✓ Calendar: Access confirmed")

        except Exception as e:
            print(f"   ⚠️  Warning: API test failed: {e}")
            print("   Authentication succeeded but API access test failed.")
            print("   Please verify that Gmail and Calendar APIs are enabled in Google Cloud Console.")

        print()
        print("Next steps:")
        print("  1. Run initial data sync: python scripts/sync_all.py")
        print("  2. Generate a test briefing: python scripts/trigger_briefing.py")
        print("  3. Start the application: python src/main.py")
        print()

    except KeyboardInterrupt:
        print()
        print("❌ Authentication cancelled by user")
        sys.exit(1)

    except Exception as e:
        print(f"❌ Error during authentication: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
