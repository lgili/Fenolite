## 0. Entry check

- [x] 0.1 Find where the default `off` is stated: the requirement "Component bodies in an Altium build" (`altium-build`, added by c0121) and the scenario "Body height" of "Component bodies are reported" (`altium-pcb-writer`, modified by c0121). c0121 is not archived (it waits for c0090), so both deltas start from c0121's text. Proof: `openspec validate c0155-altium-bodies-default --strict --no-interactive` passes.
  - 2026-10-09: no living spec states the default; both requirements stand in c0121's deltas only, and the deltas here copy them with the default changed. c0155 is archived after c0121.

## 1. The default

- [x] 1.1 Set `DEFAULT_ALTIUM_BODIES` in `src/fenolite/cli/cmd_build.py` and the default of `bodies` in `lens.altium.build_altium` to `extruded`; leave `write_model`, `lower.from_design`, `lower.write_design`, `AltiumBackend.write` and `model_roundtrip` at `off`; reword the help text and the docstrings that said the option is off by default (scenarios "Without the option", "Off on the command line", "Sample with bodies"). Proof: `uv run pytest tests/unit/cli/test_build_altium.py -k bodies_option tests/unit/lens/test_altium_bodies.py tests/unit/lens -k "altium and (samples or golden or pinned)"`.
  - 2026-10-09: done. The proof passes; `tests/unit/lens/test_altium_pcb_complete.py::test_board6_golden_files` pinned `result.pcb.bodies` as `off` and now reads `extruded` (board6 holds no body, its files do not move); the test of the command is renamed `test_bodies_option_is_extruded_by_default_and_changes_no_byte`; `test_bodies_are_written_by_default` builds `body2` without `bodies` and gets the committed files.
- [x] 1.2 Check that no committed file and no pin moves: every golden test of `tests/unit/lens`, `tests/unit/lens/test_build_bytes_pinned.py -k altium`, the kit tests, `git status --short tests/data` prints nothing. Proof: `uv run pytest tests/unit -q`.
  - 2026-10-09: `uv run pytest tests/unit -q -n 4`: every golden, pinned and kit test passes with the new default, and `git status --short tests/data` prints nothing: no committed file, no pinned digest and no kit file moved, so nothing was regenerated. (The same run failed three agent-page tests, fixed by regenerating the guide in task 2.1, and four routing-budget tests that time a router under load; they pass on their own: `uv run pytest tests/unit/cli/test_route_cmd.py tests/unit/routing -q`.)

## 2. Pages

- [x] 2.1 `docs/altium.md`, `docs/cli-contract.md`, step X8 of `docs/evidence/altium-pcb.md`, the agent guide (`uv run python tools/gen_agent_guide.py`), `docs/roadmap.md` ("Open decisions", row 33, and the row of this change) and `openspec/README.md`. Proof: `uv run python tools/gen_agent_guide.py --check`; `uv run pytest tests/consistency tests/unit/test_repo_layout.py -q`.
  - 2026-10-09: done; `tools/gen_agent_guide.py` rewrote `references/commands.md` (the help text of the option) and `--check` passes.

## 3. Closing

- [x] 3.1 Run tests/residue and the manifest test. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py -q`.
  - 2026-10-09: `uv run pytest tests/residue tests/corpus/test_manifest.py -q` passed (run with `tests/consistency` and `tests/unit/test_repo_layout.py`: 642 passed, 22 skipped).
- [x] 3.2 Update evidence labels: no row moves (the default rests on `H-A-PCBX-BODY-OPEN` and `-LIB`, author reports since 2026-10-09); the generated pages are current. Proof: `uv run python tools/gen_evidence_matrix.py --check`.
  - 2026-10-09: no row moves; `tools/gen_evidence_matrix.py`, `gen_schemas.py`, `gen_token_docs.py` and `gen_agent_guide.py` with `--check` exit 0.
- [x] 3.3 Add to `CHANGELOG.md` under `[Unreleased]` the change of the default, in bold; run the fast checks. Proof: `make check-fast PYTEST_WORKERS=3`.
  - 2026-10-09: one bold line under `[Unreleased]`, `### Changed`. `make check-fast PYTEST_WORKERS=3` on the branch `dev-bodies-default`, after the archive of c0085: exit 0.
