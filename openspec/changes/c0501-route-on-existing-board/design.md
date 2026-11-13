# Design: c0501

## D1 One board input for the router: a file or a pending session

`Session.pending() -> tuple[bytes | None, list[Issue]]` runs the queued operations on a copy of the state
(`Session.apply`) and returns `State.data()`, the bytes a commit would write before its read-back, or `None`
and the issues of a refused operation. It writes nothing and leaves the queue as it is.

`fenolite.api.read_board(given)` accepts a `Session` beside a path or a `Board`. For a session it reads
those bytes with `AltiumBackend.board_from_bytes(data, file=<document name>)`. `Board.name` is the
document's name, `Board.sha256` the digest of the pending bytes, and `Board.issues` gets
`api.pending-edit` (info) with the number of queued operations. A refused queue raises `SideUsageError`
holding the session's issues. No file is written and no process runs.

c0502 adds `Session.plan()`, which also runs the queue on a copy of the base. `pending()` and `plan()` share
that one helper; whichever change lands first adds it, and the other uses it.

Rejected: an obstacle dump through KiCad (what the workaround did). It needs `kicad-cli`, converts the board
first, and loses what the conversion does not keep.

## D2 Rules from the board, not from the command line

`api.route._job(board, ...)` builds the `RoutingJob` as `cmd_route` does today, from the backend:

- `DesignRules` from `backend.design_rules` (Altium: `rules_from_bytes`, with the slack and plane handling
  of c0152 and c0124);
- the clearance in force, `ClearanceResolver(rules.design, ...)`, given to the job as `extra["clearance"]`,
  so net-class clearances and rule scopes (a high-voltage class, a rule between two named nets) are used
  per pair of items, as the copper check uses them;
- `extra["copper_check"]` from `cmd_route._job_checks`, moved out of `cmd_route` into `api/route.py` so
  the command and the API share it.

`routing` still imports no `checks` and no backend; it reads what the job gives (capability routing,
"Clearance and copper check in job extras").

## D3 Rule areas, copper graphics and kept fills in `World`

`World.__init__` gets three more sources of obstacles, all per layer in the same spatial index:

| source | blocks | clearance |
|---|---|---|
| a rule area with `no_tracks` (`model.board.rule_areas`) | a track segment that overlaps its outline on one of its layers | 0: the copper check's `copper.keepout` tests overlap (`checks.copper.FORBIDDEN_KINDS`) |
| a rule area with `no_vias` | a via barrel on one of its layers | 0 |
| a rule area with only `no_copper_pour`, `no_pads` or `no_footprints` | nothing | – |
| a copper graphic (board or footprint) on a copper layer | any track or via | the clearance in force, net `None` |
| a fill of another net's zone, when `extra["pours"] == "kept"` | any track or via | the clearance in force against a `zone` |

Altium's Keep-Out layer: the import keeps its keep-outs as graphics of `Altium.KeepOut`, not as rule areas.
A new `AltiumBackend.rule_areas(design, data)` gives each such drawing the rule area that
`convert.altium_to_kicad` makes for it: the restrictions byte from `keepout_layer_restrictions`, bit 1 vias,
2 tracks, 4 pours, 8 and 16 pads (`docs/formats/altium/pcb-records.md`, "Regions and keep-outs";
`H-A-PCBX-KEEPOUT`, INFERRED), on every copper layer; an older drawing without the keep-out flag forbids all
four, as the conversion does (c0410). The two code paths call one function, so the router and the
conversion cannot disagree. A KiCad board's rule areas are already in `rule_areas`.

`extra["pours"]` is `kept` or `refilled`. `fenolite route` keeps `refilled` (today's behaviour: a KiCad
board is filled after routing). `fenolite path` and the API use `kept` for a `.PcbDoc`, where nothing
repours the polygons of an edited document (c0463 pours only a conversion), and `refilled` for a
`.kicad_pcb`; `--pours` overrides it. With `refilled` on a `.PcbDoc` the reply holds
`route.repour-needed` (warning).

