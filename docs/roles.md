# Net roles

A net role says what a net does on a power board: it carries the load current (`power`), it is a switch
node (`switch_node`), it is the return (`ground`), it senses a shunt (`kelvin`), it drives a gate (`gate`),
it insulates a high voltage (`high_voltage`), or it is anything else (`signal`). Fenolite infers the roles
from the circuit, you confirm or declare them, and `fenolite roles --check` (or the stage `roles.rules` of
`fenolite check`) judges the board's copper against them: hot loops, gate loops, Kelvin connections,
current capacity, returns and insulation. Change c0222 adds them; this page is their reference.

Every measure comes from an analysis of [analyses](analyses.md). The roles add only the inputs that those
analyses take (a `[[loop]]` row per loop, a `[[neck]]` row per pour, a path per power net) and two
attachment measures that no analysis has. Every finding is `INFERRED` evidence.

## Quick start

```text
fenolite build examples/roles/buck_shunt/bad.py --out build/buck --confirm
fenolite roles build/buck --json                      # what Fenolite inferred
fenolite roles build/buck --accept-all --min-confidence high --dry-run --json
fenolite roles build/buck --accept-all --min-confidence high --confirm --json
fenolite roles build/buck --check --json              # judge the copper against the roles
fenolite check build/buck --stages roles.rules --json # the same judgement as a stage of check
```

## Role kinds

| kind | a net that | judged for |
|---|---|---|
| `power` | carries the load current: a supply, a switch's far net, an inductor's far net | width, section and vias against its current; distances when it has a working voltage |
| `switch_node` | joins the source of one switch and the drain of another, with an inductor or a driver's switch pin | its current; the copper that runs near it |
| `ground` | is the return: a ground name or the most ground pins | its current; the reference of returns |
| `kelvin` | is the separate sense net of a shunt's sense pad | that it touches no other net |
| `gate` | joins a driver output and a gate, directly or through one resistor | its return over unbroken ground |
| `signal` | is anything else; `sensitive` marks one whose return and distance from switch nodes matter | its return when sensitive |
| `high_voltage` | is insulated from the others first | its distances against your rows |

A role may carry `milliamps`, `working_mv` and `sensitive`. A `power` net with a working voltage is judged
for distances like a `high_voltage` net: with no `high_voltage_mv` limit every such net is, with one only a
working voltage at or above it. Fenolite never infers a current or a voltage.

The **groups** name pads as `REF-PIN`:

- `HotLoop(name, pads)`: the commutation loop, at least three pads in loop order, such as the input
  capacitor's two pads and the switches' drain and source pads.
- `KelvinPair(name, element, receiver, force=())`: the shunt's two sense pads, the two inputs of the
  amplifier, and for a four-pad shunt its two force pads.
- `GateLoop(name, drive, gate, source, ret, resistor=())`: the driver's output, the switch's gate, its
  source (its Kelvin-source pad when it has one), the driver's return, and a gate resistor's two pads.

## Part classes

The inference first gives each part a class: `transistor`, `diode`, `inductor`, `capacitor`, `resistor`,
`shunt`, `driver`, `amplifier`, `controller`, `connector`, `net_tie` or `other`, with its terminals
(`gate`, `drain`, `source`, `kelvin_source` of a transistor, `force` and `sense` of a shunt, `in_p`,
`in_n`, `out` of an amplifier, `drive`, `ret`, `sw` of a driver or controller). The evidence is weighed in
this order: the class you state (`design.part_class`, `--class REF=CLASS`), the pin names, the pin types,
the value or the pad count (a resistor of at most `shunt_max_mohm` is a shunt; four pads make a four-pad
shunt), and last the reference prefix. A class from the prefix alone is `low` confidence, and a rule that
reads it gives no role.

The pin names come from the circuit: the `.fenolite/` model of a project that Fenolite built, or the pads'
pin functions of a board that holds them (KiCad writes them from a schematic). A board read alone without
them gives the inference prefixes only: pass the built project folder, or state the classes.

## Inference rules

The rules run in this order; each result names its rule, its confidence (the lowest of the classes it read)
and the pads it read.

