## Context

- **Scope.** The first v0.2a deliverable (plan, v0.2a): "`backends/kicad/{sch,sym}.py` with a minimal `.kicad_sch` (D10) and reading with `ext`", and the acceptance line "RT0 to RT2 (ERC) on 100 % of the demos' `.kicad_sch` without bus and without multi-instance (explicit list in the manifest)". This change is the reading half: the model, the reader, the same-version rebuild and RT0/RT1. c0061 writes created sheets; c0062 runs ERC and RT2.
- **What exists.**
  - `versions.FileKind.SCHEMATIC` with the constants `20231120` (8.0), `20250114` (9.0) and `20260306` (10.0), and `READ_FLOOR` `20231120`.
  - `sym.py` reads symbol libraries into `SymbolDef`, every sub-symbol kept as a slot (c0008).
  - `slots.py`, `_libread.Context` (exact numbers, opaque slots with a minimum version, issue sink), the token inventory and its fuzz harness (board, footprint, worksheet and rules kinds only).
  - `inspect` reads a `.kicad_sch` header-only and counts root children by head (living `cli-contract`, "Inspect command"). It stays as it is.
  - The corpus has one schematic row (`kicad-demo-10-0-6-sch-01`).
- **The format page** (S-0320, read 2026-10-04) names the root children `version`, `generator`, `uuid`, the page settings, the title block, `lib_symbols`, `junction`, `no_connect`, `bus_entry`, `wire`, `bus`, images, `polyline`, `text`, `label`, `global_label`, `hierarchical_label`, `symbol` (library identifier, position, `unit`, `in_bom`, `on_board`, uuid, properties, `pin` with a uuid, `instances` by `project` and `path` with `reference` and `unit`), `sheet` (position, `size`, stroke, fill, uuid, the mandatory sheet-name and file-name properties, hierarchical pins, `instances` with `page`) and the root sheet instance `(path "/" (page …))`. It asks third-party writers not to use `eeschema` as the generator.
- **Counted on the demo schematics of tag 10.0.6 at proposal time** (2026-10-04; file list from S-0024, files read for facts only, S-0058):
  - 115 files in 17 demo folders, 42 969 833 bytes, the largest 1 416 470 bytes; 36 project files, 35 with a root schematic of their stem, 17 of those with a board.
  - Format versions: `20250114` 91 files, `20250610` 8, `20231120` 7, `20241209` 4, `20260101` 2, `20240602` 1, `20250901` 1, and `20230819` 1, which is older than the read floor.
  - Root heads KiCad writes that the page does not name: `generator_version`, `sheet_instances`, `embedded_fonts`, `text_box`, `rectangle`, `netclass_flag`, `rule_area`, `bus_alias`, `table`.
  - Children of `symbol` that the page does not name: `lib_id` as a list, `exclude_from_sim`, `dnp`, `fields_autoplaced`, `mirror`, `body_style`, `lib_name`, `in_pos_files`.
  - 72 files hold `bus`, `bus_entry` or `bus_alias` items, or a label whose text is a bus; 22 hold a symbol with more than one instance path; 34 hold neither. 7 sheet files are referenced by more than one sheet.
  - All 115 parse with c0006's parser, and `parse(dumps(parse(t)))` is tree-equal to `parse(t)` for each.
- **Third-party schematics.** Two of the repositories the corpus already uses hold S-expression schematics at the pinned commits (S-0027, S-0028), both at format `20230121`, older than the read floor. `kicad-cli` 10 has `sch upgrade`; 9.0 has not (help pages read on 9.0.9 and 10.0.6).
- **Constraints.** Stdlib only. `checks`, `model` and `core` stay backend-free. Nothing from a demo file is committed: rows, counts and names only.

## Goals / Non-Goals

**Goals:**
- A typed reading of what the rest of v0.2a uses: symbols, labels, no-connect flags, sheet references, embedded symbols, paper and title block.
- Everything else kept in place, so an unchanged sheet is rebuilt tree-equal.
- The proof over the corpus, with every file that is not read counted by reason.
- An independent check of the reading: `kicad-cli` lists the same components.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- A reading of wires that would let Fenolite derive nets. Wires, junctions and buses are counted and kept, never interpreted.

## Decisions

1. **Probe first.** Task group 2 adds the two load checks (Decision 12) and records them on 9.0.9 and 10.0.6 before the inventory rows are written. The oracle of Decision 14 comes after the reader, on both majors.

