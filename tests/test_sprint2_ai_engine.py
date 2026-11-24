"""Unit tests for Sprint 2: 3-Pass Cloud AI Engine, Dynamic Ad-Hoc Schema, Spokesperson 3-Tier, & Fallback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

import pandas as pd
import pytest
from pydantic import BaseModel

from src.ai_engine.client import MultiModelLLMClient, ProviderSpec, TokenUsageStats
from src.ai_engine.pipeline import AIEnginePipeline
from src.ai_engine.schemas import (
    Pass2NormalizationResponse,
    Pass3NarrativeOutput,
    build_pass1_batch_schema,
)
from src.config_loader import AdhocColumnConfig, load_client_config
from src.db.database import StateDatabase
from src.db.repositories import NegativeIssueMemoryRepo, NegativeIssueRecord

T = TypeVar("T", bound=BaseModel)


class MockLLMClient:
    """Deterministic async LLM mock that records all prompts and returns schema-validated outputs."""

    def __init__(self) -> None:
        self.usage = TokenUsageStats()
        self.calls: list[dict[str, str]] = []
        self.pass1_call_count = 0

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        prefer_pro: bool = False,
    ) -> T:
        self.calls.append(
            {
                "model_name": response_model.__name__,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
            }
        )
        self.usage.add(
            TokenUsageStats(
                prompt_tokens=500,
                cached_tokens=200,
                completion_tokens=150,
                api_calls=1,
                provider_used="mock:deepseek-chat",
            )
        )

        if response_model.__name__ == "Pass1BatchResponse":
            self.pass1_call_count += 1
            rows = json.loads(user_prompt)
            items = []
            for r in rows:
                title = r["title"].lower()
                if "kur" in title:
                    items.append(
                        {
                            "idx": r["idx"],
                            "status_takeout": "Keep",
                            "alasan_spam": "",
                            "sentiment": "positive",
                            "draft_newstrend": "BRI Salurkan KUR Dorong UMKM Naik Kelas",
                            "nama_isu": "Penyaluran KUR UMKM",
                            "content_type": "Rilis",
                            "spokesperson": "Harusnya Tidak Menimpa Tier 1",
                            "jabatan": "Harusnya Tidak Menimpa",
                            "adhoc": {"Kluster": "UMKM & KUR", "Paid_Earned": "Earned"},
                        }
                    )
                elif "brimo" in title:
                    items.append(
                        {
                            "idx": r["idx"],
                            "status_takeout": "Keep",
                            "alasan_spam": "",
                            "sentiment": "positive",
                            "draft_newstrend": "BRI Tingkatkan Transaksi Digital Melalui BRImo",
                            "nama_isu": "Pertumbuhan BRImo",
                            "content_type": "Rilis",
                            "spokesperson": "Andrijanto",
                            "jabatan": "Direktur Jaringan dan Layanan BRI",
                            "adhoc": {
                                "Kluster": "Layanan Digital (BRImo)",
                                "Paid_Earned": "Earned",
                            },
                        }
                    )
                elif "fraud" in title:
                    items.append(
                        {
                            "idx": r["idx"],
                            "status_takeout": "Keep",
                            "alasan_spam": "",
                            "sentiment": "neutral",  # Pass 2 negative memory MUST lock this to negative!
                            "draft_newstrend": "Tanggapan BRI atas Dugaan Fraud Cabang X",
                            "nama_isu": "Dugaan Fraud Cabang X",
                            "content_type": "Organik",
                            "spokesperson": "",
                            "jabatan": "",
                            "adhoc": {"Kluster": "Hukum/Kriminal", "Paid_Earned": "Earned"},
                        }
                    )
                else:
                    items.append(
                        {
                            "idx": r["idx"],
                            "status_takeout": "Keep",
                            "alasan_spam": "",
                            "sentiment": "neutral",
                            "draft_newstrend": "BRI Gelar Program Pelatihan",
                            "nama_isu": "Pelatihan UMKM",
                            "content_type": "Rilis",
                            "spokesperson": "",
                            "jabatan": "",
                            "adhoc": {"Kluster": "CSR", "Paid_Earned": "Paid"},
                        }
                    )
            return response_model.model_validate({"items": items})

        if response_model is Pass2NormalizationResponse:
            payload = json.loads(user_prompt)
            mappings = []
            for item in payload["draft_issues"]:
                raw_isu = item["raw_nama_isu"]
                if "Fraud" in raw_isu:
                    mappings.append(
                        {
                            "raw_nama_isu": raw_isu,
                            "canonical_nama_isu": "Dugaan Fraud Cabang X",
                            "canonical_newstrend": "Kasus Dugaan Fraud Kredit di BRI Cabang X",
                            "final_sentiment": "negative",
                            "is_negative_issue": True,
                        }
                    )
                else:
                    mappings.append(
                        {
                            "raw_nama_isu": raw_isu,
                            "canonical_nama_isu": raw_isu,
                            "canonical_newstrend": item["draft_newstrend"],
                            "final_sentiment": item["draft_sentiment"],
                            "is_negative_issue": False,
                        }
                    )
            return response_model.model_validate({"mappings": mappings})

        if response_model is Pass3NarrativeOutput:
            return response_model.model_validate(
                {
                    "executive_summary": [
                        "Total 4 berita bersih terpantau dengan dominasi sentimen positif.",
                        "Isu utama didorong oleh penyaluran KUR UMKM dan pertumbuhan BRImo.",
                    ],
                    "pr_analysis": "Pemberitaan BRI didominasi narasi positif terkait kinerja UMKM.",
                    "public_conversation_direction": "Percakapan publik mengarah positif pada dukungan UMKM dan layanan digital BRImo.",
                    "recommendations": [
                        "Pertahankan publikasi capaian KUR melalui media Tier 1.",
                        "Siapkan Q&A respons cepat terkait isu hukum Cabang X.",
                    ],
                }
            )

        raise AssertionError(f"Unexpected response_model: {response_model}")


def test_dynamic_adhoc_schema_builder() -> None:
    cols = [
        AdhocColumnConfig(name="Kluster", description="Tema korporasi"),
        AdhocColumnConfig(name="Paid_Earned", description="Paid atau Earned"),
        AdhocColumnConfig(name="Sub_Program", description="Nama sub-program klien"),
    ]
    schema = build_pass1_batch_schema(cols)
    validated = schema.model_validate(
        {
            "items": [
                {
                    "idx": 1,
                    "status_takeout": "Keep",
                    "sentiment": "positive",
                    "draft_newstrend": "BRI Salurkan KUR",
                    "nama_isu": "KUR",
                    "content_type": "Rilis",
                    "adhoc": {
                        "Kluster": "UMKM",
                        "Paid_Earned": "Earned",
                        "Sub_Program": "KUR Mikro",
                    },
                }
            ]
        }
    )
    dumped = validated.model_dump()
    assert dumped["items"][0]["adhoc"]["Sub_Program"] == "KUR Mikro"


async def test_multi_model_fallback_chain() -> None:
    providers = [
        ProviderSpec(name="deepseek", kind="openai_compat", api_key="k1", model="deepseek-chat"),
        ProviderSpec(name="openrouter", kind="openai_compat", api_key="k2", model="qwen-72b"),
    ]
    client = MultiModelLLMClient(providers=providers, max_retries=0)
    attempted: list[str] = []

    async def fake_invoke(
        provider: ProviderSpec,
        system_prompt: str,
        user_prompt: str,
        prefer_pro: bool = False,
    ) -> tuple[str, TokenUsageStats]:
        attempted.append(provider.name)
        if provider.name == "deepseek":
            raise TimeoutError("429 Rate Limit")
        return (
            json.dumps(
                {
                    "executive_summary": ["OK from fallback"],
                    "pr_analysis": "Analisis OK",
                    "public_conversation_direction": "Arah OK",
                    "recommendations": ["Rek 1"],
                }
            ),
            TokenUsageStats(
                prompt_tokens=100,
                completion_tokens=50,
                api_calls=1,
                provider_used="openrouter:qwen-72b",
            ),
        )

    client._invoke_provider = fake_invoke  # type: ignore[method-assign]
    result = await client.complete_json("sys", "usr", Pass3NarrativeOutput)
    assert attempted == ["deepseek", "openrouter"]
    assert result.executive_summary == ["OK from fallback"]
    assert client.usage.provider_used == "openrouter:qwen-72b"


async def test_full_3pass_ai_engine_cache_cluster_spokesperson_and_negative_memory(
    tmp_path: Path,
) -> None:
    db = StateDatabase(tmp_path / "ai_state.db")
    cfg = load_client_config("bri", clients_dir=Path("clients"))

    # Pre-seed historical negative issue memory
    NegativeIssueMemoryRepo(db).upsert_many(
        [
            NegativeIssueRecord(
                issue_hash="hist-fraud-1",
                client_id="bri",
                nama_isu="Dugaan Fraud Cabang X",
                canonical_newstrend="Kasus Dugaan Fraud Kredit di BRI Cabang X",
            )
        ]
    )

    df_in = pd.DataFrame(
        [
            # Row 1: Rep for CL-0001, has Tier-1 Statement (must NOT be overwritten by AI!)
            {
                "ID": "HASH-ID-64-CHAR-0001",
                "Title": "BRI Salurkan KUR Rp 120 Triliun",
                "Content_Snippet": "BRI terus menyalurkan KUR bagi UMKM.",
                "Media Name": "Kompas.com",
                "Page/URL": "https://kompas.com/secret-url-1",
                "Media Type": "online",
                "Status_Takeout": "Keep",
                "Alasan_Spam": "",
                "Cluster_ID": "CL-0001",
                "Is_Cluster_Rep": True,
                "Has_Statement": True,
                "Spokesperson": "Sunarso",
                "Jabatan": "Direktur Utama BRI",
                "Sentiment": "neutral",
                "Newstrends": "",
            },
            # Row 2: Syndicated member of CL-0001 (must NOT be sent to LLM; inherits classification!)
            {
                "ID": "HASH-ID-64-CHAR-0002",
                "Title": "BRI Perkuat Penyaluran KUR",
                "Content_Snippet": "BRI terus menyalurkan KUR bagi UMKM.",
                "Media Name": "BeritaSatu.com",
                "Page/URL": "https://beritasatu.com/secret-url-2",
                "Media Type": "online",
                "Status_Takeout": "Keep",
                "Alasan_Spam": "",
                "Cluster_ID": "CL-0001",
                "Is_Cluster_Rep": False,
                "Has_Statement": False,
                "Spokesperson": "",
                "Jabatan": "",
                "Sentiment": "neutral",
                "Newstrends": "",
            },
            # Row 3: No Statement -> Tier-2 AI extraction from Content
            {
                "ID": "HASH-ID-64-CHAR-0003",
                "Title": "Transaksi BRImo Melonjak",
                "Content_Snippet": "Direktur Jaringan dan Layanan BRI Andrijanto menyebut transaksi BRImo melonjak.",
                "Media Name": "Detik.com",
                "Page/URL": "https://detik.com/secret-url-3",
                "Media Type": "online",
                "Status_Takeout": "Keep",
                "Alasan_Spam": "",
                "Cluster_ID": "CL-0002",
                "Is_Cluster_Rep": True,
                "Has_Statement": False,
                "Spokesperson": "",
                "Jabatan": "",
                "Sentiment": "neutral",
                "Newstrends": "",
            },
            # Row 4: Recurring negative issue + no speaker -> Tier-3 "0" & locked negative!
            {
                "ID": "HASH-ID-64-CHAR-0004",
                "Title": "Update Dugaan Fraud Cabang X",
                "Content_Snippet": "Polisi mendalami dugaan fraud pada cabang daerah.",
                "Media Name": "Tempo.co",
                "Page/URL": "https://tempo.co/secret-url-4",
                "Media Type": "online",
                "Status_Takeout": "Keep",
                "Alasan_Spam": "",
                "Cluster_ID": "CL-0003",
                "Is_Cluster_Rep": True,
                "Has_Statement": False,
                "Spokesperson": "",
                "Jabatan": "",
                "Sentiment": "neutral",
                "Newstrends": "",
            },
        ]
    )

    mock_llm = MockLLMClient()
    progress_events: list[str] = []
    pipeline = AIEnginePipeline(db=db, llm_client=mock_llm)

    res1 = await pipeline.classify_and_normalize(
        news_df=df_in,
        config=cfg,
        progress_callback=lambda c, t, m: progress_events.append(m),
    )
    out = res1.news_df.set_index("ID")

    # 1. Anti-mismatch guardrail: URL & Hash ID NEVER sent to LLM
    pass1_prompt = mock_llm.calls[0]["user_prompt"]
    assert "secret-url" not in pass1_prompt
    assert "HASH-ID-64-CHAR" not in pass1_prompt
    assert res1.pass1_stats.total_reps == 3  # Row 2 skipped via Cluster_ID
    assert res1.pass1_stats.llm_classified == 3
    assert len(progress_events) >= 2

    # 2. Cluster Fan-Out verified
    assert out.loc["HASH-ID-64-CHAR-0002", "Nama_Isu"] == "Penyaluran KUR UMKM"
    assert out.loc["HASH-ID-64-CHAR-0002", "Kluster"] == "UMKM & KUR"
    assert out.loc["HASH-ID-64-CHAR-0002", "Paid_Earned"] == "Earned"

    # 3. 3-Tier Spokesperson verified
    assert out.loc["HASH-ID-64-CHAR-0001", "Spokesperson"] == "Sunarso"  # Tier 1 preserved!
    assert out.loc["HASH-ID-64-CHAR-0001", "Jabatan"] == "Direktur Utama BRI"
    assert out.loc["HASH-ID-64-CHAR-0003", "Spokesperson"] == "Andrijanto"  # Tier 2 extracted!
    assert out.loc["HASH-ID-64-CHAR-0004", "Spokesperson"] == "0"  # Tier 3 default "0"!
    assert out.loc["HASH-ID-64-CHAR-0004", "Jabatan"] == "0"

    # 4. Pass 2 Negative Memory Consistency verified
    assert out.loc["HASH-ID-64-CHAR-0004", "Sentiment"] == "negative"
    assert out.loc["HASH-ID-64-CHAR-0004", "Newstrends"].startswith("Kasus ")

    # 5. Re-run -> 100% SQLite ai_batch_cache hit (0 new Pass 1 LLM calls!)
    pass1_calls_before = mock_llm.pass1_call_count
    res2 = await pipeline.classify_and_normalize(news_df=df_in, config=cfg)
    assert res2.pass1_stats.cache_hits == 3
    assert res2.pass1_stats.llm_classified == 0
    assert mock_llm.pass1_call_count == pass1_calls_before

    # 6. Pass 3 Narrative Engine strips URLs and produces structured narrative.json
    sample_payload = {
        "meta": {"client_id": "bri", "total_clean": 4},
        "sentiment_summary": {"positive": 3, "neutral": 0, "negative": 1},
        "competitor_highlights": {
            "Bank Mandiri": {
                "positive": [{"title": "Mandiri Laba", "url": "https://secret-comp-url.com"}]
            }
        },
    }
    narrative = await pipeline.generate_narrative(sample_payload, config=cfg)
    assert len(narrative.executive_summary) >= 2
    assert "secret-comp-url.com" not in mock_llm.calls[-1]["user_prompt"]
