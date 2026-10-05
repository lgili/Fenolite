## ADDED Requirements

### Requirement: New rule kinds are enforced by kicad-cli
`tests/kicad/rules/test_rule_kinds_new.py`, `test_rule_floors.py` and the extended `test_rule_order.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-DRU-KIND-2`, `H-K-DRU-COURTYARD` and `H-K-PRO-MIN-RULE-3` on the running `kicad-cli`, with benches built by `tests/kicad/rules/_rulebench.py`, through c0009's `KicadCli` on copies with an empty `KICAD_CONFIG_HOME`, judging DRC only from the JSON report.
- **Canary.** Every bench MUST carry the canary scoped to its own net (`A.NetName == 'CANARY_A'`), and a run whose canary does not fire MUST fail. An unscoped canary MUST NOT be used: KiCad reports one violation per item pair, so it would hide the constraint under test.
- **Kinds.** One bench per new kind, with a probed item and a control item, and the rule as Decisions 1 and 2 of the design write it: two vias whose holes are closer than the rule (`hole_to_hole`); a via hole near a track of another net (`hole_clearance`); a via whose ring is below the rule (`annular_width`); two footprints whose courtyards are closer than the rule (`courtyard_clearance`); two footprints whose silkscreen overlaps (`silk_clearance`, board-wide); c0047's slot bench (`creepage`). Probe `dru-kind-<kind>` MUST record `present` when the probed item gives a violation of the kind's DRC types and the control item none, and `absent` otherwise.
- **Courtyard selection.** `dru-courtyard-reference` MUST record `present` when the rule with `A.Reference == '<ref>'` gives `courtyards_overlap` for that footprint, and `dru-courtyard-member` `absent` when the same rule with `A.memberOfFootprint('<ref>')` gives none.
- **Order.** Two `hole_to_hole` rules matching the same vias, 0.5 mm then 1 mm, MUST give the violation, and swapped MUST give none, on both majors (the plan's overlapping-rule fixture, for a new kind).
- **Floors.** `pro-min-rule-<kind>-tM` for `hole_clearance`, `hole_to_hole` and `annular_width`, on a project that holds the template's board-setup minimums: a board-wide rule whose `min` is below the minimum of its kind, and an item between the two values; `present` when no violation of the kind's type is reported for it, and a control run without the rule MUST report one. `silk_clearance` has no such probe: the template's `min_silk_clearance` is 0, and no rule can be below it.
- Outcomes MUST be recorded in both probe files; `KIND_SUPPORT` and, through Decision 7 of the design, `MINIMUM_KEYS` MUST follow them; the facts MUST be written to `docs/formats/kicad/rules.md` and `docs/formats/kicad/drc.md` with sources and labels.
- **Stop rules.** A `dru-kind-*` outcome other than `present` leaves that kind out of `KIND_SUPPORT` for that major and is recorded; `dru-courtyard-reference` other than `present` stops courtyard selectors other than `all`.

#### Scenario: Kinds on 10.0.6
- **WHEN** `uv run pytest tests/kicad/rules/test_rule_kinds_new.py -rA` runs on the local KiCad 10.0.6
- **THEN** every `dru-kind-*` probe records `present`, the courtyard probes record `present` and `absent`, and the canary fires in every run

#### Scenario: Kinds on 9.0.9
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and `FENOLITE_REQUIRE=kicad`
- **WHEN** the same tests run in the `kicad-9` job
- **THEN** `dru-kind-creepage` records `absent`, the other kinds `present`, and `KIND_SUPPORT["creepage"]` is `frozenset({10})`

#### Scenario: Overlapping hole rules
- **WHEN** `uv run pytest tests/kicad/rules/test_rule_order.py -k hole_to_hole -rA` runs on both majors
- **THEN** the later rule governs in both orders
