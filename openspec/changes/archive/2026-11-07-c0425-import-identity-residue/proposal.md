# c0425: Import identity residue (L1 ref-ambiguous, L2 net, unknown pin)

## Why

A private sweep of reference boards (rerun on 5ab9d645) left identity findings that
came from Fenolite, not from the boards. The board data stays private: each pattern below is reproduced
by a fixture authored for Fenolite, and only codes and counts were read from the sweep.

- `convert.unexplained` at level 2 `net`: a footprint with two pads of one number,
  one on a net and one on no net, was reported although both sides agree. The comparator flagged every
  element with two labels, and printed the empty part of a label as nothing.
- `import.unequal` at level 2 `net`: the same pads in the source, and the emitted
  code puts both on the net, because the DSL joins a pin to every pad of its number. A genuine change that
  the import did not declare: the `pad-net-conflict` ledger skipped a pad on no net.
- `convert.unexplained` at level 1 `ref-ambiguous`: a designator held twice by
  the source circuit (a component linked to several footprints, a designator used twice, designators of a
  lost embedded board array). In every case the schematic is lost for the duplicate designators, but that
  row explained only `component-missing`.
- `build.unknown-pin`: the self-check build failed because the vendored symbol library held two
  symbols of one name. A footprint variant was named `<name>_2` while the board had its own footprint of
  that name, so the two footprints and their symbols collided.

## What

- **Level 2 comparator.** An element with several labels on a side is compared through the other
  elements: each label maps to the other side's label that holds most of its block (`NO_NET` to `NO_NET`),
  and the element differs only when the mapped labels differ. `net_text` prints an empty part as `no net`.
- **Import.** A pad on no net beside a pad of its number on a net is counted as `pad-net-conflict`, which
  explains the self-check's level 2 difference (needs `--allow-lossy`, reported per kind).
- **Conversion report.** A lost `schematic` row also explains `ref-ambiguous` at each designator the
  source circuit holds more than once.
- **Library derive.** A variant takes the next suffix that no footprint of the board and no earlier
  variant holds; this fixes `fenolite library` and the import's vendored library alike.

## Not in this change

- `model.duplicate-ref` stays: it reports the source's own duplicate designators, which are real.
- `ref-ambiguous` at an empty reference (holes): the sweep on 5ab9d645 shows none (the conversion ignores
  the empty reference), and c0421's pairing is in lote-24; the next combined sweep confirms it.
- Level 3 `pad-position` differences of the same cases, and the refusals that are incomplete inputs
  (`FEN-3001`, `FEN-3004`).
- The source identifiers S-1840 to S-1849 are unused: every fact here is Fenolite's own behaviour.

## Impact

- Code: `checks/assignment_compare.py`, `importer/emit/design.py`, `convert/report.py`,
  `library/derive.py`.
- Docs: `docs/equivalence.md`, `docs/import.md`, `docs/conversion.md`, `docs/cli-contract.md`.
- Specs: verification-loop (MODIFIED "Assignment compare stage"), design-conversion (MODIFIED "Library
  made from a board", ADDED "Designators used twice explained by a lost schematic"), board-to-code (ADDED
  "A pad on no net beside a pad of its number on a net").
