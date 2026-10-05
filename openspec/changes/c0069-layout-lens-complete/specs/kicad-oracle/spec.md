## ADDED Requirements

### Requirement: Renamed footprints pass the oracle
`tests/kicad/lens/test_rename_oracle.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-LENS-RENAME` on the running `kicad-cli`, with the boards of the lens acceptance fixture (`layout-lens`, "Lens acceptance fixture") before and after the rebuild that renames the module `power`. Every run MUST use c0009's `KicadCli` on copies with an empty `KICAD_CONFIG_HOME`, and judge DRC only from the JSON report read with `read_drc_report`.
- **Load.** `pcb export pos` of the rebuilt board MUST list every footprint of the edited board, by reference, at the same position, rotation and side, on 9.0.9 for target 9 and on 10.0.6 for both targets.
- **DRC.** The DRC report of the rebuilt board MUST hold the same multiset of (type, severity) pairs and the same number of `unconnected_items` as the report of the edited board.
- **Re-save.** On 10.0.6 (`kicad_min_major(10)`), `pcb upgrade --force` of the rebuilt target-10 board MUST keep the group with the two renamed footprints, by their new uuids, and every uuid of their identity maps.
- **Probes.** `lens-rename-t9` (majors 9 and 10) and `lens-rename-t10` (major 10) MUST record `equal` when every check holds and `different` otherwise, in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`.
- **Stop rule.** A `different` outcome stops the keeping of alias matches until the difference is explained and recorded in `docs/formats/kicad/board.md`; meanwhile alias matches are re-placed as before this change, and the acceptance fixture records the loss.
- `H-K-LENS-RENAME` MUST become `KICAD-VERIFIED (9.0.x, 10.0.x)` when both probes are `equal` on both majors and the `kicad-9` and `kicad-10` jobs pass.

#### Scenario: Renamed module on 10.0.6
- **GIVEN** the acceptance fixture built for target 10 on the local KiCad 10.0.6, edited, and rebuilt with `power` renamed `supply`
- **WHEN** `uv run pytest tests/kicad/lens/test_rename_oracle.py -rA` runs
- **THEN** `pcb export pos` lists every footprint at its edited placement, the two DRC reports hold the same (type, severity) multiset and `unconnected_items` count, and the re-saved board keeps the group by the new uuids

#### Scenario: Target 9 on 9.0.9
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and `FENOLITE_REQUIRE=kicad`
- **WHEN** `uv run pytest tests/kicad/lens -rA` runs in the `kicad-9` job
- **THEN** the target-9 rename case runs and passes, and the re-save case is skipped by `kicad_min_major(10)`

#### Scenario: Probe outcomes pinned
- **GIVEN** `docs/evidence/kicad/probes/10.0.6.json` regenerated with `FENOLITE_PROBES_WRITE=1`
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs on the local KiCad 10.0.6
- **THEN** it passes, and the file holds an outcome for `lens-rename-t9` and `lens-rename-t10`
