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
