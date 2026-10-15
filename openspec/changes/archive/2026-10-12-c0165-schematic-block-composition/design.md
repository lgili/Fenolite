## Scope and baseline

`backends/altium/layout.py:layout_sheet` sorts `PartSpec.key`, estimates cell extents and uses
`geometry.shelf.shelf_pack`. `project.plan_sheet` and `hierarchy.plan_sheets` call that planner.
`PlacedPart` currently has no rotation request, and `SheetPlan.lines` describes harness lines rather
than general electrical wires. Composition needs an explicit plan for transformed symbols, visible
text and local electrical connections; replacing cell ordering alone does not solve the problem.

The first implementation targets Altium, both forms, with flat and module sheets. The neutral intent
and geometry can support another backend later, but accepting an unsupported target is an error.
The mode remains opt-in to avoid changing existing files and c0164 baseline hashes.

## Proposed authoring contract

These calls are proposed APIs, not commands available in today's installation. `j1`, `r1`, `u1`,
`c1`, `c2` and `j2` below stand for existing parts authored in a synthetic design.

```python
design.schematic_layout(mode="blocks", flow="left-to-right")
design.schematic_block("input", members=[j1, r1], title="Input")
design.schematic_block("core", members=[u1, c1, c2], anchor=u1,
                       after="input", title="Core")
design.schematic_block("output", members=[j2], after="core", title="Output")
```

`Design.schematic_layout(*, mode="blocks", flow="left-to-right")` enables composition. Supported
flows are `left-to-right` and `top-to-bottom`. `Design.schematic_block(key, *, members, title=None,
anchor=None, after=None)` records a block. A key is unique within the design; members are existing
`Part` objects, which assign all their symbol units. An anchor is one of those members. `after`
names another block on the same sheet and establishes reading order, not electrical direction.
Forward references are allowed and resolved after the script finishes. Duplicate membership,
unknown anchors, cycles and blocks spanning existing electrical sheets are errors with no writes.
Block declarations require composition to be enabled by the DSL or the build selection; otherwise
validation reports unused intent instead of silently applying the legacy layout.

No coordinate is required. Flow describes how to read the diagram; it is not evidence that a passive
or bidirectional connection has a signal direction. V1 does not introduce per-unit declarations,
absolute positions, alignment DSL or a library of circuit-specific recipes.

When no blocks are declared, existing module paths supply grouping within the selected sheet mode.
Unassigned symbol units are placed in deterministic automatic groups. Components with no schematic
symbol are excluded and listed; they are not invented as schematic objects. Power/global nets do
not collapse unrelated groups. High-fanout nets are excluded from automatic grouping using a
documented, versioned threshold of eight component endpoints; explicit membership takes priority.
Block order uses the `after` DAG with code-point key ordering as its stable tie-breaker. All units
of a component appear exactly once on their existing sheet and retain their existing IDs.

## Data and files

- New `src/fenolite/dsl/schematic.py`: immutable request types and declaration validation. Add the
  two methods in `dsl/design.py`; expose `schematic_composition(design)` in `dsl/convert.py` and
  `dsl/__init__.py` to extract resolved requests. Follow existing presentation/placement side-input
  patterns; do not add layout data to canonical circuit, board or rule JSON.
- New `src/fenolite/schematic/composition.py`: `CompositionIntent`, `BlockIntent`, `CompositionPlan`
  and `compose_sheet(...)`, with integer nanometres and microdegrees, stable unit keys, regions,
  visible-object envelopes, constraint findings and bounded candidate search.
- New `src/fenolite/schematic/report.py` and `preview.py`: versioned report serialization and
  `composition_svg(plan)`. The preview uses planned symbol primitives, pins, fields, labels and
  wires, not a rectangle-only proxy for a symbol. Escape SVG text; reference no external assets.
- Extend `backends/altium/layout.py`, `project.py`, `hierarchy.py` and `schdoc.py` with opt-in
  composition, symbol transforms, fields, junctions and local electrical wires. Keep harness lines
  separately typed so a signal wire cannot be emitted as a harness by mistake.
- Add `composition=None` to `project.write_project` and `lens/altium.py:build_altium`, passing
  extracted DSL intent through `cli/cmd_build.py`. Add `--altium-layout grid|blocks`; omission
  inherits the DSL mode or uses the legacy cell layout. A flag contradicting a declared mode is a
  usage error. Reject active composition on KiCad until its adapter is implemented.
- Write `.fenolite/schematic-composition.json` and one `.fenolite/schematic-preview/<sheet>.svg`
  for composed sheets, through the normal plan/confirm/receipt transaction. Reserve
  `result.schematic_composition` for this report; c0164's `result.schematic_layout` keeps its meaning.
- Add `docs/schematic-composition.md`, tested examples to the agent guide, issue explanations and
  the CLI contract. These implementation files are not created by this proposal-only change.

## Composition stages

