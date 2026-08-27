"""Product-type classification — docs/08 GPU filter, R1 design gate.

Keyword rules only. Runs after normalize and before GPU parse so assembled PCs,
laptops, and accessories never reach VRAM/master resolution.

Priority (strongest product-level signal first):
  LAPTOP → PREBUILT_PC → GPU_ACCESSORY → GPU_PRODUCT (GPU keyword) → UNKNOWN
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pricebrain_app.pipeline.exceptions import GpuProductFilteredError
from pricebrain_app.pipeline.gpu_parser import has_gpu_keyword

FILTERED_PRODUCT_TYPES: frozenset[str]


class ProductType(StrEnum):
    GPU_PRODUCT = "GPU_PRODUCT"
    PREBUILT_PC = "PREBUILT_PC"
    LAPTOP = "LAPTOP"
    GPU_ACCESSORY = "GPU_ACCESSORY"
    UNKNOWN = "UNKNOWN"


# Longer phrases first so "조립 PC" wins over a later generic token.
_LAPTOP_KEYWORDS: tuple[str, ...] = (
    "게이밍노트북",
    "갤럭시북",
    "galaxy book",
    "galaxybook",
    "legion",
    "노트북",
    "notebook",
    "laptop",
)

_PREBUILT_KEYWORDS: tuple[str, ...] = (
    "조립컴퓨터",
    "조립 컴퓨터",
    "조립피씨",
    "조립 pc",
    "조립pc",
    "게이밍컴퓨터",
    "게임용pc",
    "게임용 pc",
    "게이밍 pc",
    "게이밍pc",
    "완본체",
    "데스크탑",
    "desktop",
    "본체",
)

# Do not use bare "fan" / "팬" / "수냉" / "교체용": Dual Fan SKUs, custom-loop
# prebuilts, and used-card listings would false-positive.
_ACCESSORY_KEYWORDS: tuple[str, ...] = (
    "그래픽카드 케이블",
    "gpu 케이블",
    "연장 케이블",
    "연장케이블",
    "전원 코드",
    "전원 커넥터",
    "쿨링 팬",
    "냉각 팬",
    "쿨링팬",
    "냉각팬",
    "교체용 팬",
    "교체 팬",
    "팬 교체용",
    "cooling fan",
    "replacement fan",
    "gpu 팬",
    "gpu 쿨러",
    "그래픽 카드 팬",
    "그래픽카드 팬",
    "비디오 카드 팬",
    "방열판",
    "히트싱크",
    "heatsink",
    "워터블록",
    "워터 블럭",
    "waterblock",
    "water block",
    "수냉 블록",
    "수냉블록",
    "백플레이트",
    "backplate",
    "12vhpwr",
    "12vhp",
    "라이저",
    "riser",
    "지지대",
    "받침대",
    "거치대",
    "브라켓",
    "브래킷",
    "홀더",
    "스탠드",
    "프레임",
    "선풍기",
    "슈라우드",
    "shroud",
    "젠더",
    "커넥터",
    "어댑터",
    "케이블",
    "액세서리",
)


def _contains_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def classify_product_type(*, raw_name: str, normalized_name: str = "") -> ProductType:
    combined = f"{raw_name} {normalized_name}".strip()
    if not combined:
        return ProductType.UNKNOWN
    if _contains_keyword(combined, _LAPTOP_KEYWORDS):
        return ProductType.LAPTOP
    if _contains_keyword(combined, _PREBUILT_KEYWORDS):
        return ProductType.PREBUILT_PC
    if _contains_keyword(combined, _ACCESSORY_KEYWORDS):
        return ProductType.GPU_ACCESSORY
    if has_gpu_keyword(combined):
        return ProductType.GPU_PRODUCT
    return ProductType.UNKNOWN


FILTERED_PRODUCT_TYPES = frozenset(
    {
        ProductType.LAPTOP.value,
        ProductType.PREBUILT_PC.value,
        ProductType.GPU_ACCESSORY.value,
    }
)


def classify_product(data: dict[str, Any]) -> dict[str, Any]:
    """Stamp product_type; filtered types raise GpuProductFilteredError."""
    result = dict(data)
    raw = str(result.get("raw_product_name") or result.get("product_name") or "")
    normalized = str(result.get("normalized_product_name") or "")
    product_type = classify_product_type(raw_name=raw, normalized_name=normalized)
    result["product_type"] = product_type.value
    if product_type.value in FILTERED_PRODUCT_TYPES:
        raise GpuProductFilteredError(
            f"non-GPU product type: {product_type.value}",
            field=product_type.value,
        )
    return result
