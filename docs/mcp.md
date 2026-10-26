# The MCP server

`fenolite mcp` serves Fenolite's commands to any client of the Model Context Protocol (MCP): a chat
application, an IDE assistant or an agent runner starts it as a subprocess and calls the commands as tools
(change c0195). It needs nothing besides Fenolite: the protocol is implemented with the standard library, from
the public specification.

## Using it

Most clients take a command line; `PROJECT` stands for the absolute path of the project's folder:

```json
{
  "mcpServers": {
    "fenolite": {
      "command": "fenolite",
      "args": ["mcp", "--root", "PROJECT"]
    }
  }
}
```

- `--root DIR`: the folder every call runs in, and the only folder a call may write to. Default: the current
  folder.
- `--read-only`: list only the commands that write nothing.
- `--tools NAME,...`: list only these commands (their command names, such as `check,route,fill`).
- `--timeout SECONDS`: stop a call that runs longer (default 600). A stopped call is `FEN-1003`, which can be
  run again.

Each command is a tool `fenolite_<command>` (hyphens as underscores) whose arguments are the command's own,
by the names of `fenolite capabilities --command <name> --json`. A tool's reply is the command's JSON envelope
(`schemas/fenolite.envelope.v0.json`); read the exit code in the reply's `_meta` (`fenolite/exit`) as the agent
guide says. A writing command writes in two calls: the first, without `confirm`, is the dry run and returns
`result.plan` and its `plan_id`; the second passes `confirm: true` and that `plan`.

The pages of the agent guide are resources `fenolite://guide/<topic>`, and the reply of `capabilities` is
`fenolite://capabilities`.

## The protocol facts

The server rests on these facts of the public specification. The label is `INFERRED` until the official SDK's
client confirms the fact against the server in the CI job `mcp` (`ORACLE-VERIFIED(mcp-sdk)`): mcp 2.3.0, in
CI run 40252974405 (2026-10-26), confirmed the rows so labelled; progress, cancellation, batches and the
annotations are not exercised by its test and stay `INFERRED`.

| fact | source | evidence |
|---|---|---|
| A version is a date `YYYY-MM-DD`; the current revision is `2026-07-28` | S-0817 | INFERRED |
| `2026-07-28` has no handshake: each request carries `io.modelcontextprotocol/protocolVersion` and `io.modelcontextprotocol/clientCapabilities` in `params._meta`; a request without them is `-32602` | S-0817, S-0819 | INFERRED |
| A request of a version the server does not serve is error `-32022` with `data.supported` (a list) and `data.requested` | S-0817 | INFERRED |
| `server/discover` is mandatory; its result holds `supportedVersions`, `capabilities`, `_meta.io.modelcontextprotocol/serverInfo` and optional `instructions` | S-0820 | ORACLE-VERIFIED(mcp-sdk) |
| Every result of `2026-07-28` holds `resultType` (`complete` here); the results of `tools/list`, `resources/list` and `resources/read` also hold `ttlMs` (≥ 0) and `cacheScope` (`public` or `private`) | S-0819, S-0825, S-0826 | INFERRED |
| Revisions `2025-11-25` and earlier open with `initialize` (`protocolVersion`, `capabilities`, `clientInfo`), answered with `protocolVersion`, `capabilities`, `serverInfo` and optional `instructions`; the server answers the client's version if it serves it, else its own latest; then `notifications/initialized` | S-0824 | ORACLE-VERIFIED(mcp-sdk) |
| A dual-era server serves a request with modern `_meta` by `2026-07-28`, and after `initialize` serves that stdio process by the negotiated legacy version | S-0817 | INFERRED |
| On stdio: one JSON-RPC message per line, UTF-8, no embedded newline; nothing but protocol messages on stdout; logs on stderr; the server writes no request; it exits when stdin closes | S-0818 | ORACLE-VERIFIED(mcp-sdk) |
| Request ids are strings or integers, never `null`; a notification has no id and gets no response | S-0819 | INFERRED |
| JSON-RPC errors: `-32700` parse, `-32600` invalid request, `-32601` unknown method, `-32602` invalid params, `-32603` internal; `-32020` to `-32099` are the specification's own | S-0819 | INFERRED |
| A tool has `name` (letters, digits, `_`, `-`, `.`; 1 to 128), optional `title` and `description`, `inputSchema` (an object schema, JSON Schema 2020-12 by default) and optional `annotations` | S-0821, S-0826 | INFERRED |
| Tool annotations: `readOnlyHint` (default false), `destructiveHint` (default true), `idempotentHint` (default false), `openWorldHint` (default true); hints only | S-0826 | INFERRED |
| A tool result has `content` (here one text item) and optional `structuredContent` with its JSON repeated as text; `isError: true` reports an execution error the model can act on, and a JSON-RPC error reports an unknown tool or a malformed call | S-0821 | ORACLE-VERIFIED(mcp-sdk) |
| A resource has `uri`, `name`, optional `title`, `description` and `mimeType`; `resources/read` returns `contents` with `uri`, `mimeType` and `text`; an unknown resource is `-32602` in `2026-07-28` and was `-32002` before | S-0822 | ORACLE-VERIFIED(mcp-sdk) |
| Progress: a request opts in with `_meta.progressToken`; `notifications/progress` carries `progressToken`, an increasing `progress`, optional `total` and `message`, and stops when the request completes | S-0823 | INFERRED |
| Cancellation: `notifications/cancelled` with `requestId` and optional `reason`; the server stops the work and sends no response for it, and ignores an unknown or finished id | S-0823 | INFERRED |

## What each version changes for this server

| version | handshake | `ping` | batches | `structuredContent` | `title` of a tool | `resultType`, `ttlMs`, `cacheScope` | resource not found |
|---|---|---|---|---|---|---|---|
| `2026-07-28` | none (`_meta`, `server/discover`) | removed | no | any JSON value | yes | required | `-32602` |
| `2025-11-25` | `initialize` | yes | no | an object | yes | absent | `-32002` |
| `2025-06-18` | `initialize` | yes | no | an object | yes | absent | `-32002` |
| `2025-03-26` | `initialize` | yes | yes (an array of messages) | absent | absent (`annotations.title`) | absent | `-32002` |

Sources: S-0825 and S-0826. The server leaves out a field that the version it serves does not define.

## Fenolite's choices

- **Versions served:** `2026-07-28`, `2025-11-25`, `2025-06-18` and `2025-03-26`. An older `initialize` gets
  `2025-11-25`, the latest legacy version, as the protocol asks. `server/discover` and the `-32022` error name
  `2026-07-28` only: a version in a request's `_meta` means the stateless protocol, and a legacy version is
  reached through `initialize`.
- **One tool per public command**, in name order; `mcp`, `skill` and the hidden commands are not tools, and the
  `view` tool has no `serve`, `port` or `no_browser`.
- **The command line runs each call**, as a child process in `--root`, so a reply is exactly the command
  line's; calls run one at a time.
- **No write without a reviewed plan**, and no write outside `--root`. Reads are not confined: a tool reads
  what the command line can read.
- **No outputSchema**: every structured result is the envelope or the error object, whose schemas are in
  `schemas/`.
- **Not implemented:** HTTP, authorization, prompts, sampling, elicitation, roots, logging, subscriptions, the
  Tasks extension, multi round-trip requests.
