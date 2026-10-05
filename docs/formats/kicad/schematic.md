# KiCad schematics (`.kicad_sch`)

`fenolite.backends.kicad.sch` reads one schematic file into the `SchematicSheet` of
`fenolite.model.schematic` and rebuilds it at its own format version. Nothing here writes a created
sheet, derives a net or runs a tool. Sources are listed in `docs/evidence/sources.md`; every fact
carries a source id and an evidence label, and the hypotheses are in `docs/hypotheses.md`.

No KiCad C++ source was read for this page. The version-history file S-0031 was consulted for dated
facts only, and the demo schematics (S-0058) for counts only.

## What is modelled

| head | entity or field | modelled children | projected children (kept as written, value copied) |
|---|---|---|---|
| root | `SchematicSheet` | `uuid`, `paper`, `title_block`, `lib_symbols`, `symbol`, `label`, `global_label`, `hierarchical_label`, `no_connect`, `sheet`, `sheet_instances` | none |
| `symbol` | `SymbolInstance` | `lib_id`, `lib_name`, `at`, `mirror`, `unit`, `body_style` (`convert` in files that write it), `exclude_from_sim`, `in_bom`, `on_board`, `dnp`, `uuid` | every `property`, `instances` |
| `label`, `global_label`, `hierarchical_label` | `NetLabel` | the text, `shape`, `at`, `uuid` | none |
| `no_connect` | `NoConnectFlag` | `at`, `uuid` | none |
| `sheet` | `SheetRef` | `at`, `size`, `uuid` | the properties `Sheetname` and `Sheetfile`, `instances` |
| `lib_symbols` / `symbol` | `SymbolDef` | as `sym.py` reads a library symbol (`libraries.md`) | as `sym.py` |
| `sheet_instances` / `path` | `SheetPage` | the path, `page` | none |

