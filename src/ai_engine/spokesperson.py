"""3-Tier Spokesperson & Jabatan Resolver (FR-03.3, SAD.md Section 3B).

Tier 1: Sheet `Statements` (already attached during Sprint 1 ingestion; never overwritten)
Tier 2: LLM extraction from `Content` (populated by Pass 1 when `Has_Statement == False`)
Tier 3: Mandatory default `"0"` (never blank/null) when neither Tier 1 nor Tier 2 has a speaker.
"""

from __future__ import annotations

import pandas as pd

EMPTY_SPEAKER_MARKERS = frozenset(
    {"", "-", "--", "none", "null", "n/a", "na", "tidak ada", "tidak ditemukan", "kosong"}
)


def _clean_speaker_value(val: object) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    text = str(val).strip()
    if text.lower() in EMPTY_SPEAKER_MARKERS:
        return ""
    return text


def apply_three_tier_spokesperson_fallback(
    news_df: pd.DataFrame,
    missing_value: str = "0",
) -> pd.DataFrame:
    """Guarantee 0 blank cells for `Spokesperson` and `Jabatan` across all kept rows."""
    df = news_df.copy()

    if "Spokesperson" not in df.columns:
        df["Spokesperson"] = ""
    if "Jabatan" not in df.columns:
        df["Jabatan"] = ""
    if "Has_Statement" not in df.columns:
        df["Has_Statement"] = False

    spokespersons = df["Spokesperson"].tolist()
    jabatans = df["Jabatan"].tolist()
    ai_spokespersons = (
        df["AI_Spokesperson"].tolist() if "AI_Spokesperson" in df.columns else [""] * len(df)
    )
    ai_jabatans = (
        df["AI_Jabatan"].tolist() if "AI_Jabatan" in df.columns else [""] * len(df)
    )
    has_stmt_list = df["Has_Statement"].tolist()
    statuses = df["Status_Takeout"].tolist()

    final_spokespersons: list[str] = []
    final_jabatans: list[str] = []

    for idx in range(len(df)):
        t1_name = _clean_speaker_value(spokespersons[idx])
        t1_pos = _clean_speaker_value(jabatans[idx])

        # Tier 1: Statements (authoritative, 0 AI tokens)
        if bool(has_stmt_list[idx]) and t1_name:
            final_spokespersons.append(t1_name)
            final_jabatans.append(t1_pos if t1_pos else missing_value)
            continue

        # Tier 2: AI extraction from Content
        t2_name = _clean_speaker_value(ai_spokespersons[idx]) or t1_name
        t2_pos = _clean_speaker_value(ai_jabatans[idx]) or t1_pos

        if t2_name:
            final_spokespersons.append(t2_name)
            final_jabatans.append(t2_pos if t2_pos else missing_value)
        elif statuses[idx] == "Keep":
            # Tier 3: Mandatory default "0" for Keep rows
            final_spokespersons.append(missing_value)
            final_jabatans.append(missing_value)
        else:
            final_spokespersons.append(missing_value)
            final_jabatans.append(missing_value)

    df["Spokesperson"] = final_spokespersons
    df["Jabatan"] = final_jabatans
    return df
