## ADDED Requirements

### Requirement: Parity types are probed
`tests/kicad/check/test_parity_probes.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-PARITY-TYPES` on the running `kicad-cli`, with the `pic_programmer` demo of the running major's tag (its board and its schematics from the corpus) copied with a `{}` project file, and judged only from the JSON report of `pcb drc --schematic-parity --format json --severity-all`.
- Edits of the board text, one per run: `ref` (one footprint's reference renamed), `value`, `libid` (one footprint's library id changed), `net` (one pad given another net of the board), `dup` (one footprint given another's reference), `extra` (a copy of a footprint with a new reference and uuid), and `none`.
- Probe `parity-type-<edit>` MUST record `equal` when the parity types are those of `H-K-PARITY-TYPES` for that edit, with their counts, and `different` otherwise, in both probe files; the facts MUST be written to `docs/formats/kicad/drc.md` with their sources and labels.
- A further run with both the value and the library id of one footprint changed MUST record the number of `footprint_symbol_mismatch` entries (`parity-type-value-and-libid`), which Decision 2 of the design relies on.

#### Scenario: Types on 10.0.6
- **WHEN** `uv run pytest tests/kicad/check/test_parity_probes.py -rA` runs on the local KiCad 10.0.6
- **THEN** every `parity-type-*` probe records `equal`

#### Scenario: Types on 9.0.9
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image, the 9.0.9.1 demo files in the corpus cache and `FENOLITE_REQUIRE=kicad`
- **WHEN** the same tests run in the `kicad-9` job
- **THEN** every `parity-type-*` probe records an outcome, and the 9.0.9 probe file holds them

### Requirement: Own parity agrees with kicad-cli
`tests/kicad/check/test_parity_agreement.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-PARITY-OWN`: for every corpus demo of the running major's tag that has a board and a schematic, for the edits of "Parity types are probed" on `pic_programmer`, and for the blink built with a schematic and the same edits, the counts per KiCad type of `checks.parity.compare` (with the side built from `kicad-cli`'s netlist export) MUST equal the counts per type of `kicad-cli`'s parity report.
- A mismatch MUST fail the test, naming the project, the type and both counts.
- For the built blink, the side built from the own netlist MUST give the same counts as the side built from the export.
- Probe `parity-own-agreement` MUST record `equal` when every comparison holds.
- The copies MUST be made in `tmp_path`; the corpus cache and the built folders MUST be unchanged.

#### Scenario: Demos on both majors
- **WHEN** `uv run pytest tests/kicad/check/test_parity_agreement.py -rA` runs on 9.0.9 and on 10.0.6
- **THEN** every comparison holds, and `parity-own-agreement` records `equal`

#### Scenario: Duplicated reference
- **GIVEN** the `dup` edit of `pic_programmer`
- **WHEN** the agreement test runs it
- **THEN** Fenolite gives one `parity.duplicate-footprints`, one `parity.missing-footprint` and as many `parity.net-conflict` as KiCad gives `net_conflict`
