## Why

An internal plane layer of an Altium PCB document is stored in negative: the layer is copper, and an object drawn on it is a place without copper (a split line, a blow-out, the pull-back at the board edge). The import (`adapter/copper.py`) reads such a layer as one more copper layer of the chain, so a free line on it becomes a `Track` without a net: copper where the board has none.

Change c0088 found the consequence on two public documents: 71 false shorts and 48 false clearance findings, every one between such a line and a via or a pad. It corrected the view that the copper check gets (`backend._without_plane_lines`) and left the import as it was. The model stayed wrong for every other reader: level 5 of `equivalent` counts the lines as copper on no net (74 and 43 items, where KiCad's import of the same documents holds none), and a rewrite of the first of the two documents writes its planes as signal layers and the 74 cut lines as tracks on them, which is the opposite of the board that was read.

The maintainer decided on 2026-10-06 that the correction belongs in the importer.

## What Changes

- **A free primitive on the layer of an internal plane is no entity of the model.** A track, an arc, a fill, a region or a text on a layer of the chain whose Altium id is 39 to 54 gives no `Track`, `Arc`, `Graphic` or `Text`, with or without a net. This is a change of behaviour: **an imported board with internal planes holds fewer tracks**.
- **Nothing is dropped silently.** Each such record is counted in the census as `plane-cuts` (`altium.import.unmapped` names the count), and the layer of the plane holds the count in its `altium` bag (`plane_cuts`). The values stay in the reader's records.
- **The copper view loses its filter.** `backend._without_plane_lines` and `PLANE_KEY` are removed; `DesignRules.design` holds every track of the import. The copper check still reports the planes as copper it did not judge (`copper.item-unsupported`, `where` = `plane`, level `UNVERIFIED`): the entry of `DesignRules.left_out` is now built from the layers and the import's count.
- **A plane is known by its layer id**, not by its net name: a plane on no net is a plane too.
- **Measured again:** the copper check, RT-A3, the container round trips and level 5 against KiCad's import, on the public documents.

Size: 1.25 design-days (a size, not time); cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-import`: MODIFIED "Layers and stack-up" (what a plane is, `plane_cuts`), "Tracks, arcs and vias", "Outline, graphics and texts" and "Unmapped records are counted" (`plane-cuts`); ADDED "Objects on an internal plane".
- `altium-verification`: MODIFIED "Clearance rules of a PCB document" (a requirement of c0088: nothing is taken out, and what `left_out` holds).

## Non-goals

- No copper for the plane itself: the model has no negative copper, and a zone for a plane with keep-outs for its cuts is a representation this change does not choose. The design says what it would take.
- No change of c0088's other correction of the view: a zone still gets the clearance 0 there, and a clearance rule the slack of the unit.
- No change of the model, of `DesignRules`, of the writer or of any KiCad output.
- No new issue code: the census of `altium.import.unmapped` counts the records.
- No change for a primitive of a component or of a polygon on a plane layer: those were not lowered before.
- No code or constant from any private project or organisation; test data is authored for Fenolite or fetched from the public rows of the corpus manifest.
- No format fact from a decompiled tool or a transcribed parser: every fact gets a row in `docs/formats/altium/*.md` with a public source of `docs/evidence/sources.md` and a label.

## Evidence level required

- That an object on an internal plane layer is a void is a format fact from Altium's documentation (S-0531, S-0550): `INFERRED` under `H-A-IMP-PLANE-CUT`, and `ORACLE-VERIFIED(kicad-cli 10.0.x)` when KiCad's import of the public documents with planes holds as many tracks as Fenolite's read and no track on a plane layer.

## Impact

- Changed: `backends/altium/adapter/layers.py`, `adapter/copper.py`, `adapter/ids.py` (one bag key), `backends/altium/backend.py`, `backends/altium/import_evidence.py`.
- Tests: `tests/unit/backends/altium/adapter/test_plane_cuts.py` (new), `test_ext.py`, `tests/unit/backends/altium/test_frame.py`, `tests/corpus/test_altium_copper.py`, `tests/corpus/test_altium_rta3.py`, `tests/kicad/equivalence/test_triangle_level5.py`.
- Pages: `docs/altium.md`, `docs/formats/altium/import.md`, `docs/evidence/altium-roundtrip.md`, `docs/evidence/equivalence-triangle.md`, `docs/evidence/sources.md`, `docs/hypotheses.md`.
- An imported board with internal planes changes its content: fewer tracks, and one more pair in the bag of a plane layer. Boards without a plane layer are unchanged, and so is every committed sample.
- Depends on: c0043 (the import), c0088 (the view this change replaces; archived before this one). c0090's RT-A3 table and c0089's triangle page are measured again.
