## ADDED Requirements

### Requirement: Edit of an Altium PCB document
`fenolite edit PATH.PcbDoc --ops-file FILE [--gate NAME]...` SHALL run the operations of a JSON list on an Altium edit
session (`backends.altium.edit`) under the write protocol. Each entry names a `Session` method in `op`, its item in
`item` as a tagged object, and its other arguments; lengths are integer nm or text with a unit. An unknown op, item
kind or argument MUST exit 2 with `FEN-2001` naming the entry's index. The plan's `result` MUST hold the operation
labels and the records removed and added per storage. The session's issues MUST keep their codes, and an error among
them MUST plan no write (exit 5). `--gate NAME` MUST open that gate for the run alone and give
`altium.edit.gate-opened` (warning) with evidence `UNVERIFIED`. `--ops-file` on a file that is not a `.PcbDoc`,
and `--content-file` or `--edits-file` on a `.PcbDoc`, MUST be usage errors (change c0497).

#### Scenario: A via mask planned and written
- **WHEN** `uv run pytest tests/unit/cli/test_edit_pcbdoc_c0497.py -k plan` runs `fenolite edit vias.PcbDoc
  --ops-file ops.json --gate tenting --dry-run --json` with one `set_via_mask` entry, then `--confirm --plan ID`
- **THEN** the dry run writes nothing and lists the operation and the changed records of `Vias6`, the
  confirmation writes the reviewed bytes, and both runs hold `altium.edit.gate-opened`

#### Scenario: A closed gate
- **WHEN** the same run is made without `--gate`
- **THEN** the exit code is 5, the issues hold `altium.edit.gate` naming `tenting`, and no plan is staged
