## Why

The rest of package 5 of change c0175 ("Copper tidy"), after c0208 built `fenolite tidy` with prune and
right-angle chamfers. A router leaves staircases: runs that step many times where one or two 45° turns
would do, T-joints entered at 90°, and pours with sharp corners. A reviewer who wants a house style also
needs it measured: how many joints are at 45°, at 90° or acute, how many jogs, which widths. Doing this
by hand on a routed board is slow, and nothing in Fenolite measures it.

## What Changes

- `fenolite.tidy.straighten`: each run of unlocked tracks between fixed points is replaced by a shape of
  at most three segments on the 0/45/90° lattice when one weighs fewer turns (45° weighs 1, 90° weighs 3,
  acute is forbidden, a turn inside the run's own pad is free) and keeps the groups and the copper check.
  Nets of a differential pair or with a length rule are left alone (`tidy.straighten-skipped`).
- `fenolite.tidy.chamfer` also turns T-joints into 45° entries and, with `zones=True`, cuts the convex
  right-angle corners of zone outlines, keeping every item of the net that touched the outline.
- `fenolite.tidy.style`: the style report per net class and copper layer (joint angles, jogs, widths,
  vias), with `tidy.acute` for each acute joint.
- `fenolite tidy` gains `--straighten` (run between prune and chamfer, and by default), `--zones`,
  `--report` and `--compare REFERENCE` (read-only); `result.style` holds the report's counts before and
  after the steps.
- Two codes, `tidy.acute` (warning) and `tidy.straighten-skipped` (info); the hypothesis `H-G-TIDY-STYLE`;
  `H-K-TIDY-DRC` covers straightened runs and T-joint entries too.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `copper-tidy` (created by c0208): ADDED "Straighten runs", "Turn costs", "Runs left alone", "Chamfer
  T-joints", "Chamfer zone outlines", "Style report" and "Tidy report option"; MODIFIED "Tidy command"
  and "Tidy codes". c0175 keeps only the routing plugin `octilinear` of package 5 (task 7.6, its
  `routing` delta) and no longer holds a `copper-tidy` delta.

## Non-goals

- The routing plugin `octilinear` (c0175, task 7.6).
- Straightening arcs, runs across layers or through vias, and shapes of more than three segments: a
  general lattice router is the plugin's job.
- Reflex zone corners (a cut there would add copper), and corners of zone cut-outs and keep-outs.
- `--compare` with a board of another format: the reference is a KiCad board.

## Evidence level required

`INFERRED` without `--drc` (`H-K-TIDY-DRC`, the groups and the copper check); `KICAD-VERIFIED` with `--drc`
for the board written. The style report is `INFERRED` (`H-G-TIDY-STYLE`), on authored benches with
hand-counted joints.

## Impact

- `src/fenolite/tidy/` (new `straighten.py`, `style.py`; `chamfer.py`, `codes.py`, `__init__.py`),
  `src/fenolite/cli/cmd_tidy.py`, `cli/data/explain.toml`, tests, `docs/cli-contract.md`,
  `docs/copper.md`, `docs/hypotheses.md`, `docs/evidence/matrix.md`, the guide's `routing` page and its
  generated `commands` page (four option lines), `CHANGELOG.md`, `openspec/README.md`, and c0175's
  `proposal.md`, `design.md`, `tasks.md` and `specs/copper-tidy/` (removed).
