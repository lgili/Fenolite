## 1. Capability evidence

- [x] 1.1 In `src/fenolite/backends/kicad/backend.py`, compute the report's evidence as `Evidence.combine(pcb.EVIDENCE, pcb.WRITE_EVIDENCE)` (design Decision 1). Write `tests/unit/test_capability_evidence.py` with `report_problems`, its synthetic cases and the live checks. Add the explanation to the "Discovery" section of `docs/cli-contract.md`. Covers the four new scenarios of "Capability reports". Proof: `uv run pytest tests/unit/test_capability_evidence.py tests/unit/cli/test_capabilities_backends.py tests/unit/backends -q`; `uv run fenolite capabilities --json --no-tools --fields backends` prints level `INFERRED` with `H-K-PCB-READ` and `H-K-PCB-WRITE`; `uv run pyright src`.

## 2. Package metadata

- [x] 2.1 Add `[project.urls]` and set the classifier to `Development Status :: 3 - Alpha` in `pyproject.toml`; add `metadata_problems` and its tests to `tests/unit/test_pyproject_invariants.py`. Covers "Metadata checked". Proof: `uv run pytest tests/unit/test_pyproject_invariants.py -q`.
- [x] 2.2 Remove the `route` extra (design Decision 3): `pyproject.toml`, `uv.lock` through `uv lock --offline`, `ALLOWED_EXTRAS`, the extras set of `tests/unit/cli/test_capabilities.py`, the extras sentence of `README.md`. Covers "Invariant test rejects an unknown extra". Proof: `uv lock --offline --check`; `uv run pytest tests/unit/test_pyproject_invariants.py tests/unit/cli/test_capabilities.py -q`; `grep -c freerouting-client pyproject.toml uv.lock` prints 0 twice.
- [x] 2.3 Replace the `exclude` list of the sdist target by the allowlist (design Decision 4); add `sdist_problems` and its tests. Covers "Allowlist checked" and "Built archive". Proof: `uv run pytest tests/unit/test_pyproject_invariants.py -k sdist -q`; with an empty file `AGENTS.md.bak-1` in the root, `uv build --offline --out-dir <scratch>` succeeds, `tar tzf <scratch>/fenolite-*.tar.gz` lists no `openspec/`, `AGENTS`, `CLAUDE`, `packaging/`, `uv.lock`, `Makefile` or `.bak` name, and `unzip -Z1` of the wheel lists the same 178 files as the wheel built before this task.

## 3. Documents, guards and register rows

- [x] 3.1 Add the `## template` section to `docs/cli-contract.md`, each statement checked against a run of the command (design Decision 5); add `undescribed_commands` and the two tests to `tests/consistency/test_cli_consistency.py`. Covers the three scenarios of "Contract page names every command". Proof: `uv run pytest tests/consistency/test_cli_consistency.py -k "contract_names or template_codes" -q`; `uv run fenolite template build src/fenolite/templates/examples/iso5457_generic.sheet.toml --target kicad -o <scratch>/out.kicad_wks --json --dry-run` exits 0 and writes nothing.
- [x] 3.2 Remove the two dead skip guards (design Decision 6). Proof: `uv run pytest tests/unit/backends/kicad/test_rules_text.py tests/unit/backends/kicad/test_projectset.py -q -rs` reports no skip.
- [x] 3.3 Update the results of `H-G-ANGLE` and `H-A-UNIT` in `docs/hypotheses.md` (design Decision 7), levels unchanged. Proof: `uv run pytest tests/corpus/test_board_census.py::test_inexact_numbers_by_context tests/kicad/altium/test_pcbdoc_oracle.py -q` passes on local `kicad-cli` 10.0.6; `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_altium_rows.py tests/unit/verify -q`.
- [x] 3.4 Add the section "Private residue gate" to `docs/provenance.md` (design Decision 8) and `test_gate_documented` to `tests/residue/test_scan.py`. Covers "Section present" and "Gate off without a list". Proof: `uv run pytest tests/residue/test_scan.py tests/unit/test_provenance.py -q`.

## 4. Closing

- [x] 4.1 Run the gates. Proof: `make check-fast` exits 0; `uv run pytest tests/residue -q`; `openspec validate c0052-release-hygiene --strict`.
- [x] 4.2 Evidence labels: confirm that no label moved. Proof: `git diff origin/main -- docs/hypotheses.md` changes only the result and date cells of `H-G-ANGLE` and `H-A-UNIT`; `uv run fenolite capabilities --json --no-tools --fields backends` still prints `INFERRED`.
- [x] 4.3 Add the lines to `CHANGELOG.md` under `## [Unreleased]` (lines of this change only, in the existing "Changed" block; no new heading and no reordering). Proof: `git diff origin/main -- CHANGELOG.md` shows added lines only.
