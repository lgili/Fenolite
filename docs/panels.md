# Panels: several copies of one board

A fabricator or an assembler often wants a board delivered as a panel: several copies in rows and columns,
held together by V-score lines or by tabs with mouse bites, with rails that carry fiducials and tooling
holes. `fenolite panel` makes such a panel from a board you already built (change c0173). It writes a KiCad
panel board, or an Altium panel document, and checks the panel against public fabricator figures before it
writes anything.

The normative text is the openspec capability `board-panels` (and "Panel command" of `cli-contract`); the
command's reference is `docs/cli-contract.md`, "panel"; the facts and their sources are in
`docs/formats/kicad/panel.md`, `docs/formats/kicad/gerber.md` ("Panels") and
`docs/formats/altium/pcb-document.md` ("Embedded board arrays").

**Fabricators differ.** Every default below cites the public page it comes from, and every one can be
replaced by your fabricator's figure (`limits=`, "Checks and limits"). Confirm the panel with your
fabricator before you order it: Fenolite ships no fabricator's preset and talks to no fabricator.

## The panel script

A panel is a script of its own that names a **built** board (routed and filled), never a design script: the
panel repeats copper that only the board file holds.

```python
from fenolite.dsl import Panel, mm

panel = Panel("blink_panel", board="../blink/out/blink.kicad_pcb")
panel.grid(2, 4)
panel.rails(top=mm(5), bottom=mm(5))
panel.separate("vscore", between="rows")
panel.separate("tabs", between="columns")
panel.fiducials()
panel.tooling_holes()
```

- `Panel(name, *, board, limits=None)`. `name` is letters, digits, `_` and `-`; it names the output files.
  `board` is a path relative to the script: a `.kicad_pcb` (any target) or a `.PcbDoc` built with
  `fenolite build --target altium` (`--target altium` only). An absolute path is refused.
- The script binds `panel` at module level. A script that raises, or binds no `panel`, is `FEN-3004`.
- Lengths are `mm()` values or strings with a unit; angles are degrees. Coordinates are relative to the
  panel: the origin is the panel's top-left corner and Y points down, as in `board()` of a design script.
- Every bad value raises `DslError` at the call, naming the argument, and records nothing.

| call | what it does | defaults |
|---|---|---|
| `grid(rows, cols, *, gap=None, gap_x=None, gap_y=None, rot=0, mirror=False)` | `rows` × `cols` copies; `gap`, or `gap_x` between columns and `gap_y` between rows, is the routed gap of a tabbed edge set; `rot` turns every copy by 0, 90, 180 or 270 degrees | gap 2 mm (S-0798) |
| `fit(width, height, *, gap=None, rot=0)` | as many copies as `width` × `height` holds ("fit()" below) | gap 2 mm |
| `rails(*, top=None, bottom=None, left=0, right=0)` | rails of these widths; `0` is no rail | top and bottom 5 mm when called (S-0798); no rail without the call |
| `separate(method, *, between)` | separates the edge set `between` (`"columns"`, `"rows"` or `"rails"`) by `method`, `"vscore"` or `"tabs"`; each set once | a set left unnamed is tabbed |
| `tabs(*, width=None, pitch=None, drill=None, hole_gap=None, holes=5, inset=0)` | the tabs of every routed edge | width 5 mm, pitch 55 mm, drill 0.6 mm, hole gap 0.4 mm, 5 holes, tangent (S-0795, S-0793) |
| `vscore(*, clearance=None, layer="V-Score", line_width=None)` | the score lines | clearance 0.45 mm (S-0799), line width 0.1 mm |
| `fiducial(ref, x, y, *, copper=None, mask=None, side="top")` | one fiducial at `(x, y)` | copper 1 mm, mask opening 2 mm (S-0797) |
| `fiducials(*, copper=None, mask=None, sides=("top",))` | three fiducials in an L on the rails per side, refs `PFID<n>` | as `fiducial()` |
| `tooling_hole(ref, x, y, *, drill=None)` | one non-plated tooling hole at `(x, y)` | drill 3 mm (S-0800) |
| `tooling_holes(*, drill=None)` | four tooling holes at the corners of the rails, refs `PTH<n>` | drill 3 mm |