Every other child is an opaque slot at its position: `wire`, `junction`, `bus`, `bus_entry`,
`bus_alias`, `polyline`, `text`, `text_box`, `rectangle`, `image`, `netclass_flag`, `rule_area`, `table`,
`embedded_fonts`, the header atoms, the `pin` children of symbols and sheets, and any head the reader
does not know. After mapping an item the reader re-emits each modelled child and keeps as an opaque slot
any child it does not reproduce tree-equal (`kicad.sch.kept-opaque`); this is how one reader takes the
8.0, 9.0 and 10.0 spellings.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| The root is `kicad_sch` with the children `version` and `generator`; the page names the sections unique identifier, page settings, title block, library symbols, junction, no-connect, wire and bus, image, graphical line and text, local, global and hierarchical labels, symbol, hierarchical sheet and root sheet instance | S-0367 | CORPUS-VERIFIED | H-K-SCH-READ |
| KiCad 9.0 and 10.0 also write root children the page does not name: `generator_version`, `sheet_instances`, `embedded_fonts`, `text_box`, `rectangle`, `netclass_flag`, `rule_area`, `bus_alias` and `table`; the reader keeps each as an opaque slot | S-0058 | CORPUS-VERIFIED | H-K-SCH-READ |
| A symbol instance holds the library identifier, the position with an angle, `unit`, `in_bom`, `on_board`, a uuid, properties, one `pin` per pin with a uuid, and `instances` grouped by `project` and `path`, each path with `reference` and `unit` | S-0367 | CORPUS-VERIFIED | H-K-SCH-READ |
| KiCad-written symbol instances also hold `exclude_from_sim`, `dnp`, `fields_autoplaced`, `mirror`, `lib_name`, and in 10.0 files `body_style` and `in_pos_files` | S-0058 | CORPUS-VERIFIED | H-K-SCH-READ |
| `kicad-cli` 9.0.9 refuses a symbol instance with a `body_style` child ("Failed to load schematic", exit 3) and loads `(convert 1)` in its place; 10.0.6 loads both spellings | S-0020 | INFERRED | H-K-SCH-TOKENS |
| An instance path is the `/`-separated chain of the uuids of the root sheet and of the sheet references down to the sheet that shows the symbol; the root sheet's own path is `/` | S-0367 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-COMPONENTS-2 |
| `sch export netlist` resolves a symbol by its instance path, not by the project name: a symbol whose uses are all filed under another project name is listed with the reference of the use whose path is the sheet's path in the hierarchy, and a symbol with no use for that path is listed with the text of its `Reference` property. In the authored fixtures the project name is the stem of the root file | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-COMPONENTS-2 |
| A property text with a text variable (`${…}`) is listed resolved in the netlist; the reader keeps the text as written | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-COMPONENTS-2 |
| The shapes of global and hierarchical labels are `input`, `output`, `bidirectional`, `tri_state` and `passive`; a local label has none | S-0367 | CORPUS-VERIFIED | H-K-SCH-READ |
| A sheet holds a position, a size, a stroke, a fill, a uuid, the two mandatory properties for the sheet name and the file name, its pins, and `instances` whose paths carry a `page` | S-0367 | CORPUS-VERIFIED | H-K-SCH-READ |
| The two mandatory sheet properties are named `Sheetname` and `Sheetfile` in files of the read range | S-0058 | CORPUS-VERIFIED | H-K-SCH-READ |
| The root sheet lists its page in `(sheet_instances (path "/" (page …)))`; a sheet that is only used as a sub-sheet may have no `sheet_instances` | S-0367, S-0058 | CORPUS-VERIFIED | H-K-SCH-READ |
| A third-party writer does not name itself `eeschema` in `generator` | S-0367 | CORPUS-VERIFIED | H-K-SCH-READ |
| Schematic format versions: 8.0 `20231120`, 9.0 `20250114`, 10.0 `20260306`; a file older than `20231120` is refused, and a version between two constants belongs to the next major | S-0031 | INFERRED | H-K-TOK-CONSTANTS |
| The text of a property of a symbol instance is kept as written, a lone `~` included: for a `20250114` file whose `Value` is `~`, `sch export netlist` of 10.0.6 lists the value `~`. The rule that `~` stands for an empty text before version `20250318` (S-0031) is applied to embedded symbol definitions only, as `sym.py` applies it to libraries | S-0020, S-0031 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-COMPONENTS-2 |
| Load check of a schematic: `kicad-cli sch export netlist <file> -o <out>` exits 0 and writes the netlist; a schematic it cannot load gives "Failed to load schematic" and exit 3 | S-0020, S-0022, S-0037 | INFERRED | H-K-SCH-TOKENS |
| Load check of a symbol library: `kicad-cli sym export svg <file> -o <folder>` exits 0 and writes one SVG per unit and body style | S-0020, S-0022, S-0037 | INFERRED | H-K-SCH-TOKENS |
| `sch export netlist --format kicadsexpr` lists one `comp` per reference with `ref`, `value` and `footprint`; the units of one symbol give one `comp`, power symbols (reference starting with `#`) give none, and a symbol with `(on_board no)` gives none on 9.0.9 and on 10.0.6 | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-COMPONENTS-2 |

## Identifiers

- The sheet: `derived_id("sch", "kicad", <root uuid>)`, or `"file:<name>"` without a root uuid.
- A symbol instance, a label, a no-connect flag and a sheet reference: `sci`, `lbl`, `ncf` and `shr`
  from their own uuid; a repeated uuid takes `:<k>` and the warning `kicad.sch.duplicate-uuid`; an item
  without a uuid takes a content id.
- An embedded symbol: `derived_id("sym", "kicad", "sch:<sheet uuid>:<embedded name>")`, so it never
  shares the id of the library symbol it was copied from.

## Issue codes

`sch.ISSUE_CODES` is the closed table of the capability `kicad-schematic`, "Schematic read issue codes".
