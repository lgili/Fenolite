## MODIFIED Requirements

### Requirement: Footprint instances and pads
`import_board` SHALL create one `FootprintInstance` per record of `Components6` from the record and from the primitives that carry its index.
- `position` MUST be the converted `x`, `y`; `side` `bottom` when `layer` is `BOTTOM`, else `top`; `locked` from the record; `lib_ref` `<stem of source_footprint_library>:<pattern>`, or the pattern alone when the library text is empty.
- `rotation` MUST be the model angle `θ` for which `Transform.placement(position, θ, mirror=(side == "bottom"))`, followed by the Y flip, is the placement the writer of c0035 writes as `ROTATION` (its inverse): reading a document that Fenolite wrote gives the rotation it was written from.
- **Pad frame.** `Pad.position` MUST be the point `p` for which `Transform.placement(position, rotation).apply(p)`, without a mirror, is the pad's absolute position, and `Pad.rotation` the pad's angle minus the instance's, as "Board entities read from file backends" requires. A bottom footprint therefore holds mirrored pad coordinates, as a bottom footprint read from a KiCad board does.
- `Pad.number` is the pad name. `Pad.kind` MUST be `thru_hole` for a hole above 0 that is plated, `np_thru_hole` for one that is not, and `smd` otherwise. `Pad.drill` is the hole size, `None` without a hole. `Pad.shape` MUST be `circle` for shape 1 with equal sizes, `oval` for shape 1 with unequal sizes, `rect` for 2, `roundrect` for shape 1 with alternate shape 9 (the percentage in the pair `corner_percent`, and `Pad.corner_ratio` 5 000 ppm per percent), and `custom` for 3 (octagonal) and any other value, with the value in the bag.
- `Pad.layers` MUST be real layers: every copper layer of the chain for a pad on Multi-Layer, else the one copper layer of the pad. Mask and paste layers are not listed; an expansion and its mode go to `paste` and `mask` as `<mode>,<expansion in units>` when the mode is not 1 (the expansion follows a rule), so a pad with rule expansions has no such pair.
- `Pad.net_id` MUST be the net of the pad's net index, `None` without one.
- `attributes` MUST be `("through_hole",)` when a pad has a hole, `("smd",)` when the footprint has pads and none has a hole, and `()` without pads.
- Tracks, arcs, texts, fills and regions that carry a component index MUST NOT become board objects: they become the graphics, the fields and the texts of their footprint ("Graphics, fields and texts of a component"). Only the primitives of a component whose record gives no readable position are still counted as `footprint-graphics` in `altium.import.unmapped`. A pad without a component index MUST become a footprint of its own with `attributes == ("board_only",)`, the reference `""` and `lib_ref == ""`.
- A component index that names no record is reported by the reader; the adapter MUST treat such a primitive as free.

#### Scenario: Placements of the blink sample
- **GIVEN** `tests/data/altium/blink/blink.PcbDoc`, written from `examples/blink_2layer/design.py`
- **WHEN** it is imported and compared with the board that the KiCad build of the same script writes, read by `KicadBackend`
- **THEN** the three footprints have that board's `side` and `rotation`, and the footprint names of the script; their positions differ from that board's by one common translation within 2 nm per axis; and each pad's `number`, `shape`, `kind`, `net` name and footprint-local `position` equals that board's within 2 nm

#### Scenario: Bottom footprint keeps mirrored pads
- **WHEN** `Transform.placement(D1.position, D1.rotation).apply(pad.position)` is computed for the two pads of `D1`, which is on the bottom side
- **THEN** each result equals the pad's absolute position in the document, converted by "Units and frame", within 1 nm

#### Scenario: Free pad
- **GIVEN** a document with one pad whose component index is `0xFFFF`
- **WHEN** it is imported
- **THEN** the board holds a footprint with `attributes == ("board_only",)` and that one pad at local position (0, 0)

