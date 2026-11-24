"""Repository classes for CRUD/upsert operations on the 4 SQLite state tables."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from src.db.database import StateDatabase


@dataclass
class TakeoutRecord:
    report_id: str
    client_id: str
    page_url: str = ""
    normalized_url: str = ""
    status_takeout: str = "Takeout"
    alasan_spam: str = ""
    is_sensitive_negative: bool = False
    recorded_date: str = field(default_factory=lambda: date.today().isoformat())


@dataclass
class NegativeIssueRecord:
    issue_hash: str
    client_id: str
    nama_isu: str
    canonical_newstrend: str
    locked_sentiment: str = "negative"
    last_seen: str = field(default_factory=lambda: date.today().isoformat())


@dataclass
class MediaMasterRecord:
    domain: str
    media_name: str = ""
    tier_bino: str = ""
    client_custom_tiers: dict[str, str] = field(default_factory=dict)
    media_type_detail: str = "Organik"
    hypestat_daily_visitor: int = 0
    media_value: int = 0


class TakeoutRegistryRepo:
    """Manages persistent Daily -> Monthly takeout records."""

    def __init__(self, db: StateDatabase) -> None:
        self.db = db

    def upsert_many(self, records: list[TakeoutRecord]) -> int:
        if not records:
            return 0
        sql = """
        INSERT INTO takeout_registry (
            report_id, client_id, page_url, normalized_url,
            status_takeout, alasan_spam, is_sensitive_negative, recorded_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(report_id) DO UPDATE SET
            page_url = excluded.page_url,
            normalized_url = excluded.normalized_url,
            status_takeout = excluded.status_takeout,
            alasan_spam = excluded.alasan_spam,
            is_sensitive_negative = excluded.is_sensitive_negative,
            recorded_date = excluded.recorded_date
        """
        rows = [
            (
                r.report_id,
                r.client_id,
                r.page_url,
                r.normalized_url,
                r.status_takeout,
                r.alasan_spam,
                1 if r.is_sensitive_negative else 0,
                r.recorded_date,
            )
            for r in records
        ]
        with self.db.connect() as conn:
            conn.executemany(sql, rows)
        return len(rows)

    def get_by_client(self, client_id: str) -> tuple[dict[str, TakeoutRecord], dict[str, TakeoutRecord]]:
        """Return two fast lookup dicts for a client: (by_report_id, by_normalized_url)."""
        sql = "SELECT * FROM takeout_registry WHERE client_id = ?"
        by_id: dict[str, TakeoutRecord] = {}
        by_url: dict[str, TakeoutRecord] = {}
        with self.db.connect() as conn:
            for row in conn.execute(sql, (client_id,)).fetchall():
                rec = TakeoutRecord(
                    report_id=row["report_id"],
                    client_id=row["client_id"],
                    page_url=row["page_url"],
                    normalized_url=row["normalized_url"],
                    status_takeout=row["status_takeout"],
                    alasan_spam=row["alasan_spam"],
                    is_sensitive_negative=bool(row["is_sensitive_negative"]),
                    recorded_date=row["recorded_date"],
                )
                by_id[rec.report_id] = rec
                if rec.normalized_url:
                    by_url[rec.normalized_url] = rec
        return by_id, by_url

    def delete_by_report_id(self, report_id: str) -> None:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM takeout_registry WHERE report_id = ?", (report_id,))


class NegativeIssueMemoryRepo:
    """Manages persistent negative issue memory for cross-day sentiment consistency."""

    def __init__(self, db: StateDatabase) -> None:
        self.db = db

    def upsert_many(self, records: list[NegativeIssueRecord]) -> int:
        if not records:
            return 0
        sql = """
        INSERT INTO negative_issue_memory (
            issue_hash, client_id, nama_isu, canonical_newstrend, locked_sentiment, last_seen
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(issue_hash) DO UPDATE SET
            nama_isu = excluded.nama_isu,
            canonical_newstrend = excluded.canonical_newstrend,
            locked_sentiment = excluded.locked_sentiment,
            last_seen = excluded.last_seen
        """
        rows = [
            (
                r.issue_hash,
                r.client_id,
                r.nama_isu,
                r.canonical_newstrend,
                r.locked_sentiment,
                r.last_seen,
            )
            for r in records
        ]
        with self.db.connect() as conn:
            conn.executemany(sql, rows)
        return len(rows)

    def list_by_client(self, client_id: str) -> list[NegativeIssueRecord]:
        sql = "SELECT * FROM negative_issue_memory WHERE client_id = ? ORDER BY last_seen DESC"
        with self.db.connect() as conn:
            rows = conn.execute(sql, (client_id,)).fetchall()
        return [
            NegativeIssueRecord(
                issue_hash=row["issue_hash"],
                client_id=row["client_id"],
                nama_isu=row["nama_isu"],
                canonical_newstrend=row["canonical_newstrend"],
                locked_sentiment=row["locked_sentiment"],
                last_seen=row["last_seen"],
            )
            for row in rows
        ]


class MediaMasterRepo:
    """Manages master media lookup (tier_bino, client custom tiers, Hypestat, Newswire/Media Bazar)."""

    def __init__(self, db: StateDatabase) -> None:
        self.db = db

    def upsert_many(self, records: list[MediaMasterRecord], merge_custom_tiers: bool = True) -> int:
        if not records:
            return 0

        existing_map: dict[str, dict[str, str]] = {}
        if merge_custom_tiers:
            domains = [r.domain for r in records]
            with self.db.connect() as conn:
                for i in range(0, len(domains), 500):
                    chunk = domains[i : i + 500]
                    placeholders = ",".join("?" for _ in chunk)
                    rows = conn.execute(
                        f"SELECT domain, client_custom_tier_json FROM media_master_hypestat WHERE domain IN ({placeholders})",
                        chunk,
                    ).fetchall()
                    for row in rows:
                        try:
                            existing_map[row["domain"]] = json.loads(
                                row["client_custom_tier_json"] or "{}"
                            )
                        except json.JSONDecodeError:
                            existing_map[row["domain"]] = {}

        sql = """
        INSERT INTO media_master_hypestat (
            domain, media_name, tier_bino, client_custom_tier_json,
            media_type_detail, hypestat_daily_visitor, media_value
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(domain) DO UPDATE SET
            media_name = CASE WHEN excluded.media_name != '' THEN excluded.media_name ELSE media_master_hypestat.media_name END,
            tier_bino = CASE WHEN excluded.tier_bino != '' THEN excluded.tier_bino ELSE media_master_hypestat.tier_bino END,
            client_custom_tier_json = excluded.client_custom_tier_json,
            media_type_detail = CASE WHEN excluded.media_type_detail != '' THEN excluded.media_type_detail ELSE media_master_hypestat.media_type_detail END,
            hypestat_daily_visitor = CASE WHEN excluded.hypestat_daily_visitor > 0 THEN excluded.hypestat_daily_visitor ELSE media_master_hypestat.hypestat_daily_visitor END,
            media_value = CASE WHEN excluded.media_value > 0 THEN excluded.media_value ELSE media_master_hypestat.media_value END
        """
        payload_rows = []
        for r in records:
            merged_tiers = dict(existing_map.get(r.domain, {}))
            merged_tiers.update(r.client_custom_tiers)
            payload_rows.append(
                (
                    r.domain,
                    r.media_name,
                    r.tier_bino,
                    json.dumps(merged_tiers, ensure_ascii=False),
                    r.media_type_detail,
                    int(r.hypestat_daily_visitor or 0),
                    int(r.media_value or 0),
                )
            )
        with self.db.connect() as conn:
            conn.executemany(sql, payload_rows)
        return len(payload_rows)

    def get_all_map(self) -> dict[str, MediaMasterRecord]:
        """Load all media master rows into an in-memory dict keyed by normalized domain (< 50ms lookup)."""
        sql = "SELECT * FROM media_master_hypestat"
        result: dict[str, MediaMasterRecord] = {}
        with self.db.connect() as conn:
            for row in conn.execute(sql).fetchall():
                try:
                    custom_tiers = json.loads(row["client_custom_tier_json"] or "{}")
                except json.JSONDecodeError:
                    custom_tiers = {}
                result[row["domain"]] = MediaMasterRecord(
                    domain=row["domain"],
                    media_name=row["media_name"],
                    tier_bino=row["tier_bino"],
                    client_custom_tiers=custom_tiers,
                    media_type_detail=row["media_type_detail"],
                    hypestat_daily_visitor=row["hypestat_daily_visitor"],
                    media_value=row["media_value"],
                )
        return result


class AIBatchCacheRepo:
    """Manages local per-row AI classification cache."""

    def __init__(self, db: StateDatabase) -> None:
        self.db = db

    def get_many(self, cache_keys: list[str]) -> dict[str, dict[str, Any]]:
        if not cache_keys:
            return {}
        result: dict[str, dict[str, Any]] = {}
        # SQLite parameter limit safety: chunk by 500
        with self.db.connect() as conn:
            for i in range(0, len(cache_keys), 500):
                chunk = cache_keys[i : i + 500]
                placeholders = ",".join("?" for _ in chunk)
                rows = conn.execute(
                    f"SELECT cache_key, json_result FROM ai_batch_cache WHERE cache_key IN ({placeholders})",
                    chunk,
                ).fetchall()
                for row in rows:
                    try:
                        result[row["cache_key"]] = json.loads(row["json_result"])
                    except json.JSONDecodeError:
                        continue
        return result

    def set_many(self, items: dict[str, dict[str, Any]]) -> int:
        if not items:
            return 0
        now_iso = datetime.now(timezone.utc).isoformat()
        sql = """
        INSERT INTO ai_batch_cache (cache_key, json_result, created_at)
        VALUES (?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
            json_result = excluded.json_result,
            created_at = excluded.created_at
        """
        rows = [
            (k, json.dumps(v, ensure_ascii=False), now_iso)
            for k, v in items.items()
        ]
        with self.db.connect() as conn:
            conn.executemany(sql, rows)
        return len(rows)
