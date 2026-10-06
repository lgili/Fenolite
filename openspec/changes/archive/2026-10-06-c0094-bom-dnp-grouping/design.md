## Context

- **What exists (c0064, archived).** `fenolite.exports.bom.group(parts, template)` leaves out DNP parts when `exclude_dnp` is true, then makes one `BomLine(refs, quantity, fields, key)` per distinct tuple of `group_by` values. Parts are sorted by the natural order of the reference first, so the lines come out in the order of their first reference. `difference(a, b)` matches the lines of two bills by `key`.
- **Both sources share it.** `cmd_bom` gets `BomPart`s from `parts_from_model` or from `parts_from_kicad` (rows read from `kicad-cli sch export bom`, one per reference) and calls `group` once. KiCad is not asked to group.
- **The defect.** With `exclude_dnp = false` and `group_by = ["value", "footprint"]`, a fitted `R1` and a DNP `R2` of one value give the line `R1,R2` with quantity 2, and a `dnp` column of that line prints `,DNP` (the two distinct values joined).
- **The decision** is the maintainer's, of 2026-10-06 (proposal).

## Decisions

1. **The DNP flag always splits a group.** In `group`, two parts are on one line when their `group_by` values are equal and their `dnp` flags are equal. Naming `dnp` in `group_by` still works and now changes nothing about which parts share a line.
2. **Where DNP lines sort: nowhere special.** Lines are sorted by the natural order of their first reference, as before, and this is the only rule. A DNP line stands where its first reference puts it. For `R1` and `R3` fitted and `R2` and `R4` DNP, all of one value, the lines are `R1,R3` and then `R2,R4`. Alternatives rejected: all DNP lines at the end of the bill (a second sort key, which moves every DNP line away from the parts of its value and changes the bills of templates that name `dnp` in `group_by` today); the DNP line right after the fitted line of its value (the order would no longer follow from the references alone). The rule kept is the one a template with `dnp` in `group_by` already had, so such a bill does not change by a byte.
3. **The key of a DNP line.** `difference` and `result.changes` identify a line by `key`. Two lines of one value need two keys, or one would hide the other. When `group_by` is not empty and does not name `dnp`, the key of a DNP line is the `group_by` values followed by `DNP` (`DNP_TEXT`, the text the `dnp` field prints). Keys of fitted lines are unchanged, so a comparison of two bills without DNP parts gives the same `changes` as before. No collision is possible: a fitted key has as many values as `group_by`, a DNP key one more. When `group_by` names `dnp`, its value is in the key already; when `group_by` is empty the key is the reference. Alternative rejected: a `dnp` attribute on `BomLine` and `BomChange` (a change of two public shapes and of the JSON of `changes` for one flag).
4. **`exclude_dnp = true` is untouched.** DNP parts are left out before grouping, so no DNP line and no longer key exists.
5. **No code in `cmd_bom`.** The command calls `group` for both sources; `counts.dnp` stays the number of DNP parts the source has, listed or not.

## Risks

- A user who relied on the mixed line gets one line more. That line was a wrong quantity; the changelog says so under "Fixed".
- A consumer of `result.changes[].key` that assumes a fixed length sees one value more on DNP lines, only with `exclude_dnp = false`. `docs/cli-contract.md` says it.

## Proof

- `tests/unit/exports/test_bom.py`: the same parts from `parts_from_model` and from `parts_from_kicad`, grouped without `dnp` in `group_by`: two lines for one value, their references, quantities, `item` numbers and keys; with `exclude_dnp = true` only the fitted line; the order by first reference; unchanged keys when `group_by` names `dnp` or is empty; `difference` when a DNP part becomes fitted.
- `tests/unit/cli/test_bom_cmd.py`: `fenolite bom` with `--source model` on an authored board and with the `kicad` source through the fake `kicad-cli`, whose bill holds a value that is not ASCII.
- Both fail before the change of `group` (6 failures on 2026-10-06) and pass after it.
- The oracle tests of `tests/kicad/assembly` compare parts, not lines; they are run on 10.0.6 and in the 9.0.9 image to show that nothing moved.

## Corrections made while implementing

- `docs/release/v0.2.md`, row "v0.2a item 5": its result is `met` and it has no entry under "Recorded limits"; no limit there mentions DNP grouping, so the record is unchanged.
- No golden CSV changes: the worked example of `docs/assembly.md` and `tests/data/assembly/` hold no fitted and DNP parts of one value under `exclude_dnp = false`.
