"""Crawling noise sanitization and 0-token regex spam/ad pre-filtering (SAD.md Section 3A2)."""

from __future__ import annotations

import re

import pandas as pd

DEFAULT_NOISE_PATTERNS: list[str] = [
    r"(?i)baca juga\s*:.*",
    r"(?i)cek berita lainnya.*",
    r"(?i)simak juga\s*:.*",
]


def _make_smart_snippet(text: str, max_chars: int = 750) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rsplit(" ", 1)[0].strip() + "..."


def sanitize_content_noise(
    news_df: pd.DataFrame,
    noise_patterns: list[str] | None = None,
    snippet_max_chars: int = 750,
) -> pd.DataFrame:
    """Strip crawling boilerplate (`Baca Juga:`, etc.) from `Content` into `Content_Clean` & `Content_Snippet`."""
    df = news_df.copy()
    patterns = noise_patterns if noise_patterns else DEFAULT_NOISE_PATTERNS
    compiled = [re.compile(p) for p in patterns if p]

    clean_contents: list[str] = []
    snippets: list[str] = []

    for raw in df["Content"].fillna("").astype(str):
        lines = raw.splitlines()
        kept_lines: list[str] = []
        for line in lines:
            updated = line
            for rx in compiled:
                updated = rx.sub("", updated)
            updated = updated.strip()
            if updated:
                kept_lines.append(updated)
        cleaned = "\n".join(kept_lines)
        clean_contents.append(cleaned)
        snippets.append(_make_smart_snippet(cleaned, max_chars=snippet_max_chars))

    df["Content_Clean"] = clean_contents
    df["Content_Snippet"] = snippets
    return df


def apply_regex_spam_filter(
    news_df: pd.DataFrame,
    spam_patterns: list[str] | None = None,
) -> pd.DataFrame:
    """Mark obvious mechanical spam/ads (e.g., `Iklan - ...`, SEO KUR tables) as `Takeout` with 0 AI tokens."""
    df = news_df.copy()
    if not spam_patterns:
        return df

    compiled = [(p, re.compile(p, re.IGNORECASE)) for p in spam_patterns if p]
    if not compiled:
        return df

    statuses = df["Status_Takeout"].tolist()
    reasons = df["Alasan_Spam"].tolist()
    titles = df["Title"].fillna("").astype(str).tolist()
    contents = (
        df["Content_Clean"].fillna("").astype(str).tolist()
        if "Content_Clean" in df.columns
        else df["Content"].fillna("").astype(str).tolist()
    )

    for idx in range(len(df)):
        if statuses[idx] != "Keep":
            continue
        title = titles[idx]
        content_head = contents[idx][:500]
        for raw_pattern, rx in compiled:
            if rx.search(title) or rx.search(content_head):
                statuses[idx] = "Takeout"
                if "iklan" in raw_pattern.lower():
                    reasons[idx] = "Pre-Filter - Iklan/Advertorial (Regex)"
                else:
                    reasons[idx] = "Pre-Filter - Spam/Artikel SEO (Regex)"
                break

    df["Status_Takeout"] = statuses
    df["Alasan_Spam"] = reasons
    return df
