"""Multi-model async Cloud AI client with retry, exponential backoff, and fallback chain (SAD.md Bab 5).

Fallback order:
1. Primary: DeepSeek (`deepseek-chat` / `deepseek-reasoner`)
2. Secondary: Qwen via OpenRouter
3. Fast Fallback: Llama 3.3 70B via Groq
4. Optional Backup: Google Gemini (`gemini-2.5-flash`)
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from src.settings import AppSettings, get_settings

T = TypeVar("T", bound=BaseModel)


@dataclass
class TokenUsageStats:
    prompt_tokens: int = 0
    cached_tokens: int = 0
    completion_tokens: int = 0
    api_calls: int = 0
    provider_used: str = ""

    def add(self, other: "TokenUsageStats") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.cached_tokens += other.cached_tokens
        self.completion_tokens += other.completion_tokens
        self.api_calls += other.api_calls
        if other.provider_used:
            self.provider_used = other.provider_used

    def estimate_cost_usd(self, off_peak: bool = True) -> float:
        """Estimate DeepSeek-Flash USD cost based on SRS.md Section 2E rates."""
        hit_rate = 0.003 if off_peak else 0.006
        miss_rate = 0.15 if off_peak else 0.30
        out_rate = 0.60 if off_peak else 1.20
        miss_tokens = max(0, self.prompt_tokens - self.cached_tokens)
        return (
            (self.cached_tokens / 1_000_000) * hit_rate
            + (miss_tokens / 1_000_000) * miss_rate
            + (self.completion_tokens / 1_000_000) * out_rate
        )


@dataclass
class ProviderSpec:
    name: str
    kind: str  # "openai_compat" | "gemini"
    api_key: str
    model: str
    base_url: str = ""


class LLMClientProtocol(Protocol):
    """Protocol implemented by both production MultiModelLLMClient and test mocks."""

    usage: TokenUsageStats

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        prefer_pro: bool = False,
    ) -> T: ...


def _extract_json_text(raw: str) -> str:
    """Strip markdown code fences if a model wraps JSON in ```json ... ```."""
    text = (raw or "").strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    return text


class MultiModelLLMClient:
    """Async Cloud AI client with exponential backoff retry and automatic provider fallback."""

    def __init__(
        self,
        settings: AppSettings | None = None,
        providers: list[ProviderSpec] | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.max_retries = (
            max_retries if max_retries is not None else self.settings.ai_max_retries
        )
        self.providers = providers if providers is not None else self._build_default_chain()
        self.usage = TokenUsageStats()

    def _build_default_chain(self) -> list[ProviderSpec]:
        s = self.settings
        builders = {
            "deepseek": lambda: (
                ProviderSpec(
                    name="deepseek",
                    kind="openai_compat",
                    api_key=s.deepseek_api_key,
                    base_url=s.deepseek_base_url,
                    model=s.deepseek_primary_model,
                )
                if s.deepseek_api_key.strip()
                else None
            ),
            "openrouter": lambda: (
                ProviderSpec(
                    name="openrouter",
                    kind="openai_compat",
                    api_key=s.openrouter_api_key,
                    base_url=s.openrouter_base_url,
                    model=s.openrouter_model,
                )
                if s.openrouter_api_key.strip()
                else None
            ),
            "groq": lambda: (
                ProviderSpec(
                    name="groq",
                    kind="openai_compat",
                    api_key=s.groq_api_key,
                    base_url=s.groq_base_url,
                    model=s.groq_model,
                )
                if s.groq_api_key.strip()
                else None
            ),
            "gemini": lambda: (
                ProviderSpec(
                    name="gemini",
                    kind="gemini",
                    api_key=s.gemini_api_key,
                    model=s.gemini_model,
                )
                if s.gemini_api_key.strip()
                else None
            ),
        }
        chain: list[ProviderSpec] = []
        for pid in s.get_provider_order():
            builder = builders.get(pid)
            if builder is not None:
                spec = builder()
                if spec is not None:
                    chain.append(spec)
        return chain

    async def _call_openai_compat(
        self,
        provider: ProviderSpec,
        system_prompt: str,
        user_prompt: str,
        model_override: str | None = None,
    ) -> tuple[str, TokenUsageStats]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=provider.api_key,
            base_url=provider.base_url,
            timeout=90.0,
        )
        model_name = model_override or provider.model
        resp = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        content = resp.choices[0].message.content or "{}"
        prompt_tok = getattr(resp.usage, "prompt_tokens", 0) or 0
        comp_tok = getattr(resp.usage, "completion_tokens", 0) or 0
        cached_tok = 0
        details = getattr(resp.usage, "prompt_tokens_details", None)
        if details is not None:
            cached_tok = getattr(details, "cached_tokens", 0) or 0

        return content, TokenUsageStats(
            prompt_tokens=prompt_tok,
            cached_tokens=cached_tok,
            completion_tokens=comp_tok,
            api_calls=1,
            provider_used=f"{provider.name}:{model_name}",
        )

    async def _call_gemini(
        self,
        provider: ProviderSpec,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[str, TokenUsageStats]:
        from google import genai
        from google.genai import types

        def _sync_call() -> Any:
            client = genai.Client(api_key=provider.api_key)
            return client.models.generate_content(
                model=provider.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )

        resp = await asyncio.to_thread(_sync_call)
        content = getattr(resp, "text", None) or "{}"
        meta = getattr(resp, "usage_metadata", None)
        prompt_tok = getattr(meta, "prompt_token_count", 0) or 0 if meta else 0
        comp_tok = getattr(meta, "candidates_token_count", 0) or 0 if meta else 0
        cached_tok = getattr(meta, "cached_content_token_count", 0) or 0 if meta else 0
        return content, TokenUsageStats(
            prompt_tokens=prompt_tok,
            cached_tokens=cached_tok,
            completion_tokens=comp_tok,
            api_calls=1,
            provider_used=f"{provider.name}:{provider.model}",
        )

    async def _invoke_provider(
        self,
        provider: ProviderSpec,
        system_prompt: str,
        user_prompt: str,
        prefer_pro: bool = False,
    ) -> tuple[str, TokenUsageStats]:
        if provider.kind == "gemini":
            return await self._call_gemini(provider, system_prompt, user_prompt)
        model_override = (
            self.settings.deepseek_pro_model
            if prefer_pro and provider.name == "deepseek" and self.settings.deepseek_pro_model
            else None
        )
        return await self._call_openai_compat(
            provider, system_prompt, user_prompt, model_override=model_override
        )

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        prefer_pro: bool = False,
    ) -> T:
        """Call configured LLM providers in fallback order and validate output with Pydantic."""
        if not self.providers:
            raise RuntimeError(
                "Tidak ada API key Cloud AI yang terkonfigurasi di .env "
                "(DEEPSEEK_API_KEY / OPENROUTER_API_KEY / GROQ_API_KEY / GEMINI_API_KEY)."
            )

        errors: list[str] = []
        for provider in self.providers:
            for attempt in range(self.max_retries + 1):
                try:
                    raw_text, call_usage = await self._invoke_provider(
                        provider=provider,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        prefer_pro=prefer_pro,
                    )
                    cleaned = _extract_json_text(raw_text)
                    parsed = json.loads(cleaned)
                    validated = response_model.model_validate(parsed)
                    self.usage.add(call_usage)
                    return validated
                except Exception as exc:
                    errors.append(f"{provider.name} (attempt {attempt + 1}): {exc}")
                    if attempt < self.max_retries:
                        await asyncio.sleep(min(2.0 ** attempt, 4.0))

        raise RuntimeError(
            "Semua provider Cloud AI gagal menghasilkan JSON valid:\n" + "\n".join(errors)
        )
