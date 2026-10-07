---
topic: altium
title: Building for Altium Designer
summary: build --target altium, what it writes, the status of each written file kind as capabilities reports it, and the kit that a person runs.
---

# Building for Altium Designer

`fenolite build --target altium` builds the same design script into an Altium Designer project instead
of a KiCad one. Nothing of Altium is needed to build, and nothing of Fenolite can open the result in
Altium: only a person with Altium Designer can say that it opens.

## A script and its build

```fenolite-design altium
from fenolite.dsl import Design, Net, Part, Power, connect, mm

design = Design("lamp")
design.board(mm(30), mm(20))
design.rules.minimum(clearance=mm(0.2), edge_clearance=mm(0.3))  # examples

j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="IN")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="330")
d1 = Part("D1", "Fenolite:LED", footprint="Fenolite:Chip_0603", value="RED")
design.add(j1, r1, d1)

vin, anode, gnd = Net("VIN"), Net("ANODE"), Net("GND")
design.add(Power(vin, gnd))  # a supply: the schematic draws its two nets as power ports
connect(vin, j1[1], r1[1])
connect(anode, r1[2], d1[1])
connect(gnd, d1[2], j1[2])

j1.place(mm(6), mm(9))
r1.place(mm(15), mm(14))
d1.place(mm(15), mm(6), rot=180)
```

```fenolite-cmd
fenolite build blink/design.py --out blink/altium --target altium --dry-run --json
fenolite build blink/design.py --out blink/altium --target altium --confirm --json
fenolite build blink/design.py --out blink/altium --target altium --altium-format ascii --confirm --json
fenolite build blink/design.py --out blink/altium --target altium --copper-from blink/build/blink.kicad_pcb --confirm --json
```

## What it writes

For a design named `lamp`, under `--out`:

- `lamp.PrjPcb`, the project file;
- `lamp.SchDoc`, the schematic, and `lamp.SchLib`, the symbols it uses;
- `lamp.PcbDoc`, the board with the outline, the placed footprints, their nets and the rules that Altium
  holds, and `lamp.PcbLib`, the footprints;
- `lamp.OutJob`, an output job, unless `--altium-outjob off`;
- `.fenolite/`, the design as data, as in a KiCad build.

Options: `--altium-format ascii` writes the schematic in Altium's text form instead of its binary form;
`--altium-sheets modules` gives each top-level module a sheet of its own, and draws a `Harness` as a
signal harness; `--copper-from BOARD.kicad_pcb` copies the tracks, vias and zones of a routed KiCad
board of the same design into the PCB document. `--kicad-version` and `--allow-lossy` change nothing
here.

What Altium cannot hold in the form the design gives it is not dropped in silence: each case is one
`altium.not-lowered` issue whose `where` names it. A board minimum for `track_width`, for example, is a
warning, because Altium's width rule also needs a maximum; declare such a rule with
`design.rules.rule(...)` and all its limits (page `rules`). Read every issue of the dry run.

## The status of each file kind

This table repeats `fenolite capabilities --json`; a test fails when the two differ. The status
`write_kinds` means the kind is listed in `write_kinds` of the Altium entry of `result.backends`. The
status `experimental` means it is not, and that `result.matrix` marks its write as `experimental`: its
output, its options and its issue codes may change in any release. The evidence is the level of
`write` in the kind's row of `result.matrix`.

| kind | file | status | evidence |
|---|---|---|---|
| `altium_harness` | `.Harness` | `experimental` | `INFERRED` |
| `altium_outjob` | `.OutJob` | `experimental` | `INFERRED` |
| `altium_pcbdoc` | `.PcbDoc` | `experimental` | `INFERRED` |
| `altium_pcblib` | `.PcbLib` | `experimental` | `INFERRED` |
| `altium_prjpcb` | `.PrjPcb` | `experimental` | `INFERRED` |
| `altium_schdoc_ascii` | `.SchDoc`, text form | `experimental` | `INFERRED` |
| `altium_schdoc_binary` | `.SchDoc`, binary form | `experimental` | `INFERRED` |
| `altium_schdot` | `.SchDot`, from `fenolite template` | `experimental` | `INFERRED` |
| `altium_schlib` | `.SchLib` | `experimental` | `INFERRED` |

`INFERRED` means that no tool judged the file. Say the status and the level of each kind you hand
over, and read them again after an upgrade of Fenolite: they change from release to release.

## Checking an Altium project without Altium

```fenolite-cmd
fenolite check blink/altium --json
fenolite parity blink/altium --json
fenolite inspect blink/altium/lamp.PcbDoc --json
fenolite equivalent blink/build blink/altium/lamp.PrjPcb --level 2 --json
```

- `check` on an Altium project runs Fenolite's own stages and no tool: the design as data, a light
  electrical check, shorts and clearances of the copper, the parity of schematic and board, and the
  round trips. Its evidence is Fenolite's own reading, `INFERRED`.
- `equivalent` compares the Altium project with the KiCad build of the same script (page `files`):
  `--level 2` asks whether both hold the same circuit.
- None of this replaces opening the project in Altium Designer.

## The verification kit is a person's run

The Altium verification kit is a run that a person performs in Altium Designer: a folder of sample
projects with a script that Altium executes, which opens each one and writes down what it found. You
can build the kit and judge the files a run left. You cannot perform the run.

```fenolite-cmd
fenolite kit build --out kit --dry-run --json
fenolite kit build --out kit --confirm --json
fenolite kit verify kit --json
fenolite kit status --json
```

- `kit build` writes the kit folder. Hand it to a person who has Altium Designer, with its
  instructions.
- `kit verify DIR` judges the files that a run left in the folder, and exits 3 for a folder that is
  not a kit.
- `kit status` lists the runs a repository has recorded; `kit record` adds one, in the repository of
  Fenolite itself.
- Until a person has run the kit on the release you use, report an Altium project as built and not
  opened.

Read next: `files`, `rules`, `checks`.
