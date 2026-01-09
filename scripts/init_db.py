#!/usr/bin/env python3
"""
Database Initialization Script

Initializes the SQLite database with the schema and verifies setup.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from dotenv import load_dotenv

from src.config.settings import init_settings, get_settings
from src.db.connection import init_db, get_db

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
    """Initialize the database"""
    print("=" * 60)
    print("AI Chief of Staff - Database Initialization")
    print("=" * 60)
    print()

    # Load environment variables
    load_dotenv()

    try:
        # Initialize settings
        print("📋 Loading configuration...")
        settings = init_settings()
        print(f"✓ Configuration loaded from config.yaml")
        print()

        # Get database path
        db_path = settings.get_database_path()
        print(f"📁 Database path: {db_path}")

        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        print("🔧 Initializing database connection...")
        db = init_db(db_path)
        print("✓ Database connection established")
        print()

        # Check if database already exists
        db_file = Path(db_path)
        if db_file.exists():
            size = db_file.stat().st_size
            print(f"⚠️  Database file already exists ({size} bytes)")
            response = input("   Do you want to reinitialize? This will NOT delete existing data (y/N): ")
            if response.lower() != 'y':
                print("   Skipping initialization")
                return
            print()

        # Initialize schema
        print("🏗️  Creating database schema...")
        db.initialize_schema()
        print("✓ Database schema created")
        print()

        # Verify tables
        print("🔍 Verifying database setup...")
        info = db.get_db_info()

        print(f"   Database size: {info['size_bytes']} bytes")
        print(f"   Tables created:")

        for table, count in info['table_counts'].items():
            if count >= 0:
                print(f"      ✓ {table}: {count} rows")
            else:
                print(f"      ✗ {table}: ERROR")

        print()
        print("=" * 60)
        print("✅ Database initialization complete!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("  1. Configure your settings in config/config.yaml")
        print("  2. Run: python scripts/authenticate.py")
        print("  3. Run: python src/main.py")
        print()

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print()
        print("Please ensure config.yaml exists:")
        print("  cp config/config.example.yaml config/config.yaml")
        sys.exit(1)

    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
