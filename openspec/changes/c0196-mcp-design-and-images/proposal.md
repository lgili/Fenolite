## Why

The maintainer asked on 2026-10-26 how much the MCP server of c0195 helps an agent make boards. Measured
against the loop of the agent guide, an agent that has only the server's tools still cannot design a board,
and it cannot see one:

- **No tool writes the design.** A board is a Python script (`design.py`, with `placements.toml` and the
  library tables beside it). `init` writes a starter and `sync --to-source` writes placements back, but no
  command writes or edits the script. An agent with a shell edits it with its own tools; a client without one
  (a chat application, an IDE assistant with no file access) can check, route, fill and export a board, but
  not add a part or a net.
- **Every reply is text.** `render` makes the PNG views of a board (`pcb render` of `kicad-cli`), and the dry
  run already holds their bytes in the staged plan, but the tool's reply is the envelope only. An agent that
  reads images cannot look at its placement, its silkscreen or its copper.

The maintainer asked for both on 2026-10-26.

## What Changes

- **`fenolite edit PATH (--content-file FILE | --edits-file FILE) [--dry-run | --confirm --plan ID]`**, a new
  writing command for the text files a design is written in: a design script (`.py`), a TOML file
  (`placements.toml`, a drawing or panel specification) and the library tables (`fp-lib-table`,
  `sym-lib-table`).
  - `--content-file` gives the whole new text (a new file is created); `--edits-file` gives a JSON list of
    `{"old": ..., "new": ...}`, applied in order, each `old` found exactly once in the text as it stands.
  - The plan carries a unified diff (`result.diff`, cut at a limit, with the counts of lines added and
    removed) and the usual write protocol; nothing is written without `--confirm --plan`.
  - A design script must parse (`ast.parse`, never run): a syntax error refuses the edit (`FEN-3004`, with the
    line). A TOML file must parse with `tomllib`. A file must be UTF-8, at most 1 MB.
- **`fenolite_edit` in the MCP server, only with `fenolite mcp --allow-edit`.** It takes `path` and either
  `content` (text) or `edits` (a list of `old`/`new`); the server writes them to a file in its own state
  folder and runs `fenolite edit` with `--content-file` or `--edits-file`, so the edit is the command line like
  every other tool, with no limit of the command line's length. It writes only under `--root`, through a
  reviewed plan, as every writing tool does.
  - Off by default because `build` runs a design script as the user's own code, without a sandbox: a client
    that may edit the script and build it may run any Python in the user's account. `--allow-edit` says so in
    its help and in `docs/mcp.md`; `--read-only` never lists the tool.
- **Images in replies.** When a tool's reply plans or writes PNG files (`render --png`; any command whose plan
  or receipt holds `.png` rows), the result also holds each image as MCP image content (`image/png`, base64),
  taken from the staged plan of a dry run or from the written file of a confirmed run. An agent sees the views
  before anything is written.
  - At most 4 images and 6 MB of image bytes per reply, in the plan's order; what is left out is named in a
    text item. The size of a render is the agent's choice (`width`, `height`; an agent may ask for 800 by 600).
  - SVG views are not sent as images (model inputs take raster images); their paths stay in the envelope.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `cli-contract`: ADDED "Edit command"; ADDED "MCP edit option".
- `mcp-server` (open change c0195): ADDED "Script editing tool" and "Images in replies"; MODIFIED
  "Commands not exposed" (`fenolite_edit` without `--allow-edit`).

## Non-goals

- Running a design script to check an edit: the edit parses the script and never runs it; `build --dry-run` is
  the check that runs it.
- Editing KiCad or Altium files: those are written by the commands that own them (`build`, `place`,
  `route`, `fill`, `fmt`).
- Raster images made by Fenolite itself (from the viewer's scene): only `kicad-cli`'s renders are sent.
- A sandbox for design scripts.

## Evidence level required

- `fenolite edit`: tested on authored files (`INFERRED` for Fenolite's own behaviour; no format fact is new).
- Image content: from the public specification (S-0821 and S-0826: `ImageContent` with `data` and
  `mimeType`, in every served version); `ORACLE-VERIFIED(mcp-sdk)` when the official client of c0195's
  oracle test reads the image of a render.

## Impact

- New: `src/fenolite/cli/cmd_edit.py`, `tests/unit/cli/test_edit_cmd.py`, `tests/unit/mcp/test_images.py`.
- Changed: `fenolite.mcp.tools` (the `edit` mapping), `fenolite.mcp.backend` (the input files, the images),
  `cmd_mcp.py` (`--allow-edit`), `docs/cli-contract.md`, `docs/mcp.md`, the guide page `design-script`
  (the tested line of `edit`) and `recovery`, `CHANGELOG.md`.
- Depends on c0195 (archived first).
- Size: about 6 design-days.
