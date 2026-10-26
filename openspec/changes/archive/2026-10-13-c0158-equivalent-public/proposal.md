## Why

This is the first proposal of milestone v0.5a (`docs/roadmap.md`, Phase 5 and Open decisions row 38: the next release, `0.5.0`, is v0.5a alone), written against `origin/dev` at `f802b60`. The roadmap names "public `equivalent`". Much of it exists: `fenolite equivalent` is a registered command since c0045, levels 1 to 5 are built (c0045, c0089), and `docs/equivalence.md` and `docs/cli-contract.md` describe it. What is not public yet, measured on `f802b60`:

- **No library entry point.** The comparison is `fenolite.checks.equivalence.compare_designs(a, b)` on two models. Reading the two sides (a built folder, a KiCad project, an Altium document) is private code of `cli/cmd_equivalent.py` (`_side`, `_preflight`, `_imported`); a script or the coming `convert` command cannot reuse it without the CLI.
- **No result schema.** `fenolite capabilities` names the schema `fenolite.equivalent.v0` for the command, and `schemas/` holds no such file.
- **A KiCad schematic is no side.** `equivalent` resolves a KiCad project to its board; a `.kicad_sch` is refused (`FEN-2001`). A circuit-only comparison of a KiCad project with an Altium project (levels 1 and 2) is not possible, though both netlists exist (`backends/kicad/oracle.py:159`, `sch_netlist.own_netlist`).
- **The same copper is reported as a difference.** An `oval` pad whose two sizes are equal is a disc. Written to Altium and read back, it is a `circle`; level 3 reports `equiv.pad-shape` for it: 40, 180 and 85 pads on three KiCad 10.0.6 demo boards (measured 2026-10-09, design "Context").

## What Changes

- **`fenolite.api.equivalent(a, b, …)`**: a public function that takes two paths or two `Design` values, reads the sides as the command does, and returns an `EquivalenceResult` (the report, the two sides, the evidence, the issues). The command becomes a thin caller of it. New sub-package `fenolite.api`, added to the layering table.
- **The result schema** `schemas/fenolite.equivalent.v0.json`, the first schema of one command's `result`; the consistency suite validates every `equivalent` reply against it.
- **A KiCad schematic as a side.** A root `.kicad_sch` is read, with its sheet tree, into a circuit through its netlist: Fenolite's own netlist when the sheets pass its grammar check, else `kicad-cli sch export netlist`. Levels 1 and 2 only; `sides.<x>.netlist_source` is `schematic`.
- **Normalisation:** an `oval` pad whose two sizes are equal within the length tolerance counts as a `circle` for `pad-shape`.
- **Discovery:** the `equivalent` entry of `capabilities` lists its levels and the side kinds; the agent guide gains the API line.

Size: 4.5 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-equivalence`: MODIFIED "Equivalent command", "Tolerances and normalisation"; ADDED "Public equivalence API", "Public equivalence API inputs", "Public API errors and effects", "Schematic sides", "Schematic side netlist", "Power symbols of a schematic side", "Fitted flag of a schematic side", "Equivalent result schema".
- `package-layering`: MODIFIED "Allowed import edges" (the `api` row).
- `cli-contract`: ADDED "Levels and sides of equivalent in capabilities".

## Non-goals

- Levels 6 to 8 (after 1.0 by the maintainer's decision of 2026-10-09, Open decisions row 3).
- Result schemas of other commands (the v1.0 freeze).
- An Altium schematic read differently: a `.SchDoc` and a `.PrjPcb` are sides already.
- A stricter level 5 that matches copper item by item (open decision 25 keeps one table).
- Conversion: c0159.

## Evidence level required

- The API and the schema: mechanical (unit and consistency tests); the evidence of a reply stays `Evidence.combine` of the two reads.
- A schematic side read through Fenolite's own netlist carries `sch_netlist.EVIDENCE` (`KICAD-VERIFIED`); through `kicad-cli`, `ORACLE-VERIFIED(kicad-cli)` for the netlist, settled on 9.0.9 and 10.0.6 by `H-K-EQ-SCHSIDE` (design).
- The pad-shape rule: `KICAD-VERIFIED` that KiCad draws an equal-sized oval as a disc (`H-K-EQ-OVAL`, rendering both pads on 9.0.9 and 10.0.6); until then `INFERRED`.

## Impact

- New `src/fenolite/api/` (`__init__.py`, `equivalence.py`, `sides.py`); `cli/cmd_equivalent.py` shrinks to argument parsing; `checks/equivalence/norm.py` and `levels.py` (shape rule); `schemas/fenolite.equivalent.v0.json`; `tests/unit/test_import_graph.py` (`api` row).
- A comparison that reported `equiv.pad-shape` for equal-sized ovals against circles no longer does: a script that counted those differences sees fewer. `CHANGELOG.md` says so.
- No KiCad or Altium output changes.
