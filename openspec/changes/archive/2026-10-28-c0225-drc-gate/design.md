## Context

`fenolite.api.trial` (change c0209, `src/fenolite/api/trials.py`) reads a KiCad board, applies an edit
function to its model, writes both models with one writer for the board's major, runs `pcb drc` on copies
with the project files (zones refilled on KiCad 10) and maps each new finding to the ids of the edit's items.
With `gate=True` it puts back the named items and runs again until no new finding names one.

Three commands already run DRC of their own after an edit: `tidy --drc`, `silk --drc` and
`place --strategy reuse --drc`. Each runs `pcb drc` on the board as it is and as the command would write it,
counts the entries per violation type, and refuses the whole write (`tidy.drc-new`, `silk.drc-new`,
`reuse.drc-new`, errors) when a type has more entries after.

## Decisions

1. **Which commands.** `route` and `tidy` write copper as many small, independent items, so dropping some
   of them leaves a useful board: they take `--gate drc`. `place --strategy reuse` copies a block as one
   fit of parts and copper; dropping part of it breaks the copy, and its `--drc` already refuses the whole
   write. `fill` lets KiCad compute the fills that the trial refills anyway; `build` writes what the script
   declares, so a gate would part the board from its script; `silk` writes no copper. None of them takes
   the option.
2. **One helper over `trial`.** `fenolite.cli._gate` registers `--gate {drc}`, finds the edit's ids by
   comparing the entity groups of `trial.GROUPS` of the board as read and as edited (added, removed or
   changed), and calls `trial` with an edit that grafts those items onto the board `trial` reads
   (`trials.revert(fresh, edited, ids)`). The command then puts back the dropped items in its own model
   (`trials.revert(edited, read, dropped)`) and writes it with its own writer and `--allow-lossy` policy, so
   the board groups written are those the trial judged. The gate runs only when the edit holds an item.
3. **Units.** `trial` takes `together`, groups of ids that the gate drops as one: when a new finding names
   one id of a group, every id of the group is dropped with that finding. `tidy` passes one group per edit
   (its removed, replaced and added ids), so a chamfer is undone whole rather than cut in half. `route`
   passes none: each track and via stands alone, and a net left open by a drop is reported by the verdict.
4. **`--drc` stays.** The existing `--drc` options keep their meaning: an all-or-nothing check by counts of
   types, with their own codes and exit 5. `--gate drc` is the per-item form; `tidy --drc --gate drc` is a
   usage error (`FEN-2001`), since the gate already runs DRC. Moving the `--drc` options onto `trial`
   would change three commands' replies and codes; it is left for a change that asks for it.
5. **The tool first.** With `--gate drc` the command runs the `kicad-cli` pre-flight of `check` (`--kicad-cli`,
   else the tool `check` finds) before it edits anything: exit 6 (`FEN-6001` or `FEN-6002`) and nothing
   written or routed. `route` gets `--kicad-cli PATH`; its `--timeout` stays the router's budget, and the
   gate's DRC runs take the default 300 s. `tidy` passes its `--timeout`. `--kicad-cli` without `--gate` on
   `route` is a usage error.
6. **The report.** `result.gate` is `null` without the option, else `tool_version`, `runs`, `refilled`,
   `items` (ids judged), `kept`, `dropped` (`{id, findings}`) and `findings` (new findings left, which name
   no item of the edit). Each dropped item gives `gate.dropped` (warning) naming the item and its first
   finding; each finding left gives `gate.unnamed` (warning), since it may be the tool's noise
   (`H-K-DRC-REPEAT`). Neither blocks the write: the command plans the board the trial keeps.
7. **The verdict follows the drops.** `route` computes `routed`, `unrouted`, `open` and `connections.after`
   on the kept board, and counts only kept tracks and vias; `tidy` lists only the kept edits in `edits`,
   `counts`, `removed` and `added`.
8. **Evidence.** A gated write with no finding left takes the trial's evidence (`KICAD-VERIFIED`,
   `H-K-DRC-TRIAL` and `H-K-DRC-REPEAT`); otherwise the command's own. No new hypothesis.

## Risks / Trade-offs

- Each gate round costs one DRC run, plus the baseline: a route of many bad tracks may take several rounds.
- A dropped track can leave a net open or a stub dangling; `route` reports the open net, and a later
  `tidy --prune` removes a stub.
- The judged and the written board share their entity groups but may differ in what the command adds
  outside them (net classes of the project, for example); both are written by the same writer.

## Open Questions

None.
