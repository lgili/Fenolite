# Design: c0503

## D1 Measurement

One run on 2026-11-12, through `~/.local/bin/fenolite-heavy`, on the maintainer's Mac (Apple silicon,
CPython 3.13.7), of `analyze_power` alone (no split), with `cProfile`. The bench is authored for this change
(script kept outside the repository; task 1.1 puts it in `tests/_power.py`): a 100 mm × 80 mm board, one
ground zone filled on `F.Cu` and on `B.Cu` with N square 2 mm holes in a grid, 30 through vias, 20 SMD pads on
`F.Cu`, and the path between two through-hole pads at opposite corners. Copper 35 µm, plating 25 µm,
resistivity given.

| holes per layer | fill vertices per layer (about) | time |
|---|---|---|
| 4 | 20 | 0.6 s |
| 16 | 68 | 1.3 s |
| 48 | 196 | 5.4 s |

At 48 holes: `surface_distance` 3.4 s (64 %, of which `allowed`/`point_in_ring` 2.6 s), `narrowest_section`
0.95 s, `area_outside` 0.94 s; everything else is below 0.1 s. A real pour has round clearance holes, each
polygonised to many vertices, and the visibility graph grows with the square of the vertex count times the
rings tested per leg, so a board with hundreds of round holes reaches minutes to hours in the region bounds
alone.

The split was not run (one run only, by the brief). Its cost follows from the code: `pour_copper` rasterises
every zone at 0.1 mm (800 000 cells per layer on that board), and `split._solve` makes up to `50 · extent +
1000` SOR passes (91 000 at an extent of 1 800 cells) over every copper cell in Python. That alone explains a
run of more than 25 minutes.

## D2 Staged, sound region bounds

`power._region_element` today computes, per region, `ℓ` (`_between_hulls`, surface distance), `w`
(`narrowest_section`) and `A` (`area_outside`) exactly, then `low = R_s·ℓ²/A`, `high = R_s·A/w²`.

Stage 0 (cheap, always): `ℓ₀` = the exact distance between the two port hull rings (segment to segment, in integers; 0 when
they meet), which is at most `ℓ`; `A₀` = the region's area (`FillRegion.area2 / 2`), at least `A`. Then
`low₀ = R_s·ℓ₀²/A₀ ≤ low` and, with `w` from stage 1, `high₀ = R_s·A₀/w² ≥ high`. Both ends stay sound
because `low` grows with `ℓ` and falls with `A`, and `high` grows with `A` and falls with `w`.

Stage 1: `w` = `narrowest_section` (needed for the capacity of a region in series, and for `high`). Without it
the region has no capacity and `high` is `None`, as for a missing input today, and the row is `complete:
false`.

Stage 2: exact `ℓ` and `A`. Run only for a region of a row whose judgment (current or drop) is undecided with
the stage-0 values, or for every region when no deadline is set; regions in order of the width of their
interval, largest first, then by `where`, so the order is deterministic.

The network solve (`power._solve`, `_chain`) is unchanged; it takes the element values of whatever stage each
region reached.

Rejected: replacing the exact bounds by a mesh solve. The exact interval is what makes `analysis.path-exceeded`
an error and not an estimate; the mesh gives shares and a resistance inside it (D3).

## D3 Indexed visibility in `surface_distance`

`surface._Board.allowed(a, b)` tests a leg against every ring with `point_in_ring` and edge crossings.
It gets a `SpatialIndex` of the ring edges (the index `geometry` already has), so a leg tests only the edges
whose boxes meet its box. The result is the same set of legs; only the cost changes. `creepage` uses the same
function and gets faster too; its tests guard that its answers do not change.

## D4 Current split on an adaptive mesh

New `analysis/mesh.py`: per copper layer of the net, a quadtree over the board box. A cell is

- `full` when it lies inside the net's copper and meets no copper edge (tested with the edge index),
- `empty` when it lies outside and meets no edge,
- split in four otherwise, down to the cell size `h` (the `--pour-grid`, default 0.1 mm), where a cell
  counts as copper when its centre is (the rule of `shape_cells` today).

Adjacent leaves are balanced to differ by at most one level. Two leaves that share an edge of length `s` are
joined by the conductance `(t/ρ)·s/d`, `d` the distance between their centres (a finite-volume two-point flux).
Pads and vias are contacts as today: the cells they cover form one node; the via barrels join layers as today.
The number of cells grows with the length of copper edges over `h`, not with the area over `h²`.

