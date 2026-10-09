## Context

**Scope.** Milestone v0.5a, the first item, direction Altium to KiCad. c0159 gives the command, the report and the verification; this change registers the direction and builds what KiCad's writers need from an imported model. The Altium side is read only, so no Altium Designer is needed: the sources are the public documents of the corpus and Fenolite's own Altium samples.

**What exists** (checked on `origin/dev` at `f802b60`, 2026-10-09):

| where | what |
|---|---|
| `src/fenolite/backends/altium/backend.py`, `adapter/` | an Altium project, PCB document or schematic read into a `Design`: circuit, board, rules mapped onto neutral rules where exact (c0042, c0084, c0125, c0130), stack-up, footprint graphics and texts (c0126) |
| `adapter/layers.py`; `docs/cli-contract.md`, "Altium import" | layer names of the import: `F.Cu`, `In<k>.Cu`, `B.Cu`, `F.SilkS`, `F.Mask`, `Edge.Cuts`, `Mech.<n>`, `Altium.KeepOut`, `Altium.DrillDrawing`, `Altium.<id>` for a layer outside the stack (`altium.import.layer-outside-stack`) |
| `src/fenolite/backends/kicad/pcb.py:619` `_emit_layers` | each board layer's row comes from its `kicad` bag (`number`, `type`, `user_name`); a layer without the bag raises `KeyError` |
| `src/fenolite/backends/kicad/layers.py:55`, `:78`, `:152` | `CREATED_ROWS` (the 2-copper table of 10.0.6), `CREATED_COPPER_COUNTS` = (2, 4, 6, 8), `inner_rows` (`In<k>.Cu` numbered `2k + 2`) |
| `src/fenolite/backends/kicad/_fpmap.py:465`–`475` | a slot is written along the pad's X or Y; another turn raises `ValueError` |
| `src/fenolite/backends/kicad/triad.py:29`, `schgen.py:312`, `mod.py`, `sym.py`, `libs.py` | the board, project and rules files; the generated schematic of a circuit from `SchematicPart`s (a symbol per component); footprint and symbol library writers and library tables |
| `src/fenolite/backends/altium/adapter/library.py:223` | a `.SchLib` read into `SymbolDef`s |
| `src/fenolite/backends/kicad/altium_import.py`; `cmd_equivalent.py --against kicad-import` | `kicad-cli pcb import --format altium` (10.0 only) and the profile `kicad-import` of `src/fenolite/backends/kicad/data/altium_import_exclusions.toml` |

