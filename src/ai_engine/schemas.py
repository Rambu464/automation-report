"""Pydantic schemas for the 3-Pass AI Engine, including dynamic Ad-Hoc columns (SAD.md Bab 4 & 5)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, create_model

from src.config_loader import AdhocColumnConfig


class Pass1RowOutput(BaseModel):
    """Canonical per-row result produced by Pass 1 Micro-Batch Classification."""

    idx: int
    status_takeout: Literal["Keep", "Takeout"] = "Keep"
    alasan_spam: str = ""
    sentiment: Literal["positive", "neutral", "negative"] = "neutral"
    draft_newstrend: str = ""
    nama_isu: str = ""
    content_type: Literal["Rilis", "Organik"] = "Organik"
    spokesperson: str = ""
    jabatan: str = ""
    adhoc: dict[str, str] = Field(default_factory=dict)


def build_pass1_batch_schema(adhoc_columns: list[AdhocColumnConfig]) -> type[BaseModel]:
    """Dynamically build a strict Pydantic batch response model that includes `config.yaml` ad-hoc columns."""
    if adhoc_columns:
        adhoc_fields: dict[str, tuple[type, object]] = {
            col.name: (str, Field(default="", description=col.description))
            for col in adhoc_columns
        }
        adhoc_model = create_model("DynamicAdhocFields", **adhoc_fields)  # type: ignore[call-overload]
        item_model = create_model(
            "DynamicPass1RowOutput",
            __base__=Pass1RowOutput,
            adhoc=(adhoc_model, Field(default_factory=adhoc_model)),
        )
    else:
        item_model = Pass1RowOutput

    return create_model(
        "Pass1BatchResponse",
        items=(list[item_model], Field(default_factory=list)),  # type: ignore[valid-type]
    )


class Pass2NormalizationItem(BaseModel):
    """Single canonical mapping returned by Pass 2 Global Newstrend Normalization."""

    raw_nama_isu: str
    canonical_nama_isu: str
    canonical_newstrend: str
    final_sentiment: Literal["positive", "neutral", "negative"]
    is_negative_issue: bool = False


class Pass2NormalizationResponse(BaseModel):
    mappings: list[Pass2NormalizationItem] = Field(default_factory=list)


class Pass3NarrativeOutput(BaseModel):
    """Structured narrative returned by Pass 3 (`narrative.json`) for PPTX & Wording."""

    executive_summary: list[str] = Field(default_factory=list)
    pr_analysis: str = ""
    public_conversation_direction: str = ""
    recommendations: list[str] = Field(default_factory=list)
