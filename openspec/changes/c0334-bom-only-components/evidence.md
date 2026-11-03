# Focused implementation proof, 2026-11-02

Source base `d348705f6344a542c842e8cd8bd4423e75c9bca7`, with local c0336 power-alias correction
`795a9c6e`. Tests explicitly bind `PYTHONPATH=src:tests` to the isolated repair source. No third-party
CAD fixture, parser, opaque exception, loss acceptance, tolerance or count baseline is added.

## Independently authored boundary

Before implementation an original authored Mini pinless accessory with explicit BOM inclusion and
board exclusion appeared in the actual KiCad 10.0.6 BOM with the ordinary two parts, while adding no
electrical pin: all 34 pins and 33 groups remained. Original model discovery omitted it; both the
target-9 and target-10 authored reader controls failed before the change. Native input hashes and
full logs are preserved outside the repository.

After implementation, the native flat/repeated-sheet × DNP false/true controls pass: original and
rebuilt complete native BOM rows match; every original electrical pin and partition remains intact
(flat 34 pins/33 groups; repeated 8 pins/5 groups). Flat BOM has three entries; repeated BOM has six,
including two independent accessory references. Both the canonical model and the raw schematic side
retain typed membership, identity, DNP and descriptive footprint metadata; there is no physical
footprint. The descriptive definition intentionally does not exist, proving no geometry lookup.
The source-controlled strict round trip also compares all levels 1–8 and S, including repeats.

The repeated control initially exposed a real path defect: compiled reference M2 was incorrectly used
as the common leaf of a shared sheet. Level S detected the difference rather than passing it. The
implementation now uses the existing hierarchy's actual stable paths, retaining refs M1/M2. No
opaque rule or S comparison was weakened.

Planted pinned, hidden-pin, power, on-board and unresolved-definition forms refuse before output and
never acquire the marker. Planted BOM exclusion is detected as a missing canonical component. Model
tests detect contradictory board-only/pin/map/physical claims and changed membership; ordinary
grouping and DNP filtering remain the existing template's behavior. Altium project output refuses
with located FEN-7001 even with allow_lossy. A standalone KiCad PCB writer still projects only the board
domain and does not claim to transport the schematic BOM; the project and canonical model carry it.

## Public owner, without copying public CAD into core

All eight affected declared source rows `kicad-demo-10-0-6-sch-002` through `009`, source tag 10.0.6
(`caf7377e9cb6`), pass their native owner-context electrical/lowering census. Each retains all 603
pins and 221 groups; the original and lowered native graphs remain equal. Existing 84 bus-member
warnings, five dangling warnings and two own/native naming differences remain visible. These are not
promoted into a full-fidelity acceptance claim.

A separate actual native BOM measurement confirms the formerly refused purchasing item is retained
as a typed canonical BOM-only component. All native base BOM fields and every original user BOM field
agree. The added `fenolite.path` remains generated canonical identity metadata, not a claimed field of
the original native BOM. The public source and every contributing cache input were SHA-checked; copied
CAD was removed after measurement. The original broad-properties comparison, which had not requested
the user fields from the native exporter, is preserved as a failed probe; its corrected explicit-field
measurement passes without changing product behavior or accepting any lost source property.

## Focused validation and remaining gates

- Source controls: 9 passed, including all unsafe forms and planted BOM loss. Log SHA-256
  `e658c8614b6640a051453c13f7a72c91bc19cd628f4e5cd6d328ade977200ab8`.
- Actual native flat/repeated/DNP and raw schematic-side controls: 4 passed. Log SHA-256
  `354d3b02f5deb0623d86ad6a274939ecae654d587a0e099afcc4fae855190458`.
- Import neighbor file: 78 passed; consumer/model/Altium-build/schematic-generator neighbors: 90
  passed; BOM/model/guide group: 129 passed; canonical controls: 20 passed. Legacy unmarked canonical
  component bytes are exact and old bytes decode with false. These groups overlap and are not summed
  into a unique-test total.
- Ruff check/format and generated schema/guide checks pass. Full src typing found one empty-set type
  annotation, corrected with its focused zero-error rerun; required combined root validation remains
  pending. No runtime dependency or default schema version is changed.

