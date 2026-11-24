"""Smart PPTX Template Element Auto-Recognition & In-Place Updater (0 AI tokens for charts/KPIs).

Automatically inspects existing slides in a client's `.pptx` template (even without `{{placeholders}}`),
identifies mass-media charts & KPI/narrative text blocks by semantic signature, and updates them
in-place using `python-pptx` `chart.replace_data()` while preserving original colors, fonts, and layout.

Social media slides (Instagram, TikTok, Facebook, etc.) are automatically detected and left untouched
when `social_media_optional` is `None`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE

from src.ai_engine.schemas import Pass3NarrativeOutput

SOCIAL_KEYWORDS = frozenset(
    {"instagram", "facebook", "twitter", "threads", "tiktok", "youtube", "media sosial", "sosmed", "engagement"}
)
SENTIMENT_LABELS = frozenset({"positive", "neutral", "negative", "positif", "netral", "negatif"})
MEDIA_TYPE_LABELS = frozenset({"online", "print", "electronic", "cetak", "elektronik"})
DOMAIN_RE = re.compile(r"\.[a-z]{2,4}$", re.IGNORECASE)
ARTICLES_RE = re.compile(r"(\d[\d.,]*)\s*(articles?|artikel|berita)", re.IGNORECASE)


@dataclass
class TemplateUpdateAction:
    slide_number: int
    shape_name: str
    element_kind: str  # "chart" | "text"
    detected_role: str
    status: str  # "updated" | "skipped_social" | "unmatched"
    detail: str = ""


@dataclass
class TemplateUpdateReport:
    updated_charts: int = 0
    updated_texts: int = 0
    skipped_social_elements: int = 0
    actions: list[TemplateUpdateAction] = field(default_factory=list)


def _slide_text_blob(slide: Any) -> str:
    parts = []
    for sh in slide.shapes:
        if sh.has_text_frame:
            parts.append(sh.text_frame.text or "")
    return " ".join(parts).lower()


def _is_social_slide(slide: Any) -> bool:
    blob = _slide_text_blob(slide)
    if "media sosial" in blob or "share by platform" in blob or "platform timeline" in blob:
        return True
    # Also check if slide charts contain social platform categories/series
    for sh in slide.shapes:
        if sh.has_chart:
            cats = _get_chart_categories(sh.chart)
            sers = _get_chart_series_names(sh.chart)
            tokens = {t.lower() for t in cats + sers}
            if len(tokens & SOCIAL_KEYWORDS) >= 2:
                return True
    return False


def _get_chart_categories(chart: Any) -> list[str]:
    try:
        if chart.plots and chart.plots[0].categories:
            return [str(c.label).strip() for c in chart.plots[0].categories]
    except Exception:
        pass
    return []


def _get_chart_series_names(chart: Any) -> list[str]:
    try:
        return [str(s.name or "").strip() for s in chart.series]
    except Exception:
        return []


def _classify_chart_role(chart: Any, is_social_slide: bool) -> str:
    """Deterministically recognize a native PPTX chart's semantic role from its categories & series."""
    cats = _get_chart_categories(chart)
    sers = _get_chart_series_names(chart)
    cats_lower = {c.lower() for c in cats if c}
    sers_lower = {s.lower() for s in sers if s}

    # 1. Social media chart guard (skip unless social_media_optional exists)
    if len((cats_lower | sers_lower) & SOCIAL_KEYWORDS) >= 2 or is_social_slide:
        return "social_media"

    # 2. Media Type chart (series or categories contain online/print/electronic)
    if len(sers_lower & MEDIA_TYPE_LABELS) >= 2:
        return "media_type_series"
    if len(cats_lower & MEDIA_TYPE_LABELS) >= 2:
        return "media_type_categories"

    # 3. Media Tier chart (Tier 1 / Tier 2 / Tier 3)
    if any("tier 1" in c or "tier 2" in c or "tier 3" in c for c in cats_lower):
        return "media_tier"

    # 4. Line chart: Timeline (total or by sentiment)
    is_line = chart.chart_type in {
        XL_CHART_TYPE.LINE,
        XL_CHART_TYPE.LINE_MARKERS,
        XL_CHART_TYPE.LINE_STACKED,
        XL_CHART_TYPE.AREA,
    }
    if is_line:
        if len(sers_lower & SENTIMENT_LABELS) >= 2:
            return "timeline_sentiment"
        return "timeline_total"

    # 5. Sentiment bar/column/pie chart
    if len(cats_lower & SENTIMENT_LABELS) >= 2:
        return "sentiment_summary"

    # 6. Top Media chart (categories look like domains e.g. kompas.com, detik.com, selalu.id)
    if cats and sum(1 for c in cats if DOMAIN_RE.search(c)) >= max(2, len(cats) // 2):
        return "top_media"

    return "unknown"


def _replace_text_preserving_style(shape: Any, new_text: str) -> None:
    """Replace a shape's text while keeping the first paragraph/run's font styling intact."""
    tf = shape.text_frame
    if not tf.paragraphs:
        shape.text = new_text
        return

    lines = new_text.splitlines() or [""]
    first_p = tf.paragraphs[0]
    font_name = None
    font_size = None
    font_bold = None
    font_color = None
    if first_p.runs:
        r0 = first_p.runs[0]
        font_name = r0.font.name
        font_size = r0.font.size
        font_bold = r0.font.bold
        try:
            if r0.font.color and r0.font.color.type is not None:
                font_color = r0.font.color.rgb
        except Exception:
            font_color = None

    # Clear extra paragraphs cleanly
    for p in tf.paragraphs[1:]:
        p.text = ""
    first_p.text = ""
    run = first_p.add_run()
    run.text = lines[0]
    if font_name:
        run.font.name = font_name
    if font_size:
        run.font.size = font_size
    if font_bold is not None:
        run.font.bold = font_bold
    if font_color is not None:
        run.font.color.rgb = font_color

    for extra_line in lines[1:]:
        p_new = tf.add_paragraph()
        r_new = p_new.add_run()
        r_new.text = extra_line
        if font_name:
            r_new.font.name = font_name
        if font_size:
            r_new.font.size = font_size
        if font_color is not None:
            r_new.font.color.rgb = font_color


def _detach_external_workbook_if_needed(chart: Any) -> None:
    """Convert Google-Slides external chart links into embedded workbooks so `replace_data()` works."""
    try:
        chart_part = chart.part
        chart_space = chart._chartSpace
        ext_data = chart_space.externalData
        if ext_data is None:
            return
        rId = ext_data.rId
        if rId and rId in chart_part.rels and chart_part.rels[rId].is_external:
            chart_part.drop_rel(rId)
            chart_space.remove(ext_data)
    except Exception:
        pass


def _safe_replace_chart_data(chart: Any, chart_data: CategoryChartData) -> None:
    _detach_external_workbook_if_needed(chart)
    chart.replace_data(chart_data)


def _update_chart_by_role(
    chart: Any,
    role: str,
    report_payload: dict[str, Any],
) -> tuple[bool, str]:
    """Update a recognized native PPTX chart in-place using `CategoryChartData`."""
    media = report_payload.get("media_breakdown") or {}
    sent = report_payload.get("sentiment_summary") or {}
    pivots = report_payload.get("pivots") or {}

    if role == "media_type_series":
        by_type = media.get("by_type") or {}
        cd = CategoryChartData()
        cd.categories = ["Media Type"]
        for s_name in _get_chart_series_names(chart) or ["online", "print", "electronic"]:
            cd.add_series(s_name, (int(by_type.get(s_name.lower(), 0)),))
        _safe_replace_chart_data(chart, cd)
        return True, f"by_type={by_type}"

    if role == "media_type_categories":
        by_type = media.get("by_type") or {}
        cats = _get_chart_categories(chart) or list(by_type.keys())
        cd = CategoryChartData()
        cd.categories = cats
        cd.add_series("Jumlah", tuple(int(by_type.get(c.lower(), 0)) for c in cats))
        _safe_replace_chart_data(chart, cd)
        return True, f"by_type={by_type}"

    if role == "media_tier":
        by_tier = media.get("by_custom_tier") or {}
        orig_cats = _get_chart_categories(chart) or ["Tier 3", "Tier 2", "Tier 1"]
        cd = CategoryChartData()
        cd.categories = orig_cats
        cd.add_series("Jumlah", tuple(int(by_tier.get(c, 0)) for c in orig_cats))
        _safe_replace_chart_data(chart, cd)
        return True, f"by_custom_tier={by_tier}"

    if role == "sentiment_summary":
        orig_cats = _get_chart_categories(chart) or ["negative", "neutral", "positive"]
        cd = CategoryChartData()
        cd.categories = orig_cats
        vals = tuple(int(sent.get(c.lower(), 0)) for c in orig_cats)
        # Keep single clean series (some Google Slides exports create empty extra series)
        cd.add_series("Jumlah", vals)
        _safe_replace_chart_data(chart, cd)
        return True, f"sentiment={sent}"

    if role == "top_media":
        top_media = (pivots.get("top_media") or [])[: max(6, len(_get_chart_categories(chart)) or 6)]
        if not top_media:
            return False, "top_media kosong"
        cd = CategoryChartData()
        cd.categories = [item["media_name"] for item in top_media]
        cd.add_series("Jumlah", tuple(int(item["count"]) for item in top_media))
        _safe_replace_chart_data(chart, cd)
        return True, f"top {len(top_media)} media"

    if role == "timeline_total":
        timeline = pivots.get("timeline_daily") or []
        if not timeline:
            return False, "timeline_daily kosong"
        cd = CategoryChartData()
        cd.categories = [str(item["date"]) for item in timeline]
        ser_name = (_get_chart_series_names(chart) or ["Total"])[0] or "Total"
        cd.add_series(ser_name, tuple(int(item["total"]) for item in timeline))
        _safe_replace_chart_data(chart, cd)
        return True, f"{len(timeline)} hari"

    if role == "timeline_sentiment":
        timeline = pivots.get("timeline_daily") or []
        if not timeline:
            return False, "timeline_daily kosong"
        cd = CategoryChartData()
        cd.categories = [str(item["date"]) for item in timeline]
        series_map = {
            "negative": ("neg",),
            "neutral": ("neu",),
            "positive": ("pos",),
        }
        orig_sers = _get_chart_series_names(chart) or ["negative", "neutral", "positive"]
        for s_name in orig_sers:
            key = series_map.get(s_name.lower(), ("total",))[0]
            cd.add_series(s_name, tuple(int(item.get(key, 0)) for item in timeline))
        _safe_replace_chart_data(chart, cd)
        return True, f"{len(timeline)} hari x {len(orig_sers)} sentimen"

    return False, "tidak dikenali"


def update_pptx_template_in_place(
    prs: Presentation,
    report_payload: dict[str, Any],
    narrative: Pass3NarrativeOutput | dict[str, Any] | None = None,
) -> TemplateUpdateReport:
    """Scan all slides in an existing client `.pptx` template and update recognized charts & KPI texts in-place."""
    report = TemplateUpdateReport()
    meta = report_payload.get("meta") or {}
    sent = report_payload.get("sentiment_summary") or {}
    media = report_payload.get("media_breakdown") or {}
    nar = (
        narrative.model_dump()
        if isinstance(narrative, Pass3NarrativeOutput)
        else (narrative or {})
    )

    period_label = meta.get("period_label") or "-"
    cutoff_wib = meta.get("cutoff_wib") or ""
    total_clean = int(meta.get("total_clean", 0))

    for slide_idx, slide in enumerate(prs.slides, start=1):
        is_social = _is_social_slide(slide)

        for shape in slide.shapes:
            # 1. Native PowerPoint Charts
            if shape.has_chart:
                role = _classify_chart_role(shape.chart, is_social_slide=is_social)
                if role == "social_media":
                    report.skipped_social_elements += 1
                    report.actions.append(
                        TemplateUpdateAction(
                            slide_number=slide_idx,
                            shape_name=shape.name,
                            element_kind="chart",
                            detected_role=role,
                            status="skipped_social",
                            detail="Dilewati (slide/chart Media Sosial)",
                        )
                    )
                    continue

                if role == "unknown":
                    report.actions.append(
                        TemplateUpdateAction(
                            slide_number=slide_idx,
                            shape_name=shape.name,
                            element_kind="chart",
                            detected_role=role,
                            status="unmatched",
                        )
                    )
                    continue

                ok, detail = _update_chart_by_role(shape.chart, role, report_payload)
                if ok:
                    report.updated_charts += 1
                    report.actions.append(
                        TemplateUpdateAction(
                            slide_number=slide_idx,
                            shape_name=shape.name,
                            element_kind="chart",
                            detected_role=role,
                            status="updated",
                            detail=detail,
                        )
                    )
                continue

            # 2. Smart KPI / Period / Narrative Text Blocks (skip social slides)
            if shape.has_text_frame and not is_social:
                raw_txt = (shape.text_frame.text or "").strip()
                if not raw_txt:
                    continue

                # Cover Period line
                if "periode report" in raw_txt.lower():
                    cutoff_suffix = f" ({cutoff_wib})" if cutoff_wib and cutoff_wib != "-" else ""
                    new_txt = f"Periode Report:\n{period_label}{cutoff_suffix}"
                    _replace_text_preserving_style(shape, new_txt)
                    report.updated_texts += 1
                    report.actions.append(
                        TemplateUpdateAction(
                            slide_number=slide_idx,
                            shape_name=shape.name,
                            element_kind="text",
                            detected_role="cover_period",
                            status="updated",
                            detail=new_txt.replace("\n", " "),
                        )
                    )
                    continue

                # Share of Voice article count (e.g. "Share Of Voice\n105 articles")
                if "share of voice" in raw_txt.lower() and ARTICLES_RE.search(raw_txt):
                    new_txt = ARTICLES_RE.sub(f"{total_clean} articles", raw_txt)
                    _replace_text_preserving_style(shape, new_txt)
                    report.updated_texts += 1
                    report.actions.append(
                        TemplateUpdateAction(
                            slide_number=slide_idx,
                            shape_name=shape.name,
                            element_kind="text",
                            detected_role="sov_articles_kpi",
                            status="updated",
                            detail=f"{total_clean} articles",
                        )
                    )
                    continue

                # Executive Summary Volume & Distribusi Media Massa paragraph
                if raw_txt.lower().startswith("terdeteksi ") and "artikel media massa" in raw_txt.lower():
                    by_tier = media.get("by_custom_tier") or {}
                    top_tier = max(by_tier.items(), key=lambda x: x[1])[0] if by_tier else "Tier 3"
                    top_tier_cnt = by_tier.get(top_tier, 0)
                    pct = (top_tier_cnt / total_clean * 100) if total_clean > 0 else 0.0
                    new_txt = (
                        f"Terdeteksi {total_clean} artikel media massa selama periode {period_label}. "
                        f"Pemberitaan didominasi oleh {top_tier} sebanyak {top_tier_cnt} artikel ({pct:.1f}%), "
                        f"dengan komposisi sentimen Positif {sent.get('positive', 0)}, "
                        f"Netral {sent.get('neutral', 0)}, dan Negatif {sent.get('negative', 0)}."
                    )
                    _replace_text_preserving_style(shape, new_txt)
                    report.updated_texts += 1
                    report.actions.append(
                        TemplateUpdateAction(
                            slide_number=slide_idx,
                            shape_name=shape.name,
                            element_kind="text",
                            detected_role="exec_summary_media_volume",
                            status="updated",
                            detail=f"{total_clean} artikel",
                        )
                    )
                    continue

                # Timeline Media Massa narrative paragraph
                if raw_txt.lower().startswith("selama periode ") and "artikel di media massa" in raw_txt.lower():
                    pr_text = (nar.get("pr_analysis") or "").strip()
                    new_txt = pr_text or (
                        f"Selama periode {period_label}, terdapat {total_clean} artikel di media massa "
                        f"dengan sentimen Positif {sent.get('positive', 0)}, Netral {sent.get('neutral', 0)}, "
                        f"dan Negatif {sent.get('negative', 0)}."
                    )
                    _replace_text_preserving_style(shape, new_txt)
                    report.updated_texts += 1
                    report.actions.append(
                        TemplateUpdateAction(
                            slide_number=slide_idx,
                            shape_name=shape.name,
                            element_kind="text",
                            detected_role="media_timeline_narrative",
                            status="updated",
                            detail="updated narrative",
                        )
                    )
                    continue

    return report
