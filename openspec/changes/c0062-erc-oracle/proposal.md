## Why

`check` judges a board with KiCad's DRC and the circuit with three rules of its own (`erc.lite`, `INFERRED`). Plan D9 marks that stage for removal in v0.2a, "when `kicad-cli sch erc --format json` becomes the source", and adds `--schematic-parity` to the DRC stage. c0061 gives every built project a schematic, so both become possible.

Measured at proposal time on 9.0.9 and 10.0.6: `sch erc --format json --severity-all` writes a report by sheet whose violations carry a type, a severity and items with a uuid and a position; that position is the sheet position in millimetres divided by 100; `ignored_checks` exists on 10.0 only; a schematic that does not load gives exit 3 and no report; `pcb drc --schematic-parity` fills the `schematic_parity` list that Fenolite already parses and does not map.

## What Changes

- `KicadCli.erc` and `backends/kicad/erc.py`: the ERC run on a copy and the report reader, with the neutral `ErcReport` in `backends.base`.
- The copy set of a check gains the schematic: the root sheet, its sheet files (c0060), `sym-lib-table`, the symbol libraries it names and the schematic's drawing sheet.
- `check`: the stage `erc.kicad` takes the place of `erc.lite` in the KiCad pipeline. Violations become `kicad.erc.<type>` issues located as `REF-PIN`; a project without a schematic skips the stage.
- `check`: the DRC run passes `--schematic-parity` when the project has a schematic, and parity entries become `kicad.drc.<type>` issues.
- `erc.lite`: out of `STAGE_ORDER`; its removal deadline goes. The three rules stay as a function for inputs that have no ERC oracle (c0044's document pipeline).
- RT2 for schematics: ERC gives equal reports for a project and for Fenolite's re-dump of every sheet; run over the corpus projects of c0060.
- Probes on both majors: report shape, positions, types and severities, the copy set, repeatability, parity.

Size: 8.5 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `verification-loop`: ADDED "ERC stage", "ERC findings as issues", "ERC stage issue codes", "Parity findings"; MODIFIED eleven requirements that name the stage list, the hermetic stages or `erc.lite`, among them "ERC lite stage" and "DRC findings as issues" (listed in the design, Migration Plan).
- `kicad-oracle`: ADDED "ERC runs through the package runner", "ERC oracle", "ERC facts proved per major", "Parity in the DRC run", "Schematic RT2 over the corpus"; MODIFIED "Check project copy set".
- `backend-protocol`: ADDED "Neutral ERC report", "ERC oracle protocol"; MODIFIED "Oracle protocol" (`DrcOutcome.parity_judged`).
- `kicad-file-backend`: ADDED "ERC report reading".

## Non-goals

- No ERC of Fenolite's own, and no new rule: KiCad's verdict is the verdict.
- No change to a project's ERC severities or pin-conflict map.
- No ERC for Altium input (c0044 keeps the three rules there).
- No netlist comparison (c0063). No `roundtrip` command (c0066).

## Evidence level required

- The ERC stage: `KICAD-VERIFIED (9.0.x, 10.0.x)` once the report shape, the position scale and the copy set are proved on both majors (`H-K-ERC-JSON`, `H-K-ERC-POS`, `H-K-ERC-COPYSET`); `UNVERIFIED` when no report was written.
- Violation types and severities of the controls: `KICAD-VERIFIED` per major (`H-K-ERC-TYPES`).
- Parity entries: `KICAD-VERIFIED` (`H-K-PARITY-RUN`), with c0061's `H-K-SCH-PARITY`.
- RT2 on schematics: `KICAD-VERIFIED` where two ERC runs of one project agree (`H-K-ERC-REPEAT`, `H-K-ERC-RT2`); projects where they do not are named, not judged.
- The three rules that stay: `INFERRED` (`H-K-CHECK-ERC`), unchanged.

## Impact

- New: `backends/kicad/erc.py`, `checks/erc.py`, `checks/erc_json.py`, `docs/formats/kicad/erc.md`.
- Changed: `backends/base.py`, `backends/kicad/{cli,oracle,projectset}.py`, `checks/{stages,drc,drc_json,codes,erc_lite}.py`, `cli/cmd_check.py`, `docs/cli-contract.md`, every test and page that names `erc.lite` as a stage.
- Depends on c0060 and c0061. c0044 modifies requirements this change also modifies; the design states the re-base rule.
