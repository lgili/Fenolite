## Why

c0032 to c0034 give Altium a schematic and symbol libraries, but no footprint, so the change order cannot place parts. The KiCad footprints a build resolves can be written as an Altium PCB library (`.PcbLib`), a compound file with one storage per footprint (S-0002, S-0162). `kicad-cli fp upgrade` converts it back on 9.0 and 10.0 (S-0166), a local oracle for the geometry. A PCB document (`.PcbDoc`) uses the same records (S-0160); `kicad-cli pcb import` reads it on 10.0, and the free Altium 365 Viewer opens it (S-0143, S-0149).

## What Changes

- `fenolite build --target altium` also writes `<name>.PcbLib`, like c0034's `<name>.SchLib`: one footprint per distinct resolved KiCad footprint. Altium links (`<X>.PcbLib:<fp>`) stay as c0032 writes them, with no footprint.
  - Scope: SMD and through-hole pads (round, rect, oval, roundrect; round holes), lines, rectangles, arcs and circles on silkscreen, fabrication and courtyard.
  - One table maps Fenolite layers to Altium layers.
  - Other graphics are dropped and reported; a footprint with an unsupported pad is refused.
  - The schematic links KiCad footprints to `<name>.PcbLib`.
- Experimental `<name>.PcbDoc`: outline, two-layer stack, components at their DSL placements (unplaced ones staged), pads at absolute coordinates, footprint graphics, nets and designators; no routing. `SOURCEUNIQUEID` is the schematic component's `UNIQUEID`, so the change order stays linked. Written only when every component has a written footprint and the design has a board. First in the cut order.
- The project file lists the new documents; `capabilities` lists `altium-pcb-writer` as experimental.
- `backends/altium/pcbrecords.py`, `pcblib.py`, `pcbdoc.py` (new), on c0034's `cfb.Storage`; `cfb` allows empty streams.
- Oracles: `.PcbLib` → `fp upgrade` → Fenolite's footprint reader vs the `FootprintDef` (output files counted); `.PcbDoc` → `pcb import` → Fenolite's board reader vs the design (JSON report and stdout).
- Sample: `examples/blink_2layer` (authored CC0 mini library), golden files, and a protocol page for the maintainer.
- Sources S-0160 … S-0166, citing c0034's S-0150; hypotheses `H-A-PCB-*`; fact pages `pcb-library.md`, `pcb-records.md`, `pcb-document.md`.
- **Source restriction:** AltiumSharp only at its 2023 version 1 commit (S-0150, Apache-2.0). Version 2 cites a non-public decompilation folder, so no fact found only there is used (`LEGAL.md` P1). Task 1.1 records this.
- Size: 9.5 design-days; 5.9 without the PcbDoc.

## Capabilities

### New Capabilities
- `altium-pcb-writer`: records, layer map, PcbLib, PcbDoc, test decoder and the two oracles.

### Modified Capabilities
- `altium-build`: ADDED PCB build rules; MODIFIED "Altium build target", "Altium build outputs" and "Altium symbol sources" (c0034's texts).
- `altium-schematic-writer`: MODIFIED "Designator, comment and links", "Project file" (c0034's texts) and "Compound file container" (c0033).
- `cli-contract`: MODIFIED "Experimental features in capabilities" (c0032).

## Non-goals

- Routing, vias, zones, keepouts, rules, net classes, polygons, more than two copper layers, 3D models, IntLib.
- Trapezoid, custom and per-layer pads, slots, offset drills, chamfers, filled shapes, polygons and texts in footprints.
- Reading Altium files; merging an edited PcbDoc (refused like any edited output); resolving a user's `.PcbLib`.

## Evidence level required

- Records, layer map, refusals, determinism and CLI: mechanical (unit tests, an independent test decoder, golden files).
- What KiCad's importer reads reaches `ORACLE-VERIFIED(kicad-cli)`: the PcbLib round trip on 10.0.6 (local and `kicad-10`) and 9.0.9 (`kicad-9`); the PcbDoc import on 10.0.x only.
- Altium-only facts stay `INFERRED`. A Viewer render gives `ALTIUM-VERIFIED(author-report; A365 Viewer; <date>; no artefact)`. Altium Designer reports count only under a licence the maintainer may use for Fenolite (`LEGAL.md` A, P4).
- The build envelope stays `INFERRED` and experimental.

## Impact

- Extended: `lens/altium.py`, `cmd_build.py`, `project.py`, `prjpcb.py`, `cmd_capabilities.py`, `tests/_cfb_read.py`.
- No runtime dependency, model, schema or layering change.
- Archive order: c0032 → c0033 → c0034 → c0035.
