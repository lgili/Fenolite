## 1. One dispatcher, two printers

- [x] 1.1 Make `_perform`, `_dispatch` and `_failed` of `fenolite/cli/main.py` return a reply value that `main` prints; add `invoke(argv, *, cwd)`, the in-process parser and `Context.in_process` (design, decisions 1, 2 and 4). Proof: `uv run pytest tests/unit/cli -q -x`.
  - 2026-10-28: proof passed (1495 passed, 3 skipped).

## 2. The runner

- [x] 2.1 Add `fenolite.api.run` and `Reply`, importing the CLI inside `run`, and the `LAZY` table of the layering test (scenarios "Lazy edge only", "Nothing printed" and "Terminal-only forms refused"). Proof: `uv run pytest tests/unit/test_import_graph.py tests/unit/api/test_run_api.py -q`.
  - 2026-10-28: proof passed (53 passed).
- [x] 2.2 Compare `run` with the command line for every command's examples, and run the mutation protocol of every writing command in process (scenarios "Same envelope as the command line" and "Plan, review, write"). Proof: `uv run pytest tests/consistency/test_api_run.py -q`.
  - 2026-10-28: proof passed (70 passed: 45 commands compared, 24 writing commands through the protocol, one plan crossed to the command line).

## 3. Typed calls

- [x] 3.1 Add `read_design`, `read_board` (`Board`), `connectivity`, `analyze_current`, `analyze_distances` and `ExtraMissingError` (scenarios "Records, not dictionaries" and "Same measures as analyze"). Proof: `uv run pytest tests/unit/api/test_board_api.py -q`.
  - 2026-10-28: proof passed (7 passed).

## 4. Documentation

- [x] 4.1 Write `docs/api.md` with every public name, frozen for 1.0, a line under "Output" of `docs/cli-contract.md`, and the CHANGELOG entry (scenario "Every public name documented"). Proof: `uv run pytest tests/unit/api/test_run_api.py -k page -q`.
  - 2026-10-28: proof passed (1 passed).
- [x] 4.2 Validate the change and run the guide, layering, hypothesis and consistency suites. Proof: `openspec validate c0206-python-api --strict --no-interactive`, `uv run ruff check`, `uv run ruff format --check`, `uv run pyright src` and `uv run pytest tests/unit/agent tests/unit/test_import_graph.py tests/unit/test_inferred_hypotheses.py tests/consistency tests/unit/api -q`.
  - 2026-10-28: the change is valid; ruff, format and pyright clean; the suites passed (682 passed, 27 skipped).
- [x] 4.3 CI on the integrated branch: `make check` green on the head that holds this change (the coordinator integrates the branch; AGENTS.md, workflow 4). Proof: the required jobs green on that commit. Done 2026-10-28: `make check-fast` passed on the integrated head (14366 passed, 41 skipped), and every CI job (unit on Ubuntu 3.11 to 3.13, macOS and Windows, kicad-9, kicad-10, routing on KiCad 9 and 10, viewer, wheel, dco) passed on `dev-c0204-c0209` at 01068dd (run 40703612332).
