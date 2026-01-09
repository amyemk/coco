"""
Database Connection and Utilities

Manages SQLite database connections with support for:
- Connection pooling
- WAL mode for better concurrency
- Automatic schema initialization
- Migration support
"""

import sqlite3
from pathlib import Path
from typing import Optional
import structlog

logger = structlog.get_logger()


class Database:
    """
    SQLite database connection manager with connection pooling
    and automatic schema initialization.
    """

    def __init__(self, db_path: str, enable_wal: bool = True):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
            enable_wal: Enable Write-Ahead Logging for better concurrency
        """
        self.db_path = Path(db_path)
        self.enable_wal = enable_wal
        self._connection: Optional[sqlite3.Connection] = None

        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("database_initialized", path=str(self.db_path))

    @property
    def connection(self) -> sqlite3.Connection:
        """
        Get database connection, creating if needed.

        Returns:
            SQLite connection with row factory configured
        """
        if self._connection is None:
            self._connection = self._create_connection()
        return self._connection

    def _create_connection(self) -> sqlite3.Connection:
        """
        Create and configure a new database connection.

        Returns:
            Configured SQLite connection
        """
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,  # Allow multi-threaded access
            timeout=30.0,  # 30 second timeout for locks
        )

        # Use Row factory for dict-like access to results
        conn.row_factory = sqlite3.Row

        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")

        # Enable WAL mode for better concurrency
        if self.enable_wal:
            conn.execute("PRAGMA journal_mode = WAL")

        # Optimize for performance
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
        conn.execute("PRAGMA temp_store = MEMORY")

        logger.info("database_connection_created", path=str(self.db_path))

        return conn

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Execute a SQL query.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            Cursor with query results
        """
        try:
            cursor = self.connection.execute(query, params)
            self.connection.commit()
            return cursor
        except sqlite3.Error as e:
            logger.error("database_query_error", query=query, error=str(e))
            raise

    def executemany(self, query: str, params_list: list[tuple]) -> sqlite3.Cursor:
        """
        Execute a SQL query with multiple parameter sets.

        Args:
            query: SQL query to execute
            params_list: List of parameter tuples

        Returns:
            Cursor with query results
        """
        try:
            cursor = self.connection.executemany(query, params_list)
            self.connection.commit()
            return cursor
        except sqlite3.Error as e:
            logger.error("database_executemany_error", query=query, error=str(e))
            raise

    def fetchone(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """
        Execute query and fetch one result.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            Single row or None
        """
        cursor = self.connection.execute(query, params)
        return cursor.fetchone()

    def fetchall(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """
        Execute query and fetch all results.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            List of rows
        """
        cursor = self.connection.execute(query, params)
        return cursor.fetchall()

    def initialize_schema(self, schema_path: Optional[Path] = None) -> None:
        """
        Initialize database schema from SQL file.

        Args:
            schema_path: Path to schema.sql file. If None, uses default location.
        """
        if schema_path is None:
            schema_path = Path(__file__).parent / "schema.sql"

        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        logger.info("initializing_database_schema", schema=str(schema_path))

        with open(schema_path, "r") as f:
            schema_sql = f.read()

        # Execute schema (may contain multiple statements)
        self.connection.executescript(schema_sql)
        self.connection.commit()

        logger.info("database_schema_initialized")

    def backup(self, backup_path: str) -> None:
        """
        Create a backup of the database.

        Args:
            backup_path: Path for backup file
        """
        backup_db_path = Path(backup_path)
        backup_db_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("creating_database_backup", backup_path=backup_path)

        # Use SQLite backup API
        backup_conn = sqlite3.connect(str(backup_db_path))
        with backup_conn:
            self.connection.backup(backup_conn)
        backup_conn.close()

        logger.info("database_backup_created", backup_path=backup_path)

    def vacuum(self) -> None:
        """
        Vacuum the database to reclaim space and optimize.
        """
        logger.info("vacuuming_database")
        self.connection.execute("VACUUM")
        logger.info("database_vacuumed")

    def get_table_count(self, table_name: str) -> int:
        """
        Get the number of rows in a table.

        Args:
            table_name: Name of the table

        Returns:
            Number of rows
        """
        result = self.fetchone(f"SELECT COUNT(*) as count FROM {table_name}")
        return result["count"] if result else 0

    def get_db_size(self) -> int:
        """
        Get database file size in bytes.

        Returns:
            Database file size in bytes
        """
        if self.db_path.exists():
            return self.db_path.stat().st_size
        return 0

    def get_db_info(self) -> dict:
        """
        Get database information and statistics.

        Returns:
            Dictionary with database info
        """
        tables = [
            "emails",
            "calendar_events",
            "coda_documents",
            "tasks",
            "decisions",
            "daily_briefings",
        ]

        info = {
            "path": str(self.db_path),
            "size_bytes": self.get_db_size(),
            "table_counts": {},
        }

        for table in tables:
            try:
                info["table_counts"][table] = self.get_table_count(table)
            except sqlite3.Error:
                info["table_counts"][table] = -1

        return info

    def close(self) -> None:
        """
        Close the database connection.
        """
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("database_connection_closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - commit or rollback."""
        if exc_type is not None:
            self.connection.rollback()
        else:
            self.connection.commit()
        return False

    def __del__(self):
        """Cleanup on deletion."""
        self.close()


# Global database instance (will be initialized in main.py)
_db_instance: Optional[Database] = None


def get_db() -> Database:
    """
    Get the global database instance.

    Returns:
        Database instance

    Raises:
        RuntimeError: If database not initialized
    """
    if _db_instance is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db_instance


def init_db(db_path: str, enable_wal: bool = True) -> Database:
    """
    Initialize the global database instance.

    Args:
        db_path: Path to database file
        enable_wal: Enable Write-Ahead Logging

    Returns:
        Initialized database instance
    """
    global _db_instance
    _db_instance = Database(db_path, enable_wal)
    return _db_instance
