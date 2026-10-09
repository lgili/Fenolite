## Context

- **Today.** `altium-pcb-writer`, "Design rule records": Clearance, Width and RoutingVias, one `All` rule and one per net class. `docs/altium.md`: "only three kinds of rules"; script rule minimums give `altium.not-lowered` with `where` `design-rules`. `read/rules.py` maps the same three and lists `PENDING_KINDS = {"BoardOutlineClearance": "edge_clearance"}`.
- **The neutral rules** (`model/rules.py`, c0071): clearance, track width, via size, edge clearance, hole size, and the six kinds `hole_to_hole`, `hole_clearance`, `annular_width`, `courtyard_clearance`, `silk_clearance`, `creepage`, each with a selector (all, net class, net, layer, pairs).
- **Public facts available.** Altium's documentation describes every rule kind, its constraint and the rule file export; the KiCad importer's reading of rule records is registered (S-0160, S-0161, facts only); c0042 recorded the text form of rule files in `docs/formats/altium/rule-file.md` from public corpus files.
- **Constraints.** A rule Fenolite cannot express exactly is never written approximately: a wrong rule is worse than a missing one, because Altium's check would pass a board the script forbids.

## Goals / Non-Goals

**Goals:**
- Every neutral rule either reaches the PCB document exactly or is named, with its reason, in an issue and in the build result.
- The same table drives the writer and the reader, so the two cannot disagree.
- The maintainer can confirm in one session that Altium shows and applies the rules.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **One table, `rulemap.TABLE`.** Rows: neutral kind, Altium rule kind, constraint fields, scope forms supported, and `exact` or a reason of the closed set `no-counterpart`, `scope-unsupported`, `value-unsupported`, `unit-loss`. Mapping after task 1.1 ("Found on 2026-10-06"): clearance → Clearance; track width → Width; via diameter and via drill → RoutingVias; edge clearance → BoardOutlineClearance; hole size → HoleSize; hole to hole → HoleToHoleClearance; annular width → MinimumAnnularRing; silk clearance, courtyard clearance, hole clearance and creepage → `no-counterpart`.
2. **Scopes.** A selector becomes a scope expression of c0042's closed grammar: `All`, `InNet`, `InNetClass` and their conjunction. A clearance rule with a second selector uses both scope fields. Any other selector, and a layer, gives `scope-unsupported` for that rule only.
3. **Priorities.** Rules of one kind are written from the most specific to the least, as the neutral rules order them, and the priority field follows that order; the facts page records how Altium orders them.
4. **Exactness.** A value that Altium's field cannot hold (below its resolution, a range where Altium has one number, or one number where Altium's record holds a range) gives `value-unsupported`. Rounding to the PCB unit (1/10 000 mil = 2.54 nm) within 2 nm is exact, as everywhere in the PCB writer.
5. **Reader.** `read/rules.py` maps every `exact` row back; `PENDING_KINDS` becomes empty for the kinds of the table. Other kinds stay opaque and counted ("Rules kept opaque").
6. **Rule file.** `rulemap.write_rule_file(rules)` writes the form that `read_rule_file` reads, from the same table; `export --altium-rul` writes `<stem>.RUL`. It is offered because the PCB Rules editor can import it into an existing board: a user who keeps his own PcbDoc gets the script's rules without a rebuild.
7. **Cut order.** First the rule file export, then pair scopes, never the single-scope kinds and the reader.

## Files and public API

- `src/fenolite/backends/altium/rulemap.py`: `TABLE`, `RuleRow`, `NOT_LOWERED_REASONS`, `KIND_ORDER`, `lower(rules) -> Lowered(records, not_lowered)`, `lift(records) -> (rules, opaque)`, `same_rules`, `write_rule_file`, `EVIDENCE`.
- `src/fenolite/backends/altium/read/rul.py`: the constants `RULE_FILE_COMMON` and `WRITTEN_END`.
- `src/fenolite/backends/altium/pcbdoc.py`: `PcbDocSpec.design_rules`.
- `src/fenolite/exports/altium_rul.py`: the kind `altium-rul` (`export_rules`).
- `tests/corpus/test_altium_rule_kinds.py`.
- Tests: `tests/unit/backends/altium/test_rulemap.py`, `tests/unit/lens/test_altium_rules.py`, `tests/unit/exports/test_altium_rul.py`, `tests/kicad/altium/test_rules_oracle.py`.

