## Context

- **The model today.** `model/circuit.py`: `Component.pin_pad_map: tuple[tuple[str, str], ...]`, marked `ordered`, `()` by default. The living requirement "Persist per-component pin-to-pad maps" (`design-model`) says that each pin and each pad is unique in the map: one pad per pin. `Design.validate()` checks nothing of the map. `model/canonical.py` writes the pairs in the order held, as arrays of two strings, and leaves out an empty map; `schemas/fenolite.model.v0/circuit.json` lists the field as an array of two-string arrays. `SCHEMA_VERSION` is `"0"` (`model/design.py`), and `canonical.load_dir` refuses any other value.
- **Who reads the map** (every place found by `grep pin_pad_map` over `src/` on 2026-10-06):

| place | what it does today |
|---|---|
| `dsl/part.py`, `Part.__init__` | `pad_map: Mapping[str, str]`; refuses a repeated pin and a pad of two pins |
| `dsl/convert.py`, `_component` | `pin_pad_map=tuple(sorted(part.pad_map.items()))` |
| `lens/build.py`, `_pad_nets` | `dict(part.component.pin_pad_map)`: one pad per pin gets the pin's net; `build.pin-pad-map-invalid`, `build.pad-without-pin`, `build.pin-without-pad` |
| `lens/build.py`, `schematic_netlist_issue` | `dict(c.pin_pad_map)`: the element `REF-<pad>` the generated sheet must hold |
| `backends/kicad/schgen.py`, `generate_schematic` and `_content` | `tuple(sorted(component.pin_pad_map))` as the key of the embedded variant; `dict(component.pin_pad_map)` for `pad_nets` of open pins |
| `backends/kicad/symembed.py`, `variant_name`, `embed_symbol`, `_pins` | the name `<name>_<8 hex>` from the sorted pairs; one pin number replaced per mapped pin |
| `checks/assignment_compare.py`, `model_netlist` | `dict(c.pin_pad_map)`: one element per pin |
| `checks/equivalence/levels.py`, `_elements` | `dict(c.pin_pad_map)`: the parts of a circuit side at level 2 |
| `backends/altium/adapter/parts.py`, `_pin_pads` | reads the map records of the current footprint model as `(pin, pads)`, any number of pads |
| `backends/altium/adapter/circuit.py`, `pin_pad_map(group)` | folds a record to one pad; keeps the rest in the bag key `pin_pads` and counts `altium.import.pin-map` |
| `backends/altium/adapter/project.py`, `link` | `pin_of_pad`, the inverse of the map, for the nets of the PCB document |
| `backends/altium/adapter/parity.py`, `pads_of` | builds pin → pads from the pairs; it already accepts a pin in several pairs |
| `lens/altium.py`, `pcb_document` (the `pad_nets` of `pcbdoc.PlacedComponent`) | does **not** read the map: the nets of a component are keyed by pin number and `pcbdoc.py` looks them up by pad number |
| `backends/altium/schdoc.py`, `schlib.footprint_chain` | write record 46 (`MapDefinerList`) without any record 47 |

- **What does not read it.** `checks/parity.py` compares a `SchematicSide` that already speaks in pad numbers. `exports/bom.py` and the placement export read components and footprints only. The KiCad readers (`pcb.py`, `sch.py`) derive no map. `checks/equivalence/levels.py` level 3 reads footprints and pads of the board.
- **What it costs.** `docs/evidence/altium-roundtrip.md`, "Project sets": on `altium-set:02` four elements are covered by the PCB document only because two pins of the sheets are bonded to two and to four pads and the model names one pad for each. The two records sit in the bag (`pin_pads`), and nothing applies them.
- **A defect found while reading.** The Altium build gives the PCB document the nets by pin number (`lens/altium.py`), so a design whose `pad_map` renames a pad gets that net on the pad of the pin's own number. The KiCad build of the same script applies the map. No test covers a map in an Altium build.
- **The goldens.** Three committed outputs pin KiCad bytes: `tests/data/kicad/parity/agree/` (the blink for target 10, board and schematic; `tests/unit/cli/test_parity_cmd.py::test_example_is_a_fresh_build`), `tests/data/lens/sync_minimal/` (`tests/unit/cli/test_sync_cmd.py::test_example_folder_is_a_fresh_build`) and the four recorded projects of `tests/data/acceptance/` (`tests/kicad/acceptance/test_finished.py::test_rebuild_is_the_identity`). The BOM and placement files are pinned by literals in `tests/unit/cli/test_bom_cmd.py`, `tests/unit/cli/test_pnp_cmd.py` and `tests/unit/exports/test_assembly_guide.py`. **None of them holds a part with a `pad_map`.** The designs with a map (`tests/_schbuild.py::units_design`, at least five of the 25 of `tests/_gendesigns.py`) are covered by determinism and oracle tests only.
- **The branch.** When the proposal was written the branch did not descend from the release commit of 0.2.0. Since the rebase of 2026-10-06 it does (base ba21a109: the release with the changes of v0.4 up to c0090), so the goldens named above are those of the release, and the comparison with the tag is run by this change (decision 5).
- **c0090 is in.** `backends/altium/lower.py` (`from_design`) writes a model with a board and accounts for what it leaves out; it counts a component with a map under the kind `pin-pad-map`.
- **Constraints.** No float, no runtime dependency, clean-room, no new source, and the four conditions of the maintainer's decision (proposal).

## Goals / Non-Goals

