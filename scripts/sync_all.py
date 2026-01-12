#!/usr/bin/env python3
"""
Manual Sync All Script

Manually triggers synchronization of all data sources.
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
from src.sync.coordinator import SyncCoordinator

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
    """Run manual sync of all sources"""
    print("=" * 60)
    print("AI Chief of Staff - Manual Sync All")
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

        # Create coordinator
        print("🔄 Creating sync coordinator...")
        coordinator = SyncCoordinator()
        print()

        # Ask if initial sync
        response = input("Perform initial sync (more data, slower)? (y/N): ")
        initial = response.lower() == 'y'
        print()

        # Run sync
        print("🚀 Starting synchronization...")
        if initial:
            print("   (This may take several minutes...)")
        print()

        results = coordinator.sync_all(initial=initial)

        # Display results
        print()
        print("=" * 60)
        print("✅ Sync Complete!")
        print("=" * 60)
        print()

        for source, result in results.items():
            if result["enabled"]:
                if result["error"]:
                    print(f"❌ {source.upper()}: ERROR - {result['error']}")
                else:
                    print(f"✓ {source.upper()}: {result['synced']} items synced")
            else:
                print(f"⊘ {source.upper()}: disabled")

        print()

        # Show stats
        print("Current Stats:")
        stats = coordinator.get_sync_stats()

        for source, source_stats in stats.items():
            print(f"\n{source.upper()}:")
            for key, value in source_stats.items():
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
