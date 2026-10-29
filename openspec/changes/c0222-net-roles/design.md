## Context

- **Request.** On 2026-10-28 the maintainer asked for a router that works from electrical intent, starting
  with a phase 0 of net roles and their checks. The decisions of that day:
  - roles are inferred from the parts and the topology, and the user confirms them;
  - a script can declare or override a role;
  - the end product of the later phases routes the critical connections and the power copper
    automatically, proposes the rest, and marks what it could not finish;
  - phase 0 is useful on boards routed by hand;
  - the output serves KiCad and Altium, so the work happens on the Fenolite model;
  - default limits come from public sources, each with its source and label, and the user overrides them
    per project;
  - three reference boards authored for Fenolite (a buck with a current shunt, a half-bridge with a gate
    driver and Kelvin sense, a simple BMS), 2 to 4 layers each, are built in a good and a bad variant.
- **The target boards.** Motor drives and inverters, switch-mode supplies (buck, boost, flyback), chargers
  and BMS, and mixed-signal control. They have 2 to 4 layers and up to about 150 parts. Currents run from
  milliamperes to tens of amperes, and voltages from logic levels to mains and high DC buses.
- **What exists on `dev`** (base `1559f1b0`, 2026-10-29; the first draft was written on `dffa5852`):
  - **Model.**
    - Net classes with widths, clearances and pair values (`model/circuit.py`).
    - `RuleSet` with rules, check severities, proximity rules (c0113), height limits (c0140) and
      impedance targets (c0105, open). Each optional key is left out of `rules.json` when it is empty.
    - Differential pairs as `Interface`s (`model/pairs.py`), net-tie groups, copper locks.
  - **Analyses** (`analysis/`, `fenolite analyze`). Each judges only against the user's requirements file
    (`fenolite.requirements.v0`), and "No shipped requirement values" forbids defaults.
    - the capacity fit of S-0269 for tracks, arcs and vias (`current.py`);
    - power paths (c0175's package 7 base, c0115): the path network with via groups and active, in-series
      elements, the narrowest section of each fill on the path, the capacity of each element by the fit
      (`network.py`, `section.py`, `power.py`); and c0213's `power --split`, the share of the path's
      current in each track, fill and via from a resistive solve on a raster (`split.py`);
    - c0213's pour shapes (`shapes.py`): `necks` (necks, tips and slivers of pours below a `[[neck]]`
      width), `loops` (the area of the closed path through the pads of a `[[loop]]` row, legs between
      pads of one net along the shortest path along copper, other legs straight), `balance`;
    - c0204's practice checks (`pour.py`, `practice.py`, `coupling.py`): the three copper states of a
      zone layer (`saved_fill`, `simulated`, `outline`) and the simulated pour, `connectivity`, `dead`,
      `decoupling` (distance along copper, `copper_path`), `bodies`, `relief`, and the `coupling` screen
      (parallel stretches, narrowest gap and broadside overlap of aggressor and victim nets);
    - clearance, creepage (with grooves and slots), insulation (`distance.py`, c0047, c0115);
    - ties and sense nets (c0198: the copper of a sense net touches another net only through a net tie),
      isolation islands, crossings (c0199) and return paths (c0202: spans of a track's centre line with
      no reference copper on a neighbouring layer, `reference` nets selectable).
  - **Checks.** The copper check (`checks/copper.py`, `checks/clearance.py`); the stages of
    `fenolite check` (`checks/stages.py`, `checks/documents.py`), which a change may extend.
    `package-layering` lets `checks` import `model`, `geometry` and `backends.base` only: a check stage
    cannot import `analysis`, and the command injects what a stage needs (the plotter and fill oracle).
  - **Placement.** `place`, constrained placement (c0096), region placement by domain with barriers
    (c0205), layout reuse by pad fit with group moves (c0210, c0227).
  - **Generated copper** (c0224). `Design.band` (a power band along a spine of horizontal and vertical
    segments, widened in 45° steps between `width` and `max_width` where clearance allows),
    `keepout_ring`, `barrier` (a rule-area band around a net class), `body_keepout`, `fanout_zone` and
    `stitch_pieces` (vias where zones of one net overlap on two layers, `min_vias`), recorded by the
    script and resolved by the KiCad build after placement into locked items.
  - **Routing.**
    - The plugin protocol, with `direct`, `freerouting` (GPL, run as a subprocess) and
      KiCadRoutingTools; tiers, a time budget, plane fan-out, Specctra fidelity (c0197).
    - c0228's built-in `octilinear` router: short connections on one layer, no via, five 0/45/90° shapes
      per connection in clearance, rounds that put failed connections first (S-0838), pairs at their gap,
      the result judged by the copper check that the command passes in `RoutingJob.extra`.
    - c0225's `route --gate drc` and `tidy --gate drc`, through c0209's `fenolite.api.trial(..., gate=True)`:
      items that bring a new KiCad DRC finding are dropped and reported.
    - c0208/c0214's `fenolite tidy`: prune, chamfer, straighten, T-joints, zone corners, style report.
  - **Review.** c0211's region renders (`render --region`), c0199's crossings.
  - **Guide and protocols.** The agent guide with its coverage rule (AGENTS.md rule 6), the MCP server
    (one tool per public command, c0195), the Python API (c0206) and the reviewed-plan write protocol.
- **What fails in use.** The routers the maintainer tried treat every net alike:
  - a 20 A path gets the class width;
  - the input capacitor of a buck ends up 15 mm from the switches;
  - a sense amplifier's inputs are joined to the nearest point of the shunt's pour;
  - a gate trace goes one way and its return another.

  None of these is a DRC error. Since `1559f1b0` the analyses can measure most of them, but only when the
  user writes the rows that say which loop, which path and which nets: nothing knows the intent of a net.

## Goals / Non-Goals

**Goals**

- Every net of a board has a role, stated by the user or inferred with a reason, and the user can see and
  confirm it in one command.
- On a board routed by hand, `fenolite check` reports the power-electronics faults that DRC does not see,
  with a number, a place and the limit used, and says where the limit came from.
- The roles say what the analyses of `dev` measure (which loops, paths, pairs and nets), so that phase 0
  adds no second measure of a loop, a section, a current or a distance.
- The same roles and checks work on a KiCad board and on an Altium board, through the model.
- Phase 0 leaves the router of phases 1 to 4 a stable input: the roles, the groups and the limits.

**Non-Goals**

- See the proposal. In addition:
  - no automatic placement;
  - no change of copper by a role check;
  - no inductance or EMI number;
  - no role for a part, only for nets and groups of pads;
  - no new measuring kernel: a measure that `analysis` lacks is added to `analysis` by its own change.

