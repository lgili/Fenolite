## ADDED Requirements

### Requirement: Altium storages through KiCad

A conversion of an Altium design to KiCad SHALL write each carried storage of the source PCB document
(`UnionNames`, `EmbeddedFonts6` and the component classes of `Classes6`; `BoardRegions` and
`CustomMaskShapes` are not carried, change c0459)
as a board property `Fenolite.Altium.<storage>` whose value is the base64 text of the zlib-compressed bytes
of its `Header` and `Data` streams. It SHALL count each of `PrimitiveGuids`, the `T*Violation` storages and
`WaivedViolations` that holds a record as lost under `altium-storage`. It SHALL give each fill it converts a
KiCad uuid tagged as an Altium fill, and each rule area that a keep-out track or arc of copper gave the
marker of its stroke as its name.

#### Scenario: A union name survives the round trip

- **GIVEN** an Altium document whose `UnionNames` storage holds records
- **WHEN** it is converted to KiCad and the KiCad board back to Altium
- **THEN** the written document's `UnionNames` storage holds the source's bytes

#### Scenario: A keep-out stroke names its rule areas

- **GIVEN** an Altium document with a keep-out line of the top layer that forbids pads alone (r = 24)
- **WHEN** it is converted to KiCad
- **THEN** the rule area of the line's band is named `Altium.KeepOut/flag24/line/…` with the line's points
  and width

### Requirement: Component fills keep their marker when placed from Python

An imported Altium component fill SHALL keep a fill marker when its vendored footprint is placed by
the Python build. Its marked KiCad uuid SHALL be deterministic and unique per placement and child.
The return conversion SHALL write eligible marked graphics as component fill records.

#### Scenario: Component fills survive import, build and conversion

- **GIVEN** an Altium document with an ordinary component overlay fill and an unnetted copper fill
- **WHEN** it is imported to Python, built and converted back to Altium
- **THEN** both fills belong to their original component and retain their layers and absent nets
