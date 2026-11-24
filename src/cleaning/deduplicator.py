"""3-Layer Deterministic Deduplication & Token-Saving Clustering Engine (SAD.md Section 3A3).

Layer 1: Exact Normalized URL (and multi-file ID) duplicates -> Takeout ('Duplikat URL Persis')
Layer 2: Same-Media Near-Duplicate (Title >= 90% AND Content >= 90%) -> Takeout ('Duplikat Media Sama')
         If Title >= 90% BUT Content < 90% -> KEEP + Flag_Near_Dup = 'CEK_MIRIP_JUDUL'
Layer 3: Cross-Media Syndication (Content >= 90% on different media) -> KEEP ALL rows,
         assign shared `Cluster_ID` and mark `Is_Cluster_Rep = True` only on representative.
"""

from __future__ import annotations

import re

import pandas as pd
from rapidfuzz import fuzz

from src.cleaning.url_utils import normalize_url

FLAG_NEAR_DUP_VALUE = "CEK_MIRIP_JUDUL"


def _norm_text(text: str, max_chars: int = 800) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()[:max_chars]


def apply_three_layer_deduplication(
    news_df: pd.DataFrame,
    title_threshold: float = 90.0,
    content_threshold: float = 90.0,
    min_cluster_content_chars: int = 80,
) -> pd.DataFrame:
    """Execute the 3-layer deduplication & cross-media clustering pipeline (0 AI tokens)."""
    df = news_df.copy()

    # Ensure Normalized_URL exists
    df["Normalized_URL"] = [normalize_url(u) for u in df["Page/URL"].fillna("").astype(str)]

    statuses = df["Status_Takeout"].tolist()
    reasons = df["Alasan_Spam"].tolist()
    near_dup_flags = df["Flag_Near_Dup"].tolist()
    ids = df["ID"].astype(str).tolist()
    norm_urls = df["Normalized_URL"].tolist()
    media_names = [str(m).strip().lower() for m in df["Media Name"].fillna("").astype(str)]
    titles = [_norm_text(t, max_chars=300) for t in df["Title"].fillna("").astype(str)]
    content_col = "Content_Clean" if "Content_Clean" in df.columns else "Content"
    contents = [_norm_text(c, max_chars=800) for c in df[content_col].fillna("").astype(str)]

    # --- Layer 1: Exact ID (multi-file safety) & Normalized URL Duplicate ---
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()

    for idx in range(len(df)):
        if statuses[idx] != "Keep":
            continue
        rid = ids[idx]
        nurl = norm_urls[idx]

        if rid and rid in seen_ids:
            statuses[idx] = "Takeout"
            reasons[idx] = "Duplikat ID Multi-File"
            continue
        if nurl and nurl in seen_urls:
            statuses[idx] = "Takeout"
            reasons[idx] = "Duplikat URL Persis"
            continue

        if rid:
            seen_ids.add(rid)
        if nurl:
            seen_urls.add(nurl)

    # --- Layer 2: Same-Media Near-Duplicate (Dual AND: Title >= 90% AND Content >= 90%) ---
    kept_by_media: dict[str, list[int]] = {}
    for idx in range(len(df)):
        if statuses[idx] != "Keep":
            continue
        media = media_names[idx]
        if not media:
            continue

        prior_indices = kept_by_media.setdefault(media, [])
        is_dup = False
        is_near_title = False

        for prev_idx in prior_indices:
            if not titles[idx] or not titles[prev_idx]:
                continue
            title_sim = fuzz.ratio(titles[idx], titles[prev_idx])
            if title_sim >= title_threshold:
                if contents[idx] and contents[prev_idx]:
                    content_sim = fuzz.ratio(contents[idx], contents[prev_idx])
                else:
                    content_sim = 0.0

                if content_sim >= content_threshold:
                    is_dup = True
                    break
                else:
                    is_near_title = True

        if is_dup:
            statuses[idx] = "Takeout"
            reasons[idx] = "Duplikat Media Sama"
        else:
            if is_near_title:
                near_dup_flags[idx] = FLAG_NEAR_DUP_VALUE
            prior_indices.append(idx)

    # --- Layer 3: Cross-Media Token-Saving Grouping (KEEP ALL, assign Cluster_ID) ---
    cluster_ids = [""] * len(df)
    is_cluster_rep = [True] * len(df)
    cluster_reps: list[tuple[str, int, str]] = []  # (cluster_id, rep_idx, rep_content)
    next_cluster_num = 1

    for idx in range(len(df)):
        if statuses[idx] != "Keep":
            is_cluster_rep[idx] = False
            continue
        content = contents[idx]
        if len(content) < min_cluster_content_chars:
            continue

        matched_cluster: str | None = None
        for cid, rep_idx, rep_content in cluster_reps:
            if media_names[idx] == media_names[rep_idx]:
                continue
            if fuzz.ratio(content, rep_content) >= content_threshold:
                matched_cluster = cid
                break

        if matched_cluster is not None:
            cluster_ids[idx] = matched_cluster
            is_cluster_rep[idx] = False
        else:
            cid = f"CL-{next_cluster_num:04d}"
            next_cluster_num += 1
            cluster_ids[idx] = cid
            is_cluster_rep[idx] = True
            cluster_reps.append((cid, idx, content))

    df["Status_Takeout"] = statuses
    df["Alasan_Spam"] = reasons
    df["Flag_Near_Dup"] = near_dup_flags
    df["Cluster_ID"] = cluster_ids
    df["Is_Cluster_Rep"] = is_cluster_rep
    return df
