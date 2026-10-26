## Context

**Scope.** The row c0111 of milestone v0.4 in `docs/roadmap.md` ("The complex board, c0100–c0120", the gaps found by the review of 2026-10-05; the branch the proposal was written on called the group v0.2c): script copper given in a part's frame (vias, waypoints, stitching) and thermal via arrays inside a pad. The review recorded this gap with no owner: c0028 closed "copper drawn from hand-computed coordinates" for pad-ended tracks only.

**What exists** (read at `origin/dev` `9aba2dff`, 2026-10-07):

- `dsl/intents.py`. A `PadRef` (`part.pad(n, index=…)`) is accepted only as a track element. Every other point goes through `_point`: an `(x, y)` pair in the frame of `place()`, shifted by `BOARD_ORIGIN`. That covers `via_step(x, y, *, to, …)`, `arc_to(mid, end)`, `Design.via(key, x, y, …)` and the `along`, `region` and `origin` of `Design.stitch`, whose `origin` defaults to the board corner.
- `backends/kicad/copper.py`. `resolve_copper` runs on the placed design. `_obstacles` gives the copper entries and the hole of every pad the net `None`, so every pad, of any net, blocks a stitch candidate at `clearance`. `_region` lays the grid `origin + (i, j)·pitch` in the board frame, with the locators `via[i,j]`. Since c0074 a stitch also drops the candidates that meet a `no_vias` keep-out, come too near the board edge or lie off the board (`_Barriers`, `H-K-STITCH-AVOID`).
- `backends/kicad/frame.py`. A pad's `position` is `Transform.placement(at, θ).apply(stored)` (`H-G-ROT-DIR`, `H-G-BOTTOM-PLACE`). The stored children of a bottom footprint are its library children mirrored about local X (`H-G-BOTTOM-STORE`). All three rows are `KICAD-VERIFIED (9.0.x, 10.0.x)`. `placed_extent` already maps a definition with `Transform.placement(at, θ, mirror=bottom)`.
- `lens/build.py`. `build_design` places each part at its effective placement (c0019: a locked `place()`, else the existing board, else `place()`), then calls `resolve_copper` before `merge_layout`. `merge_copper` regenerates script copper with the same uuids and reports `kicad.copper.regenerated` when a field changed.
- `Part.field(dx, dy)` measures in the board frame from the part's point (c0030), so a label stays where it reads well when the part turns.
- `H-K-VIA-RENET` (`KICAD-VERIFIED (9.0.x, 10.0.x)`): a via whose copper touches only copper of another net takes that net in KiCad, and `pcb drc` reports no `shorting_items` for it.
- c0059 (archived) lets an authored footprint repeat a pad number with `shared=True`. c0068 (archived on 2026-10-05) added arc steps, via kinds and the `pads` command: the living "Copper intents in the DSL" reads `via_step(x, y, *, to, diameter=None, drill=None, kind="through")` and `Design.via(key, x, y, *, net, diameter=None, drill=None, kind="through", layers=None)`. c0074 (archived on 2026-10-05) added the bullet "Keep-outs and the edge" and two scenarios to "Stitching vias".
- The second backend. The Altium build resolves script copper in an in-memory KiCad build (`altium-build`, "Script copper in an Altium build") and writes the result to the `.PcbDoc` (c0085). c0084, open on `dev`, holds a delta of that requirement; this change does not modify it.

**Measured on 2026-10-05**, with the sources of the branch the proposal was written on (its base is `7203e4b6`; the measurements were not repeated at `9aba2dff`, and task 1.3 repeats them as probes), `kicad-cli` 10.0.6 (local) and 9.0.9 (the pinned image, about 5 s per DRC run). The benches used two footprints of the fetched KiCad 10.0.6 library, `QFN-32-1EP_5x5mm_P0.5mm_EP3.1x3.1mm` and `SOT-223`, and are not committed; each measurement becomes a recorded probe or a unit scenario of this change.

