"""Shared CLI helpers for price operations commands."""

from __future__ import annotations

import argparse

from pricebrain_app.crawler.price_operations_view import PriceListFilter, PriceOperationsView
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.firebase.admin import get_firestore_client


def build_price_operations_view() -> PriceOperationsView:
    db = get_firestore_client()
    repo = CrawlTargetRepository(db)
    return PriceOperationsView(repo, db)


def add_price_filter_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target-id", help="Filter by crawl target ID")
    parser.add_argument("--mall", help="Filter by mall_id")
    parser.add_argument("--category", default="gpu", help="Filter by category (default: gpu)")
    parser.add_argument("--tag", help="Filter by tag")
    parser.add_argument("--brand", help="Filter by brand tag")
    parser.add_argument("--priority-min", type=int, help="Filter by minimum priority")
    parser.add_argument("--json", action="store_true", help="Output JSON")


def parse_price_filters(args: argparse.Namespace) -> PriceListFilter:
    return PriceListFilter(
        target_id=args.target_id.strip() if getattr(args, "target_id", None) else None,
        mall_id=args.mall,
        category=args.category,
        tag=args.tag,
        brand=args.brand,
        priority_min=args.priority_min,
    )
