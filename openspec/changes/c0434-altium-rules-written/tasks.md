## 1. Rules of a model write

- [x] 1.1 `PcbDocSpec.class_kinds`; `lower.from_design` keeps every kind for a build, Clearance alone (none
  under a clearance rule on every object) for a write of a model, and counts each net class with a value
  left out `changed` under `netclass`. Proof:
  `uv run pytest tests/unit/backends/altium/test_lower_items.py -q -n 0`.

## 2. Every loss before consent

- [x] 2.1 `LossyConversionError` and `lower.LossyWriteError` list every loss. Proof:
  `uv run pytest tests/unit/convert/test_c0429_ledger.py -q -n 0` and
  `uv run pytest tests/unit/backends/altium/test_lower_items.py -q -n 0`.

## 3. Public proof

- [x] 3.1 `altium-third-party-pcbdoc-08` converted to KiCad and back writes no net class rule, 4 Clearance
  and 1 Width record as the source, the Width limits equal. Proof:
  `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_rules_c0434.py -q -n 0`.

## 4. Close

- [x] 4.0 The v0.3 acceptance project keeps a rule of every exact kind: its Altium model states its own
  preferred via hole (0.3 mm), which a KiCad `via_drill` rule cannot hold and which a net-class default
  stood in for before. Proof: `uv run pytest tests/unit/test_acceptance_v03.py -q -n 0`.

- [x] 4.1 Light checks (ruff, ruff format, pyright, `gen_*` checks), the touched test files alone with
  `-n 0`, CHANGELOG.
