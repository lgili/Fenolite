## Why

c0039 to c0042 read Altium files into records. Nothing turns those records into the neutral model,
so no check, analysis or comparison can use an Altium design. A schematic also stores no netlist:
its nets follow from wires, junctions, labels, ports, power ports, sheet entries and harnesses.

## What Changes

- **Adapter.** `fenolite.backends.altium.adapter` maps the readers' records into `Design` and
  `Library`. It parses no bytes and writes nothing.
  - PCB document: layers named by position in the copper chain, stack-up, nets, net classes,
    footprints with pads in the footprint frame, tracks, arcs, vias, zones from polygons, graphics,
    texts, the outline as edge graphics, and a circuit synthesised from the pads.
  - Schematic: components with pins, nets, modules from sheet symbols, harnesses as interfaces,
    buses, No ERC directives as no-connect marks.
  - Project: sheets and PCB document merged; components linked by unique-id path, then by
    designator. Neither side is corrected by the other.
  - Libraries: `FootprintDef` and `SymbolDef`.
  - Rules: through c0042's mapper; an unmapped rule is counted, never approximated.
- **Connectivity.** Exact integer rules for wires, junctions and electrical points; the net
  identifier scope; names by priority. Each unclear case is a hypothesis with a corpus test.
- **Units and identity.** `u_to_nm` for binary lengths, Y negated; original integers of inexact
  values in the `altium` bag; native ids and provenance with a record locator.
- **Backend.** `AltiumBackend`, a registered built-in for `detect` and `read`, with six read kinds
  and no write kind. The writers stay experimental under `build`.
- **Model deltas, additive.** `Circuit.buses`; padstack hole shape, slot length, hole rotation and
  per-layer offset; `ComponentBody` on footprints and definitions.
- **Body records.** `read.bodies` decodes the body storages that c0041 keeps as bytes.

## Capabilities

### New Capabilities

- `altium-import`: 31 ADDED requirements.

### Modified Capabilities

- `design-model`: ADDED "Buses in the circuit model", "Padstack holes and offsets", "Component
  bodies".
- `backend-protocol`: MODIFIED "Backend registry".
- `cli-contract`: MODIFIED "Backends in capabilities" and "Experimental features in capabilities"
  (text of c0035).
- `corpus-policy`: ADDED "Altium project sets".

## Non-goals

- No byte parsing (c0039 to c0042); no `inspect`, `check`, `diff` or round-trip level (c0044); no
  equivalence verdict (c0045); no sheet template (c0046).
- No writing from an imported model, and no `write` operation of the backend (v0.4).
- No schematic presentation in the model.
- Reported, not resolved: repeated sheets with their annotation, `Repeat` statements, nested
  harnesses, variants, differential pairs.
- Kept in bags or counted: zone settings, split planes, per-layer via stacks, mask and paste layers
  of pads, graphics of placed footprints, 3D model data.
- No change to the writers or the KiCad backend.

## Evidence level required

- Layers, footprints, pads, tracks, vias and zone outlines: `ORACLE-VERIFIED(kicad-cli)` against
  `kicad-cli pcb import --format altium` (10.0) on the corpus documents; `INFERRED` before.
- Connectivity: `CORPUS-VERIFIED` per rule when the schematic netlist of public project sets from
  three repositories equals the pad netlist of their PCB documents (`H-A-IMP-NETLIST`); `INFERRED`
  for a rule that no set exercises. Net names: `INFERRED`.
- Own files (build, then import): `INFERRED`.
- Rules, padstack details that KiCad does not read, body keys: `INFERRED`.
- The backend's report carries the lowest level, `INFERRED`. No author report is needed.
- Sources: the fact pages, `docs/evidence/sources.md`, S-0185 to S-0188 and S-0301 to S-0303.

## Impact

- Code: `backends/altium/adapter/`, `backends/altium/backend.py`, `backends/altium/read/bodies.py`,
  `backends/registry.py`, `model/`, `core/ids.py`; regenerated schemas; three fact pages.
- `fenolite capabilities` lists `altium` before `kicad`.
- Depends on c0040, c0041, c0042. Archive order: c0032, c0035, c0036, c0037, c0038, c0039 to c0042,
  then this change; c0044 and c0045 after.
- Size: 19 design-days.
