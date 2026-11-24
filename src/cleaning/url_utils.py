"""Deterministic URL and domain normalization utilities (0 token AI)."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse

STRIPPED_QUERY_PREFIXES = ("utm_",)
STRIPPED_QUERY_KEYS = frozenset(
    {"page", "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source", "s", "t"}
)
SUBDOMAIN_PREFIX_RE = re.compile(r"^(?:www\d*|m|mobile|amp)\.", re.IGNORECASE)


def normalize_url(raw_url: str | None) -> str:
    """Normalize an article URL for deterministic deduplication and client list matching.

    Rules (SAD.md Section 3A3 & 3A4):
    - Strip scheme (`http://`, `https://`)
    - Normalize leading `www.`, `m.`, `mobile.`, `amp.` subdomains
    - Strip `?utm_*`, `?page=*`, and common tracking query parameters
    - Strip URL fragments (`#...`) and trailing slashes
    """
    if not raw_url:
        return ""
    text = str(raw_url).strip()
    if not text or text.lower() in {"nan", "none", "-", "0"}:
        return ""

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text):
        text = f"https://{text}"

    parsed = urlparse(text)
    host = (parsed.netloc or "").strip().lower()
    if not host:
        return ""

    # Strip default ports
    if host.endswith(":80"):
        host = host[:-3]
    elif host.endswith(":443"):
        host = host[:-4]

    host = SUBDOMAIN_PREFIX_RE.sub("", host)
    path = re.sub(r"/{2,}", "/", parsed.path or "").rstrip("/")

    # Filter tracking & pagination query params
    kept_params = []
    for k, v in parse_qsl(parsed.query, keep_blank_values=False):
        k_lower = k.lower()
        if k_lower in STRIPPED_QUERY_KEYS or any(
            k_lower.startswith(p) for p in STRIPPED_QUERY_PREFIXES
        ):
            continue
        kept_params.append((k_lower, v))
    kept_params.sort()

    query_str = urlencode(kept_params)
    normalized = f"{host}{path}"
    if query_str:
        normalized = f"{normalized}?{query_str}"
    return normalized


def extract_domain(raw_url_or_domain: str | None) -> str:
    """Extract normalized root/portal domain (without scheme, `www.`, `m.`, or path)."""
    if not raw_url_or_domain:
        return ""
    text = str(raw_url_or_domain).strip()
    if not text or text.lower() in {"nan", "none", "-", "0"}:
        return ""

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text):
        text = f"https://{text}"

    parsed = urlparse(text)
    host = (parsed.netloc or "").strip().lower()
    if ":" in host:
        host = host.split(":", 1)[0]
    return SUBDOMAIN_PREFIX_RE.sub("", host)
