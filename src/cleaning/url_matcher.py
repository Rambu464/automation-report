"""Client URL list matching (`Req Upload` & `Takedown`) and SQLite `takeout_registry` sync (SAD.md Section 3A4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

import pandas as pd

from src.cleaning.url_utils import normalize_url
from src.db.repositories import TakeoutRecord, TakeoutRegistryRepo

TAKEDOWN_REASON = "Takeout - Daftar Takedown Klien"
REQ_UPLOAD_MATCHED_LABEL = "Matched (Req Upload)"


@dataclass
class UrlMatchSummary:
    req_upload_total: int = 0
    req_upload_matched: int = 0
    req_upload_unmatched_urls: list[str] = field(default_factory=list)
    takedown_matched: int = 0
    historical_takeout_matched: int = 0


def parse_url_list(raw_input: str | Iterable[str] | None) -> list[str]:
    """Parse raw newline/comma-separated URLs or an iterable into unique non-empty URLs."""
    if raw_input is None:
        return []
    if isinstance(raw_input, str):
        items = [line.strip() for chunk in raw_input.splitlines() for line in chunk.split(",")]
    else:
        items = [str(u).strip() for u in raw_input]
    return [u for u in dict.fromkeys(items) if u]


def apply_client_url_lists_and_history(
    news_df: pd.DataFrame,
    client_id: str,
    takeout_repo: TakeoutRegistryRepo,
    req_upload_urls: str | Iterable[str] | None = None,
    takedown_urls: str | Iterable[str] | None = None,
    recorded_date: str | None = None,
) -> tuple[pd.DataFrame, UrlMatchSummary]:
    """Cross-check `News` against historical `takeout_registry`, client `Takedown`, and `Req Upload` URLs."""
    df = news_df.copy()
    if "Normalized_URL" not in df.columns:
        df["Normalized_URL"] = [normalize_url(u) for u in df["Page/URL"].fillna("").astype(str)]

    today_str = recorded_date or date.today().isoformat()
    summary = UrlMatchSummary()

    # 1. Historical takeout_registry lookup (Daily -> Monthly sync)
    hist_by_id, hist_by_url = takeout_repo.get_by_client(client_id)

    # 2. Parse client Takedown & Req Upload lists
    takedown_raw = parse_url_list(takedown_urls)
    takedown_norm_set = {normalize_url(u) for u in takedown_raw if normalize_url(u)}

    req_upload_raw = parse_url_list(req_upload_urls)
    req_upload_norm_map = {
        normalize_url(u): u for u in req_upload_raw if normalize_url(u)
    }
    summary.req_upload_total = len(req_upload_norm_map)
    matched_req_norms: set[str] = set()

    statuses = df["Status_Takeout"].tolist()
    reasons = df["Alasan_Spam"].tolist()
    req_upload_col = df["Status_Req_Upload"].tolist()
    ids = df["ID"].astype(str).tolist()
    raw_urls = df["Page/URL"].fillna("").astype(str).tolist()
    norm_urls = df["Normalized_URL"].tolist()

    new_takedown_records: list[TakeoutRecord] = []

    for idx in range(len(df)):
        rid = ids[idx]
        nurl = norm_urls[idx]

        # Match Req Upload (informational status)
        if nurl and nurl in req_upload_norm_map:
            req_upload_col[idx] = REQ_UPLOAD_MATCHED_LABEL
            matched_req_norms.add(nurl)

        # Match Client Takedown (highest priority, immediately persisted to takeout_registry)
        if nurl and nurl in takedown_norm_set:
            statuses[idx] = "Takeout"
            reasons[idx] = TAKEDOWN_REASON
            summary.takedown_matched += 1
            new_takedown_records.append(
                TakeoutRecord(
                    report_id=rid,
                    client_id=client_id,
                    page_url=raw_urls[idx],
                    normalized_url=nurl,
                    status_takeout="Takeout",
                    alasan_spam=TAKEDOWN_REASON,
                    is_sensitive_negative=True,
                    recorded_date=today_str,
                )
            )
            continue

        # Match Historical takeout_registry (Daily -> Monthly sync)
        hist_rec = hist_by_id.get(rid) or (hist_by_url.get(nurl) if nurl else None)
        if hist_rec is not None and statuses[idx] == "Keep":
            statuses[idx] = "Takeout"
            reasons[idx] = hist_rec.alasan_spam or "Takeout - Sinkronisasi Historis"
            summary.historical_takeout_matched += 1

    if new_takedown_records:
        takeout_repo.upsert_many(new_takedown_records)

    summary.req_upload_matched = len(matched_req_norms)
    summary.req_upload_unmatched_urls = [
        orig_url for norm_u, orig_url in req_upload_norm_map.items() if norm_u not in matched_req_norms
    ]

    df["Status_Takeout"] = statuses
    df["Alasan_Spam"] = reasons
    df["Status_Req_Upload"] = req_upload_col
    return df, summary
