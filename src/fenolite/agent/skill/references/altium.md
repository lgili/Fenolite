---
topic: altium
title: Building for Altium Designer
summary: Altium builds, blocks, native sync, evidence and the verification kit.
---

# Building for Altium Designer

`build --target altium` flags the experimental kinds (`altium.experimental`); `capabilities` lists `missing` proofs.

For a model already in memory, `fenolite.lens.altium.write_model(design, pour="outline")` selects the
backend's unpoured compatibility mode. Omit `pour` to keep its computed default and missing-extra
fallback, or use `pour="computed"` to require the geo extra. Historical outline measurements do not
verify computed-pour equivalence.

## A script and its build

```fenolite-design altium
from fenolite.dsl import Design, Net, Part, Power, connect, mm, schematic_composition

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

design.schematic_layout(mode="blocks", flow="left-to-right")
design.schematic_block("input", members=[j1], title="Input")
design.schematic_block("lamp", members=[r1, d1], after="input")
assert schematic_composition(design) is not None

j1.place(mm(6), mm(9))
r1.place(mm(15), mm(14))
d1.place(mm(15), mm(6), rot=180)
```

```fenolite-cmd
fenolite build blink/design.py --out blink/altium --target altium --dry-run --json
fenolite build blink/design.py --out blink/altium --target altium --altium-layout blocks --dry-run --json
fenolite build blink/design.py --out blink/altium --target altium --confirm --json
fenolite build blink/design.py --out blink/altium --target altium --copper-from blink/build/blink.kicad_pcb --confirm --json
```

## What it writes

Under `--out`: `lamp.PrjPcb`, `.SchDoc`, `.SchLib`, `.PcbDoc`, `.PcbLib` (board files need board
content), `lamp.OutJob` (unless `--altium-outjob off`) and `.fenolite/`.

`--altium-template FILE.SchDot` applies a native sheet template (binary only, no `drawing_sheet`);
see `result.native_template`.

`--altium-format ascii` writes text, not binary. `--altium-sheets modules` splits sheets
and draws `Harness` interfaces. `--copper-from BOARD.kicad_pcb` copies routed copper.

Polygons are poured by Fenolite with Altium's rules (`--altium-pour computed`, the default; needs
`fenolite[geo]`); `altium.zones-poured` marks that copper experimental, and Repour All in Altium gives
Altium's own. `altium.zone-unpoured` names a polygon left unpoured; `--altium-pour outline` pours none.

Read `altium.not-lowered` locators. A `track_width` rule needs both limits (page `rules`).

## The status of each file kind

It matches `capabilities` (`result.backends`, `result.matrix`).

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

## Checking an Altium project without Altium

```fenolite-cmd
fenolite check blink/altium --json
fenolite parity blink/altium --json
fenolite inspect blink/altium/lamp.PcbDoc --json
fenolite equivalent blink/build blink/altium/lamp.PrjPcb --level 2 --json
```

`check` measures model/ERC/copper/parity/readback with `INFERRED` evidence; run native checks too.
`equivalent --level 2` compares circuits (page `files`).

## Keep native schematic presentation

Review `result.schematic_composition` and its SVGs (`INFERRED`). Groups follow blocks, modules,
signals. `composition.<code>`: `invalid-intent` fix members/order; `overflow` larger paper or smaller
blocks; `budget-exhausted` less congestion; `overlap` separate units; `template-unverified` bounded
template; `transform-unsupported` supported geometry; `label-fallback` inspect labelled endpoints;
`connectivity-changed` keep files, report. SVGs show the base.

Capture saved Altium edits beside the script:

```fenolite-cmd
fenolite sync blink/design.py --out blink/altium --target altium --to-source --dry-run --json
fenolite sync blink/design.py --out blink/altium --target altium --to-source --confirm --json
```

Keep `altium-schematic-layout.json`: build replays native bytes; changed sheets give
`build.altium-layout-conflict`. Sync refuses electrical or symbol differences
(`sync.altium-connectivity-changed`) and unresolved inputs (`sync.altium-unverified`). Evidence: `INFERRED`.
`--discard-layout` cannot bypass the snapshot; archive it to start again.

## The verification kit is a person's run

The Altium verification kit is a run that a person performs in Altium Designer.

```fenolite-cmd
fenolite kit build --out kit --dry-run --json
fenolite kit build --out kit --confirm --json
fenolite kit verify kit --json
fenolite kit status --json
```

`kit build` writes samples/instructions; `kit verify DIR` checks results (exit 3: invalid kit).
`kit status` lists runs; `kit record` records one. Claim native opening only after a reported run.

```fenolite-cmd
fenolite convert blink/altium/lamp.PrjPcb --to kicad --out converted --dry-run --json
```

Read next: `files`, `rules`, `checks`.
