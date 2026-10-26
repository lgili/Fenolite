## Why

On 2026-10-08 the `kicad-9` job (image `kicad/kicad:9.0.9`, oracle tests on pytest-xdist workers) failed twice, each time on a commit that passed the same tests in another run:

1. `tests/kicad/check/test_erc_oracle.py::test_stage_schematic_the_tool_cannot_load`: the ERC stage's message was "kicad wrote no ERC report: Warning: Invalid lock file '/tmp/org.kicad.kicad/instances/kicad-cli-9.0'." where "Failed to load schematic" was expected.
2. `tests/kicad/sheets/test_sheet_acceptance.py::test_controls[iso5457_generic]`: the broken drawing sheet came out `absent` where `reject` was expected (no "Error loading drawing sheet").

The same message was seen before: by 10.0.6 in the `kicad-10` job (c0051, "Found outside this change"), in the worksheet boundary oracle (c0082, which isolated that one test by hand), and in the first attempt of the 0.2.2 release run (`docs/release/v0.2.md`). Each time the test passed again on a second attempt.

The message names one file in the shared system temporary folder, named by program and major only: every `kicad-cli` 9 process on the machine uses the same lock file. The package runner already gives each run its own folder and `KICAD_CONFIG_HOME`, but passes the caller's `TMPDIR` and XDG folders, so parallel workers (and a user running two `fenolite` commands at once) still share that file. A process that finds the lock file half-written by another prints the warning and, as both failures show, can lose its usual result.

## Outcome in one paragraph

**Every `kicad-cli` run of the package runner gets its own temporary, runtime, cache and state folders, removed with the run.** `private_state(root)` creates `tmp`, `runtime`, `cache` and `xdg-state` (mode 0700) under the run folder's reserved `.fenolite-state/` and names them in `TMPDIR`, `TMP`, `TEMP`, `XDG_RUNTIME_DIR`, `XDG_CACHE_HOME` and `XDG_STATE_HOME`; `KICAD_CONFIG_HOME`, `LANG`, `LC_ALL` and the caller's `env` entries are applied as before. The tests' own `kicad-cli` helpers (`_kicad.run_raw`, `run`, `supported_version`, `_libs.isolated_kicad_env`, and the Altium oracles' inline environments through `_kicad.oracle_env`) get the same folders. Outputs do not change.

## What Changes

- **`backends/kicad/cli.py`**: `STATE_DIR` (`.fenolite-state`), `RESERVED_DIRS`, `STATE_VARIABLES`, `private_state`; `KicadCli.run` passes the run's private state; `DockerCli` passes none (each container has its own `/tmp`, and the `docker` client keeps the caller's `XDG_RUNTIME_DIR`). A run file name under `.fenolite-state/` is refused like one under `config/`.
- **`backends/kicad/projectset.py`, `cli/cmd_bom.py`**: the reserved names are `RESERVED_DIRS` (a project folder `.fenolite-state` is skipped as `reserved-name`).
- **Tests' helpers**: `tests/_kicad.py` (`_call`, `oracle_env`), `tests/_libs.py`, and the 14 Altium and corpus oracles that built `{**os.environ, "KICAD_CONFIG_HOME": …}` by hand.
- **Tests**: unit tests of the environment (`test_cli_runner.py`, `test_docker_cli.py`, `test_projectset.py`); the oracle stress test `tests/kicad/check/test_parallel_runs_oracle.py` (eight runs at once, and the measurement of where the instance folder goes).
- **Pages**: `docs/formats/kicad/cli.md` ("Per-run state"), `docs/hypotheses.md` (`H-K-CLI-STATE`), `docs/evidence/sources.md` (S-0703, S-0704, S-0705).

Size: 0.75 design-day (a size, not time).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `kicad-oracle`: ADDED "Private state per kicad-cli run", "Reserved state folder", "Docker runs keep the caller's state" and "Oracle tests run kicad-cli with private state".

## Non-goals

- No change to `KICAD_CONFIG_HOME` handling, to the configuration the tests' raw helpers use (the caller's, as before), or to `HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME` and `XDG_DATA_DIRS` (fonts and user data are only read).
- No change to `tools/kicad_token_fuzz.py` (its own runner) or to the one-line `version` probes of `capabilities` and `doctor`.
- No test is skipped, retried or marked flaky.

## Evidence level required

- The cause: `INFERRED` from the message text and path printed by 9.0.9 and 10.0.6 in CI and from the failures being transient (`H-K-CLI-STATE`).
- That the instance folder follows `TMPDIR`: measured by `test_instance_folder_follows_tmpdir`, owed to the `kicad-9` and `kicad-10` jobs; no `kicad-cli` exists where this change was written.
- The variables: S-0703 (POSIX `TMPDIR`), S-0704 (XDG Base Directory specification), S-0705 (Python's `tempfile`).

## Impact

- Changed: `src/fenolite/backends/kicad/cli.py`, `projectset.py`, `src/fenolite/cli/cmd_bom.py`; the tests' helpers and oracles above; the pages above; `CHANGELOG.md`, `openspec/README.md`.
- Behaviour: a `kicad-cli` run started by `fenolite` sees private `TMPDIR`, `TMP`, `TEMP`, `XDG_RUNTIME_DIR`, `XDG_CACHE_HOME` and `XDG_STATE_HOME`. KiCad's caches no longer persist between runs (they did not persist between `KICAD_CONFIG_HOME` folders either). A project subfolder named `.fenolite-state` is not copied for a run.