1. *A part moves, its vias stay.* A QFN with nine `design.via` points inside its exposed pad, unlocked. `fenolite build … --confirm`, then `fenolite place <board> --move U7=35mm,20mm --confirm`, then the same build: `place` gives `place.copper-left`; the rebuild gives `layout.place-overridden` and nothing about the vias (`result.copper.regenerated` is 0); the pad is at (135, 120) mm and the vias still at (119 to 121, 119 to 121) mm. `kicad-cli pcb drc --format json --severity-all` (10.0.6): 9 `via_dangling`, 9 unconnected items.
2. *A stitch in the pad.* `region` = the square of the 3.1 mm pad, `origin` its centre, pitch 1 mm, via 0.6/0.3 mm, clearance 0.2 mm: `kicad.copper.stitch-skipped` with 9 candidates dropped, then `kicad.copper.stitch-empty`.
3. *The anchor map against the board frame* (no KiCad). Both footprints placed with `place_footprint` at 0°, 90°, 180°, 270°, 30° and 45°, on both sides: for each of the 552 pads, `Transform.placement(at, θ, mirror=side == "bottom").apply(library position)` equals `BoardPad.position`, with 0 differences, to the nanometre.
4. *KiCad on anchored copper.* One board, built for target 10 and for target 9 with `fenolite build bench/design.py --kicad-version {10,9} --copper-check warn --confirm`, each via placed at the point the map of item 3 gives; `pcb drc --format json --severity-all` on each major. The two reports were identical case by case:

   | case | placement | vias | DRC, 9.0.9 and 10.0.6 | copper guard of `build` |
   |---|---|---|---|---|
   | U1 | top 0° | 9 of the pad's net on a 1 mm grid in the exposed pad, joined on `B.Cu` by tracks of the net | nothing | nothing |
   | U3 | top 0° | the same, nothing on `B.Cu` | 9 `via_dangling` | nothing |
   | U4 | bottom 30° | 9 of the pad's net on the grid of the part's frame, joined on `F.Cu` | nothing | nothing |
   | U2 | top 0° | 9 of another net in the exposed pad | 9 `via_dangling`, each named with the pad's net; no `shorting_items` | 9 `copper.short` |
   | U6 | bottom 30° | 9 of a marker net on the grid of the part's frame | each named with the pad's net | 9 `copper.short` |
   | Q3 | bottom 30° | 3 of a marker net at the library points of pins 1 and 3 and inside the tab | named with the nets of pads 1, 3 and 4 | one short with each of those pads |
   | Q4 | top 90° | the same | the same | the same |
   | Q1 | bottom 30° | 3 at the same points, each on the net of its pad | each keeps its net | nothing |
   | Q2 | bottom 30° | the offsets of Q1 without the mirror (control) | the vias of pins 1 and 3 named with each other's net | 2 `copper.short` |

   So the map puts every anchored point inside the pad it names, as KiCad sees the copper, on both majors. KiCad accepts own-net through vias in an SMD pad when copper of the net joins them on another layer. And KiCad never reports a via of the wrong net inside a pad: it re-nets it. Only Fenolite's copper guard reports it.

## Goals / Non-Goals

**Goals**
- A script gives any point of its copper relative to a part or a pad, and that copper follows the part through every rebuild.
- A stitch makes a thermal via array inside a pad, aligned with the pad at any rotation and on either side.
- Where an anchor lands is proved by KiCad on both majors.

**Non-Goals**
- Everything under "Non-goals" in the proposal.
- A query that lists pad positions in a footprint's library frame: nowhere for now, because a pad anchor needs none (Open Questions).
- Anchors in `Part.field`: nowhere, because a field is placed in the board frame on purpose (c0030). Anchors in script keep-outs and board items: c0103 decides (Open Questions).

## Decisions

1. **An anchor is a point in the footprint's library frame.** The offset `d` is measured as the footprint file draws it: X right, Y down, from the footprint's origin (`part.at`) or from the pad's `at` (`part.pad(n).at`). The point is `at + R(θ)·S·d`, `S` the mirror about local X on the bottom side, rounded half to even once. Pads follow the same map (measurement 3), so an anchor keeps its place among the pads under any rotation and on either side.
   - Rejected: board-frame offsets from the part's point, as `Part.field` takes them. They keep a label upright; a via offset from a pad would leave the pad when the part turns.
   - Rejected: the pad's own frame. A pad's angle inside a footprint is a drawing choice of the library (the measured QFN draws its bottom row with swapped sizes and angle 0), so one physical direction would need different offsets in different libraries.

