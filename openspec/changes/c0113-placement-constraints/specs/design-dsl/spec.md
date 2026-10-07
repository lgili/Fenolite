## ADDED Requirements

### Requirement: Placement rules in the DSL
`Design.near(key, parts, anchor, *, within, severity="error")` SHALL record a proximity rule, and `to_model` SHALL write it into the model of `design-model`, "Proximity rules in the model". It is an addition that "DSL package" and "DSL to model" allow: no new name is re-exported, and a design without the call gives the model it gave before.
- `key` MUST match the pattern of copper keys (`^[A-Za-z0-9_.+-]+(/[A-Za-z0-9_.+-]+)*$`) and MUST NOT name another `near` rule of the design. `parts` and `anchor` each MUST be a `PadRef`, a `Part`, a `Module`, or a non-empty list or tuple of them. `within` MUST be a positive length ("DSL lengths and angles"), and `severity` `"error"` or `"warning"`. `DslError` MUST be raised at the call otherwise; for a `PinHandle` its message MUST give the hint `part.pad(<number>)`.
- **Conversion.** `to_model` MUST turn a `Part` into `PadSelection(<path>)`, a `PadRef` into `PadSelection(<path>, <number>, <index>)` and a `Module` into one `PadSelection(<path>)` per part of it and of its sub-modules, in path order, and MUST raise `DslError` naming a part or module that is not in the design. It MUST write `RuleSet.proximity` in key order.
- The argument `anchor` is the reference side of the rule. It is neither a point in a part's frame nor a placement: this requirement adds no attribute named `anchor` to `Part` or `Design`.

#### Scenario: Decoupling rule recorded
- **GIVEN** the blink with `design.near("dec", r1.pad(2), (u1.pad(1), u1.pad(9)), within=mm(3))`
- **WHEN** `uv run pytest tests/unit/dsl/test_placement_rules.py -k recorded` runs `to_model`
- **THEN** `RuleSet.proximity` is `(ProximityRule("dec", (PadSelection("R1", "2"),), (PadSelection("U1", "1"), PadSelection("U1", "9")), 3_000_000),)`

#### Scenario: Module expanded
- **GIVEN** a module `ch1` holding `U1` and `C1`, a sub-module `ch1/fb` holding `R1`, and `design.near("ch1", ch1, ch1_u1, within=mm(15))`
- **WHEN** `to_model` runs
- **THEN** the rule's `parts` are `PadSelection("ch1/C1")`, `PadSelection("ch1/U1")` and `PadSelection("ch1/fb/R1")`, in this order

#### Scenario: Refused calls
- **WHEN** `design.near("a b", r1, u1, within=mm(1))`, `design.near("k", (), u1, within=mm(1))`, `design.near("k", r1[1], u1, within=mm(1))`, `design.near("k", r1, u1, within=mm(0))`, `design.near("k", r1, u1, within=mm(1), severity="ignore")` and `design.near("dup", r1, u1, within=mm(1))` twice are called
- **THEN** each raises `DslError`, the third with the hint `part.pad(<number>)` and the sixth on its second call

#### Scenario: Unchanged designs
- **WHEN** `to_model` runs on the blink, which does not call `near`
- **THEN** `canonical.dump_texts` of its model gives the texts it gave before this change

### Requirement: Placement keep-outs in the DSL
`design.rule_area(name, outline, *, layers=None, forbid=())` of c0103 ("Rule areas in the DSL") SHALL also take `"footprints"` in `forbid`, mapped to `Keepout.no_footprints`, so that the KiCad build writes `(footprints not_allowed)` and the legality checks of `place` and `build` judge the area ("Placement legality", capability `placement`). For this value the list of `forbid` values, the clause `no_footprints == False` and the refused call `forbid=("footprints",)` of "Rule areas in the DSL" no longer hold; when that requirement is living, this one is replaced by a MODIFIED delta of it.
- **The Altium target.** `build --target altium` MUST handle the area as it handles any rule area ("Rule areas in the DSL" and the Altium requirement of the change that adds them). The restriction on footprints MUST NOT be dropped silently: the build MUST give one `altium.not-lowered` info whose `where` is the kind `keepout-footprints` (`backends.altium.lower`), naming the areas, and the kind MUST NOT be in `LOSS_KINDS`. No Altium record is written for the restriction until `docs/formats/altium/` holds a fact row for it.

#### Scenario: Antenna keep-out
- **GIVEN** the blink with `design.rule_area("ANT", <a 6 mm × 6 mm square over R1>, layers=("F.Cu",), forbid=("footprints",))`
- **WHEN** `uv run pytest tests/unit/dsl/test_placement_rules.py -k keepout` builds it with `--dry-run --json`
- **THEN** the model's `Keepout` named `ANT` has `no_footprints` true, the planned board text holds `(footprints not_allowed)` once, and `issues` hold one `place.keepout` warning naming `R1` and `ANT`

