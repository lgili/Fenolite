## 0. Entry check

- [x] 0.1 Move task 7.6 of c0175 with the requirement "Octilinear router plugin" of its `routing` delta into this change, split into the requirements of this change's delta; note the move in c0175's `tasks.md` under "## 7. Copper tidy (package 5)", remove c0175's emptied delta, and add the row of this change to `openspec/README.md`. Proof: `openspec validate c0228-octilinear-router --strict --no-interactive` and `openspec validate c0175-board-engineering-tools --no-interactive`.
  - 2026-10-28: both pass. c0175 is validated without `--strict`, as c0226 records: its other capabilities carry requirements over 500 characters. The MODIFIED "Pairs and escape in a routing job" passes `--strict`.

## 1. Octilinear router

- [x] 1.1 Add the feature `short`, the codes `route.pair-not-routed` and `route.check-refused`, and the plugin with its connections, shapes, acceptance, length limit and rounds, registered as `octilinear` (scenarios "Listed with its features", "Three pads, two connections", "A pad in the way", "Too long stays open", "A blocked connection goes first"). Proof: `uv run pytest tests/unit/routing/test_octilinear.py tests/unit/routing/test_protocol.py tests/unit/routing/test_registry.py tests/unit/test_import_graph.py -q -n 2`.
  - 2026-10-28: proof passed (14 tests of `test_octilinear.py` with the protocol, registry and import-graph tests). The connection blocked in one round is a case found by a search over dots (`BLOCKED`); `capabilities` and `doctor` tests list the new router.
- [x] 1.2 Add pairs (scenario "A sense pair"). Proof: `uv run pytest tests/unit/routing/test_octilinear.py -k pair -q`.
  - 2026-10-28: proof passed. The coupled tracks of the bench keep 0.200002 mm: half the pitch is rounded up by 1 nm.
- [x] 1.3 Add the copper check of the result and the job extras of `fenolite route` (scenarios "A finding refused", "Extras of the route command", "A gate loop routed octilinear"). Proof: `uv run pytest tests/unit/routing/test_octilinear.py tests/unit/cli/test_route_cmd.py -q -n 2`.
  - 2026-10-28: proof passed (`test_octilinear.py` and `test_route_cmd.py`, 267 tests with `tests/unit/routing`). Without a `Default` class name a net's rule subject named no class and the clearance in force was 0: the plugin names `Default` for a net without a class.
- [x] 1.4 Explain the codes (scenario "Codes explained"). Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py tests/unit/routing -k codes -q`.
  - 2026-10-28: proof passed (3 tests, and the 8 of `test_explain_cmd.py`). The two codes are in the `route` table of `docs/cli-contract.md`.

## 2. Proof on KiCad

- [x] 2.1 Register `H-G-OCTI-CHECK` and `H-K-OCTI-DRC`, and prove the gate loop and the sense pair with `kicad-cli`: no violation type grows after `route --router octilinear --confirm`, and with `--gate drc` nothing is dropped. Proof: `uv run pytest tests/kicad/routing/test_octilinear_oracle.py -rA` with the local `kicad-cli`; `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_inferred_hypotheses.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
  - 2026-10-28: proof passed with local `kicad-cli` 10.0.7 (4 oracle cases: on both benches the unconnected items go to none and no violation type grows; `--gate drc` drops nothing, evidence `KICAD-VERIFIED`; 41 unit tests; the matrix is unchanged). The 9.0.9 side waits for the `kicad-9` job.

## 3. Teaching

- [x] 3.1 Teach it: `docs/cli-contract.md` ("route"), `docs/routing.md`, S-0837 and S-0838 in `docs/evidence/sources.md`, the guide's `routing` page with a tested line, the generated `commands` page; CHANGELOG. Proof: `uv run python tools/gen_agent_guide.py --check`; `uv run python tools/gen_schemas.py --check`; `uv run pytest tests/unit/agent tests/consistency tests/corpus/test_manifest.py tests/unit/mcp -q -n 2`.
  - 2026-10-28: proof passed but one case: `tests/unit/agent/test_pages.py::test_budget_holds` (the skill folder holds 260 770 bytes against the limit of 260 000 on the base `1ff3aa8`, which already held 260 336; the integration raises the limit to 300 000 through c0212's agent-guide delta); 760 other cases pass. The guide's `routing` page holds 11 722 bytes; the generated `commands` page is unchanged at 673 lines (no argument changed). No test data file is added.

## 4. Closing

- [x] 4.1 CI on the integrated head. Proof: the required jobs (`kicad-9` and `kicad-10` among them) green on the head that carries this change. Done 2026-10-28: `make check-fast` passed on the integrated head b0ca6b9 (14856 passed, 44 skipped); the fixes after it (corpus census pins, KiCad 9 probe scopes) passed their focused tests, and every CI job (unit on Ubuntu 3.11 to 3.13, macOS and Windows, kicad-9, kicad-10, routing on KiCad 9 and 10, mcp, viewer, wheel, dco) passed on `dev-c0225-c0227` at 171bb10 (run 40756504456).
