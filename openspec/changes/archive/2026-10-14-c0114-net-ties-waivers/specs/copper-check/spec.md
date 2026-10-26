## MODIFIED Requirements

### Requirement: Pairs that are judged
`check_copper` SHALL judge every pair of copper shapes that share a copper layer and belong to two different items whose nets differ, except the pairs of tied pads below. Two items whose `net_id` are equal MUST NOT be judged, and two items without a net MUST NOT be judged; an item without a net and an item with a net MUST be judged.
- Candidate pairs MUST come from one `SpatialIndex` per copper layer, built from the `thick_bbox` of each shape grown on every side by `⌈max_value / 2⌉`, `max_value` being the largest value that `ClearanceResolver` can return for the board, so that no pair closer than its clearance is missed.
- Each item pair MUST give at most one finding: a short when its shapes touch on any shared layer, otherwise a clearance finding when they are too close on any shared layer. The finding MUST name the first such layer in copper table order.
- **Net-tie groups.** Two pads of one footprint instance whose numbers both belong to one group of that footprint's `net_ties` (`design-model`, "Net-tie groups in the model") MUST NOT be judged, neither for a short nor for clearance, because KiCad's DRC does not judge them (`H-K-NETTIE-DRC`). A pad is in a group when its `BoardPad.number` is; every physical pad of a repeated number counts. Two pads of a net-tie footprint that share no group, and a pad paired with any item that is not a pad of the same footprint, MUST be judged as before: KiCad judges no pair of pads of such a footprint, grouped or not, but a touch between a tied pad and a pad outside its group is a defect that KiCad reports only as a solder-mask bridge, so Fenolite may report more. The item pairs left out this way MUST be counted in `summary.net_tie_pairs`, which is 0 on a board without net-tie groups.

#### Scenario: Same net never judged
- **GIVEN** two overlapping tracks on net `GND` on `F.Cu`
- **WHEN** `check_copper` runs
- **THEN** it reports no finding

#### Scenario: One finding for a pair on two layers
- **GIVEN** two through vias of nets `A` and `B` whose discs overlap on a two-layer board
- **WHEN** `check_copper` runs
- **THEN** it reports exactly one `copper.short`, on `F.Cu`

#### Scenario: Index agrees with brute force
- **GIVEN** 300 generated tracks and vias on two layers and four nets with a 0.2 mm class clearance
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k brute_force` compares the findings with those of a check that judges every pair
- **THEN** the two finding lists are equal

#### Scenario: Tied pads that touch
- **GIVEN** a footprint `NT1` whose 1 mm square pads `1` (net `A`) and `2` (net `B`) overlap by 0.2 mm on `F.Cu`, with `net_ties == (("1", "2"),)`, and a class clearance of 0.2 mm
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k net_tie` runs `check_copper` with the pads of the board frame
- **THEN** it reports no finding and `summary.net_tie_pairs` is 1; with `net_ties == ()` it reports one `copper.short` naming `NT1-1` and `NT1-2`

#### Scenario: Tied pads closer than the clearance
- **GIVEN** the same pads 0.1 mm apart, the same group and the same class
- **WHEN** `check_copper` runs
- **THEN** it reports no finding; without the group it reports one `copper.clearance` error with gap 100 000 nm

#### Scenario: A pad outside the group is still judged
- **GIVEN** a footprint with three overlapping pads `1`, `2` and `3` on nets `A`, `B` and `C`, and `net_ties == (("1", "2"),)`
- **WHEN** `check_copper` runs
- **THEN** it reports exactly one `copper.short`, naming pads `2` and `3`, and `summary.net_tie_pairs` is 1

#### Scenario: A track near a tied pad is still judged
- **GIVEN** the tie of "Tied pads that touch" with its pads 0.5 mm apart, and a 0.25 mm track of net `A` ending 0.1 mm from pad `2`, class clearance 0.2 mm
- **WHEN** `check_copper` runs
- **THEN** it reports one `copper.clearance` error naming `NT1-2` and the track, as KiCad's DRC does

### Requirement: Supported cases are documented against KiCad's DRC
`docs/formats/kicad/copper.md` SHALL hold a table of the cases this check supports and how they compare with KiCad's DRC, with a hypothesis id or the word "documented difference" per row. It MUST state at least: tracks, vias and pads exact; arcs within their band; vias and through-hole pads on every spanned layer, with unused-layer removal not modelled (Fenolite may report more); two pads of one net-tie group of one footprint not judged, as KiCad's DRC does not judge them (`H-K-NETTIE-DRC`); two pads of a net-tie footprint that share no group judged, although KiCad's DRC judges no pair of pads of such a footprint and reports only a solder-mask bridge between them (Fenolite may report more); zone fills checked as stored, outlines only for overlaps; the zone's own clearance applied between a fill and a track, a via or a pad as KiCad's DRC applies it, a governing custom rule replacing it (`H-K-COPPER-ZONECLR`); pairs of two fills judged with the rule, class and board-minimum values only, although KiCad's DRC judges no pair of fills (Fenolite may report more); graphics, texts, holes, edges, mask and silkscreen not checked, so the copper of a net tie's bridge is never seen; KiCad project severity overrides and exclusions not applied to copper findings, which a waiver accepts one by one (`verification-loop`, "Waivers in the check"); opaque custom rules not applied (`copper.rules-incomplete`); a project without net classes gives no clearance in force. The parity proven on canaries (`kicad-oracle`, "Copper verdict parity canaries" and "Net-tie parity canaries") MUST be stated per row and per major.

#### Scenario: Table checked
- **GIVEN** `docs/formats/kicad/copper.md`
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** every fact row has an S-id, a valid label and a hypothesis below `CORPUS-VERIFIED`, and the supported-cases table has a hypothesis id or "documented difference" in every row

#### Scenario: Zone rows of the table
- **GIVEN** `docs/formats/kicad/copper.md` after this change
- **WHEN** `uv run pytest tests/unit/test_format_facts.py -k copper` reads the supported-cases table
- **THEN** the row of the zone's own clearance names `H-K-COPPER-ZONECLR` and its parity on 9.0.9 and 10.0.6, a row for pairs of two fills says "documented difference", and no row says that the zone's clearance is not applied

#### Scenario: Net-tie rows of the table
- **GIVEN** `docs/formats/kicad/copper.md` after this change
- **WHEN** `uv run pytest tests/unit/test_format_facts.py -k copper` reads the supported-cases table
- **THEN** a row for pads of one net-tie group names `H-K-NETTIE-DRC` and its parity on 9.0.9 and 10.0.6, a row for pads of a net-tie footprint outside a common group says "documented difference", and no row says that net-tie pad groups are reported as shorts
