"""Elevenst detail-page manufacturer part number extraction — Phase 10 pilot."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

# Board-partner MPN prefixes commonly embedded in 11번가 certification keys.
_MPN_PREFIXES: tuple[str, ...] = (
    "GV-",
    "RTX",
    "GT-",
    "PH-",
    "RX",
    "PA-",
    "NE-",
    "901-",
    "113-",
    "912-",
)

_MPN_BODY = re.compile(r"\b([A-Z]{2,3}-[A-Z0-9-]{4,})\b")

_SPEC_LABEL_KEYWORDS: tuple[str, ...] = (
    "모델명",
    "MODEL",
    "품번",
    "PART NUMBER",
    "MANUFACTURER PART",
    "MPN",
    "제조사 모델",
)


def _normalize_mpn_candidate(value: str) -> str | None:
    candidate = value.strip().upper()
    if not candidate:
        return None
    if candidate.isdigit():
        return None
    if "HTTP" in candidate or "WWW." in candidate:
        return None
    match = _MPN_BODY.search(candidate)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Z0-9-]{6,}", candidate) and "-" in candidate:
        return candidate
    return None


def _mpn_from_certification_key(cert_key: str) -> str | None:
    upper = cert_key.strip().upper()
    if not upper:
        return None

    for prefix in _MPN_PREFIXES:
        match = re.search(rf"({re.escape(prefix)}[A-Z0-9-]+)", upper)
        if match:
            normalized = _normalize_mpn_candidate(match.group(1))
            if normalized:
                return normalized

    match = _MPN_BODY.search(upper)
    if match:
        return _normalize_mpn_candidate(match.group(1))
    return None


def _mpn_from_spec_table(soup: BeautifulSoup) -> str | None:
    for row in soup.select("table tr"):
        header = row.select_one("th")
        cell = row.select_one("td")
        if header is None or cell is None:
            continue
        label = header.get_text(" ", strip=True).upper()
        if not any(keyword in label for keyword in _SPEC_LABEL_KEYWORDS):
            continue
        value = cell.get_text(" ", strip=True)
        normalized = _normalize_mpn_candidate(value)
        if normalized:
            return normalized
    return None


def extract_elevenst_detail_mpn(soup: BeautifulSoup) -> str | None:
    """Extract manufacturer part number from certification/spec tables only."""
    cert_input = soup.select_one("input#certKey")
    if cert_input is not None:
        value = cert_input.get("value")
        if isinstance(value, str):
            mpn = _mpn_from_certification_key(value)
            if mpn:
                return mpn

    for anchor in soup.select("a[data-certKey]"):
        cert_key = anchor.get("data-certKey")
        if isinstance(cert_key, str):
            mpn = _mpn_from_certification_key(cert_key)
            if mpn:
                return mpn

    return _mpn_from_spec_table(soup)