## Decisions

### 1. Role kinds

One net has one role. The kinds are a closed set, `fenolite.roles.ROLE_KINDS`:

| kind | meaning | what the later router does with it |
|---|---|---|
| `power` | carries supply or load current | polygon, width from current |
| `switch_node` | a node that a switch drives between two potentials at high dv/dt | shortest, compact, routed first, with its hot loop |
| `ground` | a reference and return net (power or signal ground) | plane or pour, return under the outgoing path |
| `kelvin` | a sense connection that must carry no load current | from the inner pad edge, as a coupled pair, away from switching |
| `gate` | the drive of a switch's control terminal | out and return together, smallest loop |
| `signal` | everything else | cost-field search, routed last |
| `high_voltage` | a net whose main concern is its insulation from other nets | creepage and clearance first |

- **Attributes of a role** (all optional, all integers):
  - `milliamps`: the current;
  - `working_mv`: the working voltage against the design's ground;
  - `sensitive` (a flag on `signal`): keep it away from switching copper, as for a feedback or
    analogue input net.
- A `power` net with a `working_mv` above the profile's `high_voltage_mv` is judged for distances like a
  `high_voltage` net. A DC bus stays `power` and still gets its creepage checks.
- **Why one kind per net.** The router needs one answer per net. The cases where a net has two concerns
  (a high-voltage bus that carries current) are covered by attributes, not by a second kind.

### 2. Role groups

Some intents tie pads of several nets together. Groups are value objects that name pads (`REF-PIN`), never
geometry:

- **`HotLoop(name, pads)`.** The ordered pads of the commutation loop. For a synchronous buck: input
  capacitor `+`, high-side drain, high-side source, low-side drain, low-side source, input capacitor `-`.
  A pad pair of one part (drain and source of one transistor) is crossed inside the part; a pad pair of
  two parts is joined by the copper of their shared net. This is exactly the leg rule of c0213's `loops`,
  so a hot loop is measured as a `[[loop]]` row (decision 8).
- **`KelvinPair(name, element, receiver)`.** `element` names the two sense pads of the shunt (for a
  two-terminal shunt, its two pads; for a four-terminal shunt, its two sense pads, with the force pads in
  `force`). `receiver` names the two amplifier inputs. The two sense branches may be nets of their own,
  or branches of the power nets when the shunt has two pads.
- **`GateLoop(name, drive, gate, source, ret)`.** The driver output pad, the switch's gate pad, the
  switch's source pad (its Kelvin-source pad when the package has one), and the driver's return pad. An
  optional `resistor` names the gate resistor's two pads, and the loop runs through it. The out net
  (driver to gate) and the return net (source to driver return) are the gate loop's pairing: the checks
  judge them together, and phase 2 routes them as one pair.

Groups have names that are keys (`KEY` of `dsl/intents.py`). Each group records its source, as roles do.

### 3. Storage, ids and units

- **Model.** `fenolite.model.rules` gains frozen value objects:
  - `NetRole(net, kind, source, rule="", confidence="", milliamps=None, working_mv=None,
    sensitive=False)`;
  - `HotLoop`, `KelvinPair` and `GateLoop` as in decision 2;
  - `RoleLimit(key, value, net=None, kind=None)`.

  `RuleSet` gains `roles: RoleSet | None`. A `RoleSet` holds `nets`, `loops`, `kelvins`, `gates` and
  `limits`, each sorted by its key.
  - It is a value, not an entity: a net role's key is the net's name, a group's key is its name.
  - It is written in `rules.json` under the key `roles` only when it is not empty, so a design without
    roles writes the bytes it wrote before.
  - `SCHEMA_VERSION` stays `"0"`; the schema is regenerated.
  - No backend lowers roles. They stay in `.fenolite/`, as height limits do.
- **Companion document.** A board that Fenolite did not build keeps its roles beside the board:
  - The file is `<board stem>.roles.json`: canonical JSON, schema `fenolite.roles.v0`, holding one
    `RoleSet`.
  - The board file itself is never written.
  - `--roles FILE` names another file.
  - The same document serves a `.kicad_pcb` and a `.PcbDoc`. Roles name nets and pads by name, which
    both readers give.
- **Units.**
  - Lengths are integer nanometres. Areas are integer square nanometres (`area_nm2`): 180 mm² is
    `180_000_000_000_000`, an integer that Python and the canonical JSON writer keep exactly.
  - Currents are integer milliamperes, voltages integer millivolts, and ratios integer per-mille.
  - No float enters the model or a reply. A reply's text says areas in mm² with two decimals, computed
    with `Fraction`.
- **Sources.** `inferred` is written by `fenolite roles --confirm` only for roles the user accepted as
  inferred, and such a role is stored as `confirmed`. `declared` comes from a design script, and it wins
  over a stored `confirmed` role of the same net, with `roles.declared-differs` (info) when they
  disagree. Unconfirmed inferred roles are never stored: they are recomputed on each run.

### 4. Part classes

Inference first gives each component a class: one of `transistor`, `diode`, `inductor`, `capacitor`,
`resistor`, `shunt`, `driver`, `amplifier`, `controller`, `connector`, `net_tie` or `other`. Each class
has terminal names:

- `transistor`: `gate`, `drain`, `source`, and `kelvin_source` when the part has a pin for it;
- `shunt`: `force` and `sense` pads.

The evidence for a class, strongest first:

1. a class or terminal map that the user gives (`design.part_class(...)` or `--class REF=CLASS`);
2. the pin names of the symbol: `G`/`D`/`S`; `IN+`/`IN-`, `+IN`/`-IN`, `SP`/`SN`, `CSP`/`CSN`, `SRP`/`SRN`
   for an amplifier input pair; `HO`, `LO`, `GH`, `GL`, `OUT`, `DRV` for a driver output; `HS`, `VS`,
   `SW`, `PH` for a switching-node pin; `COM`, `VEE`, `LS`, `PGND` for a driver return. The tables are
   written in `roles/classify.py` as Fenolite's own vocabulary, from no library;
3. the pin types of the model (`power_in`, `power_out`);
4. the value: a resistance parsed by the DSL quantity parser at or below the profile's `shunt_max_mohm`
   (a heuristic, default 100 mΩ) makes a resistor a shunt, and so does a four-pad resistor footprint;
5. the reference prefix (`Q`, `D`, `L`, `C`, `R`, `U`, `J`): weakest, and used only to break ties.

A class found only from the prefix has `low` confidence. A class found from pin names or from the user is
`high`. A part in a net-tie group of the model is `net_tie` whatever else holds.

