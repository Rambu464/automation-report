"""Output 1 — Cleaned Excel & Dynamic Formula Pivot Generator (FR-05.1, SAD.md Section 7D).

Supports:
1. New workbook generation via `xlsxwriter`:
   - `News_Clean` (with Excel Table, freeze panes, auto-width, clickable URLs, Conditional Formatting, Column Picker)
   - `Takeout_Spam` (with `Alasan_Spam` for analyst QC)
   - `Statements` (filtered to kept `ID`s)
   - `Pivot` (live `COUNTIF`, `COUNTIFS`, `SUM` formulas referencing `News_Clean` + Native Excel Chart, 0 `#REF!`)
2. Existing client template injection via `openpyxl` when `template_path` is provided.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import openpyxl
import pandas as pd
import xlsxwriter

from src.config_loader import ClientConfig

DEFAULT_CLEAN_COLUMN_ORDER = [
    "ID",
    "Date",
    "Time",
    "Title",
    "Media Name",
    "Media Type",
    "Media Type Detail",
    "Media Tier",
    "Oplah/Daily Visitor",
    "Page/URL",
    "Sentiment",
    "Newstrends",
    "Nama_Isu",
    "Content_Type",
    "Spokesperson",
    "Jabatan",
    "Flag_Cutoff_00",
    "Flag_Near_Dup",
    "Status_Req_Upload",
    "Content",
]

DEFAULT_TAKEOUT_COLUMNS = [
    "ID",
    "Date",
    "Time",
    "Title",
    "Media Name",
    "Media Type",
    "Media Type Detail",
    "Page/URL",
    "Status_Takeout",
    "Alasan_Spam",
]


def _col_letter(col_idx: int) -> str:
    """Convert 0-based column index to Excel column letters (0->A, 25->Z, 26->AA)."""
    result = ""
    n = col_idx + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def _resolve_clean_columns(
    clean_df: pd.DataFrame,
    config: ClientConfig,
    selected_columns: list[str] | None = None,
) -> list[str]:
    if selected_columns:
        return [c for c in selected_columns if c in clean_df.columns]

    ordered: list[str] = []
    custom_tier_col = config.media_and_spokesperson.custom_tier.excel_column_name
    adhoc_names = [c.name for c in config.adhoc_columns]

    for col in DEFAULT_CLEAN_COLUMN_ORDER:
        if col in clean_df.columns and col not in ordered:
            ordered.append(col)
        if col == "Media Tier" and custom_tier_col in clean_df.columns and custom_tier_col not in ordered:
            ordered.append(custom_tier_col)
        if col == "Jabatan":
            for ac in adhoc_names:
                if ac in clean_df.columns and ac not in ordered:
                    ordered.append(ac)

    return ordered


def _write_dataframe_sheet(
    workbook: xlsxwriter.Workbook,
    sheet_name: str,
    df: pd.DataFrame,
    columns: list[str],
    header_fmt: Any,
    text_fmt: Any,
    url_fmt: Any,
    yellow_fmt: Any,
    green_fmt: Any,
    red_fmt: Any,
    gray_fmt: Any,
) -> dict[str, str]:
    """Write a formatted table sheet and return `{column_name: excel_col_letter}`."""
    ws = workbook.add_worksheet(sheet_name)
    ws.freeze_panes(1, 0)

    col_letters: dict[str, str] = {}
    for c_idx, col_name in enumerate(columns):
        ws.write(0, c_idx, col_name, header_fmt)
        col_letters[col_name] = _col_letter(c_idx)

    max_widths = {c_idx: max(len(col_name) + 4, 12) for c_idx, col_name in enumerate(columns)}
    n_rows = len(df)

    for r_idx, (_, row) in enumerate(df.iterrows(), start=1):
        for c_idx, col_name in enumerate(columns):
            val = row.get(col_name, "")
            if pd.isna(val):
                val = ""

            if col_name == "Page/URL" and isinstance(val, str) and val.startswith(("http://", "https://")):
                ws.write_url(r_idx, c_idx, val, url_fmt, string=val)
                max_widths[c_idx] = min(max(max_widths[c_idx], 36), 48)
            elif col_name == "Oplah/Daily Visitor":
                try:
                    num_val = int(float(val)) if val != "" else 0
                    ws.write_number(r_idx, c_idx, num_val, text_fmt)
                except (ValueError, TypeError):
                    ws.write_string(r_idx, c_idx, str(val), text_fmt)
            else:
                s_val = str(val)
                ws.write_string(r_idx, c_idx, s_val, text_fmt)
                cap = 50 if col_name in {"Title", "Newstrends", "Content"} else 32
                max_widths[c_idx] = min(max(max_widths[c_idx], len(s_val) + 2), cap)

    for c_idx, width in max_widths.items():
        ws.set_column(c_idx, c_idx, width)

    if n_rows > 0 and columns:
        ws.autofilter(0, 0, n_rows, len(columns) - 1)

        # Conditional Formatting: Flag_Cutoff_00 (Yellow)
        if "Flag_Cutoff_00" in col_letters:
            c_idx = columns.index("Flag_Cutoff_00")
            ws.conditional_format(
                1, c_idx, n_rows, c_idx,
                {"type": "cell", "criteria": "==", "value": '"CEK_CUTOFF_00:00"', "format": yellow_fmt},
            )

        # Conditional Formatting: Sentiment (Green / Red / Gray)
        if "Sentiment" in col_letters:
            c_idx = columns.index("Sentiment")
            ws.conditional_format(
                1, c_idx, n_rows, c_idx,
                {"type": "cell", "criteria": "==", "value": '"positive"', "format": green_fmt},
            )
            ws.conditional_format(
                1, c_idx, n_rows, c_idx,
                {"type": "cell", "criteria": "==", "value": '"negative"', "format": red_fmt},
            )
            ws.conditional_format(
                1, c_idx, n_rows, c_idx,
                {"type": "cell", "criteria": "==", "value": '"neutral"', "format": gray_fmt},
            )

    return col_letters


def _write_dynamic_pivot_sheet(
    workbook: xlsxwriter.Workbook,
    clean_count: int,
    clean_col_letters: dict[str, str],
    report_payload: dict[str, Any],
    config: ClientConfig,
    section_fmt: Any,
    header_fmt: Any,
    cell_fmt: Any,
    num_fmt: Any,
    total_fmt: Any,
) -> None:
    """Build `Pivot` sheet using live Excel formulas (`COUNTIF`, `COUNTIFS`, `SUM`) + Native Chart."""
    ws = workbook.add_worksheet("Pivot")
    ws.set_column(0, 0, 42)
    ws.set_column(1, 1, 28)
    ws.set_column(2, 5, 14)

    last_row = max(2, clean_count + 1)

    def _rng(col_name: str) -> str | None:
        letter = clean_col_letters.get(col_name)
        if not letter:
            return None
        return f"News_Clean!${letter}$2:${letter}${last_row}"

    sent_rng = _rng("Sentiment")
    media_type_rng = _rng("Media Type")
    custom_tier_name = config.media_and_spokesperson.custom_tier.excel_column_name
    tier_rng = _rng(custom_tier_name) or _rng("Media Tier")
    nt_rng = _rng("Newstrends")
    isu_rng = _rng("Nama_Isu")
    ctype_rng = _rng("Content_Type")
    spk_rng = _rng("Spokesperson")
    jab_rng = _rng("Jabatan")

    row = 0

    # --- Section 1: Sentiment Summary ---
    ws.write(row, 0, "1. Ringkasan Sentimen", section_fmt)
    row += 1
    ws.write(row, 0, "Sentiment", header_fmt)
    ws.write(row, 1, "Jumlah Berita", header_fmt)
    sent_start_row = row + 1
    sentiments = ["positive", "neutral", "negative"]
    for s in sentiments:
        row += 1
        ws.write_string(row, 0, s, cell_fmt)
        if sent_rng and clean_count > 0:
            ws.write_formula(row, 1, f'=COUNTIF({sent_rng}, A{row + 1})', num_fmt)
        else:
            ws.write_number(row, 1, int(report_payload["sentiment_summary"].get(s, 0)), num_fmt)
    sent_end_row = row
    row += 1
    ws.write_string(row, 0, "Total", total_fmt)
    ws.write_formula(row, 1, f"=SUM(B{sent_start_row + 1}:B{sent_end_row + 1})", total_fmt)

    # Embed Native Excel Column Chart for Sentiment Summary
    chart = workbook.add_chart({"type": "column"})
    chart.add_series(
        {
            "name": "Jumlah Berita",
            "categories": ["Pivot", sent_start_row, 0, sent_end_row, 0],
            "values": ["Pivot", sent_start_row, 1, sent_end_row, 1],
            "data_labels": {"value": True},
        }
    )
    chart.set_title({"name": f"Distribusi Sentimen — {config.client_name}"})
    chart.set_legend({"none": True})
    ws.insert_chart("G2", chart, {"x_scale": 1.1, "y_scale": 1.0})

    # --- Section 2: Media Type Breakdown ---
    row += 2
    ws.write(row, 0, "2. Pivot Tipe Media", section_fmt)
    row += 1
    ws.write(row, 0, "Media Type", header_fmt)
    ws.write(row, 1, "Jumlah Berita", header_fmt)
    mt_start = row + 1
    media_types = list(report_payload["media_breakdown"]["by_type"].keys()) or ["online"]
    for mt in media_types:
        row += 1
        ws.write_string(row, 0, mt, cell_fmt)
        if media_type_rng and clean_count > 0:
            ws.write_formula(row, 1, f'=COUNTIF({media_type_rng}, A{row + 1})', num_fmt)
        else:
            ws.write_number(row, 1, int(report_payload["media_breakdown"]["by_type"].get(mt, 0)), num_fmt)
    mt_end = row
    row += 1
    ws.write_string(row, 0, "Total", total_fmt)
    ws.write_formula(row, 1, f"=SUM(B{mt_start + 1}:B{mt_end + 1})", total_fmt)

    # --- Section 3: Custom Media Tier Breakdown ---
    row += 2
    tier_title = custom_tier_name if config.media_and_spokesperson.custom_tier.enabled else "Media Tier"
    ws.write(row, 0, f"3. Pivot {tier_title}", section_fmt)
    row += 1
    ws.write(row, 0, tier_title, header_fmt)
    ws.write(row, 1, "Jumlah Berita", header_fmt)
    t_start = row + 1
    tiers = list(report_payload["media_breakdown"]["by_custom_tier"].keys()) or ["Tier 1", "Tier 2", "Tier 3"]
    for t_label in tiers:
        row += 1
        ws.write_string(row, 0, t_label, cell_fmt)
        if tier_rng and clean_count > 0:
            ws.write_formula(row, 1, f'=COUNTIF({tier_rng}, A{row + 1})', num_fmt)
        else:
            ws.write_number(
                row, 1, int(report_payload["media_breakdown"]["by_custom_tier"].get(t_label, 0)), num_fmt
            )
    t_end = row
    row += 1
    ws.write_string(row, 0, "Total", total_fmt)
    ws.write_formula(row, 1, f"=SUM(B{t_start + 1}:B{t_end + 1})", total_fmt)

    # --- Section 4: Pivot Newstrends & Nama_Isu vs Sentimen ---
    row += 2
    ws.write(row, 0, "4. Pivot Newstrends & Nama Isu vs Sentimen", section_fmt)
    row += 1
    for c_i, h in enumerate(["Newstrends", "Nama_Isu", "Positive", "Neutral", "Negative", "Total"]):
        ws.write(row, c_i, h, header_fmt)
    nt_start = row + 1
    top_nt = report_payload["pivots"]["top_newstrends"]
    for item in top_nt:
        row += 1
        r_excel = row + 1
        ws.write_string(row, 0, item["newstrend"], cell_fmt)
        ws.write_string(row, 1, item["nama_isu"], cell_fmt)
        if nt_rng and isu_rng and sent_rng and clean_count > 0:
            ws.write_formula(row, 2, f'=COUNTIFS({nt_rng}, A{r_excel}, {isu_rng}, B{r_excel}, {sent_rng}, "positive")', num_fmt)
            ws.write_formula(row, 3, f'=COUNTIFS({nt_rng}, A{r_excel}, {isu_rng}, B{r_excel}, {sent_rng}, "neutral")', num_fmt)
            ws.write_formula(row, 4, f'=COUNTIFS({nt_rng}, A{r_excel}, {isu_rng}, B{r_excel}, {sent_rng}, "negative")', num_fmt)
        else:
            ws.write_number(row, 2, int(item["pos"]), num_fmt)
            ws.write_number(row, 3, int(item["neu"]), num_fmt)
            ws.write_number(row, 4, int(item["neg"]), num_fmt)
        ws.write_formula(row, 5, f"=SUM(C{r_excel}:E{r_excel})", num_fmt)
    if top_nt:
        nt_end = row
        row += 1
        ws.write_string(row, 0, "Total", total_fmt)
        ws.write_string(row, 1, "", total_fmt)
        for c_i, col_l in [(2, "C"), (3, "D"), (4, "E"), (5, "F")]:
            ws.write_formula(row, c_i, f"=SUM({col_l}{nt_start + 1}:{col_l}{nt_end + 1})", total_fmt)

    # --- Section 5: Pivot Spokesperson & Jabatan (Khusus Berita Rilis) ---
    row += 2
    ws.write(row, 0, "5. Pivot Spokesperson & Jabatan (Khusus Berita Rilis)", section_fmt)
    row += 1
    for c_i, h in enumerate(["Spokesperson", "Jabatan", "Jumlah Rilis"]):
        ws.write(row, c_i, h, header_fmt)
    spk_start = row + 1
    spk_rows = report_payload["pivots"]["spokesperson_rilis"]
    for item in spk_rows:
        row += 1
        r_excel = row + 1
        ws.write_string(row, 0, str(item["spokesperson"]), cell_fmt)
        ws.write_string(row, 1, str(item["jabatan"]), cell_fmt)
        if ctype_rng and spk_rng and jab_rng and clean_count > 0:
            ws.write_formula(
                row,
                2,
                f'=COUNTIFS({ctype_rng}, "Rilis", {spk_rng}, A{r_excel}, {jab_rng}, B{r_excel})',
                num_fmt,
            )
        else:
            ws.write_number(row, 2, int(item["count"]), num_fmt)
    if spk_rows:
        spk_end = row
        row += 1
        ws.write_string(row, 0, "Total Rilis", total_fmt)
        ws.write_string(row, 1, "", total_fmt)
        ws.write_formula(row, 2, f"=SUM(C{spk_start + 1}:C{spk_end + 1})", total_fmt)


def _inject_into_excel_template(
    template_path: Path,
    output_path: Path,
    clean_df: pd.DataFrame,
    takeout_df: pd.DataFrame,
    clean_columns: list[str],
    takeout_columns: list[str],
) -> Path:
    """Inject cleaned & takeout rows into an existing client `.xlsx` template via `openpyxl`."""
    wb = openpyxl.load_workbook(template_path)

    for sheet_name, df, cols in [
        ("News_Clean", clean_df, clean_columns),
        ("Takeout_Spam", takeout_df, takeout_columns),
    ]:
        if sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            if ws.max_row > 1:
                ws.delete_rows(2, ws.max_row - 1)
        else:
            ws = wb.create_sheet(title=sheet_name)

        for c_idx, col_name in enumerate(cols, start=1):
            ws.cell(row=1, column=c_idx, value=col_name)

        for r_idx, (_, row) in enumerate(df.iterrows(), start=2):
            for c_idx, col_name in enumerate(cols, start=1):
                val = row.get(col_name, "")
                ws.cell(row=r_idx, column=c_idx, value="" if pd.isna(val) else val)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path


def generate_cleaned_excel(
    news_df: pd.DataFrame,
    statements_df: pd.DataFrame,
    report_payload: dict[str, Any],
    config: ClientConfig,
    output_path: Path | str,
    selected_columns: list[str] | None = None,
    template_path: Path | str | None = None,
) -> Path:
    """Generate Output 1: Cleaned Excel workbook (`.xlsx`) with dynamic formula Pivot & Conditional Formatting."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    clean_df = news_df[news_df["Status_Takeout"] == "Keep"].reset_index(drop=True)
    takeout_df = news_df[news_df["Status_Takeout"] != "Keep"].reset_index(drop=True)

    clean_columns = _resolve_clean_columns(clean_df, config, selected_columns=selected_columns)
    takeout_columns = [c for c in DEFAULT_TAKEOUT_COLUMNS if c in takeout_df.columns]

    tpl = Path(template_path) if template_path else (
        Path(config.output_templates.excel_template_path)
        if config.output_templates.excel_template_path
        else None
    )
    if tpl is not None and tpl.exists():
        return _inject_into_excel_template(
            template_path=tpl,
            output_path=out,
            clean_df=clean_df,
            takeout_df=takeout_df,
            clean_columns=clean_columns,
            takeout_columns=takeout_columns,
        )

    workbook = xlsxwriter.Workbook(str(out))
    header_fmt = workbook.add_format(
        {"bold": True, "bg_color": "#1F4E78", "font_color": "#FFFFFF", "border": 1}
    )
    section_fmt = workbook.add_format({"bold": True, "font_size": 12, "font_color": "#1F4E78"})
    text_fmt = workbook.add_format({"valign": "top", "border": 1})
    url_fmt = workbook.add_format({"font_color": "#0563C1", "underline": 1, "border": 1})
    num_fmt = workbook.add_format({"num_format": "#,##0", "border": 1})
    total_fmt = workbook.add_format({"bold": True, "bg_color": "#D9E1F2", "num_format": "#,##0", "border": 1})
    yellow_fmt = workbook.add_format({"bg_color": "#FFF2CC", "font_color": "#7F6000", "bold": True})
    green_fmt = workbook.add_format({"bg_color": "#E2EFDA", "font_color": "#375623"})
    red_fmt = workbook.add_format({"bg_color": "#FCE4D6", "font_color": "#C00000"})
    gray_fmt = workbook.add_format({"bg_color": "#EDEDED", "font_color": "#3F3F3F"})

    # Sheet 1: News_Clean
    clean_col_letters = _write_dataframe_sheet(
        workbook, "News_Clean", clean_df, clean_columns,
        header_fmt, text_fmt, url_fmt, yellow_fmt, green_fmt, red_fmt, gray_fmt,
    )

    # Sheet 2: Takeout_Spam
    _write_dataframe_sheet(
        workbook, "Takeout_Spam", takeout_df, takeout_columns,
        header_fmt, text_fmt, url_fmt, yellow_fmt, green_fmt, red_fmt, gray_fmt,
    )

    # Sheet 3: Statements
    stmt_cols = list(statements_df.columns) if not statements_df.empty else [
        "Report id", "Name", "Position", "Sentiment", "Quote"
    ]
    _write_dataframe_sheet(
        workbook, "Statements", statements_df, stmt_cols,
        header_fmt, text_fmt, url_fmt, yellow_fmt, green_fmt, red_fmt, gray_fmt,
    )

    # Sheet 4: Dynamic Formula Pivot
    _write_dynamic_pivot_sheet(
        workbook=workbook,
        clean_count=len(clean_df),
        clean_col_letters=clean_col_letters,
        report_payload=report_payload,
        config=config,
        section_fmt=section_fmt,
        header_fmt=header_fmt,
        cell_fmt=text_fmt,
        num_fmt=num_fmt,
        total_fmt=total_fmt,
    )

    workbook.close()
    return out
