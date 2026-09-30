# Changelog

All notable changes to Fenolite are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) (pre-1.0: minor versions may break).

## [Unreleased]

### Added

- Repository bootstrap: package skeleton (`src/fenolite`, stdlib-only core, closed extras), Apache-2.0 licence with NOTICE and SPDX headers, `LEGAL.md`/`LEGAL-ANNEX.md`, DCO, ADR-0004, evidence registers and the `unit` CI baseline (ruff, pyright strict, pytest on ubuntu and macos).
- CLI contract v0: JSON envelope (`schemas/fenolite.envelope.v0.json`) and typed stderr errors (`schemas/fenolite.error.v0.json`), exit codes 0–7, `--fields`, mutation protocol (`--dry-run`/`--confirm`, atomic writes with `.bak`, receipts), `--seed`/`--timestamp`, the `capabilities` command, a consistency test over every command and a package-layering test.
- IP hygiene: ADR-0003 (clean-room and provenance), four explicit prohibitions in `LEGAL.md`, provenance rules and test, residue scan (`tools/residue/scan.py`: structural patterns, blob hashes, private token and hash lists kept outside the repository, UTF-16/cp1252/zip awareness, `--staged` and `--history` modes) with a pre-commit hook and CI step, copyleft-dependency and no-ported-code guards, corpus manifest with the embeddable rule and `tools/corpus_fetch.py`.
- Design model v0: `fenolite.core` (integer nm/µdeg units with exact parsing and half-even conversion to 1/10 000 mil, ids, evidence levels, errors and issues, provenance, coordinates, atomic I/O) and `fenolite.model` (entity header with native ids, provenance and extension bags; circuit, board, rules, manufacturing and findings layers; `Design` with indexes, validation and entity replacement; canonical JSON with a validating decoder; JSON Schemas in `schemas/fenolite.model.v0/`), ADR-0001 and `docs/design-model.md`.
- Name reservation: alias distribution `phenolite` (installs `fenolite`) and a release workflow that publishes both to PyPI with trusted publishing when a GitHub Release is published.
