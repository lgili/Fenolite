## ADDED Requirements

### Requirement: Nets outside the routing job in design files
`backends.specctra.dsn.write_dsn` SHALL take `others: Literal["declared", "netless"] = "declared"`, which says how the nets that are not in `selected` are written. With `"declared"` the file MUST be the one that "Design files are written from the model" states, byte for byte. That requirement, as c0107 leaves it, already writes one family of nets as pins on no net in every mode: a net of one pad whose name starts with `unconnected-(`. The mode `"netless"` does the same for every net outside the job: a net that has pads, is not in `selected`, is not the net of a `plane` the file holds, and whose class clearance is not larger than `defaults.clearance`:
- MUST NOT appear in the network section, neither as a `net` nor as a member of a `class`; a class left without members MUST NOT be written;
- MUST keep its pins in their images, as netless pins;
- MUST have its tracks, arcs and vias written as wiring of type `protect` without a `net`, as copper on a net without pads already is;
- MUST NOT be a key of `DsnResult.names.nets` or `DsnResult.names.net_ids`.

A net outside the job whose class clearance is larger than `defaults.clearance` MUST stay declared with its class, as with `"declared"`: Freerouting 2.4.1 keeps only the default rule from copper and pins without a net, and KiCad asks for the larger clearance of the two classes (`H-G-DSN-NETLESS`, outcome `dsn-netless` = `present`, measured on 2026-10-08).

The via list, the default rule, the components and every other part of the file MUST be as with `"declared"`. A value other than the two MUST raise `ValueError`.

#### Scenario: Unselected net left out
- **GIVEN** an authored board with nets `A` and `B`, two pads each, one track on `B`, and `selected=("A",)`
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn.py -k netless` calls `write_dsn(..., others="netless")`
- **THEN** the network section holds `(net A …)` and no `(net B …)`, the images still hold the pins of `B`, the track of `B` is a protected wire without a `net`, and `names.nets` maps `A` only

#### Scenario: A pin on no net in both modes
- **GIVEN** a board with the selected net `A` and the net `unconnected-(R1-Pad1)` on one pad
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn.py -k "netless and unconnected"` calls `write_dsn` with `others="declared"` and with `others="netless"`
- **THEN** neither text declares `unconnected-(R1-Pad1)`, both keep the pin of `R1` in its image, and the two texts are equal

#### Scenario: Declared mode unchanged
- **WHEN** `write_dsn` runs on the two-pad board of c0016 with `others="declared"` and without the argument
- **THEN** both texts equal `tests/data/specctra/two_pads.dsn`

#### Scenario: A class emptied by the mode
- **GIVEN** a class `PWR` without a clearance of its own, whose only members `GND` and `VCC` are not selected
- **WHEN** `write_dsn` runs with `others="netless"`
- **THEN** no `(class PWR …)` is written, and the class of the selected nets is written as with `"declared"`

#### Scenario: A wider class stays declared
- **GIVEN** a net `VCC` in a class whose clearance is 0.3 mm, a default rule of 0.2 mm, and `selected=("A",)`
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn.py -k "netless and wider"` calls `write_dsn(..., others="netless")`
- **THEN** the network section declares `A` and `VCC`, the class of `VCC` is written with its clearance, and a net of a class whose clearance equals the default rule is left out
