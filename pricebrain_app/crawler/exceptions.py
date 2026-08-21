"""Crawler-layer exceptions — docs/07 §13–§15."""


class CrawlerError(Exception):
    """Base crawler error."""


class CrawlerHTTPError(CrawlerError):
    def __init__(self, message: str, *, status_code: int | None = None, url: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.url = url


class CrawlerTimeoutError(CrawlerError):
    def __init__(self, message: str, *, url: str | None = None):
        super().__init__(message)
        self.url = url


class CrawlerRetryExhaustedError(CrawlerError):
    def __init__(self, message: str, *, url: str | None = None, attempts: int = 0):
        super().__init__(message)
        self.url = url
        self.attempts = attempts
