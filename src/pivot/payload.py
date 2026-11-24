"""Single Source of Truth `report_payload.json` builder (SAD.md Section 6A)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.config_loader import ClientConfig
from src.pivot.competitor import curate_competitor_highlights
from src.pivot.engine import compute_pivots


def build_report_payload(
    news_df: pd.DataFrame,
    config: ClientConfig,
    period_label: str = "",
    cutoff_wib: str = "",
    req_upload_matched: int = 0,
    social_media_optional: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble verified `report_payload.json` consumed by Excel Pivot, PPTX/PDF, and Wording."""
    total_raw = int(len(news_df))
    keep_mask = news_df["Status_Takeout"] == "Keep"
    total_clean = int(keep_mask.sum())
    total_takeout = total_raw - total_clean

    if not period_label and not news_df.empty and "Date" in news_df.columns:
        valid_dates = sorted(
            d for d in news_df.loc[keep_mask, "Date"].fillna("").astype(str).unique() if d
        )
        if len(valid_dates) == 1:
            period_label = valid_dates[0]
        elif len(valid_dates) > 1:
            period_label = f"{valid_dates[0]} s.d. {valid_dates[-1]}"

    pivot_data = compute_pivots(news_df, config)
    competitor_highlights = curate_competitor_highlights(news_df, config)

    return {
        "meta": {
            "client_id": config.client_id,
            "client_name": config.client_name,
            "period_label": period_label,
            "cutoff_wib": cutoff_wib,
            "total_raw": total_raw,
            "total_clean": total_clean,
            "total_takeout": total_takeout,
            "req_upload_matched": int(req_upload_matched),
        },
        "sentiment_summary": pivot_data["sentiment_summary"],
        "tier1_sentiment_summary": pivot_data["tier1_sentiment_summary"],
        "media_breakdown": pivot_data["media_breakdown"],
        "pivots": pivot_data["pivots"],
        "adhoc_breakdowns": pivot_data["adhoc_breakdowns"],
        "competitor_highlights": competitor_highlights,
        "social_media_optional": social_media_optional,
    }


def save_report_payload(payload: dict[str, Any], output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path
