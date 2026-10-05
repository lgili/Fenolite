# Fenolite component catalog

Fenolite ships an offline, incrementally expanded catalog under the `Fenolite:` library ID. Its
entries are Fenolite-authored model definitions. The catalog includes generic passive,
semiconductor, protection, power/control IC and electromechanical symbols, plus a sourced starting
set of standard chip, small-outline, diode, leaded-IC and through-hole header footprints. See the
[coverage matrix](coverage.md) for exact IDs, evidence and package limitations.

Use the definitions in Python with `fenolite.catalog.get_symbol()` and
`fenolite.catalog.get_footprint()`. `fenolite catalog list` searches the installed catalog and
`fenolite catalog show Fenolite:Resistor` prints one entry's metadata. A KiCad build uses a catalog
definition when the design references its lib id. A project definition with the same exact lib id
overrides the catalog for that build only. Other component packs can be added without requiring a
CAD installation or network access.

The schematic symbols use aligned wire connection points, inward-facing stems and 0.254 mm body
strokes. Their outlines are Fenolite-authored interpretations of familiar electrical shapes.
Passive pin names are hidden where the body or polarity mark conveys the role; functional IC pins
retain names. A review sheet covering all 26 symbols is generated with the catalog definitions.

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
