## Context

Source: `docs/research/circuit-as-code.md`, section 13 "Topologies and signal-integrity constraints
(later)", core change M. Concepts only, paraphrased from JITX's public documentation: ordered connections
forming a tree of pads, series parts with a bridging model, constraints in delay and loss, protocol
constraint objects typed by bundle, and tag selection with a documented specificity. No code, operator
table, class name, schema or constant of JITX is used.

What `dev` (0.6.0) has, and this change builds on:

- `design.rules.pair(pair, gap_min=, uncoupled_max=, skew_max=, length_min=, length_max=, ...)` lowers to
  the kinds `diff_pair_gap`, `clearance`, `diff_pair_uncoupled`, `diff_pair_skew` and `length`
  (`rules-model`, "Rule kinds and limits"; all `KICAD-VERIFIED` per kind and major).
- `design.rules.impedance(name, ohms=, netclass=|pair=, layers=(trace(...), ...))` writes widths, gaps and a
  KiCad 10 tuning profile (`docs/impedance.md`). The profile has per-layer `delay`, `via_prop_delay`,
  `enable_time_domain_tuning` and `net_chain_bridge_prop_delay` keys (`docs/formats/kicad/project.md`,
  "Tuning profiles", `INFERRED`); their units and DRC behaviour are not probed.
