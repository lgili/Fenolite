## Outcome in one paragraph

**This change lifts one Clearance record of the public corpus, on the heavy document `altium-third-party-pcbdoc-08`. It does not move `-02` or `-06`, which the decision also named.** Of the four records with a matrix of differing clearances, two hold cells that the copper check cannot tell apart (and the option that ignores the pads of one footprint, which is not in v0.3), one has a scope outside the grammar, and one is exact and lifted. No level changes: `-08` goes from "no clearance in force" to "a clearance in force for every pair", and stays `UNVERIFIED` for its three unread records.

## Context

- **Today (c0125).** `read.rules.matrix_problem` accepts a blank matrix and one whose every entry equals `GAP`; any other matrix is refused (`keys`).
- **What the model and the check can say.** A neutral selector has `item_kind`, and `checks.clearance` gives a copper item the kinds `track` (a track or an arc), `via`, `pad` and `zone` (the fill of a zone); `_Candidate.matches` applies a rule with two selectors to a pair when one item matches each, in either order. So a cell "via against via" or "track against polygon" is one rule. The check has no kind for an arc as opposed to a track, none for a through-hole pad as opposed to a surface pad, and holds no item for a free fill, a free region (the import keeps them as graphics), text or a hole.
- **Order of rules.** `checks.clearance.rule_precedence` orders rules by priority and, within one priority, by name; the later one governs. Neither file under `checks/` that judges is changed (another session's c0097 edits `checks/copper.py`).

## Measured before (2026-10-07, macOS, local corpus cache, no tool; the heavy row with `FENOLITE_HEAVY=1`)

The four Clearance records of form C of c0125. Object kinds are those of the entries; values are counts read as 0.0001 mil. No name of a document is written.

| document | record | scopes | `GAP` | entries | per pair of item kinds | other blocking key | result |
|---|---|---|---|---|---|---|---|
| `-02` | priority 1 | all, all | 5.9055 mil | 27: arc and track against arc, track, through-hole pad, via, text, hole; through-hole pad against itself; via against via; every copper kind against text and hole | track to pad and pad to pad are mixed: a through-hole pad holds 15.748 or 21.6535 mil where a surface pad holds the generic value | ignore flag `TRUE` | unmapped (`keys`) |
| `-06` | priority 1 | a net, all | 11.811 mil | 8: arc and track against fill, polygon and region; surface pad against polygon; polygon against region | track to zone is mixed: an arc holds 0 against a polygon and a track 9.8425 mil; pad to zone is mixed (surface pad 9.8425 mil, through-hole pad generic) | ignore flag `TRUE` | unmapped (`keys`) |
| `-08` | priority 3 | a differential-pair class, all | 4 mil | 8: arc, track, surface pad, through-hole pad, via, fill and polygon against polygon at 15 mil; via against via at 3.5 mil | all uniform: 5 cells; 1 entry for a fill | the scope function | unmapped (`scope`) |
| `-08` | priority 4 | all, all | 4 mil | 1: via against via at 3.5 mil | uniform: 1 cell | none | **lifted** |

So the premise "form C on `-02`, `-06` and `-08` is lifted" holds for one record of four. `-02` and `-06` each fail twice: a cell without a counterpart, and form D.

## Goals / Non-Goals

**Goals:**
- A matrix that is exact in item kinds gives the rule of `GAP` and one rule per cell, in force in the right order.
- A matrix that is not exact says which pairs of item kinds are the reason.
- The stage counts the cells it judges and those it does not.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **Object kinds to item kinds** (`rules.MATRIX_KINDS`): `Arc`, `Track` → `track`; `SMDPad`, `THPad` → `pad`; `Via` → `via`; `Poly` → `zone`; `Fill`, `Region`, `Text`, `Hole` → none. `Poly` is the poured copper of a polygon, which the import reads as the fills of a zone; a free fill and a free region are graphics in the model ("What is not imported" of `docs/altium.md`), so the check holds no item for them. `INFERRED` (`H-A-RULE-CLEARANCE-CELLS`).
2. **A pair of item kinds is exact when all its object-kind pairs hold one value.** The value of a pair is its entry or, without one, `GAP` (c0125, `H-A-RULE-CLEARANCE-FORMS`). `track to track` covers arc-arc, arc-track and track-track; `track to pad` four pairs; and so on over the ten pairs of the four item kinds. A uniform value that differs from `GAP` is a cell; one equal to `GAP` needs no rule.
3. **One mixed pair refuses the record.** If `track to pad` is mixed, a rule for it cannot be written, and the rule of `GAP` alone would judge a track against a through-hole pad with the generic value where the record holds another: an approximation. So the record stays unmapped with the reason `keys` and a detail that names every mixed pair. "Exact or not at all" is kept for the record as a unit.
4. **A cell rule.** `kind` `clearance`, `min` the value (0 is kept: the resolver reads a governing rule of 0 as "no clearance asked", and shorts are still judged), name `<NAME>/<a>-<b>`, the record's priority, layers and native id, selectors `item_kind a` and `item_kind b`, each joined by `and` with the record's scope on its side. A record with two different scopes gets a second rule with the kinds exchanged for a cell of two different kinds, because Altium applies a binary rule in either order of the objects and each side of a neutral rule holds one kind. It governs above the rule of `GAP`: same priority, and its name is the record's name with a suffix, which `rule_precedence` puts later. Priorities of other records stay strictly above or below, because a priority is one record's within the kind (`H-A-RULE-PRIORITY`).
5. **What the stage does for a cell without a counterpart, and why it is not scoped to pairs.** The request was to make the rules incomplete only for the pairs the cell would govern, if the stage can scope that. It cannot without one of two things that are refused here: (a) a rule of severity `ignore` for the mixed pair, which would leave exactly those pairs unjudged, but puts a rule into the import that the document does not hold and that a KiCad export of the import would write as "do not check" (the reason the maintainer gave against form D); or (b) a change of `checks/copper.py` so that a rules source can name unjudged pair kinds, which this change may not make. So the stage does what c0088 specifies for an unread Clearance record: the record is counted in `summary.rules.opaque_clearance_rules`, the stage reports `copper.rules-incomplete` and carries `UNVERIFIED`, and the pairs are judged with the other rules that were read, or for shorts only when none applies. The detail of the import's reason and `summary.clearance_cells.unjudged` say how much was left. **Open decision for the maintainer:** allow (b) in a later change, after c0097 has landed, as `DesignRules.unjudged_pairs`; no public record needs it while form D is out (both mixed matrices of the corpus also carry form D).
6. **Entries for a kind without an item** (`Fill`, `Region`, `Text`, `Hole`) do not refuse the record: they govern no pair that the check judges, with or without a matrix, exactly as the plain record of c0084 says nothing about them. They are kept as written in the bag of the rule of `GAP` (`cells_not_lifted`) and counted as unjudged. They lower nothing by themselves.
7. **Counts.** `RuleMapping.matrix_cells` per record; `DesignRules.clearance_cells` = (judged, unjudged) summed; `summary.clearance_cells` on document input (`checks/documents.py`, which already adds `unpoured` and `zones_unjudged`). A cell is an entry of the text. The KiCad stage (`checks.copper.copper_stage`) and its summary are not changed.
8. **Bag keys.** `cell` and `cells_not_lifted` join the closed table `adapter.ids.EXT_KEYS`; the adapter copies the pairs the mapper gave beside the record text, so it still holds no rule table. The native id of a cell rule ends with the cell, so that the rules of one record differ.
9. **Read only.** `rulemap.lower` writes an empty matrix. A cell rule read from a document and written again is reported `scope-unsupported` (`item_kind`), and the rule of `GAP` is written: the rewrite says so in `not_lowered`.
10. **Cut order.** First the scoped record (no public record that maps has a scope), then the bag of unlifted entries; never the count in the summary.

## Files and public API

- `read/rules.py`: `ITEM_KINDS`, `MATRIX_KINDS`, `Matrix`, `read_matrix`, `CELL_PAIR`, `UNJUDGED_PAIR`; `Condition.matrix_with` (was `uniform_with`); `KindMap.cells`; `RuleMapping.matrix_cells`; `matrix_problem` is now `read_matrix`'s refusal.
- `adapter/rules.py`: the bag and native id of a cell rule. `adapter/ids.py`: two keys. `backend.py`: `DesignRules.clearance_cells`.
- `backends/base.py`: `DesignRules.clearance_cells: tuple[int, int] = (0, 0)`. `checks/documents.py`: `summary["clearance_cells"]`.
- `rulemap.py`: `EVIDENCE` names `H-A-RULE-CLEARANCE-CELLS`.
- Tests: `tests/unit/backends/altium/read/test_rule_map.py`, `adapter/test_rules.py`, `tests/unit/checks/test_document_copper.py`, `tests/corpus/test_altium_rule_kinds.py`, `tests/corpus/test_altium_copper.py` (the heavy row joins it).

## Sources registered by this change

None new: the block S-0590 to S-0594 is not used. The object kinds of the matrix and the simple view that joins arc with track and fill, polygon and region are on the page of S-0558 (registered by c0125; its row now names these facts too). The entries are those of S-0175, S-0176 and S-0187.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-RULE-CLEARANCE-CELLS | The object kinds of a Clearance matrix are the copper items of the import: `Arc` and `Track` a track or an arc, `SMDPad` and `THPad` a pad, `Via` a via, `Poly` the poured copper of a polygon; `Fill`, `Region`, `Text` and `Hole` are objects the copper check holds no item of. A cell governs a pair of those kinds above the record's generic value and below every rule of a higher priority | kit request (author report: a board with a via-to-via cell below the generic value and a pair of vias between the two values) | Altium's rule check reports no violation for the pair of vias, and one for a via and a track at the same distance |

Starts `INFERRED`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-07).

