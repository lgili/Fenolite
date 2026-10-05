## Why

v0.2a starts from the schematic (plan, v0.2a: "`backends/kicad/{sch,sym}.py` … and reading with `ext`"). Fenolite reads boards, footprints and symbol libraries, but a `.kicad_sch` is only looked at header-only (`versions.inspect`): no typed reading, no rebuild, and no proof that a schematic survives Fenolite.

Every other v0.2a change needs that reader: the writer builds the same entities (c0061), the ERC stage needs the sheet files of a project (c0062), the netlist check reads the sheets Fenolite generates (c0063), and `roundtrip`, `diff` and `fmt` need a reader for the kind (c0066).

The plan's acceptance asks for round trips on the demo schematics without buses and multi-instance sheets, listed in the manifest. Counted on tag 10.0.6: 115 files; 72 hold bus items, 22 hold multi-instance symbols, 34 hold neither, and one is older than the read floor.

## What Changes

- `model/schematic.py` (new): `SchematicSheet`, a definition outside `Design`, with symbol instances, labels, no-connect flags, sheet references, embedded symbol definitions, paper and title block. Schema `schematic.json`.
- `backends/kicad/sch.py` (new): `read_schematic`, `rebuild_schematic`, `roundtrip_schematic`, `sheet_files`, `components` and `opaque_count`. Wires, junctions, buses, graphics and every other child stay as slots, in place.
- Token inventory: rows for the schematic and symbol-library tokens introduced after the 8.0 format, and two load checks in the fuzz harness.
- Corpus: one row per demo schematic at both tags and two third-party schematics, tagged by content (`sch-root`, `sch-bus`, `sch-multi`, `sch-old`); RT0 and RT1 on every readable row.
- Oracle: the components Fenolite reads (reference, value, footprint) equal those of `kicad-cli sch export netlist`, on authored schematics and on corpus projects without multi-instance sheets, on 9.0.9 and 10.0.6.
- Authored CC0 fixtures under `tests/data/kicad/schematic/`.
- Hypotheses `H-K-SCH-READ`, `H-K-SCH-RT1`, `H-K-SCH-COMPONENTS`, `H-K-SCH-TOKENS`.

Size: 11 design-days; the cut order is in the design.

## Capabilities

### New Capabilities
- `kicad-schematic`: reading, version policy, modelled content, slots, same-version rebuild, round-trip verdict, sheet tree, components, issue codes, evidence, format page, fixtures.

### Modified Capabilities
- `design-model`: ADDED "Schematic sheet definitions", "Identifiers of schematic entities", "Schematic sheet schema".
- `kicad-token-inventory`: ADDED "Schematic and symbol tokens are inventoried".
- `kicad-oracle`: ADDED "Load checks for schematics and symbol libraries", "Schematic components agree with kicad-cli", "Third-party schematics are read as upgraded copies".
- `corpus-policy`: ADDED "Schematic corpus rows", "Upgraded schematic copies keep their origin"; MODIFIED "Corpus rows carry no names outside URLs" (ids of two or three digits).

## Non-goals

- No writer for created sheets, no change to `build`, no `sym-lib-table`: c0061.
- No connectivity: Fenolite does not derive the nets of a schematic it did not write (plan D9); c0063 takes them from `kicad-cli`.
- No ERC and no RT2: c0062.
- No CLI change: `roundtrip`, `diff` and `fmt` are c0066.
- No bus model (v0.3), no editing of multi-instance sheets (v0.5b), no hierarchy flattening.
- No write for another target: a read sheet is rebuilt at its own version only.

## Evidence level required

- Reading and the slot split: `INFERRED` (`H-K-SCH-READ`) until the oracle agrees.
- Components of a project: `KICAD-VERIFIED (9.0.x, 10.0.x)` when `H-K-SCH-COMPONENTS` holds on both majors.
- RT0 and RT1 over the corpus: `CORPUS-VERIFIED`, two origins, with every unread file counted by reason (`H-K-SCH-RT1`).
- Inventory rows: the level the committed fuzz results give each row (`H-K-SCH-TOKENS`).

## Impact

- New: `src/fenolite/model/schematic.py`, `src/fenolite/backends/kicad/sch.py`, `schemas/fenolite.model.v0/schematic.json`, `docs/formats/kicad/schematic.md`, `docs/evidence/kicad-schematic.md`, `tests/data/kicad/schematic/`.
- Changed: `core/ids.py` (five prefixes), `backends/kicad/data/tokens.toml`, `tools/kicad_token_fuzz.py`, `tools/gen_schemas.py`, `backends/kicad/cli.py` (`export_netlist`, `upgrade_schematic`), `tests/corpus/manifest.toml` and its tests.
- No runtime dependency. Depends on no pending change; c0061, c0062, c0063 and c0066 depend on it.
