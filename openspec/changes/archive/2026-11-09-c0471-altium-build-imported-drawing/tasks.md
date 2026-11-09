# Tasks: c0471

- [x] 1.1 Allow multi-line opaque subtrees (`OWNERINDEX=@<line>`), harness opaque records, and `Note` (`209`) /
  `CompileMask` (`225`) records in `backends/altium/drawn.py` when `build --target altium` lowers a drawing,
  and add a unit test in `tests/unit/backends/altium/test_drawn_altium.py`. Proof:
  `uv run pytest tests/unit/backends/altium/test_drawn_altium.py -q`.
- [x] 1.2 Update `docs/drawn-schematic.md` and `CHANGELOG.md` under `## [Unreleased]`, and validate the spec.
  Proof: `openspec validate c0471-altium-build-imported-drawing --strict`.
