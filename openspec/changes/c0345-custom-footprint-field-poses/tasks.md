## 1. Focused preservation
- [x] 1.1 Reproduce the custom property pose loss with authored controls and validate this contract before runtime changes.

Before-code proof: strict OpenSpec validation passed; four authored tests fail
on the original runtime. Three complete import/build proofs detect the exact
custom Author position/rotation loss (including visible text rendering), and
the declared-property field request is rejected by the old DSL.
- [x] 1.2 Extend field requests only to declared user properties; emit exact representable source poses and refuse unsupported ones before staging. Prove full strict roundtrips and planted loss detection.
- [x] 1.3 Update the public DSL guide and changelog; regenerate the guide and pass focused tests, lint, types and private residue checks.
## 2. Combined validation
- [ ] 2.1 Preserve default plans and pass accumulated fast/exact-commit CI before closing this change.

Actual focused proof:187 custom-field/DSL/merge/replacement/guide tests pass
in12.02s. This includes full strict1–8+S authored import/replay/build proofs,
unknown/reserved/case-mismatched names, and five unsupported-pose refusals with
no planned writes and unchanged sources. Native9.0.9 and10.0.6 each pass two
plain/styled SVG cases: complete primitive/style multisets agree, and moving
the custom field is detected in each case. Twelve raw SVG hashes and JUnit
hashes are recorded in `docs/evidence/custom-footprint-field-poses.json`.
The actual public Multichannel proof also passes all9 strict levels with
3546 generated field requests, zero differences and zero accepted findings;
its earlier3101 custom-field rotation losses are gone without comparator changes.
Full source Pyright reports zero errors/warnings; touched Ruff/format and
generated-guide checks pass. Private staged residue remains a commit gate.

Private staged residue passes with zero hits in17 changed files, private gate on.

## Mirror-ownership addendum (runtime not approved yet)
- [x] M1 Prepare/review the symmetric bounded native-mirror proposal and authored RED9/10/both-side/rotation/hidden/style controls; demonstrate exact existing derive/embed representation separately from production import. No third-party fixture/value/coordinate is committed.
- [x] M2 Only after root review, implement the exact native-owned predicate/retention and omit matching field requests; preserve all other refusals and normal Part.properties/field semantics.
- [ ] M3 Prove full authored import/build/native comparisons, distinct variant payloads, malformed/unknown/reserved/duplicate and other unsupported negatives, unchanged75complete default maps, and required exact-commit CI before closure.

Proposal evidence2026-11-03:64current request RED,4actual import dry-run RED/no-output,64strict modeled1–7 mechanism equal without exclusions; native9.0.9/10.0.6 four SVG representatives equal except root title metadata. Existing derive/embed is a partial reconstruction without pad-net restoration: fullL8/S remain unproved; original selfL8 passes. See c0358 mirror-proposal-proof.json. Runtime approval, implementation and complete production/native/default/CI proofs remain pending.

Mirror implementation2026-11-03: root approved scope after planning/RED checkpoints.177focused pass plus162structural/importgraph/evidence/vendor pass; actual9.0.9/10.0.6 four import→reviewedconfirm→full1–8/S controls pass without accepts/differences. All75complete maps/1137paths/exits byte-identical. Ruff/Pyright0. CM5 mirror refusal removed but source nativeTAB remains FEN-3004 unsupported native custom property text; no TAB relaxation, no completeCM5/CI success claim. See c0358 mirror-implementation-proof.json. M3 remains open for final exact-commit CI.

Native collection correction in progress: the existing complete native proofs are moved from unit collection to the existing KiCad oracle directories, preserving all assertions and fixed targets. Both oracle jobs must collect8;9runs4+4explicitunsupportedskips and10runs8. Unit-only collection must contain no complete nativeCLI case. This closes a test-placement blocker, not a feature or native evidence promotion; final exact-head CI stays open.

Native placement proof2026-11-03: both oracle collections8;actual9.0.9exec4passed+4unsupportedwriter10skips (notpasses),actual10.0.6exec8passed. Pureunitcollection100contains0completeCLIcases;100unitcases pass with KicadCli.run forbidden. Both moved function bodies/parameters and sharedtab_project AST are unchanged; only supported-version markers were added. Ruff/format/diff and strictOpenSpec pass. Source/receipts in c0363 native-proof-placement.json; final exact-head CI remains open.
