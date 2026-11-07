# c0416: level 3 compares slot length and axis

## Why

c0407 made level 3 compare the width of a pad's hole (`norm.drill_width`). A slot also has a length and an
axis, and level 3 does not compare them:

- a slot 2.15 mm long and one 3 mm long of the same width compare equal;
- so do a horizontal slot and a vertical one.

The two numbers of a slot may come in either order. An Altium record may hold a slot length below its hole
size, and KiCad reads the hole as an oval whose longer side lies across the record's axis. So the length and
the axis must be compared in one form for both sides.

## What

- **`norm.slot_form(pad)`** gives the width, length and axis of a slot hole, or `None` for any other hole:
  - the width is the shorter of `Pad.drill` and `Padstack.hole_length`, and the length is the longer;
  - the axis is in the footprint's frame: `Pad.rotation + Padstack.hole_rotation`, plus a quarter turn when
    `Pad.drill` is the longer of the two numbers;
  - the axis is taken modulo a half turn;
  - a slot whose two numbers are equal is a round hole, so `slot_form` gives `None` for it.
- **New level-3 difference `pad-slot`** (field `slot`):
  - it is reported when only one pad has a slot hole, when the lengths differ beyond the length tolerance, or
    when the axes differ beyond the angle tolerance modulo a half turn;
  - `a` and `b` are `<length>@<axis>` in nanometres and microdegrees, or empty for a pad without a slot;
  - `pad-drill` keeps comparing widths (c0407).
- **Public surface:** the kinds table, the issue code `equiv.pad-slot`, the explain entry, `docs/equivalence.md`,
  `docs/cli-contract.md` and the generated CLI surface. Adding a kind is additive in contract v0.
- **Oracle proof.** KiCad 10.0.6's `fp upgrade` of an authored PcbLib with six slot pads gives, for every slot
  KiCad can encode, the same `slot_form` as Fenolite's import of that library. The six slots are a normal
  slot, the swapped form, both at a hole rotation of 30°, and turned pads. The fact goes to
  `pcb-records.md` as `ORACLE-VERIFIED(kicad-cli)`.

## Impact

- Code: `checks/equivalence/norm.py`, `levels.py` and `model.py`; `convert/report.py` (`AT_REF`);
  `cli/data/explain.toml`.
- Tests:
  - the level-3 unit tests;
  - the kinds table of `test_codes`, which gains one row by intent;
  - a KiCad oracle test in `tests/kicad/altium/test_slots_import.py`.
- Docs: `docs/equivalence.md`, `docs/cli-contract.md`, `docs/cli-surface.json` (generated) and
  `pcb-records.md`.

## Not here

| item | owner |
|---|---|
| Running the Altium kit case for a slot length below the hole size (Part H, defined in task 3.1) | altium-rounds-2 (task 3.2) |
| Whether the Altium adapter should swap the two numbers on import | after that kit case |
