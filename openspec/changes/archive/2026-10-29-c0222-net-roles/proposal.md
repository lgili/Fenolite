## Why

The maintainer's request of 2026-10-28. None of the routers the maintainer tried works on the maintainer's
boards: they do not finish, their result is untidy or unusable, and they ignore power. They draw thin tracks
where a polygon is needed, leave a large hot loop, and take a Kelvin sense from the wrong place. The boards
are motor drives and inverters, switch-mode supplies (buck, boost, flyback), chargers and BMS, and
mixed-signal control: typically 2 to 4 layers and up to about 150 parts. Currents and voltages vary widely,
from tens of amperes at low voltage to mains and high DC buses, so creepage matters on some of them.

The vision is a router that works from electrical intent. Each net has a role, and the role says how its
copper is made and in which order:

- **power:** a polygon, with a width from its current;
- **switching node and hot loop:** shortest, smallest loop, routed first;
- **ground:** a plane or pour, with the return path under the outgoing path;
- **shunt or Kelvin sense:** from the inner edges of the shunt pads, as a coupled pair to the amplifier,
  away from switching copper;
- **gate drive:** outgoing path and return together, smallest loop;
- **ordinary signal:** routed last, by a cost-field search;
- **high voltage:** creepage and clearance.

Since commit `1559f1b0`, `dev` measures most of this: loop areas (c0213 `analyze --kinds loops`), power
paths with their sections, vias, current split and necks (c0175, c0213), distances, return paths (c0202),
the coupling screen (c0204) and sense nets (c0198). It can also generate power copper (c0224), route short
critical connections (c0228 `route --router octilinear`), gate an edit by KiCad's DRC (c0225, c0209) and
tidy copper (c0208, c0214). What none of it knows is the intent of a net: the user must write each loop,
path and net pair by hand. A router cannot use roles that nobody has stated, and a role is only worth
stating when Fenolite can check it.

This change is phase 0 of that router. It adds net roles to the model, infers them from the parts and
the topology for the user to confirm, and checks a board against them by feeding the roles to the analyses
of `dev` and judging their results against role limits. This is useful at once, even on boards routed by
hand, with findings such as:

- "hot loop of 180 mm²";
- "the Kelvin sense of R12 does not start at the inner edge of its pad";
- "a 0.3 mm track on a 2 A net".

`design.md` lays out phases 1 to 4 as the plan, rebuilt on what `dev` now has: power and ground copper
from roles through c0224's generated copper, deterministic critical routes through c0228's octilinear
router and the DRC gate, the propose-and-lock loop with tidy and region renders, and last a multi-layer
search with role cost fields and rip-up. The tasks of this change implement phase 0 only.

## What Changes

- **Roles in the model.** Seven role kinds: `power`, `switch_node`, `ground`, `kelvin`, `gate`, `signal`
  and `high_voltage`. There are three role groups that tie pads of several nets together: a hot loop, a
  Kelvin pair and a gate loop. Each role and each group records its source: `inferred`, `confirmed` or
  `declared`. Roles are stored in `rules.json` under a new optional key, and in a companion role document
  beside a board that Fenolite did not build. Both backends use them, KiCad and Altium alike, because the
  roles live in the model.
- **Inference.** A closed table of deterministic rules infers roles from part classes (transistor,
  inductor, shunt, capacitor, driver, amplifier) and from the circuit's topology. For example, a MOSFET
  drain or source joined to an inductor gives a switching node. A low-value resistor whose two nets reach
  an amplifier's inputs gives a Kelvin pair. Each inferred role names its rule and the pads that fired it,
  with a confidence of `high`, `medium` or `low`.
- **Confirmation.** `fenolite roles PATH` shows the stored and inferred roles. `--accept`, `--reject` and
  `--set` choose roles, and the role document is written only through the reviewed-plan protocol
  (`--dry-run`, then `--confirm --plan ID`). A design script declares or overrides roles with
  `design.net_role(...)`, `design.hot_loop(...)`, `design.kelvin(...)`, `design.gate_loop(...)`,
  `design.role_limits(...)` and `design.part_class(...)`.
