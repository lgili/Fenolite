# The design DSL and `fenolite build`

`fenolite.dsl` describes a board in plain Python: parts, nets, net classes, interfaces, an outline and
placements. `fenolite build design.py --out DIR` runs the script and writes a KiCad 9.0 or 10.0
project from it, or, with `--target altium`, an experimental Altium project (see "Building for
Altium"). The DSL uses the standard library and Fenolite's own `core` and `model` only.

Python facts are cited from `docs/evidence/sources.md` (S-0070 … S-0074); KiCad facts from
`docs/formats/kicad/`. Everything else on this page is a Fenolite choice.

## Security: `build` executes the script

`fenolite build` runs `design.py` as the user's own code, in the same process. There is no sandbox:
the script can do anything the user can do. **Never run `build` on a script you do not trust.**
`fenolite build --help` says the same.

## API

```python
from fenolite.dsl import Design, Net, Part, Power, connect, mm

design = Design("blink")  # the name becomes the KiCad file stem
design.board(mm(50), mm(30))  # outline width and height; copper=2 (default) or 4

u1 = Part("U1", "Mini:Mini_QFP32_IC", value="MCU")
r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330")
design.add(u1, r1)  # objects join the design only through add()

vin, drv = Net("VIN"), Net("LED_DRV")
connect(drv, u1[1], r1[1])  # designators: pin numbers first, then pin names
design.add(Power(vin, Net("GND")))
design.rules.netclass("PWR", clearance=mm(0.2), track_width=mm(0.5), nets=(vin,))

u1.place(mm(14), mm(15), locked=True)
r1.place(mm(32), mm(9), rot=90, side="bottom")
```

- `Design(name)`, `Module(name)`: containers; `add(*objs)` adds parts, modules, nets and interfaces.
  There is no implicit "current design".
- `Part(ref, lib_id, footprint=None, value="", *, properties=None)`: `lib_id` is a symbol
  `Library:Name`; `footprint=None` falls back to the symbol's `Footprint` property, and `value=""` to
  its `Value` property. `properties` maps user property names to text ("User properties").
- `part[designator]` returns a pin handle; `connect(net, *pins)` joins pins to a net.
- `Part.place(x, y, rot=0, side="top", locked=False)`, once per part.
- `Design.moved(old, new)`: a path alias that keeps a renamed part's layout ("Path aliases").
- `Design.board(width, height, copper=2)`, once per design.
- `design.rules.netclass(name, *, clearance, track_width, via_diameter, via_drill, nets)`: every value
  is optional; a net belongs to at most one class.
- `Interface`, `Power(hv, lv)` and `DiffPair(p, n)`: named groups of nets kept in the model. A
  `DiffPair` is not lowered to KiCad (`build.interface-not-lowered`, info).
- `to_model(design)` and `placements(design)` turn a DSL design into a model `Design` and the
  placement requests; `build` calls them.

Nothing of the DSL is re-exported from the root `fenolite` package: the DSL `Design` and the model
`Design` are different classes.

### Names and paths

- A design name matches `^[A-Za-z0-9][A-Za-z0-9_.-]*$`. Module names and refs match `[A-Za-z0-9_.+-]+`.
- A module path is its name at the top and `<parent path>/<name>` below; a component path is
  `<module path>/<ref>`, or `<ref>` at the top.
- Net names are global and literal. A module-local net is named by the script, for example
  `Net(f"{m.path}/FB")`.
- Errors are raised as `DslError` at the offending call, so the traceback points at the script line:
  duplicate paths, duplicate net, class or interface names, two `Net` objects with one name, a net in
  two classes, a second `place()` or `board()`, `copper` other than 2 or 4, one designator on two nets,
  an unknown `side`, an invalid name. Equal refs in different modules are reported by
  `Design.validate()` (`model.duplicate-ref`).

## Units

- A length always carries a unit: `mm()`, `mil()`, `inch()` or `nm()` return an exact `Length` in
  integer nanometres, and a string such as `"2.54mm"` is read with no default unit. A bare number or
  a string without a unit raises `DslError` naming the argument.
- The helpers take `int`, `str` or `float`. A float is converted exactly from its `repr`, which is the
  shortest string that round-trips (S-0073); a value that is not a whole number of nanometres raises.
  So `mm(0.1) == nm(100_000)`, and `mm(1/3)` raises.
- `Length` supports `==`, hashing, `+`, `-`, unary `-`, and `*` and `//` by an `int`.
- Angles are degrees: an `int`, a string (`"30.5"` or `"30.5deg"`) or a float through its `repr`;
  whole microdegrees, normalised to [0°, 360°).

## Ids: the key table

Every object that `to_model` or the build creates gets `derived_id(prefix, "dsl", key)` from
`dsl.KEYS`. Ids depend on names and paths only, never on `--seed` or on the order of calls (see
`docs/design-model.md`, "Ids of design scripts").

| object | prefix | key |
|---|---|---|
| design header | `dsn` | `design` |
| board | `brd` | `board` |
| outline | `out` | `outline` |
| rule set | `rst` | `rules` |
| manifest | `mfn` | `manifest` |
| module | `mod` | `module:<path>` |
| component | `cmp` | `component:<path>` |
| pin | `pin` | `pin:<path>:<number>` |
| net | `net` | `net:<name>` |
| net class | `cls` | `netclass:<name>` |
| interface | `itf` | `interface:<kind>:<name>` |
| layer | `lay` | `layer:<KiCad name>` |

Footprints and pads are keyed by the component path through the KiCad embedder.

## Frame and `BOARD_ORIGIN`

DSL coordinates are board-relative: the origin is the outline's top-left corner and Y points down.
`rot` is the stored footprint angle on both sides. The board is written at
`BOARD_ORIGIN = (100 mm, 100 mm)`, so `place(mm(14), mm(15))` puts the part at (114 mm, 115 mm) in
the KiCad file. This is a Fenolite choice: (0, 0) would put the board under the drawing-sheet border,
and centring on the paper would move every part when the paper size changes.

Parts without `place()` are staged in one row, in component-path order, 5 mm right of the outline and
top-aligned with it, 2 mm apart, on the top side at 0° and unlocked, each with a `layout.unplaced`
warning.

## Scripts

- The script runs with `runpy.run_path` and the run name `__fenolite_build__` (S-0070). While it runs,
  `sys.dont_write_bytecode` is set, `sys.argv` is the script path and the script folder is first on
  `sys.path` (S-0071). Afterwards these are restored, and modules the run imported from the script
  folder are removed from `sys.modules`, so no `__pycache__` is written and a second build sees edited
  sibling modules.
- The script must bind a module-level `design` of type `fenolite.dsl.Design`.
- Its stdout and stderr are captured (S-0074) into `result.script_output`, at most 4000 characters,
  ending in `…[truncated]` when cut, so stdout stays one JSON document.
- Any exception of the script, `SystemExit` and `DslError` included, and a missing `design` are
  `FEN-3004` (exit 3), with `line:<n>` of the deepest script frame as locator when there is one.
  `KeyboardInterrupt` propagates.

## Libraries and pins

- Libraries are resolved by KiCad's tables: `fp-lib-table` and `sym-lib-table` next to `design.py` are
  the recommended source; global and template tables follow `docs/formats/kicad/libraries.md`. Every
  unresolved lib id is listed in the refusal's `issues` (`FEN-3001`). Whatever the table, the placed
  footprints are vendored into the output ("Vendored libraries").
- A designator is a pin number first; otherwise it names every pin with that name. A pin number that
  is also another pin's name gives `build.pin-ambiguous`, and the number wins.
- Pads get the net of the pin with their number. Hidden and power pins create no implicit nets.
- Net or class names that differ only in letter case are refused (`build.name-case-collision`).
  KiCad 9.0.9 and 10.0.6 compare net names in custom-rule conditions without regard to case
  (`H-K-DRU-COND`, `docs/formats/kicad/rules.md`); the build refuses such names whatever is measured.

## User properties

`Part(..., properties={"Part number": "PN-330", "Supplier code": "S-1"})` gives a part user properties,
such as a part number or a supplier code, as text.

- **Text rules.** Names and values are `str`. A name is non-empty, has no leading or trailing
  whitespace and is printable (`str.isprintable`, S-0105); a value is printable and may be empty. A tab
  or a newline is refused: a multi-line part number is a mistake, and CSV exports would have to quote it.
  Numbers are refused like elsewhere in the DSL (`{"Qty": 2}` is more likely a mistake than a field).
- **Reserved names,** compared after `str.casefold` (S-0105):
  - `Reference` and `Value` come from `ref` and `value`;
  - `Datasheet` and `Description` are fields of the footprint library: every mini footprint carries
    them, and a KiCad 10.0.6 re-save merges a second `Datasheet` node into the field
    (`H-K-VENDOR-DUPNAME`, `KICAD-VERIFIED (10.0.x)`);
  - `Footprint` is removed by a 10.0.6 re-save (`H-K-UUID-KEEP-2`);
  - the prefix `fenolite.` is Fenolite's namespace (`fenolite.path` holds the component path), and the
    prefix `ki_` holds KiCad's own names (`ki_fp_filters`).

  KiCad itself keeps `datasheet` apart from `Datasheet`, but BOM columns and agents would read them as
  one field, so two names equal after `casefold` are refused too. Errors are raised at the `Part` call.
- **Build checks.** The build checks the properties of any model `Design` again: a reserved name gives
  `build.property-reserved`, other invalid text `build.property-invalid`, and a property that the
  footprint library already holds with another value `build.property-conflict` (with the same value,
  nothing is appended). The DSL reads no library, so only the build can see the last case.
- **Order and form.** The properties are written after `fenolite.path`, in code-point order of names,
  each hidden on `F.Fab` at the footprint origin with a 1 mm font (on `B.Fab`, mirrored, for a bottom
  part). Adding one moves no other uuid. KiCad 9.0.9 and 10.0.6 load them without a library mismatch,
  and a 10.0.6 re-save keeps names, values and visibility (`H-K-VENDOR-PROPS`). `Component.properties`
  holds what `read_board` reads back.
- Position, layer, visibility and size of these fields cannot be set yet (field placement, c0030).

## Vendored libraries

`fenolite build` copies every footprint it places into `lib/<nickname>.pretty/`, whatever the table row
that resolved it (project, global, template), and writes one `fp-lib-table` row per nickname. A built
project therefore needs no global or template table: `kicad-cli`, which runs with an empty
configuration, and another machine both find every footprint (`H-K-VENDOR-GLOBAL`: one
`lib_footprint_issues` per footprint without vendoring, none with it, on 9.0.9 and 10.0.6).

- **Nicknames.** The copy keeps the row's nickname, so lib ids, the board and `.fenolite/` keep the
  design's names. In KiCad's library check the vendored project row hides a global row of the same
  nickname, and with it the global library's other items (`H-K-VENDOR-SHADOW`, measured for DRC on both
  majors). The GUI footprint chooser is expected to behave the same; this is not probed.
