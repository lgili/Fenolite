## MODIFIED Requirements

### Requirement: Fetch with verification
`tools/corpus_fetch.py` SHALL download every manifest item into `~/.cache/fenolite/corpus/<id>/`, verify the SHA-256, refuse to keep a file whose hash differs, and print a summary of fetched, cached and failed items.
- A download that the host answers with HTTP 429 or 500, 502, 503 or 504 MUST be asked again after a pause, at most six attempts in all: the pause is the server's `Retry-After` when it gives a number of seconds, else 5 s doubled at each attempt, and never more than 120 s. Any other error, or the error of the last attempt, counts the item as failed.

#### Scenario: Hash mismatch
- **GIVEN** a manifest entry whose `sha256` does not match the downloaded bytes
- **WHEN** `uv run python tools/corpus_fetch.py` runs
- **THEN** the file is deleted from the cache and the exit code is non-zero

#### Scenario: Rate limit asked again
- **GIVEN** a host that answers 429 with `Retry-After: 7`, then 503, then the file
- **WHEN** the fetch downloads the item
- **THEN** it waits 7 s and then 10 s, keeps the file, and a 404 is not asked again
