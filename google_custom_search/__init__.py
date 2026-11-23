"""A Python client and a small service for the web search of Google.

Google has no API for a full web search any more, the answer comes from the
result page itself. This package asks that page, reads the hits out of it and
puts the exact destination of every hit in the answer.
"""

from .client import GoogleSearchClient
from .config import ConfigurationError, Settings
from .errors import (
    BlockedError,
    EmptyResultsError,
    GoogleSearchError,
    InvalidRequestError,
    RateLimitError,
    TransportError,
)
from .models import SearchHit, SearchResponse

# The name the first version of the package used, kept so that the old imports
# keep working.
GoogleCustomSearchClient = GoogleSearchClient
CustomSearchError = GoogleSearchError

__version__ = "2.0.0"

__all__ = [
    "GoogleSearchClient",
    "GoogleCustomSearchClient",
    "SearchHit",
    "SearchResponse",
    "Settings",
    "ConfigurationError",
    "GoogleSearchError",
    "CustomSearchError",
    "InvalidRequestError",
    "BlockedError",
    "RateLimitError",
    "TransportError",
    "EmptyResultsError",
    "__version__",
]
