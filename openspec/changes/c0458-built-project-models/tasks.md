# Tasks: c0458

## 1. Spec

- [x] 1.1 Deltas for design-dsl ("Footprints of every row origin are vendored") and design-conversion
  ("Model paths read as KiCad reads them"). Proof: `openspec validate c0458-built-project-models --strict`.

## 2. Build

- [x] 2.1 `lens.build._vendor_models`: copy the `${KIPRJMOD}` models of vendored footprints that the script's
  folder holds. Proof: `uv run pytest tests/unit/convert/test_built_models.py -k "copies or nothing" -q`, and
  `kicad-cli` 10.0.6 STEP export of the built c0423 fixture: 0 of 15 models not found (S-2170).

## 3. Conversion

- [x] 3.1 `convert.models.model_path` follows absolute paths and `..`; `NOT_FOUND`. Proof:
  `uv run pytest tests/unit/convert/test_built_models.py tests/unit/convert/test_embedded_models.py -q`.

## 4. Docs and evidence

- [x] 4.1 `docs/dsl.md`, `docs/conversion.md`, `docs/formats/kicad/libraries.md`, the two ledger rows of
  `docs/evidence/conversion.md` (counted by converting the two boards, not by the census), S-2170, CHANGELOG.
  Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/verify/test_cited_ids.py -q`.
- [ ] 4.2 The maintainer's board: flow A after a rebuild keeps its models (relayed by the coordinating session).
