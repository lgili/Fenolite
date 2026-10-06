## Why

A bill of materials is what someone buys and fits from. With `exclude_dnp = false` in the user's column template, `fenolite bom` puts a part marked "do not populate" (DNP) on the line of the fitted parts of the same value, unless the template names `dnp` in `group_by`: one line, one quantity, and the count is too high by every DNP part on it. The implementer of c0064 recorded this as an open question for the maintainer (archived design of c0064, "Measured", item 10), and the guide tells the user to add `dnp` to `group_by`.

The maintainer decided on 2026-10-06: a DNP part never shares a line with a fitted part, whether or not `dnp` is in `group_by`. A line is all DNP or all fitted.

## What Changes

- **`exports/bom.py`, `group`.** Parts of equal `group_by` values form one line only when they are all fitted or all DNP. Quantity and references are those of the line's own parts. Lines stay sorted by the natural order of their first reference; a DNP line has no place of its own.
- **`BomLine.key`.** When `group_by` is not empty and does not name `dnp`, the key of a DNP line is the values of the `group_by` fields followed by `DNP`. Every other key is as before. `difference` matches lines by this key, so the fitted line and the DNP line of one value are compared separately.
- **Both sources.** `--source model` and `--source kicad` both pass through `group`; a test of each proves it.
- **Docs.** `docs/assembly.md` states the rule and where DNP lines sort, and drops the advice to add `dnp` to `group_by`; `docs/cli-contract.md` states the rule and the key of a change.

Nothing changes for a template with `exclude_dnp = true` (the default), for one that already names `dnp` in `group_by`, or for an empty `group_by`.

Size: half a design-day.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `assembly-outputs`: MODIFIED "Neutral BOM parts and lines" (the grouping rule, the key, one scenario more) and "BOM difference" (lines are matched by their `key`).

## Non-goals

- No option to get the old grouping back: a line that mixes fitted and DNP parts has a wrong quantity.
- No change of the placement table (`pnp`): it has one row per footprint.
- No change of what `kicad-cli` is asked for, of the template format or of the default template.
- No new issue code.

## Evidence level required

None new. Grouping is mechanical (`docs/assembly.md`, "Evidence"): the levels of `H-K-BOM-CSV` and `H-K-BOM-MODEL` are about the parts, which do not change.

## Impact

- Changed: `src/fenolite/exports/bom.py`, `tests/unit/exports/test_bom.py`, `tests/unit/cli/test_bom_cmd.py`, `docs/assembly.md`, `docs/cli-contract.md`, `CHANGELOG.md`, `openspec/README.md` (the id row).
- Output that changes: a bill made with `exclude_dnp = false` and a non-empty `group_by` without `dnp`, where DNP and fitted parts share the `group_by` values. There the bill has one line more per such value, and `result.changes[].key` of a DNP line has one value more.
- Depends on c0064 (archived).
