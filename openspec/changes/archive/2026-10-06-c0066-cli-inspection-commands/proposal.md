## Why

An agent can build, check and export a board through `fenolite`, but it cannot ask the small questions in between: what changed between two files, will this file survive an edit, what does this code mean, how do I undo that write, what is on this net, what is near this part. Today it reads whole boards and whole issue lists, and a DRC report with hundreds of violations fills its context.

Plan D8 gives v0.2a these commands: `diff`, `roundtrip`, `fmt --check`, `explain`, `restore`, pagination (`--limit`, `--cursor`, `--format concise|detailed`) and the compact views `net`, `region`, `neighbors`. Its acceptance: a footprint moved by 1 mm shows as exactly one change in `diff`, and `fmt --check` is idempotent over the whole corpus.

c0044 (v0.3, proposed) already specifies a general `diff` on the model. This change takes that engine with the same names, so the two do not fork.

## What Changes

- **`diff A B`**: the differences of two boards, libraries, schematics or built models (`checks/diff.py`, c0044's API), and a tree view for two KiCad files.
- **`roundtrip PATH`**: RT0 and RT1 of a file, and RT2 through `kicad-cli` on request, with the level reached and the first difference.
- **`fmt PATH [--check]`**: Fenolite's canonical print of a KiCad S-expression file; `--check` reports without writing.
- **`explain CODE`**: what an error code or an issue code means and what to do, from one packaged table that a test keeps complete.
- **`restore RECEIPT`**: puts back the backups of one confirmed write, after checking by hash that nothing changed since. The receipt gains `id` and `undo`. It never deletes a file.
- **Paging and concise output**: `--limit`, `--cursor` and `result.page` for a command's main list or for `issues`; `--format concise` keeps one issue per code with counts. Exit codes come from the full result.
- **`net`, `region`, `neighbors`**: compact read-only views of a board, built on the board frame (c0028).

Size: 13.5 design-days in two independent halves; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `cli-contract`: ADDED "Paged results", "Concise output", "Diff command", "Roundtrip command", "Fmt command", "Explain command", "Receipt identity", "Restore command", "Net command", "Region command", "Neighbors command".
- `verification-loop`: ADDED "Model difference report".
- `kicad-sexpr`: ADDED "Canonical print check".
- `board-frame`: ADDED "Board views".

## Non-goals

- No records view and no Altium input in `diff`: c0044 adds them on this engine.
- No verdict by level between two designs: `equivalent` is c0045.
- No reformatting of `.kicad_pro` or of rules files.
- No journal of receipts on disk and no restore by id alone: the receipt the caller kept is the undo token (design, Decision 8).
- No deletion by `restore`: a file the undone write created stays.
- No connectivity in `net`: missing connections are KiCad's `unconnected_items`.
- No MCP server (v0.5b), no per-command result schemas.

## Evidence level required

- `diff`: no label of its own; the lowest level of its two readings.
- `roundtrip`: the reader's level for RT0 and RT1; `KICAD-VERIFIED` for RT2 where the oracle's reports are stable.
- `fmt`: the printer's idempotence over the corpus (`CORPUS-VERIFIED`, `H-K-FMT-IDEMPOTENT`).
- `explain`, `restore`, paging: mechanical.
- `net`, `region`, `neighbors`: the level of the board read combined with `frame.EVIDENCE`.

## Impact

- New: `checks/diff.py`, `analysis/views.py`, `cli/explain.py` with `cli/data/explain.toml`, and nine `cli/cmd_*.py` modules.
- Changed: `cli/main.py`, `cli/api.py`, `cli/output.py` (receipt fields, paging), `schemas/fenolite.envelope.v0.json`, `backends/kicad/sexpr.py`, `docs/cli-contract.md`.
- Depends on c0060 (schematic inputs) and c0062 (RT2 of schematics); both can be cut. Of c0044 and this change, the second to land re-bases two ADDED requirements on the first.
