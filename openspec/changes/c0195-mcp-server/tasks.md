## 0. Entry check

- [x] 0.1 Read the public MCP specification pages the server rests on (versioning, stdio transport, lifecycle of
  `2025-11-25`, `server/discover`, tools, resources, cancellation, progress, the schema of `2026-07-28`) and the
  changes between `2025-03-26`, `2025-06-18`, `2025-11-25` and `2026-07-28` that touch these messages; register
  each page in `docs/evidence/sources.md` with its licence, and write `docs/mcp.md` (the facts, each with its
  source and an evidence label, and the version table). Proof: `uv run pytest tests/unit/test_provenance.py
  tests/unit/test_legal_docs.py -q`; `openspec validate c0195-mcp-server --strict --no-interactive`.
  - 2026-10-26: the current revision is `2026-07-28` (no handshake, `server/discover`, `resultType`, cache fields,
    `ping` removed); the legacy revisions are `2025-11-25`, `2025-06-18` and `2025-03-26` (batches). Sources
    S-0817 to S-0826 (the specification's pages and its four `schema.ts`, Apache-2.0); `docs/mcp.md` written;
    the design's decision 2 corrected with these facts; a clean-room row in `LEGAL-ANNEX.md`. Proof passed.

## 1. Protocol

- [x] 1.1 `fenolite.mcp.protocol`: the stdio loop (lines in, lines out), JSON-RPC parse and errors (`-32700`,
  `-32600`, `-32601`, `-32602`), the modern path (`_meta` version, `-32022`, `server/discover`) and the legacy
  path (`initialize`, `notifications/initialized`, `ping`), `notifications/cancelled` (scenarios "Modern
  discovery", "Legacy handshake", "Unknown version"). Proof: `uv run pytest tests/unit/mcp/test_protocol.py -q`.
  - 2026-10-26: proof passed (16 tests: discover, the modern and legacy eras, the version refused, JSON-RPC
    errors, `ping` for legacy clients only, batches for `2025-03-26` only, resources by era, progress,
    cancellation). The package was added to the layering table first (the MODIFIED "Allowed import edges":
    `mcp` → `cli`, `agent`, standard library only) and has its `PROVENANCE.md`.

## 2. Tools

- [x] 2.1 `fenolite.mcp.tools`: the tool list from `discover()` and `describe()`, the input schemas, the
  annotations, the exclusions, the command line built from the arguments, the refusal of an unknown argument
  (scenario "Tools follow the commands"). Proof: `uv run pytest tests/unit/mcp/test_tools.py -k "listed or schema or
  unknown" -q`.
  - 2026-10-26: proof passed (13 tests). 40 tools; the schemas come from `describe()` and
    `global_arguments()`; a command line uses `--flag=value` and `--` before the positionals, so a value that
    starts with `-` stays a value; a refusal is the command line's `FEN-2001` object naming the argument. The
    shared text moved to the server's `instructions` (design, decision 3): 93 KB to 65 KB of definitions.
- [x] 2.2 The child runner: `python -m fenolite ... --json` in the root, the envelope or the error object, the
  exit code in `_meta`, the timeout, the cancellation, the progress notifications (scenarios "Same reply as the
  command line" and "Error object"). Proof: `uv run pytest tests/unit/mcp/test_tools.py -q`.
  - 2026-10-26: proof passed (20 tests). `fenolite.mcp.backend.FenoliteBackend`: the child in its own process
    group with stdin closed; the envelope equals the command line's but `elapsed_ms`; the error object of a
    non-zero exit; a timeout or a cancellation stops the group (terminate, then kill after 5 s) and gives
    `FEN-1003` (retryable); progress records become increasing reports.
- [x] 2.3 Writes: `--dry-run` without `confirm`, `confirm` without `plan` refused, the staged plan's paths under
  the root, `--read-only` (scenarios "Dry run, then confirm" and "A write outside the root"). Proof:
  `uv run pytest tests/unit/mcp/test_writes.py -q`.
  - 2026-10-26: proof passed (5 tests, in a state folder of the test's own): `init`'s dry run writes nothing
    and returns its plan; the confirmation writes it with a receipt; `confirm` without `plan`, a plan of
    another command and a plan that writes outside the root are refused with `FEN-2001` before the command
    runs; `--read-only` lists no writing tool.

## 3. Resources

- [x] 3.1 `fenolite.mcp.resources`: the guide pages and `capabilities` (scenario "A page read"). Proof:
  `uv run pytest tests/unit/mcp/test_resources.py -q`.
  - 2026-10-26: proof passed (4 tests): every guide page and `fenolite://capabilities` listed; a page's text
    equals the `text` of `fenolite guide <topic> --json` (the `--text` print adds the status line
    `fenolite guide: ok`, so the scenario names the JSON reply); the capabilities reply is run once and kept;
    an unknown URI is not found.

## 4. Command, extras and CI

- [x] 4.1 `cmd_mcp.py` (`--root`, `--read-only`, `--tools`, `--timeout`; scenario "Unknown tool name");
  `capabilities` lists the versions; `tests/unit/test_import_graph.py` and the layering table admit `mcp`.
  Proof: `uv run pytest tests/unit/cli/test_mcp_cmd.py tests/unit/cli/test_capabilities.py tests/unit/test_import_graph.py tests/consistency -q`.
  - 2026-10-26: proof passed (with tests/unit/agent and tests/unit/mcp: 604 passed). `--list` serves nothing and
    returns the versions, tools and resources as an envelope, so that the consistency suite runs the command
    like any other (`example_args` `--list --read-only`); while serving, the command leaves through
    `SystemExit`, so no envelope follows the last message (a real stdio session checks it). `capabilities`
    lists `protocol_versions`. The contract section `## mcp` and the tested lines of the guide page `recovery`
    (part of task 5.1) came here, because the consistency and coverage tests require them for a new command.
- [x] 4.2 Remove the `mcp` extra, add the pinned SDK to `oracles`, update `uv.lock` and the invariants test
  (the MODIFIED "Zero runtime dependencies in the core"). Proof: `uv run pytest tests/unit/test_pyproject_invariants.py -q`.
  - 2026-10-26: proof passed (with test_capabilities, test_agent_skill and test_import_graph: 72 passed). `oracles`
    holds `mcp==2.3.0` (MIT, published 2026-10-02; `uv.lock` moved it from the old `mcp` extra at 2.2.0); the
    README names no `mcp` extra and says the server needs none; `capabilities` lists the four extras.
- [x] 4.3 `test_sdk_oracle.py` and the CI job `mcp` (scenario "The official client agrees"), with its check in
  `tests/unit/test_ci_workflow.py`. Proof: `uv run --extra dev --extra oracles pytest tests/unit/mcp/test_sdk_oracle.py -q`
  passes locally, and the job `mcp` passes in CI.
  - 2026-10-26, OPEN until the job `mcp` passes in CI: the local proof passed (2 tests: a legacy session through
    `initialize`, answered `2025-11-25`, and a modern one through `server/discover`, both listing the
    read-only tools, calling `fenolite_capabilities` and reading `fenolite://guide/start`; with
    `FENOLITE_REQUIRE=mcp-sdk`, `tests/unit/mcp` and `test_mcp_cmd.py` give 52 passed). The job and its check
    (`test_mcp_job`) are in place; the SDK is source S-0827.
  - 2026-10-26: CLOSED. The job `mcp` passed in CI run https://github.com/lgili/Fenolite/actions/runs/40252974405
    at `95eb4ca`; five rows of `docs/mcp.md` are `ORACLE-VERIFIED(mcp-sdk)` (stdio, `server/discover`,
    `initialize`, the tool result, resources). The same run failed `unit` on Windows in `test_page_read`: the
    test ran `fenolite guide --json` without UTF-8 mode and Windows wrote cp1252; the two tests that run the
    command line directly now set `PYTHONUTF8=1`, as the server does for its children.

## 5. Documents and closing

- [x] 5.1 `docs/mcp.md` (how to add the server to a client), `docs/cli-contract.md` ("MCP command"), the agent
  guide's tested line of `mcp` and `tools/gen_agent_guide.py`, `README.md`, `docs/roadmap.md` (v0.5b), `openspec/README.md`.
  Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
  - 2026-10-26: proof passed (with test_agent_skill, test_release_record_v05 and test_adrs: 166 passed; the
    generator's check exits 0). `docs/mcp.md` says how to add the server to a client; the README's loop section
    names it; the roadmap's v0.5b row and Open decisions row 46 record the maintainer's answers; c0195 is in
    `openspec/README.md` (new changes start at c0196). The contract section and the guide's tested lines came
    with task 4.1.
- [x] 5.2 `CHANGELOG.md` under `## [Unreleased]`. Proof: `uv run pytest tests/unit -k changelog -q`.
  - 2026-10-26: proof passed (6 tests). An entry under Added and one under Changed of `[Unreleased]`, after the
    commit that opened `0.6.0.dev0` (the v0.5 guard keeps `[Unreleased]` empty only at `0.5.0`, as `dev` opened
    `0.5.0.dev0` after `0.4.0`).
- [x] 5.3 `make check-fast`. Proof: `make check-fast`.
  - 2026-10-26: exit 0, 14 042 passed, 34 skipped; lint, format, types clean. The first run found an absolute user
    path in the client example of `docs/mcp.md` (residue `abs-user-path`); it is a placeholder `PROJECT` now.
- [ ] 5.4 **Maintainer, optional.** Add `fenolite mcp` to an MCP client of his (Claude Code, an IDE) and run a
  dry run and a confirmed write; record the client, its version and the outcome under this task. Nothing waits
  on it.
