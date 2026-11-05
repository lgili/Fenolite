# c0421: equivalent pairing noise between an Altium source and its KiCad conversion

## Why

`fenolite equivalent` comparing an Altium board with its KiCad conversion reports thousands of differences
that are the same design held in another representation, so the few real differences drown. A private
rerun (no board data or counts recorded here) reported, among others, renamed rules as `rule-missing`,
net classes, stack-up entries and layers as missing, keep-out tracks against their rule areas, field poses,
`Edge.Cuts` outlines, zone settings, mounting holes, and single `route-vias`, `route-stub` and
`arc-missing`/`track-missing` items.

The public Altium rows of the corpus manifest reproduce most classes (2026-11-05, `origin/dev`
`5ab9d6452`, `convert --to kicad` then `equivalent <PcbDoc> <kicad_pro> --level 7`): rows `-02`, `-04`,
`-05`, `-06`, `-07` give 281 to 1096 differences each, and rows `-01`, `-03`, `-08` refuse with FEN-3004
before comparing. The causes, measured on those rows:

- the KiCad side of a cross-backend comparison is read without its project: no net classes, no custom
  rules (`.kicad_dru`), and footprint graphics and texts left as opaque slots;
- the native project rule context of a KiCad side runs even when the other side is not KiCad, and its
  binding check refuses the whole comparison;
- level 6 keys rules by name only (two rules of one name and two kinds collapse), and the conversion
  writes a rule as `fenolite_<priority>_<slug>`;
- level 6 compares solder mask, paste and silkscreen stack-up layers that one side does not state, and
  layer names without the user name KiCad keeps for a mechanical layer (`User.<n>` named `Mech.<k>`);
  level 7 then misses every item on such a layer;
- a drawing of the Altium Keep-Out layer is a graphic on one side and a rule area on the other;
- an Altium polygon's stored connection and clearance are not the values its rules give it;
- a mounting hole becomes a board-only footprint with one NPTH pad.

## What

Pairing rules, each with an authored negative case; no tolerance is widened and no real difference is
hidden:

- cross-backend side completion: a KiCad side compared with a non-KiCad side gets its project's net classes,
  its `.kicad_dru` rules and its projected footprint items; an Altium side's zones take the effective connect
  style and clearance of its rules; the native project rule context runs only between two KiCad sides;
- level 6: rules keyed by name, kind and repeat; a written name `fenolite_<p>_<slug>` pairs with the rule of
  priority `p` and that slug and kind, the priority then judged by the name; stack-up kinds one side does not
  state are not compared; a layer pairs with a layer of the other side whose user name is its name, and a
  non-copper layer that one side declares and nothing uses is not a difference;
- level 7: items on aliased layers compare under the paired name; keep-out layer drawings pair with rule areas
  of the same area or band; `Edge.Cuts` drawings compare as closed rings; a board hole pairs with a
  board-only one-pad NPTH footprint at the same place and drill;
- level 5: the remaining single items, as `design.md` decides.

## Impact

- `src/fenolite/checks/equivalence/` (`rules.py`, `shapes.py`, `levels.py`, `routing.py`, `strict.py`),
  `src/fenolite/api/equivalence.py`, `src/fenolite/api/_native_rules.py`, a new
  `src/fenolite/api/_cross_backend.py`.
- `docs/equivalence.md`; agent guide line if a public name changes (none planned).
- No new difference kind; the result schema is unchanged unless a summary key is added (then regenerated).
- Same-backend comparisons (`verify-source`, the fidelity ratchet) keep their results: every new rule needs two
  sides in different representations, and the side completion runs only across backends.
