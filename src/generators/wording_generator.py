"""Output 3 — Email Wording Generator 100% synced with `report_payload.json` + `narrative.json` (FR-05.3, SAD.md Section 6C)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.ai_engine.schemas import Pass3NarrativeOutput
from src.config_loader import ClientConfig


def _pct(part: int, total: int) -> str:
    if total <= 0:
        return "0%"
    return f"{(part / total) * 100:.1f}%"


def render_wording_text(
    report_payload: dict[str, Any],
    narrative: Pass3NarrativeOutput | dict[str, Any] | None,
    config: ClientConfig,
) -> str:
    """Deterministically render structured email wording directly from verified `report_payload.json`."""
    meta = report_payload["meta"]
    sent = report_payload["sentiment_summary"]
    media = report_payload["media_breakdown"]
    pivots = report_payload["pivots"]
    sosmed = report_payload.get("social_media_optional")

    nar_dict = (
        narrative.model_dump()
        if isinstance(narrative, Pass3NarrativeOutput)
        else (narrative or {})
    )

    client_name = meta.get("client_name") or config.client_name
    period = meta.get("period_label") or "-"
    cutoff = meta.get("cutoff_wib") or "-"
    total_clean = int(meta.get("total_clean", 0))

    pos = int(sent.get("positive", 0))
    neu = int(sent.get("neutral", 0))
    neg = int(sent.get("negative", 0))

    lines: list[str] = [
        f"Selamat Pagi/Siang Bapak/Ibu Tim {client_name},",
        "",
        f"Berikut kami sampaikan ringkasan Media Monitoring periode {period} (Cutoff: {cutoff}):",
        "",
        "1. Perkembangan Sentimen & Media",
        f"- Total Pemberitaan Bersih: {total_clean} berita (dari {meta.get('total_raw', total_clean)} raw data; {meta.get('total_takeout', 0)} takeout).",
        f"- Komposisi Sentimen: Positif {pos} ({_pct(pos, total_clean)}), Netral {neu} ({_pct(neu, total_clean)}), Negatif {neg} ({_pct(neg, total_clean)}).",
    ]

    by_type = media.get("by_type") or {}
    if by_type:
        type_parts = ", ".join(f"{k.capitalize()}: {v}" for k, v in by_type.items())
        lines.append(f"- Distribusi Tipe Media: {type_parts}.")

    by_tier = media.get("by_custom_tier") or {}
    if by_tier:
        tier_label = (
            config.media_and_spokesperson.custom_tier.excel_column_name
            if config.media_and_spokesperson.custom_tier.enabled
            else "Media Tier"
        )
        tier_parts = ", ".join(f"{k}: {v}" for k, v in by_tier.items())
        lines.append(f"- Distribusi {tier_label}: {tier_parts}.")

    # Conditional Sosmed block ONLY when social_media_optional is explicitly populated
    if config.output_templates.wording_include_sosmed_block and isinstance(sosmed, dict):
        lines.append(
            f"- Media Sosial: {sosmed.get('total_posts', 0)} unggahan "
            f"(Total Engagement: {sosmed.get('total_engagement', 0)})."
        )

    lines.append("")
    lines.append("2. Isu Utama (Top Newstrends)")
    top_nt = pivots.get("top_newstrends") or []
    if top_nt:
        for idx, item in enumerate(top_nt[:5], start=1):
            lines.append(
                f"  {idx}. {item['newstrend']} — {item['total']} berita "
                f"(Pos: {item['pos']}, Neu: {item['neu']}, Neg: {item['neg']})"
            )
    else:
        lines.append("  - Belum ada isu menonjol pada periode ini.")

    direction = (nar_dict.get("public_conversation_direction") or "").strip()
    if direction:
        lines.append("")
        lines.append("3. Arah Percakapan Publik")
        lines.append(direction)

    recs = nar_dict.get("recommendations") or []
    if recs:
        lines.append("")
        lines.append("4. Rekomendasi Tindak Lanjut")
        for r in recs[:3]:
            lines.append(f"- {r}")

    lines.extend(
        [
            "",
            "Terlampir file Excel Raw Data Cleaned & Pivot serta Report Visual untuk tinjauan lebih lanjut.",
            "Terima kasih.",
        ]
    )
    return "\n".join(lines)


def save_wording_text(text: str, output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
