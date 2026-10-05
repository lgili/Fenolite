# Building for Altium (experimental)

`fenolite build design.py --out DIR --target altium` builds a DSL design into an Altium Designer project
instead of a KiCad project: a project file `<name>.PrjPcb`, a schematic `<name>.SchDoc`, in Altium's
binary form by default or in its ASCII form with `--altium-format ascii` (see "Schematic forms"), and one
schematic library (`.SchLib`) per library that the lib ids name (see "Schematic libraries"). Altium
compiles the schematic, and its engineering change order creates the PCB from it. Fenolite writes no PCB
document.

The target is **experimental** (changes c0032, c0033 and c0034): its output, options and issue codes may change in any
release. `fenolite capabilities` lists it under `result.experimental`, and its evidence stays `INFERRED`
(see "Evidence" below). Format facts and their sources are in `docs/formats/altium/`; everything else on
this page is a Fenolite choice.

## Command

```bash
fenolite build design.py --out build/myboard --target altium --dry-run    # plan only
fenolite build design.py --out build/myboard --target altium --confirm    # write
fenolite build design.py --out build/myboard --target altium --altium-format ascii --confirm
```

- `--target kicad` stays the default, and a KiCad build is unchanged. `--target` accepts `kicad` and
  `altium`; any other value is a usage error (`FEN-2001`, exit 2).
- The rules of `docs/dsl.md` hold as for KiCad: the script runs as your own code, `--out` is never the
  script folder, writes follow `--dry-run` and `--confirm`, and `--discard-layout` and `--no-backup` work
  the same. `--seed` and `--timestamp` change nothing, and neither do `--kicad-version` and
  `--allow-lossy`.
- The build reads the script and, only for KiCad lib ids and KiCad footprint links, their symbol and
  footprint libraries, through the same library tables as `--target kicad` (the script folder's
  `sym-lib-table` and `fp-lib-table`, then the global tables). It reads no Altium file and starts no
  external tool. `--kicad-version` changes
  bytes only through the library configuration it selects.
- `result` holds `design`, `target` (`"altium"`), `out`, `files`, the counts `components`, `nets`,
  `labels`, `power_ports` and `no_connects` (the No ERC directives written), `sheet` (`A4` … `A0` or `custom`), `kept`, `schematic_format` (`binary`
  or `ascii`), `libraries` (the planned `.SchLib` paths), `symbols` (the number of library components),
  `experimental` (`true`) and `script_output`. Planned writes have the kinds `altium_prjpcb`,
  `altium_schdoc_binary` or `altium_schdoc_ascii` (by form, since both forms are `.SchDoc` files),
  `altium_schlib`, `altium_harness` and `fenolite`.
- `--altium-sheets {flat,modules}` picks one schematic sheet (`flat`, the default) or one sheet per
  top-level module (see "Sheets and harnesses"). `result` then also holds `sheet_mode`, `sheets` (the
  schematic files, the top sheet first), `ports`, `sheet_entries` and `harnesses` (the harness types
  drawn). Any other value, or the option with `--target kicad`, is a usage error (`FEN-2001`, exit 2).
- `--altium-format {binary,ascii}` picks the schematic form; without it the form is `binary`. Any other
  value, or the option with `--target kicad` (given or by default), is a usage error (`FEN-2001`,
  exit 2), and nothing is written.

## Lib ids, footprints and pins

- `Part(ref, lib_id, footprint=None, value="")` takes a lib id `<library>:<name>`, split at the first `:`,
  in one of two forms (change c0034):
  - an **Altium link**, whose library part ends with `.SchLib` (any letter case), names an Altium
    library file: `Part("U1", "MyParts.SchLib:LDO", footprint="MyParts.PcbLib:SOT23", value="5V")`.
    Its symbol is generic (see "The schematic").
  - any other lib id is a **KiCad lib id**, such as `Device:R`, resolved like `--target kicad` does: the
    part gets the symbol's pins, names, electrical types and units.
  A `lib_id` or a footprint without both parts is refused (`altium.lib-id-form`, `altium.footprint-form`).
- The lib id becomes the component's library link: Design Item ID `LDO`, Source `MyParts.SchLib` for an
  Altium link, and Source `<name>.SchLib`, the library the build writes, for a KiCad lib id.
  "Tools » Update From Libraries" takes its source from this link.
- The footprint becomes the component's current footprint model, `SOT23` from `MyParts.PcbLib`. A part
  without a footprint gets the warning `altium.no-footprint`: the change order cannot place it.
- A part of a KiCad lib id without `footprint` takes its symbol's `Footprint` property, and an empty
  value takes the symbol's `Value`. Footprint libraries are never opened.
- **Connect pins by number** for Altium links: `U1[3]`, not `U1["VOUT"]`. Each designator becomes a pin
  number, and the change order matches pins to footprint pads by number; Fenolite cannot check them
  against an Altium library, because it reads none. For KiCad lib ids a pin name works too: `U1["VCC"]`
  connects every pin named `VCC`, and a member that names neither a number nor a name of the symbol is
  refused (`altium.unknown-pin`).
- Every written text (design name, refs, values, net names, library, symbol and footprint names, pin
  designators) must be printable 7-bit ASCII without `|` and without leading or trailing spaces, and a
  value must not start with `=` (Altium reads it as a reference to another parameter). Anything else is
  refused with `altium.text-unwritable`, never escaped or replaced. Net names or refs that differ only
  in letter case are refused (`altium.name-case-collision`).

## The schematic

