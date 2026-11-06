# Tasks: c0433

## 1. Writers

- [x] 1.1 `pcblib.check_footprint` keeps a pad without a number; `lower.from_design` writes it in its
  component, its net by pad id; `FREE_PAD_REASON` goes;
  `uv run pytest tests/unit/backends/altium/test_pcblib_stacks.py tests/unit/backends/altium/test_derived_library.py -k "unnamed or unnumbered"`.
- [x] 1.2 Two pads without a number in one footprint convert to Altium and read back in their footprint,
  in the PcbLib, with no `pad-missing` and no `ref-ambiguous`;
  `uv run pytest tests/unit/convert/test_unnumbered_pads.py`.

## 2. RT-A3

- [x] 2.1 `rta3` drops the view of detached pads; unnumbered round and slotted hole pads stay in their
  component and a moved one is a difference;
  `uv run pytest tests/unit/backends/altium/test_derived_library.py -k unnumbered_hole`.

## 3. Evidence and docs

- [x] 3.1 `pcb-records.md` records the census of component pads without a name (S-0172, S-0200, S-0601);
  `pcb-library.md` states the new rule; `uv run pytest tests/unit/test_format_facts.py tests/unit/test_docs_altium_read.py`.
- [x] 3.2 `docs/evidence/conversion.md`, `docs/evidence/conversion-comparison-c0319.json`,
  `tests/corpus/test_convert_census.py` and `FREE_PAD_COUNTS` of `tests/kicad/convert/test_triangle.py`
  follow the demo boards whose pads are no longer detached; pinned by the coordinator from CI
  (`uv run pytest tests/corpus/test_convert_census.py tests/kicad/convert/test_triangle.py -k demo`).
  Proof (2026-11-06): lote-28 CI run 42229338778 succeeded on abe1de83f (unit on 3.11 to 3.13 and three OSes, kicad-10 shards 0-3, kicad-9, coverage audit, ci-complete); dev fast-forwarded to it.
- [x] 3.3 The scenario "Reasons are counted apart" counts two connector pads as its `changed` reason, since
  pads without a number are no longer changed; `uv run pytest tests/unit/convert/test_report.py -k counted_apart`.
