## Why

`fenolite check` on an Altium project validates the model, runs three ERC rules, compares pad nets between the schematic and the board, and checks the container round trips. It says nothing about the copper: a short between two nets or two tracks closer than the clearance pass. On KiCad input the stage `copper.clearance` finds both without a tool (c0029), and the stage `parity` (c0072) compares the board with its schematic by reference, value, footprint and net.

Both work on the neutral model, and an Altium board is a neutral model since c0043. What is missing is the wiring: the document pipeline has no such stages, the rules of an Altium board reach the model only for three kinds (c0084 widens that), and no Altium `ParityInputs` exists. Altium cannot run in CI, so for the second backend Fenolite's own check is the only check that runs before the maintainer opens the board. The roadmap calls it "a light DRC for the second backend".

## What Changes

- **`copper.clearance` on Altium boards**: shorts, clearance, board-edge clearance and zone overlaps on the imported board, with the rules read from the PCB document; built and native input alike.
- **`parity` on Altium projects**: the board against the schematic documents, with the same findings and counts as for KiCad; the schematic side comes from the import, so no tool is needed.
- **What is not judged is said**: unpoured polygons, rule kinds without a counterpart and items the import kept opaque are counted in the stage summary, and the stage evidence falls to `UNVERIFIED` when the copper or the rules were only partly judged, as on KiCad.
- **A build guard**: `build --target altium` runs the copper check on what it writes, as the KiCad build does, and refuses a board with a short.

Size: 5 design-days (a size, not time); cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-verification`: ADDED "Copper check on Altium boards", "Parity on Altium projects", "Document stage order"; these supersede the stage list of "Check on Altium inputs".
- `altium-build`: ADDED "Copper guard in an Altium build".

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

- Changed: `checks/documents.py` (stages), `backends/altium/backend.py` (`DesignRulesSource`, `BoardFrame`, `ParityInputs`), `lens/altium.py` (guard), `cli/cmd_check.py` and `cli/cmd_parity.py` (Altium input).
- Pages: `docs/cli-contract.md` ("check on Altium input", "parity"), `docs/altium.md` ("Checks"), `docs/evidence/altium-roundtrip.md`.
- Depends on: c0029 and c0068 (copper check), c0072 (parity), c0043 and c0044 (import and document check), c0084 (rules read from the PCB document; without it the check runs with three rule kinds and says so).
