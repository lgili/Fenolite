# c0439: polygon cut-outs stay cut-outs in the Altium writers

## Why

A board round-tripped Altium → KiCad → Altium (and through `import --to python`, build and Altium) came back
with hundreds of free keep-out regions on the Keep-Out layer where the source held polygon cut-outs, and
Altium's design rule check then reported most of its clearance violations between those regions and the
board's tracks, pads and vias. No board data is used here: the cause is reproduced on the public document of
S-0175 (corpus row `altium-third-party-pcbdoc-06`) and on an authored board.

The import reads an Altium polygon cut-out (a region of `KIND=1`) as a rule area that forbids poured copper
alone, on its copper layer or on every copper layer (c0407). The writers wrote every rule area as keep-out
regions: the keep-out flag, `KIND=0` and the restrictions value 4, on the Keep-Out layer when the area covers
every copper layer. A keep-out object is checked by Altium's clearance rules against every item whatever its
restrictions, so each former cut-out became a clearance obstacle. The public row `-06` has no keep-out
primitive and thirteen polygon cut-outs; its round trip wrote thirteen free keep-out regions.

## What

- A rule area that restricts poured copper and nothing else is written as a polygon cut-out: a region of
  `KIND=1` without the keep-out flag or restriction keys, on Multi-Layer (`V7_LAYER=MULTILAYER`) when it lies
  on every copper layer and else once per copper layer it names, as the saved documents of the corpus hold
  them. A footprint's such area is a cut-out region of its component.
- Every other rule area is written as before, with its restrictions and its owner.
- `pcb-records.md` records the census of cut-outs; `pcbrecords.V7_LAYERS` gains `MULTILAYER`.

## Taken in from c0438

cac-altium-code measured the same cause on the public row `-01` (S-1981) and found a second fault there:
`convert --to altium` never gave copper graphics the net that the KiCad reader keeps in their slot, so every
netted copper shape (45 regions of `-01`) was written with no net. This change takes its fix
(`fpitems.with_graphic_nets` in `convert.to_altium.write`) and its level 5 kind `copper-no-net`, with which
`equivalent` tells a cut-out turned copper, or a shape that lost its net, from the source. c0438 is dropped.

## Not in this change

- `equivalent` still reads a cut-out and a pour-only keep-out region as the same rule area; the record
  form is pinned by the writer tests. `copper-no-net` catches a cut-out written as copper.
- Component regions of the Keep-Out layer without the keep-out flag (two in row `-06`) are read as
  footprint rule areas and written back as keep-out regions; whether that is their meaning is not settled
  here and is reported to the coordinator.
- What Altium Designer's DRC reports on the rewritten document is for the kit (asked of altium-rounds-2).

## Impact

- Code: `backends/altium/pcbrecords.py` (`region_record(polygon_cutout=)`, `V7_LAYERS`),
  `backends/altium/pcblib.py` (`is_pour_cutout`, `keepout_records`), `backends/altium/pcbdoc.py`
  (`free_records`).
- Spec: `altium-pcb-writer` ("Board graphics and keep-out records"; added "Rule areas of poured copper
  alone").
- Docs: `docs/formats/altium/pcb-records.md`.
- Sources S-1980 (census of cut-outs) and S-1981 (round trip of row `-01`), first numbered S-1980 and
  S-1981 in c0438.
- Code also: `convert/to_altium.py`, `checks/equivalence/routing.py`, `checks/equivalence/model.py`,
  `cli/data/explain.toml`; schemas refrozen for the new kind.
- Specs also: `design-conversion` ("Copper shapes keep their net"), `design-equivalence` ("Copper without a
  net").
