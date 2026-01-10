"""SQLite state management for tracking processed messages."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite
import structlog

logger = structlog.get_logger(__name__)


class StateManager:
    """Manages application state using SQLite."""

    def __init__(self, db_path: Path):
        """
        Initialize state manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.current_run_id: Optional[str] = None

    async def initialize(self) -> None:
        """Initialize database schema."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP,
                    status TEXT NOT NULL,
                    period_start TIMESTAMP NOT NULL,
                    period_end TIMESTAMP NOT NULL,
                    messages_processed INTEGER DEFAULT 0,
                    error_message TEXT
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_messages (
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    processed_at TIMESTAMP NOT NULL,
                    run_id TEXT NOT NULL,
                    PRIMARY KEY (channel_id, message_id),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                )
                """
            )

            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_processed_messages_run
                ON processed_messages(run_id)
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS channel_cache (
                    channel_id INTEGER PRIMARY KEY,
                    username TEXT,
                    title TEXT,
                    is_private BOOLEAN,
                    last_updated TIMESTAMP
                )
                """
            )

            await db.commit()
            logger.info("State database initialized")

    async def start_run(
        self,
        period_start: datetime,
        period_end: datetime,
    ) -> str:
        """
        Start a new run.

        Args:
            period_start: Start of time period
            period_end: End of time period

        Returns:
            Run ID
        """
        run_id = str(uuid.uuid4())
        self.current_run_id = run_id

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO runs (run_id, started_at, status, period_start, period_end)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, datetime.now(), "running", period_start, period_end),
            )
            await db.commit()

        logger.info("Started run", run_id=run_id)
        return run_id

    async def complete_run(
        self,
        run_id: str,
        messages_processed: int,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Mark a run as completed.

        Args:
            run_id: Run ID
            messages_processed: Number of messages processed
            error_message: Optional error message if run failed
        """
        status = "failed" if error_message else "completed"

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE runs
                SET completed_at = ?, status = ?, messages_processed = ?, error_message = ?
                WHERE run_id = ?
                """,
                (datetime.now(), status, messages_processed, error_message, run_id),
            )
            await db.commit()

        logger.info("Run completed", run_id=run_id, status=status)

    async def get_last_successful_run(self) -> Optional[tuple[datetime, datetime]]:
        """
        Get the time period of the last successful run.

        Returns:
            Tuple of (period_start, period_end) or None
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT period_start, period_end
                FROM runs
                WHERE status = 'completed'
                ORDER BY completed_at DESC
                LIMIT 1
                """
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return (
                        datetime.fromisoformat(row[0]),
                        datetime.fromisoformat(row[1]),
                    )
        return None

    async def get_processed_message_ids(self) -> set[tuple[int, int]]:
        """
        Get set of all processed message IDs.

        Returns:
            Set of (channel_id, message_id) tuples
        """
        processed_ids: set[tuple[int, int]] = set()

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT channel_id, message_id FROM processed_messages"
            ) as cursor:
                async for row in cursor:
                    processed_ids.add((row[0], row[1]))

        return processed_ids

    async def mark_messages_processed(
        self,
        run_id: str,
        message_ids: list[tuple[int, int]],
    ) -> None:
        """
        Mark messages as processed.

        Args:
            run_id: Run ID
            message_ids: List of (channel_id, message_id) tuples
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany(
                """
                INSERT OR REPLACE INTO processed_messages
                (channel_id, message_id, processed_at, run_id)
                VALUES (?, ?, ?, ?)
                """,
                [(cid, mid, datetime.now(), run_id) for cid, mid in message_ids],
            )
            await db.commit()

        logger.debug("Marked messages as processed", count=len(message_ids))
