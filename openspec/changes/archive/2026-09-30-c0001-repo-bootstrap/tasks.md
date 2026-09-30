## 1. Package skeleton

- [x] 1.1 Create `pyproject.toml` (hatchling, `name = "fenolite"`, `requires-python = ">=3.11"`, `dependencies = []`, extras `geo`, `kicad-ipc`, `route`, `mcp`, `dev`, `oracles`, console script `fenolite`, ruff/pyright/pytest config with markers `needs_kicad`, `needs_corpus`, `needs_libs`, `slow`). Proof: `uv sync --extra dev`.
- [x] 1.2 Create `src/fenolite/__init__.py` (`__version__ = "0.0.1.dev0"`), `src/fenolite/__main__.py`, `src/fenolite/cli/__init__.py`, `src/fenolite/cli/main.py` stub with `--version`/`--help` only. Proof: `uv run fenolite --version` and `uv run python -m fenolite --version` print `fenolite 0.0.1.dev0`.
- [x] 1.3 Create the directory layout (`tests/unit`, `docs/adr`, `docs/evidence`, `docs/formats`, `tools`, `schemas`, `examples`, `verify_results`) each with `README.md` or `.gitkeep`; write `.gitignore`. Proof: `uv run pytest tests/unit/test_repo_layout.py`; `git check-ignore private/x` succeeds.
- [x] 1.4 Write `tests/unit/test_pyproject_invariants.py` (empty `dependencies`, closed extras list) and `tests/unit/test_repo_layout.py`. Proof: `uv run pytest tests/unit -q`.

## 2. Licensing and notices

- [x] 2.1 Add `LICENSE` (Apache-2.0 verbatim), `NOTICE` (project line only), `license`/`license-files` in `pyproject.toml`. Proof: `uv build` then `unzip -p dist/*.whl '*/METADATA' | grep License-Expression`.
- [x] 2.2 Add SPDX + copyright header to every `.py` file and write `tests/unit/test_spdx_headers.py` (exempt `schemas/`, `tools/residue/`). Proof: `uv run pytest tests/unit/test_spdx_headers.py`.
- [x] 2.3 Write `LEGAL.md` (blocks A and B as specified), `LEGAL-ANNEX.md` (empty session-log table), `CONTRIBUTING.md` (DCO, conventional commits, "one change per PR", OpenSpec workflow) and `tests/unit/test_legal_docs.py`. Proof: `uv run pytest tests/unit/test_legal_docs.py`.
- [x] 2.4 Write `docs/adr/0004-licence-apache-2.0.md` (MADR-lite; process-boundary rule for copyleft), `docs/adr/README.md` (template) and `tests/unit/test_adrs.py`. Proof: `uv run pytest tests/unit/test_adrs.py`.

## 3. Documentation and evidence scaffolding

- [x] 3.1 Write `README.md` (positioning, status "pre-alpha", install, the evidence-label vocabulary, link to `LEGAL.md`), `AGENTS.md` (repo rules for AI agents: OpenSpec-first, clean-room, no company data, run `make check`, one fix per iteration) and `CHANGELOG.md` (Keep a Changelog, `## [Unreleased]`). Proof: human review; files exist.
- [x] 3.2 Create `docs/evidence/sources.md` (columns: id, URL, source licence, used for, date consulted) and `docs/hypotheses.md` (columns: id, backend, statement, level, test or kit request, criterion, result, date), both with headers only. Proof: `grep -c '|' docs/evidence/sources.md docs/hypotheses.md`.

## 4. CI baseline

- [x] 4.1 Add `.github/workflows/ci.yml` (`unit` job, ubuntu + macos × 3.12, `astral-sh/setup-uv`, `uv sync --locked --extra dev`, ruff check, ruff format --check, pyright src, pytest) and commit `uv.lock`. Proof: workflow green on both runners. _(Verified: the first GitHub runs on `main` and on tag `v0.0.1.dev0` passed on ubuntu and macos, 2026-09-30.)_
- [x] 4.2 Add `Makefile` target `check` running the same four steps. Proof: `make check` exits 0 locally.

## 5. Name reservation (manual, author)

- [x] 5.1 Prepare the name reservation: alias distribution `packaging/phenolite/` (depends on `fenolite==<same version>`, re-exports `fenolite`, README pointing to Fenolite, version kept in sync by `tests/unit/test_pyproject_invariants.py`) and `.github/workflows/release.yml` (builds both, checks versions against the tag, publishes with PyPI trusted publishing when a GitHub Release is published). Proof: `uv build` and `uv build packaging/phenolite` succeed; installing the `phenolite` wheel in a clean venv installs `fenolite` and `import phenolite` works.
- [x] 5.2 (author, on pypi.org) Register a pending trusted publisher for `fenolite` and for `phenolite` (owner `lgili`, repository `Fenolite`, workflow `release.yml`, environment `pypi`), then publish the GitHub Release `v0.0.1.dev0`; record the date in `CHANGELOG.md`. Proof: `pip index versions fenolite` and `pip index versions phenolite` list `0.0.1.dev0`. _(Verified on pypi.org: both published 2026-09-30 by the `release` workflow; `phenolite` requires `fenolite==0.0.1.dev0`.)_

## 6. Closing

- [x] 6.1 Run the residue scan once `c0003-ip-hygiene` lands (until then: `grep -rniE 'private/|/Users/' src tests docs` must return nothing). Proof: empty grep output. _(Done with an interim scan over all non-ignored files for absolute user paths, cloud-drive paths and a private token list held outside the repo: no hits.)_
- [x] 6.2 Update evidence labels: none to update (no behaviour); note in `docs/hypotheses.md` that the register is empty by design. Proof: file unchanged except the note.
- [x] 6.3 Add the `## [Unreleased]` entry "Repository bootstrap: package skeleton, Apache-2.0, CI baseline" to `CHANGELOG.md`. Proof: `git diff CHANGELOG.md`.
