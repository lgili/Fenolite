## ADDED Requirements

### Requirement: Part heights and height limits in the DSL
The keyword-only `height=None` of `Part(…)`, `dsl.heights(design)` and `Design.height_limit(area, *, max, severity="error")` SHALL let a script state how tall a part is and where parts may not be tall. They are additions that "DSL package" and "DSL to model" allow, and a design that uses none of them gives the model and the intents it gave before.
- **Heights.** `Part(…, height=h)` MUST take `None` or a positive length ("DSL lengths and angles"), else raise `DslError`; `Part.height` holds the value in nm. It is the top of the part's body above the board surface on the part's own side.
- **Hand-over.** `dsl.heights(design) -> Mapping[str, Nm]` MUST return the height of each part that states one, by component path, in path order; `fenolite.dsl` MUST re-export it. `to_model` MUST NOT put a height into the circuit: `Component` has no height field, and the build turns each entry into a body on the placed footprint ("Part heights in a build"). `outward_height` (`design-model`, "Outward height of a part") is then the only reader.
- **`height_limit`.** `area` MUST match `^[A-Za-z0-9_.+-]+$` and MUST NOT carry a limit already; `max` MUST be a positive length and `severity` `"error"` or `"warning"`; `DslError` otherwise. The area is not looked up at the call: an area drawn in KiCad is known only on the board. `to_model` MUST write the limits into `RuleSet.heights` in area order (`design-model`, "Height limits in the model").
- A rule area that forbids nothing and carries a name ("Rule areas in the DSL") serves as the area of a limit.

#### Scenario: A height recorded
- **GIVEN** the blink with `Part("J1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", height=mm(9))` added and `design.height_limit("LID", max=mm(5))`
- **WHEN** `uv run pytest tests/unit/dsl/test_part_height.py -k recorded` calls `heights(design)` and `to_model(design)`
- **THEN** `heights(design) == {"J1": 9_000_000}`, `RuleSet.heights` is `(HeightLimit("LID", 5_000_000),)`, and no component of the model has a height attribute

#### Scenario: Refused calls
- **WHEN** `Part("R9", "Mini:Mini_R", height=mm(-1))`, `Part("R9", "Mini:Mini_R", height=0)`, `design.height_limit("L I D", max=mm(5))`, `design.height_limit("LID", max=mm(0))`, `design.height_limit("LID", max=mm(5), severity="ignore")` and `design.height_limit("LID", max=mm(5))` twice are called
- **THEN** each raises `DslError`, the last on its second call

#### Scenario: Unchanged designs
- **WHEN** `to_model` and `heights` run on the blink, which uses neither call
- **THEN** `heights(design)` is empty and `canonical.dump_texts` of its model gives the texts it gave before this change

### Requirement: Part heights in a build
`fenolite build` SHALL turn each entry of `dsl.heights(design)` into a body of the part's placed footprint, and its placement guard SHALL judge the design's height limits.
- **The body.** `lens.build.build_design(…, heights=None)` MUST give the placed footprint of each named component path one `ComponentBody` with the id `derived_id("bdy", "dsl", "height:<path>")`, `kind == "extruded"`, `height` the stated value, `standoff == 0`, an empty `outline`, no signed bounds and `name == "height"`, after the bodies its definition brings. A path that names no placed footprint MUST be ignored without an issue: the part is reported where it is missing. The lens receives plain data and MUST NOT import `fenolite.dsl`.
- **Kept in `.fenolite/`.** As "Component bodies" says, no KiCad file changes. `.fenolite/board.json` MUST hold the body on its footprint, also after a rebuild over an existing board: the merge of `layout-lens` MUST carry the built footprint's `bodies` onto the footprint it keeps, because a KiCad file holds no body.
- **The guard.** With the KiCad target, `cmd_build.placement_guard` ("Placement legality in a build") MUST also run `checks.placement.judge_heights` (`placement`, "Height limits judged") with the limits and the heights of the built model, on the planned board read back. Each `placement.too-tall` and `placement.height-unknown` MUST be reported with a severity no higher than `warning`, so a build never refuses for a height. `result.placement.rules` MUST gain the family `height`.
- **The Altium target.** `build --target altium` MUST store `RuleSet.heights` in `.fenolite/rules.json` and judge none of them; the `altium.not-lowered` info of kind `placement-rule` that "Placement legality in a build" gives for placement rules MUST count the height limits too, and MUST be given when the design holds only height limits. A body from `Part(height=…)` has no outline: with `--altium-bodies extruded` it MUST be counted under the kind `body` of `altium.not-lowered` as any body without an outline is (`altium-pcb-writer`, "Component bodies are reported"), and without the option no body is written. The stored board of an Altium build keeps the rule of that requirement: it holds the bodies that were written, so it does not hold this one.
- A design without `height=` and without a limit MUST build the bytes it built before this change, for both targets.

#### Scenario: The body is stored and survives a rebuild
- **GIVEN** the blink with `R1` created with `height=mm(9)`, built with `--confirm` into `B`
- **WHEN** `uv run pytest tests/unit/lens/test_build_bodies.py -k rebuild` loads `B/.fenolite/board.json`, then builds the same script again over `B` and loads it again
- **THEN** both times the footprint of `R1` holds one body with `height == 9_000_000`, `kind == "extruded"` and an empty outline, `outward_height` of it is `9_000_000`, no other footprint holds a body, and `B/blink.kicad_pcb` has the bytes of a build without `height=`

#### Scenario: Limits reported as warnings
- **GIVEN** the blink with `R1` created with `height=mm(9)`, `design.rule_area("LID", <an outline that covers the top-side parts R1 and U1 and no other part>, layers=("F.Cu",))` and `design.height_limit("LID", max=mm(5))`
- **WHEN** `uv run pytest tests/unit/cli/test_build_placement_guard.py -k height` builds it with `--dry-run --json`
- **THEN** the exit code is 0, `issues` hold one `placement.too-tall` warning naming `R1` and one `placement.height-unknown` warning naming `U1`, and `result.placement.rules.height` is `{"judged": 2, "failed": 1, "unknown": 1}`

#### Scenario: An Altium build stores and announces
- **GIVEN** the routed blink with `R1` created with `height=mm(9)` and `design.height_limit("LID", max=mm(5))`
- **WHEN** `uv run pytest tests/unit/cli/test_build_altium.py -k height` builds it with `--target altium --altium-bodies extruded --dry-run --json`
- **THEN** the exit code is 0, the planned `.fenolite/rules.json` holds the limit under `heights`, `issues` hold one `altium.not-lowered` info whose `where` is `placement-rule` and one `altium.not-lowered` whose `where` is `body/<the body id>`, no `placement.*` issue, and the planned documents equal those of the build without `height=` and without the limit
