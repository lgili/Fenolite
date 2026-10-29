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
- **What exists on `dev`** (base `dffa5852`):
  - **Model.**
    - Net classes with widths, clearances and pair values (`model/circuit.py`).
    - `RuleSet` with rules, check severities, proximity rules (c0113), height limits (c0140) and
      impedance targets (c0105). Each optional key is left out of `rules.json` when it is empty.
    - Differential pairs as `Interface`s (`model/pairs.py`).
  - **Analyses** (`analysis/`, `fenolite analyze`):
    - the capacity fit of S-0269 for tracks, arcs and vias (`current.py`);
    - power paths with their narrowest section (`power.py`, `section.py`, `network.py`);
    - clearance, creepage (with grooves) and insulation;
    - lengths;
    - ties and sense nets (c0198), crossings (c0199) and return paths (c0202);
    - the per-net copper shapes `net_copper` (`copper.py`) and the fills `fill_regions` (`fills.py`).
    - `analyze` judges only against the user's TOML requirements file (`fenolite.requirements.v0`:
      `[[current]]`, `[[distance]]`, `[[step]]`, `[[path]]`), and the requirement "No shipped requirement
      values" forbids defaults.
  - **Checks.** The copper check (`checks/copper.py`, `checks/clearance.py`). The stages of
    `fenolite check` in `checks/stages.py`, which a change may extend.
  - **Placement.** `place`, constrained placement (c0096), and proximity and height rules.
  - **Routing.**
    - The plugin protocol, with `direct`, `freerouting` (GPL, run as a subprocess) and
      KiCadRoutingTools.
    - Tiers, a time budget, and plane fan-out.
    - Specctra fidelity (c0197).
    - c0175 proposes an octilinear plugin for short critical connections (package 5) and generated copper
      (package 6: bands, fan-out, stitching).
  - **Guide and protocols.** The agent guide with its coverage rule (AGENTS.md rule 6), the MCP server
    (one tool per public command, c0195), and the reviewed-plan write protocol.
- **What fails in use.** The routers the maintainer tried treat every net alike:
  - a 20 A path gets the class width;
  - the input capacitor of a buck ends up 15 mm from the switches;
  - a sense amplifier's inputs are joined to the nearest point of the shunt's pour;
  - a gate trace goes one way and its return another.

  None of these is a DRC error, so no check sees them.

## Goals / Non-Goals

**Goals**

- Every net of a board has a role, stated by the user or inferred with a reason, and the user can see and
  confirm it in one command.
- On a board routed by hand, `fenolite check` reports the power-electronics faults that DRC does not see,
  with a number, a place and the limit used, and says where the limit came from.
- The same roles and checks work on a KiCad board and on an Altium board, through the model.
- Phase 0 leaves the router of phases 1 to 4 a stable input: the roles, the groups and the limits.

**Non-Goals**

- See the proposal. In addition:
  - no automatic placement;
  - no change of copper by a role check;
  - no inductance or EMI number;
  - no role for a part, only for nets and groups of pads.

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
  two parts is joined by the copper of their shared net.
- **`KelvinPair(name, element, receiver)`.** `element` names the two sense pads of the shunt (for a
  two-terminal shunt, its two pads; for a four-terminal shunt, its two sense pads, with the force pads in
  `force`). `receiver` names the two amplifier inputs. The two sense branches may be nets of their own,
  or branches of the power nets when the shunt has two pads.
- **`GateLoop(name, drive, gate, source, ret)`.** The driver output pad, the switch's gate pad, the
  switch's source pad (its Kelvin-source pad when the package has one), and the driver's return pad. An
  optional `resistor` names the gate resistor's two pads, and the loop runs through it.

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
`high`.

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

The maintainer's decision of 2026-10-28 departs, for role checks only, from the rule that every limit comes from the user (requirement "No shipped requirement values"; c0175, "Non-goals"). `analyze` keeps that rule. The defaults live in `src/fenolite/roles/profile.py` as constants. Each constant names its source id and
label, and `docs/roles.md`, "Default limits", lists them. The table below is the whole default profile.

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
    the fit is used, with the stack-up's thickness. Otherwise the rule of thumb is used.
  - Each row names the method it used. A row judged by the rule of thumb above 1 A also gets the hint to
    give a rise.
- **Overrides.** `design.role_limits(key=value, net=..., kind=...)` in a script, or `limits` in the role
  document, override a key for the whole design, for one kind or for one net. The most specific wins.
- **Severity.** A finding against a default limit is a `warning`. It becomes an `error` when two
  conditions hold: the limit is the user's (an override, or the requirements file), and the role is
  `confirmed` or `declared`. Topological checks (the Kelvin and gate-return attachments) are an `error`
  on a confirmed role, because S-0850 and S-0852 state them as rules, not as numbers. Every check on an
  unconfirmed inferred role is at most a `warning`.