- **Phase-0 checks**, run by `fenolite roles PATH --check` and by a new stage `roles.rules` of
  `fenolite check`. Each measure comes from an analysis of `dev`; the roles choose what it measures:
  - the area of the hot loop, the gate loop and the Kelvin pair: c0213's loop areas, from loop rows the
    roles derive, against the placement bound (new) and the user's limit;
  - the current capacity of tracks, pour sections and necks, and vias on the path of a power role:
    c0175's power paths with c0213's split and necks, judged by the S-0269 fit when the user gives a rise
    and by the public rule of thumb otherwise;
  - sense, gate and sensitive copper near switching copper: the distance, return and coupling analyses;
  - return gaps under gate and sensitive nets: c0202's return spans;
  - high-voltage nets with no distance requirement;
  - new measures: the Kelvin topology (the sense branch starts on the inner half of the shunt pad and
    touches no power copper) and the gate return taken from the source pad, not from power copper.
- **Default limits from public sources.** A role profile holds the default limits. Each value names its
  source and its evidence label, and the user overrides any of them per project. A finding against a
  default limit is at most a `warning`. Fenolite ships no creepage or clearance table and no default
  temperature rise: no freely usable source of such a table was found, and the paid standards are not
  copied.
- **Three reference boards** authored for Fenolite: a buck with a current shunt, a half-bridge with a gate
  driver and Kelvin sense, and a simple BMS. Each has a deliberately good and a deliberately bad variant,
  and the tests measure the findings on all six.

## Capabilities

### New Capabilities

- `net-roles`: role kinds and groups, storage, inference with confidence, confirmation, the role profile,
  the role measures taken from the analyses, the new Kelvin and gate-return measures, the phase-0 codes,
  and the reference boards.

### Modified Capabilities

- `design-model`: ADDED "Net roles in the model".
- `design-dsl`: ADDED "Net roles in the DSL".
- `cli-contract`: ADDED "Roles command".
- `verification-loop`: ADDED "Roles stage".
- `board-analyses`: MODIFIED "No shipped requirement values". `analyze` still ships no value; the role
  profile is the one stated exception, lives outside `analysis`, and is never read by `analyze`.
- `package-layering`: MODIFIED "Allowed import edges", adding the package `roles`, which may import
  `analysis`.

## Non-goals

- No routing in this change. Phases 1 to 4 are a plan in `design.md`, each to be its own change.
- No new measuring kernel: loop areas, sections, current split, necks, distances and return spans are the
  analyses of `dev`.
- No field solver, inductance value or EMI prediction. A loop area is geometry, not henries.
- No compliance verdict. No creepage or clearance values, and no tables or figures taken from IPC-2152,
  IPC-2221, IEC 60664 or any other paid standard.
- No code from third-party routers. Freerouting, KiCadRoutingTools and published routing algorithms are
  cited only as prior art.
- No design, value, footprint or name from an employer or any organisation. The reference boards are
  authored for Fenolite.

## Evidence level required

- Inference and checks: `INFERRED`, with the hypotheses of `design.md` measured on the six reference
  variants, combined with the evidence of the analyses that measured each row.
- Every default limit carries its own label: `INFERRED` with a public source, or `INFERRED` as a Fenolite
  heuristic with a hypothesis.
- Role documents written for KiCad boards: `KICAD-VERIFIED` that DRC finds nothing new on the board. The
  board itself is not written.

## Impact

- New: `src/fenolite/roles/` (`model.py`, `classify.py`, `infer.py`, `profile.py`, `measure.py` (the
  adapters to the analyses), `kelvin.py` (the attachment and gate-return measures), `checks.py`,
  `codes.py`, `store.py`, `judge.py`), `src/fenolite/cli/cmd_roles.py`, `src/fenolite/checks/roles.py`
  (the stage and its `RolesJudge` protocol), `examples/roles/` (three boards, two variants each), authored
  CC0 footprints and symbols in `tests/data/libs`, `docs/roles.md`.
- Changed: `model/rules.py` (`RuleSet.roles`), `dsl/design.py`, `checks/stages.py`, `checks/documents.py`,
  `cli/cmd_check.py`, the import-graph test (`roles` row), `explain.toml`, `docs/dsl.md`,
  `docs/design-model.md`, `docs/cli-contract.md`, `docs/analyses.md`, the guide pages `board-power`,
  `board-grounds`, `board-insulation` and `checks`, `CHANGELOG.md`. `analysis` is not changed.
- Sources: S-0850 to S-0854 registered by this proposal. S-0269 (the capacity fit) and S-0720 (stack-up
  presets) are reused.
- Size: phase 0 is about 13 design-days (18 before the revision of 2026-10-29). Phases 1 to 4 are about 36
  more (57 before; see `design.md`).
