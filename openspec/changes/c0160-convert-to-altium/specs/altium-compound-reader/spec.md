## ADDED Requirements

### Requirement: DIFAT sectors in a written compound file
`cfb.write_compound` SHALL write a file whose FAT needs more than 109 sectors: the FAT sector numbers past the 109th go into DIFAT sectors of 127 numbers each plus the number of the next DIFAT sector (ENDOFCHAIN in the last), the header names the first DIFAT sector and their count, and the FAT marks each DIFAT sector `DIFSECT` (`docs/formats/altium/compound-file.md`, S-0145). `CompoundTooLarge` MUST be raised only for a file that a version-3 compound file cannot hold. The compound reader MUST follow the DIFAT chain.

#### Scenario: Large file written and read
- **GIVEN** a storage tree whose streams need 181 FAT sectors
- **WHEN** `uv run pytest tests/unit/backends/altium/test_cfb_difat.py` writes it and reads it back
- **THEN** every stream is read back byte for byte, the header names one DIFAT sector, and a tree that needs 109 FAT sectors or fewer is written with no DIFAT sector and the bytes it had before

#### Scenario: KiCad imports a large document
- **GIVEN** `kicad-cli` 10.0.6 and the KiCad 10.0.6 demo board `vme-wren`
- **WHEN** `uv run pytest tests/kicad/convert/test_triangle_large.py -k difat -rA` converts it to Altium and imports the PCB document with `kicad-cli pcb import`
- **THEN** the import succeeds and equals the source at level 4 under the profile `kicad-import`, and the probe `convert-difat` records `equal`
