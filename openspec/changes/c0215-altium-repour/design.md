## Context

- **Request.** The maintainer's request of 2026-10-26: when Fenolite writes or edits a `.PcbDoc`, it
  computes the poured copper with Altium's rules and algorithm and writes the regions, so the document
  opens poured without Tools » Polygon Pours » Repour All. This reverses row 23 of the roadmap's "Open
  decisions" (c0085, 2026-10-06: polygons are written unpoured). The critical point is fidelity: a pour
  that removes necks or islands differently from Altium can show a net connected that Altium's repour
  leaves open, or the reverse.
- **What exists** (`dev` at `3a0bfb7`, read on 2026-10-26).
  - Writer. `pcbdoc.polygon_records` (`backends/altium/pcbdoc.py:1357`) writes one record per zone layer
    with fixed keys and `POURINDEX` equal to the record's position, in the order of falling zone priority.
    `Regions6` and `ShapeBasedRegions6` hold only filled graphics, keep-outs and cut-outs:
    `pcbrecords.region_record` (`pcbrecords.py:722`) writes no net, no polygon index and no hole.
  - Accounting. `lower.py:1196` counts every zone's fills as skipped (`zone-fill`); `convert/to_altium.py:36`
    gives the same reason; `lens/altium_copper.py:931` gives `altium.zones-unpoured`.
  - Reader. The 13-byte prefix holds the polygon index (`read/pcbprims.py:274`). A region holds holes
    (`:442-482`; `RegionRecord.hole_count` is `CORPUS-VERIFIED`). The import gives a polygon its regions as
    `Zone.fills` (`altium-import`, "Zones from polygons"; c0122 keeps their holes). `analysis/fills.py`
    turns stored fills back into rings with holes.
  - Rules. `read/rules.py` maps Clearance with a blank or uniform matrix and with matrix cells
    (c0125, c0130); the matrix kind `Poly` is the item kind `zone`. `read/scope.py` parses `All`, `InNet`,
    `InNetClass`, `InComponent`, `IsTrack`, `IsVia` and `IsPad`, and no polygon query. Polygon Connect
    Style (kind 20) is read as unmapped; `rule-file.md` lists one exported record (S-0297).
  - Geometry. `geometry.boolean` with the `clipper` backend (pyclipper, `geo` extra) gives union,
    difference, xor and offset with round joins on integer nanometres; the fallback has intersection only.
  - Check. `copper.clearance` on an Altium reading judges a poured polygon as a filled zone and counts an
    unpoured one (`altium-verification`, "Copper check on Altium boards").
  - Kit. K6.1 repours `routed` and checks `resave`, `parity`, `poured`, `copper.clearance`. The native
    campaign of c0166 passed K6.1 through the native polygon rebuild on 2026-10-13. A Force Repour All on
    a public conversion saved a polygon without a fill, with zero area in the manager, and the record says
    that repour is not proven to have run (`docs/evidence/altium-native-acceptance.md:270`).
- **Public pages read on 2026-10-26** (facts only, nothing copied):
  - The Plane rule types page of S-0287. Polygon Connect Style: Relief Connect, Direct Connect, No Connect.
    Relief has an air gap width (it applies to No Connect too), a conductor width, 2 or 4 conductors with a
    rotation, and an Auto mode with an optional minimum distance between conductors. Simple mode holds one
    setting for pads and vias; Advanced mode holds one each for through-hole pads, SMD pads and vias. The
    scope is a full query, and an object's own Thermal Relief setting overrides the rule. No default is
    stated.
  - Polygon Pour Properties (version 21; proposed S-0833). Solid is built from regions, one per contiguous
    area; Hatched from tracks and arcs; None draws the outline. Remove Islands Less Than removes areas
    below a value whatever their connection. Remove Necks Less Than removes slivers narrower than a width
    and rounds outer corners to half that width; Obey Rules takes it from the Width rule. Arc Approx. is
    the largest deviation from a true arc. Optimal Void Rotation arranges edges to widen necks. Remove Dead
    Copper removes areas with no connection to another object of the net; a polygon that encloses no pad
    of its net loses all its copper and keeps its outline. Pour Over Same Net has three choices, and Pour
    Over Same Net Polygons Only is the default. Of overlapping polygons, the one of higher order pours over
    the shared area. Clearance comes from the Clearance rules; a polygon-specific rule uses `InPolygon`.
  - Polygon Pour (version 21; proposed S-0834). Repour Selected, All, Modified (`IsModified`) and
    Violating, and Force Repour All in the manager; the preference Repour Polygons After Modification;
    shelving; `PCB.Polygon.AdvancedPour` (open beta) pours true arcs; a connect style may differ for
    through-hole pads, SMD pads and vias.
  - Not stated on any page read: whether a lower `POURINDEX` pours first, how a later polygon keeps clear
    of an earlier one, what the numbers of `POUROVERSTYLE` mean, the unit of `AREATHRESHOLD`, the order of
    the steps, what a pour does at the board edge and at a keep-out, on which side of a curve the
    approximation lies, and the shape of a relief conductor beyond its width and count.
