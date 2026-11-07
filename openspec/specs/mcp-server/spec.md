# mcp-server Specification

## Purpose
TBD - created by archiving change c0195-mcp-server. Update Purpose after archive.
## Requirements
### Requirement: MCP server on standard input and output
`fenolite mcp` SHALL serve the Model Context Protocol over standard input and output, one JSON-RPC 2.0 message per line, with the standard library only (change c0195).
- It MUST serve the revision `2026-07-28` (`server/discover`, the version in each request's `_meta`) and the `initialize` handshake of `2025-11-25`, `2025-06-18` and `2025-03-26`.
- A request whose `_meta` names another version MUST get error `-32022` ("Version refused").
- Standard output MUST carry protocol messages only.

#### Scenario: Modern discovery
- **WHEN** `uv run pytest tests/unit/mcp/test_protocol.py -k discover` sends `server/discover` with `2026-07-28` in `_meta`
- **THEN** the reply's `supportedVersions` is `2026-07-28`, with the `tools` and `resources` capabilities and the server's name and version

#### Scenario: Legacy handshake
- **WHEN** the test sends `initialize` with `protocolVersion` `2025-06-18`, then `notifications/initialized` and `tools/list`
- **THEN** the server answers `2025-06-18` and lists the tools

#### Scenario: Unknown version
- **WHEN** the test sends `tools/list` with `1900-01-01` in `_meta`
- **THEN** the reply is error `-32022` naming `1900-01-01` and `2026-07-28`

### Requirement: Version refused
A request whose `_meta` names a version other than `2026-07-28` SHALL get error `-32022` with `data.requested` and `data.supported` = `["2026-07-28"]`; `server/discover` SHALL name the same list. The legacy versions are reached through `initialize` only.

#### Scenario: Discover names the modern version
- **WHEN** `uv run pytest tests/unit/mcp/test_protocol.py -k discover` sends `server/discover`
- **THEN** `supportedVersions` is `["2026-07-28"]`

### Requirement: One tool per public command
The server SHALL list one tool per public command, named `fenolite_<command>` with hyphens as underscores, in name order, with an input schema generated from the command's parser (`fenolite.cli.describe`).
- `readOnlyHint` MUST be true for a command that writes nothing and `destructiveHint` true for one that writes.
- An argument outside the schema MUST be refused as a tool execution error naming it.

#### Scenario: Tools follow the commands
- **WHEN** `uv run pytest tests/unit/mcp/test_tools.py -k listed` lists the tools
- **THEN** their names are the public commands but `mcp` and `skill`, and each schema's properties are the command's arguments with the global options

### Requirement: Commands not exposed
The server SHALL NOT list `mcp`, `skill` or a hidden command as a tool, SHALL NOT list `fenolite_edit` unless it was started with `--allow-edit` and without `--read-only`, and the schema of `fenolite_view` SHALL NOT hold `serve`, `port` or `no_browser`.

#### Scenario: Excluded commands
- **WHEN** `uv run pytest tests/unit/mcp/test_tools.py -k excluded` lists the tools
- **THEN** no tool is named `fenolite_mcp`, `fenolite_skill` or `fenolite__echo`, and `fenolite_view` has no property `serve`

#### Scenario: Edit not listed by default
- **WHEN** the test lists the tools of a catalog made without `allow_edit`
- **THEN** no tool is named `fenolite_edit`

### Requirement: Calls run the command line
A tool call SHALL run `python -m fenolite <command> ... --json` as a child process in the server's root, and return its envelope as `structuredContent` with its canonical JSON as text; `isError` SHALL be true when the exit code is neither 0 nor 5, and then the result is the error object.
- A call that passes the timeout, or that the client cancels, MUST stop the child and give `FEN-1003`.
- With a `progressToken`, each `--progress` record MUST become a progress notification.

#### Scenario: Same reply as the command line
- **WHEN** `uv run pytest tests/unit/mcp/test_tools.py -k same_reply` calls `fenolite_inspect` (argument `file`) on a committed board
- **THEN** `structuredContent` equals the envelope that `fenolite inspect --json` prints for it

#### Scenario: Error object
- **WHEN** the test calls `fenolite_inspect` on a file that does not exist
- **THEN** `isError` is true and the result's `code` is `FEN-3001`

### Requirement: Writes through a reviewed plan
A tool of a writing command SHALL write only through a plan that a call without `confirm` returned.
- Without `confirm` the call MUST run `--dry-run`.
- `confirm` without `plan` MUST be a tool error `FEN-2001`.
- Before `--confirm --plan`, every path of the staged plan MUST lie under the root, else a tool error `FEN-2001` names it.
- `--read-only` MUST list no writing tool.

#### Scenario: Dry run, then confirm
- **WHEN** `uv run pytest tests/unit/mcp/test_writes.py -k reviewed` calls `fenolite_init` for a new folder, then again with `confirm` and the returned `plan_id`
- **THEN** the first call writes nothing and returns a plan, and the second writes the planned bytes with a receipt

#### Scenario: A write outside the root
- **GIVEN** a plan whose output lies outside the root
- **WHEN** the test confirms it
- **THEN** the call is a tool error `FEN-2001` naming the path, and nothing is written

### Requirement: Guide resources
The server SHALL list each page of the agent guide as the resource `fenolite://guide/<topic>` (`text/markdown`) and the reply of `capabilities` as `fenolite://capabilities` (`application/json`).

#### Scenario: A page read
- **WHEN** `uv run pytest tests/unit/mcp/test_resources.py` reads `fenolite://guide/start`
- **THEN** the text is the page's `text` that `fenolite guide start --json` returns

### Requirement: Official client as oracle
`tests/unit/mcp/test_sdk_oracle.py` SHALL run the official SDK's stdio client against `fenolite mcp`, list the tools and call `fenolite_capabilities`; it is skipped where the SDK is not installed and runs in the CI job `mcp`.

#### Scenario: The official client agrees
- **WHEN** the job `mcp` runs `uv run pytest tests/unit/mcp/test_sdk_oracle.py`
- **THEN** the client lists `fenolite_check` and the call of `fenolite_capabilities` returns an envelope whose `command` is `capabilities`

### Requirement: Script editing tool
The tool `fenolite_edit` SHALL take `path` and exactly one of `content` (a string) and `edits` (a list of `{old, new}` strings), write the value to a file in the server's state folder, and run `fenolite edit` with `--content-file` or `--edits-file`; the input file SHALL be removed when the call ends.
- The tool MUST follow "Writes through a reviewed plan".
- A confirmation with a content different from its dry run's MUST be refused by the command line (`FEN-4002`).

#### Scenario: Edit through the server
- **WHEN** `uv run pytest tests/unit/mcp/test_writes.py -k edit` calls `fenolite_edit` with one pair on a starter script, then confirms the returned plan
- **THEN** the dry run returns the diff and writes nothing, the confirmation writes the script, and no input file is left in the state folder

### Requirement: Images in replies
When a tool's reply plans or writes PNG files, the result SHALL hold each one as an image content item (`image/png`, base64) after the envelope's text, from the staged plan of a dry run or from the written file of a confirmed run, at most 4 images and 6 MB of image bytes, with a text item naming what was left out.

#### Scenario: A dry run of a render is seen
- **GIVEN** `kicad-cli` and a committed board
- **WHEN** `uv run pytest tests/kicad/mcp/test_render_images.py` calls `fenolite_render` with `png`, `width` 400 and `height` 300 and no `confirm`
- **THEN** the content holds the envelope's text and two PNG images whose bytes have the sha256 of the plan's rows, and nothing is written
