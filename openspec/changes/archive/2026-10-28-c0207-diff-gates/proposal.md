## Why

Task 4.6 of change c0175 (package 9, "File safety"), the part that c0201 left there. An agent that was
asked only to route must be able to prove that nothing else moved; a parallel copy of a board, edited
while the owner kept working, must go back without losing either side's work; and an Altium document saved
again without an edit must not look edited. Today `fenolite diff` lists the differences and nothing more.

## What Changes

- `fenolite diff A B --allow KINDS`: each change of the model view whose kind is not listed is a
  `diff.not-allowed` error naming its path (exit 5).
- `fenolite diff BASE OURS --three-way THEIRS --out FILE`: plans `THEIRS` with the root items that changed
  from `BASE` to `OURS` applied, for KiCad boards, under the mutation protocol. An item that `THEIRS` changed
  too is `diff.conflict` (exit 5, nothing written); boards of two versions or with differing numbered net
  tables are `diff.unmergeable`.
- The records view of two Altium files classifies a changed record whose differing values decode to one
  value (`10mil` and `10.0mil`, `T` and `TRUE`) as `resave`: counted in `result.resave`, left out of
  `differences`.
- `diff` becomes a mutating command (`mutates=True`); without `--three-way` it plans no write and asks no
  confirmation, as `refs` without `--repoint`.
- Modules `fenolite.checks.diffgate`, `fenolite.backends.kicad.merge`, `fenolite.backends.altium.resave`;
  three issue codes; two hypotheses (`H-K-MERGE-ITEMS`, `H-A-RD-RESAVE`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `file-safety`: ADDED "Gated differences", "Three-way difference of KiCad boards", "Three-way conflicts"
  and "Resave differences of Altium documents". They replace c0175's "Gated and three-way differences",
  split so each requirement's text stays under 500 characters; c0175's delta no longer holds it.
- `cli-contract`: MODIFIED "Diff command" (`mutates=True`, the options, the exit code with findings, the
  mutation example).

## Non-goals

- `--three-way` for Altium documents, schematics, libraries and built models: Fenolite writes no merged
  Altium document, and a schematic or a library has no item key proved for a merge yet. They are usage
  errors (`FEN-2001`) whose hint names the KiCad boards.
- A merge inside an item: a footprint, a zone or a group is one item, so changes to two of its parts on
  the two sides are a conflict.
- Renumbering a numbered net table (KiCad 9 and older): such boards merge only when their tables are equal.
- The KiCad load of a merged board (`H-K-MERGE-ITEMS`) and a real Altium resave pair (`H-A-RD-RESAVE`):
  both rows stay `INFERRED` until a `kicad-cli` job and an acceptance-kit save settle them.

## Evidence level required

`INFERRED`: the merge is proved on authored boards (its model difference from `THEIRS` is the one from
`BASE` to `OURS`) and the resave rule on authored records; the gate has no format claim.

## Impact

- `src/fenolite/cli/cmd_diff.py`, `src/fenolite/checks/diffgate.py`, `src/fenolite/backends/kicad/merge.py`,
  `src/fenolite/backends/altium/resave.py`, `src/fenolite/backends/altium/roundtrip.py` (`diff_records(...,
  resave=)`), `src/fenolite/cli/explain.py`, `explain.toml`.
- `docs/cli-contract.md` ("diff"), `docs/formats/kicad/board.md`, `docs/formats/altium/pcb-read.md`,
  `docs/hypotheses.md`, the two `PROVENANCE.md`, the guide's `files` page, `CHANGELOG.md`.
- Tests: `tests/_merge_boards.py`, `tests/unit/checks/test_diff_gate.py`, `tests/unit/cli/test_diff_gates.py`,
  `tests/unit/backends/kicad/test_merge.py`, `tests/unit/backends/altium/test_resave.py`.