2. **Anchors are resolved first, inside `resolve_copper`.** Each anchor becomes its board point before any other rule reads the intent. The function sees the placed design, so a build uses the effective placement, and every caller gets the same points: the build, the in-memory build of the Altium target, a script on a model design.
   - Rejected: resolving in the DSL. The script runs before placements exist, the failure c0028 was written for.
   - Rejected: a separate pass before `resolve_copper`. A script that skipped it would have its anchors read as pad ends, since both carry `component`.

3. **`part_frame` is the one map, public in `frame.py`.** `part_frame(design, component, *, number=None, index=None)` returns a `PartFrame` whose `point(offset)` applies the map; `resolve_copper` uses it, and so can a script or c0107's fan-out. The component matches as in `find_pads`: path first, then reference. A pad's base is its stored position mirrored back on the bottom side, so `point()` of a pad equals its `BoardPad.position` exactly.
   - Rejected: the map inside `copper.py` only. The board-frame queries are where a script looks for pad geometry, and `copper.py` would hold a second copy of the frame.

4. **A pad anchor names one position.** With `index`, the pad at that place among the pads of its number. Without it, every pad of the number must lie at one position, as the front and back pads of one padstack do; otherwise `kicad.copper.bad-intent`.
   - Rejected: the nearest pad. A track end has a neighbour to measure from; an anchor has none.
   - Rejected: the first pad in footprint order: arbitrary (c0028, Decision 9).

5. **An anchor joins nothing.** It is a point: it gives no net and takes none. A track's net still comes from its pad ends, and a via or a stitch names its net. A via of the wrong net anchored inside a pad is a short that KiCad's DRC re-nets away (measurement 4, U2 and Q2). The copper guard of `build`, on by default, is its gate.
   - Rejected: checking a via's net against the pad its anchor names. A fan-out via sits beside its pad, not inside it, and the guard already judges overlap exactly.

6. **A thermal array is a stitch whose region is a pad.** `region=part.pad(n)` keeps the candidates whose via disc, grown by `margin`, lies inside one copper entry of the pad on the outer copper layer of the part's side. The test is exact on the thick entries of the board frame. The pads the region names are no obstacle to its candidates; their holes, every other pad and own-net vias still are. The pad must be on the stitch's net.
   - Rejected: a new intent kind. It needs a fourth reading rule and a locator scheme for the same vias.
   - Rejected: lifting the pad rule for every pad of the net. A stitch over a pour would drop vias into the SMD pads of passives, where they wick solder.
   - Rejected: a new argument `inside=`. "Copper intents in the DSL" refuses a stitch with neither `along` nor `region`, so it would need a MODIFIED delta of that requirement for something `region` can carry.

7. **The grid follows `origin`.** An anchored `origin` lays the grid in its part's frame: the candidate `(i, j)` is `PartFrame.point(origin.offset + (i·pitch, j·pitch))`, turned with the part and mirrored on the bottom side. A board-point `origin` keeps today's board-frame grid for a ring region. A pad region lays its grid from the pad's position in the part's frame unless its `origin` is an anchor; the DSL refuses a board-point `origin` given with a pad region, so a value given is never ignored. The locators `via[i,j]` count in the grid's frame, so a moved part keeps its uuids and the build reports `kicad.copper.regenerated`.
   - Rejected: a frame inferred from the region's points. A ring with points of two parts has no single frame.
   - Rejected: changing the DSL's default `origin` for pad regions. "Copper intents in the DSL" fixes it at the board corner; the stitch rule reads a board-point origin as "no frame given" for a pad region instead, which is what the default means there.

