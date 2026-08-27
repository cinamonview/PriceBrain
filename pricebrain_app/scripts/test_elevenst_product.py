"""Live single-product 11번가 verification — optional ingest to FastAPI."""

from __future__ import annotations

import argparse
import json
import os
import sys

from pricebrain_app.crawler.adapters.elevenst import ElevenstCrawler
from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.exceptions import CrawlerError, IngestClientError

DEFAULT_TEST_URL = "https://www.11st.co.kr/products/8083397777"


def _resolve_url(cli_url: str | None) -> str:
    url = (cli_url or os.environ.get("PRICEBRAIN_TEST_ELEVENST_URL") or DEFAULT_TEST_URL).strip()
    if not url:
        raise SystemExit(
            "Provide --url or set PRICEBRAIN_TEST_ELEVENST_URL to an 11번가 product page URL."
        )
    return url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch one 11번가 product URL and optionally POST to ingest API.",
    )
    parser.add_argument(
        "--url",
        help="11번가 product URL (default: PRICEBRAIN_TEST_ELEVENST_URL or built-in test URL)",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Send parsed payload to POST /internal/ingest/listing",
    )
    args = parser.parse_args(argv)

    url = _resolve_url(args.url)

    try:
        with ElevenstCrawler() as crawler:
            payload = crawler.crawl_product_url(url)
            print(json.dumps(payload.to_dict(), ensure_ascii=False, indent=2))

            if args.ingest:
                with IngestClient() as client:
                    result = client.send_listing(payload.to_dict())
                print(json.dumps(result, ensure_ascii=False, indent=2))
    except (CrawlerError, IngestClientError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
