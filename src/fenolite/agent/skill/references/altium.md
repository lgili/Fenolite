---
topic: altium
title: Building for Altium Designer
summary: build --target altium, what it writes, the status of each written file kind as capabilities reports it, and the kit that a person runs.
---

# Building for Altium Designer

`fenolite build --target altium` generates an Altium project without Altium installed. A person must
open and verify it in Altium Designer.

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

Read every `altium.not-lowered` issue in the dry run. Its `where` names what could not be written.
A `track_width` minimum needs a maximum too: use `design.rules.rule(...)` with all limits (page `rules`).

## The status of each file kind

This table matches `fenolite capabilities --json`. `write_kinds` means listed in the Altium entry of
`result.backends`; `experimental` means the write in `result.matrix` remains experimental. Outputs,
options and issue codes may change. Evidence comes from the matrix's `write` row.

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

Report each file kind's status and evidence. `INFERRED` means no tool judged it; check again after upgrades.

## Checking an Altium project without Altium

```fenolite-cmd
fenolite check blink/altium --json
fenolite parity blink/altium --json
fenolite inspect blink/altium/lamp.PcbDoc --json
fenolite equivalent blink/build blink/altium/lamp.PrjPcb --level 2 --json
```

- `check` checks the model, electrical rules, copper, parity and round trips through Fenolite's reader,
  with `INFERRED` evidence. It replaces no native Altium check.
- `equivalent --level 2` compares circuits across backends (page `files`).

## Keep native schematic presentation

After a person organises and saves the generated sheets in Altium, capture them beside the script:

```fenolite-cmd
fenolite sync blink/design.py --out blink/altium --target altium --to-source --dry-run --json
fenolite sync blink/design.py --out blink/altium --target altium --to-source --confirm --json
```

Keep `altium-schematic-layout.json` with the source: build replays its native bytes. Changed saved sheets,
including added parts, give `build.altium-layout-conflict`. Sync refuses electrical or symbol differences
(`sync.altium-connectivity-changed`) and unresolved inputs (`sync.altium-unverified`). Evidence: `INFERRED`.
`--discard-layout` cannot bypass the snapshot. Archive it and build elsewhere to deliberately start again.

## The verification kit is a person's run

The Altium verification kit is a run that a person performs in Altium Designer. Build the samples and
inspect the results; an agent cannot perform that native run.

```fenolite-cmd
fenolite kit build --out kit --dry-run --json
fenolite kit build --out kit --confirm --json
fenolite kit verify kit --json
fenolite kit status --json
```

- `kit build` writes the kit and instructions for that person.
- `kit verify DIR` checks the run results; exit 3 means the folder is no kit.
- `kit status` lists recorded runs; `kit record` adds one in Fenolite's repository.
- Until a native run is reported, describe the project as built and not opened.

Read next: `files`, `rules`, `checks`.
