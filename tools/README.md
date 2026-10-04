# tools

Developer scripts (stdlib-only, run as `uv run python tools/<script>.py`). They are not part of the
installed package. Later changes add the schema generator, the residue scan, the corpus fetcher and
the oracle setup scripts here.

| script | what it does |
|---|---|
| `test_outcomes.py` | Compares the JUnit XML files of two pytest runs (`--junitxml`): the totals of each run and every test id whose outcome differs; exit 0 when equal, 1 when not. It proves that a parallel run gives the results of a serial run (`tests/README.md`, "Parallel runs"). |
| `kicad_libs_fetch.py` | Fetches the official KiCad footprint and symbol libraries at the pinned commits of tags 10.0.6 and 9.0.9 into a verified cache outside the repository (`--cache`, else `FENOLITE_LIBS_CACHE`, else `~/.cache/fenolite/libs`); `--verify` re-hashes it. The libraries are CC-BY-SA 4.0 and are never committed (`docs/formats/kicad/libraries.md`, "Library cache"). |
