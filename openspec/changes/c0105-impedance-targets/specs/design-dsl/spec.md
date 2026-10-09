## ADDED Requirements

### Requirement: Impedance targets in the DSL
`design.rules.impedance(name, *, ohms, netclass=None, pair=None, layers, tolerance=None, priority=1)` SHALL declare one impedance target, and `fenolite.dsl.impedance.trace(layer, *, refs, width, gap=None)` SHALL give one layer of it; `fenolite.dsl` SHALL re-export `trace` (an addition under "DSL package").
- **At the call**, `DslError` MUST be raised and nothing recorded for: a `name` that is not a non-empty string or is already used by `impedance()`; an `ohms` that is not a `Quantity` of unit ohm, a positive `int` or the text of a positive decimal number (a `float` is refused); a `tolerance` that is not a positive `int` or decimal text below 100; both or neither of `netclass` and `pair`; empty `layers`, or an item that is not a `trace()`; one layer twice; `refs` that is not one name or two distinct names, or that holds the layer; a `width` or `gap` that is not a length above 0; a `gap` on some traces only; a `pair` with a trace without `gap`; a `priority` that is not an integer of 0 or more.
- `netclass` MUST be a class name or a sequence of names. `pair` MUST be a `DiffPair` or `USB2` interface ("Typed interfaces in the DSL"), or a sequence of them. The target is `differential` when its traces carry a gap and `single` otherwise.
- **In `to_model`**, the classes MUST be the named ones, or the class of each pair's two nets; a name that is no class of the design, or a pair whose nets are in two classes or in none, MUST raise `DslError` naming them.
- `RuleSet.impedance` MUST hold one `ImpedanceTarget` per call, in call order, with an id derived from the name, `ohms` and `tolerance_percent` as the exact decimal text of the given value (`ohm("42.5")` gives `"42.5"`), and one `TraceGeometry` per trace in stack order, its references in stack order.
- **Derived rules.** `to_model` MUST add to `RuleSet.rules`, after the rules of `minimum()` and `rule()`, in call order: per trace, one `track_width` rule named `track_width_<target>_<layer>`, with `selector_a` the target's class (an `or` of `netclass` leaves for several), `layers` the trace's layer, `min` = `opt` = `max` = the width, severity `error` and the call's priority; and, for a `differential` target, per trace, one `diff_pair_gap` rule of c0104 named `diff_pair_gap_<target>_<layer>`, on the same selector, with `layers` the trace's layer, `min` = `opt` = `max` = the trace's gap, severity `error` and the call's priority (`rules-model`, "Rule kinds and limits" and "Closed selector grammar": the kind takes the three limits and a layer clause). A derived name equal to another rule's name MUST raise `DslError`.
- `docs/dsl.md` MUST describe `impedance()` and `trace()` in its section "Design rules", say that the geometry is the user's, and point to `docs/impedance.md`.

#### Scenario: Single-ended target on a class
- **GIVEN** a four-layer design with the class `SE50` and `d.rules.impedance("SE50", ohms=ohm(50), netclass="SE50", layers=(trace("F.Cu", refs="In1.Cu", width=mm(0.35)), trace("B.Cu", refs="In2.Cu", width=mm(0.35))))`
- **WHEN** `to_model` runs
- **THEN** `RuleSet.impedance` holds one `single` target with `ohms == "50"` and two layers, and `RuleSet.rules` ends with `track_width_SE50_F.Cu` and `track_width_SE50_B.Cu`, each with `layers` its layer, `min == opt == max == 350_000` and priority 1

#### Scenario: Pair target
- **GIVEN** `usb = USB2(usb_p, usb_n)` on nets `USB_P` and `USB_N` of the class `USB90`, and `d.rules.impedance("USB90", ohms=90, pair=usb, tolerance=10, layers=(trace("F.Cu", refs="In1.Cu", width=mm(0.2), gap=mm(0.15)),))`
- **WHEN** `to_model` runs
- **THEN** the target is `differential`, names the class `USB90`, has `tolerance_percent == "10"`, and the rules gain `track_width_USB90_F.Cu` at 200 000 nm and `diff_pair_gap_USB90_F.Cu` with `min == opt == max == 150_000` and `layers == ("F.Cu",)`

#### Scenario: Pair target on two layers with two gaps
- **GIVEN** the pair of "Pair target" with `layers=(trace("F.Cu", refs="In1.Cu", width=mm(0.2), gap=mm(0.15)), trace("In2.Cu", refs=("In1.Cu", "B.Cu"), width=mm(0.15), gap=mm(0.2)))`
- **WHEN** `to_model` runs
- **THEN** the rules gain `diff_pair_gap_USB90_F.Cu` at 150 000 nm on `F.Cu` and `diff_pair_gap_USB90_In2.Cu` at 200 000 nm on `In2.Cu`, each with `min == opt == max`, and no rule without a layer

#### Scenario: Pair without a gap
- **WHEN** `d.rules.impedance("USB90", ohms=90, pair=usb, layers=(trace("F.Cu", refs="In1.Cu", width=mm(0.2)),))` is called
- **THEN** `DslError` is raised naming `F.Cu` and the missing gap, and nothing is recorded

