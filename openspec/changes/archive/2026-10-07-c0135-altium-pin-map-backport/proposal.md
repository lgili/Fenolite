## Why

An Altium build ignores `pad_map`. `Part(..., pad_map={"1": "2", "2": "1"})` tells a build that pin 1 of the symbol is pad 2 of the footprint. The living requirement "Per-component pin-to-pad mapping" of `design-dsl` says what a build does with it: "The DSL build SHALL assign each symbol pin's net to the physical footprint pad named by `Component.pin_pad_map`, using identity mapping for pins not listed", and "A mapping with a missing source pin, missing pad target, or duplicate physical target MUST report `build.pin-pad-map-invalid` as an error and write no output."

The KiCad build does both. The Altium build does neither, in the releases 0.1.0 and 0.2.0:

- **The PCB document is wrong.** `lens/altium.pcb_document` keys the nets of a component by pin number, and `pcbdoc.py` looks them up by pad number. For the map above the two nets of the part are exchanged on the board. The two targets disagree on one script.
- **The schematic says nothing of the map.** The footprint model of the sheet and of the library holds an empty map list (record 46 without a record 47). Without a board document the map is lost; with one, the sheet and the board no longer say the same once the board is right.
- **An invalid map is not refused.** A map that names a pin the symbol lacks or a pad the footprint lacks, or that leaves one pad to two pins, builds without a word.
- **The check of a copper source ignores the map too.** `altium_copper.match_source` compares the pads of script copper, or of a `--copper-from` board, with nets keyed by pin: a design with a map and any track is refused with a message that names the wrong net, also against the KiCad board of its own script.

No committed sample, golden or example holds a `pad_map`, so no test saw it.

## What Changes

- **The PCB document applies the map.** A pad carries the net of the pin that names it, and the check of a copper source reads the same nets by pad, so a routed design with a map builds and a board routed for another assignment of the pads is refused with a true message.
- **The schematic and its library hold the map**, as map records of the footprint model: one record 47 for each pin whose pad is not the pad of its own designator. This is the form Altium saves.
- **An invalid map is refused**: `altium.pin-pad-map-invalid` (error, exit 5, nothing written) for a pin the symbol lacks, for a pad the resolved footprint lacks, and for a pad that two pins stand for, as the KiCad build refuses them.
- **Nothing else moves.** A script without a `pad_map` builds the same files, byte for byte. The model, its canonical JSON and its schemas are untouched: one pad per pin, as 0.2.0 has it.

Size: 1 design-day (a size, not time).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-schematic-writer`: ADDED "Pin map records of a footprint model".
- `altium-build`: ADDED "Pin maps in an Altium build".

The two requirements carry the names that change c0123 (a pin bonded to several pads, on `dev`) gives them, restricted to one pad per pin, so that c0123 modifies them when the two meet.

## Non-goals

- No pin with several pads, no change of the model, of the canonical JSON or of a schema.
- No change of the import: it reads the map records and does not put them into the model, as before.
- No change of what RT-A2 compares, and none of `fenolite check`: on a project built from a script with a renaming map it still reports `netlist.assignment-differs` (exit 5), because 0.2.x compares the schematic by pin number and the board by pad number. The files are right; the comparison learns the map in 0.3.0. A test states it, and the changelog and `docs/altium.md` say it.
- No claim that Altium applies a written map record: that is an author report still to come.
- No code or constant from any private project or organisation; test data is authored for Fenolite or fetched from the public rows of the corpus manifest.
- No format fact from a decompiled tool or a transcribed parser: every fact gets a row in `docs/formats/altium/*.md` with a public source of `docs/evidence/sources.md` and a label.

## Evidence level required

- The written records: `INFERRED` under `H-A-SCHX-PINMAP` (read back by Fenolite's readers of the sheet and of the library; pending an author report for what Altium does with them).
- The form of the records, a record only for a pin with another pad than its own: `CORPUS-VERIFIED` under `H-A-SCHX-PINMAP-FORM`, counted on four public project sets by a test of this branch. It says what Altium saves, not that Altium applies what Fenolite writes.
- The nets of the PCB document rest on the rows the document already has (`H-A-PCB-DOC-NETS`); the envelope of the Altium build stays `INFERRED`.

## Impact

- Changed: `lens/altium.py`, `lens/altium_copper.py`, `backends/altium/altsym.py`, `layout.py`, `project.py`, `schdoc.py`, `schlib.py`, `cli/data/explain.toml`.
- Pages: `docs/altium.md`, `docs/dsl.md`, `docs/formats/altium/connectivity.md`, `docs/hypotheses.md`, `CHANGELOG.md`.
- Behaviour that changes, only for a script with a `pad_map` built for the Altium target: the nets of the mapped pads in the PCB document; the map records in the sheet and in the library; what the check of a copper source accepts and refuses; a refusal where an invalid map was built. A project built with 0.1.0 or 0.2.0 from such a script must be built again; the changelog says how.
- Depends on: c0056 (`pad_map`), c0035 (the PCB document), c0034 (the schematic library). No new dependency.