Solve, coarse to fine: level `k` merges every leaf smaller than `h·2^k` into its ancestor of that size. Starting
from the coarsest level whose cells still separate the start and end contacts, each level is relaxed by the
integer SOR of `split._solve` from the previous level's potentials (each child takes its parent's), to the same
`TOLERANCE`, with at most `50 · extent_k + 1000` passes. A finished level is a complete answer at its cell
size: shares, the path's resistance, and `cell_nm`.

Zones whose copper state is `simulated` (no saved fill) still come from `pour_copper`'s raster, as today; the
mesh then takes those cells at size `h`. The gain is for saved fills, which is the case of an imported board.

Rejected: a sparse direct solver in pure Python (fill-in on a 2D mesh makes it slower than the cascade at these
sizes) and numpy or scipy (no runtime dependency in the core; no extra holds them).

## D5 Deadline and partial results

New `analysis/deadline.py`: `Deadline(seconds, clock=time.monotonic_ns)` with `passed()`. It is given
to `analyze_power` and `analyze_split` (`deadline=None` keeps today's unbounded behaviour). Work checks it
between regions (stage 2), between `surface_distance` searches, between split levels and every 64 SOR passes.

At the deadline:

- a power row keeps the stage each region reached; its intervals stay sound; `complete` is false;
- a split row keeps the finest finished level, with `cell_nm`, `converged` and `complete: false`; with no
  finished level it has no shares;
- one `analysis.deadline` warning per report names the rows and the regions left at stage 0 or 1 and the
  split level reached.

`fenolite analyze --deadline SECONDS` (default 120; `0` means none) applies to the kinds `power` and the split.
A run cut by the clock is not byte-reproducible; `inputs.deadline` and `complete` say so (as routing's
clock-limited runs do, capability routing, "Deterministic bounds"). Tests use a fake clock.

Judgments rest on the sound values only: `analysis.path-exceeded` and `analysis.drop-above` need the bound
that proves them, so a cut run gives more `-undecided` warnings and never a false error.

## D6 Pending edits

- Python: `fenolite.api.analyze_power(board, *, paths, requirements, ..., deadline=None) -> PowerReport`, and
  `analyze_split` likewise, `board` a `Board`, a path or a `Session` (c0501, `read_board(session)`). A session's
  board is read from `Session.pending()`; nothing is written.
- CLI: `fenolite analyze PATH --after-plan PLAN_ID` loads the staged plan (`cli.plans.load`), takes the bytes it
  would write to `PATH`, and analyzes them with the backend's reader (`board_from_bytes` for Altium, the KiCad
  reader on the text). The plan's recorded digest of the file it would replace MUST equal `PATH`'s digest, or
  the command exits 4 with `FEN-4002` (review again). A plan that writes nothing to `PATH` is `FEN-2001`. The
  reply's `input` holds `planned: PLAN_ID` and the digest of the planned bytes.

Rejected: a file format for a queued session (none exists, and it would duplicate the plan store).

## Codes

| code | severity | when |
|---|---|---|
| `analysis.deadline` | warning | the deadline cut power or split work; names what is coarse |

## Format evidence needed

None: no file format fact changes. The mesh conductance is Fenolite's own discretisation, `INFERRED`, under
`H-G-POWER-SPLIT`; the staged bounds rest on `H-G-AN-POUR` as today.

## Risks

- The quadtree's two-point flux is not consistent on graded cells next to diagonal edges; error is bounded by
  task 3.3's comparison with the finite-difference oracle and the old raster.
- The CI time budgets are on GitHub's Linux runners, slower than the maintainer's Mac; task 4.1 records both.

## Decisions taken while implementing

- Decision (maintainer, 2026-11-14): the mesh's two-point flux uses the normal distance `(a+b)/2` across the
  shared side (`a/2` to a contact), not the Euclidean distance of the centres; weights are integers times
  `SCALE_K = 3`, exact for leaves balanced 2:1.
