## Context

- c0307 fixes each face's 2D frame seen from outside, its `flat` rectangle, wall thickness, and the outer
  extents and split height that bound the face.
- c0308 records apertures (`rect`, `circle`, `path`, with `z`, `offset`, `radius`, `clearance`) per part
  and face, and places each aperture centre from the part's position and the board's Z.
- c0309's judge already places apertures on faces and reports `enclosure.aperture-off-face` and
  `enclosure.web-thin`.
- Fenolite writes SVG itself for previews and region renders, but has no PDF or DXF writer: `export --pdf`
  and `--dxf` are `kicad-cli` plots of board layers, which know nothing of a box face.

## Goals / Non-Goals

**Goals**: one template per face in three formats, at exact scale, byte-identical, written through plan
and confirm, refused when an aperture is off its face.

**Non-Goals**: tool paths, service formats, tiling, 3D.

## Decided

The six decided answers of c0306's `design.md` apply; in particular no kernel and stages 0 and 1 before any
3D generation.

## Decisions

### 1. Command

`fenolite enclosure templates PATH --out DIR [--faces LIST] [--formats LIST] [--enclosure FILE]
[--timestamp T]`. `PATH` is a project or board that Fenolite reads (KiCad or Altium); the record is
`.fenolite/enclosure.json` or `--enclosure FILE`. Without a record: exit 3 with `FEN-3001` and a hint
naming `design.fit`. `--faces` defaults to the faces that hold an aperture; `--formats` to all three.
`DIR` is relative, as for `export --out`. Writes follow the mutation protocol; `result.templates` lists
per face the openings (`part`, `shape`, `centre` in the face frame, `size`) and the files.

### 2. Geometry

Per face, in its frame (c0307, decision 1), all integer nm until written:

- **Outer rectangle.** Walls: u over the box's outer extent along the face, v from `outer.z_min` to
  `outer.z_max`; `top` and `bottom`: the outer length and width. The split line at `lid.split_z` on walls.
- **Flat rectangle** from the face's `flat`, dashed.
- **Datum corner** at (u min, v min) of the outer rectangle: an L mark and the words "datum".
- **Openings.** Each aperture of the face grown by its clearance: a circle; a rectangle with corner radius
  as lines and quarter arcs; a path as lines. A centre cross 2 mm long and a dimension text (`⌀ 3.6` or
  `9.8 × 3.8`, in mm with at most two decimals) beside it, and the part's reference.
- **Distances.** For each opening, the u and v of its centre from the datum, in the result and in a table on
  the SVG and PDF page.

Drawn as seen from outside: a user taping the template on the outside drills where the paper says.

### 3. SVG (S-0955)

`width` and `height` in `mm`, `viewBox` in millimetres (from nm, 6 decimals, trailing zeros removed),
Y flipped so v points up on paper. Strokes 0.2 mm, cut lines black, flat rectangle dashed grey, text in a
generic sans-serif family. Groups `outline`, `flat`, `cuts`, `marks`, `text`, each with an `id`. No
script, no external reference, no font embedding.

### 4. PDF (S-0956)

One page, `MediaBox` the drawing plus 10 mm margins, in points (1 mm = 72/25.4 pt, written with 4 decimals
from nm by integer arithmetic). Objects: catalog with `/ViewerPreferences << /PrintScaling /None >>`, pages,
page, one content stream (path operators `m`, `l`, `c`, `re`, `S`, `f`; arcs as cubic Béziers of at most 90°),
the standard Helvetica font (no embedding), and an information dictionary with `/Producer (Fenolite
<version>)` and `/CreationDate` only with `--timestamp`. Cross-reference table with fixed-width offsets.
Uncompressed, so the bytes are reviewable and stable.

### 5. DXF (S-0957)

