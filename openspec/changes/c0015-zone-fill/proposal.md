## Why

A built board has zone outlines and no copper in them. Fenolite computes no fill (plan D2: KiCad is the oracle), and only `kicad-cli` 10.0 can refill a board headless: `pcb drc --refill-zones --save-board` exists in 10.0 only (`H-K-01`). That command saves in the 10.0 format, so a target-9 board cannot simply be replaced by its output. v0.1 needs filled boards for both targets (acceptance item 1), and c0019 left the premise of its fill digests to this change (`H-K-LENS-FILL`).

Proposal-time runs (2026-10-03) answered the roadmap's open question: `kicad-cli` 10.0.6 refilled the authored project for both targets and kept every zone uuid; the fills, lifted into the original model and written for the board's own target, load on 9.0.9 and 10.0.6 with the same DRC violation types; a second refill gave the same polygons.

## What Changes

- `backends/base.py`: `ZoneFills`, `FillOutcome` and the protocol `FillOracle`.
- `backends/kicad/cli.py`: `KicadCli.refill(board, files=…)`, 10.0 only.
- `backends/kicad/fill.py` (new): `lift_fills` takes the fills and the `filled` flag of each zone from the saved copy, matched by zone uuid, and keeps everything else of the original model; `fill_board` writes the result for the board's own major. `KicadOracle.refill` satisfies `FillOracle`.
- `fenolite fill PATH` (new, mutating): plans with `--dry-run`, writes the board with `--confirm`, and writes nothing when the fills are already current. `--from REFILLED` lifts from an already refilled board without running a tool; `--out FILE` writes elsewhere.
- `checks/fill.py`, stage `zone.fill` before `drc.kicad`: the board's fills against a refill on the copy; `zone.unfilled`, `zone.fill-stale` and `zone.fill-unchecked`.
- `--kicad-cli docker:<image>`: the package runner runs `kicad-cli` in a container, for machines with KiCad 9 only.
- Probes first on 10.0.6 and 9.0.9; `H-K-LENS-FILL` is settled here.
- Sources S-0205; hypotheses `H-K-FILL-SAVE`, `H-K-FILL-LIFT`, `H-K-FILL-REPEAT`, `H-K-FILL-LOAD9`, `H-K-CLI-DOCKER`.

Budget: 6.0 days against the roadmap's 5; the Docker runner is the first cut (design, "Budget").

## Capabilities

### New Capabilities
- `zone-fill`: the refill oracle, lifting, the `fill` command, the `zone.fill` stage, issue codes.

### Modified Capabilities
- `backend-protocol`: ADDED "Fill oracle protocol".
- `kicad-oracle`: ADDED "Refill through kicad-cli 10", "Lifted fills pass the oracle", "Container runner".
- `verification-loop`: ADDED "Zone fill stage".
- `cli-contract`: ADDED "Fill command".

## Non-goals

- Computing fills in Fenolite; teardrops; fills of rule areas.
- Zone settings (c0031) and zones in the DSL (c0031).
- Refilling inside `build`, `route` or `check`: `build` keeps current fills (c0019), and `check` only compares.
- A zone's own clearance in the copper check (v0.2a).
- KiCad 8 boards (read-only, `FEN-7003`); a downgrade of the saved 10.0 file.
- Pulling or inspecting container images; a `doctor` entry for containers.

## Evidence level required

- Refill, saved uuids and repeatability: `KICAD-VERIFIED (10.0.x)` (`H-K-FILL-SAVE`, `H-K-FILL-REPEAT`).
- Lifted fills written for targets 9 and 10: `KICAD-VERIFIED (9.0.x, 10.0.x)` for loading (`H-K-FILL-LOAD9`), and `KICAD-VERIFIED (10.0.x)` for equality with a second refill (`H-K-FILL-LIFT`).
- `H-K-LENS-FILL`: `KICAD-VERIFIED (10.0.x)` by its placeholder test.
- `zone.fill` stage: the level of `fill.EVIDENCE` with the run's oracle; `UNVERIFIED` when the tool cannot refill.
- Container runner: `KICAD-VERIFIED` for the pinned images when Docker is available (`H-K-CLI-DOCKER`); mechanical with a fake `docker` otherwise.
- Lifting and the command: mechanical (hermetic tests with a fake `kicad-cli`).

## Impact

- New `backends/kicad/fill.py`, `checks/fill.py`, `cli/cmd_fill.py`; extended `backends/base.py`, `backends/kicad/{cli,oracle}.py`, `checks/{stages,codes}.py`.
- Three committed fixtures: the authored target-9 board unfilled, the copy `kicad-cli` 10.0.6 saved, and the filled result, for the 9.0.9 probes and the command's example.
- No runtime dependency, model or schema change.
- Depends on c0013 and c0019 (archived) and on c0031, which archives first; c0020 is independent.
