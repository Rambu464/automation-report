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


@dataclass
class ProjectRecord:
    project_id: str
    name: str
    client_id: str
    report_type: str = "daily"
    cutoff_datetime: str = ""
    latest_job_id: str = ""
    status: str = "draft"  # draft | running | completed | failed
    total_raw: int = 0
    total_clean: int = 0
    total_takeout: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ProjectRepo:
    """Manages persistent case-level Projects (1 Kasus = 1 Project)."""

    def __init__(self, db: StateDatabase) -> None:
        self.db = db

    def create(self, record: ProjectRecord) -> ProjectRecord:
        sql = """
        INSERT INTO projects (
            project_id, name, client_id, report_type, cutoff_datetime,
            latest_job_id, status, total_raw, total_clean, total_takeout,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.db.connect() as conn:
            conn.execute(
                sql,
                (
                    record.project_id,
                    record.name,
                    record.client_id,
                    record.report_type,
                    record.cutoff_datetime,
                    record.latest_job_id,
                    record.status,
                    record.total_raw,
                    record.total_clean,
                    record.total_takeout,
                    record.created_at,
                    record.updated_at,
                ),
            )
        return record

    def _row_to_record(self, row: Any) -> ProjectRecord:
        return ProjectRecord(
            project_id=row["project_id"],
            name=row["name"],
            client_id=row["client_id"],
            report_type=row["report_type"],
            cutoff_datetime=row["cutoff_datetime"],
            latest_job_id=row["latest_job_id"],
            status=row["status"],
            total_raw=int(row["total_raw"]),
            total_clean=int(row["total_clean"]),
            total_takeout=int(row["total_takeout"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_all(self) -> list[ProjectRecord]:
        sql = "SELECT * FROM projects ORDER BY updated_at DESC"
        with self.db.connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get(self, project_id: str) -> ProjectRecord | None:
        sql = "SELECT * FROM projects WHERE project_id = ?"
        with self.db.connect() as conn:
            row = conn.execute(sql, (project_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def update_status(
        self,
        project_id: str,
        *,
        latest_job_id: str | None = None,
        status: str | None = None,
        cutoff_datetime: str | None = None,
        total_raw: int | None = None,
        total_clean: int | None = None,
        total_takeout: int | None = None,
    ) -> ProjectRecord | None:
        existing = self.get(project_id)
        if existing is None:
            return None
        now_iso = datetime.now(timezone.utc).isoformat()
        updated = ProjectRecord(
            project_id=existing.project_id,
            name=existing.name,
            client_id=existing.client_id,
            report_type=existing.report_type,
            cutoff_datetime=cutoff_datetime if cutoff_datetime is not None else existing.cutoff_datetime,
            latest_job_id=latest_job_id if latest_job_id is not None else existing.latest_job_id,
            status=status if status is not None else existing.status,
            total_raw=total_raw if total_raw is not None else existing.total_raw,
            total_clean=total_clean if total_clean is not None else existing.total_clean,
            total_takeout=total_takeout if total_takeout is not None else existing.total_takeout,
            created_at=existing.created_at,
            updated_at=now_iso,
        )
        sql = """
        UPDATE projects SET
            cutoff_datetime = ?,
            latest_job_id = ?,
            status = ?,
            total_raw = ?,
            total_clean = ?,
            total_takeout = ?,
            updated_at = ?
        WHERE project_id = ?
        """
        with self.db.connect() as conn:
            conn.execute(
                sql,
                (
                    updated.cutoff_datetime,
                    updated.latest_job_id,
                    updated.status,
                    updated.total_raw,
                    updated.total_clean,
                    updated.total_takeout,
                    updated.updated_at,
                    updated.project_id,
                ),
            )
        return updated

    def delete(self, project_id: str) -> bool:
        with self.db.connect() as conn:
            cur = conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        return cur.rowcount > 0

