## Why

A block instance of c0251 gets a KiCad child sheet and an implicit Altium group, but its schematic is not
organised by the block. The KiCad child sheet has no pins: every net reaches it through global labels
named after the outside net (`VIN48`), so each instance's sheet reads differently and the block's interface
is not visible. The sheet reference is a box with a name. In Altium, the sheet entries of a module are
inferred from nets that happen to cross and are named after those nets. Grouping (`schematic_block`) is
declared per design and works only for Altium. The research of 2026-10-29
(`docs/research/circuit-blocks.md`, section 2 gap 3, section 3.3 and row c0269 of section 4) asks for an
organised schematic **inside** a block: groups, order and anchors declared once in the block and reused by
every instance, KiCad hierarchical pins and Altium sheet entries from the declared ports, and a tidy
default when the block declares nothing.

KiCad design blocks place a block as a sheet whose fields act as parameters, and Altium Reuse Blocks turn
ports into sheet entries. Only these concepts are taken. No file, layout or API name of either tool is
copied, and the file facts come from the public KiCad format page (S-0367) and Altium's documentation
(S-0185).

## What Changes

- **Block-local groups.** `b.schematic(schematic_group(key, *members, title=, anchor=, after=,
  flow=), ...)` declares, once per block, the groups of the block's own parts, their order, their anchors
  and their flow. Every instance reuses them. A block without the call gets one default group, which is
  today's tidy module flow.
- **KiCad hierarchical pins from ports.**
  - On the sheet of a block instance, each port member gives a hierarchical label at each of its pins.
    The label is named `<port>` for a single-member port and `<port>_<member>` otherwise.
  - The instance's sheet reference gets a sheet pin of that name, with a shape from the port direction
    (`in` → input, `out` → output, `inout` → bidirectional).
  - The parent sheet labels each sheet pin like a pin of that net, so a global label with the circuit net
    name stays on some sheet and net names do not change.
  - Local nets of a block and nets that escape it keep their global labels.
- **Shared arrangement.** Instances of one block with the same parts are laid out with the same relative
  positions. Label rooms are sized by the longest label over those instances.
- **Altium sheet entries from ports.** On the sheet of a block instance (`sheets="modules"`), the ports and
  sheet entries are the block's declared ports, named like the KiCad pins, in port order. Nets that escape
  the block still cross as inferred nets. Stubs keep the circuit net names as labels, and power nets keep
  their global power ports.
- **Altium composition.** In block composition mode, each local group gives a `schematic_block` keyed
  `<instance path>/<key>`. c0251's implicit block of the instance keeps the parts that no local group holds.
  Local groups are not design-level intent: they are never reported as unused intent, and KiCad builds do
  not refuse them.
- **Model.** `SheetRef` gains `pins: tuple[SheetPin, ...]`, omitted when empty. The KiCad writer writes
  sheet pins and hierarchical labels.
- **Netlist guard.** The own netlist and the grammar check of the KiCad schematic read hierarchical labels
  and sheet pins, so the build still proves that the sheets mean the circuit.
- **No byte change** for designs without block instances: plain modules keep global labels and pinless
  sheet references, and their sheets, boards and Altium documents keep their bytes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `kicad-schematic`:
  - MODIFIED "Hierarchical sheets of a design", "Generated sheet content", "Own netlist of a generated
    sheet", "Netlist grammar check" and "Deterministic sheet layout".
  - ADDED "Block sheet pins", "Sheet pin geometry", "Block ports sharing a net", "Block schematic groups on
    a KiCad sheet", "Shared arrangement of block sheets" and "Sheet pins and hierarchical labels written".
- `altium-schematic-writer`: MODIFIED "Sheets of a module tree". ADDED "Sheet entries from block ports" and
  "Block sheet name clash in Altium".
- `design-dsl`: ADDED "Block schematic groups in the DSL", "Block schematic groups are not composition
  intent", "Block-local groups in Altium composition" and "Sheet names of block ports".
- `design-model`: ADDED "Sheet pins in the schematic model".

## Dependencies

- **c0251 circuit-blocks** (required): blocks, ports, port members, the model `Port`, the KiCad sheet name
  `<name> (<block name>)` and the implicit Altium groups.
- **c0252 parametric-interfaces**: the kinds `Rail`, `Ground` and `Logic`, whose members follow the same rule.
- Independent of c0268. A recorded block's name is its id, which only changes the sheet name text.
- Later: c0272's starter blocks declare their groups with `b.schematic`.

## Non-goals

- No change of plain `Module` sheets, of the root sheet's content beyond the sheet pins and their labels,
  or of the grid layout (`--schematic-layout grid` keeps one sheet without pins).
- No multi-instance KiCad sheet file shared by several references. Each instance keeps its own file, so
  local nets keep their circuit names.
- No group titles drawn on KiCad sheets (open question 2). No buses or harnesses made from interface ports.
- No block-relative keys in `schematic-placements.toml`. Placements stay keyed by component path.
- No shared arrangement for Altium sheets (open question 3).

## Evidence level required

- KiCad sheet pins and hierarchical labels: `KICAD-VERIFIED (9.0.x, 10.0.x)` once the KiCad CI job reads the
  example's netlist with `kicad-cli` and finds every net under its circuit name and no ERC sheet-pin
  violation (`H-K-SCH-BLOCK-PINS`, `H-K-SCH-BLOCK-ERC`). `INFERRED` until then.
- Altium entries from ports: `INFERRED` until the maintainer's kit compiles the block example and lists no
  port message (`H-A-BLOCK-ENTRIES`).
- Groups and the shared arrangement: `INFERRED`, unit-tested (`H-G-BLOCK-SHEET-REUSE`).

## Impact

- New: `src/fenolite/dsl/blockschematic.py` (`schematic_group`, the `b.schematic` record),
  `tests/data/altium/blocks/design.py` (authored, CC0), and tests under `tests/unit/dsl`,
  `tests/unit/backends/kicad`, `tests/unit/backends/altium` and `tests/kicad/build`.
- Changed:
  - `dsl/block.py` (`schematic`, the port-name check);
  - `model/schematic.py` (`SheetPin`, `SheetRef.pins`) and the schemas;
  - KiCad backend: `backends/kicad/schgen.py`, `schlayout.py`, `sch.py` (sheet pins, hierarchical labels,
    `opaque_sheet_pins`) and `sch_netlist.py`;
  - Altium backend: `backends/altium/hierarchy.py` and the composition intent;
  - `docs/schematic.md`, `docs/schematic-composition.md`, `docs/dsl.md`, `docs/formats/kicad/schematic.md`
    and `docs/formats/altium/schematic-ascii.md`;
  - the guide page `design-script.md`;
  - `CHANGELOG.md`.
- Size: about 7 design-days (M).
