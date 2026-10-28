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

`file-safety` was created by c0201 and completed by c0207 (`openspec/changes/c0207-diff-gates/`, moved on
2026-10-28); this change no longer holds a delta of it.

`layout-reuse` is created by c0210 (`openspec/changes/c0210-layout-reuse/`, moved on 2026-10-28: the fit by
pads, the copy of placement and tracks, and the strategy `place --strategy reuse`) and completed by c0227
(`openspec/changes/c0227-reuse-moves/`, moved on 2026-10-28: pads matched by net partition, zones of a copied
block and group moves); this change no longer holds a delta of it.

`copper-tidy` was created by c0208 (`openspec/changes/c0208-copper-tidy/`) and completed by c0214
(`openspec/changes/c0214-tidy-straighten/`, moved on 2026-10-28); this change no longer holds a delta of it.
The routing plugin `octilinear`, the last task of package 5, moved to c0228
(`openspec/changes/c0228-octilinear-router/`) on 2026-10-28; this change no longer holds a delta of `routing`.

`silkscreen-layout` is created by c0212 (`openspec/changes/c0212-assembly-marks/`) and completed by c0226
(`openspec/changes/c0226-silk-clip/`, moved on 2026-10-28); this change no longer holds a delta of it.

### Modified Capabilities

- `specctra-dsn`: MODIFIED "Routing rules in design files".
- `cli-contract`: MODIFIED "Route command budget and tiers".
- `routing`: none since 2026-10-28 ("Octilinear router plugin" moved to c0228).
- `board-analyses`: ADDED "Ground ties", "Barrier crossings", "Practice checks" and "Coupling screen"; MODIFIED "Analyze command".
- `design-dsl`: none since 2026-10-28 ("Generated copper and keep-outs" moved to c0224).
- `assembly-test-features`: none any more; "Test-point placement" moved to c0229 (`openspec/changes/c0229-testpoint-place/`) on 2026-10-28.
- `design-conversion`: none any more; its three ADDED requirements moved to c0223 (`openspec/changes/c0223-library-fidelity/`) on 2026-10-28.
- `manufacturing-exports`: none left here ("Fabrication read-back" moved to c0203 on 2026-10-27, "Region renders" to c0211 on 2026-10-28).
- `kicad-oracle`: none left here ("Trial edits gated by DRC" and "DRC exclusions written" moved to c0209 on 2026-10-28, "DRC gate on writing commands" to c0225 on 2026-10-28).

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
