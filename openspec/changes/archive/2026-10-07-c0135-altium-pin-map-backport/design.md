## Context

- `dsl/part.py`: `Part(..., pad_map=…)`, one pad per pin, refuses a pad listed for two pins. `Component.pin_pad_map` holds the pairs.
- `lens/build.py` (KiCad): `_pad_nets` applies the map and reports `build.pin-pad-map-invalid`.
- `lens/altium.py`, `pcb_document`: `nets[component][member.pin] = net.name`, handed to `pcbdoc.PlacedComponent.pad_nets`, which `pcbdoc.py` reads with `pad_nets.get(pad.number)`. The map is not read anywhere under `backends/altium` or in `lens/altium.py`.
- `backends/altium/schdoc.py` and `schlib.footprint_chain`: records 44, 45, 46 and 48 of a footprint model; no record 47.
- The reader of schematic documents and libraries already reads record 47 (`read.sch.MapDefiner`: `DESINTF`, `DESIMPCOUNT`, `DESIMP<i>`; `docs/formats/altium/schematic-records.md`, S-0130, `INFERRED`). The import does not use it.
- The tag's corpus holds the five public project sets (`altium-set:01` to `05`).

## Goals / Non-Goals

**Goals:** the board and the schematic of an Altium build say what the script's `pad_map` says; an invalid map is refused; nothing moves for a script without a map.

**Non-Goals:** everything under "Non-goals" in the proposal.

## Decisions

