"""Repository-layer exceptions — docs/09 §6."""


class RepositoryError(Exception):
    """Base repository error."""


class RepositoryValidationError(RepositoryError):
    """ValidatedProduct missing required persist fields."""

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field
