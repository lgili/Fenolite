# c0429: conversion ledger consistency

## Why

A reference sweep of conversions (53 cases on `5ab9d645`, S-1880 to S-1889) found `result.report` rows with
lost items and no `convert.lossy` issue: `rule` in 49 cases, `body` in 34, `model` in 33, `schematic` in 5,
`graphic` in 1. `convert_project` gives `convert.lossy` only for kinds whose loss refuses and for the four
kinds of `WARNED_LOSSES`; every other `report` kind loses items without an issue.

`import --to python` of an Altium source converts first and keeps the conversion's issues, not its report.
So the same kinds disappear from an import with nothing said, and the import has no rows to show what was
lost, changed or kept.

## What Changes

- `convert`: one `convert.lossy` warning per report row with lost items, whatever its loss class; the
  refusal stays as it is (`refuse` kinds without `--allow-lossy`, `FEN-7001`). `convert.changed` and
  `convert.kept` stay one per row with changed or kept items. One function builds the issues of a report,
  so convert and import cannot drift apart. `WARNED_LOSSES` goes away.
- `import --to python` of an Altium source: `result.report` holds the conversion's report, the same rows as
  `convert` gives (`null` for a KiCad source); its refusal and `--allow-lossy` rule are convert's (the same
  `FEN-7001` with the same issues).
- Tests pin the invariant for every kind of `KINDS`: lost rows and `convert.lossy` issues name the same
  kinds, and likewise changed rows and `convert.changed`, kept rows and `convert.kept`.

## Impact

- `src/fenolite/convert/__init__.py`, `src/fenolite/cli/cmd_import.py`, `src/fenolite/importer/schema.py`.
- Schemas `fenolite.import.v0` and `.v1` gain an optional `report`; `schemas/frozen-v0.json` refrozen.
- More `convert.lossy` warnings on conversions that lose `report` kinds; exit codes unchanged.
