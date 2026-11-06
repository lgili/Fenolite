## 1. Cross-backend sides

- [x] 1.1 `api/_native_rules.augment` computes native contexts only when both sides are KiCad. Proof:
  `uv run pytest tests/unit/api/test_c0421_cross_backend.py -q -k native`.
- [x] 1.2 `api/_cross_backend.py` completes a KiCad side (classes, `.kicad_dru` rules, footprint items) and an
  Altium side (arc-vertex zone outlines, effective zone settings) when the backends differ, and passes the
  keep-out layers. Proof: the same file.

## 2. Level 6

- [x] 2.1 Rules keyed by name, kind and repeat; written-name pairing with its negative case. Proof:
  `uv run pytest tests/unit/checks/equivalence/test_c0421_pairing.py -q -k rule`.
- [x] 2.2 Layer aliases by user name; keep-out layers; the `across` rules of stack-up kinds and name case,
  net classes, unused layers, layer kind and order. Proof: the same file, `-k "stackup or layer or class or keepout_layer"`.

## 3. Level 7

- [x] 3.1 Items of aliased layers compare under one name. Proof: the same file, `-k user_name`.
- [x] 3.2 Keep-out layer drawings against rule areas. Proof: the same file, `-k keepout`.
- [x] 3.3 `Edge.Cuts` rings. Proof: the same file, `-k edge`.
- [x] 3.4 Mounting-hole footprints against board holes. Proof: the same file, `-k hole`.
- [x] 3.5 Field poses: a hidden field on one side only, and a field the other side holds as a component
  parameter, across backends. Proof: the same file, `-k "field or parameter"`.

## 4. Level 5

- [x] 4.1 Strict level 5: an arc whose mid lies within the length tolerance of a track's chord is that track
  (`design.md` D9). Proof: the same file, `-k arc`.
- [x] 4.2 The via counted in another piece and the zero-length stub of the private run: judged a difference
  of the filled copper (one stitching via side `b`'s refill does not reach, D9), so no pairing rule. Proof:
  `design.md` D9.

- [x] 2.3 A rule on one side only that its side marks kept (ext pair `kept_record=1`, as c0424 writes it) is
  excluded under `declared-limit`, not `rule-missing`; a kept rule the other side holds is still compared.
  Proof: the same file, `-k "kept or unmarked"`.

## 5. Evidence and close

- [x] 5.1 Public rows recount (scratch, no corpus data committed) recorded in `design.md`; `docs/equivalence.md`
  section "Pairing across representations". Proof: the recount table in `design.md`.
- [x] 5.2 `CHANGELOG.md`; `gen_schemas --check` and `tools/model_review.py --check` pass. Proof: those commands.
- [x] 5.3 Focused tests of the equivalence, API, CLI, importer, convert and fidelity suites through the heavy
  lock, and `make check-fast`. Proof: those runs.
