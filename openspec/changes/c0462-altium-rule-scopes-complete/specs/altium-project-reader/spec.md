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

- The functions MUST map as that table says: c0042's `All`, `InNet`, `InNetClass`, `InComponent`, item kinds and `InPolygon`, and change c0462's layer, pair, xSignal, component, polygon, hole and pad functions; `WithinRoom` is refused (below).
- An `InNet` or `InComponent` value MUST become a glob in which Altium's wildcards `*` and `?` stay wildcards and every other glob character matches itself (S-2212: `InNet('V*')` returns the nets whose names start with V); an `InNetClass` value MUST match its name only.
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
- **THEN** the first is `or(net A, and(net B, item_kind track))`, and the second is `and(or(and(layer F.Cu, not(M)), and(layer B.Cu, not(M))), net GND)`, where `M` is `or(item_kind via, pad_type th, pad_type npth)`, the objects on Multi-Layer

#### Scenario: A comparison under And
- **GIVEN** `HoleDiameter > 1 And IsPad` and `HoleDiameter > 1 && IsPad` in a document of millimetres
- **WHEN** the same file, `-k comparison`, parses them
- **THEN** the first is refused with the reason `type` naming `And`, and the second is `and(hole 1000001.., item_kind pad)`

#### Scenario: A wildcard in a net name
- **GIVEN** `InNet('PWR*')` and `InNet('PWR[1]')`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_scope_c0462.py -k wildcard` parses them
- **THEN** the first matches the nets `PWR1` and `PWR*`, and the second matches the net `PWR[1]` and not `PWR1`

### Requirement: Text reader issue codes
`fenolite.backends.altium.read.textfile.TEXT_READ_CODES` SHALL be this closed mapping, and every issue of the modules of this capability MUST use one of its codes with the severity given:

| code | severity | when |
|---|---|---|
| `altium.text.encoding-assumed` | warning | no byte-order mark and the bytes are not UTF-8; read as Latin-1 |
| `altium.text.mixed-line-ends` | info | more than one kind of line end |
| `altium.text.duplicate-key` | info | a key repeated in one section |
| `altium.text.stray-line` | info | a line that is neither a section, a key nor empty |
| `altium.text.unknown-key` | info | a key line of an annotation file that names no unique-id path with a designator |
| `altium.project.no-design-section` | warning | a project file without `[Design]` |
| `altium.project.hierarchy-mode-unknown` | warning | a `HierarchyMode` outside `HIERARCHY_MODES` |
| `altium.project.document-kind-unknown` | info | a document extension outside `DOCUMENT_KINDS` |
| `altium.project.document-missing` | warning | a listed document is not a file |
| `altium.project.document-outside` | warning | a document path leaves the project folder |
| `altium.project.companion-unreadable` | warning | a listed companion raised `FormatError` |
| `altium.outjob.output-incomplete` | warning | an output without its type |
| `altium.rule.record-malformed` | warning | a line of an export file without a rule kind |
| `altium.rule.summary-form` | info | a summary-form file: its rules are not mapped |
| `altium.rule.unmapped` | info | one rule that is not mapped, with its reason |
| `altium.rule.applies-to-nothing` | info | in place of `altium.rule.unmapped`: a rule whose scope applies to no object of the board (`OnMid` without an internal signal layer, c0462) |
| `altium.stackup.unknown-form` | warning | more than one generation of layer keys |
| `altium.stackup.length-unreadable` | warning | a thickness that is not a length |

No issue of this capability MUST have the severity `error`: malformed input raises `FormatError`, which the CLI maps to `FEN-3004`. An issue message MUST NOT hold a path outside the project folder.

#### Scenario: Closed set
- **GIVEN** the issues produced by the unit cases of this capability and the `altium.text.`, `altium.project.`, `altium.outjob.`, `altium.rule.` and `altium.stackup.` literals in `src/fenolite/backends/altium/read/*.py`
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_text_codes.py` runs
- **THEN** every produced code is a key of `TEXT_READ_CODES` with the table's severity, and the set of literals of the ten text modules equals the keys of `TEXT_READ_CODES`

## ADDED Requirements

### Requirement: Scope functions read from the document
`parse_scope` with a `document` SHALL read the functions of change c0462 (design D2 and D3) from the document, and MUST record each one in `rule-file.md` with its source and evidence label.

- `OnTopLayer`, `OnBottomLayer`, `OnOutside` and `OnMid` MUST give `layer` leaves of the copper layers of the board without the objects on Multi-Layer (S-2212: `OnOutside` returns none of them). `ExistsOnLayer` and `OnLayer` MUST give the `layer` leaf with the objects on Multi-Layer, and MUST be refused with the reason `via-span` when a via of the document spans part of the stack.
- `WithinRoom` of a room the document holds (`ScopeDocument.rooms`, "Altium rooms are rule areas") MUST be refused with the reason `room-membership`, naming the function: a pad or a via is in a room by its centre and any other object only wholly within it (S-2212), which no neutral leaf selects. A room the document does not hold MUST be refused with `undefined`.
- `InDifferentialPair`, `InAnyDifferentialPair` and `IsDifferentialPair` MUST give the `net` leaves of the pairs' two nets: a primitive's subject does not carry its pair, and the nets select the same primitives.
- `InDifferentialPairClass` MUST be expanded from the document's class definitions to the `net` leaves of its pairs' nets, for every rule kind: Altium's PCB filter selects the pairs' tracks, vias and pads for it (S-2214). `InxSignal` and `InxSignalClass` MUST be refused with the reason `xsignal`, and `InNamedUnion` with the reason `union`: no neutral leaf holds an xSignal, and the reader does not read unions.
- `HasFootprint`, `IsComponent`, `IsNetTieComponent`, `InComponentClass`, `IsSOIC`, `IsBGA`, `IsLCC` and `CompPinCount` MUST be expanded to `ref` leaves of the components they select, or to `not(all)` when none match; a `CompPinCount` comparison that a free object meets (a free object counts 0 pins, S-2214) MUST be expanded to `not` of the `ref` leaves of the components that do not comply, or to `all` when every component complies; a designator that also names a component not selected MUST give the reason `designator`.
- A function that returns parent objects without their children (`IsNamedPolygon`, `IsComponent`, `IsNetTieComponent`, `InComponentClass`, the package checks, `IsDifferentialPair`; S-2212) MUST map only for a rule kind whose subject is that parent, and MUST otherwise be refused with the reason `object-kind`.
- `IsNamedPolygon` and `InNamedPolygon` MUST give `zone` leaves; `HoleDiameter` comparisons `hole` leaves; `PadIsPlated` `pad_type` leaves.
- An expansion MUST be the same for the same document. `fenolite.dsl` MUST print an expanded rule with a comment naming its source function.
- A definition the document lacks MUST give the reason `undefined`. A package check that cannot decide (a component turned off the board's axes) or that disagrees with the kit oracle MUST give `package-check`.

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
- An `OBJECTCLEARANCES` matrix of a Clearance or BoardOutlineClearance record MUST give neutral rules such that every pair of object kinds gets exactly its cell's gap. A matrix that gives different values to object kinds one neutral kind holds (an arc and a track, a fill and a region, the outline and a cutout), or that names an object or edge kind outside the table, MUST be refused, reason `matrix-kind`, naming the cell. An entry of a kind no neutral rule holds (a hole, a cavity, a split line) MUST change no rule and stay in the record's bag.

#### Scenario: A matrix of differing cells
- **GIVEN** an authored Clearance record of 0.2 mm whose matrix gives track to SMD pad 0.3 mm, via to via 0.15 mm and every other cell 0.2 mm
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rule_keys_c0462.py -k matrix` maps it and evaluates every pair of object kinds
- **THEN** each pair gets its cell's gap, and no `Unmapped` is given

#### Scenario: A matrix that tells an arc from a track
- **GIVEN** an authored Clearance record whose matrix gives arc to via 0 and leaves track to via at the record's gap
- **WHEN** the same file, `-k matrix`, maps it
- **THEN** the record stays `Unmapped` with the reason `matrix-kind`, naming `Arc-Via` and `Track-Via`

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
- Unscoped and scoped SolderMaskExpansion records MUST be read by the openings' reading (`convert.openings`,
  c0440 and c0445), not mapped to `Board.mask_margin` directly.
- A record that relaxes a check Fenolite performs itself MUST be reported as a warning,
  `altium.rules.check-relaxed`. `fenolite check` takes no allowance by net and no tolerance of dangling copper
  from the design, so the relaxation is not honoured; the kind table names this limitation.
- An `OnMid` scope on a board with no internal signal layer MUST give the info `altium.rule.applies-to-nothing` in place of `altium.rule.unmapped`. Its record MUST stay an `Unmapped` with the reason `no-layer`, one of `rules.NOT_APPLYING`: it is no unread rule, and a conversion keeps it (c0424).

#### Scenario: Every corpus kind is listed
- **WHEN** `uv run pytest tests/corpus/test_altium_rule_kinds_c0462.py -q -n 0` reads every rule record of the public Altium rows
- **THEN** each kind is in the table, and no record of a kind listed as neutral or read is `Unmapped` with the reason `no-counterpart`

#### Scenario: No refusal of scope or keys in the pour census
- **WHEN** `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_pour_census.py -q -n 0` runs
- **THEN** no polygon is refused with `rule-scope`, `rule-unmapped` or `connect-scope`