`World.blocker(net, layer, points, width) -> Blocker | None` returns the first item that refuses the
segment: `Blocker(kind, net, layer, where, clearance, shape)`, `kind` one of `pad`, `hole`, `track`,
`via`, `zone`, `graphic`, `keepout`, `edge`, `placed`. `fits` becomes `blocker(...) is None`; its result does
not change for any item it already judged.

Whether Altium's clearance rule also keeps a track at a distance from a keep-out is not known from a
source. The world follows Fenolite's own copper check (overlap), and the hypothesis row
`H-A-PCBX-KEEPOUT-GAP` (INFERRED) records the open question; task 2.3's bench is the kit case that would
settle it.

## D4 Walls and proof of a refusal

`_Graph.fits` records, for each rejected edge out of an expanded state, the blocker that refused it.
`Outcome` gets `wall: tuple[WallItem, ...]`: the blockers of rejected edges, merged by item, each with the
count of edges it refused, sorted by count then `where`, at most 12. Only `no-room` (the frontier emptied
inside the bounds) gives a wall; `state-limit`, `budget` and `cancelled` give none and the reason says the
search was cut.

`proven` is decided after the search, with exact integer geometry (`thick_gap_floor`):

1. Order the wall items around the explored area by the angle of their nearest point from the start.
2. For each two neighbours `i`, `j` (and the edge ring where the explored area meets it), the free gap is
   `gap(i, j) - c_i - c_j`, `c` the clearance in force between the net and that item.
3. The refusal is `proven` when every free gap is below the track width. Else it is `grid-limited`: a track
   may pass off the grid through the widest free gap, which is named with its two items.

`proven` is sound: if every gap of a closed wall is narrower than the track, no track crosses it. When the
ordering cannot close the wall (items far apart), the answer is `grid-limited`, never `proven`. Rejected:
calling a complete grid search a proof, which is the bug the workaround's own script had in another form.

## D5 The free channel

`routing.channel.widest(job, net, a, b, *, limits, low, high, resolution)` bisects the track width:

- start with `low` (default: the governing `track_width` rule's `min`, else 1 µm) and `high` (default: the
  distance between the two points);
- each probe is one `search` at width `w` with the same `Limits`; `found` raises `low` to `w` and keeps the
  path, `no-room` lowers `high` to `w`, a cut search (`state-limit`, `budget`) stops the bisection with
  `undecided` and the bracket as it is;
- stop when `high - low <= resolution` (default 10 µm, an explicit search bound like the grid).

The reply holds `low`, `high`, the path at `low` (checked again with `World.fits` at `low`), the `pinch`
of the last refusal (D4: its widest free gap, the two items and their clearances) and `grid_limited`. When the
last refusal is `proven`, `high` is a proven upper bound; else it is the grid's.

Vias: `--max-vias 0` (the default for the channel) keeps the channel on one layer; with vias the via size is
the net class's, as for routing.

Rejected: a medial-axis or Voronoi computation of the exact widest path. It is exact, but needs robust
Voronoi of segments and arcs in integers, which Fenolite does not have; the bisection reuses the tested
search and its bounds. Shapely is not used: `geometry` already has `thick_gap_floor`, `thick_closer_than` and
`SpatialIndex`.

## D6 Writing the found copper

KiCad: the found path is a `RoutingResult(tracks=..., vias=...)` merged with `routing.merge.apply` and written
by `write_board`, as `fenolite route --accept` writes, through `PlannedWrite`.

