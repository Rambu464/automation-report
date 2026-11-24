"""Excel ingestion for Newstensity `.xls with Statements` exports via `python-calamine`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

REQUIRED_NEWS_COLUMNS = ("ID", "Title", "Content", "Date", "Media Name", "Page/URL")

# Flexible column aliases encountered across Newstensity export variants
COLUMN_ALIASES: dict[str, str] = {
    "id": "ID",
    "report id": "ID",
    "title": "Title",
    "content": "Content",
    "date": "Date",
    "media name": "Media Name",
    "page/url": "Page/URL",
    "url": "Page/URL",
    "media type": "Media Type",
    "media type detail": "Media Type Detail",
    "media tier": "Media Tier",
    "oplah/daily visitor": "Oplah/Daily Visitor",
    "sentiment": "Sentiment",
    "newstrends": "Newstrends",
}

STATEMENT_ALIASES: dict[str, str] = {
    "report id": "Report id",
    "id": "Report id",
    "name": "Name",
    "spokesperson": "Name",
    "position": "Position",
    "jabatan": "Position",
    "sentiment": "Sentiment",
    "quote": "Quote",
}


@dataclass
class IngestedWorkbook:
    """Result of reading one or more `.xls with Statements` files."""

    news_df: pd.DataFrame
    statements_df: pd.DataFrame
    source_files: list[str]


def _normalize_columns(df: pd.DataFrame, aliases: dict[str, str]) -> pd.DataFrame:
    rename_map: dict[str, str] = {}
    for col in df.columns:
        key = str(col).strip().lower()
        if key in aliases:
            rename_map[col] = aliases[key]
        else:
            rename_map[col] = str(col).strip()
    return df.rename(columns=rename_map)


def _find_sheet_name(sheet_names: list[str], target: str) -> str | None:
    target_lower = target.lower()
    for name in sheet_names:
        if name.strip().lower() == target_lower:
            return name
    return None


def read_newstensity_excel(file_path: Path | str) -> IngestedWorkbook:
    """Read a single `.xls` or `.xlsx` Newstensity export using `python-calamine`."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File Excel tidak ditemukan: {path}")

    with pd.ExcelFile(path, engine="calamine") as xf:
        sheet_names = list(xf.sheet_names)
        news_sheet = _find_sheet_name(sheet_names, "News") or sheet_names[0]
        news_df = pd.read_excel(xf, sheet_name=news_sheet)

        stmt_sheet = _find_sheet_name(sheet_names, "Statements")
        if stmt_sheet is not None:
            statements_df = pd.read_excel(xf, sheet_name=stmt_sheet)
        else:
            statements_df = pd.DataFrame(
                columns=["Report id", "Name", "Position", "Sentiment", "Quote"]
            )

    news_df = _normalize_columns(news_df, COLUMN_ALIASES)
    statements_df = _normalize_columns(statements_df, STATEMENT_ALIASES)

    missing = [c for c in REQUIRED_NEWS_COLUMNS if c not in news_df.columns]
    if missing:
        raise ValueError(
            f"Kolom wajib tidak ditemukan pada sheet News ({path.name}): {', '.join(missing)}"
        )

    # Clean ID & core string columns
    news_df = news_df.dropna(how="all").copy()
    news_df["ID"] = news_df["ID"].astype(str).str.strip()
    news_df = news_df[news_df["ID"].ne("") & news_df["ID"].str.lower().ne("nan")].reset_index(
        drop=True
    )

    for col in ("Title", "Content", "Media Name", "Page/URL"):
        news_df[col] = news_df[col].fillna("").astype(str).str.strip()

    for optional_col in ("Media Type", "Media Type Detail", "Media Tier", "Sentiment", "Newstrends"):
        if optional_col not in news_df.columns:
            news_df[optional_col] = ""
        else:
            news_df[optional_col] = news_df[optional_col].fillna("").astype(str).str.strip()

    if "Oplah/Daily Visitor" not in news_df.columns:
        news_df["Oplah/Daily Visitor"] = 0

    if not statements_df.empty and "Report id" in statements_df.columns:
        statements_df = statements_df.dropna(how="all").copy()
        statements_df["Report id"] = statements_df["Report id"].astype(str).str.strip()
        for col in ("Name", "Position", "Sentiment", "Quote"):
            if col not in statements_df.columns:
                statements_df[col] = ""
            else:
                statements_df[col] = statements_df[col].fillna("").astype(str).str.strip()
    else:
        statements_df = pd.DataFrame(
            columns=["Report id", "Name", "Position", "Sentiment", "Quote"]
        )

    # Initialize standard pipeline columns
    news_df["Status_Takeout"] = "Keep"
    news_df["Alasan_Spam"] = ""
    news_df["Flag_Cutoff_00"] = ""
    news_df["Flag_Near_Dup"] = ""
    news_df["Cluster_ID"] = ""
    news_df["Status_Req_Upload"] = ""

    return IngestedWorkbook(
        news_df=news_df,
        statements_df=statements_df,
        source_files=[path.name],
    )


def ingest_excel_files(file_paths: Iterable[Path | str]) -> IngestedWorkbook:
    """Ingest one or multiple `.xls with Statements` files (supports Daily and Monthly runs)."""
    paths = [Path(p) for p in file_paths]
    if not paths:
        raise ValueError("Minimal 1 file Excel harus diberikan.")

    workbooks = [read_newstensity_excel(p) for p in paths]
    if len(workbooks) == 1:
        return workbooks[0]

    news_df = pd.concat([w.news_df for w in workbooks], ignore_index=True)
    statements_df = pd.concat([w.statements_df for w in workbooks], ignore_index=True)
    if not statements_df.empty:
        statements_df = statements_df.drop_duplicates().reset_index(drop=True)
    return IngestedWorkbook(
        news_df=news_df,
        statements_df=statements_df,
        source_files=[f for w in workbooks for f in w.source_files],
    )


def attach_tier1_spokesperson(
    news_df: pd.DataFrame, statements_df: pd.DataFrame
) -> pd.DataFrame:
    """Attach Tier-1 Spokesperson & Jabatan directly from sheet `Statements` via `Report id == ID`.

    Saves 70%+ LLM extraction tokens (FR-03.3, SAD.md Section 3B).
    """
    df = news_df.copy()
    stmt_lookup: dict[str, tuple[str, str]] = {}

    if not statements_df.empty and "Report id" in statements_df.columns:
        for _, row in statements_df.iterrows():
            rid = str(row.get("Report id", "")).strip()
            name = str(row.get("Name", "")).strip()
            pos = str(row.get("Position", "")).strip()
            if not rid or not name or name in {"0", "-"}:
                continue
            if rid not in stmt_lookup:
                stmt_lookup[rid] = (name, pos)
            else:
                # Prefer entry that also has Position populated
                prev_name, prev_pos = stmt_lookup[rid]
                if not prev_pos and pos:
                    stmt_lookup[rid] = (name, pos)

    spokespersons: list[str] = []
    jabatans: list[str] = []
    has_stmt: list[bool] = []

    for rid in df["ID"].astype(str):
        if rid in stmt_lookup:
            name, pos = stmt_lookup[rid]
            spokespersons.append(name)
            jabatans.append(pos)
            has_stmt.append(True)
        else:
            spokespersons.append("")
            jabatans.append("")
            has_stmt.append(False)

    df["Spokesperson"] = spokespersons
    df["Jabatan"] = jabatans
    df["Has_Statement"] = has_stmt
    return df