**Goals:**
- A pin bonded to several pads is a fact of the model that every reader of the map applies.
- A design whose pins have one pad each gives every KiCad file, every `.fenolite/` layer file, the BOM and the placement file it gave before, byte for byte.
- The four elements of `altium-set:02` are matched.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **The map becomes a relation; the field does not change.** A pin may occur in several pairs of `pin_pad_map`: `(("3", "3"), ("3", "EP"))` bonds pin 3 to the pads 3 and EP. A pad is still named by one pin. Rejected:
   - *A second field* (`pin_pads: tuple[tuple[str, tuple[str, ...]], ...]`, or a field of further pads only). Two fields say one fact, every reader has to merge them, and a reader that forgets the second field is silently wrong, which is the fault of today's bag.
   - *A new type for the field* (pin → list of pads). The canonical JSON of every design with a map changes, so the layer files of 0.2.0 designs are no longer byte-equal, and old documents need a migration.
   - *Pads that share a number in the footprint.* That is KiCad's own way and it already works (the build gives every pad of a number its net), but the footprints of a library and of an imported Altium board have the numbers they have.
   - *Keeping the bag and teaching each consumer to read it.* The bag is Altium's; the DSL and the KiCad build cannot say it.
2. **The pads of a pin, and their order.** The pads of a pin that the map holds are the pads of its pairs, in map order. A pin outside the map has one pad, of its own number. The first pad is the one a schematic symbol shows as the pin's number; the order has no other meaning. The pairs of a pin need not be adjacent.
3. **Two readers in the model, and a guard.** `Component.pads_of(pin)` and `Component.pin_pads()` are the only code that turns pairs into pads. `dict(<…>.pin_pad_map)` is what every broken reader has in common (eight places today), so a test scans `src/fenolite` for it and fails on any occurrence outside `model/circuit.py`. This is what makes "walk every consumer" checkable after this change too.
4. **Canonical form and the byte-equality argument.** Nothing of the serialisation changes: same field, same place, same `ordered` mark, pairs written as held, empty map omitted. Read on 2026-10-06 to be sure: `model/canonical.py` (`to_data`, `_is_default`, `decode`), `dsl/convert.py` (`_component`), `backends/kicad/symembed.py` (`variant_name`, `_pins`, `embed_symbol`), `backends/kicad/schgen.py` (the embed key and `pad_nets`), `lens/build.py` (`_pad_nets`, `lower_for_schematic`, `schematic_netlist_issue`), `backends/kicad/sch_netlist.py` (`own_netlist`). For a map of one pad per pin:
   - `to_model` gives the pairs of the pins in sorted pin order with the pads of a pin as written. With one pad per pin that is `tuple(sorted(pad_map.items()))`, today's value.
   - `variant_name` hashes the pairs sorted by pin with the pads of a pin in map order. With one pad per pin every pin is unique, so that list is the sorted list of pairs, today's input, and the name is the same.
   - `_pins` adds a stacked pin only for a second pad; with one pad it rewrites one number, as today.
   - `pads_of(pin)` returns one pad, so `_pad_nets`, `pad_nets`, `model_netlist` and `_elements` give the values they gave.
   - No evidence constant of the KiCad backend changes (decision 13).
