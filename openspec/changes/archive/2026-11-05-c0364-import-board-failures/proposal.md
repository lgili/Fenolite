# Fix the import failures found on the maintainer's own boards

## Why

The maintainer ran `import`, `convert`, `check` and `parity` on one board in progress and on 88 of
their own older boards (31 project contexts, 57 distinct PCB documents). The boards stay private and
outside the repository; only the failures are reported here. Four of the failures are plain defects with
one cause each:

1. `fenolite check` fails with `FEN-1001` (`ValueError: a copper entry of one point needs a width above
   0`) on every board with a non-plated hole whose pad has no copper: 38 of the 88 cases.
   `checks/padpath.py:model_pads` builds a one-point `PadCopper` of width 0 for it. Both backends
   already give an `np_thru_hole` pad no copper entries and drop an entry the record refuses.
2. `fenolite convert --to kicad` fails with `FEN-1001` (`AssertionError` in
   `convert/altium_to_kicad.py:zone_outlines`) when the Altium project declares PCB documents that are
   not in the snapshot (3 cases). The read already reports `altium.project.document-missing`.
3. `fenolite parity` on an Altium project whose PCB lives in a subfolder (`PCB/Board.PcbDoc`) runs the
   comparison and then fails with `FEN-1001` (`FileNotFoundError`). `cli/_documents.py:given_document`
   keeps only `path.name`, so `input_ref` hashes `<root>/Board.PcbDoc`.
4. `fenolite import --to python` changes an empty source value. The emitter leaves `value=` out of a
   `Part` whose value is empty, and `lens/build.py:_resolve` then gives the part the Value of its symbol
   (for a vendored symbol, its own name). The self-check reports `import.unequal`.

The other reported items (components missing after conversion, the A0 limit of the intermediate
schematic, ambiguous references, embedded panel boards, multiple pin-net assignments, zone outlines,
unmapped rules and the edge-ring difference) need triage and get their own changes.

## What Changes

- `model_pads` gives an `np_thru_hole` pad no copper and leaves out a copper entry that no copper
  record can hold, as the backends do. The pad stays in the result with its hole.
- `convert` refuses a source without a PCB design with exit 3 (`FEN-3001`), naming the declared PCB
  documents the project lacks, instead of failing on an assertion.
- `given_document` names a file by its path relative to the set's root, so `parity` (and every
  document command) reports and hashes `PCB/Board.PcbDoc`.
- A `Part` given `value=""` keeps the empty value in a KiCad build: `Part.value_empty`, listed by
  `fenolite.dsl.convert.empty_value_ids` and passed as `build_design(empty_values=...)`; the import emits
  `value=""` for a source component whose value is empty. `value=None` (the default) still takes the
  symbol's Value. The Altium build keeps writing the symbol's name as the comment. The model does not
  change (its 1.0 shapes are frozen by the approval recorded in c0218).

## Impact

- Code: `checks/padpath.py`, `convert/__init__.py`, `cli/_documents.py`, `dsl/part.py`, `dsl/convert.py`,
  `lens/build.py`, `cli/cmd_build.py`, `catalog/devices.py` (reserved part attribute), `importer/emit/design.py`.
- Schema and model: unchanged. `docs/cli-surface.json` lists `Part.value_empty`.
- Docs: `docs/dsl.md`, `CHANGELOG.md`.
- Tests: synthetic, authored regressions only; no private board, name or value enters the repository.
