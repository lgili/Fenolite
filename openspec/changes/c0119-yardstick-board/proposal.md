## Why

Milestone v0.4 (written as "v0.2c" before the renaming of 2026-10-07); the statements about the code were checked against `origin/dev` at `9aba2dff`.

The complex-board review of 2026-10-05 found that nothing measures the distance to its yardstick (four to eight layers, 300 to 600 parts, repeated channels, pairs, a high-voltage section): the largest finished board has 40 parts on two layers (c0025; `examples/` still tops out at `board_40parts`), the two heavy demo boards run only with `FENOLITE_HEAVY=1`, and with no budget a tenfold slowdown passes CI. Each change of v0.4 proves its part on a bench, none on one board with the others.

Measured on 2026-10-05 on a generated stand-in (official KiCad 10.0.6 libraries, the review branch at `27ef3ad7`; not repeated on `dev`, where `check` has since gained `erc.kicad` and `parity` and `build` writes a schematic, so these numbers size the problem and are no budget):

- 369 parts, four layers: build 6 s, fill 7 s, check 9 s, export 4 s, render 2 s, a byte-identical rebuild 10 s, peak 262 MiB; `check`'s only error is KiCad's unconnected items, capped at 499. 665 parts: 3 s to 24 s per step, 313 MiB.
- From a KiCad install, whose symbol libraries are whole files, the same build takes 101 s to 161 s.
- Freerouting 2.4.1, inner zones given as planes, optimizer off: after its 20 passes (1003 s, heap 1.9 GB) 32 of 344 connections stay open, flat since pass 13. c0109's default budget of 900 s would cut that run.

## What Changes

- **The board.** `examples/yardstick/design.py`: an invented eight-channel 48 V buck controller: a QFN controller, a USB 2.0 pair, a CAN port, an isolated high-voltage sense section behind a gap; about 370 parts of the official libraries, placed by the script.
- **Stages.** 1, four layers with inner planes, the built schematic, BOM, placement table and manifest (`dev` after 0.3.0); 2, six layers, stack-up (c0100, c0101); 3, shape, rule areas, pair, impedance and placement rules, net tie, thermal arrays (c0102 to c0105, c0111 to c0114); 4, routed and analysed (c0106 to c0110, c0115); 5, the document kinds, drawings and test features (c0116 to c0118).
- **The runner.** `tools/yardstick.py run` drives the stage's loop through the CLI and judges time, peak memory, reply size and issues per step against budgets and acceptance rules.
- **Budgets.** `tools/yardstick_budgets.toml`: seconds and MiB per stage and step, ratchets on open connections and DRC errors, and the findings a stage accepts with their owners; read from a stage's first three scheduled runs, provisional from one local run on `dev` before.
- **The job.** `yardstick` in `nightly.yml`, nightly and on demand, in the pinned 10.0.6 image, not a merge gate; it also reads and round-trips the two heavy demo boards (70 MB, 85 MB).
- **The record.** An artefact per run; a row of `docs/evidence/yardstick.md` per stage reached and per release.

Size: 8.75 design-days.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `release-gate`: ADDED "Yardstick board", "Yardstick stages", "Yardstick runner", "Yardstick budgets", "Yardstick record".
- `ci-baseline`: ADDED "Yardstick nightly job".

## Non-goals

- Agent runs on this board: c0081.
- Repairing what it finds: the owning change.
- Target 9: nowhere in v0.4, because the 9.0 library tag lacks a library the board uses and 9.0 cannot refill (`H-K-01`).
- A placer: roadmap v0.5a; c0096's constrained placement has its own acceptance, and `place` is no step here (design, Decision 4). Module frames: the roadmap line `dsl-module-frame`.
- An Altium build of the board: nowhere in this change. The yardstick measures the KiCad loop, whose verdicts come from `kicad-cli`; the Altium write side has its own samples and verification kit (c0091, c0092).
- Part heights under a lid: the change that the maintainer split out of c0113 on 2026-10-07 (to be written after c0099); the example takes it when it exists, and no stage waits for it.
- A BGA: nowhere in v0.4, because c0110 measured no router that escapes one.
- Reading fabrication files back: nowhere in v0.4; the plan's `oracles` extra has no change.
- Faster reading of whole-file symbol libraries: a new roadmap line (Open Questions).

Limits: KiCad 10 only; budgets hold for the CI runner; a cut change leaves its stage part unreached; before stage 4, open connections are KiCad's count, capped at 499 (c0141 marks the cap in `check`); peak memory is a step's largest process.

## Provenance of the circuit (clean-room)

Recorded on 2026-10-07, by the maintainer's decision 1 of that day: **the maintainer, Luiz Carlos Gili, declares that the yardstick circuit (an eight-channel 48 V buck controller with an isolated high-voltage sense section) was invented for Fenolite and mirrors no board, product or reference design of any organisation.** The review of the proposals had asked for this statement, because nothing in a repository can show it. With it the circuit is kept as proposed.

What the change adds so that the statement stays checkable: every value at the top of the script is a round value with the comment `chosen for the example` or a public source id; the parts are ids of the official KiCad libraries, fetched and never committed; the file is CC0 and names no company, product or private path; `tests/residue` scans the example; the statement is copied into `docs/evidence/yardstick.md` (task 1.2).

## Evidence level required

- Stage 1: `KICAD-VERIFIED (10.0.x)` through `check` in the scheduled run (`H-K-YARD-STAGE1`); later stages by their tasks' rows. The label covers what `kicad-cli` judged. Whether a step stayed within its seconds and MiB is a measure of the runner, recorded per run, and carries no evidence label.
- `H-K-YARD-LIBREAD`, `H-K-YARD-HEAVY`, `H-G-DSN-YARD`: settled by the first scheduled runs.
- Runner, budgets, record: mechanical, hermetic tests.

## Impact

- New: `examples/yardstick/`, `tools/yardstick.py`, `tools/yardstick_budgets.toml`, `docs/evidence/yardstick.md`, `tests/unit/test_yardstick.py`.
- Changed: `nightly.yml`, two tests, two READMEs, `Makefile`; nothing under `src/fenolite/`. No model key, CLI flag or issue code is added.

## Prerequisites

- `0.3.0` is released from `dev`. Stage 1 needs nothing else: c0061 (built schematic), c0062 (`erc.kicad`, `parity`), c0064 (`bom`, `pnp`), c0065 (manifest states), c0066 (`check --format concise`), c0075 and c0076 (catalog) are archived.
- c0141 (DRC report limits, split from c0120) is not required: the runner reads its mark when `check` gives one.
- Stage 2: c0100, c0101. Stage 3: c0102 to c0105 and c0111 to c0114. Stage 4: c0106 to c0110 and c0115. Stage 5: c0116, c0117, c0118. Each stage is a task group that waits for its changes; a cut change leaves its part out.
- c0096, c0097, c0099: no stage needs them. By the maintainer's decision 2 the example uses c0102's `design.hole`, c0103's `rule_area` and c0113's `near` rules, to which c0096 adapts.
- Waiting for this change: c0113 (names this board for its acceptance), c0109 (its default budget), c0081 (may take the board as an agent task).