## Measured after (2026-10-07, same machine)

`FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_rule_kinds.py tests/corpus/test_altium_copper.py -k "not parity"`: 27 passed.

| document | | Clearance records mapped, unread | clearance rules of the check | cells judged, unjudged | pairs judged | shorts only | zones without a clearance | shorts, clearance findings | level |
|---|---|---|---|---|---|---|---|---|---|
| `-02` | before and after | 0, 1 | none | 0, 27 | 553 | 553 | 11 | 0, 0 | `UNVERIFIED` |
| `-06` | before and after | 0, 2 | none | 0, 8 | 250 | 231 | 10 | 0, 0 | `UNVERIFIED` |
| `-08` | before | 0, 4 | none | (0, 9) | 26 240 | 22 413 | 33 | 28, 0 | `UNVERIFIED` |
| `-08` | after | 1, 3 | 4 mil for all objects; 3.5 mil via to via | 1, 8 | 60 253 | 0 | 0 | 28, 17 | `UNVERIFIED` |

The findings of `-08`, by class (the check lowers a rule by 5 nm, `UNIT_SLACK_NM`; "short of the rule" is against the document's value):

- **16 clearance findings 8 to 13 nm short of the rule**: 6 track to track, 8 track to via and 1 pad to track against 4 mil, and 1 via to via against the 3.5 mil cell. The class of the 7 findings of `-03` and the 2 of `-01`: copper that the document holds a few units closer than the rule's value. Change c0131 states the rule for that slack and measures these again. Not allowed for.
- **28 shorts and 1 clearance finding (a track 33.9 µm inside 4 mil) that involve a via on an inner layer: a limit of the import, listed, not a finding of the board.** They are 7 vias against the pours of another net on each of the four inner layers, and one track beside such a via. For every one of the 28, the pour's copper stands at the via's drill radius plus the generic clearance from the via's centre (203 196 to 203 198 nm against 101 600 + 101 600), to the rounding of the pour's points: the pour was made around the via's hole, not around its pad. The import gives a via its one diameter on every layer of its span, so the pad it draws on the inner layer meets the pour. All these vias have the long form of the via record (335 bytes; 123 of the 1 770 vias) with the simple stack mode and 32 equal diameters; what the nine further bytes say is in no fact Fenolite holds. The shorts do not depend on a clearance rule and were there before this change; they were not seen because the heavy document was in no copper test. `tests/corpus/test_altium_copper.py::test_known_false_findings_of_padless_vias_c0132` pins the class and its numbers. **Follow-up: change c0132** ("Known false findings").
- Three Clearance records of `-08` stay unread (two scopes with `AND` and `or`, one differential-pair class), all of a higher priority than the lifted one: pairs they govern are judged with the lifted rule, which is what `copper.rules-incomplete` says.

## Known false findings

`fenolite check` reports 29 FALSE findings on `altium-third-party-pcbdoc-08` (28 `copper.short` and 1 `copper.clearance`): seven vias have no pad on the four inner layers, the pours of other nets were made around their holes, and the import draws each via's one diameter on every layer of its span, so the pad it invents meets the pour. They are a defect of the import, not of the board; the follow-up change c0132 is to read the fact that makes a via padless on a layer. They were measured by this change and are older than it: a short does not depend on a clearance rule, and the heavy document was in no copper test before. `tests/corpus/test_altium_copper.py::test_known_false_findings_of_padless_vias_c0132` pins their number and their cause, and says in its name that they are false.

## Out of scope, with what each would need

- **Scoping the incompleteness to pairs** (decision 5): a field of `DesignRules` that `checks/copper.py` reads.
- **The option that ignores the pads of one footprint** (form D): not in v0.3.
- **`Hole` cells as `hole_clearance` rules**: another neutral kind, which c0084 leaves without a counterpart; the copper check judges no hole.
- **A via without a pad on an inner layer** (the 28 shorts of `-08`): a format fact for the long via record, then the import and the board frame. It is a defect of the import that this measurement found, older than this change.
- **Scopes with `AND` and `or`**, `InDifferentialPairClass`: the closed grammar of c0042.

## Size (design-days)

| group | dd |
|---|---|
| measurement and proposal | 0.25 |
| matrix cells and rules | 0.5 |
| counts, measurement on the heavy row, pages | 0.25 |

Total: 1. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-project-reader`: "More forms of a Clearance record" and "Rules onto the neutral model" are MODIFIED from the text of c0125's delta (this branch; not archived); "Cells of an object matrix" is ADDED.
- `altium-import`, "Rules where they map", and `altium-verification`, "Copper check on Altium boards" and "Clearance rules of a PCB document": MODIFIED from c0125's delta.
- `backend-protocol`, "Design rules source": MODIFIED from c0088's delta, which modifies the living requirement and is not archived.
- Written by a script that asserts each sentence it replaces. Archive order: c0084, c0088, c0125, then this change.
