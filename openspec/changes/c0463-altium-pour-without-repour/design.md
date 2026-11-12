# Design: c0463

## Sources

| id | what | used for |
|---|---|---|
| S-2220 | The maintainer's report of their own board on `cac/lote-28` and `cac/lote-29`, relayed by the coordinating session on 2026-11-06. Counts and codes only: 28 polygons written unpoured by flow B, all 28 filled by Repour All, and Altium DRC after Repour. | why, and the private acceptance |
| S-2221 | The saved polygons and regions of the public rows (corpus, MIT and other declared licences). For outlines with arc vertices: how the polygon record stores the arc, and how the regions Altium saved approximate it. | D1 |
| S-2222 | The same rows: the outlines that are not simple rings, and the regions Altium saved for them. | D2 |
| S-2223 | Kit sample `pour-hatched`: authored hatched polygons (90°, 45°, horizontal, vertical) poured by Altium Designer 24.5.2.23 and saved. | D3 |
| S-2224 | Kit step `repour`: each public row, as published, opened in Altium Designer 24.5.2.23, Repour All run, the document saved, its regions read back. | D5 |
| S-2300 | K6 sample `pour` repoured in Altium 24.5.2.23. The positively cleared Keep-Out layer region has rounded corners; the polygon cut-out with zero clearance keeps its outline. | D6 |
| S-2301 | Altium 24.5.2.23 batch DRC before and after native Repour All on a Fenolite-authored 28-polygon Flow B substitute. | D6 |
| S-2303 | Native K6 P3 and a separate six-polygon neck threshold comparison in Altium 24.5.2.23. | D6 |
| S-2304 | Public row `-08` freshly repoured and saved in Altium 24.5.2.23. Its normalized polygon records match S-2224. | D5, D7 |
| S-2225 to S-2229 | reserved for the tasks' records | |

Each fact is recorded in `docs/formats/altium/pcb-pour.md` with its evidence label.

## D1: outline arcs

The reader already sees arc vertices: `outline-arc` is given where an outline vertex has `KIND=1` with a
centre, radius and angles. The pour turns each arc into chords by the polygon's `ARCRESOLUTION`. That is
the same chord rule `pour.py` uses for pad and track arcs: the largest step whose sagitta is at most `d`.
The pour then runs as for any ring.

- The written polygon keeps its arc vertices.
- The written regions are chords, which is how Altium saves them (S-2221).
- An arc of zero radius or of a sweep the reader cannot place still refuses `outline-arc`.

### D1a: arc polygons through a conversion (task 1.3)

What happens before this change (checked on row -02 at 3debc42c3):

- `convert --to kicad` and `import --to python` give an arc zone the outline of its polygon record,
  flattened at KiCad's chord error of 5000 nm (`altium_to_kicad.zone_outlines`), and report it `changed`.
  5000 nm is within `ARCRESOLUTION` for 0.5 mil but not for 0.0394 mil.
- `convert --to altium` of that board writes the chords as line vertices: 114 vertices in place of 18, with
  no reported difference.
- A model zone with no outline that reaches the Altium writer directly is skipped (`lower.py`): RT-A3
  (`model_roundtrip`) and an API write of an Altium reading. The polygon is then gone from the written
  document.

The change:

- Everywhere the model gets an arc zone, its outline is the ring of `pour.record_outline`, chorded by the
  polygon's own `ARCRESOLUTION`. No path drops it.
- The source's arc vertices travel in a board property beside the zone, keyed by the polygon's `UNIQUEID`
  (the c0450 carrier pattern). The way back writes them when the zone's outline still equals the chorded
  ring of the carried vertices. Otherwise it writes the outline's chords and reports the zone `changed`.

## D2: outlines that are not simple

The corpus's two `outline` refusals are inspected first (task 2.1). A ring that touches itself at a
vertex is split at that vertex into simple rings, when the saved pour shows Altium fills each part. A
ring that repeats a vertex keeps it once (as `_polygon_cutouts` does since lote-28). A ring that crosses
itself keeps its refusal unless a source shows how Altium fills it. Rings are never re-wound or unioned
on a guess.

