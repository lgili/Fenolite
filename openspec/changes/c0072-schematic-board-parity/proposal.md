## Why

In v0.2a, `check` runs KiCad's own parity test with DRC (c0062): with `kicad-cli` present, a board that disagrees with its schematic is found. Three questions stay open:

- Without `kicad-cli` (a laptop or a CI runner without KiCad), nothing compares the board with the schematic.
- Nothing compares a symbol's pins with its footprint's pads. A pin without a pad is a connection that can never be routed; KiCad's parity test does not report it.
- An agent gets KiCad's descriptions, not counts by category that it can act on.

The plan gives v0.2b a `parity` command, "schematic ↔ board and symbol ↔ footprint", and asks that parity reproduce measured counts of disconnected nets, missing connections and references on one side only. The counts the plan cites were measured outside this project and are not used here. This change measures the same categories against KiCad's own parity test, on the public KiCad demos and on authored edits.

A probe on 10.0.6 (2026-10-05, the `pic_programmer` demo with six board edits) gives KiCad's types:

- a renamed reference gives `missing_footprint` and `extra_footprint`;
- a changed value, or a changed footprint, gives `footprint_symbol_mismatch`;
- a pad on another net gives `net_conflict`;
- a duplicated reference gives `duplicate_footprints`, `missing_footprint` and `net_conflict`;
- an added footprint gives `extra_footprint`, and the unedited demo gives nothing.

## What Changes

- **`checks/parity.py`**: a backend-free comparison of a schematic side (components, pins, nodes) with a board. One code per KiCad type: `parity.missing-footprint`, `parity.extra-footprint`, `parity.duplicate-footprints`, `parity.footprint-mismatch`, `parity.net-conflict`. Two codes of its own: `parity.pin-without-pad` and `parity.pad-without-pin`. A summary gives the plan's categories: references on one side, missing connections, split nets.
- **KiCad adapter.** Components and pins come from the schematic reader (c0060). Nodes come from Fenolite's own netlist when the sheets are inside its grammar (c0063, c0070), else from `kicad-cli`'s netlist export.
- **`fenolite parity PATH [--netlist auto|own|kicad]`**: a read-only command; exit 5 when a finding is an error.
- **`check` stage `parity`** after `drc.kicad`. Without KiCad's parity it reports Fenolite's findings. When `drc.kicad` judged parity, it compares the two and reports a difference as `parity.oracle-differs`, so KiCad stays the authority and Fenolite's comparison is verified on every run.
- **Oracle agreement** on both majors: on every public demo with a board and a schematic, and on the six edits, the counts per KiCad type equal KiCad's.

Size: 10 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `verification-loop`: ADDED "Parity comparison", "Parity stage", "Parity issue codes".
- `cli-contract`: ADDED "Parity command".
- `kicad-oracle`: ADDED "Parity types are probed", "Own parity agrees with kicad-cli".

## Non-goals

- No change of KiCad's parity in the DRC stage (c0062): it stays the authority.
- No repair: `parity` reports; `build` or the GUI fixes.
- No Altium input yet (v0.3 adds an adapter for the same comparison).
- No connectivity of the board (routing completeness is DRC's `unconnected_items`).
- No counts from any private source.

## Evidence level required

- New rows `H-K-PARITY-TYPES` (the types per edit, both majors) and `H-K-PARITY-OWN` (agreement on the demos and edits). `checks.parity.EVIDENCE` stays `INFERRED` until `H-K-PARITY-OWN` is `KICAD-VERIFIED`, and then still names it: the demos are not every project.
- The symbol ↔ footprint codes compare numbers, with nothing to probe.

## Impact

- New: `checks/parity.py`, `backends/kicad/parity_inputs.py`, `cli/cmd_parity.py`, tests and authored fixtures.
- Changed: `checks/stages.py`, `docs/cli-contract.md`, `docs/formats/kicad/drc.md`.
- Depends on c0060 (reader, demo schematics in the corpus), c0062 (KiCad's parity in `check`) and c0063 (netlists). Uses c0070's tree grammar when it is archived.
