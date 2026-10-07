## ADDED Requirements

### Requirement: Stack-up job file parity
`tests/kicad/board/test_stackup_oracle.py` SHALL prove, through the Gerber job file that `kicad-cli pcb export gerbers` writes beside the Gerbers, that KiCad reads the stack-up node Fenolite writes and ignores the nodes that `project_stackup` calls incomplete, on 9.0.9 and 10.0.6, and SHALL record each probe in both probe files (`H-K-STACKUP-JOB`, `H-K-STACKUP-COMPLETE`, `H-K-STACKUP-DEFAULT`, `H-K-STACKUP-RESAVE`).
- **Benches.** `tests/_stackbench.py` (beside the other benches that have a hermetic half) MUST build created boards with `write_board` for the running major: 50 × 30 mm, one track per copper layer, 2, 4, 6 or 8 copper layers (inner rows numbered `2k + 2`), with the stack-up of each case written by "Stack-up written to boards" or, for a node Fenolite does not write, inserted into `setup` by token edit. Each run exports only `F.Cu` and reads the job file `<stem>-job.gbrjob`.
- `pcb-stackup-job-<n>`, for n = 2, 4, 6 and 8: `equal` when `MaterialStackup` holds, in order, one entry per row and sheet of the completed stack-up with its thickness, material and colour, its dielectric constant and loss tangent exactly when `impedance_controlled` is set, and `GeneralSpecs` holds `BoardThickness` equal to `Stackup.thickness()`, `Finish` equal to the finish (`None` when empty) and `ImpedanceControlled` when set; `different` otherwise. Together the cases MUST hold a dielectric of two sheets, a colour, a mask of thickness 0, an empty finish and a named one.
- `pcb-stackup-incomplete-<case>`, for `physical` (copper and dielectric rows only), `nosilk` (masks without silkscreen and paste rows), `fewer` and `more` (copper rows for 2 and 6 layers on a 4-layer table), `names` (copper rows not named after layers), `twodiel` (two dielectric rows in one gap) and `nopaste` (paste rows on a table without paste layers): `absent` when no `MaterialStackup` entry holds a thickness. `pcb-stackup-order` (silkscreen after mask on the top side) and `pcb-stackup-nopaste-table` (a table and a node without paste): `present` when every copper and dielectric entry holds one. Each case MUST also assert the verdict of `project_stackup`, so the reader's rule and KiCad are compared on the same files.
- `pcb-stackup-default-<n>`, for n = 2, 4, 6 and 8, a board without a node: `equal` when the job file states copper 0.035 mm, masks 0.01 mm and n − 1 FR4 dielectrics of (T − 0.02 − 0.035 n)/(n − 1) mm within 0.0001 mm for `general` thickness T, and `Finish` `None`.
- On 10.0.6 only, because 9.0.9 has no `pcb upgrade`: `pcb-stackup-resave`, `equal` when `pcb upgrade --force` keeps every node the benches write, and `general`, tree-equal, a dielectric sheet without a material, a dielectric constant or a loss tangent taking KiCad's `FR4`, 4.5 and 0.02 (measured on 2026-10-07); `pcb-stackup-resave-defaults`, `equal` when a copper row and a mask row without a thickness and a dielectric row that holds a thickness alone come back with 0.035 mm, 0.01 mm, and `FR4`, 4.5, 0.02 and type `core`, and the node gets its tail; `pcb-stackup-ipc-thickness`, `equal` when `pcb export ipc2581` states an `overallThickness` equal to the sum of the rows of a board whose `general` thickness differs from it.
- `build-stackup-job`: the stack-up variant of the blink ("Stack-up in a build") built for the running major and exported with `fenolite export --gerbers`; `equal` when its job file states the declared stack-up as `pcb-stackup-job-<n>` does.
- A probe that records another outcome MUST stop the part of the change that relies on it, and the register row MUST record what KiCad showed.

#### Scenario: Written stack-ups parity on both majors
- **WHEN** `uv run pytest tests/kicad/board/test_stackup_oracle.py -k job -rA` runs on the local 10.0.6 and inside the pinned 9.0.9 image
- **THEN** the four `pcb-stackup-job-<n>` probes and `build-stackup-job` are `equal` in both probe files

#### Scenario: Incomplete nodes are ignored
- **WHEN** the same file runs with `-k complete`
- **THEN** the seven `pcb-stackup-incomplete-<case>` probes are `absent`, `pcb-stackup-order` and `pcb-stackup-nopaste-table` are `present`, and `project_stackup` gives `None` with `kicad.board.stackup-unused` for exactly the seven

#### Scenario: Default stack-up of a board without a node
- **WHEN** the same file runs with `-k default`
- **THEN** the four `pcb-stackup-default-<n>` probes are `equal`, the dielectrics being 1.51, 0.48, 0.274 and 0.1857 mm thick for a `general` thickness of 1.6 mm

#### Scenario: Re-save and IPC-2581 on 10.0.6
- **WHEN** the same file runs with `-k resave` on the local 10.0.6
- **THEN** `pcb-stackup-resave`, `pcb-stackup-resave-defaults` and `pcb-stackup-ipc-thickness` are `equal` in the 10.0.6 probe file
