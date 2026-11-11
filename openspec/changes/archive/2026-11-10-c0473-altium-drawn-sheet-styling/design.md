# Design: c0473-altium-drawn-sheet-styling

## D1: Carrying `AltiumSheet` in `schematic.toml` and `convert`
- In `drawn_read.extract_with_pins`:
  - Extend `ITEM_FIELDS["label"]` with `"COLOR"`, `"FONTID"`, `"JUSTIFICATION"`, `"WIDTH_FRAC"`, `"HEIGHT_FRAC"` and record `kept[f"label:{len(labels)}"]` for `NetLabel` (`RECORD=25`) as well as `Port` (`RECORD=18`).
  - Record `kept[f"power_style:{len(powers)}"]` (`COLOR`, `FONTID`) for `PowerPort` (`RECORD=17`), reindexed by `_restore_stand_ins`.
  - Record `kept[f"ref:{len(refs)}"]` for `SheetSymbol` (`RECORD=15` `COLOR`/`AREACOLOR`), `SheetName` (`RECORD=32` `LOCATION.X`/`LOCATION.Y`/`FONTID`/`COLOR`), `SheetFileName` (`RECORD=33` `LOCATION.X`/`LOCATION.Y`/`FONTID`/`COLOR`), and `SheetEntry` (`RECORD=16` `TEXTFONTID`/`COLOR`/`AREACOLOR`/`TEXTCOLOR`).
  - Record `kept[f"comp_gfx:{len(symbols)}"]` with the component's drawn pose (`POSE`), `DESIGNATOR_FONTID`, `COMMENT_FONTID`, and `RECORDS` (the `record_line(child, 0)` lines of its shown body graphics and child `Label`s).
- In `importer.schematic.drawing_value`: when `source.sheet_texts` is present, append `DrawnOpaque("", f"|RECORD=41|OWNERPARTID=-1|ISHIDDEN=T|NAME=Fenolite.Altium.Sheet|TEXT={AltiumSheet(carrier.sheet, (), carrier.fields).text()}")` to each sheet's `opaques`.
- In `sheet_carrier.put_drawing` and `backends.altium.drawn.lower_drawn`: unpack any `Fenolite.Altium.Sheet` opaque carrier item from `sheet.opaques` so it populates the sheet's `AltiumSheet` `sheet` and `fields` without being emitted as a literal `RECORD=41` or altering `compare_drawn`.

## D2: Applying carried Altium styling in `backends.altium.drawn`
- Gate the styling restoration on `bool(sheet_fields or sheet_text)` so authored KiCad drawings without Altium carriers (such as `examples/drawn` in `tests/data/build_bytes.json`) keep their exact bytes.
- When `sheet_text` holds `|RECORD=31|...` and the sheet size was not grown, set `SheetPlan.sheet_record` from that `RECORD=31` line (excluding `FILEVERSIONINFO`). When `sheet_text` holds `|RECORD=39|...` (`Template`), emit `RECORD=39` and its `@<line>` children (skipping `RECORD=30` `Image` with `EMBEDIMAGE=T` when `Storage` has no image stream).
- In `_Sheet.component`: when `comp_gfx:{index}` matches the component's pose, emit the carried body graphic records with `OWNERINDEX` rebased to the component's index instead of the synthesized graphics, and apply `DESIGNATOR_FONTID` / `COMMENT_FONTID`.
- In `_Sheet.identifier`: apply carried `Port` (`RECORD=18`) `WIDTH` (when its far end does not touch a wire/pin on the sheet), `HEIGHT`, `STYLE`, `ALIGNMENT`, `BORDERWIDTH`, `COLOR`, `AREACOLOR`, `TEXTCOLOR`, `FONTID`; apply carried `NetLabel` (`RECORD=25`) `JUSTIFICATION`, `COLOR`, `FONTID`; apply carried `PowerPort` (`RECORD=17`) `COLOR`, `FONTID`.
- In `_Sheet.reference`: apply carried `SheetSymbol` `COLOR`/`AREACOLOR`, `SheetEntry` `TEXTFONTID`/`COLOR`/`AREACOLOR`/`TEXTCOLOR`, and `SheetName` (`RECORD=32`) / `SheetFileName` (`RECORD=33`) `LOCATION.X`, `LOCATION.Y` (defaulting `SheetName` to `12 * UNIT_SCALE` above `SheetFileName` when `has_altium_style`), `FONTID`, and `COLOR`.
