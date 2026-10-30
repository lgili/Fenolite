## Context

`docs/research/enclosures.md`, section 5.1, lists what a box model needs; section 4 sets what may be stored
(dimensions as facts, one box at a time, with provenance; never vendor files); section 10 holds the
maintainer's answers. Fenolite already has:

- canonical JSON with integer nm, generated schemas and a drift test (`canonical-serialization`);
- `Outline` rings with `OutlineArc` edges (`design-model`, "Board outline arcs"), reused here for polygons
  with arcs;
- `Evidence` levels and the rule that the lowest wins (`AGENTS.md`);
- `MechanicalIntent` with `status` `measured`, `estimated` or `proposed` (c0096).

The package layering forbids `model` and `dsl` to import `geometry`. The board side (c0308) must therefore
read the usable area and the zones as stored data; only the derivation that writes them needs geometry.

## Goals / Non-Goals

**Goals**: a strict, canonical, integer document of one box; derivation of the usable area and the height
zones per mount option; drift detection; per-field provenance and evidence; fixtures authored for Fenolite.

**Non-Goals**: 3D solids, curved surfaces, snap-fits, gaskets; real boxes (stage 2); vendor files.

## Decided (maintainer, `docs/research/enclosures.md`, section 10)

1. Vendor STEP: link only, never stored. A model may hold the vendor page URL in `provenance.links`.
2. Models are authored one box at a time from public datasheets, with provenance; never a scraped
   catalogue (the EU database right on substantial parts, research section 4).
3. Fenolite's own models are CC0 (`licence: "CC0-1.0"`).
4. No 3D kernel in stages 0 and 1; gmsh is stage 3.
5. A comparison against a user's vendor STEP runs locally and stores only results (`basis: "local-step"`).
6. Stages 0 and 1 before any 3D generation. The library of real boxes is stage 2 in `lgili/fenolite-library`.

## Decisions

### 1. The frame

Origin at the centre of the inside floor; X along the box length, Y along its width, Z up; Z = 0 is the
cavity floor. Faces: `front` is the wall at −Y, `back` +Y, `left` −X, `right` +X, `top` the lid, `bottom`
the floor. Each face has a 2D frame seen from outside: `front` u = +X, v = +Z; `back` u = −X, v = +Z;
`left` u = −Y, v = +Z; `right` u = +Y, v = +Z; `top` u = +X, v = +Y; `bottom` u = +X, v = −Y. All lengths
are integer nm; there are no angles (mount rotation is the board's business, c0308).

### 2. The document

```json
{
  "schema": "fenolite.enclosure.v0",
  "id": "fenolite-box-120x80x40",
  "fits": {"maker": "", "series": "", "parts": [], "material": "ABS"},
  "licence": "CC0-1.0",
  "provenance": {
    "basis": "datasheet", "source": "https://example.org/box-120x80.pdf", "revision": "A",
    "read": "2026-10-30", "author": "Fenolite contributors", "links": [], "note": "authored for Fenolite"
  },
  "outer": {"length": 120000000, "width": 80000000, "z_min": -2500000, "z_max": 37500000},
  "cavity": {"floor": [115000000, 75000000], "rim": [115600000, 75600000], "depth": 35000000,
             "corner_radius": 3000000},
  "lid": {"split_z": 30000000, "underside_z": 35000000},
  "obstacles": [
    {"name": "C1", "kind": "column", "circle": {"x": -52000000, "y": -32000000, "d": 7000000},
     "z_min": 6000000, "z_max": 35000000}
  ],
  "mounts": [{
    "name": "bosses", "kind": "bosses", "pcb_bottom_z": 6000000, "thickness": null,
    "bosses": [{"name": "B1", "x": -45000000, "y": -25000000, "d": 6000000, "top_z": 6000000,
                "pilot": 2500000, "screw": {"thread": "M3", "drill": 3200000, "head": 5500000,
                "length": 6000000}}],
    "guides": [],
    "usable": {"points": [[-55000000, -35000000], "…"], "arcs": [{"edge": 0, "mid": ["…"]}]},
    "zones": [{"name": "lid", "side": "top", "region": {"points": ["…"]}, "z": 35000000},
              {"name": "C1", "side": "top", "region": {"points": ["…"]}, "z": 6000000},
              {"name": "floor", "side": "bottom", "region": {"points": ["…"]}, "z": 0}]
  }],
  "faces": [{"name": "front", "wall": 2500000,
             "flat": {"u_min": -54000000, "u_max": 54000000, "v_min": 2000000, "v_max": 28000000}}],
  "clearances": {"wall": 500000, "obstacle": 500000, "lid": 500000, "floor": 500000},
  "tolerances": {"/outer/length": 300000},
  "fields": {"default": {"basis": "datasheet", "evidence": "INFERRED"},
             "/lid/underside_z": {"basis": "assumed", "evidence": "UNKNOWN"}}
}
```

The values above are invented for this design. The `"…"` entries are elided here; a document holds no
string where a number belongs.

- `id` matches `^[a-z0-9][a-z0-9-]{2,63}$` and is the file stem (`<id>.enclosure.json`).
- `fits` describes what the model fits, for the wording "fits <series> <part> (per datasheet rev. X)". It
  is never the model's name and holds no logo or trademark beyond the words needed to identify the box.
- `cavity.floor` and `cavity.rim` are `[length, width]` at Z = 0 and at Z = `depth`; between them the walls
  are linear (draft). `corner_radius` rounds the cavity's vertical edges.
- `obstacles` are vertical prisms (a `circle` or a `region` polygon) with a Z range: lid screw columns,
  ribs, battery holders moulded in. Support bosses belong to their mount.
- A mount `kind` is `bosses` (board on bosses, screwed), `guides` (board in wall slots: `wall`,
  `slot_width`, `slot_depth`, `z`, `from`, `to`; `thickness` is then `{min, max}` from the slot) or `floor`
  (board on the floor or on pads, no holes). `pcb_bottom_z` is the Z of the board's bottom face.
- `usable` and `zones` are **derived** fields (decision 4). `zones[].z` is the absolute Z of the surface
  that bounds parts: for `top` the lowest surface above the board in that region, for `bottom` the highest
  below it. The limit of a zone is computed by c0308 from the board's thickness and the clearances.
- `faces[].flat` is the flat, drillable rectangle of the face in its own frame, without radii, ribs or the
  split line's lip. `wall` is the wall thickness at that face.
- `clearances` are Fenolite's fit clearances (not the drawing's); defaults 0.5 mm each when absent,
  stated as parameters, not facts.
