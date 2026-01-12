"""
Coda Sync Service

Manages synchronization of Coda documents to local database.
"""

from typing import List, Optional
from datetime import datetime

import structlog

from src.integrations.coda.client import CodaClient
from src.db.connection import get_db

logger = structlog.get_logger()


class CodaSyncService:
    """
    Service for syncing Coda documents to database
    """

    def __init__(self, api_token: str):
        """
        Initialize Coda sync service.

        Args:
            api_token: Coda API token
        """
        if not api_token:
            logger.warning("coda_api_token_not_provided_sync_disabled")
            self.enabled = False
            self.client = None
        else:
            self.client = CodaClient(api_token)
            self.enabled = True

        self.db = get_db()

    def sync_document(self, doc_id: str, doc_type: str = "document") -> bool:
        """
        Sync a specific Coda document.

        Args:
            doc_id: Coda document ID
            doc_type: Type of document (roadmap, okrs, strategy, etc.)

        Returns:
            True if successful
        """
        if not self.enabled:
            logger.warning("coda_sync_disabled_no_api_token")
            return False

        logger.info("coda_document_sync_started", doc_id=doc_id, doc_type=doc_type)

        try:
            # Get document metadata
            doc = self.client.get_doc(doc_id)

            # Get document content
            content = self.client.get_doc_content(doc_id)

            # Check if we have a previous version
            previous = self._get_previous_version(doc_id)

            # Detect changes
            change_summary = None
            if previous and previous["content"] != content:
                change_summary = f"Document updated at {doc.get('updatedAt')}"
                logger.info("coda_document_changed", doc_id=doc_id)

            # Save to database
            import json

            self.db.execute(
                """
                INSERT INTO coda_documents (
                    id, name, doc_type, content, last_modified,
                    modified_by, url, change_summary, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    content = excluded.content,
                    last_modified = excluded.last_modified,
                    modified_by = excluded.modified_by,
                    change_summary = excluded.change_summary,
                    metadata = excluded.metadata,
                    synced_at = CURRENT_TIMESTAMP
                """,
                (
                    doc_id,
                    doc.get("name", "Untitled"),
                    doc_type,
                    content,
                    doc.get("updatedAt"),
                    doc.get("updatedBy", {}).get("name", "Unknown"),
                    doc.get("browserLink", ""),
                    change_summary,
                    json.dumps({
                        "workspace": doc.get("workspace", {}),
                        "folder": doc.get("folder", {}),
                    }),
                ),
            )

            logger.info("coda_document_synced", doc_id=doc_id, name=doc.get("name"))

            return True

        except Exception as e:
            logger.error("coda_document_sync_error", error=str(e), doc_id=doc_id)
            return False

    def sync_tracked_documents(self, doc_configs: List[dict]) -> int:
        """
        Sync all tracked documents from configuration.

        Args:
            doc_configs: List of document configs with 'id', 'name', 'type'

        Returns:
            Number of documents synced successfully
        """
        if not self.enabled:
            logger.warning("coda_sync_disabled")
            return 0

        logger.info("coda_tracked_sync_started", count=len(doc_configs))

        synced_count = 0

        for doc_config in doc_configs:
            doc_id = doc_config.get("id")
            doc_type = doc_config.get("type", "document")

            if not doc_id:
                logger.warning("coda_doc_missing_id", config=doc_config)
                continue

            if self.sync_document(doc_id, doc_type):
                synced_count += 1

        # Update sync status
        self._update_sync_status(
            status="success" if synced_count > 0 else "failure",
            items_synced=synced_count,
        )

        logger.info("coda_tracked_sync_complete", synced=synced_count)

        return synced_count

    def _get_previous_version(self, doc_id: str) -> Optional[dict]:
        """
        Get the previously synced version of a document.

        Args:
            doc_id: Document ID

        Returns:
            Previous document data or None
        """
        row = self.db.fetchone(
            "SELECT content FROM coda_documents WHERE id = ?",
            (doc_id,),
        )

        if row:
            return {"content": row["content"]}

        return None

    def _update_sync_status(
        self,
        status: str,
        items_synced: int,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update sync status in database.

        Args:
            status: Sync status (success, failure)
            items_synced: Number of items synced
            error_message: Error message if failed
        """
        import json

        self.db.execute(
            """
            INSERT INTO sync_status (
                source, last_sync_time, last_sync_status,
                items_synced, error_message, metadata
            ) VALUES (?, datetime('now'), ?, ?, ?, ?)
            """,
            (
                "coda",
                status,
                items_synced,
                error_message,
                json.dumps({}),
            ),
        )

    def get_sync_stats(self) -> dict:
        """
        Get synchronization statistics.

        Returns:
            Dictionary with sync stats
        """
        if not self.enabled:
            return {
                "enabled": False,
                "total_documents": 0,
            }

        # Get total documents
        result = self.db.fetchone("SELECT COUNT(*) as count FROM coda_documents")
        total_docs = result["count"] if result else 0

        # Get last sync info
        row = self.db.fetchone(
            """
            SELECT * FROM sync_status
            WHERE source = 'coda'
            ORDER BY last_sync_time DESC
            LIMIT 1
            """
        )

        stats = {
            "enabled": True,
            "total_documents": total_docs,
            "last_sync_time": row["last_sync_time"] if row else None,
            "last_sync_status": row["last_sync_status"] if row else None,
            "last_items_synced": row["items_synced"] if row else 0,
        }

        return stats
