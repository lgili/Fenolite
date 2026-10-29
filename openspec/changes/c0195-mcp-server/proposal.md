## Why

v0.5b of the roadmap is the MCP server, kept for 1.0 as "small, and central for agents" (Open decisions,
row 3), and the maintainer chose it as the next feature on 2026-10-26. Today an agent drives Fenolite only
through a shell: it must be allowed to run commands, it parses the JSON envelope from stdout, and a client
without a shell (a chat application, an IDE assistant) cannot use Fenolite at all. The Model Context
Protocol (MCP) is the public protocol through which such clients call tools; a server lets every MCP client
see Fenolite's commands, with their arguments, as typed tools.

Measured before proposing (2026-10-26, `main` at `3a0bfb7`):
- `fenolite.cli.api.discover()` registers 42 commands (41 public and the hidden `_echo`); each declares
  `mutates`, and `fenolite.cli.describe.describe` reads its arguments from its own parser. A tool list can be
  generated without declaring anything twice.
- The `mcp` extra is reserved in `pyproject.toml` (`mcp>=1.0`, the official Python SDK) and imported by no
  module.
- The MCP specification changed on 2026-07-28: the current revision has no `initialize` handshake (each
  request carries its protocol version in `_meta`, and `server/discover` is mandatory), while clients that
  speak `2025-11-25` and earlier still open with `initialize`. A server that wants both kinds of client must be
  "dual-era" (the specification's word).

## What Changes

- **`fenolite mcp`**: an MCP server on standard input and output, for the client to start as a subprocess.
  Options: `--root DIR` (the working folder of every call; default the current folder), `--read-only`
  (only the commands that write nothing), `--tools NAME,...` (a subset), `--timeout SECONDS` (per call).
- **Dual-era, standard library only**: it answers modern requests (`2026-07-28`, `server/discover`,
  `UnsupportedProtocolVersionError`) and the `initialize` handshake of `2025-11-25`, `2025-06-18` and
  `2025-03-26`. JSON-RPC 2.0 over newline-delimited UTF-8. No third-party import.
- **One tool per public command**, named `fenolite_<command>` (hyphens to underscores), in name order:
  - `inputSchema` generated from `describe()` (types, choices, defaults, required, repeatable), plus the
    global options that make sense for a call (`fields`, `limit`, `cursor`, `seed`, `timestamp`);
  - `annotations` from the command: `readOnlyHint` for a command that writes nothing, `destructiveHint` for
    one that does, `openWorldHint` for `fetch` (network);
  - the result is the command's own envelope as `structuredContent`, with its canonical JSON as text;
    `isError` is true when the exit code is neither 0 nor 5 (5 is findings, read from `issues`), and then the
    error object (`code`, `message`, `hint`, `retryable`) is the result.
- **The two-step write is kept**: a tool of a writing command takes `confirm` and `plan`. Without `confirm`
  the call runs `--dry-run` and returns the plan and its `plan_id`; with `confirm` it needs `plan` and runs
  `--confirm --plan <id>`, which writes the reviewed bytes or refuses a stale plan (`FEN-4002`). There is no way
  to write without a plan that a dry run returned. Every planned write must lie under `--root`; a plan that
  writes elsewhere is refused before the confirmation.
- **Each call runs `python -m fenolite <command> ... --json` as a child process** in `--root`: the envelope is
  exactly the command line's, a crash or a hang cannot take the server down, a timeout or a cancellation
  stops the child, and `--progress` records become progress notifications when the client asked for them.
- **Resources**: the pages of the agent guide (`fenolite://guide/<topic>`) and the reply of `capabilities`,
  so that a client can show the agent how to work before its first call.
- Not exposed as tools: `mcp` itself, `skill` (it installs files into an agent's own folders), `view --serve`
  (a server that does not return; `view` without it is a tool), and the hidden `_echo`.
- **The `mcp` extra is removed** and the official SDK moves to `oracles`, used only by a test that runs the
  SDK's own client against `fenolite mcp` (`ORACLE-VERIFIED(mcp-sdk)`). `pip install fenolite` is enough to
  serve.
- `fenolite capabilities` names the server and its protocol versions; the agent guide teaches `mcp` with a
  tested line; `docs/mcp.md` describes the server, with each protocol fact sourced.

## Capabilities

### New Capabilities

- `mcp-server`: the server, its tools, its resources, the write protocol, the protocol versions.

### Modified Capabilities

- `cli-contract`: ADDED "MCP command" (`fenolite mcp` owns standard output for the protocol; no envelope).
- `repo-layout`: MODIFIED "Zero runtime dependencies in the core" (the extras are `geo`, `kicad-ipc`, `dev` and
  `oracles`).

## Non-goals

- The Streamable HTTP transport, authorization and a hosted server: a local subprocess only.
- Prompts, sampling, elicitation, the Tasks extension and `subscriptions/listen`: the tool list is fixed for
  the life of the process.
- New behaviour of any command: every tool is the command line, unchanged.
- Importing the official SDK at run time, or copying code from any SDK: the protocol is implemented from the
  public specification.

## Evidence level required

- Protocol behaviour: `INFERRED` from the public specification pages, each a registered source.
- Interoperability: `ORACLE-VERIFIED(mcp-sdk)` when the official SDK's client (pinned in `oracles`) lists and
  calls the tools of `fenolite mcp` in CI, for one modern and one legacy version.
- A run with a real MCP client (Claude Code or another) on the maintainer's machine is recorded when he makes
  it; nothing waits on it.

## Impact

- New: `src/fenolite/mcp/` (protocol, tools, resources, child runner), `src/fenolite/cli/cmd_mcp.py`,
  `docs/mcp.md`, `tests/unit/mcp/` (with `test_sdk_oracle.py`, skipped where the SDK is not installed).
- Changed: `pyproject.toml` (extras), `tests/unit/test_pyproject_invariants.py`, `cmd_capabilities.py`,
  `docs/cli-contract.md`, `docs/evidence/sources.md`, the agent guide, `README.md`, `CHANGELOG.md`,
  `docs/roadmap.md`, `.github/workflows/ci.yml` (a job `mcp` on `ubuntu-latest` that installs `dev` and `oracles` and runs
  `tests/unit/mcp`).
- Size: about 9 design-days.
