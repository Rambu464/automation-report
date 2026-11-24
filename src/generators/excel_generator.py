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
    pct_fmt: Any,
    total_fmt: Any,
    total_pct_fmt: Any,
) -> None:
    """Build `Pivot` sheet with 8 dynamic-formula tables (`COUNTIF`, `COUNTIFS`, `COUNTBLANK`, `SUM`, `IFERROR`) & 6 Native Excel Charts."""
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
    media_name_rng = _rng("Media Name")
    date_rng = _rng("Date")
    custom_tier_name = config.media_and_spokesperson.custom_tier.excel_column_name
    tier_rng = _rng(custom_tier_name) or _rng("Media Tier")
    nt_rng = _rng("Newstrends")
    isu_rng = _rng("Nama_Isu")
    ctype_rng = _rng("Content_Type")
    spk_rng = _rng("Spokesperson")
    jab_rng = _rng("Jabatan")

    row = 0

    # --- Section 1: Ringkasan Sentimen (+ Persentase %) ---
    ws.write(row, 0, "1. Ringkasan Sentimen", section_fmt)
    row += 1
    for c_i, h in enumerate(["Sentiment", "Jumlah Berita", "Persentase"]):
        ws.write(row, c_i, h, header_fmt)
    sent_start_row = row + 1
    sentiments = ["positive", "neutral", "negative"]
    sent_total = sum(int(report_payload["sentiment_summary"].get(s, 0)) for s in sentiments)
    sent_total_excel_row = sent_start_row + len(sentiments) + 1
    for s in sentiments:
        row += 1
        r_excel = row + 1
        val = int(report_payload["sentiment_summary"].get(s, 0))
        pct_val = (val / sent_total) if sent_total > 0 else 0.0
        ws.write_string(row, 0, s, cell_fmt)
        if sent_rng and clean_count > 0:
            ws.write_formula(row, 1, f'=COUNTIF({sent_rng}, A{r_excel})', num_fmt, val)
        else:
            ws.write_number(row, 1, val, num_fmt)
        ws.write_formula(row, 2, f"=IFERROR(B{r_excel}/$B${sent_total_excel_row}, 0)", pct_fmt, pct_val)
    sent_end_row = row
    row += 1
    ws.write_string(row, 0, "Total", total_fmt)
    ws.write_formula(row, 1, f"=SUM(B{sent_start_row + 1}:B{sent_end_row + 1})", total_fmt, sent_total)
    ws.write_formula(row, 2, f"=SUM(C{sent_start_row + 1}:C{sent_end_row + 1})", total_pct_fmt, 1.0 if sent_total > 0 else 0.0)

    # Chart 1: Column Chart — Distribusi Sentimen
    chart1 = workbook.add_chart({"type": "column"})
    chart1.add_series(
        {
            "name": "Jumlah Berita",
            "categories": ["Pivot", sent_start_row, 0, sent_end_row, 0],
            "values": ["Pivot", sent_start_row, 1, sent_end_row, 1],
            "data_labels": {"value": True},
        }
    )
    chart1.set_title({"name": f"1. Distribusi Sentimen — {config.client_name}"})
    chart1.set_legend({"none": True})
    ws.insert_chart("H2", chart1, {"x_scale": 1.15, "y_scale": 1.0})

    # --- Section 2: Sentimen Khusus Tier 1 (+ Persentase %) ---
    row += 2
    tier_title = custom_tier_name if config.media_and_spokesperson.custom_tier.enabled else "Media Tier"
    ws.write(row, 0, f"2. Sentimen Khusus {tier_title} = Tier 1", section_fmt)
    row += 1
    for c_i, h in enumerate(["Sentiment (Tier 1)", "Jumlah Berita", "Persentase"]):
        ws.write(row, c_i, h, header_fmt)
    t1_start_row = row + 1
    t1_summary = report_payload.get("tier1_sentiment_summary") or {}
    t1_total = sum(int(t1_summary.get(s, 0)) for s in sentiments)
    t1_total_excel_row = t1_start_row + len(sentiments) + 1
    for s in sentiments:
        row += 1
        r_excel = row + 1
        val = int(t1_summary.get(s, 0))
        pct_val = (val / t1_total) if t1_total > 0 else 0.0
        ws.write_string(row, 0, s, cell_fmt)
        if tier_rng and sent_rng and clean_count > 0:
            ws.write_formula(row, 1, f'=COUNTIFS({tier_rng}, "Tier 1", {sent_rng}, A{r_excel})', num_fmt, val)
        else:
            ws.write_number(row, 1, val, num_fmt)
        ws.write_formula(row, 2, f"=IFERROR(B{r_excel}/$B${t1_total_excel_row}, 0)", pct_fmt, pct_val)
    t1_end_row = row
    row += 1
    ws.write_string(row, 0, "Total Tier 1", total_fmt)
    ws.write_formula(row, 1, f"=SUM(B{t1_start_row + 1}:B{t1_end_row + 1})", total_fmt, t1_total)
    ws.write_formula(row, 2, f"=SUM(C{t1_start_row + 1}:C{t1_end_row + 1})", total_pct_fmt, 1.0 if t1_total > 0 else 0.0)

    # Chart 2: Pie Chart — Sentimen Tier 1
    chart2 = workbook.add_chart({"type": "pie"})
    chart2.add_series(
        {
            "name": "Sentimen Tier 1",
            "categories": ["Pivot", t1_start_row, 0, t1_end_row, 0],
            "values": ["Pivot", t1_start_row, 1, t1_end_row, 1],
            "data_labels": {"percentage": True, "value": True},
        }
    )
    chart2.set_title({"name": f"2. Sentimen Khusus {tier_title} (Tier 1)"})
    ws.insert_chart("H18", chart2, {"x_scale": 1.15, "y_scale": 1.0})

    # --- Section 3: Pivot Tipe Media ---
    row += 2
    ws.write(row, 0, "3. Pivot Tipe Media", section_fmt)
    row += 1
    ws.write(row, 0, "Media Type", header_fmt)
    ws.write(row, 1, "Jumlah Berita", header_fmt)
    mt_start = row + 1
    media_types = list(report_payload["media_breakdown"]["by_type"].keys()) or ["online"]
    mt_total = 0
    for mt in media_types:
        row += 1
        val = int(report_payload["media_breakdown"]["by_type"].get(mt, 0))
        mt_total += val
        ws.write_string(row, 0, mt, cell_fmt)
        if media_type_rng and clean_count > 0:
            ws.write_formula(row, 1, f'=COUNTIF({media_type_rng}, A{row + 1})', num_fmt, val)
        else:
            ws.write_number(row, 1, val, num_fmt)
    mt_end = row
    row += 1
    ws.write_string(row, 0, "Total", total_fmt)
    ws.write_formula(row, 1, f"=SUM(B{mt_start + 1}:B{mt_end + 1})", total_fmt, mt_total)

    # Chart 3: Doughnut Chart — Tipe Media
    chart3 = workbook.add_chart({"type": "doughnut"})
    chart3.add_series(
        {
            "name": "Tipe Media",
            "categories": ["Pivot", mt_start, 0, mt_end, 0],
            "values": ["Pivot", mt_start, 1, mt_end, 1],
            "data_labels": {"percentage": True, "value": True},
        }
    )
    chart3.set_title({"name": "3. Distribusi Tipe Media"})
    ws.insert_chart("H34", chart3, {"x_scale": 1.15, "y_scale": 1.0})

    # --- Section 4: Pivot Custom Media Tier ---
    row += 2
    ws.write(row, 0, f"4. Pivot {tier_title}", section_fmt)
    row += 1
    ws.write(row, 0, tier_title, header_fmt)
    ws.write(row, 1, "Jumlah Berita", header_fmt)
    t_start = row + 1
    tiers = list(report_payload["media_breakdown"]["by_custom_tier"].keys()) or ["Tier 1", "Tier 2", "Tier 3"]
    t_total = 0
    for t_label in tiers:
        row += 1
        val = int(report_payload["media_breakdown"]["by_custom_tier"].get(t_label, 0))
        t_total += val
        ws.write_string(row, 0, t_label, cell_fmt)
        if tier_rng and clean_count > 0:
            if t_label == "Unassigned":
                ws.write_formula(row, 1, f'=COUNTBLANK({tier_rng})', num_fmt, val)
            else:
                ws.write_formula(row, 1, f'=COUNTIF({tier_rng}, A{row + 1})', num_fmt, val)
        else:
            ws.write_number(row, 1, val, num_fmt)
    t_end = row
    row += 1
    ws.write_string(row, 0, "Total", total_fmt)
    ws.write_formula(row, 1, f"=SUM(B{t_start + 1}:B{t_end + 1})", total_fmt, t_total)

    # Chart 4: Column Chart — Custom Media Tier
    chart4 = workbook.add_chart({"type": "column"})
    chart4.add_series(
        {
            "name": tier_title,
            "categories": ["Pivot", t_start, 0, t_end, 0],
            "values": ["Pivot", t_start, 1, t_end, 1],
            "data_labels": {"value": True},
        }
    )
    chart4.set_title({"name": f"4. Distribusi {tier_title}"})
    chart4.set_legend({"none": True})
    ws.insert_chart("H50", chart4, {"x_scale": 1.15, "y_scale": 1.0})

    # --- Section 5: Pivot Timeline Harian vs Sentimen ---
    row += 2
    ws.write(row, 0, "5. Pivot Timeline Pemberitaan Harian", section_fmt)
    row += 1
    for c_i, h in enumerate(["Tanggal", "Positive", "Neutral", "Negative", "Total"]):
        ws.write(row, c_i, h, header_fmt)
    tl_start = row + 1
    timeline_rows = report_payload["pivots"].get("timeline_daily") or []
    tl_pos_s = tl_neu_s = tl_neg_s = 0
    for item in timeline_rows:
        row += 1
        r_excel = row + 1
        p_v = int(item.get("pos", 0))
        u_v = int(item.get("neu", 0))
        n_v = int(item.get("neg", 0))
        tot_v = int(item.get("total", p_v + u_v + n_v))
        tl_pos_s += p_v
        tl_neu_s += u_v
        tl_neg_s += n_v
        ws.write_string(row, 0, str(item["date"]), cell_fmt)
        if date_rng and sent_rng and clean_count > 0:
            ws.write_formula(row, 1, f'=COUNTIFS({date_rng}, A{r_excel}, {sent_rng}, "positive")', num_fmt, p_v)
            ws.write_formula(row, 2, f'=COUNTIFS({date_rng}, A{r_excel}, {sent_rng}, "neutral")', num_fmt, u_v)
            ws.write_formula(row, 3, f'=COUNTIFS({date_rng}, A{r_excel}, {sent_rng}, "negative")', num_fmt, n_v)
        else:
            ws.write_number(row, 1, p_v, num_fmt)
            ws.write_number(row, 2, u_v, num_fmt)
            ws.write_number(row, 3, n_v, num_fmt)
        ws.write_formula(row, 4, f"=SUM(B{r_excel}:D{r_excel})", num_fmt, tot_v)
    if timeline_rows:
        tl_end = row
        row += 1
        ws.write_string(row, 0, "Total", total_fmt)
        for c_i, col_l, c_sum in [
            (1, "B", tl_pos_s),
            (2, "C", tl_neu_s),
            (3, "D", tl_neg_s),
            (4, "E", tl_pos_s + tl_neu_s + tl_neg_s),
        ]:
            ws.write_formula(row, c_i, f"=SUM({col_l}{tl_start + 1}:{col_l}{tl_end + 1})", total_fmt, c_sum)

        # Chart 5: Line Chart — Tren Pemberitaan Harian
        chart5 = workbook.add_chart({"type": "line"})
        chart5.add_series(
            {
                "name": "Total Berita",
                "categories": ["Pivot", tl_start, 0, tl_end, 0],
                "values": ["Pivot", tl_start, 4, tl_end, 4],
                "data_labels": {"value": True},
                "marker": {"type": "circle", "size": 6},
            }
        )
        chart5.set_title({"name": "5. Tren Pemberitaan Harian"})
        ws.insert_chart("H66", chart5, {"x_scale": 1.15, "y_scale": 1.0})

    # --- Section 6: Pivot Newstrends & Nama_Isu vs Sentimen ---
    row += 2
    ws.write(row, 0, "6. Pivot Newstrends & Nama Isu vs Sentimen", section_fmt)
    row += 1
    for c_i, h in enumerate(["Newstrends", "Nama_Isu", "Positive", "Neutral", "Negative", "Total"]):
        ws.write(row, c_i, h, header_fmt)
    nt_start = row + 1
    top_nt = report_payload["pivots"]["top_newstrends"]
    nt_pos_sum = nt_neu_sum = nt_neg_sum = 0
    for item in top_nt:
        row += 1
        r_excel = row + 1
        pos_v = int(item["pos"])
        neu_v = int(item["neu"])
        neg_v = int(item["neg"])
        tot_v = pos_v + neu_v + neg_v
        nt_pos_sum += pos_v
        nt_neu_sum += neu_v
        nt_neg_sum += neg_v
        ws.write_string(row, 0, item["newstrend"], cell_fmt)
        ws.write_string(row, 1, item["nama_isu"], cell_fmt)
        if nt_rng and isu_rng and sent_rng and clean_count > 0:
            ws.write_formula(row, 2, f'=COUNTIFS({nt_rng}, A{r_excel}, {isu_rng}, B{r_excel}, {sent_rng}, "positive")', num_fmt, pos_v)
            ws.write_formula(row, 3, f'=COUNTIFS({nt_rng}, A{r_excel}, {isu_rng}, B{r_excel}, {sent_rng}, "neutral")', num_fmt, neu_v)
            ws.write_formula(row, 4, f'=COUNTIFS({nt_rng}, A{r_excel}, {isu_rng}, B{r_excel}, {sent_rng}, "negative")', num_fmt, neg_v)
        else:
            ws.write_number(row, 2, pos_v, num_fmt)
            ws.write_number(row, 3, neu_v, num_fmt)
            ws.write_number(row, 4, neg_v, num_fmt)
        ws.write_formula(row, 5, f"=SUM(C{r_excel}:E{r_excel})", num_fmt, tot_v)
    if top_nt:
        nt_end = row
        row += 1
        ws.write_string(row, 0, "Total", total_fmt)
        ws.write_string(row, 1, "", total_fmt)
        for c_i, col_l, cached_sum in [
            (2, "C", nt_pos_sum),
            (3, "D", nt_neu_sum),
            (4, "E", nt_neg_sum),
            (5, "F", nt_pos_sum + nt_neu_sum + nt_neg_sum),
        ]:
            ws.write_formula(row, c_i, f"=SUM({col_l}{nt_start + 1}:{col_l}{nt_end + 1})", total_fmt, cached_sum)

    # --- Section 7: Pivot Spokesperson & Jabatan (Khusus Berita Rilis) ---
    row += 2
    ws.write(row, 0, "7. Pivot Spokesperson & Jabatan (Khusus Berita Rilis)", section_fmt)
    row += 1
    for c_i, h in enumerate(["Spokesperson", "Jabatan", "Jumlah Rilis"]):
        ws.write(row, c_i, h, header_fmt)
    spk_start = row + 1
    spk_rows = report_payload["pivots"]["spokesperson_rilis"]
    spk_total = 0
    for item in spk_rows:
        row += 1
        r_excel = row + 1
        cnt_v = int(item["count"])
        spk_total += cnt_v
        ws.write_string(row, 0, str(item["spokesperson"]), cell_fmt)
        ws.write_string(row, 1, str(item["jabatan"]), cell_fmt)
        if ctype_rng and spk_rng and jab_rng and clean_count > 0:
            ws.write_formula(
                row,
                2,
                f'=COUNTIFS({ctype_rng}, "Rilis", {spk_rng}, A{r_excel}, {jab_rng}, B{r_excel})',
                num_fmt,
                cnt_v,
            )
        else:
            ws.write_number(row, 2, cnt_v, num_fmt)
    if spk_rows:
        spk_end = row
        row += 1
        ws.write_string(row, 0, "Total Rilis", total_fmt)
        ws.write_string(row, 1, "", total_fmt)
        ws.write_formula(row, 2, f"=SUM(C{spk_start + 1}:C{spk_end + 1})", total_fmt, spk_total)

    # --- Section 8: Pivot Top Media Name ---
    row += 2
    ws.write(row, 0, "8. Pivot Top Media (Media Name)", section_fmt)
    row += 1
    ws.write(row, 0, "Media Name", header_fmt)
    ws.write(row, 1, "Jumlah Berita", header_fmt)
    tm_start = row + 1
    top_media_rows = (report_payload["pivots"].get("top_media") or [])[:30]
    tm_total = 0
    for item in top_media_rows:
        row += 1
        r_excel = row + 1
        cnt_v = int(item["count"])
        tm_total += cnt_v
        ws.write_string(row, 0, str(item["media_name"]), cell_fmt)
        if media_name_rng and clean_count > 0:
            ws.write_formula(row, 1, f'=COUNTIF({media_name_rng}, A{r_excel})', num_fmt, cnt_v)
        else:
            ws.write_number(row, 1, cnt_v, num_fmt)
    if top_media_rows:
        tm_end = row
        row += 1
        ws.write_string(row, 0, "Total Top Media", total_fmt)
        ws.write_formula(row, 1, f"=SUM(B{tm_start + 1}:B{tm_end + 1})", total_fmt, tm_total)

        # Chart 6: Horizontal Bar Chart — Top 10 Media
        top10_end = min(tm_end, tm_start + 9)
        chart6 = workbook.add_chart({"type": "bar"})
        chart6.add_series(
            {
                "name": "Jumlah Berita",
                "categories": ["Pivot", tm_start, 0, top10_end, 0],
                "values": ["Pivot", tm_start, 1, top10_end, 1],
                "data_labels": {"value": True},
            }
        )
        chart6.set_title({"name": "6. Top 10 Media Teraktif"})
        chart6.set_legend({"none": True})
        ws.insert_chart("H82", chart6, {"x_scale": 1.15, "y_scale": 1.15})


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
    pct_fmt = workbook.add_format({"num_format": "0.0%", "border": 1})
    total_fmt = workbook.add_format({"bold": True, "bg_color": "#D9E1F2", "num_format": "#,##0", "border": 1})
    total_pct_fmt = workbook.add_format({"bold": True, "bg_color": "#D9E1F2", "num_format": "0.0%", "border": 1})
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
        pct_fmt=pct_fmt,
        total_fmt=total_fmt,
        total_pct_fmt=total_pct_fmt,
    )

    workbook.close()
    return out
