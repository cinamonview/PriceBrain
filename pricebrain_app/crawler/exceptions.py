"""Crawler-layer exceptions — docs/07 §13–§15."""


class CrawlerError(Exception):
    """Base crawler error."""


class CrawlerHTTPError(CrawlerError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
        error_code: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.error_code = error_code


class CrawlerTimeoutError(CrawlerError):
    def __init__(self, message: str, *, url: str | None = None):
        super().__init__(message)
        self.url = url


class CrawlerRetryExhaustedError(CrawlerError):
    def __init__(self, message: str, *, url: str | None = None, attempts: int = 0):
        super().__init__(message)
        self.url = url
        self.attempts = attempts


class IngestClientError(CrawlerError):
    """Ingest API client error — docs/07 → FastAPI ingest."""


class IngestClientConfigError(IngestClientError):
    """Missing or invalid ingest client configuration."""


class IngestClientTimeoutError(IngestClientError):
    def __init__(self, message: str, *, url: str | None = None):
        super().__init__(message)
        self.url = url


class IngestClientNetworkError(IngestClientError):
    def __init__(self, message: str, *, url: str | None = None):
        super().__init__(message)
        self.url = url


class IngestClientHTTPError(IngestClientError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        url: str | None = None,
        detail: str | object | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.detail = detail


class CrawlerParseError(CrawlerError):
    """HTML/parser could not produce a valid ingest payload."""
