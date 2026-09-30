## Why

Fenolite is developed clean-room (ADR-0003): no design files, constants, seeds, fixtures, statistics, vocabularies, templates or examples belonging to or derived from any organisation's non-public material may enter the repository, even when such files were used privately to try an idea. Policy documents alone do not prevent leaks; this change makes the rules mechanical (tests, hooks, manifests) before any format code is written.

## What Changes

- `LEGAL.md` completed (blocks A and B in full), `LEGAL-ANNEX.md` session-log discipline made mandatory for work under `backends/` and `docs/formats/`, `PROVENANCE.md` required in every backend package (public sources read, with URL and date).
- ADR-0003 "Clean-room development and provenance of format knowledge".
- Residue scan `tests/residue/`: public **structural** patterns (`tools/residue/patterns.regex`: 9–10 digit numeric codes in fixtures, internal revision formats such as `v<digits>r<Letter>`, absolute user paths, cloud-drive paths), public `tools/residue/blobs.sha256` (hashes of whole artefacts known to be derived from non-public material), and a **private** token list read from `~/.fenolite-residue-tokens` or `FENOLITE_RESIDUE_TOKENS` (never committed, no hashed variant in the repo). Scope: working tree except `tests/corpus/cache`, built wheel, `docs/`, `openspec/`, `schemas/`, docstrings; tokenisation in UTF-8, UTF-16LE and cp1252; compound-file streams and XML payloads. Failure prints path and offset, never the token.
- `tests/unit/test_no_copyleft_deps.py`: closed list of copyleft package names that may never appear in `pyproject.toml` dependencies or extras.
- `tests/unit/test_no_ported_code.py`: forbids `Ported-From:` trailers/markers and any file header claiming origin in a non-public project (nothing is ported).
- Corpus policy: `tests/corpus/manifest.toml` schema (`url, ref, sha256, license, license_variant, embeddable, uses`), `tools/corpus_fetch.py` (download, verify SHA-256, cache under `~/.cache/fenolite/corpus`), pytest markers `needs_corpus`/`needs_libs` with clean skips, and the rule that only `embeddable = true` files (CC0 or equivalently permissive, or authored in-repo) may be committed.
- Git pre-commit hook script (`tools/hooks/pre-commit`, opt-in via `make hooks`) running the residue scan on staged files.

## Capabilities

### New Capabilities
- `ip-hygiene`: clean-room policy documents, provenance obligations, forbidden sources, copyleft-dependency and ported-code tests.
- `residue-scan`: the scan engine, its public/private pattern sources, scope, failure semantics, hook and CI integration.
- `corpus-policy`: the corpus manifest, fetch tool, skip markers and the embeddable rule.

### Modified Capabilities
- (none)

## Non-goals

- Deciding legal questions (the ADR records the project's decision; legal advice is the author's business).
- Any actual corpus file: the manifest starts empty and is populated by the KiCad backend changes.
- Licence-compatibility scanning of transitive dependencies (the core has none; extras are permissive by construction).

## Evidence level required

- Mechanical: residue scan, copyleft test, ported-code test and manifest validation green on CI and on the private runner (the private token list is a release gate documented but not published).

## Impact

- Every later change ends with `pytest tests/residue`; backend PRs must add `PROVENANCE.md` rows and `LEGAL-ANNEX.md` sessions.
- `pyproject.toml` gains no dependency; `tools/` gains three scripts; CI gains the residue step inside the `unit` job.
