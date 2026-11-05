# Express more board copper in the Python import

## Why

`import --to python` declares as unexpressed copper the DSL cannot hold: tracks and arcs without a net
(`importer/tables.py:227`, `:238`), arcs that become collinear after nanometre rounding
(`tables.py:242`), Altium zone outlines with arcs that have no native KiCad slots
(`importer/emit/design.py:734`), and zone names that repeat or carry surrounding spaces
(`emit/design.py:749`). These losses are declared, but they stop a faithful rebuild of real boards.

## What Changes

- Copper tables accept net-less tracks and arcs.
- A degenerate arc is written as the straight track it is, with the change reported.
- Zone outlines with arcs from an Altium source are written with `arc_to`.
- Repeated or padded zone names keep their exact text through an explicit name argument.

## Impact

`importer/tables.py`, `importer/emit/design.py`, the copper DSL, docs, authored tests.
