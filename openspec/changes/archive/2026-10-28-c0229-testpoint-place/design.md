## Context

c0175's package 8 plans `testpoints --place --side SIDE [--pitch] [--reach] [--size] [--nets]`: one probe per
uncovered net on a grid site near its copper, joined by sitting on the copper or by one straight track, spread
by `--min-pitch`, with `testpoints.no-site` for a net without room. c0212 deferred it: the probes are parts and
copper the design script lacks, and the search needs the clearance of new copper. What exists:

- `exports.testpoints.report` (c0118): eligible nets (two pads or more), access from a side, coverage.
- `design.test_point` and `dsl.assembly.test_point_footprint`: the generated probe of `Fenolite_Assembly`.
- `embed.place_footprint`, the board writer, `backend.board_pads`, `placed_extents`, `board_edges`,
  `design_rules`; exact thick shapes and `thick_closer_than`; `checks.copper.check_copper` with
  `CopperChecker` and `tidy.edits.fresh_clashes` (c0210, c0214).
- `docs/lens.md`, "Board-only footprints": a footprint without `fenolite.path` that matches no part is kept by
  a rebuild with `layout.board-only`; tracks drawn on the board are kept while their net exists.
- `silk.board.gather` (c0212): the silkscreen strokes and text boxes of a board.

## Decisions

1. **Back into the script: not needed.** A probe is placed without `fenolite.path`, so a rebuild keeps it as
   a board-only footprint, and its track (no script copper uuid) as board copper. A test builds the blink,
   places probes, rebuilds and finds them. `sync` is not changed; `testpoint.board-only` (info) names the
   probes and how to author them in the script instead.
2. **The probe.** `dsl.assembly.test_point_footprint(size, shape="circle")`, placed with `place_footprint`
   (uuids derived from the net's name, so a run again gives the same bytes), reference `TP<n>` after the
   highest `TP` number in use. Its `Reference` goes to the side's fabrication layer, on the probe (hidden when
   the board has no such layer): on the silkscreen, KiCad's default field place lies over the neighbours' pads
   (measured on the bench, `silk_over_copper`). `fenolite silk --designators` can place it later.
3. **Sites.** Points of a grid of `--grid` (default 2.54 mm; c0175's `--pitch`, renamed so it is not taken
   for `--min-pitch`) in the board frame, within `--reach` (5 mm) of an anchor of the net on the side's outer
   layer: a pad centre, a via, a track or arc end. Nearest first, then by y and x; the anchor is the nearest
   one. A site on an anchor needs no track; otherwise one straight track of the net's class width (else
   0.25 mm) runs to it. Sitting on a track's middle is left out: the track joins at an anchor.
4. **Obstacles.** The probe pad (`--size`, default 1 mm) and its track keep the clearance in force from other
   nets' copper on the layer (pads, tracks, arcs, vias, stored zone fills), from holes (the track ignores its
   own net's holes), and from earlier probes and tracks; the edge clearance from the edge, the site inside the
   material; the probe touches no courtyard face of the side, no silkscreen ink of the side (`silk_over_copper`
   of KiCad: a probe has a mask opening) and no rule area of the layer that forbids footprints or pads; the
   track touches no rule area that forbids tracks. The clearance is the largest of the project's minimum, its
   class clearances and 0.2 mm (a Fenolite floor for a board without project file); the edge clearance the
   project's (0.5 mm by default) and at least that. Probes keep `--min-pitch` (1.27 mm with `--place`).
5. **Silkscreen as a shape.** `silk.board.silkscreen_ink` gives the strokes of the side and the estimated
   boxes of its visible texts (the estimate only grows, c0212), so `exports` takes them as data and keeps its
   import layering.
6. **Greedy, per net.** Nets in natural order; each takes its first free site. A net without one is
   `testpoint.no-site` (warning) with the nearest site and its first blocker, or why no site was looked at.
7. **Check before write.** `CopperChecker` with the project's rules judges the board before and after; a probe
   whose footprint, pad or track a fresh clash names is left out (`testpoint.check-failed`, warning) and the
   others are written. Removing items cannot add a clash, so one check suffices.
8. **`--drc`.** As `silk --drc`: copies before and after, by type; a grown type is `testpoint.drc-new`
   (error), nothing is written. `lib_footprint_issues` and `lib_footprint_mismatch` are left out: the probes'
   library is in no table of an edited board, and KiCad 10.0.7 gives one `lib_footprint_issues` per probe
   (measured, `docs/formats/kicad/drc.md`). Clean, the reply is `KICAD-VERIFIED`.
9. **Codes keep the singular prefix** `testpoint.` of c0118, not c0175's `testpoints.no-site`.
10. **The report is of the written board.** With `--place`, `test_points`, `coverage`, the findings and the
    CSV of `--out` describe the board with the probes; `result.place.before` keeps the coverage as read.

## Risks / Trade-offs

- A custom clearance rule larger than the clearance of the search is found by the copper check (decision 7)
  and the probe dropped, not moved: run again with a larger floor if this becomes common.
- The search is greedy: an early probe may take the only site of a later net.
- Zone fills are judged as stored; a probe beside a fill of another net may be refused although a refill would
  make room.

## Migration Plan

None: new options of an existing command.

## Open questions

None.
