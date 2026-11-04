# Compare conversions within the scope each written file can hold

## Why

`verify_conversion` (`api/conversion.py:174`) compares the whole source circuit with the read-back of the
written `.kicad_pcb`. A source component without a footprint (a schematic-only part, a logo symbol
without pins, a part not yet placed) is written to the generated schematic, but cannot be on the board, so
level 1 reports `component-missing` and `convert.unexplained` for it. In the maintainer's 88-case batch
this produced unexplained differences in 21 project contexts. The same comparison reports
`ref-ambiguous` when the source itself repeats a designator (two sheets that use one reference, or one
component linked to two footprints on the PCB), with no source diagnostic that explains it.

## What Changes

- Level 1 of the board comparison leaves out source components that have no footprint in the source
  board; the schematic comparison (`_schematic`) remains the check for them, and a component missing
  from the written schematic is still reported.
- The Altium read reports a repeated designator and a component linked to several footprints as source
  diagnostics (warnings) naming the references; `ref-ambiguous` differences that such a diagnostic
  covers are explained, not unexplained.
- No tolerance or comparison is relaxed for placed components.

## Impact

`api/conversion.py`, `convert/report.py` (Explainer), the Altium adapter diagnostics, docs and tests with
authored inputs only.
