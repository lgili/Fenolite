## ADDED Requirements

### Requirement: Altium board settings through KiCad

A conversion of an Altium design to KiCad SHALL carry, as the board property
`Fenolite.Altium.Board6.Settings`, every key of the source's `Board6` record that the record holds once
and that the writer does not own (`docboard.OWNED_KEY`), with its value and its place, and the names of
mechanical layers 1 to 16. A key whose text a record line cannot hold SHALL NOT be carried.

The conversion back SHALL write the source's value of each carried key, and SHALL write a carried key that
the writer does not write after the key it followed in the source. A mechanical layer SHALL take the
source's name when the KiCad layer that reaches it is named `Mech.<n>`, or when no written primitive lies
on it.

#### Scenario: A metric document stays metric

- **GIVEN** an authored Altium document with `DISPLAYUNIT=0`, `GR0_DISPLAYUNIT=0` and one clearance rule of
  0.025 mm
- **WHEN** it is imported, built and converted back to Altium (flow A)
- **THEN** the written `Board6` holds `DISPLAYUNIT=0` and `GR0_DISPLAYUNIT=0`, and the rule's gap is
  0.025 mm

#### Scenario: Altium's mechanical names come back

- **GIVEN** an authored Altium document whose mechanical layers carry Altium's default names (`Board`,
  `Top Assembly`, …, `Top Courtyard`), with a line on Mechanical 15
- **WHEN** it goes through flow A
- **THEN** each of the sixteen `LAYER<57+k>NAME` keys of the written `Board6` is the source's, and the line
  lies on Mechanical 15

#### Scenario: A black solder mask stays black

- **GIVEN** an authored Altium document whose 3D view settings give both solder masks colour 0 (black)
- **WHEN** it goes through flow A
- **THEN** the written `3DCONFIGURATION` holds `CFG3D.TOPSOLDERMASKCOLOR=0` and
  `CFG3D.BOTSOLDERMASKCOLOR=0`, not the writer's green

#### Scenario: Settings the writer does not write come back in place

- **GIVEN** an authored Altium document whose `Board6` holds `HASHKEY0`/`HASHVALUE0` and
  `SITUSSTRATEGYNAME`
- **WHEN** it is converted to KiCad and back
- **THEN** the written `Board6` holds them with their values, on the line and after the key they followed
