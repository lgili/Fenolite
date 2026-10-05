# The schematic of a built project

`fenolite build` writes a KiCad schematic beside the board: `<name>.kicad_sch`, the symbol libraries it
uses under `lib/`, and `sym-lib-table`. KiCad can then run its electrical rules check (ERC) on the
project, compare the board with the schematic (the parity test of its DRC), and export a netlist and a
bill of materials. The facts behind this page are in `docs/formats/kicad/schematic.md` ("Generated
sheets"), and the measurements on KiCad 9.0.9 and 10.0.6 in `docs/evidence/kicad-schematic.md`.

The schematic is correct, not pretty. It is one flat sheet without wires; a readable drawing and one
sheet per module are planned for a later release (v0.2b).

```sh
fenolite build design.py --out build/blink --confirm            # board, project, rules and schematic
fenolite build design.py --out build/blink --schematic skip --confirm    # as before: no schematic
```

`--schematic` is an option of the KiCad target; `--target altium` writes its own schematic
(`docs/altium.md`).

## What the sheet holds

- **One symbol per unit.** Every unit of every part's symbol is placed, also the units you connect
  nothing to, because KiCad's ERC reports a symbol with units missing. A part without a symbol (a
  footprint that exists only on the board) gets none.
- **Global labels instead of wires.** Each connected pin carries a global label with the name of its
  net. KiCad joins pins by the label text, so no wire is drawn and no symbol position can break a
  connection.
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
  it updates the board.

A net name with a slash, such as `mod/LED_A`, is stored by KiCad as `mod{slash}LED_A`, because it keeps
the slash for sheet paths. The build writes that form in the board and in the labels; KiCad shows the
name with the slash, and so does Fenolite when it reads the board.

## Placements file

Symbols are placed automatically: one cell per unit, in rows, sorted by module and by reference, with
the power flags in the last row. To fix a symbol somewhere else, write `schematic-placements.toml`
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

A placed unit keeps its position and the others flow as if it were absent. Because nothing connects by
touching, a symbol placed over another one is only hard to read (`build.symbol-overlap`, a warning). Two
pins at one point would join their nets, so that is refused (`build.symbol-short`), as is a position off
the grid or an unknown key (`build.symbol-placement-invalid`). A table that names no unit of the design
is ignored with a warning (`build.symbol-placement-unknown`).

## Rebuilding

The schematic is a view of the script, generated again by every build; two builds of one script give the
same bytes. If you edit the schematic in KiCad, the next build replaces it: you get the warning
`build.schematic-replaced`, and the edited file is kept as `<name>.kicad_sch.bak` unless `--no-backup`
is given. Opening and saving the sheet in KiCad also changes its bytes, so this warning does not mean
that anything was lost. Positions belong in the placements file. An edited `sym-lib-table` or symbol
library is refused like an edited vendored footprint (`build.layout-exists`; `docs/dsl.md`, "Edited
outputs").

The board keeps its layout as before (`docs/lens.md`). A project built by an earlier version gets its
schematic on the next build; the pads of unconnected pins and nets with a slash change their names in
the board file once, and tracks and zones stay on their nets. Zone fills are kept: a pad that
only gains the name of its unconnected pin does not make a fill stale.

## Limits

- One sheet, up to A0. A design that does not fit is refused (`build.schematic-too-large`); build with
  `--schematic skip` until sheets per module exist.
- No wires, no hierarchy, no buses, no drawing sheet of its own.
- Edits made in the schematic are not read back.
- No command-line tool runs KiCad's "Update PCB from Schematic", so no test measures it. One manual run
  in KiCad 10.0.6 on the built blink example added the sheet name and file to each footprint and the pin
  function and type to each pad, and moved nothing. A rebuild over a board with such additions keeps
  every position and track (`H-K-SCH-UPDATE`).
- `fenolite check` does not run KiCad's ERC yet; run `kicad-cli sch erc` on the built folder.
