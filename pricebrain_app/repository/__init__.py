"""Repository layer — SSOT: docs/09 §6."""

from pricebrain_app.repository.exceptions import RepositoryError, RepositoryValidationError
from pricebrain_app.repository.listing_repository import (
    ListingRepository,
    build_listing_document_id,
    build_price_history_document_id,
)
from pricebrain_app.repository.price_history_repository import PriceHistoryRepository
from pricebrain_app.repository.product_repository import ProductRepository
from pricebrain_app.repository.service import save_validated_product

__all__ = [
    "ListingRepository",
    "PriceHistoryRepository",
    "ProductRepository",
    "RepositoryError",
    "RepositoryValidationError",
    "build_listing_document_id",
    "build_price_history_document_id",
    "save_validated_product",
]
