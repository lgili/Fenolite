## 1. Contract definitions

- [x] 1.1 Write `openspec/specs/cli-contract/spec.md` and `openspec/specs/package-layering/spec.md` are promoted from this change's specs at archive time; meanwhile add `docs/cli-contract.md` (human summary: modes, envelope, errors, exit codes, mutation protocol, determinism flags). Proof: file exists; reviewed against the spec.
- [x] 1.2 Implement `src/fenolite/cli/exitcodes.py` (`ExitCode` IntEnum 0–7) and the `FEN-NNNN` error-code families with a small registry (`errors.py`). Proof: `uv run pytest tests/unit/cli/test_exitcodes.py`.

## 2. Framework

- [x] 2.1 Implement `src/fenolite/cli/output.py`: `Envelope`, `Issue`, `Evidence`, `Receipt` dataclasses; TTY detection; `--json/--text` precedence; `--fields` projection; text renderer; stderr error writer. Proof: `uv run pytest tests/unit/cli/test_output.py`.
- [x] 2.2 Implement `src/fenolite/cli/main.py`: global flags (`--json`, `--text`, `--fields`, `--seed`, `--timestamp`, `--no-backup`), `cmd_*` auto-discovery, `argparse` error interception → exit 2, exception interception → exit 1, mutation protocol (`--dry-run`/`--confirm`, plan, atomic writes via `fenolite.core.io`, receipts). Proof: `uv run pytest tests/unit/cli/test_main.py`.
- [x] 2.3 Implement hidden `src/fenolite/cli/cmd__echo.py` exercising every branch (`--issue`, `--raise`, `--write`, `--gen-id`). Proof: `uv run fenolite _echo --json | python -m json.tool`.
- [x] 2.4 Implement `src/fenolite/cli/cmd_capabilities.py` (commands, backends registry stub, extras detection via `importlib.util.find_spec`, external tools detection with version strings, `sends_data_offsite`). Proof: `uv run fenolite capabilities --json --fields tools`.

## 3. Schemas

- [x] 3.1 Write `tools/gen_schemas.py` (stdlib-only dataclass → JSON Schema 2020-12) and generate `schemas/fenolite.envelope.v0.json` and `schemas/fenolite.error.v0.json`. Proof: `uv run python tools/gen_schemas.py --check` exits 0.
- [x] 3.2 Write `tests/unit/test_schema_drift.py` (regeneration must not change a byte) and add a stdlib JSON-Schema validator subset (`tests/_schema.py`) sufficient for the envelope (types, required, enum, pattern). Proof: `uv run pytest tests/unit/test_schema_drift.py`.

## 4. Consistency and layering tests

- [x] 4.1 Write `tests/consistency/test_cli_consistency.py` (enumerate commands; `--help`; envelope validity; text mode; `--fields`; error mapping; mutation protocol for mutating commands; determinism on `_echo`). Proof: `uv run pytest tests/consistency -q`.
- [x] 4.2 Write `tests/unit/test_import_graph.py` (AST-based edge check with the allowed-edge table; exempt non-existent packages; verify third-party imports are guarded outside core/model/geometry/dsl). Proof: `uv run pytest tests/unit/test_import_graph.py`.
- [x] 4.3 Add a pseudo-terminal test for TTY detection (`pty.openpty`, skipped on Windows). Proof: `uv run pytest tests/unit/cli/test_tty.py`.

## 5. Documentation

- [x] 5.1 Update `AGENTS.md` with the contract (JSON outside TTY, exit codes, `--dry-run` then `--confirm`, `--fields`, `capabilities` first) and `README.md` with a three-line example. Proof: review.

## 6. Closing

- [x] 6.1 Run `uv run pytest tests/residue` (or the interim grep from c0001 if c0003 has not landed). Proof: exit 0. _(Interim scan over all non-ignored files: no hits.)_
- [x] 6.2 Update evidence labels: `capabilities` and `_echo` documented as `UNVERIFIED` (no external oracle applies). Proof: `docs/evidence/` note.
- [x] 6.3 `CHANGELOG.md`: "CLI contract v0: envelope, exit codes 0–7, mutation protocol, capabilities command". Proof: `git diff CHANGELOG.md`.
