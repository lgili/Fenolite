# Electrical contracts

Fenolite checks copper, placement, DRC, ERC and the copper of power nets against their roles. The stage
`circuit.rules` also checks each part against the circuit it sits in (change c0253): a 16 V capacitor on a
12 V ± 10 % input under your derating policy, an inductor rated 1 A on a 1.2 A rail, a divider that no longer
sets its output after an edit in KiCad. This page says where the values come from, what is judged, and how
to read the one requirement table. The DSL calls are listed in `docs/dsl.md`, "Electrical contracts"; the
codes and the reply in `docs/cli-contract.md`, "Circuit stage".

There is no simulation, no solver and no operating-point analysis. Every number is a range of what you
stated, combined at its worst case. Fenolite infers no voltage and no current, and ships no derating
number.

## Values and their sources

Each net may get a **voltage bound** (a range against the design's ground) and a **current bound** (an upper
bound on the current any copper of the net carries), only from what you stated, in this order:

| order | source | voltage | current | table source |
|---|---|---|---|---|
| 1 | a rig element on the net (`design.rig`) | the supply's range | the supply's `current`, or a sink's | `user`, basis `rig <name>` |
| 2 | a rail (`design.rail`, change c0252) | the rail's voltage | the upper sum of its loads | `user`, basis `rail <name>` |
| 3 | a declared or confirmed net role | `working_mv` read as `-v` to `+v` | `milliamps` | `role` |
| 4 | a `[[current]]` row (`fenolite roles --check --requirements`) | none | its `current` | `user`, basis its `source` text |
| 5 | `--current NET=AMPS` of `fenolite roles --check` | none | the option's value | `user`, basis `--current` |
| 6 | a ground (`design.ground`) or a `ground` role | 0 V | none | `user` or `role` |

An inferred role that is not confirmed gives nothing. When two sources of different kinds give one net
voltages that do not overlap, the first is used and `circuit.value-conflict` (warning) names both.
`fenolite check` takes neither a requirements file nor `--current`, so only orders 1 to 3 and 6 reach it.

## Part classes

The derating keys, the series rule and the power rule need a part's class. There is one classifier,
`fenolite.roles.classify` (`docs/roles.md`, "Part classes"): your `design.part_class`, the pin names, the
value, the reference prefix. The commands run it and pass the classes to the stage. A part without a class
gives `unknown` rows (`no class`) for the checks that need one.

## Device records

A part is judged when its component names a device (`fenolite.device`, `docs/devices.md`) and the command
resolves the record: `fenolite build` uses the records it placed; `fenolite check` and `fenolite roles` read
`devices/` of the project folder or of its parent (a build folder beside the script), then the shipped
`Fenolite:` devices. A part whose record is not found is counted by `circuit.rating-missing`. When the
record's digest differs from the one the build recorded, the current record is judged and
`circuit.device-changed` (warning) names both digests.

## `abs_max` against `operating`

| limit | meaning | judged as | derated | code |
|---|---|---|---|---|
| `abs_max` | an absolute maximum rating: beyond it the part may be damaged | the worst case of the applied value within the limit | yes, by your policy | `circuit.rating-*` |
| `operating` | the range the part needs to work (VIN 2.7 V to 6 V) | the applied range within the limit, exactly | never | `circuit.operating-range` |

A derating tightens a rating toward zero; applied to an operating minimum it would loosen it, so the two
never share a check. An `operating` voltage of a pin that is a member of a device port stating `voltage` is
judged by c0252's `circuit.rail-voltage`, not again here.

## The ratings checks

