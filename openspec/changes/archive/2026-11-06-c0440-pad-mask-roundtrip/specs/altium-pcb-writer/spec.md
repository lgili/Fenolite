## MODIFIED Requirements

### Requirement: Footprint pad records
`pcbrecords.pad_record(...)` SHALL write one pad as the six subrecords of record type 2 (S-0150, S-0160, S-0161, S-0143).
- Subrecord 1 MUST hold the pad number as a short string, its length exactly 1 + the text's length. Subrecords 2 to 4 MUST hold the bytes `00`, the short string `|&|0` and `00` (S-0150).
- Subrecord 5 MUST be 114 bytes: the prefix; x, y; top, middle and bottom size equal to the pad size; hole size (the drill, 0 for SMD); top, middle and bottom shape; rotation; plated (1 only for `thru_hole`); pad mode 0; the values S-0150 writes at offsets 63 to 85; for a pad without its own margins the mask expansions 0, paste mode 0 and solder mode 1, and for a pad with `Pad.mask_margin` solder mode 2 with the margin as the solder-mask expansion, with `Pad.paste_margin` paste mode 2 with the margin as the paste expansion (change c0440; a connector pad keeps modes 0); the int32 at 106 and the bytes 110 to 113 zero.
- Shapes: `circle` and `oval` MUST be shape 1 (round; an oval has unequal sizes), `rect` shape 2, `roundrect` shape 1 with subrecord 6.
- Subrecord 6 MUST be empty, except for a `roundrect` pad: 596 bytes, every inner size equal to the pad size, every inner shape 1, hole shape 0, no slot, zero offsets, the rounded-rectangle flag 1, every alternate shape 9 and every corner percentage `round(200 · ratio)` clamped to 0 … 100, where `ratio` is the pad's corner ratio (`H-A-PCB-PAD`).
- The pad rotation MUST be the pad angle in degrees; KiCad's and Altium's positive angles both turn counter-clockwise on screen (`H-G-ROT-DIR`).

#### Scenario: Roundrect pad
- **WHEN** a `roundrect` pad `1` of 0.9 × 0.95 mm at (−0.8, 0) mm with ratio 0.25 is written
- **THEN** the test decoder reads subrecord 5 of 114 bytes with shape 1, sizes 354331 × 374016, x −314961 and y 0, and subrecord 6 of 596 bytes with alternate shape 9 and percentage 50

#### Scenario: Through-hole pads
- **WHEN** the mini LED footprint's pads are written
- **THEN** both are on layer 74 with hole size 354331 and plated 1, pad `1` has shape 2 and pad `2` shape 1, and both have an empty subrecord 6

#### Scenario: A pad's own margin is a manual expansion
- **GIVEN** the KiCad board converted from `tests/data/altium/blink`, whose pads are given a `solder_mask_margin` of 0.05 mm, the first of 0
- **WHEN** `uv run pytest tests/unit/convert/test_pad_mask_c0440.py` converts it to Altium and back to KiCad
- **THEN** each written pad holds solder mode 2 with the expansion 19685 or 0, and the KiCad board read again holds the same margins
