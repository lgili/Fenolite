## ADDED Requirements

### Requirement: Stack-up in the DSL
`fenolite.dsl.stack` SHALL provide the entries of a stack-up, and `Design.stackup(*entries, finish=None, impedance_controlled=False, locked=False)` SHALL declare the board's stack-up from its top face to its bottom face. `fenolite.dsl` MUST re-export `stack` and `stackup_locked` (an addition under "DSL package"), and `dsl/stack.py` MUST import only the standard library, `fenolite.core`, `fenolite.model` and the DSL's own `fenolite.dsl.errors` (`DslError`) and `fenolite.dsl.units` (DSL lengths).
- **Entries.** `stack.silkscreen(*, color="")`, `stack.mask(thickness, *, material="", epsilon_r=None, loss_tangent=None, color="")`, `stack.copper(thickness)`, `stack.core(thickness, *, material="", epsilon_r=None, loss_tangent=None, color="")` and `stack.prepreg(…)`, with the arguments of `core`, each MUST return a frozen `StackEntry`. A thickness is a DSL length ("DSL lengths and angles"); a copper, core or prepreg thickness MUST be above 0, and a mask's at least 0. `epsilon_r` and `loss_tangent` MUST be an `int`, a `fractions.Fraction` or a decimal text, `epsilon_r` above 0 and `loss_tangent` at least 0, and are stored as the shortest plain decimal (`"4.50"` gives `"4.5"`, `4` gives `"4"`); a `float`, a `bool`, a sign, an exponent or a value that is not a terminating decimal MUST raise `DslError` naming the value. `material` and `color` MUST be strings without surrounding blanks.
- **The call.** `stackup()` MUST be called after `board()`, and once. Its entries, top to bottom, MUST be: at most one silkscreen, then at most one mask; the copper entries, exactly as many as `board(copper=…)` declares, with at least one `core` or `prepreg` between neighbours and the dielectrics of one gap all of one kind; then at most one mask, then at most one silkscreen. Any other sequence, a `finish` that is neither `None` nor a non-empty string, and an `impedance_controlled` or `locked` that is not a `bool` MUST raise `DslError`, naming the position of the first entry out of place.
- **Names.** The copper entries MUST take the names of the board's copper layers from the top, `F.Cu`, `In1.Cu` … `In<n − 2>.Cu` and `B.Cu` for `copper=n`; every dielectric of the gap between the j-th and the (j + 1)-th copper entries the name `dielectric <j>`; masks and silkscreens `F.Mask`, `B.Mask`, `F.SilkS` and `B.SilkS`. These are the names that `kicad-file-backend` "Stack-up on boards" gives the same rows.
- **Model.** `to_model` MUST give the keyed `Board` of "DSL to model" a `Stackup` with the id `key_id("stackup")`, one `StackLayer` per entry with the id `key_id("stack_layer", "<k>")`, k from 0, `dielectric_kind` `core` or `prepreg` for those entries, `finish` (`""` for `None`) and `impedance_controlled`. `KEYS` MUST gain `stackup` (`stk`) and `stack_layer` (`sly`), and `docs/dsl.md` MUST list them in "Ids: the key table". A design without `stackup()` MUST give `Board.stackup = None`.
- `stackup_locked(design) -> bool` (`dsl/convert.py`) MUST return the `locked` argument, and `False` without a call.
- Fenolite MUST NOT supply a thickness, a material, a dielectric constant or a finish that the script does not give.

#### Scenario: Four layers in the model
- **GIVEN** `d.board(mm(50), mm(30), copper=4)` and `d.stackup(stack.mask("10um"), stack.copper("35um"), stack.prepreg("0.2mm", material="FR4", epsilon_r="4.50", loss_tangent="0.02"), stack.copper("17.5um"), stack.core("1.2mm", material="FR4", epsilon_r=4), stack.copper("17.5um"), stack.prepreg("0.2mm"), stack.copper("35um"), stack.mask("10um"), finish="ENIG")`
- **WHEN** `to_model` runs
- **THEN** `board.stackup` holds nine entries named `F.Mask`, `F.Cu`, `dielectric 1`, `In1.Cu`, `dielectric 2`, `In2.Cu`, `dielectric 3`, `B.Cu` and `B.Mask`; the first prepreg has `epsilon_r == "4.5"`; the core has `epsilon_r == "4"` and `dielectric_kind == "core"`; `finish == "ENIG"`; and `thickness() == 1_725_000`

