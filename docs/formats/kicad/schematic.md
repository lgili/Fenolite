# KiCad schematics (`.kicad_sch`)

`fenolite.backends.kicad.sch` reads one schematic file into the `SchematicSheet` of
`fenolite.model.schematic` and rebuilds it at its own format version. Since change c0061 it also writes a
created sheet for KiCad 9.0 or 10.0 (`write_schematic`), and `schgen` creates the sheet of a built design
("Generated sheets" below; the user guide is `docs/schematic.md`). The reader derives no net, and nothing
here runs a tool. Sources are listed in `docs/evidence/sources.md`; every fact
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
| `kicad-cli` 9.0.9 refuses a symbol instance with a `body_style` child ("Failed to load schematic", exit 3) and loads `(convert 1)` in its place; 10.0.6 loads both spellings | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-TOKENS |
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
| Load check of a schematic: `kicad-cli sch export netlist <file> -o <out>` exits 0 and writes the netlist; a schematic it cannot load gives "Failed to load schematic" and exit 3 | S-0020, S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-TOKENS |
| Load check of a symbol library: `kicad-cli sym export svg <file> -o <folder>` exits 0 and writes one SVG per unit and body style | S-0020, S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-TOKENS |
| `sch export netlist --format kicadsexpr` lists one `comp` per reference with `ref`, `value` and `footprint`; the units of one symbol give one `comp`, power symbols (reference starting with `#`) give none, and a symbol with `(on_board no)` gives none on 9.0.9 and on 10.0.6 | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-COMPONENTS-2 |

## Generated sheets

The facts `schgen` and `write_schematic` are written from (change c0061). Each was measured with
`kicad-cli sch erc`, `sch export netlist` and `pcb drc --schematic-parity` on sheets written by hand in
`tests/kicad/schematic/_gencases.py` and on projects that `build` wrote; the outcomes per version are in
`docs/evidence/kicad-schematic.md`. The power flag is authored for Fenolite: a staff with a small
rectangular flag and one power-output pin, with no content of any other library.