- **Constraint.** Facts come from these pages, from records of the registered public corpus read with
  Fenolite's readers, from KiCad's importer run as an oracle, and from the maintainer's kit. Samples are
  written for Fenolite. Nothing of a private project is read, and no vendor code is read or decompiled.

## Goals / Non-Goals

**Goals**
- A document that Fenolite writes opens with every polygon poured, where the pour is fully determined by
  what the document holds and by facts that have a source or a hypothesis.
- Each difference from Altium's own repour is measurable, located and reported, on authored samples and
  on the public corpus.
- Nothing is claimed for Altium Designer before the kit has shown it.

**Non-Goals**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **Row 23 reversed, as the maintainer's decision.** Row 48 of "Open decisions" records the decision of
   2026-10-26: "Fenolite computes the poured copper of every polygon it writes with Altium's rules and
   algorithm and writes the regions; experimental until a K6 round passes". Row 23 keeps its text and gains
   "superseded on 2026-10-26 by row 48". When the change is implemented, `docs/altium.md` replaces the
   paragraph "Fenolite never writes poured copper" with a description of the computed pour and its limits.

2. **Pour the document as it reads.** The writer writes the document without pour regions, reads it back
   with Fenolite's reader (rules mapped as the copper check maps them), pours that reading, and writes the
   document again with the regions. The engine sees the rules, pads, vias, keep-outs and outline that
   Altium will see. The same function pours a public document for the census. Nothing the writer leaves
   out can enter a pour: a model zone's own KiCad settings, cut-outs while `CUTOUT_REGIONS` is off, items
   in `not_lowered`.
   - Rejected: pouring the neutral model before lowering. The model's zone settings and the items that are
     not written would shape a pour that Altium cannot reproduce.

