## MODIFIED Requirements

### Requirement: Closed scope grammar
`fenolite.backends.altium.read.scope.parse_scope(text, *, document=None)` SHALL return a neutral `Selector`, or a string that says why the expression is outside the grammar. It MUST parse with Altium's order of precedence (S-2211), from tightest to loosest:

1. brackets;
2. `Not`;
3. `^ * / Div Mod And`;
4. `+ - Or Xor`;
5. `= <> < > <= >=`;
6. `&& ||`.

Equal levels resolve left to right. The parse MUST be typed: boolean, number with a unit, string.

Refusals:

- An expression whose typed reading is not well formed MUST be refused with the reason `type`, naming the operator. It MUST never be bracketed again.
- `All` below the top level, every function the tables of `docs/formats/altium/rule-file.md`, "Closed scope grammar", do not name, and any text left over MUST be refused.
- A function whose reading needs the document (D2 of change c0462) MUST be refused with the reason `document` when `document` is `None`.

Mappings:

- The functions MUST map as that table says: c0042's `All`, `InNet`, `InNetClass`, `InComponent`, item kinds and `InPolygon`, and change c0462's layer, room, pair, xSignal, component, polygon, hole and pad functions.
- An `InNet` value MUST be escaped into a glob that matches that name only.
- A scope MUST never be approximated: each selector MUST select exactly the objects Altium selects in the document read.

#### Scenario: Class and item kind
- **GIVEN** `InNetClass('HV') And (Not IsVia)`
- **WHEN** `parse_scope` is called
- **THEN** it returns `and(netclass HV, not(item_kind via))`

#### Scenario: Pour copper
- **GIVEN** `InPolygon And (Not InNetClass('HV'))` and `InPoly`
- **WHEN** `parse_scope` is called on each
- **THEN** it returns `and(item_kind zone, not(netclass HV))` and `item_kind zone`

