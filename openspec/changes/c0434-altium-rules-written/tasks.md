## 1. Rules written

- [x] 1.1 `rulemap`: open limits, the via hole from a hole_size rule, Component Clearance, Silk To Silk
  Clearance and Differential Pairs Routing rows, `Lowered.changed`; `lower.py` counts changed rules.
  Proof: `uv run pytest tests/unit/backends/altium/test_rulemap_c0434.py tests/unit/backends/altium/test_rulemap.py -q`.

## 2. Every loss before consent

- [x] 2.1 `LossyConversionError` and `lower.LossyWriteError` list every loss. Proof:
  `uv run pytest tests/unit/convert/test_c0429_ledger.py tests/unit/backends/altium/test_lower_items.py -q`.

## 3. Public proof

- [x] 3.1 `altium-third-party-pcbdoc-01` converted to KiCad and back writes 8 of 8 rules (3 changed), and
  the refusal lists every lost kind. Proof: `uv run pytest tests/corpus/test_altium_rules_c0434.py -q`.

## 4. Close

- [ ] 4.1 `make check-fast`, the focused suites through the heavy lock, the `gen_*` checks, CHANGELOG.