The copies are arranged once, by `grid()` or by `fit()`; a second call raises. A fiducial or tooling hole
`ref` is used once.

### grid()

`grid(2, 4)` gives 2 rows of 4 copies. Rows count from 1 at the top and columns from 1 at the left; copy
`k = (row − 1) · cols + col`. With `rot=90` every copy is turned a quarter turn, exactly (integer
nanometres, nothing rounded). `mirror=True` is Altium's Mirrored property of an Embedded Board Array: no
form that this release writes holds it, so `fenolite panel` refuses it with exit 7.

### fit()

`fit(width, height)` takes as many copies as the size holds. With `U` the width inside the rails (less the
rail gaps when the rails are tabbed), `b` the board's width after the turn and `g` the gap between columns:

```text
cols = ⌊(U + g) / (b + g)⌋        rows likewise, with the heights
```

`rot="auto"` takes the quarter turn that holds more copies, 0° on a tie. Zero copies is `panel.no-fit`
(error). The panel then has the size of what it holds, not the asked size: `result.panel.unused` gives the
rest (`w`, `h` in nanometres), and `rails()` can take it up if you want the asked size.

## The three separations

Each of the three edge sets (`columns`, `rows`, `rails`) is separated by V-score or by tabs; a panel may mix
them, for example scored between rows and tabbed between columns.

### V-score

The boards of a V-scored edge set touch: there is no gap (S-0796, S-0798). One straight score line runs per
scored boundary, from panel edge to panel edge (S-0794, S-0801). V-score is for straight edges only (S-0791,
S-0801), which the rectangular boards of this release have; a gap asked for a scored edge set is
`panel.vscore-shape` (error), because scored boards touch. Copper is kept
`clearance` (0.45 mm, S-0799) from each line on every layer (`panel.vscore-copper`).

In the KiCad panel board the lines are `gr_line` items `line_width` wide on a user layer whose user name is
`layer` (`V-Score` by default); `result.panel.score_layer` names that layer (`User.1` on the fixture
`mixed.py`). In the flattened Altium panel they are lines on Mechanical 2, named `V-Cut`.

### Tabs with mouse bites

A tabbed edge set has a routed gap (`gap`, 2 mm by default) bridged by tabs. Along each tabbed edge of length
`L`, `n = max(1, ⌈L / pitch⌉)` tabs sit at `(i + ½)·L/n`, each `width` wide. A tab between two boards carries
a row of `holes` holes of `drill` at each board's edge; a tab to a rail carries one row, at the board's edge,
and none on the rail's side (S-0795). The holes are `drill + hole_gap` apart, tangent to the board's edge
outside it (`inset=0`, the least intrusive, S-0793), or reaching `inset` into the board, at most a third of
the drill (S-0795).

In the KiCad panel board each row of holes is one generated footprint
`Fenolite_Panel:MouseBites_<n>x<d>mm_P<p>mm` of unnumbered `np_thru_hole` pads, ref `MB<k>`, written under
`lib/Fenolite_Panel.pretty/`. In the flattened Altium panel they are free round non-plated pads.

### Rails with fiducials and tooling holes

`rails()` adds a frame. Between rails and copies the `rails` edge set decides: V-score lets the copies touch
the rail, tabs leave the gap. `fiducials()` puts three fiducials in an L on a pair of rails (top and bottom
when both exist, else left and right), 10 mm from the panel's sides, their centres at least 3.85 mm from
the panel's edge (S-0794) or on the rail's middle line when that is further, and their mask opening within
the rail. `tooling_holes()` puts four holes on the same pair of rails, 5 mm from
the panel's sides, in the rails' middle. The 10 mm and 5 mm are Fenolite's choices. Without a pair of rails
neither call places anything, and a `panel.fiducial-place` or `panel.tooling-place` warning says so; place
them yourself with `fiducial(ref, x, y)` and `tooling_hole(ref, x, y)`.

In KiCad the fiducials and tooling holes are the generated footprints of `design.fiducial()` and
`design.tooling_hole()` (`docs/dsl.md`, "Assembly and test features (c0118)"), written under
`lib/Fenolite_Assembly.pretty/`. In the flattened Altium panel a fiducial is a free round copper pad on the
Top (or Bottom) Layer marked `fiducial_global`, with the mask opening of the rule, and a tooling hole is a
free round non-plated pad. Altium's page names only tooling holes as acceptable free pads on a panel
(S-0791): whether the free fiducial pads reach Altium's outputs is a case of the maintainer's kit (Q9).

