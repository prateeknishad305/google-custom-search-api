# Google Web Search API

A standalone Python client and a small HTTP service for the **web search of
Google**.

There is no API key and no search engine id: a full web search is a request to
the result page of Google, the client reads the hits out of the answer itself
and puts the exact destination of every hit in the answer. The package does
not call the Node renderer, it has its own parser, its own browser and its own
pool of exits.

```json
{
  "engine": "google",
  "source": "google",
  "query": "rust async runtime",
  "count": 2,
  "results": [
    {
      "title": "The Async Ecosystem",
      "url": "https://rust-lang.github.io/async-book/08_ecosystem/00_chapter.html",
      "snippet": "A chapter about async.",
      "rank": 1,
      "resolved": true,
      "source": "google"
    }
  ]
}
```

## What it does

- **Its own parser.** The cards of the result page are read with `lxml`, the
  destination of a hit is unwrapped from the link of Google and the hits whose
  cite is cut off are matched against the inline destinations of the page.
- **Its own browser.** The page of the result is rendered with Chromium
  (camoufox is the second choice), with the cookies of the consent, with the
  traces of the automation hidden and with the exit of the request on the
  context.
- **Its own pool of exits.** Google blocks the address of a data centre fast.
  The client asks a few exits at the same time and the first exit that answers
  with hits wins.
- **Async first.** The client is built on `httpx.AsyncClient` and
  `playwright`, the pages of a long answer are asked at the same time and the
  browser is opened once for the whole search.
- **Clean errors.** `GoogleSearchError` is the base of `InvalidRequestError`,
  `TransportError`, `BlockedError`, `RateLimitError` and `EmptyResultsError`.
- **A service with the shape of the renderer.** `GET /api/search?q=...&num=...`
  answers with the same fields as the Node renderer, `GET /health` says whether
  the service is ready.

## Install

```bash
# Install the dependencies
pip install -r requirements.txt

# Install the package itself
pip install -e .
```

The browser needs Playwright and a Chromium of the system:

```bash
# Install Playwright
pip install "google-custom-search-api[browser]"
```

For the tests:

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Configure

Every setting is an environment variable, `.env.example` holds the whole list:

| Variable | Meaning |
| --- | --- |
| `GOOGLE_SEARCH_ENDPOINT` | The result page of Google |
| `GOOGLE_SEARCH_TIMEOUT` | The timeout of one request in seconds |
| `GOOGLE_SEARCH_MAX_RESULTS` | The highest number of hits one search may answer |
| `GOOGLE_SEARCH_PROXY` | The exit of the request |
| `GOOGLE_SEARCH_HL` / `GOOGLE_SEARCH_GL` | The language and the country of the hits |
| `GOOGLE_SEARCH_MAX_CONCURRENCY` | How many pages are asked at the same time |
| `GOOGLE_SEARCH_MODE` | `browser`, `http` or `auto` |
| `GOOGLE_SEARCH_BROWSER` | `chromium` or `firefox` |
| `GOOGLE_SEARCH_BROWSER_PATH` | The binary of the browser, empty picks the default |
| `GOOGLE_SEARCH_POOL` | The list of the exits |
| `GOOGLE_SEARCH_EXITS` | How many exits one search may ask |
| `GOOGLE_SEARCH_RACE` | How many exits are asked at the same time |

## Use it in the code

```python
import asyncio

from google_custom_search import GoogleSearchClient


async def main():
    async with GoogleSearchClient() as client:
        answer = await client.search("rust async runtime", num=25)
        for hit in answer.hits:
            print(hit.rank, hit.title, hit.url)


asyncio.run(main())
```

The search understands the operators of Google and keeps the contract of the
site operator:

```python
answer = await client.search("async runtime site:github.com", num=20)
answer = await client.search("report", site="arxiv.org", file_type="pdf")
```

## Use it as a service

```bash
# Start the service
uvicorn google_custom_search.server:app --host 0.0.0.0 --port 8080
```

```bash
# Ask for hits
curl "http://127.0.0.1:8080/api/search?q=rust+async+runtime&num=10"

# Ask the health of the service
curl "http://127.0.0.1:8080/health"
```

## Use it from the shell

```bash
# Print the hits
google-custom-search --query "rust async runtime" --num 10

# Print the answer as JSON
google-custom-search --query "rust async runtime" --num 10 --json
```

## The modules

| Module | What it holds |
| --- | --- |
| `google_custom_search/client.py` | The client: the parameters, the pages, the race of the exits |
| `google_custom_search/fetchers.py` | The plain request and the browser that renders the page |
| `google_custom_search/parser.py` | The cards of the page, the destinations, the cites |
| `google_custom_search/dork.py` | The operators of Google and the contract of the site operator |
| `google_custom_search/pool.py` | The list of the exits and the health of the exits |
| `google_custom_search/models.py` | `SearchHit` and `SearchResponse` |
| `google_custom_search/errors.py` | The errors of the client |
| `google_custom_search/server.py` | The service |
| `google_custom_search/cli.py` | The command line |

## Tests

```bash
pytest -q
```

The tests of the parser, of the client and of the service run without a
network.

## Note

The search of Google is the result page of Google, and Google changes that page
and the way it blocks automated traffic from time to time. The client answers
with an error when Google blocks the request (`BlockedError`), it never makes
up a hit.

## License

MIT, see `LICENSE`.
