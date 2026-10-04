## ADDED Requirements

### Requirement: Rule minimums in the DSL
`design.rules.minimum(*, clearance=None, track_width=None, via_diameter=None, via_drill=None, hole_size=None, edge_clearance=None, netclass=None)` SHALL declare one design-rule minimum per given length. The keywords are the six rule kinds of the model (`fenolite.model.rules.RuleKind`), listed in this order by `dsl.design.MINIMUM_KINDS`.
- A value MUST be a `Length` or a string with a unit, as "DSL lengths and angles" rules, and MUST be above 0.
- `netclass=None` declares board minimums. `netclass="<name>"` declares minimums for the nets of that class, which MUST already be declared with `design.rules.netclass`.
- `minimum()` MAY be called several times. `DslError` MUST be raised at the call for: no length given; a bare number, a value without a unit or a value of 0 or less; a `netclass` that is not a declared class; and a kind declared twice for the same scope (the board, or one class). A refused call MUST record nothing.
- `Rules.minimums` MUST hold one `dsl.design.MinimumSpec(kind, netclass, min)` per declared minimum, keyed by `(kind, netclass)`, with `min` in integer nanometres.
- `dsl.to_model` MUST write one model `Rule` per minimum into `Design.rules.rules`:

  | field | board minimum | class minimum |
  |---|---|---|
  | `id` | `derived_id("rul", "dsl", "rule:<kind>")` | `derived_id("rul", "dsl", "rule:<kind>:<class>")` |
  | `name` | `min_<kind>` | `min_<kind>_<class>` |
  | `selector_a` | `Selector("all")` | `Selector("netclass", "<class>")` |
  | `priority` | `0` | `1` |

  with `kind` the keyword, `min` the value, severity `error`, and no `selector_b`, `layers`, `opt` or `max`. The rules MUST be in this order: board minimums, then class minimums by class name, each group in the order of `MINIMUM_KINDS`. The order of the `minimum()` calls MUST NOT change the model.
- The priorities make a class minimum govern the items of its class over the board minimum of the same kind (`rules-model`, "Lowered rules follow priority").
- The KiCad build needs no step of its own: `write_triad` lowers `Design.rules` to `<name>.kicad_dru` (`rules-model`, "Fenolite lowers only the design's rules") and to the board-setup minimums of `<name>.kicad_pro` ("Board-wide rules lower to board-setup minimums"), with the issues of those requirements. A design without `minimum()` calls MUST build the same bytes as before this requirement.
- `docs/dsl.md` MUST describe `minimum()` in a section "Design rules", list it in the API section, and hold the `rule` row in the key table.

#### Scenario: Board and class minimums in the model
- **GIVEN** a design with the class `PWR`, `d.rules.minimum(track_width=mm(0.6), netclass="PWR")` and then `d.rules.minimum(clearance=mm(0.15), track_width="0.25mm")`
- **WHEN** `to_model(d)` runs
- **THEN** `rules.rules` holds, in this order, `min_clearance` (`clearance`, `all`, `min == 150_000`, priority 0), `min_track_width` (`track_width`, `all`, `min == 250_000`, priority 0) and `min_track_width_PWR` (`track_width`, `netclass PWR`, `min == 600_000`, priority 1), and the id of the last is `derived_id("rul", "dsl", "rule:track_width:PWR")`

#### Scenario: Call order does not matter
- **GIVEN** two designs that make the same `minimum()` calls in opposite orders
- **WHEN** `canonical.dump_texts(to_model(d))["rules.json"]` is taken for both
- **THEN** the two texts are byte-identical

#### Scenario: Refused calls
- **WHEN** `d.rules.minimum()`, `d.rules.minimum(clearance=0.2)`, `d.rules.minimum(clearance=mm(0))`, `d.rules.minimum(clearance=mm(0.2), netclass="HV")` without a class `HV`, and a second `d.rules.minimum(clearance=mm(0.3))` after `d.rules.minimum(clearance=mm(0.2))` are called
- **THEN** each raises `DslError` naming `minimum()`, and `d.rules.minimums` holds only the minimum of the accepted call

#### Scenario: Built rules and minimums
- **GIVEN** the blink design with `d.rules.minimum(clearance=mm(0.15), track_width=mm(0.25))` and `d.rules.minimum(clearance=mm(0.2), track_width=mm(0.5), netclass="PWR")`
- **WHEN** it is built for target 10
- **THEN** `blink.kicad_dru` holds the rules `fenolite_0_min_clearance`, `fenolite_0_min_track_width`, `fenolite_1_min_clearance_pwr` and `fenolite_1_min_track_width_pwr` in this order, the last two with the condition `"A.NetClass == 'PWR'"`; `board.design_settings.rules` of `blink.kicad_pro` has `min_clearance == 0.15` and `min_track_width == 0.25`; and `.fenolite/rules.json` holds the four rules

