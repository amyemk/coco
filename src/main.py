"""
AI Chief of Staff - Main Application Entry Point

This module initializes and runs the AI Chief of Staff application,
including the scheduler for daily briefings and periodic syncs.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from dotenv import load_dotenv

from src.config.settings import init_settings, get_settings
from src.db.connection import init_db, get_db
from src.auth.google_oauth import init_oauth, get_oauth

# Load environment variables
load_dotenv()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()


async def initialize_application():
    """
    Initialize the application:
    - Load configuration
    - Set up database
    - Initialize integrations
    - Configure scheduler
    """
    logger.info("initializing_application", version="1.0.0")

    # Load configuration
    logger.info("loading_configuration")
    settings = init_settings()
    logger.info("configuration_loaded")

    # Initialize database
    logger.info("initializing_database")
    db_path = settings.get_database_path()
    db = init_db(db_path)

    # Check if schema needs initialization
    if db.get_table_count("emails") == -1:
        logger.info("database_schema_not_found_initializing")
        db.initialize_schema()

    logger.info("database_initialized", **db.get_db_info())

    # Initialize OAuth
    logger.info("initializing_oauth")
    oauth = init_oauth(
        settings.env.google_client_id,
        settings.env.google_client_secret,
    )

    if not oauth.is_authenticated():
        logger.error("not_authenticated_run_authenticate_script")
        print("\n❌ Not authenticated! Please run: python scripts/authenticate.py\n")
        sys.exit(1)

    logger.info("oauth_initialized")

    # TODO: Initialize integrations
    # TODO: Configure scheduler

    logger.info("application_initialized")


async def run_scheduler():
    """
    Run the scheduler for periodic tasks:
    - Daily briefing generation (7 AM)
    - Gmail sync (every 15 minutes)
    - Calendar sync (every 30 minutes)
    - Coda sync (every 60 minutes)
    """
    logger.info("starting_scheduler")

    # TODO: Configure APScheduler
    # TODO: Add jobs for each sync task
    # TODO: Add job for daily briefing

    logger.info("scheduler_started_placeholder_mode")
    print("\n✅ Application initialized successfully!")
    print("📋 Phase 1 (Foundation) complete - Database and OAuth ready")
    print("⏳ Phase 2 (Data Integration) - Coming next")
    print("\nPress Ctrl+C to stop\n")

    # Keep the scheduler running
    while True:
        await asyncio.sleep(60)


async def main():
    """Main application entry point"""
    try:
        logger.info("starting_ai_chief_of_staff")

        # Initialize application
        await initialize_application()

        # Run scheduler
        await run_scheduler()

    except KeyboardInterrupt:
        logger.info("application_stopped_by_user")
        print("\n👋 Application stopped\n")
    except Exception as e:
        logger.error("application_error", error=str(e), exc_info=True)
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
