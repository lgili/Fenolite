## MODIFIED Requirements

### Requirement: Level 5 compares routing per net
`level_routing(a, b, pairing, tolerances)` SHALL compare the pieces of the nets that level 2 pairs, and SHALL report each difference with one code, located by the net's name on side `a` and the pads involved.
- `equiv.route-missing` (error): one side has copper on the net and the other has none.
- `equiv.route-connectivity` (error): the multisets of the pad sets of the pieces differ; `where` names the first pad set on one side only.
- `equiv.route-vias` (error): for equal pad sets, the via counts per span pair differ.
- `equiv.route-length` (error): for equal pad sets, a length per copper span differs by more than `max(length_nm, length × length_ppm / 1_000_000)`.
- `equiv.route-stub` (warning): the pieces without a pad differ in number or in total length beyond the tolerance.
- `equiv.route-unjudged` (info): a net whose pads are joined only through an unfilled zone on either side; such a net gives no other difference. Its issue MUST carry a `hint` that names the unfilled zone as the cause, says that an open connection may be hidden, and says to fill the zones and compare again.
- `pairing` MUST hold the pairs of net ids whose `REF-PIN` blocks are equal at level 2 and the elements both sides hold; a net that level 2 reported is not compared again, and the summary counts the nets of each side that no pair holds. `pairing` MUST also hold the elements that only one side holds (a pad a conversion lost): such a pad MUST count on that side in a piece that holds a track, an arc, a via or a fill, so copper that reaches a pad the other side lacks joins a pad set the other side does not hold. Any other pad outside the elements gives no element at this level.
- The four error kinds MUST be judged in the order above; `route-missing` and `route-connectivity` end the judgement of a net. `route-stub` and `route-unjudged` are notices (`LevelResult.notices`): they are reported and located, and they never make two designs unequal.
- A net is unjudged when a side holds an unfilled zone on it and more than one piece of it.
- The comparison rule (the kinds, their order and what each compares) MUST be one table of `routing.py`, so that another rule can be added beside it without a change to `pieces`.
- Copper spans MUST be compared as level 3 compares them. The level summary MUST hold the nets compared, the pieces, the vias, the total length per side and `zones_unfilled`.

#### Scenario: A faithful copy
- **GIVEN** the routed two-layer board and a copy written and re-read by the KiCad backend
- **WHEN** level 5 runs
- **THEN** it reports no difference

#### Scenario: Five planted edits
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_level5.py -k planted` removes a track, removes a via, moves a track to another layer, opens a connection and deletes a net's copper, one at a time
- **THEN** each run reports one difference, of the code `equiv.route-connectivity`, `equiv.route-vias`, `equiv.route-length`, `equiv.route-connectivity` and `equiv.route-missing` in that order, naming the net

#### Scenario: Copper that reaches a pad the other side lacks
- **GIVEN** the authored board `tests/data/kicad/convert/roundrect_roundtrip.kicad_pcb` converted to Altium, to KiCad and back to Altium, with `R1`'s pad 2 dropped from side b
- **WHEN** `uv run pytest tests/unit/convert/test_roundrect_roundtrip.py -k lost_pad` runs level 5 against the Altium source
- **THEN** it reports one `equiv.route-connectivity` on net `B`, side a `J1-2,R1-2` and side b `J1-2`, beside the level-3 `equiv.pad-missing` of `R1-2`
