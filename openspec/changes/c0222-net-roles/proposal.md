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

A router cannot use roles that nobody has stated, and a role is only worth stating when Fenolite can check
it. This change is phase 0 of that router. It adds net roles to the model, infers them from the parts and
the topology for the user to confirm, and checks a board against them. This is useful at once, even on
boards routed by hand, with findings such as:

- "hot loop of 180 mm²";
- "the Kelvin sense of R12 does not start at the inner edge of its pad";
- "a 0.3 mm track on a 2 A net".

`design.md` lays out phases 1 to 4 as the plan: power and ground polygons, deterministic critical routes,
a cost-field multi-layer router with rip-up and reroute, and the propose-and-lock loop. The tasks of this
change implement phase 0 only.

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
  `design.net_role(...)`, `design.hot_loop(...)`, `design.kelvin(...)`, `design.gate_loop(...)` and
  `design.role_limits(...)`.
- **Phase-0 checks**, run by `fenolite roles PATH --check` and by a new stage `roles.rules` of
  `fenolite check`:
  - the area of the hot loop and of the gate loop, against the placement bound and the user's limit;
  - the Kelvin topology: the sense branch starts on the inner half of the shunt pad, touches no power
    copper, and runs as a pair;
  - the current capacity of tracks, of the narrowest section of pours, and of the vias at each layer change
    on the path of a power role;
  - sense and gate copper near switching copper;
  - return gaps under gate and signal nets;
  - high-voltage nets with no distance requirement.
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
  the phase-0 checks and their codes, and the reference boards.

### Modified Capabilities

- `design-model`: ADDED "Net roles in the model".
- `design-dsl`: ADDED "Net roles in the DSL".
- `cli-contract`: ADDED "Roles command".
- `verification-loop`: ADDED "Roles stage".
- `board-analyses`: MODIFIED "No shipped requirement values". `analyze` still ships no value; the role
  profile is the one stated exception, and it never feeds `analyze`.

## Non-goals

- No routing in this change. Phases 1 to 4 are a plan in `design.md`, each to be its own change.
- No field solver, inductance value or EMI prediction. A loop area is geometry, not henries.
- No compliance verdict. No creepage or clearance values, and no tables or figures taken from IPC-2152,
  IPC-2221, IEC 60664 or any other paid standard.
- No code from third-party routers. Freerouting, KiCadRoutingTools and published routing algorithms are
  cited only as prior art.
- No design, value, footprint or name from an employer or any organisation. The reference boards are
  authored for Fenolite.

## Evidence level required

- Inference and checks: `INFERRED`, with the hypotheses of `design.md` measured on the six reference
  variants.
- Every default limit carries its own label: `INFERRED` with a public source, or `INFERRED` as a Fenolite
  heuristic with a hypothesis.
- Role documents written for KiCad boards: `KICAD-VERIFIED` that DRC finds nothing new on the board. The
  board itself is not written.

## Impact

- New: `src/fenolite/roles/` (`model.py`, `classify.py`, `infer.py`, `profile.py`, `measure.py`,
  `checks.py`, `codes.py`, `store.py`), `src/fenolite/cli/cmd_roles.py`, `src/fenolite/checks/roles.py`
  (the stage), `examples/roles/` (three boards, two variants each), authored CC0 footprints and symbols
  in `tests/data/libs`, `docs/roles.md`.
- Changed: `model/rules.py` (`RuleSet.roles`), `dsl/design.py`, `checks/stages.py`, `explain.toml`,
  `docs/dsl.md`, `docs/design-model.md`, `docs/cli-contract.md`, `docs/analyses.md`, the guide pages
  `board-power`, `board-grounds`, `board-insulation` and `checks`, `CHANGELOG.md`.
- Sources: S-0850 to S-0854 registered by this proposal. S-0269 (the capacity fit) and S-0720 (stack-up
  presets) are reused.
- Size: phase 0 is about 18 design-days. Phases 1 to 4 are about 57 more (see `design.md`).
