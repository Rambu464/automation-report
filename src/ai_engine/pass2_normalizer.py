"""Pass 2 — Global Newstrend Normalization & Negative Issue Memory (SAD.md Bab 5 & FR-03.2)."""

from __future__ import annotations

import hashlib
import json
from datetime import date

import pandas as pd

from src.ai_engine.client import LLMClientProtocol
from src.ai_engine.schemas import Pass2NormalizationResponse
from src.config_loader import ClientConfig
from src.db.repositories import NegativeIssueMemoryRepo, NegativeIssueRecord


def _issue_hash(client_id: str, canonical_nama_isu: str) -> str:
    norm = f"{client_id.strip().lower()}::{canonical_nama_isu.strip().lower()}"
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:24]


def _build_newstrend_brief_block(config: ClientConfig) -> str:
    nb = config.newstrend_brief
    lines = [
        "\n=== PANDUAN PEMBUATAN & CLUSTERING NEWSTREND (ALL CLIENT) ===",
        nb.general_guideline.strip(),
        "",
        nb.additional_information.strip(),
    ]
    if nb.examples:
        lines.append("\nContoh Pola Clustering:")
        for ex in nb.examples:
            lines.append(f"- Konteks: {ex.context}\n  Pola: {ex.pattern}")
    lines.append("=== AKHIR PANDUAN NEWSTREND ===\n")
    return "\n".join(lines)


def _build_pass2_system_prompt(config: ClientConfig) -> str:
    hints = config.newstrend_rules.sentiment_wording_hints
    positive_exception = ""
    if config.sentiment_brief.has_content():
        positive_exception = (
            "   (PENGECUALIAN BRIEF KLIEN: Jangan ubah berita yang sudah dinilai `positive` oleh Pass 1 "
            "karena fokusnya klarifikasi resmi, bantahan, dukungan proses hukum, atau mitigasi klien.)\n"
        )
    nt_brief = _build_newstrend_brief_block(config)
    return (
        f"Anda adalah Editor Senior Media Monitoring untuk klien {config.client_name}.\n"
        "Tugas Anda (Pass 2) adalah menstandardisasi daftar `nama_isu` dan `draft_newstrend` hasil Pass 1:\n"
        f"{nt_brief}"
        "1. Gabungkan variasi redaksi yang membahas topik utama sama ke satu `canonical_nama_isu` & `canonical_newstrend` yang seragam (jangan gabungkan jika topik utamanya berbeda).\n"
        f"2. Pastikan `canonical_newstrend` berbentuk kalimat aktif maksimal {config.newstrend_rules.max_words} kata:\n"
        f"   - Negative: {hints.negative}\n"
        f"   - Neutral: {hints.neutral}\n"
        f"   - Positive: {hints.positive}\n"
        "3. KONSISTENSI ISU NEGATIF: Jika suatu isu cocok dengan daftar `historical_negative_issues`, "
        "WAJIB kunci `final_sentiment = 'negative'`, gunakan `canonical_newstrend` yang konsisten, "
        "dan set `is_negative_issue = true`.\n"
        f"{positive_exception}"
        "4. Untuk isu negatif baru, set `is_negative_issue = true`.\n"
        "Kembalikan HANYA JSON valid: {\"mappings\": [{raw_nama_isu, canonical_nama_isu, canonical_newstrend, final_sentiment, is_negative_issue}]}."
    )


async def run_pass2_normalization(
    news_df: pd.DataFrame,
    config: ClientConfig,
    llm_client: LLMClientProtocol,
    neg_memory_repo: NegativeIssueMemoryRepo,
) -> pd.DataFrame:
    """Run 1 lightweight global API call to unify Newstrends & enforce negative issue consistency."""
    df = news_df.copy()
    keep_mask = df["Status_Takeout"] == "Keep"
    keep_df = df.loc[keep_mask]
    if keep_df.empty:
        return df

    # Collect unique (Nama_Isu, draft Newstrends, Sentiment)
    seen_issues: dict[str, dict[str, str]] = {}
    for _, row in keep_df.iterrows():
        raw_isu = str(row.get("Nama_Isu", "")).strip()
        if not raw_isu or raw_isu in seen_issues:
            continue
        seen_issues[raw_isu] = {
            "raw_nama_isu": raw_isu,
            "draft_newstrend": str(row.get("Newstrends", "")).strip(),
            "draft_sentiment": str(row.get("Sentiment", "neutral")).strip().lower() or "neutral",
        }

    if not seen_issues:
        return df

    historical_negatives = neg_memory_repo.list_by_client(config.client_id)
    user_payload = {
        "draft_issues": list(seen_issues.values()),
        "historical_negative_issues": [
            {
                "nama_isu": rec.nama_isu,
                "canonical_newstrend": rec.canonical_newstrend,
                "locked_sentiment": rec.locked_sentiment,
            }
            for rec in historical_negatives
        ],
    }

    resp = await llm_client.complete_json(
        system_prompt=_build_pass2_system_prompt(config),
        user_prompt=json.dumps(user_payload, ensure_ascii=False),
        response_model=Pass2NormalizationResponse,
    )

    mapping_by_raw = {m.raw_nama_isu.strip(): m for m in resp.mappings}
    today_str = date.today().isoformat()
    new_negative_records: list[NegativeIssueRecord] = []

    for df_idx in df.index[keep_mask]:
        raw_isu = str(df.at[df_idx, "Nama_Isu"]).strip()
        m = mapping_by_raw.get(raw_isu)
        if m is None:
            continue

        df.at[df_idx, "Nama_Isu"] = m.canonical_nama_isu.strip()
        df.at[df_idx, "Newstrends"] = m.canonical_newstrend.strip()
        if config.newstrend_rules.enforce_negative_consistency and m.is_negative_issue:
            df.at[df_idx, "Sentiment"] = "negative"
        else:
            df.at[df_idx, "Sentiment"] = m.final_sentiment

    for m in resp.mappings:
        if m.is_negative_issue or m.final_sentiment == "negative":
            new_negative_records.append(
                NegativeIssueRecord(
                    issue_hash=_issue_hash(config.client_id, m.canonical_nama_isu),
                    client_id=config.client_id,
                    nama_isu=m.canonical_nama_isu.strip(),
                    canonical_newstrend=m.canonical_newstrend.strip(),
                    locked_sentiment="negative",
                    last_seen=today_str,
                )
            )

    if new_negative_records:
        neg_memory_repo.upsert_many(new_negative_records)

    return df
