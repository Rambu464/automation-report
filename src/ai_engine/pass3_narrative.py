"""Pass 3 — Narrative & Wording Engine driven strictly by verified `report_payload.json` (SAD.md Bab 5)."""

from __future__ import annotations

import json
from typing import Any

from src.ai_engine.client import LLMClientProtocol
from src.ai_engine.schemas import Pass3NarrativeOutput
from src.config_loader import ClientConfig


def _build_pass3_system_prompt(config: ClientConfig) -> str:
    return (
        f"Anda adalah Konsultan PR & Media Intelligence Senior untuk klien {config.client_name}.\n"
        "Anda diberikan `report_payload.json` berisi angka statistik & daftar isu yang SUDAH TERVERIFIKASI.\n"
        "ATURAN KETAT:\n"
        "1. DILARANG mengarang angka baru, mengubah statistik, atau menulis ulang URL berita.\n"
        "2. Buat narasi profesional Bahasa Indonesia untuk:\n"
        "   - `executive_summary`: 3-5 poin ringkas untuk slide Executive Summary PPTX.\n"
        "   - `pr_analysis`: 1 paragraf analisis PR & sentimen berbasis data payload.\n"
        "   - `public_conversation_direction`: 1 paragraf ringkas 'Arah Percakapan Publik' untuk teks Wording email.\n"
        "   - `recommendations`: 2-3 rekomendasi tindak lanjut PR yang actionable.\n"
        "Kembalikan HANYA JSON valid sesuai skema."
    )


async def run_pass3_narrative(
    report_payload: dict[str, Any],
    config: ClientConfig,
    llm_client: LLMClientProtocol,
    prefer_pro: bool = False,
) -> Pass3NarrativeOutput:
    """Generate verified `narrative.json` from `report_payload.json` in 1 API call."""
    # Strip any raw URLs from competitor_highlights before sending to LLM so it never echoes/mutates URLs
    sanitized_payload = json.loads(json.dumps(report_payload, ensure_ascii=False))
    comp = sanitized_payload.get("competitor_highlights")
    if isinstance(comp, dict):
        for entity_data in comp.values():
            if isinstance(entity_data, dict):
                for bucket in ("positive", "negative"):
                    for item in entity_data.get(bucket, []):
                        if isinstance(item, dict):
                            item.pop("url", None)

    return await llm_client.complete_json(
        system_prompt=_build_pass3_system_prompt(config),
        user_prompt=json.dumps(sanitized_payload, ensure_ascii=False),
        response_model=Pass3NarrativeOutput,
        prefer_pro=prefer_pro,
    )