## D3: hatched polygons

Altium's hatch is a set of tracks over the solid pour's area:

- tracks of the polygon's `TRACKWIDTH`;
- at `GRIDSIZE` pitch;
- in the directions `HATCHSTYLE` names (90°, 45°, horizontal, vertical);
- clipped to the solid pour, with its outline track drawn.

The order of these steps and their alignment (the grid origin) come from the kit sample S-2223, never
from a guess. Until the sample's record exists, `hatched` stays a refusal.

## D4: the exact non-pours and the cascade

- `shelved`: Altium shows a shelved polygon with no copper.
- `plane-layer`: planes are not polygons; c0461 counts split planes.

Both stay in `REASONS` as exact outcomes. The census counts them apart from refusals, under the key
`exact`.

`depends-on-refused` is computed as now. With c0462 and D1 to D3 its roots go away. It must still exist,
because pouring a neighbour of a refused polygon would use copper that is not there.

## D5: the Repour oracle

`fenolite kit` gains the step `repour`: open, Repour All, save, close. Its record per row is the region
set Altium saves, kept as M1 to M4 inputs: a JSON of rings in nanometres, declared in
`tests/data/MANIFEST.toml`. The rows' licences allow keeping derived geometry, as for the existing kit
records. `tests/corpus/test_altium_pour_repour_c0463.py` compares, for each polygon, Fenolite's computed
pour of the converted document with that record. Every polygon must pass M1 to M4.

The comparison with the source's saved pours stays as well. Where the two oracles disagree, the saved
pour is stale. The test then says so for that polygon and uses the Repour record.

The exact neck cut of the heavy public row reaches the spatial index comparison cap inside one
arrangement. Retry that cap once with a smaller cell target, retaining the same exact arithmetic
and operation-wide budget. Any remaining limit still refuses the polygon. This retry does not
change the candidate geometry tolerance or the Repour comparison thresholds.

## D6: graduation

Use a round conservative clearance around filled keep-out regions (S-2300); the square-corner rule for
ordinary rectangular pads and filled copper is separate. Polygon cut-outs still carry no clearance.
Remove the two copper lobes of a short opened neck where it crosses between distinct copper rims,
using the chords of its convex hull (S-2303).

`Computed pours are experimental` names the K6 round as its exit. This change adds the conditions and
performs it:

- K6 passes `pour`, `pour4` and `pour-hatched`;
- the Repour oracle passes every polygon of the 8 rows;
- the authored Flow B acceptance board reproduces the default keep-out clearance trigger, writes all
  28 polygons poured, and Altium's DRC with no Repour gives the same counts per rule as after Repour
  on the same return (S-2301). The original private board remains a separate unverified case (S-2220).

Then:

- `result.pcb.pour.evidence` is `ALTIUM-VERIFIED(kit)`, and the hypotheses are recorded as verified;
- `altium.zones-poured` no longer names Repour All;
- `--altium-pour outline` stays for users who want Altium to pour.

K6.5 measures the Polygon Pour Manager's pending repour status, as specified by c0215. The authored
`P5` and `P5_NONET` negative controls have no copper both before and after a successful repour
(S-1572, S-1579). A zero area alone does not put either control in the K6.5 count; a manager flag
still does. The native save, DRC and geometry comparisons remain separate gates.

K6.6 keeps the original DRC report and accepts only the exact expected unrouted-net diagnostic for
the netless, empty `P5_NONET` control. Altium 24.5 reported 42 raw findings, with one polygon finding
for this control and zero Modified Polygon findings. Any other polygon finding remains a failure.

At the release of 2026-11-07 the conditions are not all met (D7), so none of these steps is taken: the
computed pour stays `INFERRED` and experimental, and `altium.zones-poured` still names Repour All.