Implementation note: `backends/altium/composition.py` adapts the neutral plan after existing hierarchy
resolution; `verification.py` compares complete native electrical signatures. The writer has separate
composition geometry and harness lines. Per-sheet normalized intent plus algorithm version is fingerprinted
in a hidden root parameter, so declaration insertion order is irrelevant and sync detects intent changes
even when a different constraint happens to yield identical placement. Fixed custom/template paper is
rounded down to the 10 mil native grid; unsupported occupancy is refused. Preview markers and text metrics
remain estimates, with actual symbol primitives shared from the native source geometry.

Layering: `schematic` is a stdlib-only core presentation package that may import itself and `core`.
DSL, lens and backend adapters may depend on it; it cannot import DSL or a backend. Architecture tests
retain that boundary and explicitly reject third-party imports into the new package. Native adapter
modules inherit the existing writer's inferred format evidence; the evidence matrix is regenerated.

1. Resolve the existing sheet hierarchy and symbol definitions. Build a graph of component units
   and nets, retaining pin endpoints and explicit power-interface roles. Resolve block membership.
2. Evaluate the selected paper and drawing sheet. Derive a content region from its margins and
   reserve title blocks, logos and annotations; border lines are not giant occupied rectangles.
   Native or opaque template objects whose occupancy cannot be bounded produce an explicit finding.
3. Within each block, use its anchor or a deterministic topology-based root. Place the main path
   in the requested reading direction, align compatible connected pins, and place two-pin branches
   beside the connected anchor pins with staggered spacing. Ambiguous attachments use a stable
   choice, exposed in the report, rather than guessed circuit semantics. Rotate complete symbol
   units in quarter turns; visible reference/value text remains horizontal and separately placed.
4. Pack complete block envelopes into the content region. `after` constrains reading order: row
   order then left-to-right, or column order then top-to-bottom. Wrapping is allowed and reported.
   Explicit paper size is fixed. Without one, choose the smallest supported ISO paper that fits;
   failure at the largest supported paper reports overflow instead of unbounded custom growth.
5. Attempt short local wires inside a block using deterministic straight/one-bend/two-bend
   candidates on the native connection grid. Search is bounded by a fixed candidate-count budget,
   never elapsed time. Do not cross a foreign pin, body, text or reserved area, and do not join
   different nets. V1 falls back to labelled stubs when no legal candidate exists; inter-block
   connections, buses and harnesses retain existing labelled/port representations.
6. Verify final envelopes and electrical readback. Publish diagnostics and preview, then use the
   normal transactional writer. Hard layout or electrical findings prevent every planned write.

Pins already off the component-origin grid retain their native endpoint precision. Normalize every
candidate to the writer's representable connection grid before collision and connectivity checks.
The report contains emitted geometry, not pre-quantization values. Every moved/rotated graphic, pin,
field, no-connect marker and directive is transformed or placed consistently. Unsupported transform
geometry is diagnosed, never dropped or silently replaced by a simplified symbol.

## Reports and acceptance

The report schema is `fenolite.schematic-composition.v0`, algorithm `blocks-v1`. Per sheet: usable
and reserved regions, block order/envelopes, unit origins/rotations, attachment decisions, visible
object envelopes, wired and labelled connections, fallback reasons, crossings/bends/wire lengths,
estimated text bounds, budget usage, findings and evidence. Pin and unit locators link a finding to
the design path, block, sheet and proposed corrective action. Pure geometry/text estimates are
`INFERRED`; no aggregate aesthetic score hides defects.

Issue namespaces are proposed as `composition.*`: invalid membership/ordering, overflow,
overlap, template-unverified, transform-unsupported, connectivity-changed, and label-fallback.
Finalize and register the closed code/severity table in task 1.2. Hard constraints use error
findings (exit 5); safe label fallback is informational. A preview shares the report's bounds and
IDs. It is a review aid, not an Altium screenshot or a replacement for native compilation.

Synthetic fixtures cover an input/core/output path, a passive chain, a fanout with nearby branches,
a feedback loop, a multi-unit device, module hierarchy, long texts and a restricted template.
Acceptance is zero hard envelope violations, exact unit coverage, unchanged electrical signature,
deterministic output under reordered declarations, honoured block order and nonzero local wiring
on eligible fixtures. Cases with inadequate space or impossible constraints must fail atomically.
Do not claim universal visual quality from these metrics; keep before/after previews for review.

## c0164 compatibility

Always generate the complete fresh baseline using the selected mode before checking snapshots.
Changing mode, membership, algorithm geometry or template occupancy may change that baseline and
must raise `build.altium-layout-conflict` for saved sheets. Keep the snapshot and output untouched.
Once a composed sheet is edited in Altium and synced, compatible rebuilds replay its exact bytes.
Mark previews/reports as `source="generated-baseline"` and identify replayed sheets: their planned
SVG is not a rendering of the human-edited native document. Preview generation cannot bypass replay.

## Evidence before merge

Contracts, composition and SVG are `INFERRED`, proved with authored tests. Native output must pass
Fenolite electrical readback in both forms and existing regression gates, retaining that evidence
level. Record a manual native Altium review separately with tool version and observed limitations;
without it, acceptance remains unmeasured. Any newly needed record/transform fact is documented from
public sources before emitter code. No native files or numbers from a private design enter fixtures.
