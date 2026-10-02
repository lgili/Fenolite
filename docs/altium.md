# Building for Altium (experimental)

`fenolite build design.py --out DIR --target altium` builds a DSL design into an Altium Designer project
instead of a KiCad project: a project file `<name>.PrjPcb` and a schematic `<name>.SchDoc` in Altium's
ASCII form. Altium compiles the schematic, and its engineering change order creates the PCB from it.
Fenolite writes no PCB document.

The target is **experimental** (change c0032): its output, options and issue codes may change in any
release. `fenolite capabilities` lists it under `result.experimental`, and its evidence stays `INFERRED`
(see "Evidence" below). Format facts and their sources are in `docs/formats/altium/`; everything else on
this page is a Fenolite choice.

## Command

```bash
fenolite build design.py --out build/myboard --target altium --dry-run    # plan only
fenolite build design.py --out build/myboard --target altium --confirm    # write
```

- `--target kicad` stays the default, and a KiCad build is unchanged. `--target` accepts `kicad` and
  `altium`; any other value is a usage error (`FEN-2001`, exit 2).
- The rules of `docs/dsl.md` hold as for KiCad: the script runs as your own code, `--out` is never the
  script folder, writes follow `--dry-run` and `--confirm`, and `--discard-layout` and `--no-backup` work
  the same. `--seed` and `--timestamp` change nothing, and neither do `--kicad-version` and
  `--allow-lossy`.
- The build reads only the script: no library, no KiCad or Altium file, no external tool.
- `result` holds `design`, `target` (`"altium"`), `out`, `files`, the counts `components`, `nets`,
  `labels` and `power_ports`, `sheet` (`A4` … `A0` or `custom`), `kept`, `experimental` (`true`) and
  `script_output`. Planned writes have the kinds `altium_prjpcb`, `altium_schdoc_ascii` and `fenolite`.

## Lib ids, footprints and pins

- `Part(ref, lib_id, footprint=None, value="")` names Altium libraries as `<library>:<name>`, split at the
  first `:`. The library part is the file name with its extension, written as given:
  `Part("U1", "MyParts.SchLib:LDO", footprint="MyParts.PcbLib:SOT23", value="5V")`. A `lib_id` or a
  footprint without both parts is refused (`altium.lib-id-form`, `altium.footprint-form`).
- The lib id becomes the component's library link: Design Item ID `LDO`, Source `MyParts.SchLib`.
  "Tools » Update From Libraries" takes its source from this link.
- The footprint becomes the component's current footprint model, `SOT23` from `MyParts.PcbLib`. A part
  without a footprint gets the warning `altium.no-footprint`: the change order cannot place it.
- **Connect pins by number.** `U1[3]`, not `U1["VOUT"]`: each designator becomes a pin number, and the
  change order matches pins to footprint pads by number. Fenolite cannot check pin numbers against a
  library, because it reads none.
- Every written text (design name, refs, values, net names, library, symbol and footprint names, pin
  designators) must be printable 7-bit ASCII without `|` and without leading or trailing spaces, and a
  value must not start with `=` (Altium reads it as a reference to another parameter). Anything else is
  refused with `altium.text-unwritable`, never escaped or replaced. Net names or refs that differ only
  in letter case are refused (`altium.name-case-collision`).

## The schematic

- **Generic bodies.** Each part is a rectangle with one passive pin per designator its nets use, in
  natural order (`1`, `2`, `10`, `A1`, `B`): the first half on the left edge, the rest on the right,
  200 mil long and 100 mil apart. The designator is drawn above the body and the comment below it; the
  comment is the value, or the symbol name when the value is empty.
- **Connections.** Every pin gets a short horizontal wire stub. A net of a `Power(hv, lv)` interface ends
  each stub with a power port named after the net: the "power ground" symbol for a net that is only ever
  the `lv` member, a bar otherwise. Every other net gets a net label on each stub. Labels of one name
  join within the sheet; ports of one name join across the design. No wire runs between parts.