## Copies

Every copy holds every item of the source board, moved by an exact integer translation after its quarter
turn. Each copy's nets are renamed `B<k>/<name>`, so KiCad's DRC does not join the nets of different copies
(`H-K-PANEL-NETS`); a renamed net equal to another is `panel.net-collision` (error). Designators stay as
they are, so each copy reads like the board it is. The copies' own outline edges are dropped: the panel's
outline replaces them.

**Rectangular boards only.** This release panels a board whose outline is one rectangle; any other outline,
or a board without a closed outline, is `panel.board-outline` (error). The routed gaps are found exactly on
the grid of the rectangles' coordinates, with no extra package.

## Checks and limits

The checks run before anything is planned. An error plans no write: exit 5 (`FEN-5001`) with the findings in
`issues`. `fenolite explain <code>` gives each code's meaning and fix.

| code | severity | rule (default) | source |
|---|---|---|---|
| `panel.vscore-copper` | error | copper of any layer nearer than 0.45 mm to a score line | S-0799 (S-0794: 0.4 mm) |
| `panel.vscore-shape` | error | a gap is asked for a scored edge set: scored boards touch | S-0791, S-0796, S-0801 |
| `panel.vscore-spacing` | error, warning | parallel score lines nearer than 2 mm (error) or 5 mm (warning) | S-0796; S-0798, S-0801 |
| `panel.vscore-thickness` | error, warning, info | board thickness below 0.6 mm (error), below 0.8 mm (warning), unknown (info) | S-0794, S-0801 |
| `panel.tab-copper` | error | copper nearer than 0.25 mm (outer layers) or 0.40 mm (inner layers) to a mouse-bite hole | S-0799 |
| `panel.gap` | error, warning | a routed gap below 1.2 mm (error) or 2.0 mm (warning) | S-0795, S-0798 |
| `panel.tab-count` | error, warning | a copy held by no tab and no score line (error); fewer than 5 holes per row, or a copy held by one tab only (warning) | S-0795 |
| `panel.tab-spacing` | warning | tabs more than 60 mm apart along an edge | S-0795 |
| `panel.fiducial-place` | warning | a fiducial off the rails, its centre nearer than 3.85 mm to the panel's edge, or fewer than three on an assembled side | S-0794, S-0796, S-0797 |
| `panel.tooling-place` | warning | a tooling hole not wholly on a rail | S-0800 |
| `panel.size` | warning | a side under 50 mm or above 250 mm, or a scored panel under 70 × 70 mm | S-0800, S-0795, S-0794 |
| `panel.board-outline` | error | the board's outline is not one closed rectangle | — |
| `panel.no-fit` | error | `fit()` holds no copy | — |
| `panel.net-collision` | error | a renamed net equals another net | — |
| `panel.altium-cutout` | error | a copy with cut-outs or slots in a flattened Altium panel (Altium's board cut-out regions are behind their own gate, change c0168) | — |
| `panel.source-unreachable` | error | the document an Embedded Board Array references has no path relative to the panel (the array only) | — |
| `panel.output-changed` | error | a file a previous run wrote was edited since ("Writing" below) | — |
| `altium.panel-flattened` | info | the Altium panel is written flattened, with the reason | — |

The copper checks judge each copy in its own frame, with the copper shapes of `fenolite check` (tracks, arcs,
vias, pads and zone fills on every copper layer) and the exact distance of two thick shapes. The board's
thickness is its stack-up's, else the file's `(general (thickness …))`.

**Defaults and their sources.** `fenolite.panel.limits.DEFAULTS` holds one default per limit, each naming
its row of `docs/formats/kicad/panel.md`, the sources of that row and the figure it equals
(`H-G-PANEL-LIMITS`). Where two fabricators publish different figures, the stricter one is the error and the
other the warning. No figure comes from a panelisation tool (KiKit, S-0802, is prior art only).

| limit | default | source |
|---|---|---|
| `vscore_copper` | 0.45 mm | S-0799 |
| `vscore_spacing`, `vscore_spacing_warn` | 2 mm, 5 mm | S-0796; S-0798, S-0801 |
| `vscore_thickness`, `vscore_thickness_warn` | 0.6 mm, 0.8 mm | S-0794; S-0801 |
| `tab_copper_outer`, `tab_copper_inner` | 0.25 mm, 0.40 mm | S-0799 |
| `gap`, `gap_warn` | 1.2 mm, 2 mm | S-0795; S-0798 |
| `tab_holes` | 5 (a count) | S-0795 |
| `tab_spacing` | 60 mm | S-0795 |
| `fiducial_edge` | 3.85 mm | S-0794 |
| `fiducial_count` | 3 (a count) | S-0797 |
| `size_min`, `size_max`, `vscore_size_min` | 50 mm, 250 mm, 70 mm | S-0800; S-0795; S-0794 |

`Panel(name, board=…, limits={"gap": mm(1.6), "tab_holes": 6})` replaces any of them; a length takes a unit,
the two counts take a whole number, and any other name raises `DslError`. The tab width (5 mm) and pitch
(55 mm) are Fenolite's choices, not limits: a row of five 0.6 mm holes fits in 5 mm, and 55 mm is the middle
of S-0795's 50 to 60 mm.

## The command

```bash
fenolite panel blink_panel.py --out panel --target 10 --dry-run --json
fenolite panel blink_panel.py --out panel --target 10 --confirm --plan <result.plan_id> --json
```

`fenolite panel PANEL.py --out DIR --target {9,10,altium} [--altium-panel {auto,embedded,flat}]
[--discard-layout]` runs the panel script in-process, as `build` runs a design script, reads the board it
names, lays the panel out, checks it, and plans every file under `DIR`.

- `--target 9` or `10` is the KiCad major the board was built for; a board written for another major, or a
  `.PcbDoc` board, is a usage error (exit 2). `--altium-panel` with a KiCad target is exit 2 too.
- `--target altium` writes the Altium panel ("The Altium panel").
- **Writing.** `--dry-run` plans; `--confirm` writes every file or none, and records the SHA-256 of each in
  `.fenolite/<name>.panel-written.json`. A later run refuses a file edited since (`panel.output-changed`,
  exit 5) unless `--discard-layout` replaces it (a `.bak` copy is kept).
- **The reply.** `result.panel` holds `target`, `form` (`kicad`, `flat` or `embedded`), `rows`, `cols`,
  `copies`, `rotation`, `size`, `unused`, `separations`, `items` (counts of tabs, mouse-bite rows and holes,
  score lines, fiducials and tooling holes) and `score_layer`; `result.files` lists the planned files.
- **Exit codes.** 0; 2 usage; 3 (`FEN-3001`) a missing script or board, (`FEN-3004`) a script that raises
  or binds no `panel`; 4 (`FEN-4001`, `FEN-4002`); 5 (`FEN-5001`) error findings; 7 (`FEN-7001`)
  `--altium-panel embedded` while the gate is off, and `mirror=True`.

Pass `--seed` and `--timestamp` as for every writing command when you need byte-identical files; the panel
of a script and a board is the same bytes on every run.

## The KiCad panel board

`--target 9` or `10` writes:

| file | content |
|---|---|
| `<name>.kicad_pcb` | the panel board: the copies, the panel's outline on `Edge.Cuts` (its outer ring, and every routed gap less its tabs as an inner ring), the score lines, the mouse-bite, fiducial and tooling-hole footprints |
| `<name>.kicad_pro` | the source board's own project, with its net-class patterns turned into `B*/<pattern>`, or a synthesized one |
| `<name>.kicad_dru` | a copy of the source board's rules file, when one lies beside it |
| `lib/Fenolite_Panel.pretty/*.kicad_mod`, `lib/Fenolite_Assembly.pretty/*.kicad_mod`, `fp-lib-table` | the generated footprints the panel uses, and the table that names them |
| `<name>.panel.json` | the model panel with the SHA-256 of its board (schema `schemas/fenolite.model.v0/panel.json`) |

The panel board is `KICAD-VERIFIED (9.0.x, 10.0.x)`: on the three fixture panels of `tests/data/panels/` it
loads with no outline error, its DRC gives each copy the source board's own findings and nothing between
copies, and its mouse-bite and tooling holes reach the NPTH drill file at their places (`H-K-PANEL-LOAD`,
`H-K-PANEL-NETS`, `H-K-PANEL-DRILL`). Check and export it as any board: `fenolite check`, then
`fenolite export --gerbers --drill`. The panel checks themselves run in `fenolite panel`.

**Tell your fabricator about the V-score file.** `fenolite export --gerbers` of a panel board plots the user
layer whose user name is `V-Score` as its own Gerber file, between the silkscreen and `Edge.Cuts`
(`docs/exports.md`). `kicad-cli` 9.0.9 and 10.0.6 give that file the file function `Other,User`, not the
Gerber function `Vcut` (`H-K-PANEL-GERBER`), and Fenolite never edits a file `kicad-cli` wrote: the file
holds exactly the score lines, but a fabricator's tool will not recognise it as V-score by itself. Name the
file in your order. A score layer given another name with `vscore(layer=…)` is not added to the export.

## The Altium panel

Altium's native panel is the **Embedded Board Array**: a panel document that references the board's
`.PcbDoc` and repeats it in rows and columns (S-0790, S-0791). Its records are not stated by any public page
(KiCad's importer lists the storage `EmbeddedBoards6` as not imported, S-0002, and no public document of the
corpus holds an array), so Fenolite writes one only after the maintainer's kit has shown the written file in
Altium Designer. Until then `--target altium` writes the flattened panel.

### The flattened panel (what ships)

`--target altium` (`--altium-panel auto` or `flat`) writes `<name>.PcbDoc`, `<name>.PrjPcb` holding the panel
document alone, and `<name>.panel.json`, with one `altium.panel-flattened` info naming the reason. The
document holds every copy's items like the KiCad panel board (nets `B<k>/<name>`, designators kept); its board
shape is the panel's rectangle; the routed gaps are lines on Mechanical 1 named `Route Tool Path` and the
score lines on Mechanical 2 named `V-Cut`, without a layer type (S-0792: older versions find routing data by
the layer's name; where a type is stored is measured by the kit, `H-A-PANEL-LAYERKIND`); mouse-bite and
tooling holes are free round non-plated pads; fiducials are free round copper pads. The source may be a
`.kicad_pcb` or a `.PcbDoc`. A copy with cut-outs or slots is `panel.altium-cutout` (error).

Its level is `ORACLE-VERIFIED(kicad-cli)` (10.0.6): KiCad's importer reads the flattened panels of the
fixtures with every pad, track, via, route and score line at the KiCad panel's places within 10 nm
(`H-A-PANEL-FLAT`). That KiCad reads it is not that Altium opens it: Altium's view of it is case Q11 of the
kit.

### The Embedded Board Array (behind its gate)

`--altium-panel embedded` asks for the array. It is refused with exit 7 (`FEN-7001`, hint
`--altium-panel flat`) while `pcbdoc.EMBEDDED_ARRAYS = False`, and for a `.kicad_pcb` board (an array
references a `.PcbDoc`). The gate is a constant, not an option: it opens only when the maintainer reports
cases Q7, Q8 and Q9 of Part Q (`docs/evidence/altium-pcb.md`) as passed in Altium Designer 26.5. Until then
nothing about the array is claimed: its rows are `UNKNOWN` or `INFERRED` (`H-A-PANEL-RECORD`,
`H-A-PANEL-LAYERKIND`, `H-A-PANEL-KIT`). If the records cannot be tied to what Fenolite sets, the attempt
stops (the stop rules of the change's design) and the flattened panel stays what ships. An Altium user can
still place an array by hand on the board.

The outputs of an Altium panel (Gerber, NC drill) are Altium's: `fenolite export` does not run Altium.

## What a panel is not

- Several different boards in one panel, nested arrays, arbitrary angles, jump scoring, and a mirrored KiCad
  copy.
- Assembly outputs of a panel: `pnp`, `bom` and `testpoints` stay per board.
- A run of a panelisation tool: Fenolite runs and imports none.
- An order: confirm every figure with your fabricator.
