# Tasks: c0449

## 1. Spec

- [x] 1.1 Deltas for altium-pcb-writer ("Embedded model bodies", "Component bodies are reported") and
  design-conversion ("Models of a KiCad board in an Altium target"). Proof:
  `openspec validate c0449-altium-embedded-models --strict`.

## 2. Readers

- [x] 2.1 `backends/stepbox.py`: `model_box(data)`; the transformation convention chosen on the corpus.
  Proof: `tests/unit/backends/test_stepbox.py`, and the corpus box run (S-2081).
- [x] 2.2 `kicad.pcb.read_model_ref(node)`, the inverse of `model_ref_node`. Proof:
  `tests/unit/convert/test_embedded_models.py -k placement`.

## 3. Writer and conversion

- [x] 3.1 `pcbrecords.model_id`, `model_record`, `model_body_record`; `pcbdoc` writes `Models` and the
  model bodies. Proof: `tests/unit/backends/altium/test_model_bodies.py`.
- [x] 3.2 `convert.models.altium_pose` (inverse of `placement`) and the outline and heights of the placed
  box. Proof: `test_embedded_models.py -k pose`.
- [x] 3.3 `to_altium` finds the files and `lower` accounts the kind `model`. Proof:
  `test_embedded_models.py -k "roundtrip or losses"`.
- [x] 3.4 Pins: the consuming test files alone (list in the commit message); `gen_altium_graduation --check`;
  the `model` rows of the demo census ledger (`docs/evidence/conversion.md`), counted from the boards with
  `footprint_models` (the census itself runs in CI).

## 4. Records and proof

- [x] 4.1 The round trip of the eight public rows (S-2081): models, poses, boxes.
- [x] 4.2 `pcb-bodies.md` ("Written form of a model body", the box rows), `docs/conversion.md`,
  `docs/formats/step/part21.md` ("Box of a model"), `sources.md` (S-2080 to S-2082), `H-G-STEP-BOX`,
  CHANGELOG.
- [ ] 4.3 Altium opens a round trip with its models (altium-rounds-2).
