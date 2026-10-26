## ADDED Requirements

### Requirement: Rule areas in the copper check
`check_copper` SHALL find, for each copper item and each copper layer it is on, the names of the rule areas it lies in, and SHALL pass them to `ClearanceResolver.subject` as `areas`, so that clearance rules scoped to an area are judged where KiCad's DRC applies them (`H-K-AREA-COND`).
- A rule area is a `Keepout` of `design.board.keepouts` with a non-empty `name`. An item lies in it on a layer when the layer is one of the area's `layers` and the item's shape on that layer, narrowed by its band for an arc as for shorts, touches or overlaps the area's outline taken as a filled polygon (`thick_touch`). Fills count as items; zone outlines do not.
- An item lies in a name that two areas carry when it lies in either.
- A `Keepout` whose outline is empty (kept opaque by the reader) or refused by `Polygon` MUST be left out, counted in `summary.unsupported` under `rule-area`, and reported by one `copper.item-unsupported` warning with the count, as "Copper items and their shapes" does for items it cannot shape. Its name then matches no item and its settings are not judged ("Keep-out findings").
- `summary.rule_areas` MUST report the count of rule areas that were used.
- The membership is computed once per item and layer, from a spatial index of the areas' boxes, and changes no shape and no pair of "Pairs that are judged".

