# c0464: the source's Board6 carried on the way back

## Why

The maintainer's flow A on their own board (S-2230; codes and counts only) gives a `Board6` that the writer
made up, not the source's:
- `DISPLAYUNIT` and `GR0_DISPLAYUNIT` are always 1 (`docboard.py`), where the source holds 0. Altium then
  shows the rules in whole mils: a 0.025 mm rule reads as 1 mil.
- The 16 mechanical layer names (`LAYER57NAME` … `LAYER72NAME`, and the V7, V8 and V9 tables) come back
  as KiCad layer names (`User.1`, `Dwgs.User`, …). "Top Courtyard" does not come back.
- 23 `HASHKEY`/`HASHVALUE` pairs and 5 `SITUSSTRATEGY*` keys are dropped. Grid, snap and view settings
  take the writer's values.

- A black solder mask comes back green: the round trip of public row `-05` (PiDP11) in Altium (S-2234).
  Altium keeps the mask colour in the 3D view settings of `Board6` (`3DCONFIGURATION`,
  `CFG3D.TOPSOLDERMASKCOLOR=0`), which the writer replaced with its own (green, 3307556).

The public rows show the same (S-2231): all eight hold `DISPLAYUNIT`, five of them 0, and five name their
mechanical layers.

## What

- The conversion to KiCad carries the source's `Board6` settings as the board property
  `Fenolite.Altium.Board6.Settings`: every key that occurs once in the record and that the writer owns not
  (below), with its value, in the source's order, each run of them after the source key it followed. The
  names of mechanical layers 1 to 16 travel with them.
- The writer owns the keys that the model or the written document decides: the document's identity
  (`FILENAME`, `KIND`, `VERSION`, `DATE`, `TIME`, `UNIQUEID`), the frame (`ORIGINX/Y`, the outline, the
  sheet, the camera and viewport, grid origins, guides, place markers, movies), the layer stack and its
  tables, layer sets and pairs, planes, routing directions, layer toggles, the xSignals (c0461's carrier)
  and the keys a record line holds twice.
- The conversion back merges the carried settings into the writer's `Board6`: a carried key the writer
  writes takes the source's value; a key the writer does not write is written after the key it followed in
  the source.
- A mechanical layer takes the source's name when the written layer is the source's layer: the KiCad layer
  that reaches it is named `Mech.<n>` (the import's name, `lower.kicad_mechanical`), or no layer of the
  written document holds anything on it. A KiCad layer that the fixed map puts there keeps its KiCad name.

## Not in this change

- Super classes. Every public row holds the same ten built-in super classes in `Classes6` and `All xSignals`
  in `SignalClasses` (S-2231); the writer writes `All xSignals` alone (c0035, c0461). Whether Altium makes
  the others again on opening is a kit question (task 5.2).
- Grids other than `GR0` keep their settings but not their origin (no public row holds one).
- A setting whose text a record line cannot hold (`|`, a character outside printable ASCII) is not carried.

## Impact

- Code: `convert/altium_storages.py`, `backends/altium/docboard.py`, `backends/altium/pcbdoc.py`,
  `backends/altium/lower.py`.
- Docs: `docs/formats/altium/pcb-records.md`, `docs/hypotheses.md` (H-A-CONV-BOARD6),
  `docs/evidence/sources.md` (S-2230 to S-2234), `CHANGELOG.md`.
- Tests: `tests/unit/convert/test_board6_settings_c0464.py`; `tests/unit/convert/test_altium_storages.py`
  (the carried names gain `Board6.Settings`).
