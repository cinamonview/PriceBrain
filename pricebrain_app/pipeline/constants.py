"""Pipeline constants from docs/08 §13–§14, §24, §9."""

from __future__ import annotations

# Canonical board-partner IDs — must stay aligned with GPU master slugs
# (repository.gpu_master_seed.BOARD_PARTNERS). Do not put language aliases here.
GPU_BOARD_PARTNERS: tuple[str, ...] = (
    "ZOTAC",
    "ASUS",
    "MSI",
    "GIGABYTE",
    "GALAX",
    "PALIT",
    "PNY",
    "COLORFUL",
    "INNO3D",
    "GAINWARD",
    "SAPPHIRE",
    "XFX",
    "ASROCK",
    "MANLI",
    "POWERCOLOR",
)

# Input aliases → canonical partner. Targets must be members of GPU_BOARD_PARTNERS.
# Korean transliterations observed in 11번가 titles; English variants stay out of
# the canonical tuple so master identity and input language stay separate.
GPU_BOARD_PARTNER_ALIASES: dict[str, str] = {
    "기가바이트": "GIGABYTE",
    "조텍": "ZOTAC",
    "게인워드": "GAINWARD",
    "사파이어": "SAPPHIRE",
    "에이수스": "ASUS",
    "갤럭시": "GALAX",
    "팔릿": "PALIT",
    "컬러풀": "COLORFUL",
    "이노쓰리디": "INNO3D",
    "애즈락": "ASROCK",
    "엠에스아이": "MSI",
    "ROG": "ASUS",
    "TUF": "ASUS",
    "만리": "MANLI",
    "PowerColor": "POWERCOLOR",
    "파워컬러": "POWERCOLOR",
    "파워칼라": "POWERCOLOR",
}

GPU_SERIES_PATTERNS: tuple[str, ...] = ("RTX", "GTX", "RX", "Radeon", "GeForce", "Arc")

GPU_FILTER_KEYWORDS: tuple[str, ...] = ("RTX", "GTX", "RX", "Radeon", "GeForce", "Arc")

MALL_CODE_MAP: dict[str, str] = {
    "SSG": "SSG",
    "신세계몰": "SSG",
    "쓱닷컴": "SSG",
    "ELEVENST": "ELEVENST",
    "11번가": "ELEVENST",
    "COUPANG": "COUPANG",
    "쿠팡": "COUPANG",
    "GMARKET": "GMARKET",
    "G마켓": "GMARKET",
    "AUCTION": "AUCTION",
    "옥션": "AUCTION",
}

URL_TRACKING_QUERY_PARAMS = frozenset(
    {
        "click",
        "tlidSrchWd",
        "srchPgNo",
        "taste",
        "advertBidId",
        "siteNo",
        "salestrNo",
    }
)

MAX_PRICE_KRW = 100_000_000
