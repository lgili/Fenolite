# import_python

Authored for Fenolite: the inputs of the `fenolite import` tests (change c0275).

- `src/two_sheet.py`: the authored design script, with the project tables that name the authored mini
  library of `tests/data/libs`.
- `two_sheet/`: its build for KiCad 10 (`fenolite build two_sheet.py --out ../two_sheet --confirm
  --timestamp 2026-10-30T00:00:00Z` in `src/`), the one committed input; `tests/unit/importer/test_data.py`
  keeps it equal to a fresh build.

The other boards of the tests (no schematic, a `group`, an edited instance, an old format version, no
`fenolite.path`, KiCad sheet names) are made from this board by `tests/_importcode.py` in each test's
temporary folder. No board, value or name here comes from any other project.