8. **`via_step` and `Design.via` take one point argument.** `via_step(anchor, to=…)` and `design.via(key, anchor, net=…)`, and also an `(x, y)` pair; two lengths work as before. Every other argument keeps its living meaning in both forms: `diameter`, `drill` and `kind` of `via_step`; `diameter`, `drill`, `kind` and `layers` of `Design.via`. So a blind or micro via can be anchored; only stitch vias stay through vias. A `PadRef` where a point is expected is refused with a hint to `.at()`: in a path it means "join this pad", and a point must not mean that silently.
   - Rejected: a keyword `at=` beside `x` and `y`: three ways to give one point.

9. **Existing issue codes** (`manual-copper`, "Copper issue codes"; `altium-build` has a requirement of the same name, which is not meant here). A missing part, pad or index gives `kicad.copper.pad-not-found`; an ambiguous pad `kicad.copper.bad-intent`; a staged part `kicad.copper.end-unplaced` (warning); a pad region on another net or none `kicad.copper.net-conflict`; one without copper on the side's outer layer `kicad.copper.layer-mismatch`. Each keeps its severity, so the closed table does not change. `docs/copper.md` lists the new uses.
   - Rejected: new rows. They need a MODIFIED "Copper issue codes" and an entry each in `cli/data/explain.toml`, for no new severity.

10. **ADDED requirements, one MODIFIED.** c0068 and c0074 are archived on `dev`, so the living texts of "Copper intents in the DSL", "Copper module", "Tracks from intents", "Single vias" and "Copper issue codes" hold arc steps and via kinds, and "Stitching vias" holds c0074's keep-out bullet. This change still adds requirements that extend those lists "in addition", as c0028 extended c0011's (its Decision 13): four long requirements are not copied for one new kind of point. "Stitching vias" must change: its pad rule forbids a thermal array, and an ADDED requirement overriding it would leave two conflicting MUSTs (c0028, Decision 16). Its delta is regenerated from the living text at `9aba2dff` with five edits: the opening sentence, the first bullet, "Region", the new bullet "Pad region", and the exemption in "Clearance"; c0074's bullet is kept whole with one sentence added (Decision 12), and its two scenarios are kept. No open change on `dev` holds a delta of "Stitching vias", and no other proposal of v0.4 modifies it; c0107 and c0112 may add copper calls, and task 0.1 checks again that neither modifies these requirements.
    - Rejected: MODIFIED deltas of the four other requirements: four full copies to keep in step for no change of meaning.

11. **KiCad proves the landing point with marker vias.** A via of a marker net anchored inside a pad is reported with that pad's net (`H-K-VIA-RENET`), so the DRC report tells, item by item, which pad KiCad sees under each anchor; the unmirrored control shows that the probe can fail.
    - Rejected: `shorting_items`. KiCad does not report it for a via inside a pad of another net (measurement 4).
    - Rejected: IPC-D-356 via records: the same re-net, one more export per run.

12. **A pad region obeys keep-outs and the edge.** c0074's bullet "Keep-outs and the edge" drops a candidate in a `no_vias` rule area, near the edge or off the board. It applies to the candidates of a pad region too; the exemption covers only the copper entries of the region's own pads. A thermal array under a `no_vias` area is therefore dropped and counted in `kicad.copper.stitch-skipped`, and the scenario "A keep-out across a pad region" fixes it.
    - Rejected: exempting a pad region from keep-outs. A rule area that forbids vias is the user's statement, and KiCad's DRC reports a via inside it.

