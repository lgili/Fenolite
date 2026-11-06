# Tasks: c0423

## 1. KiCad's pose

- [x] 1.1 Probe and record KiCad's model pose on 9.0.9 and 10.0.6 (`H-K-MODEL-POSE`, S-1820):
  `docs/formats/kicad/libraries.md`, `docs/hypotheses.md`, `docs/evidence/sources.md`. Proof:
  `uv run pytest tests/kicad/convert/test_model_pose.py -q` (and the same file in the pinned 9.0.9 image).

## 2. Models and bodies

- [x] 2.1 `convert.models.placement` solves the pose for any turn on either side (design, Decision 2). Proof:
  `uv run pytest tests/unit/convert/test_model_placement.py -q`.
- [x] 2.2 `backends.step` writes faceted cylinders and spheres; prisms keep their bytes. Proof:
  `uv run pytest tests/unit/backends/test_step.py -q`.
- [x] 2.3 `models3d.body_forms` and the generated body models with their `body` report (Decision 3); the
  kept files include those the board names (Decision 4). Proof:
  `uv run pytest tests/unit/convert/test_body_models.py -q`.

## 3. Import parity

- [x] 3.1 `body` and `model` losses warn; the import of the authored fixture holds the conversion's
  model references and files. Proof: `uv run pytest tests/unit/importer/test_altium_models.py -q`.

## 4. Proof and close

- [x] 4.1 Authored PCB document with every body type and models turned about X, Y and Z on both sides:
  empty `body` and `model` ledger; the KiCad oracle puts every vertex where the source pose puts it
  (`KICAD-VERIFIED`). Proof: `uv run pytest tests/kicad/convert/test_altium_model_pose.py -q`, also in the
  pinned 9.0.9 image.
- [x] 4.2 `docs/conversion.md`, `docs/formats/altium/pcb-bodies.md`, `docs/formats/step/part21.md`,
  `CHANGELOG.md`; `tools/gen_schemas.py --check`, `tools/model_review.py --check`, the generator checks,
  the tests that consume the changed outputs, `make check-fast`, the unit suite on Python 3.11.
  `make check-fast`, the heavy suite and the unit suite on Python 3.11 are the coordinator's combined run
  (lote-24).

## Proof (2026-11-05)

- 1.1: `tests/kicad/convert/test_model_pose.py` 30 passed on the local `kicad-cli` 10.0.6 (macOS) and 30
  passed on 9.0.9 (the pinned image `kicad/kicad:9.0.9@sha256:e638b79b…`, local run); the case turned about
  all three axes rules out the five other orders of the turns on both sides.
- 2.1: `tests/unit/convert/test_model_placement.py` 16 passed (343 turn combinations × 5 angles × 2 sides
  against an independent forward model, within 1 nm).
- 2.2: `tests/unit/backends/test_step.py` 13 passed.
- 2.3: `tests/unit/convert/test_body_models.py` 11 passed.
- 3.1: `tests/unit/importer/test_altium_models.py` 4 passed.
- 4.1: `tests/kicad/convert/test_altium_model_pose.py` 17 passed on 10.0.6 and 17 on 9.0.9.
- 4.2: ruff, ruff format, pyright `src`, `gen_schemas`, `model_review`, `gen_cli_surface`,
  `gen_altium_graduation`, `gen_evidence_matrix` and `gen_agent_guide` `--check` clean. The consumer sweep
  (`tests/unit/convert`, `importer`, `backends`, `lens`, `exports`, `checks`, `agent`, the convert, explain
  and export CLI tests, `test_examples.py` and the Altium corpus tests) gave 11771 passed and 7 failed: the
  pinned `body` and `model` losses of `tests/corpus/test_convert_altium_census.py`, which are now none
  on the eight public documents (`docs/evidence/conversion.md`, "Bodies and models — c0423"). With the
  table updated the census gives 20 passed (2 heavy skips); `FENOLITE_HEAVY=1` measured row `-08` too.
  The register and docs tests pass, except two of `tests/unit/test_altium_verification_docs.py`
  (cp1252 default), which fail on Python 3.13 on the base commit 5ab9d6452 too: `Path.read_text` no longer goes through
  the patched `Path.open`.
