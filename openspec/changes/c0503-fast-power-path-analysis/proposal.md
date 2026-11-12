# c0503: power-path analysis in bounded time, also on a pending edit

Found on: editing a private two-layer power board in place (field failure F44; codes only, nothing from the
board is in this change).

## Why

- **Too slow to finish.** `fenolite analyze --kinds power` with the current split (`--split`) ran for more
  than 25 minutes at 100 % CPU on a two-layer power board and was killed. There is no deadline and no partial
  answer: the user got nothing.
- **Where the time goes** (design D1, measured on an authored 100 mm × 80 mm two-layer ground-pour bench):
  the exact region bounds of `analysis.power` spend about two thirds of their time in
  `surface.surface_distance` (a visibility graph over every vertex of the fill, each leg tested against every
  ring), and the rest in `narrowest_section` and `area_outside`, all in `Fraction`s. The time grows faster
  than the fill's vertex count, and a real pour has hundreds of round clearance holes, each many vertices.
  The split (`analysis.split`) relaxes a 0.1 mm raster of all the net's copper in pure Python, with up to
  `50 · extent + 1000` passes over every cell: about 90 000 passes over up to 1.6 million cells on a board
  of that size.
- **No pending edits.** The analysis reads a file. Copper that an edit session changed but has not saved
  cannot be judged, so the user cannot check a fix before committing it.
- The workaround was ad-hoc IPC-2152 width checks and current-flow scripts.

## What Changes

- **Sound coarse bounds first.** Each fill region of a path gets a cheap interval first: the shortest path
  `ℓ` between the port hulls is bounded below by their straight distance, and the area by the region's whole
  area. Both keep the interval sound (wider, never wrong). The exact `ℓ`, area and section are computed only
  for regions whose interval leaves a judgment undecided, largest first, while time remains.
- **A faster exact `ℓ`.** `surface_distance`'s visibility test uses a spatial index of the ring edges instead
  of testing every ring, so a leg costs the edges near it.
- **Current split on an adaptive mesh.** The raster becomes a quadtree of the copper: large cells inside
  plain copper, cells of the grid size (`--pour-grid`, default 0.1 mm) only along edges, holes, pads and
  vias. It is solved coarse to fine (each level starts from the coarser level's potentials), so the finest
  level needs few passes. Each finished level is a complete answer at its cell size.
- **A deadline.** `fenolite analyze --deadline SECONDS` (default 120) bounds the power and split work. At the
  deadline the reply keeps what is finished: sound intervals, the finest split level reached, `complete:
  false` on each row cut short, and `analysis.deadline` (warning) naming what was not refined.
- **Pending edits.** `fenolite.api.analyze_power(board, ...)` takes a `Board`, a path or an Altium edit
  `Session` (through `read_board(session)` of c0501). `fenolite analyze PATH --after-plan PLAN_ID` analyzes
  the bytes a staged plan would write to `PATH` (for example the plan of `fenolite path --dry-run`), without
  writing them.

## Impact

- `src/fenolite/analysis/power.py` (`_region_element`, `_bounds`: staged bounds), `analysis/surface.py`
  (indexed visibility), `analysis/split.py` (mesh and cascade), new `analysis/mesh.py` and
  `analysis/deadline.py`, `analysis/codes.py`.
- `src/fenolite/cli/cmd_analyze.py` (`--deadline`, `--after-plan`); `src/fenolite/api/board.py`
  (`analyze_power`); `docs/analyses.md`, "Power paths"; `docs/cli-contract.md`, "analyze"; `docs/api.md`.
- Results of complete runs do not change for `power`; split shares and resistance may move within the
  stated tolerance (task 3.3). The existing finite-difference agreement test stays.
- Depends on c0501 task 1.1 (`read_board` of a session). If c0503 is implemented first, it does that task and
  c0501 ticks it.