2. **A sheet is a definition outside `Design`.** `fenolite.model.schematic.SchematicSheet` is read from one `.kicad_sch` file and is not a layer of `Design`, as `DrawingSheet` is not (c0012).
   - The circuit is the source of a generated schematic, so a sheet stored in `.fenolite/` would be a second source of the same facts. A sheet read from another project is checked and compared; it is not imported in v0.2a.
   - Rejected: a schematic layer in `Design` now. The model is additive-only from the end of v0.3, so a layer added without a consumer cannot be taken back; v0.5b (editing that keeps presentation) decides it with a consumer in hand.
   - Rejected: backend-local records, as the Altium readers have (c0040). Slots and `ext` belong to model entities, and c0061 and c0066 need a type that `checks` and `lens` may import.

3. **What is modelled.** One table, per head:

   | head | entity or field | children that are modelled | children that are projected |
   |---|---|---|---|
   | root | `SchematicSheet` | `uuid`, `paper`, `title_block`, `lib_symbols`, `symbol`, `label`, `global_label`, `hierarchical_label`, `no_connect`, `sheet`, `sheet_instances` | — |
   | `symbol` | `SymbolInstance` | `lib_id`, `lib_name`, `at`, `mirror`, `unit`, `body_style` (`convert` in files that write it), `exclude_from_sim`, `in_bom`, `on_board`, `dnp`, `uuid` | every `property` (name and text into `properties`; `Reference`, `Value` and `Footprint` also into `ref`, `value` and `footprint`), `instances` (into `uses`) |
   | `label`, `global_label`, `hierarchical_label` | `NetLabel` | the text atom, `shape`, `at`, `uuid` | — |
   | `no_connect` | `NoConnectFlag` | `at`, `uuid` | — |
   | `sheet` | `SheetRef` | `at`, `size`, `uuid` | the properties `Sheetname` and `Sheetfile` (into `name` and `file`), `instances` (into `uses`) |
   | `lib_symbols` / `symbol` | `SymbolDef` | as `sym.py` reads a library symbol | as `sym.py` |
   | `sheet_instances` / `path` | `SheetPage` | the path atom, `page` | — |

   Every other child is an opaque slot at its position: `wire`, `junction`, `bus`, `bus_entry`, `bus_alias`, `polyline`, `text`, `text_box`, `rectangle`, `image`, `netclass_flag`, `rule_area`, `table`, `embedded_fonts`, the header atoms, and any head this change does not know.
   - "Projected" means what it means on boards: the child stays an opaque slot, and its value is also copied into the model (`kicad-file-backend`, "Unmodelled board content is kept as slots").
   - Rejected: typed wires and junctions. They are only useful to derive nets, which plan D9 rejects for schematics Fenolite did not write.

4. **Symbol instances.** `SymbolInstance(lib_ref, position, rotation, mirror, unit, body_style, ref, value, footprint, properties, dnp, in_bom, on_board, exclude_from_sim, lib_name, uses)`.
   - `rotation` is 0, 90, 180 or 270 degrees; `mirror` is `""`, `"x"` or `"y"`.
   - `uses` holds one `SymbolUse(project, path, ref, unit)` per `path` of `instances`, in file order. A symbol with more than one use under one project is a multi-instance symbol.
   - A duplicate property name keeps the last text and gives `kicad.sch.duplicate-property` (warning).
   - An instance whose `lib_id`, or whose `lib_name` when it has one, names no embedded symbol gives `kicad.sch.symbol-undefined` (warning) and is still read.

5. **Labels, flags and sheet references.**
   - `NetLabel(kind, name, position, rotation, shape)`: `kind` is `local`, `global` or `hierarchical` and has no default, so the canonical form always writes it; `shape` is `""` for a local label.
   - `NoConnectFlag(position)`.
   - `SheetRef(name, file, position, size, uses)` with `SheetUse(project, path, page)`. `file` is the text as written. Sheet pins stay opaque slots of the reference.
   - `SheetPage(path, page)` for the root's `sheet_instances`.

6. **Embedded symbols.** Each child of `lib_symbols` is read by `sym.py`'s symbol reader with the text before the first `:` of its name as `library` and the rest as `name`; a name without `:` has an empty library. They are read as written: KiCad embeds flattened copies, so an `extends` child is not expected and is kept if present.
   - Their ids use the native id `sch:<sheet uuid>:<embedded name>`, so an embedded copy never shares an id with the library symbol it was copied from.

