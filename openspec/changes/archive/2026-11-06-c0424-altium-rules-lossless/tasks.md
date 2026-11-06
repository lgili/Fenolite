## 1. Evidence

- [x] 1.1 `docs/evidence/sources.md`: S-1830 to S-1837, Altium's rule pages (manufacturing, electrical,
  routing, placement, plane, mask and test point rules; defining and scoping rules), and S-1838, the key
  census of the public rule file and the eight public PCB documents for the kinds of this change.
  `docs/formats/altium/rule-file.md`: the new rows of "Rule kinds that map", the Routing Layers key names,
  "Kept rule records" and "Fates in a conversion".
  Proof: `uv run pytest tests/unit/test_legal_docs.py tests/unit/test_format_facts.py -q`.

## 2. Reader

- [x] 2.1 `read.rules`: rows for Silk To Silk Clearance, Component Clearance, Differential Pairs Routing
  (key patterns, pair selector), Routing Layers (`CopperLayer.altium_id`, one `no_tracks`), and Hole To
  Hole Clearance with either `ALLOWSTACKEDMICROVIAS`. Proof:
  `uv run pytest tests/unit/backends/altium/read/test_rule_kinds_c0424.py tests/unit/backends/altium/read/test_rule_map.py -q`.

## 3. Kept records

- [x] 3.1 `adapter.rules.kept_indexes` and `kept_text` and the `kept_rule` pairs of the board; `kept_record` on rules of a
  kept record; `rulemap.lower` leaves them out. Proof: `uv run pytest tests/unit/backends/altium/test_kept_rules.py -k "not written" -q`.
- [x] 3.2 `PcbDocSpec.kept_rules` and `pcbdoc.rule_records` write-back. Proof:
  `uv run pytest tests/unit/backends/altium/test_kept_rules.py tests/unit/backends/altium/test_pcbdoc.py -q`.

## 4. Conversion

- [x] 4.1 `convert.report`: outcome `kept`, `ReportRow.kept`; `api.schema`; regenerated schemas. Proof:
  `uv run pytest tests/unit/convert/test_report.py -q` and `uv run python tools/gen_schemas.py --check`.
- [x] 4.2 `convert.altium_rules` (`lower_rules`, `record_fates`) and the record fates in `altium_to_kicad` and `to_kicad`; the
  `convert.kept` info. Proof: `uv run pytest tests/unit/convert/test_altium_rule_fates.py -q`.
- [x] 4.3 Limits the KiCad rule cannot take are left out and reported as changed. Proof:
  `uv run pytest tests/unit/convert/test_altium_rule_fates.py -k drill -q`.
- [x] 4.4 Shadowed imported rules keep Altium's order. Proof:
  `uv run pytest tests/unit/convert/test_altium_rule_fates.py -k shadowed -q`.

## 5. Hand-over

- [x] 5.1 CHANGELOG, `docs/altium.md`, the agent guide line for `convert.kept`; `make check-fast`,
  `tools/model_review.py --check`, the tests that consume the report, and the unit suite on Python 3.11,
  through `fenolite-heavy`. Proof: those commands.
  Proof (2026-11-06): lote-28 CI run 42229338778 succeeded on abe1de83f (unit on 3.11 to 3.13 and three OSes, kicad-10 shards 0-3, kicad-9, coverage audit, ci-complete); dev fast-forwarded to it.
