## ADDED Requirements

### Requirement: Frame-bound Altium storages are not carried

A conversion of an Altium design to KiCad SHALL NOT carry the `BoardRegions` storage of the source PCB
document, whose records hold the source's geometry in its frame and name its layer stack by id, nor its
`CustomMaskShapes` storage, whose content no public source shows. It SHALL count each lost under
`altium-storage` when it holds data, and a conversion back to Altium SHALL NOT write a
`Fenolite.Altium.BoardRegions` or `Fenolite.Altium.CustomMaskShapes` board property that a KiCad board
holds.

#### Scenario: The board region stays behind

- **GIVEN** an Altium document whose `BoardRegions` storage holds a record
- **WHEN** it is converted to KiCad and the KiCad board back to Altium
- **THEN** the KiCad board holds no `Fenolite.Altium.BoardRegions` property, the report counts
  `BoardRegions` lost under `altium-storage`, and the written document does not hold the source's record

#### Scenario: A custom mask shape stays behind

- **GIVEN** an Altium document whose `CustomMaskShapes` storage holds a record
- **WHEN** it is converted to KiCad and the KiCad board back to Altium
- **THEN** the report counts `CustomMaskShapes` lost under `altium-storage` with a reason that says its
  content is not known, and the written document does not hold the source's record