7. **Version policy.** The board's (`kicad-file-backend`, "Board version policy"), with `FileKind.SCHEMATIC`: older than `READ_FLOOR` raises `UnsupportedFormatError` (`FEN-3003`); newer than the newest constant is read with `kicad.version.future`, and `rebuild_schematic` refuses it; versions between two constants belong to the next major, as `versions.major_for` says.

8. **Exact numbers.** Lengths with `Atom.to_nm(exact=True)`, angles with `core.units.parse_angle`. A value that is not a whole number of nm or µdeg, a symbol angle that is not a multiple of 90 degrees, and a mirror value this change does not know leave the whole item an opaque slot of the root, with the info `kicad.sch.inexact-length`, `kicad.sch.inexact-angle` or `kicad.sch.kept-opaque`.

9. **Reproducible children.** As on boards ("Modelled children are reproducible"): after mapping an item, the reader re-emits each modelled child and keeps as an opaque projected slot any child the emitter does not reproduce tree-equal, with the info `kicad.sch.kept-opaque`. This is what lets one reader take the 8.0 form (`convert`, bare `hide`) and the 10.0 form without a table per version.

10. **Identifiers.** Sheet `derived_id("sch", "kicad", <root uuid>)`; symbol instance `sci`, label `lbl`, no-connect flag `ncf` and sheet reference `shr`, each from its `uuid`. An item without a uuid takes `content_id(<prefix>, "kicad", <sheet uuid>, <head>, content_hash(<compact text>, <occurrence>))`. A repeated uuid takes the suffix `:<k>` and gives `kicad.sch.duplicate-uuid` (warning). The five prefixes join the closed table.

11. **Rebuild and verdict.**
    - `rebuild_schematic(sheet) -> Node` walks the slot lists: modelled fields are emitted from the model, opaque fragments verbatim. An unchanged sheet gives a tree equal to the parsed source.
    - A modelled field that changed (a symbol moved) is emitted from the model. A projection that changed (a property text, a use) raises `ValueError` naming the entity and the field: editing projections belongs to the change that needs it.
    - `roundtrip_schematic(text, *, file="") -> RoundTrip` returns the `backends.base.RoundTrip` of `backend-protocol`, "Validation operation" (level `RT1`): `tree_equal` (the rebuilt tree equals the parsed one), `model_equal` (reading the rebuilt text gives an equal sheet), `opaque_equal` (equal multisets of opaque digests), `opaque_count`, `passed`, `difference`.
    - `opaque_count(sheet)` counts the opaque slots of the sheet and of every entity in it.
    - Rejected: a `write_schematic` for another target here. Gating a read sheet to an older target needs c0061's writer rules; a rebuild at the same version needs none.

12. **Two load checks for the fuzz harness.**

    | kind | command | outcome `load` when |
    |---|---|---|
    | schematic | `sch export netlist <file> -o <out>.net` | exit 0 and the netlist exists |
    | symbol library | `sym export svg <file> -o <existing dir>` | exit 0 and an SVG exists |

    Observed at proposal time: both majors have both commands; a hand-made `20250114` and `20260306` schematic loads on 9.0.9 and 10.0.6 respectively; a schematic with an invented root child, a missing file and a version `20990101` give "Failed to load schematic" and exit 3 on 10.0.6.

13. **Inventory rows for the two kinds.** `tokens.toml` gains rows of kinds `kicad_sch` and `kicad_sym` for every token name or value introduced after the 8.0 constants, with one `[[note]]` per dated version, as "Inventory scope" asks for boards.
    - The dated versions and their one-line descriptions come from S-0031; each name is confirmed one by one in the keyword list of the schematic editor at the tags (S-0321), which is never converted into data; the fuzz results on both images give each row its level.
    - With the rows in place, the reader passes `_libread.Context.min_version` for the chains `("kicad_sch", …)` and `("kicad_sch", "lib_symbols", "symbol", …)`, and `sym.py` keeps doing so for libraries.
    - Rejected: the conservative file version on every slot. A sheet saved by 10.0 would then carry `20260306` on every slot, and c0061 could never write a symbol read from a 10.0 library for target 9 without a refusal per child.

