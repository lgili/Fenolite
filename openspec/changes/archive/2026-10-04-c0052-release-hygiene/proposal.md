# c0052 — Release hygiene: capability evidence, package metadata, small documents

## Why

A review of `main` before v0.1 found small loose ends that no active change owns:

- `fenolite capabilities` reports the KiCad backend at `INFERRED`, as a literal in `backends/kicad/backend.py`, while the two hypotheses it names are `CORPUS-VERIFIED` and `KICAD-VERIFIED`. Nothing ties the literal to the evidence that `read` and `write` return, or to the register, and no page says why the level is lower than the rows.
- `pyproject.toml` has no `[project.urls]`, still says "Pre-Alpha", and has an extra `route` that pins `freerouting-client`, a package no code imports. The source distribution packs `openspec/`, the agent instruction files and any stray file of the working tree.
- `docs/cli-contract.md` has no section for the `template` command. Two tests keep skip guards for things that exist. Two register rows have observations that were never written. `docs/provenance.md` does not explain the private residue gate.

## What Changes

- **Capability evidence.** `KicadBackend`'s report takes its evidence from `Evidence.combine(pcb.EVIDENCE, pcb.WRITE_EVIDENCE)`. A test fails when a registered backend's level is stronger than the register row of a hypothesis it names, when a named row is missing or refuted, or when the KiCad report differs from its operations. The level stays `INFERRED`: `kicad-file-backend` ("Board reading evidence") keeps `pcb.EVIDENCE` at `INFERRED`, and the row `H-K-PCB-WRITE` itself says that writing arbitrary designs stays `INFERRED`. The contract page says so.
- **Package metadata.** `[project.urls]` (repository https://github.com/lgili/Fenolite), classifier `Development Status :: 3 - Alpha`, and the `route` extra removed: c0023 runs Freerouting as a subprocess and lists the cloud API as a non-goal, so no change uses that package.
- **Source distribution.** An allowlist: `src`, `tests`, `docs`, `examples`, `schemas`, `tools` and the licence and project documents. `openspec/`, `AGENTS.md`, `CLAUDE.md`, `packaging/`, `uv.lock` and `Makefile` do not ship.
- **Documents and tests.** A `template` section in `docs/cli-contract.md`, written from runs of the command; the two dead skip guards removed; the results of `H-G-ANGLE` and `H-A-UNIT` updated with what was observed; a section "Private residue gate" in `docs/provenance.md`.

## Capabilities

- `backend-protocol`: MODIFIED "Capability reports".
- `repo-layout`: MODIFIED "Zero runtime dependencies in the core"; ADDED "Package metadata", "Source distribution contents".
- `cli-contract`: ADDED "Contract page names every command".
- `residue-scan`: ADDED "Private gate is documented".

## Non-goals

- The version, the release record, the wheel job and the `CHANGELOG.md` clean-up (c0025).
- `docs/roadmap.md` and `openspec/README.md`.
- Raising any evidence label, in code or in the register.
- Per-command result schemas; a Docker-capable CI job; the history residue scan for the tag.
- Changing `.gitignore`, or the uncommitted `AGENTS.md` block of the main checkout.
- The package description text.

## Evidence level required

- No label is raised. The KiCad capability level stays `INFERRED`.
- `H-G-ANGLE` and `H-A-UNIT` stay `INFERRED`: each result records supporting data, and neither row's criterion is met in full.
- The `template` section is checked by running the command; the command's own evidence stays `INFERRED` (`H-K-WKS-CORNER`).

## Impact

- Changed: `src/fenolite/backends/kicad/backend.py`, `pyproject.toml`, `uv.lock`, `README.md`, `docs/cli-contract.md`, `docs/provenance.md`, `docs/hypotheses.md`, `CHANGELOG.md`, five test files.
- New: `tests/unit/test_capability_evidence.py`.
- Users of `pip install fenolite[route]` get a warning that the extra does not exist. It never did anything.
- c0016 and c0023 add entry points to `pyproject.toml`, not extras: no conflict beyond a textual merge.
