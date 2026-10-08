## 0. Investigation

- [x] 0.1 Read the two failures of the `kicad-9` job of 2026-10-08, the earlier sightings (c0051, c0082, the 0.2.2 release run), the `kicad-9` and `kicad-10` jobs of `.github/workflows/ci.yml`, and every place that launches `kicad-cli` in `src` and `tests`. Proof: `design.md`, Context and "The evidence for the cause".
  - **2026-10-08.** Both failing tests run through `KicadCli.run`, which passed the caller's `TMPDIR` (unset in the container); the message names `/tmp/org.kicad.kicad/instances/kicad-cli-9.0`, one file for every process of the major. The ERC stage already keeps kicad-cli's stderr when no report is written; unchanged.

## 1. Facts first

- [x] 1.1 "Per-run state" in `docs/formats/kicad/cli.md`; `H-K-CLI-STATE` in `docs/hypotheses.md`; S-0703, S-0704 and S-0705 in `docs/evidence/sources.md` (each page read on 2026-10-08). Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py -q`.
  - **2026-10-08.** 66 passed.

## 2. Runner and helpers

- [x] 2.1 `cli.private_state`, `STATE_DIR`, `RESERVED_DIRS`, `STATE_VARIABLES`; `KicadCli.run` passes the run's private state, `DockerCli` none; `projectset` and `cmd_bom` skip `RESERVED_DIRS`. Tests: `test_cli_runner.py`, `test_docker_cli.py`, `test_projectset.py`. Proof: `uv run pytest tests/unit/backends/kicad/test_cli_runner.py tests/unit/backends/kicad/test_docker_cli.py tests/unit/backends/kicad/test_projectset.py tests/unit/cli/test_bom_cmd.py -q`; `uv run pyright src`.
  - **2026-10-08.** 89 passed; pyright 0 errors.
- [x] 2.2 The tests' launchers: `_kicad._call` (`run_raw`, `run`, `supported_version`), `_kicad.oracle_env` in the 14 oracles that built their environment by hand, `_libs.isolated_kicad_env`. Proof: `uv run ruff check src tests`; `uv run pytest tests/kicad/altium tests/corpus/test_altium_cfb.py tests/kicad/test_environment.py tests/kicad/check/test_parallel_runs_oracle.py -q` collects and skips without `kicad-cli`.
  - **2026-10-08.** ruff clean; 14 passed, 111 skipped (no `kicad-cli` here).

## 3. Oracle

- [ ] 3.1 `tests/kicad/check/test_parallel_runs_oracle.py` passes on 9.0.9 and 10.0.6: eight runs at once of each kind with their usual result and no lock message, and the instance folder under the given `TMPDIR`; then `H-K-CLI-STATE` is raised to `KICAD-VERIFIED (9.0.x, 10.0.x)` with the run linked. Proof: the `kicad-9` and `kicad-10` jobs.
  - Owed: CI kicad-9/kicad-10 (no `kicad-cli` where this change was written).
- [ ] 3.2 `test_erc_oracle.py::test_stage_schematic_the_tool_cannot_load` and `test_sheet_acceptance.py::test_controls` pass in the `kicad-9` job without a second attempt. Proof: the `kicad-9` job.
  - Owed: CI kicad-9/kicad-10.

## 4. Closing

- [x] 4.1 `CHANGELOG.md` (the line at the end of `[Unreleased]`), `openspec/README.md`. Proof: `uv run python tools/gen_evidence_matrix.py --check`, `tools/gen_schemas.py --check`, `tools/gen_token_docs.py --check`; `uv run pytest tests/residue tests/corpus/test_manifest.py -q`.
- [x] 4.2 `make check-fast`; `openspec validate c0153-kicad-cli-per-worker --strict`. Proof: each exits 0, counts in the commit message.
- [ ] 4.3 Run the full suite once on the rebased branch. Proof: `make check` passes.
  - Not run here: the coordinator runs it once at the merge.