- `tolerances` maps a JSON pointer to the drawing's ± tolerance in nm.
- `fields` maps a JSON pointer (or `default`) to `{basis, evidence}`. `basis` is `datasheet`, `measured`
  (a physical sample by the author), `local-step` (measured against the user's vendor STEP on the user's
  machine), `derived` or `assumed`. `evidence` is a level name of `core.evidence`; a field is never above
  `INFERRED` in v0. Derived fields take the weakest evidence of their inputs.

### 3. Reader and writer (`fenolite.model.enclosure`)

Frozen dataclasses `Enclosure`, `Fits`, `Provenance`, `Cavity`, `Lid`, `Obstacle`, `Mount`, `Boss`,
`Screw`, `Guide`, `Zone`, `Face`, `Flat`, `Clearances`, `FieldNote`; `load_enclosure(text) -> Enclosure`,
`dump_enclosure(box) -> str`. The writer follows the canonical form (two-space indent, LF, field order,
defaults omitted, sorted maps and named lists by name). The reader validates against the schema, then the
structural rules: positive lengths; unique names; `z_min < 0 < depth ≤ z_max`; `split_z ≤ underside_z ≤
z_max`; every boss inside the floor rectangle; `pcb_bottom_z` within `[0, depth)`; face names from the six;
each pointer of `tolerances` and `fields` names an existing field; each evidence a known level. A failure
raises `FormatError` with the pointer; the command maps it to exit 3 `FEN-3009`.

### 4. Derivation (`fenolite.enclosure.derive`)

`derive(box) -> Enclosure` fills `usable` and `zones` of every mount; pure, integer, deterministic:

1. **Cavity at board level.** The board occupies Z from `pcb_bottom_z` to `pcb_bottom_z + t`, where `t` is
   the mount's `thickness.max` or 1.6 mm when the mount names none (a parameter, recorded in `fields`).
   The cavity rectangle is interpolated linearly at both Zs; the smaller is kept, rounded by
   `corner_radius` (arcs), inset by `clearances.wall`.
2. **Obstacles through the board.** Each obstacle whose Z range meets the board's Z range, grown by
   `clearances.obstacle`, is subtracted. A circle becomes a ring with arcs (`OutlineArc`), so notches stay
   exact.
3. **Guides.** For `guides`, the usable area is the rectangle between the slot bottoms, along the slot
   span, inset by `clearances.wall` only at the open ends.
