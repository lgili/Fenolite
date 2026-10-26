## Context

- **Request.** On 2026-10-26 the maintainer chose the MCP server (v0.5b of `docs/roadmap.md`) as the next feature
  after `0.5.0`.
- **What exists** on `main` at `3a0bfb7`:
  - `fenolite.cli.api.discover()` gives 42 `Command`s, each with `name`, `help` (`None` hides it), `mutates`,
    its parser (`register`) and `run`. `fenolite.cli.describe.describe` turns a command's parser into
    `Argument`s (`name`, `flags`, `kind`, `type`, `choices`, `default`, `required`, `repeatable`, `help`).
  - The command line's contract (`docs/cli-contract.md`): JSON envelope on stdout, one error object on stderr,
    exit codes 0 to 7, `--dry-run` then `--confirm --plan <id>` for every write, `--progress` records on
    stderr, `--fields`, `--limit`, `--cursor`, `--seed`, `--timestamp`.
  - The agent guide (`fenolite.agent.guide`): pages with a topic, a title and a summary.
  - `pyproject.toml`: the `mcp` extra (`mcp>=1.0`), imported by nothing.
- **The protocol** (public specification, read on 2026-10-26; each fact goes to `docs/mcp.md` with its source):
  - JSON-RPC 2.0. On stdio, one message per line, UTF-8, no embedded newline; the server writes only protocol
    messages to stdout, and may log to stderr.
  - The current revision is `2026-07-28`. It has no handshake: every request carries
    `io.modelcontextprotocol/protocolVersion` (and the client's identity and capabilities) in `_meta`; the
    server answers a request of a version it does not support with error `-32022`
    (`UnsupportedProtocolVersionError`, `data.supported`, `data.requested`), and MUST implement
    `server/discover` (supported versions, capabilities, identity).
  - Legacy revisions (`2025-11-25` and earlier) open with `initialize` and `notifications/initialized`. A
    dual-era server answers `initialize` with the negotiated legacy version and serves that client by it for the
    life of the stdio process; a request with modern `_meta` is served statelessly by `2026-07-28`.
  - Tools: `tools/list` (paginated, deterministic order recommended) and `tools/call`; a `Tool` has `name`
    (letters, digits, `_`, `-`, `.`, up to 128), `title`, `description`, `inputSchema` (JSON Schema 2020-12 by
    default), optional `outputSchema` and `annotations`; a result has `content`, optional `structuredContent`
    (with its JSON also as text, for older clients) and `isError`. An unknown tool or a malformed call is a
    JSON-RPC error; a failure the model can act on is a result with `isError: true`.
  - In `2026-07-28` a result carries `resultType` (`complete`, or `input_required` for multi round-trip
    requests, which this server does not use).

## Goals / Non-Goals

**Goals**
- Every MCP client, modern or legacy, lists Fenolite's commands as tools and calls them, with no package
  besides Fenolite.
- A tool behaves exactly as its command: same arguments, same envelope, same refusals, same evidence.
- No write without a plan that the client saw.

**Non-Goals**
- HTTP transport, authorization, prompts, sampling, elicitation, Tasks, subscriptions.
- Any change of a command's behaviour.

## Decisions

1. **Standard library, not the SDK.** The subset needed (JSON-RPC over stdio, `server/discover`, `initialize`,
   `ping` for legacy clients, `tools/list`, `tools/call`, `resources/list`, `resources/read`, cancellation and
   progress notifications) is small, and the core takes no runtime dependency (`AGENTS.md`). The SDK becomes the oracle
   of a test instead (decision 9). Alternative: build on the `mcp` extra; rejected because `pip install fenolite`
   would not be enough, and the SDK's support of `2026-07-28` would set the server's pace.
2. **Dual-era.** Supported versions, newest first: `2026-07-28`, `2025-11-25`, `2025-06-18`, `2025-03-26`.
   - A request whose `_meta` names `2026-07-28` is served by it; any other version there gets `-32022` whose
     `supported` is `2026-07-28`, as is `server/discover`'s `supportedVersions`: a version in `_meta` means the
     stateless protocol, and the legacy versions are reached through `initialize` only.
   - `initialize`: the server answers with the client's `protocolVersion` if it supports it, else with
     `2025-11-25`; the process then serves legacy requests by that version. A legacy request before
     `initialize` is an error (`-32600`).
   - The differences between the versions that touch this server's messages are the table of `docs/mcp.md`
     (task 0.1), each row sourced; the server leaves out a field a version does not define:
     `structuredContent` and a tool's `title` before `2025-06-18`; `resultType`, `ttlMs` and `cacheScope` before
     `2026-07-28`. `ping` is answered for a legacy client only (`2026-07-28` removed it); a JSON array of
     messages (a batch) is answered with an array for a `2025-03-26` client only.
   - Resource not found: `-32602` for `2026-07-28`, `-32002` for the legacy versions.
   - The cache fields of `2026-07-28`: `ttlMs` 0 and `cacheScope` `private` for `tools/list`, `resources/list`
     and `resources/read` (the list follows the installed version and `--tools`; a page of the guide may name a
     local path).
3. **Tool names and order.** `fenolite_` plus the command name with `-` as `_`; listed in name order; one page
   (the list is short). `title` is the command name; `description` is its help text and, for a writing
   command, one sentence on the two-step write.
4. **Input schema from `describe()`.** One property per argument, named by `Argument.name`:
   - `string`, `integer`, `number`, `boolean` as JSON types; `choices` as `enum`; `repeatable` as an array;
     `default` copied; `required` from the argument; `additionalProperties: false`.
   - Global options a call may set: `fields` (array of strings), `limit`, `cursor`, `seed`, `timestamp`; and for
     a writing command `confirm` (boolean) and `plan` (string).
   - The server builds the command line from the arguments in the parser's order, and refuses an argument the
     schema does not hold (a tool execution error naming it).
5. **A child process per call.** `sys.executable -m fenolite <command> <arguments> --json` in `--root`, with
   stdin closed; the envelope (stdout) or the error object (stderr) is parsed and returned.
   - Isolation: a command's crash, memory or global state never reaches the server; the reply is byte for byte
     what the command line gives.
   - `--timeout` (default 600 s) and `notifications/cancelled` stop the child (its process group) and give
     `FEN-1003` as a tool error, retryable.
   - When the call carries a `progressToken`, the server adds `--progress` and turns each record into
     `notifications/progress`.
   - Calls run one at a time, in order of arrival, so that two writes never race; `ping` (legacy) and
     cancellation are answered while a call runs.
   - Alternative: run `main()` in the server's process; rejected for the reasons above, at the cost of about
     0.3 s of interpreter start per call.
6. **Writes.** For a command with `mutates`:
   - no `confirm`: the server adds `--dry-run`; the reply holds `result.plan` and `plan_id`;
   - `confirm: true` without `plan`: a tool error (`FEN-2001`, hint: run without `confirm` first);
   - `confirm: true` with `plan`: the server first checks the staged plan's paths: every one must resolve under
     `--root` (else a tool error, `FEN-2001`, naming the path); then it runs `--confirm --plan <id>`.
   - `--read-only` lists no writing tool.
7. **Results.** `structuredContent` is the envelope (exit 0 or 5) or the error object (any other exit), and the
   single text item is its canonical JSON (`fenolite.cli.output.canonical_json`). `isError` is true for an exit
   other than 0 and 5. The exit code is in `_meta` (`fenolite/exit`) so that an agent can follow the guide's
   rules by code. No `outputSchema`: the envelope's schema is `schemas/fenolite.envelope.v0.json`, named in the
   description, and a fixed schema per tool would duplicate it.
8. **Resources.** `fenolite://guide/<topic>` for each page of `guide.pages()` (`text/markdown`) and
   `fenolite://capabilities` (`application/json`, the reply of `capabilities --json --no-tools`). Read from the
   installed package, in the server's process (they write nothing and run no tool).
9. **The SDK as an oracle.** The `mcp` extra is removed (`repo-layout`); the SDK goes into `oracles`, pinned.
   `tests/unit/mcp/test_sdk_oracle.py` starts `fenolite mcp` with the SDK's stdio client, lists the tools and
   calls `fenolite_capabilities` and a dry run of `fenolite_fmt`, once with a legacy version (the SDK's
   default) and once with `2026-07-28` if the pinned SDK speaks it. It is skipped where the SDK is missing and
   runs in the CI job `mcp`.
10. **Exposure.** Every public command except `mcp`, `skill` and `view`'s `--serve`, `--port` and
    `--no-browser` (left out of the `view` tool's schema). `--tools` narrows the list; an unknown name is a usage
    error of `fenolite mcp` (exit 2) before the server starts.
11. **Standard output.** `fenolite mcp` writes protocol messages only on stdout; diagnostics go to stderr as
    lines `fenolite mcp: ...`. A usage error before the server starts is the usual error object and exit code.

## Risks / Trade-offs

- **Many tools in a client's context.** 40 tools of long schemas cost tokens in every request of some clients.
  Mitigation: `--tools` and `--read-only`; descriptions are the command's one-line help; the guide resources
  carry the detail.
- **Protocol churn.** A new revision may change a message. Mitigation: the version table of `docs/mcp.md`, the
  `-32022` answer for an unknown version, and the oracle test that fails when the pinned SDK moves.
- **Start time.** A child per call adds about 0.3 s. Accepted; long commands dominate.
- **Paths.** Reads are not confined: a tool reads what the command line can read, as the agent's shell could.
  Writes are confined to `--root` (decision 6). See open question 3.

## Migration Plan

New command; nothing to migrate. The `mcp` extra had no user: its removal is noted in the changelog.

## Open Questions

Decided by the maintainer on 2026-10-26: every recommended answer below is accepted.

1. **Standard library or the SDK?** Recommended: standard library (decision 1).
2. **One tool per command, or one tool `fenolite` with a `command` argument?** Recommended: one per command
   (typed arguments, per-tool annotations, clearer to a model), with `--tools` to narrow.
3. **Confine reads to `--root` too?** Recommended: no for now; reads follow the command line. Writes are
   confined.
4. **Remove the `mcp` extra?** Recommended: yes, with the SDK in `oracles`.
5. **Legacy versions served.** Recommended: `2025-11-25`, `2025-06-18` and `2025-03-26` (the three revisions
   that clients in use are likely to speak); older ones get the supported list.

## Budget

About 9 design-days: protocol and dual-era 2.5, tools and schemas 2, the child runner with timeout,
cancellation and progress 1.5, writes and confinement 1, resources 0.5, the SDK oracle and the CI job 1,
documents and the guide 0.5.
