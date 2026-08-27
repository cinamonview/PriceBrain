"""ValidatedProduct persist orchestration — docs/09 §6.2."""

from __future__ import annotations

from typing import Any, Callable

from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.repository import constants as c
from pricebrain_app.repository.exceptions import IdentityReviewBlockedError
from pricebrain_app.repository.gpu_master_seed import ensure_gpu_master_seeded
from pricebrain_app.repository.listing_repository import (
    listing_payload_from_validated,
    build_price_history_document_id,
)
from pricebrain_app.repository.price_history_repository import normalize_krw_price
from pricebrain_app.repository.product_repository import product_payload_from_validated
from pricebrain_app.repository.reference_repository import ReferenceRepository
from pricebrain_app.repository.stored_product_collision import (
    review_reason_from_report,
    review_stored_mapping,
)
from pricebrain_app.repository.validation import validate_for_persist


class _PersistTransaction:
    """Unwrap counting-client refs so Admin SDK and FakeFirestore transactions work."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def set(self, ref: Any, data: dict[str, Any], merge: bool = False) -> None:
        real_ref = getattr(ref, "_inner", ref)
        counters = getattr(ref, "_counters", None)
        path = getattr(ref, "_path", None)
        if counters is not None and path is not None:
            counters.record_write(path)
        self._inner.set(real_ref, data, merge=merge)


def run_persist_transaction(db: FirestoreClient, callback: Callable[[Any], Any]) -> Any:
    """Run callback(transaction) with FakeFirestore or Admin SDK transaction semantics."""
    inner_db = getattr(db, "_inner", db)
    runner = getattr(inner_db, "run_transaction", None)

    def _invoke(inner_txn: Any) -> Any:
        return callback(_PersistTransaction(inner_txn))

    if callable(runner):
        return runner(_invoke)

    from google.cloud.firestore_v1 import transactional as firestore_transactional

    @firestore_transactional
    def _wrapped(transaction: Any) -> Any:
        return _invoke(transaction)

    return _wrapped(inner_db.transaction())


def _write_validated_product(
    db: FirestoreClient,
    data: dict[str, Any],
) -> dict[str, str | bool]:
    """Identity-checked atomic persist. Application code must use persist_service."""
    validate_for_persist(data)

    ensure_gpu_master_seeded(db)

    reference_repo = ReferenceRepository(db)
    reference_repo.resolve_all(data)

    canonical_product_id = str(data["canonical_product_id"])
    listing_id, listing_payload = listing_payload_from_validated(
        data, canonical_product_id
    )
    external_product_id = str(data.get("product_id") or "")
    product_name = str(
        data.get("normalized_product_name") or data.get("raw_product_name") or ""
    )
    price = data.get("price")
    crawled_at = data.get("crawled_at")

    def _txn(transaction: Any) -> dict[str, str | bool]:
        product_ref = db.collection(c.PRODUCTS).document(canonical_product_id)
        listing_ref = db.collection(c.LISTINGS).document(listing_id)
        raw_txn = getattr(transaction, "_inner", transaction)
        product_snap = product_ref.get(transaction=raw_txn)
        listing_snap = listing_ref.get(transaction=raw_txn)

        stored = product_snap.to_dict() if product_snap.exists else None
        if stored is not None:
            report = review_stored_mapping(
                stored,
                data,
                external_product_id=external_product_id,
                product_name=product_name,
            )
            if report is not None and report.review_required:
                raise IdentityReviewBlockedError(
                    "persist blocked by stored product identity review",
                    canonical_product_id=canonical_product_id,
                    review_reason=review_reason_from_report(report),
                )

        keep_snapshot = bool(
            stored is not None and isinstance(stored.get("identity_snapshot"), dict)
        )
        product_payload = product_payload_from_validated(
            data,
            include_identity_snapshot=not keep_snapshot,
        )
        product_payload["updated_at"] = SERVER_TIMESTAMP
        if not product_snap.exists:
            product_payload.setdefault("active", True)
            product_payload["created_at"] = SERVER_TIMESTAMP

        transaction.set(product_ref, product_payload, merge=True)

        listing_write = dict(listing_payload)
        if not listing_snap.exists:
            listing_write["created_at"] = SERVER_TIMESTAMP
        transaction.set(listing_ref, listing_write, merge=True)

        price_history_appended = False
        if price is not None and crawled_at is not None:
            new_price = normalize_krw_price(price)
            previous_price: int | None = None
            if listing_snap.exists:
                listing_data = listing_snap.to_dict() or {}
                if listing_data.get("current_price") is not None:
                    previous_price = normalize_krw_price(listing_data["current_price"])
            if previous_price is None or previous_price != new_price:
                history_id = build_price_history_document_id(
                    int(crawled_at.timestamp() * 1000)
                )
                history_ref = listing_ref.collection(c.PRICE_HISTORY).document(history_id)
                price_change = (
                    (new_price - previous_price) if previous_price is not None else None
                )
                transaction.set(
                    history_ref,
                    {
                        "price": new_price,
                        "crawled_at": crawled_at,
                        "previous_price": previous_price,
                        "price_change": price_change,
                    },
                )
                price_history_appended = True

        return {
            "product_id": canonical_product_id,
            "listing_id": listing_id,
            "price_history_appended": price_history_appended,
        }

    return run_persist_transaction(db, _txn)