- **Layout.** Parts are placed in component-path order, so a module's parts stay together, in rows on
  the smallest ISO sheet, A4 to A0 landscape, that holds them. A design too large for A0 gets a custom
  sheet and the warning `altium.sheet-custom`.
- **Unique ids.** Each component's unique id is derived from its component path. A rebuild that keeps
  the paths keeps the ids, so Altium keeps the links between schematic and PCB components.
- **Not lowered.** The board outline, placements, net classes and diff pairs have no place in these
  files. They stay in `.fenolite/`, and each kind gives one `altium.not-lowered` info. Modules only order
  the layout; the schematic is one flat sheet.

## Project file and outputs

Under `--out DIR`:

- `<name>.PrjPcb`: `[Design]`, `Version=1.0` and one document, `<name>.SchDoc`, written only when the
  folder has no `<name>.PrjPcb` yet. An existing project file is kept, whatever `--discard-layout`
  says, listed in `result.kept` and reported with `altium.project-kept`, because Altium rewrites it when
  you add the PCB document. Delete it to get a new one.
- `<name>.SchDoc`: the ASCII schematic, with CR LF line ends.
- `.fenolite/`: the six layer files of the model, with the generic pins, and `build.json` with
  `"target": "altium"`.

**Edited outputs.** As for KiCad (`docs/dsl.md`, "Edited outputs"), a schematic changed since the last
build, for example one saved by Altium in any form, is refused with `FEN-7001` (exit 7) and one
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
| `altium.no-footprint` | warning | a part names no footprint |
| `altium.sheet-custom` | warning | the layout does not fit A0, so a custom sheet is written |
| `altium.generic-symbols` | info | the components got generic bodies |
| `altium.not-lowered` | info | the board, placements, net classes or diff pairs are kept in the model only |
| `altium.project-kept` | info | `<name>.PrjPcb` exists in `--out` and is kept |

Model findings (`model.*`) pass through. A build with an error exits 5 and writes nothing.

## In Altium Designer

1. Put the libraries the lib ids and footprints name beside the project file, or install them. The
   change order searches the project folder first.
2. Open `<name>.PrjPcb`. The schematic is listed among the source documents.
3. Compile the project ("Project » Validate PCB Project", "Compile PCB Project" in older versions) and
   check the nets in the Navigator panel.
4. Add a new PCB document to the project and save the project. Altium rewrites the project file;
   later builds keep it.
5. Run "Design » Update PCB Document", then "Validate Changes" and "Execute Changes".
6. To use the library symbols, run "Tools » Update From Libraries" with "Replace selected attributes"
   and graphical attributes off: parameters and models are updated, and the generic bodies and every
   connection stay. A full replacement puts the library symbols in, whose pins may sit elsewhere, so the
   stubs may be left unconnected (`H-A-SCH-UPDATE`).
7. After a change to the script, rebuild with `--target altium --confirm`, compile, and run the change
   order again. Unchanged component paths keep their unique ids, so the PCB components stay linked
   (`H-A-SCH-RELINK`).

## Evidence

- Every format fact is `INFERRED` from public sources (`docs/formats/altium/`). `kicad-cli` cannot read a
  `.SchDoc` (S-0132, S-0020), so no oracle checks these files.
- The maintainer checks the committed sample (`examples/altium_sample/`, files under
  `tests/data/altium/sample/`) in Altium Designer following `docs/evidence/altium-schematic.md`. Each
  confirmed `H-A-SCH-*` or `H-A-PRJ-*` row becomes an author report,
  `ALTIUM-VERIFIED(author-report; …)`, which never promotes an operation: the envelope of
  `build --target altium` stays `INFERRED` for every design.

## Limits

One flat sheet; no buses, harnesses, variants, rules, net classes or output jobs; no PCB document, no
library file written or copied; no pin taken from a library; text in 7-bit ASCII only. Reading Altium
files is planned for v0.3.
