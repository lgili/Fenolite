## ADDED Requirements

### Requirement: Level 2 names every pad of a pin
On a side whose source is `circuit`, level 2 SHALL take one element `REF-<pad>` per pad of each pin of the components it compares, with the pads of `Component.pads_of`, as `assignment_compare.model_netlist` gives them ("Assignment comparison names every pad of a pin" of `verification-loop`). The reference and pad of each element in a located difference MUST be those of the pad, not of the pin.
- A side whose source is `board` is unchanged: its elements are its numbered pads.
- Level 3 MUST NOT read `pin_pad_map`: it compares the footprints and pads of two boards.
- `checks/equivalence/levels.py` MUST NOT build a mapping of one pad per pin from `pin_pad_map`.

#### Scenario: Circuit against board
- **GIVEN** side `a` without a board, whose `U1` has `pin_pad_map == (("3", "3"), ("3", "EP"))` and pin `3` on `GND`, and side `b` with a board whose `U1` has the pads `3` and `EP` on `GND`
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_levels.py -k several_pads` compares them at level 2
- **THEN** there is no `pin-missing` and no `net` difference; and with the pad `EP` of side `b` on another net there is one `net` difference whose `where` names `U1` and `EP`
