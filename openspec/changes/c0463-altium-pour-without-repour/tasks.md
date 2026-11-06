# Tasks: c0463

Rules for every task:

- Public sources only. Each fact goes in `docs/formats/altium/pcb-pour.md` with an S- id from S-2220..2229
  and an evidence label.
- The maintainer's board is private: codes and counts only. It is never in tests, fixtures, commits or
  messages.
- Run each touched test file alone with `-n 0`. Heavy runs go through `fenolite-heavy` with `-n 2`.
- Kit runs go on the shared Altium VM: record a foreign restart, close only your own documents.
- This change starts after c0462 tasks 1 to 4.

## 1. Outline arcs

- [ ] 1.1 Record S-2221: how the polygon record stores an arc vertex, and how the saved regions
  approximate it. Proof: `uv run pytest tests/unit/docs -q -n 0`.
- [ ] 1.2 Chord the arcs by `ARCRESOLUTION` and pour. The written polygon keeps its arcs. Proof:
  `uv run pytest tests/unit/backends/altium/test_pour_outline_c0463.py -k arc -q -n 0`.

## 2. Outlines

- [ ] 2.1 Inspect the corpus's two `outline` refusals and record S-2222. Proof: the record in
  `pcb-pour.md`.
- [ ] 2.2 Repeated vertices kept once; self-touching rings split where S-2222 shows Altium's fill.
  Proof: the same file, `-k "touch or repeat"`.

## 3. Hatch and the remaining reasons

- [ ] 3.1 Kit sample `pour-hatched` authored and run (S-2223). Proof: the kit record, declared in
  `tests/data/MANIFEST.toml`, and `uv run pytest tests/corpus/test_manifest.py -q -n 0`.
- [ ] 3.2 Hatched pour. Proof: `uv run pytest tests/corpus/test_altium_pour_hatched_c0463.py -q -n 0`.
- [ ] 3.3 `unshaped-copper` and `unshaped-pad` shaped through the writer's text and pad geometry (c0460).
  `threshold` and `pour-over` read every documented value. Proof:
  `uv run pytest tests/unit/backends/altium/test_pour_inputs.py tests/unit/backends/altium/test_pour_refusal.py -q -n 0`.
- [ ] 3.4 `shelved` and `plane-layer` counted as `exact`. Proof: the same files.

## 4. The Repour oracle

- [ ] 4.1 The kit step `repour` (S-2224), and its records for the 8 rows. Proof:
  `uv run pytest tests/unit/cli/test_kit.py -q -n 0`, and the records declared in the manifest.
- [ ] 4.2 `tests/corpus/test_altium_pour_repour_c0463.py`, with stale saved pours named. Proof:
  `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_pour_repour_c0463.py -q -n 0`.
- [ ] 4.3 Repin the census to no refusals. Proof:
  `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_pour_census.py -q -n 2`.

## 5. Graduation

- [ ] 5.1 K6 round of `pour`, `pour4` and `pour-hatched` on Altium Designer 26. Proof: the kit report,
  recorded as S-2225.
- [ ] 5.2 The maintainer's board, flow B: 28 of 28 polygons poured, and Altium DRC with no Repour equal
  per rule to the DRC after Repour. The coordinator records the counts as S-2226. Proof: that record.
- [ ] 5.3 Evidence `ALTIUM-VERIFIED(kit)`, the new message texts, CHANGELOG, `gen_evidence_matrix` and
  `gen_altium_graduation` checks, and `openspec validate --all --strict`. Proof:
  `uv run pytest tests/unit/backends/altium/test_pour_modes.py -q -n 0`, then each `--check`.
