## Context

Fenolite is a new open-source Python library and CLI for PCB design automation (KiCad first, Altium second, agent-first). The repository is empty except for the OpenSpec scaffold. The project has three hard rules that must be enforced from commit one: the core has zero runtime dependencies, the licence is Apache-2.0 with copyleft software only behind process boundaries, and nothing derived from any organisation's non-public material enters the tree (clean-room). This change lays the skeleton those rules hang on.

## Goals / Non-Goals

**Goals:**
- A `pip`-installable, importable package with a working `fenolite --version` entry point.
- Licensing, notice and legal scaffolding present before any format code exists.
- A CI baseline that fails on lint, type or test errors on ubuntu and macos.
- Documentation stubs that later changes fill: ADRs, evidence sources, hypotheses register, changelog, agent guide.

**Non-Goals:**
- Any EDA behaviour (model, backends, checks).
- The CLI output contract (`c0002-cli-contract`), the residue scan and corpus policy (`c0003-ip-hygiene`), the design model (`c0004-design-model-core`).
- Windows CI, wheel job, Docker `kicad-cli` jobs (later changes in v0.1).

## Decisions

1. **src layout with `hatchling` as build backend.** Files: `pyproject.toml`, `src/fenolite/__init__.py` (`__version__`), `src/fenolite/__main__.py`, `src/fenolite/cli/main.py` (temporary stub replaced by `c0002`). Alternatives: flat layout (rejected: test imports leak the working tree), `setuptools` (works, but hatchling needs less configuration), `uv_build` (young; revisit at 1.0).
2. **Version single-sourced in `src/fenolite/__init__.py`** and read by hatchling (`[tool.hatch.version] path = "src/fenolite/__init__.py"`). `fenolite --version` prints `fenolite <version>`.
3. **`dependencies = []` is a tested invariant**, not a convention: `tests/unit/test_pyproject_invariants.py` parses `pyproject.toml` with `tomllib` and asserts the list is empty and that only the declared extras exist (`geo`, `kicad-ipc`, `route`, `mcp`, `dev`, `oracles`). Extras content in this change: `dev = [pytest, pytest-xdist, hypothesis, ruff, pyright]`; `geo = [shapely>=2.1, pyclipper]`; `kicad-ipc = [kicad-python]`; `route = [freerouting-client]`; `mcp = [mcp]`; `oracles = [gerbonara, pygerber]`. Copyleft tools never appear here (enforced by `c0003`).
4. **Tooling:** `uv` for environments and lockfile (`uv.lock` committed); `ruff` (lint + format, line length 110, rules E/F/W/I/B/UP); `pyright` in `strict` mode on `src/` only; `pytest` with `testpaths = ["tests"]`, markers `needs_kicad`, `needs_corpus`, `needs_libs`, `slow` declared now so later changes only use them.
5. **Licence files:** `LICENSE` = verbatim Apache-2.0 text; `NOTICE` lists only works with real derivation (empty at bootstrap except the project line); every `.py` starts with `# SPDX-License-Identifier: Apache-2.0` and `# Copyright (c) 2026 Fenolite contributors`; `tests/unit/test_spdx_headers.py` enforces the header on every file under `src/`, `tests/` and `tools/`.
6. **`LEGAL.md` skeleton with two blocks.** Block A "Format analysis": Fenolite learns third-party file formats only from public documentation and from files it is entitled to read; contributors never decompile or disassemble vendor software; every fact is recorded in `docs/formats/<backend>/*.md` with its public source. Block B "Material from organisations": Fenolite is developed clean-room — no design files, constants, seeds, fixtures, statistics, vocabularies or templates belonging to or derived from any organisation's non-public material are added (decision recorded in ADR-0003, `c0003`). `LEGAL-ANNEX.md` holds the session log format (date, files touched, public sources consulted) that `c0003` makes mandatory for backend work.
7. **DCO instead of a CLA:** `CONTRIBUTING.md` requires `Signed-off-by:` trailers; a CI check for the trailer is added with the wheel job later, not now.
8. **ADR format:** MADR-lite (`docs/adr/NNNN-slug.md`: Status, Context, Decision, Alternatives, Consequences, Evidence). ADR-0004 "Licence: Apache-2.0" is written in this change; ADR-0001 (model), ADR-0002 (KiCad backend) and ADR-0003 (clean-room) belong to `c0004`, `c0006` and `c0003` respectively.
9. **Evidence scaffolding:** `docs/evidence/sources.md` (table: id, URL, licence of the source, what it is used for, date consulted) and `docs/hypotheses.md` (table: id, backend, statement, level, test or kit request, criterion, result, date) start empty with their headers, so `c0002`–`c0004` append rows instead of inventing formats.
10. **CI:** `.github/workflows/ci.yml` with one job `unit`, matrix `os: [ubuntu-latest, macos-latest]`, `python: ["3.12"]`, steps: checkout → `astral-sh/setup-uv` → `uv sync --extra dev` → `uv run ruff check .` → `uv run ruff format --check .` → `uv run pyright src` → `uv run pytest -q`. Python 3.11 and 3.13 and Windows join the matrix at the end of v0.1 (roadmap), not now.
11. **`.gitignore`:** `.claude/*`, `private/` (planning material that must never be published), `.fenolite/` (derived cache), `.venv/`, `dist/`, `build/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `*.bak`, `verify_results/*.tmp`.

## Risks / Trade-offs

- [Hatchling version discovery fails on an unusual `__init__.py`] → keep `__version__ = "0.0.1.dev0"` as the first statement after the SPDX header; test asserts `fenolite --version` output matches.
- [Contributors add a runtime dependency "just for now"] → `test_pyproject_invariants.py` fails the build.
- [SPDX header test blocks generated files] → generated files live under `schemas/` and `tools/residue/` data, which the header test excludes explicitly.
- [macos runner cost/latency] → acceptable for one job; Docker `kicad-cli` jobs run on ubuntu only.

## Migration Plan

- First commit of the repository; nothing to migrate. Rollback is deleting the repository.

## Open Questions

- PyPI placeholder release: publish `0.0.1.dev0` or `0.0.0`? Default: `0.0.1.dev0` for both `fenolite` and `phenolite` (the latter as a redirect package whose README points to `fenolite`).

## Evidence level required before merge

- Mechanical only: CI green on ubuntu and macos; `uv pip install --dry-run fenolite` resolves zero third-party packages; `pytest tests/unit/test_spdx_headers.py tests/unit/test_pyproject_invariants.py` pass.
