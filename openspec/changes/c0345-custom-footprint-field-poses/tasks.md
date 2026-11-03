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