#### Scenario: Stack-ups refused at the call
- **WHEN** these are called on fresh two-layer designs: `d.stackup(stack.copper("35um"), stack.copper("35um"))`; `d.stackup(stack.copper("35um"), stack.core("1.5mm"), stack.prepreg("0.1mm"), stack.copper("35um"))`; `stack.core("1.5mm", epsilon_r=4.5)`; and `d.stackup(stack.copper("35um"))` before `board()`
- **THEN** each raises `DslError`, the first naming position 1 and the third naming `4.5`

#### Scenario: No stack-up declared
- **GIVEN** the DSL design of `examples/blink_2layer/design.py`
- **WHEN** `to_model` runs and `stackup_locked` is called
- **THEN** `board.stackup is None` and `stackup_locked(design) is False`

### Requirement: Stack-up in a build
`fenolite build` SHALL write the stack-up that the script declares, and SHALL decide it against an existing board as `layout-lens` "Stack-up across rebuilds" states. This requirement adds a step to "Built project files" and a key to the `result` of "Build command".
- `lens.build.build_design` MUST keep `Board.stackup` of the model it is given and take `lock_stackup: bool = False`; `cmd_build` MUST pass `stackup_locked(design)`. On a created board the writer follows `kicad-file-backend` "Stack-up written to boards". `Design.validate()` of the design to write runs before writing, so a `model.stackup-*` error refuses the build and nothing is written.
- `result.stackup` MUST be `null` when the written board holds no stack-up, and otherwise `{"source": "script" | "board", "thickness": <nm>, "copper": <number of copper entries>}`, `source` naming whose stack-up the written board holds.
- A script without `stackup()` MUST build every file with the bytes it had before this change, for both targets.
- `--target altium` MUST keep the rule of `lens.altium_copper.stack_values`: a stack-up with one dielectric between neighbouring copper entries gives the document its values; any other gives the defaults and one `altium.not-lowered` info.

#### Scenario: Blink with a stack-up on both targets
- **GIVEN** a blink variant with `d.stackup(stack.mask("10um"), stack.copper("35um"), stack.core("1.5mm", material="FR4"), stack.copper("35um"), stack.mask("10um"), finish="ENIG")`
- **WHEN** it is built for targets 9 and 10 with `--confirm`, each board is read back, and each build runs again
- **THEN** each board's stack-up equals `complete` of the declared one by `stackup.values`, `general` holds `(thickness 1.59)`, `result.stackup` is `{"source": "script", "thickness": 1590000, "copper": 2}`, and the second build writes every file with the bytes of the first

#### Scenario: An invalid stack-up stops the build
- **GIVEN** a model, built in the test because the DSL refuses it, whose stack-up names only `F.Cu` and `B.Cu`, given to `build_design` with `copper=4`
- **WHEN** the build runs
- **THEN** no file is written and the issues hold `model.stackup-copper`

### Requirement: Stack-up presets
`stack.preset(name) -> tuple[StackEntry, ...]` SHALL return the entries of the packaged preset `fenolite/dsl/stackups/<name>.toml`, and `stack.PRESETS` SHALL list the names in code-point order.
- A preset file MUST hold `source` (an S-id of `docs/evidence/sources.md`), `url`, `retrieved` (an ISO date), `copper` (its copper count), an optional `finish`, and one `[[entry]]` table per entry with `kind` (`silkscreen`, `mask`, `copper`, `core` or `prepreg`), `thickness` (a length with a unit) and, where the page states them, `material`, `epsilon_r` and `loss_tangent`. Every value MUST be the page's, and no value the page does not state MUST appear.
- An unknown name MUST raise `DslError` listing `PRESETS`. The entries pass the checks of "Stack-up in the DSL" when they are given to `stackup()`.
- At most three presets ship with this change, and `docs/dsl.md` MUST list each with its source URL and date.

#### Scenario: Every preset is sourced and valid
- **WHEN** `uv run pytest tests/unit/dsl/test_stackup_presets.py` runs
- **THEN** the `source` of each file is a row of `docs/evidence/sources.md` whose URL equals the file's `url`, and `design.stackup(*stack.preset(name))` on a board of the preset's copper count raises nothing

#### Scenario: Unknown preset
- **WHEN** `stack.preset("nope")` is called
- **THEN** `DslError` is raised listing the names of `stack.PRESETS`