- **Bodies from the library symbol.** Each component is drawn from the symbol its library holds,
  placed with the symbol's origin at the component's location, so the schematic and the library hold
  the same pins at the same places (change c0034).
  - **Generic bodies** (Altium links): a rectangle with one passive pin per designator that the nets
    name on any part of that lib id, in natural order (`1`, `2`, `10`, `A1`, `B`): the first half on
    the left edge, the rest on the right, 200 mil long and 100 mil apart. Parts sharing a lib id share
    one body.
  - **KiCad symbols**: every pin of body style 1 and the common style at its place, length and
    direction, with its electrical type, edge shape and visibility, and one synthesised rectangle per
    unit around its pins (the symbol's own graphics are not read). A symbol of several units is placed
    once per unit (parts A, B, …, in consecutive cells); common pins are drawn on every part and wired
    on part A only.
  - The designator is drawn above the body and the comment below it; the comment is the value, or the
    symbol name when the value is empty.
- **Connections.** Every pin gets a short wire stub, outwards from its end: horizontal for left and right
  pins, vertical for top and bottom pins, whose labels run upwards along the stub. A net of a `Power(hv, lv)` interface ends
  each stub with a power port named after the net: the "power ground" symbol for a net that is only ever
  the `lv` member, a bar otherwise. Every other net gets a net label on each stub. Labels of one name
  join within the sheet; ports of one name join across the design. No wire runs between parts. When
  adjacent pins on one edge both end in ports, their stubs alternate between short and long, so no port
  overlaps its neighbour.
- **Layout.** Parts are placed in component-path order, so a module's parts stay together, in rows on
  the smallest ISO sheet, A4 to A0 landscape, that holds them. A design too large for A0 gets a custom
  sheet and the warning `altium.sheet-custom`.
- **Unique ids.** Each component's unique id is derived from its component path. A rebuild that keeps
  the paths keeps the ids, so Altium keeps the links between schematic and PCB components.
- **Not lowered.** The board outline, placements, the rule values of net classes and diff pairs have no
  place in these files (the nets of a net class are declared by directives, see "Change order"). They stay in `.fenolite/`, and each kind gives one `altium.not-lowered` info. By default modules
  only order the layout and the schematic is one flat sheet; `--altium-sheets modules` gives each
  top-level module its own sheet (next section).

## Sheets and harnesses

Change c0037. `--altium-sheets {flat,modules}` chooses how the schematic is split; the default, `flat`,
writes the single sheet described above, byte for byte as before.

```
fenolite build design.py --out build/myboard --target altium --altium-sheets modules --confirm
```

- **One sheet per top-level module.** `<name>.SchDoc` becomes the top sheet and each top-level module gets
  `<name>_<module>.SchDoc` beside it. Parts outside any module stay on the top sheet. Nested modules are
  flattened: a part of `power/ldo` is drawn on the sheet of `power`. The hierarchy has one level and no
  sheet is repeated.
- **Sheet symbols.** The top sheet holds one sheet symbol per module, in module-name order, named after
  the module, with the module sheet's file name.
- **Ports and sheet entries.** A net with pins on a module's sheet and on another sheet gets a port on
  the module's sheet and a sheet entry of the same name on its sheet symbol. Each has a short wire with a
  net label, like a pin; no wire is routed between sheet symbols, the labels of the top sheet join them.
  The port, the sheet entry and every label carry the net's name, so the nets keep the names of the flat
  build.
- **Power nets are global.** Nets of a `Power(hv, lv)` interface keep their power ports on every sheet,
  which Altium joins across the project, and get neither a port nor a sheet entry.
- **Harnesses.** `Harness(name, members)` (`docs/dsl.md`) groups nets with different names, such as
  `Harness("SPI", {"MOSI": mosi, "MISO": miso, "SCK": sck, "CS": cs})`. When nets of a harness leave a
  module, the build draws one port and one sheet entry named after the harness instead of one per net.
  On the module sheet the port has a block beside it: a signal harness line, a harness connector with
  one entry per member, the harness type, and a labelled wire on each entry whose net leaves that
  module. Every block of a type holds all its entries, so the definitions never differ; an entry whose
  net stays on one sheet is drawn without a wire, which Altium Designer reports as the warning
  "Unconnected Harness Entry". Each sheet with a block gets `<sheet stem>.Harness`, a definition file
  with the line `<type>=<entry>,<entry>,…`, listed in the project file after the module sheets.
- **Harnesses on the top sheet.** When a harness runs between exactly two modules that are neighbours
  in name order, and no other sheet holds a pin of its nets, the top sheet joins the two sheet entries by
  one signal harness line: the entry of the first module on the right side of its symbol, the entry of
  the second on the left side of its symbol, and no connector, wire or label. The nets keep the names
  their labels give them on the module sheets. In every other case (three modules, a pin on the top
  sheet, the two symbols in different rows of the sheet) each sheet entry gets the same block as a port,
  with labels that join the sheets; Altium Designer then warns that each of those nets has multiple
  names, the label and the name each sheet entry derives from the harness (maintainer's report of
  2026-10-03).
- **The ASCII form writes no harness.** With `--altium-format ascii` the hierarchy is written, and the
  nets of a harness cross as plain nets with their own ports. A harness that is not drawn (in the `flat`
  mode, in the ASCII form, or because none of its nets leaves a module) gives one `altium.not-lowered`
  info and stays in `.fenolite/`.
- **Names.** A harness type name or entry name may not hold `=`, `,` or `;`, two names may not differ
  only in letter case, a type name may not equal a net name, a net belongs to at most one harness entry,
  and a power net belongs to no harness. Two top-level modules may not differ only in letter case. These
  are errors in both modes, so a design is refused before its mode is switched.
- **Unique ids and the PCB link.** Components keep their unique ids in both modes. A sheet symbol gets
  an id derived from its module name and a port one from its module and name. In the PCB document a part
  on a module sheet links as `\<sheet symbol id>\<component id>` with the hierarchical path
  `<name>\<module>`, the form Altium saves; a part on the top sheet keeps `\<component id>`. Its channel
  offset counts the parts of its own sheet from 0. Every module gets its sheet symbol on the top sheet,
  also when none of its nets leaves it.
- **Project file order.** A new project file lists the schematic documents first and together: the
  top sheet, then the module sheets in module-name order, then the PCB document, the libraries and the
  harness files. With the PCB document and the libraries between the top sheet and the module sheets,
  Altium Designer 26.5 took only the first module sheet into the hierarchy, and the parts of the other
  sheets were missing from the compiled design (maintainer's report of 2026-10-03). An existing
  `<name>.PrjPcb` is kept as it is: if it comes from an earlier build with the other order, delete it
  and build again, or move its module-sheet sections up in Altium.
- **Switching the mode later.** On a design whose PCB was already made in Altium, switching between
  `flat` and `modules` changes the links of the parts on module sheets. "Project » Component Links"
  matches them again by designator (S-0164). Decide the mode before the first change order.
- **Rebuilds.** Every sheet and harness file follows the edited-output rule on its own. A sheet of an
  earlier build that the new plan no longer holds (a renamed module, or a switch back to `flat`) is left
  in the folder and is no longer listed. A kept project file does not list new sheets:
  `altium.sheets-not-in-project` names them, to add with "Project » Add Existing to Project".
- **Evidence.** The sheet symbols, ports, harness records, the `Additional` stream, the definition files
  and the two-id link are `INFERRED` from public sources and checked against sheets Altium saved in two
  public repositories (`docs/formats/altium/`). Only the maintainer's report of Part H of
  `docs/evidence/altium-schematic.md` settles the nine `H-A-SCH-HIER-*` and `H-A-SCH-HARN-*` rows.
  On 2026-10-03, in Altium Designer 26.5, the sheets and harness blocks of the sample opened, and on
  the board example (`examples/altium_hier_board/`) both module sheets were under the top sheet after
  a compile and "Design » Update PCB Document" listed no component, pin or net change. It offered to
  remove the board's net class, which the schematic does not declare yet. The compile messages, the
  net list and the change order of the rebuilt hierarchy sample (steps H3 to H5) are not reported.
  The sample is `examples/altium_hier/design.py`, with its built files under `tests/data/altium/hier/`.

## No-connect marks

`no_connect(u1[11], u1[12])` (`docs/dsl.md`, "No-connect marks") marks pins as intentionally
unconnected. Altium's compiler otherwise reports each open input as a floating pin.

- **The directive.** Each marked pin gets one No ERC directive (record 22) at its electrical end, in
  the binary and in the ASCII form, in the "Suppress All Violations" mode, drawn as a red thin cross.
  The directives are the last records of the schematic, so a design without marks keeps its bytes.
  `result.no_connects` counts them.
- **No stub.** A marked pin gets no wire, no net label and no power port; its cell on the sheet is the
  cell of an unconnected pin.
- **Resolution.** For a KiCad lib id a mark is resolved like a net member: a pin number stays, a pin
  name marks every pin of that name, and a designator that is neither is refused
  (`altium.unknown-pin`). For an Altium link the marked designator joins the generic body and the
  generated library symbol, even when no net names it. A marked designator must be writable text
  (`altium.text-unwritable`).
- **Marked and connected.** A pin that is marked and on a net is refused with
  `model.no-connect-on-net` (error, exit 5, nothing written).
- **Libraries.** The symbols of KiCad lib ids, their pins and pin types, the project file, the PCB
  library and the PCB document do not depend on the marks. The resolved marks are kept in
  `.fenolite/circuit.json`.
- **Update From Libraries.** A directive is a sheet object, not a part of the component. It stays at
  its sheet position when "Tools » Update From Libraries" replaces a body; if the update moves a pin,
  move the directive back onto the pin's end.
- **Evidence.** Record 22 and its keys are `INFERRED` from public sources (`H-A-SCH-NC-RECORD`). No
  source says that a directive on a pin's end without a wire silences the compiler for that pin
  (`H-A-SCH-NC-ERC`), nor that the Altium 365 Viewer draws it (`H-A-SCH-NC-VIEWER`); the maintainer
  checks all three with `examples/altium_kicad/no_connect.py` (Part N of
  `docs/evidence/altium-schematic.md`). On 2026-10-03, in Altium Designer 26.5, a binary build of the
  blink example with two marked pins showed the cross at each marked pin, and the compiler no longer
  named those pins; the committed sample, the ASCII form and the Viewer are not reported.

## Schematic forms

Altium reads a `.SchDoc` in two forms, and both use the same extension, so the form is chosen by option,
never by file name.

- **Binary (default).** Altium's own default save format: a compound file (Microsoft's MS-CFB container)
  with two streams. `FileHeader` holds a header record, then every record of the schematic, each a
  length word and the record's text ending with a NUL; `Storage` holds an empty icon store. The records,
  their keys, order and values are exactly those of the ASCII form; only the header text and the framing
  differ. Facts: `docs/formats/altium/compound-file.md` and `schematic-binary.md`.
- **ASCII (`--altium-format ascii`).** One record per CR LF line (change c0032). Its bytes are exactly
  what c0032 writes; the ASCII golden files under `tests/data/altium/sample/` are this form.
- **Size limit.** Fenolite's compound-file writer writes no DIFAT sector, so the header can list at most
  109 FAT sectors, about 7 MB of file. A larger binary schematic is refused with the error
  `altium.schematic-too-large` (exit 5, nothing written); `--altium-format ascii` has no such limit. A
  schematic that size has thousands of parts.
- **Switching forms.** A rebuild that only changes `--altium-format` replaces an unchanged schematic
  without `--discard-layout`: the edited-output check compares the file on disk with the last build
  record, not with the new form.

### Checking a build without an Altium licence: the Altium 365 Viewer

The free Altium 365 Viewer (a web page, S-0149) renders Altium design files without Altium Designer. It
takes one file, or one project in a Zip archive, up to 200 MB, and lists `*.SchDoc` among its inputs.

1. Build with the default (binary) form.
2. Open the Viewer page and upload `<name>.SchDoc` alone, or a Zip holding `<name>.PrjPcb` and
   `<name>.SchDoc`.
3. Check the sheet: every part with its pin numbers, designator and comment, the power ports and the net
   labels.

The Viewer only renders: it neither compiles the project nor runs a change order, so nets and the PCB
update still need Altium Designer. Upload only files you may share with Altium's service. In the
maintainer's check of 2026-10-02 the Viewer rendered the binary sample and refused the ASCII sample with
a generic message about supported files, so upload the binary form (`docs/evidence/altium-schematic.md`,
Part V and "Reports").

## Schematic libraries

The build writes the libraries that the schematic's links name, so "Tools » Update From Libraries" finds
every component (change c0034). Facts: `docs/formats/altium/schematic-library.md`.

- **File names.** All KiCad lib ids of a design share one library, `<name>.SchLib` (the design name).
  Each Altium link library gets the file it names, for example `MyParts.SchLib`. Each library holds one
  component per distinct symbol the design uses, in a compound file with one storage per component.
- **Symbols.** A KiCad symbol keeps its pins (numbers, names with `~{…}` overbars rewritten as Altium's
  `A\B\`, electrical types, positions, lengths, directions, shapes, hidden pins), its units as parts and
  its common pins as Part Zero; its body is a synthesised rectangle per part (`altium.symbol-simplified`).
  Other body styles and pin alternates are dropped. Pins off the 10-mil grid are refused
  (`altium.symbol-off-grid`; KiCad's 50-mil grid is on it). Types and shapes with no Altium equivalent
  are mapped with the warning `altium.pin-lossy`. The designator prefix is the `Reference` property, the
  comment the `Value`, and the footprint model the `Footprint` property.
- **Generic stand-in libraries.** An Altium link library holds generic symbols, the bodies the schematic
  draws. It stands in for your real library of the same name and copies nothing from it
  (`altium.schlib-generic`). Keep the real library elsewhere: Fenolite refuses to overwrite a library in
  `--out` that changed since the last build, and putting the generated one in place of the real one
  hides the real symbols.
- **Names.** A symbol name longer than 31 characters is stored under a section key
  (`altium.section-key`); two lib ids that give one library and one storage name, such as `Device:R` and
  `Other:R`, or library file names that differ only in letter case, are refused
  (`altium.symbol-name-collision`).
- **In the project.** The project file lists each library as a document after the schematic. A kept
  project file does not: `altium.schlib-not-in-project` names the libraries to add.
- **Oracle.** `kicad-cli sym upgrade X.SchLib -o Y.kicad_sym` converts a library through KiCad's Altium
  importer. `tests/kicad/altium/test_schlib_oracle.py` converts both committed libraries and compares
  every pin with its source on kicad-cli 10.0.6 and 9.0.9. KiCad is not Altium: that confirms what
  KiCad's importer reads, not that Altium opens the file (Part L of `docs/evidence/altium-schematic.md`).
- **Example.** `examples/altium_kicad/` builds from its own `FenoliteDemo.kicad_sym` through its
  `sym-lib-table`; its build is committed under `tests/data/altium/kicad_example/`.

## PCB library and PCB document (change c0035)

**Footprint sources.** A footprint link whose library part ends with `.PcbLib` (any letter case) is an
Altium link: the link is written as given and no footprint is written. Every other link is a KiCad
footprint id, resolved with the same library tables as `--target kicad` (`fp-lib-table` beside the
script, then the global table). A link that does not resolve gives `altium.footprint-unresolved`
(warning) and the build goes on.

**`<name>.PcbLib`.** Every resolved KiCad footprint goes into one PCB library named after the design,
beside `<name>.SchLib`; the schematic links each KiCad footprint to it (`MODELDATAFILE0=<name>.PcbLib`),
whether or not that footprint could be written. Written: surface and through-hole pads (round, oval,
rectangular and rounded-rectangle shapes, round holes, plated or not), lines, rectangles, arcs and circles
on the mapped layers. Refused, with `altium.footprint-unsupported` (warning; the footprint is not
written): trapezoid and custom pads, connector pads, padstacks, slots and oval or offset drills, chamfered
corners, a through-hole pad with copper on one side, and graphics on copper layers. Dropped, with
`altium.primitive-dropped` (warning): polygons, filled rectangles and circles, graphics on unmapped layers,
and pad settings the Altium record has no field for (mask and paste margins, zone and thermal settings).
Texts, properties and 3D model links are not written (`altium.footprint-extras-dropped`, info); Altium adds
the designator and comment when it places a footprint. Two KiCad links with one footprint name give
`altium.footprint-name-collision` and neither is written.

**Layer map.** One table, Fenolite's choice for fabrication and courtyard (Altium has no fixed layer for
them, and no KiCad oracle can check it; tell us which mechanical layers you use):

| Fenolite layer | Altium layer |
|---|---|
| `F.Cu`, `B.Cu` | Top Layer (1), Bottom Layer (32) |
| `F.SilkS`, `B.SilkS` | Top Overlay (33), Bottom Overlay (34) |
| `F.Fab`, `B.Fab` | Mechanical 13 (69), Mechanical 14 (70) |
| `F.CrtYd`, `B.CrtYd` | Mechanical 15 (71), Mechanical 16 (72) |
| through-hole pads | Multi-Layer (74) |

**`<name>.PcbDoc` (experimental).** Written when the design has a board outline without cutouts and every
component with a footprint link has a KiCad link whose footprint is in `<name>.PcbLib`; otherwise
`altium.pcbdoc-not-written` (info) names the reason. It holds the outline, the layer stack, every
component with a footprint at its script placement (unplaced ones are staged right of the outline as the
KiCad build stages them, with `altium.pcb-staged`), its pads at absolute coordinates with their nets, its
graphics, and its designator (the comment is written hidden), and the copper of "Copper" below.
The frame: Y up, the board's lower-left corner and the origin at (1000 mil, 1000 mil); bottom-side parts
are mirrored as KiCad places them and their layers swapped. Each component carries
`SOURCEUNIQUEID=\<id>`, the unique id of the same component in `<name>.SchDoc`, so "Design » Update PCB
Document" should match every component (`H-A-PCB-DOC-LINK`). When the document is written, the board and
the placements and the net classes are no longer reported by `altium.not-lowered`; a board's keep-outs,
texts, graphics and holes are. A document edited in Altium is refused on
the next build like any edited output; `--discard-layout` replaces it. Fenolite never merges it.

**Oracles.** `kicad-cli fp upgrade <name>.PcbLib -o <dir>.pretty` converts the library back (10.0 and
9.0); `tests/kicad/altium/test_pcblib_oracle.py` counts the files, since a footprint KiCad cannot find
still exits 0, and compares the geometry. `kicad-cli pcb import --format altium` (10.0 only) reads the
document; `tests/kicad/altium/test_pcbdoc_oracle.py` reads its JSON report and its standard output, where
missing storages are reported. Both check only what KiCad's importer reads.

**In Altium.** With `<name>.PcbLib` in the project, the change order into a new PCB document finds every
KiCad footprint (step 5 below). With `<name>.PcbDoc` in the project, open it and run "Design » Update PCB
Document": no component should be added or removed. The checks are in `docs/evidence/altium-pcb.md`; the
free Altium 365 Viewer opens `.PcbDoc` files but not `.PcbLib`.

## Copper (change c0038)

`<name>.PcbDoc` holds copper, and it invents none. The format facts are in
`docs/formats/altium/pcb-copper.md`; what Altium Designer does with them is `INFERRED` until the
maintainer reports Part C of `docs/evidence/altium-pcb.md`.

**What is written.**

- Tracks and arcs as free primitives with their net, in the short forms Altium Designer 26.5 accepts.
- Through vias in the 321-byte form Altium saves.
- Each zone as one polygon pour per layer **without poured copper**: the outline, the net, a name and a
  pour index. Altium fills them on a repour: run "Tools » Polygon Pours » Repour All" once after opening
  the document. The build says so with `altium.zones-unpoured`. A zone's fills are never copied.
- A stack of 2 or 4 copper layers, from `design.board(..., copper=…)`. The stack values come from the
  model's stack-up when it fits, else from Fenolite's defaults (1.4 mil copper; for four layers a 0.2 mm
  prepreg, a 1.0 mm core and a 0.2 mm prepreg).
- One net class per `design.rules.netclass(...)`, with its nets.
- Clearance, Width and Routing Via Style rules: one per class value, and one `All` rule per kind with
  Fenolite's defaults (0.2 mm, 0.25 mm, a 0.6 mm via with a 0.3 mm hole). Width and via limits span the
  written copper, so the document's own copper never breaks them.

**Layers.** An inner layer is a signal layer unless the script declares it a plane:

| Fenolite layer | as | Altium layer |
|---|---|---|
| `F.Cu` | signal | Top Layer (1) |
| `In1.Cu` | signal | Mid-Layer 1 (2) |
| `In2.Cu` | signal | Mid-Layer 2 (3) |
| `B.Cu` | signal | Bottom Layer (32) |
| first inner layer declared as a plane | plane | Internal Plane 1 (39) |
| second inner layer declared as a plane | plane | Internal Plane 2 (40) |

`design.board(mm(50), mm(30), copper=4, planes={"In1.Cu": gnd})` makes `In1.Cu` an internal plane on
`GND`. A plane holds one net and no primitive: through vias and pads cross it, and Altium's default plane
rules decide how they join it. A zone of the plane's net on that layer is left to the plane
(`altium.plane-zone-merged`). The KiCad target writes no plane; it reports `build.plane-not-lowered`.

**Refused, with an error and no file.** Nothing is dropped to make a document fit.

- Blind, buried and micro vias, and vias that do not span the top and the bottom layer
  (`altium.via-unsupported`).
- Copper on a layer the board does not have (`altium.copper-layer`); a stack other than 2 or 4 layers, or
  a plane on an outer layer or an unknown net (`altium.copper-stack`).
- A track or arc on a plane, or a zone of another net on it (`altium.plane-copper`): split planes are not
  written.
- A zone without an outline (`altium.zone-unsupported`); a track of zero length, a width of 0, a drill not
  below its diameter (`altium.copper-invalid`).

**Where the copper comes from.** A build takes the copper from exactly one of three routes:

1. **Script copper.** The tracks, vias and stitching vias that the script declares with `Design.track`,
   `Design.via` and `Design.stitch` (`docs/copper.md`), together with its `Design.zone` pours.
   `fenolite build design.py --out DIR --target altium` resolves the intents as the KiCad build does: it
   runs that build in memory, writes none of its files, and copies the resolved copper
   (`result.copper.source` is `script`). `examples/blink_routed` gives 11 tracks and 7 vias.
   - An intent that does not resolve (`kicad.copper.*` or `kicad.frame.*` error) refuses the build: exit 5,
     no file.
   - An intent that creates nothing is reported, never dropped silently: `kicad.copper.end-unplaced` (it
     ends at a part that is not placed), `kicad.copper.stitch-empty`, `kicad.copper.stitch-skipped`. A part
     that the script does not place is named by `layout.unplaced`.
   - Shorts and clearances of script copper are not judged for this target: the copper guard runs for the
     KiCad target only (`docs/cli-contract.md`, `build`).
2. **`--copper-from BOARD.kicad_pcb`.** A routed KiCad board of the same design: build the KiCad project
   from the script, route it in KiCad, then run
   `fenolite build design.py --out DIR --target altium --copper-from DIR_KICAD/<name>.kicad_pcb`.
3. **Routers.** The router plugins of c0016 and c0023 return model copper, which the build writes as it
   writes any copper the model holds.

When a script with copper intents is built with `--copper-from`, the board wins: the intents are not
resolved, and one `altium.not-lowered` info names them. The board of a KiCad build of that script
already holds its script copper, so both routes give the same document.

**Checks of `--copper-from`.** The board must be of the same design. Fenolite reads it in-process (no
`kicad-cli`) and checks, before any copper is copied:

- every component with a footprint matches exactly one footprint of the board, by the `fenolite.path`
  property, else by reference; a board footprint the design does not hold is a mismatch too;
- each footprint is the linked one, with the pad numbers and positions of the library footprint;
- every pad is on the net of the same name as the design puts its pin on;
- the outline's box is the design's;
- every net of the copper is a net of the design (`altium.copper-net-missing`).

A difference gives `altium.copper-board-mismatch` with the component, the pad or `outline` in `where`,
and the board's path in the message. **The board's placements win**: the copper is only right relative to
the footprints as the board places them, so every component is written where the board has it, and
`altium.placement-from-board` names the parts whose placement differs from the script's. Keep-outs,
texts, graphics and holes of the board are not copied (`altium.not-lowered`).

`result.copper` reports what was written: `source` (`none`, `model`, `script` or `board`), `from`,
`layers`, `planes`, `tracks`, `arcs`, `vias`, `zones` (polygons), `net_classes` and
`placements_from_board`.

**Oracles.** `tests/kicad/altium/test_pcbdoc_copper_oracle.py` imports the routed sample and the plane
variant with `kicad-cli pcb import` and compares the copper and the layer types;
`test_copper_from_oracle.py` proves that copper copied with `--copper-from` equals the source board after
the way back. KiCad reads a plane of the stack as a `power` layer; it does not import the plane's net,
net classes or rules.

## Project file and outputs

Under `--out DIR`:

- `<name>.PrjPcb`: `[Design]`, `Version=1.0`, `<name>.SchDoc` as `[Document1]` and each library as
  `[Document2]`, `[Document3]`, …, written only when the folder has no `<name>.PrjPcb` yet. An existing project file is kept, whatever `--discard-layout`
  says, listed in `result.kept` and reported with `altium.project-kept`, because Altium rewrites it when
  you add the PCB document. Delete it to get a new one.
- `<name>.SchDoc`: the schematic, a binary compound file by default, or ASCII text with CR LF line ends
  with `--altium-format ascii`.
- `<library>.SchLib`: one schematic library per library file the lib ids give (see "Schematic
  libraries"), always a compound file.
- `<name>.PcbLib` and `<name>.PcbDoc` (change c0035, see above), listed in a new project file right
  after the schematic documents (the document, `[Document2]` in a flat build) and with the libraries. A kept project file does not list them:
  `altium.pcb-not-in-project` names them.
- With `--altium-sheets modules`: `<name>_<module>.SchDoc` per top-level module and `<sheet stem>.Harness`
  per sheet with a harness block. A new project file lists the top sheet, then the module sheets, then
  the PCB document, the libraries and the harness files ("Sheets and harnesses").
- `.fenolite/`: the six layer files of the model, with the pins the build gave the components, and
  `build.json` with `"target": "altium"`.

**Edited outputs.** As for KiCad (`docs/dsl.md`, "Edited outputs"), a schematic or library changed since
the last build, for example one saved by Altium in any form, is refused with `FEN-7001` (exit 7) and one
`build.layout-exists` issue. `--discard-layout` replaces it and keeps a `.bak` unless `--no-backup`.
Work done on the schematic in Altium is lost by such a rebuild: change the design script instead.

## Change order

"Design » Update PCB Document" compares the compiled schematic with the PCB document. Besides components
and nets it compares classes, rooms and some rules, which Altium derives from the schematic and the
project options. The build writes what is needed for that comparison to find no class difference
(change c0048):

- **Net classes.** Each net of a net class (`design.rules.netclass(...)`) carries a Parameter Set directive
  on one of its stubs, once per sheet, with a hidden parameter `ClassName` holding the class name. A new
  project file ends with a `[PrjClassGen]` section whose `NetClassManualEnabled=1` is the project option
  "Generate Net Classes" (tab "Class Generation", "User-Defined Classes"). The PCB document holds the same
  class with the same nets, so Altium keeps it. Without that option, or with the Constraint Manager flow,
  Altium ignores the directives and proposes to remove the class from the board.
- **Component classes.** Altium derives one component class per schematic sheet that holds a part. The PCB
  document holds each of them with the refs of the sheet's parts: named after the module for a module sheet
  (`--altium-sheets modules`; the name of its sheet symbol), and after the sheet, which is the design name,
  for the top sheet or the single sheet of a flat build. A new project file with a PCB document or module
  sheets sets, for every schematic document, `ClassGenCCAutoEnabled=1`, `ClassGenCCAutoRoomEnabled=0` and
  `ClassGenNCAutoScope=None`: component classes on, rooms off, no net class per sheet.
- **A kept project file.** An existing `<name>.PrjPcb` is kept, so these keys reach only a project file
  that the build writes. For a project made before this change, delete the project file and rebuild, or
  tick "Generate Net Classes" and untick "Generate Rooms" in the project options yourself.

What the change order may still propose:

| difference | why | what to do |
|---|---|---|
| "Add Rules": "Supply Nets", one per net with a power port | Altium suggests the rule when its advanced setting `Schematic.AutoGenerateSupplyNetsRule` is on (S-0185, S-0312). Fenolite does not write it: no permitted source holds the rule's record | execute it (it adds a rule with a voltage of 0 and removes nothing), untick the group, or turn the setting off |
| "Add Rooms" | only when "Generate Rooms" is ticked for a sheet. Fenolite writes no room, for the same reason, and turns the option off in a new project file (`H-A-ECO-ROOMS`) | untick "Generate Rooms", or execute it: a room is added beside the board |
| "Add Component Classes" or "Add Rooms" on a flat build | not expected since the sheet's class and the class keys are written: the maintainer's repeat of step E4 listed neither (`H-A-ECO-SHEETCLASS`). A build made before that, or a project file that Altium saved earlier, may still show them | execute it; it removes nothing |

The maintainer's report of 2026-10-04 (Altium Designer 26.5; Part E of `docs/evidence/altium-pcb.md`)
confirms this for a build with module sheets: its change order lists only the two "Supply Nets" rules
(`H-A-ECO-NETCLASS`, `H-A-ECO-PRJ-KEYS`, `H-A-ECO-COMPCLASS`, `H-A-ECO-ROOMS`, `H-A-ECO-SUPPLY`). A flat
build kept its net class in that report but was offered a component class and a room for its sheet; both
are written or turned off since, and the repeat of the same day on the rebuilt samples lists only the two
"Supply Nets" rules for the flat build too (`H-A-ECO-SHEETCLASS`). The ticks of the tab "Class
Generation" were not reported.
An author report never raises the build's evidence level.

## Issue codes

| code | severity | when |
|---|---|---|
| `altium.lib-id-form` | error | a `lib_id` is not `<library>:<name>` with both parts |
| `altium.footprint-form` | error | a footprint is not `<library>:<name>` with both parts |
| `altium.text-unwritable` | error | a written text is not printable 7-bit ASCII, holds `\|`, is empty, has a leading or trailing space, or is a value that starts with `=` |
| `altium.name-case-collision` | error | two net names, or two refs, differ only in letter case |
| `altium.unique-id-collision` | error | two components, sheet symbols or ports get the same unique id |
| `altium.schematic-too-large` | error | the binary schematic needs more than 109 FAT sectors (about 7 MB); never with `--altium-format ascii` |
| `altium.library-too-large` | error | a schematic library needs more than 109 FAT sectors |
| `altium.unknown-pin` | error | a net member names neither a pin number nor a pin name of a resolved symbol |
| `altium.symbol-off-grid` | error | a pin position or length of a resolved symbol is not a multiple of 10 mil |
| `altium.pin-text-too-long` | error | a pin name or number is longer than 255 bytes |
| `altium.symbol-name-collision` | error | two lib ids give one library and one storage name, or two library file names differ only in letter case |
| `altium.no-footprint` | warning | a part names no footprint |
| `altium.sheet-custom` | warning | the layout does not fit A0, so a custom sheet is written |
| `altium.pin-lossy` | warning | a pin's electrical type or shape has no Altium equivalent and is mapped |
| `altium.generic-symbols` | info | components of Altium links got generic bodies |
| `altium.symbol-simplified` | info | a resolved symbol's graphics became rectangles, or other body styles or alternates were dropped |
| `altium.section-key` | info | a lib ref longer than 31 characters is stored under a section key |
| `altium.schlib-generic` | info | a library is written with generic symbols |
| `altium.schlib-not-in-project` | info | the project file is kept, so the libraries are not listed in it |
| `altium.not-lowered` | info | the board, placements, the rule values of the net classes (their nets are declared in the schematic), diff pairs or harnesses are kept in the model only (without a PCB document); the script's rule minimums (`where` = `design-rules`, with or without a PCB document: its rules come from the net classes); a board's keep-outs, texts, graphics and holes; a stack-up that does not fit; items of a copper source that are not copied |
| `altium.project-kept` | info | `<name>.PrjPcb` exists in `--out` and is kept |
| `altium.pcb-too-large` | error | the PCB library or document needs more than 109 FAT sectors |
| `altium.footprint-unresolved` | warning | a KiCad footprint link does not resolve |
| `altium.footprint-unsupported` | warning | a footprint is refused (a pad or graphic with no exact Altium form) |
| `altium.footprint-name-collision` | warning | two KiCad footprint links give one footprint name |
| `altium.primitive-dropped` | warning | a footprint graphic or pad setting is left out |
| `altium.footprint-extras-dropped` | info | a footprint's texts, properties or 3D model links are not written |
| `altium.pcbdoc-not-written` | info | the PCB document's conditions do not hold |
| `altium.pcb-staged` | info | unplaced components are staged beside the outline |
| `altium.pcb-not-in-project` | info | the project file is kept, so the PCB files are not listed in it |
| `altium.sheet-name-collision` | error | two top-level module names differ only in letter case, so their sheet files would collide |
| `altium.harness-name` | error | a harness type name or entry name holds `=`, `,` or `;`; two type names, or two entry names of one type, differ only in letter case; or a type name equals a net name in any letter case |
| `altium.harness-net-shared` | error | a net is a member of two harnesses, or twice of one |
| `altium.harness-power-net` | error | a member of a harness is also a member of a `power` interface |
| `altium.sheets-not-in-project` | info | the project file is kept, so the module sheets and harness files are not listed in it |
| `altium.copper-stack` | error | the board's copper layers are not `F.Cu`, `B.Cu` or `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu`, their count differs from `copper`, or a plane names a layer that is not an inner layer or a net the design does not hold |
| `altium.copper-layer` | error | a track, arc, via or zone names a layer outside the board's copper layers |
| `altium.via-unsupported` | error | a via is blind, buried or micro, or does not span the top and the bottom layer |
| `altium.zone-unsupported` | error | a zone has fewer than three outline points, or names no layer |
| `altium.copper-invalid` | error | a track of zero length, a width of 0 or less, a drill not below its diameter, or a net id that names no net |
| `altium.plane-copper` | error | a track or arc lies on a plane layer, or a zone on a plane layer has another net than the plane |
| `altium.copper-board-mismatch` | error | a copper source does not match the design: a component, a footprint, a pad net or the outline |
| `altium.copper-net-missing` | error | copper of a source is on a net whose name the design does not hold |
| `altium.copper-no-document` | error | a copper source is given and the PCB document is not planned |
| `altium.zones-unpoured` | info | polygons are written without poured copper |
| `altium.plane-zone-merged` | info | a zone on a plane layer with the plane's net is left to the plane |
| `altium.placement-from-board` | info | components are placed as the board of `--copper-from` places them, not as the script requests |

Model findings (`model.*`) pass through. A build with an error exits 5 and writes nothing. A KiCad lib id
that does not resolve stops the build with `FEN-3001` (exit 3) and its `kicad.lib.*` issues.

## In Altium Designer

1. Put the footprint libraries the footprints name beside the project file, or install them. The
   change order searches the project folder first. The schematic libraries are written beside it.
2. Open `<name>.PrjPcb`. The schematic and the libraries are listed among the project's documents.
3. Compile the project ("Project » Validate PCB Project", "Compile PCB Project" in older versions) and
   check the nets in the Navigator panel.
4. Add a new PCB document to the project and save the project. Altium rewrites the project file;
   later builds keep it.
5. Run "Design » Update PCB Document", then "Validate Changes" and "Execute Changes".
6. "Tools » Update From Libraries" finds every component in the written libraries, whose pins sit
   where the schematic draws them (`H-A-SCHLIB-UPDATE`). With your real Altium libraries instead of the
   generated stand-ins, use "Replace selected attributes" with graphical attributes off: parameters and
   models are updated, and the generic bodies and every connection stay. A full replacement puts the real
   symbols in, whose pins may sit elsewhere, so the stubs may be left unconnected (`H-A-SCH-UPDATE`).
7. After a change to the script, rebuild with `--target altium --confirm`, compile, and run the change
   order again. Unchanged component paths keep their unique ids, so the PCB components stay linked
   (`H-A-SCH-RELINK`).

## Reading a compound file

`fenolite.backends.altium.read.cfb` reads an MS-CFB container without interpreting its streams. Use
`open_compound(data, file="", limits=DEFAULT_LIMITS, strict=False)` for bytes and
`read_compound(path, limits=DEFAULT_LIMITS, strict=False)` for a file. `is_compound(data)` checks only the
signature. `CompoundFile` exposes `header`, `root`, `nodes()`, `node(path)`, `children(path="")`,
`streams()`, `storages()`, `read(path)`, `as_dict()` and `tree()`. Paths use `/`; lookups ignore case,
while `Node.path` preserves stored spelling. The container and all chains are checked when it opens;
`read(path)` copies that stream only. `tree()` returns the writer's `Storage` and `Entry` forms.

The default limits are 1,073,741,824 input bytes, 262,144 directory entries and 64 nested storages.
`read_compound` checks the file size before reading. Version 3 evidence is `CORPUS-VERIFIED` for the ten
public rows tested by c0039; version 4 remains `INFERRED` until a public version 4 file is available.
`fenolite inspect FILE --streams [--limit-bytes N]` lists storages and streams by path. Its result contains
container sizes and counts, the root CLSID, and one entry per stream or storage; stream entries include
their size and SHA-256. It does not interpret stream content or run a subprocess. Full result fields are
in `docs/cli-contract.md`, section "inspect".

Reader notes are `Issue` values, ordered by this table. `strict=True` raises the first note.

| code | severity | meaning |
|---|---|---|
| `cfb.note.minor-version` | info | minor version differs from `0x003E` |
| `cfb.note.header-fields` | info | a tolerated header field or declared chain count differs from the specification's usual value |
| `cfb.note.partial-sector` | warning | trailing bytes do not make a complete sector |
| `cfb.note.fat-marks` | info | FAT/DIFAT marks or past-file FAT entries are unusual |
| `cfb.note.high-size-bits` | info | version 3 high size bits are ignored |
| `cfb.note.long-chain` | info | a chain has sectors beyond the entry's size |
| `cfb.note.entry-fields` | info | an entry has tolerated metadata, storage size or colour fields |
| `cfb.note.tree-order` | warning | sibling links do not follow the name search order |
| `cfb.note.orphan-entries` | warning | entries are not reachable from a storage and are omitted |

Every malformed container raises `CompoundError`, a `FormatError` with `rule`, `file`, `locator` and byte
`offset`. The message starts with the `cfb.*` rule code. The closed structural-error table is:

| code | meaning |
|---|---|
| `cfb.signature` | signature mismatch |
| `cfb.truncated` | input shorter than its signature or header |
| `cfb.header` | unsupported version, sector shifts, byte order or cutoff |
| `cfb.difat` | invalid, repeated or incomplete FAT/DIFAT listing |
| `cfb.chain` | invalid, repeated or undersized regular or mini chain |
| `cfb.shared-sector` | two chains claim one regular or mini sector |
| `cfb.directory` | invalid type, link or repeated tree entry |
| `cfb.name` | invalid name length, encoding or character |
| `cfb.duplicate-name` | sibling names collide under the MS-CFB name order |
| `cfb.size` | stream or mini stream size exceeds its chain |
| `cfb.limit` | a configured reader limit is exceeded |

CLI errors map to `FEN-3004` (exit 3); their `where` names the file, locator and byte offset when present.

## Evidence

- Every format fact is `INFERRED` from public sources (`docs/formats/altium/`). `kicad-cli` cannot read a
  `.SchDoc` (S-0132, S-0020), so no oracle checks the schematic. The binary form's facts are the
  `H-A-SCHBIN-*` rows, the libraries' the `H-A-SCHLIB-*` rows; the build's evidence names them all.
- `kicad-cli sym upgrade` reads the libraries: the facts that KiCad's importer reads are
  `ORACLE-VERIFIED(kicad-cli)` once its round trip passes (`H-A-SCHLIB-KICAD`), which settles no
  Altium-only fact and never raises the build's level.
- The maintainer checks the committed sample (`examples/altium_sample/`, files under
  `tests/data/altium/sample/`, the binary build under `binary/`) in Altium Designer and in the Altium
  365 Viewer following `docs/evidence/altium-schematic.md`. Each
  confirmed `H-A-SCH-*` or `H-A-PRJ-*` row becomes an author report,
  `ALTIUM-VERIFIED(author-report; …)`, which never promotes an operation: the envelope of
  `build --target altium` stays `INFERRED` for every design.

## Limits

One flat sheet by default, or one level of hierarchy with `--altium-sheets modules` (no repeated sheets,
no deeper levels, no routed wires between sheet symbols, no port directions, no harness in the ASCII form,
no nested harnesses); no buses, variants or output jobs; the PCB document has unpoured polygons, no
split planes, no blind, buried or micro vias and only three kinds of rules, and the PCB library holds only the footprint content listed above; schematic libraries hold synthesised rectangles, not the symbols' graphics, and no
alternate display modes; an Altium library is never read or copied, only stood in for; text in 7-bit
ASCII only. The v0.3 reader currently reads the MS-CFB container; schematic, PCB and Altium library
records are interpreted by later changes.
