## Why

Task 7.6 of change c0175 ("Copper tidy", package 5): a routing plugin `octilinear` for the short,
critical connections that a person routes by hand first, such as a gate loop between a driver and its
switch or a sense pair from a shunt to an amplifier. The external routers (`freerouting`,
`kicadroutingtools`) route whole boards and need a tool and a time budget; `direct` checks nothing. A
small built-in router that draws only 0°, 45° and 90° segments, keeps the clearance in force and lets the
copper check judge its result fills the gap, with no external tool. c0208 and c0214 moved the rest of
package 5 out of c0175; this change takes its last task.

## What Changes

- **Plugin.** `fenolite.routing.octilinear.OctilinearRouter`, registered as `octilinear` in the entry-point
  group `fenolite.routers`, with the features `pairs` and `short`. It runs no process and sends nothing
  offsite.
- **Shapes.** For each open connection (a minimum spanning tree over the pads of a net, pads already
  joined by the net's copper counting as one), on each allowed copper layer, it tries a straight segment,
  45° then straight, straight then 45°, and the two L shapes, and keeps the first that keeps the clearance
  in force to all other copper, the board edge and the holes, and makes no acute angle with copper of its
  own net. No via is placed.
- **Limits.** `--router-option max-length=LENGTH` (default 20 mm): a connection whose every shape is longer
  stays open with `route.unrouted`. `--router-option rounds=N` (default 3): the failed connections go first
  in the next round, which rips up only the copper the plugin placed in the job.
- **Pairs.** A differential pair of two pads per net is routed as two parallel tracks at the pair's gap,
  joined to its pads by short entries, or left open with `route.pair-not-routed`.
- **Checked.** The command gives the job the clearance in force (`checks.clearance`) and the copper check
  (`checks.copper.check_copper` with the project's rules) through `RoutingJob.extra`; the plugin removes
  the copper of each connection that brings a new finding (`route.check-refused`).
- **Feature `short`.** `routing.protocol.ROUTER_FEATURES` gains `short`: the router routes short
  connections, not whole boards. `fenolite capabilities` lists it.
- Two hypotheses: `H-G-OCTI-CHECK` (the plugin's copper passes the copper check) and `H-K-OCTI-DRC`
  (KiCad's DRC finds nothing new on a board it routed).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `routing`: ADDED "Octilinear router plugin" (moved from c0175 and split into "Octilinear router plugin",
  "Octilinear connections", "Octilinear shapes", "Octilinear acceptance", "Octilinear length limit",
  "Octilinear rounds", "Octilinear pairs", "Octilinear copper check" and "Octilinear codes"), ADDED
  "Clearance and copper check in job extras"; MODIFIED "Pairs and escape in a routing job" (the feature
  `short`).

c0175 no longer holds a delta of `routing`.

## Non-goals

- **Vias and layer changes.** A connection is routed on one layer that both its pads reach; a connection
  that needs a via stays open.
- **Search beyond the five shapes.** No maze or grid search: a connection that no shape reaches stays
  open (c0175's design: "for gate loops, sense pairs and the like, not for whole boards").
- **Arcs, length tuning and pair skew.** Segments only; the skew of a pair's two tracks is not tuned, and a
  `diff_pair_skew` rule is judged by KiCad's DRC (`route --gate drc`).
- **Pairs of more than two pads per net**, and pairs whose four pads share no copper layer:
  `route.pair-not-routed`.

## Evidence level required

`UNVERIFIED` for the routing result, as every router's (`routing`, "Router protocol"); `INFERRED` for the
copper check of the result (`H-G-OCTI-CHECK`); `KICAD-VERIFIED` for a board written with `--gate drc` and
no new finding, and for the benches judged by `kicad-cli` 10.0.7 (`H-K-OCTI-DRC`). The oracle tests run in
the jobs `kicad-9` and `kicad-10`.

The shape families follow the published idea of pattern routing (S-0837: routes of one or two bends tried
in a fixed order) and the round order follows rip-up and reroute (S-0838: repeated passes that route the
failed connections again). Nothing is copied from any router's code.

## Impact

- New: `src/fenolite/routing/octilinear.py`, `tests/unit/routing/test_octilinear.py`,
  `tests/_octibench.py`, `tests/kicad/routing/test_octilinear_oracle.py`. No test data file is added: the
  benches are written in the tests.
- Changed: `src/fenolite/routing/protocol.py` (`short`), `src/fenolite/routing/codes.py`,
  `src/fenolite/cli/cmd_route.py` (the job extras), `pyproject.toml` (the entry point),
  `cli/data/explain.toml`, `docs/cli-contract.md`, `docs/routing.md`, `docs/evidence/sources.md` (S-0837,
  S-0838), `docs/hypotheses.md`, `docs/evidence/matrix.md`, the guide page `routing` and the generated
  `commands`, `CHANGELOG.md`, `openspec/README.md`, and c0175's `tasks.md`, `design.md`, `proposal.md` and
  its `routing` delta (removed).