### 5. Inference rules

The rules form a closed table, `roles/infer.py`, ordered and deterministic. Each fired rule records its
id, its confidence (the lowest of the classes it used) and the pads it read.

| rule | fires when | gives |
|---|---|---|
| `SW-1` | a net joins a transistor's `source` and another transistor's `drain`, and an inductor or a winding pin | `switch_node`, high |
| `SW-2` | a net joins one transistor's `drain` or `source` (or a diode) and an inductor | `switch_node`, medium |
| `SW-3` | a net joins a driver or controller pin named as a switching-node pin | `switch_node`, medium |
| `HL-1` | for each `switch_node`, a capacitor whose two nets are the far `drain` net of the high side and the far `source` net of the low side (or the diode's far net) | `HotLoop` through those pads, the confidence of the switch node |
| `GD-1` | a net joins a driver output and a transistor `gate`, directly or through one resistor | `gate` (both nets when there is a resistor), high |
| `GD-2` | for each `gate`, the transistor's `kelvin_source` or `source` and the driver's return pin | `GateLoop`; the return net keeps its own role |
| `KS-1` | a `shunt` whose two sense terminals reach an amplifier input pair, directly or through at most two passive parts in series per side | `KelvinPair`; separate sense nets get `kelvin` |
| `GND-1` | a net whose name matches the profile's ground patterns (`GND*`, `*GND`, `VSS*`, `0V`), or the net of the most `power_in` pins of negative supply | `ground`; high with both, medium with one |
| `PWR-1` | a net with a power symbol, or with `power_in`/`power_out` pins, or a transistor's far `drain`/`source` net, or an inductor's far net | `power`, medium |
| `HV-1` | a net with a `working_mv` at or above `high_voltage_mv` | `high_voltage`, high; `HV-1` never fires from a name |
| `SIG-0` | no other rule | `signal`, low |

- **Order and conflicts.** The rules run in the order of the table, and a later rule does not replace an
  earlier `high` result. When two rules give different kinds at the same confidence, the net gets the
  first and the issue `roles.ambiguous` (warning) names both.
- **Currents.** A role's `milliamps` comes from the role, then from a `[[current]]` row of the requirements
  file, then from `--current NET=AMPS`. Fenolite infers no current and ships no default current.
- **Why from names and topology, not from libraries.** Library names differ between users and tools.
  Terminal names and the circuit's shape are what both backends give.

### 6. Confirmation flow

1. `fenolite roles PATH` (read-only) shows one row per net: `net`, `kind`, `source`, `rule`,
   `confidence`, `pads`, `milliamps`, `working_mv`. Then the groups with their pads, and the issues
   `roles.unconfirmed` (info, with the count) and `roles.ambiguous`.
2. The user confirms:
   - `--accept NET[,NET...]` or `--accept-all [--min-confidence high|medium]` stores inferred roles as
     `confirmed`;
   - `--set NET=KIND[:milliamps=N][:working_mv=N]` stores a role the user chose;
   - `--reject NET` stores `signal` as `confirmed`, so the net is not inferred again;
   - `--accept-group NAME` and `--reject-group NAME` do the same for groups;
   - `--current NET=AMPS` sets `milliamps`.
3. The write goes through the reviewed-plan protocol: `--dry-run` gives `result.plan`, and
   `--confirm --plan ID` writes the role document. For a built project, the write goes to
   `.fenolite/rules.json`, and the build keeps it on the next run.
4. A design script's declarations are `declared`. `fenolite roles` shows them and cannot change them; it
   tells the user to edit the script.

### 7. The role profile (defaults and overrides)

The maintainer's decision of 2026-10-28 departs, for role checks only, from the rule that every limit
comes from the user (requirement "No shipped requirement values"; c0175, "Non-goals"). `analyze` keeps that
rule: the command never reads the profile. The defaults live in `src/fenolite/roles/profile.py` as
constants, outside `src/fenolite/analysis/`. Each constant names its source id and label, and
`docs/roles.md`, "Default limits", lists them. The table below is the whole default profile.

| key | default | source | label |
|---|---|---|---|
| `width_per_amp_nm` | 381 000 nm per ampere (15 mil per ampere) | S-0851 | `INFERRED` (public rule of thumb) |
| `milliamps_per_via` | 200 | S-0851 ("one standard via per 200 mA"; the via size is not stated) | `INFERRED` |
| `kelvin_inner_edge` | the sense branch attaches on the inner half of the sense pad | S-0850 | `INFERRED` |
| `kelvin_pair` | the two branches run as a coupled pair | S-0852 | `INFERRED` |
| `loop_ratio_max` | 2000 per-mille: the loop's area at most twice its placement bound | Fenolite heuristic | `INFERRED` (`H-G-ROLE-LOOP-RATIO`) |
| `loop_bound_floor_nm2` | 1 mm²: below it the ratio is not judged | Fenolite heuristic | `INFERRED` |
| `pair_ratio_max` | 2000 per-mille, for the area between the two Kelvin branches | Fenolite heuristic after S-0852 | `INFERRED` (`H-G-ROLE-KELVIN-PAIR`) |
| `switching_distance_nm` | 1 mm on one layer; any overlap on an adjacent layer | Fenolite heuristic after S-0852 and S-0851 | `INFERRED` (`H-G-ROLE-NEAR-SW`) |
| `gate_ratio_max` | 2000 per-mille | Fenolite heuristic after S-0853 and S-0852 | `INFERRED` |
| `shunt_max_mohm` | 100 | Fenolite heuristic (classification only) | `INFERRED` |
| `high_voltage_mv` | none: no net is high voltage unless the user gives a `working_mv` | — | — |
| temperature rise, copper thickness | none: the fit of S-0269 runs only with the user's rise; thickness comes from the stack-up | — | — |
| creepage, clearance | none: the user's `[[distance]]` and `[[step]]` rows | — | — |

- **What has no public source.** No public, freely usable source gives a number for a hot-loop area, a
  Kelvin pair spacing or a distance from switching copper. The public notes (S-0851 to S-0853) say only
  to minimise them. Those defaults are therefore relative to the placement bound or are Fenolite
  heuristics. Each is a hypothesis below, and the reference boards measure it.
- **Creepage and clearance.** IEC 60664-1 and IPC-2221 are paid. The public material found (S-0854) gives
  the method: creepage by RMS working voltage, pollution degree and material group; clearance by
  transients, pollution degree and altitude. It reproduces tables from the standards, which Fenolite does
  not take. Fenolite ships no table: a `high_voltage` net without a `[[distance]]` or `[[step]]` row is
  `roles.limit-missing` (warning), with a hint that names the method.
- **Current: the rule of thumb and the fit.** The rule of thumb is linear in current, and the fit of S-0269
  is not.
  - Computed by Fenolite from the two sources (`INFERRED`): for 35 µm outer copper at a 10 K rise, the fit
    needs about 0.30 mm at 1 A, 0.78 mm at 2 A and 2.77 mm at 5 A. The rule of thumb gives 0.38 mm,
    0.76 mm and 1.91 mm.
  - So the rule is the more lenient of the two above about 1.9 A at a 10 K rise, and above about 5.7 A at
    20 K.
  - When the user gives a temperature rise (`--temp-rise`, the requirements file or `design.role_limits`),
    the fit is used, through the capacities that `analyze_power` already computes (decision 8). Otherwise
    the rule of thumb is used.
  - Each row names the method it used. A row judged by the rule of thumb above 1 A also gets the hint to
    give a rise.
- **Overrides.** `design.role_limits(key=value, net=..., kind=...)` in a script, or `limits` in the role
  document, override a key for the whole design, for one kind or for one net. The most specific wins.
  The user keys `loop_max` and `gate_max` (areas) have no default.
- **Severity.** A finding against a default limit is a `warning`. It becomes an `error` when two
  conditions hold: the limit is the user's (an override, or the requirements file), and the role is
  `confirmed` or `declared`. Topological checks (the Kelvin and gate-return attachments) are an `error`
  on a confirmed role, because S-0850 and S-0852 state them as rules, not as numbers. Every check on an
  unconfirmed inferred role is at most a `warning`.

### 8. Measuring through the analyses of `dev`

Phase 0 writes no measuring kernel. `fenolite.roles.measure` turns the roles into the inputs of the
analyses that `dev` already has, calls them on the `Design` a backend gives (so KiCad and Altium boards
are measured by the same code), and hands their rows to `fenolite.roles.checks`, which judges them against
the role limits. Every row keeps the copper state (`saved_fill`, `simulated`, `outline`) and the evidence
of the analysis that measured it. The analyses' own `analysis.input-missing` and `analysis.item-unsupported`
warnings are passed through unchanged.

| role measure | analysis of `dev` that measures it | what roles add |
|---|---|---|
| hot loop, gate loop, Kelvin pair area | c0213 `shapes.loop_areas`, one derived `[[loop]]` row per group (pads in loop order) on c0204's `pour_copper` | the placement bound and the ratio; the group's limits |
| current of tracks, arcs, fills and via groups | c0175/c0115 `power.analyze_power` (path network, in-series elements, narrowest sections, via groups, capacities by the S-0269 fit at the user's rise) | derived path pads; the rule-of-thumb width and via count when no rise is given; role severities |
| share of a parallel element | c0213 `split.analyze_split` (`--split`), when the thickness, plating and stack-up are given | judges a parallel element by its share instead of leaving it undecided |
| pour narrowings of a power net | c0213 `shapes.analyze_necks`, one derived `[[neck]]` row of the required width per role net with a current | the required width from the role's current |
| sense or gate copper near switching copper | c0047 `distance.analyze_distances` (gaps per layer), c0202 `returns.analyze_returns` with the switch nodes as `reference` (length over switching fills on a neighbouring layer), c0204 `coupling.analyze_coupling` (broadside overlap of tracks, parallel runs) | which nets are victims and aggressors; the distance limit |
| return gaps of gate and sensitive nets | c0202 `returns.analyze_returns` with the `ground` nets as `reference` | which nets; the role code |
| a sense net of its own that touches power copper | c0198 `ties.analyze_ties(sense=...)` | the sense nets of each `KelvinPair` |
| high-voltage distances | `distance.analyze_distances` with the user's `[[distance]]` and `[[step]]` rows | which nets; `roles.limit-missing` |
| Kelvin attachment on the pad's inner half, gate return from the source pad | none on `dev` | the whole measure (below) |

- **Loops.** For each `HotLoop`, `GateLoop` (drive, resistor pads, gate, source, return) and `KelvinPair`
  (element `+`, receiver `+`, receiver `-`, element `-`), `measure` builds a `LoopRule` row and calls
  `loop_areas`. A leg between pads of one net follows c0204's shortest path along copper (stored fills
  walked, a simulated pour not), any other leg is straight, exactly as c0213 specifies; the area is the
  absolute shoelace sum of the closed polyline. Roles add:
  - **Placement bound:** `bound_nm2`, the shoelace area of the polygon through the pad centres in loop
    order. It is what placement alone fixes, measured on the same pad positions as the loop's legs.
  - **Ratio:** `ratio_permille = area * 1000 // bound` when the bound is at least `loop_bound_floor_nm2`.
  - **Open legs:** a leg of two pads of one net that c0213 drew straight (no copper joins them) makes the
    loop `roles.loop-open` (warning): the board is not routed there, and the area is not judged.
- **Current capacity**, for each `power`, `switch_node` and `ground` net with `milliamps`:
  - **Paths.** The `[[path]]` rows of the requirements file for the net; else one derived path from the
    net's connector and inductor pads to its transistor, shunt and capacitor pads; else the net's tracks and
    arcs are judged one by one, as `analyze_current` gives them, and no section or via is judged.
  - **With a rise** (the fit): `analyze_power` runs with the paths, the rise, the stack-up's thicknesses and
    the plating, and gives each active element its capacity. An element whose capacity is below the role's
    current is a finding when it is in series; a parallel element is judged by its share when
    `analyze_split` ran, otherwise it is reported at most as a `warning` whose message says that its share
    is not computed, as `analysis.path-undecided` does.
  - **Without a rise** (the rule of thumb): the same elements, with no capacity. A track or arc is judged by
    its width, a fill by its section's `low`, against `width_per_amp_nm` times the current; a via group by
    its count of vias against `ceil(milliamps / milliamps_per_via)`.
  - **Pours.** `analyze_necks` runs with a derived `[[neck]]` row whose `min_width_nm` is the required
    width, so a narrowing of the net's pour off the path's narrowest section is also found.
  - **Findings:** `roles.width-current` (track or arc), `roles.section-current` (a fill's section or a
    neck, naming which), `roles.via-current` (a via group); each names the item, its width or count, the
    required value and the method. An `analysis.*` finding against a derived row is replaced by the
    `roles.*` finding, so no `analysis.path-exceeded` or `analysis.neck-narrow` comes from the profile.
  - A role without `milliamps` gets `roles.current-missing` (info), and its current is not judged.
- **Near switching.** The victims are each `kelvin` branch, each `gate` net of another switch than the
  node's, and each `signal` with `sensitive`; the aggressors are the `switch_node` nets:
  - the least gap on one layer comes from the `gaps` of `analyze_distances` for each victim and aggressor
    pair;
  - the overlap on an adjacent layer is the victim's length over switching fills (`analyze_returns` with the
    switch nodes as `reference`: the referenced length) plus the broadside overlap of tracks that
    `analyze_coupling` gives;
  - a gap under `switching_distance_nm`, or any overlap, is `roles.near-switching` (warning); the coupling
    score of the pair is shown beside it and judges nothing.
