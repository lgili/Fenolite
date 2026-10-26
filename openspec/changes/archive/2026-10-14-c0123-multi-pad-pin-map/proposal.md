## Why

`Component.pin_pad_map` gives a pin one pad. A part whose pin is bonded to several pads cannot be said in the model: a regulator whose tab and one pad are one pin, a connector whose shield pin has four pads, a footprint model in Altium that lists several pads for a pin. The requirement of the model says so in words ("each source and target unique"), and eight places in the code turn the pairs into a mapping of one pad per pin.

The Altium import (c0083) meets such parts in a public project. It keeps the further pads in an extension bag (`pin_pads`), reports their count (`altium.import.pin-map`) and applies none of them: on `altium-set:02` four elements of the assignment comparison stay covered by the PCB document only (`docs/evidence/altium-roundtrip.md`). A script cannot say such a part at all, and the Altium build ignores the map altogether: it gives the PCB document its nets by pin number.

## What Changes

- **The model.** A pin may occur in several pairs of `pin_pad_map`; its pads are the pads of its pairs, in map order. The field, its type and its place in the canonical JSON do not change, so a design whose pins have one pad each is written byte for byte as before, and a document written before this change reads as it is. The model version stays `"0"`.
- **Two readers and a guard.** `Component.pads_of(pin)` and `Component.pin_pads()` are the only code that turns pairs into pads; a test refuses `dict(….pin_pad_map)` anywhere else. `Design.validate()` reports `model.pin-pad-map` for a pair twice and for a pad that two pins name.
- **The DSL.** `pad_map={"3": "5"}` stays; `pad_map={"3": ("3", "EP")}` bonds a pin to several pads.
- **The KiCad build.** Every pad of a pin takes the pin's net. The generated schematic embeds one stacked, hidden pin per further pad, so KiCad's netlist, its ERC and its parity test see the pads; Fenolite's own netlist and the netlist guard read them.
- **The comparisons.** `netlist.assignment_compare` and level 2 of `equivalent` name every pad of a pin.
- **The Altium import.** A map record of several pads gives one pair per pad. The bag `pin_pads` and `altium.import.pin-map` keep only what the model still cannot say: a record without a pad, and a pad that another pin holds.
- **The Altium build.** The pads of the PCB document take their nets through the map, and the schematic writes the map as records of the footprint model. The round trip RT-A2 compares it.
- **Proved.** Every committed golden stays untouched. Builds of the designs that hold a map of one pad per pin are pinned by digest before any code changes. The row of `altium-set:02` is measured again.

