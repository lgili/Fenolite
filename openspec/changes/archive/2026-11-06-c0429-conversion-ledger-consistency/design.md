# Design: c0429 conversion ledger consistency

## One function for the issues of a report

`report_issues(report)` in `fenolite.convert` builds the `convert.*` issues of a `ConversionReport`:
`convert.lossy` for each row with `lost > 0`, then `convert.changed` for each row with `changed > 0`, then
`convert.kept` for each row with `kept > 0`, rows in report order. It is pure, so a test can build a report
for every kind of `KINDS` and check the invariant without a source project.

`convert_project` keeps its refusal first: the `convert.lossy` issues of the refused kinds (`report.refused`)
raise `LossyConversionError` without `allow_lossy`, as before. With `allow_lossy`, or when nothing refuses,
the conversion's issues are `report_issues(report)`. The order of the lossy issues changes only in that the
refused and warned kinds now come in report order, not refused kinds first.

`WARNED_LOSSES` (change c0409) goes: every lost kind now warns. The loss class (`refuse` or `report`) keeps
its one meaning, whether a loss needs consent.

## Import

`cmd_import._altium` already calls `fenolite.api.convert` with the command's `--allow-lossy`, so the refusal
is convert's: `LossyConversionError` reaches the CLI's error mapping with the same issues and `FEN-7001`.
What the import lacks is the report. `_read` returns the conversion with the source, and `_run` puts
`conversion.report.to_json()` under `result.report`; a KiCad source gives `null`. The import keeps every
`convert.*` issue of the conversion (it filters only `convert.no-verify`, as before).

The importer may not import `fenolite.api` (`tests/unit/test_import_graph.py`), so `ImportReply` (the v0
wire shape) gains `report: ImportReport | None`, a copy of `ReportReply`'s fields; a test validates the
replies of both commands against their schemas. The v1 result class `ImportResult` takes the
`ConvertReport` that `ConvertResult` uses, and its row gains the optional `kept` of change c0424, which
the closed v1 convert schema lacked. Every new field is optional, so the v1 compatibility check against
the release tag holds; `fenolite.import.v0` changes, so `frozen-v0.json` is refrozen.

## Not changed

- What a direction counts as lost, changed or kept (c0423 and c0424 own those counts).
- The refusal rule, the exit codes, `convert.changed` and `convert.kept`.
- `checks.equivalence` and the verification of a conversion.
