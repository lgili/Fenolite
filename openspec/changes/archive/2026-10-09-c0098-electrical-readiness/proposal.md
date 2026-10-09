## Why

This is a proposal of milestone v0.4, written against `origin/v04` at `04ef42a`. The maintainer decided on 2026-10-08 that c0098 is in v0.4 (`docs/roadmap.md`, "Open decisions", row 35).

Before fabrication an agent asks: is the design electrically ready? Today the answer is spread over several commands, and some rules are missing:

- Open connections come from `fenolite net` (c0108) or from KiCad's DRC inside `fenolite check`.
- ERC and DRC findings come from `fenolite check`, among ten other stages.
- An unmarked pin on no net is seen by ERC lite on document input only, and on a KiCad project by KiCad's ERC only when a schematic exists.
- No command says that a power net has neither a declared track width nor a zone, so a supply drawn at the default width passes every check.
- A part without a footprint is `check.footprint-unresolved`; a part without a value is reported nowhere.

## What Changes

- **`fenolite ready PATH`**, read-only: six checks in one reply, `result.ready` and `result.complete`, exit 0 when ready and 5 with `issues` when not. It never writes a file and runs `kicad-cli` only for ERC and DRC.
- **Reused, not rewritten.** Open connections are `analysis.connectivity` (c0108). ERC and DRC are the `erc.kicad` and `drc.kicad` stages of `check`, run through `cmd_check.run_stages`, with its pre-flight. A missing footprint is the rule of `model.validate`, moved into one function that both use.
- **New rules**, in `checks.readiness`: unconnected pins without a no-connect mark; power nets (named by an interface of kind `power`, or holding a `power_in` or `power_out` pin) with no track width of their own class or of a rule and no zone; parts without a value.
- **No `kicad-cli`.** As `check` does for its oracle stages: exit 6 with `FEN-6001`, whose hint names `--no-kicad`. With `--no-kicad` the two checks are reported `skipped`, each with a `ready.check-skipped` warning, and `result.complete` is false.
- **Registered** in `capabilities`, `docs/cli-contract.md`, `fenolite explain` and the agent guide.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `cli-contract`: ADDED "Ready command", "Ready checks and their sources", "Ready intent", "Ready without kicad-cli", "Ready result and exit codes", "Ready example and documentation".
- `verification-loop`: ADDED "Shared readiness definitions", "Open nets check", "Unconnected pins rule", "Power nets rule", "Power net coverage", "Part fields rule", "Readiness issue codes".

## Non-goals

- Replacing `check`: `ready` runs two of its stages and adds rules; `check` stays the judge of every change.
- Currents, voltage drops and creepage: `fenolite analyze` (c0047, c0115).
- Altium input: `ready` reads KiCad projects; document input exits 2.
- A longer loop block in the agent guide (`release-gate` caps it at ten lines).
- Removing the duplicate between `ready.net-open` and KiCad's `unconnected_items`: both are reported, because the first runs without a tool.

## Evidence level required

- Open connections: `connectivity.EVIDENCE` (`KICAD-VERIFIED`, `H-K-CONN-PARITY`), combined with the board read's.
- ERC and DRC: the level each stage reports, as in `check`.
- The new rules: `INFERRED` (`H-G-READY-RULES`), Fenolite's own definitions judged on the model.
- The envelope: the lowest level of the checks that ran, so `INFERRED` at best.

## Impact

- New `cli/cmd_ready.py` and `checks/readiness.py`; `checks/validate.py` gains `unresolved_footprints`; `model/circuit.py` gains `power_interface_nets`, used by ERC lite and the schematic writer in place of their own copies.
- New issue codes `ready.*` in `fenolite explain`; a new fixture project `tests/data/kicad/ready/` (the starter of `fenolite init`, built and routed with `direct`).
- No existing output changes.

## Prerequisites

c0108 (`analysis.connectivity`) and c0114 (waivers in the DRC stage) are on `origin/v04`. No other proposal of v0.4 must land first.
