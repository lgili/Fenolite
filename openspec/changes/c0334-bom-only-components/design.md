# Design for review

## Measured boundary

On signed source 8aea3ace, the literal native KiCad 10.0.6 census owner003 has one source instance with `on_board=False`, `in_bom=True`, no pins and no power flag. The native/own original electrical partitions match completely. The source map omits it and strict drawn lowering refuses. The instance label and public CAD remain external; only counts, flags and original input hashes belong in core evidence.

Current `Component` has `dnp` and the opposite `board_only` flag, but no typed off-board/BOM membership. `exports.bom.parts_from_model` intentionally enumerates placed footprint instances. `DrawnOpaque` is explicitly restricted to both-excluded graphics/passives. Thus a local change to `_graphic_instance` would violate the contract and lose the item from the canonical bill.

## Recommended typed choice

Append `bom_only: bool = False` to `Component` and `Part`. Omit false from canonical JSON; old folders decode with false. True is mutually exclusive with board_only, requires no logical pins, and must have no physical footprint instance. A resolved source symbol must be pinless and non-power. An original footprint-name field may remain descriptive BOM metadata; it must never trigger physical lookup/placement. DNP remains distinct from inclusion in the bill.

This is deliberately narrower than a general schematic-only component with electrical pins. Such pinned, hidden-power, power and on-board instances must not become opaque or be silently classified as BOM-only.

## Complete pipeline

1. Project/source reading discovers explicit board-excluded/BOM-included pinless instances and preserves one canonical identity per hierarchy instance. It must not rely on library defaults to erase instance flags.
2. The source symbol map and generated Python retain that component and typed marker. DSL resolution loads its symbol but skips physical footprint placement/routing. A pin reference or contradictory physical declaration refuses before output.
3. Drawn lowering emits the same instance with board exclusion and BOM inclusion. Keep the existing both-excluded graphic/passive path unchanged. No fake footprints or invisible electrical nodes are permitted.
4. The neutral model BOM includes explicitly marked entries even though no footprint is placed. Preserve ordinary grouping, value/properties, reference, quantity, footprint-name metadata and DNP behavior. Existing parts remain governed by their current footprint attributes.
5. Project readers, parity, native component-set guards and all-level equivalence need explicit review. The original project and imported/rebuilt design must both represent the item; it is not acceptable merely to exclude it from comparison. Electrical pin sets remain exact and board physical comparisons must not require nonexistent geometry.
6. The corpus harness currently requests board-only component metadata; update that lookup only as typed support requires, with canonical BOM and native BOM controls. A census row remains failed until all required comparisons actually pass.
7. For an output backend without this behavior, retain a located existing unsupported-operation refusal before staging. Do not add a generic fallback or loss acceptance.

Coordinator clarification, 2026-11-02: a standalone KiCad PCB writer continues to project only the
board domain, as its existing contract requires; it does not claim to transport the schematic BOM.
The project build and canonical model carry that bill. Altium project write/build, which currently
cannot preserve this item, refuse with located FEN-7001 before staging, including with allow_lossy.

## Authored proof and rollout

Author a tiny Fenolite-only drawing with one ordinary electrical part and one pinless purchasing accessory, independently of the public board. Native 9/10 exports must show equal original/rebuilt BOM membership and unchanged complete electrical pin partitions; the model BOM must include the accessory and there must be no physical footprint for it. Plant removal and flag changes to ensure the comparison/BOM checks detect them. Cover repeated sheet instances, DNP, contradictory flags, pinned/power/on-board lookalikes and missing definitions.

Keep API/result key shapes unchanged except the reviewed optional model field and public DSL argument. Update the guide with a tested line. Recapture all existing complete 75 plans and final model-0 field/schema inventory; coordinate the new field with c0217/c0218's pending freeze. Run focused tests and the one coordinated fast/CI gates. No evidence promotion follows from an authored codec test alone.

## Decision needed

Coordinator review must accept the narrow `bom_only` field and complete pipeline, or choose a different typed representation with equivalent preservation. A broad `schematic_only` model is not the recommended overnight scope. This proposal must not be implemented as an opaque-graphic exception.

## Coordinator decision — 2026-11-02

The root coordinator reviewed the proposal at 6dd86796 and approved the narrow
`bom_only=False` appended/default-omitted representation and complete pipeline.
Implementation may proceed one fix/proof at a time. Only explicit off-board,
BOM-included, pinless/non-power source instances qualify. Canonical BOM identity,
reference and DNP must survive without physical footprints; repeated instances,
source flags and planted failures are mandatory proofs. Opaque rules remain
unchanged. Public DSL teaching/generation, legacy byte controls and new final-0
inventory precede the c0218/model-1 freeze. Unsupported outputs must refuse
before staging. No baseline, loss, tolerance or evidence waiver is authorized.
