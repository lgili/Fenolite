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

- `freerouting` runs [Freerouting](https://github.com/freerouting/freerouting) 2.4.1, a GPL-3.0 autorouter,
  as a subprocess. Fenolite does not bundle or import it, and downloads it only when you ask:
  `fenolite fetch freerouting --confirm`. It is the only router that needs no
  KiCad file: Fenolite writes a Specctra design file of its own from the model and reads the session
  Freerouting writes back (`fenolite.backends.specctra`, [format notes](formats/specctra/dsn.md)).
  See [Freerouting](#freerouting) below.

Discover routers with `fenolite capabilities --json`; `fenolite doctor --json` checks their local
availability. Route with `fenolite route BOARD --router NAME --dry-run`, inspect the plan, then rerun
with `--confirm` to write. `--nets` may be repeated with glob patterns. Routed files from external
tools are read for copper only, then Fenolite's writer produces the board.

## Open nets, second passes and locks

**Selection.** `route` takes every net that matches `--nets`, has two or more pads and still has an
**open connection** on the board. Fenolite computes the open connections from the board itself
(`docs/analyses.md`, "Open connections"): copper that touches is joined, and what stays apart is open.
A net that already holds copper is therefore routed when it is not complete: a stub written by the
script, the tracks of an earlier run, a fan-out. A net whose pads are all joined is never given to a
router. A net that a zone carries is left out unless `--include-zone-nets` is given.

**The verdict.** After the router's copper is merged, Fenolite computes the open connections of the
selected nets again. `result.routed` holds the nets that are now closed and `result.unrouted` the others,
whatever the router said; `result.open` lists the connections that are still open, each with its two
ends and its length, and `result.connections` gives the counts before and after. When a router called a
net routed that is still open, the `route.unrouted` message says so.

**Partial copper is kept.** Copper that the router returns for a net that stays open is merged and
written, with one `route.partial` (info) per net. The second pass starts from it:

```
fenolite route BOARD --router freerouting --confirm      # some nets stay open
fenolite route BOARD --router freerouting --confirm      # selects only those nets again
```

Run `route` again until `result.unrouted` is empty, or give the router more room first. Use `--rip`
only when the copper of a net is in the way.

One case needs it with Freerouting 2.4.1: a pad whose nearest copper of its net is the **middle** of one
track. The router joins new copper to a pad or to the end of an existing wire and does not split a wire it
must keep, so that connection stays open on every pass (recorded in
[routing evidence](evidence/routing.md), "Routers on nets that hold copper"). `route --rip --nets NAME`
routes that net again from its pads; script copper can end a track where the branch should leave.

**`--require-complete`.** With this option a run that leaves a selected net open adds one
`route.incomplete` (error), writes nothing and exits 5. The reply still lists `result.open`. Run without
the option to keep the partial copper.

**Locks and `--rip`.** `--rip` removes the tracks, arcs and vias of the matching nets before the router
runs, but for two kinds of copper, which it keeps:

- copper that is **locked**: a track, an arc or a via written `(locked yes)` in the board, locked in
  KiCad's editor or by `locked=True` in the script;
- **script copper**: what `design.track`, `design.via` and `design.stitch` created, locked or not. The
  next build would create it again, over the routed copper.

`result.ripped` is the number of items removed, and `result.rip_kept` counts what was kept (`locked`,
`script`). To have such copper gone, unlock it in KiCad or remove the intent from the script. A rip that
is followed by no new copper is not written.

**Two rules for plugin authors.**

1. A router MAY return copper for a net that it lists in `unrouted`. `route` merges every valid item of
   a result, and it never removes copper because its net stays open. The `routed` and `unrouted` of a
   `RoutingResult` are the router's own claim; the verdict is the board's.
2. A router is never given a net without an open connection. A job still carries every pad of its nets
   and the design with the copper already on the board: join that copper, do not route beside it.

## Time budget, kept runs, groups and tiers

**One budget for the step.** `fenolite route --timeout SECONDS` bounds the whole routing step, whatever
the router. Without it each external router uses its own default, 900 s. The value is the budget of
the job, not of a process or of a net: every process a plugin starts gets the time that is left, and is
stopped when it is spent. `--timeout` must be a positive number; the built-in `direct` router starts no
process and ignores it.

**Finished runs are kept.** A *router run* is one process. When the budget ends:

- the copper of every run that finished is merged and written, as any routed copper;
- the run under way is stopped and gives no copper. Freerouting writes its session only when it has
  finished, and the output board of a stopped KiCadRoutingTools process may be cut, so neither is read;
- the runs never started are listed in `result.not_attempted`;
- one `route.budget-exhausted` (warning) names the budget and the counts, and the exit code stays 0.

`result.budget` gives the seconds of the budget, the seconds spent and whether it ended; `result.runs`
lists each run with its tier, its count of nets, its seconds and its outcome: `done`, `failed` or `cut`.

**Continue a cut job** with `route` again: it selects the nets that are still open ("Open nets, second
passes and locks"), so the second run spends its budget on what the first left.

```
fenolite route BOARD --router kicadroutingtools --timeout 600 --confirm   # route.budget-exhausted
fenolite route BOARD --router kicadroutingtools --timeout 600 --confirm   # the nets still open
```

A job of one run keeps nothing when it is cut. Make smaller runs with tiers or with `group-nets`, or
raise `--timeout`.

**Tiers: `--order GLOB`.** `--order` may be repeated. The nets that match the first glob are tier 0,
those that match the second and not the first are tier 1, and the nets that match none come last. A
router routes tier after tier, and the copper of earlier tiers is fixed for the later ones. `--order`
selects nothing: it orders the nets that `--nets` and the open connections give.

```
fenolite route BOARD --router freerouting --order 'CLK*' --order 'USB_*' --timeout 1800 --confirm
```

Inside a tier each tool keeps its own order of the nets.

**KiCadRoutingTools routes in groups.** One process routes one *group*: the nets of a tier that share
track width, via diameter and via drill. The tool then orders those nets and rips up among them itself;
Fenolite routed one net per process before, which was slower and left crossings on a 100-part board
([routing evidence](evidence/routing.md), "Scale"). What the plugin passes:

- every name of the group after `--nets`, the group's `--track-width`, `--via-size` and `--via-drill`;
- no `--clearance`: the tool reads each class's clearance from the project file of the temporary copy;
- `--escalation off`: the sizes stay the ones of the job. A net that does not fit is left open and
  reported, instead of being routed with a narrower track or a smaller via. `--router-option
  escalation=board` is passed after it and replaces it;
- `--no-fix-drc-settings`: the project file of the copy stays the one Fenolite wrote.

`--router-option group-nets=N` splits a group into runs of at most N nets, for smaller kept units;
`group-nets=1` gives one net per process again. The options `nets`, `output` and `overwrite` belong to
the plugin and are ignored with `route.option-ignored`. A run that fails gives `route.tool-failed` with
the names of its nets, and the next run starts.

**Freerouting sees only the nets of the job.** The design file declares the selected nets (of the tier
being routed). Every other net leaves the network section: its pads stay in the file as pins on no net,
and its tracks and vias stay as protected copper without a net, so the router spends no time on them and
still keeps clear of them. One kind of net stays declared: a net whose class clearance is larger than
the board's default rule, because the router keeps only the default rule from copper without a net and
KiCad would report a clearance violation (measured: [routing evidence](evidence/routing.md),
`dsn-netless`). `route.net-declared` (info) names those nets; Freerouting may route them too, and that
copper is not taken.

**Freerouting's optimizer is off.** The plugin passes `--router.optimizer.enabled=false`: the session is
written as soon as the autorouter ends. With the optimizer on, Freerouting writes nothing until the
optimizer ends, and a run that reaches the budget before that leaves no copper at all.
`--router-option optimize=on` runs it afterwards: a second run of the same design file with the
optimizer, on the time that is left. Its session replaces the first when it ends in time; otherwise the
first is kept and `route.optimizer-cut` (info) says so. That second run routes the nets again before it
optimizes, and it is not offered together with `--order`.

## Plane layers and plane fan-out

A copper layer of the KiCad row type `power` is a plane layer, and a net with a zone on one is a plane net
(change c0107). `design.board(planes=…)` sets the type in a build; KiCad's board setup sets it too.
`fenolite route` then works in three steps:

1. **Plane nets leave the selection.** A plane net is never given to a router, also with
   `--include-zone-nets`: a router cannot bring a pad to a plane on a `power` layer (`H-G-DSN-PLANE`), so it
   would trace the net on the surface. Each plane net that `--nets` selects gives `route.plane-net`.
2. **Plane fan-out.** Each SMD pad of a selected plane net gets one short track and one through via
   (`backends.kicad.fanout.plan_fanout`), unless `--no-plane-fanout` is given. The copper is merged before
   the router runs, so every router sees it as existing copper, and it is written also when no net goes
   to a router. `result.plane_fanout` counts it.
3. **Routing layers.** A net's tracks may use the copper layers that are not plane layers and that no
   `no_tracks` rule forbids to it (`routing.layers.allowed_layers`; `JobNet.layers`). A net left with no
   layer gives `route.no-layer`.

The fan-out search is deterministic. Pads are taken in board footprint order, then pad order.

- **Joined pads are skipped**: a via of the net overlaps the pad's copper, or a chain of the net's tracks
  and arcs on the pad's layer leads from its copper, through equal end points or ends inside another pad
  of the net, to a via of the net or to a through-hole pad of the net. Copper made earlier in the same run
  counts, so a pad tied by a track to a fanned-out pad gets no second via.
- **Sizes** are the net's: track width, via diameter and drill from its class, else the project's
  `Default` class, else 0.2 mm, 0.6 mm and 0.3 mm. The neck between the via and its own pad is the net's
  clearance.
- **Candidates.** The eight directions at multiples of 45° are tried in the order of their angle to the
  outward direction, from the footprint's position to the pad's. Along each, the step is a quarter of the
  via diameter, rounded up to a whole micrometre; the first distance is the smallest multiple at which the
  via keeps the neck from its pad, and eight more follow. Via centres lie on whole micrometres.
- **Tests**, exact in integers: the via keeps the clearance in force (the copper check's
  `ClearanceResolver`, over the project's classes and rules) from every copper item of another net on
  every copper layer, pads and holes included; it overlaps no other pad of its net and no other via; it
  lies inside the outline of a zone of its net on a plane layer by at least half its diameter; it keeps
  the edge clearance from every outline ring and lies on the board; it touches no keep-out that forbids
  vias; its drill keeps a board-wide `hole_to_hole` rule from every other drill. The track keeps the
  clearance in force on the pad's layer and crosses no keep-out that forbids tracks there. Zone fills are
  not obstacles: run `fenolite fill` after routing.
- **A pad without room** stays open with `kicad.fanout.failed`, which names the pad, the net and what
  blocked the first candidate. Move the part, or join the pad in the script.

The fan-out via takes the board's default via protection, as every via without its own values does
(`docs/lens.md`, "Via protection across rebuilds"). It is routed copper: a later build keeps it, `--rip`
on its net removes it and makes it again, and locked copper stays (`--rip` keeps locked items).

This is not Freerouting's own fanout stage, which makes escapes for signal pins and stays enabled: that
stage added no via to a plane in any measured run.

### What each router is given

| | plane layers | layers of a net | rules of the design |
|---|---|---|---|
| `direct` | takes the first shared layer that is not a plane layer | and that is in the net's layers | none: it checks nothing |
| `freerouting` | `(type power)` and one `plane` per zone | `use_layer` in the net's class, split by layer set | class clearances, `class_class`, widths, `layer_rule`; the rest is reported (`specctra.rule-not-sent`, `specctra.rule-widened`) |
| `kicadroutingtools` | not told (`route.constraint-not-sent`); its board file holds the row types | not told; its rules file holds the `disallow track` rules | its rules file holds them (`H-K-KRT-PLANES`: on the plane bench of 2026-10-08 the tool used `F.Cu` only, with and without them, so it is not settled) |

The rules the design file cannot carry: a rule on single nets, references or item kinds, a glob, a `not`,
every kind other than `clearance` and `track_width`, and the edge clearance. Keep-out bands along the board
edges were measured and not adopted: they kept the edge clearance where the board left room and lost the
route in a 2 mm passage (`H-G-DSN-EDGE-2`). KiCad's check judges the routed board for all of them.

Measured on 2026-10-05 with Freerouting 2.4.1 on a generated board of 100 parts with two inner planes, its
83 plane vias made by hand, the inner layers written `power` and one plane per zone: with the optimizer off,
no unrouted connection in 365 s, 1133 tracks and 170 vias, none on a plane layer and none added to a plane
net; `kicad-cli` 10.0.6 after a refill reported no unconnected item and no violation of severity error.

## The job record

A long route does not start over when it is stopped. `fenolite route` keeps the copper of each router
process that finished in the state folder (`jobs/<key>/` under `~/.cache/fenolite/state`, or the folder
that `FENOLITE_STATE_DIR` names; `off` keeps nothing), one file per finished run, written as the run
ends.

- **What is kept.** The tracks, arcs and vias that one tool process added, and the nets it routed: one
  process per group of nets for KiCadRoutingTools, one per tier for Freerouting ("Time budget, kept
  runs, groups and tiers"). A process that failed, was cut by the budget or gave no copper is not
  recorded, so its nets are routed again. The built-in `direct`
  router starts no process and records nothing.
- **The key.** The first 16 hex digits of the SHA-256 of the Fenolite version, the router's name and
  version, the SHA-256 of the board, of its project file and of its rules file, and the route arguments without the run
  flags (`docs/cli-contract.md`, "Staged plans") and without `--out`. Another board, another router or
  another `--nets` is another job.
- **When it is reused.** The same call made again reads the board, applies `--rip`, makes the plane
  fan-out again (the same copper, since the board is the same), merges the recorded copper and only then
  selects the nets with an open connection, so the recorded nets are not routed
  again. The reply holds one `route.resumed` info and `result.resumed` (`runs`, `nets`). A record that
  cannot be read is removed, and the route starts from the board.
- **When it is removed.** After a confirmed write of the routed board (the board then holds the copper,
  and its digest names another job), and after a dry run that attempted every selected net, whose plan
  holds the board. It stays after a dry run that the budget cut or that reports an error, so the same dry run goes on, after a
  stop by a signal (`FEN-1003`), after a failed write (`FEN-1002`) and after a run whose errors wrote
  nothing. At most 8 records are kept, and none older than 7 days.

Copper made in two calls need not equal the copper of one call: the router sees the reused copper as
existing copper. KiCad judges the board as always (`fenolite check`). With `--progress`, each router
process is one unit of the progress records on stderr.

## Freerouting

**Install.** Let Fenolite fetch the pinned jar:

```
fenolite fetch freerouting --dry-run
fenolite fetch freerouting --confirm
```

- `--dry-run` shows the file, its size, its SHA-256, its address and its licence (GPL-3.0), and makes no
  request. `--confirm` downloads `freerouting-2.4.1.jar` from the project's release page, checks its size
  and its SHA-256 against the values recorded in [routing evidence](evidence/routing.md), and writes it
  only when both match. No other command downloads anything
  ([ADR-0007](adr/0007-fetching-external-tools.md)), and no design data is sent.
- The jar goes to the **tools folder**, outside your project, where `route --router freerouting` finds it:

  | platform | folder |
  |---|---|
  | any, when `FENOLITE_TOOLS_DIR` is set (an absolute path) | that folder |
  | any, when `XDG_CACHE_HOME` is set | `$XDG_CACHE_HOME/fenolite/tools` |
  | macOS | `~/Library/Caches/fenolite/tools` |
  | Windows | `%LOCALAPPDATA%\fenolite\tools` |
  | elsewhere | `~/.cache/fenolite/tools` |

  The jar is `freerouting/freerouting-2.4.1.jar` in it. It is a cache entry: delete it and fetch it again.
- On a machine without a network, download the jar another way and run
  `fenolite fetch freerouting --from FILE --confirm`: the same size and digest are checked.

**Install by hand** (the second way). Download `freerouting-2.4.1.jar` from the project's release page
yourself, check its SHA-256 against the one the release lists (recorded in
[routing evidence](evidence/routing.md)), keep it outside your project, and set `FENOLITE_FREEROUTING_JAR`
to it, or pass `--router-path JAR`. Both win over the tools folder.

Freerouting 2.4.1 needs **Java 25** or newer: `java` on `PATH`, or `FENOLITE_JAVA`. `fetch` does not
install it. `fenolite doctor --json` reports the jar, where it came from (`source`: `argument`, `env` or
`fetched`), its version and the Java major in the `freerouting` entry of `result.routers`.

**Run.**

```
fenolite route BOARD --router freerouting --allow-offsite --dry-run
```

- The board needs a closed outline: a design file cannot be written without one.
- Every component is written locked in place, and the copper already on the board is written as protected;
  the router adds copper and removes none. Only the copper of the selected nets is taken from its session.
- `--router-option max-passes=N` sets the number of autorouter passes (default 20), and
  `--router-option optimize=on` adds the optimizer run. `--timeout SECONDS` is the budget of the whole
  step (default 900 s; "Time budget, kept runs, groups and tiers"). No other option is passed on.
- The route is a proposal (`UNVERIFIED`): run `fenolite fill` and `fenolite check` afterwards.
- Net-class widths, clearances and vias reach the router; custom rules of the model do not, so KiCad's DRC
  stays the judge of every route.

**Data leaving your machine.** Freerouting sends anonymous usage data unless told otherwise. Fenolite always
passes the flag that disables it (`-da`), runs the tool in a temporary folder that is also its `HOME`, and
never uses its hosted API. A run of the pinned image with the network disabled routes a board
(`H-G-DSN-OFFLINE`, recorded on 2026-10-04), so `fenolite capabilities` lists this router with
`sends_data_offsite: false` and `fenolite route` does not ask for `--allow-offsite`.


**Net classes and open connections.** `fenolite route` reads the net classes from the project file beside
the board (a KiCad board holds none), so each net is routed with the track width, clearance and via size of
its own class. Which nets are `routed` and which `unrouted` is read from the board after the merge
("Open nets, second passes and locks"), not from Freerouting's output; run `fenolite check` afterwards,
where KiCad's DRC is the judge.

`--router-path docker:<image>` runs a container image of Freerouting instead of a local
jar, with the run folder mounted and `--network none`; Fenolite never pulls the image.

## Differential pairs and escape

Three steps carry the word fan-out or escape, and they differ. The **plane fan-out** of `route`
("Plane layers and plane fan-out") is Fenolite's own: one short track and one via from each SMD pad of a
plane net to its plane. **Freerouting's fanout stage** is a step inside Freerouting that escapes SMD pins
before its autorouter runs; `--router-option fanout=off` turns it off. **Escape** (change c0110) is a
step per part that a router runs before it routes, asked for with `--escape REF[=grid|perimeter]`; no
registered router declares it today, so each request gives `route.escape-skipped`.

**Pairs.** `route` pairs two selected nets by KiCad's name rule (`model.pairs`, `H-K-DIFFPAIR-NAMES-2`):
the same name except for a polarity character `P`/`N` or `+`/`-`, followed in both by the same run of
digits and underscores. A pair goes to the router when both nets are selected, share a class, and the
class (or the `Default` class) holds a pair width and gap (`diff_pair_width`, `diff_pair_gap`); the
`max` of the `diff_pair_skew` rule that governs the pair is its skew limit. Otherwise its nets are left
out with `route.pair-skipped`: half a pair routed alone, or a pair routed as two single nets, is
uncoupled copper. `--pairs-as-nets` routes them as single nets on purpose (`route.pair-uncoupled`).

**Features.** A router lists what it takes beyond single nets in `features` (`fenolite capabilities`):
`pairs` and `escape`. `direct` and `freerouting` list none: Freerouting 2.4.1 routes a pair as two single
nets, with or without a `pair` list in the design file (`H-G-DSN-PAIR`), so Fenolite writes no such list.
`kicadroutingtools` lists `pairs`: one `route_diff.py` process per pair, at the pair's width and gap,
without ground vias or polarity swaps, before the single nets of its tier. The gate of change c0110
routed both pairs of its bench coupled, with no unconnected item and no gap or uncoupled finding, under
KiCad 9.0.9 and 10.0.6 (`H-K-KRT-PAIR`). It does not list `escape`: on the gate's BGA bench its dog-bone
escape (`bga_fanout.py`) left more connections open than routing without it and put vias in pads, while
on the QFN bench `qfn_fanout.py` closed every connection (`H-K-KRT-ESCAPE-2`); the escape steps stay in
the plugin, undeclared, so `route` gives it no escape request. The tool
pairs fewer names than KiCad: `X_P`/`X_N`, `X_P0`/`X_N0`, `X+`/`X-` and `X_DP`/`X_DN`, not `DP1`/`DN1`
(`H-K-KRT-PAIRNAMES`); another form gives `route.pair-skipped`. The router options
`polarity-swap-nets`, `impedance`, `rip-existing-nets` and `force-reroute` never reach the tool.

**Judging a pair.** KiCad counts as uncoupled every segment outside the range of the `diff_pair_gap`
rule that governs it, and without a gap rule it counts far parallel segments as coupled
(`H-K-DRU-PAIRCOUPLE`). Give `pair(gap_min=…, gap_max=…, uncoupled_max=…)` together, so that a pair
routed apart is reported.

**Escape kinds.** A part is a `grid` (a BGA) when one of its surface pads has neighbours at the part's
pitch on two orthogonal directions, both ways, and a `perimeter` (QFN, QFP, SOIC) otherwise; the suffix
of `--escape` overrides it. Dog-bone vias of a BGA sit between balls: a via in a pad needs a filled and
capped via. With 0.1 mm clearance and a 0.4/0.2 mm via, a track passes 0.2 mm from a via's hole, so a
board with such a BGA needs a `hole_clearance` rule below KiCad's default of 0.25 mm.

**Narrow copper.** Freerouting always runs with its automatic neck-down off
(`--router.automatic_neckdown=false`), which narrowed wires at pins below their class. Its fanout stage
still wrote wires of 0.1124 mm under a 0.15 mm class at QFN pins on a board with inner signal layers
(`H-G-DSN-NARROW`); `route` reports any copper narrower than asked with `route.width-below-job`, whose hint
for Freerouting names `fanout=off`.

**Limits.** A pair needs two selected nets of one class with pair values; a leg may be 0.4 µm narrower
than asked; the tool may leave skew, which KiCad's `diff_pair_skew` rule reports; per-part escape is not
declared by any router (Freerouting's fanout stage, on by default, is the escape it has: on the gate's QFN
and BGA benches it left fewer connections open with the stage than without, `H-G-DSN-FANOUT-2`). No model field and no schema change come with pairs or escape.

## Loop order

Use `build` → `place` → `route` → `fill` → `check`. Routing changes copper inputs used by a fill, so
refill after routing. Later builds keep routed tracks and vias whose nets remain in the design.

## Tool smoke job

The optional `routing` CI job runs the pinned tool and oracle smoke tests on KiCad 9.0.9 and 10.0.6.
It downloads external code and a router binary, so it is informative evidence rather than a required
merge check. It runs the feasibility probes and the `build` → `place` → `route` → `fill` → `check`
loop on each target. It also installs Java 25 and the pinned Freerouting jar, checked against its SHA-256,
and runs the Freerouting probes and the same loop with `--router freerouting`.
