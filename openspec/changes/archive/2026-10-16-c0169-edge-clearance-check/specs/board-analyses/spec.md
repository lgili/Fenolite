## ADDED Requirements

### Requirement: Slots in creepage
A slot SHALL give the same creepage as the same stadium drawn with `cutout(shape.stadium(…))`, and overlapping slots the same as their merged ring drawn as one cut-out, on every path the creepage analysis reports. The groove width SHALL bridge a slot narrower than it, as any cut-out.

#### Scenario: Slot and ring are equal
- **GIVEN** two copies of the shared fixture with two pads of different nets on either side of slot `S1`, one with `S1` and one with `cutout(shape.stadium(…))` of the same size
- **WHEN** `uv run pytest tests/unit/analysis/test_creepage_slots.py` runs the creepage analysis on both
- **THEN** the two reported creepages are equal to the nanometre, and with `--groove-width` above 2 mm both bridge the slot
