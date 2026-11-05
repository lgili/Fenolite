## ADDED Requirements

### Requirement: Draftsman native document correction round
Before any writer content is added, one correction round SHALL be run on the native document: FP3 and FP4 corrected from the members that every saved document of round F0 holds and the candidates lack, and FP5 tried through a document template registered in Altium's Preferences. Gate G2 SHALL be decided again from that round's report only; without a passing probe the native document stays unshipped and route P is decided.

#### Scenario: Correction round before writer content
- **GIVEN** gate G2 failed on 2026-11-04 (c0172, S-1575 and S-1581)
- **WHEN** an agent would add views, tables or dimensions to the writer
- **THEN** the correction round's report is recorded first, and the writer tasks stay open until it shows a probe that opens

#### Scenario: Gate stays shut without a report
- **GIVEN** no report of the correction round is recorded in `docs/evidence/altium-draftsman.md`
- **WHEN** `uv run pytest tests/unit/test_altium_verification_docs.py -k part_f` runs
- **THEN** it passes only while `draftsman.NATIVE_WRITE` is `False`

### Requirement: Fabrication sheet of a Draftsman document
The first sheet SHALL hold a Drill Drawing View (top, Top–Bottom pair), a Drill Table, a Layer Stack Legend when the board has a stack-up, a Table of c0117's board rows, a Note of `[fab].notes` when it has any, and the title-block Texts, placed by c0117's `place` at 1:1 on the paper `choose_paper` gives.

#### Scenario: Fabrication sheet of the routed blink
- **GIVEN** the routed blink and a drawing specification with two `[fab]` notes
- **WHEN** `uv run pytest tests/unit/lens/test_altium_draftsman.py -k fab` builds its spec
- **THEN** sheet 1 has the title `Fabrication drawing`, one drill drawing view, one drill table, one layer stack legend, one table, one note of two entries, and no two objects overlap by the estimated sizes

### Requirement: Assembly sheets of a Draftsman document
The document SHALL hold one assembly sheet per side of `[assembly].sides` that has parts, each with a Board Assembly View of that side with designator captions, a Bill Of Materials table filtered to that view, the title-block Texts, and on the top sheet a Note of `[assembly].notes`. A do-not-populate part MUST give one `altium.not-lowered` info naming it.

#### Scenario: No part on the bottom
- **GIVEN** the routed blink with `D1` placed on the top, so that every part is on the top
- **WHEN** its Draftsman spec is built with the default drawing specification
- **THEN** the document has two sheets, the second holds a top assembly view and a BOM table, and no bottom sheet exists
