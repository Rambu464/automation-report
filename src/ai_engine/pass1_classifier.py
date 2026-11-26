"""Pass 1 — Async Micro-Batch Classification & Extraction (SAD.md Bab 5).

Key cost & integrity guardrails:
1. Only processes `Status_Takeout == 'Keep'` AND `Is_Cluster_Rep == True`.
2. Checks local SQLite `ai_batch_cache` keyed by `sha256(ID + config_version_hash)`.
3. Uses temporary Integer ID Mapping (`idx: 1..N`) — NEVER sends `Page/URL` or hash `ID` to LLM.
4. Sends compact Smart Snippet (`Content_Snippet`) and dynamic `adhoc_columns` schema.
5. Fans out cluster representative classifications to all rows sharing `Cluster_ID`.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from src.ai_engine.client import LLMClientProtocol
from src.ai_engine.schemas import build_pass1_batch_schema
from src.config_loader import ClientConfig
from src.db.repositories import AIBatchCacheRepo
from src.settings import AppSettings

ProgressCallback = Callable[[int, int, str], None]

PASS1_PROMPT_VERSION = "p1_v1"


@dataclass
class Pass1Stats:
    total_reps: int = 0
    cache_hits: int = 0
    human_qc_hits: int = 0
    llm_classified: int = 0
    batches_executed: int = 0


def resolve_active_model_name(
    llm_client: Any = None,
    settings: AppSettings | None = None,
    model_name: str | None = None,
) -> str:
    """Resolve the active LLM model identifier for Pass 1 cache keying."""
    if model_name and model_name.strip():
        return model_name.strip()

    if llm_client is not None:
        explicit = getattr(llm_client, "active_model_name", None)
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()
        providers = getattr(llm_client, "providers", None)
        if providers:
            first = providers[0]
            p_name = getattr(first, "name", "")
            p_model = getattr(first, "model", "")
            if p_name and p_model:
                return f"{p_name}:{p_model}"
            if p_model:
                return str(p_model)

    if settings is not None:
        if settings.deepseek_api_key.strip():
            return f"deepseek:{settings.deepseek_primary_model}"
        if settings.openrouter_api_key.strip():
            return f"openrouter:{settings.openrouter_model}"
        if settings.groq_api_key.strip():
            return f"groq:{settings.groq_model}"
        if settings.gemini_api_key.strip():
            return f"gemini:{settings.gemini_model}"
        return f"deepseek:{settings.deepseek_primary_model}"

    return "default"


def _make_cache_key(
    report_id: str,
    config_hash: str,
    prompt_version: str = PASS1_PROMPT_VERSION,
    model_name: str = "default",
) -> str:
    raw = f"{report_id}:{config_hash}:{prompt_version}:{model_name}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _make_human_qc_cache_key(report_id: str, client_id: str) -> str:
    """Stable per-client human QC override key that survives prompt/model/config changes."""
    raw = f"human_qc:{client_id.strip().lower()}:{report_id.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


make_cache_key = _make_cache_key
make_human_qc_cache_key = _make_human_qc_cache_key


def _dedupe_lines(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        clean = item.strip()
        if clean and clean not in seen:
            seen.add(clean)
            out.append(clean)
    return out


def _build_sentiment_brief_block(config: ClientConfig) -> str:
    sb = config.sentiment_brief
    if not sb.has_content():
        return ""
    parts: list[str] = ["\n=== PANDUAN SENTIMEN KHUSUS KLIEN (POV WAJIB DIPATUHI) ==="]
    if sb.deskripsi:
        parts.append(f"Deskripsi: {sb.deskripsi}")
    if sb.analyst_verdict:
        parts.append(f"\nPrinsip Utama (Analyst Verdict):\n{sb.analyst_verdict.strip()}")
    if sb.negative_guidelines:
        parts.append(
            "\nAturan NEGATIVE:\n"
            + "\n".join(f"- {g}" for g in _dedupe_lines(sb.negative_guidelines))
        )
    if sb.neutral_guidelines:
        parts.append(
            "\nAturan NEUTRAL:\n"
            + "\n".join(f"- {g}" for g in _dedupe_lines(sb.neutral_guidelines))
        )
    if sb.positive_guidelines:
        parts.append(
            "\nAturan POSITIVE:\n"
            + "\n".join(f"- {g}" for g in _dedupe_lines(sb.positive_guidelines))
        )
    if sb.output_rules:
        parts.append(
            "\nAturan Output Koreksi:\n"
            + "\n".join(f"- {r}" for r in _dedupe_lines(sb.output_rules))
        )
    parts.append("=== AKHIR PANDUAN SENTIMEN KHUSUS KLIEN ===\n")
    return "\n".join(parts)


def _build_pass1_system_prompt(config: ClientConfig) -> str:
    exclusions = "\n".join(
        f"- {rule}" for rule in config.takeout_rules.client_specific_exclusions
    ) or "- Berita murni iklan/promosi tanpa substansi berita"

    adhoc_lines = "\n".join(
        f'- "{col.name}": {col.description}' for col in config.adhoc_columns
    )
    adhoc_block = (
        f"\nKolom Ad-Hoc wajib diisi di dalam objek `adhoc`:\n{adhoc_lines}\n"
        if adhoc_lines
        else "\nTidak ada kolom ad-hoc tambahan (`adhoc`: {}).\n"
    )

    competitor_note = ""
    if config.competitors.enabled and config.competitors.entities:
        ents = ", ".join(config.competitors.entities)
        competitor_note = (
            f"\nKompetitor yang dipantau: {ents}. "
            "Jika berita fokus membahas kompetitor tersebut, evaluasi sentimen berdasarkan POV kompetitor tersebut.\n"
        )

    brief_block = _build_sentiment_brief_block(config)
    hints = config.newstrend_rules.sentiment_wording_hints
    return (
        f"Anda adalah Analis Media Monitoring Senior untuk klien {config.client_name} (`{config.client_id}`).\n"
        "Tugas Anda menganalisis micro-batch berita (JSON array) dan mengembalikan JSON objek dengan key `items`.\n"
        f"{brief_block}\n"
        "Aturan Klasifikasi:\n"
        f"1. `status_takeout`: 'Keep' atau 'Takeout'. Tandai 'Takeout' + isi `alasan_spam` jika termasuk:\n{exclusions}\n"
        "2. `sentiment`: 'positive', 'neutral', atau 'negative' sesuai POV klien (patuhi Panduan Sentimen Khusus Klien di atas jika tersedia). "
        "Isi `perlu_koreksi` (true jika berbeda dari `orig_sentiment`) dan `confidence` (0.0-1.0).\n"
        f"3. `draft_newstrend`: Kalimat aktif maks. {config.newstrend_rules.max_words} kata sesuai topik utama pada Title & Content "
        "(prioritaskan konsistensi Newstrend untuk topik utama sama; pisahkan jika topik utama berbeda walau entitas/tema sama).\n"
        f"   - Negative: {hints.negative}\n"
        f"   - Neutral: {hints.neutral}\n"
        f"   - Positive: {hints.positive}\n"
        "4. `nama_isu`: Label isu ringkas (2-5 kata) untuk pengelompokan Pivot.\n"
        "5. `content_type`: 'Rilis' (berita press release/seragam korporasi) atau 'Organik' (liputan mandiri jurnalis).\n"
        "6. `spokesperson` & `jabatan`: Ekstrak dari snippet HANYA jika `has_stmt == false`. "
        "Jika `has_stmt == true` atau tidak ada narasumber di snippet, isi string kosong \"\".\n"
        f"{competitor_note}"
        f"{adhoc_block}\n"
        "Kembalikan HANYA JSON valid dengan struktur: {\"items\": [{...}]} untuk setiap `idx` yang diberikan."
    )


async def run_pass1_classification(
    news_df: pd.DataFrame,
    config: ClientConfig,
    llm_client: LLMClientProtocol,
    cache_repo: AIBatchCacheRepo,
    batch_size: int = 30,
    max_concurrency: int = 5,
    progress_callback: ProgressCallback | None = None,
    prompt_version: str = PASS1_PROMPT_VERSION,
    model_name: str | None = None,
) -> tuple[pd.DataFrame, Pass1Stats]:
    """Execute Pass 1 async micro-batch classification with SQLite caching and cluster fan-out."""
    df = news_df.copy()
    stats = Pass1Stats()

    # Ensure output columns exist
    for col in ("Nama_Isu", "Content_Type", "AI_Spokesperson", "AI_Jabatan"):
        if col not in df.columns:
            df[col] = ""
    for adhoc_col in config.adhoc_columns:
        if adhoc_col.name not in df.columns:
            df[adhoc_col.name] = ""

    # Identify rows needing classification (Keep & cluster representative)
    if "Is_Cluster_Rep" not in df.columns:
        df["Is_Cluster_Rep"] = df["Status_Takeout"] == "Keep"

    rep_mask = (df["Status_Takeout"] == "Keep") & (df["Is_Cluster_Rep"].astype(bool))
    rep_indices = df.index[rep_mask].tolist()
    stats.total_reps = len(rep_indices)

    if not rep_indices:
        return df, stats

    cfg_hash = config.config_version_hash()
    effective_model = resolve_active_model_name(llm_client=llm_client, model_name=model_name)
    row_cache_keys = {
        idx: _make_cache_key(
            str(df.at[idx, "ID"]),
            cfg_hash,
            prompt_version=prompt_version,
            model_name=effective_model,
        )
        for idx in rep_indices
    }
    row_human_keys = {
        idx: _make_human_qc_cache_key(str(df.at[idx, "ID"]), config.client_id)
        for idx in rep_indices
    }

    # 1. Check SQLite ai_batch_cache (Priority 1: human_qc override, Priority 2: versioned AI key)
    all_lookup_keys = list(set(row_cache_keys.values()) | set(row_human_keys.values()))
    cached_by_key = cache_repo.get_many(all_lookup_keys)
    results_by_df_idx: dict[int, dict[str, Any]] = {}
    uncached_indices: list[int] = []

    for df_idx in rep_indices:
        hkey = row_human_keys[df_idx]
        ckey = row_cache_keys[df_idx]
        human_entry = cached_by_key.get(hkey)
        if human_entry and human_entry.get("source") == "human_qc":
            results_by_df_idx[df_idx] = human_entry
            stats.cache_hits += 1
            stats.human_qc_hits += 1
        elif ckey in cached_by_key:
            results_by_df_idx[df_idx] = cached_by_key[ckey]
            stats.cache_hits += 1
            if cached_by_key[ckey].get("source") == "human_qc":
                stats.human_qc_hits += 1
        else:
            uncached_indices.append(df_idx)

    # 2. Micro-batch LLM calls for uncached representatives
    if uncached_indices:
        system_prompt = _build_pass1_system_prompt(config)
        batch_schema = build_pass1_batch_schema(config.adhoc_columns)
        batches = [
            uncached_indices[i : i + batch_size]
            for i in range(0, len(uncached_indices), batch_size)
        ]
        total_batches = len(batches)
        stats.batches_executed = total_batches
        semaphore = asyncio.Semaphore(max(1, max_concurrency))
        completed_count = 0

        async def _process_batch(batch_num: int, batch_df_indices: list[int]) -> None:
            nonlocal completed_count
            # Build compact payload using Integer ID Mapping (1..N), NO URL and NO hash ID
            idx_map: dict[int, int] = {}
            payload_rows: list[dict[str, Any]] = []
            for local_idx, df_idx in enumerate(batch_df_indices, start=1):
                idx_map[local_idx] = df_idx
                snippet = (
                    str(df.at[df_idx, "Content_Snippet"])
                    if "Content_Snippet" in df.columns
                    else str(df.at[df_idx, "Content"])[:750]
                )
                payload_rows.append(
                    {
                        "idx": local_idx,
                        "title": str(df.at[df_idx, "Title"]),
                        "snippet": snippet,
                        "media_type": str(df.at[df_idx, "Media Type"]),
                        "orig_sentiment": str(df.at[df_idx, "Sentiment"])
                        if "Sentiment" in df.columns
                        else "",
                        "has_stmt": bool(df.at[df_idx, "Has_Statement"])
                        if "Has_Statement" in df.columns
                        else False,
                    }
                )

            user_prompt = json.dumps(payload_rows, ensure_ascii=False)
            async with semaphore:
                resp = await llm_client.complete_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_model=batch_schema,
                )

            to_cache: dict[str, dict[str, Any]] = {}
            for item in getattr(resp, "items", []):
                item_dict = item.model_dump()
                item_dict["source"] = "ai"
                item_dict["prompt_version"] = prompt_version
                item_dict["model_name"] = effective_model
                local_idx = int(item_dict["idx"])
                if local_idx not in idx_map:
                    continue
                target_df_idx = idx_map[local_idx]
                results_by_df_idx[target_df_idx] = item_dict
                to_cache[row_cache_keys[target_df_idx]] = item_dict
                stats.llm_classified += 1

            if to_cache:
                cache_repo.set_many(to_cache)

            completed_count += 1
            if progress_callback is not None:
                progress_callback(
                    completed_count,
                    total_batches,
                    f"Pass 1: Batch {completed_count}/{total_batches} selesai",
                )

        await asyncio.gather(
            *[_process_batch(i + 1, b) for i, b in enumerate(batches)]
        )

    # 3. Map cluster_id -> representative classification for fan-out
    cluster_results: dict[str, dict[str, Any]] = {}
    for df_idx, res in results_by_df_idx.items():
        cid = str(df.at[df_idx, "Cluster_ID"]) if "Cluster_ID" in df.columns else ""
        if cid:
            cluster_results[cid] = res

    # 4. Apply results to representatives AND cluster members (100% locked to original ID/URL)
    adhoc_names = [c.name for c in config.adhoc_columns]
    for df_idx in df.index:
        if df.at[df_idx, "Status_Takeout"] != "Keep":
            continue

        res = results_by_df_idx.get(df_idx)
        if res is None and "Cluster_ID" in df.columns:
            cid = str(df.at[df_idx, "Cluster_ID"])
            if cid:
                res = cluster_results.get(cid)
        if res is None:
            continue

        is_human_qc = res.get("source") == "human_qc"
        if res.get("status_takeout") == "Takeout":
            df.at[df_idx, "Status_Takeout"] = "Takeout"
            df.at[df_idx, "Alasan_Spam"] = res.get("alasan_spam") or "Takeout - Klasifikasi AI"
        elif is_human_qc and res.get("status_takeout") == "Keep":
            df.at[df_idx, "Status_Takeout"] = "Keep"
            df.at[df_idx, "Alasan_Spam"] = str(res.get("alasan_spam") or "")

        if res.get("sentiment"):
            df.at[df_idx, "Sentiment"] = res["sentiment"]
        newstrend_val = res.get("draft_newstrend") or res.get("newstrends")
        if newstrend_val:
            df.at[df_idx, "Newstrends"] = newstrend_val
        if res.get("nama_isu"):
            df.at[df_idx, "Nama_Isu"] = res["nama_isu"]
        if res.get("content_type"):
            df.at[df_idx, "Content_Type"] = res["content_type"]

        # Store AI-extracted spokesperson separately so Tier-1 Statements are never clobbered
        spk_val = str(res.get("spokesperson") or "").strip()
        jab_val = str(res.get("jabatan") or "").strip()
        df.at[df_idx, "AI_Spokesperson"] = spk_val
        df.at[df_idx, "AI_Jabatan"] = jab_val
        if is_human_qc:
            if spk_val:
                df.at[df_idx, "Spokesperson"] = spk_val
            if jab_val:
                df.at[df_idx, "Jabatan"] = jab_val

        adhoc_vals = res.get("adhoc") or {}
        for col_name in adhoc_names:
            df.at[df_idx, col_name] = str(adhoc_vals.get(col_name, "") or "").strip()

    return df, stats
