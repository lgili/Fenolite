# c0501: route and measure a free channel on an existing board

Found on: editing a private two-layer power board in place with `fenolite.backends.altium.edit` (field
failures F37 and F38; codes only, nothing from the board is in this change).

## Why

- **F37: no path search on an imported board.** Fenolite has a router (`routing.octilinear`, the bounded
  search of c0365 in `routing.search` and `routing.search_grid`, the proposals of c0280), but
  `fenolite route` reads a `.kicad_pcb` only (`cmd_route._run` calls `projectset.resolve_board` and the
  KiCad reader). On an Altium board under an edit session, two jobs were done by a hand-written A* over an
  obstacle dump taken from KiCad: a dedicated return trace between two capacitors of a ground net, and a
  three-lane escape. The same script was used to declare one of them infeasible. It had a bug: it treated
  every keep-out as a track obstacle, also keep-outs that forbid only poured copper (polygon cut-outs). The
  fix took only keep-outs whose restrictions forbid tracks.
- The router's world (`octilinear.World`) has the same gap in another form: it holds pads, holes, tracks,
  arcs, vias and the edge, but no rule area and no copper graphic. A route can cross a keep-out that forbids
  tracks; only the copper check after it notices.
- A "no path" answer has no explanation. `RoutingResult.refusals` names up to three blockers of the
  fixed patterns; the search (`search.Outcome`) gives only a reason (`no-room`, `state-limit`). Nothing says
  whether a refusal is proven or only a limit of the grid.
- **F38: no free-channel query.** Nothing answers "what is the widest track that fits between these two
  points under the board's rules" (net-class clearances, such as a large high-voltage clearance, and
  per-rule exceptions). The workaround did it by hand with shapely.

## What Changes

- **Rule areas and other copper in the routing world.** `World` takes the rule areas in force
  (`model.board.rule_areas`): one that forbids tracks blocks tracks on its layers, one that forbids vias
  blocks via barrels; one that forbids only pours or pads blocks nothing. On an Altium board the
  keep-outs of the Keep-Out layer, which the import keeps as graphics, are given their own restrictions
  (`adapter.copper.keepout_layer_restrictions`, as `convert.altium_to_kicad.keepout_restrictions` does).
  Copper graphics and the saved fills of other nets' zones are obstacles when the job says the pours stay
  as saved (`pours=kept`, the default for a `.PcbDoc`).
- **A refusal names its wall.** `World.blocker(...)` returns the first item that refuses a segment.
  When the search ends with `no-room` (every reachable state explored), the outcome lists the blocking
  items met at the edge of the explored area (the "wall"), each with its kind, net, layer, place and the
  clearance in force, and says whether the refusal is `proven` (every gap between neighbouring wall items
  is narrower than the width plus both clearances, measured exactly) or `grid-limited`.
- **Free channel.** `routing.channel.widest(...)` brackets the widest track of a net between two points:
  `low` is a width with a found path (returned, and checked again exactly), `high` the smallest width
  refused by a complete search, and `pinch` the two wall items and the exact free gap between them.
- **One public path, two backends.** `fenolite.api.read_board` also takes an Altium edit `Session` and
  reads the design of its pending edits. `fenolite.api.find_route` and `fenolite.api.free_channel` take a
  `Board` (or a path, or a session) and build the job with the board's own rules (`design_rules` of its
  backend and `ClearanceResolver`). `RouteFound.queue_on(session)` queues the found copper on a session as
  `clone` operations, so a script keeps editing and commits once.
- **New command `fenolite path`.** `fenolite path PATH --net NET --from A --to B (--width W | --widest)`
  reads a `.kicad_pcb` or a `.PcbDoc`. With `--width` it searches one connection and, with `--dry-run`, plans
  the write through the mutation protocol (`--confirm --plan ID` writes the reviewed bytes); on a `.PcbDoc`
  the write is an edit session commit and needs `--gate clone` (the `clone` gate is not confirmed by the
  kit). With `--widest` it is read-only and gives the channel.

## Impact

- `src/fenolite/routing/octilinear.py` (`World`: rule areas, graphics, kept fills, `blocker`),
  `routing/search.py` (`Outcome.wall`, `proven`), new `routing/channel.py`, `routing/codes.py`.
- `src/fenolite/backends/altium/backend.py` (rule areas of a document, for the world),
  `backends/altium/edit/session.py` (`Session.pending()`).
- `src/fenolite/api/board.py` and a new `api/route.py`; `docs/api.md`.
- New `src/fenolite/cli/cmd_path.py`; `docs/cli-contract.md`, "path"; `docs/routing.md`; agent guide page
  `route-search.md`.
- `fenolite route` on KiCad boards: routes no longer cross a rule area that forbids tracks or vias.
  Candidate ids of boards with such areas can change.
- Related: c0502 (`Session.plan()` shares the run-on-a-copy helper of `pending()`; `--emit-plan` once it lands).
  c0503 uses `read_board(session)` (task 1.1).
