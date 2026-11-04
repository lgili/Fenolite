# Proof

## Authored controls before runtime changes

The cluster-only ownership counterexample passed: two intentionally distinct parallel lines one
nanometre apart have one matching clustered candidate, so uniqueness alone is unsafe.
The first correctly configured regression run produced **7 failed, 6 passed** before runtime changes:
explicit writer cases on targets 9/10, end-to-end line/arc imports, and DSL Edge.Cuts support were red;
negative ownership controls already refused honestly. An initial collection used a system pytest
without this worktree's package and was corrected by installing the declared dev extra. A preliminary
control also used an invalid ID prefix and omitted explicit downgrade permission; these harness errors
were fixed before recording the genuine red result.

The final controls cover exact physical root/footprint geometry and widths, distinct one-nanometre
parallel lines, changed integer arc mids, duplicate edge multiplicity, strict ten-micrometre endpoint
gaps, collapsed pieces, transitive clusters spanning eighteen micrometres, and inconsistent logical
outlines. Every successful write preserves all explicit graphics; invalid cases refuse rather than
silently deleting them. The unchanged original exact notched case retains its existing code contract.

## Public reproduction (external only)

All original inputs of the existing public Tiny replay were verified against their recorded SHA-256s
before fresh import. Import and build used dry-run plans and confirmed those reviewed plans.
The native model reconstruction has exactly **11 root edges plus 9 footprint edges**, with exact source
root edge-text and footprint kind/point multisets. No source CAD coordinates were normalized.

Compared as difference multisets with the c0346 replay, verify-source removes exactly five duplicate
L7 graphic rows and the one L8 Edge.Cuts pixel row (311/14602), adds no row, and leaves the **328 existing
field-pose rows exactly unchanged**. Overall exit remains 5 until the independently owned c0345 fix
is integrated. There are no accepted exclusions or tolerance changes. L8 is equal.

KiCad **10.0.6** exported original and rebuilt Edge.Cuts SVGs successfully. The complete native SVG
shape/attribute multisets are exactly equal: **307 shapes on each side**. Font substitution warnings
remain visible in the native stdout/stderr receipt and do not constitute font validation. The first SVG
invocation used deprecated default single-file behavior with a directory output and failed; the explicit
`--mode-multi` invocations succeeded. No source was saved or modified by these exports.

External receipts: `c0349-tiny-explicit/{import-plan,import-receipt,build-plan,build-receipt,
fresh-proof,controlled-delta,native-kicad10-svg,native-svg-geometry}.json` in the overnight artifact
bundle. Public CAD and generated library material remain outside the core repository.

## Focused validation

`uv run pytest tests/unit/importer/test_explicit_edge_ownership.py
 tests/unit/importer/test_notched.py tests/unit/importer/test_outline_width.py
 tests/unit/backends/kicad/test_pcb_write.py tests/unit/backends/kicad/test_outline_write.py
 tests/unit/backends/kicad/test_outline.py tests/unit/dsl/test_drawings.py
 tests/unit/agent/test_pages.py -q` passed **206 cases** on the final candidate.
Ruff check and format checks pass for all touched Python files; targeted Pyright reports zero errors.
Agent-guide generation completed. The private staged residue gate passed: zero hits across sixteen staged files, private gate enabled.

## Validation still required

Root owns the combined default-plan capture, serialized check-fast, full CI on the exact integrated
commit, integration, and archival. No release, push, merge, or archival was performed by this change.
