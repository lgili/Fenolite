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

1. **One table, `rulemap.TABLE`.** Rows: neutral kind, Altium rule kind, constraint fields, scope forms supported, and `exact` or a reason of the closed set `no-counterpart`, `scope-unsupported`, `value-unsupported`, `unit-loss`. Proposed mapping, each row confirmed against the public documentation in task 1.1 before code: clearance → Clearance; track width → Width; via size → RoutingVias; edge clearance → BoardOutlineClearance; hole size → HoleSize; hole to hole → HoleToHoleClearance; annular width → MinimumAnnularRing; silk clearance → SilkToSolderMaskClearance or SilkToSilkClearance by selector; courtyard clearance → ComponentClearance; hole clearance and creepage → `no-counterpart` unless task 1.1 finds an exact kind (Altium has a creepage rule in recent versions: if its constraint is the neutral one, it becomes `exact`).
2. **Scopes.** A selector becomes a scope expression of c0042's closed grammar. Pair rules use both scope fields. A selector outside the grammar gives `scope-unsupported` for that rule only.
3. **Priorities.** Rules of one kind are written from the most specific to the least, as the neutral rules order them, and the priority field follows that order; the facts page records how Altium orders them.
4. **Exactness.** A value that Altium's field cannot hold (below its resolution, or a range where Altium has one number) gives `value-unsupported`. Rounding to the PCB unit (1/10 000 mil = 2.54 nm) within 2 nm is exact, as everywhere in the PCB writer.
5. **Reader.** `read/rules.py` maps every `exact` row back; `PENDING_KINDS` becomes empty for the kinds of the table. Other kinds stay opaque and counted ("Rules kept opaque").
6. **Rule file.** `rul.write_rule_file(rules)` writes the text form that `read_rule_file` reads, from the same table; `export --kinds altium-rul` writes `<name>.RUL`. It is offered because the PCB Rules editor can import it into an existing board: a user who keeps his own PcbDoc gets the script's rules without a rebuild.
7. **Cut order.** First the rule file export, then pair scopes, never the single-scope kinds and the reader.

## Files and public API

- `src/fenolite/backends/altium/rulemap.py`: `TABLE`, `RuleRow`, `NOT_LOWERED_REASONS`, `lower(rules) -> Lowered(records, not_lowered)`, `lift(records) -> (rules, opaque)`, `EVIDENCE`.
- `src/fenolite/backends/altium/read/rul.py`: `write_rule_file`.
- `src/fenolite/exports/`: the kind `altium-rul`.
- Tests: `tests/unit/backends/altium/test_rulemap.py`, `tests/unit/lens/test_altium_rules.py`, `tests/unit/exports/test_altium_rul.py`, `tests/kicad/altium/test_rules_oracle.py`.

## Sources registered by this change

- S-0160, S-0161 (registered; facts only): how the KiCad importer reads rule records.
- c0042's rows for rule files (`docs/formats/altium/rule-file.md`).
- New: Altium's public documentation pages of each rule kind of the table and of the rule import and export dialog (read for facts).

Each new source gets the next free `S-` number in `docs/evidence/sources.md` when its task runs (numbers are not reserved here, because changes that run in parallel would collide), with its licence and what was read. Sources under a copyleft or an all-rights-reserved licence are read for facts only; nothing is transcribed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-RULE-KINDS | Each `exact` row of `rulemap.TABLE` names an Altium rule kind whose constraint is the neutral rule's, with the fields the table lists | author report, Part U steps U1–U3 | the PCB Rules editor lists every written rule under the kind of the table, with its value |
| H-A-RULE-SCOPE | The scope expressions Fenolite writes (`All`, `InNet`, `InNetClass`, `OnLayer`, and their conjunction) are shown and applied by Altium as written | author report, Part U step U4 | each rule's scope in the editor equals the expression written, and the rule check flags the two planted violations and no other |
| H-A-RULE-PRIORITY | Among rules of one kind, the one written with the higher priority wins where two scopes overlap | author report, Part U step U5 | the planted track inside the class takes the class width, not the `All` width |
| H-A-RULE-READBACK | The rules Fenolite reads from a PCB document it wrote equal the rules of the design for every `exact` row | `tests/unit/lens/test_altium_rules.py::test_readback` | equal for every example script and for the generated rule sets |
| H-A-RULE-FILE | A rule file written by `write_rule_file` is imported by the PCB Rules editor and gives the same rules as the PCB document's | author report, Part U step U6 | import succeeds without a message and the rule list equals that of U1 |

All start `INFERRED`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06).

## Author report: Part U, rules

Files: the project `rules` that Fenolite builds from `examples/` with one rule of every `exact` kind, one net class, and two planted violations (a track narrower than its class width, two pads closer than the clearance), plus `rules.RUL`.

1. U1: open the project and the PCB document; open Design » Rules. Expected: one entry per written rule, under the kinds of the table in `docs/altium.md`.
2. U2: for each entry, compare the value with the table sent with the files. Expected: equal.
3. U3: confirm that no kind shows only Altium's default rule where the table says a rule was written.
4. U4: read each entry's scope text; run Tools » Design Rule Check with the default report. Expected: the scopes as written; exactly the two planted violations for the written kinds.
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
- Archive order: before c0088 (which reads the rules for its check) and before c0090 (which compares them).

## Risks / Trade-offs

- [A proposed mapping is wrong] → task 1.1 confirms each row against the public documentation before code, and Part U confirms it in Altium; a row that fails becomes `no-counterpart`.
- [Altium versions name a kind differently] → the facts page records the version of each source; the report names the version used.
- [A rule check in Altium flags more than the planted violations] → the sample board is the routed blink, which c0038's report already opened; unrelated findings are listed, not hidden.

## Migration Plan

- Builds write more rules. A project built before this change is rebuilt as usual; an edited PcbDoc is refused as before ("Edited Altium outputs are not overwritten").
- `altium.not-lowered` at `design-rules` disappears; scripts that matched on that `where` get one issue per kind instead, documented in the changelog.

## Open Questions

- **Should a `value-unsupported` rule be written with the nearest value and a warning?** Default: no, not written.
- **Should the rule file be written by `build` too?** Default: no, only by `export`, to keep the build's file set stable.
