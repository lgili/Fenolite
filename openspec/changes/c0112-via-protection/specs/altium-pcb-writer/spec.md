## ADDED Requirements

### Requirement: Via tenting flags
`pcbrecords.via_record` SHALL take the keywords `tented_top=False` and `tented_bottom=False` and write them as bits 5 and 6 of the first flags byte of the via's subrecord, the bits that `read.pcbprims` reads as `ViaRecord.tented_top` and `ViaRecord.tented_bottom` (`docs/formats/altium/pcb-copper.md`, "Flags of a via"; S-0160, S-0172, S-0174, S-0175, S-0176; `H-A-PCB-CU-VIATENT`). This requirement refines the flags that "Via records" states; every other byte of the record is as that requirement states it.
- The first flags byte MUST be `0x0C`, plus `0x20` when `tented_top` is true, plus `0x40` when `tented_bottom` is true: `0C`, `2C`, `4C` or `6C`. The second flags byte stays `00`. With both keywords false the record MUST equal, byte for byte, the record written before this change.
- `pcbdoc.write_pcbdoc` MUST set the two keywords of each via of `PcbDocSpec.vias` from the tenting that the build resolved for it (`altium-build`, "Via protection in an Altium build"): the via's own `tenting_front` and `tenting_back`, else the board default's, else false. It MUST write nothing for `covering_front`, `covering_back`, `plugging_front`, `plugging_back`, `capping` and `filling`, and MUST NOT raise for any value of them.
- The solder-mask expansions of the record (at 54 and at 242) MUST stay the values of "Via records": no fact recorded here ties them to the tenting flags.
- A via written with tenting flags MUST read back, through `read.pcbprims`, with `tented_top` and `tented_bottom` equal to the keywords.
- `docs/formats/altium/pcb-copper.md` MUST hold a fact row for the written flags with its sources, the label `INFERRED` and `H-A-PCB-CU-VIATENT`, MUST take "tented vias" out of its list of what is not written, and MUST say in "Vias" that the flags are `0C 00` only for a via that is not tented.

#### Scenario: Flags of the four cases
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pcb_vias.py -k tenting` calls `via_record(393701, 393701, 236220, 118110, net=2)` with no tenting keyword, with `tented_top=True`, with `tented_bottom=True` and with both
- **THEN** bytes 0 to 4 of the subrecord are `4A 0C 00 02 00`, `4A 2C 00 02 00`, `4A 4C 00 02 00` and `4A 6C 00 02 00`, the four records are equal in every other byte, and the first equals the record of "Via bytes"

#### Scenario: Written flags read back
- **GIVEN** a PCB document written with four through vias, one per case
- **WHEN** it is read with the PCB reader
- **THEN** the four via records hold (`tented_top`, `tented_bottom`) = (false, false), (true, false), (false, true) and (true, true)