- **Returns.** For `gate` and `sensitive` `signal` nets, `analyze_returns` runs with the `ground` nets as
  `reference`. Each `split` span becomes `roles.return-gap` (warning), with the span; the
  `analysis.return-split` of the same span is not repeated.
- **High voltage.** For each `high_voltage` net, and each `power` net whose `working_mv` is at or above
  `high_voltage_mv`, the distances to every other net come from `analyze_distances` (clearance and
  creepage, with grooves), against the user's rows. Their findings keep their `analysis.*` codes and
  severities, since the rows are the user's. Without a row, the issue is `roles.limit-missing`.
- **Kelvin attachment** (new). For each sense pad `P` of a `KelvinPair`:
  1. The **power copper** of `P`'s net is the union of the active elements of `path_network` between `P`'s
     part and the other power pads of that net.
  2. The **sense branch** is the connected copper reached from the receiver pad without crossing `P`'s pad
     shape and without entering power copper. A net tie (class `net_tie`) ends the branch at its pad. When
     the branch is a net of its own, `analyze_ties(sense=...)` gives the node it shares with another net
     (`analysis.sense-shared` becomes `roles.kelvin-shared`).
  3. The **attachment** is the set of points where the sense branch touches `P`'s pad: a track end inside
     the pad, or the centroid of the overlap of a fill with the pad.
  4. With `u` the unit vector from `P`'s centre to the centre of the other sense pad, the attachment
     offset `t = (a - centre(P)) · u`, in nm, is reported for each attachment point `a`.

  Findings:
  - `t < 0` is `roles.kelvin-outer`: the sense line starts on the outer half of the pad, where the load
    current's path through pad and solder lies in the measurement (S-0850);
  - a sense branch that reaches power copper before the pad (a track joined to a pour or to a power track)
    is `roles.kelvin-shared`, and the reply names the shared item;
  - for a four-terminal shunt, a sense branch that touches a force pad is `roles.kelvin-shared`.