## Sources registered by this change

- S-0160, S-0161 (registered; facts only): how the KiCad importer reads rule records.
- c0042's rows for rule files (`docs/formats/altium/rule-file.md`).
- New: Altium's public documentation pages of each rule kind of the table and of the rule import and export dialog (read for facts).

Registered on 2026-10-06 from the block reserved for this change (S-0460 to S-0469): S-0460 (manufacturing rule types), S-0461 (placement rule types), S-0462 (electrical rule types: creepage, the hole row of the clearance matrix). The rule import and export dialog is S-0294, already registered. The keys of the records come from the corpus sources S-0172, S-0174, S-0175, S-0176, S-0187, S-0188, S-0199, S-0200 and S-0297, already registered. Sources under a copyleft or an all-rights-reserved licence are read for facts only; nothing is transcribed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-RULE-KINDS | Each `exact` row of `rulemap.TABLE` names an Altium rule kind whose constraint is the neutral rule's, with the fields the table lists | author report, Part U steps U1–U3 | the PCB Rules editor lists every written rule under the kind of the table, with its value |
| H-A-RULE-SCOPE | The scope expressions Fenolite writes (`All`, `InNet`, `InNetClass` and their conjunction; a second scope for Clearance) are shown and applied by Altium as written | author report, Part U step U4 | each rule's scope in the editor equals the expression written, and among the written kinds the rule check names only the two planted rules |
| H-A-RULE-PRIORITY | Among rules of one kind, the one written with the higher priority wins where two scopes overlap | author report, Part U step U5 | the planted track inside the class takes the class width, not the `All` width |
| H-A-RULE-READBACK | The rules Fenolite reads from a PCB document it wrote equal the rules of the design for every `exact` row | `tests/unit/lens/test_altium_rules.py::test_readback` | equal for every example script and for the generated rule sets |
| H-A-RULE-FILE | A rule file written by `rulemap.write_rule_file` is imported by the PCB Rules editor and gives the same rules as the PCB document's | author report, Part U step U6 | import succeeds without a message and the rule list equals that of U1 |

All start `INFERRED`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06).

## Author report: Part U, rules

Files: the folder `rules`, the routed sample of Part C built with one rule of every `exact` kind, the net class `PWR`, and two planted violations (the `VIN` tracks narrower than their class width, the two pads of `R1` closer than a clearance between their nets), plus `routed.RUL`. The steps with their file hashes are in `docs/evidence/altium-pcb.md`, "Part U"; the wording there is the one to follow.

1. U1: open the project and the PCB document; open Design » Rules. Expected: one entry per written rule, under the kinds of the table in `docs/altium.md`.
2. U2: for each entry, compare the value with the table sent with the files. Expected: equal.
3. U3: confirm that no kind shows only Altium's default rule where the table says a rule was written.
4. U4: read each entry's scope text; run Tools » Design Rule Check with the default report. Expected: the scopes as written; among the written kinds, violations that name only the two planted rules (their number is reported, not expected).
5. U5: select the planted narrow track and read which Width rule the violation names. Expected: the class rule.
6. U6: in a copy of the board, delete the rules of one kind, import `rules.RUL` from the rules editor, and compare the list with U1. Expected: equal.

The maintainer reports one generic outcome per step (`as expected`, or what differed in one sentence), the tool as `AD <major>.<minor>` and the date. No file that Altium wrote is committed. A step that fails refutes the row it names: the row keeps its id and gets a registered successor (`verification-evidence`, "Refuted rows keep their id"). An author report never moves an operation out of `experimental` ("Author reports never promote an operation").

## Size (design-days)

| group | dd |
|---|---|
| entry, facts and sources | 0.75 |
| rule map and records | 2 |
| scopes and priorities | 1 |
| reader | 0.75 |
| build integration and issues | 0.75 |
| rule file export | 0.75 |
| oracle, sample, report, docs | 0.75 |
| closing | 0.25 |