ASCII, a `HEADER` with `$ACADVER` and `$INSUNITS` 4 (the reference defines it as the default units of
inserted blocks, 4 = millimetres; that readers take it as the drawing's unit is INFERRED), a `TABLES` section with layers
`OUTLINE`, `FLAT`, `CUT`, `MARK`, `TEXT`, and `ENTITIES` with `LINE`, `ARC` and `CIRCLE` only (and `TEXT`
on its layer). Coordinates in mm with 6 decimals. The version and the minimal section set are recorded
facts with their labels in `docs/formats/templates/dxf.md`; which readers accept them is
`H-G-ENCL-TEMPLATE-FILES`.

### 6. Determinism

Faces in the order `front`, `back`, `left`, `right`, `top`, `bottom`; openings sorted by part reference,
then by centre; numbers formatted by one integer routine; LF line ends; no date unless `--timestamp`. The
same inputs give the same bytes on every platform (`H-G-ENCL-TEMPLATE-BYTES`), checked against golden
files authored for Fenolite.

### 7. Checked first

Before planning, the judge of c0309 runs on the face rules of the selected faces only. An
`enclosure.aperture-off-face` (error) plans no write: exit 5 with the issue. `enclosure.web-thin` stays a
warning and the files are written. A face named by `--faces` without an aperture gets its outline, flat
rectangle and datum only, with `enclosure.template-empty` (info). A page larger than A4 portrait or
landscape gets `enclosure.template-large` (warning).

## Codes

| code | severity | when |
|---|---|---|
| `enclosure.template-empty` | info | a face named by `--faces` holds no aperture |
| `enclosure.template-large` | warning | a page exceeds A4 in both orientations |

No new `FEN-` code: a missing record is `FEN-3001`, a broken one `FEN-3009` (c0307), an aperture error
exits 5 (`FEN-5001`).

## Hypotheses registered by this change

- `H-G-ENCL-TEMPLATE-BYTES`: the templates of the example are byte-identical to their golden files on
  Linux, Windows and macOS.
- `H-G-ENCL-TEMPLATE-FILES`: the SVG parses as SVG, the PDF passes an independent checker and the DXF
  loads in an independent reader with the same entity counts and millimetre sizes.
- `H-G-ENCL-TEMPLATE-SCALE`: printed at actual size, the 100 mm scale bar and a 10 mm test opening measure
  within 0.5 mm (author report by the maintainer).

## Evidence per behaviour

| behaviour | level |
|---|---|
| geometry, ordering, bytes | `INFERRED` (unit and golden tests) |
| readers | `INFERRED` until `H-G-ENCL-TEMPLATE-FILES` |
| printed scale | `INFERRED` until the author report |

## Risks / Trade-offs

- **Printers rescale** despite `/PrintScaling /None`: the scale bar and the "print at 100 %" text make it
  visible; the docs say to measure the bar before drilling.
- **Draft**: a wall's outside is not perpendicular on a drafted box; the template is for the flat area,
  which c0307 defines without radii and ribs.
- **DXF dialects** vary; the minimal entity set keeps the risk low.

## Open Questions

1. Independent readers for `H-G-ENCL-TEMPLATE-FILES`: `ezdxf` (MIT) in the dev group and `qpdf` as an
   optional tool? Recommended: yes, both outside the runtime, skipped when absent, measured in CI.
2. Tiling for faces larger than A4? Recommended: not in v0; the warning and the DXF cover large faces.
3. Also mirror templates for drilling from inside? Recommended: an option `--inside` later if asked.
4. A drill size table (round up to standard drills)? Recommended: no; the opening size is the user's
   aperture plus clearance, and the docs say to round up.

## Relation to the other changes

Uses c0307's faces, c0308's apertures and record, and c0309's judge. Independent of c0306. Stage 2's box
library makes templates available for real boxes; stage 4's generated enclosure takes the same apertures
as its cut-outs.

## Size

About 5 design-days: geometry and command 1.5, SVG 0.5, PDF 1, DXF 1, golden files, readers and docs 1.
