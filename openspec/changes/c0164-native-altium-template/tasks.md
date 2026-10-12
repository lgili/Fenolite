## 1. Entry and native composition
- [x] 1.1 Read the living altium-build and sheet-templates specs and public format facts; validate this delta. Proof: `openspec validate c0164-native-altium-template --strict --no-interactive`.
- [x] 1.2 Implement native binary composition with authored tests for page settings, fonts, ownership, parameters, images, extra streams and refusals. Proof: `uv run pytest tests/unit/backends/altium/test_native_template.py -q`.

## 2. Build option
- [x] 2.1 Add the option, reviewed input dependency, per-sheet application, unchanged template copy and result metadata, with CLI tests for flat and hierarchical builds and stale plans. Proof: `uv run pytest tests/unit/cli/test_build_native_template.py -q`.

## 3. Documentation and proof
- [x] 3.1 Teach the flag, its limits and evidence; update changelog, backend provenance and session ledger, and regenerate the agent guide and evidence matrix. Proof: generated-page checks; `uv run pytest tests/unit/agent/test_pages.py tests/unit/backends/test_evidence_declared.py tests/unit/test_evidence_matrix_page.py tests/unit/test_provenance.py -q`.
- [ ] 3.2 Run the focused build/template regression tests and `make check-fast`. Record results here; leave the full suite to the pre-merge gate. Proof: focused tests and `make check-fast` pass.
- [x] 3.3 Locally apply the caller's template outside the repository and check page/font/owner/storage preservation. Record only generic outcomes, no project data. Altium appearance remains unverified until the caller opens it.

### Recorded proofs

- 2026-10-12: strict OpenSpec validation passed; native backend and CLI tests: 22 passed.
- Agent guide and evidence matrix generation checks passed; guide, evidence declarations, matrix and provenance tests: 82 passed.
- Native caller-template checks outside the repository passed: unchanged copy, original sheet settings and fonts retained, owners precede children, Storage byte-identical on every generated sheet. No Altium UI run was possible.
- The unfiltered fast gate initially reported 8 failures. Four evidence-declaration/matrix failures and the new-week session-ledger failure were corrected and their proof tests passed. The remaining baseline faults are the unsigned starting commit `1e3e21fc` (`save`) and both variants of `test_the_lowering_writes_the_former_documents`, whose expected table lacks `blink_official/design.py`. The latter were reproduced in a snapshot of the unchanged starting commit. No baseline commit was rewritten and no unrelated golden was changed. Task 3.2 stays open until the unfiltered gate passes.

- Final focused regressions, new native-template tests and documentation/evidence proofs: **207 passed**.
- Final fast gate with exactly the three proven baseline failures deselected: **13148 passed, 27 skipped**, exit 0; ruff, format, pyright and generated-guide checks passed, residue scan had zero hits with the private gate enabled. The command used `PYTEST_ADDOPTS` with explicit `--deselect` entries for the DCO repository-history test and the flat/modules former-document tests; no other test was excluded beyond the normal fast markers. This does not close task 3.2, whose unfiltered proof still requires the baseline fixes.
