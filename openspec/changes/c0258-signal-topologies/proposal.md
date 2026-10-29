## Why

Fenolite constrains fast signals today with lengths: `rules.pair` gives gap, uncoupled length, skew and
length of a differential pair, `rules.impedance` gives widths per layer, and `length.rules` judges totals
per net. Three things are missing for clocks, buses and links:

- **Order and branches.** A net is a set of pads; a clock that must go driver, terminator, then three loads
  in a daisy chain, with short stubs, cannot be stated.
- **Series parts.** A constraint stops at a net boundary, so a series resistor or AC-coupling capacitor
  splits one signal path into two unrelated nets.
- **Time and loss.** Protocols budget delay and insertion loss, not millimetres; converting by hand hides
  the assumption (the layer's propagation delay) that the result depends on.

And when several rules select an item, `check` does not say which one governed and why.

The research of 2026-10-29 (`docs/research/circuit-as-code.md`, section 13, core change M) takes concepts
from JITX's public documentation: ordered pad trees, a bridging model through series parts, constraints in
time and dB, protocol constraint objects, and a documented rule specificity.

## What Changes

- **Topologies.** `design.topology(name, u1["CLK"] >> r1[1], r1[2] >> (u2["CLK"], u3["CLK"]))`: an
  ordered tree of pads across nets, joined through series parts that declare a bridge (`design.bridge`, or
  the device record of c0248).
- **Integer time and loss.** New DSL values: delays in integer femtoseconds (`fs`, `ps`, `ns`) and loss in
  integer milli-decibels (`mdb`, `db`). Propagation and loss per layer, per via and per bridge are the
  user's inputs (`design.propagation`, `design.loss`); Fenolite ships no dielectric value.
- **Constraints.** `topo.delay(a, b, min=, max=)`, `topo.skew(*ends, max=)`, `topo.loss(a, b, max=)`,
  `topo.stub(max=)` and `topo.order()`, with severity.
- **Protocol constraint objects.** `protocol.Usb2(...)`, `protocol.Clock(...)`: typed bundles of named
  limits bound to an interface kind (c0252), with no shipped default numbers.
- **Check stage `topology.rules`** (tool-free, after `length.rules`): pad-to-pad copper paths, delays and
  losses with strict-side rounding, order and stubs, with subjects (c0256).
- **Rule specificity.** A documented rank of every selector; `rules.shadowed` (info) when a more specific
  rule loses; an opt-in `design.rules.precedence("specificity")`; and `fenolite check --explain-rules`,
  which prints the governing rule per item and kind with the rules it overrode.
- **Lowering.** A single-net delay or skew with one propagation value on its layers lowers to KiCad's
  `length`/`skew` rules; everything else is judged by Fenolite only, with `rules.topology-not-lowered`
  (info). Native time-domain lowering waits for a KiCad probe.

Depends on: c0256 (subjects, `findings()`), c0252 (interface kinds), c0248 (bridges in device records),
c0246 (ranges, for protocol limits given as ranges), and the existing `rules.pair`, `rules.impedance`,
`select.*` and `length.rules`. Later; after 1.0 unless a reference board needs it.

## Non-goals

- No field solver, impedance or loss computation from geometry; no S-parameters.
- No router change: the routers read the constraints later.
- No protocol numbers from paid or non-public specifications; no defaults in protocol objects.
- No change to KiCad's precedence of lowered rules (priority, then name; `H-K-DRU-ORDER`) unless opted in.

## Evidence level required

- `topology.rules`: `INFERRED`, `H-G-TOPO-DELAY` measured on authored benches against hand calculation.
- Lowered length and skew rules: the existing `KICAD-VERIFIED` kinds.
- Specificity and `--explain-rules`: `INFERRED`, checked against `rule_precedence` on every rule bench.

## Impact

- New: `src/fenolite/dsl/topology.py`, `dsl/timing.py`, `dsl/protocol.py`, `checks/topology.py`,
  `checks/specificity.py`, `checks/padpath.py`, `docs/topologies.md`, `examples/topologies/`.
- Changed: `dsl/part.py` (`>>`), `dsl/design.py`, `model/rules.py`, `backends/kicad` lowering,
  `checks/stages.py`, `cli/cmd_check.py`, `explain.toml`, `docs/dsl.md` ("Design rules"), `docs/formats/kicad/rules.md`, the guide pages
  `rules` and `board-routing`, `CHANGELOG.md`.
- Size: about 12 design-days.