#### Scenario: Larger clearance inside a high-voltage area
- **GIVEN** a rule area `HV` on `F.Cu` and `B.Cu`, a clearance rule with `selector_a = area HV` and `min = 2 mm`, and two pairs of tracks of different nets 1 mm apart, one inside the area and one outside
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k area` runs `check_copper`
- **THEN** it reports one `copper.clearance` with source `rule:<name>` for the pair inside and nothing for the pair outside

#### Scenario: Neck-down inside a BGA area
- **GIVEN** a board-wide clearance rule of 0.2 mm, then a rule of priority 1 with `selector_a = area BGA` and `min = 0.1 mm`, and two pairs 0.15 mm apart, one inside the area and one outside
- **WHEN** `check_copper` runs
- **THEN** it reports one `copper.clearance` for the pair outside and none for the pair inside

#### Scenario: An area on one layer
- **GIVEN** the rule area `HV` on `F.Cu` only, the 2 mm rule, and a pair 1 mm apart on `B.Cu` under the area
- **WHEN** `check_copper` runs
- **THEN** it reports no finding for the pair

#### Scenario: Copper just outside the area
- **GIVEN** the 2 mm rule and a pair whose first track's copper ends 50 µm outside the area, and again with the area reaching 50 µm into that copper
- **WHEN** `check_copper` runs on both
- **THEN** it reports nothing for the first and one `copper.clearance` for the second

#### Scenario: Opaque area outline
- **GIVEN** a board read from a file whose rule area `HV` has an arc in its `pts`
- **WHEN** `check_copper` runs
- **THEN** `summary.unsupported` holds `rule-area: 1`, the issues hold one `copper.item-unsupported` naming it, and no item lies in `HV`

### Requirement: Keep-out findings
`check_copper` SHALL report one `copper.keepout` error for each copper item that lies, on a layer of a `Keepout`, in an area whose settings forbid its kind: a track or an arc where `no_tracks` is true, a via where `no_vias` is true, and a pad where `no_pads` is true (`H-K-AREA-KEEPOUT`). Lying in an area is decided as in "Rule areas in the copper check", for every `Keepout`, named or not.
- One finding MUST be given per item and keep-out, on the first such layer in copper table order. Fills MUST NOT be reported, because KiCad's DRC does not report a stored fill in a copper-pour keep-out and its filler leaves the area out; zone outlines and footprints are not copper items here.
- The `CopperFinding` MUST hold the code, severity `error`, the layer, a point of the overlap (`thick_witness`), the item and the area as `CopperRef("keepout", <the area's name, else its locator>, <its id>, "<no net>")`, a gap of 0, no clearance, and the source `keepout:<name or locator>`. `CopperKind` gains `keepout`, which no rule subject takes.
- The message MUST name the item's kind and net, the area, the setting that forbids it, the layer and the point in millimetres.
- `summary.keepouts` MUST report the count of findings, and the findings MUST follow the order of "Locations and deterministic output".

#### Scenario: Track in a tracks keep-out
- **GIVEN** a keep-out on `F.Cu` with `no_tracks`, a track inside it, a track crossing its edge, a track outside it, and a track on `B.Cu` under it
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k keepout` runs `check_copper`
- **THEN** it reports exactly two `copper.keepout` errors, naming the track inside and the crossing track, on `F.Cu`

#### Scenario: Only the forbidden kind
- **GIVEN** a keep-out on both copper layers with `no_vias` only, holding a via and a track
- **WHEN** `check_copper` runs
- **THEN** it reports one `copper.keepout` for the via and none for the track

#### Scenario: Pads and fills
- **GIVEN** a keep-out with `no_pads` and `no_copper_pour` over a placed two-pad footprint and over part of a zone's stored fill
- **WHEN** `check_copper` runs
- **THEN** it reports one `copper.keepout` per pad and none for the fill

## MODIFIED Requirements

### Requirement: Clearance in force
`fenolite.checks.clearance.ClearanceResolver(design, *, min_clearance=None, rules_over_classes=True, floor_over_rules=False)` SHALL return, through `resolve(a, b, *, zone_clearance=None)` for two `RuleSubject`s on the same layer, a `Clearance(value, severity, source)`:
- **Subjects.** `item_kind` is `track` for tracks and arcs, `via`, `pad` or `zone` (fills); `net` is the net name; `netclass` is the name of the net's class, or `Default` when its `netclass_id` is `None`; `ref` is the component reference for a pad and `None` otherwise; `layer` is the shared layer; `areas` holds the names of the rule areas the item lies in on that layer ("Rule areas in the copper check") and is empty for a subject built without them. `ClearanceResolver.subject(kind, net_id, *, ref, layer, areas=frozenset())` builds a subject.
- **Rules.** The candidates MUST be the rules of `design.rules.rules` (none when `design.rules` is `None`) with `kind == "clearance"`, a `min` limit, and empty `layers` or `layers` holding the shared layer. A rule MUST match the pair when `selector_a` matches one subject and `selector_b` (or every subject, when it is `None`) matches the other, in either order. Leaf values and subject names MUST be compared without regard to letter case (`H-K-DRU-COND`), except `area` leaves and area names, which MUST be compared with letter case and with `*` as a glob, as KiCad compares them (`H-K-AREA-COND`).
- **Precedence.** The governing rule MUST be the last matching rule in the order of `rule_precedence(rules)`, which MUST equal c0018's `rulemap.rule_order`: priority 0 first, then descending priority, ties by name, then id.
- **Value.** Let `k` be the larger `clearance` of the two nets' classes that set one, the class of a net whose `netclass_id` is `None` being the class named `Default` when `design.circuit.netclasses` holds one, let `f` be `min_clearance` when it is positive, and let `z` be `zone_clearance` when it is positive.
  - A governing rule with severity `ignore` MUST give `value=None` and `severity=None`, so the pair is not judged for clearance.
  - Without a governing rule, the value MUST be the largest of `k`, `z` and `f` that exist, with severity `error` and source `class:<name>`, `zone` or `floor` (`H-K-PRO-FLOOR`, `H-K-PRO-MIN-KEYS`, `H-K-COPPER-ZONECLR`). Among equal values the source MUST be the class, then the zone, then the floor.
  - With a governing rule of `min` `r`, the value MUST start at `r` with the rule's severity and source `rule:<name>`; when `rules_over_classes` is false, the largest of it, `k` and `z` MUST be taken (`H-K-PRO-MIN-CLASS`), so `z` is kept wherever a class value is kept and replaced wherever a class value is replaced; when `floor_over_rules` is true, the larger of the result and `f` MUST be taken (the claim of `H-K-PRO-MIN-RULE`, which c0026 refuted on 9.0.9 and 10.0.6: `H-K-PRO-MIN-RULE-2`). The source names whichever value governs, and the severity is the rule's when its `min` governs and `error` otherwise.
  - `rules_over_classes` and `floor_over_rules` carry c0026's measured tables `lowering.RULES_OVER_CLASSES` and `lowering.FLOOR_OVER_RULES["min_clearance"]` for the major being judged. The defaults are the values those tables ship with for 9 and 10: `rules_over_classes` true (`H-K-PRO-MIN-CLASS`) and `floor_over_rules` false, because a custom rule governs below the board minimum (`H-K-PRO-MIN-RULE-2`).
- **Unset.** When nothing gives a value, `value` MUST be `None` and the pair is judged for shorts only; `check_copper` MUST count such pairs in `summary.unset_pairs` and report one `copper.clearance-unset` info with the count.
- **Zone clearance.** `zone_clearance` is the `settings.clearance` of the zone of a fill. `check_copper` MUST pass it for a pair of one fill and one item that is not a fill, and MUST pass `None` for every other pair, two fills included. KiCad's DRC judges a stored fill against a track, a via or a pad with the zone's clearance as it does a class value, lets a governing custom rule replace it, and judges no pair of two fills (`H-K-COPPER-ZONECLR`, measured on 9.0.9 and 10.0.6). The zone's clearance is not written into a rule and changes no file.
- `max_value` MUST be the largest value `resolve` can return for the design, the `settings.clearance` of every zone of the board that has fills included, or 0.

#### Scenario: Rule overrides the classes
- **GIVEN** nets `HV` and `LV` in classes with clearances 0.5 mm and 0.2 mm, and a `clearance` rule `hv_lv` with `selector_a = net HV`, `selector_b = net LV` and `min = 1 mm`
- **WHEN** `uv run pytest tests/unit/checks/test_clearance.py -k rule` resolves an `LV` track against an `HV` pad
- **THEN** it returns 1 mm, severity `error` and source `rule:hv_lv`; without the rule it returns 0.5 mm with source `class:<HV class name>`

#### Scenario: Classes above a rule where KiCad keeps them
- **GIVEN** the same nets and a rule of 0.1 mm on the pair
- **WHEN** the pair is resolved with `rules_over_classes=True` and with `rules_over_classes=False`
- **THEN** the first gives 0.1 mm with source `rule:<name>`, and the second 0.5 mm with source `class:<HV class name>`

#### Scenario: Later rule governs
- **GIVEN** two matching clearance rules `a` (priority 1, 0.1 mm) and `b` (priority 2, 0.3 mm)
- **WHEN** the pair is resolved
- **THEN** the value is 0.1 mm, because `rule_order` puts `a` last

#### Scenario: Floor and ignore
- **GIVEN** a governing rule of 0.1 mm and `min_clearance = 0.15 mm`, and then the same rule with severity `ignore`
- **WHEN** the pair is resolved
- **THEN** the first gives 0.1 mm with source `rule:<name>`, the second gives `value is None`, and with `floor_over_rules=True` the first gives 0.15 mm with source `floor`

#### Scenario: Letter case ignored
- **GIVEN** a rule on `net gnd` and a track on net `GND`
- **WHEN** the pair is resolved
- **THEN** the rule governs

#### Scenario: Zone clearance above the class
- **GIVEN** nets `A` and `B` in a class with a clearance of 0.2 mm
- **WHEN** `uv run pytest tests/unit/checks/test_clearance.py -k zone` resolves a fill of `A` against a track of `B` with `zone_clearance=300_000`, and again with `zone_clearance=100_000`
- **THEN** the first gives 0.3 mm, severity `error` and source `zone`, and the second 0.2 mm with source `class:<class name>`

#### Scenario: Rule replaces the zone clearance
- **GIVEN** the same nets, a `clearance` rule of 0.2 mm on the pair and `zone_clearance=500_000`
- **WHEN** the pair is resolved with `rules_over_classes=True` and with `rules_over_classes=False`
- **THEN** the first gives 0.2 mm with source `rule:<name>`, and the second 0.5 mm with source `zone`

#### Scenario: Board minimum above the zone
- **GIVEN** the same nets without a rule, `min_clearance = 0.4 mm` and `zone_clearance=300_000`
- **WHEN** the pair is resolved
- **THEN** the value is 0.4 mm with source `floor`; with `min_clearance = 0.25 mm` it is 0.3 mm with source `zone`

#### Scenario: Fill against a track and against another fill
- **GIVEN** a board whose zone of net `A` has a clearance of 0.5 mm and a stored fill, a track of net `B` 0.3 mm from that fill, and a second zone of net `B`, also with a clearance of 0.5 mm, whose stored fill is 0.3 mm from the first fill, both nets in a class with a clearance of 0.2 mm
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k zone_clearance` runs `check_copper`
- **THEN** it reports exactly one `copper.clearance`, between the first fill and the track, with clearance 500 000 nm and source `zone`

#### Scenario: Rule scoped to an area
- **GIVEN** a clearance rule `hv` with `selector_a = area HV` and `min = 2 mm`, and two tracks of nets `A` and `B` in a class with a clearance of 0.2 mm
- **WHEN** `uv run pytest tests/unit/checks/test_clearance.py -k area` resolves the pair with `areas={"HV"}` on the first subject, and again with no areas
- **THEN** the first gives 2 mm with source `rule:hv`, and the second 0.2 mm with source `class:<class name>`

#### Scenario: Area names keep their case
- **GIVEN** the same rule and a subject whose `areas` is `{"hv"}`
- **WHEN** the pair is resolved
- **THEN** the rule does not govern
