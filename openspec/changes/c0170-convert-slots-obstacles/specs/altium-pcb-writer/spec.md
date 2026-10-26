## ADDED Requirements

### Requirement: Slotted drills of footprint pads
A footprint pad whose padstack holds only a slotted hole (`hole_shape` `slot`, `hole_length`, `hole_rotation`, no per-layer shapes and no offset) SHALL be written in the library and the document with hole shape 2, hole size the drill, slot length `hole_length` and slot rotation `hole_rotation` relative to the pad. A pad with an offset drill or per-layer shapes stays refused.

#### Scenario: An oval mounting slot
- **GIVEN** a KiCad footprint with an `np_thru_hole` oval pad of drill 1 × 3 mm turned 30°
- **WHEN** `uv run pytest tests/unit/backends/altium/test_slot_drills.py` writes the library and reads it back
- **THEN** the pad is read with hole shape 2, hole size 1 mm, slot length 3 mm and the pad's rotation, and the footprint is not refused
