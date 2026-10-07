# The schematic of a built project

`fenolite build` writes a KiCad schematic beside the board: `<name>.kicad_sch`, the symbol libraries it
uses under `lib/`, and `sym-lib-table`. KiCad can then run its electrical rules check (ERC) on the
project, compare the board with the schematic (the parity test of its DRC), and export a netlist and a
bill of materials. The facts behind this page are in `docs/formats/kicad/schematic.md` ("Generated
sheets"), and the measurements on KiCad 9.0.9 and 10.0.6 in `docs/evidence/kicad-schematic.md`.

The schematic is correct first and readable second. Each module of the script gets a sheet of its own,
and a 2-pin part is drawn beside the IC pin it connects to, joined by a wire. It is not a drawn
schematic: nothing routes wires between symbols, and every other connection is a label.

```sh
fenolite build design.py --out build/blink --confirm            # board, project, rules and schematic
fenolite build design.py --out build/blink --schematic-layout grid --confirm   # one flat sheet (v0.2a)
fenolite build design.py --out build/blink --schematic skip --confirm    # no schematic
```

`--schematic` and `--schematic-layout` are options of the KiCad target; `--target altium` writes its own
schematic (`docs/altium.md`).

## One sheet per module

With `--schematic-layout readable` (the default), the root sheet `<name>.kicad_sch` holds the parts
outside every module, and each module that holds a part, directly or in a module below it, gets a child
sheet:

| module path | file | named from |
|---|---|---|
| `power` | `sheets/power.kicad_sch` | the root, as `sheets/power.kicad_sch` |
| `power/ldo` | `sheets/power.ldo.kicad_sch` | the sheet of `power`, as `power.ldo.kicad_sch` |

- **A box on the sheet above.** The sheet of a module is named by a sheet symbol on the sheet of its
  parent: a box with the module's name and no pin, in a row below the parts. All child files lie in one
  folder, `sheets/`, and a child names its own children from that folder, because KiCad resolves a file
  name from the folder of the sheet that names it.
- **Nets cross sheets by their labels.** Every label is a global label, so a net has the same name on
  every sheet, and that name is the one of the script and of the board. There is no hierarchical label
  and no sheet pin: those would rename a net of a module to `/power/FB`, and the board would no longer
  agree.
- **Pages.** The root is page 1; the children follow from 2, a module before the modules inside it,
  in natural order of their names.
- **Power flags** stay on the root sheet. Each sheet has its own paper, from A4 to A0.
- **Two modules, one file.** A top-level module `a.b` and a module `b` inside a module `a` would both
  be `sheets/a.b.kicad_sch`; so would two names that differ only in letter case. The build refuses
  that (`build.sheet-file-collision`): rename one module.
- **A design without modules** has one sheet, as before.

KiCad drops a sheet whose file it cannot find, and its ERC says nothing about it. The build therefore
proves, before it writes anything, that every child sheet is reached from the root (see "The netlist of
the generated sheets").

## Parts beside IC pins

On each sheet, a part with exactly two pins (a resistor, a capacitor, an LED) that is on a net of an IC
pin of the same sheet is moved beside that pin: turned along the pin, 5.08 mm away, and joined to it by
one straight wire. The wired pair carries one label, at the part's pin and turned across the wire; the
part's other pin keeps its own label. The Reference and the Value of a part turned on its side are
written level, beside that label and on its side of the part, so that no text lies on a label, on
another text, on a symbol or on a wire end.

- An **IC** here is any unit with three pins or more. Each of its pins takes at most one part; a second
  part on the same net looks for another free pin of one of its nets, or stays where the grid puts it.
- The part is **not moved when it would lie on something**: the IC's body or texts, the label of a
  neighbouring pin, or a part already moved there. With pins 2.54 mm apart, two neighbours cannot both
  get a part. So the sheet is never harder to read than the grid.
- A part in a module is on the sheet of its module, so it is moved only beside an IC of that module.
- Only this one wire is drawn. No wire bends, none has a junction, and none passes a pin.

`result.schematic` tells how many parts were moved (`satellites`) and how many wires the sheets hold.

## What the sheet holds

- **One symbol per unit.** Every unit of every part's symbol is placed, also the units you connect
  nothing to, because KiCad's ERC reports a symbol with units missing. A part without a symbol (a
  footprint that exists only on the board) gets none.
- **Global labels instead of wires.** Each connected pin carries a global label with the name of its
  net. KiCad joins pins by the label text, so no symbol position can break a connection. The one
  exception is the wire between an IC pin and the part moved beside it ("Parts beside IC pins").
- **No-connect flags from your marks.** Each pin marked with `no_connect()` gets a no-connect flag. A pin
  that is on no net and not marked gets nothing, and KiCad's ERC reports it (`pin_not_connected`): that
  is the finding you need. Mark the pins you leave open on purpose, as `examples/blink_2layer` does.
- **Power flags from power interfaces.** Each net of a `Power(...)` interface that no power-output pin
  of a fitted part drives gets one power flag, the symbol `fenolite:PWR_FLAG`. It tells ERC that the net
  is driven from outside the sheet, for example through a connector. A net with power inputs that is in
  no power interface gets no flag, and ERC reports `power_pin_not_driven`. The flag is drawn for
  Fenolite: it is not KiCad's symbol of the same purpose, and it is not in the BOM or on the board.
- **Fields.** A symbol has the properties of its footprint: Reference, Value, Footprint, Datasheet,
  Description, your user properties, and `fenolite.path`. Reference and Value are shown.
- **The title block** of the board, and the smallest paper from A4 to A0 that holds the symbols.

## The symbols and their libraries

The sheet embeds one definition per symbol it uses, and the same definitions are written to project
libraries, `lib/<nickname>.kicad_sym`, with one `sym-lib-table` row each. The folder therefore needs no
global library table, like the vendored footprints (`docs/dsl.md`, "Vendored libraries"), and ERC finds
the library copy equal to the embedded one. Three things differ from the library file a symbol came
from:

- **A derived symbol is flattened**: it gets the body of the symbol it extends and keeps its own
  properties.
- **A part with a pad map gets pad numbers.** KiCad ties a symbol pin to the pad of the same number, so
  for `Part(..., pad_map={"1": "2", "2": "1"})` the symbol is embedded as `<name>_<8 hex digits>` with
  the pad numbers on its pins. Parts with equal maps share one definition.
- **A pin bonded to several pads gets stacked pins** (change c0123). For
  `pad_map={"2": ("2", "4")}` the pin of the symbol takes the first pad, `2`, and the embedded symbol
  holds one more pin for the pad `4` at the same place, with the same name: `passive` and hidden, so the
  sheet shows one number and the symbol's pin table lists both. KiCad joins pins of one symbol that lie at
  one point, so its netlist has both pads on the pin's net, and its parity test finds the board in
  agreement. One label, or one no-connect flag, serves the pin. When such a pin is on no net, KiCad makes
  one net of its pads and names it after the pad whose number sorts first as text:
  `unconnected-(U1-Pad15)` for the pads `5`, `15` and `9` under a no-connect flag, and `Net-(D2-K-Pad17)`
  for the pads `21` and `17` of a pin named `K` without a flag; the board carries that name on each of
  those pads.
- **Hidden power input pins are shown.** KiCad puts hidden power inputs of one name on one global net,
  whatever label they carry. A shown pin connects by its label, as the script says
  (`kicad.sch.power-pin-shown`).

Only the symbols the design uses are written, never a whole library. The copies keep their library's
licence (`docs/dsl.md`, "Vendored libraries"). With `--vendor project`, a symbol from a table that is not
a project table is still embedded in the sheet but gets no project library (`build.global-library`);
KiCad then needs that global table to check the symbol. `lib/fenolite.kicad_sym` is always written when
the sheet has a power flag, and a design may not name a library `fenolite` (`build.reserved-library`).

A symbol library file for KiCad 9 must not hold tokens that only KiCad 10 reads. Building for
`--kicad-version 9` from a library saved by KiCad 10 is refused (`FEN-7001`), or, with `--allow-lossy`,
those tokens are removed (`kicad.sch.dropped-too-new`).

## The board follows the schematic

KiCad compares the board with the netlist of the schematic. Two things in the board file exist only for
that comparison, and neither is in the `.fenolite/` model or in your script:

- **Pads of unconnected pins have a net.** KiCad gives every pin on no net a net of its own, named
  after the part, the pin and the pad: `unconnected-(U1-PA1-Pad2)`, or `unconnected-(U1-Pad16)` for a
  pin without a name. The build writes those names on the pads, so the parity test reports nothing and
  "Update PCB from Schematic" has nothing to change. `fenolite check` treats such a pad as a pad on no
  net. When a pin name holds a character whose spelling in a net name was not measured, the pad stays on
  no net and the build says so (`kicad.sch.unconnected-name-unproven`).
- **Footprints carry the path of their symbol**, which KiCad uses to match a footprint to its symbol when
  it updates the board: `/<symbol uuid>` for a part of the root sheet, and
  `/<uuid of each sheet symbol from the root down>/<symbol uuid>` for a part of a module. These are the
  values of KiCad's own netlist for the symbol (`H-K-SCH-HIER-PATH`).

A net name with a slash, such as `mod/LED_A`, is stored by KiCad as `mod{slash}LED_A`, because it keeps
the slash for sheet paths. The build writes that form in the board and in the labels; KiCad shows the
name with the slash, and so does Fenolite when it reads the board.

## The netlist of the generated sheets

What the generated sheets mean electrically follows from points alone: a pin is on the net whose global
label lies on its connection point, or on the other end of the one wire that starts there; labels of one
text are one net, on every sheet; and a pin without a label is alone on a net that KiCad names after
it. Fenolite reads its own sheets this way (`backends/kicad/sch_netlist.py`), the root and every child
sheet it names, and that reading is used in two places.

- **Every build checks its own sheets.** Before any file is returned, the nets read back from the sheets
  are compared with the circuit of the script: each member of each net must be on the net of that name,
  the pad of each unconnected pin on the net written for it on the board, and every other pin alone. No
  tool runs. A difference means the generator wrote a sheet that says something other than the circuit;
  the build stops with `build.schematic-netlist-differs`, names the first net and pin, and writes
  nothing. That is a defect to report, not something to fix in the script; `--schematic skip` builds
  the board meanwhile.
- **`fenolite netlist DIR --source fenolite`** prints the components and nets of a built project
  without KiCad (`docs/cli-contract.md`, "netlist").

Fenolite reads only what it generates. A sheet with a junction or a bus, a wire that is not one
straight segment from one pin end to another (or that passes a pin, meets another wire or carries no
label), a local or hierarchical label, a sheet symbol with pins, a child sheet that is missing or named
twice, a symbol at another path than its sheet's, a symbol without an embedded definition, a label that
lies on no pin, two names on one net, several pins on one point, a power symbol other than Fenolite's
own flag, or a hidden power pin is refused (`kicad.sch.netlist-unsupported`, the reason first in the
message). For such a sheet, and for
any schematic drawn in KiCad, the netlist is KiCad's to tell: `fenolite netlist` runs
`kicad-cli sch export netlist` by default, and `fenolite check` compares that export with the model of
a built project and with the board.

On the examples and on generated designs, with and without modules, Fenolite's reading equals KiCad's
export on 9.0.9 and on 10.0.6: components, net names, pins and pin types
(`docs/evidence/kicad-schematic.md`, "Netlists" and "Hierarchy and wires").

## Placements file

Symbols are placed automatically on the sheet of their module: one cell per unit, in rows, sorted by
reference, with an IC and the parts beside it in one cell, then the sheet symbols, and the power flags
in the last row. To fix a symbol somewhere else, write `schematic-placements.toml`
beside the script:

```toml
["R1"]
x = 25.4          # the symbol origin, in millimetres, a multiple of 1.27
y = 50.8
rotation = 90     # 0, 90, 180 or 270; optional
mirror = "y"      # "x" or "y"; optional

["bank1/U1"]      # a part of a module is named by its path
x = 101.6
y = 76.2

["U2#2"]          # the second unit of U2
x = 152.4
y = 76.2
```

A position is on the sheet of the part's module. A part beside an IC pin keeps its wire only when the
file gives the IC a place too and the part exactly the place beside the pin: that is what
`fenolite sync --to-source` writes, so a build after `sync` draws the same sheet. Give the part any
other place and it gets its two labels back; place only the IC and its parts follow it.

A placed unit keeps its position and the others flow as if it were absent. Because nothing connects by
touching, a symbol placed over another one is only hard to read (`build.symbol-overlap`, a warning). Two
pins at one point would join their nets, so that is refused (`build.symbol-short`), as is a position off
the grid or an unknown key (`build.symbol-placement-invalid`). A table that names no unit of the design
is ignored with a warning (`build.symbol-placement-unknown`).

## Rebuilding

The schematic is a view of the script, generated again by every build; two builds of one script give the
same bytes. If you edit the schematic in KiCad, the next build replaces it: you get the warning
`build.schematic-replaced`, and the edited file is kept as `<name>.kicad_sch.bak` unless `--no-backup`
is given. A child sheet under `sheets/` is replaced in the same way. When a module is removed or
renamed, the sheet file of the old name is no longer named by any sheet; the build leaves it in place
and says so once (`build.sheet-stale`), because it deletes nothing. Opening and saving the sheet in KiCad also changes its bytes, so this warning does not mean
that anything was lost. Positions belong in the placements file. An edited `sym-lib-table` or symbol
library is refused like an edited vendored footprint (`build.layout-exists`; `docs/dsl.md`, "Edited
outputs").

The board keeps its layout as before (`docs/lens.md`). The first build with module sheets over a project
of v0.2a writes `sheets/` and changes the path of each footprint of a part in a module; positions,
tracks, pad nets and net names stay. A project built by an earlier version gets its
schematic on the next build; the pads of unconnected pins and nets with a slash change their names in
the board file once, and tracks and zones stay on their nets. Zone fills are kept: a pad that
only gains the name of its unconnected pin does not make a fill stale.

## Limits

- Each sheet up to A0. A sheet that does not fit is refused (`build.schematic-too-large`, which names
  it): put parts into modules, or build with `--schematic skip`.
- Only the straight wire between an IC pin and the part beside it: no bent wire, no junction.
- No hierarchical labels and no sheet pins; no sheet used twice; no buses.
- Power flags have no entry in the placements file: once every part is placed, they flow on their own.
- Edits made in the schematic are not read back.
- No command-line tool runs KiCad's "Update PCB from Schematic", so no test measures it. One manual run
  in KiCad 10.0.6 on the built blink example added the sheet name and file to each footprint and the pin
  function and type to each pad, and moved nothing. A rebuild over a board with such additions keeps
  every position and track (`H-K-SCH-UPDATE`). For a part of a module the path that the update writes
  was not measured either; the build writes the path of KiCad's netlist.
- `fenolite check` does not run KiCad's ERC yet; run `kicad-cli sch erc` on the built folder.
