## Why

The Altium import reads a poured polygon as a zone whose fills are the polygon's regions. A region record holds an outline and any number of holes; the reader parses both (`read/pcbprims.py`), and the adapter builds the fill from the outline alone (`adapter/copper.zones`). A pour with holes is solid copper in the model.

Level 5 of `equivalent` (c0089) found the consequence on a public document. Its main pour is one region with 268 holes, and five more regions lie inside holes of it. In Fenolite's read the five touch the main region and are one piece with it; in KiCad's import of the same document they are five pieces that reach no pad. The triangle pins that as one `route-stub` notice with Fenolite as the cause. The copper check has the same fault from the other side: every track, via and pad of another net that passes through a hole of a pour lies inside the solid fill and is reported as a short.

## What Changes

- **A fill keeps its holes.** `ZoneFill.polygon` of an imported Altium pour is one ring in which each hole is joined to the ring around it by a bridge of zero width that is walked once in each direction (a keyhole ring). This is the form in which a KiCad board already stores a filled polygon with holes, so the model, the copper check and level 5 read it as they read a KiCad fill.
- **A helper of the geometry kernel** (`geometry.polygon.keyhole_ring`) builds that ring from an outline and its holes in integers and in a stated order.
- **A hole that does not lie in its outline is dropped and reported**: one `altium.import.zone-hole-outside` warning per document, with the counts.
- **Measured.** The stub notice of the triangle, the pieces without a pad on each side, and what the copper check reports on the imported pour, before and after.

Size: 1.5 design-days (a size, not time); cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-import`: MODIFIED "Zones from polygons" (a fill holds the holes of its region) and "Import issue codes" (one more warning).
- `geometry-kernel`: ADDED "Keyhole ring of a polygon with holes".

## Non-goals

- No change of the model: `ZoneFill.polygon` stays one ring, and no entity gains a field.
- No change of what the Altium writer writes: a polygon is written unpoured (c0085), so no fill reaches a document. The design says what a writer of fills would need.
- No holes on free regions and footprint regions: they are graphics, not copper with a net, and their holes stay counted as `region-holes`. The design lists each place.
- No repair of a document whose holes overlap each other or cross their outline: such a hole is merged as it is given, or dropped when its leftmost vertex is outside the outline.
- No code or constant from any private project or organisation; test data is authored for Fenolite or fetched from the public rows of the corpus manifest.
- No format fact from a decompiled tool or a transcribed parser: every fact gets a row in `docs/formats/altium/*.md` with a public source of `docs/evidence/sources.md` and a label.

## Evidence level required

- The helper is general, with no format fact: `INFERRED` under `H-G-KEYHOLE`, settled by a property test.
- That a hole of a poured region is free of the pour's copper is a format fact: `ORACLE-VERIFIED(kicad-cli 10.0.x)` under `H-A-IMP-ZONE-HOLES` when Fenolite's read and KiCad's import of the public document with such a pour hold the same pieces per net at level 5, without the stub notice.

## Impact

- Changed: `geometry/polygon.py`, `geometry/__init__.py`, `backends/altium/adapter/copper.py`, `backends/altium/adapter/codes.py`, `cli/data/explain.toml`.
- Pages: `docs/geometry.md`, `docs/cli-contract.md` ("Altium import"), `docs/formats/altium/import.md`, `docs/evidence/equivalence-triangle.md`.
- An imported board whose pours have holes gets fills with more points; the content of such a board changes, and so does every result that reads its fills (the copper check reports fewer shorts, level 5 finds the islands).
- Depends on: c0043 (the import), c0029 (the copper check), c0089 (level 5 and its triangle, on whose branch this change is written). Nothing of v0.4 depends on it.
