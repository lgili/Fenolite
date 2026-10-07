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
  module (see "Sheets and harnesses"). `result` then also holds `sheet_mode`, `sheets` (the
  schematic files, the top sheet first), `ports`, `sheet_entries` and `harnesses` (the harness types
  drawn). Any other value, or the option with `--target kicad`, is a usage error (`FEN-2001`, exit 2).
- `--altium-symbols {graphics,generic}` (change c0086) picks how a resolved symbol is drawn: `graphics`
  (the default) from its own graphics, `generic` as one rectangle per part. **The default output of an
  Altium build changed with this option**: `generic` gives the files that earlier versions wrote, byte
  for byte. `--altium-directions {on,off}` (default `on`) picks the I/O types of ports and sheet
  entries. `--altium-bodies {off,extruded}` (change c0121, default `off`) picks whether the extruded
  component bodies of the board's footprints are written ("Component bodies" below). All three are
  usage errors without `--target altium`. `result.schematic` holds `sheets`,
  `symbols`, `symbols_drawn`, `symbols_simplified`, `buses`, `parameters`, `directions` and `directed`.
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
  - **KiCad, catalog and authored symbols**: every pin of body style 1 and the common style at its
    place, length and direction, with its electrical type, edge shape and visibility. The body is the
    symbol's own graphics (change c0086, the default `--altium-symbols graphics`): its lines,
    rectangles, polygons and circles at their own coordinates, filled where the symbol fills them, in
    Altium's default colours. Three kinds of symbol keep one synthesised rectangle per unit around
    their pins, each with one `altium.symbol-simplified` info: a symbol of several units or body
    styles (the model does not say which unit draws a graphic), a symbol without graphics, and a KiCad
    symbol with an arc, a Bezier curve or a text (the model does not hold those). `--altium-symbols
    generic` draws every symbol as that rectangle, the output of earlier versions. A symbol of several
    units is placed once per unit (parts A, B, …, in consecutive cells); common pins are drawn on
    every part and wired on part A only.
  - **Parameters** (change c0086): each property of a part (`Part(..., properties={"MPN": "X-1"})`)
    is a hidden parameter of its component, in name order. `Comment`, `Designator`, `Footprint`,
    `Reference` and `Value` are not parameters, nor is a property without a value. A property that no
    parameter can hold (a name outside 7-bit ASCII, a value the form cannot carry, a name that repeats
    another in a different letter case) stays in the model, and one `altium.not-lowered` info names it.
  - **Text outside ASCII** (change c0086): in the binary form the comment of a part and the value of
    a parameter may hold any printable character of Windows-1252 (`Indutância 10 µH`); it is written
    in that code page with a UTF-8 copy beside it. Every other text, and every text of the ASCII
    form, is printable 7-bit ASCII; `altium.text-unwritable` names the first character refused and
    says whether the binary form carries it. The PCB document holds 7-bit text: there such a comment
    is replaced by the symbol name, with one `altium.not-lowered` info.
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
- **Not lowered.** The board outline, placements, the rule values of net classes, diff pairs and typed interfaces have no
  place in these files (the nets of a net class are declared by directives, see "Change order"). They stay in `.fenolite/`, and each kind gives one `altium.not-lowered` info. By default modules
  only order the layout and the schematic is one flat sheet; `--altium-sheets modules` gives each
  top-level module its own sheet (next section).

## Sheets and harnesses

Change c0037. `--altium-sheets {flat,modules}` chooses how the schematic is split; the default, `flat`,
writes the single sheet described above, byte for byte as before.

```
fenolite build design.py --out build/myboard --target altium --altium-sheets modules --confirm
```

- **One sheet per module, at any depth** (change c0086). `<name>.SchDoc` becomes the top sheet and each
  module gets a sheet of its own beside it: `<name>_<module>.SchDoc` for a top-level module, and
  `<name>_<module path with "." for "/">.SchDoc` below it, so the module `power/ldo` is
  `<name>_power.ldo.SchDoc`. Parts outside any module stay on the top sheet; a part is drawn on the
  sheet of its own module. No sheet is repeated. The tree, its order (a module before its sub-modules,
  siblings in natural order) and the sheet names are those of the KiCad schematic (`docs/schematic.md`);
  the files stay beside the project, with the design name in front, as Altium opened them in Part H.
- **Sheet symbols.** A sheet holds one sheet symbol per module directly below it, in that order, named
  after the last segment of the module path, with the module sheet's file name.
- **Ports and sheet entries.** A net with pins on a module's sheet or below it, and on any other sheet,
  gets a port on the module's sheet and a sheet entry of the same name on its sheet symbol. A net that
  crosses two levels is passed through the sheet between, which holds its port and the sheet entry of
  the module below. Each has a short wire with a net label, like a pin; no wire is routed between sheet
  symbols, the labels of a sheet join them. The port, the sheet entry and every label carry the net's
  name, so the nets keep the names of the flat build.
- **Port directions** (change c0086). A port and its sheet entry carry the same I/O type, from the pin
  types of the net on the two sides of the sheet boundary: the pins on the module's sheet and below it
  ("inside"), and all the others ("outside"). A side is *bidirectional* when it holds a bidirectional
  pin, else a *driver* when it holds an output, tri-state, open-collector, open-emitter or power-output
  pin, else an *input* when it holds an input or power-input pin, else *passive*.

  | inside | outside | I/O type |
  |---|---|---|
  | bidirectional | any | bidirectional |
  | any | bidirectional | bidirectional |
  | driver | driver | bidirectional |
  | driver | input or passive | output |
  | input | driver, input or passive | input |
  | passive | driver, input or passive | unspecified |

  An unspecified type is left out of the record, as Altium leaves it out. A harness and a bus carry no
  type. `--altium-directions off` leaves every port and sheet entry unspecified.
- **Buses** (change c0086). A bus of the model whose nets are one stem followed by consecutive integers
  (`D0` to `D3`) is drawn as a bus: a bus line with the net label `D[0..3]`, and per member a bus entry
  and a wire with the member's net label, so the nets keep their names. Where the bus leaves a module
  it is one port and one sheet entry named `D[0..3]` instead of one per net; a sheet that only passes
  it through draws it twice, at its port and at the sheet entry below. A bus with other net names, or
  with a power net, a harness net or a net of another bus, is drawn as its nets
  (`altium.bus-flattened`). The DSL has no bus yet: a bus reaches a build from a design that was read
  from a schematic.
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
  and a power net belongs to no harness. Two modules may not give one sheet file name, or names that
  differ only in letter case. These are errors in both modes, so a design is refused before its mode is
  switched. A harness is drawn where it leaves a top-level module; below the first level its nets cross
  as ports.
- **Unique ids and the PCB link.** Components keep their unique ids in both modes. A sheet symbol gets
  an id derived from its module name and a port one from its module and name. In the PCB document a part
  on a module sheet links as `\<sheet symbol id>\<component id>` with the hierarchical path
  `<name>\<module>`, the form Altium saves; a part on the top sheet keeps `\<component id>`. A part two
  levels down links through both sheet symbols, `\<id>\<id>\<component id>`, with the path
  `<name>\<module>\<module>` (the ids as saved designs hold them; the path form below the first level is
  inferred, step Y8). Its channel offset counts the parts of its own sheet from 0. Every module gets
  its sheet symbol on the sheet above, also when none of its nets leaves it.
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
- **Evidence of change c0086.** Symbol graphics, sheets below the first level, I/O types, bus records,
  text with a UTF-8 copy and parameters read back with Fenolite's own reader (`H-A-SCHX-READBACK`),
  and KiCad's importer reads the library graphics as the model holds them. Nothing of it has been
  opened in Altium: the six rows `H-A-SCHX-GRAPHICS`, `-TREE`, `-DIR`, `-BUS`, `-TEXT` and `-ECO` wait
  for the report of Part Y of `docs/evidence/altium-schematic.md`. The sample is
  `tests/data/altium/tree/design.py` with its built files beside it. The author reports of 2026-10-02
  and 2026-10-03 covered the samples `blink`, `kicad_example`, `no_connect` and `routed` with rectangle
  bodies; those bytes are kept under `tests/data/altium/generic/` and `--altium-symbols generic` still
  gives them.

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
  its common pins as Part Zero; its body is its own graphics, or a synthesised rectangle per part where
  "The schematic" says so (`altium.symbol-simplified`). Symbols the script authored or took from the
  catalog are written the same way, and no library is read for them (change c0086).
  The `Reference` and `Value` fields that the KiCad build generates for catalog and authored footprints
  (change c0077) change no Altium document: a placed component is named from the part's reference and
  value. The KiCad build that resolves script copper for an Altium project takes the catalog's
  definitions too, so a design that names only catalog ids and declares tracks builds.
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
the placements and the net classes are no longer reported by `altium.not-lowered`, and a board's keep-outs,
texts, graphics and holes are written ("Complete board" below). A document edited in Altium is refused on
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
- Through, blind and buried vias in the 321-byte form Altium saves, with one drill pair per span.
- Each zone as one polygon pour per layer **without poured copper**: the outline, the net, a name and a
  pour index. Altium fills them on a repour: run "Tools » Polygon Pours » Repour All" once after opening
  the document. The build says so with `altium.zones-unpoured`. A zone's fills are never copied.
- A stack of 2 or 4 copper layers, from `design.board(..., copper=…)`, or the copper layers that the
  model's board names (any even count, see "Complete board"). The stack values come from the
  model's stack-up when it fits, else from Fenolite's defaults (1.4 mil copper; for four layers a 0.2 mm
  prepreg, a 1.0 mm core and a 0.2 mm prepreg).

**Complete board (change c0085).** A model can hold more than a script declares: a design that was
imported, or one built in Python from the model's classes, as the sample `tests/_altium_board6.py` is.
The build writes these items too, and `result.pcb` counts them: `written` maps each kind (`footprint`,
`pad`, `track`, `arc`, `via`, `zone`, `text`, `graphic`, `keep-out`, `hole`, `body`, `rule`) to the number
of model items the document holds, and `not_lowered` the kinds with items it does not hold. Every item is
in one of the two; an item that is not written has an issue whose `where` is `<kind>/<id>`.
`result.pcb.bodies` (change c0121) is the value of `--altium-bodies` that was used.

