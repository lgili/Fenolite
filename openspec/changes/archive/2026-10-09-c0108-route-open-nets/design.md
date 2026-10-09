## Context

**Scope.** Milestone v0.4 (`docs/roadmap.md`, "v0.4: proposals on other branches", row c0108 `route-open-nets`; called v0.2c until c0136 renamed the milestones on 2026-10-07): `route` selects by open connections, so a second pass and script copper can share a net; locked tracks and vias; an option that fails on open nets. It answers two gaps of the review of 2026-10-05: a net with any copper is never routed and copper cannot be locked, while `--rip` removes everything; and nothing happens when nets stay open. A second check of the review added that copper returned for nets reported open is lost without an issue. Bordering rows: c0107 (plane nets, fan-out before the router), c0109 (order, time and partial sessions of the two plugins; it depends on this change), c0110 (pairs and escape), c0111 (script copper in a part's frame), c0120 (report limits, `--confirm`, failed writes), and c0066 (the `net` view and paging, archived).

**What exists** (checked on `origin/dev` at `9aba2dff`, 2026-10-07; `routing/select.py`, `cli/cmd_route.py`, `model/board.py` and the two plugins have not changed since the proposal was first written):

| where | what |
|---|---|
| `routing/select.py:33` | `unrouted()` keeps a net with two or more pads and no track, arc or via of its own; a zone net only with `include_zone_nets` |
| `routing/select.py:41-58` | `rip()` keeps an item when `getattr(item, "locked", False)` is true; `Track`, `Arc` and `Via` have no such field (`model/board.py:193-220`), so it removes all copper of the nets |
| `cli/cmd_route.py:174-206` | the selection; with `--rip`, every matching net with two or more pads is ripped, then selected again |
| `cli/cmd_route.py:275-277`, `:296` | `route.unrouted` comes from the router's list; the board is written only when `outcome.routed` is not empty |
| `routing/plugins/kicad/routingtools.py:212-218` | a net that got any copper is `routed` |
| `routing/plugins/specctra/freerouting.py:348-356` | a net with copper is `routed` unless Freerouting's output names it (`H-G-DSN-INCOMPLETE`) |
| `backends/kicad/pcb.py:176-198`, `:1763-1765` (`TRACK_FIELDS`, `VIA_FIELDS`, `CANONICAL_ORDER`); `docs/formats/kicad/board.md`, model table | `locked` of a segment, an arc or a via is an opaque child, written back where it was |
| `analysis/copper.py:98` | `net_copper()`: the thick shapes of every net, the copper check's shapes (c0047) |
| `cli/cmd_net.py` (c0066) | the net view "never says whether it is connected" (c0066, Non-goals) |
| `cli/main.py:299-308` | a write under `--confirm` happens before the exit code is chosen; a command that reports an error plans no write, by convention |
| `dsl/intents.py:76-108`, `dsl/design.py:625-670`, `backends/kicad/copper.py:897`, `:932` | script copper has no lock; `merge_copper` compares points, sizes, layers, via type and net (`_fields`) |
| `checks/equivalence/routing.py:375-398`, `:421` | `_joined` and `pieces()` (c0089, archived 2026-10-07): the connected pieces of each net, joined by `thick_touch` over a `SpatialIndex`; pads shaped from the model alone, fills join, no open connection and no anchor. The module may import `core`, `model`, `geometry` and `checks`; `analysis` may not import `checks` |
| `backends/altium/pcbrecords.py`; `altium-pcb-writer`, "PCB units and record framing" | every primitive is written with the flag bytes `0x0C 0x00` (unlocked) |
| `backends/altium/read/pcbprims.py:91`; `docs/formats/altium/pcb-read.md`, row `Prefix.locked`; `pcb-copper.md`, rows of the track and via flags | the reader yields `Prefix.locked` (bit 2 of the first flag byte clear; S-0160, S-0150; `INFERRED`); the import maps it for a component and drops it for a track, an arc and a via |
| `backends/kicad/netnames.py:19` | a built board holds one net `unconnected-(…)` per pin on no net (c0061), each with one pad |

**Measured on 2026-10-05.** The probe scripts, command lines and outputs are kept with the change's working notes and are not committed; each becomes a recorded probe or test below. `kicad-cli` 10.0.6 is the local macOS application, run as `kicad-cli pcb drc --format json --severity-all -o <report> <board>` and `kicad-cli pcb upgrade --force <board>`; 9.0.9 is the pinned image, one container per run: `docker run --rm --platform linux/amd64 -v <folder>:/p -w /p -e HOME=/tmp kicad/kicad:9.0.9@sha256:e638b79b… kicad-cli pcb drc --format json --severity-all -o <report> <board>`. Benches are built with `tests/kicad/rules/_rulebench.Builder` and written with `write_board`; the prototype of the query is a script on `net_copper` and `thick_touch`.

1. *The defects* (no tool; the code paths are unchanged on `9aba2dff`). `unrouted()` returns `("ROUTE_ME",)` for `tests/data/kicad/routing/two_pads.kicad_pcb` and `()` once a 3 mm track leaves `J1-1`. That track, written with `(locked yes)` after `width`, is read without a lock field, kept by a read and a write, and removed by `rip()` (count 1). A test router that returns one track and lists its net as unrouted: `route --confirm` exits 0 with `tracks: 1`, `routed: []`, no receipt, the board unchanged, and one `route.unrouted` warning.
2. *Lock forms.* Census of the 25 corpus boards cached that day: 7 locked segments and 5 locked vias, all on one board of format 20241229 (written by KiCad 9), all `(locked yes)`, in the orders `start end width locked layer net uuid` and `at size drill layers locked net uuid`; no locked arc, no bare `locked` atom. On 10.0.6, a lock written as the first child of a segment, an arc and a via is re-saved by `pcb upgrade --force` after `width` (segment, arc) and after `layers` (via), uuids kept; an unlocked item gets no `locked` child; the DRC result does not change (1 unconnected item, the same violation types). On 9.0.9 the target-9 bench loads with the lock first or after `width` and `layers`, with the DRC result of the bench without locks. 9.0.9's `kicad-cli` has no `pcb upgrade`, so its own place for an arc's lock is not observed.
3. *Connectivity parity*, one net per case, 0.25 mm tracks, `unconnected_items` of the net:

   | case | 10.0.6 | 9.0.9 | prototype |
   |---|---|---|---|
   | two pads, no copper | 1 | 1 | 1 |
   | a track from pad to pad | 0 | 0 | 0 |
   | a 3 mm stub from one pad | 1 | 1 | 1 |
   | two tracks from the pads that cross at 70 % of their length | 0 | 0 | 0 |
   | a track across the far pad, ending 2 mm beyond it | 0 | 0 | 0 |
   | two parallel tracks overlapping by 0.05 mm, no end inside the other | 0 | 0 | 0 |
   | a track ending on another's centre line; 0.1 mm off it; 0.2 mm off it (the end cap overlaps) | 0, 0, 0 | 0, 0, 0 | 0, 0, 0 |
   | pads joined, plus a floating track of the net | 1 | 1 | 1 |
   | F.Cu, via, B.Cu, via, F.Cu; the same without the second via | 0; 1 | 0; 1 | 0; 1 |
   | an arc from pad to pad | 0 | 0 | 0 |
   | a stored fill covering both pads; a fill between them touching neither | 0; 1 | 0; 1 | 0; 1 |
   | three pads, two of them joined | 1 | 1 | 1 |
   | pads joined, plus a fill island holding a floating track; plus a lone via | 1; 1 | 1; 1 | 1; 1 |
   | a fill touching one pad, the other pad alone | 1 | 1 | 1 |

   KiCad joins copper that touches, wherever it touches. It counts an island without a pad when the island holds a track or a via, and not an island of fill alone. It names the nearest items of two islands, track ends and zones included: "Track … length 3.0000 mm" and the far pad for the stub; the two tracks, 0 mm apart, without the second via; the zone in the last case. A first prototype that ignored islands without a pad differed on the floating track.
4. *Scale*: the filled 4-layer boards of the review's scale probe. 128, 260 and 452 open connections at 100, 200 and 400 parts, equal to the `unconnected-items` that `check` recorded with 10.0.6; 644 at 600 parts, where KiCad's report stops at 499. The query took 0.08 s to 0.85 s; reading the board took 0.6 s to 4.2 s.
5. *Corpus*, 10.0.6, on the manifest of 2026-10-05 (not counted again on `dev`; task 1.4 does): the count per net equals KiCad's on 20 of 21 readable boards (148 open connections on one, 1 on another, 0 on the rest). The 21st has two filled `gr_rect` on `F.Cu` holding `(net 1)`, which join the four shield pads of a connector: KiCad counts them as copper, while the model keeps a drawing's `net` as an opaque child, so the prototype reports 2 open connections. The query took 0.02 s to 9.4 s per board on a loaded machine; a second run on the three largest took 2.6 s to 3.5 s, of which the nets without a zone took 0.4 s to 0.9 s and the zone nets the rest.
6. *Freerouting 2.4.1 on nets that hold copper* (the plugin called directly, as today's selection skips them), 8 nets of 7 kinds: a stub; three pads, two joined; a fan-out of a track, a via and a B.Cu stub (twice); the same without the stub; a track to a via 1 mm from the pad, towards the other pad; the same 3 mm from it; a via with a B.Cu stub joined to nothing. All 8 nets closed, by wires that join the existing copper (the stub's end, not its pad); the prototype and `kicad-cli` 10.0.6 found 0 open connections after the merge. A first run whose parts lay outside the board outline left those nets open with no reason given; it was rerun with the outline around them.
7. *Fixtures*: `tests/data/kicad/board/two_layer.kicad_pcb` has one open connection, on `LED_A`, between `D1-2` and the end of the arc (10.0.6 names "Track (arc) [LED_A]" and "PTH pad 2 [LED_A] of D1"); `two_pads.kicad_pcb` has one, `J1-1` to `J2-1`, 10 mm.

Not measured: KiCadRoutingTools on nets that hold copper (no checkout here: `H-K-KRT-PARTIAL`); the corpus census and the scale boards on 9.0.9; a router judged by 9.0.9.

## Goals / Non-Goals

**Goals**
- A second `route` completes what the first left open, next to script copper and earlier routes, without a rip.
- `route` says, from the board and not from the router, which nets stay open and between which items, and can be made to fail.
- Copper locked in KiCad survives a rip; script copper is never ripped.
- An agent can ask which connections are open without running KiCad.

**Non-Goals**
- Everything under "Non-goals" in the proposal.
- Changing what the three routers do with a job: nowhere, because a job still carries every pad of its net and the routers already join the copper on the board (measurement 6); how they run is c0109's.

## Decisions

1. **The query reads the board model, in `analysis`.** `analysis.connectivity.connectivity(design, *, pads, nets=None)` works on the shapes of `net_copper`, which are the copper check's, with the `BoardPad` records that `net` and `analyze` already pass. Rejected: KiCad's DRC before and after each run: a tool on every `route`, 1 s to 12 s per corpus board, a report that stops at 499 items, and a DRC that does not repeat on large boards. Rejected: the query in `routing`, which may not import `backends.base` and whose `JobPad` has no copper.
   - **One union of touching copper.** `dev` gained `checks.equivalence.routing.pieces` (c0089) after this proposal was first written. Its joining step (`_joined`: a union-find over the pairs of a `SpatialIndex`, joined by `thick_touch`) is the step this query needs. It moves to `geometry.touch_groups(items)`, which both import (`geometry` is below `analysis` and `checks`), and `pieces` calls it with no change of result. What stays apart is what differs by purpose: `pieces` shapes a pad from the model so that a KiCad and an Altium design compare, joins fills and sums lengths; the query takes the pad copper of the KiCad frame, which is what KiCad's DRC judges, keeps fill-only islands out and finds anchors. A test (`-k agree`) holds the two to the same islands where their shapes are the same.
   - Rejected: the query calling `pieces`. `analysis` may not import `checks` (`package-layering`), a `Piece` has no anchor, and its pad shapes are supersets (a rectangle for a round-rect), which can join what KiCad leaves open.
   - Rejected: two unions and only the agreement test. Two copies of one step drift; c0106 (lengths) and the connectivity stage split out of c0120 would be a third and a fourth caller.

2. **Copper joins where it touches.** Two shapes of a net on one copper layer join when `thick_touch` is true, exactly, on integers; the shapes of one via, and of one pad, join across their layers; fill polygons are separate shapes, so two islands of one zone stay apart. KiCad joins crossing tracks, a track across a pad, tracks side by side and an overlapping end cap (measurement 3). Rejected: joining only where an end lies inside the other item, which those cases refute.

3. **What counts as an island.** An island counts when it holds a pad, a track, an arc or a via; an island of fills alone is reported as `fill_islands` and joins nothing. KiCad counts a floating track and a lone via, and not a fill that touches nothing (measurement 3). Rejected: pads only (the floating track); every island (the lone fill).

4. **Open connections form a minimum spanning tree of nearest anchors.** Anchors are a pad's position, the two ends of a track or an arc, and a via's position; fills have none. Between two counted islands the edge joins their nearest anchors by exact squared distance; ties go to the smaller pair of `where` texts, then of positions. Kruskal's algorithm gives `islands − 1` connections, whatever the order of the items on the board. Each connection holds its two ends (`kind`, `where`, `position`, `layers`) and `length`, the straight distance rounded with `isqrt`. Rejected: pairs of pads only, which hide a missing via that shows as two tracks 0 mm apart. Rejected: reproducing KiCad's choice of items, which also anchors zones and breaks ties its own way; `H-K-CONN-PARITY` claims the counts, which are what the selection needs.

5. **Selection by open connections.** `routing.select.unrouted(design, open_nets, *, patterns=("*",), include_zone_nets=False)` takes a net with two or more pads and at least one open connection; the zone and pattern rules are unchanged. The command computes `open_nets` after `--rip` and after any copper it adds before the router (c0107's fan-out), so a router never gets a closed net. A net of one pad is never selected and never open: the `unconnected-(…)` nets of a built board (29 on the blink) show in `fenolite net` with `islands` 1 and `open` 0. Rejected: keeping "no copper" when `open_nets` is missing (two rules under one name); a second function beside `unrouted` (two selection rules in the public API); every matching net (routers would add copper to closed nets).

6. **Locks.** `Track`, `Arc` and `Via` gain `locked: bool = False`. The reader maps `(locked yes)`; the writer writes it after `width`, or after `layers` for a via, for both majors, and nothing for an unlocked item (measurement 2). `rip(design, nets, *, keep=frozenset())` removes the tracks, arcs and vias of `nets` that are not locked and whose id is not in `keep`; the command passes the ids of script copper (`is_copper_uuid`). A script sets `locked=True` on `Design.track`, `via` and `stitch`; script copper is unlocked by default. Rejected: script copper locked by default: every board with script copper would change bytes on its next build and every script track would become read-only in KiCad's editor, while the copper uuid already keeps it out of a rip. Rejected: ripping script copper, which the next build creates again over the routed copper.

7. **The verdict is taken after the merge.** `route` computes the open connections of the selected nets again on the merged design. `routed` holds the selected nets now closed, `unrouted` those still open, `result.open` their connections, and `result.connections` the counts over the selected nets before and after. A router's lists no longer decide; when it called an open net routed, the `route.unrouted` message says so. Rejected: trusting the routers' lists, since KiCadRoutingTools calls routed any net that got copper.

8. **Copper of open nets is kept.** What the router returns for a net that stays open is merged and written, with `route.partial` (info) naming the net and the count. The command plans a write when it added a track, arc or via, merged from the router or added before it (c0107's fan-out), when no error was reported, and when the text changed or `--out` was given; `fills_stale` and `route.fill-stale` follow the same test instead of "a net was completed". A rip that is followed by no new copper is therefore not written. Rejected: dropping that copper, since a second pass starts from it (measurement 6) and `--rip` on that pass removes it when it is in the way. Rejected: an option to drop it, which is what `--rip` already does.

9. **`--require-complete`.** When a selected net is still open after the merge, the command adds one `route.incomplete` (error) with the count and the first five net names, plans no write, and exits 5. Without the option nothing else changes: `route.unrouted` stays a warning. Rejected: writing the partial board and exiting 5, because a command that reports an error writes nothing today and c0120 makes that an invariant. Rejected: raising `route.unrouted` to an error, because a code has one severity ("Routing issue codes").

10. **`net` says what is open.** Each row of `result.nets` gains `islands` and `open` (a count); `result.net` gains `islands`, `fill_islands` and `open` (the connections). This reverses c0066's non-goal "no connectivity in `net`", written while the only connectivity was KiCad's. Rejected: a `ratsnest` command, a second view of a net; `route --dry-run` as the query, which runs the router.

11. **Codes and keys.** `routing.codes.ISSUE_CODES` gains `route.incomplete` (error) and `route.partial` (info); "Routing issue codes" asks for "at least" its list, so it is not modified. `result` of `route` gains `open`, `connections` and `rip_kept` (`locked`, `script`), and `route` declares `paged = "open"` (c0066, "Paged results"). The query reports `analysis.item-unsupported` for items it could not shape, as every analysis does. Rejected: modifying "Routing issue codes" to list the two codes, since c0107, c0109 and c0110 may add codes too and a list of "at least" needs no edit.

12. **Order with other changes** (checked on `origin/dev` at `9aba2dff`, 2026-10-07; task 0.1 checks again).
    - "Net selection" and "Route command": the living text is what it was on 2026-10-05 and no open change on `dev` holds a delta of either. Both deltas are generated from it. Among the proposals of v0.4, c0109 modifies "Route command" and depends on this change: this change lands first and c0109 regenerates from its archived text. c0107 adds its own requirement ("Plane nets in the route command") and lands after.
    - "PCB units and record framing": no open change on `dev` modifies it; the delta is generated from the living text. "Via records" is modified by c0085 and c0128, both open on `dev` and part of `0.3.0`: they land first, and task 0.1 regenerates this delta from their archived text (the blind and buried spans of c0085, the full-drill option of c0128) with the one change of this proposal, the flag byte and the `locked` argument. c0112 (tenting bits in the same flag byte, decision 7 of 2026-10-07) lands after this change and regenerates from its text.
    - The import's "Tracks, arcs and vias" is modified by c0124 and c0132 (open on `dev`); this change adds "Copper locks from an Altium board" beside it and copies none of its text.
    - "Modelled board content" is modified by c0101, c0103 and c0112; this change adds "Copper locks on boards" beside it instead. c0112 also adds `Via.protection` and its children of a via: the second of the two to land puts its field after the other's, regenerates the board schema and re-bases `VIA_FIELDS` and `CANONICAL_ORDER["via"]`, as c0112's design says too.
    - c0111 adds anchored points to script copper and modifies "Stitching vias"; its intents take `locked` as the others do.
    - c0068 modifies "Copper intents in the DSL", "Tracks from intents", "Single vias" and "Script copper is regenerated", and c0074 "Stitching vias"; this change adds "Copper locks in the DSL" and "Locked script copper" instead, so neither re-bases.
    - c0066 ("Net command", "Paged results") and c0068 are archived: "Open connections in the net command" adds keys to living rows, and `locked` comes after `kind` and `layers` on the intents.
    - c0096 gives `Part.place` a `locked` argument: the lock of a placed part, written on the footprint. It shares the word with this change's copper lock and no field.
    - c0069 modifies "Copper items follow their nets": a kept item keeps every field, `locked` included, so nothing changes there.
    - Rejected: modifying "Modelled board content" and the requirements of c0068, which would make this change re-base on three open changes for one field each.

13. **Locks in the second backend** (decision 8 of the maintainer, 2026-10-07: the Altium build writes the locked bit of a locked track or via; the format fact from a public source first).
    - **The fact.** `dev` already records, for reading, that bit 2 of the first flag byte of a primitive's common prefix is set when the primitive is unlocked (`docs/formats/altium/pcb-records.md`, the row of the flag bytes; `pcb-read.md`, row `Prefix.locked`; S-0160, KiCad's importer, facts only, and S-0150). What is missing is the write-side row per record kind: that a free track, a free arc and a via written with that bit clear, and every other byte as today, is a locked primitive. Task 4.4 writes those rows into `pcb-copper.md` before any writer code: one per kind, each with the source that states the bit for that record kind and the label `INFERRED`, and registers `H-A-PCB-CU-LOCK`. If S-0160 does not state it for a kind, another public source is registered as `S-0661` (reserved), or the kind gets no row.
    - **Never silent.** `pcbrecords.LOCK_WRITTEN` is the set of kinds with a row. Task 4.1, which adds the model field, also adds the set, empty, and the build's warning (`altium.not-lowered`, `where` `copper/locked`) for every locked item of a kind outside it; task 4.5 fills the set from the page and writes the bit. So from the first commit in which a locked track can reach an Altium build, it is either written locked or named in a warning, and a kind whose fact cannot be sourced stays at the warning for good.
    - **Reading.** The import maps `Prefix.locked` to `locked` for the three kinds, from the read row that exists; without it Fenolite's own document would not import to the model it was written from.
    - **Evidence.** `INFERRED`: a public reader's statement and Fenolite's reader agreeing with Fenolite's writer. Altium Designer's own view is asked through the verification kit (`fenolite kit`, c0091) as an author report and can raise the row to `ALTIUM-VERIFIED(author-report)`; this change does not wait for it.
    - Rejected: a warning only (the first draft of this proposal left Altium locks to "the second backend's list"; that backend is on `dev`, and a locked KiCad track would reach Altium unlocked without a word). Rejected: refusing the build (exit 7) for a locked item of a kind outside the set: a lock changes no copper, and `--copper-from` of a board with one locked track would stop every Altium build. Rejected: writing the bit before the row exists.
    - `result.copper.locked` counts what was written locked, so a caller can check the number against the board.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/analysis/connectivity.py` (new) | `LinkEnd(kind, where, position, layers)`, `OpenConnection(a, b, length)`, `NetConnectivity(name, pads, islands, fill_islands, open, unsupported)`, `ConnectivityReport(nets, issues, evidence)`, `connectivity(design, *, pads, nets=None)`, `EVIDENCE` |
| `src/fenolite/geometry/` (`touch.py`, new, exported from the package); `src/fenolite/checks/equivalence/routing.py` | `touch_groups(items) -> list[int]`; `pieces` calls it in place of its private `_joined` |
| `src/fenolite/backends/altium/pcbrecords.py`, `pcbdoc.py` | `LOCK_WRITTEN`; `locked=False` on `track_record`, `arc_record`, `via_record`; the writer passes the model's `locked` |
| `src/fenolite/backends/altium/adapter/board.py` | `locked` of imported tracks, arcs and vias from `Prefix.locked` |
| `src/fenolite/lens/altium_copper.py` | `result.copper.locked`; the `altium.not-lowered` warning with `where` `copper/locked` |
| `docs/formats/altium/pcb-copper.md`, `docs/hypotheses.md` | the locked-flag rows per record kind; `H-A-PCB-CU-LOCK` |
| `src/fenolite/routing/select.py` | `unrouted(design, open_nets, *, patterns, include_zone_nets)`; `rip(design, nets, *, keep=frozenset())` |
| `src/fenolite/routing/codes.py` | `route.incomplete`, `route.partial` |
| `src/fenolite/cli/cmd_route.py` | the query before and after, `--require-complete`, the write rule, `result.open`, `connections`, `rip_kept`, `paged = "open"` |
| `src/fenolite/cli/cmd_net.py`, `src/fenolite/analysis/views.py` | `islands`, `open`, `fill_islands` |
| `src/fenolite/model/board.py`; `schemas/fenolite.model.v0/board.json` | `Track.locked`, `Arc.locked`, `Via.locked` |
| `src/fenolite/backends/kicad/pcb.py` | `locked` in `TRACK_FIELDS`, `VIA_FIELDS` and `CANONICAL_ORDER` |
| `src/fenolite/dsl/intents.py`, `src/fenolite/dsl/design.py`, `src/fenolite/backends/kicad/copper.py` | `locked=` on `track`, `via` and `stitch`; `locked` on the intents; `_fields` compares it |
| `tests/unit/analysis/test_connectivity.py` (new) | the cases of measurement 3 as unit scenarios; the sweep against brute force; order independence |
| `tests/kicad/copper/_openbench.py`, `tests/kicad/copper/test_open_parity.py` (new) | probes `copper-open-kicad` and `copper-open-parity` per major |
| `tests/corpus/test_open_census.py` (new) | per-board census against KiCad's DRC |
| `tests/kicad/board/test_copper_locks.py` (new) | probes `pcb-lock-form` (10) and `pcb-lock-load` (9, 10) |
| `tests/routing/test_open_nets.py` (new) | `needs_router`: Freerouting on nets that hold copper; KiCadRoutingTools when present |
| `tests/unit/routing/test_select.py`, `tests/unit/cli/test_route_cmd.py`, `test_views_cmd.py`, `tests/unit/dsl/test_copper_dsl.py`, `tests/unit/backends/kicad/test_copper_merge.py`, `test_pcb_locks.py` (new) | the scenarios of the deltas |
| `docs/routing.md`, `docs/cli-contract.md`, `docs/dsl.md`, `docs/copper.md`, `docs/analyses.md`, `docs/formats/kicad/board.md`, `docs/evidence/routing.md`, `agent/SKILL.md` | the second pass, locks, `--require-complete`, the census and the probes |

## Sources registered by this change

None is certain. `S-0661` is reserved (block S-0660 to S-0679 of this group; `docs/evidence/sources.md` ends at S-0601 on `9aba2dff`) for a public source of the locked flag of a record kind that S-0160 does not state; task 4.4 registers it or writes that it was not needed. The KiCad facts rest on S-0020 and S-0029 (the two `kicad-cli` oracles) and S-0058 (the corpus demo boards); the router facts on S-0220 (Freerouting) and S-0215 and S-0216 (KiCadRoutingTools).

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-CONN-PARITY | For a board as stored, the count of open connections per net of `analysis.connectivity` equals the count of `unconnected_items` naming that net in `kicad-cli pcb drc`, on 9.0.9 and 10.0.6, for the cases of measurement 3 (S-0020, S-0029, S-0058) | `tests/kicad/copper/test_open_parity.py`; `tests/corpus/test_open_census.py` | probe `copper-open-parity` `equal` on both majors; the census equal per net on every readable corpus board below KiCad's cap of 499, a board with a copper drawing that holds a net listed apart |
| H-K-LOCK-FORM | KiCad 10.0.6 writes `(locked yes)` of a segment and an arc after `width` and of a via after `layers`, and nothing for an unlocked item; 9.0.9 loads a lock there and judges the board as without it. KiCad 9 writes the segment's and the via's lock there too (corpus); where it writes an arc's cannot be observed with its `kicad-cli` (S-0020, S-0029, S-0058) | `tests/kicad/board/test_copper_locks.py` | `pcb-lock-form` `equal` on 10.0.6: the re-saved text of the bench's four items (three locked, one not) equals Fenolite's; `pcb-lock-load` `equal` on both majors |
| H-G-DSN-PARTIAL | Freerouting 2.4.1 completes a selected net from the protected copper it already holds: a stub, joined pads, a fan-out via, a floating via of the net (S-0220) | `tests/routing/test_open_nets.py::test_freerouting` | the bench of measurement 6, routed through `fenolite route`, has 0 open connections by the query and 0 unconnected items by `kicad-cli` 10.0.6; outcome `dsn-partial` `equal` |
| H-K-KRT-PARTIAL | KiCadRoutingTools v0.22.1 closes a net that already holds copper of its own (S-0215, S-0216) | `tests/routing/test_open_nets.py::test_krt` | outcome `krt-partial` recorded `equal` or `different`; nothing depends on it |

| H-A-PCB-CU-LOCK | A free track, a free arc and a via whose first flag byte has bit 2 clear, every other byte as Fenolite writes the unlocked record, is a locked primitive: Fenolite's reader gives `Prefix.locked` and Altium Designer shows the item locked (S-0160, S-0150; S-0661 if registered) | `tests/unit/backends/altium/test_pcbdoc_copper.py -k locked`; kit request (author report) | read back by Fenolite's reader: mechanical; the author report: the three items shown locked, the others not |

All five start `INFERRED`, the first four with the measurements of "Context" as their first record. Ids used without changing their level: `H-K-PCB-READ`, `H-K-PCB-WRITE`, `H-G-DSN-PROTECT`, `H-G-DSN-INCOMPLETE`, `H-K-KRT-CLI`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| open connections per net | KICAD-VERIFIED (9.0.x, 10.0.x) for the bench counts; CORPUS-VERIFIED for the census | `copper-open-parity`, `test_open_census.py` |
| the two ends of a connection | mechanical: Fenolite's rule, not KiCad's | unit tests |
| selection, verdict, partial copper, `--require-complete`, rip | mechanical | `tests/unit/routing`, `test_route_cmd.py` |
| locks read and written | KICAD-VERIFIED (9.0.x, 10.0.x) | `pcb-lock-form`, `pcb-lock-load` |
| a second pass of Freerouting | ORACLE-VERIFIED(freerouting 2.4.1), judged by KiCad 10.0.6 | `dsn-partial` |
| `net` keys | the board read's level combined with `connectivity.EVIDENCE` | `test_views_cmd.py` |
| locks written to and read from an Altium document | INFERRED (`H-A-PCB-CU-LOCK`: fact rows with a public source, own reader); ALTIUM-VERIFIED(author-report) after a kit run, not required | `test_pcbdoc_copper.py -k locked`, `test_own_files.py -k locked` |
| `geometry.touch_groups` | mechanical | `tests/unit/geometry/test_touch_groups.py`; the equivalence tests unchanged |

`connectivity.EVIDENCE` names `H-K-CONN-PARITY` and takes its level; `fenolite.analysis.EVIDENCE` does not change, because it describes the analyses of c0047. Routes stay `UNVERIFIED`.

## Risks / Trade-offs

- **The query and KiCad disagree.** A copper drawing with a net, pad copper that the frame approximates (`exact` false), an arc that touches within its 1 µm band. Mitigation: the census lists every disagreement; `check` stays the gate, with KiCad's DRC.
- **Routers given nets that hold copper.** A router that treats a net's own copper as an obstacle adds copper beside it, or fails. Freerouting closed all 8 such nets. KiCadRoutingTools' documentation calls existing tracks obstacles that it leaves alone (S-0216), so `H-K-KRT-PARTIAL` records what it does; `--rip` gives a router a clean net.
- **Partial copper in the way.** Copper kept on an open net may block a later pass. Mitigation: `route.partial` names it, and `--rip --nets <net>` removes it.
- **More nets go to the router.** Boards whose nets hold stubs are now routed, and runs take longer. That is the purpose; `--nets` narrows them.
- **Time.** The query runs before and after the router: under 1 s on the scale boards and up to 9.4 s on a corpus board with large fills, mostly for zone nets, which `route` leaves out by default because it computes the query for its candidate nets only. `net` without a name computes every net.
- **A pass under `--require-complete` that ends open writes nothing.** The router's work is lost. Mitigation: run without the option to keep it; the reply still lists `open`.

## Migration Plan

- `route` selects nets that hold copper and are still open; a board with stubs gets them routed on the next run. `CHANGELOG.md` says so.
- `routed` and `unrouted` mean closed and open after the merge; a router's claim no longer counts.
- `--rip` keeps locked and script copper. A user who wants such copper gone unlocks it in KiCad or removes the intent.
- `unrouted()` takes `open_nets`: a caller of the old signature gets a `TypeError`, not a different answer. `rip()` keeps its positional arguments.
- The model gains three fields with defaults; old `board.json` documents load, and a design without locked copper serialises to the bytes it had; boards with locks keep their bytes on a rebuild, now through the model instead of an opaque child. Releases 0.2.x and 0.3.x cannot read a model document that carries the key `locked` on a track, an arc or a via: their reader refuses an unknown key. `docs/design-model.md` and `CHANGELOG.md` say so.
- An Altium build of a design with locked copper writes the lock bit, or warns; a design without locked copper gives the same document bytes, and `result.copper` gains `locked`.
- An Altium document with locked free primitives now imports with `locked` set: a model diff against an import made before this change shows those items.
- Each part can be reverted alone; the parts share only the query.

## Budget (6.5 days)

| part | days |
|---|---|
| registers and the probes of section 1: locks, KiCad's counts on the bench and the corpus, routers called directly | 0.5 |
| the query: islands, spanning tree, ends; unit and brute-force tests | 1.0 |
| parity canary on both majors, corpus census | 0.5 |
| selection, rip with `keep`, verdict after the merge, partial copper, write rule, `--require-complete`, result keys | 1.25 |
| locks in the model, the reader and the writer; lock oracle | 0.75 |
| `locked=` in the DSL and in script copper | 0.5 |
| locks in the Altium writer, build and import: fact rows first, the warning, then the bit | 0.75 |
| `geometry.touch_groups` moved out of `pieces`, agreement test | 0.25 |
| `net` keys | 0.25 |
| router oracle: Freerouting bench through the command, KiCadRoutingTools probe | 0.25 |
| documentation, guide, closing | 0.5 |
| **total** | **6.5** |

Cut order: (1) `locked=` in the DSL: locks made in KiCad are still read, written and kept by `--rip`; (2) the `net` keys: `route` still lists `open`; (3) the KiCadRoutingTools probe. Not cut: the query with its parity probe, the selection by open connections, the verdict after the merge, partial copper written, `--require-complete`, locks in the model and the files.

## Open Questions

- **Lock script copper by default?** It would make edits in KiCad impossible instead of undone at the next build. Default: no (Decision 6).
- **Write the partial board under `--require-complete`?** Default: no (Decision 9); c0120's invariant decides it for every command.
- **Model the net of a copper drawing?** 1 of 21 corpus boards uses one. Default: a change of its own after v0.4's routing group; until then such a net is reported open.
- **Name the items KiCad names?** Anchoring zones would name the zone in the last case of measurement 3, as KiCad does. Default: no; the counts are what the selection needs.
- **A connectivity stage in `check`?** It would give the true count above KiCad's 499. Default: c0120 decides with its report limits.
- **Should `direct` route the open connections of a net of three or more pads?** Default: no; it stays the two-pad test router.
