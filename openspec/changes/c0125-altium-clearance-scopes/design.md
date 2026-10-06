## Outcome in one paragraph

**One of the three public boards without a clearance in force is lifted from `UNVERIFIED` by this change, not three.** The eight public PCB documents hold 12 unmapped Clearance records in five forms ("Measured before"). Forms A (the matrix's own record) and B (a matrix cell with a layer condition) are exact in a neutral rule on a two-layer board; they are the three records of `altium-third-party-pcbdoc-03`, which gets a clearance in force and the level `INFERRED`. Forms C (a matrix of differing clearances), D (the option that ignores the pads of one footprint) and E (a scope function outside the grammar) are not exact in one neutral rule; they are the 9 records of `-02`, `-04`, `-06`, `-07` and `-08`, which stay as they were: `-02` and `-06` without a clearance in force, and all five `UNVERIFIED`. After this change 3 of the 7 documents of the copper test have no unread Clearance record (`-01`, `-03`, `-05`), and 2 of the 7 carry `INFERRED` (`-03`, `-05`; `-01` is `UNVERIFIED` for its internal planes).

## Context

- **Today.** `read.rules.map_rules` (c0042, widened by c0084) maps a `Clearance` record only with an empty `OBJECTCLEARANCES`, `IGNOREPADTOPADCLEARANCEINFOOTPRINT=FALSE`, no key outside its row and two scopes of the closed grammar, which holds no layer function. `AltiumBackend.design_rules` (c0088) counts the enabled Clearance records that stay unmapped; one such record makes the copper stage `UNVERIFIED`, and a document with no mapped record has no clearance in force.
- **What the model can say.** A neutral `Rule` of kind `clearance` holds one `min`, two selectors (`net`, `netclass`, `ref`, `layer`, `item_kind`, and `and`, `or`, `not` of those) and `layers`. `checks.clearance.ClearanceResolver` honours `layers`: a rule with layers is a candidate only for a pair judged on one of them (`_Candidate.matches`; `tests/unit/checks/test_clearance.py::test_rule_candidates`, and this change adds a test through `check_copper`). The item kinds of the check are track (arcs with them), via, pad and zone fill. The model cannot say "two pads of one footprint", "a through-hole pad" as opposed to a surface pad, or "an object that exists on a layer other than the one the pair is judged on".
- **Constraints.** Exact or not at all; every fact with a public source; no change of `checks/` and none of the neutral model; `copper.clearance` on KiCad boards as in 0.2.0.

## Measured before (2026-10-06, macOS, local corpus cache, no tool)

Every Clearance record of the eight public PCB documents (the seven rows with the use `altium-pcbdoc` and the heavy row `altium-third-party-pcbdoc-08`), read with `read.pcb.read_pcbdoc` and mapped with `map_rules` at the base commit. Counts and forms only: no net, class, footprint or layer name of a document is written here. 17 records, all enabled, all `NETSCOPE=DifferentNets` and `LAYERKIND=SameLayer`; 5 mapped, 12 not.

| document | copper layers | record (priority) | scopes | `GAP` | matrix | other keys | before |
|---|---|---|---|---|---|---|---|
| `-01` | 4 (2 planes) | 1 | all, all | 6 mil | empty | | mapped |
| `-02` | 4 (2 planes) | 1 | all, all | 5.9055 mil | 27 entries, 5 values (0, 6, 10, 15.748 and 21.6535 mil) | ignore flag `TRUE` | `keys` |
| `-03` | 2 | 1 | `OnMid`, `OnMid` | 5 mil | one space | cell keys, `INNERLAYERS=TRUE` | `keys` |
| `-03` | 2 | 2 | an `Or` of two `ExistsOnLayer`, the same on both scopes | 5 mil | one space | cell keys, `OUTERLAYERS=TRUE` | `keys` |
| `-03` | 2 | 3 | all, all | 10 mil | one space | `ISMATRIX=TRUE` | `keys` |
| `-04` | 4 | 1 | `HasFootprint`, all | 3.937 mil | empty | | `scope` |
| `-04` | 4 | 2 | all, all | 5.9055 mil | empty | | mapped |
| `-05` | 2 | 1 | all, all | 6 mil | empty | | mapped |
| `-06` | 2 | 1 | `InNet`, all | 11.811 mil | 8 entries, 3 values (0, 3.937 and 9.8425 mil) | ignore flag `TRUE` | `keys` |
| `-06` | 2 | 2 | all, all | 11.811 mil | empty | ignore flag `TRUE` | `keys` |
| `-07` | 4 | 1 | `InPolygon`, `InAnyDifferentialPair` | 15 mil | empty | | `scope` |
| `-07` | 4 | 2 | all, all | 3.5 mil | empty | | mapped |
| `-07` | 4 | 3 | all, all | 4 mil | empty | | mapped |
| `-08` (heavy) | 6 | 1 | `(IsVia AND InNet)`, all | 9.8425 mil | empty | | `scope` |
| `-08` | 6 | 2 | `(InNet or InNet)`, all | 5 mil | empty | | `scope` |
| `-08` | 6 | 3 | `(InDifferentialPairClass)`, all | 4 mil | 8 entries, 2 values (3.5 and 15 mil) | | `keys` |
| `-08` | 6 | 4 | all, all | 4 mil | 1 entry (via to via, 3.5 mil) | | `keys` |

"Cell keys" are `SOURCERULE=38` (the `ISMATRIX` record is the 39th and last rule record of the document, 38 counting from zero), `CELLROWNAME=All`, `CELLROWTYPE=0`, `CELLCOLNAME=All` and `CELLCOLTYPE=0`. The "ignore flag" is `IGNOREPADTOPADCLEARANCEINFOOTPRINT`. The lengths of the matrix entries are their counts read as 0.0001 mil.

The 12 unmapped records by form (a record is counted under the first reason the mapper gives):

| form | records | documents | what it says | exact in the neutral rule? |
|---|---|---|---|---|
| A. the matrix's own record: `ISMATRIX=TRUE`, blank matrix, all objects | 1 | `-03` | one clearance for every pair that no cell governs | yes: one `clearance` rule for all objects |
| B. a cell of the matrix with a layer condition on both scopes (blank matrix) | 2 | `-03` | one clearance for the pairs on the inner, or on the outer, layers | where the condition is every copper layer of the board, or applies to nothing (decision 4); not otherwise |
| C. a matrix of differing clearances | 4 | `-02`, `-06`, `-08` (2) | a clearance per pair of object kinds | no: one rule holds one value, and the kinds of the matrix (arc, track, surface pad, through-hole pad, via, fill, polygon, region, text, hole) are finer than the check's |
| D. the ignore flag alone | 1 | `-06` | the pads of one footprint are not judged against each other | no: no selector says "of the same component" |
| E. a scope outside the closed grammar | 4 | `-04`, `-07`, `-08` (2) | functions the grammar lacks; operators spelled `AND` and `or` | not by this change (Out of scope) |

**No public record holds an explicit uniform matrix.** In the four matrices no entry holds the length of its record's `GAP` (40000, 59055 or 118110 counts): a matrix lists the cells that differ from the generic value. The uniform matrix of the decision is, in the public files, the blank one of form A and B. The explicit form is mapped all the same (decision 2), because a text whose every entry equals `GAP` cannot say anything else, whatever the cells it leaves out hold.

## Decisions of the maintainer (2026-10-06)

Taken on the questions this change raised, after its first commit:

1. **Form C becomes change c0130** (`altium-clearance-matrix-cells`): a matrix of differing clearances is lifted as one neutral clearance rule per cell with `item_kind` conditions, where the neutral rule says the cell exactly; a cell without a counterpart is named. No conservative judging with the largest or the smallest entry.
2. **Form D is not in v0.4.** A record with the option that ignores the pads of one footprint stays unmapped and reported.
3. **The Altium step of task 5.4 is optional**, listed for the maintainer's second session of Altium work ("session 2"); the row `H-A-RULE-CLEARANCE-FORMS` stays `INFERRED` and pending until then.
4. **The slack of the unit becomes change c0131** (`altium-unit-slack-rule`): the 5 nm of c0088 are replaced by a stated rule, one file unit per item of the pair, and the 7 findings of `-03` and the 2 of `-01` are measured again under it. This change does not touch `UNIT_SLACK_NM`.

## Goals / Non-Goals

**Goals:**
- Forms A and B, and an explicit uniform matrix, give the clearance the record holds, exactly, and a clearance in force on the public document that holds them.
- Every form that stays unmapped says which one it is.
- The copper check and the import count the same records as mapped.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **Blank is empty.** `OBJECTCLEARANCES` of white space only holds no entry (three records of `-03` hold one space). It maps as the empty value does. Only for `Clearance`: the row of `BoardOutlineClearance` is not touched, no public record of that kind holds a blank value.
2. **A uniform matrix is one clearance.** Entries are `ClearanceObj_<kind>-ClearanceObj_<kind>:<count>` joined by `;`. A count is 0.0001 mil, the unit of the document's coordinates (2.54 nm): `INFERRED` from the four public matrices, whose eight distinct counts above zero are all round lengths in that unit (0.1, 0.25, 0.4 and 0.55 mm; 3.5, 6, 10 and 15 mil) and in no other plausible one; `rules.MATRIX_UNIT`. A matrix whose every entry holds the length of `GAP` to the nanometre maps to `GAP`. If the inferred unit were wrong, a matrix would be taken for uniform only if its counts equalled `GAP` in the wrong unit by accident; the hypothesis row says so. Any other text gives `keys`.
3. **The cell keys are a closed set of values.** `ISMATRIX` only `TRUE`; `CELLROWNAME` and `CELLCOLNAME` only `All`; `CELLROWTYPE` and `CELLCOLTYPE` only `0`; `INNERLAYERS` and `OUTERLAYERS` only `TRUE`; `SOURCERULE` any value. These are the values the one public document holds. They are bookkeeping of the Constraint Manager's matrix (S-0557: a matrix between net classes with a default entry for all classes, and a value per cell for all layers, the outer layers, the inner layers or one layer); the record's own scopes, `GAP` and `PRIORITY` say what it governs, as for any rule record (S-0286). A cell for a named class would hold another `CELLROWNAME`; no public file shows its scope text, so it is refused (`keys`) rather than guessed.
4. **A layer condition maps only where the neutral layer condition says the same.** The neutral condition is "the pair is judged on one of these layers". Altium's functions test an object: `OnMid` is true for an object on an internal signal layer (S-0555), `ExistsOnLayer('X')` for an object that exists on layer X, an object on Multi-Layer included (S-0556, and the note of S-0555 on objects with shapes on the top or bottom layer). The two differ for an object that the check judges on several layers, a via or a through-hole pad:
   - `ExistsOnLayer` of the layers S on both scopes governs a pair of two such objects on every layer, also outside S; a neutral rule with `layers = S` does not. **When S is every copper layer of the board there is no layer outside S**, so the rule with `layers` = the board's copper layers governs exactly the pairs of the record. That is the mapped case. For a proper subset the record stays unmapped (`scope`), and the detail names the layers left.
   - `OnMid`: the documentation does not say whether a via is "on" an internal signal layer (the entry of `OnOutside` says an object on Multi-Layer is not returned; the entry of `OnMid` says nothing). **On a board without an internal signal layer no object is on one**, whatever the answer: the rule applies to nothing. That is the second mapped case, reported with the reason `no-layer`. On a board with such a layer the record stays unmapped (`scope`).
   - An internal plane is no signal layer (`OnPlane` is another function, S-0555): `inner_signal` is true for the ids between the top layer's (1) and the bottom layer's (32), the mid layers of `pcb-records.md`, "Layers".
   - The rule keeps `layers` although it names every copper layer: it is what the record says, and it stays true if the model is later judged with more layers.
5. **Both scopes must hold the same condition.** A binary rule applies when one object matches the first scope and the other the second. With one layer condition and one other scope the rule would need a `layer` selector on one side, and the check gives both objects of a pair the same layer, so that selector could not tell the two sides apart as Altium does for a via. Refused (`scope`).
6. **Layer names are the document's.** `ExistsOnLayer` takes the layer's name as the layer list shows it (S-0556): the name of the board record, which the import keeps as `altium_name`. Compared letter for letter; a name that no copper layer or more than one holds is refused. The names reach the mapper as `CopperLayers`, built by `LayerMap.copper_layers()` in the import and by `adapter.layers.copper_layers_of` from the imported layers in the rules source of the copper check; a test holds the two equal.
7. **`no-layer` is a reason, not a rule.** `RuleMapping` keeps its invariant: every record is the source of a rule or one `Unmapped`. A record that applies to nothing gives no rule and must not count as an unread rule, so `rules.NOT_APPLYING` = {`disabled`, `no-layer`} replaces the backend's single reason. The import reports it in `altium.import.rule-unmapped` like any other reason (`no-layer 1`).
8. **Read only.** `rulemap.lower` writes one form per rule and none of these: a rule with `layers` stays `scope-unsupported` (the text of the reason now says that a layer condition is read from a PCB document and not written). Writing `ExistsOnLayer` for "every copper layer" would be exact only for the board it was read from, and a build's rule has no such board in hand. `Condition.read_only` marks the keys so that c0084's test of the table (every key of the reader is a key of the writer) keeps its meaning for the others.
9. **Priorities are kept.** A mapped record keeps its `PRIORITY`. An unmapped record of a higher priority may still govern pairs that a mapped one is judged with; that is what `copper.rules-incomplete` says today and it is not changed (c0088, "Found on 2026-10-06", point 4).
10. **Cut order.** First the explicit uniform matrix (no public record holds one), then the `no-layer` reason; never the count of the copper check.

## Files and public API

- `read/scope.py`: `LayerScope(inner, names)`, `parse_layer_scope(text) -> LayerScope | None`, `INNER_SIGNAL`, `EXISTS_ON_LAYER`. `parse_scope` is not changed.
- `read/rules.py`: `CopperLayer`, `CopperLayers`, `MATRIX_UNIT`, `matrix_problem`, `NOT_APPLYING`; `Condition.uniform_with` and `Condition.read_only`; the reason `no-layer`; `map_rules(..., layers=None)`.
- `rulemap.py`: `lift(..., layers=None)`; `EVIDENCE` names `H-A-RULE-CLEARANCE-FORMS`.
- `adapter/layers.py`: `LayerMap.copper_layers()`, `copper_layers_of(layers)`. `adapter/rules.py`: `import_rules(..., layers=None)`. `adapter/board.py` passes the layers. `backend.py`: `rules_from_bytes` maps with the layers of `design`; its `NOT_APPLYING` moved to `read.rules`.
- Tests: `tests/unit/backends/altium/read/test_rule_map.py` and `test_scope.py`, `tests/unit/backends/altium/adapter/test_rules.py`, `tests/unit/backends/altium/test_rulemap.py` (the table test reads `read_only`), `tests/unit/checks/test_copper.py`, `tests/corpus/test_altium_copper.py` (the pinned rule counts).

## Sources registered by this change

Block S-0555 to S-0559; pages of Altium's public documentation, all rights reserved, read for facts on 2026-10-06, nothing transcribed.

- S-0555: the page on layer checks of the query language (`OnMid`, `OnOutside` and its note on Multi-Layer, `OnPlane`).
- S-0556: the page on membership checks (`ExistsOnLayer` and its argument).
- S-0557: the page on the Constraint Manager (the clearance matrix between net classes, its default entry, values per layer set).
- S-0558: the Clearance section of the page on electrical rule types (one value is copied to every cell of the object matrix; the option that ignores pad-to-pad clearances within a footprint). The page is S-0462's, registered again for these two facts.
- S-0559 is not used.

The public documents are rows already registered: S-0172 (`-03`), S-0175 (`-06`), S-0176 (`-02`), S-0187 (`-08`).

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-RULE-CLEARANCE-FORMS | The forms of a Clearance record that c0125 maps say what the neutral rule says: a count of `OBJECTCLEARANCES` is 0.0001 mil and a cell the text leaves out holds the generic value; the keys of a matrix cell add nothing to the record's scopes and `GAP`; `ExistsOnLayer` of every copper layer on both scopes governs every pair of copper objects; `OnMid` matches nothing on a board without an internal signal layer | kit request (an author report on a document with a clearance matrix: the pairs Altium's rule check reports for each of the three rules) | Altium reports each planted pair under the rule that the neutral mapping gives it, and none under the inner-layer rule on a two-layer board |

