# Preserve canonical BOM-only components

## Why

A registered public corpus owner has one pinless, non-power instance excluded from the board but included in the BOM. The current source map includes board components only, while the bounded opaque-graphic path requires exclusion from both board and BOM. Its explicit `drawn.part-unknown` refusal is therefore correct under the current contract. Treating that instance as a graphic would hide a purchasing item from the canonical BOM.

The native census measures all 603 electrical pins and 221 groups equal before lowering, then refuses this one unmatched item across eight owner rows. No public CAD content is proposed as a fixture or seed. This change needs typed representation, not a weakened comparison or acceptance baseline.

## What changes

Add a narrow canonical `Component.bom_only` boolean, false and omitted by default. A true value denotes an explicit pinless, non-power source/DSL part that belongs to the bill but has no board footprint instance. Preserve its reference, identity, value, properties, DNP state, symbol definition, source flags and footprint-name metadata. Include it in the neutral BOM without inventing physical geometry. Keep electrical/power/board-only lookalikes refused by this path.

Expose a tested `Part(..., bom_only=True)` contract and preserve it through import/code replay. Review actual project reading, parity and all-level equivalence so an omitted BOM item cannot produce a false passing comparison. Keep all existing both-excluded opaque rules unchanged. Unsupported backends must refuse before a write.

## Review gate and impact

No implementation is authorized by this proposal alone. The coordinator must review the typed choice, public API and complete-model-0/schema/contract impact before coding. This crosses model, DSL, import, schematic emission, BOM and validation; it must land before the final model-1 freeze. All historical captures stay immutable and the actual final-0 inventory must be replaced explicitly. No baseline, tolerance, licence, existing input or evidence level changes here.
