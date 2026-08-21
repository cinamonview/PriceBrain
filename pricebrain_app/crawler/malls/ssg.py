"""SSG mall crawler — docs/07 §6, §13–§14."""

from __future__ import annotations

from urllib.parse import urlencode

from pricebrain_app.crawler.base import BaseMallCrawler
from pricebrain_app.crawler.exceptions import CrawlerHTTPError
from pricebrain_app.crawler.http_client import HttpClient, HttpResponse
from pricebrain_app.crawler.parser.ssg import parse_ssg_search_html
from pricebrain_app.crawler.types import RawProductData

SSG_SEARCH_BASE_URL = "https://www.ssg.com/search.ssg"


def build_ssg_search_url(keyword: str) -> str:
    """Build SSG search URL — public search endpoint (target=all per common SSG pattern)."""
    query = urlencode({"target": "all", "query": keyword})
    return f"{SSG_SEARCH_BASE_URL}?{query}"


class SsgCrawler(BaseMallCrawler):
    mall_code = "SSG"

    def __init__(self, http_client: HttpClient | None = None) -> None:
        self._http = http_client or HttpClient()

    def fetch_search_html(self, keyword: str) -> str:
        url = build_ssg_search_url(keyword)
        response = self._http.get(url)
        if response.status_code != 200:
            raise CrawlerHTTPError(
                f"Unexpected HTTP status {response.status_code}",
                status_code=response.status_code,
                url=url,
            )
        return response.text

    def fetch_search_response(self, keyword: str) -> HttpResponse:
        url = build_ssg_search_url(keyword)
        return self._http.get(url)

    def parse_search_html(self, html: str) -> list[RawProductData]:
        return parse_ssg_search_html(html, mall=self.mall_code)

    def search(self, keyword: str) -> list[RawProductData]:
        html = self.fetch_search_html(keyword)
        return self.parse_search_html(html)

    def close(self) -> None:
        self._http.close()
