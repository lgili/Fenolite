## ADDED Requirements

### Requirement: Rule kinds of change c0424 onto the neutral model
`read.rules.RULE_KIND_MAP` SHALL map the following Altium kinds onto model kinds that the KiCad target writes. Their keys come from the public rule file and PCB documents of the corpus (S-0297, S-1838).
- `SilkToSilkClearance` MUST map onto `silk_clearance`, with `min` taken from `SILKTOSILKCLEARANCE`.
- `ComponentClearance` MUST map onto `courtyard_clearance`, with `min` taken from `GAP`. `VERTICALGAP`, `COLLISIONCHECKMODE` and `SHOWDISTANCES` MUST be allowed and unused.
- `DiffPairsRouting` MUST map onto `diff_pair_gap`, with `min`, `opt` and `max` taken from `MINLIMIT`, `MOSTFREQGAP` and `MAXLIMIT`, and onto `diff_pair_uncoupled`, with `max` taken from `MAXUNCOUPLEDLENGTH`.
  - The per-layer width keys (`<LAYER>_MINWIDTH`, `_MAXWIDTH`, `_PREFWIDTH`) and `IMPEDANCEPROFILEDRIVEN`, `IMPEDANCEPROFILEID` and `IMPEDANCEPROFILEVALUE` MUST be allowed and unused.
  - Its selector MUST name the pairs: `diff_pair *` for the scope `All`, otherwise `and` of `diff_pair *` and the scope's selector.
- `RoutingLayers` MUST map, when the caller gives the copper layers, onto one `no_tracks` rule. Its layers MUST be every copper layer of the board whose key `<NAME>_V5` is `FALSE`. The name of a layer's key MUST be `TOP LAYER`, `MID LAYER <n>` or `BOTTOM LAYER` by its Altium layer id.
  - A record that disallows no layer of the board MUST map onto no rule. It MUST count as mapped.
  - Without copper layers the record MUST be refused with the reason `no-layer`.
- `HoleToHoleClearance` MUST map with `ALLOWSTACKEDMICROVIAS` `FALSE` or `TRUE`.

#### Scenario: One record of each new kind
- **GIVEN** authored records of Silk To Silk Clearance, Component Clearance, Differential Pairs Routing, Routing Layers that disallow `MID LAYER 1` on a four-layer board, and Hole To Hole Clearance with stacked micro vias allowed
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_rule_kinds_c0424.py` maps them with the board's copper layers
- **THEN** the rules are one `silk_clearance`, one `courtyard_clearance`, one `diff_pair_gap` with three limits, one `diff_pair_uncoupled`, one `no_tracks` on `In1.Cu`, and one `hole_to_hole`, with no unmapped record
