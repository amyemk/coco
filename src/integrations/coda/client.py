"""
Coda API Client

Wrapper around Coda API for fetching documents and tables.
"""

from typing import List, Optional, Dict, Any

import httpx
import structlog

logger = structlog.get_logger()


class CodaClient:
    """
    Coda API client for document operations
    """

    BASE_URL = "https://coda.io/apis/v1"

    def __init__(self, api_token: str):
        """
        Initialize Coda client.

        Args:
            api_token: Coda API token
        """
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        logger.info("coda_client_initialized")

    def list_docs(self) -> List[Dict[str, Any]]:
        """
        List all accessible documents.

        Returns:
            List of document objects
        """
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.BASE_URL}/docs",
                    headers=self.headers,
                    timeout=30.0,
                )
                response.raise_for_status()

                data = response.json()
                docs = data.get("items", [])

                logger.info("coda_docs_listed", count=len(docs))
                return docs

        except httpx.HTTPError as e:
            logger.error("coda_list_docs_error", error=str(e))
            raise

    def get_doc(self, doc_id: str) -> Dict[str, Any]:
        """
        Get a specific document by ID.

        Args:
            doc_id: Coda document ID

        Returns:
            Document object
        """
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.BASE_URL}/docs/{doc_id}",
                    headers=self.headers,
                    timeout=30.0,
                )
                response.raise_for_status()

                doc = response.json()
                logger.debug("coda_doc_retrieved", doc_id=doc_id, name=doc.get("name"))
                return doc

        except httpx.HTTPError as e:
            logger.error("coda_get_doc_error", error=str(e), doc_id=doc_id)
            raise

    def list_tables(self, doc_id: str) -> List[Dict[str, Any]]:
        """
        List all tables in a document.

        Args:
            doc_id: Coda document ID

        Returns:
            List of table objects
        """
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.BASE_URL}/docs/{doc_id}/tables",
                    headers=self.headers,
                    timeout=30.0,
                )
                response.raise_for_status()

                data = response.json()
                tables = data.get("items", [])

                logger.info("coda_tables_listed", doc_id=doc_id, count=len(tables))
                return tables

        except httpx.HTTPError as e:
            logger.error("coda_list_tables_error", error=str(e), doc_id=doc_id)
            raise

    def list_rows(
        self,
        doc_id: str,
        table_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List rows in a table.

        Args:
            doc_id: Coda document ID
            table_id: Table ID or name
            limit: Maximum number of rows to return

        Returns:
            List of row objects
        """
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.BASE_URL}/docs/{doc_id}/tables/{table_id}/rows",
                    headers=self.headers,
                    params={"limit": limit},
                    timeout=30.0,
                )
                response.raise_for_status()

                data = response.json()
                rows = data.get("items", [])

                logger.info(
                    "coda_rows_listed",
                    doc_id=doc_id,
                    table_id=table_id,
                    count=len(rows),
                )
                return rows

        except httpx.HTTPError as e:
            logger.error(
                "coda_list_rows_error",
                error=str(e),
                doc_id=doc_id,
                table_id=table_id,
            )
            raise

    def get_doc_content(self, doc_id: str) -> str:
        """
        Get document content as text.
        Note: This is a simplified version. Full implementation would
        parse all pages and sections.

        Args:
            doc_id: Coda document ID

        Returns:
            Document content as string
        """
        try:
            # Get doc metadata
            doc = self.get_doc(doc_id)

            # Get all tables
            tables = self.list_tables(doc_id)

            # Build content string
            content_parts = [
                f"Document: {doc.get('name', 'Untitled')}",
                f"Updated: {doc.get('updatedAt', 'Unknown')}",
                ""
            ]

            # Add table contents
            for table in tables:
                table_name = table.get("name", "Untitled Table")
                content_parts.append(f"\n## {table_name}\n")

                try:
                    rows = self.list_rows(doc_id, table["id"], limit=50)
                    for row in rows:
                        # Extract cell values
                        values = row.get("values", {})
                        row_text = " | ".join(str(v) for v in values.values())
                        content_parts.append(row_text)

                except Exception as e:
                    logger.warning(
                        "coda_table_content_error",
                        error=str(e),
                        table_id=table["id"],
                    )

            content = "\n".join(content_parts)

            logger.info(
                "coda_doc_content_retrieved",
                doc_id=doc_id,
                length=len(content),
            )

            return content

        except Exception as e:
            logger.error("coda_get_doc_content_error", error=str(e), doc_id=doc_id)
            raise
