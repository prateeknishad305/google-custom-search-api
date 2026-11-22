# Google Custom Search API

A small Python client and a small HTTP service for the **Google Custom Search
JSON API** (`customsearch/v1`).

The answer has the same shape as the renderer of the Node project
[`gsearch-renderer`](https://github.com/prateeknishad305/gsearch-renderer), so
a caller can switch between both without touching the rest of the code:

```json
{
  "engine": "google_cse",
  "query": "rust async runtime",
  "count": 2,
  "results": [
    {
      "title": "The Async Ecosystem",
      "url": "https://rust-lang.github.io/async-book/08_ecosystem/00_chapter.html",
      "snippet": "A chapter about async.",
      "rank": 1
    }
  ]
}
```

## What it does

- **One request, ten hits.** The API answers ten hits per request. A search of
  more hits is more than one request, and those requests do not depend on each
  other: they are sent at the same time.
- **Async first.** The client is built on `httpx.AsyncClient`, the pages of a
  long answer are gathered with `asyncio.gather` and the connection pool is
  reused between the searches.
- **Clean errors.** The status of the API is mapped to an error of the client:
  `AuthenticationError`, `InvalidRequestError`, `QuotaError`, `RateLimitError`,
  `TransportError` and `EmptyResultsError`.
- **A service with the shape of the renderer.** `GET /api/search?q=...&num=...`
  answers with the same fields as the Node renderer, `GET /health` says whether
  the service has the credentials it needs.

## Install

```bash
# Install the dependencies
pip install -r requirements.txt

# Install the package itself
pip install -e .
```

For the tests:

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Configure

The service needs an API key and the id of a programmable search engine. Both
belong to the operator of the service, they are read from the environment and
are never part of the source tree:

```bash
export GOOGLE_CSE_API_KEY=your-api-key-here
export GOOGLE_CSE_CX=your-search-engine-id-here
```

`.env.example` holds the whole list of the settings:

| Variable | Meaning | Default |
| --- | --- | --- |
| `GOOGLE_CSE_API_KEY` | the key of the Custom Search JSON API | required |
| `GOOGLE_CSE_CX` | the id of the programmable search engine | required |
| `GOOGLE_CSE_ENDPOINT` | the endpoint of the API | `https://www.googleapis.com/customsearch/v1` |
| `GOOGLE_CSE_TIMEOUT` | the timeout of one request in seconds | `10` |
| `GOOGLE_CSE_MAX_RESULTS` | the highest number of hits one search may answer with | `100` |

## Use the client

```python
import asyncio

from google_custom_search import GoogleCustomSearchClient


async def main() -> None:
    client = GoogleCustomSearchClient(api_key="...", cx="...")
    answer = await client.search("rust async runtime", num=25)
    for hit in answer.hits:
        print(hit.rank, hit.url)
    await client.aclose()


asyncio.run(main())
```

The filters of the API are parameters of the search:

```python
answer = await client.search(
    "async runtime",
    num=20,
    site_search="github.com",   # only the hits of this host
    file_type="pdf",            # only the hits of this file type
    language="en",              # lr
    country="us",               # gl
    safe="active",
    date_restrict="m1",         # d1, w1, m1, y1
)
```

Several queries at once:

```python
answers = await client.search_many(["rust async", "tokio tutorial"], num=10)
```

## Use the service

```bash
# Start the service
uvicorn google_custom_search.server:app --host 0.0.0.0 --port 8000

# Search
curl "http://127.0.0.1:8000/api/search?q=rust+async+runtime&num=10"

# Search with the filters
curl "http://127.0.0.1:8000/api/search?q=rust+async&site=github.com&filetype=pdf"

# The state of the service
curl "http://127.0.0.1:8000/health"
```

## Use the command line

```bash
python -m google_custom_search.cli "rust async runtime" --num 20
python -m google_custom_search.cli "rust async runtime" --site github.com --json
```

## Layout

```
google_custom_search/
├── __init__.py    the public API of the package
├── cli.py         the command line
├── client.py      the client of the Custom Search JSON API
├── config.py      the settings of the service
├── errors.py      the errors of the client
├── models.py      the hits and the answer
└── server.py      the HTTP service (FastAPI)
tests/
├── test_client.py
└── test_server.py
```

## License

MIT
