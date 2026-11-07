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

Metadata follow-up approved 2026-11-02: the implemented `bom-only` difference already produces the
public `equiv.bom-only` issue. Keep the independent closed-kind ledger, CLI contract, explain table
and tested guide in sync, with a real CLI membership-change scenario. This changes no model/schema
or comparison semantics and must not weaken the closed-set assertions.

Coordinator addendum, 2026-11-02: before freezing, independently measure pinless multi-unit source
symbols whose instance BOM/board/DNP flags disagree. A confirmed unrepresentable flag combination
must refuse with a located existing input error before staging; no unit may be silently normalized
to another unit's flags. Prove the same-flags positive independently and retain all electrical pins.
This focused boundary audit is independent of the root-owned full-census/freeze work.

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

## Existing diagnostic contract follow-up

Coordinator review requested the independent equivalence ledger, actual CLI membership
scenario, public explanation and guide teaching before floor work. The authored
pinned Mini_R control additionally reproduced KeyError('build.bom-only') because
the existing guard omitted the closed severity registry. Register that existing
build guard and the existing model.bom-only guard, explain and teach both, and
prove that the pinned symbol returns a located error with zero output files.
This completes existing diagnostics without changing fields or supported membership.

## API layering follow-up — coordinator review, 2026-11-02

The accumulated fast gate found three forbidden API-to-importer edges introduced
by source BOM discovery. Reusing `importer.bom_only.preserve` is deliberate: it
uses the same complete Source/Hierarchy instance traversal as import and avoids
misidentifying repeated modules. Approve only this exact module at the existing
two API boundaries, only inside function bodies. Keep the general allowed table
and all other package boundaries unchanged. Add independent positive/negative
AST controls and a fresh-process no-importer assertion before recording proof.
Coordinator fast audit requested the separate narrow adjacent-contract follow-up: document the existing Altium refusal, retain the exact appended Component field order in its regression, and reserve the actual Part.bom_only name against device interfaces. No field or ordering is changed.
