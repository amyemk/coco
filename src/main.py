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
from src.sync.coordinator import SyncCoordinator

# APScheduler imports
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

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

# Global instances
scheduler = None
sync_coordinator = None


async def initialize_application():
    """
    Initialize the application:
    - Load configuration
    - Set up database
    - Initialize integrations
    - Configure scheduler
    """
    global sync_coordinator

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

    # Initialize sync coordinator
    logger.info("initializing_sync_coordinator")
    sync_coordinator = SyncCoordinator()
    logger.info("sync_coordinator_initialized")

    logger.info("application_initialized")


async def sync_gmail_job():
    """Scheduled job to sync Gmail"""
    logger.info("scheduled_gmail_sync_started")
    try:
        count = sync_coordinator.sync_gmail_only()
        logger.info("scheduled_gmail_sync_complete", count=count)
    except Exception as e:
        logger.error("scheduled_gmail_sync_error", error=str(e))


async def sync_calendar_job():
    """Scheduled job to sync Calendar"""
    logger.info("scheduled_calendar_sync_started")
    try:
        count = sync_coordinator.sync_calendar_only()
        logger.info("scheduled_calendar_sync_complete", count=count)
    except Exception as e:
        logger.error("scheduled_calendar_sync_error", error=str(e))


async def sync_coda_job():
    """Scheduled job to sync Coda"""
    logger.info("scheduled_coda_sync_started")
    try:
        count = sync_coordinator.sync_coda_only()
        logger.info("scheduled_coda_sync_complete", count=count)
    except Exception as e:
        logger.error("scheduled_coda_sync_error", error=str(e))


async def run_triage_job(run_type: str):
    """
    Run the triage pre-processing pipeline (noon or afternoon).
    Classifies emails, processes each category, stores results, sends notification.
    """
    logger.info("triage_job_started", run_type=run_type)
    try:
        settings = get_settings()
        from src.triage.pre_processor import TriagePreProcessor
        from src.delivery.triage_notification import TriageNotificationSender

        processor = TriagePreProcessor(settings)
        result = await processor.run(run_type=run_type)

        # Send "triage ready" notification email
        notifier = TriageNotificationSender(settings)
        sent = notifier.send(result)

        from src.triage.session_store import TriageSessionStore
        if sent:
            TriageSessionStore().mark_notification_sent(result.session_id)

        logger.info(
            "triage_job_complete",
            run_type=run_type,
            session_id=result.session_id,
            total_processed=result.total_processed,
            action_items=result.action_items_count,
            notification_sent=sent,
        )
    except Exception as e:
        logger.error("triage_job_error", run_type=run_type, error=str(e))


async def noon_triage_job():
    """Scheduled noon triage run (covers midnight → noon)."""
    await run_triage_job("noon")


async def afternoon_triage_job():
    """Scheduled afternoon triage run (covers noon → 4pm)."""
    await run_triage_job("afternoon")


