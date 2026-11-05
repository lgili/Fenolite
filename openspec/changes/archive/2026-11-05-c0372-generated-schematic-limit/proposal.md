# Do not let the generated schematic's page limit block a conversion

## Why

An Altium to KiCad conversion regenerates the schematic from the circuit. When the generator cannot fit
one sheet on A0 (`backends/kicad/schlayout.py:799`, `build.schematic-too-large`), `schematic_files`
(`convert/altium_to_kicad.py:641`) declares the schematic lost but still returns the generator's error,
so the whole conversion plans no write, even for a PcbDoc given alone, whose schematic exists only
because Fenolite generates one. Six of the maintainer's cases were blocked this way.

## What Changes

- With `--allow-lossy`, a refused generated schematic is a declared `schematic` loss and the board and
  libraries are still written; without it, the refusal stays a lossy-conversion refusal (exit 7), not a
  finding that blocks every plan.
- The generator places the parts of an Altium sheet on a KiCad sheet of its own when the source has
  sheets, and spreads a flat circuit over several pages instead of refusing it.

## Impact

`convert/altium_to_kicad.py`, `backends/kicad/schgen.py`, `schlayout.py`; docs; authored tests.