#### Scenario: Unchanged without minimums
- **GIVEN** the blink design without a `minimum()` call
- **WHEN** it is built for target 10
- **THEN** `blink.kicad_dru` is `(version 1)\n` and `.fenolite/rules.json` holds no rule

#### Scenario: Rebuild replaces the minimums
- **GIVEN** a built project whose script declares `minimum(track_width=mm(0.25))`, and a rule named `mine` added to its `.kicad_dru` by hand
- **WHEN** the script changes the value to `mm(0.3)` and the project is built again
- **THEN** the rules file holds `fenolite_0_min_track_width` once, with `(min 0.3mm)`, followed by the rule `mine`

## MODIFIED Requirements

### Requirement: Net classes in the DSL
`design.rules.netclass(name, *, clearance=None, track_width=None, via_diameter=None, via_drill=None, nets=())` SHALL declare one net class whose values are lengths and whose members are the given `Net` objects.
- Each given net joins the design and gets `Net.netclass_id` of that class in the model.
- A class name used twice, or a net given to two classes, MUST raise `DslError`.
- A net class adds no rule to the model `RuleSet`. The only rule constructor is `design.rules.minimum` ("Rule minimums in the DSL"); without a call to it the `RuleSet` of a DSL design is empty, and the build lowers it through c0018 to `(version 1)`.

#### Scenario: Class with members
- **GIVEN** `d.rules.netclass("PWR", clearance=mm(0.2), track_width=mm(0.5), nets=(vin, gnd))`
- **WHEN** `to_model(d)` runs
- **THEN** the model holds a `NetClass` named `PWR` with `clearance == 200_000` and `track_width == 500_000`, and the nets `VIN` and `GND` carry its id in `netclass_id`

#### Scenario: Net in two classes
- **WHEN** a net already in `PWR` is given to a second class `SIG`
- **THEN** `DslError` is raised naming the net and both classes

### Requirement: DSL to model
`dsl.to_model(design) -> fenolite.model.Design` SHALL convert a DSL design into model types only, with the ids of `design-model` "Identifier derivation" (fourth case).
- **Circuit.** One `Component` per added part, with `ref`, `value`, `lib_symbol_ref`, `lib_footprint_ref` (empty when `Part.footprint` is `None`), empty `pins`, empty `path` and `properties` holding `"fenolite.path"` mapped to the component path and every entry of `Part.properties` ("User properties in the DSL"), keys in code-point order. Nets whose `PinRef.pin` holds the designator as written. Net classes with `Net.netclass_id`. Interfaces. One `Module` per DSL module, with `path`, `parent` and `component_ids`.
- **Board.** A keyed `Board` without layers and footprints, whose `Outline` is the rectangle from `BOARD_ORIGIN` to `BOARD_ORIGIN + (width, height)` in the order of c0017's "Outline lowering", or no outline when `board()` was not called.
- **Other layers.** A keyed `RuleSet` holding the rules of "Rule minimums in the DSL" (empty without a `minimum()` call), a keyed `Manifest` and a keyed header named after the design.
- Every object MUST have `provenance = None`, so no absolute user path reaches `.fenolite/`.
- `to_model` MUST NOT call `Design.validate()`, MUST NOT resolve libraries, and MUST NOT change the DSL design.

#### Scenario: Blink in the model
- **GIVEN** the DSL design of `examples/blink_2layer/design.py`
- **WHEN** `to_model` runs
- **THEN** `R1` has `lib_symbol_ref == "Mini:Mini_R"`, `lib_footprint_ref == "Mini:Mini_R_0603"`, `pins == ()`, `path == ""` and `properties == {"fenolite.path": "R1"}`, and the outline points are (100 mm, 100 mm), (150 mm, 100 mm), (150 mm, 130 mm) and (100 mm, 130 mm)

#### Scenario: Designators as written
- **GIVEN** `connect(gnd, u1["GND"])`
- **WHEN** `to_model` runs
- **THEN** the net `GND` holds `PinRef(<U1 id>, "GND")`

#### Scenario: No provenance and no absolute path
- **WHEN** the texts of `canonical.dump_texts(to_model(design))` are searched for the absolute path of the script folder
- **THEN** no text contains it, and no entity has a provenance

#### Scenario: User properties in the model
- **GIVEN** `Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330", properties={"Supplier code": "S-1", "Part number": "PN-330"})` added to a design
- **WHEN** `to_model` runs
- **THEN** the component `R1` has `properties == {"Part number": "PN-330", "Supplier code": "S-1", "fenolite.path": "R1"}`, with its keys in this order
