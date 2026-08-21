"""Pipeline validation exceptions — docs/08 §22–§23."""

from __future__ import annotations

from enum import Enum


class ValidationStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    WARNING = "WARNING"
    FILTERED = "FILTERED"


class PipelineValidationError(Exception):
    """Validation failure — data must not pass silently (docs/08 §22)."""

    def __init__(
        self,
        message: str,
        *,
        status: ValidationStatus = ValidationStatus.INVALID,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.field = field


class GpuProductFilteredError(PipelineValidationError):
    """Non-GPU product filtered out — docs/08 §24."""

    def __init__(self, message: str, *, field: str | None = "gpu") -> None:
        super().__init__(message, status=ValidationStatus.FILTERED, field=field)
