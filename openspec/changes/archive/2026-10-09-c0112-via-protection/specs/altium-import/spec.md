## ADDED Requirements

### Requirement: Via tenting of imported vias
`import_board` SHALL map the two tenting flags of each via record to the via's protection: `Via.protection` MUST be `ViaProtection(tenting_front=<tented_top>, tenting_back=<tented_bottom>)`, both as booleans, and the six other fields MUST be `None`. This requirement adds one field to the `Via` that "Tracks, arcs and vias" maps; everything else there holds.
- Both tenting fields MUST be explicit for every imported via, `False` for a clear flag: an Altium via carries its own flags and follows no board default, and a `None` would be read by the KiCad backend as "tented" (`kicad-file-backend`, "Via protection defaults on boards").
- `Board.via_protection` of an imported board MUST be `None`: the PCB document holds no default that the reader reads.
- Covering, plugging, capping and filling MUST stay `None`: no record read here states them.
- The mapping has the label of the two fields it reads, `INFERRED` (`ViaRecord.tented_top`, `ViaRecord.tented_bottom`; `docs/formats/altium/pcb-read.md`), and `adapter` evidence MUST name `H-A-PCB-CU-VIATENT` beside the hypotheses of the via mapping. A clear flag is read as "not tented"; what the solder-mask expansion of the via does to its mask opening is not read.
- The equivalence levels and RT-A2 do not compare `Via.protection`; `docs/altium.md` ("Round trips") MUST list the field among those left out, with the reason: a `None` has no Altium form, so a written and re-read model differs from the original where a side is stated nowhere.

#### Scenario: Flags become tenting
- **GIVEN** a PCB document with four vias whose flags are `0C`, `2C`, `4C` and `6C`
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_copper.py -k tenting` imports it
- **THEN** the four vias have (`tenting_front`, `tenting_back`) = (`False`, `False`), (`True`, `False`), (`False`, `True`) and (`True`, `True`), every other field of their `protection` is `None`, and `board.via_protection` is `None`

#### Scenario: Stated tenting survives the round trip
- **GIVEN** a design whose two vias have `protect(tenting="front")` and `protect(tenting=False)`, built for the Altium target
- **WHEN** the written PCB document is imported
- **THEN** each imported via has the tenting of the via it was written from

#### Scenario: An imported board written for KiCad
- **GIVEN** the imported board of "Flags become tenting"
- **WHEN** it is written with `write_board` for target 10
- **THEN** the four vias hold `(tenting (front no) (back no))`, `(tenting (front yes) (back no))`, `(tenting (front no) (back yes))` and `(tenting (front yes) (back yes))`, and no via follows KiCad's board default
