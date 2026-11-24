"""Media master seeding & fast in-memory lookup (Custom Tier, Hypestat, Newswire/Media Bazar)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.cleaning.url_utils import extract_domain
from src.config_loader import ClientConfig
from src.db.repositories import MediaMasterRecord, MediaMasterRepo


def import_media_master_file(
    file_path: Path | str,
    repo: MediaMasterRepo,
    custom_tier_client_key: str | None = None,
) -> int:
    """Import or update media master entries from `.xlsx` or `.csv` into SQLite `media_master_hypestat`."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File master media tidak ditemukan: {path}")

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path, engine="calamine")

    col_map = {str(c).strip().lower(): c for c in df.columns}

    def _pick(*candidates: str) -> str | None:
        for cand in candidates:
            if cand in col_map:
                return col_map[cand]
        return None

    domain_col = _pick("domain", "url", "website", "portal", "media domain")
    name_col = _pick("media_name", "media name", "nama media", "media")
    tier_bino_col = _pick("tier_bino", "tier bino", "tier binokular", "media tier", "tier")
    custom_tier_col = _pick(
        "client_custom_tier",
        "custom_tier",
        "custom tier",
        f"tier {custom_tier_client_key.lower()}" if custom_tier_client_key else "",
    )
    detail_col = _pick("media_type_detail", "media type detail", "kategori media", "type detail")
    visitor_col = _pick("hypestat_daily_visitor", "daily visitor", "hypestat", "visitor")
    value_col = _pick("media_value", "media value", "valuasi")

    if domain_col is None and name_col is None:
        raise ValueError("File master media wajib memiliki minimal kolom 'domain' atau 'media_name'.")

    records: list[MediaMasterRecord] = []
    for _, row in df.iterrows():
        raw_domain = str(row[domain_col]).strip() if domain_col and pd.notna(row[domain_col]) else ""
        domain = extract_domain(raw_domain)
        if not domain:
            continue

        media_name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else ""
        tier_bino = (
            str(row[tier_bino_col]).strip()
            if tier_bino_col and pd.notna(row[tier_bino_col])
            else ""
        )
        detail = (
            str(row[detail_col]).strip()
            if detail_col and pd.notna(row[detail_col])
            else "Organik"
        )

        custom_tiers: dict[str, str] = {}
        if custom_tier_client_key and custom_tier_col and pd.notna(row[custom_tier_col]):
            val = str(row[custom_tier_col]).strip()
            if val:
                custom_tiers[custom_tier_client_key.lower()] = val

        visitor = 0
        if visitor_col and pd.notna(row[visitor_col]):
            try:
                visitor = int(float(str(row[visitor_col]).replace(",", "").strip()))
            except ValueError:
                visitor = 0

        media_val = 0
        if value_col and pd.notna(row[value_col]):
            try:
                media_val = int(float(str(row[value_col]).replace(",", "").strip()))
            except ValueError:
                media_val = 0

        records.append(
            MediaMasterRecord(
                domain=domain,
                media_name=media_name,
                tier_bino=tier_bino,
                client_custom_tiers=custom_tiers,
                media_type_detail=detail or "Organik",
                hypestat_daily_visitor=visitor,
                media_value=media_val,
            )
        )

    return repo.upsert_many(records, merge_custom_tiers=True)


def enrich_media_attributes(
    news_df: pd.DataFrame,
    config: ClientConfig,
    media_repo: MediaMasterRepo,
) -> pd.DataFrame:
    """Enrich Media Tier (Bino & Client Custom Tier), Hypestat, & Media Type Detail, and auto-takeout Newswire."""
    df = news_df.copy()
    media_map = media_repo.get_all_map()

    custom_tier_cfg = config.media_and_spokesperson.custom_tier
    custom_key = (custom_tier_cfg.client_key or config.client_id).lower()
    custom_col_name = custom_tier_cfg.excel_column_name or f"TIER {config.client_id.upper()}"

    domains: list[str] = []
    tier_bino_list: list[str] = []
    custom_tier_list: list[str] = []
    media_detail_list: list[str] = []
    visitors: list[int] = []

    statuses = df["Status_Takeout"].tolist()
    reasons = df["Alasan_Spam"].tolist()
    urls = df["Page/URL"].fillna("").astype(str).tolist()
    existing_tiers = df["Media Tier"].fillna("").astype(str).tolist()
    existing_details = df["Media Type Detail"].fillna("").astype(str).tolist()
    existing_visitors = df["Oplah/Daily Visitor"].tolist()

    for idx in range(len(df)):
        domain = extract_domain(urls[idx])
        domains.append(domain)
        rec = media_map.get(domain)

        # Tier Bino
        tier_bino = (rec.tier_bino if rec and rec.tier_bino else existing_tiers[idx]).strip()
        tier_bino_list.append(tier_bino)

        # Client Custom Tier (e.g. TIER BRI / TIER BNI)
        custom_tier = ""
        if rec and custom_key in rec.client_custom_tiers:
            custom_tier = rec.client_custom_tiers[custom_key]
        elif custom_tier_cfg.fallback_to_bino_tier:
            custom_tier = tier_bino
        custom_tier_list.append(custom_tier)

        # Media Type Detail (Organik / Newswire / Media Bazar)
        detail = (
            rec.media_type_detail
            if rec and rec.media_type_detail
            else (existing_details[idx] or "Organik")
        ).strip()
        media_detail_list.append(detail)

        # Hypestat daily visitor
        cur_vis = 0
        try:
            cur_vis = int(float(existing_visitors[idx])) if pd.notna(existing_visitors[idx]) else 0
        except (ValueError, TypeError):
            cur_vis = 0
        if cur_vis <= 0 and rec and rec.hypestat_daily_visitor > 0:
            cur_vis = rec.hypestat_daily_visitor
        visitors.append(cur_vis)

        # Auto-Takeout Newswire (0 token AI)
        if (
            config.takeout_rules.auto_takeout_newswire
            and detail.lower() == "newswire"
            and statuses[idx] == "Keep"
        ):
            statuses[idx] = "Takeout"
            reasons[idx] = "Takeout - Newswire"

    df["Domain"] = domains
    df["Media Tier"] = tier_bino_list
    df["Media Type Detail"] = media_detail_list
    df["Oplah/Daily Visitor"] = visitors
    if custom_tier_cfg.enabled:
        df[custom_col_name] = custom_tier_list

    df["Status_Takeout"] = statuses
    df["Alasan_Spam"] = reasons
    return df
