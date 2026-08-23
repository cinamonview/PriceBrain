"""Request-scoped Firestore read deduplication for operations views."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:
    from pricebrain_app.crawler.price_alert_models import PriceAlert
    from pricebrain_app.crawler.price_ops_models import PriceSummary
    from pricebrain_app.crawler.targets import CrawlTarget

_ops_read_cache: ContextVar[OperationsReadCache | None] = ContextVar(
    "operations_read_cache",
    default=None,
)


@dataclass
class OperationsReadCache:
    crawler_targets: dict[tuple[Any, ...], list[CrawlTarget]] = field(default_factory=dict)
    listing_data: dict[str, tuple[bool, dict[str, Any] | None]] = field(default_factory=dict)
    price_history: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    price_summaries: dict[str, PriceSummary] = field(default_factory=dict)
    price_alerts: tuple[list[PriceAlert], int] | None = None


def get_operations_read_cache() -> OperationsReadCache | None:
    return _ops_read_cache.get()


@contextmanager
def operations_read_scope() -> Iterator[OperationsReadCache]:
    existing = _ops_read_cache.get()
    if existing is not None:
        yield existing
        return

    cache = OperationsReadCache()
    token = _ops_read_cache.set(cache)
    try:
        yield cache
    finally:
        _ops_read_cache.reset(token)
