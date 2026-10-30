# import_python

Authored for Fenolite (CC0-1.0). The code that `fenolite import` writes from
`tests/data/import_python/two_sheet`, a board built from the authored script
`tests/data/import_python/src/two_sheet.py` (change c0275; `docs/import.md`):

```sh
fenolite import tests/data/import_python/two_sheet/two_sheet.kicad_pro --to python --out examples/import_python \
    --licence CC0-1.0 --copyright "2026 Fenolite contributors" \
    --source https://github.com/lgili/Fenolite --revision main \
    --timestamp 2026-10-30T00:00:00Z --confirm
fenolite build examples/import_python/design.py --out build/import_python --confirm
```

- `design.py`: the board, the nets, the net class `Power`, five parts in the modules `ch1` and `ch2` with
  their keys (`name="R101"` for the second channel's `R201`), the connections, the placements, a zone, a
  keep-out and two silkscreen drawings.
- `copper.py`: the 40 track segments, 3 arcs and 6 vias as `track_table`, `arc_table` and `via_table` rows
  in nanometres.
- `lib/`: the two footprints brought back from the board and the symbols drawn from their pads, named by
  the project tables `fp-lib-table` and `sym-lib-table`.
- `design.lock` and `PROVENANCE.json`: the refs, and where the code came from.

Each `.py` file carries, after the provenance header, the line `# Authored for Fenolite: …`: the residue
test (`tests/residue/test_converted_code.py`) flags any committed code converted from a board that was not.
`uv run python tests/_importexample.py` writes the folder again; `tests/unit/test_examples.py -k
import_python` keeps it equal to a fresh import.
