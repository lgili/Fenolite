# Design: c0416

## Evidence

The authored library `slot_library()` (`tests/_altium_slotcases.py`) holds one footprint with six slot pads.
Each pad is 4 mm round, and every slot hole is 1 mm by 2.15 mm:

| pad | `Pad.drill` | `hole_length` | `hole_rotation` | `Pad.rotation` | KiCad 10.0.6 `fp upgrade` | axis |
|---|---|---|---|---|---|---|
| 1 | 1 | 2.15 | 0° | 0° | `(drill oval 2.15 1)` | 0° |
| 2 | 2.15 | 1 | 0° | 0° | `(drill oval 1 2.15)` | 90° |
| 3 | 1 | 2.15 | 30° | 0° | `(drill oval 0.762)`: lost | — |
| 4 | 2.15 | 1 | 30° | 0° | `(drill oval 0.762)`: lost | — |
| 5 | 1 | 2.15 | 90° | 45° | pad at 45°, `(drill oval 1 2.15)` | 135° |
| 6 | 2.15 | 1 | 0° | 30° | pad at 30°, `(drill oval 1 2.15)` | 120° |

Measured 2026-11-05.

- KiCad writes the oval as the record's slot length along the pad's x axis and the hole size across it.
- When the hole size is the larger number, the long side of the oval lies across the record's axis. That is
  pad 2 and pad 6.
- A hole rotation that is not a multiple of 90° has no oval form, and KiCad's import loses it (pads 3 and 4).
  Fenolite's KiCad writer already refuses such a slot.

## Decisions

1. **One form for both sides.** `slot_form` reads the hole by its extents, as KiCad's oval does:
   - the width is the shorter number and the length the longer;
   - the axis lies along the longer number;
   - it is in the footprint's frame (pad rotation plus hole rotation), so a turned pad with a turned hole
     compares equal;
   - the axis is modulo a half turn, because a slot is the same turned by 180°.
2. **A separate kind.** `pad-drill` keeps its meaning (the widths, c0407). `pad-slot` names length and axis,
   so an exclusion profile can waive one without the other.
3. **Equal numbers are a round hole.** KiCad reads `(drill oval d d)` as a round drill. A slot whose two
   numbers are equal therefore has no `slot_form`, and against a round hole of that size it gives no
   difference.
4. **The axis is compared only when the slot is longer than wide.** With `slot_form` this is always true,
   because equal numbers give `None`.