Size: 5.5 design-days (a size, not time); cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-model`: MODIFIED "Persist per-component pin-to-pad maps".
- `design-dsl`: MODIFIED "Per-component pin-to-pad mapping".
- `kicad-schematic`: ADDED "Pins with several pads on a generated sheet"; MODIFIED "Embedded symbols of a generated sheet", "Own netlist of a generated sheet", "Netlist grammar check".
- `kicad-oracle`: ADDED "Stacked pins pass ERC, the netlist export and parity".
- `verification-loop`: ADDED "Assignment comparison names every pad of a pin".
- `design-equivalence`: ADDED "Level 2 names every pad of a pin".
- `altium-import`: MODIFIED "Pin-to-pad map of a footprint model".
- `altium-schematic-writer`: ADDED "Pin map records of a footprint model".
- `altium-build`: ADDED "Pin maps in an Altium build".
- `altium-verification`: ADDED "Pin maps in the Altium round trips".

## Non-goals

- No pad that two pins share: a pad is named by one pin, and an Altium record that says otherwise stays in the bag and is counted.
- No pin without any pad: a record that lists no pad stays in the bag and is counted.
- No change of what the BOM, the placement file, the parity comparison and level 3 of `equivalent` compute: the design says for each why it does not read the map.
- No map derived when a KiCad board or schematic is read: pads that share a number, and stacked pins of a sheet, stay what they are in the file.
- No regenerated golden and no changed recorded acceptance project.
- No new model version and no migration of stored documents.
- No claim that Altium applies a written map: the build stays `INFERRED` until an author report says so.
- No code or constant from any private project or organisation; test data is authored for Fenolite or fetched from the public rows of the corpus manifest.
- No format fact from a decompiled tool or a transcribed parser: every fact gets a row in `docs/formats/altium/*.md` or `docs/formats/kicad/*.md` with a public source of `docs/evidence/sources.md` and a label.

## Evidence level required

- The model change holds no format fact. Its promise, equal bytes for a design of one pad per pin, is `H-G-PINMAP-BYTES`: `INFERRED`, settled by the pinned builds and the untouched goldens.
- Stacked pins in KiCad are a format fact: `KICAD-VERIFIED (9.0.9, 10.0.6)` under `H-K-SCH-STACKED` and `H-K-SCH-STACKED-OPEN` when the generated sheets pass ERC, the netlist export equals Fenolite's own netlist and the parity test reports nothing on both majors. The evidence constants of `sch_netlist` and of the generator are not changed, so the envelopes of a design without such a pin keep their bytes; a design that holds such a pin lists the two rows in its evidence.
- The meaning of an Altium record with several pads: `INFERRED` under `H-A-IMP-PINMAP-MULTI`, measured on the one public set that holds such records.
- The written Altium map: `INFERRED` under `H-A-SCHX-PINMAP` (read back by Fenolite's readers; the numbering of its keys counted on the corpus).

## Decision of the maintainer (2026-10-06): inside v0.3 (named v0.4 on that day)

- **Names.** Since change c0136 the Altium write side is v0.3 and is released as `0.3.0`; the decision below was written when it was called v0.4, and reads so.
- **Question.** Does the pin of several pads enter the model now, in v0.4, or after it?
- **Recommendation that was written.** Defer it: it is a change of the design model, it touches the KiCad schematic generator whose outputs were released in 0.2.0, and nothing of v0.4 fails without it; the import already keeps the further pads in a bag and says so.
- **Decision.** Inside v0.4, against that recommendation. A bag that no consumer reads is a fact the model does not hold, and the Altium write of v0.4 (c0090) would have to list it as lost on every round trip.
- **Conditions of the decision.**
  1. Every KiCad output of release 0.2.0 stays byte-equal for a design with one pad per pin: schematic, board, netlist, parity, BOM, placement file. The proof uses the existing goldens and recorded acceptance projects; none is regenerated.
  2. The change is stated as a change of the design model: version, canonical JSON, schemas, old documents.
  3. The DSL keeps its spelling for one pad per pin and gains one for several.
  4. The four elements of `altium-set:02` are measured before and after.
- **To defer after all.** Drop this change; nothing of c0083 to c0092 depends on it. c0090 then lists `pin_pad_map` and `pin_pads` as not written.

## Impact

- Changed: `model/circuit.py`, `model/design.py`, `dsl/part.py`, `dsl/convert.py`, `lens/build.py`, `backends/kicad/schgen.py`, `symembed.py`, `sch_netlist.py`, `checks/assignment_compare.py`, `checks/equivalence/levels.py`, `backends/altium/adapter/circuit.py`, `adapter/parity.py`, `backends/altium/schdoc.py`, `schlib.py`, `roundtrip.py`, `lens/altium.py`, `cli/data/explain.toml`; generated `schemas/fenolite.model.v0/circuit.json`.
- Pages: `docs/design-model.md`, `docs/dsl.md`, `docs/schematic.md`, `docs/formats/kicad/schematic.md`, `docs/altium.md`, `docs/formats/altium/connectivity.md`, `import.md`, `schematic-records.md`, `docs/cli-contract.md`, `docs/evidence/altium-roundtrip.md`.
- Behaviour that changes:
  - a script may give a pin several pads, and every backend applies them;
  - an Altium project whose footprint models list several pads for a pin imports with those pads in the map, so its canonical model changes and its comparisons cover more elements;
  - an Altium build of a script with a `pad_map` puts the nets on the mapped pads (it put them on the pads of the pins' own numbers) and writes the map;
  - `Design.validate()` gains `model.pin-pad-map`, the Altium build `altium.pin-pad-map-invalid`;
  - Fenolite 0.2.x and earlier read a document that holds a pin of several pads without an error and apply one pad.
  - Since the release 0.2.1 (change c0135, merged into this line on 2026-10-07) an Altium build already applies and writes a map of one pad per pin, and refuses a pad of two pins with `altium.pin-pad-map-invalid`. This change adds the several pads per pin to that build, modifies the two requirements c0135 made living, and keeps the build's code beside the model's `model.pin-pad-map`.
- Behaviour that does not change: every output of a design whose pins have one pad each.
- Depends on: c0083 (the import's map, on whose text one requirement is written), c0063 and c0070 (the own netlist and the guard), c0061 (the generator), c0072 and c0088 (parity), c0045 (equivalence), c0086 (the schematic writer). c0090 depends on it for its written scope. No new runtime dependency.