Starts `INFERRED`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06).

## Measured after (2026-10-06, macOS, local corpus cache, no tool)

`tests/corpus/test_altium_copper.py` (14 tests: 13 passed, `altium-set:01` skipped as heavy; `FENOLITE_HEAVY=1` was not set: the heavy document `-08` is no row of that test, and its four records are measured above with the readers alone).

Clearance records: 7 mapped (5 before), 1 that applies to nothing, 9 unmapped (12 before). Only `-03` moves:

| | before | after |
|---|---|---|
| Clearance records mapped, applying to nothing, unmapped | 0, 0, 3 | 2, 1, 0 |
| clearance rules of the check | none | 5 mil on `F.Cu` and `B.Cu` (priority 2); 10 mil for all objects (priority 3), which governs no copper pair |
| pairs judged | 1 087 | 3 204 |
| pairs judged for shorts only | 954 | 0 |
| zones without a clearance | 1 | 0 |
| `copper.short`, `copper.clearance` | 0, 0 | 0, 7 |
| findings the unit's slack removes | 0 | 359 |
| issues that lower the level | `copper.rules-incomplete` (3 records; 1 pour) | none |
| level, status | `UNVERIFIED`, `ok` | `INFERRED`, `errors` |

- **The 7 findings are one class and are real by the document's own numbers.** Each is a square through-hole pad and a track on the bottom layer, 126 991 or 126 992 nm apart against the rule's 127 000 nm (5 mil): 8 to 9 nm short, 3.5 units of the document. The pads are 637 795 units wide, an odd number, so their edge lies on half a unit, and the nearest track edges stand about 49 996.5 units from it, against the 50 000 of the rule. No rounding of the import explains it (the slack of the unit is 5 nm and covers 1 to 4 nm, as on the other documents); `-01` holds the same class (two pairs 9 and 20 nm short, recorded by c0088). Whether Altium's own check tolerates such a gap is not known. They are recorded, not allowed for: `UNIT_SLACK_NM` is not changed here (change c0131 replaces the constant by a stated rule and measures these pairs again).
- **`-02` and `-06` keep no clearance in force.** `-02`: its one record is a matrix of differing clearances with the ignore flag. `-06`: one record with a net scope and a matrix of differing clearances, and one with the ignore flag alone. Both forms are outside what the neutral rule says (table above, C and D).
- **`-04`, `-07` and `-08`** are unchanged: their unmapped records are of form C and E.
- **RT-A3** (`tests/corpus/test_altium_rta3.py`, the rows that are not heavy): `-03` is still equal inside the scope; the rule with `layers` is one more model item that the rewrite does not hold (`rule 1`), named `scope-unsupported`.

