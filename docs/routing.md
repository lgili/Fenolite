# Routing

Fenolite treats routers as local plugins. `fenolite.routing` defines plain-data jobs and results, the
`fenolite.routers` entry-point group discovers implementations, and the command merges only routed
tracks, arcs and vias back into Fenolite's board. A plugin reports whether it sends design data off
the machine; `fenolite route` requires explicit permission for such a router. Route results are
`UNVERIFIED`: run `fenolite check` to judge the board.

## Built-in routers

- `direct` joins a two-pad net with a straight segment. It avoids no obstacles and is intended for
  hermetic tests and small examples.
- `kicadroutingtools` runs KiCadRoutingTools from a separate checkout as a subprocess. Fenolite does
  not install or import it. Install the pinned `v0.22.1` checkout and build its Rust router with
  `python build_router.py`; keep its dependencies in an environment separate from Fenolite. Set
  `FENOLITE_KRT` to the checkout and `FENOLITE_KRT_PYTHON` to the interpreter that has the tool's
  dependencies. The pinned commit and platform-specific setup are recorded in
  [routing evidence](evidence/routing.md).

Discover routers with `fenolite capabilities --json`; `fenolite doctor --json` checks their local
availability. Route with `fenolite route BOARD --router NAME --dry-run`, inspect the plan, then rerun
with `--confirm` to write. `--nets` may be repeated with glob patterns; `--rip` permits the selected
unlocked copper to be replaced. Routed files from external tools are read for copper only, then
Fenolite's writer produces the board.

## Loop order

Use `build` → `place` → `route` → `fill` → `check`. Routing changes copper inputs used by a fill, so
refill after routing. Later builds keep routed tracks and vias whose nets remain in the design.

## Tool smoke job

The optional `routing` CI job runs the pinned tool and oracle smoke tests on KiCad 9.0.9 and 10.0.6.
It downloads external code and a router binary, so it is informative evidence rather than a required
merge check. It runs the feasibility probes and the `build` → `place` → `route` → `fill` → `check`
loop on each target.