**Measured on 2026-10-09** (no tool; probe scripts kept with the change's working notes, not committed; task 1.1 turns them into a corpus test). The eight public PCB documents of the corpus (`altium-third-party-pcbdoc-01` to `-08`), read with the Altium backend:

1. `write_board(design, target=10)` raises `KeyError: 'number'` at `pcb.py:619` for all eight.
2. Giving the layers whose names `created_layers(copper)` holds their KiCad bag (all eight have two copper layers), and leaving the others as they are:

   | document | written | layer names written that no row declares (items) | read back against the import |
   |---|---|---|---|
   | `-01` | yes | `Altium.KeepOut` (20) | level 5, one `ref-ambiguous` |
   | `-02` | yes | `Mech.1` (16), `Altium.DrillDrawing` (1) | level 5, equal |
   | `-03` | yes | `Altium.KeepOut` (1) | level 5, one `ref-ambiguous` |
   | `-04` | yes | `Mech.2` (15), `Mech.1` (12) | level 5, one `ref-ambiguous` |
   | `-05` | yes | `Mech.1` (4) | level 5, one `ref-ambiguous` |
   | `-06` | yes | `Mech.1` (16), `Altium.KeepOut` (4), `Altium.74` (3), `Mech.2` (1) | level 5, equal |
   | `-07` | no: `ValueError: pad SH4: KiCad writer cannot represent this slot rotation` | — | — |
   | `-08` | no: the same | — | — |

   The writer issued no warning for the undeclared names. Whether KiCad loads such a file, drops those items or refuses was not run (no `kicad-cli` in that session; task 1.2 runs it). The `ref-ambiguous` is the pads without a component, which the triangle meets too (`docs/equivalence.md`, "The triangle").

## Goals / Non-Goals

**Goals**
- `fenolite convert --to kicad` writes a KiCad project of any public Altium project or PCB document of the corpus that KiCad's model can hold, for target 9 or 10, and reports the rest per kind and reason.
- The written board is the import at level 5, and agrees with KiCad's own importer at level 5.
- No item is written on a layer that the board does not declare, for any caller.

**Non-Goals**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **The lowering lives in `convert/to_kicad.py`,** on KiCad's writers: it gives each layer its KiCad bag, renames footprints and nets to KiCad's forms, and hands the design to `write_triad`. Rejected: a KiCad backend that knows Altium names: `backends.kicad` may not import `backends.altium` (`package-layering`), and the names are the import's, which `convert` already knows. Rejected: changing the Altium import to produce KiCad bags: the model stays neutral.
2. **Layer table.** `layers.board_rows(copper)` generalises `created_layers` to every even count from 2 to 32 with the rows of `inner_rows`; `CREATED_COPPER_COUNTS` keeps (2, 4, 6, 8) for scripts. An odd count of signal layers (Altium allows it) gets one more inner layer, empty, counted `changed` under `stackup`. The non-copper map is closed: `F.SilkS` … `Edge.Cuts` by name; `Mech.<n>` to KiCad's user layers in order of `n`, as many as the target's layer table holds (a fact row with its source and the numbers, task 1.2: KiCad 9 and 10 user layers and their numbers in the board format), and beyond that a loss; `Altium.KeepOut` see 3; `Altium.DrillDrawing` and `Altium.<id>` are lost with their reasons. The written board names each user layer with the Altium layer's name as its user name.
3. **Keep-out drawings.** A closed outline on `Altium.KeepOut` (a polygon, or tracks and arcs that join into a ring) becomes a KiCad rule area on every copper layer that keeps out tracks, vias and copper pour (`Keepout` of the model, c0103); an open line stays a loss with the reason "a keep-out line that encloses no area". The meaning of the layer comes from a public Altium page registered first (S-0742; task 1.3), stated as a fact row in `docs/formats/altium/import.md`. Rejected: copying the lines to a user layer: a router would not see them, and the report would hide that.
4. **Slots.** A slot turned against its pad is written by turning the pad to the slot's angle when the pad is a circle, or an oval whose axis lies along the slot (same copper); any other pad with such a slot is a lost `pad` with the reason. Measured: the two documents that fail have such slots; task 1.1 counts their pad shapes.
5. **No undeclared layer, for every caller.** `write_board` raises `LossyWriteError` with one `kicad.board.layer-undeclared` error per layer name (count of items in the message) when a modelled item names a layer that no row of the board declares; the convert direction never reaches it, because the map of 2 removes or maps every layer first. The census of task 1.4 runs it over every committed board, script, example and demo before the change lands, so the refusal can only meet foreign models. Rejected: a warning: KiCad's behaviour with such a file is unknown until task 1.2, and a conversion must not depend on it.
6. **Names.** Footprints are named `<project>:<name>` with the library `<project>.pretty` derived from the instances, one `.kicad_mod` per footprint name from its first instance in reference order (as c0160's derived `.PcbLib`; edited instances `changed`). Net names are written in KiCad's stored form (`netnames`); a name that the stored form cannot hold is renamed and counted `changed` under `net`.
7. **The schematic.** The circuit becomes a schematic through `schgen.generate_schematic` with the layout `readable` (one sheet per module of the import's module tree). Each component's symbol is the `SymbolDef` that its `lib_symbol_ref` names in the project's `.SchLib` files, read by the Altium adapter; a component without one gets a generic symbol with one pin per pin of the circuit (`schgen`'s box). The symbols are written into `<project>.kicad_sym` with its `sym-lib-table`. Positions, wires and sheet symbols' places are not converted: `schematic` is `changed`. Rejected: converting Altium's wires and labels: presentation is after 1.0.
8. **Project and rules.** `write_triad` with the net classes and the class of each net of the import; the neutral rules that the import mapped exactly go to `.kicad_dru` by `lower_rules` for the target (refusals for target 9 as for any design, e.g. creepage); the rules the import left out are already counted by the read (`altium.import.rule-unmapped`) and become `rule` rows of the report. The stack-up of the document goes to the board's `setup` (c0101).
9. **The profile and the oracle.** The direction's profile compares the written board read back with the import: frame `absolute`, `tolerance_nm` 1 (KiCad holds nanometres; the import rounds to whole nanometres already), and `--ignore-ref ""` for the pads without a component (the rule names `H-K-CONV-A2K-IMPORT`). The independent check compares the written board with `kicad-cli pcb import` of the same document at level 5 under the profile `kicad-import`: two converters, one of them KiCad's own, agreeing.
10. **Targets.** `--kicad-version 9` writes for KiCad 9: what target 9 cannot hold is refused or dropped by the writers as for any design and reported (`kicad.token.too-new` rows mapped into the report by c0162's table when it lands, else by kind `kicad-token`).

## Files and public API

| file | content |
|---|---|
| `src/fenolite/convert/to_kicad.py` | the direction Altium to KiCad: layers, keep-outs, slots, names, libraries, schematic, project |
| `src/fenolite/backends/kicad/layers.py` | `board_rows(copper)`, `user_rows(count, *, target)` |
| `src/fenolite/backends/kicad/pcb.py`, `_fpmap.py` | `kicad.board.layer-undeclared`; slots turned with a round or aligned pad |
| `docs/formats/kicad/board.md`, `docs/formats/altium/import.md` | the user layer rows; the keep-out layer row |
| `src/fenolite/convert/data/profiles.toml` | the profile `altium-to-kicad` |
| `tests/unit/convert/test_to_kicad.py`, `tests/unit/backends/kicad/test_layer_undeclared.py` (new) | the scenarios |
| `tests/corpus/test_convert_altium_census.py` (new) | the eight documents and five project sets |
| `tests/kicad/convert/test_a2k_load.py`, `test_a2k_import.py`, `test_a2k_schematic.py` (new) | the three KiCad rows |
| `docs/conversion.md`, `docs/evidence/conversion.md` | the direction, the layer map, the census |

## Sources registered by this change

From the block S-0740 to S-0759: S-0742 for the public Altium page that states what the Keep-Out layer restricts (task 1.3). The KiCad user-layer facts are read from KiCad's own files (S-0030, S-0058) and confirmed by the pinned `kicad-cli` (S-0020, S-0029); if a public page is needed, S-0743.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-CONV-A2K-LOAD | The KiCad board that `convert --to kicad` writes from each public PCB document of the corpus loads in `kicad-cli` 9.0.9 and 10.0.6 for its target, and its DRC runs to a report (S-0020, S-0029) | `tests/kicad/convert/test_a2k_load.py` | probe `convert-a2k-load` `equal` on both majors for every written document |
| H-K-CONV-A2K-IMPORT | That board equals `kicad-cli pcb import` (10.0.6) of the same document at level 5 under the profile `kicad-import`, apart from what the report names lost (S-0029, S-0160) | `tests/kicad/convert/test_a2k_import.py` | probe `convert-a2k-import` `equal` on every written document |
| H-K-CONV-A2K-SCH | The schematic written for a public project set passes KiCad's ERC without a connection error and its netlist (`kicad-cli sch export netlist`) equals the import's circuit at level 2 (S-0020, S-0029) | `tests/kicad/convert/test_a2k_schematic.py` | probe `convert-a2k-sch` `equal` on both majors for the sets the writer takes |
| H-K-BOARD-USERLAYERS | KiCad 9.0.9 and 10.0.6 load a board whose layer table holds user layers `User.1` … `User.n` with the numbers that task 1.2 records, and keep items on them (S-0030, S-0020, S-0029) | `tests/kicad/board/test_user_layers.py` | probe `pcb-user-layers` `equal` on both majors; `n` recorded per major |
| H-A-IMP-KEEPOUT-LAYER | A closed outline on Altium's Keep-Out layer restricts tracks, vias and copper on every signal layer (S-0742) | `tests/unit/convert/test_to_kicad.py -k keepout` (the mapping); no Altium run | the fact row cites S-0742; mapping tested |

All start `INFERRED`. Ids used without changing their level: `H-A-IMP-LAYERS`, `H-A-IMP-PADSTACK`, `H-K-PCB-WRITE`, `H-G-CONV-LEDGER` (its census gains the Altium documents).

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| a written board loads and its DRC runs | `KICAD-VERIFIED (9.0.x, 10.0.x)` | `test_a2k_load.py` in both pinned images |
| agreement with KiCad's importer | `ORACLE-VERIFIED(kicad-cli)` (10.0.6) | `test_a2k_import.py` |
| the schematic | `KICAD-VERIFIED (9.0.x, 10.0.x)` for ERC and netlist | `test_a2k_schematic.py` |
| user layers | `KICAD-VERIFIED (9.0.x, 10.0.x)` | `test_user_layers.py` |
| keep-out mapping | `INFERRED` (public page) | unit test |
| the undeclared-layer refusal | mechanical; the census of committed boards | `test_layer_undeclared.py` |

## Risks / Trade-offs

- **The refusal of undeclared layers hits a user's board.** A board read from KiCad declares its layers, and a script's board is built from `created_layers`; the census of task 1.4 is the proof. A model edited by hand could meet it, and the message names the layer.
- **KiCad's importer and Fenolite disagree** on items that neither documents. The profile `kicad-import` holds the known rules; a new disagreement is either fixed or becomes a rule with a hypothesis, as the triangle does.
- **Generated schematics of large public projects** may be refused by the generator (pins on two nets, very long names). The report says so and the board is still written, as the Altium write does with its schematic.
- **User layer counts differ between KiCad 9 and 10.** Task 1.2 records both; mechanical layers beyond the count are lost and reported.

## Migration Plan

- A new direction of `convert`; `capabilities.conversions` gains `altium` to `kicad` with targets 9 and 10.
- `write_board` refuses items on undeclared layers: before this change it wrote them silently; no committed input holds one.

## Budget (10 days)

| part | days |
|---|---|
| entry check, measurements as tests, `kicad-cli` on the probe files, the census of committed boards | 1.0 |
| facts and registers: user layers, the keep-out page | 0.75 |
| layer table and map, odd counts, the refusal | 1.25 |
| keep-out outlines to rule areas | 0.75 |
| slots, names, the derived footprint library | 1.25 |
| symbols from `.SchLib`, generic symbols, the generated schematic, the symbol library | 2.0 |
| project, rules, stack-up, target 9 | 1.0 |
| oracles: load, importer agreement, schematic | 1.25 |
| documentation, census, closing | 0.75 |
| **total** | **10** |

Cut order: (1) symbols from `.SchLib` (generic symbols for every component); (2) keep-out outlines (reported lost); (3) odd copper counts (refused with a reason). Not cut: the layer map, the refusal of undeclared layers, the derived footprint library, the project and rules files, the importer agreement.

## Open questions

All answered on 2026-10-09: the maintainer accepted every recommended answer (`docs/roadmap.md`, Open decisions row 40).

1. **Refuse items on undeclared layers for every caller, or only in conversion?** Recommended: every caller; a silent item on a layer KiCad does not know is the defect, wherever it comes from. Decided by the maintainer on 2026-10-09: every caller refuses items on undeclared layers.
2. **Mechanical layers beyond KiCad's user layers: lost, or merged onto the last one?** Recommended: lost and reported; merging mixes drawings a fabricator reads apart. Decided by the maintainer on 2026-10-09: lost and reported; never merged onto the last user layer.
3. **The pads without a component (free pads): footprints without a reference, or one footprint `FREE_PADS` holding them all?** Recommended: one footprint per free pad without a reference, as KiCad's importer does, so the two converters agree. Decided by the maintainer on 2026-10-09: one footprint per free pad, without a reference, as KiCad's importer does.
4. **Should the maintainer convert one Altium board of his own drawing and report KiCad's view?** Recommended: optional, after the census; it is a KiCad check, so the oracle already covers it, and his board stays private (the report gives outcomes only). Decided by the maintainer on 2026-10-09: optional, after the census; his board stays private and the report gives outcomes only.