| rule | when | gives |
|---|---|---|
| `SW-1` | a net joins a switch's source, another switch's drain and an inductor or winding pin | `switch_node`, high |
| `SW-2` | a net joins a switch's drain or source (or a diode) and an inductor | `switch_node`, medium |
| `SW-3` | a net joins a driver's or a controller's switching-node pin | `switch_node`, medium |
| `HL-1` | the capacitor across the far nets of a switch node's two switches (the nearest when several qualify) | `HotLoop` |
| `GD-1` | a net joins a driver output and a gate, directly or through one resistor | `gate`, high |
| `GD-2` | for each gate, its Kelvin source (or source) and the driver's pin on that net | `GateLoop` |
| `KS-1` | a shunt's sense pins reach an input pair, through at most two resistors a side; a four-pad shunt whose force pads reach the pair forms the pair too | `KelvinPair`, and `kelvin` for separate sense nets |
| `GND-1` | a ground name (`GND*`, `*GND`, `VSS*`, `0V`), and the most ground pins | `ground` |
| `PWR-1` | a power interface or supply pin; a switch's or inductor's far net; both nets of a switch at no switch node | `power`, medium |
| `HV-1` | a working voltage at or above `high_voltage_mv`, never a name | `high_voltage` |
| `SIG-0` | no other rule | `signal`, low |

A later rule does not replace an earlier result of at least its confidence; two rules that give different
kinds at one confidence keep the first and give `roles.ambiguous`. `PWR-1` does not contest `GND-1`. A
`low` result is not given, so the net falls to `SIG-0`.

## Where roles are kept

- A project that Fenolite built keeps its roles in `.fenolite/rules.json` (`RuleSet.roles`): the script's
  declarations (source `declared`) and the roles you confirmed (`confirmed`). A rebuild keeps the
  confirmed roles beside the new declarations.
- A board that Fenolite did not build keeps them in its role document, `<board stem>.roles.json` beside the
  board (or `--roles FILE`): canonical JSON of the schema `fenolite.roles.v0`, holding one `RoleSet`. The
  board file is never written, and one document serves a KiCad and an Altium board.
- Inferred roles that you have not confirmed are never stored: they are computed on each run.
- A declaration wins over a confirmed and over an inferred role of the same net, with
  `roles.declared-differs` (info) when they differ.

## Confirming roles

`fenolite roles PATH` shows one row per net and the groups, with `roles.unconfirmed` (info) giving the
count of inferred roles and groups. `--accept`, `--accept-all [--min-confidence]`, `--set
NET=KIND[:KEY=N]`, `--reject` (stored as a confirmed `signal`), `--accept-group`, `--reject-group` and
`--current NET=AMPS` write through the reviewed-plan protocol: `--dry-run` shows the plan and the roles as
they will be stored, `--confirm --plan ID` writes them. A script's declarations are changed in the script.
Until you confirm them, the findings of inferred roles are at most warnings.

## What measures what

Every measure is an analysis of [analyses](analyses.md), called with inputs that the roles derive; the
roles define no area, section, capacity or gap of their own. Each measure in `result.measures` names its
analysis and the copper state it read (`saved_fill`, `simulated`, `outline` or `tracks`).

| role or group | analysis and derived input | what the roles judge |
|---|---|---|
| hot loop, gate loop, Kelvin pair | `shapes.loop_areas` with one `[[loop]]` row per group, pads in loop order | the area, the placement bound (the shoelace area through the pad centres in loop order) and their ratio |
| a role with a current | `power.analyze_power` and `network.path_network` on its paths: its `[[path]]` rows, else from its connector and inductor pads (else its shunt's pads, else its first switch pad, else its first connector) to its other power pads; `split.analyze_split` with `--split` and a rise | width, section and vias by the rule of thumb, or the capacity fit with your rise |
| the pours of a role with a current | `shapes.analyze_necks` with a `[[neck]]` row at the rule-of-thumb width, on the fills active on its paths | the narrow places not already reported by a section |
| sense, gate and sensitive copper | `distance.analyze_distances` to switch-node copper on its layer, `returns.analyze_returns` and `coupling.analyze_coupling` on the neighbouring layer | the gap, the length over switch-node fill, the broadside overlap |
| gate nets and sensitive signals | `returns.analyze_returns` with the ground nets as reference | each span over a gap of the ground |
| high-voltage nets | `distance.analyze_distances` against your `[[distance]]` and `[[step]]` rows | the analysis's own `analysis.*` findings |
| separate sense nets | `ties.analyze_ties(sense=...)` | that they touch no other net's copper |

The analyses' own findings against the derived rows (`analysis.path-exceeded`, `analysis.neck-narrow`,
`analysis.return-split`) are replaced by the `roles.*` findings; their input warnings pass unchanged, except
the inputs of the capacity fit when no rise is given.