- Decision (maintainer, 2026-11-14): a hanging side (a leaf of size `2s` whose side two free leaves of size `s`
  share) takes `g1·g2/(g1+g2)` off the link between the two small leaves. Without it the flux along the side
  through the large leaf broke the strip benches (`two_strips` gave 669 µΩ against the exact 686); with it a
  linear potential solves the mesh exactly and the strips match the raster to the microohm.
- Decision (maintainer, 2026-11-14): leaves are at most 8 cells across (`mesh.MAX_LEAF`). Measured on the
  dumbbell bench at 0.1 mm against the oracle's 1312 µΩ: no cap 1342 (+2.3 %), 16 cells 1341, 8 cells 1336
  (+1.8 %), 4 cells 1327 (+1.1 %); 4 cells tripled the nodes of the 48-hole plane (100 322 against 30 026) and
  the split time (132.6 s against 27.6 s). 8 cells meets the 2 % of task 3.3.
- Decision (maintainer, 2026-11-14): the cascade has four levels, `8h`, `4h`, `2h`, `h` (`split.LEVELS = 3`), each
  built by the same mesh code at its own cell size; a coarse level that merges the start and end contacts is
  skipped. `ω` uses `n`, the most links from a start node (BFS), in place of the raster's two spans; tried
  `n/2` and `2n` on the 48-hole plane at 0.2 mm: `n` took the fewest passes at the finest level.
- Decision (maintainer, 2026-11-14): a split row reports `nodes` and `iterations` of its finest finished level.
  The raster's `MAX_CELLS` guard now counts the fills by area over `h²`, so the guard no longer rasterises.
- Decision (maintainer, 2026-11-14): `--deadline` takes whole seconds (the reply holds no float); `inputs.deadline`
  is that integer, `0` for none.
- Decision (maintainer, 2026-11-14): `Deadline` and the API's `deadline=` take whole seconds too, read on
  `time.monotonic_ns`: `fenolite.analysis` names no float (`tests/unit/analysis/test_report.py`).
- Decision (maintainer, 2026-11-14): the envelope's `input` is frozen (`schemas/fenolite.envelope.v0.json`,
  `additionalProperties: false`), so `--after-plan` puts the plan id in `result.inputs.planned`; `input.sha256`
  is the digest of the planned bytes. An unknown or damaged plan is `FEN-4002` too (review again). The scenario
  "Analyze a planned route before writing it" runs on the authored Altium return-trace bench of the `path`
  tests (`tests/_route_benches.py`), whose plan writes the board itself.
- Decision (maintainer, 2026-11-14): stage 1 runs for every fill before any stage 2; the order of stage 2 is
  the fills of rows that a scratch judgment at stage 1 leaves with a `-undecided` issue, then the rest, each
  group by the widest interval (an interval without a high end first), then `where`. The deadline is checked
  between fills, not inside one search.
- Decision (maintainer, 2026-11-14): the exact bounds were made faster without changing a value: a hole whose box
  misses a port hull adds nothing to `area_outside`, a ring inside the hull adds its whole area without
  clipping, a ring edge strictly inside a port hull is skipped by `narrowest_section`, and a chord pair whose
  box gap or exact distance cannot beat the chord held for each parity it may have is skipped (`store` would
  keep the held one). `test_section.py`, `test_fills.py`, `test_power.py` and `test_power_benches.py` give
  the same values.
- Decision (maintainer, 2026-11-14): the speed test records the times and marks itself `xfail` while a budget is
  not met, so the unit job stays green and the times are not hidden; task 4.1 stays open.
- Decision (maintainer, 2026-11-14): the agent guide's command reference grows a seventh page
  (`references/commands-7.md`): the new options pushed the six bounded pages over their size.

## Measurements (task 1.1 and 4.1)

All on the maintainer's Mac (Apple silicon, CPython 3.13), through `~/.local/bin/fenolite-heavy`, on the
authored bench `plane_board` of `tests/_power.py`; the split at 0.1 mm. Runs shared the machine with another
agent's work, so the times are indicative.

| bench | step | parent commit (1e1595c99) | this change |
|---|---|---|---|
| 48 square holes | `analyze_power` | 1.4 s | 0.8 s |
| 48 square holes | `analyze_split` | more than 600 s (stopped) | 28.3 s |
| 300 round holes | `analyze_power` | 133.3 s | see below |
| 300 round holes | `analyze_split` | more than 600 s (stopped) | see below |
