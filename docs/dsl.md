# The design DSL and `fenolite build`

`fenolite.dsl` describes a board in plain Python: parts, nets, net classes, interfaces, an outline and
placements. `fenolite build design.py --out DIR` runs the script and writes a KiCad 9.0 or 10.0
project from it. The DSL uses the standard library and Fenolite's own `core` and `model` only.

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
- `Part(ref, lib_id, footprint=None, value="")`: `lib_id` is a symbol `Library:Name`; `footprint=None`
  falls back to the symbol's `Footprint` property, and `value=""` to its `Value` property.
- `part[designator]` returns a pin handle; `connect(net, *pins)` joins pins to a net.
- `Part.place(x, y, rot=0, side="top", locked=False)`, once per part.
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
  unresolved lib id is listed in the refusal's `issues` (`FEN-3001`).
- A designator is a pin number first; otherwise it names every pin with that name. A pin number that
  is also another pin's name gives `build.pin-ambiguous`, and the number wins.
- Pads get the net of the pin with their number. Hidden and power pins create no implicit nets.
- Net or class names that differ only in letter case are refused (`build.name-case-collision`).
  KiCad 9.0.9 and 10.0.6 compare net names in custom-rule conditions without regard to case
  (`H-K-DRU-COND`, `docs/formats/kicad/rules.md`); the build refuses such names whatever is measured.

## Determinism

A build is a pure function of the script and the Fenolite version: ids come from keys, files hold no
date, and sets are never iterated in hash order, so builds with different `--seed`, `--timestamp` and
`PYTHONHASHSEED` values (S-0072) are byte-identical. `--seed` and `--timestamp` are accepted and unused.

## Output layout

Under `--out DIR` (never the script folder):

- `<name>.kicad_pcb`, `<name>.kicad_pro`, `<name>.kicad_dru`;
- `fp-lib-table` with one row per vendored nickname, uri `${KIPRJMOD}/lib/<nickname>.pretty`, in the
  table form of the target (`docs/formats/kicad/libraries.md`, "Writing library tables");
- `lib/<nickname>.pretty/<entry>.kicad_mod`: every footprint resolved through a project table, copied
  byte for byte. Footprints from global or template tables are not vendored (`build.global-library`);
- `.fenolite/{meta,circuit,board,rules,manufacturing,findings}.json`: the model, as `dump_dir` writes it;
- `.fenolite/build.json`: `{"design", "files": {path: sha256}, "schema": "fenolite.build-record.v0",
  "target"}`, with every file outside `.fenolite/` that the build wrote, and no date.

The folder is self-contained and can be moved or copied whole.

## Edited outputs

Before the plan is returned (so `--dry-run` refuses too), each planned file that already exists must
either have the planned bytes or the SHA-256 recorded in `.fenolite/build.json`. Anything else, for
example a board saved from KiCad, is refused with `FEN-7001` (exit 7) and one `build.layout-exists`
issue per file. `--discard-layout` replaces those files, keeping `.bak` copies unless `--no-backup`.
Without a readable record only identical bytes pass.

## Stale vendored files

A build writes files; it never deletes them. A footprint vendored by an earlier build stays in `lib/`
after its part is removed from the script, and is no longer listed in `build.json`. Delete the folder,
or `lib/`, to start clean.
