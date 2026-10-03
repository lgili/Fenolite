## Why

The last two steps of v0.1's loop are `export` and `render` (plan, v0.1 goal: "`export --manifest` → `render`"), and no change owns them: the roadmap lists them as unowned deliverables. Fenolite writes no Gerber: fabrication files come from `kicad-cli` (plan D2), which both majors provide (`pcb export gerbers`, `drill`, `pos`, `ipcd356`, `svg`, `pdf` and `pcb render`; checked on 9.0.9 and 10.0.6 at proposal time). What Fenolite adds is the same guarantees as its other commands: the tool runs on a copy, nothing is written without `--confirm`, and a manifest says which file came from which board, by which tool version, with its SHA-256.

An agent needs that manifest to hand files to a fab without guessing, and a render to look at the board without opening KiCad. Renders are review artefacts, never a gate (plan D9).

## What Changes

- `backends/kicad/cli.py`: `KicadCli.export(kind, board, …)` and `render`, with one argument table per kind and major.
- `exports/` (new package): `plan` builds the `kicad-cli` calls for the kinds asked; `manifest` builds `fenolite-artifacts.json` (schema `fenolite.artifacts.v0`).
- `fenolite export PATH --out DIR [--gerbers] [--drill] [--pos] [--ipcd356] [--all] [--manifest]` (new, mutating): every file is planned from the copy's outputs and written through the mutation protocol.
- `fenolite render PATH --out DIR [--svg] [--png]` (new, mutating): front and back views; a view that fails is a warning.
- `check`: an opt-in stage `render`, last, which proves that the board plots and reports the plot's size and hash; it never gives an error.
- `cli-contract`: commands that wrap a tool declare `example_tools`, and the consistency suite runs their examples against the fake `kicad-cli`.
- Probes first on 9.0.9 and 10.0.6: the files each kind writes, which of them repeat byte for byte, and whether `pcb render` works headless.
- Hypotheses `H-K-EXPORT-FILES`, `H-K-EXPORT-REPEAT`, `H-K-EXPORT-RENDER`.

Budget: 5.25 days against the roadmap's 4.5; the cut order is in the design.

## Capabilities

### New Capabilities
- `manufacturing-exports`: export kinds, the manifest and its schema, renders, issue codes, evidence.

### Modified Capabilities
- `cli-contract`: ADDED "Export command", "Render command", "Tool-backed command examples".
- `kicad-oracle`: ADDED "Export runs through the package runner", "Exports are probed on both majors".
- `verification-loop`: ADDED "Render stage".

## Non-goals

- Writing or parsing Gerber, Excellon, IPC-2581 or ODB++ in Fenolite; normalising a fab file (dates included).
- BOM and pick-and-place in an assembly house's columns, and the complete manifest with a state per artefact (v0.2a).
- STEP, IPC-2581, ODB++, PDF and DXF exports; schematic exports; `jobset`.
- Refilling zones during export: `--check-zones` is never passed, so the files show the board as it is.
- A gate on `check` before export; a fab-specific preset.

## Evidence level required

- File sets per kind and major: `KICAD-VERIFIED (9.0.x, 10.0.x)` (`H-K-EXPORT-FILES`).
- Byte repeatability: recorded per kind (`H-K-EXPORT-REPEAT`); the manifest states it and promises nothing more.
- Renders: `KICAD-VERIFIED` where `pcb render` and `pcb export svg` write a file headless (`H-K-EXPORT-RENDER`); otherwise the view is reported as unavailable.
- Manifest, planning and the commands: mechanical (hermetic tests with the fake `kicad-cli`).
- An exported file's content is KiCad's: results carry `exports.EVIDENCE` with the oracle `kicad-cli <version>`; Fenolite claims the file set and the hashes, not the fab data.

## Impact

- New `exports/`, `cli/cmd_export.py`, `cli/cmd_render.py`, `checks/render.py`, `schemas/fenolite.artifacts.v0.json`; extended `backends/kicad/cli.py`, `cli/api.py` (`example_tools`), `tests/_fakecli.py`, the consistency suite.
- No model change, no runtime dependency. The `exports` row of `package-layering` exists.
- Depends on c0013 (archived). It needs no other pending change, so it can be implemented at any time; c0015 only makes the exported copper include fills.