3. **The inputs of a pour.** Each row becomes a fact row of the new page `docs/formats/altium/pcb-pour.md`
   (task 1.1) with its source and label, or a hypothesis row. Every input has a kit probe (Decision 8) or
   is settled on the corpus. "Refuse" means that the polygon keeps its outline (Decision 5).

   | # | input | what the engine does | source | hypothesis |
   |---|---|---|---|---|
   | I1 | the polygon record: outline, layer, net, `POURINDEX`, `HATCHSTYLE`, `REMOVEDEAD`, `REMOVEISLANDSBYAREA` with `AREATHRESHOLD`, `REMOVENECKS` with `NECKWIDTHTHRESHOLD`, `ARCRESOLUTION`, `POUROVER` with `POUROVERSTYLE`, `OPTIMALVOIDROTATION`, `SHELVED` | read from the document; `HATCHSTYLE` other than `Solid`, `SHELVED=TRUE` or an arc vertex refuses | `pcb-copper.md`, "Polygon pour" (S-0160, S-0172, S-0174, S-0175, S-0176, S-0196); S-0833 | H-A-PCB-CU-REPOUR (existing) |
   | I2 | clearance to an object of another net | the first Clearance rule by priority whose two scopes match the polygon and the object, as the copper check resolves it; a matrix cell of `Poly` against the object's kind above the generic value; a record that could govern the polygon and does not map refuses | S-0558, S-0462, S-0833; native measurement of a via cell, S-0744 | H-A-RULE-CLEARANCE-CELLS, H-A-RULE-SCOPE, H-A-RULE-PRIORITY (existing); H-A-POUR-CLEARANCE |
   | I3 | a polygon-specific Clearance rule (`InPolygon`, `InPoly`, `IsPolygon`) | refuses until `read/scope.py` parses the form; the census counts how often it occurs | S-0833 | H-A-POUR-SCOPE |
   | I4 | Altium's measuring tolerance | a void lies at the exact rule value, rounded outward to whole units; c0152's 3.5-unit tolerance is the check's, never the pour's | S-0616 (c0152) | — |
   | I5 | Polygon Connect Style: style, conductor width, 2 or 4 conductors, angle, air gap; one setting (Simple) or one per through-hole pad, SMD pad and via (Advanced); the rule's scopes and priority | read from the rule records (`connectstyle.py`); Auto mode, a minimum distance or an object's own override refuses | S-0287 (plane page, 2026-10-26), S-0833, S-0834; the record's keys from the census of task 1.2 | H-A-POUR-CONNECT |
   | I6 | the shape of a relief | the void is the pad's (or via's) copper grown by the air gap; each conductor is a bar of the conductor width from the pad centre at the angle (0° or 45°, then every 90° for four, 180° for two), turned with a pad's rotation and not with a via's, ending at the outer edge of the gap; a conductor that would cross another net's clearance is left out | not stated | H-A-POUR-RELIEF |
   | I7 | Direct Connect and No Connect | Direct: the pad's copper joins the pour without a void. No Connect: the air-gap void, no conductor | S-0287, S-0833 | H-A-POUR-RELIEF |
   | I8 | same-net tracks, arcs, fills, regions and polygons | by `POUROVERSTYLE`: covered by the pour (all objects), covered for polygons only, or avoided at the governing clearance; the mapping of the numbers 0, 1 and 2 to the three choices is measured, not assumed | S-0833 (the three choices) | H-A-POUR-OVER |
   | I9 | pour order | polygons of one layer poured in rising `POURINDEX`; a later polygon of another net keeps the clearance from the pour of an earlier one; layers are independent | S-0833 (higher order takes precedence), S-0196; `pcb-copper.md` ("a lower index is poured first", `INFERRED`) | H-A-POUR-ORDER |
   | I10 | necks | an opening by a disc of diameter `NECKWIDTHTHRESHOLD`: inward offset by half, outward by half, round joins; it rounds outer corners to half the width; "Obey Rules" refuses until the census shows its key | S-0833 | H-A-POUR-NECK |
   | I11 | order of the steps | area, voids, necks, then conductors and direct joins, then pieces, islands, dead copper | not stated | H-A-POUR-STEPS |
   | I12 | islands | a piece whose area is below `AREATHRESHOLD` is removed whatever it connects; the value is in square file units (the written value is then 2500 mil²) | S-0833; the unit from the census | H-A-POUR-ISLAND |
   | I13 | dead copper | a piece that touches no object of the polygon's net (a pad through a conductor or a direct join, a via, a same-net track or region under the pour) is removed; a polygon without a pad of its net pours nothing and keeps its outline; a polygon without a net pours nothing | S-0833, S-0834 | H-A-POUR-DEAD |
   | I14 | curves | every arc, round pad, track end, via and rounded corner becomes chords within `ARCRESOLUTION`; voids lie outside the true curve, copper corners inside it, so no copper comes nearer than the rule | S-0833; S-0771 (Arc Approximation of a region) | H-A-POUR-ARC |
   | I15 | optimal void rotation | a computed pour is written with `OPTIMALVOIDROTATION=FALSE` (Decision 6), so the arrangement of edges is no input | S-0833 | H-A-POUR-VOIDROT |
   | I16 | keep-outs | a keep-out region or track with the copper restriction on the polygon's layer, or on the Keep-Out layer, is a void at the clearance of the governing rule | `pcb-records.md`, keep-out rows; behaviour not stated | H-A-POUR-KEEPOUT |
   | I17 | the board edge | the pour is clipped to the board shape (the outline less the cut-outs the document holds), inset by the governing Board Outline Clearance when the document holds one | S-0460 (the rule's edges); not stated for pours | H-A-POUR-EDGE |
   | I18 | pads and vias | the copper shapes the copper check builds for an Altium reading, on the polygon's layer (a through-hole pad's inner shape on an inner layer); a shape it cannot build refuses; a via without a pad on the layer (c0132) keeps clearance to its hole | `altium-verification`, "Copper check on Altium boards"; H-A-IMP-VIA-PADLESS | H-A-POUR-VIAPAD |
   | I19 | holes without copper | the clearance of the `Hole` row of the matrix | S-0462, S-0558 | H-A-RULE-CLEARANCE-CELLS |
   | I20 | copper text, polygon cut-outs, polygon-connect overrides | refuse | — | — |
   | I21 | the pour engine and its preferences | Altium Designer 26.5 with `PCB.Polygon.AdvancedPour` off; a kit form step records the setting | S-0834 | H-A-POUR-ENGINE |