13. **The word "anchor".** Three changes of v0.4 use it. Here an anchor is a point in a part's frame: `Part.at()`, `PadRef.at()`, `AnchorRef`, `Anchor`, `AnchorLike`. In c0096 `Part.place(…, anchor=…)` and `Placement.anchor` name the mechanical reason of a locked placement. In c0113 the `anchor` of `near` is the reference side of a proximity rule. No identifier is shared: this change adds no keyword argument `anchor` and no attribute `anchor`. `docs/dsl.md` gets one sentence that tells the three apart (task 6.1); if the coordinator renames c0096's argument, that sentence follows.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/backends/kicad/frame.py` | `@dataclass(frozen=True, slots=True) class PartFrame(footprint_id: str, at: Point, rotation: Udeg, side: Side, base: Point, pad_ids: tuple[str, ...] = ())` with `point(offset: Point = Point(0, 0)) -> Point`; `part_frame(design, component, *, number: str \| int \| None = None, index: int \| None = None) -> PartFrame` |
| `src/fenolite/backends/kicad/__init__.py` | re-exports `part_frame` |
| `src/fenolite/backends/kicad/copper.py` | protocol `AnchorLike(component, number, index, offset)`; anchors resolved first in `resolve_copper`; pad regions, the grid of an anchored origin and the pad exemption in `_resolve_stitch` |
| `src/fenolite/dsl/intents.py` | `AnchorRef(part, number, index, offset)` with `PadRef.at(dx=None, dy=None)`; plain `Anchor(component, number, index, offset)`; anchors and the one-argument point in `via_step`, `arc_to`, `record_track`, `record_via`, `record_stitch`; `region=PadRef`; `copper()` output |
| `src/fenolite/dsl/part.py`, `design.py`, `__init__.py` | `Part.at(dx=None, dy=None)`; `Design.via(key, x, y=None, …)`; docstrings; re-exports `AnchorRef` and `Anchor` |
| `tests/data/libs/Frame.pretty/Frame_Anchor.kicad_mod` (authored, CC0, format 20241229) | pads `1`, `2`, `3`: 1.5 mm × 1 mm at (−4, −2), (−4, 0) and (−4, 2) mm; pad `4`: 3 mm × 3 mm at (1, 0) mm; courtyard (−5, −3)–(3, 3) mm; a row in `tests/data/MANIFEST.toml` |
| unit tests | `tests/unit/backends/kicad/test_frame_anchor.py` (new), `test_copper_anchor.py` (new), `test_frame_pads.py`, `test_copper_stitch.py`, `test_copper_issues.py`; `tests/unit/dsl/test_copper_anchors_dsl.py` (new); `tests/unit/lens/test_build_copper.py` |
| oracle tests | `tests/kicad/frame/_anchorbench.py`, `test_anchor_oracle.py`; probes in `tests/kicad/_probes.py` |
| documentation | `docs/dsl.md` ("Copper"), `docs/copper.md` (anchors, pad regions, the codes, `via_dangling` on one layer), `docs/placement.md` (the sentence on script copper), `docs/formats/kicad/frame.md`; `docs/hypotheses.md`; probe files |

No model, schema, file-format, CLI or FEN code change, so no entry in `cli/data/explain.toml` and no compatibility note for a model key. `result.copper` keeps its fields.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-G-FRAME-ANCHOR | A point at offset `d` in the library frame of a footprint stored at `at`, angle `θ`, lies for KiCad at `at + R(θ)·S·d`, `S` the mirror about local X on the bottom side, rounded half to even: a via of a marker net placed there inside a pad is reported with that pad's net and in no `shorting_items`, on 9.0.9 and 10.0.6, at 0° and 90° on the top and 30° on the bottom; after `fenolite place --move` and a rebuild, an anchored array lies in its pad at the new place (builds on `H-G-ROT-DIR`, `H-G-BOTTOM-PLACE`, `H-G-BOTTOM-STORE`, `H-K-VIA-RENET`; S-0020, S-0029) | `tests/kicad/frame/test_anchor_oracle.py -k "frame or moved"` | `copper-anchor-frame` `equal`, `copper-anchor-frame-control` `different`, `copper-anchor-moved` `absent` and `copper-anchor-moved-control` `present` on both majors |
| H-K-VIA-IN-PAD | Through vias of a pad's net inside an SMD pad get no DRC violation on 9.0.9 and 10.0.6 when copper of the net joins them on another layer, and one `via_dangling` warning each when nothing does (S-0020, S-0029) | `test_anchor_oracle.py -k thermal` | `copper-anchor-thermal` `absent` and `copper-anchor-thermal-alone` `present` on both majors |

Both ids are free in `docs/hypotheses.md` at `9aba2dff`. Both start `INFERRED`, with measurement 4 as their first record; the moved part of `H-G-FRAME-ANCHOR` has only its control measured (measurement 1, on 10.0.6). Rows used without changing their level: `H-G-ROT-DIR`, `H-G-BOTTOM-PLACE`, `H-G-BOTTOM-STORE`, `H-K-VIA-RENET`, `H-G-FRAME-ROUTE`, `H-G-FRAME-UUID`. No source is registered: S-0020 and S-0029 are the two `kicad-cli` oracles.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| where an anchored point lands | KICAD-VERIFIED (9.0.x, 10.0.x) | `copper-anchor-frame`, its control |
| thermal arrays accepted by KiCad's DRC | KICAD-VERIFIED (9.0.x, 10.0.x) | `copper-anchor-thermal`, `-alone` |
| anchored copper follows a part moved by `place` | KICAD-VERIFIED (9.0.x, 10.0.x) for the bench | `copper-anchor-moved`, its control |
| `part_frame`, resolution, codes, DSL forms, stitch rules | mechanical | unit scenarios |
| `copper.EVIDENCE`, `frame.EVIDENCE` | unchanged (`INFERRED`) | "Copper evidence", "Board-frame evidence" |

## Risks / Trade-offs

- **An anchor in the wrong pad passes KiCad's DRC.** KiCad re-nets the via (measurement 4). Mitigation: the copper guard of `build` refuses it by default with `copper.short`; `docs/copper.md` says that `--copper-check warn` leaves only Fenolite's check to report it.
- **Vias in SMD pads wick solder.** A thermal array is what the user asked for; protecting it is c0112's, and `docs/copper.md` points there.
- **`via_dangling` before a fill.** A thermal array joined only by a plane is dangling until the plane is filled (measurement 4, U3). `docs/copper.md` says so; `fenolite fill` clears it.
- **Library coordinates.** A part anchor needs offsets from the footprint's origin. A pad anchor needs only an offset from its pad, so the documentation leads with it.
- **Rounding at other angles.** A grid point at 30° is rounded once, as a pad position is. A candidate on the margin boundary is judged on its rounded point, the point that is written.
- **Cost.** A grid in a part's frame tests at most `(2⌈R/pitch⌉ + 1)²` candidates, `R` the farthest point of the region from the origin; a pad region holds a few dozen.

## Migration Plan

- Additive. Scripts without anchors record and resolve the same intents, and every file they build keeps its bytes. `via_step` and `Design.via` keep their two-length form.
- Absolute vias that a script turns into anchors keep their keys and locators, so the next build regenerates them in place with `kicad.copper.regenerated` infos.
- Rollback: remove the anchors from the script; the next build regenerates the copper where the absolute points say.

## Budget (4.5 days)

| part | days |
|---|---|
| entry check, registers, `Frame_Anchor`, the frame and thermal probes first, with points computed by the test | 0.75 |
| `part_frame`, `PartFrame`, unit scenarios | 0.5 |
| DSL: `Part.at`, `PadRef.at`, the forms, `copper()`, refusals | 0.75 |
| `resolve_copper`: anchors in paths, steps, arcs, vias and stitch points; codes | 0.75 |
| pad regions, the grid of an anchored origin, the pad exemption | 0.75 |
| the bench moved to the script's anchors, the moved-part probes, on both majors | 0.5 |
| documentation and closing | 0.5 |

Cut order, each cut leaving the rest consistent: (1) the moved-part probe (−0.25; the hermetic regeneration scenario stays); (2) anchors in `arc_to` and in the `along` and `region` points of a stitch (−0.25); (3) `Part.at`, keeping pad anchors (−0.25). Never cut: pad anchors for vias, via steps and waypoints, the pad region with its exemption, and the frame probe.

## Open Questions

- **Library-frame pad positions on the command line** (`fenolite pads --frame part`), for authors of part anchors? Default: no; `part.pad(n).at()` needs no library coordinates, and `pads` of a part at 0° on the top gives them by subtraction.
- **Should a pad region exempt every pad of its net, not only the pads it names?** Default: no (Decision 6).
- **Anchors for script rule areas** (c0103) and placement keep-outs (c0113)? Default: their owners decide; `part_frame` is public for them.
- **Should `place` regenerate anchored copper?** Default: no; the next build does (c0028, Decision 20), and `place.copper-left` stays.
