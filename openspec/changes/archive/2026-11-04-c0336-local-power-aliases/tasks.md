## 0. Review

- [x] 0.1 Verify the ID, current contracts and source, record the actual one-net discrepancy, and validate before code. Proof: strict OpenSpec validation and clean source binding.

## 1. Native rule and focused correction

- [x] 1.1 Author native same-sheet power/local-name positive and unequal/no-power/other-sheet controls; prove the current resolver disagreement independently. Proof: actual KiCad export, complete pin coverage and source hashes.
- [x] 1.2 After the native rule is established, correct only the KiCad same-sheet policy. Prove generic/default behavior, global detection, labels and bus policy remain scoped. Proof: focused authored/unit/native tests, ruff/format/types.
- [x] 1.3 Rerun the actual affected owner rows and current native neighbors with checked inputs. Record counts, names, warnings and every remaining failure without acceptance. Proof: actual source-bound per-row reports.

## 2. Integration

- [x] 2.1 Record public-tool evidence and update CHANGELOG, with model/DSL/schema/dependency invariants. Proof: evidence/format/register controls and strict validation.
- [x] 2.2 Run the root-owned combined fast gate and required exact-head CI before archive. Proof: complete successful logs on the recorded source; native partial proof alone does not close this item.

Closed 2026-11-04: `make check-fast` passed on the batch (22620 passed, 51 skipped); every
required job of CI 41853235387 passed on the exact commit 0bce63e2 (unit on Linux 3.11/3.12/3.13, macOS
after a rerun of a runner-capacity cancellation, Windows; kicad-9, kicad-10, drawn-floor, routing
9/10, viewer, mcp, wheel, dco).