#### Scenario: Antenna keep-out in an Altium build
- **GIVEN** the same design
- **WHEN** `uv run pytest tests/unit/cli/test_build_altium.py -k keepout_footprints` builds it with `--target altium --dry-run --json`
- **THEN** the exit code is 0, and `issues` hold one `altium.not-lowered` info whose `where` is `keepout-footprints` and whose message names `ANT`

## MODIFIED Requirements

### Requirement: Placement legality in a build
`fenolite build` with the KiCad target (`--target kicad`, the default) SHALL judge the placement of the board it is about to write with `fenolite.placement.legality.check` (`placement`, "Placement legality") and its placement rules with `fenolite.checks.placement.judge` (`placement`, "Placement rules judged"), in `cmd_build.placement_guard`, after `lens.build.build_design` returns its files and before `cmd_build` returns its plan, on `--dry-run` and `--confirm` alike. When `build_design` refused (no files), the check MUST NOT run and `result.placement.ran` MUST be false. With `--target altium` the check MUST NOT run and `result` holds no `placement`.
- **What is judged.** `cmd_build` MUST read the planned `<name>.kicad_pcb` text back with `read_board`, take the extents from c0028's `BoardFrame.placed_extents` of `KicadBackend`, the rings from `backends.kicad.outline.board_outline` of that board, the keep-outs from that board's `Keepout`s, and `edge_clearance` from `placement.legality.edge_clearance` of the built model design (0 without a board-wide `edge_clearance` rule). `judge` MUST take the pads of `BoardFrame.board_pads` of that board and `rules_of(<built model design>)`. The check therefore judges the bytes that will be written, preserved placements (`layout-lens`) included. It MUST read and write no file.
- Each `place.*` and `placement.*` issue MUST be reported with a severity no higher than `warning`, so a build never refuses and never exits 5 for placement.
- Parts that the build stages (`result.staged`, reported as `layout.unplaced`) MUST NOT be judged by the legality check; `judge` reports rules that name them as `placement.rule-skipped`.
- **Codes.** The codes are those of `placement.ISSUE_CODES` (`placement`, "Placement issue codes") and the `placement.*` codes of `verification-loop`, "Placement stage issue codes". They are not build findings: they join the envelope's `issues` as "Build issue codes" allows for codes that later requirements add, and `lens.build.BUILD_ISSUE_CODES` and `build_design` stay unchanged, because `lens` may not import `placement` or `checks` (`package-layering`).
- `result.placement` MUST hold `ran`, `counts`, the number of issues by code, and `rules`, the counts of `judge`.
- **The Altium target.** With `--target altium` no placement rule is judged at the build. The proximity rules of the design are stored in `.fenolite/rules.json` as on the KiCad target, and the build MUST say that it did not judge them in one `altium.not-lowered` info whose `where` is the kind `placement-rule` (`backends.altium.lower`), naming their count and that `fenolite check` judges them (`verification-loop`, "Placement rules stage"); the kind MUST NOT be in `LOSS_KINDS`. A design without proximity rules gives no such info and the bytes it gave before.
- The step of `cmd_build` and the `result` key are additions that "Build command" allows.

#### Scenario: Overlap reported, build written
- **GIVEN** a blink variant whose `R1` and `D1` are placed on the same side with courtyards that overlap by 0.1 mm and copper that stays clear
- **WHEN** `fenolite build … --confirm` runs
- **THEN** the exit code is 0, the board is written, and `issues` holds one `place.courtyard-overlap` warning naming `D1,R1`

#### Scenario: Part over the edge
- **GIVEN** a blink variant whose `R1` is placed across the outline's right edge
- **WHEN** the build runs with `--dry-run`
- **THEN** `issues` holds `place.outside-outline` naming `R1` as a warning, and nothing is written

#### Scenario: Staged parts are not judged
- **GIVEN** a blink variant in which `R1` has no `place()`
- **WHEN** the build runs
- **THEN** `issues` holds `layout.unplaced` for `R1` and no `place.outside-outline` for it

#### Scenario: Clean blink stays clean
- **WHEN** the blink is built for targets 9 and 10
- **THEN** `issues` holds no `place.*` or `placement.*` issue, `result.placement.counts` is empty, `result.placement.rules` counts nothing, and every file has the bytes it had before this change

#### Scenario: Rules reported as warnings
- **GIVEN** the blink with `design.near("led", d1, r1.pad(2), within=mm(5))`
- **WHEN** `uv run pytest tests/unit/cli/test_build_placement_guard.py -k rules` builds it with `--dry-run --json`
- **THEN** the exit code is 0, `issues` hold one `placement.too-far` warning naming `D1`, and `result.placement.rules` is `{"near": {"judged": 1, "failed": 1, "skipped": 0}}`

#### Scenario: Rules of an Altium build are stored and announced
- **GIVEN** the routed blink with `design.near("led", d1, r1.pad(2), within=mm(5))`
- **WHEN** `uv run pytest tests/unit/cli/test_build_altium.py -k placement_rule` builds it with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `result` holds no `placement`, the planned `.fenolite/rules.json` holds the rule under `proximity`, `issues` hold one `altium.not-lowered` info whose `where` is `placement-rule`, and no `placement.*` issue
