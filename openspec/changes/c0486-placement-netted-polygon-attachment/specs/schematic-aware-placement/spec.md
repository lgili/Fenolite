## ADDED Requirements

### Requirement: Netted copper graphics in the attachment check
The optimizer's attachment check SHALL read a board graphic on a copper layer that has a net as copper of
that net (change c0486).
- Before the check, the optimizer MUST give each copper graphic the net its backend names
  (`model.graphicnets.with_graphic_nets`).
- A selected part whose pad touches a netted copper graphic MUST be fixed as `attached_copper`.
- A netted copper graphic that touches no pad of a selected part MUST NOT make that part
  `attachment_unchecked`.
- A copper graphic with no net, or one whose shape cannot be built, MUST keep every selected part
  `attachment_unchecked`, as before.

#### Scenario: A GND polygon away from the part
- **GIVEN** an authored KiCad board with a `gr_poly` on `F.Cu` with `(net "GND")` in one corner, and a
  resistor R1 whose pads lie 5 mm away from it
- **WHEN** `fenolite place --strategy optimize` selects R1
- **THEN** R1 is movable, and no part is `attachment_unchecked`

#### Scenario: A GND polygon under a pad
- **GIVEN** the same board with R1 moved so that its pad 2 lies on the polygon
- **WHEN** R1 is selected
- **THEN** R1 is fixed with the reason `attached_copper`

#### Scenario: A copper polygon with no net
- **GIVEN** the same board with the polygon's net removed
- **WHEN** R1 is selected
- **THEN** R1 is fixed with the reason `attachment_unchecked`
