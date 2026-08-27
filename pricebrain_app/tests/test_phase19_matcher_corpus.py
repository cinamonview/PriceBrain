"""Phase 19 — corpus-measured manufacturer line splits (no global color tokens)."""

from __future__ import annotations

from pricebrain_app.pipeline.identity_variants import extract_variant_token
from pricebrain_app.pipeline.product_matcher import build_canonical_product_id


def _cid(brand: str, model: str, vram: int, name: str) -> str | None:
    return build_canonical_product_id(
        {
            "brand": brand,
            "gpu_model": model,
            "vram_gb": vram,
            "normalized_product_name": name,
        }
    )


def test_phase19_corpus_confirmed_lines_do_not_share_canonical() -> None:
    ultra = _cid("COLORFUL", "RTX 5070", 12, "COLORFUL iGame RTX 5070 ULTRA OC D7 12GB")
    gaming = _cid("COLORFUL", "RTX 5070", 12, "COLORFUL RTX 5070 GAMING D7 12GB")
    battle = _cid(
        "COLORFUL", "RTX 5070 Ti", 16, "COLORFUL RTX 5070 Ti BATTLE AX SFF D7 16GB"
    )
    ultra_ti = _cid(
        "COLORFUL",
        "RTX 5070 Ti",
        16,
        "COLORFUL iGame RTX 5070 Ti ULTRA OC SFF D7 16GB",
    )
    assert ultra != gaming
    assert battle != ultra_ti

    twin = _cid("INNO3D", "RTX 5070", 12, "INNO3D RTX 5070 OC D7 12GB TWIN X2")
    x3 = _cid("INNO3D", "RTX 5070", 12, "INNO3D RTX 5070 OC D7 12GB X3")
    assert twin != x3

    infinity = _cid("PALIT", "RTX 5070", 12, "PALIT RTX 5070 INFINITY 3 D7 12GB")
    gamingpro = _cid("PALIT", "RTX 5070", 12, "PALIT RTX 5070 GAMINGPRO-S D7 12GB")
    assert infinity != gamingpro

    hof = _cid("GALAX", "RTX 5070 Ti", 16, "GALAX RTX 5070 Ti HOF GAMING D7 16GB")
    ex = _cid("GALAX", "RTX 5070 Ti", 16, "갤럭시 GALAX RTX 5070 Ti EX GAMER OC D7 16GB")
    assert hof != ex

    swift = _cid("XFX", "RX 9070 XT", 16, "XFX 라데온 RX 9070 XT SWIFT D6 16GB")
    quick = _cid("XFX", "RX 9070 XT", 16, "XFX 라데온 RX 9070 XT QUICKSILVER D6 16GB")
    assert swift != quick


def test_phase19_color_is_not_identity_token() -> None:
    white = extract_variant_token(
        brand="GALAX",
        normalized_name="갤럭시 GALAX RTX 5070 Ti EX GAMER WHITE OC D7 16GB",
    )
    black = extract_variant_token(
        brand="GALAX",
        normalized_name="갤럭시 GALAX RTX 5070 Ti EX GAMER BLACK OC D7 16GB",
    )
    assert white == black == "EXGAMER"


def test_phase19_trinity_and_strix_not_forced_without_sku_corpus() -> None:
    """TRINITY/STRIX GPU SKUs are not in the stored 11st corpus as card titles."""
    assert extract_variant_token(brand="ASUS", normalized_name="ASUS ROG STRIX") == "ROG"
    zotac_trinity = extract_variant_token(
        brand="ZOTAC",
        normalized_name="ZOTAC GAMING RTX 4070 TRINITY",
    )
    assert zotac_trinity == "TRINITY"
