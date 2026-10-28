## ADDED Requirements

### Requirement: MCP command
`fenolite mcp [--root DIR] [--read-only] [--tools NAME,...] [--timeout SECONDS]` SHALL serve the MCP server of capability `mcp-server` until its input ends; while it serves, standard output belongs to the protocol and no envelope is written.
- A usage error before the server starts (an unknown tool name, a root that is not a folder) MUST be the usual error object with exit 2.
- `fenolite capabilities` MUST list the command with the protocol versions it serves.

#### Scenario: Unknown tool name
- **WHEN** `uv run fenolite mcp --tools nope` runs
- **THEN** the exit code is 2 and the error object names `nope`
