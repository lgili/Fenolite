## Context

`fenolite check` runs twelve stages, `fenolite net` gives the open connections of a board (c0108), and the model holds what a readiness question needs: net classes, rules, interfaces, pin types, no-connect marks, zones. Read on `origin/v04` at `04ef42a` (2026-10-08):

- `cli/cmd_check.run_stages(board, stages, *, kicad_cli, timeout, hint)` runs selected stages with the pre-flight of the oracle stages (`FEN-6001` and `FEN-6002`) and the refusal of an unreadable board; `fenolite manifest` already reuses it.
- `checks.stages.StageResult` carries `name`, `status`, `reason`, `evidence`, `summary` and its issues; its JSON is the entry of `result.stages` of `check`.
- `analysis.connectivity.connectivity(design, pads=…)` gives the open connections per net with `EVIDENCE` `KICAD-VERIFIED` (`H-K-CONN-PARITY`); `cli/_boardview.load_board` reads a board with its pads, as `net` does.
- The model names a power net in one way only: an `Interface` of kind `power` (the DSL's `Power`). `checks/erc_lite.py` and `backends/kicad/schgen.py` each compute that set. A pin type `power_in` or `power_out` (read from the symbol, or from a board pad's `pintype`) is the other mark the model holds.
- `checks/validate.validate_stage` reports `check.footprint-unresolved` for a fitted part with no footprint reference or no footprint instance; nothing reports an empty value.
- A board pad under a no-connect flag carries a `pintype` ending in `+no_connect` (`backends.kicad.netlist.NO_CONNECT_SUFFIX`); `read_board` keeps that text in the pin's `ext["kicad"]` because it is no `PinType`.
- A board built by Fenolite gives each pin on no net a net of its own, `unconnected-(…)`, in the written board only; the `.fenolite/` model leaves the pin on no net.

## Goals / Non-Goals

Goals: one read-only reply that says whether a KiCad project is electrically ready, from findings that exist, plus three rules the model can decide; the exit codes of contract v0; no logic copied.

Non-goals: see the proposal.

## Decisions

1. **Six checks, fixed order.** `nets.open`, `erc.kicad`, `drc.kicad`, `pins.unconnected`, `power.nets`, `parts.fields` (`checks.readiness.READY_CHECKS`). Each is a `StageResult`, so `result.checks` has the shape of `result.stages` of `check`, and an agent reads both alike.
2. **ERC and DRC through `run_stages`.** `ready` calls `run_stages(board, ("erc.kicad", "drc.kicad"), …)` and takes the two `StageResult`s and their issues as they are: waivers, stored exclusions, report limits and severities stay those of `check`. No other stage runs.
3. **A missing tool is exit 6**, as `check` does for a selected oracle stage: the pre-flight of `run_stages` raises `FEN-6001` or `FEN-6002`, and the hint of `ready` adds "or pass --no-kicad". Silently skipping would make `ready` exit 0 on a machine without KiCad for a board that KiCad rejects. `--no-kicad` is the explicit opt-out: the two checks are `skipped` with reason `no-kicad`, each gives one `ready.check-skipped` warning, and `result.complete` is false. A stage that `check` itself skips (no schematic: `no-schematic`) is reported the same way, with its own reason.
4. **Two designs.** The *board* is the board as read (`load_board`): copper, zones, pads. The *intent* is the `.fenolite/` model of a built project (`built_cache`), else the board as read with the classes and rules of the project files (`DesignRulesSource.design_rules`). Pins, no-connect marks, interfaces, net classes, rules, values and footprints come from the intent; open connections and zones from the board. Nets are matched by name. An unreadable `.fenolite/` gives `check.cache-unreadable` and the board's reading stands in.
5. **Unconnected pin.** A pin of a part that is not DNP, whose type is not `no_connect`, that no `Circuit.no_connects` entry marks and whose board pad is not flagged `+no_connect`, and that is on no net or alone on its net. "Alone" covers the `unconnected-(…)` nets of a board read. One `ready.pin-unconnected` per pin, `where` `REF-PIN`.
6. **Power net.** A net of an interface of kind `power` (`model.circuit.power_interface_nets`, shared with ERC lite and the schematic writer), or a net with a member pin of type `power_in` or `power_out`. Its source is reported (`interface` before `pin-type`).
7. **Declared width.** The power net's own class (not `Default`) has a `track_width`, or a `track_width` rule that is not `ignore` and whose `selector_a` is not `all` selects a track of the net (`RuleSubject("track", net, netclass)`). A board-wide minimum is not a declaration for the net. **Plane or zone:** a zone of the board on the net. A power net with neither gives `ready.power-net-unsized`.
8. **Part fields.** `checks.validate.unresolved_footprints(design)` is the rule of `model.validate`, moved; `validate_stage` and `ready` call it, so `check.footprint-unresolved` keeps its text and code. An empty value (after stripping) of a part that is not DNP gives `ready.part-value-missing`.
9. **Open nets.** One `ready.net-open` per net with open connections, its count and its shortest connection in the message; `result` lists no connections (`fenolite net BOARD NAME` does). The issues of the query (`analysis.item-unsupported`) are passed on.
10. **Severities and exit.** Every finding of the new rules is an `error`; `ready.check-skipped` is a `warning`. `result.ready` is true when no issue has severity `error`, so it equals exit 0. The dispatcher sets exit 5 from the errors.
11. **Evidence.** Each check carries its own. `nets.open`: the board read's combined with `connectivity.EVIDENCE`; the three rules: `checks.readiness.EVIDENCE` (`INFERRED`, `H-G-READY-RULES`); ERC and DRC: their stages'. The envelope is `Evidence.combine` of the checks that ran.
12. **The loop block stays ten lines.** `release-gate` caps it; the start page of the guide names `ready` in the prose of "The loop", after `check`, and the page `checks` holds its tested line.

