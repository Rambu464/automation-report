"""Unit tests for Sprint 3: Auto-Pivot, Competitor Curation, `report_payload.json`, & Triple Deliverables."""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pandas as pd
from pptx import Presentation

from src.ai_engine.schemas import Pass3NarrativeOutput
from src.config_loader import load_client_config
from src.generators.excel_generator import generate_cleaned_excel
from src.generators.pptx_generator import generate_pptx_report
from src.generators.wording_generator import render_wording_text, save_wording_text
from src.pivot.payload import build_report_payload, save_report_payload


def _sample_classified_df() -> tuple[pd.DataFrame, pd.DataFrame]:
    news_df = pd.DataFrame(
        [
            {
                "ID": "N-1",
                "Date": "2026-11-19",
                "Time": "09:30",
                "Title": "BRI Salurkan KUR Rp 120 Triliun Dorong UMKM",
                "Content": "Penyaluran KUR BRI meningkat signifikan.",
                "Media Name": "Kompas.com",
                "Media Type": "online",
                "Media Type Detail": "Organik",
                "Media Tier": "Tier 1",
                "TIER BRI": "Tier 1",
                "Oplah/Daily Visitor": 500000,
                "Page/URL": "https://kompas.com/bri-kur-1",
                "Sentiment": "positive",
                "Newstrends": "BRI Salurkan KUR Dorong UMKM Naik Kelas",
                "Nama_Isu": "Penyaluran KUR UMKM",
                "Content_Type": "Rilis",
                "Spokesperson": "Sunarso",
                "Jabatan": "Direktur Utama BRI",
                "Kluster": "UMKM & KUR",
                "Paid_Earned": "Earned",
                "Status_Takeout": "Keep",
                "Alasan_Spam": "",
                "Flag_Cutoff_00": "",
                "Flag_Near_Dup": "",
                "Status_Req_Upload": "Matched (Req Upload)",
            },
            {
                "ID": "N-2",
                "Date": "2026-11-19",
                "Time": "00:00",
                "Title": "BRI Gelar Pelatihan UMKM Tanpa Narasumber",
                "Content": "Pelatihan UMKM digelar serentak.",
                "Media Name": "BeritaSatu.com",
                "Media Type": "online",
                "Media Type Detail": "Organik",
                "Media Tier": "Tier 1",
                "TIER BRI": "Tier 2",
                "Oplah/Daily Visitor": 200000,
                "Page/URL": "https://beritasatu.com/bri-umkm-2",
                "Sentiment": "positive",
                "Newstrends": "BRI Salurkan KUR Dorong UMKM Naik Kelas",
                "Nama_Isu": "Penyaluran KUR UMKM",
                "Content_Type": "Rilis",
                "Spokesperson": "0",
                "Jabatan": "0",
                "Kluster": "UMKM & KUR",
                "Paid_Earned": "Earned",
                "Status_Takeout": "Keep",
                "Alasan_Spam": "",
                "Flag_Cutoff_00": "CEK_CUTOFF_00:00",
                "Flag_Near_Dup": "",
                "Status_Req_Upload": "",
            },
            {
                "ID": "N-3",
                "Date": "2026-11-19",
                "Time": "11:00",
                "Title": "Bank Mandiri Catat Laba Bersih Tumbuh 15 Persen",
                "Content": "Kinerja Bank Mandiri tumbuh positif di kuartal IV.",
                "Media Name": "Bisnis.com",
                "Media Type": "online",
                "Media Type Detail": "Organik",
                "Media Tier": "Tier 1",
                "TIER BRI": "Tier 1",
                "Oplah/Daily Visitor": 420000,
                "Page/URL": "https://bisnis.com/mandiri-laba-3",
                "Sentiment": "positive",
                "Newstrends": "Bank Mandiri Catat Pertumbuhan Laba Bersih",
                "Nama_Isu": "Kinerja Bank Mandiri",
                "Content_Type": "Organik",
                "Spokesperson": "0",
                "Jabatan": "0",
                "Kluster": "Korporasi & Keuangan",
                "Paid_Earned": "Earned",
                "Status_Takeout": "Keep",
                "Alasan_Spam": "",
                "Flag_Cutoff_00": "",
                "Flag_Near_Dup": "",
                "Status_Req_Upload": "",
            },
            {
                "ID": "N-4",
                "Date": "2026-11-19",
                "Time": "12:15",
                "Title": "Kasus Gangguan Layanan Aplikasi Bank Mandiri Dikeluhkan Nasabah",
                "Content": "Nasabah Bank Mandiri mengeluhkan gangguan transaksi.",
                "Media Name": "Tempo.co",
                "Media Type": "online",
                "Media Type Detail": "Organik",
                "Media Tier": "Tier 1",
                "TIER BRI": "Tier 1",
                "Oplah/Daily Visitor": 350000,
                "Page/URL": "https://tempo.co/mandiri-gangguan-4",
                "Sentiment": "negative",
                "Newstrends": "Kasus Gangguan Aplikasi Bank Mandiri Dikeluhkan Nasabah",
                "Nama_Isu": "Gangguan Bank Mandiri",
                "Content_Type": "Organik",
                "Spokesperson": "0",
                "Jabatan": "0",
                "Kluster": "Layanan Digital (BRImo)",
                "Paid_Earned": "Earned",
                "Status_Takeout": "Keep",
                "Alasan_Spam": "",
                "Flag_Cutoff_00": "",
                "Flag_Near_Dup": "",
                "Status_Req_Upload": "",
            },
            {
                "ID": "N-5",
                "Date": "2026-11-19",
                "Time": "13:00",
                "Title": "Iklan - Promo Diskon Akhir Tahun",
                "Content": "Iklan promo.",
                "Media Name": "Koran Lokal",
                "Media Type": "print",
                "Media Type Detail": "Organik",
                "Media Tier": "Tier 3",
                "TIER BRI": "Tier 3",
                "Oplah/Daily Visitor": 10000,
                "Page/URL": "https://koranlokal.id/iklan-5",
                "Sentiment": "neutral",
                "Newstrends": "",
                "Nama_Isu": "",
                "Content_Type": "Organik",
                "Spokesperson": "0",
                "Jabatan": "0",
                "Kluster": "",
                "Paid_Earned": "Paid",
                "Status_Takeout": "Takeout",
                "Alasan_Spam": "Pre-Filter - Iklan/Advertorial (Regex)",
                "Flag_Cutoff_00": "",
                "Flag_Near_Dup": "",
                "Status_Req_Upload": "",
            },
        ]
    )
    statements_df = pd.DataFrame(
        [
            {
                "Report id": "N-1",
                "Name": "Sunarso",
                "Position": "Direktur Utama BRI",
                "Sentiment": "positive",
                "Quote": "BRI terus mendorong UMKM naik kelas.",
            }
        ]
    )
    return news_df, statements_df


