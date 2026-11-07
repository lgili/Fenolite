## MODIFIED Requirements

### Requirement: Board graphics and keep-out records
Board graphics on the non-copper layers of the board layer map SHALL be written as track, arc and region records without a net. Board graphics on a signal layer of the written stack SHALL be written as copper records on that layer with the net index of their net (change c0412). Keep-outs SHALL be written as region records with the keep-out flag and the restriction set of the model, on the Keep-Out layer when they name every copper layer of the board, else one per copper layer, except a rule area of poured copper alone, which is a polygon cut-out ("Rule areas of poured copper alone").
- A filled rectangle or polygon on a signal layer MUST be one region record with `KIND=0`, its layer's id and its net's index in the common prefix (`0xFFFF` for a shape without a net), in `Regions6` and in `ShapeBasedRegions6`. A drawn line, arc, circle, rectangle or polygon outline on a signal layer MUST be tracks and arcs of its width with that net. No fill record is written: `docs/formats/altium` records no field after offset 37 of a fill, whose saved lengths are 46 and 50.
- A shape on an internal plane, a filled circle, a shape that `pcbdoc.graphic_problem` refuses, and a shape whose net no net record holds MUST give `altium.not-lowered` with the kind `copper-shape` and `where` `graphic/<id>`; `copper-shape` stays a loss kind, which `FEN-7001` refuses without `--allow-lossy`.
- A keep-out record MUST hold its restrictions value in two keys, `KEEPOUTRESTRICTIONS` (the key saved documents hold) and after it `KEEPOUTRESTRIC` (the key KiCad's importer reads; not a key Altium writes), both with the same value (the maintainer's decision of 2026-10-06), so that KiCad imports the keep-out with exactly the restrictions written. That Altium accepts the pair stays `INFERRED` until step X11 of Part X.
- A restriction that the record cannot carry (`no_footprints`) MUST give `altium.not-lowered` with `where` `keepout/<id>` naming the restriction; the keep-out is written with the others, and not at all when it has no other.
- A graphic that has no record (a layer outside the map, a drawn shape without a positive width, a filled circle, a shape without an extent) MUST give `altium.not-lowered` with `where` `graphic/<id>`. A graphic on `Edge.Cuts` is the outline and counts as written.
- The board outline MUST stay as written before this change.

#### Scenario: Keep-out with two restrictions
- **GIVEN** a keep-out that forbids tracks and vias in a rectangle on all copper layers
- **WHEN** the document is written and read back
- **THEN** one keep-out region with those two restrictions is read, its value 3 in `KEEPOUTRESTRICTIONS` and in `KEEPOUTRESTRIC`

#### Scenario: Copper polygon with a net
- **GIVEN** a KiCad board with a filled `gr_poly` on `F.Cu` on the net `VIN`, a filled `gr_rect` on `B.Cu` without a net and a drawn `gr_line` on `F.Cu` on `GND`
- **WHEN** it is converted with `convert --to altium` without `--allow-lossy`
- **THEN** the write succeeds, the document holds one region on the top layer with the index of `VIN`, one region on the bottom layer with no net and one track on the top layer with the index of `GND`, the report has no `copper-shape` loss, and KiCad's import of the document holds the shapes on their layers and nets

#### Scenario: Copper on a plane stays a loss
- **GIVEN** a filled polygon on an internal plane layer
- **WHEN** the board is converted without `--allow-lossy`
- **THEN** `FEN-7001` names `copper-shape` for that graphic

## ADDED Requirements

### Requirement: Rule areas of poured copper alone
A rule area that restricts poured copper and nothing else (no tracks, vias, pads or footprints), on the board or in a footprint, SHALL be written as a polygon cut-out: a region record with `KIND=1` and without the keep-out flag or restriction keys, on Multi-Layer (`V7_LAYER=MULTILAYER`) when it lies on every copper layer, else one per copper layer it names, owned by its component when it belongs to a footprint. This is the form of the cut-outs of documents saved by Altium (`pcb-records.md`, "Regions and keep-outs") and the form the import reads as such a rule area, so a document read and written again keeps each cut-out a cut-out instead of turning it into a keep-out that Altium's clearance rules check against every track, pad and via.

#### Scenario: Cut-outs stay cut-outs
- **GIVEN** a two-layer board with pour-only rule areas on both copper layers, on `F.Cu` and on `B.Cu`, a rule area that forbids tracks on both layers, and a pour-only rule area on `*.Cu` in a footprint
- **WHEN** the PCB document is written and read back
- **THEN** it holds free cut-out regions on Multi-Layer, Top and Bottom, one cut-out region of the component on Multi-Layer and one keep-out region (on the Keep-Out layer, for the track rule area), and the import reads the pour-only rule areas again with their layers and the footprint's area in its footprint

#### Scenario: The authored cut-out board
- **GIVEN** the authored board `polygon_cutouts.kicad_pcb`
- **WHEN** it is converted to Altium
- **THEN** its pour-only areas give two `KIND=1` regions (one on Top for the area on `F.Cu`, one on Multi-Layer for the area on both copper layers) with no keep-out flag and no net, its area that forbids tracks too is a keep-out region of restrictions 6, and the reading holds the two pour-only rule areas on their layers
