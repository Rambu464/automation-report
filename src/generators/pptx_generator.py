"""Output 2 — Visual Report Generator (`.pptx` + optional `.pdf` export) with 0% Media-URL Mismatch (FR-05.2)."""

from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from src.ai_engine.schemas import Pass3NarrativeOutput
from src.config_loader import ClientConfig

NAVY = RGBColor(0x1F, 0x4E, 0x78)
DARK_TEXT = RGBColor(0x22, 0x22, 0x22)
MUTED_TEXT = RGBColor(0x59, 0x59, 0x59)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_BG = RGBColor(0xF2, 0xF5, 0xF9)


def _render_sentiment_chart_png(sentiment_summary: dict[str, int]) -> io.BytesIO:
    labels = ["Positive", "Neutral", "Negative"]
    values = [
        int(sentiment_summary.get("positive", 0)),
        int(sentiment_summary.get("neutral", 0)),
        int(sentiment_summary.get("negative", 0)),
    ]
    colors = ["#2E7D32", "#757575", "#C62828"]

    fig, ax = plt.subplots(figsize=(4.8, 3.6), dpi=150)
    if sum(values) == 0:
        ax.text(0.5, 0.5, "No Data", ha="center", va="center", fontsize=14)
        ax.axis("off")
    else:
        bars = ax.bar(labels, values, color=colors, width=0.55)
        ax.set_title("Distribusi Sentimen", fontsize=12, fontweight="bold", color="#1F4E78")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(values) * 0.02,
                str(val),
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
            )
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _add_slide_title(slide: Any, title: str, subtitle: str = "") -> None:
    tb = slide.shapes.add_textbox(Inches(0.6), Inches(0.3), Inches(12.1), Inches(0.8))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(24)
    p.font.bold = True
    p.font.color.rgb = NAVY
    if subtitle:
        p2 = tf.add_paragraph()
        p2.text = subtitle
        p2.font.size = Pt(12)
        p2.font.color.rgb = MUTED_TEXT


def _style_table_cell(cell: Any, text: str, bold: bool = False, bg: RGBColor | None = None, fg: RGBColor = DARK_TEXT, size: int = 10) -> None:
    cell.text = ""
    p = cell.text_frame.paragraphs[0]
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = fg
    if bg is not None:
        cell.fill.solid()
        cell.fill.fore_color.rgb = bg


