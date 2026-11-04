# Six ordinary role views: direct inspection

The delegated agent looked at all six original browser screenshots on 2026-11-03
(America/Sao_Paulo; capture timestamps are UTC on 2026-11-04). These are Fenolite-authored
`good.py`/`bad.py` variants of `buck_shunt`, `half_bridge` and `bms`, built to KiCad by
the real capabilities → dry-run → reviewed-plan → confirm flow. They were then opened
through the real `fenolite view --roles run --serve --no-browser --no-run` product,
with actions disabled. Browser DOM controls only were used; no native input was sent.

[receipt.json](receipt.json) binds each observation to its original JPEG, board and
retained DOM hashes. [retained-artifacts.json](retained-artifacts.json) records all
46 external evidence files (1,522,995 bytes) with relative names, sizes and SHA-256.
All 46 retained files, including the six authored JPEG originals, remain in the external
packet named by the manifest. No binary payload is committed here. The originals were
not converted, edited or used to update visual-test references. The hashes bind the
original external bytes rather than rewritten local-path records.

All 57 viewer/roles product modules match both tested source
`985f59a1d01a612b2eac0219243199896c24075a` and served source
`723183a11ebffe4bcdf5d6d0795420db57e2847e`. The complete `tests/visual`, `viewer/src`
and built viewer-static git trees are also identical between those snapshots.
The retained source985 viewer job 126171394431 passed its fresh-bundle step and
`FENOLITE_REQUIRE=browser uv run pytest tests/visual -q` with 104 passed. That
individual job is valid scoped evidence; the overall source985 run failed, and its
later removal is not evidence of a green run. No new tests were run for this receipt.

For current source723 run 41744987316, exact API metadata records viewer job
126295612259 as completed/success. The overall run was still in progress and
the job log was not yet available, so this receipt claims no new test count
and does not close task 6.2 or claim the overall run passed.

| Variant | Role rows | Groups | Findings | Zones without saved fill |
|---|---:|---:|---:|---:|
| buck_shunt good | 12 | 4 | 10 | 6 |
| buck_shunt bad | 12 | 4 | 13 | 6 |
| half_bridge good | 11 | 4 | 9 | 5 |
| half_bridge bad | 11 | 4 | 11 | 6 |
| bms good | 13 | 3 | 6 | 6 |
| bms bad | 11 | 3 | 8 | 7 |

## What was seen

- Buck good: the full board, orange hot-loop hatch, purple gate loops and green
  Kelvin overlay were visible. Buck bad visibly moves C1 left and displays the
  Kelvin outer-pad warning. Both retain open-loop/path warnings. The displayed
  hot_SW labels are 55.230 mm² (good) and 46.126 mm² (bad); these labels are not
  validated physical routed loop areas and do not establish a good/bad area ordering.
- Half-bridge good: the full board and hot/gate/Kelvin overlays were visible.
  Half-bridge bad shows the purple gate_Q2 detour; its 116.046 mm² canvas label
  corresponds to the product warning rounded to 116.05 mm². Open-loop warnings
  remain. Both outputs lack adjacent `requirements.toml` and report the VBUS
  limit as missing. The source requirements were not retrospectively copied;
  no 400 V spacing or distance validation is claimed.
- BMS good: purple gate hatches and green Kelvin branches were visible. BMS bad:
  two diagonal purple gate hatches and markers were visible, together with two
  Kelvin-shared warnings and the PACK_N width-current warning. No green dashed
  branches were visible in that bad canvas. Neither BMS canvas showed numerical
  loop-area captions; group names remain in the sidebar. No area value was invented.

## Limits and task state

All six boards are **without saved fill**: 36 unfilled zones in total. All 57 findings
remain available; none was accepted, filtered away or changed. Role evidence remains
`INFERRED`, with zero confirmed roles. The passed read card means only that the
file was read; the other nine review cards remain not-run. No fill, route, role-copper,
CAD, electrical approval or geometry investigation occurred. The six boards, 23
source/copy inputs and 1,152 prepared runtime files were rehashed unchanged.

The native browser captures are JPEG, 1512×751. Their fixed viewport can truncate
sidebar captions, and the complete findings require sidebar scrolling. The DOM
records preserve every actual code/count/message; a screenshot does not show all
findings simultaneously. Only the created tab and six owned servers were closed;
serve replies recorded no extra runs and no write receipt.

Task 6.1's historical checked state is unchanged: this adds the previously missing
direct dated inspection receipt, alongside scoped source-bound visual-test evidence.
This is delegated inspection, not invented human acceptance. Task **6.2 stays open**
for exact-source CI run **41744987316** and applicable local fast evidence. No archive,
release, later-run success or electrical equivalence follows from this record.
