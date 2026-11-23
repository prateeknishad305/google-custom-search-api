"""Errors of the Google web search client."""

from __future__ import annotations


class GoogleSearchError(RuntimeError):
    """Base class of every error of the client."""

    def __init__(self, message: str, *, status: int | None = None, payload: dict | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.payload = payload or {}


class InvalidRequestError(GoogleSearchError):
    """The request was refused (bad query, bad parameters)."""


class TransportError(GoogleSearchError):
    """Google could not be reached."""


class BlockedError(GoogleSearchError):
    """Google answered with a block, a challenge or a consent page."""


class RateLimitError(GoogleSearchError):
    """Google answered 429, the caller should slow down."""


class EmptyResultsError(GoogleSearchError):
    """The query answered without a single hit."""


# The name the first version of the package used, kept so that the old imports
# keep working.
CustomSearchError = GoogleSearchError

_STATUS_ERRORS = {
    400: InvalidRequestError,
    403: BlockedError,
    429: RateLimitError,
    503: BlockedError,
}


def error_for_status(status: int, message: str, payload: dict | None = None) -> GoogleSearchError:
    """Maps an HTTP status of Google to the error of the client."""

    if status in _STATUS_ERRORS:
        return _STATUS_ERRORS[status](message, status=status, payload=payload)
    return GoogleSearchError(message, status=status, payload=payload)
