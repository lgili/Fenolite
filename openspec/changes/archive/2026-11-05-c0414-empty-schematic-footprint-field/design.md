# c0414 design: empty schematic Footprint fields

## Measurement (2026-11-05, KiCad 10.0.6)

`kicad-demo-9-0-9-1-pcb-01` after c0413: the only difference is `8:render-pixels=1` on
`sheet:custom_pads_test.kicad_sch`, the strip x 132.461–133.223 mm, y 94.488–106.172 mm. The source R2
`(property "Footprint" "" (at 132.842 100.33 90) (effects (font (size 0.762 0.762))))` is visible and
empty; the board footprint of R2 is `custom_pads_test:DO-214AB`; the rebuilt field holds that id.

## Decisions

### A flag, not a text

The source field is either empty, an alias of the same footprint (kept as the part's `footprint=`), or a
contradiction (refused by c0342). The only case to carry is "empty", so the drawing holds a boolean on
the unit. A free text would be the generic override c0326 refuses, and could hide a contradiction.

### Who sets it

`extract(..., footprints={ref: footprint})` flags a unit whose source `Footprint` field is empty when
any reference the unit stands for builds with a non-empty footprint. Without `footprints` (the
`verify-source`, `sync`, equivalence and drawn-side readers) nothing is flagged, so their values do not
change. The import passes the footprint text each `Part(..., footprint=…)` gets. Parts without a
footprint already write an empty field and are never flagged.

### Who reads it

Only the KiCad drawn writer (`lower_drawn`): a flagged unit's instance gets `footprint=""` and an empty
`Footprint` property; the field keeps its drawn pose and font. The part, the board, the netlist export
and the BOM still take the part's footprint. The Altium drawn writer ignores the flag.

### Compatibility

`fenolite.drawn-schematic.v0` gains the optional key `empty_footprint` (boolean, written only when
true). Older files read unchanged; the canonical writer emits it after `symbol` and before the fields.
