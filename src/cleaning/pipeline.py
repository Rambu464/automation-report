"""End-to-end deterministic Pre-Cleaning Pipeline orchestrator (Sprint 1 — 0 AI tokens)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.cleaning.cutoff import FLAG_CUTOFF_00_VALUE, apply_date_time_and_cutoff
from src.cleaning.deduplicator import FLAG_NEAR_DUP_VALUE, apply_three_layer_deduplication
from src.cleaning.ingestion import attach_tier1_spokesperson, ingest_excel_files
from src.cleaning.media_lookup import enrich_media_attributes
from src.cleaning.sanitizer import apply_regex_spam_filter, sanitize_content_noise
from src.cleaning.url_matcher import UrlMatchSummary, apply_client_url_lists_and_history
from src.config_loader import ClientConfig, load_client_config
from src.db.database import StateDatabase
from src.db.repositories import MediaMasterRepo, TakeoutRegistryRepo


@dataclass
class PreCleaningStats:
    total_raw: int = 0
    total_keep: int = 0
    total_takeout: int = 0
    flagged_cutoff_00: int = 0
    flagged_near_dup: int = 0
    ai_cluster_reps: int = 0
    tier1_spokesperson_filled: int = 0


@dataclass
class PreCleaningResult:
    news_df: pd.DataFrame
    statements_df: pd.DataFrame
    source_files: list[str]
    url_match_summary: UrlMatchSummary
    stats: PreCleaningStats = field(default_factory=PreCleaningStats)


class PreCleaningPipeline:
    """Runs all deterministic Sprint 1 cleaning, enrichment, and deduplication steps."""

    def __init__(
        self,
        db: StateDatabase | None = None,
        clients_dir: Path | None = None,
    ) -> None:
        self.db = db if db is not None else StateDatabase()
        self.clients_dir = clients_dir
        self.takeout_repo = TakeoutRegistryRepo(self.db)
        self.media_repo = MediaMasterRepo(self.db)

    def run(
        self,
        excel_paths: Path | str | Iterable[Path | str],
        client_id: str,
        cutoff_datetime: datetime | str | None = None,
        req_upload_urls: str | Iterable[str] | None = None,
        takedown_urls: str | Iterable[str] | None = None,
        config_override: ClientConfig | None = None,
    ) -> PreCleaningResult:
        if isinstance(excel_paths, (str, Path)):
            paths: list[Path | str] = [excel_paths]
        else:
            paths = list(excel_paths)

        config = (
            config_override
            if config_override is not None
            else load_client_config(client_id, clients_dir=self.clients_dir)
        )

        # 1. Ingest .xls with Statements (python-calamine)
        ingested = ingest_excel_files(paths)
        df = ingested.news_df
        statements_df = ingested.statements_df

        # 2. Tier-1 Spokesperson lookup from Statements (0 AI tokens)
        df = attach_tier1_spokesperson(df, statements_df)

        # 3. Date/Time split, cutoff enforcement, & 00:00 flag
        df = apply_date_time_and_cutoff(df, cutoff_datetime=cutoff_datetime)

        # 4. Content crawling noise sanitization & Smart Snippet
        df = sanitize_content_noise(
            df,
            noise_patterns=config.takeout_rules.content_noise_patterns,
        )

        # 5. Historical takeout_registry sync + Client Takedown & Req Upload URL matching
        df, url_summary = apply_client_url_lists_and_history(
            df,
            client_id=config.client_id,
            takeout_repo=self.takeout_repo,
            req_upload_urls=req_upload_urls,
            takedown_urls=takedown_urls,
        )

        # 6. Media master lookup (Custom Tier, Hypestat, Newswire auto-takeout)
        df = enrich_media_attributes(df, config=config, media_repo=self.media_repo)

        # 7. Mechanical Regex Spam / Ad pre-filter (0 AI tokens)
        df = apply_regex_spam_filter(
            df,
            spam_patterns=config.takeout_rules.regex_spam_patterns,
        )

        # 8. 3-Layer Deduplication & Cross-Media Cluster_ID grouping
        df = apply_three_layer_deduplication(df)

        # 9. Sync Statements sheet to only keep statements of non-Takeout news
        keep_ids = set(df.loc[df["Status_Takeout"] == "Keep", "ID"].astype(str))
        if not statements_df.empty and "Report id" in statements_df.columns:
            filtered_statements = statements_df[
                statements_df["Report id"].astype(str).isin(keep_ids)
            ].reset_index(drop=True)
        else:
            filtered_statements = statements_df.copy()

        # 10. Compute summary statistics
        keep_mask = df["Status_Takeout"] == "Keep"
        stats = PreCleaningStats(
            total_raw=len(df),
            total_keep=int(keep_mask.sum()),
            total_takeout=int((~keep_mask).sum()),
            flagged_cutoff_00=int((df["Flag_Cutoff_00"] == FLAG_CUTOFF_00_VALUE).sum()),
            flagged_near_dup=int((df["Flag_Near_Dup"] == FLAG_NEAR_DUP_VALUE).sum()),
            ai_cluster_reps=int((keep_mask & df["Is_Cluster_Rep"]).sum()),
            tier1_spokesperson_filled=int((keep_mask & df["Has_Statement"]).sum()),
        )

        return PreCleaningResult(
            news_df=df,
            statements_df=filtered_statements,
            source_files=ingested.source_files,
            url_match_summary=url_summary,
            stats=stats,
        )