Total: 7. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-pcb-writer`, "Design rule records" and `altium-build`, "Rule minimums in an Altium build": superseded; task 0.1 writes them as MODIFIED from the living text.
- `altium-project-reader`, "Rules onto the neutral model": its list of mapped kinds grows (MODIFIED at task 0.1).
- `cli-contract`, "Export command": the flag `--altium-rul` (MODIFIED; found at task 3.2).
- Archive order: before c0088 (which reads the rules for its check) and before c0090 (which compares them).

## Found on 2026-10-06 (tasks 0.1 and 1.1), and what changed

The proposal was written from a survey. Reading the code and the public sources changed these points; the specs, the tasks and the decisions above follow the list.

- **The mapping (Decision 1).** Seven rows are `exact`: Clearance, Width, Routing Via Style (two neutral kinds), Hole Size, Board Outline Clearance, Hole To Hole Clearance and Minimum Annular Ring. The keys of the four kinds that c0038 did not write are not in Altium's documentation; they are those of the rule records of the eight public PCB documents and the public rule file of the corpus manifest, read with Fenolite's own readers (`docs/formats/altium/pcb-copper.md`, "Rule kinds lowered"). So `PENDING_KINDS` is empty: the keys of `BoardOutlineClearance`, which c0042 could not source, are in five public documents.
- **`silk_clearance` and `courtyard_clearance` are `no-counterpart`**, not mapped "by selector". Altium splits the silkscreen clearance into two rules, each narrower than the neutral one (text against other silkscreen objects; silkscreen against mask openings or exposed copper, by a mode). Component Clearance measures bodies or selection areas, with a vertical clearance and a check mode whose number no permitted source explains. `creepage` stays `no-counterpart`: Altium documents the rule, and no public file holds its record. `hole_clearance` too: Altium has it only as a row of the Clearance matrix.
- **Limits are part of exactness (Decision 4).** Every Width, Routing Via Style and Hole Size record that was read holds all its limits, and nothing says what Altium does with a record that lacks one. So a rule must give exactly the limits of its row: `design.rules.minimum(track_width=…)`, `via_diameter`, `via_drill` and `hole_size` minimums are `value-unsupported`, and `clearance` and `edge_clearance` minimums are written. A `via_diameter` and a `via_drill` rule of one selector share one record; one alone is not written. A severity other than `error` is `value-unsupported` as well. `unit-loss` stays in the closed set and is used by no row.
- **No layer scope (Decision 2).** The proposal named `OnLayer` as part of c0042's closed grammar. It is not: `read.scope.parse_scope` refuses every layer function, because a layer name is the board's own. A rule with `layers` or a `layer` selector is `scope-unsupported`. `H-A-RULE-SCOPE` is restated without `OnLayer`. Pair scopes are written for `clearance` only, the one binary kind of the reader's table.
- **`ALLOWSTACKEDMICROVIAS=FALSE`.** A Hole To Hole Clearance with `TRUE` exempts stacked microvias, which the neutral rule does not; the writer writes `FALSE` and the reader maps only `FALSE`. Seven of the nine public records hold `TRUE` and stay unmapped with the reason `keys`.
- **Order against the class rules (Decision 3).** The build still writes the class rules and the `All` defaults of c0038. Within a kind the design's rules come first and a class rule or default of the same scopes is left out, so a board-wide rule of the script governs the classes: the precedence a KiCad build has (`kicad.project.class-shadowed`). The neutral priority is 1 the highest and 0 unset, the reverse of the order of a KiCad rules file.
- **One issue per rule, not per kind**, as the spec said and the proposal did not: two rules of one kind can have two reasons. A build without a PCB document reports every rule with the reason `no-document`, which is a reason of the build and not of `rulemap`.
- **`write_rule_file` lives in `rulemap.py`**, not in `read/rul.py`: the text readers import nothing but each other, `core` and `model` (`tests/unit/backends/altium/read/test_text_imports.py`). It returns bytes, because the end mark of the public file is the single byte `B6`, which is no UTF-8 text; `read_rule_file` reports `altium.text.encoding-assumed` for such a file, as it does for the one Altium saved.
- **`export` has no `--kinds` option.** Each kind is a flag, so the kind is `--altium-rul`. The command reads a KiCad project, so the rules are those of `<stem>.kicad_dru`; an Altium output folder is no input of `export`. An artefact entry has no `notes`, so `result.rules` names what was written and what was not. The capability `cli-contract` gets a MODIFIED "Export command".
- **`kicad-cli pcb import` shows one kind.** It writes the board file only, and KiCad keeps rule minimums and net classes in the project file. The import takes the clearance of the zones it makes from the Clearance rule; the other six kinds load without a message and leave nothing in the board (`docs/evidence/altium-pcb.md`, "Rules against KiCad's importer").
- **Script copper and via rules.** An Altium build of a script with copper intents resolves them through the KiCad build in memory (c0053), which judges the script's rules by KiCad's grammar and refuses a `via_drill` rule with `opt`. Altium's Routing Via Style needs that preferred hole. So such a script cannot hold a via style rule today. The fix belongs to the copper route (which rules that in-memory build needs: it reads the board-wide `edge_clearance`), not to this change; it is listed under "Open Questions".
- **Part U.** The sample is the routed sample of Part C built through `tests/_altium_copper.py`, not a script under `examples/`, for the reason above. How many violations Altium counts for a planted rule is not known, so step U4 asks which rules the violations name, not for exactly two violations.
- **After c0085 (rebased on 2026-10-06).** c0085 landed first: stacks of 2 to 32 layers, blind and buried vias, and `result.pcb`, which counts every model item as written or not lowered. Its count for `rule` was "none written"; it now is the number of rules the document holds and the number it does not (`lens.altium_copper.account`). A rule record holds no layer and no layer count, so nothing of the table depends on the stack: `tests/unit/lens/test_altium_rules.py::test_board6_rules_are_written_and_read_back` writes one rule of every `exact` kind into the six-layer sample and reads them back, and the committed sample, which has no rules, keeps its bytes. `VIASTYLE=Through Hole` is written also beside blind and buried vias: it is the value of all thirteen Routing Via Style records read, two of which are scoped to drill pairs.
- **The hypothesis family `H-A-RULE-*`** is added to the families that `tests/unit/test_format_facts.py` accepts on an Altium facts page.

## Risks / Trade-offs

- [A proposed mapping is wrong] → task 1.1 confirms each row against the public documentation before code, and Part U confirms it in Altium; a row that fails becomes `no-counterpart`.
- [Altium versions name a kind differently] → the facts page records the version of each source; the report names the version used.
- [A rule check in Altium flags more than the planted violations] → the sample board is the routed blink, which c0038's report already opened; unrelated findings are listed, not hidden.

## Migration Plan

- Builds write more rules. A project built before this change is rebuilt as usual; an edited PcbDoc is refused as before ("Edited Altium outputs are not overwritten").
- `altium.not-lowered` at `design-rules` disappears; scripts that matched on that `where` get one warning per rule with `where` `design-rules/<kind>` instead, documented in the changelog.
- A script with `design.rules.minimum(clearance=…)` or `edge_clearance` now changes its PCB document: the clearance for all objects is the script's, and it precedes the class rules.

## Open Questions

- **Should a `value-unsupported` rule be written with the nearest value and a warning?** Default: no, not written.
- **Should the rule file be written by `build` too?** Default: no, only by `export`, to keep the build's file set stable.
- **Should a `minimum()` of a width, a via or a hole size reach Altium by filling the limits it does not give?** Default: no, not written (`value-unsupported`). The alternative is to put the script's minimum into the class rule or default of the same scope, which already holds a preferred value and a maximum; that rule would then no longer read back as the script's.
- **Should the in-memory KiCad build that resolves script copper for an Altium build stop judging rules that only Altium takes?** Default: unchanged. Today a `via_drill` rule with `opt` refuses such a build.
- **Should `export --altium-rul` also read an Altium output folder (`.fenolite/rules.json`)?** Default: no; `export` reads a KiCad project.
