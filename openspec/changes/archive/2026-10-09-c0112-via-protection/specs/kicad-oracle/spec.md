## ADDED Requirements

### Requirement: Via protection passes the oracle
`tests/kicad/vias/test_via_protection_oracle.py` (markers `needs_kicad`, major-aware) SHALL prove on the running `kicad-cli` how KiCad reads, plots and exports via protection (`H-K-VIAPROT-FORMS`, `H-K-VIAPROT-MASK`, `H-K-VIAPROT-NINE`, `H-K-VIAPROT-UPGRADE`, `H-K-VIAPROT-OUTPUTS`).
- **Bench.** `tests/kicad/vias/_viabench.py` writes a created two-layer board with `write_board`: one row of vias of 0.8 mm with a 0.4 mm drill on one net, joined by an `F.Cu` track, one via per row case, and its project `{}`. The facts benches set each via's protection and the `setup` default by token edit, so they do not depend on the writer under test: the 10.0 forms of design measurement 3 on target-10 boards under the defaults tented, open and front only; the 9.0 forms (none, `front back`, `front`, `back`, `none`, no atom) on target-9 boards under the defaults none, `front back`, `none` and `front`. The written bench sets the same cases through the model and writes them for each target.
- **Reading the plots.** A side of a via is open when `pcb export gerbers -l F.Mask,B.Mask` gives a flash within 0.45 mm of the via's centre on that side's plot, read with `tests/kicad/zones/_gerber.py::flashes`; tented otherwise.
- **Probes**, recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`:

| probe | majors | outcome |
|---|---|---|
| `via-prot-resave` | 10 | `equal` when `pcb upgrade --force` of the written target-10 bench under each stated default (tented, open, front only) gives every via, matched by its position, and `setup`, the protection children Fenolite wrote; `different` otherwise. The bench without a default is left out: a re-save gives its `setup` the five children of KiCad's default |
| `via-prot-order` | 10 | `equal` when `pcb upgrade --force` keeps the order of the children of every via of the order bench: a target-10 board whose vias hold `(free yes)`, `(locked yes) (free yes)`, `(locked yes)` or neither, read, each via given a tenting, a capping and a filling through the model, and written; `different` otherwise |
| `via-prot-mask` | 9, 10 | `equal` when every via of the facts bench of the running major (9.0 forms on 9.0.9, 10.0 forms on 10.0.6) is open exactly where `via_protection.effective` of its read protection and the board's default is `False`; `different` otherwise |
| `via-prot-load-nine` | 9 | `reject` when `pcb drc` gives exit 3 on a target-9 bench holding `(plugging (front yes) (back yes))` on one via; `load` otherwise |
| `via-prot-upgrade` | 10 | `different` when 10.0.6 plots the target-9 facts bench under the default `front back` as tented on the unnamed sides of `front`, `back`, `none` and the empty child and agrees with 9.0.9 on the others; `equal` when it agrees everywhere; `inconclusive` otherwise |
| `via-prot-outputs` | 10 | `equal` when each drill side file of `pcb export drill --format gerber --generate-tenting` and each coating or hole-fill layer of `pcb export ipc2581` holds exactly the vias whose own value for its feature and side is `True`; `different` otherwise |
| `via-prot-default-outputs` | 10 | `absent` when the same bench under a default of `True` for all eight fields adds no via to any of those files and layers; `present` otherwise |

- **Written bench.** On both majors, the written bench for the running major MUST load (`pcb drc` exit 0) and plot as `via_protection.effective` says, for every case the target can hold; without `kicad-cli`, writing the cases with a `True` covering, plugging, capping or filling for target 9 MUST raise `LossyWriteError` (`kicad-file-backend`, "Via protection on boards").
- **Fallback.** A `different` outcome of `via-prot-resave` or `via-prot-mask` MUST stop the part that writes or reads that form: the form or the meaning is corrected from the bench before it merges, and the register row records what KiCad showed. A change of `via-prot-default-outputs` to `present` MUST remove `kicad.via.protection-not-exported` for that version before the probe file is updated.
- Built files MUST NOT be committed.

#### Scenario: Masks agree on both majors
- **WHEN** `uv run pytest tests/kicad/vias/test_via_protection_oracle.py -k mask` runs on 10.0.6 and in the `kicad-9` job
- **THEN** `via-prot-mask` records `equal` on both majors, and on 9.0.9 the via with `(tenting front)` under the default `front back` is open on `B.Mask`

#### Scenario: Re-save and outputs on 10.0.6
- **WHEN** `uv run pytest tests/kicad/vias/test_via_protection_oracle.py -k "resave or outputs"` runs on 10.0.6
- **THEN** `via-prot-resave` and `via-prot-outputs` record `equal`, and `via-prot-default-outputs` records `absent`

#### Scenario: KiCad 9 refuses the 10.0 forms
- **WHEN** `uv run pytest tests/kicad/vias/test_via_protection_oracle.py -k nine` runs in the `kicad-9` job
- **THEN** `via-prot-load-nine` records `reject`

#### Scenario: KiCad 10 reads 9.0 children its own way
- **WHEN** `uv run pytest tests/kicad/vias/test_via_protection_oracle.py -k upgrade` runs on 10.0.6
- **THEN** `via-prot-upgrade` records `different`, the test passing on the recorded outcome only

#### Scenario: The written bench
- **WHEN** `uv run pytest tests/kicad/vias/test_via_protection_oracle.py -k written` runs on 10.0.6 and in the `kicad-9` job
- **THEN** the written bench of the running major loads and every via's openings equal `via_protection.effective`