- **Kelvin pair.** The loop's `area_nm2`, bound and ratio as above, judged by `pair_ratio_max`.
  `roles.kelvin-apart` is a warning, and the reply gives the longest leg of the two branches.
- **Gate return** (new). For a `GateLoop`, the return branch is found as a sense branch is, from the
  driver's return pad to the `source` pad. A return that reaches the switch's power source copper before the
  `source` pad (or the Kelvin-source pad) is `roles.gate-return-shared`.

### 9. Issue codes and severities

The closed table `fenolite.roles.codes.ISSUE_CODES` follows the pattern of `analysis/codes.py`.
`fenolite explain` gains each code. No `FEN-` code is added:

- a bad option is `FEN-2001`;
- an unreadable or malformed role document is `FEN-3004`;
- a write uses `FEN-4001` and `FEN-4002`;
- an error finding gives `FEN-5001`, exit 5.

| code | severities | meaning |
|---|---|---|
| `roles.loop-area` | warning, error | a hot loop over the user's `loop_max`, or over the bound ratio |
| `roles.loop-open` | warning | a leg of a role loop, or a sense branch, has no copper path |
| `roles.gate-loop` | warning, error | a gate loop over its limit or ratio |
| `roles.gate-return-shared` | warning, error | the gate return leaves from the power source copper, not from the source or Kelvin-source pad |
| `roles.kelvin-outer` | warning, error | the sense branch attaches on the outer half of the pad |
| `roles.kelvin-shared` | warning, error | the sense branch shares power copper or a force pad |
| `roles.kelvin-apart` | warning | the two sense branches enclose more than the ratio |
| `roles.near-switching` | warning | sense, gate or sensitive copper too near switching copper |
| `roles.width-current` | warning, error | a track or arc narrower than its current needs |
| `roles.section-current` | warning, error | the section or a neck of a pour is too narrow for its current |
| `roles.via-current` | warning, error | too few vias, or too little via capacity, at a layer change |
| `roles.return-gap` | warning | a gate or sensitive net crosses a gap of its ground |
| `roles.limit-missing` | warning | a high-voltage net without a distance requirement |
| `roles.current-missing` | info | a role without a current |
| `roles.ambiguous` | warning | two rules give different kinds at one confidence |
| `roles.unconfirmed` | info | the count of inferred roles not confirmed |
| `roles.declared-differs` | info | a script's role differs from a stored or inferred one |

The first draft's `roles.input-missing` is gone: a missing input is the `analysis.input-missing` of the
analysis that needed it.

### 10. Package, command line, check stage, MCP and guide

- **Package.** `src/fenolite/roles/` is a new sub-package. `package-layering`, "Allowed import edges", gains
  the row `roles` → `model`, `geometry`, `backends.base`, `analysis`; nothing but `cli` and the root modules
  imports `roles`. `checks` keeps its edges.
- **`fenolite roles PATH`.** `PATH` is a board, or a built project folder, that a registered backend
  reads. Options: `[--roles FILE] [--requirements FILE] [--net GLOB]... [--kinds KIND,...]
  [--class REF=CLASS]... [--check] [--temp-rise KELVIN] [--copper-thickness ...] [--via-plating LENGTH]
  [--board-thickness LENGTH] [--pour-grid LENGTH] [--split] [--arc-tol LENGTH] [--current NET=AMPS]... [--accept NET[,NET...]]... [--accept-all]
  [--min-confidence high|medium] [--set NET=KIND[:KEY=N]...]... [--reject NET]... [--accept-group NAME]...
  [--reject-group NAME]... [--dry-run | --confirm [--plan ID]]`. The measuring options are those of
  `analyze`, parsed by the same code, and are usage errors without `--check`.
  - Schema `fenolite.roles.v0`.
  - Without an accept, set or reject option, the command is read-only. With one, it is a writing command
    of the mutation protocol, and it writes only the role document.
  - `result` holds `roles`, `loops`, `kelvins` and `gates`; with `--check`, also `measures` (each with the
    analysis and copper state it came from) and `summary`.
