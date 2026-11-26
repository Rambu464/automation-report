"""SQLite local state database initialization and connection management (`data/newstent_state.db`).

Implements the 4 tables defined in SAD.md Section 2:
1. `takeout_registry` — Persistent Daily -> Monthly takeout synchronization
2. `negative_issue_memory` — Cross-day negative sentiment & canonical Newstrend consistency
3. `media_master_hypestat` — Media Tier (Binokular & Client Custom Tier), Hypestat, Newswire/Media Bazar
4. `ai_batch_cache` — Per-row AI classification cache keyed by Hash(ID + Client_Config_Version)
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from src.settings import get_settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS takeout_registry (
    report_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    page_url TEXT NOT NULL DEFAULT '',
    normalized_url TEXT NOT NULL DEFAULT '',
    status_takeout TEXT NOT NULL DEFAULT 'Takeout',
    alasan_spam TEXT NOT NULL DEFAULT '',
    is_sensitive_negative INTEGER NOT NULL DEFAULT 0,
    recorded_date TEXT NOT NULL,
    PRIMARY KEY (client_id, report_id)
);

CREATE INDEX IF NOT EXISTS idx_takeout_client_norm_url
    ON takeout_registry (client_id, normalized_url);

CREATE TABLE IF NOT EXISTS negative_issue_memory (
    issue_hash TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    nama_isu TEXT NOT NULL,
    canonical_newstrend TEXT NOT NULL,
    locked_sentiment TEXT NOT NULL DEFAULT 'negative',
    last_seen TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_neg_issue_client
    ON negative_issue_memory (client_id);

CREATE TABLE IF NOT EXISTS media_master_hypestat (
    domain TEXT PRIMARY KEY,
    media_name TEXT NOT NULL DEFAULT '',
    tier_bino TEXT NOT NULL DEFAULT '',
    client_custom_tier_json TEXT NOT NULL DEFAULT '{}',
    media_type_detail TEXT NOT NULL DEFAULT 'Organik',
    hypestat_daily_visitor INTEGER NOT NULL DEFAULT 0,
    media_value INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ai_batch_cache (
    cache_key TEXT PRIMARY KEY,
    json_result TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    client_id TEXT NOT NULL,
    report_type TEXT NOT NULL DEFAULT 'daily',
    cutoff_datetime TEXT NOT NULL DEFAULT '',
    latest_job_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    total_raw INTEGER NOT NULL DEFAULT 0,
    total_clean INTEGER NOT NULL DEFAULT 0,
    total_takeout INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS client_media_tier (
    client_id TEXT NOT NULL,
    media_key TEXT NOT NULL,
    media_name TEXT NOT NULL DEFAULT '',
    custom_tier TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (client_id, media_key)
);

CREATE INDEX IF NOT EXISTS idx_client_media_tier_client
    ON client_media_tier (client_id);
"""


class StateDatabase:
    """Thin, thread-safe SQLite manager for Newstent's local state database."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else get_settings().sqlite_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        """Ensure all core tables, indexes, and safe schema migrations are applied."""
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            self._migrate_takeout_registry_composite_pk(conn)

    @staticmethod
    def _migrate_takeout_registry_composite_pk(conn: sqlite3.Connection) -> None:
        """Upgrade legacy takeout_registry(report_id PK) -> PRIMARY KEY (client_id, report_id) without data loss."""
        cols = conn.execute("PRAGMA table_info(takeout_registry)").fetchall()
        pk_cols = [c["name"] for c in cols if c["pk"] > 0]
        if set(pk_cols) == {"client_id", "report_id"}:
            return
        conn.executescript(
            """
            CREATE TABLE takeout_registry_new (
                report_id TEXT NOT NULL,
                client_id TEXT NOT NULL,
                page_url TEXT NOT NULL DEFAULT '',
                normalized_url TEXT NOT NULL DEFAULT '',
                status_takeout TEXT NOT NULL DEFAULT 'Takeout',
                alasan_spam TEXT NOT NULL DEFAULT '',
                is_sensitive_negative INTEGER NOT NULL DEFAULT 0,
                recorded_date TEXT NOT NULL,
                PRIMARY KEY (client_id, report_id)
            );
            INSERT OR REPLACE INTO takeout_registry_new (
                report_id, client_id, page_url, normalized_url,
                status_takeout, alasan_spam, is_sensitive_negative, recorded_date
            )
            SELECT
                report_id, client_id, page_url, normalized_url,
                status_takeout, alasan_spam, is_sensitive_negative, recorded_date
            FROM takeout_registry;
            DROP TABLE takeout_registry;
            ALTER TABLE takeout_registry_new RENAME TO takeout_registry;
            CREATE INDEX IF NOT EXISTS idx_takeout_client_norm_url
                ON takeout_registry (client_id, normalized_url);
            """
        )