#### Scenario: Silkscreen of the blink sample
- **WHEN** `tests/data/altium/blink/blink.PcbDoc` is imported
- **THEN** its three footprints hold 27 graphics in all (24 lines and 3 arcs), each footprint holds the fields `Reference` and `Value`, and `altium.import.unmapped` names no `footprint-graphics`

#### Scenario: Corner ratio of the blink sample
- **WHEN** the same document is imported
- **THEN** each of its 34 pads of shape `roundrect` has `corner_ratio` equal to 5 000 times the value of its pair `corner_percent`

## ADDED Requirements

### Requirement: Graphics, fields and texts of a component
`import_board` SHALL give each `FootprintInstance` the primitives that carry its component's index and are no pad: tracks, arcs, fills and regions as `graphics`, the designator and the comment as the fields `Reference` and `Value`, and every other text as `texts` (`design-model`, "Graphics and texts of a footprint instance").
- A track MUST become a `line`; an arc an `arc`, or a `circle` when its sweep is a full turn; a fill a filled `rect`, or a filled `polygon` when it is turned by an angle that is no multiple of 90 degrees; a region a filled `polygon`. The mapping is that of a library footprint (`adapter.copper.definition_graphics`), in the order tracks, arcs, fills, regions and, within each, record order.
- Points and angles MUST be taken into the footprint frame with the inverse of `Transform.placement(position, rotation)`, the transform of the pads of "Footprint instances and pads", so a bottom footprint holds mirrored coordinates and its layers are those the primitives lie on.
- `layer` is the neutral name of the record's layer ("Layers and stack-up"). A graphic on a copper layer MUST keep its net name in the pair `net`.
- The first text with `is_designator` MUST give the field `Reference` and the first with `is_comment` the field `Value`: `position`, `layer`, `size` (the height for both), `thickness`, `rotation` relative to the footprint, and `visible` from the component record's `name_on` and `comment_on` (true when the key is missing). The string stays in `Component.ref` and `Component.value`. A further designator or comment text of the same component, and any other text, MUST become a `Text` of `texts` with its string as stored.
- An arc with a radius that is not positive and a region with fewer than three vertices MUST be reported and counted as `bad-geometry`; the holes of a region are counted as `region-holes`, as for a free region.
- A mapped record MUST count under `mapped` of its kind in the census, so "Unmapped records are counted" holds: the mapped and the unmapped counts of a kind add up to the reader's record count.
- Ids are content ids in the section `fp:<native id of the footprint>`, over the fields in the footprint frame ("Identifiers and provenance"); each entity carries the provenance of its record. Inexact lengths and angles keep their pairs ("Extension bags").
- The facts MUST be rows of `docs/formats/altium/import.md` with their sources and the hypothesis `H-A-IMP-FPGFX` before the code is written.

#### Scenario: A track of a bottom component
- **GIVEN** an authored document with one component on the bottom side, turned by 90 degrees, that owns one track on the bottom overlay
- **WHEN** it is imported
- **THEN** the footprint holds one `line` on `B.SilkS`, and `Transform.placement(position, rotation)` applied to its two points gives the converted ends of the record within 1 nm

#### Scenario: Designator and comment
- **GIVEN** an authored document whose component has `NAMEON` true, `COMMENTON` false, a designator text and a comment text
- **WHEN** it is imported
- **THEN** the footprint has the fields `Reference` (visible) and `Value` (not visible) at the texts' places, `texts` is empty, and `Component.ref` and `Component.value` hold the two strings

#### Scenario: The census is conserved on the corpus
- **WHEN** `uv run pytest tests/corpus/test_altium_import.py -k footprint_items` imports every PCB document with the use `rta`
- **THEN** for each of `tracks`, `arcs`, `fills`, `regions` and `texts` the mapped and unmapped counts add up to the reader's count, the category `footprint-graphics` is 0, and the test prints the number of graphics, fields and texts per document for the evidence page