- **`fenolite check`.** A stage `roles.rules`, standing after `placement.rules` and before `zone.fill` in
  `STAGE_ORDER`, and after `placement.rules` and before `parity` in `DOCUMENT_STAGES`:
  - a default stage that runs no tool;
  - `checks.roles.roles_stage` takes a `RolesJudge` (a protocol of `checks.roles`: a callable from the
    board model, the `.fenolite/` model, the project and the board-frame pads to the judged issues,
    summary and evidence) that `cmd_check` passes as `fenolite.roles.judge`, as it passes the plotter and
    the fill oracle; `checks` does not import `roles` or `analysis`;
  - it reads the stored roles (`rules.json` or the companion document) and the inferred ones;
  - it judges them as decisions 7 and 8 say;
  - it is skipped with the reason `no-roles` when the board has no stored or declared role, so existing
    boards keep their result, and with `not-judged` when no judge is passed.
- **MCP and Python API.** The server makes a tool of each public command, so `roles` is served as
  `fenolite_roles`; `fenolite.api.run("roles", ...)` reaches it through the dispatcher (c0206). Its writes
  follow the plan protocol, as every writing tool's do.
- **Guide.** The guide gets tested lines (`tests/unit/agent/test_pages.py`):
  - `roles` on the page `checks`, with a `fenolite-cmd` block;
  - `design.net_role`, `design.hot_loop`, `design.kelvin`, `design.gate_loop`, `design.role_limits` and
    `design.part_class` on `board-power`, in a `fenolite-design` block;
  - one line on `board-grounds` (`roles.return-gap`) and one on `board-insulation`
    (`roles.limit-missing`).

  No page names a limit as a value, a source company or a change id, as "Page budgets and writing rules"
  requires. `tools/gen_agent_guide.py` regenerates `commands` and `dsl-reference`.

### 11. DSL

```python
design.part_class(q1, "transistor", terminals={"gate": "1", "source": "2", "kelvin_source": "3", "drain": "4"})
design.net_role(vbus, "power", current=amp(20), voltage=volt(400))
design.net_role(sw, "switch_node")
design.hot_loop("buck", pads=[c3.pad(1), q1.pad("D"), q1.pad("S"), q2.pad("D"), q2.pad("S"), c3.pad(2)])
design.kelvin("isense", element=(r12.pad(1), r12.pad(2)), receiver=(u3.pad("IN+"), u3.pad("IN-")))
design.gate_loop("hs", drive=u2.pad("HO"), gate=q1.pad("G"), source=q1.pad("KS"), ret=u2.pad("HS"),
                 resistor=(r5.pad(1), r5.pad(2)))
design.role_limits(loop_max="60mm2", kind="switch_node")
```

- The calls record plain data, as the copper intents and c0224's generated-copper calls do. The build
  resolves pads after placement and writes `RuleSet.roles` with source `declared`.
- A call with an unknown kind or key, a pad of another part, or a group name used twice raises
  `DslError`.
- Currents and voltages take the existing quantities `amp(...)` and `volt(...)`, stored as whole mA and mV
  (a value that is not a whole number of them raises `DslError`). Areas take the existing area strings of
  `as_nm2` (`"60mm2"`). No new DSL helper is added.

### 12. Reference boards

Each board is authored for Fenolite under `examples/roles/<board>/`. It has a shared module and two
scripts, `good.py` and `bad.py`. It uses authored CC0 footprints and symbols added to `tests/data/libs`
(a power MOSFET in an SO-8 style package and in a four-pin package with a Kelvin source, a shielded
inductor, a 2512 two-pad shunt, a four-pad shunt, a half-bridge driver, a current-sense amplifier and a
cell-monitor IC). Every value is a round illustrative number, marked as such. The pours are ordinary
zones of the script (`zone()`), not c0224's generated copper, which the Altium target refuses
(`kicad.generate.altium`), so both targets build the same script; phase 1 later regenerates the same
boards' power copper from their roles and compares.

| board | layers | parts | good variant | bad variant (designed faults) |
|---|---|---|---|---|
| `buck_shunt` | 2 | about 25 | input capacitor across the switch pair; switch node a compact pour; output shunt sensed from the inner pad edges as a pair; power copper as pours | input capacitor 15 mm away (hot loop about 180 mm²); sense lines from the outer ends of the shunt pads, one from the pour; a 0.3 mm track on the 2 A output path |
| `half_bridge` | 4 | about 40 | gate out on layer 1 and return on layer 2 under it, from the Kelvin-source pad; low-side shunt with a coupled sense pair; DC bus `working_mv` 400 000 with the user's distance rows | gate return from the source pour; gate loop over three times its bound; sense pair crossing the switch node's pour on the adjacent layer; one bus via where the rule of thumb needs five |
| `bms` | 2 | about 30 | pack shunt sensed by a four-pad part; charge and discharge gate traces with their returns; pack path as pours | sense from the force pads; pack path narrowed to 1 mm for 20 A; a cell-tap trace across a ground gap |

- The tests build each variant, run `fenolite roles --check`, and assert:
  - the inferred roles and groups, against an expected table in the test;
  - no finding of severity warning or above on `good`;
  - the designed findings on `bad`, with their measures within stated tolerances.
- Both backends: each variant is also built for Altium. The test compares the role rows and measures of
  the two readings (`ALTIUM-VERIFIED` is not claimed; the Altium reading is the model of the written
  document).

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| `H-G-ROLE-INFER` | The rule table of decision 5 gives the expected role of every net, and the expected groups, on the six reference variants | `tests/unit/roles/test_infer_reference.py` | every net matches the expected table, no group is missing or extra, and every `low` result is `signal` |
| `H-G-ROLE-LOOP-RATIO` | A ratio of twice the placement bound, on the areas of c0213's `loops`, separates the good and the bad hot and gate loops of the reference boards | `tests/unit/roles/test_reference_boards.py -k loop` | every good loop is at or under 2000 per-mille, and every designed bad loop is over it |
| `H-G-ROLE-KELVIN-EDGE` | The attachment offset of decision 8 tells an inner-edge sense connection from an outer one and from one taken off the pour | `tests/unit/roles/test_kelvin.py` | on authored pads, inner attachments give `t ≥ 0`, outer ones `t < 0`, and a branch from the pour gives `roles.kelvin-shared` |
| `H-G-ROLE-KELVIN-PAIR` | A pair ratio of twice the bound separates a coupled sense pair from a split one on the reference boards | `tests/unit/roles/test_reference_boards.py -k kelvin` | good pairs at or under 2000 per-mille, bad pairs over it |
| `H-G-ROLE-NEAR-SW` | One millimetre on a layer and no overlap on an adjacent layer, measured by the distance, return and coupling analyses, flag the designed crossings and nothing on the good variants | `tests/unit/roles/test_reference_boards.py -k switching` | exactly the designed `roles.near-switching` findings |
| `H-G-ROLE-CURRENT` | The width, section and via checks on the elements of `analyze_power` find the designed narrow copper and the single via, by both methods | `tests/unit/roles/test_current.py` | the 0.3 mm track at 2 A fails both methods, a 1 mm track passes the rule of thumb, and the via count matches `ceil(I / 200 mA)` |

