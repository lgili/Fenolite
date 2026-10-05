## ADDED Requirements

### Requirement: Parity types are probed
`tests/kicad/check/test_parity_probes.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-PARITY-TYPES` on the running `kicad-cli`, with the blink that `build` writes for the running major, and judged only from the report of `pcb drc --schematic-parity` as `KicadCli.drc` reads it. The probes need no corpus. Marked `needs_corpus`, the same edits MUST be run on the `pic_programmer` demo of the running major's tag (its board and its schematics from the corpus, with a `{}` project file), where the types an edit adds to those of the published demo MUST be the same; when the published demo already holds `footprint_symbol_mismatch` entries, as at tag 9.0.9.1, that type is not judged there.
- Edits of the board text, one per run: `ref` (one footprint's reference renamed), `value`, `libid` (one footprint's library id changed), `net` (one pad given another net of the board), `dup` (one footprint given another's reference), `extra` (a copy of a footprint with a new reference and uuid), and `none`.
- Probe `parity-type-<edit>` MUST record `equal` when the parity types are those of `H-K-PARITY-TYPES` for that edit, with their counts, and `different` otherwise, in both probe files. For `dup` the types are one `duplicate_footprints` and one `missing_footprint`; `footprint_symbol_mismatch`, `footprint_symbol_field_mismatch` and `net_conflict` may come with them, when the footprint that took the reference comes first on the board; the facts MUST be written to `docs/formats/kicad/drc.md` with their sources and labels.
- A further run with both the value and the library id of one footprint changed MUST record `equal` for two `footprint_symbol_mismatch` entries (`parity-type-value-and-libid`), which Decision 2 of the design relies on.

#### Scenario: Types on 10.0.6
- **WHEN** `uv run pytest tests/kicad/check/test_parity_probes.py -rA` runs on the local KiCad 10.0.6
- **THEN** every `parity-type-*` probe records `equal`

#### Scenario: Types on 9.0.9
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image, the 9.0.9.1 demo files in the corpus cache and `FENOLITE_REQUIRE=kicad`
- **WHEN** the same tests run in the `kicad-9` job
- **THEN** every `parity-type-*` probe records `equal`, and the 9.0.9 probe file holds them

### Requirement: Own parity agrees with kicad-cli
`tests/kicad/check/test_parity_agreement.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-PARITY-OWN`: for every corpus demo of the running major's tag that has a cached, readable board and a schematic, for the edits of "Parity types are probed" on `pic_programmer`, and for the blink built with a schematic and the same edits, the counts per KiCad type of `checks.parity.compare` (with the side built from `kicad-cli`'s netlist export) MUST equal the counts per type of `kicad-cli`'s parity report, for the five types of `checks.parity.KICAD_TYPES`. Entries of another KiCad type (`footprint_symbol_field_mismatch` on 10.0.6) are counted and printed, not compared. Counts are compared, never the items of two runs.
- A mismatch MUST fail the test, naming the project, the type and both counts.
- For the built blink, the side built from the own netlist MUST give the same counts as the side built from the export.
- Probe `parity-own-agreement` MUST record `equal` when every comparison on the built blink holds, so the probe needs no corpus; the demos are a `needs_corpus` test.
- The copies MUST be made in `tmp_path`; the corpus cache and the built folders MUST be unchanged.

#### Scenario: Demos on both majors
- **WHEN** `uv run pytest tests/kicad/check/test_parity_agreement.py -rA` runs on 9.0.9 and on 10.0.6
- **THEN** every comparison holds, and `parity-own-agreement` records `equal`

#### Scenario: Duplicated reference
- **GIVEN** the `dup` edit of `pic_programmer`
- **WHEN** the agreement test runs it
- **THEN** Fenolite gives one `parity.duplicate-footprints`, one `parity.missing-footprint` and as many findings of type `net_conflict` as KiCad gives