def generate_pptx_report(
    report_payload: dict[str, Any],
    narrative: Pass3NarrativeOutput | dict[str, Any] | None,
    config: ClientConfig,
    output_path: Path | str,
    template_path: Path | str | None = None,
) -> Path:
    """Generate Output 2: `.pptx` visual report strictly from `report_payload.json` + `narrative.json`."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    tpl = Path(template_path) if template_path else (
        Path(config.output_templates.pptx_template_path)
        if config.output_templates.pptx_template_path
        else None
    )
    if tpl is not None and tpl.exists():
        prs = Presentation(str(tpl))
    else:
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

    blank_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[-1]

    meta = report_payload["meta"]
    sent = report_payload["sentiment_summary"]
    media = report_payload["media_breakdown"]
    pivots = report_payload["pivots"]
    nar_dict = (
        narrative.model_dump()
        if isinstance(narrative, Pass3NarrativeOutput)
        else (narrative or {})
    )

    # --- Slide 1: Cover ---
    s1 = prs.slides.add_slide(blank_layout)
    tb = s1.shapes.add_textbox(Inches(0.8), Inches(2.0), Inches(11.7), Inches(3.2))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = f"Media Monitoring Report — {meta.get('client_name', config.client_name)}"
    p.font.size = Pt(34)
    p.font.bold = True
    p.font.color.rgb = NAVY

    p2 = tf.add_paragraph()
    period = meta.get("period_label") or "-"
    cutoff = meta.get("cutoff_wib") or "-"
    p2.text = f"Periode: {period}  |  Cutoff: {cutoff}"
    p2.font.size = Pt(18)
    p2.font.color.rgb = DARK_TEXT

    p3 = tf.add_paragraph()
    p3.text = (
        f"Total Raw: {meta['total_raw']}  •  "
        f"Clean: {meta['total_clean']}  •  "
        f"Takeout: {meta['total_takeout']}"
    )
    p3.font.size = Pt(14)
    p3.font.color.rgb = MUTED_TEXT

    # --- Slide 2: Executive Summary & Sentiment Chart ---
    s2 = prs.slides.add_slide(blank_layout)
    _add_slide_title(
        s2,
        "Executive Summary & Distribusi Sentimen",
        f"Positif: {sent['positive']} | Netral: {sent['neutral']} | Negatif: {sent['negative']}",
    )
    chart_png = _render_sentiment_chart_png(sent)
    s2.shapes.add_picture(chart_png, Inches(0.6), Inches(1.4), width=Inches(5.4))

    tb2 = s2.shapes.add_textbox(Inches(6.3), Inches(1.4), Inches(6.4), Inches(5.3))
    tf2 = tb2.text_frame
    tf2.word_wrap = True
    p_hdr = tf2.paragraphs[0]
    p_hdr.text = "Ringkasan Utama"
    p_hdr.font.size = Pt(16)
    p_hdr.font.bold = True
    p_hdr.font.color.rgb = NAVY

    bullets = nar_dict.get("executive_summary") or [
        f"Total {meta['total_clean']} berita bersih terpantau pada periode {period}."
    ]
    for b in bullets[:5]:
        bp = tf2.add_paragraph()
        bp.text = f"• {b}"
        bp.font.size = Pt(12)
        bp.font.color.rgb = DARK_TEXT

    pr_analysis = nar_dict.get("pr_analysis", "")
    if pr_analysis:
        pa_hdr = tf2.add_paragraph()
        pa_hdr.text = "\nAnalisis PR"
        pa_hdr.font.size = Pt(14)
        pa_hdr.font.bold = True
        pa_hdr.font.color.rgb = NAVY

        pa = tf2.add_paragraph()
        pa.text = pr_analysis
        pa.font.size = Pt(11)
        pa.font.color.rgb = DARK_TEXT

    # --- Slide 3: Media Breakdown & Top Newstrends ---
    s3 = prs.slides.add_slide(blank_layout)
    tier_str = ", ".join(f"{k}: {v}" for k, v in media["by_custom_tier"].items())
    type_str = ", ".join(f"{k}: {v}" for k, v in media["by_type"].items())
    _add_slide_title(s3, "Top Newstrends & Distribusi Media", f"Tipe: {type_str}  |  Tier: {tier_str}")

    top_nt = pivots["top_newstrends"][:8]
    rows_n = max(2, len(top_nt) + 1)
    table_shape = s3.shapes.add_table(rows_n, 5, Inches(0.6), Inches(1.4), Inches(12.1), Inches(5.2))
    tbl = table_shape.table
    headers = ["Newstrends", "Nama Isu", "Pos", "Neu", "Neg"]
    widths = [Inches(5.6), Inches(3.2), Inches(1.1), Inches(1.1), Inches(1.1)]
    for c_i, (h, w) in enumerate(zip(headers, widths)):
        tbl.columns[c_i].width = w
        _style_table_cell(tbl.cell(0, c_i), h, bold=True, bg=NAVY, fg=WHITE, size=11)

    for r_i, item in enumerate(top_nt, start=1):
        bg = LIGHT_BG if r_i % 2 == 0 else None
        _style_table_cell(tbl.cell(r_i, 0), item["newstrend"], bg=bg, size=10)
        _style_table_cell(tbl.cell(r_i, 1), item["nama_isu"], bg=bg, size=10)
        _style_table_cell(tbl.cell(r_i, 2), str(item["pos"]), bg=bg, size=10)
        _style_table_cell(tbl.cell(r_i, 3), str(item["neu"]), bg=bg, size=10)
        _style_table_cell(tbl.cell(r_i, 4), str(item["neg"]), bg=bg, size=10)

    # --- Slide 4: Spokesperson Berita Rilis ---
    s4 = prs.slides.add_slide(blank_layout)
    _add_slide_title(s4, "Rekapitulasi Spokesperson — Berita Rilis", "Termasuk entri '0' jika tanpa narasumber")
    spk_rows = pivots["spokesperson_rilis"][:10]
    tbl_s4 = s4.shapes.add_table(max(2, len(spk_rows) + 1), 3, Inches(0.6), Inches(1.4), Inches(12.1), Inches(5.0)).table
    for c_i, (h, w) in enumerate(zip(["Spokesperson", "Jabatan", "Jumlah Rilis"], [Inches(4.5), Inches(5.6), Inches(2.0)])):
        tbl_s4.columns[c_i].width = w
        _style_table_cell(tbl_s4.cell(0, c_i), h, bold=True, bg=NAVY, fg=WHITE, size=11)
    for r_i, item in enumerate(spk_rows, start=1):
        bg = LIGHT_BG if r_i % 2 == 0 else None
        _style_table_cell(tbl_s4.cell(r_i, 0), str(item["spokesperson"]), bg=bg, size=10)
        _style_table_cell(tbl_s4.cell(r_i, 1), str(item["jabatan"]), bg=bg, size=10)
        _style_table_cell(tbl_s4.cell(r_i, 2), str(item["count"]), bg=bg, size=10)

    # --- Slide 5+: Competitor Highlights (100% Anti-Mismatch from report_payload.json) ---
    comp_highlights = report_payload.get("competitor_highlights") or {}
    for entity, buckets in comp_highlights.items():
        combined = [
            ("Positive", item) for item in buckets.get("positive", [])
        ] + [
            ("Negative", item) for item in buckets.get("negative", [])
        ]
        if not combined:
            continue

        sc = prs.slides.add_slide(blank_layout)
        _add_slide_title(sc, f"Highlight Berita Kompetitor — {entity}", "Pasangan Media & URL terverifikasi langsung dari DataFrame asli")
        tbl_c = sc.shapes.add_table(len(combined) + 1, 5, Inches(0.5), Inches(1.4), Inches(12.3), Inches(5.2)).table
        c_headers = ["Sentimen", "Media Name", "Tier", "Judul Berita", "URL"]
        c_widths = [Inches(1.2), Inches(2.1), Inches(1.0), Inches(4.8), Inches(3.2)]
        for c_i, (h, w) in enumerate(zip(c_headers, c_widths)):
            tbl_c.columns[c_i].width = w
            _style_table_cell(tbl_c.cell(0, c_i), h, bold=True, bg=NAVY, fg=WHITE, size=10)

        for r_i, (sent_label, item) in enumerate(combined, start=1):
            bg = LIGHT_BG if r_i % 2 == 0 else None
            _style_table_cell(tbl_c.cell(r_i, 0), sent_label, bg=bg, size=9)
            _style_table_cell(tbl_c.cell(r_i, 1), item["media_name"], bg=bg, size=9)
            _style_table_cell(tbl_c.cell(r_i, 2), item["tier"], bg=bg, size=9)
            _style_table_cell(tbl_c.cell(r_i, 3), item["title"], bg=bg, size=9)

            url_cell = tbl_c.cell(r_i, 4)
            url_cell.text = ""
            p_url = url_cell.text_frame.paragraphs[0]
            run_u = p_url.add_run()
            run_u.text = item["url"]
            run_u.font.size = Pt(8)
            run_u.font.color.rgb = RGBColor(0x05, 0x63, 0xC1)
            if item["url"].startswith(("http://", "https://")):
                run_u.hyperlink.address = item["url"]
            if bg is not None:
                url_cell.fill.solid()
                url_cell.fill.fore_color.rgb = bg

    prs.save(str(out))
    return out


def export_pptx_to_pdf(pptx_path: Path | str, output_dir: Path | str | None = None) -> Path | None:
    """Optionally convert `.pptx` to `.pdf` using LibreOffice (`soffice`) if installed locally."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    src = Path(pptx_path)
    out_dir = Path(output_dir) if output_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(src)],
        check=True,
        capture_output=True,
    )
    pdf_path = out_dir / f"{src.stem}.pdf"
    return pdf_path if pdf_path.exists() else None
