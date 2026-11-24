"""Client configuration schema and YAML loader (`clients/<client_id>/config.yaml`)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from src.settings import get_settings


class TakeoutRulesConfig(BaseModel):
    auto_takeout_newswire: bool = True
    exclude_pure_ads: bool = True
    content_noise_patterns: list[str] = Field(default_factory=list)
    regex_spam_patterns: list[str] = Field(default_factory=list)
    client_specific_exclusions: list[str] = Field(default_factory=list)
    sync_sensitive_negative_to_monthly: bool = True


class SentimentWordingHintsConfig(BaseModel):
    negative: str = "Biasanya mengandung kata seperti 'Kasus ...'"
    neutral: str = "Biasanya mengandung kata seperti 'Tanggapan ...'"
    positive: str = "Kalimat aktif langsung yang merepresentasikan aksi/kinerja positif"


class NewstrendRulesConfig(BaseModel):
    evaluate_from_content: bool = True
    sentence_style: str = "active_sentence"
    max_words: int = Field(default=12, ge=3, le=30)
    enforce_negative_consistency: bool = True
    sentiment_wording_hints: SentimentWordingHintsConfig = Field(
        default_factory=SentimentWordingHintsConfig
    )


class CustomTierConfig(BaseModel):
    enabled: bool = False
    client_key: str = ""
    excel_column_name: str = "TIER KLIEN"
    fallback_to_bino_tier: bool = True


class MediaAndSpokespersonConfig(BaseModel):
    classify_content_type: list[str] = Field(default_factory=lambda: ["Rilis", "Organik"])
    classify_media_detail: list[str] = Field(
        default_factory=lambda: ["Organik", "Newswire", "Media Bazar"]
    )
    custom_tier: CustomTierConfig = Field(default_factory=CustomTierConfig)
    spokesperson_fallback_to_content: bool = True
    spokesperson_missing_value: str = "0"


class AdhocColumnConfig(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)


class CompetitorsConfig(BaseModel):
    enabled: bool = False
    entities: list[str] = Field(default_factory=list)
    evaluate_using_competitor_pov: bool = True
    daily_highlight_count_per_sentiment: int = Field(default=3, ge=1, le=10)
    prioritize_by_media_tier: list[str] = Field(
        default_factory=lambda: ["Tier 1", "Tier 2", "Tier 3"]
    )


class OutputTemplatesConfig(BaseModel):
    pptx_template_path: str | None = None
    excel_template_path: str | None = None
    wording_include_sosmed_block: bool = False


class ClientConfig(BaseModel):
    """Full client configuration parsed from `clients/<client_id>/config.yaml`."""

    client_id: str = Field(..., min_length=1)
    client_name: str = Field(..., min_length=1)
    focus_type: Literal["brand_only", "brand_and_competitor", "crisis"] = "brand_and_competitor"

    takeout_rules: TakeoutRulesConfig = Field(default_factory=TakeoutRulesConfig)
    newstrend_rules: NewstrendRulesConfig = Field(default_factory=NewstrendRulesConfig)
    media_and_spokesperson: MediaAndSpokespersonConfig = Field(
        default_factory=MediaAndSpokespersonConfig
    )
    adhoc_columns: list[AdhocColumnConfig] = Field(default_factory=list)
    competitors: CompetitorsConfig = Field(default_factory=CompetitorsConfig)
    output_templates: OutputTemplatesConfig = Field(default_factory=OutputTemplatesConfig)

    def config_version_hash(self) -> str:
        """Deterministic short hash of AI-relevant config fields for `ai_batch_cache` keys."""
        payload = self.model_dump(
            include={
                "client_id",
                "takeout_rules",
                "newstrend_rules",
                "media_and_spokesperson",
                "adhoc_columns",
                "competitors",
            }
        )
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def load_client_config(client_id: str, clients_dir: Path | None = None) -> ClientConfig:
    """Load and validate a client's `config.yaml`."""
    base_dir = clients_dir if clients_dir is not None else get_settings().clients_dir
    config_path = Path(base_dir) / client_id / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Client config tidak ditemukan: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    return ClientConfig.model_validate(raw)


def save_client_config(config: ClientConfig, clients_dir: Path | None = None) -> Path:
    """Persist a validated ClientConfig back to `clients/<client_id>/config.yaml`."""
    base_dir = clients_dir if clients_dir is not None else get_settings().clients_dir
    config_path = Path(base_dir) / config.client_id / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            config.model_dump(mode="json"),
            f,
            sort_keys=False,
            allow_unicode=True,
        )
    return config_path


def list_clients(clients_dir: Path | None = None) -> list[str]:
    """Return sorted list of client IDs that have a `config.yaml`."""
    base_dir = Path(clients_dir if clients_dir is not None else get_settings().clients_dir)
    if not base_dir.exists():
        return []
    return sorted(
        p.name for p in base_dir.iterdir() if p.is_dir() and (p / "config.yaml").exists()
    )
