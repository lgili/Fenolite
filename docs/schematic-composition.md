# Schematic block composition

Altium builds can arrange components by functional blocks. Enable automatic grouping with
`--altium-layout blocks`, or declare presentation intent in the script:

```python
design.schematic_layout(mode="blocks", flow="left-to-right")
design.schematic_block("input", members=[j1], title="Input")
design.schematic_block("core", members=[u1, r1, c1], anchor=u1, after="input")
design.schematic_block("output", members=[j2], after="core")
```

Declare blocks after adding their parts to the design. Members are existing `Part` objects; an
anchor belongs to its block, and `after` names another block on the same electrical sheet.
`schematic_composition(design)` extracts immutable intent without changing the electrical model.
Both supported flows (`left-to-right` and `top-to-bottom`) use integer coordinates and stable ordering.
Every symbol unit is retained. Composition currently supports Altium only; an explicit `grid` selection
contradicting script declarations is a usage error. Without selection or declarations, legacy bytes remain.

Each block instance of the script (`docs/dsl.md`, "Blocks") that owns parts gives an implicit block when
composition is in force: key its path, members the parts it owns directly minus those of declared blocks,
title `<path> (<block name>)`, no anchor and no `after`. A declared block with the same key replaces it.
Without composition no implicit block is made, so no unused-intent diagnostic can arise.

A block's own schematic groups (`b.schematic(schematic_group(...))`, `docs/dsl.md`, "Blocks"; change
c0269) each give a block when composition is in force: key `<instance path>/<key>`, the group's title (or
key), its members, its anchor and its `after` mapped to keys of that instance. The implicit block of the
instance then keeps only the parts that no local group holds, and is dropped when none remain. A declared
block that holds a part takes it from the local group; a local group left empty is dropped. The groups
belong to the block, not to the design: they are never unused intent, a KiCad build (which applies them in
its own layout) never refuses them, and without composition Altium ignores them silently. A library block
with groups therefore builds in every mode.

Explicit blocks take precedence over module groups. Remaining root components form signal-connected
groups, ignoring power-interface nets and nets reaching more than eight components. The engine does
not infer circuit function. It records deterministic ambiguous branch choices in the report.

Review `result.schematic_composition` in a dry run. Confirmation writes its versioned report at
`.fenolite/schematic-composition.json` and standalone SVGs under `.fenolite/schematic-preview/`,
in the same transaction as the native files. Coordinates are nanometres, X right and Y down;
origins use 100 mil, pins 10 mil and rotations integer microdegrees. SVGs show emitted symbol
primitives, pin ends, horizontal reference/value text and local wiring. Reserved template/interface
areas are shaded; the preview is an estimate, with no claim of native font rendering equivalence.

`blocks-v1` bounds placement search at 10,000 candidates per paper trial and local wiring at 64
candidates per pin pair. Clear same-net pairs may get straight or orthogonal wires; other connections
retain labels. `composition.label-fallback` identifies endpoints and its reason. Verify the reported
connection in the preview; retaining labels is valid and requires no electrical edit.

Fixed paper and template dimensions never grow. Fixed template/custom paper is rounded down by
less than 10 mil (0.254 mm) for exact native endpoints. `composition.overflow` names the sheet/block:
split the block or explicitly choose larger paper. `composition.budget-exhausted` means that the bounded
search did not find an arrangement; simplify congestion. `composition.overlap` names affected units.
`composition.template-unverified` refuses content whose occupancy cannot be bounded, including
unsupported native assets. Use bounded template lines, rectangles and text. Border lines reserve thin
strips; filled shapes reserve their area. Text boxes use conservative character estimates, including
extra slack for template text. Native font metrics and automatic sheet choice are estimates.

An unsupported transform yields `composition.transform-unsupported`; `composition.invalid-intent`
identifies membership/order faults. `composition.connectivity-changed` refuses the complete transaction
if native readback changes component identities, pin assignments, nets, no-connects, buses or harnesses.
The check compares with the established native writer of the same resolved circuit.

Saved `altium-schematic-layout.json` remains authoritative. An unchanged build replays native bytes
and lists the replayed sheets in the report. SVGs always describe the generated baseline, including
when the final sheet is replayed. Changing block intent or the generated baseline after sync refuses
all writes with `build.altium-layout-conflict`; `--discard-layout` does not bypass it. Preserve the
snapshot and resolve the change deliberately. See [native sync](altium-schematic-layout.md).

Evidence is `INFERRED`. Synthetic ASCII/binary readback is measured; Altium GUI acceptance,
font metrics and editing quality remain unmeasured. Format facts reuse the public-source tables in
[schematic-ascii.md](formats/altium/schematic-ascii.md); the placement algorithm and examples were
authored for Fenolite. Compare [the before/after example](../examples/schematic_blocks/README.md).
