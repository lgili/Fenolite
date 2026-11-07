# Exact import-only annotation iteration

Coordinator approved0.3 before runtime on2026-11-03. No identity/order normalizer is implemented;
0.2, its controls and final required CI remain open. No canonical field, public argument, dependency,
schema, generic library extraction or default board writer changed.

The authored regression has physically coincident duplicate pad numbers with different annotations,
an empty function, unknown type suffix, explicit passive and exact absent metadata. The corrected
before control fails both target9/10 cases while its fixture/default controls pass:2failed/2passed.
An earlier fixture preparation attempt accidentally retained preexisting passive children; that
attempt is preserved separately and is not the corrected regression proof.

After the import-only restoration,19 focused controls pass, including full actual import/build with
repeated footprint references and distinct per-pad metadata; variant splitting and sharing; changed
identity/order/cardinality/ref negatives; malformed/ambiguous annotations; and exact untouched child
order. The neighboring importer/shared-ref/physical-definition, generic derivation and top/bottom
embedding group passes131tests in13.16s. Focused pyright reports0errors; focused ruff passes.

An additional focused boundary group passes26tests in3.03s: the physical metadata control now crosses
source top/bottom, output top/bottom and target9/10 at90degrees; source bottom edits only its physical
footprint layers, leaving the board layer table intact. A malformed annotation through the real API
returns located FEN-3004 before any plan/output and leaves its source unchanged. The broad importer
group is also being checked; its older-base inherited-symbol failure is unrelated to annotations and
already has the independently integrated resolve_extends fix on the coordinator's newer base.

Native9.0.9 load passes1test in2.49s. Native10.0.6 load/save passes1test in2.16s. Every DRC JSON is
retained without filtering; these commands prove load, not a zero-finding DRC claim. The first strict
native10 save control found that the vendor omits the single authored empty pinfunction. Its final
independent expectation identifies that exact physical UUID and one literal field; all other values,
presence and UUIDs compare exactly. Raw import/build retains the explicit empty child, so no production
normalization or matcher omission follows. Initial driver failure and native empty-field finding stay
separate from final receipts. Source bytes remain unchanged. S-1294 records the bounded observation.

Public Royal at declared library pin97acc80c223d75520c03fc44cab63cd9a3202c42, immutable source board
535dbe212f43a8bab12b23277e176a94ac9694177258af2981c0e7b08e4b7252, has all428 physical pads across71
footprints exact through source→vendor definition→native placement, including every annotation
sequence and absence. This is a preservation checkpoint, not a full current-combined replay or L7
claim. The first diagnostic compared Node repr including source offsets and falsely differed onC25;
the corrected compact content comparison succeeds and retains that failed driver attempt visibly.

External artifacts: `c0355-annotations-before-v2.log`, `c0355-annotations-neighbors.log`,
`c0355-native-annotations-v3-9`, `c0355-native-annotations-v3-10` and
`c0355-royal-vendor-annotations-v2/summary.json`. Fresh combined actual import/build all428pad
preservation and complete strict levels1–8/S remain required before1.0 is checked. Royal raw cache and
derived-fill differences must stay visible; the model/geometry/annotation/unknown guards are unchanged.
