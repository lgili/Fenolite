## ADDED Requirements

### Requirement: Preserved layouts pass the oracle
`tests/kicad/lens/` (marker `needs_kicad`, major-aware) SHALL prove on the running `kicad-cli` that a rebuild keeps a layout edited outside Fenolite. Every case MUST build `examples/blink_2layer/design.py` into a temporary folder, edit its board with `tests/_layout_edit.py::edit_blink` (`D1` moved 4 mm to the right; one segment on `F.Cu` from `R1` pad 2 to a via, and one segment on `B.Cu` from that via to `D1` pad 2, all on `LED_A`, with fixed uuids), run `kicad-cli` through c0009's `KicadCli` on copies with an empty `KICAD_CONFIG_HOME`, and judge DRC only from the JSON report read with c0017's `read_drc_report`, never from the exit code.
- **Re-save.** On 10.0.6 (`kicad_min_major(10)`), the edited target-10 board MUST be re-saved with `pcb upgrade --force` (`KicadCli.upgrade_board`, S-0022) before the rebuild, as the stand-in for a save in the KiCad GUI. KiCad 9.0 has no `pcb upgrade` (S-0037), so the target-9 cases, and every case on 9.0.9, rebuild the edited text.
- **Survival.** On the rebuilt board, `pcb export pos` MUST give `D1` at its moved position and `U1` and `R1` at theirs, compared through c0009's `tests/kicad/board/_frame.py`. The rebuilt board MUST hold both segments and the via of the edit with the same uuids, end points, widths, layers and net name. Its DRC report MUST hold the same multiset of (type, severity) pairs and the same number of `unconnected_items` as the report of the edited (or re-saved) board.
- **Identity.** A second rebuild MUST write every file with the bytes of the first.
- **Downgrade.** A target-9 blink whose board was re-saved by 10.0.6 MUST be refused when rebuilt with `--kicad-version 9` (exit 7, `FEN-7002`), and MUST rebuild with `--kicad-version 10`.
- **Probes first.** Before the lens code exists, `tests/kicad/lens/test_lens_probes.py` MUST run, as probes of c0017's `tests/kicad/_probes.py`:
  - `lens-resave-t10` (major 10): `present` when, after `pcb upgrade --force` of the edited target-10 board, `D1` keeps its uuid and its `fenolite.path` property and the two segments and the via keep their uuids, and `absent` otherwise;
  - `lens-rewrite-t9` (majors 9 and 10) and `lens-rewrite-t10` (major 10): `equal` when the edited board, read with `read_board` and written by `write_board` for its own target, gives a DRC report with the same (type, severity) multiset and `unconnected_items` count as the edited board, and `different` otherwise.
  - Stop rules: an `absent` outcome stops the change until the matching keys are revised, because matching rests on them; a `different` outcome stops it until the changed types are explained and recorded in `docs/formats/kicad/drc.md`.
- `lens-keep-t9` (majors 9 and 10) and `lens-keep-t10` (major 10) MUST record the survival outcome: `equal` when every survival check holds and `different` otherwise.
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json` (c0017), and built files MUST NOT be committed.

#### Scenario: Moved footprint survives a re-save on 10.0.6
- **GIVEN** the blink built for target 10 on the local KiCad 10.0.6, edited by `edit_blink` and re-saved with `pcb upgrade --force`
- **WHEN** `uv run pytest tests/kicad/lens/test_preserve_oracle.py::test_moved_footprint_survives` rebuilds it
- **THEN** `pcb export pos` gives `D1` 4 mm right of its `place()` position, both segments and the via are present with their uuids, and the DRC reports of the re-saved and rebuilt boards hold the same (type, severity) multiset and `unconnected_items` count

#### Scenario: Target 9 on 9.0.9
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and `FENOLITE_REQUIRE=kicad`
- **WHEN** `uv run pytest tests/kicad/lens -rA` runs in the `kicad-9` job
- **THEN** the target-9 cases run and pass on the edited text, and the re-save and downgrade cases are skipped by `kicad_min_major(10)`

#### Scenario: Second rebuild identical
- **GIVEN** the rebuilt folder of the re-saved target-10 case
- **WHEN** the build runs again
- **THEN** every file keeps its bytes

#### Scenario: Downgrade refused after a 10.0 save
- **GIVEN** the blink built for target 9, edited by `edit_blink` and re-saved by `pcb upgrade --force` on 10.0.6
- **WHEN** it is rebuilt with `--kicad-version 9 --dry-run`, and then with `--kicad-version 10 --confirm`
- **THEN** the first exits 7 with `FEN-7002`, and the second exits 0 with `D1` at its moved position

#### Scenario: Probe outcomes pinned
- **GIVEN** `docs/evidence/kicad/probes/10.0.6.json` regenerated with `FENOLITE_PROBES_WRITE=1`
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs on the local KiCad 10.0.6
- **THEN** it passes, and the file holds an outcome for `lens-resave-t10`, `lens-rewrite-t9`, `lens-rewrite-t10`, `lens-keep-t9` and `lens-keep-t10`
