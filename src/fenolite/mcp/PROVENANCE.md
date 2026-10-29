# Provenance of `fenolite.mcp`

The protocol constants and message shapes of the MCP server (change c0195). Every fact is in `docs/mcp.md`
with its evidence label; the server is written from those rows, and no code of any SDK was read or copied.

| fact-or-area | public source | licence of source | date | how used |
|---|---|---|---|---|
| the served versions `2026-07-28`, `2025-11-25`, `2025-06-18`, `2025-03-26`; a request's version in `_meta`; error `-32022` with `supported` and `requested`; the dual-era rule | S-0817 | Apache-2.0 (specification) | 2026-10-26 | facts only |
| one message per line on stdio, nothing else on stdout, exit at the end of stdin | S-0818 | Apache-2.0 (specification) | 2026-10-26 | facts only |
| JSON-RPC ids, notifications, the error codes `-32700`, `-32600`, `-32601`, `-32602`, `-32603`; `resultType`; the `_meta` keys | S-0819 | Apache-2.0 (specification) | 2026-10-26 | facts only |
| `server/discover` and its result | S-0820 | Apache-2.0 (specification) | 2026-10-26 | facts only |
| tool names, `inputSchema`, `structuredContent` with its text, `isError` | S-0821 | Apache-2.0 (specification) | 2026-10-26 | facts only |
| resources, and resource not found `-32602` (`-32002` before `2026-07-28`) | S-0822 | Apache-2.0 (specification) | 2026-10-26 | facts only |
| progress and cancellation notifications | S-0823 | Apache-2.0 (specification) | 2026-10-26 | facts only |
| `initialize`, `notifications/initialized`, `ping` of the handshake revisions | S-0824 | Apache-2.0 (specification) | 2026-10-26 | facts only |
| what each revision changed (batches in `2025-03-26` only; `structuredContent` and `title` from `2025-06-18`; `ttlMs` and `cacheScope` from `2026-07-28`) | S-0825, S-0826 | Apache-2.0 (specification) | 2026-10-26 | facts only |
| the annotation hints and their defaults | S-0826 | Apache-2.0 (specification) | 2026-10-26 | facts only |
