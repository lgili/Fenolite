## Context

c0175's design, decision 9 and the list of package 9 under "Later", asked for a gated difference, a
three-way port of a parallel copy, and the resave bytes of Altium documents kept out of the semantic
difference. `fenolite diff` already gives the model difference (`checks.diff`), a tree view of KiCad
files and a records view of Altium files (`roundtrip.diff_records`). The mutation protocol gives plans,
`--confirm`, receipts and "an error finding plans no write".

## Decisions

1. **The gate reads the model view.** A kind is the first segment of a change's path (`/track/3` is a
   `track`), the names `result.summary` already uses; `--allow` takes them comma-separated and refuses an
   unknown one. Each change outside them is one error, so an agent reads every unexpected change in
   `issues` without paging `differences`. An empty `--allow` allows nothing: a gate for "nothing changed".
2. **The merge works on the board's text, not through the model writer.** Writing `THEIRS` back from the
   model would rewrite what Fenolite does not model, and the writer refuses KiCad 8 boards. A merge of
   root items keeps every byte of `THEIRS` that it does not change, and holds no claim about the meaning
   of an item beyond its key.
3. **Root items are keyed by uuid.** Footprints, drawings, tracks, vias, zones and groups carry a `uuid`
   (`tstamp` in old files), which a re-save keeps (`H-K-PCB-UUID`, `H-K-UUID-KEEP-2`). A head without a
   uuid that each board holds at most once (`general`, `setup`, `layers`) is keyed by its head; any other
   child by its compact text, numbered when repeated, so it can only be added or removed.
4. **Three outcomes per item.** For an item that differs between `BASE` and `OURS`: `THEIRS` as in `BASE`
   gives `applied`, `THEIRS` as in `OURS` gives `already`, anything else is `diff.conflict`. A footprint is
   one item; merging inside it would need a key for its pads and drawings and is a non-goal.
5. **Refuse what a key cannot make safe.** Boards of two format versions, and numbered net tables that
   differ, are `diff.unmergeable`: the text of an item from `OURS` would name another net, or use another
   grammar, in `THEIRS`. KiCad 10 boards name their nets, so they need no equal table.
6. **Splice, then prove.** The text of each changed item of `OURS` replaces that of `THEIRS`; an added item
   follows the nearest kept item before it in `OURS`; a removed item takes its own line. Inserted text
   takes the line ends of `THEIRS`. The spliced bytes are parsed again and must give the expected list of
   items, or the merge raises (`FEN-1001`, a bug), never writes.
7. **Resave by decoded value, only in the records view.** Two values of a property record are one value
   when both are mil text of one value in units of 1/10 000 mil (rounded half to even), both are decimal
   numbers of one exact value, or both are booleans of one value. Keys of free text (names, texts,
   designators, ids, paths) are never decoded: `1` and `1.0` are two pad names. `diff_records` keeps its
   behaviour unless a `resave` list is passed; the command passes one and reports `result.resave`, and the
   evidence names `H-A-RD-RESAVE` only when a record was classified. The model view already compares
   decoded values.
8. **`diff` declares that it mutates.** Only `--three-way` plans a write; a plain `diff` exits 0 without a
   confirmation, as `refs` does without `--repoint`. The mutation example merges the example board with
   itself into `merged.kicad_pcb`, so the protocol tests cover the merge.

## Risks / Trade-offs

- A board that KiCad saved with every item re-ordered still merges (keys, not places), but the added items
  follow `OURS`'s order and KiCad sorts them again on its next save.
- The free-text key list is Fenolite's choice; a numeric key outside it that holds free text would be
  decoded. The list is in `docs/formats/altium/pcb-read.md`, "Resave differences".

## Open Questions

None.