The first draft's hypothesis of its own loop area is dropped: the loop area is c0213's measure, settled by
`H-G-SHAPE-LOOP`.

## Evidence level per behaviour

| behaviour | level | proof |
|---|---|---|
| role model, storage, round trip | `INFERRED` until a release; the write is plain canonical JSON | `tests/unit/model/test_rules.py -k roles` |
| inference | `INFERRED` (`H-G-ROLE-INFER`) | the reference boards |
| measures | the evidence of the analysis that measured each row (`H-G-SHAPE-LOOP`, `H-G-AN-NETWORK`, `H-G-AN-SECTION`, `H-G-SHAPE-NECK`, `H-G-POWER-SPLIT`, `H-G-RETURN-PATH`, `H-G-PRACTICE-COUPLING`), combined with the role hypotheses above | the analyses' own tests and the reference boards |
| default limits | `INFERRED`, each with its source or hypothesis | `docs/roles.md`, "Default limits" |
| KiCad reference boards | `KICAD-VERIFIED` that DRC finds nothing on the good variants | `tests/kicad/roles/test_reference_drc.py` |

## Plan of phases 1 to 4

Each phase becomes its own change with the next free id when its turn comes. Sizes are design-days, as in
`docs/roadmap.md`, re-estimated on 2026-10-29 against `1559f1b0`.

| phase | what dev already gives | what the phase adds | size (was) |
|---|---|---|---|
| 1. Power and ground copper | c0224: `band` (width between `width` and `max_width`, 45° steps, clearance), `stitch_pieces` (`min_vias`), `fanout_zone`, `barrier`, `keepout_ring`, `body_keepout`, resolved after placement into locked items; `zone()`; `fill`; c0204/c0213 analyses | a resolver that turns roles into those calls: a `power` net's band with `width` from its current (decision 7's method) and a spine of horizontal and vertical segments between its pads (the one new geometric step); a `ground` zone on each reference layer; `stitch_pieces` with `min_vias` from the current (`milliamps_per_via`); a `barrier` around each `high_voltage` net's class; refill, then `roles.rules` as the acceptance gate, with `--gate drc` | 5 (10) |
| 2. Deterministic critical routes | c0228: `route --router octilinear` (five 0/45/90° shapes per connection on one layer, no via, rounds, pairs at their gap, the copper check from `RoutingJob.extra`); c0225/c0209: `--gate drc`, `api.trial(..., gate=True)` | a role-ordered job (switch-node copper, then gate loops, then Kelvin pairs; the hot loop is copper of phase 1); the gate loop's out and return nets routed as one octilinear pair; Kelvin pairs entering each sense pad on its inner half (an entry point instead of the pad centre); a `role_check` callable in `RoutingJob.extra`, as `copper_check` is, which refuses a connection whose phase-0 checks get worse; `--gate drc` for the result | 6 (12) |
| 4. Propose and lock | copper locks in the model; c0211 region renders; c0199 crossings; the plugin protocol (Freerouting, KiCadRoutingTools) for the rest; c0208/c0214 `tidy` (prune, chamfer, straighten) with `--gate drc` | `route --router roles --propose`: phases 1 and 2 as locked copper, the rest sent to the chosen external router, `tidy --gate drc` on the job's copper, every unfinished connection marked with its reason (no way across by c0199, a check refused it), a region render of each, and a run again that keeps what the user locked | 7 (10) |
| 3. Own search router | c0228's acceptance test, rounds of failed connections first, pair offsets and copper-check judging; the route merge and DRC gate | what the five shapes cannot do: a search (A* with 45° moves, from published descriptions only) on several layers with vias, for connections the shapes leave open; cost fields from the roles (repelled by switching copper, drawn over ground, kept off high-voltage gaps); negotiated congestion with rip-up and reroute across nets (PathFinder-style), beyond c0228's reordering; as a search mode of the octilinear router, sharing its acceptance and checks | 18 (25) |

- **Cut order.** Unchanged: 0, then 1, 2 and 4 with an external router for the rest, then 3 last. Phases 1
  and 2 give the maintainer the deliverable (critical routes and power copper done) without Fenolite's own
  general router. Phase 3 is the largest and the riskiest, and it can stop at any time without loss.
- **Total.** About 13 days for phase 0 (was 18) and 36 for phases 1 to 4 (was 57).

## Risks / Trade-offs

- **Wrong inference.** A role inferred wrongly gives wrong findings. This is mitigated by:
  - confidence;
  - the cap at `warning` for unconfirmed roles;
  - `roles.ambiguous`;
  - the user's classes;
  - the six reference variants as a gate.

  Libraries with unusual pin names give `low` results, which fall back to `signal`.
- **Defaults read as rules.** A warning against a heuristic can be taken as a requirement. Each finding
  therefore names its limit's key, source and label, and `docs/roles.md` says which defaults are
  heuristics.
- **The rule of thumb is lenient at high current** (decision 7). The reply states the method, and above
  1 A it asks for a temperature rise.
- **Loop area is c0213's plan area.** A leg through a pour is c0204's chain of straight steps between
  anchors, a lower bound of the current's path; a return run under its outgoing path on the next layer
  encloses almost no plan area, so a stacked gate loop reads small (its true area is its length times the
  layer distance, also small). The shoelace sum lets the two lobes of a figure-eight cancel, as their
  fluxes do. The bound ratio compares like with like, so the bias cancels in part. A field solve is out of
  scope; a stacked area, if the reference boards show it is needed, goes to `analysis` by its own change.
- **Near switching misses square crossings of tracks.** Returns see switching fills on a neighbouring
  layer and coupling sees parallel tracks; a track of a switch node crossing a victim at a right angle on
  the next layer adds about its width, which is below what the check can tell anyway.
- **Stale fills.** The analyses name the copper state of each row; a stale fill is simulated (c0204), and
  a leg of a loop does not walk a simulated pour. The reply says which state each row used.
- **No creepage defaults.** Users of mains boards must enter their own rows. This is deliberate. If a
  freely licensed public table is found, it becomes a later change.
