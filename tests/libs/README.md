# tests/libs: official KiCad library census

These tests read every footprint and symbol of the official KiCad libraries and resolve the reference
items through the library tables. They are marked `needs_libs` and `slow`. The libraries are
CC-BY-SA 4.0 as a collection, so they are read from a local install or from folders named by
variables, and never committed.

## Sources

Each available source is tested on its own:

- `env`: folders named by `KICAD10_FOOTPRINT_DIR` / `KICAD10_SYMBOL_DIR` (or the `KICAD9_*` pair)
- `install`: the local KiCad install, or the share folder named by `FENOLITE_KICAD_INSTALL_DIR`
- `cache`: the verified cache made by `uv run python tools/kicad_libs_fetch.py`, at
  `FENOLITE_LIBS_CACHE` or `~/.cache/fenolite/libs`; one source per fetched tag (`cache-10`, `cache-9`)

## Fetching the cache

```bash
uv run python tools/kicad_libs_fetch.py
```

It downloads the official footprint and symbol libraries at the pinned commits of tags 10.0.6 and 9.0.9,
checks each tree against its pin and writes a stamp. Run one fetch at a time: there is no lock.
`--verify` re-hashes the cache.

Disk needs, measured on 2026-10-03: four archives of 11 to 12 MB each (47 MB downloaded in all), and
765 MB of extracted files (about 840 MB on disk): 149 MB and 222 MB for the 10.0.6 footprints and symbols,
146 MB and 212 MB for 9.0.9.

Without any source the tests skip; with `FENOLITE_REQUIRE=libs` they fail instead.

## Running the census

```bash
FENOLITE_CENSUS_OUT="$(mktemp -d)/census.json" uv run pytest -m needs_libs tests/libs -q
```

The counts, the time taken and the source of each run go to the JSON file named by
`FENOLITE_CENSUS_OUT`, and only there. A closing task copies the public numbers into
`docs/evidence/kicad-libs.md`. Never point `FENOLITE_CENSUS_OUT` at a tracked file.
