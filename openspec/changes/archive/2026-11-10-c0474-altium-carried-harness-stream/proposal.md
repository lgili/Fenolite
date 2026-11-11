# Proposal: c0474-altium-carried-harness-stream

## Problem
After c0470–c0473, `build --target altium` of an imported Altium project (without KiCad) produced
documents that Altium's own compiler rejects with "Missing child-sheet in Symbol …" on every sheet that
holds a signal harness, while the GUI opens them fine.

The harness records of a source document (connector `215`, entries `216`, type `217`, line `218`) live in
the document's `Additional` CFB stream (`docs/formats/altium/schematic-binary.md`, "Additional stream and
harness records"), never in `FileHeader`. The import reads them through
`read.sch.document.SchDocument.all_records()`, which merges both streams, so the drawn writer (c0471)
re-emitted them as ordinary opaque records — into the `FileHeader` stream of the written document — with
children naming their connector through `OWNERINDEX` counted over the FileHeader records. Altium's
compiler refuses such documents.

## Change
`lower_drawn` routes every opaque subtree whose root record is a harness connector (215) or signal
harness line (218) — together with its children (216, 217, named with `@<line>`) — into a new
`SheetPlan.carried_additional` plan field instead of the sheet's records; `schdoc.additional_records`
appends the carried records after the ones it builds itself, shifting each child's `OWNERINDEX` behind
that base and omitting the owner of the first record (the native convention). The ASCII form refuses
carried Additional records, as it refuses drawn harnesses. Harness-block placement counts the carried
records as occupied space.

## Proof
- `tests/unit/backends/altium/test_drawn_altium.py::test_carried_harness_records_write_to_the_additional_stream`
- `uv run pytest tests/unit/backends/altium/ -q` (3425 passed, 24 skipped)
- The authored regression fixture verifies the `Additional` and `FileHeader` streams and readback.