1. **One place says which net is on which pad.** `altium_copper.pad_net_names(design)` takes the pad of each net member from the component's map (identity for a pin outside it). `pcb_document` hands it to `pcbdoc.py`, which keeps reading by pad number, and `altium_copper.match_source` compares the pads of a copper source with it. The first form of this change keyed the nets by pad in `pcb_document` alone; the check of a copper source still keyed them by pin, so the two disagreed: a routed design with a map was refused against the board of its own script, and a board routed without the map was accepted, with a track then ending on a pad of another net (found in review, reproduced, and covered by `tests/unit/lens/test_altium_pad_map_copper.py`).
2. **A record only for a renamed pin.** `altsym.map_pins` gives a record for each pin of the body whose pad in the map is not the pad of its own designator; `altsym.map_records` writes `DESINTF`, `DESIMPCOUNT=1`, `DESIMP0`. A footprint model that Altium saved holds records only for such pins: counted on the sets 02 to 05, of 295 footprint models 293 hold no record, one holds 6 records for 6 pins (none an identity) and one holds 1 record for 8 pins, and all 7 records number their pads from `DESIMP0` (`tests/corpus/test_altium_map_records.py`). A component without a map therefore writes record 46 without a child, the bytes of 0.2.0.
3. **The library holds the map only on the footprint its model names.** A library component gets the map when every component of its symbol links the footprint that the library's record 45 names and has the same pad for every pin; otherwise none. A part may link another footprint than its symbol's own (the library then still names the symbol's footprint, as before this change), and a map onto that other footprint must not be written onto the library's model. The sheet holds the map of each component in every case. A symbol whose Footprint property is empty has no footprint model in the library and therefore no library map; that is left as it is.
4. **One new issue code**, `altium.pin-pad-map-invalid`, with the name and the conditions c0123 gives it. It is checked after the footprints are resolved, before anything is planned; the pads of a footprint that is not resolved are not checked. Rejected: passing the KiCad build's `build.pin-pad-map-invalid` through, because the Altium build reports its own findings only with the codes of its closed table.
5. **A pad that two pins stand for is refused, as the KiCad build refuses it.** `Part` raises `DslError` for a map that lists one pad for two pins, so that form reaches no build. A map such as `{"1": "2"}` on a part with a pin 2 leaves pad 2 to the pins 1 and 2. Measured at the tag: the KiCad build exits 5 with `build.pin-pad-map-invalid` ("D1 pins 1 and 2 both map to pad 2"), with the two pins on two nets and with both on one net; the Altium build of 0.2.0 ignored the map and wrote a board on which every net kept its pads. With the nets keyed by pad and no rule, one of the two nets would lose its pad without a word, which is worse than 0.2.0; so `pin_map_issues` reports one `altium.pin-pad-map-invalid` per such pad, naming the pad and the pins, whatever their nets, and nothing is written. A script that 0.2.0 built for Altium with such a map is now refused. A pin number that a component lists twice is one pin. c0123 makes the same case an error of the model (`model.pin-pad-map`), which then comes first.
6. **The import is not changed.** It reads the records as records; `Component.pin_pad_map` of an imported component stays empty on this branch, so RT-A2 keeps the field outside its scope, with the reason corrected in `docs/altium.md`.
7. **Where the facts of the written record stand.** The two counted facts are rows of `docs/formats/altium/connectivity.md`, "Component link" (`CORPUS-VERIFIED`, `H-A-SCHX-PINMAP-FORM`), and a third row says what Fenolite writes (`INFERRED`, `H-A-SCHX-PINMAP`): the record directly after record 46, with an owner key in a document and without one in a library, where no record carries an owner and a reader takes the record as part of the component it follows. The guard of the format pages (`tests/unit/test_format_facts.py`) accepts an `INFERRED` row only with a hypothesis of the families it lists; this change adds the family `H-A-SCHX-` to that list, which the development line already has.
8. **No evidence constant changes.** The two rows are in the register; `H-A-SCHX-` is no stem of the build's evidence on this branch, so no envelope lists them and no output of a script without a map moves.

9. **A pad name that no record holds is a finding.** The build checks each pad of a map with the texts of its component (`altium.text-unwritable`); without that the writer raised and the command ended with exit 1.
10. **A part of an Altium link.** Its pins are the designators its nets and marks use, since the symbol is not known. A pair of its map whose pin no net uses is therefore not reported as a pin the symbol lacks; it gets no record, because the generic body has no such pin.
11. **`fenolite check` is not changed.** On a project built from a script with a renaming map it reports `netlist.assignment-differs` and exits 5: 0.2.x compares the schematic by pin number and the model and the board by pad number. Before this change it reported the board too. Teaching the comparison the map needs the import to carry it, which is c0083 and c0123 on the development line and no patch. `test_check_still_compares_the_schematic_by_pin` states the behaviour.

## Files and public API

- `src/fenolite/lens/altium_copper.py`: `pad_net_names(design)`, read by `pcb_document` and by `match_source`.
- `src/fenolite/lens/altium.py`: `pin_map_issues(design, footprints)`, `ALTIUM_ISSUE_CODES["altium.pin-pad-map-invalid"]`.
- `src/fenolite/backends/altium/altsym.py`: `PinPads`, `map_pins(component, designators)`, `map_records(pin_pads, owner=None)`, `AltiumSymbol.pin_pads`; `layout.PartSpec.pin_pads`; `project.part_specs`, `project.library_symbols`; `schdoc.py`; `schlib.footprint_chain(library, footprint, pin_pads=())`.
- Tests: `tests/unit/lens/test_altium_pad_map.py`, `tests/unit/lens/test_altium_pad_map_copper.py`, `tests/_altium_padmap.py` (shared helpers), `tests/unit/lens/test_altium_issues.py` (the closed set, two cases), `tests/corpus/test_altium_map_records.py`; `tests/unit/test_format_facts.py` (the family `H-A-SCHX-`).

## Sources registered by this change

- None. Records 46 and 47 are rows of `docs/formats/altium/schematic-records.md` (S-0130); the counts are read from the files of the sets of S-0188, S-0174, S-0176 and S-0175, which the corpus manifest lists.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-SCHX-PINMAP | A written map record is read back to the pad of its pin, and Altium applies it | `tests/unit/lens/test_altium_pad_map.py`; an author report | the records read back equal the script's map in both forms and in the library; Altium shows the pad on the pin and proposes no change of a net of the part |
| H-A-SCHX-PINMAP-FORM | Altium saves a map record only for a pin whose pads are not the pad of its own designator, its pads numbered from 0 | `tests/corpus/test_altium_map_records.py` | the counts of decision 2 |

The ids are those of change c0123 on `dev`, so the two registers meet in one row each.

## For the merge with c0123

c0123 (on `dev`) supersedes this code: its `map_pins` reads several pads per pin through `Component.pads_of`, its `map_records` writes `DESIMPCOUNT` of any number, and its import puts the records into the model. Its two requirements of the same names turn from ADDED into MODIFIED, written from the text of this change.

## Risks / Trade-offs

- [Altium does not apply a written record] → the board is right either way; the author report settles the row, and a script without a map is untouched.
- [The files of a script with a `pad_map` change in a patch release] → that is the correction; the changelog says so.

## Migration Plan

- None for a script without a `pad_map`. A script with one that was built for Altium with 0.1.0 or 0.2.0: build again. Verified on the tag: the PCB document, the sheet and the library change and the files they replace are kept as `.bak`; a PCB document edited since its build stops the rebuild with exit 7 (`build.layout-exists`), and `--discard-layout` or another folder gets past it; a board laid out from the old document has the nets of the mapped pads on the wrong pads. The changelog says all of it.
- Rollback: the two edits of `lens/altium.py` and the two calls of `map_records`.

## Open Questions

- **Does Altium take pin N for pad N when a footprint model holds no record for it?** Default: yes, which is what the partial form relies on and what the public files show Altium saving. The author report on a built sample answers it.
