# Tasks: c0457

## 1. Carried rules matched by content

- [x] 1.1 `rulecarrier.rule_keys`, `dru_rules` and `match`; version 1 of the property with content and shape
  keys, version 0 still read. Proof: `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -q -n 0`.
- [x] 1.2 A copy of a kept record's rule is taken, not lowered. Proof: the same file, flow A case.

## 2. Edited source rules

- [x] 2.1 `rulemap.edited_fields`; a record with edited limits keeps its name, priority, scopes and enabled
  state, `changed` under `rule`. Proof: the same file and
  `uv run pytest tests/unit/convert/test_rule_carrier_c0434.py -q -n 0`.
- [x] 2.2 Any other edit is lowered as a rule of its kind and counts `changed`; `SOURCE_RULE_LOST` only for
  an edit no record holds. Proof: the same files.

## 3. The pour of the way back

- [x] 3.1 Public row -04 refuses on the way back what the pour of its source refuses (9 of 9), and writes
  the polygons. Proof: `uv run pytest tests/corpus/test_altium_pour_c0457.py -q -n 0`.

## 4. Close

- [x] 4.1 Docs, S-2160 and S-2161, CHANGELOG; light checks; the touched and consuming test files alone with
  `-n 0`.