| item | written as | not written |
|---|---|---|
| copper layers | any even count from 2 to 32 with at most 16 signal layers and 16 internal planes; the k-th inner layer is Mid-Layer k, a plane declared with `planes` is the next Internal Plane; dielectrics with thickness, material and constant from the stack-up | an odd count or a larger stack: the stack of the two outer layers and `altium.not-lowered` (`where` = `stackup`) |
| vias | through, blind and buried, with the two layers of their span; one drill pair per distinct span | a micro via: `altium.via-unsupported` (warning), the build goes on |
| board texts | stroke texts with string (any character, through the wide string), layer, position, height, stroke width and rotation; mirrored on a bottom-side layer | no justification and no TrueType or barcode text (the model holds none); a text on a copper or user layer, an empty or multi-line text |
| graphics | lines, arcs, circles and drawn rectangles and polygons as tracks and arcs without a net; filled rectangles and polygons as regions; on the silkscreen, paste, solder-mask, fabrication and courtyard layers | a graphic on copper or on a user layer, a filled circle, a drawn shape of width 0 (a graphic on `Edge.Cuts` is the outline) |
| keep-outs | one keep-out region with its restrictions for vias, tracks, pads and copper (in the key Altium saves and, for KiCad's importer, in `KEEPOUTRESTRIC` too), on the Keep-Out layer when it names every copper layer, else one per layer | `no_footprints` (reported, the keep-out is written with the others); a keep-out with no other restriction |
| holes | a free pad without copper, plated or not | a slot (the model's board hole is round) |
| component bodies | with `--altium-bodies extruded` only (change c0121): an extruded body with an outline and a height above its standoff, as one record in `ComponentBodies6` and its twin in `ShapeBasedComponentBodies6`, owned by its component, with its two heights, its side, a mechanical layer (its own when it is Mechanical 1 to 16, else Mechanical 13 on the top side and 14 on the bottom side) and its name. **Experimental, off by default, never opened in Altium** | without the option, every body; with it: a body that names a 3D model (the model holds a name and no data), a body without an outline, a height that is not above the standoff or a standoff below the board surface, a body whose footprint is no component of the document; each `altium.not-lowered` (`where` = `body/<id>`) with its height and its reason. No body is made for a footprint that has none |
| zones | one **unpoured** polygon per layer, as above; a zone whose islands are never removed keeps them | poured copper, always: **repour the board in Altium** ("Tools » Polygon Pours » Repour All") |

**Component bodies (change c0121).** The model can hold component bodies on a footprint: an extruded
body has an outline, a height and a standoff; a body of kind `model` names a 3D model. A script declares
none today (the DSL has no height), so bodies come from an import or from a model built in Python, as the
sample `tests/_altium_body2.py` is.

- **What is written, and when.** Only with `--altium-bodies extruded` (in the library: `bodies="extruded"`
  on `lens.altium.build_altium`, `lens.altium.write_model`, `lower.from_design`, `lower.write_design`,
  `AltiumBackend.write` and `AltiumBackend.model_roundtrip`). Each extruded body with an outline of at
  least three points and a height above its standoff becomes one record in `ComponentBodies6` and its
  twin in `ShapeBasedComponentBodies6`, linked to its component by index: the outline placed with the
  component and rounded to whole units, the standoff and the overall height, the board side of the
  footprint, a mechanical layer and the name as the identifier. The bodies of a footprint definition go
  into the PCB library as primitives of type 12.
- **What is not written.** A body that names a 3D model, ever: its record must name model data in the
  `Models` storage, and the design model holds a name and no data. A body without an outline, with a
  height that is not above its standoff, or with a standoff below the board surface. No model file, no
  entry of `Models`, no texture, no arc in an outline, no cylinder and no sphere. Each body that is not
  written is one `altium.not-lowered` (info) with `where` `body/<id>`, its height and its reason.
- **Nothing is invented.** A footprint without a body gets none: no outline is derived from a courtyard
  or any other graphic, and no height is assumed.
- **Off by default, and why.** The saved form of an extruded body holds 35 keys
  (`docs/formats/altium/pcb-bodies.md`, "Written form of an extruded body"). For 33 of them the public
  corpus gives a value rule. For two, `MODELID` and `MODEL.CHECKSUM`, it gives none: Fenolite writes
  stand-ins (a GUID derived from the body's id, and `0`), and only Altium can say whether it takes them.
  That is `H-A-PCBX-BODY-OPEN`, step X8 of the author report (`docs/evidence/altium-pcb.md`, Part X),
  which is **not settled**. The option stays `off` until that step is reported.
- **How far the evidence goes.** It is thin. The rows of the record were measured on 1272 saved extruded
  bodies of five public documents of three repositories, and 1265 of the 1272 come from one repository.
  They say what Altium saved in those files, not what Altium accepts. Nothing that Fenolite writes for a
  body was opened in Altium. Fenolite's own reader reads a written body back to the model's body
  (`H-A-PCBX-BODY-READBACK`, `INFERRED`), and KiCad's importer reads the document as it reads the same
  document without bodies and shows nothing for an extruded body (`H-A-PCBX-BODY-KICAD`): neither says
  that Altium shows the body. `result.pcb.bodies` records the value used, and with `off` every file is
  the file of earlier versions, byte for byte.

Fenolite never writes poured copper: a pour is the result of Altium's rules and Altium's algorithm, and a
fill computed elsewhere would be shown as poured while disagreeing with what a repour gives. Clearance and
thermal reliefs of a polygon come from Altium's rules, not from the polygon. What KiCad's importer reads
of these items is checked by `tests/kicad/altium/test_pcb_complete_oracle.py` (`H-A-PCBX-KICAD`); that
Altium shows them is Part X of `docs/evidence/altium-pcb.md`, not yet reported, so every row is
`INFERRED`.
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

A script of 6 or 8 copper layers (`design.board(..., copper=6)`) is written with the stack of
"Complete board" below, which takes any even count: no count that `board()` accepts is refused, and no
record is added for it. When the board names no copper layer, the document's copper layers are those of
`Design.copper_layers`, `F.Cu`, `In1.Cu` … `In<copper − 2>.Cu`, `B.Cu`, so a plane, a zone or script
copper on `In4.Cu` of the script lies on a layer of the document.

`design.board(mm(50), mm(30), copper=4, planes={"In1.Cu": gnd})` makes `In1.Cu` an internal plane on
`GND`; a plane takes any inner layer of the count. A plane holds one net and no primitive: through vias and pads cross it, and Altium's default plane
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
- each footprint is the linked one, with the pad numbers and positions of the library footprint; a
  KiCad board stores the pads of a bottom footprint mirrored about the footprint's X axis
  (`docs/formats/kicad/board.md`, `H-G-BOTTOM-STORE`), so the mirror is undone before the comparison
  (c0142), whatever the footprint's rotation;
- every pad is on the net of the same name as the design puts its pin on;
- the outline's box is the design's;
- every net of the copper is a net of the design (`altium.copper-net-missing`).

A difference gives `altium.copper-board-mismatch` with the component, the pad or `outline` in `where`,
and the board's path in the message. **The board's placements win**: the copper is only right relative to
the footprints as the board places them, so every component is written where the board has it, and
`altium.placement-from-board` names the parts whose placement differs from the script's. Keep-outs,
texts, graphics and holes of the board are not copied (`altium.not-lowered`).

`result.copper` reports what was written: `source` (`none`, `model`, `script` or `board`), `from`,
`layers`, `planes`, `tracks`, `arcs`, `vias`, `zones` (polygons), `locked`, `net_classes` and
`placements_from_board`.

**Locks (change c0108).** A locked track, arc or via of the model, from any copper source, is written as
a locked primitive: bit 2 of the first flag byte of its record is clear (`docs/formats/altium/pcb-copper.md`,
"Locked flag of a free primitive"). `result.copper.locked` holds `tracks`, `arcs` and `vias`, the numbers
of items written locked, so the count can be checked against the board. The lock is written only for a
record kind whose fact row is on that page (`pcbrecords.LOCK_WRITTEN`; today the three kinds). For a kind
without its row, the items are written unlocked and the build gives one `altium.not-lowered` **warning**
with `where` `copper/locked` that names the kind and the count: a lock is never dropped in silence. The
Altium import reads the same bit back into `locked`. A design without locked copper gives the documents it
gave before. The lock is `INFERRED`: a public reader's statement and Fenolite's own reader; Altium
Designer's view is step X12 of `docs/evidence/altium-pcb.md`, which has not been run. A lock changes no
copper, and no rule of the document depends on it.

**Oracles.** `tests/kicad/altium/test_pcbdoc_copper_oracle.py` imports the routed sample and the plane
variant with `kicad-cli pcb import` and compares the copper and the layer types;
`test_copper_from_oracle.py` proves that copper copied with `--copper-from` equals the source board after
the way back. KiCad reads a plane of the stack as a `power` layer; it does not import the plane's net
or the net classes, and of the rules it shows only the clearance of the zones ("Rules").

## Rules (change c0084)

A build writes the rules of the script into `<name>.PcbDoc`, each as the Altium rule kind that carries
it, and names every rule it cannot write. A rule is written exactly or not at all: a rule that Altium
would read with another value or scope is worse than a missing one, because Altium's check would pass
a board that the script forbids.

| neutral kind | Altium rule | limits the rule must give | written |
|---|---|---|---|
| `clearance` | Clearance | `min` | yes |
| `track_width` | Width | `min`, `opt` and `max` | yes |
| `via_diameter` | Routing Via Style | `min`, `opt` and `max`, with a `via_drill` rule of the same selector | yes |
| `via_drill` | Routing Via Style | `min`, `opt` and `max`, with a `via_diameter` rule of the same selector | yes |
| `hole_size` | Hole Size | `min` and `max` | yes |
| `edge_clearance` | Board Outline Clearance | `min` | yes |
| `hole_to_hole` | Hole To Hole Clearance | `min` | yes |
| `annular_width` | Minimum Annular Ring | `min` | yes |
| `hole_clearance` | none | | no (`no-counterpart`) |
| `courtyard_clearance` | none (Component Clearance measures bodies, with a vertical clearance) | | no (`no-counterpart`) |
| `silk_clearance` | none (Altium splits it into two narrower rules) | | no (`no-counterpart`) |
| `creepage` | none (the record of Altium's Creepage Distance is in no public file) | | no (`no-counterpart`) |

- **Limits.** Altium's Width, Routing Via Style and Hole Size records hold every limit, so a rule must
  give them all: `design.rules.minimum(track_width=…)`, which gives a minimum only, is reported
  (`value-unsupported`); write `design.rules.rule("w", "track_width", min=…, opt=…, max=…)` to get a
  Width rule. A severity other than `error` is `value-unsupported` too: a rule record is enabled or not.
- **Scopes.** All objects, a net (`InNet('<net>')`), a net class (`InNetClass('<class>')`) and the
  conjunction of those (`… And …`); a `clearance` rule takes a second scope from `between`. A glob, a
  `ref`, `item_kind`, `or` or `not` selector and a rule with `layers` are `scope-unsupported`: that
  rule is reported and the others of its kind are written.
- **What is read and not written (change c0125).** The import of a PCB document also maps a Clearance
  record whose object matrix is blank or holds one value, a record of a clearance matrix between net
  classes (the entry for all classes and its cells), and two layer conditions: `ExistsOnLayer` of
  every copper layer of the board on both scopes gives a clearance rule with `layers`, and `OnMid` on
  a board without an internal signal layer applies to nothing (reason `no-layer`, no unread rule). A
  matrix of differing clearances, the option that ignores the pads of one footprint, a layer condition
  for some of the copper layers and every other scope function stay unmapped, each with its reason
  (`docs/formats/altium/rule-file.md`, "Clearance forms that map"). A build writes none of these
  forms: a rule with `layers` stays `scope-unsupported`.
- **Cells of a clearance matrix (change c0130).** A Clearance record whose matrix holds differing
  clearances gives its generic rule and one more clearance rule per cell, named
  `<rule>/<kind>-<kind>` with `item_kind` selectors (`track`, `pad`, `via`, `zone`), when the matrix is
  exact in those kinds. A matrix that tells an arc from a track or a through-hole pad from a surface
  pad stays unmapped, and its reason names the pairs. Cells for fills, regions, text and holes are
  kept in the rule's `altium` bag (`cells_not_lifted`). `fenolite check` reports
  `summary.clearance_cells` (`judged`, `unjudged`). Read only: a build writes no matrix.
- **Order.** Within one Altium kind the rules of the script come first, from the most governing to the
  least (priority 1, 2, … and then 0), with Altium priorities from 1. After them come the rules the
  build always wrote: one per net class that holds the value and Fenolite's `All` default ("Copper").
  A class rule or default whose scope a rule of the script holds is left out. So a board-wide rule of
  the script governs the classes, as it does in a KiCad build (`kicad.project.class-shadowed`).
- **Names.** `<Kind>`, `<Kind>_<class>`, `<Kind>_net_<net>`, with `_and_` for a conjunction and `_to_`
  before a second scope, so two builds give equal names and unique ids.
- **What is reported.** One `altium.not-lowered` warning per rule that is not written, with `where`
  `design-rules/<kind>` and a message that holds the rule's name, its selector and the reason
  (`no-counterpart`, `scope-unsupported`, `value-unsupported`, or `no-document` when the build plans no
  PCB document). `result.rules` holds `written` (`kind`, `selector`, `rule`: the Altium rule's name)
  and `not_lowered` (`kind`, `selector`, `reason`). The rules stay in `.fenolite/rules.json`, and
  `result.pcb` counts them under `rule`: those the document holds and those it does not ("Copper").
- **Stacks.** A rule record holds no layer and no layer count: the same records are written for every
  stack of "Copper" (2 to 32 layers, planes, blind and buried vias). A Routing Via Style rule is written
  with `VIASTYLE=Through Hole`, the value of every such record read, also in public documents whose rules
  select drill pairs. A rule for one layer or one drill pair is not written (`scope-unsupported`).
- **Script copper.** A script with copper intents is resolved through the KiCad build in memory
  ("Copper"), which judges the script's rules by KiCad's grammar: a `via_drill` rule with `opt`, which
  Routing Via Style needs, refuses that build. Such a script cannot hold a via style rule yet; a design
  without copper intents, or one built with `--copper-from`, can.
- **A rule file.** `fenolite export <KiCad project> --out DIR --altium-rul` writes the same rules as
  `<stem>.RUL` (`docs/exports.md`), which the PCB Rules editor imports into a board you keep.
- **Reading.** The same kinds are read from a PCB document and a rule file ("Reading Altium files");
  what Fenolite writes it reads back equal within 2 nm (`H-A-RULE-READBACK`,
  `tests/unit/lens/test_altium_rules.py`).
- **Evidence.** The constraints come from Altium's public documentation and the keys from public PCB
  documents (`docs/formats/altium/pcb-copper.md`, "Rule kinds lowered"); that Altium lists and applies
  the written rules is `INFERRED` until the author report, Part U of `docs/evidence/altium-pcb.md`.
  `kicad-cli pcb import` loads a document with all seven kinds and takes the zone clearance from the
  Clearance rule; it shows no other kind (`tests/kicad/altium/test_rules_oracle.py`).

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

## Output job

Change c0087. A build that writes a PCB document also writes `<name>.OutJob`, an output job that you run in
Altium (Fenolite runs no output and produces none of Altium's files). `--altium-outjob off` leaves it out.

| output | Altium type | source document | container |
|---|---|---|---|
| Gerber | `Gerber` | `<name>.PcbDoc` | `fab` (folder) |
| NC drill | `NC Drill` | `<name>.PcbDoc` | `fab` |
| pick and place | `Pick Place` | `<name>.PcbDoc` | `fab` |
| bill of materials | `BOM_PartType` | the project | `fab` |
| schematic print | `Schematic Print` | the project | `doc` (PDF) |
| PCB print | `PCB Print` | `<name>.PcbDoc` | `doc` |

- **The Gerber output holds its settings (change c0138).** Run in Altium Designer 26, the job of change
  c0087, which held no setting, produced every output but the Gerber files: a Gerber output without a
  settings record plots no layer. The Gerber output now carries the complete record of 44 fields that the
  public saved jobs hold (`docs/formats/altium/output-job.md`, "The Gerber settings record"), and every
  output carries the key `OutputDefault<i>=0`, as every saved output does. The record is written whole or
  the job is not written. **Altium has not opened such a job yet** (Part O, "Session 2", of
  `docs/evidence/altium-schematic.md`).
  - *Unit and decimals.* Millimetres. The decimals are `gerbers.precision` of the preset you give with
    `--altium-outjob-preset FILE` (5 or 6), and 4 without one. Millimetres with 4 decimals is the one pair a
    public job holds; whether Altium takes 5 or 6 beside millimetres is not known yet, so read the setup of
    the output after a build with a preset. The KiCad export without the key uses KiCad's own default, so
    the two targets can differ here.
  - *What is plotted.* The layers of the board and no other, in this order: Top Overlay, Top Paste, Top
    Solder; the copper layers from top to bottom, an internal plane at its place; Bottom Solder, Bottom
    Paste, Bottom Overlay; Mechanical 13, 14, 15 and 16 (fabrication and courtyard drawings of both sides).
    `result.outjob.gerber.layers` lists them by id and name. The KiCad export plots none of the four
    mechanical layers; turn them off in the setup of the output if your fabricator does not want them. The
    preset's `gerbers.layers` does not choose the plotted layers (it holds KiCad layer names) and stays in
    `result.outjob.defaults`.
  - **What is not plotted: the board outline.** The Gerber set of the written job holds no outline file.
    The PCB document holds the outline as the board shape and on no layer, and no public file shows how a
    saved job names the board shape among its plotted layers. `result.outjob.gerber.outline` says so
    (`plotted: false` and the reason). Before you send the set to a fabricator, open the setup of the
    Gerber output in Altium, turn on the board outline in its layer list, and save the job (the next build
    then refuses the edited job unless `--discard-layout` is given).
  - **Not plotted either:** a drill drawing, a drill guide and the pad master plots; the record asks for
    none of them.
- **Every other output has Altium's default settings.** NC drill, pick and place, the bill of materials
  and the two prints hold no settings record: they ran with Altium's defaults in Altium Designer 26, and
  their public records are larger and less regular than the Gerber record. Open the setup of each in Altium
  and set what your fabricator needs. `result.outjob.defaults` lists the options your preset sets that the
  job does not carry (`drill.units`, `gerbers.layers`, …), which are the ones to carry over by hand.
- **There is no assembly drawing.** No public file gives its output type, so the sixth output is a PCB
  print of the board. The job has no STEP and no ODB++ output either: it holds the kinds that
  `fenolite export` has, a bill of materials and the two prints.
- **The containers have no path.** They are named `fab` and `doc`; where Altium writes them is its default
  until you set the output path of each container.
- A new project file lists the job after the PCB document. A project file that exists and lists the job
  is kept as always. **A project file that exists and does not list the job is written again with the job
  listed when it is still as a build wrote it** (change c0138): its bytes are those that the folder's
  `.fenolite/build.json` records. This is the folder that a build of 0.2.x leaves, or a build with
  `--altium-outjob off`. The file is written as a build into an empty folder writes it, the old one is kept
  as `<name>.PrjPcb.bak`, and `result.files` lists it in place of `result.kept`. A project file that was
  changed since (Altium saves it when a document is added, or you edited it), or that the record does not
  know, is kept, whatever `--discard-layout`: the build says so with `altium.outjob-not-listed`, and you add
  the job in Altium (Project » Add Existing to Project) or delete the project file and build again.
- **A kept project file that is still as a build wrote it stays in the record** (change c0138): a rebuild
  that keeps it, because it lists everything or because the job is off, writes its digest into
  `.fenolite/build.json` again, so a later build with the job still adds the job to it. A project file that
  is kept because it was changed, or that had no record, is not recorded: the build never turns an edited
  file into one "as built". One kind of folder stays outside this: a folder that a development build
  before this change rebuilt once has a record without the project file, and nothing can tell that file
  from an edited one; there the build keeps it and tells you how to list the job.
- **The notes about a kept project file name only what it lacks** (change c0138). The build reads the kept
  file with its own project reader: `altium.pcb-not-in-project`, `altium.schlib-not-in-project`,
  `altium.sheets-not-in-project` and `altium.outjob-not-listed` are given only for documents the file does
  not list, and a kept file that lists everything gets `altium.project-kept` alone. A kept file that
  cannot be read gets the notes for every document, and their hint says so.
- An output job that you changed in Altium is an edited output: the next build refuses it unless
  `--discard-layout` is given.
- `backends.altium.outjob.write_outjob(groups)` writes any groups, containers and outputs that the reader
  `read_outjob` returns, and `from_preset(preset, name=…, copper=…)` gives the job above for a board with
  the given copper stack. `write_outjob` refuses a Gerber output without the complete record and a setting
  on any other output. `read_outjob` gives the settings of an output (`JobOutput.settings`) and
  `record_fields` the fields of a record. What is confirmed is own readback only (`H-A-OUTJOB-READBACK`,
  `H-A-OUTJOB-GERBER-READBACK`) and that the record has the form of two public jobs: whether Altium opens
  the job, takes the record and generates the outputs is Part O of `docs/evidence/altium-schematic.md`,
  not reported yet.
- **Every written `.OutJob` differs from the one a build before change c0138 wrote.** No release wrote a
  job (0.2.x writes none), so this is about folders built from the development branch. A rebuild into such
  a folder **replaces the job and keeps the old one as `<name>.OutJob.bak`**, as for every other file the
  build wrote: the folder's `.fenolite/build.json` records the digest of the job it wrote, so the build knows
  the file as its own. The build refuses instead (exit 7, `FEN-7001`, nothing written) in two cases: the job
  was edited since that build, or the folder's `.fenolite/` record is gone, so that the build cannot tell
  its own old job from an edited one. The hint names both ways out: `--discard-layout` replaces the job
  (the backup is kept), or build into another `--out` folder. A folder built by 0.2.x holds no job: the
  build adds one and lists it in the project file, which it writes again (see above).
  Measured with real builds on 2026-10-07 (change c0138, design, "Found on 2026-10-07").

## Drawing sheet

Change c0087. When the script names a drawing sheet, `design.sheet("A4", drawing_sheet="frames/x.sheet.toml")`
(a `*.sheet.toml` specification or a `.kicad_wks` file beside the script, as for KiCad), the build draws it
on every schematic document, and the fields of `design.title_block(…)` become sheet parameters, so the
title block shows them.

- **The sheet is a custom sheet of the paper's exact size**, A4 landscape being 297 mm by 210 mm, with the
  built-in border and title block off. The frame, the reference zones and the title block are drawn lines
  and texts, the same that the KiCad drawing sheet of the specification has. No template file is linked: the
  project needs no path to one.
- **Sheet parameters.** `Title`, `Revision`, `Date`, `Organization`, `DocumentNumber`, `DrawnBy` and
  `ApprovedBy` for the fields that are not empty, `SheetNumber` and `SheetTotal` (the position of the
  document among the schematic documents and their count), and each variable under its own name. The texts
  of the title block are special strings (`=Title`, …) that Altium fills from them. A variable with the name
  of one of these parameters, or a value outside printable 7-bit ASCII, is the error `altium.text-unwritable`.
- **The paper.** The page is the paper and the orientation of `sheet()` when the layout of the document
  fits it. When it does not, the page is the smallest of A4 to A0 that holds the layout (or the layout's own
  area past A0) and the build warns with `altium.sheet-paper`. `result.drawing_sheet.pages` names the page
  of every document.
- **The layout does not know the title block.** Components are laid out from the top-left corner as
  before; on a sheet that is nearly full they can lie under a title block in the bottom-right corner. Name
  a larger paper, or use `--altium-sheets modules`.
- **Losses.** A logo (a bitmap of the sheet), a text that mixes a token with other text, a text outside
  printable 7-bit ASCII, a rotation that is not a quarter turn and a length limit of a text cannot be
  carried: each gives an `altium.sheet.*` warning and the build is refused with `FEN-7001` unless
  `--allow-lossy` is given, which leaves the item out or writes it without the style. Line widths become the
  nearest of 4, 10, 20 and 40 mil and text heights whole points (the info `altium.sheet.rounded`); texts
  are black, in the schematic's one font.
- A script without a drawing sheet gives the schematic it gave before, byte for byte; `sheet()` and
  `title_block()` alone change nothing in an Altium build.
- `fenolite template build SPEC --target altium --out FILE.SchDot` writes the same sheet as a standalone
  template (`docs/sheet-templates.md`, "Building an Altium sheet template").
- Confirmed is own readback only (`H-A-SCHDOT-READBACK`): `import_sheet` reads the frame of a built
  schematic back to the lines and texts of the specification. That Altium draws it as KiCad does and fills
  the strings is Part W of `docs/evidence/altium-schematic.md`, not reported yet.

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
| `altium.text-unwritable` | error | a written text is not printable 7-bit ASCII (a comment of a binary schematic may also hold Windows-1252 characters), holds `\|`, is empty, has a leading or trailing space, or is a value that starts with `=` |
| `altium.name-case-collision` | error | two net names, or two refs, differ only in letter case |
| `altium.unique-id-collision` | error | two components, sheet symbols or ports get the same unique id |
| `altium.schematic-too-large` | error | the binary schematic needs more than 109 FAT sectors (about 7 MB); never with `--altium-format ascii` |
| `altium.library-too-large` | error | a schematic library needs more than 109 FAT sectors |
| `altium.unknown-pin` | error | a net member names neither a pin number nor a pin name of a resolved symbol |
| `altium.pin-pad-map-invalid` | error | a `pad_map` names a pin the symbol lacks, names a pad the resolved footprint lacks, or leaves one pad to two pins, one of them by its own number (changes c0135 and c0123); for a pad of two pins the model's `model.pin-pad-map` is reported beside it |
| `altium.symbol-off-grid` | error | a pin position or length of a resolved symbol is not a multiple of 10 mil |
| `altium.pin-text-too-long` | error | a pin name or number is longer than 255 bytes |
| `altium.symbol-name-collision` | error | two lib ids give one library and one storage name, or two library file names differ only in letter case |
| `altium.no-footprint` | warning | a part names no footprint |
| `altium.sheet-custom` | warning | the layout does not fit A0, so a custom sheet is written |
| `altium.pin-lossy` | warning | a pin's electrical type or shape has no Altium equivalent and is mapped |
| `altium.generic-symbols` | info | components of Altium links got generic bodies |
| `altium.symbol-simplified` | info | a resolved symbol is drawn as rectangles (`--altium-symbols generic`, no graphics, a graphic without a record, several units or body styles), or other body styles or alternates were dropped |
| `altium.bus-flattened` | info | a bus of the design is drawn as its nets; the message says why |
| `altium.section-key` | info | a lib ref longer than 31 characters is stored under a section key |
| `altium.schlib-generic` | info | a library is written with generic symbols |
| `altium.schlib-not-in-project` | info | the project file is kept, so the libraries are not listed in it |
| `altium.not-lowered` | info | the board, placements, the rule values of the net classes (their nets are declared in the schematic), diff pairs, typed interfaces (`i2c`, `spi`, `uart`, `usb2`) or harnesses are kept in the model only (without a PCB document); as a **warning**, one per rule of the script that is not written into the PCB document (`where` = `design-rules/<kind>`, with the selector and the reason: "Rules"); a board's keep-outs, texts, graphics and holes without a PCB document, and with one each item that has no record (`where` = `<kind>/<id>`: a text, graphic, keep-out, hole or component body; `stackup` for a stack that is not written); a stack-up that does not fit; items of a copper source that are not copied |
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
| `altium.outjob-not-listed` | info | the project file is kept and does not list the output job |
| `altium.sheet-paper` | warning | the layout of a schematic document does not fit the paper of `sheet()`, so the drawing sheet is drawn on a larger page |

Model findings (`model.*`) pass through, and so do the `altium.sheet.*` codes of a drawing sheet ("Drawing sheet"). A build with an error exits 5 and writes nothing. A KiCad lib id
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

## Reading Altium schematics

Change c0040 reads Altium schematics and schematic libraries back. It is a library API only: no command, no
registered backend, and `fenolite capabilities` does not change.

```python
from fenolite.backends.altium.read import sch, schlib

document = sch.read_schematic(data, file="top.SchDoc")  # .SchDoc or .SchDot, binary or ASCII
library = schlib.read_schlib(data, file="parts.SchLib")
sch.detect(data)  # "ascii", "binary", "library" or None
sch.check_identity(document)  # () when every stream is rebuilt exactly
```

- **Bytes in, frozen records out.** Both readers take the file's bytes and open nothing. File names held by
  records (images, templates, sheet files, model files) are returned as text and never resolved; embedded
  files are decompressed only by `EmbeddedFile.data(limit)`, capped at 64 MiB. `codepage=` takes another
  single-byte code page (default `cp1252`); `issues=` collects the findings, which the result also keeps.
- **`SchDocument`.** `header`, `records` (the records of `FileHeader`, or of the ASCII file's first section),
  `additional` (the `Additional` stream), `storage_header` and `embedded`, `streams` (the bytes read),
  `extra_streams`, `roots`. Typed access: `components()`, `wires()`, `buses()`, `net_labels()`,
  `power_ports()`, `ports()`, `junctions()`, `no_ercs()`, `sheet_symbols()`, `harnesses()`, `templates()`,
  `template_children()`, `of_type(cls)`; the owner tree through `get(ref)`, `owner_of`, `children_of(record,
  part=, mode=)`, `shown_children(component)` and `walk(record)`.
- **`SchLibrary`.** `header`, `header_tail`, `listed_names`, `fonts`, `section_keys`, `components` (one
  `SchLibComponent` per storage, in the header's order) and `get(lib_ref)`. A component has `name`,
  `storage_name`, `records`, `component`, `pins`, `children(part=, mode=)`, `parts`, `modes`, `side_streams`
  and `extra_streams`. `PinFrac` is decoded (`SIDE_STREAMS_DECODED`); the other side streams are kept as bytes.
- **Records.** One class per record id of the closed table `RECORD_TYPES` (43 ids, the record page
  `docs/formats/altium/schematic-records.md`); any other record is an `UnknownRecord`. Every record keeps its
  `payload` and `props` (`PropertyList`: fields in file order, keys as written, raw values); typed attributes
  are views of them, and `unknown_keys` lists what a class does not model. Lengths are `SchLength`: an exact
  integer count of 1/100 000 of the 10-mil unit, with `nm()` (rounded half to even) and `exact`. Coordinates are
  in the file's frame, Y upwards.
- **What is kept.** Unknown keys, unknown records, a binary pin's trailing bytes (`Pin.tail`), opaque embedded
  files, side streams, the bytes after the library header, unread streams and ASCII sections. Nothing is
  normalised: letter case, key order, spaces, line ends and number formats stay as read.
- **What is not done.** No net, connection or model entity is computed (change c0043); parts and display
  modes are exposed, not chosen; the reader writes nothing.

Fatal errors are few (neither form, no `FileHeader`, a wrong header text, a cut frame, a broken container)
and raise `FormatError` with `file`, `locator` and `offset`. Everything else is an issue:

| code | severity | when |
|---|---|---|
| `altium.sch.malformed-record` | warning | a property list without its final NUL, a record without an integer `RECORD`, a binary pin cut inside a required field |
| `altium.sch.bad-value` | warning | a modelled key whose value does not parse, or a count that disagrees with the keys present |
| `altium.sch.unknown-record` | info | a record id with no class (once per id, with the count) |
| `altium.sch.unknown-stream` | info | a stream or ASCII section the reader keeps without reading |
| `altium.sch.empty-stream` | warning | an `Additional` or `Data` stream of 0 bytes |
| `altium.sch.weight-mismatch` | warning | `WEIGHT` or `COMPCOUNT` differs from what was read |
| `altium.sch.orphan-record` | warning | an `OWNERINDEX` that names no earlier record |
| `altium.sch.no-sheet` | warning | record 0 of a schematic is not the sheet |
| `altium.sch.part-out-of-range` | warning | a child outside its component's part or display-mode count |
| `altium.sch.text-undecodable` | warning | a byte the decoding does not define (the text view shows U+FFFD) |
| `altium.sch.pin-trailing-bytes` | info | bytes after a binary pin's last known field |
| `altium.sch.storage-opaque` | info | a `Storage` record without the embedded-file layout |
| `altium.schlib.unlisted-component` | info | a component storage the header does not list |
| `altium.schlib.missing-component` | warning | a listed lib ref without a storage |
| `altium.schlib.no-component` | warning | a `Data` stream whose record 0 is not the component |
| `altium.schlib.side-stream-opaque` | info | a pin side stream kept and not decoded |
| `altium.schlib.side-stream-orphan` | warning | a side-stream entry that names no pin |

Evidence: `read.sch.EVIDENCE` is the lowest level of the `H-A-RD-SCH-*` rows of `docs/hypotheses.md`; the
corpus census and the library oracle are in `docs/evidence/altium-read-schematic.md`.

## Importing a sheet template

Change c0046 imports an Altium sheet template (`.SchDot`, or the template graphics that a record 39 owns in
a `.SchDoc`) into the neutral drawing sheet, on top of the schematic reader:

```
fenolite template import SRC --target kicad --out OUT --dry-run
```

`fenolite.backends.altium.read.sheet.import_sheet(data)` returns a `SheetImport`: the `DrawingSheet`, the
`source` (form, style, paper, orientation, drawing area), the `issues`, the record counts `imported` and
`reported`, the special `strings` with their neutral texts and the names of the sheet-level `parameters`.
The size, lines, rectangles, texts, special strings and embedded PNG images are imported; everything else is
reported with its record number under one of twelve `altium.sheet.*` codes, and a loss needs
`--allow-lossy`. Nothing is written back to Altium: writing a `.SchDot` is a later roadmap item. The user
guide is `docs/sheet-templates.md`, "Importing an Altium sheet template"; the facts are in
`docs/formats/altium/sheet-template.md` (`H-A-RD-SHT-*`, all `INFERRED`).

## Reading PCB files

Change c0041 reads PCB documents and libraries that Altium Designer saved, and every file Fenolite
writes, into typed records. It reads; it writes nothing and runs no subprocess. Import into the model is
change c0043.

- `fenolite.backends.altium.read.pcb.read_pcbdoc(source, *, file="", strict=False)` returns a
  `PcbDocument`; `fenolite.backends.altium.read.pcblib.read_pcblib(source, *, file="", strict=False)` a
  `PcbLibrary`. `source` is the file's bytes or a `CompoundFile` of `read.cfb`; `read.pcb.detect_pcb`
  tells `"pcbdoc"`, `"pcblib"` or `None`. Only the binary form is read: other bytes raise `PcbReadError`
  (a `FormatError`), and a container error of `read.cfb` passes unchanged.
- **Records.** `read.pcbprims` gives `TrackRecord`, `ArcRecord`, `ViaRecord`, `FillRecord`, `PadRecord`,
  `TextRecord`, `RegionRecord` (with `RegionVertex`) and `RawPrimitive` (component bodies, and records
  shorter than the reader's minimum), each with the common `Prefix`. `read.pcbstack.BoardRecord` gives
  the outline, the numbered layers with `copper_chain`, the physical `stack`, `plane_nets` and
  `layer_pairs`. `read.pcb` adds `NetRecord`, `ComponentRecord`, `ClassRecord`, `PolygonRecord` and
  `RuleRecord` (rules stay opaque: every key in `fields`); `read.pcblib` gives `LibFootprint`.
  `PcbDocument.net_name`, `primitives_of` and `regions_of` join records by index.
- **Units.** Lengths stay integers of 1/10 000 mil and angles the stored doubles; `pcbprims.to_nm`
  (half to even, as `fenolite.core.units.u_to_nm`) and `to_nm_exact` convert.
- **Lossless.** Every record keeps its bytes in `raw`; typed fields are views, the bytes after the known
  fields are `tail`, and unknown keys keep their order and duplicates. `PcbDocument.rebuild(storage)` and
  `LibFootprint.rebuild()` join the records' bytes and the trailing bytes into the stream again; every
  other stream is returned unchanged in `storages`.
- **Lengths.** A subrecord at or above its minimum is typed whatever its length; the lengths seen in the
  corpus are listed in `docs/formats/altium/pcb-read.md`.

Problems are `Issue` values whose `where` is `<storage>/<stream>`, then `#<record>` and `@<byte offset>`;
messages hold no value of the file. `strict=True` raises `PcbReadError` at the first error.

| code | severity | meaning |
|---|---|---|
| `altium.pcb-read.truncated` | error | a block or subrecord runs past the end; the rest of the stream is kept as `trailing` |
| `altium.pcb-read.unknown-type` | error | a type byte that is no primitive type; the stream stops there |
| `altium.pcb-read.missing-stream` | error | a footprint listed in `Library/Data` has no storage |
| `altium.pcb-read.bad-stack` | error | the copper chain links to a layer without a name, or loops |
| `altium.pcb-read.short-record` | warning | a subrecord below the minimum; the record is a `RawPrimitive` |
| `altium.pcb-read.count-mismatch` | warning | a `Header` count differs from the records read |
| `altium.pcb-read.bad-index` | warning | records of a storage name a net, component or polygon that does not exist |
| `altium.pcb-read.wrong-type` | warning | a record of another type in a primitive storage; it is in `others` |
| `altium.pcb-read.bad-frame` | warning | a name list, `SectionKeys` or wide-string table does not parse |
| `altium.pcb-read.bad-value` | warning | a typed key whose text does not parse; the view is `None` |
| `altium.pcb-read.unlisted-footprint` | info | a footprint storage that `Library/Data` does not list; it is read too |

Evidence: the framing, the identity of every typed stream, the lengths, regions, wide strings, rule
framing and text encoding are `CORPUS-VERIFIED` on eleven public files saved between 2016 and 2025
(`docs/evidence/altium-pcb-read.md`); nets, footprints, pads, vias, copper tracks and the copper chain
are `ORACLE-VERIFIED(kicad-cli)` against `kicad-cli pcb import` and `fp upgrade` 10.0.6. Each typed
field has its own level in `read.pcbprims.FIELD_LEVELS`, the label of its row of the fact page;
`PcbDocument.evidence` and `PcbLibrary.evidence` are `CORPUS-VERIFIED`.

## Reading Altium files

The registered backend `altium` (`fenolite.backends.altium.backend.AltiumBackend`, change c0043) reads
Altium files into the neutral model. `fenolite capabilities` lists it in `result.backends`, before `kicad`.
It reads; it writes nothing: the writers above stay experimental features of `build`. The commands
`inspect`, `check` and `diff` take Altium files (change c0044): see "Round trips" below and
`docs/cli-contract.md`, sections "inspect", "check" and "diff".

```python
from pathlib import Path
from fenolite.backends import registry

backend = registry.for_path(Path("board.PcbDoc"))  # the Altium backend, by the file's suffix
result = backend.read(Path("design.PrjPcb"))
design = result.design  # a Design; result.issues lists what was found
```

| read kind | file | result |
|---|---|---|
| `altium_pcbdoc` | `.PcbDoc` | a `Design` with the board, a circuit synthesised from the pads (one component per footprint, one pin per pad name, pin type `unspecified`) and the rules that map |
| `altium_schdoc_binary`, `altium_schdoc_ascii` | `.SchDoc` | a `Design` with the circuit of that one sheet and no board |
| `altium_prjpcb` | `.PrjPcb` | a `Design` with the circuit of the listed sheets and the board of the first PCB document, linked |
| `altium_pcblib` | `.PcbLib` | a `Library` of footprint definitions |
| `altium_schlib` | `.SchLib` | a `Library` of symbol definitions |

**What a board read gives.** Copper layers named by their position in the stack (`F.Cu`, `In<j>.Cu`,
`B.Cu`), the stack-up, nets and net classes, one footprint per component with its pads in the footprint
frame, tracks, arcs, vias, zones from polygon pours (with their poured copper as fills), the outline as
graphics on `Edge.Cuts`, free graphics and texts, component bodies (height, standoff, outline), and the
rules of the kinds Clearance, Width, Routing Via Style and Hole Size when they map exactly. Lengths are
integer nanometres; the model's Y axis points down, so Y is negated; no origin is subtracted.

**What a schematic read gives.** A sheet stores no netlist. The import derives the nets from wires,
junctions, pin ends, net labels, power ports, ports, sheet entries, buses and signal harnesses, by the rules
of `docs/formats/altium/connectivity.md`, and joins sheets by the project's net identifier scope
(Automatic chooses hierarchical, flat or global as Altium documents it). It gives components with their
pins and pin types, nets with their names and aliases, one module per sheet symbol, one interface per
harness, buses, and the pins that a No ERC directive leaves open.

**What a project read does.** It reads the sheets and the first PCB document that the project file lists
inside the project folder. A footprint links to its schematic component by the unique-id path
(`SOURCEUNIQUEID`), else by its designator; a PCB net links to the schematic net of the same name. Neither
side is corrected by the other: a pad keeps the net the PCB document gives it. A component or a net that
only the PCB document holds is added to the circuit and reported. A document outside the folder, a missing
one or an unreadable one is skipped with `altium.import.document-skipped`.

**Channels.** A sheet that several sheet symbols name is read once per symbol, and the sheet of a sheet
symbol whose designator is `Repeat(NAME, first, last)` once per index; each instance is a
channel with its own components and nets (`altium.import.channels`, info). Its components are named, in
this order: by the PCB document of the project, whose components link to them by their unique-id path
and hold the designators the project was annotated to; else by the project's designator format
(`ChannelDesignatorFormatString` with `ChannelRoomNamingStyle`), for example `D9_3` for `D9` in the
channel `3` under `$Component_$RoomName`. A format the import does not resolve gives
`<designator>@<channel>` and `altium.import.channel-naming`. Sheets read without their project file keep
the designators of the sheet. The facts are in `docs/formats/altium/connectivity.md`, "Channels".

- **`Repeat` statements.** The channel `i` of `Repeat(CH, 1, 2)` is the module `CH[i]`; its components are
  named by the format, where `$ChannelIndex` is `i`, `$ChannelAlpha` its letter (`A` for 1 to `Z` for 26),
  `$ChannelPrefix` is `CH` and the room is `CH1` or `CHA` by the style. No public file holds such a
  statement: this part rests on Altium's documentation and on authored sheets (`INFERRED`).
- **Nets of a channel.** A net that the sheet does not export is one net per channel: a net label is renamed
  by the designator format (`MID_CH1`), and a net without an identifier takes the system name of the
  channel's designator (`NetD9_11_A`). A sheet entry `Repeat(NAME)` gives channel `i` the member `i` of the
  parent's bus `NAME`; any other sheet entry is one net for all channels.
- **The board of a `Repeat` project.** The unique-id path of a board component of a `Repeat` channel has no
  recorded form, so such a component links by designator only (the board's designator equal to the
  channel's); what does not link is counted by `altium.import.channel-naming`.
- **Not instantiated.** A statement of another form, with its first index above its last, or that would
  bring the project above 256 sheet instances gives one instance and `altium.import.repeated-sheet`.

**Pin-to-pad map.** A component whose footprint model maps a pin to a pad of another name carries the pair
in `pin_pad_map`, and `netlist.assignment_compare` and level 2 of `fenolite equivalent` name the pin by
that pad (`JP6-VBUS`, not `JP6-1`); the nets of the circuit stay keyed by pin number. A pin whose map
lists several pads is bonded to each of them (change c0123): the map holds one pair per pad, in the order
of the record, and the comparisons name every pad. An Altium build writes the map back the way Altium
saves it: a map record of the footprint model for each pin whose pads are not the pad of its own
designator, and none for the other pins. This holds for Fenolite's own builds: a project built from a
script with a `pad_map` holds the map in its schematic and the nets on the mapped pads of its PCB
document, and `fenolite check` on it compares the two through the map and reports no
`netlist.assignment-differs` for the mapped pins (the release 0.2.1, whose import leaves the map
records out of the model, reports it). The library of a built project holds the map only when every
part of the symbol links the footprint the symbol names. The model gives a pad one pin: a pad that another pin
holds gives no pair, and a pin mapped to no pad keeps its designator; each such record is kept in the
component's `altium` bag (`pin_pads`) and counted by `altium.import.pin-map`.

**What is not imported.** Nothing is dropped silently: `altium.import.unmapped` counts every record that
gave no model entity.

- Schematic drawings (the model holds no schematic presentation), sheet templates, variants, differential
  pairs and the annotation file of a project (the form of a non-empty one is not known from a public
  source).
- Graphics, texts and regions of placed footprints; zone settings; split planes; per-layer via stacks; mask
  and paste layers of pads (their modes and expansions are in the pad's `altium` bag); 3D model data.
- Rules of other kinds, disabled rules, Clearance rules with a matrix of differing clearances, and rules
  whose scope is outside the mapper's grammar or names a kind of layer the board lacks (`no-layer`):
  `altium.import.rule-unmapped` counts them per kind and reason. No rule is approximated.
- A copper fill or region with a net is a graphic with the net's name in its bag: the model has no copper
  shape with a net.
- What is drawn on an internal plane. A plane layer (Internal Plane 1 to 16) is stored in negative: the
  layer is copper, and a line, an arc, a fill, a region or a text on it is a place without copper (the
  line that splits a plane, a blow-out). Such an object is no track and no drawing of the imported board,
  with or without a net: the census counts it as `plane-cuts`, and the layer of the plane holds the count
  in its `altium` bag (`plane_cuts`). The plane's own copper is not in the model either: the layer is a
  copper layer with its net in the bag (`plane_net`), and no zone is made for it. An imported board with
  planes therefore shows less copper than the fabricated board has, and the copper check says so
  (`copper.item-unsupported` at `plane`).
- A pad that the footprint model maps to two pins, and a pin that it maps to no pad: the model gives a
  pad one pin and a pin at least one pad, so the record stays in the bag (`pin_pads`).

The issue codes `altium.import.*` are listed in `docs/cli-contract.md`, "Altium import". An error issue
never stops an import.

**Evidence.** Three kinds, none of which needs Altium Designer:

- *Own files.* Every example that Fenolite builds for the Altium target imports to the nets, no-connect
  marks, references, values and footprint names of its model, in both schematic forms
  (`tests/unit/backends/altium/adapter/test_own_files.py`). This is `INFERRED`: Fenolite reads what
  Fenolite wrote.
- *Public project sets.* On public projects saved by Altium Designer, the netlist computed from the sheets
  equals the pad netlist of the project's PCB document (`tests/corpus/test_altium_import.py`; results in
  `docs/formats/altium/connectivity.md`, "Result per project set").
- *KiCad's importer.* The board import agrees with `kicad-cli pcb import --format altium` 10.0 on copper
  layers, footprint sides, rotations and positions, pad nets and positions, vias, tracks and zone outlines
  (`tests/kicad/altium/test_import_oracle.py`; differences by kind in `docs/formats/altium/import.md`).

The backend's report and every read stay `INFERRED` while any `H-A-IMP-*` row of `docs/hypotheses.md` is
(the lowest wins).

## Round trips

Four levels say how far a reading, a build or a rewrite of Altium files can be trusted (changes c0044
and c0090). They are
Fenolite's own measures: no level says that Altium Designer opens a file. Results on the public corpus
and on the example builds are in `docs/evidence/altium-roundtrip.md`.

| level | what is done | what it proves | what it does not prove |
|---|---|---|---|
| RT-A0 | a compound file is read, written again by Fenolite's compound writer and read again | no storage and no stream is lost or changed by a copy, byte for byte | nothing about the meaning of a stream; the sector layout, CLSIDs and times are not compared |
| RT-A1 | every stream the reader types is encoded from its records and read again | the records of every stream survive a decode and an encode: key spelling, key order, raw values and kept bytes | that the records mean what Fenolite reads into the model |
| RT-A2 | the model a build stored in `.fenolite/` is compared with the reading of the documents the build wrote | the writers and the import agree on the circuit and on the board that was written (footprints, pads, tracks, arcs, vias, zones, net classes), within 2 nm | that Altium reads the files (one tool writes and reads), and any field outside the scope below |
| RT-A3 | a document is read, its model is written as new documents, and those are read again | the write of a model and the import agree on everything the write carries of a document that Altium saved, within 2 nm; what the write leaves out is counted per kind | that Altium opens the rewrite, and anything in the counts: a rewrite is not a copy of the document |

**A level that is not judged** is neither a pass nor a failure. The reasons:

- `not-a-container` (RT-A0): the file is text (an ASCII schematic or a project file).
- `too-large` (RT-A0): the file needs DIFAT sectors, which the compound writer does not write. RT-A1
  still judges its records.
- `writer-refused` (RT-A0): the compound writer refuses the tree (an empty storage, or a name it does
  not write).
- `native-input` (RT-A2): the files were not written by a Fenolite build. RT-A2 compares a stored model
  with its documents, so it is judged on Fenolite's own builds only; the level of any other file is
  RT-A3.
- `model-predates-board` (RT-A2): the project was built before change c0090, so its stored model holds
  no footprint while its PCB document holds some. Build it again.
- `model-predates-graphics` (RT-A2): the project was built before change c0126, so its stored footprints
  hold no graphic while its PCB document draws some. Build it again.
- `no-document` (RT-A3): the write gave no document of the kind that was read. This happens for a
  project whose circuit the schematic writer refuses (one pin on two nets, a text that no record
  holds); the PCB document is still written, and the stage's `written` and `unwritten` count it.

**Commands.** `fenolite check PATH` reports the levels as the stages `roundtrip.rta0`, `roundtrip.rta1`
and `roundtrip.rta2` (`docs/cli-contract.md`, "check"), and `roundtrip.rta3` when `--stages` names it;
`fenolite roundtrip PATH --level rta0|rta1|rta2|rta3` runs one of them and says whether it holds;
`fenolite inspect FILE` gives the counts of RT-A1
for one file (`opaque_count`, `streams`); `fenolite diff A B --view records` lists the records that
differ between two Altium files of one kind.

### The scope of RT-A2

RT-A2 compares the fields that the writers write (`roundtrip.RT_A2_SCOPE`). A length is written in
units of 2.54 nm, so two lengths within 2 nm are equal; angles are written with six decimals of a
degree and must be equal. The circuit kinds (`component`, `net`, `no_connect`) are compared with the
reading of the schematic documents, and every other kind with the reading of the PCB document.

| kind | compared | with |
|---|---|---|
| `component` | `ref`, `value`, `pin_pad_map` | schematic |
| `net` | `name`, `members` | schematic |
| `no_connect` | the marked pins | schematic |
| `netclass` | `name` | PCB document |
| `footprint` | `position`, `rotation`, `side` | PCB document |
| `pad` | `number`, `net_id`, `position`, `size`, `corner_ratio` | PCB document |
| `footprint_graphic` | `kind`, `layer`, `points`, `width`, `filled` | PCB document |
| `track` | `start`, `end`, `width`, `layer`, `net_id`, `locked` | PCB document |
| `arc` | `start`, `mid`, `end`, `width`, `layer`, `net_id`, `locked` | PCB document |
| `via` | `position`, `diameter`, `drill`, `net_id`, `locked` | PCB document |
| `zone` | `outline`, `layers`, `net_id` | PCB document |

**The built model holds the board that was written** (change c0090). A build that writes a PCB document
stores, in `.fenolite/board.json`, one footprint per placed component with the pads that the document
holds, and the tracks, arcs, vias and zones of the document (a zone on two layers is two zones, one per
written polygon). So every kind of the scope is compared and none is only counted: a track that only
the document holds is a difference. The document lies in its own frame (the outline's lower-left corner
at 1000 mil, 1000 mil), and the stage moves its reading back into the frame of the script by the corner
of the outline, which is exact. Rules are not in the scope: the document also holds the rules that the
writer derives from the net classes and from its defaults, which are no rule of the model. A project
that was built before this change is skipped with `model-predates-board`.

**Footprint graphics and corner ratios** (change c0126). The stored footprints also hold the graphics
that the document draws for each component, in the pad frame and in the written form (a rectangle is its
four lines, a circle and an arc the points that the import reads back from the written record), and a
rounded pad holds its corner ratio, 5 000 ppm per written percent. The kind `footprint_graphic` and the
pad's `corner_ratio` are compared; the points of an arc graphic follow the rule of a copper arc (c0127):
three points within 2 nm. When the model was not read from Altium, the stage names the graphics that the
reading holds on Mechanical 13 to 16 `F.Fab`, `B.Fab`, `F.CrtYd` and `B.CrtYd`, the layers Fenolite writes
there. A project built before this change, whose stored footprints hold no graphic while its document
draws some, is skipped with `model-predates-graphics`.

Fields of these kinds that the scope leaves out, and why:

| kind | field | reason |
|---|---|---|
| `component` | `dnp` | the writer does not write it |
| `component` | `lib_symbol_ref` | the writer writes a fixed value: the name of the generated schematic library for a KiCad lib id |
| `component` | `lib_footprint_ref` | the writer writes a fixed value: the name of the generated PCB library for a KiCad footprint link |
| `component` | `properties` | the writer does not write it (only the comment and the footprint link are parameters) |
| `component` | `path` | the reader maps it elsewhere: an imported path is built from the sheet names |
| `component` | `pins` | the writer writes a fixed value: the pins of the body it draws, whose ids and, for a generic body, names are its own |
| `net` | `netclass_id` | the reader maps it elsewhere: a class is a record of the PCB document, and a schematic reading holds none |
| `netclass` | `clearance`, `track_width`, `via_diameter`, `via_drill` | the reader maps it elsewhere: the values are written as design rules and read as rules |
| `netclass` | `description` | the writer does not write it |
| `footprint` | `component_id` | the reader maps it elsewhere: a footprint is matched by the reference of its component |
| `footprint` | `lib_ref` | the writer writes a fixed value: the name of the generated PCB library |
| `footprint` | `locked` | the writer does not write it from the model: the lock comes with the placement request |
| `footprint` | `attributes` | the writer does not write it |
| `footprint` | `pads` | the reader maps it elsewhere: pads are the kind `pad` |
| `footprint` | `graphics` | the reader maps it elsewhere: graphics are the kind `footprint_graphic` |
| `footprint` | `fields`, `texts` | written and not compared: the write of a model writes the fields `Reference` and `Value` at their place and the free texts as texts of the component (change c0126), but a build places the designator and the comment itself and its stored board holds no field for them; their read-back is covered by unit tests (`tests/unit/backends/altium/test_lower_items.py`) |
| `footprint` | `bodies` | the writer does not write it by default; it writes it on request only (`--altium-bodies extruded`, change c0121), and then the kind `body` is compared beside the scope (`roundtrip.BODY_SCOPE`: `kind`, `height`, `standoff`, `outline`, `layer`, `name`), for the bodies that were written |
| `pad` | `shape`, `kind`, `rotation`, `drill`, `layers`, `padstack` | the reader maps it elsewhere: a pad is written as an Altium pad stack, which the import reads by its own rules (`docs/formats/altium/import.md`) |
| `pad` | `zone_connection` | the writer does not write it |
| `via` | `layers` | the writer writes a fixed value: only through vias are written |
| `via` | `via_type` | the writer writes a fixed value: only through vias are written |
| `zone` | `name` | the writer writes a fixed value for a zone without a name: a generated one |
| `zone` | `priority` | the reader maps it elsewhere: the priority is written as the pour order |
| `zone` | `fills`, `filled` | the writer does not write it: the poured copper is Altium's to compute |
| `zone` | `settings` | the writer does not write it |
| `zone` | `locked` | the writer does not write it |

A component whose value is empty in the script is written with its symbol's name as the comment, and
the built model stores that value, so that the model is what the documents read back to.

### Written scope

`fenolite.backends.altium.lower` writes a model that holds a board as Altium documents without a
script (`AltiumBackend().write(design)`, change c0090): the PCB document from the board, and a schematic
that is generated from the circuit, with its library and the project file. The scope of RT-A3 is the
scope of RT-A2 above (`RT_A3_SCOPE` is `RT_A2_SCOPE`). The table says what a write carries of each kind
of a model, what RT-A3 compares of it, and what is left out and counted in `unwritten`.

| kind | written | compared by RT-A3 | left out, with its key in `unwritten` |
|---|---|---|---|
| `component` | reference and comment as the component's texts, the symbol link | `ref`, `value` | nothing; a component without a reference is a free pad |
| `net` | one net record per name | `name`, `members` | `net`: a name that no record holds, or a second net of one name |
| `netclass` | one class per name with its nets | `name` | `netclass`: a name that no record holds |
| `footprint` | a component record with its own pads, its placement, and the unique ids of the document it was read from; since change c0126 its graphics, its fields `Reference` and `Value` (the designator and the comment at their place, shown or hidden) and its free texts | `position`, `rotation`, `side` | `footprint`: a reference with `|`, or a free pad that cannot be written |
| `footprint_graphic` | a line, rectangle, circle or arc on the overlays (and, for a model not read from Altium, on the four mechanical layers of Fenolite's layer map) through the footprint's definition; every other graphic as the instance holds it, as a track, an arc or a region of the component, on the overlays, Mechanical 1 to 16 of a board that was read, paste and solder mask (c0126) | `kind`, `layer`, `points`, `width`, `filled` | `footprint-graphic`: a layer without a layer in the document, a graphic that no record holds; `footprint-copper`: a graphic on a copper layer, which would be copper (a loss: it needs `allow_lossy`) |
| footprint field, footprint text | the designator and the comment from the fields `Reference` and `Value`, a free text of the footprint as a text of the component (c0126) | not compared | `footprint-text`: a text with a line break, without a positive height or stroke, or on a layer without a layer in the document |
| `pad` | number, net, position, size, shape, rotation, round hole, one shape on all its layers; a rounded rectangle with the percentage of `corner_ratio` (c0126) | `number`, `net_id`, `position`, `size`, `corner_ratio` | `pad`: a per-layer pad stack, a custom or trapezoid shape, a slot, no copper layer, no number, or a rounded rectangle whose corner ratio is not known |
| `track`, `arc` | on a signal layer of the stack, with its net; an arc that was read from an Altium document with the centre, radius and angles of its record (c0127) | every field of the scope | `track`, `arc`: a layer that is an internal plane or no layer of the written stack, no width; an arc of three points on a line that holds no record of its own |
| `via` | through, blind and buried, with its net; in the rewrite of a document that was read (`rewrite=True`, c0128) also a via whose drill equals its diameter | `position`, `diameter`, `drill`, `net_id` | `via`: a micro via, a span outside the stack, a drill that is not below the diameter (in a rewrite: above the diameter); `via-pad-shape`: the layers on which a via that was read has no pad shape (the pair `pad_removed`, c0132): the via is written, with its pad on every layer |
| `zone` | one unpoured polygon per layer, with its net | `outline`, `layers`, `net_id` | `zone`: an outline that the model does not hold (an outline with an arc); `zone-fill`: the poured copper, which Altium computes on a repour |
| text, graphic, keep-out, hole | as `fenolite build` writes them (c0085) | not compared | `text`, `graphic`, `keep-out`, `hole`: a layer without a layer in the document, an item that the record cannot hold |
| shape on copper | not written | not compared | `copper-shape`: a fill or a region on a copper layer, which the model holds as a graphic with its net in the bag |
| body | with `bodies="extruded"` (c0121): an extruded body with an outline and a height above its standoff, with the stand-in values of its two identity keys; never by default | with `bodies="extruded"`: `kind`, `height`, `standoff`, `outline` (as a ring), `layer` (as the writer's rule gives it) and `name`, within 2 nm; else not compared | `body`: every body without the request; with it, a body that names a 3D model, has no outline or no height above its standoff, or whose footprint is not written |
| rule | the rules that `rulemap.lower` writes exactly (c0084) | not compared | `rule` |
| stack | the copper layers in order, planes with their net, the stack-up values when they fit | not compared | `plane`: a plane without a net of the document is written as a signal layer; `stackup`: default values are written |
| outline | `Board.outline`, else the ring of the `Edge.Cuts` graphics | not compared | `outline`: an arc of the outline is two straight edges; a cut-out; no closed ring |
| schematic | generated from the circuit: generic symbols, one sheet | the circuit, when a project is read | `schematic`: the writer refuses the circuit, and only the PCB document is written; `module`: every module, because the schematic is one sheet; `channel`: the channel of a repeated sheet (the bag keys `sheet_symbol` and `channel_index`); `pin-pad-map`: the pin-to-pad map of a component that has no footprint model in the generated schematic (the map of every other component is written as records of its footprint model, change c0123); `pin-pads`: a component whose bag holds a map record that the model cannot say (the key `pin_pads`) |

Keys of `unwritten` that start with `record:` count what the import maps to no model entity, by the
category of its census: `footprint-graphics` (since change c0126 only the primitives of a component
without a readable position, or on an internal plane), `pour-primitives`, `plane-cuts`, `shape-based-regions`,
`polygons`, `classes`, `raw-primitives`, `region-holes`, and one for each storage that the import keeps as bytes (a
rewrite holds Fenolite's own content in such a storage, not the document's). **A rewrite is therefore
not a copy.** It holds the placement, the pads, the routing and the polygon outlines of the board;
`unwritten` lists what it does not hold, and the counts measured on the public corpus are in
`docs/evidence/altium-roundtrip.md`.

A loss of a footprint, a pad, a track, an arc, a via, a zone, a net, a net class, a shape on copper or
a plane makes the write refuse (`FEN-7001`) unless `allow_lossy` is given; every loss is one
`altium.not-lowered` per kind. The corner ratio of a rounded rectangle is `Pad.corner_ratio` (change
c0126), which the Altium import fills; a design read from a KiCad board holds it, with the graphics of its
footprints, once `fenolite.lens.altium.write_model` projected it (`backends.kicad.fpitems`). A board read from an Altium document is written in the document's frame
with its origin, and its components keep their unique ids; any other board is written like a build, with
the outline's lower-left corner at (1000 mil, 1000 mil). The write is experimental: the backend's
capability report names no write kind.

**The write runs no check.** `fenolite build --target altium` runs the copper check before it writes
and refuses a board with a short (section "Checks"); `AltiumBackend().write` and `write_model` do not:
they write the model as it is. Run `fenolite check` on the written documents.

**Limits that later changes close** (decisions of the maintainer, 2026-10-06):

- Closed by change c0126: a rewritten board had no silkscreen of its footprints, and a build did not go
  through this write. A footprint of the model now holds its graphics and free texts and a pad its
  corner ratio; a rewrite keeps the lines, arcs, fills, regions, designator and comment of its
  footprints on the overlays and on Mechanical 1 to 16, and `fenolite build --target altium` places the
  footprints into the model and goes through `lower.from_design` with its options (the committed samples
  keep their bytes). No PCB library is derived from an imported model.
- RT-A3 holds on the eight public PCB documents since change c0127, and `H-A-VER-RTA3` is
  `CORPUS-VERIFIED`. That level means: Fenolite reads its own rewrite of a public Altium PCB document
  back to an equal model inside the written scope, and KiCad's importer reads the rewrite as Fenolite
  does at the levels 1 to 5 of `equivalent`. It says nothing about Altium opening a written file,
  which stays `INFERRED` until the kit run (c0091, c0092); the write stays experimental. The scope
  holds the graphics of footprints since change c0126 and leaves out component bodies (written on request since
  c0121, and never by the stage `roundtrip.rta3`, which runs without them) and the items
  that `unwritten` counts per kind (`docs/evidence/altium-roundtrip.md`, "RT-A3").
- Closed by change c0127: the 2 nm of the scope did not hold for the points of an arc, because an arc
  record holds a centre, a radius and two angles, and the model three points. An arc that was read
  now keeps the record's own values in its `altium` bag (the pair `arc`), and the write uses them
  while they still give the arc's three points within 2 nm. An arc that was moved in the model, and
  an arc of a script or of a KiCad board, is derived from its three points as before.
- Closed by change c0128 for a rewrite: a via whose drill equals its diameter, which a document that
  Altium saved can hold, is written when the caller says that the write is the rewrite of a document
  that was read: `AltiumBackend().write(design, rewrite=True)`. RT-A3 (`fenolite roundtrip PATH --level
  rta3`, the stage `roundtrip.rta3`) writes that way. `rewrite=True` is refused for a board that was
  not read from an Altium document. A build from a script, `write_model` and a write without the
  argument keep refusing such a via.
- The schematic of a rewrite is written only when the build's schematic writer takes the circuit. A
  tolerant schematic write for circuits that were read belongs to v0.5a, with `convert`.

## Checks

`fenolite check` on an Altium project, folder or document runs eight stages without any tool
(`docs/cli-contract.md`, "check on Altium input"). Two of them are the light DRC of change c0088:

- **`copper.clearance`** finds shorts and clearance violations in the copper of the PCB document: tracks,
  arcs, vias, pads and the poured regions of polygons. The clearance in force comes from the Clearance
  rules of the document that map onto the model (rules scoped by `All`, a net or a net class).
- **`parity`** compares the PCB document with the schematic documents: a component on one side only,
  two footprints of one designator, another value or footprint name, a pad on another net, a pin
  without a pad. `fenolite parity` gives the same comparison alone.

It is not Altium's design rule check. What it does not judge, it says, and the stage then carries
`UNVERIFIED`:

| not judged | why | how the stage says it |
|---|---|---|
| unpoured polygons | the document holds no copper for them; a Fenolite build writes its polygons unpoured | `summary.unpoured`, one `copper.item-unsupported` |
| internal planes | a plane is drawn in negative: the document holds the lines that cut it, not its copper, and the import makes no track of those lines | one `copper.item-unsupported` at `plane`, with the number of planes and of the objects left out |
| Clearance rules with a matrix that tells an arc from a track or a through-hole pad from a surface pad, the option that ignores the pads of one footprint, a layer condition for some of the board's copper layers, a scope function outside the grammar or another key outside the rule table | the model has no rule of that form; a blank or uniform matrix, a clearance matrix between all net classes and a layer condition for every copper layer are read ("Rules") | `summary.rules.opaque_clearance_rules`, one `copper.rules-incomplete` |
| the clearance of a pour that no mapped rule applies to | a polygon has no clearance of its own, and no default is invented | `summary.zones_unjudged`, one `copper.rules-incomplete` at `zone` |
| board-edge clearance, component clearance, silkscreen, hole and width rules | outside the copper check | nothing: these are not stages |

**A via without a pad on some layers (change c0132).** Altium's "Remove Unused Pad Shapes" takes the pad
of a via off the layers on which nothing touches it, and a pour then keeps its clearance to the hole.
The via record names those layers; the import keeps their Altium layer ids in the via's bag (the pair
`pad_removed`), because a via of the model holds one diameter. The copper check judges such a via with
its diameter where it has a pad and with its drill as diameter where it has none, so a pour around the
hole is no short and copper inside the hole still is one. Nothing is left unjudged. Three things to
know: `summary.items.via` counts the parts in which such a via is judged (one per run of layers that
are alike), not the vias; `analyze` and `equivalent` draw the via with its pad on every layer, as the
model says it; and the meaning of the bytes is `INFERRED` from one public document and Altium's
documentation (`docs/formats/altium/pcb-copper.md`, "Via"; `H-A-IMP-VIA-PADLESS`).

`fenolite build --target altium` runs the copper check on the PCB document before it writes and refuses
a board with a short (`docs/cli-contract.md`, "Copper guard of an Altium build").

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

One flat sheet by default, or one sheet per module at any depth with `--altium-sheets modules` (no
repeated sheets, no routed wires between sheet symbols, no harness in the ASCII form, no harness below
the first level, no nested harnesses); a sheet that passes a bus through draws it twice; no bus in the
DSL, no variants; an output job whose Gerber output holds its settings and plots no board outline, no drill drawing and no pad master, and whose other outputs (NC drill, pick and place, bill of materials, prints) hold no settings; a drawing sheet without a logo; the PCB document has unpoured polygons, no
split planes, no micro vias, component bodies only on request (extruded ones, experimental, never opened in Altium) and only the rule kinds and scopes of "Rules", and the PCB library holds only the footprint content listed above; a symbol of several units or body styles, a symbol with an arc, a Bezier curve or a text, and every Altium link are drawn as rectangles, the line widths and colours of a symbol are not written, and there are no
alternate display modes; an Altium library is never read or copied, only stood in for; text in 7-bit
ASCII, except the comment and the parameter values of a binary schematic (Windows-1252); a property that no parameter can hold stays in the model. Nothing of change c0086 has been opened in Altium yet (Part Y). The v0.3 reader reads the MS-CFB container and PCB documents and libraries ("Reading PCB files");
schematic and other Altium records are interpreted by later changes.