The final model-0 inventory, 75 complete unchanged-plan byte comparison, c0217/c0218 transition review,
root-owned fast gate, full current literal census and required exact-head KiCad 9/10 CI still need
their independent receipts. This patch must not be archived from focused native proof alone. The
literal 130-row census on the earlier immutable source remains separate and is never relabeled.

## Multi-unit boundary audit before freeze

The coordinator requested and approved this focused follow-up. Independently authored pinless two-unit
native inputs expose a real normalization error before the guard: every input exports a native 10.0.6
BOM successfully. With a board-included second unit, strict import initially succeeds but rebuild
changes that unit to board-excluded. With mixed DNP flags, it changes false/true to true/true. The
unchanged-flags positive and a both-excluded second unit preserve their original flags. All controls
retain the complete ordinary native graph (34 pins/33 groups).

The before-regression group records four failures and two supported positives. The correction checks
the actual reference/use path before canonical discovery and raises a located existing FEN-3004 on
only the unrepresentable board/DNP combinations, before staging, including with allow_lossy. The
supported both-excluded graphic stays opaque and retains its own flags. It adds no model field, schema,
dependency, comparison waiver or fallback. The focused after group passes 38 tests, including no plan,
no output and immutable-source assertions on target 9/10; the native flat/repeat/DNP and four authored
multi-unit controls pass all eight cases on the actual 10.0.6 CLI. Ruff and focused typing pass. Required
exact-head CI and release freeze remain separate pending gates.

An actual isolated official 9.0.9 CLI subsequently passed all eight native BOM/multi-unit controls
(flat/repeat × DNP plus original multi-unit flags). Its first attempt exposed a test setup bug: the
explicit rebuild omitted its target major and wrote default-target-10 files, which native9 correctly
refused. The oracle now passes the running major to build, matching the existing fidelity harness.
No product refusal or version policy was changed; source-bound 9 evidence remains partial until CI.

## Closed diagnostic-ledger follow-up

The coordinator's independent 235-case equivalence/verify-source audit found four
closed-ledger/documentation failures: the test table omitted the real bom-only
kind and the equivalent CLI section omitted equiv.bom-only. The initial focused
reproduction retained four failures and two passing controls. The correction
keeps the closed table and exact-message assertions, adds an actual canonical
changed-membership CLI scenario and actionable public explanation/guide tests.

An independent authored blink/Mini_R Part(bom_only=True) then reproduced a real
KeyError('build.bom-only') in the already-written rejection path. Registering its
existing error severity makes the same control report build.bom-only at M1, with
zero output files. The already-emitted model.bom-only guard is also registered
and both have public explanations and tested teaching; model fields are unchanged.

On combined base 24e63d06 plus this follow-up, the complete focused equivalence,
verify-source, equivalent/explain CLI, guide, build-issue and BOM model group
passes 392 tests in 30.77 seconds. Ruff check/format, focused typing (zero errors),
strict OpenSpec and generated-guide checks pass. The first expanded run exposed
two new-test documentation mistakes; both are corrected and its 186-pass/2-fail
log remains preserved. Final fast and exact-head CI are still coordinator gates,
and no census or acceptance record is changed.

## Exact lazy source boundary

Integration source52134c17 plus the reviewed AST boundary change: import-graph
and project-curve API suites passed74 tests in3.94s. Independent controls reject
module-level, ImportError-only, other-API-file and other-importer-target edges;
fresh-process API import loads no importer. Ruff and generated guide check pass.
## Adjacent contracts from the combined fast audit

The coordinator's next fast audit identified three adjacent contracts not yet
updated for the appended field. An isolated focused reproduction fails exactly
all three: Altium unsupported-field documentation, Component suffix-order
regression and the closed device Part attribute set. Documenting the existing
Altium refusal, asserting all four unchanged suffix fields and reserving the
actual bom_only attribute fixes those contracts. A new authored device interface
named bom_only is genuinely refused as a Part attribute. No model field, field
order, Altium scope or device tolerance is altered. The four complete focused
modules (Altium round-trip, value ranges, device ports and BOM-only model) pass
168 tests in 0.92 seconds. A first selector typo collected no tests and is
retained separately; it is not used as validation.
