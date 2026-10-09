---
topic: fabrication
title: Fabrication files, assembly tables and views
summary: export, the bill of materials, the position table, the manifest and its states, render, and what is not produced.
---

# Fabrication files, assembly tables and views

Export only a board that `fenolite check` passed, with its zones filled. `export` and `render` run
`kicad-cli` on a copy of the project (exit 6 without it), so the project folder itself never changes.
They write under the folder that `-o` names.

## export

```fenolite-cmd
fenolite export blink/build -o blink/build/fab --all --manifest --dry-run --json
fenolite export blink/build -o blink/build/fab --all --manifest --confirm --json
fenolite export blink/build -o blink/build/fab --gerbers --drill --confirm --json
fenolite export blink/build -o blink/build/fab --step --pdf --sch-pdf --confirm --json
```

| flag | files under the output folder |
|---|---|
| `--gerbers` | `gerbers/`: one Gerber file per copper, mask, paste and silkscreen layer and for the outline, and the job file |
| `--drill` | `drill/`: Excellon files, plated and non-plated holes apart, in millimetres |
| `--pos` | `pos/`: the component positions as CSV, in millimetres |
| `--ipcd356` | `netlist/`: the netlist for the electrical test |
| `--all` | the four above |
| `--ipc2581`, `--odb` | one file each, in that exchange format |
| `--step` | `3d/`: a 3D model of the board |
| `--pdf`, `--dxf` | the board, one file per layer |
| `--sch-pdf` | the schematic, every sheet |

- `--dry-run` runs the tool and shows the plan; `--confirm` writes. A call that selects no kind exits 2.
- `result.artifacts` lists each file with its kind, its size and its SHA-256.
- `--preset FILE` names a TOML file of your fabrication options for the Gerber, drill and position
  files. Fenolite ships the options of no fabricator: ask yours what it wants and write that file.
- A board without a declared stack-up gets KiCad's default one in the Gerber job file
  (`export.stackup-default`, info). Declare yours in the script (page `rules`).
- Fenolite writes no Gerber itself: the files are KiCad's, so they show the board as KiCad sees it.

## 3D models

```fenolite-cmd
fenolite models blink/build --json
```

`models` lists the 3D model files that the footprints of a board name and where each is found, without
a tool: `result.counts` gives the paths that are `located` and those that are `missing`. Read it before
`export --step`. The footprints of the built-in catalog name no model.

## The bill of materials and the position table

```fenolite-cmd
fenolite bom blink/build --json
fenolite bom blink/build --source model -o blink/build/fab/bom.csv --manifest --confirm --json
fenolite pnp blink/build --json
fenolite pnp blink/build --side top -o blink/build/fab/pnp.csv --manifest --confirm --json
```

- **`bom`** groups the parts into lines: `refs`, `quantity`, `value`, `footprint`. `--source kicad`, the
  default, takes them from the schematic through `kicad-cli`; `--source model` takes them from the
  design that `build` stored and needs no tool. `--against OTHER` also lists what changed from another
  project.
- **`pnp`** gives one row per part from the board file: reference, value, footprint, position, rotation
  and side. It runs no tool. `result.units`, `result.origin` and `result.y_axis` say how to read the
  coordinates; say them to whoever assembles the board.
- Both print the table in the reply; `-o FILE` also writes it as CSV, after `--confirm`.
- **`--template FILE`** names a column template of yours (TOML): which columns, in which order, under
  which headings. Fenolite ships the template of no assembly service: each one publishes the columns
  it wants.
- Check the rotation of polarised parts against the assembler's convention. No command can.

## Test points and fiducials

```fenolite-cmd
fenolite testpoints blink/build --json
fenolite testpoints blink/build --min-coverage 90 --min-fiducials 3 --json
fenolite testpoints blink/build -o blink/build/fab/testpoints.csv --manifest --confirm --json
```

