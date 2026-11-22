"""A thin client and service for the Google Custom Search JSON API."""

from .client import GoogleCustomSearchClient
from .config import ConfigurationError, Settings
from .errors import (
    AuthenticationError,
    CustomSearchError,
    EmptyResultsError,
    InvalidRequestError,
    QuotaError,
    RateLimitError,
    TransportError,
)
from .models import SearchHit, SearchResponse

__version__ = "1.0.0"

__all__ = [
    "GoogleCustomSearchClient",
    "SearchHit",
    "SearchResponse",
    "Settings",
    "ConfigurationError",
    "CustomSearchError",
    "AuthenticationError",
    "InvalidRequestError",
    "QuotaError",
    "RateLimitError",
    "TransportError",
    "EmptyResultsError",
    "__version__",
]