## Kelvin and gate-return measures

Two measures have no analysis; `fenolite.roles.kelvin` walks the copper of `analysis.copper.net_copper`
(items of one net that touch on a layer, and the layers of one via or pad) and measures nothing else.

- **Kelvin attachment.** For each sense pad `P`, the power copper of its net is the active part of
  `path_network` between `P` and the net's other power pads. The sense branch is the copper reached from the
  receiver's pad (or from a series resistor's pad on `P`'s net) without crossing `P` or entering that power
  copper. Each point where the branch touches `P` gets the offset `t = (a - centre(P)) · u`, `u` the unit
  vector toward the other sense pad: `t < 0` is on the outer half, where the load current's path through
  the pad and the solder is in the measurement (S-0850), `roles.kelvin-outer`. A branch that reaches power
  copper first, or a receiver on a force pad's net of a four-pad shunt, is `roles.kelvin-shared`.
- **Gate return.** The walk from the driver's return pad to the loop's source pad against the power copper
  of the switch's source: a return that reaches it first is `roles.gate-return-shared` (S-0852, S-0853).
  For a switch without a Kelvin pin, the copper that touches the source pad counts as reaching it; the
  source pads of the other gate loops end the walk, since switches with a common source share their
  driver's return pin.

## Checks

| finding | when |
|---|---|
| `roles.loop-area` | a hot loop's area over your `loop_max`, or its ratio over `loop_ratio_max` (bound at least `loop_bound_floor_nm2`) |
| `roles.gate-loop` | the same for a gate loop, against `gate_max` and `gate_ratio_max` |
| `roles.kelvin-apart` | a Kelvin pair's ratio over `pair_ratio_max` |
| `roles.loop-open` | a leg of a role loop, or a sense or return branch, without copper: that part is not judged |
| `roles.kelvin-outer`, `roles.kelvin-shared`, `roles.gate-return-shared` | the attachments above |
| `roles.near-switching` | sense, gate or sensitive copper within `switching_distance_nm` of switch-node copper on its layer, or over it on a neighbouring layer; one finding per victim and switch node |
| `roles.width-current`, `roles.section-current`, `roles.via-current` | copper of a role with a current below the rule of thumb (`width_per_amp_nm` times the current, `ceil(milliamps / milliamps_per_via)` vias), or below the current by the capacity fit with your rise |
| `roles.return-gap` | a gate net or a sensitive signal over a gap of its ground |
| `roles.limit-missing` | a high-voltage net without a distance row |
| `roles.current-missing` | a `power`, `switch_node` or `ground` role without a current (info): its copper is not judged for current |

Each finding names its limit as `key=value (origin)`: `profile` with the source of the default,
`override` or `requirements`.

## Codes

The seventeen codes of `fenolite.roles.codes.ISSUE_CODES` are explained by `fenolite explain CODE`. A
finding against a default of the profile is a `warning`. It is an `error` only when its limit is yours (an
override or the requirements file) and its role is confirmed or declared; the three attachment findings are
an `error` on a confirmed or declared group, since their sources state them as rules. Every finding on an
inferred role that is not confirmed is at most a `warning`. `roles.ambiguous` is a warning;
`roles.unconfirmed`, `roles.declared-differs` and `roles.current-missing` are info. No `FEN-` code is added.

## Default limits