- **Only placed footprints:** no whole library, no 3D models (they stay at their `${KICAD…_3DMODEL_DIR}`
  paths), no symbols and no `sym-lib-table` before schematics (v0.2a).
- **Unsafe names.** A nickname holding `/`, `\` or a non-printable character, or two vendored paths
  that differ only in letter case, give `build.vendor-unsafe-name` and no file.
- **Library changes.** Every build copies the footprints again from their libraries. When a copy
  differs from the one the last build recorded, `build.library-changed` names it, so a library update
  shows in the `--dry-run` plan before `--confirm`. An untouched old copy is replaced; one edited by
  hand is protected like any output ("Edited outputs").
- **Stale copies** of removed parts stay in `lib/` ("Stale vendored files").
- **Licence.** The copies keep their library's licence. KiCad's official libraries are CC-BY-SA 4.0
  with an exception for designs that use them, and the exception does not cover redistributing the
  collection (S-0048). Fenolite gives no legal advice; copies are written only into `--out`.
- **Opt-out.** `fenolite build --vendor project` (or `build_design(..., vendor="project")`) copies only
  the footprints of project tables, as before c0027; the others give `build.global-library` and need
  the same global tables wherever the project is opened.

## Path aliases (`moved()`)

`design.moved(old, new)` records that the part at component path `new` was at `old` in an earlier
build, so a rebuild keeps its layout (`docs/lens.md`). `dsl.moves(design)` returns the aliases, new path
to old path. Both paths must be component paths (`R1`, `power/R1`); `old == new`, a malformed path and a
second alias with the same `old` or the same `new` raise `DslError` at the call. `moves` raises it when
`new` is not an added part or `old` still is one, so chains are refused; `fenolite build` reports this
as `FEN-3004`. Aliases are not model data: `to_model` and every id ignore them. One build is enough:
the footprint is re-placed under its new path, and the alias can then be removed.

## Determinism

A build is a pure function of the script and the Fenolite version: ids come from keys, files hold no
date, and sets are never iterated in hash order, so builds with different `--seed`, `--timestamp` and
`PYTHONHASHSEED` values (S-0072) are byte-identical. `--seed` and `--timestamp` are accepted and unused.

## Output layout

Under `--out DIR` (never the script folder):

- `<name>.kicad_pcb`, `<name>.kicad_pro`, `<name>.kicad_dru`;
- `fp-lib-table` with one row per vendored nickname, uri `${KIPRJMOD}/lib/<nickname>.pretty`, in the
  table form of the target (`docs/formats/kicad/libraries.md`, "Writing library tables");
- `lib/<nickname>.pretty/<entry>.kicad_mod`: every placed footprint, whatever the table that resolved
  it, copied byte for byte; with `--vendor project` only those of project tables ("Vendored libraries");
- `.fenolite/{meta,circuit,board,rules,manufacturing,findings}.json`: the model, as `dump_dir` writes it;
- `.fenolite/build.json`: `{"design", "files": {path: sha256}, "schema": "fenolite.build-record.v0",
  "target"}`, with every file outside `.fenolite/` that the build wrote, and no date.

The folder is self-contained and can be moved or copied whole.

## Edited outputs

A rebuild over an existing project keeps the work done in KiCad: the board, project and rules files are
merged, not replaced (`docs/lens.md`). The other outputs have no merge: before the plan is returned (so
`--dry-run` refuses too), `fp-lib-table` and each vendored footprint under `lib/` that already exists
must either have the planned bytes or the SHA-256 recorded in `.fenolite/build.json`. Anything else is
refused with `FEN-7001` (exit 7) and one `build.layout-exists` issue per file. `--discard-layout` builds
from scratch and replaces those files, keeping `.bak` copies unless `--no-backup`. Without a readable
record only identical bytes pass.

## Stale vendored files

A build writes files; it never deletes them. A footprint vendored by an earlier build stays in `lib/`
after its part is removed from the script, and is no longer listed in `build.json`. Delete the folder,
or `lib/`, to start clean.

## Building for Altium

`fenolite build design.py --out DIR --target altium` builds the same script into an experimental Altium
Designer project instead: a project file and an ASCII schematic with one generic body per part, net
labels and power ports on wire stubs, and a grid layout. Altium's engineering change order then creates
the PCB. This build reads no library, so lib ids and footprints name Altium library files
(`"MyParts.SchLib:LDO"`, `"MyParts.PcbLib:SOT23"`), and designators must be pin numbers. The board,
placements, net classes and diff pairs stay in `.fenolite/` only. See `docs/altium.md`.
