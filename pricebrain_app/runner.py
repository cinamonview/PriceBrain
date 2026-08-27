"""07 → 08 → 09 orchestration — docs/07, docs/09, docs/13."""

from __future__ import annotations

from typing import Any

from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.crawler.malls.ssg import SsgCrawler
from pricebrain_app.firebase.admin import get_firestore_client
from pricebrain_app.pipeline.exceptions import (
    GpuProductFilteredError,
    PipelineValidationError,
)
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.pipeline.types import ValidatedProduct
from pricebrain_app.repository.crawl_repository import (
    LOG_LEVEL_ERROR,
    LOG_LEVEL_INFO,
    LOG_LEVEL_WARN,
    CrawlRepository,
)
from pricebrain_app.repository.exceptions import UnknownGpuModelError
from pricebrain_app.repository.operational_service import (
    persist_pipeline_validation_failure,
    quarantine_unknown_gpu_model,
)
from pricebrain_app.repository.persist_service import (
    PersistBoundarySession,
    PersistDecision,
    persist_validated_product as persist_through_boundary,
)


def persist_validated_product(
    db: FirestoreClient,
    validated: ValidatedProduct | dict[str, Any],
    *,
    boundary_session: PersistBoundarySession | None = None,
) -> dict[str, str | bool]:
    """Persist already-validated product (08 output → 09) through identity boundary."""
    data = dict(validated)
    external_id = str(data.get("external_product_id") or data.get("product_id") or "")
    product_name = str(
        data.get("normalized_product_name") or data.get("raw_product_name") or ""
    )
    return persist_through_boundary(
        db,
        data,
        external_product_id=external_id,
        product_name=product_name,
        boundary_session=boundary_session,
    )


def run_raw_through_pipeline(raw: dict[str, Any]) -> ValidatedProduct:
    """Run 08 pipeline only — no network, no Firestore."""
    return run_pipeline(raw)


def run_crawl_batch(
    db: FirestoreClient,
    mall_id: str,
    raw_items: list[dict[str, Any]],
    *,
    keyword: str | None = None,
    validation_source: str = "pipeline",
) -> dict[str, Any]:
    """Crawl batch orchestration: crawl_job + crawl_logs + pipeline + repository."""
    crawl_repo = CrawlRepository(db)
    job_id = crawl_repo.start_job(mall_id, keyword=keyword)
    log_ids: list[str] = []

    start_message = "Crawl job started"
    if keyword:
        start_message = f"Crawl job started (keyword={keyword})"
    log_ids.append(
        crawl_repo.create_log(job_id, mall_id, LOG_LEVEL_INFO, start_message)
    )
    log_ids.append(
        crawl_repo.create_log(
            job_id,
            mall_id,
            LOG_LEVEL_INFO,
            f"Processing {len(raw_items)} item(s)",
        )
    )

    results: list[dict[str, str | bool]] = []
    validation_failures = 0
    quarantined = 0
    identity_review_blocked = 0

    boundary_session = PersistBoundarySession(db)

    try:
        for raw in raw_items:
            product_id = str(raw.get("product_id", "unknown"))
            validated_data: dict[str, Any] = {}
            try:
                validated = run_pipeline(dict(raw))
                validated_data = dict(validated)
                persist_validated_product(
                    db,
                    validated_data,
                    boundary_session=boundary_session,
                )
            except UnknownGpuModelError as exc:
                quarantine_unknown_gpu_model(db, exc, validated_data=validated_data)
                quarantined += 1
                log_ids.append(
                    crawl_repo.create_log(
                        job_id,
                        mall_id,
                        LOG_LEVEL_WARN,
                        f"Unknown GPU model quarantined: {product_id}: {exc.gpu_model_id}",
                    )
                )
            except (PipelineValidationError, GpuProductFilteredError) as exc:
                persist_pipeline_validation_failure(
                    db,
                    exc,
                    source=validation_source,
                    raw_data=dict(raw),
                )
                validation_failures += 1
                log_ids.append(
                    crawl_repo.create_log(
                        job_id,
                        mall_id,
                        LOG_LEVEL_WARN,
                        f"Product validation failed: {product_id}: {exc}",
                    )
                )

        for outcome in boundary_session.finalize():
            if outcome.decision is PersistDecision.PERSISTED and outcome.save_result:
                results.append(outcome.save_result)
                log_ids.append(
                    crawl_repo.create_log(
                        job_id,
                        mall_id,
                        LOG_LEVEL_INFO,
                        f"Product processed: {outcome.external_product_id}",
                    )
                )
            elif outcome.decision is PersistDecision.IDENTITY_REVIEW_BLOCKED:
                identity_review_blocked += 1
                log_ids.append(
                    crawl_repo.create_log(
                        job_id,
                        mall_id,
                        LOG_LEVEL_WARN,
                        f"Identity review blocked: {outcome.external_product_id}",
                    )
                )

        if raw_items and validation_failures == len(raw_items):
            error_message = f"{validation_failures} item(s) failed validation"
            log_ids.append(
                crawl_repo.create_log(
                    job_id,
                    mall_id,
                    LOG_LEVEL_ERROR,
                    f"Crawl job failed: {error_message}",
                )
            )
            crawl_repo.fail_job(job_id, error_message)
        else:
            log_ids.append(
                crawl_repo.create_log(
                    job_id,
                    mall_id,
                    LOG_LEVEL_INFO,
                    "Crawl job completed",
                )
            )
            crawl_repo.complete_job(job_id)
    except Exception as exc:
        log_ids.append(
            crawl_repo.create_log(
                job_id,
                mall_id,
                LOG_LEVEL_ERROR,
                f"Crawl job failed: {exc}",
            )
        )
        crawl_repo.fail_job(job_id, str(exc))
        raise

    return {
        "job_id": job_id,
        "results": results,
        "validation_failures": validation_failures,
        "quarantined": quarantined,
        "identity_review_blocked": identity_review_blocked,
        "log_ids": log_ids,
    }


def run_ssg_pipeline(keyword: str) -> list[dict[str, str | bool]]:
    """Crawler → Pipeline → Repository (requires Firebase configuration)."""
    crawler = SsgCrawler()
    try:
        raw_items = [dict(raw) for raw in crawler.search(keyword)]
        db = get_firestore_client()
        batch = run_crawl_batch(db, "SSG", raw_items, keyword=keyword)
        return batch["results"]
    finally:
        crawler.close()
