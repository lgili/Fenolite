## ADDED Requirements

### Requirement: Pair selectors in the DSL
`fenolite.dsl.select` SHALL also provide `pair(x)`, a `select.Select` of the leaf `diff_pair` (`rules-model`, "Closed selector grammar"), which combines with `&`, `|` and `~` as the selectors of "Selectors in the DSL" do.
- `x` MUST be a `DiffPair`, a `USB2`, or another `Interface` of a kind of `fenolite.model.pairs.PAIR_ROLES`. `pair(x)` MUST then give `Selector("diff_pair", <base>)`, the base being `pair_base(<positive net name>, <negative net name>)` (`design-model`, "Differential pairs in the model"). When the names do not pair, `DslError` MUST be raised naming both nets and `coupled_name` of the positive one.
- `x` MAY be a non-empty string without surrounding blanks, which is taken as a base; `"*"` selects every pair.
- Any other `x` MUST raise `DslError`.

#### Scenario: Base of a USB pair
- **GIVEN** `usb = USB2(Net("USB_DP"), Net("USB_DN"))`
- **WHEN** `select.pair(usb).to_model()` is evaluated
- **THEN** it is `Selector("diff_pair", "USB_D")`

#### Scenario: Names that do not pair
- **WHEN** `select.pair(USB2(Net("USB_DP"), Net("USB_DM")))` is evaluated
- **THEN** `DslError` is raised naming `USB_DP`, `USB_DM` and `USB_DN`

#### Scenario: Every pair but one net
- **WHEN** `(select.pair("*") & ~select.net("CLK_P")).to_model()` is evaluated
- **THEN** it is `Selector("and", items=(Selector("diff_pair", "*"), Selector("not", items=(Selector("net", "CLK_P"),))))`

### Requirement: Pair rules in the DSL
`design.rules.pair(pair, *, gap_min=None, gap_max=None, clearance=None, uncoupled_max=None, skew_max=None, length_min=None, length_max=None, severity="error", priority=1)` SHALL declare the rules of one differential pair, each through "Rule constructor in the DSL" with `where=select.pair(pair)`:

| given | kind | limits | name |
|---|---|---|---|
| `gap_min`, `gap_max` | `diff_pair_gap` | `min`, `max` | `pair:<pair name>:gap` |
| `clearance` | `clearance`, with `between=select.pair(pair)` | `min` | `pair:<pair name>:clearance` |
| `uncoupled_max` | `diff_pair_uncoupled` | `max` | `pair:<pair name>:uncoupled` |
| `skew_max` | `diff_pair_skew` | `max` | `pair:<pair name>:skew` |
| `length_min`, `length_max` | `length` | `min`, `max` | `pair:<pair name>:length` |

- `pair` MUST be an interface that `select.pair` accepts, and the call MUST add it to the design. A call that gives no limit, or one of whose rules "Rule constructor in the DSL" refuses, MUST raise `DslError` naming `pair()` and record nothing.
- `severity` and `priority` MUST be given to every rule of the call. With the default priority 1, the pair's rules come after the class minimums of `minimum(netclass=…)`, which also have priority 1, because ties are broken by name and `pair:` sorts after `min_` (`rules-model`, "Lowered rules follow priority"); so they govern the pair's items.
- The rules MUST reach the model as the rules of `rule()` do, in the order of the table, and the build lowers them with the rest.

#### Scenario: Rules of a USB pair
- **GIVEN** `usb = USB2(usb_p, usb_n, name="USB")` on the nets `USB_P` and `USB_N`, and `d.rules.pair(usb, gap_min=mm(0.13), gap_max=mm(0.17), clearance=mm(0.13), skew_max=mm(0.15))`
- **WHEN** `to_model(d)` runs and the design is built for target 10
- **THEN** `rules.rules` holds `pair:USB:gap` (`diff_pair_gap`, `min == 130_000`, `max == 170_000`), `pair:USB:clearance` (`selector_a` and `selector_b` both `Selector("diff_pair", "USB_")`) and `pair:USB:skew` (`diff_pair_skew`, `max == 150_000`), each with priority 1; and `<name>.kicad_dru` holds `fenolite_1_pair_usb_gap` with `(constraint diff_pair_gap (min 0.13mm) (max 0.17mm))` and the condition `"A.inDiffPair('USB_')"`

#### Scenario: Nothing given
- **WHEN** `d.rules.pair(usb)` is called
- **THEN** `DslError` is raised naming `pair()`, and nothing is recorded

