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
  `altium_schlib` and `fenolite`.
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
- **Not lowered.** The board outline, placements, net classes and diff pairs have no place in these
  files. They stay in `.fenolite/`, and each kind gives one `altium.not-lowered` info. Modules only order
  the layout; the schematic is one flat sheet.

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
  `docs/evidence/altium-schematic.md`).

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
`altium.pcbdoc-not-written` (info) names the reason. It holds the outline, a two-layer stack, every
component with a footprint at its script placement (unplaced ones are staged right of the outline as the
KiCad build stages them, with `altium.pcb-staged`), its pads at absolute coordinates with their nets, its
graphics, and its designator (the comment is written hidden). No routing, vias, zones, rules or classes.
The frame: Y up, the board's lower-left corner and the origin at (1000 mil, 1000 mil); bottom-side parts
are mirrored as KiCad places them and their layers swapped. Each component carries
`SOURCEUNIQUEID=\<id>`, the unique id of the same component in `<name>.SchDoc`, so "Design » Update PCB
Document" should match every component (`H-A-PCB-DOC-LINK`). When the document is written, the board and
the placements are no longer reported by `altium.not-lowered`. A document edited in Altium is refused on
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
- `<name>.PcbLib` and `<name>.PcbDoc` (change c0035, see above), listed in a new project file as
  `[Document2]` (the document) and with the libraries. A kept project file does not list them:
  `altium.pcb-not-in-project` names them.
- `.fenolite/`: the six layer files of the model, with the pins the build gave the components, and
  `build.json` with `"target": "altium"`.

**Edited outputs.** As for KiCad (`docs/dsl.md`, "Edited outputs"), a schematic or library changed since
the last build, for example one saved by Altium in any form, is refused with `FEN-7001` (exit 7) and one
`build.layout-exists` issue. `--discard-layout` replaces it and keeps a `.bak` unless `--no-backup`.
Work done on the schematic in Altium is lost by such a rebuild: change the design script instead.

## Issue codes

| code | severity | when |
|---|---|---|
| `altium.lib-id-form` | error | a `lib_id` is not `<library>:<name>` with both parts |
| `altium.footprint-form` | error | a footprint is not `<library>:<name>` with both parts |
| `altium.text-unwritable` | error | a written text is not printable 7-bit ASCII, holds `\|`, is empty, has a leading or trailing space, or is a value that starts with `=` |
| `altium.name-case-collision` | error | two net names, or two refs, differ only in letter case |
| `altium.unique-id-collision` | error | two components get the same unique id |
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
| `altium.not-lowered` | info | the board, placements, net classes or diff pairs are kept in the model only |
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

One flat sheet; no buses, harnesses, variants, rules, net classes or output jobs; the PCB document has
no routing and two copper layers, and the PCB library holds only the footprint content listed above; schematic libraries hold synthesised rectangles, not the symbols' graphics, and no
alternate display modes; an Altium library is never read or copied, only stood in for; text in 7-bit
ASCII only. Reading Altium files is planned for v0.3.
