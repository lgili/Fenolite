## ADDED Requirements

### Requirement: Rule areas and area conditions are probed
`tests/kicad/board/test_keepout_settings.py` and `tests/kicad/rules/test_area_rules.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-AREA-KEEPOUT`, `H-K-AREA-NAME` and `H-K-AREA-COND` on the running `kicad-cli`, with benches of `tests/kicad/rules/_areacases.py` built on `tests/kicad/rules/_rulebench.py` and written with `write_board` for the running major, through c0009's `KicadCli` on copies with an empty `KICAD_CONFIG_HOME`, judging DRC only from the JSON report by violation type and item uuid, never by description.
- **Canary.** Every bench MUST carry the canary scoped to its own net (c0071), and a run whose canary does not fire MUST fail.
- **Keep-out settings.** One bench per setting, with an item inside a rule area on `F.Cu` that forbids it and a control item outside: `area-keepout-tracks`, `-vias`, `-pads` and `-footprints` record `present` when `items_not_allowed` names the item inside (each pad, for pads; the footprint, for footprints) and nothing names the control item; `area-keepout-cross` records `present` for a track that crosses the area's edge; `area-keepout-layer` records `absent` for a track on `B.Cu` under the area; `area-keepout-pour` records `absent` when no `items_not_allowed` names a zone whose stored fill covers a `copperpour` keep-out. On 10.0.6, `area-keepout-refill` records `equal` when `pcb drc --refill-zones --save-board` leaves no fill polygon of that zone overlapping the area.
- **Names.** `area-name-keep` (major 10) records `equal` when `pcb upgrade --force` keeps a created area's `(name …)`; on 9.0.9 the named benches MUST load and fire the canary.
- **Conditions.** A rule of 2 mm scoped to an area named `HV` and two pairs 1 mm apart, inside and outside: `dru-cond-area` records `present` for `A.intersectsArea('HV')` when the pair inside is reported and the pair outside is not; `area-cond-two-sided` (`A.intersectsArea('P') && B.intersectsArea('Q')`), `area-cond-width` (a 0.1 mm `track_width` rule inside a 0.3 mm board-wide one), `area-cond-hole` (`hole_to_hole`), `area-cond-glob` (`'H*'`), `area-cond-touch` (an area 50 µm into the copper) and `area-cond-twin` (two areas named `HV`, the pair in the second) record `present`; `area-cond-unknown` (no area of that name, the canary still firing), `area-cond-case` (`'hv'`), `area-cond-layer` (an area on `F.Cu`, a pair on `B.Cu`) and `area-cond-edge` (copper 50 µm outside) record `absent`.
- `rulemap.SELECTOR_SUPPORT["area"]` MUST equal the majors on which `dru-cond-area` recorded `present`.
- **Stop rules.** `dru-cond-area` other than `present` on a major leaves `area` out of `SELECTOR_SUPPORT` for that major. An `area-keepout-*` outcome other than the stated one is written into the register row, and `copper.keepout` is not reported for that setting. `build.area-unknown` stays an error whatever `area-cond-unknown` records: KiCad then either ignores the rule or drops the whole file.
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, and the facts written to `docs/formats/kicad/rules.md`, `drc.md` and `board.md` with sources and labels. Built files MUST NOT be committed.

#### Scenario: Keep-out settings on both majors
- **WHEN** `uv run pytest tests/kicad/board/test_keepout_settings.py -rA` runs on the local KiCad 10.0.6 and in the `kicad-9` job
- **THEN** on both majors the four setting probes and `area-keepout-cross` are `present` and `area-keepout-layer` and `area-keepout-pour` are `absent`, and on 10.0.6 `area-keepout-refill` and `area-name-keep` are `equal`

#### Scenario: Area conditions on both majors
- **WHEN** `uv run pytest tests/kicad/rules/test_area_rules.py -rA` runs on the local KiCad 10.0.6 and in the `kicad-9` job
- **THEN** each `area-cond-*` probe and `dru-cond-area` records the outcome this requirement states, and the canary fires in every run

### Requirement: Board texts and dimensions are probed
`tests/kicad/board/test_board_items_oracle.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-BOARD-TEXT` and `H-K-DIM` on the running `kicad-cli`, with created boards written by `write_board`, under the rules of "Rule areas and area conditions are probed".
- **Texts.** `text-board-load` records `absent` when a board with texts on `F.SilkS`, `B.SilkS`, `F.Fab`, `Cmts.User` and `Dwgs.User`, each justification of `FIELD_JUSTIFY` and none, loads and no violation names a text; `text-height` records `present` when a silkscreen text 0.5 mm high and 0.06 mm thick gives `text_height` and `text_thickness`; `text-copper-short` records `present` when a copper text over a track gives `shorting_items`; `graphic-copper-silent` records `absent` when a copper `gr_line` across a track gives no violation naming the line and no `shorting_items` or `clearance` naming the track. The last two are the measured reasons why drawings are refused on copper; a change in either is recorded and reopens that refusal.
- **Dimensions.** `dim-load` records `present` when a board with an aligned and an orthogonal dimension of each unit, as "Board items of a script are written" writes them, loads; `dim-recompute` records `equal` when the `pcb export svg` plots of `Dwgs.User` of two boards that differ only in the cache text and its position are equal (title and description elements left out); on 10.0.6, `dim-resave-text` records `equal` when `pcb upgrade --force` writes the texts "20.0000 mm" and "25.50 mm" for the benches of that requirement.
- The outcomes MUST be recorded in both probe files.

#### Scenario: Texts on both majors
- **WHEN** `uv run pytest tests/kicad/board/test_board_items_oracle.py -k "text or graphic" -rA` runs on 10.0.6 and in the `kicad-9` job
- **THEN** `text-board-load` and `graphic-copper-silent` are `absent`, and `text-height` and `text-copper-short` are `present`, on both majors

#### Scenario: Dimensions on both majors
- **WHEN** `uv run pytest tests/kicad/board/test_board_items_oracle.py -k dimension -rA` runs on 10.0.6 and in the `kicad-9` job
- **THEN** `dim-load` is `present` and `dim-recompute` `equal` on both majors, and `dim-resave-text` is `equal` on 10.0.6

### Requirement: Keep-outs and area rules agree with the copper check
`tests/kicad/copper/test_copper_parity.py` SHALL compare `check_copper` with KiCad's DRC on a bench of `tests/kicad/copper/_copperparity.py` that holds, on two copper layers, tracks, vias and pads inside, across and outside keep-outs of each copper setting, and track pairs inside, across and outside a rule area named `HV` under a clearance rule of 2 mm scoped to it, settling `H-K-COPPER-AREA`.
- `copper-keepout-parity` MUST record `equal` when the items of the `copper.keepout` findings are exactly the items that `items_not_allowed` names, the footprint of a pads bench left out.
- `copper-area-parity` MUST record `equal` when the pairs of the `copper.clearance` findings whose source is the area rule are exactly the pairs that KiCad reports under that rule.
- The hermetic half (the findings of `check_copper` on the bench, without `kicad-cli`) MUST run in `tests/kicad/copper/test_parity_bench.py`.

#### Scenario: Parity on both majors
- **WHEN** `uv run pytest tests/kicad/copper/test_copper_parity.py -k "keepout or area" -rA` runs on 10.0.6 and in the `kicad-9` job
- **THEN** `copper-keepout-parity` and `copper-area-parity` are `equal` on both majors

#### Scenario: Hermetic half
- **WHEN** `uv run pytest tests/kicad/copper/test_parity_bench.py -k "keepout or area"` runs without `kicad-cli`
- **THEN** it passes, with the expected findings of the bench
