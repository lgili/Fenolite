## Why

Fenolite does not exist as a repository yet. Every later change (CLI contract, design model, KiCad backend, IP hygiene) needs a package skeleton, a licence, a CI baseline and the legal/evidence scaffolding in place first, so that the very first commit already enforces the project's non-negotiable rules: stdlib-only core, Apache-2.0, clean-room provenance and evidence labels on every claim.

## What Changes

- New repository layout (src layout): `src/fenolite/`, `tests/`, `docs/`, `tools/`, `schemas/`, `examples/`, `openspec/`, `verify_results/`.
- `pyproject.toml`: name `fenolite`, `requires-python >= 3.11`, **`dependencies = []`** (stdlib-only core), optional extras `geo`, `kicad-ipc`, `route`, `mcp`, `dev`, `oracles` (permissive-licence tools only), console script `fenolite`, single-source version.
- Licensing and notices: `LICENSE` (Apache-2.0), `NOTICE`, SPDX header in every source file, `LEGAL.md` skeleton with two blocks (A: format analysis of files; B: material from organisations — the project is clean-room), `LEGAL-ANNEX.md` (clean-room session log), Developer Certificate of Origin in `CONTRIBUTING.md`.
- Documentation scaffolding: `README.md`, `AGENTS.md` (how an AI agent works in this repo), `CHANGELOG.md` (Keep a Changelog), `docs/adr/` with ADR-0004 "Licence: Apache-2.0", `docs/evidence/sources.md` (the only place public sources are listed), `docs/hypotheses.md` (empty register).
- CI baseline: GitHub Actions job `unit` on ubuntu-latest and macos-latest × Python 3.12 running `ruff check`, `ruff format --check`, `pyright src`, `pytest`; `uv` as the package manager with a committed `uv.lock`; `.gitignore` covering `private/`, `.fenolite/`, build artefacts and caches.
- Name reservation (manual, by the author): placeholder releases `fenolite` and `phenolite` on PyPI.

## Capabilities

### New Capabilities
- `repo-layout`: package skeleton, stdlib-only dependency rule, version single-sourcing, console entry point, ignored paths.
- `licensing-and-notices`: Apache-2.0 licence, SPDX headers, NOTICE, LEGAL.md/LEGAL-ANNEX.md skeletons, DCO.
- `ci-baseline`: the `unit` CI job, its matrix and the quality gates it runs.

### Modified Capabilities
- (none — first change)

## Non-goals

- No functional behaviour beyond `fenolite --version` and `fenolite --help`.
- No design model, no backend, no residue scan yet (residue scan is `c0003-ip-hygiene`; the CLI envelope is `c0002-cli-contract`).
- No Windows CI runner yet (added at the end of v0.1 per the roadmap).

## Evidence level required

- Not applicable to design behaviour. Acceptance is mechanical: CI green on both operating systems, `pip install fenolite` pulling zero dependencies, every source file carrying an SPDX header.

## Impact

- Creates the repository; no downstream consumers yet.
- Establishes files that every later change edits: `pyproject.toml`, `CHANGELOG.md`, `docs/evidence/sources.md`, `docs/hypotheses.md`, `LEGAL-ANNEX.md`.
