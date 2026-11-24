"""Deterministic Competitor Highlight Curation (FR-04.2, NFR-03 Anti-Mismatch)."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from src.config_loader import ClientConfig


def _tier_rank(tier_value: str, priority_order: list[str]) -> int:
    norm = (tier_value or "").strip().lower()
    for idx, label in enumerate(priority_order):
        if norm == label.strip().lower():
            return idx
    return len(priority_order) + 1


def curate_competitor_highlights(
    news_df: pd.DataFrame,
    config: ClientConfig,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Select top 2-3 positive and negative articles per competitor prioritized by Media Tier & Hypestat.

    All `id`, `title`, `media_name`, `tier`, and `url` fields are extracted directly from the
    original DataFrame to guarantee 0% Media-URL mismatch (NFR-03).
    """
    comp_cfg = config.competitors
    if not comp_cfg.enabled or not comp_cfg.entities:
        return {}

    keep_df = news_df[news_df["Status_Takeout"] == "Keep"].copy()
    if keep_df.empty:
        return {entity: {"positive": [], "negative": []} for entity in comp_cfg.entities}

    custom_tier_col = config.media_and_spokesperson.custom_tier.excel_column_name
    tier_col = (
        custom_tier_col
        if config.media_and_spokesperson.custom_tier.enabled and custom_tier_col in keep_df.columns
        else "Media Tier"
    )
    priority = comp_cfg.prioritize_by_media_tier or ["Tier 1", "Tier 2", "Tier 3"]
    limit = comp_cfg.daily_highlight_count_per_sentiment

    # Build searchable text column once
    search_text = (
        keep_df["Title"].fillna("").astype(str)
        + " "
        + keep_df.get("Nama_Isu", pd.Series([""] * len(keep_df))).fillna("").astype(str)
        + " "
        + keep_df.get("Newstrends", pd.Series([""] * len(keep_df))).fillna("").astype(str)
    )
    keep_df["_search"] = search_text
    keep_df["_sent"] = keep_df["Sentiment"].fillna("").astype(str).str.strip().str.lower()
    keep_df["_tier_val"] = (
        keep_df[tier_col].fillna("").astype(str).str.strip()
        if tier_col in keep_df.columns
        else ""
    )
    keep_df["_tier_rank"] = keep_df["_tier_val"].map(lambda v: _tier_rank(v, priority))
    keep_df["_visitor"] = pd.to_numeric(
        keep_df.get("Oplah/Daily Visitor", 0), errors="coerce"
    ).fillna(0)

    highlights: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for entity in comp_cfg.entities:
        pattern = re.compile(rf"\b{re.escape(entity)}\b", re.IGNORECASE)
        matched = keep_df[keep_df["_search"].str.contains(pattern, na=False)]

        entity_buckets: dict[str, list[dict[str, Any]]] = {"positive": [], "negative": []}
        for sentiment in ("positive", "negative"):
            subset = matched[matched["_sent"] == sentiment].sort_values(
                by=["_tier_rank", "_visitor", "Date"],
                ascending=[True, False, False],
            )
            for _, row in subset.head(limit).iterrows():
                entity_buckets[sentiment].append(
                    {
                        "id": str(row["ID"]),
                        "title": str(row["Title"]),
                        "media_name": str(row["Media Name"]),
                        "tier": str(row["_tier_val"] or row.get("Media Tier", "")),
                        "url": str(row["Page/URL"]),
                        "newstrend": str(row.get("Newstrends", "")),
                        "date": str(row.get("Date", "")),
                    }
                )
        highlights[entity] = entity_buckets

    return highlights
