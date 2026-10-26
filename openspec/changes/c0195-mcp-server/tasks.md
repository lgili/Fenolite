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

- [ ] 1.1 `fenolite.mcp.protocol`: the stdio loop (lines in, lines out), JSON-RPC parse and errors (`-32700`,
  `-32600`, `-32601`, `-32602`), the modern path (`_meta` version, `-32022`, `server/discover`) and the legacy
  path (`initialize`, `notifications/initialized`, `ping`), `notifications/cancelled` (scenarios "Modern
  discovery", "Legacy handshake", "Unknown version"). Proof: `uv run pytest tests/unit/mcp/test_protocol.py -q`.

## 2. Tools

- [ ] 2.1 `fenolite.mcp.tools`: the tool list from `discover()` and `describe()`, the input schemas, the
  annotations, the exclusions, the command line built from the arguments, the refusal of an unknown argument
  (scenario "Tools follow the commands"). Proof: `uv run pytest tests/unit/mcp/test_tools.py -k "listed or schema or
  unknown" -q`.
- [ ] 2.2 The child runner: `python -m fenolite ... --json` in the root, the envelope or the error object, the
  exit code in `_meta`, the timeout, the cancellation, the progress notifications (scenarios "Same reply as the
  command line" and "Error object"). Proof: `uv run pytest tests/unit/mcp/test_tools.py -q`.
- [ ] 2.3 Writes: `--dry-run` without `confirm`, `confirm` without `plan` refused, the staged plan's paths under
  the root, `--read-only` (scenarios "Dry run, then confirm" and "A write outside the root"). Proof:
  `uv run pytest tests/unit/mcp/test_writes.py -q`.

## 3. Resources

- [ ] 3.1 `fenolite.mcp.resources`: the guide pages and `capabilities` (scenario "A page read"). Proof:
  `uv run pytest tests/unit/mcp/test_resources.py -q`.

## 4. Command, extras and CI

- [ ] 4.1 `cmd_mcp.py` (`--root`, `--read-only`, `--tools`, `--timeout`; scenario "Unknown tool name");
  `capabilities` lists the versions; `tests/unit/test_import_graph.py` and the layering table admit `mcp`.
  Proof: `uv run pytest tests/unit/cli/test_mcp_cmd.py tests/unit/cli/test_capabilities.py tests/unit/test_import_graph.py tests/consistency -q`.
- [ ] 4.2 Remove the `mcp` extra, add the pinned SDK to `oracles`, update `uv.lock` and the invariants test
  (the MODIFIED "Zero runtime dependencies in the core"). Proof: `uv run pytest tests/unit/test_pyproject_invariants.py -q`.
- [ ] 4.3 `test_sdk_oracle.py` and the CI job `mcp` (scenario "The official client agrees"), with its check in
  `tests/unit/test_ci_workflow.py`. Proof: `uv run --extra dev --extra oracles pytest tests/unit/mcp/test_sdk_oracle.py -q`
  passes locally, and the job `mcp` passes in CI.

## 5. Documents and closing

- [ ] 5.1 `docs/mcp.md` (how to add the server to a client), `docs/cli-contract.md` ("MCP command"), the agent
  guide's tested line of `mcp` and `tools/gen_agent_guide.py`, `README.md`, `docs/roadmap.md` (v0.5b), `openspec/README.md`.
  Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
- [ ] 5.2 `CHANGELOG.md` under `## [Unreleased]`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 5.3 `make check-fast`. Proof: `make check-fast`.
- [ ] 5.4 **Maintainer, optional.** Add `fenolite mcp` to an MCP client of his (Claude Code, an IDE) and run a
  dry run and a confirmed write; record the client, its version and the outcome under this task. Nothing waits
  on it.
