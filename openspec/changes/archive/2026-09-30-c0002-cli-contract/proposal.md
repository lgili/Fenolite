## Why

Fenolite's primary users are AI coding agents and CI pipelines, not humans at a terminal. Every command added later (`build`, `check`, `export`, `inspect` …) must speak one stable, machine-readable contract from day one: JSON when not on a TTY, a fixed envelope, a fixed exit-code vocabulary, typed errors, an explicit confirmation protocol for mutations and an evidence label on every answer. Freezing this contract before the first real command avoids a breaking rewrite later and lets agents learn the tool once.

## What Changes

- `fenolite.cli` framework: `main.py` (dispatcher, global flags), `output.py` (envelope, TTY detection, `--fields` projection, text renderer), `exitcodes.py` (the 0–7 vocabulary), auto-discovery of `cmd_*.py` modules, `capabilities` command.
- Envelope `fenolite.envelope.v0` on stdout for every command; typed error object on stderr; JSON Schema for both generated into `schemas/`.
- Exit-code vocabulary: `0` ok · `1` internal failure · `2` usage error · `3` input unreadable or from a future format version · `4` confirmation required · `5` verification produced findings · `6` external tool missing or incompatible · `7` requested operation is not representable without loss.
- Mutation protocol: `--dry-run` (structured plan, exit 0, nothing written) and `--confirm` (required to write; otherwise exit 4 with the plan); atomic writes with `.bak`; receipts listing every written path with SHA-256.
- Determinism flags `--seed` and `--timestamp` accepted globally.
- `tests/consistency/test_cli_consistency.py`: every registered command must honour `--help`, `--json`, `--text`, `--fields`, the envelope and the exit codes.
- `tests/unit/test_import_graph.py`: the allowed import edges between packages (layering), enforced from this change on.

## Capabilities

### New Capabilities
- `cli-contract`: output modes, envelope, errors, exit codes, mutation protocol, determinism flags, `capabilities` command, consistency test.
- `package-layering`: allowed dependency edges between `fenolite` sub-packages and the test that enforces them.

### Modified Capabilities
- (none)

## Non-goals

- No domain commands yet (`build`, `check`, `export` arrive with `c0009`–`c0013`); this change ships `capabilities`, `--version`, `--help` and a hidden `_echo` command used by the consistency test.
- No MCP server, no pagination (`--limit/--cursor`, v0.2a), no `explain <code>` (v0.2a), no `restore` (v0.2a).
- No third-party CLI framework (stdlib `argparse` only).

## Evidence level required

- Contract behaviour is verified by unit and consistency tests on both CI operating systems (mechanical). Evidence labels carried in the envelope default to `UNVERIFIED` until a command sets a higher level; the label vocabulary itself is defined in `c0004-design-model-core` (`fenolite.core.evidence`).

## Impact

- Every future `cmd_*.py` depends on `fenolite.cli.output` and `fenolite.cli.exitcodes`.
- `schemas/fenolite.envelope.v0.json` and `schemas/fenolite.error.v0.json` become public artefacts; changing them before 1.0 requires a change that bumps the schema id.
- `AGENTS.md` and the future `agent/SKILL.md` describe this contract to agents.