#### Scenario: Pair rule after a class minimum
- **GIVEN** the class `USB` holding the pair's nets, `d.rules.minimum(clearance=mm(0.2), netclass="USB")` and `d.rules.pair(usb, clearance=mm(0.13))`
- **WHEN** the design's rules are lowered for target 10
- **THEN** `fenolite_1_pair_usb_clearance` is written after `fenolite_1_min_clearance_usb`

## MODIFIED Requirements

### Requirement: Net classes in the DSL
`design.rules.netclass(name, *, clearance=None, track_width=None, via_diameter=None, via_drill=None, diff_pair_width=None, diff_pair_gap=None, diff_pair_via_gap=None, nets=())` SHALL declare one net class whose values are lengths and whose members are the given `Net` objects.
- Each given net joins the design and gets `Net.netclass_id` of that class in the model.
- A class name used twice, or a net given to two classes, MUST raise `DslError`.
- Each value MUST be a length as "DSL lengths and angles" states. `dsl.to_model` MUST write the seven values into the model `NetClass`, the last three into `diff_pair_width`, `diff_pair_gap` and `diff_pair_via_gap` (`design-model`, "Differential pairs in the model").
- A net class adds no rule to the model `RuleSet`. Rules come from `minimum()`, `rule()` and `pair()`; without them the `RuleSet` of a DSL design is empty, and the build lowers it to `(version 1)`.

#### Scenario: Class with members
- **GIVEN** `d.rules.netclass("PWR", clearance=mm(0.2), track_width=mm(0.5), nets=(vin, gnd))`
- **WHEN** `to_model(d)` runs
- **THEN** the model holds a `NetClass` named `PWR` with `clearance == 200_000` and `track_width == 500_000`, and the nets `VIN` and `GND` carry its id in `netclass_id`

#### Scenario: Net in two classes
- **WHEN** a net already in `PWR` is given to a second class `SIG`
- **THEN** `DslError` is raised naming the net and both classes

#### Scenario: Class with pair values
- **GIVEN** `d.rules.netclass("USB", clearance=mm(0.2), diff_pair_width=mm(0.3), diff_pair_gap="0.15mm", nets=(usb_p, usb_n))`
- **WHEN** `to_model(d)` runs
- **THEN** the model class `USB` has `diff_pair_width == 300_000`, `diff_pair_gap == 150_000` and `diff_pair_via_gap is None`, and `rules.rules` is empty

### Requirement: Interfaces in the DSL
`Interface(name, kind, members)`, `Power(hv, lv, *, name=None)` and `DiffPair(p, n, *, name=None)` SHALL record groups of nets as model `Interface` entities, without any model delta.
- `Power(hv, lv)` MUST become `Interface(kind="power", members={"hv": <net id>, "lv": <net id>})`, and `DiffPair(p, n)` MUST become `Interface(kind="diff_pair", members={"p": <net id>, "n": <net id>})`.
- The default name MUST be `"<first net name>/<second net name>"`.
- Member nets join the design.
- Interfaces are not written to KiCad files, which hold no pair object: a pair reaches KiCad through its net names and the rules that select it (`rules-model`, "Closed selector grammar"). A build MUST give one `build.interface-not-lowered` info per `diff_pair` and per `usb2` interface ("Typed interfaces in the DSL") that no rule of the design selects, a rule selecting it when one of its `diff_pair` leaves matches the pair's base (`design-model`, "Differential pairs in the model"). The nets of each such pair MUST pass the name check of "Interface checks in a build".

#### Scenario: Power interface
- **GIVEN** `Power(vin, gnd)` added to a design
- **WHEN** `to_model` runs
- **THEN** the model holds an `Interface` named `VIN/GND` with kind `power` and members `hv` and `lv` equal to the ids of `VIN` and `GND`

#### Scenario: Diff pair reported
- **GIVEN** a blink variant holding `DiffPair(usb_p, usb_n)` on nets `USB_P` and `USB_N`
- **WHEN** it is built with `--dry-run`
- **THEN** `issues` holds one info `build.interface-not-lowered` naming `USB_P/USB_N`

#### Scenario: Diff pair names checked
- **GIVEN** a blink variant holding `DiffPair(clk_p, clk_n)` on nets `CLK_P` and `CLKN`
- **WHEN** it is built with `--dry-run --json`
- **THEN** `issues` hold one info `build.interface-not-lowered` naming `CLK_P/CLKN` and one warning `build.diff-pair-name` naming both nets

