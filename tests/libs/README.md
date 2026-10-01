# tests/libs: official KiCad library census

These tests read every footprint and symbol of the official KiCad libraries and resolve the reference
items through the library tables. They are marked `needs_libs` and `slow`. The libraries are
CC-BY-SA 4.0 as a collection, so they are read from a local install or from folders named by
variables, and never committed.

## Sources

Each available source is tested on its own:

- `env`: folders named by `KICAD10_FOOTPRINT_DIR` / `KICAD10_SYMBOL_DIR` (or the `KICAD9_*` pair)
- `install`: the local KiCad install, or the share folder named by `FENOLITE_KICAD_INSTALL_DIR`

Without any source the tests skip; with `FENOLITE_REQUIRE=libs` they fail instead.

## Running the census

```bash
FENOLITE_CENSUS_OUT="$(mktemp -d)/census.json" uv run pytest -m needs_libs tests/libs -q
```

The counts, the time taken and the source of each run go to the JSON file named by
`FENOLITE_CENSUS_OUT`, and only there. A closing task copies the public numbers into
`docs/evidence/kicad-libs.md`. Never point `FENOLITE_CENSUS_OUT` at a tracked file.
