## Context

Two contamination paths exist: (1) material from an organisation's non-public files entering the tree (files, byte blobs, constants measured on private files, vocabularies, parameter names, identifiers, paths); (2) copyleft or restrictively licensed code entering an Apache-2.0 package (GPL parsers, AGPL tools, CC-BY-SA library collections). Both must be blocked by tests that run on every commit, without the tests themselves revealing what they block.

## Goals / Non-Goals

**Goals:**
- Make the clean-room decision explicit and auditable (ADR-0003, `LEGAL.md`, `LEGAL-ANNEX.md`, `PROVENANCE.md`).
- Block leaks mechanically: residue scan (public structural patterns + public blob hashes + private token list), copyleft-dependency test, ported-code test, embeddable rule on corpus files.
- Keep the public repository free of any list that would itself disclose private identifiers.

**Non-Goals:**
- Populating the corpus (later changes).
- Static licence scanning of extras' transitive trees.

## Decisions

1. **No token denylist in the public repository, hashed or not.** A salted hash list with a public salt is a dictionary oracle for low-entropy tokens (organisation names, parameter names). Therefore the repo carries only: (a) `tools/residue/patterns.regex` — structural regexes that reveal nothing specific (`\b\d{9,10}\b` in fixture files, `\bv\d+r[A-Z]\b`, `/Users/[^/\s]+/`, `Shared drives`, `[A-Z]:\\Users\\`); (b) `tools/residue/blobs.sha256` — SHA-256 of whole artefacts (high entropy, not reversible). The private token list lives in `~/.fenolite-residue-tokens` (one token per line, case-insensitive) or in the `FENOLITE_RESIDUE_TOKENS` environment variable, is read by the scan when present, and is used by a private pre-release runner; CI documents that a private gate exists without disclosing its content.
2. **Scan engine** `tools/residue/scan.py` (stdlib-only, also importable by tests): walks the tree (excluding `.git`, `.venv`, `tests/corpus/cache`, `private/`), the built wheel when present (`dist/*.whl` unzipped in memory), and decodes each file three ways (UTF-8, UTF-16LE, cp1252) before matching; for compound files (OLE, signature `D0 CF 11 E0`) it additionally scans the raw bytes; for `.zip`-based artefacts it scans entries. Output: `path:offset:pattern-id`, never the matched text; exit 5 on any hit, mirroring the "findings" exit code.
3. **Scope rules** in `tools/residue/scope.toml`: everything is scanned except explicitly listed paths; `tests/data/` and `examples/` are scanned with the numeric-code pattern enabled; source code is scanned for tokens and paths only (numeric codes are legitimate in code).
4. **Copyleft dependency test.** `tests/unit/test_no_copyleft_deps.py` parses `pyproject.toml` and fails if any dependency or extra names a package in a closed list kept in the test (`altium-monkey`, `altium-cruncher`, `easyeda2kicad`, `kiutils`, `kicad-skip`, `kicad-library-tools`, `KicadModTree`, `cgal`, `lcapy`, `freerouting` jar wrappers that vendor the jar). The list is a public statement of the process-boundary rule from ADR-0004, so it may be public.
5. **Ported-code test.** `tests/unit/test_no_ported_code.py` greps `git log` trailers for `Ported-From:` and source headers for `Ported from` / `Derived from` markers pointing at non-public projects, and fails on any match. Under the clean-room decision the only acceptable derivation notes are for public works listed in `NOTICE`.
6. **Provenance obligations.** Every package under `src/fenolite/backends/<x>/` MUST contain `PROVENANCE.md` with a table `fact-or-area | public source (URL) | licence of source | date | how used (facts only / design with attribution)`; `tests/unit/test_provenance.py` fails if a backend package lacks the file or if a `docs/formats/<x>/*.md` page cites no source. `LEGAL-ANNEX.md` must gain one row per working session on `backends/` or `docs/formats/` (`date | area | files touched | public sources consulted | author`); the test checks that the annex has at least one row per calendar week in which those paths changed (from `git log`).
7. **Forbidden sources, stated once in `LEGAL.md` block A:** decompiling or disassembling vendor software; transcribing, compiling or converting GPL/AGPL parser sources or machine-readable grammar files into Fenolite code (reading them for facts is allowed and must be logged); using files one is not entitled to read; using an employer's software licence for reverse engineering.
8. **Corpus manifest** `tests/corpus/manifest.toml`: one `[[file]]` table per item with `id`, `url`, `ref` (tag or commit), `sha256`, `license` (SPDX id), `license_variant` (free text, e.g. which reciprocal variant), `embeddable` (bool), `uses` (list of test purposes), `notes`. `tools/corpus_fetch.py` downloads into `~/.cache/fenolite/corpus/<id>/`, verifies SHA-256, and refuses files whose `sha256` is missing. `tests/corpus/test_manifest.py` validates the schema and asserts that every file committed under `tests/data/` either is authored in-repo (`origin = "authored"` in a sidecar `tests/data/MANIFEST.toml`) or references a manifest item with `embeddable = true`.
9. **Embeddable rule:** only CC0-1.0, or content authored for Fenolite, or files explicitly dedicated to the public domain may be committed; reciprocal or share-alike licences (any CERN-OHL variant other than P, CC-BY-SA, GPL-repository files) are fetch-only measurement material. `license = "CC0-1.0"` or `origin = "authored"` is the only way to get `embeddable = true`.
10. **Skip markers:** `needs_corpus` skips with the message "run `uv run python tools/corpus_fetch.py`" when the cache is absent; `needs_libs` skips when neither `KICAD10_SYMBOL_DIR` nor a fetched library tag is present.
11. **Hook:** `tools/hooks/pre-commit` runs `scan.py --staged`; installed by `make hooks` (opt-in, symlink into `.git/hooks`).

## Risks / Trade-offs

- [Structural patterns produce false positives on legitimate 9–10 digit numbers in examples] → pattern applies only to fixture/example paths and can be waived per file with a `# residue: allow-numeric` sidecar entry in `scope.toml`, reviewed in PR.
- [Private token list drifts between machines] → the pre-release runner is the source of truth; contributors without the list still get the structural scan.
- [Provenance tests become bureaucratic] → rows are one line each; the weekly-session check only fires when backend paths changed.
- [Contributors misread "facts only" and transcribe code] → `CONTRIBUTING.md` gives the concrete rule with an example of allowed (a documented offset) vs forbidden (a copied function).

## Migration Plan

- Retroactively apply the scan to the whole history at the first tag (`git log --all` file contents), so the public history is clean from the start.

## Open Questions

- Should `LEGAL-ANNEX.md` rows be enforced by CI or only by the PR checklist? Default: CI enforces existence per week; content is reviewed by humans.

## Evidence level required before merge

- Mechanical: `pytest tests/residue tests/unit/test_no_copyleft_deps.py tests/unit/test_no_ported_code.py tests/unit/test_provenance.py tests/corpus/test_manifest.py` green; hook installed and exercised once with a planted structural hit.
