# Read Altium copper fills and regions as copper with a net

## Why

Fills and regions on copper layers are imported as graphics with their net kept in the extension bag
(`backends/altium/adapter/copper.py:973`, `altium.import.copper-shape`): the model has no copper shape
with a net. `check` therefore does not judge that copper (shorts, clearance), and conversions carry it as
drawing. 52 of the maintainer's cases hold such shapes.

## What Changes

- A model entity (or an extension of an existing one) for a filled copper shape with a net and layer.
- The Altium reader maps fills and copper regions to it; the copper check, the KiCad writer and the
  Python import handle it.

## Impact

Model (schema v1), Altium reader, copper check, KiCad writer, importer; docs/design-model.md.
