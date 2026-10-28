## Why

Package 5 of change c0175 ("Copper tidy"). A router, a rip and a hand edit leave copper behind: stubs that
end in the air, leads to vias that join nothing, right angles that a reviewer asks to soften. KiCad's DRC
lists the dangling items, but nothing in Fenolite removes them, and doing it by hand on a board an agent
routed is the slow, error-prone part of the loop. The pieces to do it safely exist: the connected groups
of `analysis.connectivity`, the copper check of `checks.copper` and the board write of `route`.

## What Changes

- New package `fenolite.tidy` (imports `model`, `geometry` and `backends.base` only):
  - `prune`: removes, pass after pass, unlocked tracks and arcs with a free end and unlocked vias joined on
    fewer than two layers, each only when its net keeps its connected groups.
  - `chamfer`: turns each right-angle joint of two horizontal or vertical tracks into a 45° track, kept
    only when its net keeps its groups and the copper check (passed in by the caller) finds nothing new.
- New writing command `fenolite tidy PATH [--nets GLOB]... [--prune] [--chamfer] [--leg LENGTH] [-o FILE]
  [--drc] [--kicad-cli PATH]`: the glue that reads the board and the project's rules, runs the steps,
  checks the whole result again and, with `--drc`, compares `kicad-cli` DRC before and after.
- Seven issue codes `tidy.*`, explained by `fenolite explain`; the hypothesis `H-K-TIDY-DRC`.

## Capabilities

### New Capabilities

- `copper-tidy`: "Prune dangling copper", "Prune keeps the groups", "Chamfer right-angle joints",
  "Chamfers are checked", "Tidy command", "Tidy command checks the result" and "Tidy codes". The
  capability holds the tools that clean the routed copper of a board, each edit proved to keep the
  board's connectivity and clearance.

### Modified Capabilities

None. c0175 keeps the rest of its `copper-tidy` delta, narrowed: "Straighten runs", "Chamfer T-joints and
zone outlines", "Style report" and "Tidy straighten and report options", with its tasks 7.2, 7.3 (rest),
7.4 and 7.6.

## Non-goals

- Straightening runs on the 0/45/90° lattice, the style report with `--compare`, and the routing plugin
  `octilinear` (c0175, tasks 7.2, 7.4 and 7.6): each needs a search and a bench of its own.
- Chamfers of T-joints, of joints at other angles, of arcs and of zone outlines (`--zones`; c0175, task
  7.3): a T-joint moves copper that a third item joins, and a zone outline needs its fill to be judged.
- Trimming a track that dangles past its last joint: prune removes whole items, never parts of one.
- Running DRC without `--drc`: the examples and the unit suites stay without a tool.

## Evidence level required

`INFERRED` without `--drc`: the groups (`H-K-CONN-PARITY`) and the copper check (`H-K-COPPER-*`) judge every
edit, and `H-K-TIDY-DRC` claims that KiCad agrees. With `--drc`, `KICAD-VERIFIED` for the board written,
proved by `kicad-cli` on the exact bytes; `tests/kicad/tidy/test_tidy_oracle.py` settles the row on both
majors.

## Impact

- `src/fenolite/tidy/`, `src/fenolite/cli/cmd_tidy.py`, `cli/_examples.py`, `cli/explain.py`,
  `cli/data/explain.toml`, `tests/unit/test_import_graph.py` (row `tidy`), tests, the example board
  `tests/data/kicad/tidy/stub.kicad_pcb`, `docs/cli-contract.md`, `docs/copper.md`, `docs/hypotheses.md`,
  the guide's `routing` page and its generated `commands` page, `CHANGELOG.md`, and c0175's `tasks.md`,
  `design.md` and `specs/copper-tidy/spec.md`.