### 8. Measuring on the model

All measures read the `Design` that a backend gives, so KiCad and Altium boards are measured by the same
code. They reuse:

- `analysis.copper.net_copper` (shapes per net and layer, fills included);
- `analysis.fills.fill_regions`;
- `analysis.section.narrowest_section`;
- `analysis.network.path_network`;
- the crossing and return machinery of c0199 and c0202.

- **Copper path between two pads.** In a net's copper graph:
  - **Nodes:** pads, track and arc ends, vias, and fill regions.
  - **Edges, with their lengths:**
    - a track: its centre line;
    - an arc: its chord polyline at `--arc-tol`;
    - a via: zero plan length, plus a layer change;
    - a fill region: the shortest path inside the region's ring between its two touch points, over the
      visibility graph of the ring's vertices with integer coordinates.
  - The path is the shortest by plan length, with ties broken by item id.
  - When no path exists, the measure is `null` and the issue is `roles.loop-open` (warning): the board is
    not routed there.
- **Loop area** (hot loop, gate loop, Kelvin pair).
  - **The closed path:** the copper paths between consecutive pads of the group, closed by the straight
    chord between two pads of one part (the part's own path).
  - **Plan area:** `enclosed_nm2`, the area where the closed path's winding number is not zero. It is
    computed with the geometry kernel's boolean on the path as a polygon under the non-zero rule, so a
    figure-eight is counted, not cancelled. `signed_nm2`, the absolute shoelace sum, is reported beside
    it.
  - **Stacked area:** where the outgoing and the return paths run on different layers over each other,
    within half the wider width in plan, `stacked_nm2` adds the overlap length times the distance between
    the two layers from the stack-up. Without stack-up depths, `stacked_nm2` is `null` and
    `roles.input-missing` names `stack-up`.
  - **Total:** `area_nm2 = enclosed_nm2 + stacked_nm2`.
  - **Placement bound:** `bound_nm2`, the enclosed area of the polygon through the pad centres in loop
    order. It is what placement alone fixes.
  - **Ratio:** `ratio_permille = area * 1000 // bound` when the bound is at least `loop_bound_floor_nm2`.
- **Kelvin attachment.** For each sense pad `P` of a `KelvinPair`:
  1. The **power copper** of `P`'s net is the union of the items on the copper paths from `P`'s part to
     the other power pads of that net, as the path network gives them.
  2. The **sense branch** is the connected copper reached from the receiver pad without crossing `P`'s pad
     shape and without entering power copper. A net tie (class `net_tie`) ends the branch at its pad.
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
- **Kelvin pair.** `area_nm2` of the loop element, branch `+`, receiver, branch `-`, with its bound and
  ratio as above, judged by `pair_ratio_max`. `roles.kelvin-apart` is a warning, and the reply gives the
  largest gap between the two branches.
- **Near switching.** For each `kelvin` branch, each `gate` loop of another switch and each `signal` with
  `sensitive`:
  - the least plan distance from its copper to `switch_node` copper on the same layer;
  - the overlap length over `switch_node` copper on an adjacent layer.

  A distance under `switching_distance_nm`, or any overlap, is `roles.near-switching` (warning). The
  gate loop of a switch is not judged against its own switch node.
- **Current capacity**, for each `power`, `switch_node` and `ground` net with `milliamps`, along the path
  network between the pads that the role or a `[[path]]` row names (default: every pad of the net's
  transistors, inductors, shunts and connectors):
  - **Tracks and arcs on the path:** the width against the required width. That is `width_per_amp_nm`
    times the current, or the width the fit gives at the user's rise and the layer's thickness.
    `roles.width-current` names the item, its width, the required width and the method.
  - **Pours:** the narrowest section of the net's copper on the path (`narrowest_section`), compared the
    same way, giving `roles.section-current`.
  - **Vias:** at each layer change of the path, the vias of the net that join the same two copper regions
    there count as parallel. Their number is compared with `ceil(milliamps / milliamps_per_via)`, or
    their summed capacity with the fit, giving `roles.via-current`.
  - A role without `milliamps` gets `roles.current-missing` (info), and its current is not judged.
- **Returns.** For `gate` and `sensitive` `signal` nets, `analysis.returns.analyze_returns` runs with the
  `ground` nets as reference. Each `split` span becomes `roles.return-gap` (warning), with the span.
- **High voltage.** For each `high_voltage` net, and each `power` net whose `working_mv` is at or above
  `high_voltage_mv`, the distances to every other net come from `analysis` (clearance and creepage, with
  grooves), against the user's rows. Their findings keep their `analysis.*` codes. Without a row, the
  issue is `roles.limit-missing`.

### 9. Issue codes and severities

The closed table `fenolite.roles.codes.ISSUE_CODES` follows the pattern of `analysis/codes.py`.
`fenolite explain` gains each code. No `FEN-` code is added:

- a bad option is `FEN-2001`;
- an unreadable or malformed role document is `FEN-3004`;
- a write uses `FEN-4001` and `FEN-4002`;
- an error finding gives `FEN-5001`, exit 5.

| code | severities | meaning |
|---|---|---|
| `roles.loop-area` | warning, error | a hot loop over the user's `loop_max_nm2`, or over the bound ratio |
| `roles.loop-open` | warning | a loop or a sense branch has no copper path |
| `roles.gate-loop` | warning, error | a gate loop over its limit or ratio |
| `roles.gate-return-shared` | warning, error | the gate return leaves from the power source copper, not from the source or Kelvin-source pad |
| `roles.kelvin-outer` | warning, error | the sense branch attaches on the outer half of the pad |
| `roles.kelvin-shared` | warning, error | the sense branch shares power copper or a force pad |
| `roles.kelvin-apart` | warning | the two sense branches enclose more than the ratio |
| `roles.near-switching` | warning | sense, gate or sensitive copper too near switching copper |
| `roles.width-current` | warning, error | a track or arc narrower than its current needs |
| `roles.section-current` | warning, error | the narrowest section of a pour is too narrow |
| `roles.via-current` | warning, error | too few vias at a layer change |
| `roles.return-gap` | warning | a gate or sensitive net crosses a gap of its ground |
| `roles.limit-missing` | warning | a high-voltage net without a distance requirement |
| `roles.current-missing` | info | a role without a current |
| `roles.input-missing` | warning | a measure needs an input the board lacks (stack-up depths) |
| `roles.ambiguous` | warning | two rules give different kinds at one confidence |
| `roles.unconfirmed` | info | the count of inferred roles not confirmed |
| `roles.declared-differs` | info | a script's role differs from a stored or inferred one |

### 10. Command line, check stage, MCP and guide

- **`fenolite roles PATH`.** `PATH` is a board, or a built project folder, that a registered backend
  reads. Options: `[--roles FILE] [--requirements FILE] [--net GLOB]... [--kinds KIND,...]
  [--class REF=CLASS]... [--check] [--temp-rise KELVIN] [--current NET=AMPS]... [--accept NET[,NET...]]...
  [--accept-all] [--min-confidence high|medium] [--set NET=KIND[:KEY=N]...]... [--reject NET]...
  [--accept-group NAME]... [--reject-group NAME]... [--dry-run | --confirm [--plan ID]]`.
  - Schema `fenolite.roles.v0`.
  - Without an accept, set or reject option, the command is read-only. With one, it is a writing command
    of the mutation protocol, and it writes only the role document.
  - `result` holds `roles`, `loops`, `kelvins` and `gates`; with `--check`, also `measures` and `summary`.
- **`fenolite check`.** A stage `roles.rules`, standing after `placement.rules` and before `zone.fill` in
  `STAGE_ORDER`, and after `placement.rules` in the document pipeline:
  - a default stage that runs no tool;
  - it reads the stored roles (`rules.json` or the companion document) and the inferred ones;
  - it judges them as decision 7 says;
  - it is skipped with the reason `no-roles` when the board has no stored or declared role, so existing
    boards keep their result.
- **MCP.** The server makes a tool of each public command, so `roles` is served as `fenolite_roles`. Its
  writes follow the plan protocol, as every writing tool's do.
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

- The calls record plain data, as the copper intents do. The build resolves pads after placement and
  writes `RuleSet.roles` with source `declared`.
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
cell-monitor IC). Every value is a round illustrative number, marked as such.

