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

`--altium-draftsman on` requests a native document; `--drawing-spec FILE` uses the same drawing TOML as
KiCad exports and requires that option plus `--target altium`. The native gate is closed pending Part F:
`altium.draftsman-not-written` explains why no file is planned and `result.draftsman` is null.
`altium.draftsman-not-listed` names a kept project that needs the drawing added. Candidate shells and
their own readback stay `INFERRED`; they do not prove that Altium fills or prints the drawing.

```fenolite-cmd
fenolite build blink/design.py --out blink/altium --target altium --altium-draftsman on --dry-run --json
```

It matches `capabilities` (`result.backends`, `result.matrix`).

| kind | file | status | evidence |
|---|---|---|---|
| `altium_draftsman` | `.PCBDwf`, gate closed | `experimental` | `INFERRED` |
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
fenolite check blink/altium/lamp.PcbDoc --stages altium.integrity --json
fenolite equivalent blink/build blink/altium/lamp.PrjPcb --level 2 --json
```

`check` measures model/ERC/copper/parity/readback with `INFERRED` evidence; run native checks too.
`equivalent --level 2` compares circuits (page `files`). The opt-in stage `altium.integrity` warns about
index-table faults (`altium.integrity.*`) in a PCB document. Python edit sessions are gated off
(`altium.edit.gate`).

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


## A drawing beside the script

`design.load_schematic("schematic.toml")` also selects the Altium drawn writer. Its ASCII/binary native
records carry wires, junctions, buses, labels, ports and sheet references; the build verifies actual
native units, pin tables, physical maps and connectivity before staging and again after templates.
Compatible per-unit aliases resolve through the project libraries; changed alias files invalidate a
reviewed plan. `result.schematic.source` is `drawn`, with counts in `result.schematic.drawn`.

`drawn.coordinate-rounded` names each point accepted with `--allow-lossy`; without that flag an
unrepresentable coordinate gives `FEN-7001`. Opaque content without native text gives
`drawn.opaque-dropped`. `drawn.altium-repeat-flattened` reports repeated instances written separately.
Automatic/Global scope may qualify shared local labels; each text change is reported. Native mirror
metadata, field justification, power field poses, bus aliases and per-sheet title metadata have explicit
limitations. Read the findings. Edit the drawing in `schematic.toml`; Altium-to-drawn sync is unavailable.

These files stay `INFERRED`: the drawn-sheet writer needs the native kit in
`docs/evidence/altium-schematic.md`. Altium is currently unavailable; own-reader checks do not establish
application acceptance or drawing identity.



## Version scopes

```fenolite-cmd
fenolite capabilities --no-tools --fields matrix --json
```

Read `versions` per operation: `version`, `tool`, `level`, `source`. Empty lists mean no recorded
version-specific scope. Sources name existing tests or actual native-kit runs; their existence is
traceability, not a new execution or broader native guarantee. Keep current CI and native acceptance
pending until their exact-commit proofs pass. The repository publishes `docs/evidence/conformance.json`
and `conformance.md`; releases attach the JSON and checksum.

A native kit reply lists only hypotheses whose actual verdict passed. Failed and synthetic runs
retain their lower kit-stability evidence; a displayed scene also retains the lowest source level.

## Reply metadata

```fenolite-cmd
fenolite explain cli.evidence-unsound --json
```

Supported evidence lists its hypotheses. Lower evidence requires an eligible no-claim command,
a named experimental feature, or an actual incomplete report with its matching issue. A marker
alone cannot excuse a complete claim. Unknown detection stays distinct. Unsound ordinary replies
retain their result with one metadata warning; strict tests reject it before plans or writes.

Read next: `files`, `rules`, `checks`.
