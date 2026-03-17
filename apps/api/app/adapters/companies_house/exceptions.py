"""
Companies House adapter exceptions.

All exceptions raised by the adapter inherit from CompaniesHouseError so
callers can catch the base class or specific sub-classes as needed.

Not-retryable:
  CHNotFoundError  — 404, resource does not exist
  CHAuthError      — 401, invalid or missing API key
  CHRequestError   — network or timeout error (after retry exhausted)

Retryable (raised only after all retries are exhausted):
  CHRateLimitError  — 429, rate limit hit
  CHUpstreamError   — 5xx, upstream service error
"""


class CompaniesHouseError(Exception):
    """Base exception for all Companies House adapter errors."""


class CHNotFoundError(CompaniesHouseError):
    """HTTP 404 — the requested Companies House resource does not exist."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Companies House resource not found: {path}")
        self.path = path


class CHRateLimitError(CompaniesHouseError):
    """
    HTTP 429 — rate limit exceeded.

    retry_after is the value from the Retry-After response header (seconds),
    or 60 seconds if the header was absent.
    """

    def __init__(self, retry_after: int = 60) -> None:
        super().__init__(
            f"Companies House rate limit exceeded. Retry after {retry_after}s."
        )
        self.retry_after = retry_after


class CHAuthError(CompaniesHouseError):
    """HTTP 401 — invalid or missing Companies House API key."""

    def __init__(self) -> None:
        super().__init__(
            "Companies House API authentication failed. "
            "Check CH_API_KEY is set and valid."
        )


class CHUpstreamError(CompaniesHouseError):
    """HTTP 5xx — Companies House server error."""

    def __init__(self, status_code: int, detail: str = "") -> None:
        super().__init__(
            f"Companies House upstream error (HTTP {status_code}): {detail}"
        )
        self.status_code = status_code


class CHRequestError(CompaniesHouseError):
    """Network error, timeout, or unexpected transport failure."""
