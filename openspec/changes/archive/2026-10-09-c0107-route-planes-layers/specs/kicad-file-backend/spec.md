## ADDED Requirements

### Requirement: Plane layers of a board
`backends.kicad.layers.plane_layers(design) -> tuple[str, ...]` SHALL return, in stack order, the copper layers whose KiCad row type, kept in `Layer.ext["kicad"]` under `type`, is `power`, and `layers.with_plane_types(layers, planes) -> tuple[Layer, ...]` SHALL return `layers` with the row type `power` on each copper layer named in `planes` and every other layer unchanged (`H-K-LAYER-POWER`).
- `read_board` MUST keep the row type of every copper layer, and `write_board` MUST write it back unchanged, for targets 9 and 10.
- `with_plane_types` MUST raise `ValueError` for a name in `planes` that is not a copper layer of `layers`.
- A copper layer without a `type` in its ext bag is not a plane layer.

#### Scenario: Plane layers read from a board
- **GIVEN** the bench board of `tests/routing/_planebench.py`, written for target 10 with `(4 "In1.Cu" power)` and `(6 "In2.Cu" signal)`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_layers.py -k plane` reads it and calls `plane_layers`
- **THEN** the result is `("In1.Cu",)`, and `write_board` of the read design holds `(4 "In1.Cu" power)` and `(6 "In2.Cu" signal)`

#### Scenario: Types set on created layers
- **WHEN** `with_plane_types(created_layers(4), ("In2.Cu",))` is called, and then with `("Edge.Cuts",)`
- **THEN** the first gives `In2.Cu` the type `power` and leaves the other 21 layers equal to those of `created_layers(4)`, and the second raises `ValueError` naming `Edge.Cuts`

### Requirement: Track layer rules in rules files
`read_rules` SHALL lift a rule whose constraint is `disallow track`, whose layer clause names one KiCad layer for which `layers.is_canonical` is true, and whose condition lies in the grammar of `no_tracks` (`rules-model`, "Track layer rules"), into a model rule of kind `no_tracks` with that one layer. This extends "Custom rules files are read and written".
- Any other rule with a `disallow` constraint (other item types, several items, a layer clause `inner` or `outer`, no layer clause) MUST stay opaque with `rules.kept-opaque` naming the reason.
- A rule set lowered by `lower_rules` and read back MUST give one `no_tracks` rule per lowered layer, with the same selector and severity.

#### Scenario: Lift and opaque forms
- **GIVEN** a rules file holding `(rule "a" (layer "In2.Cu") (condition "A.NetClass == 'SIG'") (constraint disallow track))`, `(rule "b" (layer inner) (condition "A.NetClass == 'SIG'") (constraint disallow track))` and `(rule "c" (layer "F.Cu") (constraint disallow via))`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_dru.py -k no_tracks` reads it
- **THEN** the rule set holds one `no_tracks` rule `a` with `selector_a` `netclass SIG` and `layers == ("In2.Cu",)`, and `b` and `c` stay opaque, each with one `rules.kept-opaque`