4. **Zones.** `top`: one zone `lid` over the usable area with `z = lid.underside_z`, plus one zone per
   obstacle above the board (grown by `clearances.obstacle`) with `z = obstacle.z_min`. `bottom`: one zone
   `floor` with `z = 0`, plus one zone per boss (grown by `clearances.obstacle`) with `z = boss.top_z` (a
   bottom-side keep-out where the board rests) and one per obstacle below the board with its `z_max`.
5. Polygons are written with the geometry package's integer rounding (outward for areas that bound
   parts, inward for the usable area), so a derived area is never larger than the exact one.

`show` re-derives and compares: a stored derived field that differs gives `enclosure.model-drift`
(error). The arcs make most comparisons exact; a 1 nm rounding difference is not drift.

### 5. Package `fenolite.enclosure`

New sub-package → `model`, `geometry` (MODIFIED "Allowed import edges"); like `roles`, only `cli` and the
root modules may import it. c0309's judge and c0310's templates live here; `checks` receives the judge
injected (as `roles.rules` does).

### 6. Command actions

- `fenolite enclosure show BOX [--mount NAME]`: read-only; `result` holds `id`, `fits`, `licence`,
  `provenance`, `mounts` (name, kind, usable area in mm², zones with their Z), `faces`, `weakest` (the
  lowest evidence of any field), `drift` (pointers). Issues: `enclosure.model-drift` (error),
  `enclosure.field-assumed` (warning, one per `assumed` field), `enclosure.boss-outside` (error: a boss
  outside its usable area grown by its own radius). Exit 5 on an error.
- `fenolite enclosure derive BOX`: plans the rewritten document with fresh derived fields through the
  mutation protocol; nothing else changes.

### 7. Fixtures

`tests/data/enclosure/` holds three boxes authored for Fenolite with invented, round dimensions: a box with
four corner bosses and two lid columns; a box with card guides; a floor-mount box with a drafted cavity.
Each carries `licence: "CC0-1.0"`, `provenance.basis: "assumed"` and the note "authored for Fenolite; fits
no product". Expected derived areas are computed by hand in the test file, not by the code under test.

## FEN- and issue codes

| code | kind | when |
|---|---|---|
| `FEN-3009` | exit 3 | a box model or a fit record (c0308) breaks its schema or a structural rule |
| `enclosure.model-drift` | error | a stored derived field differs from the derivation |
| `enclosure.boss-outside` | error | a boss lies outside its mount's usable area |
| `enclosure.field-assumed` | warning | a field whose basis is `assumed` |

## Hypotheses registered by this change

- `H-G-ENCL-DERIVED`: the derived usable areas and zones of the fixture boxes equal the hand-computed ones,
  and no point of a usable area lies inside an obstacle or boss envelope.
- `H-G-ENCL-CANON`: `dump_enclosure(load_enclosure(t))` is byte-identical to `t` on Linux, Windows and macOS.

## Evidence per behaviour

Reader, writer, derivation: `INFERRED` by tests. Box fields: as their `fields` entries say, never above
`INFERRED`.

## Risks / Trade-offs

- **Datasheets omit ribs and lid columns.** A model that misses one gives a confident wrong area. The
  basis `assumed` and the warning keep this visible; c0309 adds a first-board warning.
- **Linear draft** is an approximation; drafted walls with steps need an obstacle.
- **Schema growth.** v0 may need fields for gaskets or flanges; additions with defaults keep v0.

## Open Questions

1. Store `usable` and `zones` in the document, or derive them on every read? Recommended: store them
   (the DSL cannot import geometry) and detect drift in `show`.
2. Should `fits.maker` be allowed at all in our models? Recommended: yes, as plain words needed to identify
   what the model fits, never as the model's name or with a logo.
3. Default board thickness for derivation when the mount names none: 1.6 mm? Recommended: yes, as a
   recorded parameter; c0309 reports `enclosure.thickness-mismatch` when the board differs.
4. Should v0 hold a per-field label above `INFERRED` after a sample measurement? Recommended: no; keep the
   basis `measured` and decide a label with stage 2.

## Relation to the other changes

c0306 places a user's STEP; this change gives the box as data. c0308 reads `usable`, `zones`, bosses and
faces; c0309 judges against them; c0310 draws faces. Stage 2 (`lgili/fenolite-library`, `enclosures/`)
stores real boxes in this format with `PROVENANCE.json`; it is referenced here, not specified.

## Size

About 6 design-days: model and reader 1.5, schema and canonical tests 0.5, derivation 2, command actions
1, fixtures and docs 1.
