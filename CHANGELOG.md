# Changelog

All notable changes to Fenolite are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) (pre-1.0: minor versions may break).

## [Unreleased]

### Added

- KiCad libraries: neutral library definitions (`FootprintDef`, `SymbolDef`), `.kicad_mod`/`.kicad_sym`/`.kicad_symdir` readers with slots, library-table resolution (project, global, template and nested tables, path variables, local install), and an authored CC0 mini library checked by `kicad-cli` 9.0 and 10.0 (`fenolite.model.library`, `fenolite.backends.kicad.{mod,sym,libs,liberrors}`, `schemas/fenolite.model.v0/library.json`, `docs/formats/kicad/libraries.md`, `docs/evidence/kicad-libs.md`, `tests/data/libs/`). The census of the local 10.0.6 install reads 15 450 footprints and 22 860 symbols without error; `H-K-LIB-NAME-STEM` (9.0.9, 10.0.6) and `H-K-LIB-SYMDIR` (10.0.6) verified. Observed: KiCad sorts pads, graphics, symbols and pins when it saves, and the official footprints repeat graphic uuids inside single files.
- KiCad format versions and gating (`versions.py`), token inventory `tokens.toml` with fuzz results on kicad-cli 9.0.9 and 10.0.6, `kicad-9` CI job and `kicad_min_major` test marker, error codes FEN-3003/FEN-3004/FEN-7002 (`tools/kicad_token_fuzz.py`, `tools/gen_token_docs.py`, `docs/formats/kicad/versions.md`, `docs/formats/kicad/tokens.md`, `docs/evidence/kicad/token-fuzz/`). All 184 inventory rows are verified on both majors; observed: both majors refuse future board headers, and 9.0.9 keeps pad-level tenting and drops the press-fit pad property.
- KiCad S-expression layer (spelling-preserving parser, KiCad-style and compact printers, fragment codec, tree equality), slots helper with extension-bag persistence, KiCad demo and third-party corpus rows with RT0, and the `kicad-10` Docker oracle job (`fenolite.backends.kicad`, `docs/formats/kicad/sexpr.md`, `docs/formats/kicad/corpus.md`; `FENOLITE_REQUIRE` required-resource mode; `tools/corpus_fetch.py --uses/--exclude-uses`). Verified with `kicad-cli` 10.0.6: lexical acceptance and rejections, string escapes, number reading, re-save equality; `H-K-SEXPR-NUM-WRITE` refuted (KiCad writes non-length values with up to 10 decimals).
- Geometry kernel: exact integer predicates, three-point arcs, polygons with a canonical normal form, mixed contours, deterministic µdeg transforms, STR spatial index, boolean backend protocol with a convex-only stdlib fallback, and KiCad frame and arc evidence tests (`fenolite.geometry`, `docs/geometry.md`, `docs/formats/kicad/geometry.md`; `H-G-ROT-DIR`, `H-G-BOTTOM-PLACE`, `H-G-ARC-ROUND`, `H-G-ARC-DIR` and `H-G-PTS-ARC` verified with `kicad-cli` 10.0.6).

### Changed

- The `kicad-9` CI job runs `pytest -q -rA`, so its log lists the outcome of every oracle test.
- CI evidence recorded: the first green `kicad-10` run and the `kicad-9` run confirm the geometry hypotheses (`H-G-ROT-DIR`, `H-G-BOTTOM-PLACE`, `H-G-ARC-ROUND`, `H-G-ARC-DIR`, `H-G-PTS-ARC`) on 9.0.9 and settle `H-K-02`; `main` now requires the `kicad-9` and `kicad-10` checks. Changes c0006 and c0007 archived.

## [0.0.1.dev0] - 2026-09-30

Pre-alpha repository bootstrap; not usable for real boards yet. Published to PyPI as `fenolite` and its
alias `phenolite` on 2026-09-30 (`pip install --pre fenolite`).

### Added

- Repository bootstrap: package skeleton (`src/fenolite`, stdlib-only core, closed extras), Apache-2.0 licence with NOTICE and SPDX headers, `LEGAL.md`/`LEGAL-ANNEX.md`, DCO, ADR-0004, evidence registers and the `unit` CI baseline (ruff, pyright strict, pytest on ubuntu and macos).
- CLI contract v0: JSON envelope (`schemas/fenolite.envelope.v0.json`) and typed stderr errors (`schemas/fenolite.error.v0.json`), exit codes 0–7, `--fields`, mutation protocol (`--dry-run`/`--confirm`, atomic writes with `.bak`, receipts), `--seed`/`--timestamp`, the `capabilities` command, a consistency test over every command and a package-layering test.
- IP hygiene: ADR-0003 (clean-room and provenance), four explicit prohibitions in `LEGAL.md`, provenance rules and test, residue scan (`tools/residue/scan.py`: structural patterns, blob hashes, private token and hash lists kept outside the repository, UTF-16/cp1252/zip awareness, `--staged` and `--history` modes) with a pre-commit hook and CI step, copyleft-dependency and no-ported-code guards, corpus manifest with the embeddable rule and `tools/corpus_fetch.py`.
- Design model v0: `fenolite.core` (integer nm/µdeg units with exact parsing and half-even conversion to 1/10 000 mil, ids, evidence levels, errors and issues, provenance, coordinates, atomic I/O) and `fenolite.model` (entity header with native ids, provenance and extension bags; circuit, board, rules, manufacturing and findings layers; `Design` with indexes, validation and entity replacement; canonical JSON with a validating decoder; JSON Schemas in `schemas/fenolite.model.v0/`), ADR-0001 and `docs/design-model.md`.
- Name reservation: alias distribution `phenolite` (installs `fenolite`) and a release workflow that publishes both to PyPI with trusted publishing when a GitHub Release is published.