| fact | source | label | hypothesis |
|---|---|---|---|
| A flat sheet with this token set is loaded by 9.0.9 (written with `version 20250114`) and by 10.0.6 (`20260306`): the header, `uuid`, `paper`, `title_block`, `lib_symbols`, `no_connect` (`at`, `uuid`), `global_label` (the text, `shape`, `at`, `effects`, `uuid`), `symbol` (`lib_id`, `at`, `mirror`, `unit`, `exclude_from_sim`, `in_bom`, `on_board`, `dnp`, `uuid`, properties, one `pin` with a `uuid` per pin, `instances`) and `sheet_instances` | S-0367, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-MINIMAL |
| Written form per target. For 10.0 a symbol instance also holds `body_style` and `in_pos_files`, a property holds `show_name`, `do_not_autoplace` and, when hidden, `hide` as its own children, and a global label holds an `Intersheetrefs` property: this is what a 10.0.6 re-save keeps unchanged. For 9.0 a hidden property has `hide` inside `effects`, a symbol has no `body_style` and no `in_pos_files`, and the root ends with `(embedded_fonts no)`. ERC of the two generated designs reports no violation on its major | S-0020, S-0367 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-MINIMAL |
| A pin connects at its library position turned into the sheet: for a pin at (px, py) in the library frame (Y up) and an instance at (x, y), the mirror is applied first (`mirror x` negates py, `mirror y` negates px), then the rotation by the instance angle counter-clockwise (90° maps (px, py) to (−py, px)), and the point is (x + px′, y − py′). A global label at that point leaves no `pin_not_connected`, for the four angles and the three mirror states | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-PINFRAME |
| A global label at the connection point of a pin puts the pin on the net named by the label's text, and labels of one text are one net; no wire is needed. A `no_connect` at the connection point of a pin on no net removes its `pin_not_connected` and `pin_not_driven` violations | S-0046, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-MINIMAL |
| `sch export netlist` gives a pin on no net a net of its own: `unconnected-(<ref>-<pin name>-Pad<number>)`, or `unconnected-(<ref>-Pad<number>)` for a pin without a name. For a named pin of a symbol with several units the reference is followed by the unit letter (`U2C` for unit 3); in the pin name a blank is written `_` and a `/` is written `{slash}`; `+`, `-`, `_`, `.`, `~`, `{`, `}`, a leading digit and a name that two pins share are written as they are. A pin with a no-connect flag is named the same way | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-UNCONNECTED |
| A pin named `~` in an embedded symbol has no name in a `20250114` sheet (9.0.9 names its net `unconnected-(X1-Pad4)`) and the name `~` in a `20260306` sheet (10.0.6: `unconnected-(X1-~-Pad4)`), as the reader's rule for `~` says; the generator therefore writes an empty name for target 10 where the library meant none | S-0020, S-0031 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-UNCONNECTED |
| The net of a global label is named by the label's text for letters, digits, a blank, `[ ]`, `{ }`, `( )`, a quote, a backslash, a non-ASCII letter and `+ . - _ : , # $ ~ =`. A `/` in the text is stored as `{slash}` in the net name (`mod/LED_A` gives `mod{slash}LED_A`) | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-SLASH |
| The parity test compares pad nets by their stored names: a board pad on `mod{slash}LED_A` agrees with that label, and the same pad on a net stored `mod/LED_A` gives `net_conflict` | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-SLASH |
| A net whose only driver is a power-input pin gives `power_pin_not_driven`; a symbol flagged `power` with one `power_out` pin on that net (Fenolite's authored `fenolite:PWR_FLAG`) removes it, and that symbol names no net | S-0046, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-POWER |
| Two hidden power-input pins of one name end on one net whatever labels they carry (pins `VSS` labelled `GND` and `OTHER` are both on `GND`); the same pins without `hide` are on their two nets | S-0046, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-POWER |
| ERC reports `lib_symbol_issues` for a symbol whose library no table of the project lists. With a project `sym-lib-table` whose row `${KIPRJMOD}/lib/<nickname>.kicad_sym` holds the same definition as the sheet embeds, a pin-pad variant included, it reports neither `lib_symbol_issues` nor `lib_symbol_mismatch` | S-0046, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-LIBTABLE |
| `pcb drc --schematic-parity` reports nothing for a board whose footprints have the references, values and pad nets of the netlist, the `unconnected-(…)` nets included. It matches footprints by reference: a pad on another net gives `net_conflict`, a changed Value `footprint_symbol_mismatch`, a renamed reference `missing_footprint` and `extra_footprint`, and exchanged `path` values give nothing | S-0020, S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-SCH-PARITY |
| `sch upgrade --force` of a generated sheet re-saves only its embedded symbols in the 10.0 form (it adds `in_pos_files`, `duplicate_pin_numbers_are_jumpers`, `show_name`, `do_not_autoplace` and moves `hide` out of `effects`); the order of the root items and every item Fenolite writes itself are kept, ERC still reports nothing, and a second re-save is byte-identical | S-0020, S-0022 | KICAD-VERIFIED (10.0.x) | H-K-SCH-RESAVE |
| What KiCad's "Update PCB from Schematic" writes on a built board is not measured by a test: no headless command runs it. One manual run in 10.0.6 on the built blink example added `sheetname`, `sheetfile` and the pads' `pinfunction` and `pintype`, and changed no field text, position or pad net | S-0046 | INFERRED | H-K-SCH-UPDATE |

Net names on boards follow the same rule (`pcb.stored_net_name`): a created net is written with
`{slash}` for a slash, a net read from a file keeps its spelling, and the reader gives a net stored with
`{slash}` the name with the slash, keeping the stored spelling in the net's `kicad` bag (`stored`).

## Netlist export

What `netlist.read_netlist` reads of the file that `kicad-cli sch export netlist --format kicadsexpr`
writes (change c0063). No format page describes this file; every row is an observation on the netlist of
projects that `build` wrote, on 9.0.9 and on 10.0.6. The outcomes per version are in
`docs/evidence/kicad-schematic.md`.

| fact | source | label | hypothesis |
|---|---|---|---|
| The export is one list `(export (version "E") …)` with the children `design`, `components`, `libparts`, `libraries` and `nets`; 10.0.6 adds `groups` and `variants` between `components` and `libparts` | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NETLIST-SHAPE |
| `components` holds one `comp` per reference, with `ref`, `value`, `footprint`, `description`, `fields`, `libsource`, `property` entries, `sheetpath` and `tstamps` (the uuid of the symbol); 10.0.6 also lists `units` with the pin numbers of each unit. The reader takes `ref`, `value`, `footprint` and `fields` | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NETLIST-SHAPE |
| `fields` holds one `(field (name "N") "text")` per field other than the reference and the value: `Footprint`, `Datasheet`, `Description` and the user fields; an empty field has no text atom | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NETLIST-SHAPE |
| `nets` holds one `net` per net with `code`, `name`, `class` and one `node` per pin; a `node` holds `ref`, `pin` (the pin number), `pintype` and, for a pin with a name, `pinfunction`. The reader takes `name`, `class`, `ref`, `pin` and `pintype` | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NETLIST-SHAPE |
| `pinfunction` is the pin name on 9.0.9 and `<name>_<number>` on 10.0.6, and `code` numbers the nets in the order of the file: the reader ignores both | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NETLIST-SHAPE |
| `pintype` is the electrical type of the pin as a symbol library spells it (`input`, `output`, `bidirectional`, `tri_state`, `passive`, `power_in`, `power_out`, …), followed by `+no_connect` for a pin under a no-connect flag | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NETLIST-SHAPE |
| A symbol whose reference starts with `#` (a power flag) is neither a `comp` nor a `node`, and names no net | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NETLIST-SHAPE |
| `design` holds the date of the export, the tool version and the absolute path of the schematic; `libraries` holds one `uri` per symbol library, as the table writes it on 10.0.6 and resolved to an absolute path on 9.0.9; `libparts` repeats the library symbols. The reader ignores the three sections, so no date and no path of a run reaches Fenolite | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NETLIST-SHAPE |
| For a sheet that `build` wrote, the nets of the export are the texts of the global labels, each with the pins whose points carry it, and one `unconnected-(…)` net per pin without a label: what `sch_netlist.own_netlist` computes from the sheet alone | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NETLIST-OWN |
## Identifiers

- The sheet: `derived_id("sch", "kicad", <root uuid>)`, or `"file:<name>"` without a root uuid.
- A symbol instance, a label, a no-connect flag and a sheet reference: `sci`, `lbl`, `ncf` and `shr`
  from their own uuid; a repeated uuid takes `:<k>` and the warning `kicad.sch.duplicate-uuid`; an item
  without a uuid takes a content id.
- An embedded symbol: `derived_id("sym", "kicad", "sch:<sheet uuid>:<embedded name>")`, so it never
  shares the id of the library symbol it was copied from.

## Issue codes

`sch.ISSUE_CODES` is the closed table of the capability `kicad-schematic`, "Schematic read issue codes". The writer's codes are `sch.WRITE_ISSUE_CODES` (`kicad.sch.dropped-too-new`), and those of the generator, its layout and the embedding are `schgen.ISSUE_CODES`; both are listed in `docs/cli-contract.md` under `build`.
