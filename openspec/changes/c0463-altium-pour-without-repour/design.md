# Design: c0463

## Sources

| id | what | used for |
|---|---|---|
| S-2220 | The maintainer's report of their own board on `cac/lote-28` and `cac/lote-29`, relayed by the coordinating session on 2026-11-06. Counts and codes only: 28 polygons written unpoured by flow B, all 28 filled by Repour All, and Altium DRC after Repour. | why, and the private acceptance |
| S-2221 | The saved polygons and regions of the public rows (corpus, MIT and other declared licences). For outlines with arc vertices: how the polygon record stores the arc, and how the regions Altium saved approximate it. | D1 |
| S-2222 | The same rows: the outlines that are not simple rings, and the regions Altium saved for them. | D2 |
| S-2223 | Kit sample `pour-hatched`: authored hatched polygons (90°, 45°, horizontal, vertical) poured by Altium Designer 24.5.2.23 and saved. | D3 |
| S-2224 | Kit step `repour`: each public row, as published, opened in Altium Designer 24.5.2.23, Repour All run, the document saved, its regions read back. | D5 |
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

## D6: graduation

`Computed pours are experimental` names the K6 round as its exit. This change adds the conditions and
performs it:

- K6 passes `pour`, `pour4` and `pour-hatched`;
- the Repour oracle passes every polygon of the 8 rows;
- the maintainer's board, flow B, writes all 28 polygons poured, and Altium's DRC with no Repour gives
  the same counts per rule as after Repour (S-2220, counts only).

Then:

- `result.pcb.pour.evidence` is `ALTIUM-VERIFIED(kit)`, and the hypotheses are recorded as verified;
- `altium.zones-poured` no longer names Repour All;
- `--altium-pour outline` stays for users who want Altium to pour.

## Risks

- **Run time.** The pour of -08 is the slowest case (watch item `test_pour_time`). More polygons poured
  means more time. The budget of `test_pour_time` stays; a pour over budget is a finding, not a
  refusal.
- **A disagreement with Altium on a corner case.** Such a polygon is refused with its reason, which is
  never worse than today.
