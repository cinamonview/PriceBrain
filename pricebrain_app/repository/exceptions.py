"""Repository-layer exceptions — docs/09 §6."""


class RepositoryError(Exception):
    """Base repository error."""


class IdentityReviewBlockedError(RepositoryError):
    """Persist refused because collision review requires human review."""

    def __init__(
        self,
        message: str,
        *,
        canonical_product_id: str,
        review_reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.canonical_product_id = canonical_product_id
        self.review_reason = review_reason


class RepositoryValidationError(RepositoryError):
    """ValidatedProduct missing required persist fields."""

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class UnknownGpuModelError(RepositoryValidationError):
    """Parser produced a gpu_model_id absent from GPU master — quarantine, not discard.

    Subclasses RepositoryValidationError so existing callers keep their contract;
    callers that can quarantine must catch this first.
    """

    def __init__(self, message: str, *, gpu_model_id: str) -> None:
        super().__init__(message, field="gpu_model_id")
        self.gpu_model_id = gpu_model_id
