## ADDED Requirements

### Requirement: Altium project sets
`tests/corpus/manifest.toml` SHALL mark the rows of one public Altium project as a set, so that the import of change c0043 can read a project's sheets and its PCB document together. This requirement extends "Second-backend corpus rows" (c0039), whose rules hold for every row of a set.
- A set is the rows that carry the use `altium-set:<nn>`, `<nn>` two digits. A set MUST hold exactly one project file row (`altium-third-party-prjpcb-NN`), exactly one PCB document row, and every schematic sheet that the project file lists. All rows of a set MUST come from one repository at one commit and MUST carry one licence.
- Every row of a set MUST also carry the use `altium-import`. The use `altium-import:known-diff` MAY be added to the project file row of a set whose sheets and PCB document disagree; its `notes` MUST then give the cause by row ids and counts only.
- Change c0043 adds no file of a new kind: it tags rows that c0039 to c0042 list and adds the sheets, project files and PCB documents that those changes do not list for the chosen projects. Each added row follows the id pattern, the pinned commit and the licence rule of c0039, with its source id registered, takes the next free number of its kind, and carries only `altium`, `origin:third-party` and the set uses: it carries none of `cfb`, `altium-sch`, `altium-pcbdoc` and `altium-text`, so the row counts that c0039 to c0042 state still hold.
- The sets MUST come from at least three repositories when they support a `CORPUS-VERIFIED` label; with fewer, the label is not given.
- `tools/corpus_fetch.py --uses altium-import` MUST fetch exactly the rows of the sets.
- `tests/corpus/test_manifest.py` SHALL check, for every `altium-set` use: one project file row and one PCB document row, one repository, one commit and one licence over the set, and `altium-import` on every row.
- Nothing read from a set, and nothing derived from it, is committed.

#### Scenario: Set without a PCB document
- **GIVEN** rows that carry `altium-set:01`, among them a project file and four sheets but no PCB document
- **WHEN** `uv run pytest tests/corpus/test_manifest.py -k altium_set` runs
- **THEN** it fails naming the set and the missing kind

#### Scenario: Set from two commits
- **GIVEN** a set whose sheets are pinned to one commit and whose PCB document to another
- **WHEN** the manifest test runs
- **THEN** it fails naming the set and the two commits

#### Scenario: Fetch of the sets
- **WHEN** `uv run python tools/corpus_fetch.py --uses altium-import` runs
- **THEN** only rows with an `altium-set` use are fetched, and each file's SHA-256 is verified