`testpoints` reads the board file and runs no tool. It lists the pads marked `test_point` with the side a
probe reaches them from, the fiducials, the holes that are not plated, and which nets of two pads or more
have a test point. It counts marks, never names: the test points and fiducials of KiCad's library carry no
mark, and the info `testpoint.none` says so; place them with `design.test_point()` and
`design.fiducial()` (page `placement`), or mark a pad with `fab_property="test_point"` in `Footprint.pad`. Fenolite ships no target: `--min-coverage`, `--min-pitch` and `--min-fiducials` are the
user's numbers, and a missed one is an error with exit code 5. `-o` writes the rows as CSV in the frame of
the placement table.

## The manifest

```fenolite-cmd
fenolite manifest blink/build --artifacts blink/build/fab --dry-run --json
fenolite manifest blink/build --artifacts blink/build/fab --confirm --json
fenolite manifest blink/build --no-check --confirm --json
fenolite manifest blink/build --verify --json
```

`manifest` writes one file, `fenolite-artifacts.json` beside the board, that lists every design file
and every exported file with its SHA-256 and a state:

| state | meaning |
|---|---|
| `generated` | the file exists and its SHA-256 is recorded; nothing looked at it |
| `checked` | the stages `model.validate` and `copper.clearance` were `ok` for the project it belongs to, or came from |
| `roundtrip-ok` | a board or a schematic sheet that Fenolite also reads and writes back without loss |
| `native-verified` | a design file that KiCad's own check also judged `ok`, at the level `KICAD-VERIFIED` |

- The states are a ladder, and an exported file stops at `checked`: KiCad produced the Gerbers, and
  nothing judged them. The state `oracle-verified` exists and no file reaches it.
- The command runs the stages of `check` first, so it needs `kicad-cli`; `--no-check` runs none, and
  every entry is then `generated`. `result.states` counts the entries per state, and `held` of an entry
  says what its next state is missing.
- **`--artifacts DIR`** adds the files that `export`, `render`, `bom` and `pnp` listed there with
  `--manifest`. The folder must lie inside the project folder, so export into `blink/build/fab`, not
  beside the project; a folder outside it exits 2.
- **`--verify`** compares the manifest with the files on disk and writes nothing. Run it before you
  hand a folder over: a file changed after the manifest was written is reported.

## Views

```fenolite-cmd
fenolite render blink/build -o blink/views --svg --png --confirm --json
fenolite render blink/build -o blink/views --png --width 800 --height 600 --confirm --json
```

`render` writes `front.svg` and `back.svg` (plots of the copper, silkscreen and outline) and `top.png`
and `bottom.png` (rendered images). They are for looking at a board, yours or the user's; they are not
fabrication data. A view shows what no finding says: a part across the outline, a text over a pad.

## Filled and capped vias

`protection=protect(filling=True, capping=True)` asks for the vias of a stitch to be filled and capped,
as vias inside a pad often are. A KiCad 9 board holds tenting only, so this block builds for target 10:
target 9 exits 7. `fenolite inspect` counts the protected vias (`result.via_protection`).

```fenolite-design kicad10
from fenolite.dsl import Design, Net, Part, connect, mm, protect

design = Design("filled")
design.board(mm(20), mm(15))
j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="PWR")
d1 = Part("D1", "Fenolite:LED", footprint="Fenolite:Chip_0603", value="LED")
design.add(j1, d1)
vin, gnd = Net("VIN"), Net("GND")
connect(vin, j1[1], d1[1])
connect(gnd, j1[2], d1[2])
j1.place(mm(5), mm(7))
d1.place(mm(14), mm(7))
# Vias inside pad 2 of D1, filled and capped.
design.stitch(
    "d1_vias", net=gnd, pitch=mm(1), region=d1.pad(2), diameter=mm(0.6), drill=mm(0.3), clearance=mm(0.2),
    protection=protect(filling=True, capping=True),
)
```

## What is not produced

- No panel: the files hold one board.
- No order: no command talks to a fabricator or an assembler.
- No judgement that a board can be made. `check` holds the board against the rules of the script, and
  those are as good as the limits you were given.

Read next: `checks`, `files`, `altium`.