- **Scope of later phases.** A general router is a large project. The plan keeps an external router for
  the rest until phase 3 proves itself on the reference boards.

## Open Questions

1. Where do the roles of a board not built by Fenolite live? **Recommended:** a companion
   `<stem>.roles.json` beside the board, with `--roles FILE` for another place. The board file stays
   untouched.
2. Are inferred roles that the user has not confirmed checked? **Recommended:** yes, at most as warnings,
   with one `roles.unconfirmed` info. A board routed by hand gets value without a confirmation step first.
3. Which current method is the default? **Recommended:** the rule of thumb of S-0851 when no temperature
   rise is given, the fit of S-0269 when one is. Fenolite ships no default rise.
4. Is `roles.rules` a default stage of `check`? **Recommended:** yes, skipped with `no-roles` when the board
   has no stored or declared role, so existing results do not change.
5. Should the high-voltage kind be inferred from net names (`VBUS`, `HV`, `L`, `N`)? **Recommended:** no.
   Only a `working_mv` makes a net high voltage, because a guess about safety distances is worse than none.
6. How is confidence written? **Recommended:** the three words `high`, `medium` and `low`, not a number. A
   rule's strength is a category, and a number would suggest a precision that it does not have.
7. Should phase 3's router be pure Python? **Recommended:** yes at first, measured on the reference boards.
   A native accelerator, if it is ever needed, goes to an optional extra, since the core keeps no runtime
   dependency.

### Decided by the maintainer on 2026-10-28

- Questions 1 to 7: every recommended answer accepted.
- Default limits: shipped only for the role checks, each with its source, never above a warning; the
  user's own limits on confirmed roles are errors. `analyze` keeps shipping none (the exception to the
  rule of c0175 is limited to `roles.rules`).
- Creepage and clearance: no table ships; each project declares its distance rows per working voltage, and
  a high-voltage net without them gives the warning of a missing requirement.
- Order of the phases after this change: 1 (polygons), 2 (critical routes), 4 (propose and lock, with
  Freerouting or KiCadRoutingTools for the remaining nets), then 3 (Fenolite's own A* router).

### Revised on 2026-10-29 after commit 1559f1b0

The branch was rebased from `dffa5852` onto `1559f1b0`, which landed c0204, c0205, c0206, c0208 to c0214
and c0223 to c0229. Much of what the first draft measured itself now exists in `analysis`, and much of
what phases 1 to 3 planned now exists as generated copper, the octilinear router, the DRC gate and tidy.
Every decision of 2026-10-28 above stands unchanged. What changed:

- **Phase 0 measures through the analyses** (decision 8). The draft's own copper path between pads (a
  visibility graph inside fills), its loop area (non-zero winding plus a stacked area) and its own current,
  section, via and distance measures are removed. Loops are c0213's `loops`; currents are c0175's power
  paths with c0213's split and necks; near switching is the distance, return and coupling analyses; return
  gaps are c0202's; separate sense nets use c0198's sense check. Roles say which loops, paths and nets are
  measured, and `roles.rules` judges the rows against the role limits.
- **What stays new:** the roles, groups and their sources; inference and confirmation; the role profile and
  severities decided on 2026-10-28; the placement bound and ratio; the Kelvin attachment on the pad's inner
  half and the gate-return attachment; the gate loop's pairing of its out and return nets; the reference
  boards.
- **Codes and hypotheses.** `roles.input-missing` and the hypothesis of the draft's own loop area are removed (17 codes, six
  hypotheses). Requirements "Copper path between pads" and "Loop area" are replaced by "Role measures come
  from the analyses" and "Role loops".
- **Layering.** The draft put a check stage over code that reads `analysis`, which `package-layering`
  forbids for `checks`. `roles` becomes a package with its own row (`roles` → `model`, `geometry`,
  `backends.base`, `analysis`), and the stage takes the judge from `cmd_check`, as it takes the plotter.
  This adds a MODIFIED delta of "Allowed import edges".
- **"No shipped requirement values"** is now MODIFIED from its full living text (the draft had shortened it).
- **Plan.** Phase 1 builds on c0224, phase 2 on c0228 with c0225/c0209, phase 4 on c0211, c0199 and
  c0208/c0214, and phase 3 shrinks to the search, the cost fields and negotiated rip-up that c0228 lacks.
  Sizes: phase 0 18 → 13, phase 1 10 → 5, phase 2 12 → 6, phase 4 10 → 7, phase 3 25 → 18; the cut order
  0 → 1 → 2 → 4 → 3 stands.

| area | what `dev` already gives | what c0222 adds |
|---|---|---|
| loop areas | c0213 `loops` (`[[loop]]` rows, legs along copper or straight, shoelace area) | the loops themselves (hot, gate, Kelvin) from roles; bound, ratio and role limits |
| current | c0175 power paths (sections, via groups, fit), c0213 split and necks, S-0269 fit | which nets and paths, the role's current, the rule of thumb and via count, role severities |
| near switching | distances per layer, c0202 returns with `reference`, c0204 coupling screen | which nets are victims and aggressors; the distance limit |
| ground gaps | c0202 return spans | which nets; `roles.return-gap` |
| sense nets | c0198 sense check (own sense nets) | Kelvin attachment on the pad's inner half; branches of a two-pad shunt; force pads |
| gate loops | — | gate-return attachment; out and return judged as one pair |
| high voltage | distances, creepage, grooves, user rows | which nets; `roles.limit-missing` |
| power copper | c0224 `band`, `stitch_pieces`, `fanout_zone`, `barrier` | phase 1: roles to those calls |
| critical routes | c0228 octilinear, c0225/c0209 DRC gate | phase 2: role order, gate pairs, Kelvin entries, `role_check` |
| finishing and review | c0208/c0214 tidy, c0211 region renders, c0199 crossings, copper locks | phase 4: propose and lock |
| general routing | c0228 five shapes and rounds; external routers | phase 3: multi-layer search, role cost fields, negotiated rip-up |

**Open for the maintainer (2026-10-29).**

8. May `fenolite.roles` be a new package that imports `analysis`, with the check stage taking its judge from
   `cmd_check`? **Recommended:** yes. The alternative, the stage inside `analysis`, would put a check stage
   and a write of the role document in a package whose functions are pure.
9. May the loop area be c0213's plan area (shoelace, legs through pours as c0204's lower bound), instead of
   the draft's non-zero winding area with a stacked term? **Recommended:** yes for phase 0; a stacked area
   goes to `analysis` by its own change only if the half-bridge variants show that the plan area cannot
   tell the good gate loop from the bad one.