## Result

```json
{"project": {"board": "blink.kicad_pcb", "built": false},
 "ready": true, "complete": true,
 "checks": [{"name": "nets.open", "status": "ok", "reason": "",
             "evidence": {"level": "INFERRED", "oracle": null, "hypotheses": ["…", "H-K-CONN-PARITY", "H-K-PCB-READ"]},
             "summary": {"nets": 0, "connections": 0}}, "…"],
 "counts": {"error": 0, "warning": 0, "info": 0}}
```

`summary` per check: `nets.open` `{nets, connections}`; `erc.kicad` and `drc.kicad` that of `check`; `pins.unconnected` `{pins}`; `power.nets` `{nets: [{net, source, width, zones}]}` with `width` `class:<name>`, `rule:<name>` or `null`; `parts.fields` `{footprint, value}`.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/checks/readiness.py` (new) | `READY_CHECKS`, `READY_ISSUE_CODES`, `EVIDENCE`, `issue(code, message, *, where)`, `OpenNet(name, connections, shortest, a, b)`, `open_stage(nets, *, evidence, issues)`, `unconnected_pins(design, *, flagged)`, `pins_stage(design, *, flagged)`, `PowerNet(net, source, width, zones)`, `power_nets(intent, *, board)`, `power_stage(intent, *, board)`, `parts_stage(design)`, `skipped_check(name, reason)` |
| `src/fenolite/checks/validate.py` | `unresolved_footprints(design) -> tuple[Component, ...]`, `footprint_issue(component)` |
| `src/fenolite/model/circuit.py` | `power_interface_nets(circuit) -> frozenset[str]`; used by `checks/erc_lite.py` and `backends/kicad/schgen.py` |
| `src/fenolite/cli/cmd_ready.py` (new) | the command; `--no-kicad`, `--kicad-cli`, `--timeout` |
| `src/fenolite/cli/explain.py`, `cli/data/explain.toml` | the table `checks.readiness.READY_ISSUE_CODES` and its five entries |
| `tests/unit/checks/test_readiness.py`, `tests/unit/cli/test_ready_cmd.py` (new) | the scenarios, with the fake `kicad-cli` of `tests/_fakecli.py` |
| `tests/data/kicad/ready/` (new, `MANIFEST.toml`) | the starter built and routed: board and schematic |
| `docs/cli-contract.md`, `src/fenolite/agent/skill/SKILL.md`, `references/checks.md`, the generated `references/commands.md` | the command |

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-G-READY-RULES | The three rules of `checks.readiness` (unconnected pin, power net without a declared width or a zone, part without a value) find each such case of a design and nothing else, under the definitions of this design | `tests/unit/checks/test_readiness.py` | every scenario of the rules of `verification-loop` added by this change holds |

It starts `INFERRED` and stays so: the rules are Fenolite's definitions, which no tool computes. Ids used without changing their level: `H-K-CONN-PARITY`, `H-K-CHECK-ERC`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| open connections | the board read's level combined with `connectivity.EVIDENCE` (`KICAD-VERIFIED`, `H-K-CONN-PARITY`, c0108): `INFERRED` on a KiCad board read | `test_ready_cmd.py -k open` |
| ERC and DRC | the stages' own, unchanged | `test_ready_cmd.py -k "ready_project or drc or stage_skip"` against the fake |
| the three rules | `INFERRED` (`H-G-READY-RULES`) | `test_readiness.py` |
| exit codes, read-only, JSON | mechanical | `tests/consistency`, `test_ready_cmd.py` |

## Risks / Trade-offs

- **Duplicates.** An open net is `ready.net-open` and, after DRC, `kicad.drc.unconnected-items`; an unconnected pin may also be a KiCad ERC finding. Kept: the first of each runs without a tool, and dropping the second would hide KiCad's verdict.
- **Power nets by type.** A `power_in` pin marks `GND` and every supply; a design that types its pins `passive` has no power net unless it declares a `Power` interface. Reported as `source`, so an agent can tell.
- **Single-pin nets.** A test point alone on a net is reported unconnected. That is the honest reading of the netlist.
- **Two board reads.** `load_board` and the DRC stage each read the board; a large board pays twice. Acceptable for a command run before fabrication.

## Migration Plan

New command and codes only; `check`, `net`, ERC lite and the schematic writer give the same output as before.

## Budget (1.5 days)

| part | days |
|---|---|
| shared helpers, rules and unit tests | 0.5 |
| command, fixture, command tests | 0.5 |
| docs, guide, explain, closing | 0.5 |

## Open Questions

- **Warnings for power nets?** Default: `error`, as the scope approved on 2026-10-08 lists it among what makes a design not ready. A design may waive nothing here yet; a later change may let `design.waive()` reach `ready.*`.
- **A `ready` stage in `check`?** Default: no; `ready` stays a separate reply.
