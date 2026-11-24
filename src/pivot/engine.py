"""Deterministic Auto-Pivot Engine (FR-04.1, SAD.md Section 6A — 0 AI tokens)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.cleaning.media_lookup import normalize_tier_label
from src.config_loader import ClientConfig


def _norm_sentiment(val: object) -> str:
    s = str(val or "").strip().lower()
    if s in {"positive", "positif", "pos"}:
        return "positive"
    if s in {"negative", "negatif", "neg"}:
        return "negative"
    return "neutral"


def compute_pivots(news_df: pd.DataFrame, config: ClientConfig) -> dict[str, Any]:
    """Compute all deterministic pivots strictly from `Status_Takeout == 'Keep'` rows."""
    keep_df = news_df[news_df["Status_Takeout"] == "Keep"].copy()

    if keep_df.empty:
        return {
            "sentiment_summary": {"positive": 0, "neutral": 0, "negative": 0},
            "tier1_sentiment_summary": {"positive": 0, "neutral": 0, "negative": 0},
            "media_breakdown": {"by_type": {}, "by_custom_tier": {}, "by_detail": {}},
            "pivots": {
                "top_newstrends": [],
                "spokesperson_rilis": [],
                "timeline_daily": [],
                "top_media": [],
            },
            "adhoc_breakdowns": {},
        }

    keep_df["_sent"] = keep_df["Sentiment"].map(_norm_sentiment)

    # 1. Sentiment summary
    sent_counts = keep_df["_sent"].value_counts().to_dict()
    sentiment_summary = {
        "positive": int(sent_counts.get("positive", 0)),
        "neutral": int(sent_counts.get("neutral", 0)),
        "negative": int(sent_counts.get("negative", 0)),
    }

    # 2. Pivot 1 — Media Breakdown (Type, Custom Tier, Media Type Detail)
    media_type_series = (
        keep_df["Media Type"].fillna("").astype(str).str.strip().str.lower().replace("", "unknown")
    )
    by_type = {str(k): int(v) for k, v in media_type_series.value_counts().items()}

    custom_tier_col = config.media_and_spokesperson.custom_tier.excel_column_name
    tier_col = (
        custom_tier_col
        if config.media_and_spokesperson.custom_tier.enabled and custom_tier_col in keep_df.columns
        else "Media Tier"
    )
    if tier_col in keep_df.columns:
        tier_series = keep_df[tier_col].map(normalize_tier_label).replace("", "Unassigned")
    else:
        tier_series = pd.Series(["Unassigned"] * len(keep_df), index=keep_df.index)
    keep_df["_tier_norm"] = tier_series
    by_custom_tier = {str(k): int(v) for k, v in tier_series.value_counts().items()}

    # Tier 1 Sentiment Summary
    t1_df = keep_df[keep_df["_tier_norm"] == "Tier 1"]
    t1_counts = t1_df["_sent"].value_counts().to_dict() if not t1_df.empty else {}
    tier1_sentiment_summary = {
        "positive": int(t1_counts.get("positive", 0)),
        "neutral": int(t1_counts.get("neutral", 0)),
        "negative": int(t1_counts.get("negative", 0)),
    }

    detail_series = (
        keep_df["Media Type Detail"].fillna("").astype(str).str.strip().replace("", "Organik")
        if "Media Type Detail" in keep_df.columns
        else pd.Series(["Organik"] * len(keep_df))
    )
    by_detail = {str(k): int(v) for k, v in detail_series.value_counts().items()}

    # 3. Pivot 2 — Newstrends & Nama_Isu vs Sentiment
    keep_df["_nt"] = keep_df.get("Newstrends", pd.Series([""] * len(keep_df))).fillna("").astype(str).str.strip()
    keep_df["_isu"] = keep_df.get("Nama_Isu", pd.Series([""] * len(keep_df))).fillna("").astype(str).str.strip()

    top_newstrends: list[dict[str, Any]] = []
    for (nt, isu), grp in keep_df.groupby(["_nt", "_isu"], dropna=False):
        if not nt and not isu:
            continue
        sc = grp["_sent"].value_counts().to_dict()
        pos = int(sc.get("positive", 0))
        neu = int(sc.get("neutral", 0))
        neg = int(sc.get("negative", 0))
        top_newstrends.append(
            {
                "newstrend": str(nt),
                "nama_isu": str(isu),
                "pos": pos,
                "neu": neu,
                "neg": neg,
                "total": pos + neu + neg,
            }
        )
    top_newstrends.sort(key=lambda x: (-x["total"], -x["neg"], x["newstrend"]))

    # 4. Pivot 3 — Spokesperson & Jabatan (ONLY Content_Type == 'Rilis', including '0')
    spokesperson_rilis: list[dict[str, Any]] = []
    if "Content_Type" in keep_df.columns:
        rilis_df = keep_df[
            keep_df["Content_Type"].fillna("").astype(str).str.strip().str.lower() == "rilis"
        ].copy()
        if not rilis_df.empty:
            missing_val = config.media_and_spokesperson.spokesperson_missing_value
            rilis_df["_spk"] = (
                rilis_df.get("Spokesperson", pd.Series([missing_val] * len(rilis_df)))
                .fillna(missing_val)
                .astype(str)
                .str.strip()
                .replace("", missing_val)
            )
            rilis_df["_jab"] = (
                rilis_df.get("Jabatan", pd.Series([missing_val] * len(rilis_df)))
                .fillna(missing_val)
                .astype(str)
                .str.strip()
                .replace("", missing_val)
            )
            for (spk, jab), grp in rilis_df.groupby(["_spk", "_jab"], dropna=False):
                spokesperson_rilis.append(
                    {
                        "spokesperson": str(spk),
                        "jabatan": str(jab),
                        "count": int(len(grp)),
                    }
                )
            spokesperson_rilis.sort(key=lambda x: (-x["count"], x["spokesperson"]))

    # 5. Timeline Daily
    timeline_daily: list[dict[str, Any]] = []
    keep_df["_date"] = keep_df["Date"].fillna("").astype(str).str.strip()
    for dt_str, grp in keep_df.groupby("_date", dropna=False):
        if not dt_str:
            continue
        sc = grp["_sent"].value_counts().to_dict()
        timeline_daily.append(
            {
                "date": str(dt_str),
                "total": int(len(grp)),
                "pos": int(sc.get("positive", 0)),
                "neu": int(sc.get("neutral", 0)),
                "neg": int(sc.get("negative", 0)),
            }
        )
    timeline_daily.sort(key=lambda x: x["date"])

    # 5b. Top Media Name Breakdown
    media_name_series = (
        keep_df["Media Name"].fillna("").astype(str).str.strip().replace("", "Unknown")
        if "Media Name" in keep_df.columns
        else pd.Series(["Unknown"] * len(keep_df))
    )
    top_media = [
        {"media_name": str(name), "count": int(cnt)}
        for name, cnt in media_name_series.value_counts().items()
    ]

    # 6. Ad-hoc column breakdowns
    adhoc_breakdowns: dict[str, dict[str, int]] = {}
    for col_cfg in config.adhoc_columns:
        if col_cfg.name in keep_df.columns:
            vc = (
                keep_df[col_cfg.name]
                .fillna("")
                .astype(str)
                .str.strip()
                .replace("", "Unassigned")
                .value_counts()
            )
            adhoc_breakdowns[col_cfg.name] = {str(k): int(v) for k, v in vc.items()}

    return {
        "sentiment_summary": sentiment_summary,
        "tier1_sentiment_summary": tier1_sentiment_summary,
        "media_breakdown": {
            "by_type": by_type,
            "by_custom_tier": by_custom_tier,
            "by_detail": by_detail,
        },
        "pivots": {
            "top_newstrends": top_newstrends,
            "spokesperson_rilis": spokesperson_rilis,
            "timeline_daily": timeline_daily,
            "top_media": top_media,
        },
        "adhoc_breakdowns": adhoc_breakdowns,
    }