| rating | parts | applied value |
|---|---|---|
| device `voltage` | two-pin parts | `|V(a) - V(b)|` worst case: `max(a.max - b.min, b.max - a.min)` |
| pin `voltage` | any device | the pin's net from the net of the device's `ground` function (a MOSFET's drain to source with `ground = "S"`) |
| `[[limits]]` `voltage` | any device | `V(first) - V(second)` (`BST - SW`, a high-side gate to source); an unbounded second net is `unknown` |
| device `current` | the owner of an `out` power port | the upper load sum of that port's rail |
| device `current` | `inductor`, `shunt` | the smaller of its two nets' current bounds, only when both are known |
| pin `current` | any device | the net's current bound, when the pin is the part's only pin on the net |
| device `power` | `resistor`, `shunt` | `V_across.max² / R.min`, else for a shunt `I.max² x R.max`; `R` is the part's value range |
| device `temperature` | any device | the ambient range of `design.operating` |

A row is `pass` when the worst case is within the limit, `fail` when it is not, and `unknown` when an input
is missing; a rating row is never `unsure`.

## Derating: yours, never shipped

```python
design.derating(capacitor_voltage=ratio(50), resistor_power=ratio(50), source="our design rule 4.2")
design.derating(capacitor_voltage=ratio(80), parts=select.ref("C1*"))
design.derating(temperature_margin=kelvin(15))
```

`ratio(50)` reads "at most 50 % of the rating" and is stored as 500 per mille; `pct()` is a ± tolerance and
is refused here. The keys are `voltage`, `current`, `power`, `pin_voltage`, `pin_current`,
`capacitor_voltage`, `resistor_power`, `resistor_voltage`, `shunt_power`, `inductor_current`,
`diode_voltage`, `diode_current`, `transistor_voltage`, `transistor_current` and `temperature_margin`. The
most specific rule wins: a part scope, then a class key, then a generic key. A rating no rule covers is
judged at 100 %, with source `device`, and one `circuit.policy-missing` (info) lists it.

Fenolite ships no derating number: no public source has been checked and registered for one. **Cite your
own**: put the document and clause your numbers come from in `source=`; it is shown in the basis of every
limit the rule sets.

## Expectations

```python
b.expect(within(vref * (1 + value_of(top) / value_of(bot)), vout), "VOUT set by the divider")
b.expect(at_least(rating_of(inductor, "current"), current * 13 / 10), "inductor current margin")
```

An expectation is data, not Python: the stage evaluates its handles on the built model, so a value kept
after an edit in KiCad (change c0250) or a new pick is judged again. On worst-case ranges:

| test | pass | fail | otherwise |
|---|---|---|---|
| `within(a, b)` | `b.min <= a.min` and `a.max <= b.max` | `a.max < b.min` or `a.min > b.max` | unsure |
| `at_least(a, b)` | `a.min >= b.max` | `a.max < b.min` | unsure |
| `at_most(a, b)` | `a.max <= b.min` | `a.min > b.max` | unsure |

A fail is `circuit.expect-failed` (error), an unsure result `circuit.expect-unsure` (warning), and a handle
that cannot be resolved (a value turned into text, a rail without a voltage) `circuit.expect-unknown`
(warning). Ids are `<instance path>/expect#<n>`; the top level is `design`.

## The rig and its corners

```python
design.rig(
    supply(v12, gnd, voltage=volt("12").pct(10), current=amp(3), name="bench"),
    sink(v33, gnd, current=amp("0.2"), name="probe"),
)
```

A rig element states the outside world: a bench supply on the input, a load on an output. It is a record of
the rules layer, never a component, so it reaches no netlist, schematic, board, BOM or export (a test builds
the example with and without it and compares every file). On a rail, a supply is a source and a sink a load.
Each row and expectation that reads a supply is also evaluated at every **corner**, each supply at its
minimum and at its maximum (`bench=min`, `bench=max`); a failing row names the corners that fail. Corners
never loosen a verdict. Above six supplies they are not evaluated (`summary.corners` is
`too-many-supplies`).

## Strictness

By default the rows that cannot be judged give one `circuit.value-unknown` info with their count, and the
parts without a record or a needed rating one `circuit.rating-missing` info: a design that states little
reads as quiet. `design.contracts(unknown="warning")` makes each of them a warning that names what is
missing. The default stays `info` until every shipped device carries the ratings its class needs.

## The requirement table

`summary.requirements` of the stages `circuit.rules` and `roles.rules`, and `result.requirements` of
`fenolite roles --check`, are one table: one row per judged limit, expectation and rail or role check,
sorted by `id`. Each row names its `value` and its `limit` with their range (c0246's encoding), text,
`source` (`device`, `role`, `policy` or `user`) and basis, its `status`, the severity of its finding, its
corners and what is missing. Role rows (`docs/roles.md`, "The requirement table") take the source `policy`
for a profile default and `user` for an override or a requirements limit.

## Severities

A fail against a device rating, an operating range, your policy or an expectation is an `error`, and stops
`fenolite build` (c0252's build rule). An unsure or unknown expectation, a value conflict and a changed device
warn. The evidence of the stage is `INFERRED` (`H-G-CIRCUIT-EXAMPLE`), lowered to the label of each device
record it judged: a rating of an `UNVERIFIED` record still fails as an `error`, and its row shows the label.

## The example

`examples/circuit/sensor/` holds a good and a bad variant of a 12 V sensor board with a buck block, authored
for Fenolite with illustrative devices. The good one gives nothing above info; the bad one gives exactly
`circuit.rating-voltage` (the input capacitor under the policy), `circuit.rating-current` (the inductor),
`circuit.expect-unsure` (the divider) and `circuit.rating-power` (the bleeder). Its `requirements.toml`
uses unit keys (`docs/analyses.md`, "The requirements file").
