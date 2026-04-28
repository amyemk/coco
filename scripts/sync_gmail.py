#!/usr/bin/env python3
"""
Manual Gmail Sync Script

Manually triggers Gmail synchronization.
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
from src.integrations.gmail.sync_service import GmailSyncService

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ]
)

logger = structlog.get_logger()


def main():
    """Run manual Gmail sync"""
    print("=" * 60)
    print("AI Chief of Staff - Gmail Sync")
    print("=" * 60)
    print()

    # Load environment
    load_dotenv()

    try:
        # Initialize
        print("📋 Loading configuration...")
        settings = init_settings()

        print("🔧 Initializing database...")
        db = init_db(settings.get_database_path())

        print("🔐 Initializing OAuth...")
        oauth = init_oauth(
            settings.env.google_client_id,
            settings.env.google_client_secret,
        )

        if not oauth.is_authenticated():
            print("❌ Not authenticated! Run: python scripts/authenticate.py")
            sys.exit(1)

        print("✓ Initialization complete")
        print()

        # Create service
        print("📧 Creating Gmail sync service...")
        gmail_service = GmailSyncService()
        print()

        # Ask sync type
        print("Sync Options:")
        print("  1. Initial sync (last 30 days, max 500 emails)")
        print("  2. Incremental sync (only new/changed since last sync)")
        print()

        choice = input("Choose option (1 or 2): ").strip()
        print()

        if choice == "1":
            print("🚀 Starting initial sync...")
            print("   (This may take several minutes...)")
            print()
            count = gmail_service.initial_sync()
        elif choice == "2":
            print("🚀 Starting incremental sync...")
            print()
            count = gmail_service.incremental_sync()
        else:
            print("❌ Invalid choice")
            sys.exit(1)

        print()
        print("=" * 60)
        print(f"✅ Gmail Sync Complete - {count} emails synced")
        print("=" * 60)
        print()

        # Show stats
        stats = gmail_service.get_sync_stats()
        print("Gmail Stats:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

        print()

    except KeyboardInterrupt:
        print("\n\n❌ Sync cancelled by user")
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ Error during sync: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