- `select.net/netclass/ref/item/area/pair` with `& | ~` and `ALL` (`rules-model`, "Closed selector
  grammar").
- `rule_precedence` (`checks/clearance.py`): the last matching rule in lowering order governs; lowering
  emits priority 0 first, then descending, priority 1 last; ties by name, then id (`rules-model`, "Lowered
  rules follow priority"; `H-K-DRU-ORDER`, `KICAD-VERIFIED` on 9.0.9 and 10.0.6).
- `length.rules` judges `length`, `skew`, `diff_pair_skew` on routed totals per net, tool-free.
- Copper findings carry candidate rows and the governing rule (`copper-rule-explanation`).
- c0256: subjects on findings, `fenolite.testing.findings()`.

## Goals / Non-Goals

Goals: state order, branches and bridges; constrain in time and loss with integer units and the user's
propagation and loss data; judge it without a tool; explain which rule governs each item.

Non-goals: field solving, S-parameters, router changes, shipped protocol numbers, changing KiCad's
precedence by default.

## Decisions

### 1. Units: integer femtoseconds and milli-decibels

`fenolite.dsl.timing`: `fs(n)`, `ps("12.5")`, `ns("1.2")` give a `Delay` holding integer femtoseconds;
`mdb(n)`, `db("1.5")` give a `Loss` holding integer milli-decibels. A text with more digits than the unit
holds (`ps("0.0001")`) is refused, as lengths refuse sub-nanometre text. Negative values are refused except
for a skew's signed result. The model stores `*_fs` and `*_mdb` integers. One femtosecond is about 0.15 µm
of travel on common boards, far below routing precision, and an `int` holds any board-scale delay.

Alternative considered: picoseconds. A ps grid loses precision when summing many short segments with
`ceil`; fs keeps the sum's error below a picosecond for any board.

### 2. Propagation and loss are inputs

```python
design.propagation("F.Cu", per_mm=fs(5_900))  # example value: the user's stack-up figure
design.propagation("In1.Cu", per_mm=fs(6_900))
design.propagation(via=fs(10_000))  # per via barrel crossed
design.loss("F.Cu", per_mm=mdb(4), at=hertz("1G"))  # optional, at the protocol's frequency
```

Fenolite ships no dielectric constant, no propagation figure and no loss figure: they depend on the user's
material and stack-up, and public figures are not universal. Values in docs and guide pages are marked as
examples (`agent-guide` writing rules). A layer used by a constrained path without a propagation gives
`topology.input-missing` (warning) and the constraint is not judged.

A pad's die delay (KiCad 10's `die_delay` token, `docs/formats/kicad/tokens.md`) is added when the board
holds it, as `length.rules` adds die lengths.

### 3. Topologies: ordered pad trees across nets

Today (lengths per net only):

```python
design.rules.rule("clk len", "length", where=select.net("CLK_A") | select.net("CLK_B"), max=mm(60))
```

Proposed:

```python
r1 = design.part(device="Fenolite:R_0402")  # c0248 device; its record declares bridge 1-2
clk = design.topology(
    "clk",
    u1["CLK"] >> r1[1],  # driver to series terminator (net CLK_A)
    r1[2] >> u2["CLK"] >> u3["CLK"] >> u4["CLK"],
)  # daisy chain on net CLK_B
clk.delay(u1["CLK"], u4["CLK"], max=ps(900))
clk.skew(u2["CLK"], u3["CLK"], u4["CLK"], max=ps(50))
clk.stub(max=mm(2))
clk.order()  # copper must visit the loads in this order
```

- `PinHandle.__rshift__` returns a `Chain`; `a >> (b, c)` fans out. `design.topology(name, *chains)`
  joins chains whose ends share a pin, and a bridge joins two pins of one part.
- The topology MUST be a tree: a cycle, a pin on two branches, or two disconnected parts is a `DslError` at
  the call, located by line.
- Consecutive pins MUST be on one net, except across a bridge; otherwise `DslError`.
- Bridges: `design.bridge(part, "1", "2", delay=fs(0), loss=mdb(0))`, or the `bridges` table of the part's
  device record (c0248), each with optional `delay_fs` and `loss_mdb`. A series part in a chain without a
  bridge is `topology.bridge-missing` (error) at build.

Model: `RuleSet.topologies` (new optional key of `rules.json`, empty stored as absent, as `roles`):
`Topology(name, nodes, edges, constraints)` with nodes as `REF-PIN`, edges `(a, b, kind)` with `kind` in
`net`, `bridge`; `RuleSet.propagation` and `RuleSet.losses` per layer and per via. Ids:
`derived_id("top", "dsl", "topology:<name>")`.

### 4. Constraints and their judgement

| constraint | judged on | rounding |
|---|---|---|
| `delay(a, b, min=, max=)` | sum along the tree path a→b: copper segments (`length_nm * per_mm_fs`, divided by 10⁶), vias, bridges, die delays | `max`: ceil per segment; `min`: floor |
| `skew(*ends, max=)` | delays from the root to each end; skew = delay − longest, as `length.rules` does | as `delay` |
| `loss(a, b, max=)` | sum of per-mm loss, vias, bridges along a→b | ceil |
| `stub(max=)` | length of each copper branch that leaves the tree path to end at no listed pin | — |
| `order()` | the copper path from the root visits the pins of each chain in chain order | — |

Pad-to-pad copper paths (`checks/padpath.py`, model and geometry only): a graph of track and arc ends, via
centres and pad copper per net; the path is the shortest by centre-line length between the two pads' graph
nodes. A path through a zone is not measured (`topology.path-through-zone`, warning; the constraint is not
judged). An unrouted end gives `topology.unrouted` (info) and the constraint is not judged.

Protocol constraint objects (`fenolite.dsl.protocol`):

```python
design.constrain(usb, protocol.Usb2(skew_max=ps(10), delay_max=ps(1_500), loss_max=db("1.5")))  # example
```

A protocol object is a frozen record of named limits that MUST be bound to an interface of its kind
(`Usb2` to a `USB2` or `DiffPair`, `Clock` to a topology); it expands to topology constraints and, where
they apply, to `rules.pair` rules. It has no defaults: each limit is the user's. A later change MAY add
defaults taken from a public specification recorded in `docs/formats` with an evidence label.

### 5. The stage `topology.rules`

Inserted right after `length.rules` in `STAGE_ORDER` (a later change may insert a stage), default, not in
`ORACLE_STAGES`, not in `DOCUMENT_STAGES` at first (KiCad input only, as `length.rules`). Skipped with
`no-topology` when the design has none, and `read-refused` as the others. Every issue carries subjects
(c0256): the topology, the pins and nets on the path.

| code | severity | when |
|---|---|---|
| `topology.delay-out-of-range` | error, warning (constraint's) | a path delay is outside `min`/`max` |
| `topology.skew-out-of-range` | error, warning | an end's skew exceeds `max` |
| `topology.loss-over-budget` | error, warning | a path loss exceeds `max` |
| `topology.stub-too-long` | error, warning | a stub exceeds `max` |
| `topology.order` | error, warning | the copper visits the pins out of order |
| `topology.bridge-missing` | error | a series part in a chain has no bridge |
| `topology.input-missing` | warning | a layer or via of a path has no propagation (or loss for a loss constraint) |
| `topology.path-through-zone` | warning | a path runs through zone copper and is not measured |
| `topology.unrouted` | info | an end of a constrained path has no copper path yet |

`summary`: `topologies`, `constraints` (count per kind), `judged`, `not_judged`. Evidence:
`Evidence(Level.INFERRED, hypotheses=("H-G-TOPO-DELAY",))`, combined with the read's.

### 6. Lowering

A `delay` or `skew` whose path lies on one net, crosses no bridge and uses layers of one propagation value
lowers to a `length` rule (`max_nm = floor(max_fs * 10⁶ / per_mm_fs)`, `min_nm = ceil(...)`) or a `skew`
rule on that net, named `topology:<name>:<constraint>`, so KiCad's DRC and length tuner see it. Everything
else stays in the model with `rules.topology-not-lowered` (info). Native lowering to the KiCad 10 tuning
profile's time-domain keys waits for a probe (`H-K-PRO-TIME-DOMAIN`, `UNKNOWN` today): open question 2.

### 7. Rule specificity

The rank of a selector (`checks/specificity.py`, documented in `docs/dsl.md`, "Design rules"):

| leaf | rank |
|---|---|
| `ALL` | 0 |
| `area(...)` | 1 |
| `item(...)` | 1 |
| `netclass(...)` | 2 |
| `net(...)` with `*` | 3 |
| `pair(...)` | 4 |
| `ref(...)` | 4 |
| `net(...)` exact | 5 |

`a & b` ranks as the sum of its items; `a | b` as the least of its items; `~a` as 0. Two-sided rules
(`between=`) rank as the sum of both sides.

Precedence stays what KiCad applies (`H-K-DRU-ORDER`): priority, then name, then id; the last governs. This
change adds:

- `rules.shadowed` (info), from the build and from `check`: for an item matched by two rules of one kind,
  the governing rule has a strictly lower rank than one it overrides. The message names both rules and
  ranks, and the hint suggests a priority or `precedence("specificity")`.
- `design.rules.precedence("specificity")` (opt-in): every rule without an explicit `priority=` gets one
  from its rank, so the most specific rule governs; ties keep name order. The lowered bytes change only
  for designs that call it.
- `fenolite check --explain-rules`: `result.rules` lists, for each net (and pad, track, via kind it holds)
  and each rule kind with at least two matching rules, `{subject, kind, governing, rank, overrides}`, with
  `governing` and each entry of `overrides` as `{name, id, priority, rank}`, sorted by subject then kind.
  It runs no tool and reuses `rule_precedence`, so it cannot disagree with the stages.

Alternative considered: make specificity the default precedence. It would change the lowered rules and the
verdicts of every existing design whose rules overlap; rejected for now (open question 3).

### 8. Files and API

- `dsl/timing.py` (`Delay`, `Loss`, `fs`, `ps`, `ns`, `mdb`, `db`), `dsl/topology.py` (`Chain`,
  `Topology`, `design.topology`, `design.bridge`, `design.propagation`, `design.loss`), `dsl/protocol.py`
  (`Usb2`, `Clock`, `design.constrain`).
- `model/rules.py`: `Topology`, `TopologyConstraint`, `Propagation`, `LayerLoss`, `RuleSet.topologies`,
  `.propagation`, `.losses`; schemas regenerated.
- `checks/padpath.py`, `checks/topology.py`, `checks/specificity.py`.
- `docs/topologies.md` (new), `docs/dsl.md`, `docs/formats/kicad/rules.md` (the lowering rows).

### 9. Evidence per behaviour

| behaviour | level |
|---|---|
| delay, skew, loss, stub, order | `INFERRED`, `H-G-TOPO-DELAY` (benches with hand-computed sums, exact to the femtosecond) |
| lowered `length`/`skew` | `KICAD-VERIFIED` kinds; the conversion is `INFERRED` |
| specificity, `rules.shadowed`, `--explain-rules` | `INFERRED`, equal to `rule_precedence` on every rule bench |
| time-domain profile lowering | `UNKNOWN` until `H-K-PRO-TIME-DOMAIN` is probed; not shipped |

## Relation to the other changes of this batch

c0256 gives subjects and `findings()`; c0252 the interface kinds that protocol objects bind to; c0248 the
`bridges` table of device records; c0246 ranges, which protocol limits MAY take (`min`/`max` from one
range); c0251 block paths in pin names (`buck/U1-3`); c0257 (pin assignment) can pick pins before a
topology names them: a topology on a `TakenInterface` resolves after the solve. The routers of c0243/c0244
(other branches) read `RuleSet.topologies` later.

## Risks / Trade-offs

- Users may trust delays as physics. Mitigation: every message states the propagation inputs it used; the
  docs say the figures are the user's.
- Shortest-path through copper is a model; a meandered stub-free route is exact, a net with loops is not
  (`topology.order` reports loops as out of order).
- Specificity adds a second ordering concept. Mitigation: precedence stays KiCad's; specificity only
  informs, unless opted in.
- Size: 12 design-days; split into two implementation PRs (topologies and stage; specificity and
  `--explain-rules`), each green on its own.

## Open Questions

1. Do protocol objects ship defaults? **Recommended:** no, until each value has a public source recorded in
   `docs/formats` with an evidence label; the maintainer decides per protocol.
2. Lower delays natively to the KiCad 10 tuning profile? **Recommended:** only after a probe settles the
   units and DRC behaviour of `delay`, `via_prop_delay` and `net_chain_bridge_prop_delay`; until then lower
   only the single-net length form.
3. Make specificity the default precedence at 1.0? **Recommended:** no; keep KiCad's order and the
   `rules.shadowed` info, so a lowered design means in KiCad what it means in Fenolite.
4. Are topologies judged on Altium input? **Recommended:** later, once the Altium reader gives pad paths;
   the stage is KiCad-only at first, as `length.rules`.
5. Should the I2C pull-up range be derived here from the bus specification's public method (rise time, bus
   capacitance, low-level current), as c0252's open question 3 suggests? **Recommended:** yes, as a
   `protocol.I2c` object whose inputs (capacitance, rise time) are the user's and whose formulas are recorded
   with their source under `docs/evidence/`; it expands into a c0253 expectation on the pull-up resistors,
   not into a topology constraint.
