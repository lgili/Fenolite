## ADDED Requirements

### Requirement: Pour mode of a conversion to Altium

A conversion to Altium SHALL pour its polygons in the mode it is given, `computed` when none is given, and
SHALL NOT write them unpoured unless the mode `outline` is given. Without the `geo` extra, `computed`, the
default included, SHALL refuse the conversion: `convert_project` raises `BackendUnavailable`, and
`fenolite convert` exits 6 with `FEN-6001` (`where` `--altium-pour`), plans no file, and gives a hint that
names the `geo` extra and `--altium-pour outline`.

#### Scenario: The geo extra is missing

- **GIVEN** a KiCad board with polygons and no `geo` extra
- **WHEN** it is converted with `fenolite convert --to altium` and no `--altium-pour`
- **THEN** the command exits 6 with `FEN-6001`, plans nothing, and its hint names `fenolite[geo]` and
  `--altium-pour outline`
- **AND** with `--altium-pour outline` the same conversion exits 0 with no `altium.pour-unavailable` warning
