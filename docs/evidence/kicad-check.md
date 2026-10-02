# `fenolite check` on the KiCad demo boards and projects

Counts only (change c0013, task 7.3). Measured on 2026-10-02 with kicad-cli 10.0.6 (macOS) by
`tests/kicad/check/test_check_demos.py` and `tests/kicad/check/test_canary.py` (`FENOLITE_CHECK_EVIDENCE`),
over the 21 readable non-heavy `rt0` demo boards, each in a folder with a `{}` project and a `(version 1)`
rules file, and over the 20 cached demo `project` rows whose board is one of those 21 (paired by tag and
file stem; none of them ships a rules file). Every copy was made in a temporary folder; nothing derived
from the corpus is kept.

| | demo boards | demo projects |
|---|---|---|
| runs | 21 | 20 |
| project folder unchanged (paths, SHA-256, `st_mtime_ns`) | 21 | 20 |
| `model.validate` `ok` / `errors` | 19 / 2 | 18 / 2 |
| `erc.lite` skipped (`native-input`) | 21 | 20 |
| `drc.kicad` `ok` | 21 | 20 |
| `roundtrip` `ok` | 21 | 20 |
| canary `fired` | 21 | 0 |
| canary `not-applicable` (no rules file) | 0 | 20 |
| `tool_writes` = `<stem>.kicad_prl` only | 21 | 20 |
| seconds per run: min / median / max | 0.8 / 1.9 / 12.6 | 0.6 / 1.8 / 11.5 |
| seconds in total | 72.4 | 63.9 |

The `model.validate` errors are the boards' own model findings (duplicate references, as the reader
already reports for them); every round trip passed with `opaque_count` equal to the reader's.

**Canary neutrality on the demo boards** (`test_canary_neutral_demo_boards`): the stripped canary run
reports what a plain run reports on 15 boards. On 6 boards kicad-cli 10.0.6 does not repeat its own
plain report: between identical runs it names a different partner item for some clearance violations,
and on one board it reported 871 violations in one run and 864 in the others. Neutrality cannot be judged
there, and those cases are skipped with that reason; no board showed a difference that KiCad's own
repeated runs did not also show. For the same reason, two `check` runs on such a board can give different
DRC counts; the determinism of `check` is proved on authored projects (`test_check_oracle.py -k
deterministic`).