#### Scenario: Float refused
- **WHEN** `d.rules.impedance("SE50", ohms=50.0, netclass="SE50", layers=(trace("F.Cu", refs="In1.Cu", width=mm(0.35)),))` is called
- **THEN** `DslError` is raised naming `50.0`

#### Scenario: Pair across two classes
- **GIVEN** a `DiffPair` whose `P` net is in class `A` and whose `N` net is in class `B`, given to `impedance(pair=…)`
- **WHEN** `to_model` runs
- **THEN** `DslError` is raised naming the pair, `A` and `B`

### Requirement: Impedance targets in a build
A build SHALL check the impedance targets of the design after the parts are resolved, as "Built project files" allows for added steps of `build_design`, with `lens.build.impedance_checks(design, *, target)`, and SHALL report these six codes, which join the closed build set ("Build issue codes"); each MUST have a table in `src/fenolite/cli/data/explain.toml`:

| code | severity | when |
|---|---|---|
| `build.impedance-layer` | error | a trace's layer or reference is not a copper layer of the board |
| `build.impedance-shadowed` | warning | a rule of the same kind as a derived rule, emitted after it, selects a target class on a trace's layer (below) |
| `build.impedance-class-width` | warning | a target class has a value that differs from a trace's: `track_width` for a single target; c0104's `diff_pair_width` or `diff_pair_gap` for a differential one |
| `build.impedance-gap-clearance` | warning | target 9: a trace's gap is below the clearance of its class, and the class has no `diff_pair_gap` (c0104) at or below that gap |
| `build.impedance-stackup` | warning | the board has no stack-up, or one whose `impedance_controlled` (c0101) is false |
| `build.impedance-rules-only` | info | target 9: the targets are written as rules only |

- **Shadowing.** The emission order MUST be the order of `lower_rules` ("Lowered rules follow priority"). A later rule shadows when its `selector_a` is one leaf, or an `or` of leaves, each `all`, a `netclass` leaf naming a target class, or a `diff_pair` leaf (c0104) naming a pair of a target class or `*`, and its layers are empty or hold the trace's layer. Any other selector, an area leaf (c0103) among them, MUST NOT count, so a narrower rule may relax a target on purpose.
- `build.impedance-shadowed` MUST name the later rule, the target and the layer. `build.impedance-gap-clearance` MUST name the class, the gap and the clearance, with a hint naming c0104's `netclass(…, diff_pair_gap=…)` and `pair(…, clearance=…)`. `build.impedance-stackup` MUST name the targets and hint at `design.stackup(…, impedance_controlled=True)` (c0101), because the job file states the dielectric constants and `ImpedanceControlled` only then (c0101's `H-K-STACKUP-JOB`).
- The checks MUST NOT change a file or the model, and a design without targets MUST give none of these codes.
- The checks are those of a KiCad build. An Altium build reports targets as `altium-build`, "Impedance targets in an Altium build", states: it gives `build.impedance-layer`, and the other five only where the script is judged through the KiCad build in memory.

#### Scenario: Layer not on the board
- **GIVEN** the two-layer blink with a class `SIG` and a target whose trace is on `In1.Cu`
- **WHEN** it is built with `--dry-run --json`
- **THEN** the exit code is 5 and `issues` hold one `build.impedance-layer` error naming `In1.Cu`

#### Scenario: Class minimum does not shadow
- **GIVEN** the design of "Single-ended target on a class" with `d.rules.minimum(track_width=mm(0.2), netclass="SE50")`
- **WHEN** it is built for target 10 with `--dry-run --json`
- **THEN** `issues` hold no `build.impedance-shadowed`, and the planned `.kicad_dru` writes the rule of `min_track_width_SE50` before the two derived rules

#### Scenario: A later rule shadows the target
- **GIVEN** the same design with `d.rules.rule("wide", "track_width", where=select.netclass("SE50"), min=mm(0.3), priority=1)`
- **WHEN** it is built with `--dry-run --json`
- **THEN** `issues` hold two `build.impedance-shadowed` warnings, one per layer, each naming `wide` and `SE50`

#### Scenario: KiCad 9 build
- **GIVEN** the design of "Pair target" with class `USB90` at clearance 0.2 mm, no class pair values and a stack-up declared with `impedance_controlled=True`
- **WHEN** it is built with `--kicad-version 9 --dry-run --json`
- **THEN** `issues` hold one `build.impedance-rules-only` info and one `build.impedance-gap-clearance` warning naming `USB90`, 0.15 mm and 0.2 mm, no `build.impedance-stackup`, and the planned project has no key `tuning_profiles`

#### Scenario: Stack-up not marked
- **GIVEN** the design of "Single-ended target on a class" with a stack-up declared without `impedance_controlled`
- **WHEN** it is built with `--dry-run --json`
- **THEN** `issues` hold one `build.impedance-stackup` warning naming `SE50` and `impedance_controlled`