| board | layers | parts | good variant | bad variant (designed faults) |
|---|---|---|---|---|
| `buck_shunt` | 2 | about 25 | input capacitor across the switch pair; switch node a compact pour; output shunt sensed from the inner pad edges as a pair; power copper as pours | input capacitor 15 mm away (hot loop about 180 mm²); sense lines from the outer ends of the shunt pads, one from the pour; a 0.3 mm track on the 2 A output path |
| `half_bridge` | 4 | about 40 | gate out on layer 1 and return on layer 2 under it, from the Kelvin-source pad; low-side shunt with a coupled sense pair; DC bus `working_mv` 400 000 with the user's distance rows | gate return from the source pour; gate loop over three times its bound; sense pair crossing the switch node on the adjacent layer; one bus via where the rule of thumb needs five |
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
| `H-G-ROLE-LOOP-AREA` | The loop area of decision 8 equals the area of an authored loop of known geometry | `tests/unit/roles/test_loop_area.py` | a 10 mm × 5 mm rectangular loop of tracks gives 50 mm² exactly; a figure-eight gives the sum of its two lobes; a loop stacked over 20 mm at 0.2 mm adds 4 mm² |
| `H-G-ROLE-LOOP-RATIO` | A ratio of twice the placement bound separates the good and the bad hot and gate loops of the reference boards | `tests/unit/roles/test_reference_boards.py -k loop` | every good loop is at or under 2000 per-mille, and every designed bad loop is over it |
| `H-G-ROLE-KELVIN-EDGE` | The attachment offset of decision 8 tells an inner-edge sense connection from an outer one and from one taken off the pour | `tests/unit/roles/test_kelvin.py` | on authored pads, inner attachments give `t ≥ 0`, outer ones `t < 0`, and a branch from the pour gives `roles.kelvin-shared` |
| `H-G-ROLE-KELVIN-PAIR` | A pair ratio of twice the bound separates a coupled sense pair from a split one on the reference boards | `tests/unit/roles/test_reference_boards.py -k kelvin` | good pairs at or under 2000 per-mille, bad pairs over it |
| `H-G-ROLE-NEAR-SW` | One millimetre on a layer and no overlap on an adjacent layer flag the designed crossings and nothing on the good variants | `tests/unit/roles/test_reference_boards.py -k switching` | exactly the designed `roles.near-switching` findings |
| `H-G-ROLE-CURRENT` | The width, section and via checks find the designed narrow copper and the single via, by both methods | `tests/unit/roles/test_current.py` | the 0.3 mm track at 2 A fails both methods, a 1 mm track passes the rule of thumb, and the via count matches `ceil(I / 200 mA)` |

