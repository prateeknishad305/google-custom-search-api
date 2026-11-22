"""Errors of the Custom Search JSON API client."""

from __future__ import annotations


class CustomSearchError(RuntimeError):
    """Base class of every error of the client."""

    def __init__(self, message: str, *, status: int | None = None, payload: dict | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.payload = payload or {}


class InvalidRequestError(CustomSearchError):
    """The request was refused by the API (bad query, bad parameters)."""


class AuthenticationError(CustomSearchError):
    """The API key is missing, wrong or not allowed to use this engine."""


class QuotaError(CustomSearchError):
    """The daily quota of the API key is used up."""


class RateLimitError(CustomSearchError):
    """The API answered 429, the caller should slow down."""


class TransportError(CustomSearchError):
    """The API could not be reached."""


class EmptyResultsError(CustomSearchError):
    """The query answered without a single hit."""


_STATUS_ERRORS = {
    400: InvalidRequestError,
    401: AuthenticationError,
    403: AuthenticationError,
    429: RateLimitError,
}


def error_for_status(status: int, message: str, payload: dict | None = None) -> CustomSearchError:
    """Maps an HTTP status of the API to the error of the client."""

    if status in _STATUS_ERRORS:
        if status == 429:
            return QuotaError(message, status=status, payload=payload)
        return _STATUS_ERRORS[status](message, status=status, payload=payload)
    return CustomSearchError(message, status=status, payload=payload)
