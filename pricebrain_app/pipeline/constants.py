"""Pipeline constants from docs/08 §13–§14, §24, §9."""

from __future__ import annotations

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
)

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
