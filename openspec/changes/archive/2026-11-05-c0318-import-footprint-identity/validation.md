# Validation receipt

Base: `96d687d18450f429bcc57b60087f9e6f43dfb707`. Package version remains `0.7.0.dev0`;
model schema version remains `0`. This additive field belongs in the coordinator's actual final
model0 KEEP/freeze inventory, after the pending schematic source packets are united.

The immutable base reproduced both failures with Fenolite-authored fixtures: a real 0.1 mm pad edit
produced a public level-3 footprint-name difference, and the same edit beside one shared physical
sheet failed import with `drawn.repeated-value-differs` wrapped in `import.unequal`.

## Focused proofs

- `pytest tests/unit/importer/test_footprint_identity.py -q`: 14 passed. Targets 9 and 10 preserve
  distinct physical pad geometry, the original actual PCB names and the shared native schematic
  property. Both builds/rebuilds pass public level 5 in the absolute frame with strict copper item
  comparison, no exclusions, no loss flags and no explained differences. Native/value metadata
  mismatches and a same-unit pin electrical-type conflict remain errors; a missing local definition
  cannot fall back to the available native definition. Altium refuses the explicit KiCad selector.
- `pytest tests/unit/lens/test_footprint_identity_bytes.py tests/unit/dsl/test_footprint_identity.py
  tests/unit/catalog/test_device_ports.py -q`: 28 passed. Complete file-map hashes match the immutable
  base for four ordinary KiCad builds, two ordinary Altium builds with the geo extra, and the two
  ordinary imported project/rebuild targets covered by the importer tests. The DSL/canonical and
  device-interface checks cover default omission, keyword-only use, old documents, invalid types,
  explicit native identity and reserved attributes.
- Focused importer, native embedding, model/drawn connectivity, canonical and default pad-map
  dependency checks passed. The two historical edited-variant emission digests were refreshed:
  independent base/current comparison proves only `design.py` changed; every local library file is
  byte-identical. Ordinary emission digests are unchanged. The deterministic import/ruff proof also
  passed with the worktree's ruff on PATH.
- Final focused group covering identity, vendor, self-check, drawn import, deterministic import,
  embedding, DSL, drawn metadata, device ports and complete-file byte guards: 103 passed.
- `pytest tests/unit/agent/test_pages.py -q`: 91 passed. The tested `files` page is 245 lines/11,694
  bytes; the unchanged root guide is 159 lines/11,998 bytes. The generated DSL signature is current.
- `ruff check .`, `ruff format --check .`, `pyright src`, residue scan, schema/guide/evidence-matrix/
  Altium-graduation generator checks and strict OpenSpec validation pass. The two new requirement
  bodies are 367 and 414 characters.

No comparator, drawn guard, source schematic adapter or accepted-loss policy was loosened. The old
variant-name self-check exception was removed. Default Part/build bytes remain unchanged; variant
PCB header bytes now preserve the original identity. Exact footprint nodes stay byte-identical across
rebuilds; this receipt makes no new claim about unrelated board-graphic ordering or backup files.
No new native-format fact, source ID, FEN code, oracle, GUI proof or external corpus fixture is added.

## Still open

Task 3.2 belongs to the coordinator: source-packet integration, actual final model0 KEEP/freeze,
scheduled full gate and exact-head CI. No full suite, push, PR, tag or release was run here.
