## Why

`fenolite check` on an Altium project validates the model, runs three ERC rules, compares pad nets between the schematic and the board, and checks the container round trips. It says nothing about the copper: a short between two nets or two tracks closer than the clearance pass. On KiCad input the stage `copper.clearance` finds both without a tool (c0029), and the stage `parity` (c0072) compares the board with its schematic by reference, value, footprint and net.

Both work on the neutral model, and an Altium board is a neutral model since c0043. What is missing is the wiring: the document pipeline has no such stages, the rules of an Altium board reach the model only for three kinds (c0084 widens that), and no Altium `ParityInputs` exists. Altium cannot run in CI, so for the second backend Fenolite's own check is the only check that runs before the maintainer opens the board. The roadmap calls it "a light DRC for the second backend".

## What Changes

- **`copper.clearance` on Altium boards**: shorts, clearance and zone overlaps on the imported board, with the Clearance rules read from the PCB document; built and native input alike. (The copper check judges no board-edge clearance on any backend: corrected on 2026-10-06, see the design.)
- **`parity` on Altium projects**: the board against the schematic documents, with the same findings and counts as for KiCad; the schematic side comes from the import, so no tool is needed.
- **What is not judged is said**: unpoured polygons, internal planes, Clearance rules outside the rule table and pours that no clearance applies to are counted in the stage summary, and the stage evidence falls to `UNVERIFIED` when the copper or the rules were only partly judged, as on KiCad. A pour is never judged against a clearance the document does not hold.
- **A build guard**: `build --target altium` runs the copper check on the PCB document it is about to write, as the KiCad build does on its board, and refuses a board with a short; `--copper-check warn` writes it.

Size: 5 design-days (a size, not time); cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-verification`: ADDED "Document stage order", "Copper check on Altium boards", "Board frame of an imported board", "Clearance rules of a PCB document", "Parity on Altium projects"; MODIFIED "Check on Altium inputs" and "Altium check stage evidence".
- `altium-build`: ADDED "Copper guard in an Altium build".
- `verification-loop`: MODIFIED "Document check pipeline" (the stage tuple and the two stages).
- `backend-protocol`: MODIFIED "Design rules source" (`left_out`); ADDED "Document parity protocol".
- `design-dsl`: MODIFIED "Copper guard before writing" (`--copper-check` with the Altium target).

## Non-goals

- Not Altium's design rule check: no rule kind beyond those the copper check judges for KiCad, no component clearance, no silkscreen checks, no unrouted-net report (connectivity is `netlist.assignment_compare`'s).
- No poured-copper check of polygons that Altium has not poured: an unpoured polygon is not copper.
- No new check logic: `checks/copper.py` and `checks/parity.py` are used as they are.
- No code or constant from any private project or organisation; test data is authored for Fenolite or fetched from the public rows of the corpus manifest.
- No format fact from a decompiled tool or a transcribed parser: every fact gets a row in `docs/formats/altium/*.md` with a public source of `docs/evidence/sources.md` and a label.

## Evidence level required

- The stages carry the evidence of the copper check and of the parity comparison (`INFERRED`), combined with the import's (`INFERRED`).
- An agreement run with KiCad: for boards that both backends hold (the samples built for both targets, and the corpus PCB documents that KiCad imports), the copper findings of the Altium reading equal those of the KiCad reading of the same board. `CORPUS-VERIFIED` for `H-A-DRC-SAME` on the listed boards.
- Optional author report, Part D: Altium's own rule check on one board gives the two planted violations that Fenolite reports.

## Impact

- Changed: `checks/documents.py` (stages), `checks/copper.py` (`rules_issues` reports `left_out`), `backends/base.py` (`DocumentParity`, `DesignRules.left_out`), `backends/altium/backend.py` (`DesignRulesSource`, `BoardFrame`, `DocumentParity`), `backends/altium/read/pcb.py` (`read_rule_fields`), `cli/cmd_build.py` (guard) and `cli/cmd_parity.py` (Altium input). New: `backends/altium/frame.py`, `backends/altium/adapter/parity.py`.
- Pages: `docs/cli-contract.md` ("check on Altium input", "parity"), `docs/altium.md` ("Checks"), `docs/evidence/altium-roundtrip.md`.
- Depends on: c0029 and c0068 (copper check), c0072 (parity), c0043 and c0044 (import and document check), c0084 (rules read from the PCB document; without it the check runs with three rule kinds and says so).
