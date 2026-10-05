## ADDED Requirements

### Requirement: Rule constructor in the DSL
`design.rules.rule(name, kind, *, where=select.ALL, between=None, layers=(), min=None, opt=None, max=None, severity="error", priority=0)` SHALL declare one design rule of any model kind (`fenolite.model.rules.RuleKind`), with selectors from `fenolite.dsl.select` ("Selectors in the DSL").
- `DslError` MUST be raised at the call, and nothing recorded, for: a `name` that is not a non-empty string or is already used by `rule()`; a `kind` outside `RuleKind`; no limit; a limit that is not a `Length` or a string with a unit; a negative `min`, or an `opt` or `max` of 0 or less; `min` above `opt` or `max`, or `opt` above `max`; a `where` or `between` that is not a selector; a `between` for a kind other than `clearance` and `creepage`; a `layers` value that is not a tuple of strings; a `severity` outside `error`, `warning` and `ignore`; a `priority` that is not an integer of 0 or more.
- What depends on the target is not checked here: limits per kind, kind support, globs, selector support and layer names are refused by the lowering with its codes, and `build` reports them (exit 7, `FEN-7001`).
- `Rules.named` MUST hold one `dsl.design.RuleSpec` per call, in call order.
- `dsl.to_model` MUST add one model `Rule` per call to `Design.rules.rules`, after the rules of `minimum()`, in call order: id `derived_id("rul", "dsl", "rule:named:<name>")`, the given name, kind, limits, severity and priority, `selector_a` from `where`, `selector_b` from `between` (`None` when not given) and `layers` as given.
- `docs/dsl.md` MUST describe `rule()` in its section "Design rules", with an example per kind group, and say that priority 0 is written first and governs least.

#### Scenario: Creepage rule in the model
- **GIVEN** a design with the classes `HV` and `LV` and `d.rules.rule("mains", "creepage", where=select.netclass("HV"), between=select.netclass("LV"), min=mm(6.4))`
- **WHEN** `to_model(d)` runs
- **THEN** `rules.rules` holds one `creepage` rule named `mains`, with `selector_a == Selector("netclass", "HV")`, `selector_b == Selector("netclass", "LV")`, `min == 6_400_000` and the id `derived_id("rul", "dsl", "rule:named:mains")`

#### Scenario: Board-wide hole pitch
- **WHEN** `d.rules.rule("pitch", "hole_to_hole", min="0.25mm")` is declared and the design is built for target 10
- **THEN** `<name>.kicad_dru` holds a rule `"fenolite_0_pitch"` with `(constraint hole_to_hole (min 0.25mm))` and no condition

#### Scenario: Second side refused for a hole kind
- **WHEN** `d.rules.rule("x", "hole_clearance", where=select.net("A"), between=select.net("B"), min=mm(0.3))` is called
- **THEN** `DslError` is raised naming `between` and `hole_clearance`, and nothing is recorded

#### Scenario: Target refusal reported by the build
- **GIVEN** a design with a `creepage` rule
- **WHEN** it is built with `--kicad-version 9 --dry-run --json`, and again with `--allow-lossy`
- **THEN** the first exits 7 with `FEN-7001`, a message that names the rule and says that KiCad 9.0 does not check creepage rules, and a hint naming `--allow-lossy`; the second exits 0 with `rules.dropped-for-target` in `issues`

### Requirement: Selectors in the DSL
`fenolite.dsl.select` SHALL build rule selectors: `ALL`, `net(name)`, `netclass(name)`, `ref(name)` and `item(kind)`, each a `select.Select`, combined with `&` (and), `|` (or) and `~` (not); `fenolite.dsl` SHALL re-export `select` (an addition under "DSL package").
- `net` MUST take a net name or a `Net`, `netclass` a class name declared with `design.rules.netclass`, `ref` a reference or a `Part`, and `item` one of `track`, `via`, `pad` and `zone`. A `Net` or `Part` MUST be stored by its name, so a rule follows a rename made where the object is created. An empty name, or an `item` value outside the list, MUST raise `DslError`.
- `a & b` MUST give `Selector("and", items=…)` and `a | b` `Selector("or", items=…)`, flattening nested operations of the same op; `~a` MUST give `Selector("not", items=(a,))`. `ALL` MUST NOT be combined: `ALL & x` raises `DslError`.
- A name MAY hold `*`, which the model keeps as a glob; whether a target writes it is decided by the lowering (`rules-model`, "Closed selector grammar").
- `Select.to_model()` MUST return the model `Selector`, and two equal expressions MUST give equal selectors.

#### Scenario: Compound selector
- **WHEN** `(select.net("A") | select.net("B")) & ~select.item("via")` is turned into a model selector
- **THEN** it is `Selector("and", items=(Selector("or", items=(Selector("net", "A"), Selector("net", "B"))), Selector("not", items=(Selector("item_kind", "via"),))))`

#### Scenario: Net object
- **GIVEN** `vbus = Net("VBUS")` added to the design and a rule with `where=select.net(vbus)`
- **WHEN** `to_model` runs
- **THEN** the rule's `selector_a` is `Selector("net", "VBUS")`

#### Scenario: ALL combined
- **WHEN** `select.ALL & select.net("A")` is evaluated
- **THEN** `DslError` is raised

## MODIFIED Requirements

### Requirement: Rule minimums in the DSL
`design.rules.minimum(*, clearance=None, track_width=None, via_diameter=None, via_drill=None, hole_size=None, edge_clearance=None, netclass=None)` SHALL declare one design-rule minimum per given length. The keywords are the first six rule kinds of the model (`fenolite.model.rules.RuleKind`), listed in this order by `dsl.design.MINIMUM_KINDS`; the other kinds are declared with `rule()` ("Rule constructor in the DSL").
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