def test_auto_pivot_competitor_and_triple_deliverables(tmp_path: Path) -> None:
    cfg = load_client_config("bri", clients_dir=Path("clients"))
    news_df, statements_df = _sample_classified_df()

    # 1. Build & save report_payload.json (Single Source of Truth)
    payload = build_report_payload(
        news_df=news_df,
        config=cfg,
        period_label="19 Nov 2026",
        cutoff_wib="15:00 WIB",
        req_upload_matched=1,
    )
    payload_path = save_report_payload(payload, tmp_path / "report_payload.json")
    assert payload_path.exists()

    # Zero discrepancy checks
    assert payload["meta"]["total_raw"] == 5
    assert payload["meta"]["total_clean"] == 4
    assert payload["meta"]["total_takeout"] == 1
    assert payload["sentiment_summary"] == {"positive": 3, "neutral": 0, "negative": 1}
    assert payload["media_breakdown"]["by_custom_tier"] == {"Tier 1": 3, "Tier 2": 1}
    assert payload["social_media_optional"] is None

    # Spokesperson Rilis Pivot MUST include both Sunarso AND "0"
    spk_map = {(r["spokesperson"], r["jabatan"]): r["count"] for r in payload["pivots"]["spokesperson_rilis"]}
    assert spk_map[("Sunarso", "Direktur Utama BRI")] == 1
    assert spk_map[("0", "0")] == 1

    # Competitor highlights MUST have 0% Media-URL mismatch
    mandiri_pos = payload["competitor_highlights"]["Bank Mandiri"]["positive"]
    mandiri_neg = payload["competitor_highlights"]["Bank Mandiri"]["negative"]
    assert len(mandiri_pos) == 1
    assert mandiri_pos[0]["media_name"] == "Bisnis.com"
    assert mandiri_pos[0]["url"] == "https://bisnis.com/mandiri-laba-3"
    assert len(mandiri_neg) == 1
    assert mandiri_neg[0]["media_name"] == "Tempo.co"
    assert mandiri_neg[0]["url"] == "https://tempo.co/mandiri-gangguan-4"

    narrative = Pass3NarrativeOutput(
        executive_summary=[
            "Total 4 berita bersih dengan 3 sentimen positif dan 1 sentimen negatif.",
            "Isu utama didorong oleh penyaluran KUR UMKM BRI.",
        ],
        pr_analysis="Sentimen positif mendominasi pemberitaan BRI.",
        public_conversation_direction="Percakapan publik mengarah positif pada dukungan UMKM.",
        recommendations=["Lanjutkan publikasi capaian KUR di media Tier 1."],
    )

    # 2. Output 1: Excel (xlsxwriter) with live formulas & 0 #REF!
    excel_path = generate_cleaned_excel(
        news_df=news_df,
        statements_df=statements_df,
        report_payload=payload,
        config=cfg,
        output_path=tmp_path / "BRI_Cleaned.xlsx",
    )
    wb = openpyxl.load_workbook(excel_path, data_only=False)
    assert wb.sheetnames == ["News_Clean", "Takeout_Spam", "Statements", "Pivot"]
    ws_clean = wb["News_Clean"]
    assert ws_clean.max_row == 5  # 1 header + 4 keep rows
    ws_takeout = wb["Takeout_Spam"]
    assert ws_takeout.max_row == 2  # 1 header + 1 takeout row

    ws_pivot = wb["Pivot"]
    formulas = [
        str(cell.value)
        for row in ws_pivot.iter_rows()
        for cell in row
        if isinstance(cell.value, str) and cell.value.startswith("=")
    ]
    assert any("COUNTIF(" in f for f in formulas)
    assert any("COUNTIFS(" in f for f in formulas)
    assert any("SUM(" in f for f in formulas)
    assert not any("#REF!" in f for f in formulas)

    # Verify cached formula values are present immediately (even in Excel Protected View)
    wb_cached = openpyxl.load_workbook(excel_path, data_only=True)
    ws_pivot_cached = wb_cached["Pivot"]
    assert ws_pivot_cached["B3"].value == 3  # positive
    assert ws_pivot_cached["B5"].value == 1  # negative
    assert ws_pivot_cached["B6"].value == 4  # total

    # Test Column Picker (hide internal Flag_Cutoff_00)
    client_excel = generate_cleaned_excel(
        news_df=news_df,
        statements_df=statements_df,
        report_payload=payload,
        config=cfg,
        output_path=tmp_path / "BRI_Client_Picked.xlsx",
        selected_columns=["ID", "Date", "Title", "Media Name", "TIER BRI", "Sentiment", "Kluster"],
    )
    wb_picked = openpyxl.load_workbook(client_excel, data_only=False)
    picked_headers = [c.value for c in wb_picked["News_Clean"][1]]
    assert picked_headers == ["ID", "Date", "Title", "Media Name", "TIER BRI", "Sentiment", "Kluster"]
    assert "Flag_Cutoff_00" not in picked_headers

    # Test openpyxl template injection mode
    tpl_path = tmp_path / "client_template.xlsx"
    wb_tpl = openpyxl.Workbook()
    wb_tpl.active.title = "Custom_Cover"
    wb_tpl.save(tpl_path)
    injected_path = generate_cleaned_excel(
        news_df=news_df,
        statements_df=statements_df,
        report_payload=payload,
        config=cfg,
        output_path=tmp_path / "BRI_From_Template.xlsx",
        template_path=tpl_path,
    )
    wb_inj = openpyxl.load_workbook(injected_path)
    assert "Custom_Cover" in wb_inj.sheetnames
    assert "News_Clean" in wb_inj.sheetnames
    assert wb_inj["News_Clean"].max_row == 5

    # 3. Output 2: PPTX Visual Report (Anti-Mismatch verification)
    pptx_path = generate_pptx_report(
        report_payload=payload,
        narrative=narrative,
        config=cfg,
        output_path=tmp_path / "BRI_Report.pptx",
    )
    prs = Presentation(str(pptx_path))
    assert len(prs.slides) == 5  # Cover, Exec Summary, Top Newstrends, Spokesperson, Bank Mandiri Competitor
    all_pptx_text = "\n".join(
        shape.text
        for slide in prs.slides
        for shape in slide.shapes
        if shape.has_text_frame
    )
    assert "Bank Rakyat Indonesia (BRI)" in all_pptx_text
    assert "19 Nov 2026" in all_pptx_text

    # Check competitor table URLs match Media Name on Slide 5
    comp_tables = [s.table for s in prs.slides[4].shapes if s.has_table]
    assert len(comp_tables) == 1
    row1_cells = [c.text for c in comp_tables[0].rows[1].cells]
    assert row1_cells[1] == "Bisnis.com"
    assert row1_cells[4] == "https://bisnis.com/mandiri-laba-3"

    # 4. Output 3: Wording Text (100% synced numbers, no Sosmed placeholder)
    wording = render_wording_text(payload, narrative, cfg)
    wording_path = save_wording_text(wording, tmp_path / "BRI_Wording.txt")
    assert wording_path.exists()
    assert "Total Pemberitaan Bersih: 4 berita" in wording
    assert "Positif 3 (75.0%)" in wording
    assert "Negatif 1 (25.0%)" in wording
    assert "Media Sosial:" not in wording
    assert "Percakapan publik mengarah positif" in wording
