"""
Sync Coordinator

Orchestrates synchronization across all data sources (Gmail, Calendar, Coda).
"""

from typing import Optional

import structlog

from src.config.settings import get_settings
from src.integrations.gmail.sync_service import GmailSyncService
from src.integrations.calendar.sync_service import CalendarSyncService
from src.integrations.coda.sync_service import CodaSyncService

logger = structlog.get_logger()


class SyncCoordinator:
    """
    Coordinates synchronization across all data sources
    """

    def __init__(
        self,
        gmail_service: Optional[GmailSyncService] = None,
        calendar_service: Optional[CalendarSyncService] = None,
        coda_service: Optional[CodaSyncService] = None,
    ):
        """
        Initialize sync coordinator.

        Args:
            gmail_service: Gmail sync service (creates new if None)
            calendar_service: Calendar sync service (creates new if None)
            coda_service: Coda sync service (creates new if None)
        """
        self.settings = get_settings()

        # Initialize services
        self.gmail_service = gmail_service or GmailSyncService()
        self.calendar_service = calendar_service or CalendarSyncService()

        # Initialize Coda only if enabled and token available
        coda_token = self.settings.env.coda_api_token
        self.coda_service = coda_service or CodaSyncService(coda_token)

        logger.info("sync_coordinator_initialized")

    def sync_all(self, initial: bool = False) -> dict:
        """
        Sync all enabled data sources.

        Args:
            initial: If True, perform initial sync (more data)

        Returns:
            Dictionary with sync results
        """
        logger.info("sync_all_started", initial=initial)

        results = {
            "gmail": {"enabled": False, "synced": 0, "error": None},
            "calendar": {"enabled": False, "synced": 0, "error": None},
            "coda": {"enabled": False, "synced": 0, "error": None},
        }

        # Sync Gmail
        if self.settings.is_integration_enabled("gmail"):
            results["gmail"]["enabled"] = True
            try:
                if initial:
                    days_back = self.settings.config.integrations.gmail.initial_sync_days
                    max_emails = self.settings.config.integrations.gmail.max_results_per_sync
                    count = self.gmail_service.initial_sync(
                        days_back=days_back,
                        max_emails=max_emails,
                    )
                else:
                    count = self.gmail_service.incremental_sync()

                results["gmail"]["synced"] = count

                logger.info("gmail_sync_complete", count=count, initial=initial)

            except Exception as e:
                logger.error("gmail_sync_failed", error=str(e))
                results["gmail"]["error"] = str(e)

        # Sync Calendar
        if self.settings.is_integration_enabled("calendar"):
            results["calendar"]["enabled"] = True
            try:
                days_back = self.settings.config.integrations.calendar.lookback_days
                days_ahead = self.settings.config.integrations.calendar.lookahead_days
                calendar_ids = self.settings.config.integrations.calendar.calendars

                count = self.calendar_service.full_sync(
                    days_back=days_back,
                    days_ahead=days_ahead,
                    calendar_ids=calendar_ids,
                )

                results["calendar"]["synced"] = count

                logger.info("calendar_sync_complete", count=count)

            except Exception as e:
                logger.error("calendar_sync_failed", error=str(e))
                results["calendar"]["error"] = str(e)

        # Sync Coda
        if self.settings.is_integration_enabled("coda") and self.coda_service.enabled:
            results["coda"]["enabled"] = True
            try:
                doc_configs = [
                    {
                        "id": doc.id,
                        "name": doc.name,
                        "type": doc.type,
                    }
                    for doc in self.settings.config.integrations.coda.tracked_docs
                ]

                count = self.coda_service.sync_tracked_documents(doc_configs)

                results["coda"]["synced"] = count

                logger.info("coda_sync_complete", count=count)

            except Exception as e:
                logger.error("coda_sync_failed", error=str(e))
                results["coda"]["error"] = str(e)

        logger.info("sync_all_complete", results=results)

        return results

    def sync_gmail_only(self, initial: bool = False) -> int:
        """
        Sync only Gmail.

        Args:
            initial: If True, perform initial sync

        Returns:
            Number of emails synced
        """
        if not self.settings.is_integration_enabled("gmail"):
            logger.warning("gmail_integration_disabled")
            return 0

        try:
            if initial:
                days_back = self.settings.config.integrations.gmail.initial_sync_days
                max_emails = self.settings.config.integrations.gmail.max_results_per_sync
                return self.gmail_service.initial_sync(days_back, max_emails)
            else:
                return self.gmail_service.incremental_sync()

        except Exception as e:
            logger.error("gmail_sync_only_failed", error=str(e))
            return 0

    def sync_calendar_only(self) -> int:
        """
        Sync only Calendar.

        Returns:
            Number of events synced
        """
        if not self.settings.is_integration_enabled("calendar"):
            logger.warning("calendar_integration_disabled")
            return 0

        try:
            days_back = self.settings.config.integrations.calendar.lookback_days
            days_ahead = self.settings.config.integrations.calendar.lookahead_days
            calendar_ids = self.settings.config.integrations.calendar.calendars

            return self.calendar_service.full_sync(
                days_back=days_back,
                days_ahead=days_ahead,
                calendar_ids=calendar_ids,
            )

        except Exception as e:
            logger.error("calendar_sync_only_failed", error=str(e))
            return 0

    def sync_coda_only(self) -> int:
        """
        Sync only Coda documents.

        Returns:
            Number of documents synced
        """
        if not self.settings.is_integration_enabled("coda") or not self.coda_service.enabled:
            logger.warning("coda_integration_disabled_or_no_token")
            return 0

        try:
            doc_configs = [
                {
                    "id": doc.id,
                    "name": doc.name,
                    "type": doc.type,
                }
                for doc in self.settings.config.integrations.coda.tracked_docs
            ]

            return self.coda_service.sync_tracked_documents(doc_configs)

        except Exception as e:
            logger.error("coda_sync_only_failed", error=str(e))
            return 0

    def get_sync_stats(self) -> dict:
        """
        Get synchronization statistics for all sources.

        Returns:
            Dictionary with stats for each source
        """
        stats = {
            "gmail": self.gmail_service.get_sync_stats(),
            "calendar": self.calendar_service.get_sync_stats(),
            "coda": self.coda_service.get_sync_stats(),
        }

        logger.info("sync_stats_retrieved", stats=stats)

        return stats
