## 0. Entry check

- [ ] 0.1 Read `openspec/specs/cli-contract/spec.md`, c0216 (its `CONTRACT_VERSION`) and the open questions of
  the design; record the maintainer's answers under this task. Proof: `openspec validate c0217-result-schemas-v1 --strict`.
  - 2026-10-27: the maintainer accepted every recommended answer (roadmap, "Open decisions", row 49): the public
    formats are the list of open question 1, and a removed result key is refused after `1.0.0`.

## 1. Infrastructure and inventory

- [ ] 1.1 `fenolite.cli.results` (`RESULTS`), the generator for result schemas, `tests/_schema.closed`, and the
  consistency suite's check that every visible command has a schema, with an allow-list of the commands still
  to do that the later tasks empty (scenarios "New command without a result schema fails the suite", "An
  undocumented key fails the suite"). Proof: `uv run pytest tests/consistency -q`.
- [ ] 1.2 Measure, on every example and on the replies the unit tests build, the keys whose type varies; list
  them under this task with the form kept. Proof: the list under this task.
- [ ] 1.3 `tools/gen_schemas.py --formats`: every `fenolite.<name>.v0` id of `src/` with its module, classified
  by the list of open question 1 (decided on 2026-10-27); **the maintainer** classifies any other id it finds,
  recorded under this task. Proof:
  `uv run python tools/gen_schemas.py --formats` lists them.

## 2. Result schemas, by family

- [ ] 2.1 Discovery and setup: `capabilities`, `doctor`, `explain`, `guide`, `skill`, `init`, `fetch`,
  `catalog`, `models`, `mcp`. Proof: `uv run pytest tests/consistency -q`; `uv run python tools/gen_schemas.py --check`.
- [ ] 2.2 Writers: `build`, `sync`, `template`, `panel`, `kit`, `edit`. Proof: as 2.1.
- [ ] 2.3 Verification: `check`, `ready`, `parity`, `roundtrip`, `diff` (`equivalent` and `convert` exist).
  Proof: as 2.1.
- [ ] 2.4 Analyses and nets: `analyze`, `impedance`, `neighbors`, `net`, `netlist`, `pads`, `region`,
  `testpoints`. Proof: as 2.1.
- [ ] 2.5 Outputs: `export`, `render`, `bom`, `pnp`, `manifest`. Proof: as 2.1.
- [ ] 2.6 Board edits and file safety: `place`, `route`, `fill`, `restore`, `fmt`, `snapshot`, `publish`, `refs`. Proof: as 2.1.
- [ ] 2.7 Inspection: `inspect`, `view`; the allow-list of 1.1 is empty. Proof: as 2.1, and the allow-list is
  gone from the suite.
- [ ] 2.8 The drift test compares property names and types with the last release tag after `1.0.0` (scenario
  "A removed property is refused after 1.0"); `docs/cli-contract.md` names each schema. Proof:
  `uv run pytest tests/unit/test_schema_drift.py tests/consistency -q`.

## 3. File formats

- [ ] 3.1 Schemas of the public inputs (by 1.3) and their readers accept `v0` and `v1` (scenario "A v0 document
  is still read"). Proof: `uv run pytest tests/unit -q -k "requirements or drawing_spec or placement_request or export_preset or assembly_template or review"`.
- [ ] 3.2 Schemas of the public outputs, and `schemas/README.md` lists every id with its class (scenario "Every
  format id is classified"). Proof: `uv run python tools/gen_schemas.py --formats --check`.

## 4. Closing

- [ ] 4.1 Run the tests and the residue scan. Proof: `make check-fast`.
- [ ] 4.2 Update the evidence labels: none changes; no format claim. Proof:
  `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 4.3 Update `CHANGELOG.md` under `## [Unreleased]`, with the keys of 1.2. Proof:
  `uv run pytest tests/unit/test_release_record.py -q`.