#### Scenario: Pair selected by a rule
- **GIVEN** the variant of "Diff pair reported" with `d.rules.pair(pair, uncoupled_max=mm(5))`, or with a rule on `select.pair("*")`
- **WHEN** it is built with `--dry-run --json`
- **THEN** `issues` hold no `build.interface-not-lowered`

### Requirement: Interface checks in a build
A build SHALL check the interfaces of the design after the parts are resolved, as "Built project files" allows for added steps of `build_design`, and SHALL report three warnings, which join the closed build set ("Build issue codes"):

| code | severity | when |
|---|---|---|
| `build.diff-pair-name` | warning | the two nets of a `diff_pair` (`p`, `n`) or `usb2` (`dp`, `dn`) interface do not form a KiCad differential pair by name |
| `build.i2c-pullup-missing` | warning | an I2C line has no two-pin part to the `hv` net of a `power` interface |
| `build.diff-pair-gap-shadowed` | warning | KiCad would report two tracks of a pair interface laid at its class pair gap |

- **Pair names** (`H-K-DIFFPAIR-NAMES-2`). The names, in KiCad's stored form, form a pair when `fenolite.model.pairs.pair_base(<positive name>, <negative name>)` is not `None` (`design-model`, "Differential pairs in the model"). The hint MUST propose a second name: `coupled_name(<positive name>)` when the positive name has the polarity `P` or `+`; otherwise `<positive name>_P` and `<positive name>_N`.
- **Pull-ups.** For the `sda` and `scl` nets of each `i2c` interface, a pull-up is a component whose resolved symbol has exactly two pins, one on that net and the other on the `hv` net of a `power` interface of the design. The issue MUST name the interface and the line.
- **Shadowed pair gap** (`H-K-PRO-PAIR`). For each `diff_pair` or `usb2` interface whose nets form a pair by name and are in one model class whose `diff_pair_gap` `g` is set, the warning MUST be given when the clearance in force between a track of each net on one copper layer (`copper-check`, "Clearance in force" and "Clearance between the nets of a differential pair", with the switches of the target) is above `g`, or when the board minimum clearance that the build writes for the target is above `g` and no rule of kind `diff_pair_gap` selects the pair's tracks. The message MUST name both nets, `g` and what governs (a rule, a class or the board minimum); the hint MUST name `design.rules.pair(…, clearance=…, gap_min=…)`.
- The checks MUST NOT change any file or the model, and a design without interfaces MUST give none of the three codes.

#### Scenario: Pair names that KiCad does not pair
- **GIVEN** a blink variant with `USB2(usb_dp, usb_dm)` on the nets `USB_DP` and `USB_DM`
- **WHEN** it is built with `--dry-run --json`
- **THEN** `issues` hold one `build.diff-pair-name` naming `USB_DP` and `USB_DM`, with a hint naming `USB_DN`, and one `build.interface-not-lowered`

#### Scenario: Pair names that KiCad pairs
- **WHEN** the same variant uses the nets `USB_P` and `USB_N`
- **THEN** `issues` hold no `build.diff-pair-name`

#### Scenario: Pair names with a tail
- **WHEN** the same variant uses the nets `D_P0` and `D_N0`, and then `D_P0` and `D_N1`
- **THEN** the first build's `issues` hold no `build.diff-pair-name`, and the second's hold one whose hint names `D_N0`

#### Scenario: Missing pull-up
- **GIVEN** a design with `Power(vdd, gnd)`, `I2C(sda, scl)`, a resistor from `SDA` to `VDD` and none on `SCL`
- **WHEN** it is built with `--dry-run --json`
- **THEN** `issues` hold one `build.i2c-pullup-missing` naming the interface and `scl`

#### Scenario: Pair gap under a board-wide clearance rule
- **GIVEN** a blink variant with `usb = USB2(usb_p, usb_n)` on `USB_P` and `USB_N`, both in the class `USB` (clearance 0.2 mm, `diff_pair_gap` 0.15 mm), and `d.rules.minimum(clearance=mm(0.2))`
- **WHEN** it is built for target 10 with `--dry-run --json`
- **THEN** `issues` hold one `build.diff-pair-gap-shadowed` naming `USB_P`, `USB_N`, `0.15` and the rule `min_clearance`; after `d.rules.pair(usb, clearance=mm(0.15), gap_min=mm(0.13))` they hold none
