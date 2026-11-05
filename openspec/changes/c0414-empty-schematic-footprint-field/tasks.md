## 1. Model and file

- [x] 1.1 Add `DrawnSymbol.empty_footprint`, its `schematic.toml` key in the reader, the canonical writer,
  the schema and `docs/drawn-schematic.md`. Proof:
  `uv run pytest tests/unit/importer/test_empty_footprint_field.py -q`. Done 2026-11-05: 6 passed.

## 2. Import and build

- [x] 2.1 `drawn.extract(..., footprints=...)` flags an empty source Footprint field of a part with a
  footprint; the import passes the footprints it writes. Proof: the same file. Done 2026-11-05.
- [x] 2.2 The KiCad drawn writer writes an empty Footprint field for a flagged unit, keeping the part's
  footprint. Proof: the same file. Done 2026-11-05.
- [x] 2.3 The strict round trip of `kicad-demo-9-0-9-1-pcb-01` is equal at every level with KiCad 10.0.6, and
  the row becomes a measured `[[row]]` of `tests/kicad/fidelity/accepted.toml`. Proof:
  `uv run pytest tests/kicad/fidelity -rA -k "9-0-9-1-pcb-01"` with the corpus, and the kicad-10 CI job.
  Done 2026-11-05 locally (KiCad 10.0.6): all nine levels equal, counts none, 5.003 s; the kicad-10 CI
  job runs with the coordinator's batch.

## 3. Evidence and validation

- [x] 3.1 `CHANGELOG.md` line and a dated note in `docs/evidence/fidelity.md`. Proof:
  `uv run pytest tests/unit/test_fidelity_docs.py -q`. Done 2026-11-05: 3 passed.
- [ ] 3.2 The coordinator's batch `make check-fast` and the required CI jobs pass on the exact commit.
