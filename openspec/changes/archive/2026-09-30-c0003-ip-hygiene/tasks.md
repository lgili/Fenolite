## 1. Policy documents

- [x] 1.1 Write `docs/adr/0003-clean-room-and-provenance.md` (Status Accepted; context; decision; alternatives considered; consequences; evidence = `docs/evidence/sources.md`). Proof: `uv run pytest tests/unit/test_adrs.py`.
- [x] 1.2 Complete `LEGAL.md` block A (four prohibitions, "facts with source" rule) and block B (clean-room statement about material from organisations), and `CONTRIBUTING.md` section "Allowed vs forbidden derivation" with one concrete example each. Proof: `uv run pytest tests/unit/test_legal_docs.py`.
- [x] 1.3 Define the `PROVENANCE.md` table format and the `LEGAL-ANNEX.md` weekly-session rule in `docs/provenance.md`; write `tests/unit/test_provenance.py` (backend packages, docs/formats pages, weekly rows from `git log`). Proof: `uv run pytest tests/unit/test_provenance.py`.

## 2. Residue scan

- [x] 2.1 Write `tools/residue/patterns.regex` (structural patterns with ids: `numeric-code`, `internal-rev`, `abs-user-path`, `cloud-drive-path`, `win-user-path`) and `tools/residue/scope.toml` (exclusions, per-path pattern sets, waivers with justification). Proof: file review; `uv run python tools/residue/scan.py --list-patterns`.
- [x] 2.2 Implement `tools/residue/scan.py` (tree/staged/wheel walkers; UTF-8/UTF-16LE/cp1252 decoding; compound-file raw scan; zip entries; blob hashes; private token list from file or env; `path:offset:pattern-id` output; exit 0/5; waiver count). Proof: `uv run pytest tests/residue/test_scan.py` with planted fixtures under `tests/residue/fixtures/`. _(Planted trees are generated at run time in a temporary directory instead of committed fixtures, so the repository scan never sees them; planted strings are assembled at run time for the same reason.)_
- [x] 2.3 Write `tests/residue/test_repo_clean.py` (runs the scan on the tree; fails on hits), `tests/residue/test_no_token_list.py` (rejects any token list, hashed or plain, under `tools/`), `tests/residue/test_official_libs.py` (byte-identity against fetched official KiCad library items when the cache is present). Proof: `uv run pytest tests/residue -q`.
- [x] 2.4 Add `tools/hooks/pre-commit` and the `make hooks` target; add the residue step to the CI `unit` job. Proof: plant a structural hit, `git commit` refused; CI step visible in the workflow run. _(Proved by `tests/residue/test_hook.py` in a throwaway repository; the hook is not installed in this checkout until `make hooks` is run.)_

## 3. Dependency and ported-code guards

- [x] 3.1 Write `tests/unit/test_no_copyleft_deps.py` with the closed copyleft list. Proof: temporarily add `kiutils` to an extra → test fails; revert.
- [x] 3.2 Write `tests/unit/test_no_ported_code.py` (git trailers `Ported-From:`; source markers). Proof: `uv run pytest tests/unit/test_no_ported_code.py`.

## 4. Corpus policy

- [x] 4.1 Write `tests/corpus/manifest.toml` (headers and schema comment, zero entries), `tests/data/MANIFEST.toml` (`origin = "authored"` declarations, empty), and `tests/corpus/test_manifest.py` (schema, embeddable rule, tests/data cross-check). Proof: `uv run pytest tests/corpus/test_manifest.py`.
- [x] 4.2 Implement `tools/corpus_fetch.py` (download by `url`+`ref`, SHA-256 verification, cache dir, summary, non-zero exit on mismatch). Proof: `uv run python tools/corpus_fetch.py` on an empty manifest exits 0; unit test with a local `file://` fixture and a wrong hash exits non-zero.
- [x] 4.3 Add `needs_corpus` and `needs_libs` skip logic in `tests/conftest.py` with the prescribed messages. Proof: `uv run pytest -m needs_corpus -q` shows skips with the message.

## 5. History hygiene

- [x] 5.1 Run the scan over the full git history (`uv run python tools/residue/scan.py --history` with the private lists) right before the first tag, `v0.0.1.dev0`; document the result in `docs/evidence/residue-history.md`. Proof: file lists commit range and `0 hits`.

## 6. Closing

- [x] 6.1 Run `uv run pytest tests/residue`. Proof: exit 0.
- [x] 6.2 Update evidence labels: none (policy change); add the `residue` step to the CI description in `README.md`. Proof: review.
- [x] 6.3 `CHANGELOG.md`: "IP hygiene: clean-room ADR, residue scan, copyleft and ported-code guards, corpus policy". Proof: `git diff CHANGELOG.md`.