14. **Components oracle.** `sch.components(sheets, *, project) -> tuple[SchComponent, ...]` lists one `(ref, value, footprint)` per reference, from the uses of `project`, leaving out references that start with `#`; a multi-unit symbol counts once, with the value and footprint of its lowest unit. `KicadCli.export_netlist(schematic, *, files=None) -> CliRun` runs `sch export netlist --format kicadsexpr`. The oracle test compares the two sets on the authored fixtures and on the corpus projects whose sheets carry no `sch-multi` tag, on both majors.
    - Whether a symbol with `(on_board no)` is listed is recorded by a probe; if a major leaves it out, `components` takes `on_board_only=True` for that comparison and the fact row says so.
    - The netlist is parsed by a test helper with c0006's parser. The product netlist reader is c0063's.

15. **Sheet tree.** `sch.sheet_files(root_file) -> SheetTree` reads the root and every file its sheet references name, relative to the referencing file's folder, breadth first. `SheetTree(files, references, issues)`: `files` in first-visit order, `references` mapping each file to the number of sheet references that name it.
    - A file named twice is read once. A reference to a file already on the path from the root gives `kicad.sch.sheet-cycle` (error) and is not followed. A missing file gives `kicad.sch.sheet-missing` (warning). A file outside the root file's folder tree is listed and not read (`kicad.sch.sheet-outside`, info).
    - c0062 uses it for the copy set of an ERC run; the corpus census uses it to tag multi-instance sheets.

16. **Corpus rows.** One row per `.kicad_sch` of the demo folders at tags 10.0.6 and 9.0.9.1, a file identical at both tags listed once, and two third-party rows.
    - Uses: `rt0`, `sch` and one origin; plus `sch-root` for a file with a project file of its stem, `sch-bus` for a file with bus items or a bus label, `sch-multi` for a file that holds a multi-instance symbol or is referenced more than once in its project, and `sch-old` for a file older than the read floor.
    - Ids `kicad-demo-<tag>-sch-NNN` with three digits and `third-party-sch-NN`; the existing row keeps its id. The id pattern of `tests/corpus/test_manifest.py` is widened to two or three digits.
    - The tags are computed by `tests/corpus/test_schematic_census.py` and checked against the manifest, so a wrong tag fails with the row's id.
    - The acceptance list of the plan is then a query: rows with `sch` and neither `sch-bus`, `sch-multi` nor `sch-old`.
    - RT0 and RT1 run on every row without `sch-old`, bus or not: buses are opaque slots, so they do not prevent a round trip. The third-party rows are read as copies re-saved by `kicad-cli` 10 (`sch upgrade`), on major 10 only, as the third-party boards are (`corpus-policy`, "Upgraded copies keep their origin").

17. **Authored fixtures**, CC0, under `tests/data/kicad/schematic/`, written by hand for the Mini library:
    - `flat.kicad_sch` (`20260306`) and `flat_v9.kicad_sch` (`20250114`): a resistor, an LED, the 32-pin IC and the power symbol; global labels, one local label on a wire with a junction, no-connect flags, a text, a DNP symbol and a symbol with `(on_board no)`;
    - `units.kicad_sch` and `units_v9.kicad_sch`: the three units of `Mini_DualGate` under one reference (the symbol is authored for `Mini_v9.kicad_sym` too);
    - `hier/top.kicad_sch` and `hier/child.kicad_sch`: one sheet reference, a hierarchical label and its sheet pin;
    - `multi/top.kicad_sch` and `multi/cell.kicad_sch`: `cell` referenced twice;
    - `bus.kicad_sch`: a bus, two bus entries and a bus label.
    Each is loaded by `kicad-cli` on its major in the oracle test.

