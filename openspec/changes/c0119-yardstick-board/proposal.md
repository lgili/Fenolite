## Why

The review of 2026-10-05 (`docs/roadmap.md`, Gaps to a complex board) found that nothing measures the distance to its yardstick: the largest finished board has 40 parts on two layers (c0025), the two heavy demo boards never run, and with no budget a tenfold slowdown passes CI. Each v0.2c change proves its part on a bench, none on one board with the others.

Measured on 2026-10-05 on a generated stand-in (official KiCad 10.0.6 libraries, this branch):

- 369 parts, four layers: build 6 s, fill 7 s, check 9 s, export 4 s, render 2 s, a byte-identical rebuild 10 s, peak 262 MiB; `check`'s only error is KiCad's unconnected items, capped at 499. 665 parts: 3 s to 24 s per step, 313 MiB.
- From a KiCad install, whose symbol libraries are whole files, the same build takes 101 s to 161 s.
- Freerouting 2.4.1, inner zones given as planes, optimizer off: after its 20 passes (1003 s, heap 1.9 GB) 32 of 344 connections stay open, flat since pass 13. c0109's default budget of 900 s would cut that run.

## What Changes

- **The board.** `examples/yardstick/design.py`: an invented eight-channel 48 V buck controller: a QFN controller, a USB 2.0 pair, a CAN port, an isolated high-voltage sense section behind a gap; about 370 parts of the official libraries, placed by the script.
- **Stages.** 1, four layers with inner planes (today's code); 2, six layers, stack-up (c0100, c0101); 3, shape, rule areas, pair, impedance and placement rules, net tie, thermal arrays (c0102 to c0105, c0111 to c0114); 4, routed and analysed (c0106 to c0110, c0115); 5, manufacturing package (c0061, c0064, c0065, c0116 to c0118).
- **The runner.** `tools/yardstick.py run` drives the stage's loop through the CLI and judges time, peak memory, reply size and issues per step against budgets and acceptance rules.
- **Budgets.** `tools/yardstick_budgets.toml`: seconds and MiB per stage and step, ratchets on open connections and DRC errors; read from a stage's first three scheduled runs.
- **The job.** `yardstick` in `nightly.yml`, nightly and on demand, in the pinned 10.0.6 image, not a merge gate; it also reads and round-trips the two heavy demo boards (70 MB, 85 MB).
- **The record.** An artefact per run; a row of `docs/evidence/yardstick.md` per stage reached and per release.

Size: 8.5 design-days.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `release-gate`: ADDED "Yardstick board", "Yardstick stages", "Yardstick runner", "Yardstick budgets", "Yardstick record".
- `ci-baseline`: ADDED "Yardstick nightly job".

## Non-goals

- Agent runs on this board: c0081.
- Repairing what it finds: the owning change.
- Target 9: nowhere in v0.2c, because the 9.0 library tag lacks a library the board uses and 9.0 cannot refill (`H-K-01`).
- A placer: roadmap v0.5a. Module frames: roadmap v0.2b, `dsl-module-frame`.
- A BGA: nowhere in v0.2c, because c0110 measured no router that escapes one.
- Reading fabrication files back: nowhere in v0.2c; the plan's `oracles` extra has no change.
- Faster reading of whole-file symbol libraries: a new roadmap line (Open Questions).

Limits: KiCad 10 only; budgets hold for the CI runner; a cut change leaves its stage part unreached; before stage 4, open connections are KiCad's count, capped at 499; peak memory is a step's largest process.

## Evidence level required

- Stage 1: `KICAD-VERIFIED (10.0.x)` through `check` in the scheduled run (`H-K-YARD-STAGE1`); later stages by their tasks' rows.
- `H-K-YARD-LIBREAD`, `H-K-YARD-HEAVY`, `H-G-DSN-YARD`: settled by the first scheduled runs.
- Runner, budgets, record: mechanical, hermetic tests.

## Impact

- New: `examples/yardstick/`, `tools/yardstick.py`, `tools/yardstick_budgets.toml`, `docs/evidence/yardstick.md`, `tests/unit/test_yardstick.py`.
- Changed: `nightly.yml`, two tests, two READMEs, `Makefile`; nothing under `src/fenolite/`.