## Out of scope, with what each would need

- **A matrix of differing clearances (form C).** The neutral rule holds one value. A matrix whose differing cells are kinds the check tells apart (via to via, as the second matrix of `-08`) could be said by two neutral rules with `item_kind` selectors; cells for a through-hole pad as opposed to a surface pad, for a polygon as opposed to a fill or a region, for text and for holes could not. That is a mapping of one record to several rules with an order among them, larger than a correction. **Decided on 2026-10-06: change c0130 lifts the cells that are exact; no conservative judging.** The question was: Judging a matrix with its largest entry would report pairs that the document allows (false findings); with its smallest it would pass pairs the document forbids, which a check must not do silently. Either is an approximation that the stage would have to mark (`UNVERIFIED`, as now). Not implemented.
- **The ignore flag (form D).** It can be said exactly, by one rule of severity `ignore` per component (`and(item_kind pad, ref R1)` on both sides) above the clearance; that needs the board's components at mapping time and adds rules the document does not hold. It would give `-06` its second record, not its first. Not implemented. Decided on 2026-10-06: not in v0.4.
- **Scopes (form E).** `HasFootprint`, `InPolygon`, `InAnyDifferentialPair`, `InDifferentialPairClass` have no neutral selector. `AND` and `or` in other letter case are refused by the closed grammar of c0042 (no permitted source registered there says that the language ignores case); widening the grammar belongs to that capability.
- **Layer conditions that stay unmapped** (decision 4): a subset of the copper layers, and `OnMid` on a board with internal signal layers. Both need to know how Altium's rule check treats a via and a through-hole pad for a layer function, which is the kit request of the hypothesis.
- **`OnLayer`, `OnOutside`, `OnTopLayer` and the other layer functions.** No public record holds one in a Clearance rule.
- **`BoardOutlineClearance` with a blank or uniform matrix.** No public record; the copper check does not read the kind.

## Size (design-days)

| group | dd |
|---|---|
| measurement and proposal | 0.25 |
| matrix and cell keys | 0.25 |
| layer conditions and the board's layers | 0.5 |
| measurement after, pages | 0.25 |

Total: 1.25. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-project-reader`, "Rules onto the neutral model": MODIFIED from the text of c0084's delta (`openspec/changes/c0084-altium-rule-lowering/specs/altium-project-reader/spec.md`), which already modifies the living requirement and is not archived. "More forms of a Clearance record" is ADDED. "Closed scope grammar" is not modified: `parse_scope` refuses every layer function as before.
- `altium-import`, "Rules where they map": MODIFIED from the living text of `openspec/specs/altium-import/spec.md`; no active change holds a delta for it.
- `altium-verification`, "Copper check on Altium boards" and "Clearance rules of a PCB document": both are ADDED by c0088, which is not archived; MODIFIED here from c0088's delta.
- The deltas are written by a script that asserts each sentence it replaces. Archive order: c0084, c0088, then this change.