5. **The proof needs pins the goldens do not have, and a comparison with the tag.** The existing goldens stay untouched and are the proof for designs without a map. For designs with a map of one pad per pin there is no golden, so the first task after the entry check, before any product code, pins one SHA-256 per build of: the units design (targets 9 and 10), the 25 generated designs (9 and 10), `examples/blink_2layer` and `examples/board_40parts` (9 and 10). The digest is over the sorted `(path, SHA-256)` list of every built file except `.fenolite/meta.json` and `.fenolite/build.json`, which hold the package version. The pins are computed on the base commit of this change and are never changed by a later task of it. Beside the pins, a scratch script builds every example and every golden design without a `pad_map` with the command line of three trees (the tag `v0.2.0`, the base ba21a109 and the tip of this change, each in a worktree with its own environment, same seed and timestamp) and compares every written file and the outputs of `bom`, `pnp`, `netlist`, `parity` and `check`; the counts are under "Measured" and in the row of `H-G-PINMAP-BYTES`. A difference between the tag and the tip that the base already shows is another change's, not this one's.
6. **The model version stays `"0"`** (decided by the maintainer on 2026-10-06). The schema of the field does not change, and a document of one pad per pin is the same bytes. A new version would change `meta.json` of every design and make 0.2.0 refuse every document written after this change, which breaks condition 1 for no gain. The cost is stated under Risks: Fenolite 0.2.0 reads a document with a pin of several pads without an error and applies one pad. `schemas/fenolite.model.v0/circuit.json` gains a `description` on the field (from field metadata, which `tools/gen_schemas.py` already copies), so the schema says what the pairs mean; the item form is unchanged.
7. **Old documents.** They load as they are: a map of unique pins is a relation. Nothing is migrated. A project imported from Altium before this change holds `pin_pads` pairs in the bag where the new import gives pairs in the map; importing again gives the new form, and a stored model is not rewritten.
8. **Validation.** `model.pin-pad-map` (error): a pair with an empty text, a pair twice, a pad that two pins name (the identity of a pin outside the map counted, for a component that holds pins). The living requirement already asks for it and nothing enforced it. The DSL and the Altium import never build such a map, so no design of 0.2.0 gets the finding; the pinned builds of decision 5 hold `findings.json` and prove it.
9. **The DSL.** `pad_map={"3": "5"}` stays. `pad_map={"3": ("3", "EP")}` gives several pads: the value is a tuple or a list of pad numbers. Rejected: a second keyword (`pads=`, `extra_pads=`), for the reason of decision 1; a string with a separator (`"3,EP"`), because a pad number may hold any character. `Part.pad_map` keeps a string for one pad, so a script that reads the attribute back sees what it wrote.
10. **The KiCad schematic: stacked pins.** A KiCad symbol pin has one number. The variant that `symembed` already embeds for a map gains, directly after the pin, one more pin per further pad: same place, length and name, the pad as number, type `passive`, hidden. Checked on an authored case before any code (section "Measured"): `kicad-cli` 9.0.9 and 10.0.6 put every stacked pin on the label's net and report no ERC violation. Rejected: stacked pins of the pin's own type (two `power_in` or two `output` pins; a hidden `power_in` joins by name on KiCad 9, which is why `symembed` shows hidden power inputs today); the bracket notation of KiCad 10 for several numbers on one pin (KiCad 9 does not read it, and no registered source states it).
11. **An open pin with several pads.** KiCad joins stacked pins without a label into one net and names it after one of them. Measured: `unconnected-(U2-Pad0)` for the pads `2` and `0`, `unconnected-(U2-Pad10)` for `5`, `A1` and `10`: the number that is lowest in code-point order. `pad_nets`, `lower_for_schematic` and `own_netlist` follow that (`netnames.stack_pad`, `netnames.open_name`). **Found while implementing (2026-10-06):** those three cases all carried a no-connect flag. Without a flag the same pins are a net of several pins to KiCad, and both versions name it `Net-(D2-K-Pad17)`, not `unconnected-(…)`; with the first name the parity test of both versions reported a net conflict on each pad. `open_name` therefore takes the flag into account, and the requirement and the hypothesis say so. `own_netlist` refuses several pins of one instance at an unlabelled point today (`shared-point`); the grammar is widened for pins of one name only, which is what a stacked pin is.
12. **Comparisons.** `model_netlist` and level 2 give one element per pad. The pads of an open pin with several pads share one label of the pin's own (`bonded_label`) instead of `NO_NET`: they are joined inside the part, and a board built beside a schematic holds them on one net, so two pads on `NO_NET`, which are a block each, would be a difference of every build. `adapter/parity.pads_of` becomes `Component.pads_of`. `project.link` keeps its inverse map: a pad has one pin, so the inverse is still a function.
13. **The evidence of a design with stacked pins.** `sch_netlist.EVIDENCE` and the evidence of `schgen` are `KICAD-VERIFIED` and list their hypotheses in the envelopes of `netlist`, `parity`, `check` and `build`. The constants are not changed: a longer list would change those envelopes for every design, and the comparison with the release found them byte-equal. But a design that does hold a pin with several pads rests on `H-K-SCH-STACKED`, and on `H-K-SCH-STACKED-OPEN` when a stack carries no label, so its evidence must name them (added on 2026-10-07; the first implementation named them nowhere, and such a design answered with the evidence of a one-pad design). `sch_netlist.stack_evidence(sheets)` finds the stacks of the sheets and returns the rows they add, nothing for sheets without a stack; `sch_netlist.evidence_of` combines them with `EVIDENCE` and returns `EVIDENCE` itself when there is none. The build, `netlist --source fenolite`, `parity` with its own netlist and the parity side of `check` use it.
14. **The Altium import.** A record of several pads gives one pair per pad in record order. A pad that another pin stands for, and a record without a pad, stay what the model cannot say: the record is kept in `pin_pads` and counted by `altium.import.pin-map`, whose meaning narrows to those two cases.
15. **The Altium write.** No active change writes the map: c0084 to c0090 do not name it (`grep` over their texts, 2026-10-06), and `docs/altium.md` lists `component.pin_pad_map` as "the writer does not write it". This change writes it, because a model fact that one backend drops is the fault this change exists to remove:
    - the PCB document: a pad takes the net of the pin that names it (this also fixes the defect of "Context");
    - the schematic document and library: one record 47 per pin of a component with a map, under record 46;
    - RT-A2 compares `pin_pad_map` as the pads of each pin; `pin_pads` (what the model cannot hold) is listed as not written, with a count, which is what c0090's RT-A3 reports as left out.
    - the write of a model (c0090, `lower.from_design`): the schematic it generates carries the map like a built one, so the kind `pin-pad-map` counts only the components whose bag holds a `pin_pads` record, which is what stays unwritten.
    A component without a map writes the bytes it wrote before: the Altium goldens of `tests/unit/lens/test_altium_*golden*.py` are untouched.
