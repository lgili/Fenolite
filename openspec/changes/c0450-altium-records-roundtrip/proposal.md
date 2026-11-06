# c0450: Altium records that the round trip through KiCad loses

## Why

The round trip Altium → KiCad → Altium of the public rows writes back records that are not the source's,
or none at all (S-2090). On row `-01` (BMS):
- **Fills.** `Fills6` 2 → 0: a fill comes back as a region.
- **Classes.** `Classes6` 39 → 4: component classes are dropped; net classes survive.
- **Storages without a model entity.** `UnionNames`, `EmbeddedFonts6`, `BoardRegions` and
  `CustomMaskShapes` are absent.
- **Index-bound storages.** `PrimitiveGuids`, the saved violation records (`T*Violation`) and
  `WaivedViolations` are absent, with no report row.
- **Flagged keep-out strokes.** These come back as regions, round ends as ten-sided polygons. A plain stroke
  of the Keep-Out layer already comes back as a stroke (c0442).

KiCad holds no fill, no union and no Altium font. The KiCad board is the only file the conversion writes
between the two legs, so whatever the second leg needs must travel in it.

## What

- **Fills stay Fills.** A fill read from Altium gets a KiCad uuid tagged as an Altium fill. The KiCad
  board keeps that uuid on its rectangle or polygon, even through an edit in KiCad. The Altium writer
  writes a filled rectangle, or a four-corner rectangle polygon, that carries the tag as a fill record
  (type 6) of its layer, net and owner, in the 50-byte form of the public census (S-2091).
- **Storages travel as board properties.** The conversion to KiCad copies each carried storage of the
  source document to a board-level `(property "Fenolite.Altium.<storage>" "<value>")`.
  - The carried storages are `UnionNames` and `EmbeddedFonts6` (`BoardRegions` and `CustomMaskShapes`
    were carried here and are not since change c0459), plus the component classes of `Classes6` as `Classes6.Component`.
  - The value is the base64 text of the zlib-compressed bytes of the storage's `Header` and `Data` streams.
  - KiCad keeps such a property on a save (S-2092).
  - The conversion to Altium writes each carried storage back in place of an empty one. A component class
    is merged into `Classes6` unless the writer already wrote a class of its name.
- **Index-bound storages are a declared loss.** `PrimitiveGuids`, the `T*Violation` storages and
  `WaivedViolations` refer to primitives by index, and the round trip renumbers primitives. The
  conversion to KiCad counts them lost under `altium-storage`, with a reason; nothing carries them.
- **Flagged keep-out strokes.** The marker of c0442 also names a stroke that holds the keep-out flag and its
  restriction byte. The writer writes it back as a flagged track or arc, in the long form of the census.
  The second ring of a c0442 circle now pairs with its first, so a plain circle also comes back whole.

## Not in this change

- An Altium → Altium write of a model (flow A). The storages travel only through a conversion.
- Fills that a KiCad user draws: only a tagged rectangle is a fill.

## Impact

- Code:
  - `convert/altium_to_kicad.py`, `convert/altium_storages.py`, `convert/to_kicad.py` and
    `convert/to_altium.py`;
  - `backends/altium/pcbrecords.py`, `pcbdoc.py`, `lower.py`, `fills.py` and `keepout_lines.py`;
  - `backends/altium/adapter/copper.py` and `adapter/ids.py` (the bag key `stroke`).
- Docs:
  - `docs/formats/altium/pcb-records.md` and `docs/formats/altium/import.md`;
  - `docs/formats/kicad/board.md`;
  - `docs/evidence/sources.md` (S-2090 to S-2093);
  - `CHANGELOG.md`.
