"""Media master seeding & fast in-memory lookup (Custom Tier, Hypestat, Newswire/Media Bazar)."""

from __future__ import annotations

from pathlib import Path
import re

import pandas as pd

from src.cleaning.url_utils import extract_domain
from src.config_loader import ClientConfig
from src.db.repositories import MediaMasterRecord, MediaMasterRepo


def normalize_tier_label(raw_val: object) -> str:
    """Normalize numeric/float tiers (`1.0`, `2`, `tier1`) into canonical `'Tier 1'` / `'Tier 2'` / `'Tier 3'`."""
    if raw_val is None or (isinstance(raw_val, float) and pd.isna(raw_val)):
        return ""
    text = str(raw_val).strip()
    if not text or text.lower() in {"nan", "none", "-", "0", "0.0"}:
        return ""
    m = re.match(r"^(?:tier\s*)?([1-9])(?:\.0+)?$", text, re.IGNORECASE)
    if m:
        return f"Tier {m.group(1)}"
    return text


def import_media_master_file(
    file_path: Path | str,
    repo: MediaMasterRepo,
    custom_tier_client_key: str | None = None,
    sheet_name: str | None = None,
) -> int:
    """Import or update media master entries from `.xlsx` or `.csv` into SQLite `media_master_hypestat`."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File master media tidak ditemukan: {path}")

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        with pd.ExcelFile(path, engine="calamine") as xf:
            target_sheet = sheet_name
            if target_sheet is None:
                # Auto-detect `Tier-*` or `Media Master` sheet if multi-sheet workbook
                for sname in xf.sheet_names:
                    if sname.strip().lower().startswith("tier-") or "media" in sname.strip().lower():
                        target_sheet = sname
                        break
                if target_sheet is None:
                    target_sheet = xf.sheet_names[0]
            df = pd.read_excel(xf, sheet_name=target_sheet)

    col_map = {str(c).strip().lower(): c for c in df.columns}

    def _pick(*candidates: str) -> str | None:
        for cand in candidates:
            if cand and cand in col_map:
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
        f"tier-{custom_tier_client_key.lower()}" if custom_tier_client_key else "",
    )
    detail_col = _pick("media_type_detail", "media type detail", "tipe media 2", "kategori media", "type detail")
    visitor_col = _pick("hypestat_daily_visitor", "daily visitor", "hypestat", "visitor")
    value_col = _pick("media_value", "media value", "pr value", "valuasi")

    if domain_col is None and name_col is None:
        raise ValueError("File master media wajib memiliki minimal kolom 'domain' atau 'media_name'.")

    records_by_key: dict[str, MediaMasterRecord] = {}
    for _, row in df.iterrows():
        raw_domain = str(row[domain_col]).strip() if domain_col and pd.notna(row[domain_col]) else ""
        media_name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else ""
        domain = extract_domain(raw_domain) if raw_domain else ""
        if not domain and media_name:
            # Support `Tier-BNI` where `nama media` holds either domain (`detik.com`) or Print/TV name (`Bali TV`)
            domain = extract_domain(media_name) if "." in media_name and " " not in media_name else media_name.lower()
        if not domain:
            continue

        tier_bino = normalize_tier_label(
            row[tier_bino_col] if tier_bino_col and pd.notna(row[tier_bino_col]) else ""
        )
        detail = (
            str(row[detail_col]).strip()
            if detail_col and pd.notna(row[detail_col])
            else "Organik"
        )

        custom_tiers: dict[str, str] = {}
        if custom_tier_client_key and custom_tier_col and pd.notna(row[custom_tier_col]):
            val = normalize_tier_label(row[custom_tier_col])
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

        records_by_key[domain] = MediaMasterRecord(
            domain=domain,
            media_name=media_name,
            tier_bino=tier_bino,
            client_custom_tiers=custom_tiers,
            media_type_detail=detail or "Organik",
            hypestat_daily_visitor=visitor,
            media_value=media_val,
        )

    return repo.upsert_many(list(records_by_key.values()), merge_custom_tiers=True)


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
    media_names = df["Media Name"].fillna("").astype(str).tolist()
    existing_tiers = df["Media Tier"].fillna("").astype(str).tolist()
    existing_details = df["Media Type Detail"].fillna("").astype(str).tolist()
    existing_visitors = df["Oplah/Daily Visitor"].tolist()

    for idx in range(len(df)):
        domain = extract_domain(urls[idx])
        domains.append(domain)
        mname_key = media_names[idx].strip().lower()
        rec = media_map.get(domain) or (media_map.get(mname_key) if mname_key else None)

        # Tier Bino
        raw_tier_bino = (rec.tier_bino if rec and rec.tier_bino else existing_tiers[idx]).strip()
        tier_bino = normalize_tier_label(raw_tier_bino)
        tier_bino_list.append(tier_bino)

        # Client Custom Tier (e.g. TIER BRI / TIER BNI)
        custom_tier = ""
        if rec and custom_key in rec.client_custom_tiers:
            custom_tier = normalize_tier_label(rec.client_custom_tiers[custom_key])
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
