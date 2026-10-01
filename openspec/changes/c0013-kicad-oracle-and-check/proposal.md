## Why

Plan item 0013 makes `fenolite check` the product: one read-only command that judges a KiCad project, with evidence per stage. c0009, c0017 and c0018 ship the reader, the runner, the DRC report reader and the rules writer; nothing runs them together. Two facts shape the design. `kicad-cli` writes into the folder it runs in (`.kicad_prl`; a configuration folder even for `--help`), so it may only see copies. KiCad drops a broken rules file silently, so a clean DRC proves nothing about custom rules (`H-K-TOK-RULES-SILENT`, S-0038).

## What Changes

- `backends/base.py`: neutral `RoundTrip`, `Validation`, `Validator`, `ProjectSet`, `SkippedFile`, `CanaryState`, `DrcOutcome` and the `Oracle` protocol.
- `backends/kicad/roundtrip.py`: RT1 in `src` (`rt1`; locations from c0006's `first_difference`); `KicadBackend.validate`; `"validate"` in `operations`.
- `backends/kicad/projectset.py`: the closed copy set of a project (board, same-stem project and rules, `${KIPRJMOD}` libraries, named worksheet), skips reported.
- `backends/kicad/canary.py`, `oracle.py`: `KicadOracle.drc` appends a net-scoped clearance canary to copied rules, inserts two distant canary tracks into the copied board as text, and strips canary violations.
- `checks/` (new): stages `model.validate`, `erc.lite`, `drc.kicad`, `roundtrip`; evidence per stage; an issue table. `erc.lite` gives three `INFERRED` warnings on built input until 0.2.
- `fenolite check PATH [--stages] [--kicad-cli] [--timeout]`: read-only; exit 5 on an error issue; exit 6 when DRC is selected and `kicad-cli` is missing or too old. DRC violations are counted, not yet issues (c0020).
- `fenolite inspect FILE --summary` (moved from c0009): header, counts, `opaque_count`; hermetic.
- `fenolite doctor [--no-run]`: each `kicad-cli` candidate, its version and a subcommand matrix from `--help`; `java`, `docker`.
- Probes first (9.0.9, 10.0.6): copy set, canary (fired, neutral, broken rules, ignored severity), help grammar.
- Docs `docs/formats/kicad/cli.md`, `docs/evidence/kicad-check.md`, `docs/cli-contract.md`; sources S-0080 (Docker) and S-0081 (JEP 223); hypotheses `H-K-CHECK-COPYSET`, `H-K-CHECK-CANARY`, `H-K-CLI-HELP`, `H-K-CHECK-ERC`.

Budget: 8.5 days against the roadmap's 7, with a cut order (design, "Budget").

## Capabilities

### New Capabilities
- `verification-loop`: `check` input, stages, evidence, read-only guarantee, ERC lite, DRC rules verdict, RT1, unreadable inputs, issue and exit codes, determinism.

### Modified Capabilities
- `backend-protocol`: ADDED the `Oracle` protocol and the `validate` operation. MODIFIED Write capability fields: c0017's exact `operations` pin becomes membership (`lower`, `validate` when implemented).
- `kicad-file-backend`: ADDED the round-trip verdict.
- `kicad-oracle`: ADDED the copy set, the canary and the help-text subcommand matrix.
- `cli-contract`: ADDED `inspect` and `doctor`.

## Non-goals

- DRC violations as issues, `netlist.assignment_compare`, RT2, `Oracle.netlist` and `Oracle.upgrade` (c0020).
- The `render` stage (c0024); zone fill (c0015); library environment pass-through (c0021); board versus `.fenolite/` (c0019).
- `sch erc`, `inspect` of `.kicad_pro`/`.kicad_dru`, `inspect --detailed` (v0.2a).
- Any write to the user's project; new FEN codes, model changes, an ADR; any other MODIFIED requirement.

## Evidence level required

- `drc.kicad`: c0017's `drc.EVIDENCE` combined with `oracle.EVIDENCE` (`KICAD-VERIFIED` once their hypotheses are) when a report exists and the canary fired or no rules file exists; else `UNVERIFIED`.
- Copy set, canary and help matrix: `KICAD-VERIFIED` on 9.0.9 and 10.0.6 once their probes settle.
- Read-only: equal snapshots (paths, SHA-256, `st_mtime_ns`), with a fake and both majors.
- `model.validate`, `roundtrip`: the reader's `INFERRED` (`H-K-PCB-READ`); `erc.lite`: `INFERRED` (`H-K-CHECK-ERC`, pending).
- `inspect`: the reader's level. `doctor`: `helpmatrix.EVIDENCE` (`KICAD-VERIFIED` once `H-K-CLI-HELP` is) when every help page parsed, else `UNVERIFIED`.
- Envelope: the lowest level of the stages that ran or were skipped because their input failed; `UNVERIFIED` when none counts.

## Impact

- New `checks/`, `cli/cmd_check.py`, `cmd_inspect.py`, `cmd_doctor.py`, `backends/kicad/{roundtrip,projectset,canary,oracle,helpmatrix}.py`; `cli.py` lists candidates. No `package-layering` change.
- Tests: hermetic fakes; oracle tests on both majors; projects assembled in `tmp_path`; `check-*` probe rows.
- Registers: `sources.md`, `hypotheses.md`, `PROVENANCE.md`, `LEGAL-ANNEX.md`.
- Depends on c0009, c0014, c0017, c0018, c0010, and c0011 (refusal issues, library tables, one end-to-end test).