The role checks judge against a profile of default limits, so that a board with roles but no requirements
file gets useful findings. The maintainer decided on 2026-10-28 that this profile departs, for the role
checks only, from the rule that every limit comes from the user ([analyses](analyses.md), "No shipped
requirement values"): `fenolite analyze` never reads it, and a finding against a default is never more than
a `warning`.

Each key names its source: an `S-` id of the [sources](evidence/sources.md), or the `H-G-ROLE-` hypothesis
of the [register](hypotheses.md) that measures a Fenolite heuristic. A finding names the limit it used, as
`key=value (origin)`, with the source id when the origin is `profile`.

| key | default | unit | source | label | meaning |
|---|---|---|---|---|---|
| `width_per_amp_nm` | 381000 | nm per A | S-0851 | `INFERRED` | the rule of thumb of a power track's width: 15 mil (0.381 mm) per ampere, used when no temperature rise is given |
| `milliamps_per_via` | 200 | mA | S-0851 | `INFERRED` | one standard via per 200 mA at a layer change of a power path; the via size is not stated |
| `kelvin_inner_edge` | 1 | flag | S-0850 | `INFERRED` | the sense branch of a Kelvin connection attaches on the inner half of the shunt's sense pad |
| `kelvin_pair` | 1 | flag | S-0852 | `INFERRED` | the two sense branches of a Kelvin connection run as a coupled pair |
| `loop_ratio_max` | 2000 | ‰ | H-G-ROLE-LOOP-RATIO | `INFERRED` | a hot loop's area at most twice its placement bound (Fenolite heuristic) |
| `loop_bound_floor_nm2` | 1000000000000 | nm² | H-G-ROLE-LOOP-RATIO | `INFERRED` | below this bound (1 mm²) a loop's ratio is not judged (Fenolite heuristic) |
| `pair_ratio_max` | 2000 | ‰ | H-G-ROLE-KELVIN-PAIR | `INFERRED` | the area between the sense branches at most twice its bound (Fenolite heuristic after S-0852) |
| `switching_distance_nm` | 1000000 | nm | H-G-ROLE-NEAR-SW | `INFERRED` | sense, gate and sensitive copper at least 1 mm from switching copper on its layer, and none over it on an adjacent layer (Fenolite heuristic after S-0852 and S-0851) |
| `gate_ratio_max` | 2000 | ‰ | H-G-ROLE-LOOP-RATIO | `INFERRED` | a gate loop's area at most twice its bound (Fenolite heuristic after S-0853 and S-0852) |
| `shunt_max_mohm` | 100 | mΩ | H-G-ROLE-INFER | `INFERRED` | a resistor of at most 100 mΩ is a shunt, for the classes only (Fenolite heuristic) |
| `high_voltage_mv` | none | mV | user | — | no net is high voltage unless you give its working voltage; with this limit, only a working voltage at or above it |
| `loop_max` | none | nm² | user | — | the largest area of a hot loop is yours |
| `gate_max` | none | nm² | user | — | the largest area of a gate loop is yours |
| `temp_rise_mk` | none | mK | user | — | the capacity fit of S-0269 runs only at your temperature rise |

The profile deliberately holds no value for:

- creepage and clearance: your `[[distance]]` and `[[step]]` rows. No freely usable table was found; the
  paid standards are not copied, and S-0854 gives the method only. A `high_voltage` net without a row is
  `roles.limit-missing`.
- temperature rise and copper thickness: your rise; the thickness comes from the stack-up or the option.
- current: the role's `milliamps`, a `[[current]]` row, or `--current NET=AMPS`. A `power`, `switch_node` or
  `ground` role without one is `roles.current-missing` (info) and its copper is not judged for current.

### Overrides

A `RoleLimit(key, value, net=None, kind=None)` overrides a key for the whole design, for one role kind or for
one net, from `design.role_limits(...)` in a script or the `limits` of a role document. The most specific
wins: the net's limit, then the kind's, then the design's, then the requirements file (a `[[current]]`
row's `temp_rise_mk`), then the profile. A limit of yours on a confirmed or declared role makes its finding
an `error`.

```python
design.role_limits(loop_max="200mm2")
design.role_limits(net=sw, loop_max="60mm2")  # the switch node's own limit wins
```

## Reference boards

`examples/roles/` holds three boards authored for Fenolite with the CC0 parts of `tests/data/libs/Roles.*`,
each with `good.py` and `bad.py` (a shared `*_board.py` builds both, and `open.py` of "Critical routes"). Every value is a round illustrative
number. The good variants give no warning once their roles are confirmed; the bad ones give exactly their
designed findings, on the KiCad and the Altium build alike.

| board | layers | bad variant |
|---|---|---|
| `buck_shunt` | 2 | the input capacitor far from the switches (hot loop about 180 mm²); one sense line from the outer end of the shunt's pad and one from the output pour; a 0.3 mm track on the 2 A output |
| `half_bridge` | 4 | the high side's gate return taken from the switch-node pour; the low side's gate trace on a detour (about three times its bound); a switch-node pour under the sense pair on the next layer; one bus via where the bus's via limit asks for five |
| `bms` | 2 | the monitor sensing the four-pad shunt on its force pads; the pack path narrowed to a 1 mm track at 20 A; a slot of the ground plane under a cell tap |

## Critical routes

`fenolite route BOARD --router octilinear --roles critical --dry-run` (change c0244) draws the copper that
clears the role findings of critical copper: each gate loop's drive and return, the return from the source
or Kelvin-source pad, and each Kelvin pair as a coupled pair from the inner halves of the sense pads. Only
confirmed or declared groups are routed, and only their open connections; the routes are locked and fenced
by corridors `role.corridor.<group>.<net>` that keep every pour off the branch. Then refill the zones
(`fenolite fill`) and run `fenolite roles BOARD --check`.

- **One entry per group** in `result.roles`: `routed`, `complete` (joined, no finding), `kept` (joined, with
  findings: run again with `--rip` to replace its branches; locked and script copper stay), `refused` (a
  role finding got worse), `unrouted` or `skipped`. A group that is not routed gives its reason and a
  proposal with the command to run and a `fenolite render --region` command for the place.

| reason | proposal |
|---|---|
| `no-room`, `isolation`, `near-switching`, `role-check`, `drc` | `free-corridor`: what blocks it, and the render command |
| `too-long` | `raise-limit` |
| `no-layer` | `allow-via` |
| `pads` | `move-part` |
| `unconfirmed` | `confirm`: `fenolite roles BOARD --accept-group NAME --dry-run` |
| `phase-1` | `power-copper`: a hot loop named by `--group` is power copper |

- **Run order with the power copper.** Critical routes first, then the pours around them. The power-copper
  phase treats locked copper and every `role.corridor.*` area as obstacles; `fenolite.roles.routes.
  critical_copper(design, roles)` lists the copper and corridors of each group. The other order works as
  well: existing pours are obstacles, and their provisional corridors are replaced along the routes.
- **Altium.** `route` writes KiCad boards. The Altium deliverable of a routed board is `fenolite convert
  BOARD --to altium`: the locked tracks and vias keep their lock, and each corridor becomes a keep-out region
  that forbids polygon copper on its layer. Routing a `.PcbDoc` in place is not supported.
- **Reference boards.** Each board has an `open.py` variant: its `bad` placement and power-copper faults,
  without its critical copper. Routed, the buck and the bms keep only their power-copper faults; the
  half-bridge routes both gate loops and reports its sense pair blocked by the switch-node pour under it.

## Limits

- Loop areas are plan areas of the copper legs: a return under the forward path on the next layer counts
  as no area, and a field solver would see more (c0213, a lower bound of the loop). The ratio to the
  placement bound compares like with like.
- The rule of thumb of S-0851 is one public figure for a standard board; it states no copper thickness or
  temperature rise. Above 1 A give a rise to judge by the capacity fit of S-0269.
- No public source gives a hot-loop or gate-loop area, a ratio, a pair ratio or a switching distance: those
  defaults are Fenolite heuristics, each measured by its `H-G-ROLE-` hypothesis on the reference boards
  only.
- No freely usable creepage or clearance table exists: those distances are yours.
- A share of the current between parallel copper is computed only with `--split` and a rise; otherwise a
  parallel element's finding says that the measure does not decide.
