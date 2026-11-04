## 0. Entry check

- [x] 0.1 Read `openspec/specs/cli-contract/spec.md`, c0216 (its `CONTRACT_VERSION`) and the open questions of
  the design; record the maintainer's answers under this task. Proof: `openspec validate c0217-result-schemas-v1 --strict`.
  - 2026-10-27: the maintainer accepted every recommended answer (roadmap, "Open decisions", row 49): the public
    formats are the list of open question 1, and a removed result key is refused after `1.0.0`.

## 1. Infrastructure and inventory

- [x] 1.1 `fenolite.cli.results` (`RESULTS`), the generator for result schemas, `tests/_schema.closed`, and the
  consistency suite's check that every visible command has a schema, with an allow-list of the commands still
  to do that the later tasks empty (scenarios "New command without a result schema fails the suite", "An
  undocumented key fails the suite"). Proof: `uv run pytest tests/consistency -q`.
- [x] 1.2 Measure, on every example and on the replies the unit tests build, the keys whose type varies; list
  them under this task with the form kept. Proof: the list under this task.
- [x] 1.3 `tools/gen_schemas.py --formats`: every `fenolite.<name>.v0` id of `src/` with its module, classified
  by the list of open question 1 (decided on 2026-10-27); **the maintainer** classifies any other id it finds,
  recorded under this task. Proof:
  `uv run python tools/gen_schemas.py --formats` lists them.

## 2. Result schemas, by family

- [x] 2.1 Discovery and setup: `capabilities`, `doctor`, `explain`, `guide`, `skill`, `init`, `fetch`,
  `catalog`, `models`, `mcp`. Proof: `uv run pytest tests/consistency -q`; `uv run python tools/gen_schemas.py --check`.
- [x] 2.2 Writers: `build`, `sync`, `template`, `panel`, `kit`, `edit`. Proof: as 2.1.
- [x] 2.3 Verification: `check`, `ready`, `parity`, `roundtrip`, `diff` (`equivalent` and `convert` exist).
  Proof: as 2.1.
- [x] 2.4 Analyses and nets: `analyze`, `impedance`, `neighbors`, `net`, `netlist`, `pads`, `region`,
  `testpoints`. Proof: as 2.1.
- [x] 2.5 Outputs: `export`, `render`, `bom`, `pnp`, `manifest`. Proof: as 2.1.
- [x] 2.6 Board edits and file safety: `place`, `route`, `fill`, `restore`, `fmt`, `snapshot`, `publish`, `refs`. Proof: as 2.1.
- [x] 2.7 Inspection: `inspect`, `view`; the allow-list of 1.1 is empty. Proof: as 2.1, and the allow-list is
  gone from the suite.
- [x] 2.8 The drift test compares property names and types with the last release tag after `1.0.0` (scenario
  "A removed property is refused after 1.0"); `docs/cli-contract.md` names each schema. Proof:
  `uv run pytest tests/unit/test_schema_drift.py tests/consistency -q`.

## 3. File formats

- [x] 3.1 Schemas of the public inputs (by 1.3) and their readers accept `v0` and `v1` (scenario "A v0 document
  is still read"). Proof: `uv run pytest tests/unit -q -k "requirements or drawing_spec or placement_request or export_preset or assembly_template or review"`.
- [x] 3.2 Schemas of the public outputs, and `schemas/README.md` lists every id with its class (scenario "Every
  format id is classified"). Proof: `uv run python tools/gen_schemas.py --formats --check`.

## 4. Closing

- [ ] 4.1 Run the tests and the residue scan. Proof: `make check-fast`.
- [x] 4.2 Update the evidence labels: none changes; no format claim. Proof:
  `uv run pytest tests/unit/test_hypotheses_register.py -q`.
  Done 2026-11-04: no label changes; the proof passed with 4.3's (52 passed).
- [x] 4.3 Update `CHANGELOG.md` under `## [Unreleased]`, with the keys of 1.2. Proof:
  `uv run pytest tests/unit/test_release_record.py -q`.
  Done 2026-11-04: the c0217 entry names the measured keys of 1.2 (recorded in
  `current-source-proof.md`, "Retained measured polymorphism"); the proof passed.

## Current-source selective preparation

- [x] 0.2 Review the current-source selective-port packet in c0216 before runtime changes; preserve
  current model0/CLI0 and every later field/validation. Historical bf6532a4 receipts are source material,
  not current test/freeze proof. Final inventories wait for the actual final c0348 source.

- [x] 3.1a Describe the actual public symbol-contexts input and test v1 rebinding explicitly;
  schema-only changes, malformed/stale hashes, targets and unknown fields refuse, v0 bytes stay exact.

Actual-source preparation proof: current-source-proof.md. Root must refresh/freeze the complete
reviewed final source and confirm exact-head gates before archival. No historical approval/freeze is used.

- [x] 0.4 Resolve the actual combined-fast stale proposal future-version negative with a literal v1
  positive and unsupported v2 negative, retaining closed data and decimal refusal. Proof:
  `uv run pytest tests/unit/library/proposals/test_parse.py -q` and focused proposal component.

Follow-up proof: the actual reader deliberately accepts only the reviewed v0/v1 pair; initial stale
v1-as-future negative failed. The literal v1 authored positive preserves every field/parameter/
quantity; unsupported v2 still refuses. Literal TOML decimal pin counts are rejected at
`decimal.toml:package.pins` under both mirrors, in addition to the original serializer refusal.
`uv run pytest tests/unit/library/proposals -q`: 51 passed. No parser, schema, tamper guard,
fixture byte or writer changed. Ruff/format and strict OpenSpec pass; combined CI remains open.
