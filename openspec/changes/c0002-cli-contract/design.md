## Context

Agent-first CLIs converge on the same practices (structured output when not on a TTY, field selection, typed errors with hints, small fixed exit-code sets, confirmation as a non-interactive protocol, receipts, dry-run diffs, a capabilities endpoint, additive-only evolution after 1.0). The `kicad-cli` verification commands already use exit code 5 for "violations found"; Fenolite mirrors it so CI scripts compose. This change builds the framework once; every later command plugs into it.

## Goals / Non-Goals

**Goals:**
- One dispatcher, one envelope, one error shape, one exit-code table, one consistency test.
- Mutations are impossible by accident: writing requires `--confirm`; `--dry-run` shows the plan.
- Agents discover the tool in one call (`fenolite capabilities --json`).

**Non-Goals:**
- Interactive prompts of any kind (never).
- Command implementations, pagination, `explain`, `restore`, MCP (later changes).

## Decisions

1. **`argparse` (stdlib) with a thin registry.** `fenolite/cli/main.py` scans `fenolite.cli.cmd_*` modules; each exports `register(subparsers) -> None` and a `run(args, ctx) -> Envelope` function. Alternatives: `typer`/`click` (rejected: runtime dependency in the core; the core is stdlib-only).
2. **Output mode.** `output.py` decides: `--json` forces JSON, `--text` forces text, otherwise JSON if `not sys.stdout.isatty()`, text if it is. Text mode renders the same envelope (never a different data set) through a small formatter; JSON is `json.dumps(envelope, ensure_ascii=False, sort_keys=False, indent=None)` followed by a newline. `--fields a,b.c` projects dotted paths on `result` and always keeps `ok`, `command`, `schema`, `issues`, `evidence`, `receipt`.
3. **Envelope `fenolite.envelope.v0`** (a frozen dataclass in `output.py`):
   `ok: bool`, `command: str`, `schema: str` (`"fenolite.<cmd>.v0"`), `input: {path, sha256, kind, format_version} | null`, `result: object`, `issues: list[Issue]`, `evidence: {level, oracle, hypotheses}`, `receipt: {written: [{path, sha256}], backup: [paths]} | null`, `elapsed_ms: int`. `Issue` is `{code, severity, message, where, hint, retryable}` with `severity ∈ {error, warning, info}` and `code` matching `^[a-z][a-z0-9]*(\.[a-z0-9-]+)+$` (e.g. `kicad.drc.clearance`). Until `c0004` lands, `evidence.level` is the literal `UNVERIFIED`; afterwards it is `fenolite.core.evidence.Level`.
4. **Errors on stderr** as one JSON object `{code: "FEN-NNNN", message, hint, retryable, where}` when in JSON mode, or a one-line `error FEN-NNNN: message (hint)` in text mode; codes are allocated by family: `FEN-1xxx` internal, `FEN-2xxx` usage, `FEN-3xxx` input, `FEN-4xxx` confirmation, `FEN-5xxx` findings, `FEN-6xxx` external tools, `FEN-7xxx` capability loss — the first digit equals the exit code.
5. **Exit codes** live in `exitcodes.py` as an `IntEnum` (`OK=0, INTERNAL=1, USAGE=2, INPUT=3, CONFIRM_REQUIRED=4, FINDINGS=5, TOOL=6, LOSSY=7`). `argparse` usage errors are intercepted to return 2 with the typed error, never `argparse`'s default text.
6. **Mutation protocol.** Commands declare `mutates = True`. The dispatcher then: (a) always computes a `plan` (list of intended writes with kind and path); (b) with `--dry-run` returns the plan in `result.plan`, exit 0, writes nothing; (c) without `--confirm` returns the plan, exit 4, error `FEN-4001`; (d) with `--confirm` performs writes through `fenolite.core.io.atomic_write` (temp file + rename, `.bak` of any overwritten file unless `--no-backup`) and fills `receipt`. `--dry-run` and `--confirm` together are a usage error.
7. **Determinism flags.** Global `--seed INT` and `--timestamp ISO8601` are parsed by `main.py` and placed in `ctx`; commands that generate ids or dates MUST take them from `ctx`; the consistency test asserts that a mutating command run twice with the same flags produces byte-identical outputs on the hidden `_echo` fixture.
8. **`capabilities` command.** Static in this change: lists commands (name, mutates, schema id), backends (empty), extras detected (`geo`, `kicad-ipc`, …), external tools detected with version (`kicad-cli`, `java`, `docker` — detection only, no invocation of their subcommands yet), `sends_data_offsite: false`. The generated matrix (detect/read/write/roundtrip/verified_by) is v0.2a.
9. **Consistency test.** `tests/consistency/test_cli_consistency.py` enumerates registered commands and, for each: `--help` exits 0; invocation with `--json` yields an envelope that validates against `schemas/fenolite.envelope.v0.json`; `--text` yields at least one line; `--fields` restricts `result`; a forced internal exception maps to exit 1 with `FEN-1xxx`; unknown flag maps to exit 2; mutating commands without `--confirm` exit 4. The hidden `_echo` command exercises every branch.
10. **Schemas.** `tools/gen_schemas.py` (dev-only, stdlib) converts the envelope and error dataclasses into JSON Schema draft 2020-12 files under `schemas/`; `tests/unit/test_schema_drift.py` fails if regenerating changes a byte. (`c0004` reuses the same generator for the model.)
11. **Package layering** (`tests/unit/test_import_graph.py`) parses every module's imports with `ast` and asserts the edge set: `core` → stdlib only; `model` → `core`; `geometry` → `core`; `dsl` → `model`, `core`; `lens` → `model`, `backends`; `backends.*` → `model`, `geometry`, `core`; `libs` → `model`, `geometry`; `checks`, `analysis`, `placement` → `model`, `geometry`, `backends.base`; `routing.protocol` → `model`, `geometry`; `routing.plugins.*` → `backends.*`; `templates` → `model`; `cli` → everything; `agent` → `cli`. Packages that do not exist yet are simply absent from the graph; the rule set is the contract.

## Risks / Trade-offs

- [Envelope too rigid for streaming or very large results] → `result` may carry `{"truncated": true, "next": <cursor>}` from v0.2a; the envelope fields stay.
- [Text mode drifting from JSON mode] → text is rendered from the envelope object, never from a separate data path; consistency test compares both.
- [`isatty` misdetection under some runners] → `--json`/`--text` always win; documented in `AGENTS.md`.
- [Exit code 5 collides with tools that use 5 differently] → chosen deliberately to match `kicad-cli`; documented.

## Migration Plan

- First CLI framework; the `c0001` stub `main.py` is replaced. No external consumers.
- After 1.0 the envelope becomes `v1` and only additive changes are allowed; before that, breaking changes bump the `v0` schema file and the `schema` string.

## Open Questions

- Should `--fields` also apply to `issues`? Default: no; issues are always complete because agents act on them.

## Evidence level required before merge

- Mechanical: consistency and unit tests green on ubuntu and macos; `schemas/` regenerated with zero drift.
