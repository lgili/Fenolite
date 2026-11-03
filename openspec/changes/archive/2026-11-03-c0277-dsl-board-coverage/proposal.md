## Why

A real board hits things the DSL cannot say: more than eight copper layers, copper text and logos,
custom or chamfered pads, teardrops, groups, images, radial and leader dimensions, arcs in zone outlines,
an edited footprint instance, a 3D model offset. Research section 4.3 of `docs/research/board-library.md`
lists them; today the reader keeps most as opaque slots, and a build from code loses them. c0275's
importer needs each one to be expressible, or at least kept verbatim with a finding, never dropped.

## What Changes

- **Copper counts 1 to 32.** `COPPER_COUNTS` and `CREATED_COPPER_COUNTS` become every even count from 2
  to 32 (inner rows `2k + 2`, already loaded by hand on both majors, `H-K-PCB-LAYERS`). `copper=1` joins
  only if a new probe finds that KiCad loads a one-copper table (`H-K-PCB-ONE-COPPER`); otherwise it is
  refused with a hint. Odd counts stay refused. Stack-up, planes, zones, presets, the lens, the router
  hand-off and the Altium build (at most 16 signal layers and 16 planes) follow.
- **Copper text and graphics.** The drawing calls accept copper layers; a copper graphic may carry
  `net=`, a copper text `knockout=`. The copper guard judges them.
- **Authored pads**: `trapezoid` (`delta`), chamfered `rect`/`roundrect` (`chamfer`, `corners`),
  `roundrect` `radius_ratio`, and `custom` (anchor plus primitives).
- **Teardrops**: `design.teardrops(...)` with the parameters KiCad documents, written as pad and via
  settings; KiCad regenerates the teardrop zones on fill.
- **Groups**: `design.group(name, *members, locked=False)` over parts and keyed items.
- **Images**: `design.image(key, file, at, *, layer, scale)`; the build embeds a PNG read beside the
  script and records its SHA-256.
- **Dimensions**: `radial_dimension`, `leader` and `center_mark` beside today's aligned and orthogonal.
- **Zone arcs**: `zone(outline=…)` accepts `arc_to` steps, as `board(outline=…)` does.
- **Footprint-instance overrides**: `part.override(clearance=, mask_margin=, paste_margin=,
  paste_ratio=, zone_connection=, thermal_gap=, thermal_spoke_width=)`, `part.edit_pad(number, ...)`
  and field fonts (`bold`, `italic`, `face`) on field placements.
- **3D model references** by name: `part.model(name, offset=, rotation=, scale=, hidden=)`.
- **Verbatim items**: `design.verbatim(key, text, target=...)` and `part.verbatim(key, text)` keep any
  other KiCad item as given, after a parse and the version gate, with `build.verbatim-item` (info);
  the net rewrite of opaque content applies. An Altium build lists each one as not written.
- **Model**: new fields and entities (`Group`, `Image`, dimension kinds, pad shapes, overrides, zone
  arcs, graphic nets), all omitted from canonical JSON when empty, so **every existing build keeps its
  bytes**; the KiCad reader projects what it can and keeps the slots it holds today.

## Capabilities

- Modified: `design-dsl` (MODIFIED "Board and placements in the DSL", "Copper layer counts in a build",
  "Board drawings in the DSL"; ADDED one requirement per item), `kicad-file-backend` (MODIFIED "Created
  board header"; ADDED writing rules), `kicad-oracle` (MODIFIED "Created layer tables are probed on both
  majors"; ADDED probes), `altium-build` (ADDED reports and stack limits), `dsl-footprint-authoring`
  (ADDED pad shapes).

## Non-goals

- No new stack-up presets (no fabricator data), no auto-placement of teardrops beyond KiCad's own, no
  image tracing, no Altium records for the new items (reported instead), no Altium verbatim items.
- No change of how the reader models existing boards beyond projections that keep the written bytes.

## Evidence level required

- Every DSL call: `INFERRED`, unit-tested; every written item: `KICAD-VERIFIED` on 9.0.x and 10.0.x by a
  load, DRC and re-save probe (`H-K-PCB-LAYERS`, `H-K-BUILD-LAYERS-32`, `H-K-PCB-ONE-COPPER`,
  `H-K-COPPER-ART`, `H-K-PAD-SHAPES`, `H-K-TEARDROP`, `H-K-GROUP`, `H-K-IMAGE`, `H-K-DIM-KINDS`,
  `H-K-ZONE-ARC`, `H-K-FP-OVERRIDE`, `H-K-MODEL-REF`, `H-K-VERBATIM`). Altium stacks over 8 layers:
  `ALTIUM-VERIFIED(kit)` (`H-A-STACK-32`).

## Impact

- Changed: `dsl/design.py`, `dsl/items.py`, `dsl/footprint.py`, `dsl/part.py`, `model/board.py`,
  `backends/kicad/layers.py`, `backends/kicad/pcb*.py`, `lens/build.py`, `lens/altium_copper.py`,
  `checks/copper*`, `docs/dsl.md`, `docs/formats/kicad/board.md`, guide pages, `CHANGELOG.md`.
- New: `dsl/verbatim.py`, authored fixtures, tests, `examples/board_coverage/`.
- No dependency; used by c0275 (coverage table), c0278 (levels 6 and 7).
- Size: about 10 design-days.
