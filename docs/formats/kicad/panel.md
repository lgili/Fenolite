# Panels: what a KiCad panel board holds, and the fabricators' rules

Change c0173 writes a panel (several copies of one board, a frame, separations, fiducials and tooling
holes) as a flattened KiCad board, and checks it against the public panel rules of fabricators. This page
records what is known, in Fenolite's own words, before any panel code exists. Sources are listed in
`docs/evidence/sources.md`. No panelisation tool's code, presets or default values were read: S-0802 is
cited as prior art only.

## KiCad facts

| fact | source | label | hypothesis |
|---|---|---|---|
| `kicad-cli` 10.0.6 has no panel command: its `pcb` words are `drc`, `export`, `import`, `render` and `upgrade` (measured by c0118 on 2026-10-05, not committed as a probe), so a panel is a board that Fenolite writes | S-0020 | INFERRED | H-K-PANEL-LOAD |
| A panel is one board: the frame's outer ring on `Edge.Cuts`, and every routed gap between boards (a gap less its tabs) an inner ring of that ring, as a cut-out is; the copies' own cut-outs and slots stay inner rings | S-0021, S-0020 | INFERRED | H-K-PANEL-LOAD |
| KiCad holds a non-plated hole only as an `np_thru_hole` pad of a footprint, so the holes of a mouse bite are pads of one generated footprint per tab | S-0040 | INFERRED | H-K-PANEL-DRILL |
| `pcb export drill --excellon-separate-th` writes non-plated holes to their own file, so mouse-bite and tooling holes go to the NPTH file and nothing of a V-score line or of a routed gap does | S-0022, S-0020 | INFERRED | H-K-PANEL-DRILL |
| Boards that declare `User.1` to `User.45` load in 9.0.9 and 10.0.6 with drawings on them, so V-score lines are `gr_line` items on a user layer whose user name is `V-Score` | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-BOARD-USERLAYERS |
| Which `.FileFunction` `pcb export gerbers` gives the plot of a user layer is not recorded; the Gerber function for score lines is `Vcut` (S-0125), and Fenolite never edits a plot that `kicad-cli` wrote | S-0020, S-0125 | UNKNOWN | H-K-PANEL-GERBER |
| Two copies of a board whose nets keep their names are one net each across the copies, so KiCad's DRC would ask to connect them; each copy's nets are renamed | S-0021, S-0020 | INFERRED | H-K-PANEL-NETS |
| The 10.0.6 footprint library has a `Panelization.pretty` of 31 mouse-bite and break-line footprints (counted by c0118); Fenolite generates its own and uses none of them | S-0018 | INFERRED | H-K-PANEL-DRILL |

## Fabricators' rules

The figures of public guidelines, as read on 2026-10-16. They differ between fabricators; each default of
the panel checks names the row it comes from (`H-G-PANEL-LIMITS`).

| fact | source | label | hypothesis |
|---|---|---|---|
| V-score is for rectangular boards; other shapes are separated by routing with breakaway tabs | S-0791, S-0798, S-0801 | INFERRED | H-G-PANEL-LIMITS |
| A V-score line runs straight over the whole length or width of the panel, scored on both sides; boards on a V-score touch (no gap) | S-0794, S-0796, S-0798, S-0801 | INFERRED | H-G-PANEL-LIMITS |
| Copper is kept at least 0.45 mm from a V-score on every layer (one fabricator), at least 0.4 mm from the V-cut centre line with 1.0 mm recommended (another) | S-0799, S-0794 | INFERRED | H-G-PANEL-LIMITS |
| Copper is kept at least 0.25 mm (outer layers) and 0.40 mm (inner layers) from a routed board edge | S-0799 | INFERRED | H-G-PANEL-LIMITS |
| Two V-score lines are at least 5.00 mm apart (one fabricator) or 2 mm (another) | S-0798, S-0801, S-0796 | INFERRED | H-G-PANEL-LIMITS |
| V-score needs a board of at least 0.8 mm (one fabricator) or 0.6 mm (another) | S-0801, S-0794 | INFERRED | H-G-PANEL-LIMITS |
| A mouse bite is a set of 5 to 8 holes of 0.60 mm, 0.35 to 0.4 mm from hole edge to hole edge (0.3 mm minimum) | S-0795 | INFERRED | H-G-PANEL-LIMITS |
| Mouse-bite holes lie on the frame's centre line or reach a third of their diameter into the board; holes tangent to the edge keep the intrusion small, and holes cutting into it can expose inner copper | S-0795, S-0793 | INFERRED | H-G-PANEL-LIMITS |
| Two tab sets per board up to 30 mm wide, one more every 50 to 60 mm; mouse bites on both sides of a tab between two boards, and none on the rail's (process edge's) side | S-0795 | INFERRED | H-G-PANEL-LIMITS |
| Routed gaps between boards are typically 1.6 or 2 mm, at least 1.2 mm (one fabricator); at least 2.00 mm, the break-routing tool being 2 mm (another) | S-0795, S-0798 | INFERRED | H-G-PANEL-LIMITS |
| A panel border (rail) is at least 5 mm, besides the 2 mm of break routing, so a board is at least 7 mm from the panel edge when routed; a V-score panel needs no border for stability | S-0798, S-0800 | INFERRED | H-G-PANEL-LIMITS |
| A fiducial is a copper circle of about 1 mm with a mask opening and a copper keep-out of at least twice its diameter; three in an L, as far apart as possible, a set on each assembled side; panel fiducials go on the rails | S-0797, S-0796 | INFERRED | H-G-PANEL-LIMITS |
| A fiducial's centre is at least 3.85 mm from the panel edge (one page), and the fiducial with its clear area at least 3.35 mm from the board edge (another page of the same fabricator) | S-0794, S-0797 | INFERRED | H-G-PANEL-LIMITS |
| Tooling holes on a fabricator's own panel are 3.00 mm (registration) or 0.125 in, on the border | S-0800 | INFERRED | H-G-PANEL-LIMITS |
| Panel sizes: 50 × 50 mm to 250 × 350 mm or 580 × 425 mm (one fabricator), V-cut panels 70 × 70 mm to 475 × 475 mm (another), the longest side preferably under 250 mm | S-0800, S-0801, S-0794, S-0796, S-0795 | INFERRED | H-G-PANEL-LIMITS |
