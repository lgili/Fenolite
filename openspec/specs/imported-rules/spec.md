# imported-rules Specification

## Purpose
TBD - created by archiving change c0352-import-project-rule-semantics. Update Purpose after archive.
## Requirements
### Requirement: Import preserves native rule origin semantics

A supported KiCad project import SHALL preserve modeled Default and named netclasses through the existing DSL, preserve native hard floors through the declared digest-bound project carrier, and emit custom-rule DSL rows only for actual source custom rules. It SHALL preserve both native Pro floors and DRU overrides when both are present. Existing authored DSL minimum lowering SHALL remain unchanged.

#### Scenario: Project floor below named class

- GIVEN native min_clearance 0.0762 mm and a named class clearance 0.2032 mm
- WHEN importing and rebuilding
- THEN no invented unconditional clearance override replaces the native class/floor precedence

### Requirement: Native-context floor comparisons are explicit and traced

Path-based level6 comparisons with supported native project contexts SHALL compare the five supported floor values without removing existing canonical differences, and SHALL bind every consumed context input into hashes and write-plan dependencies. Pure Design comparisons SHALL make no independent native-floor equality claim.

#### Scenario: Tampered floor below every class

- GIVEN two otherwise equal supported projects whose hard floor values differ below every netclass value
- WHEN path-based level6 comparison runs
- THEN it reports the exact floor difference even though effective canonical class values remain equal

### Requirement: Native class comparison names its supported scope

After option B approval, path-based level6 SHALL additionally compare the seven supported modeled class length fields and effective class assignments using verified native numbered-pad partitions, without comparing raw escaped JSON strings or claiming unknown native class properties. Relevant ambiguity, malformed/inexact values, duplicate identity or unsupported aggregation SHALL not yield full native-context equality.

#### Scenario: Native class field changes below an unchanged floor

- GIVEN equal native projects with Default clearance 0.15 mm versus 0.2 mm and the same lower floor
- WHEN native-context level6 compares the projects
- THEN it reports a supported native netclass field difference

### Requirement: Imported rules keep the source's rank
The importer SHALL write custom rules in the source's order of precedence (change c0409, B4).
- A custom rule MUST become `design.rules.minimum()` only where the minimum keeps its rank: a board-wide rule that is the first of its kind with no other of priority 0, or a class rule that is the last of its kind with no other of priority 1.
- Any other one-sided rule MUST be `design.rules.rule()` with `where=` and no `between`, and its priority.
- A rule whose name Fenolite wrote (`fenolite_<p>_<name>`) MUST get the priority `p` when the numbers of all rules give the file's order within each kind; otherwise it MUST get the reader's priority.

#### Scenario: A class x All rule ranked below a pairwise rule
- **GIVEN** an authored design with a pairwise clearance `PWR` to `LED_A` of priority 1 and a one-sided clearance of class `PWR` of priority 2, built for Altium
- **WHEN** `uv run pytest tests/unit/importer/test_altium_rule_rank.py -q` imports it to Python and builds the code for KiCad
- **THEN** no `minimum()` names a class, the one-sided rule is `rule(where=select.netclass("PWR"), priority=2)`, the pairwise one has `priority=1`, and in the `.kicad_dru` the pairwise rule comes after the class rule

#### Scenario: Written numbers that disagree with the file order
- **WHEN** the rules' written numbers do not give their order in the file
- **THEN** the reader's priorities are kept

### Requirement: Rules scoped to items without a net
An Altium rule scope `InNet('No Net')` SHALL import as the selector of items without a net, `not(net "*")`, not as a net named "No Net" (change c0409, B7).

#### Scenario: A clearance between netless items and a class
- **GIVEN** an authored Altium clearance record `InNet('No Net')` x `All`, and a KiCad project built from a script with `design.rules.rule("netless", "clearance", where=select.no_net(), min=mm(0.3))`
- **WHEN** `uv run pytest tests/unit/importer/test_no_net_rule.py -q` maps the record and imports the project to Python
- **THEN** the record maps, with no unmapped record, to a rule on `not(net "*")` that the code writes as `select.no_net()`, and the imported code holds `where=select.no_net()` with nothing unexpressed about the rule

### Requirement: Rules scoped to items in no net
The Altium scope reader SHALL read `InAnyNet` as the selector of any net (`net *`), so that `Not InAnyNet` is `model.rules.NO_NET` and a scope such as `IsPad And (Not InAnyNet)` maps without a `scope` refusal (change c0420, B7; S-1680). The Altium rule writer SHALL lower `net *` to `InAnyNet`, so a rule scoped to `NO_NET` is written as `Not InAnyNet`.

#### Scenario: A netless pad scope
- **WHEN** `uv run pytest tests/unit/importer/test_no_net_rule.py -k any_net -q` maps a Clearance rule scoped `IsPad And (Not InAnyNet)`
- **THEN** the rule maps with no unmapped record and its first selector is `and(item_kind pad, NO_NET)`

#### Scenario: A netless pad scope written to Altium
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap.py -k without_a_net -q` lowers a rule on pads in no net
- **THEN** its scope is written as `IsPad And (Not InAnyNet)` and reads back as the same selector

### Requirement: Altium rooms are rule areas
An Altium import SHALL read each room of the document (a Room Definition record: `read.rooms`) as a neutral rule area of the room's name, its outline and the copper layer of its side, that restricts nothing (change c0462).

- Only a room whose `LAYER` is `TOP` or `BOTTOM` and whose outline is straight edges MUST give a rule area; its provenance MUST be the room's record (`Rules6/Data#<index>`).
- The room's record MUST stay a kept record (c0434): an Altium write gives it back as it was read, and the Altium writer MUST count the room's rule area `changed` under `keep-out`, not lost, and write no keep-out region for it.
- `RuleSubject.areas` and the `area` leaf MUST keep their meaning: `WithinRoom` stays refused (`altium-project-reader`, `room-membership`), because a pad or a via is in a room by its centre and any other object only wholly within it (S-2212).
- That a document's room record holds the keys of the public rule file's rooms (S-0297) is `INFERRED` (`H-A-RD-ROOM`).

#### Scenario: A rule within a room
- **GIVEN** authored records: the room `PWR` on the top side, a room on no side, a room with an arc, and a Clearance rule scoped `WithinRoom('PWR')`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rooms_c0462.py -q -n 0` imports it
- **THEN** the design holds the one rule area `PWR`, on `F.Cu`, restricting nothing, its provenance the room's record; the scope is refused `room-membership`; and the Altium writer counts the area `changed`, not lost

