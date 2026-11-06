# c0421 design: equivalent pairing noise

## Measurement (2026-11-05, `origin/dev` `5ab9d6452`)

`convert --to kicad --allow-lossy` of the public Altium rows, then `equivalent <PcbDoc> <kicad_pro> --level 7`
(scratch only, no corpus data in the repository):

| row | differences | main kinds |
|---|---|---|
| `altium-third-party-pcbdoc-02` | 612 | graphic-missing 548, layer-missing 28, zone-field 10, stackup-missing 6, rule-missing 3 |
| `altium-third-party-pcbdoc-04` | 395 | graphic-missing 303, layer-missing 26, field-pose 19, zone-field 18, rule-missing 7 |
| `altium-third-party-pcbdoc-05` | 281 | graphic-missing 233, layer-missing 23, rule-missing 8, hole-missing 4, ref-ambiguous 1 |
| `altium-third-party-pcbdoc-06` | 1096 | graphic-missing 1027, layer-missing 29, text-missing 27, rule-missing 4, keepout-missing 2 |
| `altium-third-party-pcbdoc-07` | 380 | graphic-missing 295, layer-missing 27, zone-field 12, text-missing 12, zone-missing 8 |
| `-01`, `-03`, `-08` | refused | FEN-3004 from the native project rule context of the KiCad side |

Causes, read from the designs of both sides:

- The KiCad side is read by `api.sides.read_path`, which resolves a project to its board: the net classes of
  `<stem>.kicad_pro` and the rules of `<stem>.kicad_dru` are not in the design, and `read_board` keeps
  `fp_line`/`fp_arc`/`fp_poly`/`fp_text` as opaque slots (`fpitems`), so every footprint graphic of the
  Altium side is `graphic-missing`. Between two KiCad sides the native context (`_native_rules`, c0352)
  compares classes and floors instead.
- `_native_rules.augment` computes the context of every side before it checks that both are KiCad, so a
  KiCad side whose numbered-pad binding is ambiguous refuses an Altium comparison.
- `rules._rules` keys by name: Altium `RoutingVias` is two rules (`via_diameter`, `via_drill`). The KiCad
  lowering names a rule `fenolite_<priority>_<slug>` (`lowering.lowered_names`, `rulemap.slug`), and a
  `.kicad_dru` read back numbers priorities by file order.
- The Altium stack-up holds copper and dielectric layers only; KiCad's also lists `F.SilkS`, `F.Paste`,
  `F.Mask` and their back copies.
- The conversion writes Altium `Mech.<k>` as KiCad `User.<n>` with the user name `Mech.<k>`; the KiCad
  reader keeps that name in the layer's `kicad` bag (`user_name`). KiCad also declares its fixed technical
  layers (`F.CrtYd`, `Margin`, `Cmts.User`, …) whether used or not.
- Altium footprint drawings of the Keep-Out layer are graphics of `Altium.KeepOut`; `convert` makes each a
  rule area on every copper layer: a filled shape its outline, a stroke the band of its width
  (`geometry.bands`, c0407, c0411).
- Altium polygons store a connection and clearance that the Polygon Connect Style and clearance rules
  override; `convert` writes the governing values (`convert.altium_zones`, c0409 B5/B6).
- A free Altium hole becomes a footprint `Fenolite_Holes:NPTH_<d>mm`: board-only, no reference, one
  `np_thru_hole` pad at its origin (c0420 N2).

## Recount after the change (2026-11-05, same scratch conversions, level 7, exact tolerance)