For solid pours in 45° mode, a through-hole pad with capsule-shaped copper starts each relief
conductor at the endpoint facing that spoke (S-2308). The pad copper shape decides the endpoint;
the observed pads include both plated slots and a round drill. This removes the dominant interior
difference on row `-06` P7 and P9. The P6 discrepancy near an existing same-net track and the
rectangular pad control remain open.

## D7: known differences (measured 2026-11-06, reported)

The release of 2026-11-06 closes this change with the differences below measured and named, not fixed.
Each is a polygon that pours and fails a criterion against Altium 24.5's Repour All (S-2224, S-2227), or a
refusal with its reason. The evidence of `result.pcb.pour` stays below `ALTIUM-VERIFIED(kit)` for them.

| Row | Polygons | Measured | Reason |
|---|---|---|---|
| `-01` | 4 of 5 (`Top Layer-No Net`) | M1 1.27 to 4.01 times the allowance; one M2 (0.30) | not measured; the five share one name, so a layer's verdicts share a key |
| `-02` | GND planes `P18` (top), `P17` (bottom) | M1 0.205 and 0.188 after corrections. M2 remains | S-2311 separates the outer board shape from physical cut-outs. S-2314 removes the largest P18 M2 difference by matching the simple octagonal SMD void. Two P18 and 17 P17 M2 differences remain |
| `-04` | `P7`, `P8`, `P9`, `P14` (top) | M1 1.99 to 3.85 | the ball grid of an LM3644: Altium's copper stands 142 to 282 µm from pads whose governing Clearance is 100 µm. Not explained |
| `-06` | GND `P6`, `P7` (top), `P9` (bottom) | M1 1.48, 2.23, 2.45 | read with its Board Outline Clearance matrix by the outline's cells (S-2227), the band along the board's edge is gone (16.1 and 14.1 before); what remains is not measured |
| `-08` | `P100`, `P14` (bottom); one polygon refused `neck-bound` | M1 2.83 and 24.4 | on `P14` Altium pours a piece of 13.95 mm² among 83 pads of other nets that Fenolite leaves free (Fenolite's extra copper there is 0.015 mm²); not explained. `P100` not measured. The refused polygon's exact neck cut exceeds its work bound |
| `-08` | the pour of the row | 175.2 s alone, 209 s with two workers, for 32 of 33 polygons poured (none before task 4.3) | the Clearance matrices are read cell by cell, so the row pours instead of refusing; `test_pour_time` gives `-08` its own limit of 270 s (175.2 s × 1.5, rounded up to 10 s), every other row keeps 60 s. A known difference for the performance work of v0.8 |
| all | M2 on most polygons | the saved and repoured pours differ by small slivers | M2 counts pieces; slivers below the allowance count |

On 2026-11-10 (S-2304), the smaller exact cut cells and keep-out restriction fix pour all 33 polygons
of row `-08`. Its computed polygon pieces agree when read from the published and fresh native inputs,
and all 33 M1 comparisons pass against both. The native M1 ratios of P100, P14 and P102 are 0.68800,
0.05620 and 0.50583. The remaining M2–M4 findings stay in the oracle pins.

An experimental replay clipped foreign clearance beyond the thermal air gap when the centerline
reached receiving copper first. Both U11 directions on P107 meet that condition. The isolated
replay recovers 3.581786 of a 3.583251 mm² native pocket. On the full row the M1 ratio nevertheless
rises from 0.671 to 0.711 and the 27 polygons with residual findings remain the same. The S-2321
native controls omit three conductors accepted by this replay. A direct via and a second candidate
conductor do not explain the omitted east conductor. The engine retains its conservative rejection.

The independent S-2321 clear-receiver controls establish the area cutoff before the solid thermal
conductors. Removing dead copper is disabled in one matched native board. The small receiver
survives with the cutoff off and disappears with it on. The large clear receiver connects. The
isolated public P107 replay reduces the M1 ratio from 0.671 to 0.458, the M2 pocket count from 590
to 576, and the candidate region count from 32 to the native 31. Four lighter native rows retain
their measured criteria. The public replay SHA-256 is
`54679481362653850fa121f284887cb1aef523b7fc0e4a0690b65b601e61049d`.

The S-2318 side-in-gap controls keep conductors with as little as 19.996 µm of centerline
clearance under a 100 µm neck threshold, while the S-2310 side obstructions are rejected. The
two fixture geometries differ, so the native result needs a more specific rule.
In S-2324, changing only the air gap flips both matched families when the gap crosses the foreign
pad center along the spoke axis. The width, pad length and equivalent-void swaps preserve their
original outcomes. The scope is those authored side-obstruction cases.

Dead-copper filtering indexes contact bounds before exact intersection when there are several pieces
and contacts. On row `-08` P100, 2,329 of 71,208 piece/contact pairs can intersect. The indexed and
unfiltered checks retained identical pieces in the same order and the final P100 geometry was identical.
This measures only the filtering phase.

The solid relief check uses the same bounds rule for the copper and foreign-clearance pieces.
On P100, 1,132 spoke queries select 2,211 obstacle pieces and 1,463 receiver pieces in total.
Reusing the same exact cut and prior pours, the measured P100 geometry is identical with and without
the indices. Intersection CPU on this isolated phase was 53.48 s before and 24.53 s after.
On the combined row `-08` engine, the 33-polygon computed result is byte-identical across the index
change (SHA-256 `6492c918492dd74b2bd65bc76593d691e2ffbf42bbc5a673b9031cdc555362a2`).
Process CPU under host load changes from 439.92 to 293.71 s. The 270 s local elapsed limit is open.

The M4 grouping check indexes region and hole bounds before the same exact point-in-ring predicate.
On the row `-08` B.Cu GND comparison, the prepared check handled 1,978 contacts and 584 holes in
13.30 CPU s. All 66 sampled assignments agree with the unfiltered exact check. This measures the
comparison phase separately from the pour timer.

On 2026-11-10 (S-2313), Altium repoured two variants of row `-04`, changing one flag per variant
across all nine polygons. Turning off optimal void rotation still left the same four M1 failures
against Fenolite. With neck removal off in both engines, all nine M1 comparisons passed. The M1
ratios for P14, P7, P8 and P9 were 0.74647, 0.11708, 0.30643 and 0.10838. Six M2 findings remain
even with neck removal off. This isolates the four M1 failures to the neck-removal stage. The
normal-settings reference and its failing comparisons stay in the oracle pins.

The authored chamfer controls (S-2316) reproduce the missed cut when a foreign clearance shapes
a 0.14 mm tip under a 0.20 mm neck threshold. Three such cases lose about 0.04054 mm² in Altium
while Fenolite loses at most 0.000434 mm². A fourth 0.14 mm case keeps its copper, as do all
six unobstructed axis-aligned controls. The tested threshold sweep uses separate board positions.
Both foreign-pad arrangements keep the tip at 0.26 mm despite cutting it at 0.20 mm.
The width of a chamfer alone cannot determine the cut and no correction is established for row `-04`.

A dominant row `-06` P6 difference is localized to the east relief of one SMD pad. The authored
controls retain it beside a same-net straight track or T junction and omit it when it would enter
the air gap of an adjacent SMD relief pad whose centre is ahead of it. The native matrix retains
the conductor beside lateral and behind-pad gaps (S-2309). The engine uses facing gaps for 90°
solid-pour SMD reliefs. The hatched and 45° rules keep their separate native measurements.
Switching off neck removal leaves the twelve rectangular authored outcomes unchanged. The switch
on P6 of public row `-06` restores two native copper pockets (S-2315). In the ten circular-peer
controls (S-2317), the extension can pass a facing gap when one receiver contact spans its full
width. Clipping the extension to that gap matches all ten M1–M4 comparisons with neck removal
off. Public P6 with neck removal off then passes M1–M4 (M1 0.14541). With the original setting
P6 passes M1 (0.19821) and M3, with M2 and M4 still open.

In the authored straight-to-curved taper matrix (S-2319), the six cut pairs at widths of 100, 150
and 200 µm attach to opposing rims within 2.5 µm of the threshold distances. The wide control
keeps its copper. One native cap has two spans, so the endpoint measurement alone does not
determine the cap. The first attachment of public P6 is 150.001 µm from the opposite neck-off rim.
This observation does not resolve the remaining M2 and M4 findings.
A straight chord between the derived taper endpoints leaves no M2 pocket in the seven
authored local windows at 12.7 µm. The same local diagnostic on public P6 reduces XOR from
0.008067 to 0.001569 mm², with one M2 pocket at 2.54 µm. The S-2320 chamfered terminal has
different attachment distances and remains unmodelled. Its pad-free control reproduces the native cut.
The straight-to-curved taper cap still uses two spans when its stored arc resolution tightens
from 12.7 to 2.54 and 0.508 µm (S-2323). The intermediate point moves as the rim changes.
A finer tessellation of the cap itself cannot explain that point.

The S-2322 straight-sided controls distinguish acute tips from those constrained chamfers. Altium cuts
the 30°, 45°, 60°, 75° and 85° tips with a chord normal to the bisector at the analytic tangent distance
on that bisector. Both side endpoints agree within 2.3 nm at both tested rotations. The right-angle
controls retain the apex. At an apex in the actual removed copper, the engine builds the chord using
integer lengths and exact rational projections when both source sides extend far enough. It checks
the cut stays inside the apex's raw component. Other acute corners keep the local opening hull.
The cuts of the circular opening and the pinch handling still apply.
All 18 authored M1–M4 comparisons pass. On isolated row `-08` replays the 0.006365 mm² acute-tip
finding clears on both P14 and P65. P65 again touches the same-net track, with 0.000481474 mm² of
overlap against 0.000481447 mm² in the native reference. The remaining findings stay open.
The integrated cutoff and cap corrections clear M4 on P65 against both row `-08` references. P107
and P100's native M1 ratios improve to 0.457 and 0.354. All 33 polygons pour and pass M1. The same
27 polygons retain at least one M2–M4 finding against both references. The local measured pour
took 163.00 s elapsed and 158.26 s of process CPU. The published and native comparison hashes are
`fb2443c7900789750e95386b05a4bc593ff5a115cf5a45cd7fd239c508516c7b` and
`936caabb5d3ec781e17cac3200f455720e30b9100eef8d9ac113373bb5b501e8`.
Rows `-01` and `-04` still have four native M1 findings each. The kit plan retains all 70 prior
file hashes and the same kit SHA-256. Verification of the retained native results reports 11
K6 passes and no failures. K6.8 remains unavailable on the approved 24.5 build.

The S-2322 diamond controls preserve all four right-angle vertices in Altium. An isolated circular
opening cap can have an axis-aligned box wider than the neck radius after rotation. Fenolite
preserves the cap when it has one nonacute apex and all its vertices are within the radius plus
the arc tolerance. This restores all 16 corners of four native-matched diamond controls and
0.002149315 mm² in public row `-04` P11. Two diamond controls with connected removal rings and
the separate 0.001654949 mm² P11 difference stay open.

Task 3.3 is not done: a text or a graphic within a polygon's reach still refuses it (`unshaped-copper`,
`unshaped-pad`). Shaping a stroke text needs the glyphs of Altium's stroke font, for which no public
source was found. No public row refuses for it. The authored Flow B substitute also pours all of its polygons (task 5.2).

## Risks

- **Run time.** The pour of -08 is the slowest case (watch item `test_pour_time`). More polygons poured
  means more time. The budget of `test_pour_time` stays; a pour over budget is a finding, not a
  refusal.
- **A disagreement with Altium on a corner case.** Such a polygon is refused with its reason, which is
  never worse than today.
