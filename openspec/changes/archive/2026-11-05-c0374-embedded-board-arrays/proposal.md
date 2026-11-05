# Refuse, then resolve, Altium embedded board arrays

## Why

A PCB document that places other PCB documents (an Embedded Board Array: a panel or a motherboard of
modules) is read without its embedded boards: the reader lists `EmbeddedBoards6` as unmapped
(`altium.import.unmapped`) and the conversion proceeds as if the board were complete, reporting hundreds
of components as missing. No public source describes the records (`backends/altium/PROVENANCE.md`,
c0173); `pcbdoc.EMBEDDED_ARRAYS` stays false until the kit cases Q7 to Q9 pass.

## What Changes

- Now: a source board whose `EmbeddedBoards6` storage holds records (`backends/altium/read/cfb.py:
  holds_embedded_boards`, from the storage header and data length only) is the report kind
  `embedded-board`, lost with a reason that `REFUSE_REASONS` makes refused: `convert` and the Altium
  `import` exit 7 without `--allow-lossy`, so no such board is called converted.
- Later, after c0173's kit cases measure the records on maintainer-saved documents: resolve each
  instance (document, position, rotation, mirror, array steps) and read the embedded boards.

## Impact

Altium PCB reader, conversion report kinds, docs/formats with evidence labels; kit cases in c0173.
