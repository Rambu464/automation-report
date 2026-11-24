"""3-Pass Cloud AI Engine orchestrator (Sprint 2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from src.ai_engine.client import LLMClientProtocol, MultiModelLLMClient, TokenUsageStats
from src.ai_engine.pass1_classifier import Pass1Stats, ProgressCallback, run_pass1_classification
from src.ai_engine.pass2_normalizer import run_pass2_normalization
from src.ai_engine.pass3_narrative import run_pass3_narrative
from src.ai_engine.schemas import Pass3NarrativeOutput
from src.ai_engine.spokesperson import apply_three_tier_spokesperson_fallback
from src.config_loader import ClientConfig
from src.db.database import StateDatabase
from src.db.repositories import AIBatchCacheRepo, NegativeIssueMemoryRepo
from src.settings import AppSettings, get_settings


@dataclass
class AIEngineResult:
    news_df: pd.DataFrame
    pass1_stats: Pass1Stats = field(default_factory=Pass1Stats)
    usage: TokenUsageStats = field(default_factory=TokenUsageStats)


class AIEnginePipeline:
    """Orchestrates Pass 1 (Micro-Batch) -> 3-Tier Spokesperson -> Pass 2 (Global Normalization) -> Pass 3 (Narrative)."""

    def __init__(
        self,
        db: StateDatabase | None = None,
        llm_client: LLMClientProtocol | None = None,
        settings: AppSettings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.db = db if db is not None else StateDatabase(self.settings.sqlite_db_path)
        self.llm_client: LLMClientProtocol = (
            llm_client if llm_client is not None else MultiModelLLMClient(self.settings)
        )
        self.cache_repo = AIBatchCacheRepo(self.db)
        self.neg_memory_repo = NegativeIssueMemoryRepo(self.db)

    async def classify_and_normalize(
        self,
        news_df: pd.DataFrame,
        config: ClientConfig,
        progress_callback: ProgressCallback | None = None,
    ) -> AIEngineResult:
        """Run Pass 1, 3-Tier Spokesperson Fallback, and Pass 2 Global Normalization."""
        # Pass 1: Micro-Batch Classification & Extraction
        df, pass1_stats = await run_pass1_classification(
            news_df=news_df,
            config=config,
            llm_client=self.llm_client,
            cache_repo=self.cache_repo,
            batch_size=self.settings.ai_batch_size,
            max_concurrency=self.settings.ai_max_concurrency,
            progress_callback=progress_callback,
        )

        # 3-Tier Spokesperson & Jabatan Resolver (Statements -> Content -> "0")
        df = apply_three_tier_spokesperson_fallback(
            df,
            missing_value=config.media_and_spokesperson.spokesperson_missing_value,
        )

        # Pass 2: Global Newstrend Normalization & Negative Issue Memory
        if progress_callback is not None:
            progress_callback(1, 1, "Pass 2: Standardisasi Newstrend & Memori Isu Negatif...")
        df = await run_pass2_normalization(
            news_df=df,
            config=config,
            llm_client=self.llm_client,
            neg_memory_repo=self.neg_memory_repo,
        )

        return AIEngineResult(
            news_df=df,
            pass1_stats=pass1_stats,
            usage=self.llm_client.usage,
        )

    async def generate_narrative(
        self,
        report_payload: dict[str, Any],
        config: ClientConfig,
        prefer_pro: bool = False,
    ) -> Pass3NarrativeOutput:
        """Run Pass 3 Narrative & Wording Engine from verified `report_payload.json`."""
        return await run_pass3_narrative(
            report_payload=report_payload,
            config=config,
            llm_client=self.llm_client,
            prefer_pro=prefer_pro,
        )