4. **The written form.** Facts first: task 1.3 measures the poured regions of the public corpus before the
   record writer changes.
   - One region (type 11) per piece in `Regions6`. The prefix holds the layer, no net (the census of
     task 1.3 found `0xFFFF` in every saved poured region: the net is the polygon's), the polygon's index
     and no component. The keys and their order are those of saved poured regions (census). The holes
     follow the outline in both forms (hole count and rings, as `read/pcbprims.py` reads them).
   - The twin in `ShapeBasedRegions6` at the same position, with its holes in the form the census shows,
     every vertex straight.
   - The polygon index is the record's position in `Polygons6`, which `POURINDEX` already equals, so no
     reading can mistake one for the other.
   - The pieces of a polygon come together, in polygon order and then by lowest point; vertices are whole
     units, rings without slits, at least three vertices. The census says whether any other storage
     refers to a region by its index; if one does, the record of that storage joins this change.
   - No key of a polygon marks it poured (`pcb-copper.md`, S-0176). That Altium opens the regions as the
     pour, without listing the polygon as modified and without repouring it, is H-A-POUR-OPEN.
   - Read-back: Fenolite's reader gives each zone fills equal to the written pieces within one unit
     (RT-A2 compares `Zone.fills`). KiCad's importer reads them as the zone's fills (10.0.6, oracle test).

5. **Refusal, never a guess.** A polygon is refused when an input of Decision 3 says "refuse", when the
   copper check of the poured reading reports a short or a clearance finding that involves its copper, or
   when it depends on a refused polygon: a later polygon of the same layer whose outline, grown by the
   largest clearance of the layer, meets the refused one. A refused polygon is written with its outline
   only, as today. The closure is computed again after each refusal until no finding involves a pour, and
   it ends because the set of poured polygons only shrinks. Each refused polygon gets `altium.zone-unpoured`
   (warning, `where` `zone/<id>`) with its reason; the reasons are a closed list in `pour.REASONS`.

6. **Switching it on: `computed` by default** (open question 1, decided on 2026-10-26).
   `--altium-pour outline|computed` on every command that writes a `.PcbDoc` (build, convert, panel), and
   `pour=` on `lens.altium.build_altium`, `lower.write_design`, `AltiumBackend.write` and
   `pcbdoc.write_pcbdoc`.
   - The commands and `lens.altium.build_altium`, `lower.write_design` and `AltiumBackend.write` default to
     `computed`. The record-level `pcbdoc.write_pcbdoc` defaults to `outline`, so a test of records names
     its mode; `AltiumBackend.model_roundtrip` keeps `outline` (RT-A3 does not compare fills); the kit
     builds `routed` with `outline`, so K6.1 still repours an unpoured board.
   - `outline` writes today's bytes and gives `altium.zones-unpoured`, as today.
   - `computed` writes the pour, `OPTIMALVOIDROTATION=FALSE` and the Polygon Connect Style rules
     (Decision 11). It gives one `altium.zones-poured` (info) with the counts, the evidence level and the
     words "computed by Fenolite, experimental: Repour All in Altium gives Altium's own copper".
   - `computed` by default without `fenolite[geo]` writes the outline, as `outline` does, and adds one
     `altium.pour-unavailable` (warning) naming the extra; an explicit `--altium-pour computed` without it
     is refused with exit 6 and that hint. The core keeps no dependency.
   - `result.pcb.pour` holds `mode`, `poured`, `unpoured` (reason to count), `evidence` and `hypotheses`.
   - A rewrite of a read document (`rewrite=True`) in `computed` mode pours every polygon again
     (open question 5).
   - Builds of the committed samples with polygons change once: they gain regions, the rules of Decision 11
     and `OPTIMALVOIDROTATION=FALSE`. Task 5.4 rebuilds them, and their pinned tests name the mode.

7. **The comparison** (`fenolite.backends.altium.pourcompare.compare_pours(candidate, reference, *, points=())`). Both
   sides are readings of the same board; polygons are matched by layer, name and `POURINDEX`. Per polygon,
   with `d` its `ARCRESOLUTION` (0.5 mil as written; open question 3, decided on 2026-10-26):
   - **M1 area.** The XOR area of the two pours must not exceed `d` times the boundary length of the
     reference pour. The two approximations of one curve, each within `d`, differ by less than that band.
   - **M2 located differences.** Each part of the XOR that still has area after an inward offset by `d`
     (one that holds a disc of diameter `2d`) is one difference, with its centre, its area and the side
     that has the copper. None may exist. This is where a neck, an island or a dead piece removed by one
     side and not by the other shows, at its place.
   - **M3 islands.** The pieces match one to one: each piece overlaps exactly one piece of the other side
     by more than half the smaller area, with the same number of holes.
   - **M4 connectivity.** For each piece, the set of objects it touches (pads by reference and number,
     vias and tracks by position), a conductor counting as a touch. For each net, the partition of its
     objects into groups connected through copper, the pours included. Both must be equal.
   - **M5 declared points** (authored samples only). Each probe declares points where copper must stay or
     must be gone. The two sides must agree at every point; a declaration that both sides contradict is
     reported as a fault of the probe.
   - The verdict names each failed criterion with the polygon and the place. `compare_pours` writes
     nothing.

8. **Kit group K6, enlarged.** Two samples written for Fenolite: `pour` (two layers) and `pour4` (four
   layers with blind and buried vias and the inner shapes of through-hole pads). Each probe is its own
   polygon on its own net, so a difference points to one input.
   - Probes: P0 a sentinel polygon that must pour copper; P1 clearance (generic, net-class and net rules,
     priority; pads of each shape, vias, a track, an arc); P2 the connect styles the writer lowers
     (Decision 11), one probe net each: `thermal`, `thru_hole_only`, `solid` and `none`, each with a
     through-hole pad, an SMD pad and a via (45°, two conductors and the Simple form occur only in read
     documents and are settled by the census); P3 necks just below and above the width, with a conductor
     narrower than the width; P4 islands just below and above the area, one holding a connected pad; P5 dead copper,
     a polygon without a pad of its net, a polygon without a net; P6 two overlapping polygons of two nets
     and two of one net; P7 a large round pad and an arc track; P8 a keep-out on the layer and one on the
     Keep-Out layer; P9 a polygon past the board edge and one on it, with a Board Outline Clearance rule;
     P10 three polygons with `POUROVERSTYLE` 0, 1 and 2 over a same-net track.
   - Each sample is written twice from one computation: `computed/` with the regions, and `reference/`,
     the same bytes without the regions of the polygons (`pcbdoc.write_pcbdoc(…, pour_regions=False)`,
     internal). The two inputs differ in the pour only.
   - Steps per sample (ids in the spec): rebuild every polygon of `reference/` through the kit script and
     save (checks `resave`, `repoured` with the sentinel, `pour-match` against Fenolite's pour); the same
     by hand with Tools » Polygon Pours » Repour All, once, for `pour` (check `pour-same` against the
     scripted result, H-A-POUR-SCRIPT); open `computed/` and save it without a repour (`resave`,
     `pour-kept`, `parity`); typed: the number of polygons the Polygon Pour Manager lists as needing a
     repour (0) and the number of design rule check violations that name a polygon (0); Force Repour All
     on `computed/` and save (`pour-match`, and `pour-same` against the reference repour); typed: the
     value of `PCB.Polygon.AdvancedPour`.
   - K6.1 stays as it is (`routed`, outline repour).

9. **The public corpus.** `tests/corpus/test_altium_pour_census.py` pours every polygon of the eight
   public PCB documents (`altium-third-party-pcbdoc-01` to `-08`) whose inputs the engine evaluates. It
   compares each with the regions the document holds (M1 to M4) and writes the counts into
   `docs/evidence/altium-pour.md`: polygons, refused with their reasons, compared, passing, the worst
   ratios. A saved pour may be stale, or poured by another version or with AdvancedPour. A disagreement is
   a lead, not a refutation, and an agreement supports only that polygon. The census compares with the
   saved pours only: no copy of a public document is repoured in Altium (open question 4, decided on
   2026-10-26), so the kit's authored samples are the only native reference.

10. **Evidence and graduation.** Every computed pour carries `INFERRED` and the `H-A-POUR-*` rows it used.
    It stays experimental until one K6 round on Altium Designer 26.5 passes every step of `pour` and `pour4`
    (row 29: one kit run on one version, the version named). The corpus census does not raise the level.
    The default is `computed` before that run (Decision 6), so every computed pour says that it is
    experimental, and the round's verdict is recorded in `docs/evidence/altium-pour.md`. The change is
    placed in v0.6, beside the maintainer's other Altium tests of v0.5 (open question 6).

11. **The Polygon Connect Style rules of a computed document** (open question 2, decided on 2026-10-26).
    Lowered from the zones, in Altium's Advanced form (one setting each for through-hole pads, SMD pads and
    vias), because a KiCad zone connects vias solidly and `thru_hole_only` relieves through-hole pads only:
    - For each net whose zones agree on `ZoneSettings.connection`, `thermal_gap`, `thermal_spoke_width` and
      `clearance` (compared through `effective()`), one rule scoped `InNet('<net>')`: `thermal` is Relief
      Connect for both pad kinds; `thru_hole_only` is relief for through-hole pads and Direct Connect for
      SMD pads; `solid` is Direct Connect for both; `none` is No Connect for both, with `clearance` as the
      air gap. A relief has 4 conductors at 90°, the conductor width `thermal_spoke_width` and the air gap
      `thermal_gap`. Vias are Direct Connect in every rule.
    - One `All` rule, last by priority, from the model's default `ZoneSettings()`.
    - A net whose zones disagree gets the rule of its zone of highest priority (then the lowest zone id),
      and each other zone of that net is one `altium.not-lowered` (`where` `zone/<id>`, reason "its
      connection settings differ from the net's rule"). A pad's own `zone_connection` is not lowered and is
      reported in the same way.
    - A read document that is rewritten keeps its own Polygon Connect Style records when they map exactly
      (task 2.1); otherwise the rules above are written, and each record that does not map is reported.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/backends/altium/pour.py` (new) | `PourResult`, `PolygonPour(index, zone_id, pieces, reason, hypotheses)`, `REASONS`, `pour_reading(reading, *, backend=None) -> PourResult`; the `geo` extra, imported lazily |
| `src/fenolite/backends/altium/connectstyle.py` (new) | `ConnectStyle`, `read_connect_styles(records) -> (styles, refusals)`, `connect_rule_fields(style, scope)` |
| `src/fenolite/backends/altium/pcbrecords.py` | `polygon_region(layer, ring, holes, *, net, polygon, shape_based=False)`; `polygon_fields(…, optimal_void_rotation=True)` |
| `src/fenolite/backends/altium/pcbdoc.py` | `write_pcbdoc(spec, *, pour="outline", pour_regions=True)`; the two passes, the self-check, `PcbDocResult.pour` |
| `src/fenolite/backends/altium/rulemap.py`, `read/rules.py` | the Polygon Connect Style record, written and read |
| `src/fenolite/backends/altium/lower.py`, `lens/altium.py`, `lens/altium_copper.py`, `convert/to_altium.py`, `panel/altium.py` | `pour=` and the codes `altium.zones-poured`, `altium.zone-unpoured` |
| `src/fenolite/cli/cmd_build.py`, `cmd_convert.py`, the panel command | `--altium-pour` |
| `src/fenolite/backends/altium/pourcompare.py` (new) | `compare_pours`, `PourComparison`, `PourDifference` |
| `src/fenolite/verify/kit/steps.py`, `results.py`, `script.py`; `cli/_kit.py` | the K6 steps, the checks `repoured`, `pour-match`, `pour-same`, `pour-kept`, the rebuild and save routines |
| `examples/kit/pour/design.py`, `examples/kit/pour4/design.py` (new) | the probes, with `kit_model` for what the DSL cannot declare |
| `docs/formats/altium/pcb-pour.md` (new), `docs/evidence/altium-pour.md` (new) | fact rows; census and kit results |

## Sources registered by this change

- S-0833: Polygon Pour Properties, `https://www.altium.com/documentation/altium-designer/pcb-polygon-pour-properties?version=21` (read 2026-10-26).
- S-0834: Polygon Pour, `https://www.altium.com/documentation/altium-designer/pcb-polygon-pour?version=21` (read 2026-10-26).
- S-0287 gains the reading of 2026-10-26 of its Plane page (Polygon Connect Style).
- The ids are proposed: task 1.1 takes the next two free ids and corrects this list.

## Hypotheses registered by this change

| id | statement | settled by |
|---|---|---|
| H-A-POUR-OPEN | Regions written with their polygon's index open as its pour: not listed as modified or unpoured, not repoured on open, kept by a save | K6 `computed/` steps |
| H-A-POUR-REGION | The written region form (prefix, keys, holes in both storages) is read by Altium as saved regions are | K6 `pour-kept`; census |
| H-A-POUR-CLEARANCE | A pour keeps the governing Clearance (I2) from objects of other nets | P1 |
| H-A-POUR-SCOPE | Polygon-specific rules use the scopes of S-0833; their record form | census |
| H-A-POUR-CONNECT | The keys and values of the Polygon Connect Style record (I5) | census; P2 |
| H-A-POUR-RELIEF | The shape of reliefs, direct joins and no-connect voids (I6, I7) | P2 |
| H-A-POUR-OVER | The meaning of `POUROVERSTYLE` 0, 1 and 2 (I8) | P10 |
| H-A-POUR-ORDER | Pour order and the clearance between polygons of one layer (I9) | P6 |
| H-A-POUR-NECK | Neck removal is an opening by the width (I10) | P3 |
| H-A-POUR-STEPS | The order of the steps (I11) | P3, P4 |
| H-A-POUR-ISLAND | Island removal by area and the unit of `AREATHRESHOLD` (I12) | P4; census |
| H-A-POUR-DEAD | Dead copper (I13) | P5 |
| H-A-POUR-ARC | The approximation of curves (I14) | P7 |
| H-A-POUR-VOIDROT | `OPTIMALVOIDROTATION=FALSE` turns the arrangement off and changes nothing else | P7 |
| H-A-POUR-KEEPOUT | Keep-outs in a pour (I16) | P8 |
| H-A-POUR-EDGE | A pour at the board edge (I17) | P9 |
| H-A-POUR-VIAPAD | Pads and vias in a pour, a via without a pad on a layer among them (I18) | P1, `pour4`; census |
| H-A-POUR-ENGINE | The K6 round ran with AdvancedPour off | K6 typed step |
| H-A-POUR-SCRIPT | The kit script's polygon rebuild gives what Repour All gives | K6 by hand |
| H-A-POUR-KIT | Fenolite's pour of `pour` and `pour4` meets M1 to M5 against Altium's repour | K6 |
| H-A-POUR-CORPUS | Fenolite's pour of the public polygons it evaluates meets M1 to M4 against their saved pours | census |
| H-A-POUR-KICAD | KiCad's importer reads the written regions as the zone's fills | oracle test |

## Evidence level per behaviour (before merge)

| behaviour | level before merge |
|---|---|
| fact rows of `pcb-pour.md` | `INFERRED`, each with its source |
| read-back by Fenolite's reader | exact within one unit (unit and RT-A2 tests) |
| KiCad's import of the written regions | `ORACLE-VERIFIED(kicad-cli)` (10.0.6) |
| refusals and the self-check | mechanical (unit tests on authored readings) |
| agreement with the public corpus | `CORPUS-VERIFIED` for the polygons that agree, else listed |
| agreement with Altium | `INFERRED` until the K6 round; then `ALTIUM-VERIFIED(kit; AD 26.5; <date>; <run>)` |

## Risks / Trade-offs

- **An Altium behaviour no probe shows.** The corpus census looks at real boards, a computed pour says
  that it is experimental, and Repour All in Altium still gives Altium's own copper.
- **Interacting polygons.** A refusal can unpour later polygons of its layer (Decision 5), which costs
  pours on boards with one bad input, rather than writing pours that Altium would not give.
- **Time.** Boolean work grows with the objects near each polygon. A box index (`geometry.index`) limits
  each polygon to its neighbours. Task 3.6 measures the largest public document; above 60 s the plan comes
  back to the maintainer.
- **Determinism.** Integer clipping, sorted inputs and sorted pieces give the same bytes for the same
  inputs, `--seed` and `--timestamp`.
- **A default that writes pours before the kit.** The maintainer's choice (open question 1). A document
  that opens poured can be fabricated without a repour, so every build says that the pour is experimental,
  the refusals and the self-check stand between an unknown input and the file, and `outline` stays one
  option away.

## Migration Plan

- The default becomes `computed`: a document with polygons gains regions, the Polygon Connect Style rules
  and `OPTIMALVOIDROTATION=FALSE`, and a conversion counts `zone-fill` as `changed` with the reason
  "computed by Fenolite". `--altium-pour outline` gives the files of earlier versions, byte for byte.
  `CHANGELOG.md` names the change of default.

## Budget (14 days)

| part | days |
|---|---|
| facts, censuses, register (tasks 1.x) | 2.5 |
| rules: connect style read and written, clearance resolution | 1.5 |
| engine (tasks 3.x) | 4.5 |
| written form, two passes, self-check, read-back, KiCad oracle | 1.5 |
| commands, conversion, rewrite | 1 |
| comparison and corpus census | 1.5 |
| kit samples, steps, script | 1 |
| docs and closing | 0.5 |

Cut order: (1) `pour4`; (2) the census's time measurement beyond the largest document. The per-net
Polygon Connect Style rules are the maintainer's decision and are not cut.
Never cut: the fact rows before the engine, the refusals, the comparison, the experimental label.

## Open questions

1. **How is the computed pour switched on before a K6 round passes?** Recommended: `--altium-pour`, with
   `outline` as the default until the round passes; the maintainer then decides the default, as c0155 did
   for bodies. Alternatives: `computed` by default now, marked experimental; or a constant gate that is
   off until the kit, as `CUTOUT_REGIONS` (c0168, open question 4), so that only the kit writes pours.
   Decided by the maintainer on 2026-10-26: `computed` by default now, marked experimental;
   `--altium-pour outline` gives today's files (Decision 6).
2. **Which Polygon Connect Style does a computed document hold?** Recommended: lowered from the zones:
   one rule per net whose zones agree, scoped `InNet`, from `ZoneSettings.connection`, `thermal_gap` and
   `thermal_spoke_width` (thermal is Relief Connect with 4 conductors at 90°), and one `All` rule from the
   model's default zone settings; a zone that disagrees with its net is reported as not lowered.
   Alternatives: one fixed `All` rule of Fenolite's values; or no rule, which leaves Altium's behaviour
   without a rule as one more hypothesis. Decided by the maintainer on 2026-10-26: as recommended, from the
   zones, per net (Decision 11).
3. **The comparison bounds.** Recommended: `d` = the polygon's `ARCRESOLUTION` (0.5 mil as written); M1
   at most `d` times the boundary length; M2 none wider than `2d`; M3 and M4 exact. Alternatives: half of
   that; or a fixed 1 mil band and 0.5 % of the area. Decided by the maintainer on 2026-10-26: as
   recommended.
4. **May the maintainer repour copies of the public corpus documents in Altium** (Part R, copies in ignored
   storage, only measurements committed, as the public conversion of c0166 and S-0616)? Recommended: yes.
   Decided by the maintainer on 2026-10-26: no. The census compares with the saved pours only, and Part R
   is not written (Decision 9).
5. **A rewrite of a read Altium document in `computed` mode.** Recommended: every polygon is poured again
   by Fenolite; keeping Altium's saved regions of a polygon whose inputs did not change is a follow-up that
   reuses the input list of this change. Alternative: keep them in this change. Decided by the maintainer
   on 2026-10-26: as recommended; every polygon is poured again.
6. **Milestone.** Recommended: v0.6, beside the maintainer's other Altium tests of v0.5. Alternative:
   unplaced until the K6 round. Decided by the maintainer on 2026-10-26: v0.6.