| row | before | after | what is left |
|---|---|---|---|
| `-01` | refused | 226 | footprint-name 176, field-pose 24, pin-missing 12, pad-missing 12 (free pads that `convert` wraps in `FREE_fp_<id>` footprints), layer-missing 1 (`F.Fab`, used by those footprints' Value), rule-missing 1 |
| `-02` | 612 | 13 | footprint-name 6 (`_2` names of footprint variants), text-missing 5 (footprint `.Designator` texts `convert` does not write), route-unjudged 1, layer-missing 1 (`Altium.DrillDrawing`), rule-missing 1 |
| `-03` | refused | 50 | text-missing 46 (footprint free texts), rule-missing 3, rule-field 1 |
| `-04` | 395 | 21 | footprint-name 12 (name sanitising), field-pose 4, text-missing 3, layer-missing 1, rule-missing 1 |
| `-05` | 281 | 1 | rule-missing 1 (`RoutingVias` `via_drill`, which `convert` does not write) |
| `-06` | 1096 | 26 | text-missing 25 (footprint `.Designator` texts), rule-missing 1 |
| `-07` | 380 | 25 | text-missing 12, footprint-name 8, field-pose 4, layer-missing 1 |
| `-08` | refused | 2262 | graphic-missing 1000 and text-missing 298 on `Altium.DrillDrawing` (not written), text-missing 554 (footprint texts), footprint-name 400, field-pose 8, layer-missing 2 |

Every class left is something the conversion writes differently or not at all (footprint names, free-pad
footprints, footprint free texts, the drill drawing layer, a via drill rule): reported, as `equivalent` must.

## Decisions

### D1. Cross-backend side completion lives in the API, not in the package

`checks.equivalence` stays pure and names no backend. A new `api/_cross_backend.py` prepares the two read
designs when their backends differ, before `compare_designs`:

- a KiCad side with a traced project: `pro.apply_project` (classes and membership, as the importer does) and
  `dru.read_rules` of `<stem>.kicad_dru` into `Design.rules`; `fpitems.with_footprint_items` projects
  footprint graphics and texts;
- an Altium side: `altium_to_kicad.zone_outlines` gives a zone whose polygon has an arc vertex (the import
  leaves its outline empty) the flattened outline of the polygon record, read again from the file given for
  the side; a zone no record outlines stays as read (a writer drops it, a comparison must not hide it).
  `convert.altium_zones.connect_zones` and `zone_clearances` give each zone the connect style and clearance
  its rules govern (the stored values are defaults the rules override; the effective value is what the board
  means). Pad `zone_connection` overrides come with it. The ledger notes are discarded;
- the names of the keep-out layers of each side (`Altium.KeepOut` for Altium) go to `compare_designs`.

Between two sides of one backend nothing changes, so `verify-source` and the fidelity ratchet keep their
counts; the triangle (`against`) compares KiCad's own import under its profile and stays as read.
`_native_rules.augment` computes contexts only when both sides are KiCad.

### D2. Rules pair by identity, then by written name and content

A rule's identity is `(name, kind)` with a repeat number for a further rule of the same pair, so two rules of
one name and two kinds no longer collapse. A rule of one side named `fenolite_<p>_<slug>` (optionally
followed by `_<k>` for a repeat or `_<layer slug>`, as `lowered_names` writes) and unmatched by identity
pairs with an unmatched rule of the other side of the same kind, priority `p` and `slug(name) == <slug>`;
when several qualify, the one whose fields other than name and priority are all equal wins, else the first in
name order. A pair made this way compares every field except `name` and `priority`: the written priority
equals the source priority by construction, and file-order numbering is not a priority. A written name
whose priority, slug or kind matches nothing stays `rule-missing` on both sides.

### D2b. Declared format limits

A `rule-missing` whose rule its side marks kept (any ext bag pair `kept_record` = `1`: a record the other
format cannot hold, kept by the conversion for a later write, change c0424) moves to the level's `excluded`
list under the rule id `declared-limit` with its reason. It stays in the output and fails nothing, as an
exclusion rule's match does; no kind is added. An unmarked rule stays `rule-missing`, and a kept rule the other
side holds is compared field by field.

### D3. The `across` flag: what one backend states and the other leaves out

`compare_designs(..., across=True)`, which `equivalent` passes for sides of two backends without the
triangle, turns on the rules below. Between sides of one backend (`across=False`, the default, also for
`verify-source`, the fidelity ratchet and the triangle) each is still a difference, so the c0281 expectation
that a declared `Eco1.User` on one side is `layer-missing` holds. Each rule leaves out only a statement one
side never makes; the value both sides state is compared:

- stack-up: a layer of kind silkscreen, solder paste or solder mask is compared only when both stack-ups hold
  one of that kind (Altium's stack-up has copper and dielectric only); copper and dielectric always;
- net classes: a class on one side only that holds no net (KiCad always declares `Default`); a class field
  one side leaves unset (an Altium class carries no widths; its rules do);
- layers: a non-copper layer on one side only that no item of that side uses, a pad counting on its copper
  layers only (KiCad lists mask and paste layers of a pad, Altium derives them); a mechanical and a user
  layer are one kind; only the copper layers' order is compared (the rest is each backend's table order);
- stack-up names: compared without letter case (`Dielectric 1` against `dielectric 1`);
- fields: a hidden footprint field on one side only (KiCad declares every footprint's reference and value),
  and a field on one side only that the other side's component holds as a parameter of that name (KiCad
  places every parameter as a footprint field, Altium keeps it on the component); a field whose own
  component holds another value for that parameter is still reported.

### D4. Layer aliases and keep-out layers

A layer of side `a` without a same-named layer on side `b` pairs with a layer of side `b` whose user name (the
`user_name` of any ext bag of the layer) is its name, and the other way round, one pair per name; the pair is
compared as one layer (kind, order). The aliases map side `b`'s names to side `a`'s for level 7 (graphics,
texts, fields, zones, rule areas). The summary counts them (`layers_aliased`). A keep-out layer passed for a
side and held by it only is not `layer-missing`: level 7 compares its drawings with rule areas (D5).

### D5. Keep-out drawings against rule areas

Given the keep-out layers of a side, a graphic on such a layer becomes, for level 7 only, the rule area(s)
`convert` would write: a filled polygon or rectangle (or one of width 0) its outline; a line, arc, circle or
stroked outline the band of its width per stroke (`geometry.bands`, the documented band of c0407). They
match the other side's rule areas by layers (every copper layer of the board) and normalised ring, as rule
areas match today. The graphics leave the graphic set. A keep-out drawing whose band or outline differs stays
missing on both sides.

### D6. Edge.Cuts as rings

Level 7 chains the `Edge.Cuts` lines and arcs of the board on each side into closed rings (end to end, exact
points) and normalises each ring with its arc mids; polygons and rectangles on `Edge.Cuts` are rings already.
Rings match as a multiset by their normalised edges; a matched ring compares nothing more, and items of an
open chain stay items. So a closed outline drawn as segments equals the same outline drawn as one polygon; an
arc approximated by segments on one side still differs.

### D7. Mounting holes as board-only footprints

Before level 1, a footprint whose component has an empty reference, whose attributes hold `board_only`, and
which holds exactly one `np_thru_hole` pad becomes, when a board hole of the other side lies at the pad's
board position with the same drill (and slot length and axis), a board hole of its own side: the footprint
and its component leave the comparison. An unpaired footprint stays (levels 1 and 3 report it).

### D8. Field poses

Fields compare their layer under the alias of D4, and across backends a hidden field on one side only is not
a difference (D3). On the public rows the `field-pose` left are the `Reference` and `Value` of the footprints
`convert` makes for free pads (`FREE_fp_<id>`, a visible pair on `F.SilkS` and `F.Fab`) against Altium free
pads, which have no footprint: a conversion representation, not a pairing of one item, left as reported.

### D9. Level 5 single items

The strict rule pairs an arc left unmatched with a track left unmatched of the other side when both lie on
one span, the ends agree within the length tolerance and the arc's mid lies within the length tolerance of
the chord (integers: `cross² ≤ tol² · chord²`); the pair is compared by the track rule and counted with the
tracks. Under the exact tolerance only an arc of three collinear points pairs, which the importer already
takes as the track it draws (c0375). The private run's arc (sub-micron, its chord the KiCad track) pairs when `equivalent` is given a length tolerance above its sagitta; `equivalent` keeps the exact default.

The via counted in another piece and the zero-length stub are one item (generic description from the private
run): both sides hold the same vias at the same positions and the same sub-micron tracks; side `b` holds one
piece without a pad of length 0, one via split off the net's main route. Stitching vias touch no track and
join the route through the pour, so the split via is one that side `b`'s fill (KiCad's refill)
does not reach while side `a`'s pour does. That is a difference of the filled copper, not of pairing: it stays
reported (task 4.2 records it, no rule).
