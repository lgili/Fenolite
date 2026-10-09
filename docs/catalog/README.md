# Fenolite component catalog

Fenolite ships an offline, incrementally expanded catalog under the `Fenolite:` library ID. Its
entries are Fenolite-authored model definitions. The catalog includes generic passive,
semiconductor, protection, power/control IC and electromechanical symbols: **49 symbols** plus **100 distinct
footprint variants** for chip passives, discretes, ICs, connectors, LEDs, switches, leaded passives,
crystals and mechanical features. See the
[coverage matrix](coverage.md) for exact IDs, evidence and package limitations.

Use the definitions in Python with `fenolite.catalog.get_symbol()` and
`fenolite.catalog.get_footprint()`. `fenolite catalog list` searches the installed catalog and
`fenolite catalog show Fenolite:Resistor` prints one entry's metadata. A KiCad build uses a catalog
definition when the CLI design references its lib id. With the lower-level `build_design()` API,
pass `get_footprint(lib_id)` definitions in `authored_footprints` and symbol definitions in
`authored_symbols`. A project definition with the same exact lib id
overrides the catalog for that build only. Other component packs can be added without requiring a
CAD installation or network access.

A catalog footprint definition holds no text field. The KiCad build generates the two a KiCad
footprint needs (change c0077): `Reference` (`REF**` in the project library, the part's reference on the
board) on `F.SilkS`, 1 mm above the footprint's courtyard box, and `Value` (the footprint's name in the
library, the part's value on the board) on `F.Fab`, 1 mm below it. `Part.field("Reference", …)` and
`Part.field("Value", …)` move or hide them (`docs/dsl.md`, "Field placement"). So a board that names
only catalog ids passes `fenolite check`: `tests/_catalog_design.py` holds such a design, and
`tests/unit/cli/test_catalog_only.py` and `tests/kicad/build/test_catalog_only.py` build and check it.

The schematic symbols use aligned wire connection points, inward-facing stems and 0.254 mm body
strokes. Their outlines are Fenolite-authored interpretations of familiar electrical shapes.
Review sheets render the actual catalog geometry, including background fill and terminal roles.

Pin names follow one rule (change c0134): a symbol shows a pin name only where it can be read.

- A symbol whose drawing tells its pins apart hides its pin names and shows the pin numbers alone:
  the passives, diodes, transistors, thyristors, switches, the relay, the transformer, the
  optocoupler, the bridge rectifier and the two amplifiers. Where the drawing alone would not say
  which pin is which, strokes say it: a plus and a minus at the amplifier inputs; a plus, a minus
  and two waves inside the bridge; an arrowhead on the optocoupler's emitter leg.
- The four plain rectangles show their names and are sized for them: `Linear_Regulator`,
  `Offline_Power_Controller`, `Microcontroller` and `Power_Module`.
- A hidden name stays in the definition: `fenolite catalog show` and the role line of the review
  sheets list every name, and a design may still name a pin by it.

`tests/unit/catalog/test_pin_text_legibility.py` measures the rule on every catalog symbol at the text
size of KiCad (1.27 mm) and at an estimate of Altium's 10-point pin text: no shown pin text overlaps
another, a shown name has room inside the body, no shown name or number lies on a stroke of the body or
on the mark of a pin shape, and no shown name only repeats its pin's number. The Altium size is an
assumption, not a measurement in Altium.

## Symbol review

The [20-symbol expansion inventory](target-20-symbols.md) records exact IDs, conceptual pin roles and public references.

- [New symbols, sheet 1](previews/c0076-new-20-symbols-page1.svg): transistors, thyristors, protection and potentiometer.
- [New symbols, sheet 2](previews/c0076-new-20-symbols-page2.svg): thermistors, crystal, switches, relay, transformer and photodetectors.
- [Complete 49-symbol gallery](previews/c0076-all-49-symbols.svg).

Regenerate the complete gallery with:

```sh
uv run python tools/catalog/render_symbols.py docs/catalog/previews/c0076-all-49-symbols.svg --page-size 20
```

The new drawings retain zigzag resistance, show unactuated contact states and inward photodetector arrows. Generic B/C/E, G/D/S, coil and winding numbers are role identifiers. The four-terminal pushbutton has two internally common pairs; the two Würth footprints require different explicit maps. No generic symbol supplies a default footprint. Offline build tests preserve these maps and pad nets for KiCad 9/10 targets.


## Footprint review

The [100-slot inventory](target-100-footprints.md) is fully resolved. It is a curated selection
informed by a public-board corpus; it is not a measured worldwide popularity ranking.

Review the native geometry in five sheets of 20 footprints each:

- [Sheet 1](previews/c0076-current-gallery-page1.svg)
- [Sheet 2](previews/c0076-current-gallery-page2.svg)
- [Sheet 3](previews/c0076-current-gallery-page3.svg)
- [Sheet 4](previews/c0076-current-gallery-page4.svg)
- [Sheet 5](previews/c0076-current-gallery-page5.svg)

Blue is the fabrication outline, green the courtyard, orange copper and gray explicit paste
windows. White drill apertures distinguish round holes and plated slots. The sheets show the
component-side view with pad numbers; asymmetric connector origins retain their electrical
coordinates while the renderer centers the courtyard. These are schematic review drawings of
the footprint geometry, not 3D mechanical models.

Regenerate the full sheet and its five pages with:

```sh
uv run python tools/catalog/render_footprints.py docs/catalog/previews/c0076-current-gallery.svg --page-size 20
```

The final audit checks 100 unique IDs against the inventory, registered public sources, distinct
pad/body/paste geometry (ignoring labels and IDs), positive pad clearance and the complete courtyard
bounds. Every definition is serialized and read back with its pad kind, layers, drill, slot,
attributes and drawing geometry preserved. A hermetic API build assigns all 100 definitions to
authored terminal-only test symbols, explicitly maps their terminals, and reads the resulting
board back for KiCad 9 and 10 targets. This proves catalog use and pad/net preservation; the
audit fixture does not represent a functional circuit or a routed board.

Reproduce the focused audit and local branch gate with:

```sh
uv run pytest tests/unit/catalog tests/unit/cli/test_catalog.py tests/unit/lens/test_build_catalog_inventory.py tests/unit/lens/test_build_catalog_symbols.py -q
make check-fast
openspec validate --specs --strict
```

The catalog is not a substitute for checking a selected manufacturer's part. Generic symbols do not
promise a device pinout. Copper lands without an explicit source recommendation are labelled
`INFERRED`; even sourced example lands are starting patterns that require checking against the exact
component datasheet and assembly process before fabrication. Catalog entries do not qualify a part
or board for electrical, thermal or safety requirements.

## Public evidence

- `S-0314` identifies the common passive component families and schematic-symbol categories.
- `S-0315` supplies 0402, 0603, 0805 and 1206 resistor body dimensions. It does not specify the
  footprints' copper land geometry.
- New family and package references are mapped per entry in [the catalog evidence map](sources.md).

Source details are in [the evidence register](../evidence/sources.md).
