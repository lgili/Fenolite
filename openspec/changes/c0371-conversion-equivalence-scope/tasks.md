## 1. Scope

- [ ] 1.1 Authored regression: an Altium project with one schematic-only part converts without
      `convert.unexplained`; removing that part from the written schematic is still reported.
- [ ] 1.2 Leave source components without a source footprint out of level 1 of the board comparison.

## 2. Source duplicates

- [ ] 2.1 Authored regressions: a designator repeated on two sheets; a component linked to two footprints.
- [ ] 2.2 Source diagnostics for both, and the Explainer explains the matching `ref-ambiguous`.

## 3. Close

- [ ] 3.1 Docs, CHANGELOG, explain entries, `openspec validate --strict`, focused tests, `make check-fast`.
- [ ] 3.2 Re-run the private batch outside the repository and record the outcome there.
