# Progress

## 2026-11-23 - standalone Google web search client

The package was the client of the Custom Search JSON API. It is now a
standalone client of the web search of Google: no API key, no search engine id,
its own parser, its own browser, its own pool of exits. It does not call the
Node renderer of `gsearch-renderer`.

### Modules

| Module | What it does | State |
| --- | --- | --- |
| `google_custom_search/client.py` | Parameters of the result page, the pages in parallel, the race of the exits, the contract of the site operator | done |
| `google_custom_search/fetchers.py` | `HttpFetcher` (httpx) and `BrowserFetcher` (Chromium, camoufox as the second choice) | done |
| `google_custom_search/parser.py` | Cards of the page, unwrapping of the links of Google, inline destinations, cites | done |
| `google_custom_search/dork.py` | Operators of Google, the site targets, the client side contract | done |
| `google_custom_search/pool.py` | The list of the exits, the health of the exits, the rotation | done |
| `google_custom_search/models.py` | `SearchHit`, `SearchResponse` | done |
| `google_custom_search/errors.py` | `GoogleSearchError`, `InvalidRequestError`, `TransportError`, `BlockedError`, `RateLimitError`, `EmptyResultsError` | done |
| `google_custom_search/config.py` | The settings of the environment | done |
| `google_custom_search/server.py` | `GET /api/search`, `GET /health`, one client for the whole service | done |
| `google_custom_search/cli.py` | The command line | done |
| `google_custom_search/__init__.py` | The exports, `GoogleSearchClient` and `GoogleCustomSearchClient` | done |

### Endpoints

| Endpoint | Method | Answer | State |
| --- | --- | --- | --- |
| `/api/search` | GET | The hits of the result page of Google, the shape of the renderer | done |
| `/health` | GET | The state of the service | done |

### Tests

- `tests/test_parser.py` - 11 tests of the parser.
- `tests/test_client.py` - 8 tests of the client.
- `tests/test_server.py` - 4 tests of the service.
- `pytest -q` - 23 passed.

### Live state from this machine

- The plain request (`HttpFetcher`) answers with the shell of the page of
  Google, no hits: the path of the plain request is dead.
- The browser (`BrowserFetcher`, Chromium 156) renders the page, the exits of
  the pool answer, but Google answers with the challenge of the traffic
  ("unusual traffic", `/sorry/index`) from this address.
- The Node renderer of `gsearch-renderer` answers with hits through the same
  exits, the difference between the two browser setups is still open.