async def run_scheduler():
    """
    Run the scheduler for periodic tasks:
    - Gmail sync (every 15 minutes)
    - Calendar sync (every 30 minutes)
    - Coda sync (every 60 minutes)
    - Daily briefing generation (7 AM) - Phase 4
    """
    global scheduler

    settings = get_settings()

    logger.info("starting_scheduler")

    # Create scheduler
    scheduler = AsyncIOScheduler()

    # Get scheduler config
    scheduler_config = settings.config.scheduler

    # Add Gmail sync job (every N minutes)
    gmail_job = scheduler_config.jobs.get("gmail_sync")
    if gmail_job and gmail_job.enabled and gmail_job.interval_minutes:
        scheduler.add_job(
            sync_gmail_job,
            trigger=IntervalTrigger(minutes=gmail_job.interval_minutes),
            id="gmail_sync",
            name="Gmail Sync",
            replace_existing=True,
        )
        logger.info("gmail_sync_job_scheduled", interval_minutes=gmail_job.interval_minutes)

    # Add Calendar sync job (every N minutes)
    calendar_job = scheduler_config.jobs.get("calendar_sync")
    if calendar_job and calendar_job.enabled and calendar_job.interval_minutes:
        scheduler.add_job(
            sync_calendar_job,
            trigger=IntervalTrigger(minutes=calendar_job.interval_minutes),
            id="calendar_sync",
            name="Calendar Sync",
            replace_existing=True,
        )
        logger.info("calendar_sync_job_scheduled", interval_minutes=calendar_job.interval_minutes)

    # Add Coda sync job (every N minutes)
    coda_job = scheduler_config.jobs.get("coda_sync")
    if coda_job and coda_job.enabled and coda_job.interval_minutes:
        scheduler.add_job(
            sync_coda_job,
            trigger=IntervalTrigger(minutes=coda_job.interval_minutes),
            id="coda_sync",
            name="Coda Sync",
            replace_existing=True,
        )
        logger.info("coda_sync_job_scheduled", interval_minutes=coda_job.interval_minutes)

    # Add noon triage job
    noon_job = scheduler_config.jobs.get("noon_triage")
    if noon_job and noon_job.enabled and noon_job.time:
        hour, minute = noon_job.time.split(":")
        scheduler.add_job(
            noon_triage_job,
            trigger=CronTrigger(
                hour=int(hour),
                minute=int(minute),
                timezone=scheduler_config.timezone,
            ),
            id="noon_triage",
            name="Noon Triage Pre-Processing",
            replace_existing=True,
        )
        logger.info("noon_triage_job_scheduled", time=noon_job.time)

    # Add afternoon triage job
    afternoon_job = scheduler_config.jobs.get("afternoon_triage")
    if afternoon_job and afternoon_job.enabled and afternoon_job.time:
        hour, minute = afternoon_job.time.split(":")
        scheduler.add_job(
            afternoon_triage_job,
            trigger=CronTrigger(
                hour=int(hour),
                minute=int(minute),
                timezone=scheduler_config.timezone,
            ),
            id="afternoon_triage",
            name="Afternoon Triage Pre-Processing",
            replace_existing=True,
        )
        logger.info("afternoon_triage_job_scheduled", time=afternoon_job.time)

    # Start the scheduler
    scheduler.start()

    logger.info("scheduler_started")
    print("\n✅ Application initialized successfully!")
    print("📋 Phase 1 (Foundation) complete - Database and OAuth ready")
    print("✅ Phase 2 (Data Integration) complete - Gmail, Calendar, Coda sync active")
    print("")
    print("Scheduled Jobs:")
    if gmail_job and gmail_job.enabled:
        print(f"  • Gmail sync: every {gmail_job.interval_minutes} minutes")
    else:
        print("  • Gmail sync: disabled")

    if calendar_job and calendar_job.enabled:
        print(f"  • Calendar sync: every {calendar_job.interval_minutes} minutes")
    else:
        print("  • Calendar sync: disabled")

    if coda_job and coda_job.enabled:
        print(f"  • Coda sync: every {coda_job.interval_minutes} minutes")
    else:
        print("  • Coda sync: disabled")

    if noon_job and noon_job.enabled:
        print(f"  • Noon triage:      {noon_job.time} (classify + process emails since midnight)")
    else:
        print("  • Noon triage:      disabled")

    if afternoon_job and afternoon_job.enabled:
        print(f"  • Afternoon triage: {afternoon_job.time} (classify + process emails since noon)")
    else:
        print("  • Afternoon triage: disabled")

    print("")
    print("✅ Phase 3 (AI Intelligence) complete — email classifier, drafts, Obsidian tasks")
    print("✅ Phase 4 (Triage Infrastructure) complete — pre-processing jobs, notification, session state")
    print("⏳ Phase 5 (Triage Session) — interactive Claude Code triage interface next")
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
        if scheduler:
            scheduler.shutdown()
        print("\n👋 Application stopped\n")
    except Exception as e:
        logger.error("application_error", error=str(e), exc_info=True)
        if scheduler:
            scheduler.shutdown()
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