## Evidence level per behaviour

| behaviour | level | proof |
|---|---|---|
| role model, storage, round trip | `INFERRED` until a release; the write is plain canonical JSON | `tests/unit/model/test_rules.py -k roles` |
| inference | `INFERRED` (`H-G-ROLE-INFER`) | the reference boards |
| measures | `INFERRED` (the hypotheses above) | authored geometry and the reference boards |
| default limits | `INFERRED`, each with its source or hypothesis | `docs/roles.md`, "Default limits" |
| KiCad reference boards | `KICAD-VERIFIED` that DRC finds nothing on the good variants | `tests/kicad/roles/test_reference_drc.py` |

## Plan of phases 1 to 4

Each phase becomes its own change with the next free id when its turn comes. Sizes are design-days, as in
`docs/roadmap.md`.

| phase | what | builds on | size |
|---|---|---|---|
| 1. Power and ground copper | generate zones from roles: a `power` net's polygon from its pads, grown to the width its current needs; `ground` planes on the reference layers; stitching and fan-out by current; refill and check | c0175 package 6 (bands, fan-out, stitching), phase 0 | 10 |
| 2. Deterministic critical routes | in order, hot loops (copper between the loop pads on the layer nearest the plane, with a check of the area against the bound), switch-node copper, gate loops (out and return on adjacent layers or side by side), Kelvin pairs from the inner pad edges; each route accepted only if the phase-0 checks and the copper check find nothing new | c0175 package 5 (octilinear plugin), phase 0 | 12 |
| 3. Cost-field router | Fenolite's own multi-layer A* on a grid with 45° moves, with cost fields from the roles (repelled by switching copper, drawn over ground, kept off high-voltage gaps) and negotiated congestion with rip-up and reroute. Written from published descriptions only (A*, PathFinder-style negotiation, Lee's maze routing), cited as prior art; no code of Freerouting or any other router | phases 0 to 2 | 25 |
| 4. Propose and lock | `fenolite route --router roles --propose` writes critical and power copper as locked, proposes the rest, and marks every unfinished connection with the reason (no way across, by c0199's crossings; a check failed); a region render for review; the user locks or rejects pieces and runs again. Until phase 3 lands, the rest can go to Freerouting or KiCadRoutingTools through the plugin protocol | phases 0 to 2, c0199, c0175 package 11 (region renders) | 10 |

- **Cut order.** 0, then 1, 2 and 4 with an external router for the rest, then 3 last. Phases 1 and 2 give
  the maintainer the deliverable (critical routes and power copper done) without Fenolite's own general
  router. Phase 3 is the largest and the riskiest, and it can stop at any time without loss.
- **Total.** About 18 days for phase 0 and 57 for phases 1 to 4.

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
- **Loop area on pours.** A shortest path inside a fill is a proxy for where the current flows. A field
  solve would be better and is out of scope. The bound ratio compares like with like, so the proxy's bias
  cancels in part.
- **Stale fills.** As with every analysis that reads fills, an Altium board whose pours are older than
  their outlines is measured on its old fill. The reply says so when the reader reports it.
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
