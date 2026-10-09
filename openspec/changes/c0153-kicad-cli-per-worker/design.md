## Outcome in one paragraph

**Give every `kicad-cli` run its own temporary, runtime, cache and state folders.** The package runner already runs each command in a fresh folder with its own `KICAD_CONFIG_HOME`; it now also creates `.fenolite-state/{tmp,runtime,cache,xdg-state}` there (owner only) and points `TMPDIR`, `TMP`, `TEMP`, `XDG_RUNTIME_DIR`, `XDG_CACHE_HOME` and `XDG_STATE_HOME` at them. The folder goes with the run folder. The tests that run `kicad-cli` without the runner get the same folders through two helpers.

## Context

- **The failures.** Two tests of the `kicad-9` job failed on 2026-10-08 and passed elsewhere on the same code. The ERC stage's message held kicad-cli's whole stderr: "Warning: Invalid lock file '/tmp/org.kicad.kicad/instances/kicad-cli-9.0'." and nothing else, so the run lost its usual "Failed to load schematic". The drawing-sheet control lost its "Error loading drawing sheet" and was judged `absent`. The ERC stage already keeps kicad-cli's stderr when no report is written ("kicad wrote no ERC report: …"), which is what made the cause visible; it is unchanged.
- **Earlier sightings.** 10.0.6 printed the same message for `kicad-cli-10.0` in the `kicad-10` job (c0051, `test_pcbdoc_oracle.py`, through a raw `subprocess.run` with only `KICAD_CONFIG_HOME` set). c0082 saw a worksheet probe lose its rejection message next to the lock warning and isolated that one test by passing `HOME`, the XDG folders and `TMPDIR` by hand. The 0.2.2 release run failed once the same way (`docs/release/v0.2.md`).
- **The CI job.** `uv run pytest tests/kicad -q -rA -n auto --dist loadfile` in one container: one `/tmp` and one root user for every worker, so every `kicad-cli` process of one major names the same lock file.
- **Who launches `kicad-cli`.** In `src`: `KicadCli.run` (every command and helper, through `cli_for`), plus one-line `version` probes in `capabilities` and `doctor`. In the tests: the runner (`_probes.runner()`, the check, sheet, board and export oracles), `tests/_kicad.py` (`run_raw`, `run`, `supported_version`, used by about a dozen oracle files), `tests/_libs.py` (`isolated_kicad_env`), and 14 Altium and corpus oracles that call `subprocess.run` with `{**os.environ, "KICAD_CONFIG_HOME": …}`. `tools/kicad_token_fuzz.py` has its own runner and is run alone.

## The evidence for the cause

1. The message is the tool's own and names the file: `org.kicad.kicad/instances/kicad-cli-<major>.0` under `/tmp`, the system temporary folder. The name holds the program and the major and nothing per process, so every `kicad-cli` of one major on the machine uses it.
2. Each failure was a run that printed the message and lost its usual result; every such test passed on a second attempt and in other runs of the same commit. Nothing else in those runs is shared between workers: each run had its own folder and its own `KICAD_CONFIG_HOME`.
3. Fenolite passes the caller's `TMPDIR` (unset in the container, hence `/tmp`). With a private `TMPDIR` per run the folder that holds the lock file is per run, so no other process can see it; this is measured by `test_instance_folder_follows_tmpdir` (owed to CI, since no `kicad-cli` exists where this change was written). Until then the row `H-K-CLI-STATE` is `INFERRED`. No KiCad source was read.

## Decisions

1. **Per run, not per worker.** A run already has a fresh folder; the state goes inside it (`.fenolite-state/`), so it is removed with the run, needs no new cleanup path, and also covers a user running two `fenolite` commands at once and threads inside one process. A per-worker folder would not cover those.
2. **Which variables.** Only folders a process writes transient state to: `TMPDIR` (POSIX, S-0703), `TEMP` and `TMP` (read by Python's `tempfile` and by Windows programs, S-0705), `XDG_RUNTIME_DIR`, `XDG_CACHE_HOME` and `XDG_STATE_HOME` (S-0704). `KICAD_CONFIG_HOME` is already per run. `HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME` and `XDG_DATA_DIRS` are left alone: fonts and other data the tool only reads live there, and moving them could change a rendered output. Each folder is mode 0700, as the specification requires of `XDG_RUNTIME_DIR`.
3. **Order of the environment.** Caller's environment without `KICAD*`, then the private state, then `KICAD_CONFIG_HOME`, `LANG`, `LC_ALL`, then the caller's `env`. A probe that names its own `TMPDIR` (c0082's worksheet oracle) still wins, as it does for `KICAD_CONFIG_HOME`.
4. **Reserved name.** `.fenolite-state` joins `config` in `RESERVED_DIRS`: refused as a run file name, never an output, skipped by the copy set (`reserved-name`) and by `bom`'s sheet scan. A dot name is unlikely to be a project folder.
5. **Docker.** `DockerCli` passes no private state: each container (`--rm`) has its own `/tmp`, and the `docker` client needs the caller's `XDG_RUNTIME_DIR`, where a rootless daemon's socket lives. Its command line is unchanged.
6. **Tests' helpers.** `_kicad._call` runs `run_raw`, `run` and `supported_version` with private state in a temporary folder (the configuration stays the caller's, as before, since those tests rely on it); `_kicad.oracle_env(config)` replaces the 14 inline environments, keeping their `KICAD_CONFIG_HOME` and adding `kicad-state` beside it; `_libs.isolated_kicad_env` adds it too.
7. **Not changed.** The `version` probes of `capabilities` and `doctor` (one short run each, never in parallel within a command) and `tools/kicad_token_fuzz.py`.

## Tests

- `tests/unit/backends/kicad/test_cli_runner.py`: `private_state` makes owner-only folders and is idempotent; a run sees the six variables inside `<tmp>/.fenolite-state/`, whatever the caller's; what the tool writes there is not an output; eight runs at once get eight temporary folders, all removed; an explicit `env` entry wins; `oracle_env` keeps the configuration folder; `.fenolite-state/x` is refused.
- `tests/unit/backends/kicad/test_docker_cli.py`: the `docker` client keeps the caller's `XDG_RUNTIME_DIR` and `TMPDIR`, and the command passes only the three variables it passed before.
- `tests/unit/backends/kicad/test_projectset.py`: a row under `.fenolite-state/` is skipped as `reserved-name`.
- `tests/kicad/check/test_parallel_runs_oracle.py` (`needs_kicad`, run by the `kicad-9` and `kicad-10` jobs): eight runner `version` runs, eight `sch erc` runs of an unloadable schematic and eight raw `run_raw("version")` runs at once all give their usual result and print no lock message; with `TMPDIR` given, the instance folder is created there.

## Released output

`backends/kicad/cli.py`, `backends/kicad/projectset.py` and `cli/cmd_bom.py` change. No written file changes: the variables touch only where the tool keeps its own transient state.

## Size (design-days)

| group | dd |
|---|---|
| cause, launchers, pages | 0.25 |
| runner, helpers | 0.25 |
| tests | 0.25 |

Total: 0.75. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `kicad-oracle`: ADDED "Private state per kicad-cli run", "Reserved state folder", "Docker runs keep the caller's state" and "Oracle tests run kicad-cli with private state". No open change touches "Package kicad-cli runner", which stays as it is.
