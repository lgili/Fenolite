## Context

`checks.drc` already reads the exclusions of a project (`board.design_settings.drc_exclusions`, change
c0114) and judges each as live or stale. KiCad applies a key only when its type, marker position in nm and
ordered uuid pair equal a violation's (`H-K-DRC-EXCL`). The JSON report gives each item's own position, not
the marker's. `kicad-cli pcb drc` takes `--refill-zones` on 10.0, and `KicadCli.refill` already uses it.

Measured on 2026-10-28 with `kicad-cli` 10.0.7 before the design was fixed:

1. The marker of a missing connection between two tracks sits at the end of the first track that faces the
   second; neither reported position is it.
2. At that position both uuid orders of a missing-connection key apply.
3. A clearance key applies only in the report's order, at the first item's reported position; with the
   second item's uuid made the lowest, the report names it first and its own position keys the entry.
4. Among stored keys with distinct comments, the excluded entry carries the comment of the key that matched.

## Decisions

1. **The position by trial, not by model.** Fenolite does not model KiCad's marker placement. It stores
   one probe key per anchor of the two items (reported positions, track and arc ends, via, pad and
   footprint positions, zone corners; at most 128) and per order, each with the comment
   `fenolite-probe:<n>`, in the project of a copy, runs `pcb drc` once and reads the comment on the entry.
   An entry already excluded takes the position of its stored key.
2. **Both orders, confirmed.** The exclusion is written as `[key, reason]` in both item orders, as c0175
   asks: for a missing connection both apply, and for other types the second costs nothing (an unmatched
   key is ignored) and covers a report that names the items the other way. A third run on a copy must show
   the entry excluded with the reason before the write is planned, so a planned key is a verified key.
3. **A mode of `check`.** `--exclude` runs no stage and plans one write of the project file; its own
   findings decide the exit code, so the board's DRC errors do not block the write. `check` becomes a
   mutating command; without `--exclude` it plans nothing, and the examples suite lists it with the other
   commands whose example plans nothing.
4. **Items named as the check prints them.** `ITEM` is a KiCad uuid or the location of the finding's
   `where` (`R1-1`, `/kicad_pcb/segment[0]`), matched in either order; `CODE` is KiCad's type or the
   `kicad.drc.*` code. Several matching entries are refused; the user then gives uuids.
5. **Mirrored keys judged together.** In the DRC stage two stored keys with one type, position and item
   pair in both orders are one exception: live when an excluded entry of that type names the two items in
   either order; otherwise unjudged for the four types KiCad does not repeat, else stale with one warning.
   The counts of `summary.exclusions` keep their meaning per key; `summary.accepted` lists the exceptions.
6. **Trial as a library call.** `fenolite.api.trial` (module `api/trials.py`, so the function does not
   shadow its module in `fenolite.api`) writes the unedited and the edited model with the same writer for
   the board's major, so writer differences cancel, and compares reports by type and item uuid set,
   counted. A new finding names the edit's ids whose KiCad uuids it holds (a footprint's pads count for the
   footprint). The gate reverts the named items (removes an added one, puts back a changed or removed one)
   and runs again until no new finding names an edit item. No command takes `--gate drc` yet.
7. **Refill.** On KiCad 10 both copies are checked with `pcb drc --refill-zones` (no `--save-board`); on 9
   a board with zones gives `trial.not-refilled` and both copies keep their stored fills.

## Risks / Trade-offs

- Entries of `clearance`, `hole_clearance` and `unconnected_items` can differ between two runs of one board
  (`H-K-DRC-REPEAT`): a trial may report such a new finding that names no edit item; the gate only drops
  items a finding names.
- A marker at no anchor (a zone's fill edge, for example) cannot be located: `check.exclusion-unlocated`.
- Each exclusion costs three DRC runs; each trial round one, plus the baseline.

## Open Questions

None.
