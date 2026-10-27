"""Danawa-Crawler VGA.csv backfill — historical lowest prices through the persist boundary.

Source: sammy310/Danawa-Crawler (MIT) ``crawl_data/VGA.csv``. One row per Danawa
product (``Id`` = pcode), one column per crawl date holding the lowest price.
Nothing here talks to Danawa; the CSV is read from disk.

Every row goes through ``run_pipeline`` and ``persist_validated_product`` exactly
like a crawled listing, so GPU master and identity-review gates still apply.
Rows the gates reject are reported, not forced in.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.pipeline.exceptions import (
    GpuProductFilteredError,
    PipelineValidationError,
)
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository.exceptions import (
    IdentityReviewBlockedError,
    RepositoryValidationError,
    UnknownGpuModelError,
)
from pricebrain_app.repository.gpu_master_seed import ensure_gpu_master_seeded
from pricebrain_app.repository.gpu_repository import GpuRepository
from pricebrain_app.repository.persist_service import (
    PersistBoundarySession,
    PersistDecision,
    persist_validated_product,
)

KST = timezone(timedelta(hours=9))
DANAWA_MALL = "danawa"
DANAWA_SELLER = "Danawa"
DANAWA_PRODUCT_URL = "https://prod.danawa.com/info/?pcode={pcode}"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_MASTER_SENTINEL_MODEL = "rtx_5070"
_EXAMPLES_PER_CATEGORY = 3


class DanawaImportSetupError(RuntimeError):
    """The target database is not ready for an import run."""


@dataclass(frozen=True)
class DanawaProduct:
    pcode: str
    name: str
    # (crawled_at, price) ascending, only where the price differs from the previous kept point.
    observations: tuple[tuple[datetime, int], ...]


@dataclass
class ImportReport:
    rows: int = 0
    accepted: int = 0
    listings_written: int = 0
    price_points_written: int = 0
    skipped: Counter[str] = field(default_factory=Counter)
    examples: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    def skip(self, category: str, name: str) -> None:
        self.skipped[category] += 1
        samples = self.examples[category]
        if len(samples) < _EXAMPLES_PER_CATEGORY:
            samples.append(name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "accepted": self.accepted,
            "listings_written": self.listings_written,
            "price_points_written": self.price_points_written,
            "skipped": dict(self.skipped.most_common()),
            "examples": {key: list(value) for key, value in self.examples.items()},
        }


def parse_price(cell: str) -> int | None:
    """``"1,234,000"`` → 1234000; blanks and labels such as ``일시품절`` → None."""
    text = cell.strip().replace(",", "")
    return int(text) if text.isdigit() and int(text) > 0 else None


def parse_danawa_csv(path: Path) -> list[DanawaProduct]:
    """Read VGA.csv; header columns after ``Id, Name`` are KST crawl timestamps."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if not header or header[:2] != ["Id", "Name"]:
            raise ValueError("expected a Danawa-Crawler CSV with 'Id,Name,<dates...>' header")
        crawl_times = [
            datetime.strptime(column, _DATE_FORMAT).replace(tzinfo=KST) for column in header[2:]
        ]
        products: list[DanawaProduct] = []
        for row in reader:
            if len(row) < 2 or not row[0].strip():
                continue
            observations: list[tuple[datetime, int]] = []
            for crawled_at, cell in zip(crawl_times, row[2:]):
                price = parse_price(cell)
                if price is None:
                    continue
                if observations and observations[-1][1] == price:
                    continue
                observations.append((crawled_at, price))
            products.append(
                DanawaProduct(
                    pcode=row[0].strip(),
                    name=row[1].strip(),
                    observations=tuple(sorted(observations)),
                )
            )
    return products


def _raw_listing(product: DanawaProduct, crawled_at: datetime, price: int) -> dict[str, Any]:
    return {
        "mall": DANAWA_MALL,
        "product_id": product.pcode,
        "product_name": product.name,
        "price": price,
        "seller": DANAWA_SELLER,
        "product_url": DANAWA_PRODUCT_URL.format(pcode=product.pcode),
        "crawled_at": crawled_at,
    }


def _skip_category(exc: Exception) -> str:
    if isinstance(exc, GpuProductFilteredError):
        return "not_gpu"
    if isinstance(exc, PipelineValidationError):
        return f"pipeline_invalid:{exc.field}" if getattr(exc, "field", None) else "pipeline_invalid"
    if isinstance(exc, UnknownGpuModelError):
        return f"unknown_gpu_model:{exc.gpu_model_id}"
    if isinstance(exc, RepositoryValidationError):
        return f"repository_invalid:{exc.field}" if exc.field else "repository_invalid"
    return f"failed:{type(exc).__name__}"


def import_danawa_products(
    db: FirestoreClient,
    products: list[DanawaProduct],
    *,
    dry_run: bool = False,
    progress: Callable[[int, int], None] | None = None,
) -> ImportReport:
    """Screen every product through the persist boundary, then write accepted ones.

    Phase 1 registers each product's latest price in one boundary session so batch
    collisions are detected. Phase 2 replays the accepted products' price changes in
    chronological order so ``price_history`` and ``current_price`` end up consistent.
    """
    if dry_run:
        if GpuRepository(db).get_model(_MASTER_SENTINEL_MODEL) is None:
            raise DanawaImportSetupError(
                "GPU master is not seeded — run `python -m pricebrain_app.scripts.seed_gpu_master` "
                "against the emulator first"
            )
    else:
        ensure_gpu_master_seeded(db)

    report = ImportReport(rows=len(products))
    screening = PersistBoundarySession(db, dry_run=True)
    candidates: dict[str, DanawaProduct] = {}

    for product in products:
        if not product.observations:
            report.skip("no_price", product.name)
            continue
        crawled_at, price = product.observations[-1]
        try:
            validated = run_pipeline(_raw_listing(product, crawled_at, price))
            persist_validated_product(
                db,
                validated,
                external_product_id=product.pcode,
                product_name=product.name,
                boundary_session=screening,
            )
        except Exception as exc:  # noqa: BLE001 - one bad row must not stop the batch
            report.skip(_skip_category(exc), product.name)
            continue
        candidates[product.pcode] = product

    names = {code: product.name for code, product in candidates.items()}
    accepted: list[DanawaProduct] = []
    for outcome in screening.finalize():
        product = candidates[outcome.external_product_id]
        if outcome.decision is PersistDecision.PERSIST_CANDIDATE:
            accepted.append(product)
        else:
            report.skip("identity_review_blocked", names[outcome.external_product_id])
    report.accepted = len(accepted)

    if dry_run:
        return report

    for index, product in enumerate(accepted, start=1):
        wrote_listing = False
        for crawled_at, price in product.observations:
            try:
                validated = run_pipeline(_raw_listing(product, crawled_at, price))
                result = persist_validated_product(
                    db,
                    validated,
                    external_product_id=product.pcode,
                    product_name=product.name,
                )
            except IdentityReviewBlockedError:
                report.skip("identity_review_blocked", product.name)
                break
            except Exception as exc:  # noqa: BLE001
                report.skip(_skip_category(exc), product.name)
                break
            wrote_listing = True
            if result.get("price_history_appended"):
                report.price_points_written += 1
        if wrote_listing:
            report.listings_written += 1
        if progress is not None:
            progress(index, len(accepted))
    return report