16. **Four engineering choices, each in one place so it can be switched.** They were open questions of the proposal; the maintainer left them to the change.
    - *The pad a symbol shows is the first of the map*: `Component.pads_of` returns the pads in map order and `symembed._pins` numbers the pin with `pads[0]`.
    - *A stacked pin is `passive` and hidden*: the constants `STACKED_TYPE` and `STACKED_HIDDEN` of `symembed`.
    - *Record 47 only for a pin whose pads differ from the pad of its own designator* (changed on 2026-10-07 by the coordinator's decision, from "a record for every pin"): `altsym.MAP_RECORDS_FOR_EVERY_PIN`, false, read by `altsym.map_pins`, which both schematic writers call. The partial form is what Altium saves (`H-A-SCHX-PINMAP-FORM`, counted on four public sets); the full form is one edit away, and the import reads both to the same map.
    - *A pad named by two pins is an error*: `SHARED_PAD_IS_AN_ERROR` of `model/circuit.py`, read by `pin_pad_map_problems`, which `Design.validate()` reports as `model.pin-pad-map`.
17. **Cut order.** First the records 47 of the Altium write (the pad nets of the PCB document stay, and `altium.not-lowered` names the maps that were not written). Then the open stacked pin in `own_netlist` (such a design is then refused by the netlist guard with `shared-point`, as today's grammar says). Never the model, the DSL, the pinned builds, the set-02 measure and the oracle run of the stacked pins on a net.

## Consumers, one by one

| consumer | file and function | this change |
|---|---|---|
| model | `model/circuit.py` `Component` | `pads_of`, `pin_pads`; field metadata `description` |
| model validation | `model/design.py` `Design.validate` | new `model.pin-pad-map` |
| canonical JSON | `model/canonical.py` | unchanged, because the field's type and mark do not change |
| schemas | `tools/gen_schemas.py`, `schemas/fenolite.model.v0/circuit.json` | regenerated: one `description` |
| DSL | `dsl/part.py` `Part.__init__`; `dsl/convert.py` `_component` | a value may be a sequence; pairs per pad |
| KiCad build, pads | `lens/build.py` `_pad_nets` | every pad of a pin takes its net |
| KiCad build, guard | `lens/build.py` `schematic_netlist_issue` | one expected element per pad |
| KiCad build, lowering | `lens/build.py` `lower_for_schematic` | the pads of an open pin share one net |
| KiCad schematic | `backends/kicad/schgen.py` `generate_schematic`, `_content` | key of the variant; `pad_nets` per pad |
| KiCad embedded symbol | `backends/kicad/symembed.py` `variant_name`, `_pins` | stacked pins; name from pairs sorted by pin |
| KiCad own netlist | `backends/kicad/sch_netlist.py` `own_netlist`, `_sheet_issues` | stacked pins without a label are one net |
| parity | `checks/parity.py` `compare`, `checks/parity_stage.py` | unchanged, because a `SchematicSide` holds pad numbers: the KiCad side is read from the sheet, which now holds the stacked pins, and the Altium side from `adapter/parity.py` |
| assignment comparison | `checks/assignment_compare.py` `model_netlist` | one element per pad |
| equivalence level 2 | `checks/equivalence/levels.py` `_elements` | one element and one part per pad |
| equivalence level 3 | `checks/equivalence/levels.py` `level_footprints` | unchanged, because it compares the footprints and pads of the two boards and reads no map |
| Altium import, parts | `backends/altium/adapter/parts.py` `_pin_pads` | unchanged, because it already reads every pad of a record |
| Altium import, circuit | `backends/altium/adapter/circuit.py` `pin_pad_map`, `build_circuit` | one pair per pad; the bag and the count hold only what is left |
| Altium import, project | `backends/altium/adapter/project.py` `link` | unchanged code, because a pad has one pin; one test with a pin of two pads is added |
| Altium import, ids | `backends/altium/adapter/ids.py` | unchanged: the bag key `pin_pads` stays |
| Altium import, codes | `backends/altium/adapter/codes.py`, `cli/data/explain.toml` | the code stays `info`; its text narrows |
| Altium parity side | `backends/altium/adapter/parity.py` `pads_of`, `side_of` | `pads_of` is replaced by `Component.pads_of`; the result is the same |
| Altium build, board | `lens/altium.py` `pcb_document` (the `pad_nets` of `PlacedComponent`), `backends/altium/pcbdoc.py` | nets by pad through the map; `altium.pin-pad-map-invalid` |
| Altium build, schematic | `backends/altium/schdoc.py`, `schlib.py` `footprint_chain` | records 47 for a component with a map |
| Altium round trips | `backends/altium/roundtrip.py` `RT_A2_SCOPE` | `pin_pad_map` compared; `pin_pads` counted as not written |
| Altium write of a model | `backends/altium/lower.py` `from_design` | the kind `pin-pad-map` counts the components with a `pin_pads` record; the map itself is written |
| BOM | `exports/bom.py` | unchanged, because a line is made of components and their properties; a test asserts equal output with and without further pads |
| placement file | `exports/placement.py` | unchanged, because a row is a footprint; same test |
| KiCad readers | `backends/kicad/pcb.py`, `sch.py` | unchanged, because they derive no map: a board read from KiCad has pads with numbers, and a pin of several pads is there as pads sharing a number or as stacked pins of the sheet |
| model difference | `checks/diff.py` | unchanged, because it compares the field as a value |

## Files and public API

- `src/fenolite/model/circuit.py`: `Component.pads_of(pin: str) -> tuple[str, ...]`, `Component.pin_pads() -> dict[str, tuple[str, ...]]`; `model/design.py`: `model.pin-pad-map`.
- `src/fenolite/dsl/part.py`: `Part(..., pad_map: Mapping[str, str | Sequence[str]] | None)`; `Part.pad_map: Mapping[str, str | tuple[str, ...]]`; `dsl/convert.py`.
- `src/fenolite/lens/build.py`; `backends/kicad/schgen.py`, `symembed.py`, `sch_netlist.py`.
- `src/fenolite/checks/assignment_compare.py`, `checks/equivalence/levels.py`.
- `src/fenolite/backends/altium/adapter/circuit.py`, `parity.py`; `backends/altium/schdoc.py`, `schlib.py`, `roundtrip.py`; `lens/altium.py` (`ALTIUM_ISSUE_CODES` gains `altium.pin-pad-map-invalid`).
- `schemas/fenolite.model.v0/circuit.json` (generated); `src/fenolite/cli/data/explain.toml`.
- Tests: new `tests/unit/model/test_pin_pad_map.py`, `tests/unit/lens/test_build_bytes_pinned.py`, `tests/unit/backends/altium/test_pin_map_records.py`, `tests/unit/lens/test_altium_pin_map.py`; extended `tests/unit/dsl/test_footprint.py`, `tests/unit/lens/test_build_pins.py`, `tests/unit/lens/test_build_netlist_guard.py`, `tests/unit/backends/kicad/test_symembed.py`, `test_schgen.py`, `test_sch_netlist.py`, `tests/unit/checks/test_assignment_compare.py`, `tests/unit/checks/equivalence/test_levels.py`, `tests/unit/backends/altium/adapter/test_repeat.py`, `test_parity_side.py`, `test_project.py`, `tests/unit/lens/test_altium_issues.py`, `tests/unit/exports/test_bom.py`, `test_placement.py`, `tests/corpus/test_altium_channels.py`, `tests/kicad/schematic/test_generated_oracle.py`, `tests/kicad/schematic/test_own_netlist.py`.
- Pages: `docs/design-model.md`, `docs/dsl.md`, `docs/schematic.md`, `docs/formats/kicad/schematic.md`, `docs/altium.md`, `docs/formats/altium/connectivity.md`, `docs/formats/altium/import.md`, `docs/formats/altium/schematic-records.md`, `docs/cli-contract.md`, `docs/evidence/altium-roundtrip.md`, `docs/hypotheses.md`.

## Reused from the frozen branch `codex/board-authoring-gaps`, file by file

Both paths named in the brief exist on that ref. Ideas are reused; no file and no line is carried, and no guard allowance, waiver or test relaxation of that branch comes with them.

| file | reused | not reused |
|---|---|---|
| `docs/board-authoring-gaps.md`, "Pin-to-pad map write" | the need as it states it: several physical pads for one logical pin, written without changing the net partition; its warning not to carry the branch's catalog import allowance | its list of changed files as a plan; its tests, which this pass did not read |
| `src/fenolite/lens/altium_maps.py`, `relation` | the reading of `pin_pad_map` as a relation in which a pin may repeat, with identity for a pin outside the map | its place (`lens`), and its sorting of the pads of a pin: here the readers live in the model and keep map order |
| the same file, `physical_nets` | pad → net through the relation, with a refusal when two nets meet on one pad | the `ValueError`: here the model's `model.pin-pad-map` and the build's issue codes say it |
| the same file, `validate_maps` | the checks of a missing pin and a missing pad before anything is written, and the code name `altium.pin-pad-map-invalid` | `altium.pin-pad-map-unresolved`: a footprint that is not resolved already gives `altium.footprint-unresolved` |
| the same file, `compare_maps` | the thought that a read-back compares the relation, not the nets alone | the function: RT-A2's scope compares the field |
| the same file, `schematic_side` | nothing | `adapter/parity.side_of` of c0088 is the side of this branch |
| `backends/altium/schdoc.py` and `schlib.py` of that ref (read for records 46 and 47 only) | that one record 47 per pin carries `DESINTF`, `DESIMPCOUNT` and the pads | the numbering of `DESIMP` from 0 as a fact: it is a hypothesis here (`H-A-SCHX-PINMAP`), settled on the corpus; and the sorting of the pads |

## After the review of c0135 (2026-10-07)

The fix of the 0.2.x line (change c0135) was reviewed after this change was written, and four of its findings hold here too. They are carried with the same requirement names and wording, so that "Pin maps in an Altium build" and "Pin map records of a footprint model", which both changes ADD, can become MODIFIED here when the release line is merged back.

- **Copper by pad.** `altium_copper.match_source` read the wanted net of a pad by pin number. `altium_copper.pad_net_names(design)` is now the one place that turns the nets of the circuit into component → pad → net name, through `Component.pads_of`; `match_source` and `lens.altium.pcb_document` both read it. Every pad of a pin carries the pin's net, so the KiCad board of a script with several pads per pin is accepted as copper source, and the board of the script without the map is refused for each further pad.
- **The library's own footprint.** A library symbol holds the map only when every user of the symbol links the footprint that the library's footprint model names (record 45) and has the same pads for every pin. The condition before, "one footprint among the users", let a library hold a map onto a footprint its own model does not name.
- **Pad names are written text.** A pad name of a map goes through `text_problem`: `altium.text-unwritable`, not an exception from the record writer.
- **Parts of an Altium link.** Their symbol is not known, and their pins are the designators the nets use: a mapped pin that no net uses is not "a pin the symbol lacks".
- **One statement differs from c0135 on purpose.** There `fenolite check` reports `netlist.assignment-differs` on a correct project with a renaming map, because 0.2.x compares the schematic by pin and the board by pad. Here the import reads the records into `pin_pad_map` and the comparison names every pad: `check` exits 0 (`test_check_knows_the_map`).
- **A pad of two pins: both codes** (decision of the coordinator, 2026-10-07). c0135 refuses it in the build with `altium.pin-pad-map-invalid`, and a user of 0.2.1 knows that code. Here the model says `model.pin-pad-map` of the same pad, which is what model validation and `check` report of a model that holds it. The build keeps its code: `build_altium` calls `pin_map_issues` as soon as the validation holds a `model.pin-pad-map`, before that error ends the build, and reports both; the KiCad build reports `build.pin-pad-map-invalid` and the model's finding likewise. `pin_map_issues` finds the pad by `Component.pads_of`, so a pad that one pin holds by its own number and another by a map of several pads is found too.
- **Author report.** On 2026-10-07 the maintainer opened in Altium Designer 26 a project of one pad per pin built by c0135: it compiled clean; with the map records the PCB update proposed no change on the mapped pins, and without them it proposed to remove and add them. `H-A-SCHX-PINMAP` stays `INFERRED`: an author report leaves no artefact, and a record of several pads was not opened.
- **Found on the way, not fixed here.** (1) `schlayout.pin_point` mirrors and then rotates; two demo sheets show KiCad rotating first (instances mirrored and turned by 90 or 270 degrees). Reported as change c0137; the corpus test of stacks leaves such instances out. (2) `--copper-from` refuses a KiCad board whose bottom-side footprint has pads off its x axis, with or without a map: the pad positions differ in the sign of y from the resolved footprint. The blink's LED has both pads on the axis, so no test met it.

### Stacks on third-party sheets (item 3)

`tests/kicad/schematic/test_stacked_corpus.py` asks the stack rule of the demo projects of the corpus. Measured on 10.0.6: one project holds stacks of same-named pins at a point that nothing else touches, 10 of them, each one net of KiCad's export with the name `netnames.open_name` gives. That is all the test proves: the whole own netlist of a third-party sheet is not compared, because no demo sheet is inside the grammar of `sch_netlist.own_netlist`. The 9.0.9 run waits (task 10.5).

## On the base that holds 0.2.1 (rebase of 2026-10-07)

The branch was one commit on a343cf87 and is now one commit on `dev` 9322ff2f, which holds the merge of the release 0.2.1 (c0133, c0135), c0121 (component bodies), c0124 to c0132 and c0136 (milestone names).

- **Two requirements became living.** "Pin maps in an Altium build" and "Pin map records of a footprint model" were ADDED here and are now MODIFIED, generated from the living text of c0135 with asserted replacements: several pads per pin (`DESIMPCOUNT` the number of pads, `Component.pads_of`), the switch `MAP_RECORDS_FOR_EVERY_PIN`, both codes for a pad of two pins, and the statement about `check`. The living bullet "What `check` says" and its scenario described 0.2.x (exit 5, a test `-k check_still` that no longer exists); the MODIFIED text says what this line does (exit 0) and names the tests that exist.
- **Code.** Where both sides held the same thing in two shapes, this change's shape stays (`altsym.map_pins` and `map_records` for several pads, `pad_net_names` through `pads_of`), and it contains what the base has: the `bodies` argument of `resolve_footprints` and of the round trip (c0121), `result.pcb`, the three refusals of c0135. The line of the merge that took the map off the components of a written model (`lower.schematic_design`) is gone: this change writes the map and accounts for what it cannot write (`pin-pad-map`, `pin-pads`).
- **Tests.** The tests of c0135 stay as the tests of a map of one pad per pin (`test_altium_pad_map.py`, `test_altium_pad_map_copper.py`, `tests/corpus/test_altium_map_records.py`); this change's own copies of them are removed, and its files keep what is about several pads, the two record forms and RT-A2. One test of c0135 is adapted: `test_a_pad_that_two_pins_stand_for_is_refused` expects each build's own code once and `model.pin-pad-map` beside it.
- **Pinned builds.** Measured on 9322ff2f without this change and with it: the 70 KiCad pins and the 10 Altium pins are equal. The two Altium pins of the units design, which this change moved on its old base, are already the base's values: 0.2.1 writes the same two records for that map.
- **Names.** The Altium write side is v0.3 and is released as `0.3.0` (c0136). The dated notes of `tasks.md` and the decision section of the proposal keep the name of their day (v0.4).
- **Measured on the old base and not again:** the counts of `altium-set:02` (698, 7, 27, 2; 17 net conflicts) and the oracle runs. They are owed on this base (task 13.2).

## Measured on 2026-10-07, after the implementation

- **Against the release.** Three trees (tag `v0.2.0`, base ba21a109, tip), 36 builds each from 9 scripts without a `pad_map`, by the command line with one seed and timestamp. KiCad side, 306 files per tree (written files and the outputs of `build`, `bom`, `pnp`, `netlist`, `parity`, `check`): 0 differences tag against tip, 0 base against tip. Altium side: no written file differs between base and tip; 18 `build` envelopes list two more hypothesis rows; the 98 paths that differ from the tag are the 98 that the base differs in.
- **Pins.** 70 KiCad pins and 8 of 10 Altium pins hold; the two that moved are the Altium builds of the units design, whose `pad_map` an Altium build ignored before.
- **`altium-set:02`.** 694, 7, 31, 2 → 698, 7, 27, 2; pairs 6 → 11; records in a bag 2 → 0; parity net conflicts 21 → 17. Sets 03 to 05 unchanged; set 01 not run (heavy).
- **KiCad.** The stacked design passes on 10.0.6 and 9.0.9: probes `netlist-own-stacked` and `sch-stacked-erc` `equal`, `sch-stacked-parity` `absent`; no other probe outcome moved.
- **The defect.** `test_pad_nets_follow_a_renaming_map` fails on ba21a109 and on `v0.2.0` and passes at the tip; `v0.1.0` holds the same two lines.

## Measured (2026-10-06, before any product code)

**Stacked pins in KiCad.** The units design of `tests/_schbuild.py` was built for each target and its embedded symbols were edited by a scratch script: further `passive`, hidden pins at the place of a pin on a labelled net, of a marked pin and of two more marked pins, with pad numbers chosen to sort before and after the pin's. `kicad-cli sch export netlist` and `kicad-cli sch erc` of 10.0.6 (local) and 9.0.9 (the pinned image):

| case | 9.0.9 | 10.0.6 |
|---|---|---|
| pin on a labelled net with two further pads | the three pads are nodes of that net | the same |
| output pin with one further pad | both pads on the net | the same |
| marked pin `1` with the further pad `41` | one net `unconnected-(U2-Pad1)` with both nodes | the same |
| marked pin `2` with the further pad `0` | one net `unconnected-(U2-Pad0)` | the same |
| marked pin `5` with the further pads `A1` and `10` | one net `unconnected-(U2-Pad10)` | the same |
| marked pin `PA1` numbered `2` with the further pads `20` and `1X` (the blink) | not run | one net `unconnected-(U1-PA1-Pad1X)` |
| marked pin `PA2` numbered `3` with the further pad `03` (the blink) | not run | one net `unconnected-(U1-PA2-Pad03)` |
| ERC violations caused by the further pins | none | none |

- On 9.0.9 ERC gave four `lib_symbol_mismatch` warnings, because the script edited the embedded copy and not the project library; a build writes both from one node. 10.0.6 gave no violation. With further pins of the pin's own type instead of `passive`, 10.0.6 gave no violation either; that variant was not run on 9.0.9.
- A further pad whose number another pin of the symbol holds gave the ERC error `duplicate_pins` on 10.0.6 (a mistake of the first run of the script on the blink, kept as a fact): KiCad too refuses a pad of two pins.
- Not measured: an open pin without a mark, the named pins on 9.0.9, the parity test of the board, and a re-save. The oracle tasks cover them.

**`altium-set:02`.** A scratch script added, to the schematic side of the stage, one element per pad of the two records kept in the bag, on the net of their pin: 4 elements are added; common 694 → 698, only schematic 7 → 7, only PCB 31 → 27, differences 2 → 2. Both records list several pads; none lists a pad that another pin holds and none is empty. Sets 03, 04 and 05 hold no such record and do not move; set 01 was not run (heavy).

## Sources registered by this change

- None. The map records are rows of `docs/formats/altium/schematic-records.md` (records 46 and 47; S-0130) and of `docs/formats/altium/connectivity.md`, "Component link" (S-0130 and the sets of S-0187 and S-0188). The numbering of `DESIMP` is read from the files of those two sets by a census. The behaviour of stacked pins is read from `kicad-cli` (S-0020) on authored sheets.

Each new source gets the next free `S-` number in `docs/evidence/sources.md` when its task runs (numbers are not reserved here, because changes that run in parallel would collide), with its licence and what was read. Sources under a copyleft or an all-rights-reserved licence are read for facts only; nothing is transcribed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-G-PINMAP-BYTES | A design whose pins have one pad each gives, after this change, the bytes it gave before it: every file of a KiCad build for 9 and 10, the layer files, the BOM and the placement file | `tests/unit/lens/test_build_bytes_pinned.py`; the goldens of `test_parity_cmd.py`, `test_sync_cmd.py`, `test_bom_cmd.py`, `test_pnp_cmd.py`, `test_assembly_guide.py` and `tests/kicad/acceptance/test_finished.py`, none edited | every pin of task 2.1 holds and `git diff --stat <base> -- tests/data` lists no file of those goldens |
| H-K-SCH-STACKED | Pins of one symbol instance at one point are joined: with a label there, each is a node of the label's net, and further `passive` hidden pins cause no ERC violation and no parity finding | `tests/kicad/schematic/test_generated_oracle.py -k stacked` and `test_own_netlist.py -k stacked` on 9.0.9 and 10.0.6 | the export equals `own_netlist`; ERC and the parity test report what the same design without further pads reports |
| H-K-SCH-STACKED-OPEN | Stacked pins of one name without a label are one net, named `unconnected-(…-Pad<n>)` with the number that is lowest in code-point order, marked or not, with or without a pin name | the same tests, the cases with an open pin | the net names of the export equal those of `own_netlist` and of the board on both majors |
| H-A-IMP-PINMAP-MULTI | A map record that lists several pads bonds the pin to each of them: the board's pads of those names are on the pin's net | `tests/corpus/test_altium_channels.py -k pin_map` on `altium-set:02` | 698 common, 7 only schematic, 27 only PCB, 2 differences; no record of several pads left in a bag |
| H-A-SCHX-PINMAP-FORM | Altium saves a map record only for a pin whose pads are not the pad of its own designator alone, with its pads numbered from 0 without a gap (added on 2026-10-07) | `tests/corpus/test_altium_channels.py::test_map_records_are_saved_for_the_mapped_pins_only` | over the sets 02 to 05: no record names the pin's own pad alone, and models with fewer records than pins exist |
| H-A-SCHX-PINMAP | A footprint model's map is written as one record 47 per pin with other pads than its own under record 46, `DESIMP` numbered from 0, and is read back to the same pads of each pin | `tests/unit/backends/altium/test_pin_map_records.py`, `tests/unit/lens/test_altium_pin_map.py`; the census of `DESIMP` keys over the sets of S-0187 and S-0188 | the read-back relation equals the model's in both schematic forms and in the library; every record 47 of the census starts at `DESIMP0` |

All start `INFERRED`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06). The two KiCad rows become `KICAD-VERIFIED (9.0.9, 10.0.6)` when their tests pass on both; `H-A-SCHX-PINMAP` stays `INFERRED` until an author report of the kit (c0091) says that Altium applies a written map.

## Size (design-days)

| group | dd |
|---|---|
| entry, registers, pinned builds | 0.75 |
| model, schema, validation | 0.5 |
| DSL and the KiCad build's pads | 0.5 |
| KiCad schematic, own netlist, guard | 1.0 |
| comparisons (assignment, level 2) | 0.25 |
| Altium import and the set-02 measure | 0.5 |
| Altium write and round trip | 1.0 |
| oracle runs on 9.0.9 and 10.0.6 | 0.5 |
| pages and closing | 0.5 |

Total: 5.5. This is a size, not a calendar estimate.

## Spec deltas and archive order

| capability | requirement | delta | written from |
|---|---|---|---|
| `design-model` | "Persist per-component pin-to-pad maps" | MODIFIED | the living text; no active change holds a delta for it |
| `design-dsl` | "Per-component pin-to-pad mapping" | MODIFIED | the living text; no active change holds a delta for it |
| `kicad-schematic` | "Embedded symbols of a generated sheet" | MODIFIED | the living text; no active change holds a delta for it |
| `kicad-schematic` | "Own netlist of a generated sheet", "Netlist grammar check" | MODIFIED | the text of the active change c0070, which modified what c0063 added; neither is in the living spec of this branch, and both are in the living spec of `origin/dev`, where c0063 and c0070 are archived |
| `kicad-schematic` | "Pins with several pads on a generated sheet" | ADDED | |
| `kicad-oracle` | "Stacked pins pass ERC, the netlist export and parity" | ADDED | |
| `verification-loop` | "Assignment comparison names every pad of a pin" | ADDED | |
| `design-equivalence` | "Level 2 names every pad of a pin" | ADDED | |
| `altium-import` | "Pin-to-pad map of a footprint model" | MODIFIED | the text of the active change c0083, which adds it |
| `altium-schematic-writer` | "Pin map records of a footprint model" | ADDED | |
| `altium-build` | "Pin maps in an Altium build" | ADDED | |
| `altium-verification` | "Pin maps in the Altium round trips" | ADDED | |

- Three living requirements name one pad per pin in a sentence and are **not** modified, because an added requirement of the same capability says the several-pad case: "Assignment compare stage" of `verification-loop` (its bullet "Sources"; the active change c0063 holds its text), "Generated sheet content" of `kicad-schematic` (its bullet "Pins and pads"; the active change c0070 holds its text), and "Level 2 compares the netlist as REF-PIN sets" of `design-equivalence` (living; it delegates to `model_netlist`). For a pin with one pad they stay true word for word.
- "Import issue codes" of `altium-import` (modified by c0083 and c0122) is not modified: the code `altium.import.pin-map` keeps its name and severity. "Altium build issue codes" is not modified: `altium.pin-pad-map-invalid` joins the closed table through the added requirement, as the codes of later capabilities did.
- Archive order: after c0083 (whose requirement this change modifies) and after c0063 and c0070 (already archived on `origin/dev`). Before c0090, or with a task there: c0090's lowering of a model must pass the map to the writers of this change. c0086, c0088 and c0122 hold no delta for a requirement modified here (checked 2026-10-06 by `grep` over `openspec/changes/*/specs`).

## Risks / Trade-offs

- [Fenolite 0.2.0 reads a document with a pin of several pads and applies one pad, without an error] → stated in the changelog and in `docs/design-model.md`; the alternative, a new model version, breaks condition 1 (decision 6).
- [A reader of the map is added later with `dict(...)`] → the guard test of decision 3.
- [The goldens hold no map, so they prove nothing about designs with one] → the pinned builds of decision 5, made before any code.
- [The pins break at an unrelated change of a writer] → that is what a pin is for; the test says in its message that a pin is changed only by the change that changes the writer, never by this one.
- [KiCad names the net of stacked open pins by another rule than the three cases measured show] → `H-K-SCH-STACKED-OPEN` is settled by cases with names, without marks and with numbers of mixed length on both majors; if it fails, the cut of decision 17 applies.
- [A hidden stacked pin is not seen on the sheet] → the first pad is shown, the others are in the symbol's pin table and in `docs/schematic.md`; a visible stack prints its numbers on top of each other.
- [Altium does not accept a written record 47] → the envelope of the Altium build stays `INFERRED`; a component without a map writes the bytes it wrote before, so no accepted sample changes.
- [The proof against the goldens of 0.2.0 itself cannot be run on this branch] → the branch does not hold the release commit. The pins and goldens of the branch are proved here; the coordinator runs the named tests again on the branch rebased onto `dev`.

## Migration Plan

- Callers: `Part(pad_map=…)` accepts what it accepted. `Component.pin_pad_map` may now hold a pin twice: code outside Fenolite that calls `dict()` on it takes the last pad; `pads_of` is the reader.
- A project imported from Altium gets pairs where it had `pin_pads` bag entries for records of several pads; import again to get them.
- Rollback: the readers take the first pad of a pin again; documents stay readable both ways.

## For c0126

c0126 (footprint graphics in the model) follows this change on the same model. What it must respect:

- **Canonical form.** A new field is added after the existing ones with a default, so `canonical` leaves it out and a design without it keeps its bytes; `SCHEMA_VERSION` stays `"0"` unless the maintainer decides otherwise. `Component.pin_pad_map` keeps its type and its `ordered` mark.
- **The pinned builds.** `tests/unit/lens/test_build_bytes_pinned.py` holds one pin per build of 35 designs for KiCad 9 and 10 and of five designs for the Altium target. A pin moves only in the change that changes the writer, with the reason beside it; a change of the model alone moves none. `uv run python tests/_pinned.py` prints the tables.
- **The readers of the map.** `tests/unit/model/test_pin_pad_map.py -k readers` refuses `dict(….pin_pad_map)` outside `model/circuit.py`. New code reads the map with `Component.pads_of` and `Component.pin_pads`.
- **Old readers.** Fenolite 0.2.0 reads a document with a pin of several pads without an error and applies one pad per pin; a document with footprint graphics should fail or degrade as visibly as the maintainer wants, which is a decision of c0126.

## Open Questions

- **Does the model version stay `"0"`?** Decided by the maintainer on 2026-10-06: yes (decision 6).
- **Which pad does the KiCad symbol show?** Default: the first of the map, which the script chooses. Alternative: the lowest in code-point order, the one KiCad names an open net after.
- **Type and visibility of a stacked pin.** Default: `passive` and hidden. Alternative: the pin's own type, shown.
- **Records 47 for every pin, or only for the mapped ones?** Decided on 2026-10-07: only for a pin whose pads differ from the pad of its own designator, the form the public files hold. What stays open is whether Altium applies a record that Fenolite writes (author report).
- **Is a pad named by two pins an error of the model?** Default: yes (`model.pin-pad-map`); the Altium records of that kind stay in the bag. It becomes a question if a corpus project needs two pins on one pad.
- **Are new pinned digests acceptable as proof beside the existing goldens?** Default: yes, made on the base commit before any code and never regenerated by this change; without them the designs with a map have no byte proof at all.
- **Where is the 0.2.0 proof run?** Default: here on the branch's own goldens, and by the coordinator on the rebased branch.
