## Why

The maintainer's request of 2026-10-24. The maintainer's board work needed many scripts around Fenolite for jobs every board needs: copying a reference block (mirrored once, when copied by part positions), tidying router output, proving a single ground tie, counting the ways across a barrier, placing test points and designators, editing a board the owner keeps open in Altium, and not writing over a file the owner saved. A survey of the scripts against Fenolite 0.5 found about a hundred capability families: about forty absent, about forty present only as building blocks, two Specctra export defects. c0174 says what to check; this change gives the tools.

## What Changes

Twelve work packages, each implementable alone or splittable into its own change; `design.md` gives details and order.

1. **Router input:** Specctra width rules and one-sided clearance rules, and several globs per tier.
2. **Ground ties** (`analyze --kinds ties`): a single tie proved by removing exactly its geometry; sense nets sharing power copper; isolation islands.
3. **Barrier crossings** (`analyze --kinds crossings`): free ways across a cut line against the connections that must cross it.
4. **Layout reuse:** copy a block with its copper by pad fit; move or turn a block rigidly, with a pose search.
5. **Copper tidy** (`fenolite tidy`): prune, straighten, chamfer, and report the routing style. A new octilinear routing plugin routes the critical connections.
6. **Generated copper:** power bands, hole rings, class barrier bands, body keep-outs, zone fan-out, stitching.
7. **Practice checks:** decoupling, connectivity after cut-outs, copper under bodies, relief entry, necks, loops, pad balance, current split, coupling, dead copper.
8. **Assembly marks:** designators placed with measured text extents, silkscreen clipping, test-point placement.
9. **File safety:** snapshots, receipt-guarded replace, open sessions, cloud placeholders, reference repointing, gated and three-way diffs.
10. **Library fidelity:** imported pad mask and paste, 3D model placement, library from a board and its drift, body copy by pad fit, house-library coverage.
11. **Release checks:** Gerber and Excellon read-back, trial edits gated by DRC, DRC exclusions, region renders.
12. **Native Altium edit sessions:** typed, asserted edits keeping index tables consistent, connectivity gates, and an integrity check for faults that crash the native tool.

## Capabilities

### New Capabilities

`layout-reuse`, `copper-tidy`, `file-safety`, `silkscreen-layout` and `altium-edit`.

### Modified Capabilities

- `specctra-dsn`: MODIFIED "Routing rules in design files".
- `cli-contract`: MODIFIED "Route command budget and tiers".
- `routing`: ADDED "Octilinear router plugin".
- `board-analyses`: ADDED "Ground ties", "Barrier crossings", "Practice checks" and "Coupling screen"; MODIFIED "Analyze command".
- `design-dsl`: ADDED "Generated copper and keep-outs".
- `assembly-test-features`: ADDED "Test-point placement".
- `design-conversion`: ADDED "Mask and paste of imported pads", "Model placement of imported footprints" and "Library made from a board".
- `manufacturing-exports`: ADDED "Fabrication read-back" and "Region renders".
- `kicad-oracle`: ADDED "Trial edits gated by DRC".

## Non-goals

- No limit values and no standard's tables: every limit comes from the user's requirements.
- No compliance verdict or gate approval.
- No automatic placement of a whole board.
- No organisation's code, values, geometry, names or format facts; format facts come from public sources or the maintainer's kit.
- Out of scope: report generators, converter equations, purchasing, project records.

## Evidence level required

- KiCad writes: `KICAD-VERIFIED` by DRC on both majors.
- Analyses: `INFERRED` on authored benches, KiCad-bracketed where possible.
- Altium writes: experimental, until the maintainer's kit runs (`ALTIUM-VERIFIED(kit)`).

## Impact

- New: `reuse/`, `tidy/`, `safety/`, `silk/`, `backends/altium/edit/`, `analysis/ties.py`, `crossings.py`, `practice.py`, `coupling.py`, `routing/octilinear.py`, `dsl/generate.py`, `exports/readback.py`.
- Changed: Specctra writer, `route`, `analyze`, `testpoints`, `convert`, guide pages.
- Size: about 60 design-days. Packages 1 to 3 (6 days) come first.
