## Context

- **Request.** On 2026-10-26, after c0195, the maintainer asked how much the MCP server helps an agent make
  boards; the answer named two gaps (no tool writes the design; replies are text only), and he asked for both.
- **What exists** on `c0195-mcp-server` at `95eb4ca`:
  - `fenolite mcp` lists one tool per public command and runs each call as the command line in `--root`;
    writes go through `--dry-run` and `--confirm --plan`, and a confirmed plan must write under the root.
  - A staged plan holds the bytes of every planned write (`fenolite.cli.plans`, `StagedPlan.data`), so a dry
    run of `render --png` already holds `top.png` and `bottom.png`.
  - `fenolite.cli._script` runs a design script with `runpy`, "as the user's own code: there is no sandbox".
  - No command writes a design script, a `placements.toml` or a library table from given text.
- **The protocol** (S-0821, S-0826): a tool result's `content` may hold `{"type": "image", "data": <base64>,
  "mimeType": "image/png"}` in every served version.

## Goals / Non-Goals

**Goals**
- An agent with only the server's tools writes and changes a design, through a reviewed plan.
- An agent that reads images sees the views of a board, before they are written.

**Non-Goals**
- Running a script to check an edit; a sandbox; editing tool-owned files; images made by Fenolite itself.

## Decisions

1. **A command, not a server-only tool.** `fenolite edit` keeps c0195's rule that every tool is the command
   line: the same plan, receipt, backups and refusals in a shell and through the server, and one place to test.
2. **Two forms of an edit.** `--content-file` (the whole text: a new file, or a rewrite) and `--edits-file` (a
   JSON list of `old`/`new` pairs, applied in order to the text as it stands, each `old` found exactly once:
   else `FEN-3004` naming the pair and the count). Exact text, not line numbers, so that an edit made from an
   older read fails instead of landing in the wrong place.
3. **The files it edits.** By name: `*.py`, `*.toml`, `fp-lib-table`, `sym-lib-table`; UTF-8 text of at most
   1 MB, line ends kept as the file has them (a new file gets `\n`). Any other path is `FEN-2001`. KiCad and
   Altium documents are written by the commands that own them.
4. **Checks without running.** A `.py` result must parse with `ast.parse`; a `.toml` result with `tomllib`. A
   failure is `FEN-3004` with the line, and nothing is planned. The script is never imported or run.
5. **The plan shows the change.** `result` holds `path`, `created`, `lines_added`, `lines_removed` and `diff`
   (a unified diff with three lines of context, cut at 400 lines with a note); the write is the new text.
6. **The server's input files.** `fenolite_edit` takes `path` and exactly one of `content` (string) and `edits`
   (array of `{old, new}` strings). The server writes the value to `<state>/mcp-inputs/<uuid>.txt` or `.json`,
   passes `--content-file` or `--edits-file`, and removes the file when the call ends. The confirmation call
   passes the same arguments again: the plan id binds the input file's digest, as for any input (`depends`),
   so a different content refuses the confirmation (`FEN-4002`).
7. **Opt-in.** `fenolite mcp --allow-edit` lists `fenolite_edit`; without it the tool is absent and a call is
   an unknown tool. The reason is in the option's help and in `docs/mcp.md`: editing the script and building it
   runs that code as the user. `--read-only` wins over `--allow-edit`.
8. **Images.** After any tool call, the server collects the `.png` rows of the reply: the plan's rows of a dry
   run (their bytes from the staged plan, `StagedPlan.data`, which checks their digest) or the receipt's
   written files of a confirmed run (read under the root). Up to 4 images and 6 MB of image bytes, in the
   rows' order; one text item names what was left out. The envelope stays the first content item and
   `structuredContent` is unchanged. Nothing is resized: the agent sets `width` and `height` of `render`.

## Risks / Trade-offs

- **Code execution.** With `--allow-edit` a client can run any Python through `build`. Mitigation: opt-in,
  stated plainly; the plan shows every edit before it is written, and a client shows tool calls to the person.
- **Context weight of images.** A 1600 by 1200 PNG is about 1 MB of base64. Mitigation: the caps, and the
  guide teaches rendering at 800 by 600 for a look.
- **Stale reads.** An agent may edit from an old read. Mitigation: exact `old` text found once, and the plan's
  digest binding.

## Open Questions

Decided by the maintainer on 2026-10-26: every recommended answer below is accepted.

1. **Command line command or server-only tool for the edit?** Recommended: the command (decision 1).
2. **Edit off by default in the server?** Recommended: yes, `--allow-edit` (decision 7).
3. **Which files may `edit` write?** Recommended: `*.py`, `*.toml` and the two library tables (decision 3).
4. **Image caps?** Recommended: 4 images and 6 MB per reply, no resizing (decision 8).

## Budget

About 6 design-days: `fenolite edit` with its checks and diff 2.5, the server's input files and opt-in 1,
images 1.5, tests, guide and documents 1.