18. **Evidence.** `sch.EVIDENCE` starts `INFERRED` (`H-K-SCH-READ`) and is raised to `KICAD-VERIFIED` only when `H-K-SCH-COMPONENTS` holds on both majors. The round trips are `CORPUS-VERIFIED` when `H-K-SCH-RT1` holds on both origins.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/model/schematic.py` (new) | `SchematicSheet`, `SymbolInstance`, `SymbolUse`, `NetLabel`, `NoConnectFlag`, `SheetRef`, `SheetUse`, `SheetPage`; `SymbolMirror`, `LabelKind`, `LabelShape` |
| `src/fenolite/core/ids.py` (extended) | prefixes `sch`, `sci`, `lbl`, `ncf`, `shr` |
| `src/fenolite/backends/kicad/sch.py` (new) | `read_schematic(source, *, file="", issues=None) -> SchematicSheet`; `rebuild_schematic(sheet) -> Node`; `roundtrip_schematic(text, *, file="") -> RoundTrip`; `opaque_count(sheet) -> int`; `opaque_digests(sheet) -> Counter[str]`; `sheet_files(root_file) -> SheetTree`; `components(sheets, *, project, on_board_only=False) -> tuple[SchComponent, ...]`; `EVIDENCE`; `ISSUE_CODES` |
| `src/fenolite/backends/kicad/sym.py` (extended) | `symbol_from(node, *, library, name, native, ctx)`: the symbol reader on one node, used for embedded symbols |
| `src/fenolite/backends/kicad/cli.py` (extended) | `KicadCli.export_netlist(schematic, *, files=None) -> CliRun`; `KicadCli.upgrade_schematic(schematic, *, files=None) -> bytes` (10.0 only) |
| `src/fenolite/backends/kicad/data/tokens.toml` (extended) | rows and notes of kinds `kicad_sch` and `kicad_sym` |
| `tools/kicad_token_fuzz.py` (extended) | the load checks of Decision 12 |
| `tools/gen_schemas.py` (extended); `schemas/fenolite.model.v0/schematic.json` (new) | schema id `fenolite.schematic.v0` |
| `tests/data/kicad/schematic/` (new); `tests/data/libs/Mini_v9.kicad_sym` (extended) | the fixtures of Decision 17 |
| `tests/unit/backends/kicad/test_sch_read.py`, `test_sch_rebuild.py`, `test_sch_tree.py`; `tests/unit/model/test_schematic.py` (new) | hermetic |
| `tests/corpus/test_schematic_census.py`, `test_schematic_rt.py` (new); `tests/corpus/manifest.toml`, `test_manifest.py` (extended) | corpus |
| `tests/kicad/schematic/` (new): `_schcases.py`, `test_components_oracle.py`, `test_schematic_upgraded.py` | oracle, both majors |
| `tests/_netlist.py` (new) | `components(text) -> set[tuple[str, str, str]]`: the components of a KiCad netlist, for tests |
| `docs/formats/kicad/schematic.md`, `docs/evidence/kicad-schematic.md` (new); `docs/design-model.md`, `docs/formats/kicad/tokens.md` (extended) | fact table; census and results; the model section; the generated token page |

## Sources registered by this change

| id | URL | used for |
|---|---|---|
| S-0320 | https://dev-docs.kicad.org/en/file-formats/sexpr-schematic/index.html | the schematic format page: the sections and children listed in "Context", instance paths, label shapes, the generator advice |
| S-0321 | https://gitlab.com/kicad/code/kicad/-/blob/<tag>/eeschema/schematic.keywords; tags 9.0.9.1 and 10.0.6 | confirmation that a single schematic or symbol token name exists at a tag; single names only, never converted into data |

Rows of other changes cited here: S-0001 (common syntax), S-0020 (observed `kicad-cli` behaviour), S-0022 and S-0037 (`sch export netlist`, `sch upgrade`, `sym export svg`), S-0024 (demo file lists), S-0027 and S-0028 (the third-party repositories), S-0031 (dated schematic and symbol versions), S-0041 (symbol library page), S-0058 (demo files, counts only). Task 1.1 widens S-0020, S-0022, S-0024, S-0027, S-0028, S-0031, S-0037 and S-0058, each only with what it states or what was observed. S-0322 to S-0324 stay unused.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-SCH-READ | In a `.kicad_sch` of format `20231120` to `20260306`, every root child and every child of a modelled item is either mapped by the table of Decision 3 or kept as an opaque slot, so a sheet that was not changed is rebuilt tree-equal (S-0320, S-0058) | `tests/unit/backends/kicad/test_sch_rebuild.py`, `tests/corpus/test_schematic_rt.py` | every authored fixture and every corpus row without `sch-old`: `rebuild_schematic(read_schematic(t))` is tree-equal to `parse(t)` |
| H-K-SCH-RT1 | RT0 and RT1 hold on every readable schematic of the corpus, in two origins | `tests/corpus/test_schematic_rt.py`, `tests/kicad/schematic/test_schematic_upgraded.py` | no failure on the demo rows and on the two upgraded third-party copies; files not read are counted by reason in `docs/evidence/kicad-schematic.md` |
| H-K-SCH-COMPONENTS | The references, values and footprints that `sch.components` gives for a project equal the `components` of `kicad-cli sch export netlist` (S-0020, S-0022, S-0037) | `tests/kicad/schematic/test_components_oracle.py` | on 9.0.9 and 10.0.6: probes `sch-components-flat`, `sch-components-units` and `sch-components-hier` = `equal`; `sch-components-on-board` records `present` or `absent`; equal sets on every corpus project without `sch-multi` |
| H-K-SCH-TOKENS | The rows of kinds `kicad_sch` and `kicad_sym` say which major loads each token (S-0031, S-0321) | `tests/kicad/test_token_fuzz.py` | the committed fuzz results of 9.0.9 and 10.0.6 equal the expected outcomes of every new row |

Ids used without changing their level: `H-K-LIB-READ`, `H-K-TOK-CONSTANTS`, `H-K-SEXPR-STRICT`, `H-K-FMT-RESAVE`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Reading and slot split | INFERRED, `H-K-SCH-READ` | `test_sch_read.py`, `test_sch_rebuild.py` |
| Components of a project | KICAD-VERIFIED (9.0.x, 10.0.x), `H-K-SCH-COMPONENTS` | `test_components_oracle.py` |
| RT0 and RT1 over the corpus | CORPUS-VERIFIED, `H-K-SCH-RT1` | `test_schematic_rt.py`, `test_schematic_upgraded.py` |
| Inventory rows | per row, from the fuzz results, `H-K-SCH-TOKENS` | `test_token_fuzz.py` |
| Model, schema, ids, sheet tree | mechanical | unit tests |

## Budget (11 days)

| work | days |
|---|---|
| registers, sources, fact rows | 0.5 |
| load checks, inventory rows, fuzz on both images | 2.0 |
| model, ids, schema | 1.0 |
| reader | 2.5 |
| rebuild, verdict, opaque count | 1.0 |
| sheet tree | 0.5 |
| authored fixtures | 0.75 |
| corpus rows, census, RT0/RT1, upgraded copies | 1.5 |
| components oracle on both majors | 0.75 |
| docs, closing | 0.5 |
| **total** | **11.0** |

Cut order: (1) the third-party copies, and then the round trips are labelled `INFERRED` with one origin; (2) symbol-library rows of the inventory that no demo symbol uses; (3) the `hier` and `multi` corpus comparisons of the components oracle (the authored fixtures stay). Not optional: the reader, the rebuild, RT0 and RT1 on the demo rows, the components oracle on both majors.

## Risks / Trade-offs

- [A head this change does not know appears in a later KiCad version] → it is an opaque slot by default; nothing is lost and `opaque_count` shows it.
- [The 8.0, 9.0 and 10.0 forms differ in more places than the fixtures show] → the reproducibility check keeps what the emitter cannot reproduce; the corpus holds eight format versions.
- [The fetch grows by about 43 MB per tag] → rows identical at both tags are listed once; the `kicad-9` job fetches only the rows of its tag. The measured fetch time is written in `docs/evidence/kicad-schematic.md`.
- [Counts drift when a tag changes] → rows are pinned by SHA-256; the census test names the row.
- [`sch export netlist` writes absolute paths and a date] → the oracle test reads only `components`; nothing of the netlist is stored.
- [The fuzz finds a token the inventory dates wrongly] → the row is corrected before the reader relies on it, as c0007 did; the hypothesis row records each correction.

## Migration Plan

Additive: a model module, a reader module, inventory rows, corpus rows and one runner helper. No command changes its output. To roll back, remove the modules and the rows; the five id prefixes stay reserved.

## Open Questions

- **Should `inspect` show typed counts for a schematic?** Default: no. Its header-only summary already counts root children by head; changing "Inspect command" would chain with c0039 and c0044, which modify the same requirement.
- **A schematic layer in `Design`.** Default: not before v0.5b has a consumer (Decision 2).
- **Rows for demo schematics older than the read floor.** Default: listed with `sch-old`, counted, never read; no upgraded copy is made for a demo.
- **Maintainer:** is the larger fetch of the `kicad-10` and `kicad-9` jobs acceptable, or should schematic rows be fetched by the nightly job only? Default: both jobs fetch them.