Altium: `RouteFound.queue_on(session)` queues, per run, one `Session.clone` of a template track per segment
(`start`, `end`, `layer`, `width`, `net`) and, per via, one `clone` of a template via (`at`, `net`). The
template track is the first track of the net on that layer, else any track (a clone on another layer takes a
record of that layer, `ops._template`). A via clone keeps its template's size, so the template via is the
first via of the net whose diameter and drill are the job's via size; with none, the outcome is refused with
`route.via-template` (error) and nothing is queued. `fenolite path` opens a session, queues, and plans the
bytes of `Session.pending()`; `--confirm --plan ID` commits them with the session's read-back and
connectivity checks (`declare_connectivity` is not called: a route of one net changes no connectivity).

When c0502's `EditPlan` exists, `fenolite path --emit-plan FILE` also writes the queued clones as an
`EditPlan`, so the route replays on a newer save of the document (c0502's rebase). Until then this is not
offered.

`clone` is behind its gate, off until Part J phase B case J12 is recorded (`H-A-EDIT-CLONE`). The command
refuses a `.PcbDoc` write without `--gate clone` (exit 2, `FEN-2001`); with it, it opens the `clone` gate
for this commit only, the reply carries the session's `INFERRED` evidence, and `route.altium-edit-unconfirmed`
(warning) says the gate is not confirmed by the kit.

## D7 The command

`fenolite path PATH --net NET --from A --to B` with `A`, `B` each `REF-PIN` or `X,Y@LAYER` (mm):

- `--width W` (search) or `--widest` (channel), exactly one;
- `--layers L1,L2` (default: the net's pads' layers and the copper layers between), `--grid` (default
  0.1 mm), `--max-states` (default 200 000), `--max-vias` (default 0 with `--widest`, 2 with `--width`),
  `--resolution` (channel), `--pours kept|refilled`, `--timeout` (whole command);
- `--dry-run` / `--confirm --plan ID` with `--width`; `--widest` never writes.

Result: `result.path` (`runs`, `vias`, `length`), or `result.refusal` (`reason`, `proven`, `wall`, `pinch`);
`result.channel` (`low`, `high`, `grid_limited`, `pinch`, `path`). Exit 0 with a path or a channel, 5 with a
refusal (`route.no-path`, warning, or `route.path-limit`, info, when the search was cut).

Decision (maintainer, 2026-11-13): `queue_on` declares the routed net's connectivity (joining islands changes
the signature); template vias match within 10 nm; a `.PcbDoc` write needs `--gate clone`, checked before the
search. The full list is in `tasks.md`, "Decisions".

## Codes

| code | severity | when |
|---|---|---|
| `route.no-path` | warning | a complete search found no path; `proven` in its detail |
| `route.path-limit` | info | the search stopped at a bound; nothing is proven |
| `route.via-template` | error | no via of the net has the job's via size to clone |
| `route.repour-needed` | warning | a `.PcbDoc` routed with `--pours refilled` |
| `route.altium-edit-unconfirmed` | warning | a `.PcbDoc` written with `--gate clone` |

## Format evidence needed

- Keep-Out layer restrictions: existing rows of `pcb-records.md` ("Regions and keep-outs"), `INFERRED`.
- New row `H-A-PCBX-KEEPOUT-GAP`: whether Altium's clearance rule keeps a track away from a keep-out it may
  not cross. Until a kit case decides it, the world tests overlap only.
- The written tracks and vias rest on `H-A-EDIT-CLONE` (pending, kit J12).

## Risks

- Bisection cost: each probe is a full search. With the default bounds a probe on a 100 mm board at 0.1 mm
  takes seconds; the channel makes at most `log2((high - low) / resolution)` probes (about 14 from 0.1 mm
  to 100 mm at 10 µm). `--timeout` bounds the whole command and gives `undecided` with the bracket.
- Wall ordering by angle can fail to close around a concave area; then the answer is `grid-limited`, which
  is honest but weaker.

## Hypotheses registered by this change

| id | statement |
|---|---|
| `H-A-PCBX-KEEPOUT-GAP` | Altium Designer's clearance rule keeps a track away from a keep-out by the rule's gap, rather than only forbidding overlap, so a route that meets the gap passes Altium's DRC |
