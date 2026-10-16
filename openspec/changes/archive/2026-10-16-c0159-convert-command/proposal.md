## Why

Milestone v0.5a (`docs/roadmap.md`, Phase 5; Open decisions row 38, 2026-10-09) promises "conversion between KiCad and the second backend, with a report of what is kept or lost". Written against `origin/dev` at `f802b60`. The writers exist; the conversion does not:

- `lens.altium.write_model` (c0090, c0126) writes a KiCad board's model as an Altium project, and `AltiumBackend.write` a model read from Altium. Neither has a command: the only Altium output of the CLI is `build --target altium` from a script, and `roundtrip --level rta3` writes into a temporary folder.
- What a write leaves out is counted per kind with **the first reason only** (`backends/altium/lower.py:276`, `_Account.skip`), and not at all for some content: on 16 KiCad 10.0.6 demo boards written that way and read back (2026-10-09), 22 and 11 do-not-populate flags of two boards were gone with no line.
- No conversion is checked: whether the written project is the same design, except where a loss was declared, is nobody's verdict.
- A KiCad board read alone has no net classes or custom rules; they come from the project files (`DesignRulesSource.design_rules`), which no write path asks for.

## What Changes

- **`fenolite.convert`** (the package the layering table already reserves): one entry, `convert_project(source, *, to, kicad_version, allow_lossy, bodies)`, that reads a source project with its project files and returns the files of the target project with a **conversion report**.
- **The report** (`ConversionReport`): per kind of model item, how many the source holds, how many are written, changed or lost, each loss and change counted **per reason** with the ids of the items; a closed vocabulary of kinds shared by both backends; a loss of a copper, footprint, pad, net or fitted-flag kind needs `--allow-lossy`, else exit 7 (`FEN-7001`) with the report in the error.
- **Verification.** `fenolite.api.convert` reads the written project back with the target backend and compares it with the source through `fenolite.api.equivalent` (c0158) at the highest level both hold. A difference that no loss of the report and no rule of the direction's profile explains is `convert.unexplained` (error): exit 5, nothing written.
- **`fenolite convert SRC --to {kicad,altium} --out DIR`**, mutating (`--dry-run`, `--confirm`), with the global `--kicad-version` and `--allow-lossy`. This change wires two directions with today's writers: KiCad to Altium (`fpitems` projection and `lower.write_design`), and KiCad to KiCad for the same or a newer major (`write_board` and the project files). Altium to KiCad is c0161; an older major is c0162.
- **The do-not-populate flag** joins the accounting of the Altium write as kind `dnp` (an info there; a loss in the report).
- **Discovery:** `capabilities.conversions` lists each direction with its evidence and whether it is experimental; schema `fenolite.convert.v0`; the agent guide gains the command.

Size: 6.75 design-days.

## Capabilities

### New Capabilities
- `design-conversion`: the package, the report, the verification, the command and the first two directions.

### Modified Capabilities
- `backend-protocol`: MODIFIED "Altium write of a model" (losses per reason, the kind `dnp`).
- `cli-contract`: ADDED "Conversions in capabilities".

## Non-goals

- Altium to KiCad (c0161), a KiCad downgrade (c0162), and the losses of KiCad to Altium that a writer must close (c0160).
- Converting a library alone (a `.kicad_mod`, a `.PcbLib`): a library goes with its project.
- Altium to Altium: `roundtrip --level rta3` is that trip.
- Variants: after 1.0 (Open decisions row 3).

## Evidence level required

- The report and the verification: mechanical, and `CORPUS-VERIFIED` that every difference of the 18 KiCad 10.0.6 demo boards is explained (`H-G-CONV-LEDGER`).
- KiCad to Altium inherits the Altium writers' level, `INFERRED` and experimental (c0092's rule), with the triangle (`kicad-cli pcb import` of the written document equal to the source at level 5, `H-K-CONV-TRIANGLE`) as its oracle.
- KiCad to KiCad: `KICAD-VERIFIED (9.0.x, 10.0.x)`: the written board loads and its DRC equals the source's (`H-K-CONV-RETARGET`).

## Impact

- New `src/fenolite/convert/`, `src/fenolite/api/conversion.py`, `src/fenolite/cli/cmd_convert.py`, `schemas/fenolite.convert.v0.json`; changed `backends/altium/lower.py` (reasons per item, `dnp`).
- An Altium write of a design with do-not-populate parts reports the kind `dnp` as an `altium.not-lowered` info; `LOSS_KINDS` does not gain it, so `AltiumBackend.write` and `build --target altium` keep their behaviour and gain one info. The conversion report classes `dnp` as a loss that needs `--allow-lossy`, because the bill of materials changes.
