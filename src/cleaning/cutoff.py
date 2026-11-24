"""Date/Time splitting, cutoff enforcement, and `00:00` default time guard (SAD.md Section 3A)."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

FLAG_CUTOFF_00_VALUE = "CEK_CUTOFF_00:00"
CUTOFF_TAKEOUT_REASON = "Lewat Jam Cutoff"


def _parse_cutoff(cutoff_datetime: datetime | str | None) -> pd.Timestamp | None:
    if cutoff_datetime is None:
        return None
    ts = pd.to_datetime(cutoff_datetime, errors="coerce")
    if pd.isna(ts):
        raise ValueError(f"Format cutoff_datetime tidak valid: {cutoff_datetime}")
    # Normalize to timezone-naive local time (WIB) for deterministic comparison with Newstensity export
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts


def apply_date_time_and_cutoff(
    news_df: pd.DataFrame,
    cutoff_datetime: datetime | str | None = None,
) -> pd.DataFrame:
    """Split raw `Date` into `Date` (`YYYY-MM-DD`) and `Time` (`HH:MM`), flag `00:00`, and enforce cutoff."""
    df = news_df.copy()
    parsed = pd.to_datetime(df["Date"], errors="coerce")

    dates: list[str] = []
    times: list[str] = []
    flags: list[str] = []

    for raw_val, ts in zip(df["Date"], parsed):
        if pd.isna(ts):
            dates.append(str(raw_val).strip())
            times.append("")
            flags.append("")
        else:
            date_str = ts.strftime("%Y-%m-%d")
            time_str = ts.strftime("%H:%M")
            dates.append(date_str)
            times.append(time_str)
            flags.append(FLAG_CUTOFF_00_VALUE if time_str == "00:00" else "")

    df["Date"] = dates
    df["Time"] = times
    df["Flag_Cutoff_00"] = flags

    cutoff_ts = _parse_cutoff(cutoff_datetime)
    if cutoff_ts is not None:
        is_after_cutoff = parsed.notna() & (parsed > cutoff_ts)
        # Only mark rows that are currently Keep so prior more specific reasons aren't overwritten
        mask = is_after_cutoff & (df["Status_Takeout"] == "Keep")
        df.loc[mask, "Status_Takeout"] = "Takeout"
        df.loc[mask, "Alasan_Spam"] = CUTOFF_TAKEOUT_REASON

    return df