#### Scenario: Mixed operators by Altium's precedence
- **GIVEN** `InNet('A') Or InNet('B') And IsTrack` and `(OnTopLayer Or OnBottomLayer) && InNet('GND')`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_scope_c0462.py -k precedence` parses them
- **THEN** the first is `or(net A, and(net B, item_kind track))`, and the second is `and(or(layer F.Cu, layer B.Cu), net GND)`

#### Scenario: A comparison under And
- **GIVEN** `HoleDiameter > 1 And IsPad` and `HoleDiameter > 1 && IsPad` in a document of millimetres
- **WHEN** the same file, `-k comparison`, parses them
- **THEN** the first is refused with the reason `type` naming `And`, and the second is `and(hole 1000001.., item_kind pad)`

#### Scenario: A wildcard in a net name
- **GIVEN** `InNet('PWR*')`
- **WHEN** `parse_scope` is called
- **THEN** it returns a `net` selector that matches the net `PWR*` and does not match `PWR1`

## ADDED Requirements

### Requirement: Scope functions read from the document
`parse_scope` with a `document` SHALL read the functions of change c0462 (design D2 and D3) from the document, and MUST record each one in `rule-file.md` with its source and evidence label.

- `OnLayer`, `OnTopLayer`, `OnBottomLayer` and `OnMid` MUST give `layer` leaves of the copper layers of the board.
- `WithinRoom` MUST give `area` leaves of the rooms read as rule areas.
- `InDifferentialPair`, `InAnyDifferentialPair` and `IsDifferentialPair` MUST give `diff_pair` leaves.
- `InDifferentialPairClass`, `InxSignal` and `InxSignalClass` MUST be expanded from the document's definitions.
- `HasFootprint`, `IsComponent`, `IsNetTieComponent`, `IsSOIC`, `IsBGA`, `IsLCC` and `InNamedUnion` MUST be expanded to `ref` leaves of the components they select, or to `not(all)` when none match.
- `IsNamedPolygon` and `InNamedPolygon` MUST give `zone` leaves; `HoleDiameter` comparisons `hole` leaves; `PadIsPlated` `pad_type` leaves.
- An expansion MUST be the same for the same document. `fenolite.dsl` MUST print an expanded rule with a comment naming its source function.
- A definition the document lacks MUST give the reason `undefined`. A package check that disagrees with the kit oracle MUST give `package-check`.

#### Scenario: Package checks on authored footprints
- **GIVEN** authored footprints: an 8-pad SOIC, a 4 × 4 LCC of 16 pads, a 10 × 10 BGA of 100 pads, and a 2-pad chip
- **WHEN** `uv run pytest tests/unit/backends/altium/test_scope_packages_c0462.py -q -n 0` evaluates `IsSOIC`, `IsLCC` and `IsBGA`
- **THEN** each check selects exactly its own footprint, and none selects the chip

#### Scenario: Altium selects the same objects
- **GIVEN** every distinct scope of the 8 public rows of the pour census that maps to a selector
- **WHEN** `uv run pytest tests/corpus/test_altium_scope_oracle_c0462.py -q -n 0` compares Fenolite's selection with the kit record of Altium's PCB filter (S-2214)
- **THEN** the objects of each kind agree for every scope

### Requirement: Rule record keys read
`map_rules` SHALL read the record keys of change c0462 (design D5) and MUST NOT approximate any of them.

- Per-layer Width and DiffPairsRouting values MUST give one rule per copper layer of the board whose value differs from the general one.
- Width impedance keys MUST be read through the per-layer widths the record holds. When the widths come from a profile the record does not hold, the record MUST stay `Unmapped`, reason `impedance-profile`.
- RoutingVias template keys MUST be read from the template the document holds. A template the document does not hold MUST stay `Unmapped`, reason `template`.
- An `OBJECTCLEARANCES` matrix of a Clearance or BoardOutlineClearance record MUST give neutral rules such that every pair of object kinds gets exactly its cell's gap. A cell whose object kind has no neutral kind MUST be refused, reason `matrix-kind`, naming the cell.

#### Scenario: A matrix of differing cells
- **GIVEN** an authored Clearance record of 0.2 mm whose matrix gives track to SMD pad 0.3 mm, via to via 0.15 mm and every other cell 0.2 mm
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rule_keys_c0462.py -k matrix` maps it and evaluates every pair of object kinds
- **THEN** each pair gets its cell's gap, and no `Unmapped` is given

#### Scenario: Per-layer widths
- **GIVEN** an authored Width record with a general preferred width of 0.25 mm and `BOTTOMLAYER_PREFWIDTH` 0.3 mm on a two-layer board
- **WHEN** the same file, `-k layer`, maps it
- **THEN** it gives the general rule and one rule `and(scope, layer B.Cu)` of 0.3 mm

### Requirement: Rule kinds and their reading
`docs/formats/altium/rule-file.md`, "Rule kinds and their reading", SHALL list every rule kind of the corpus as one of:

- neutral (a `RuleKind`);
- read by a backend part, naming the part;
- checked by `fenolite check` itself;
- carried only (c0434), with the reason it governs no copper geometry.

The rest of the requirement:

- MatchedLengths MUST map to `skew` and, with a target length, to `length`.
- An unscoped SolderMaskExpansion MUST give `Board.mask_margin`.
- A record that relaxes a check Fenolite performs itself MUST give the warning `altium.rules.check-relaxed`, and `check` MUST honour it.
- An `OnMid` scope on a board with no internal copper layer MUST give the info `altium.rules.applies-to-nothing` and no `Unmapped`.

#### Scenario: Every corpus kind is listed
- **WHEN** `uv run pytest tests/corpus/test_altium_rule_kinds_c0462.py -q -n 0` reads every rule record of the public Altium rows
- **THEN** each kind is in the table, and no record of a kind listed as neutral or read is `Unmapped` with the reason `no-counterpart`

#### Scenario: No refusal of scope or keys in the pour census
- **WHEN** `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_pour_census.py -q -n 0` runs
- **THEN** no polygon is refused with `rule-scope`, `rule-unmapped` or `connect-scope`
