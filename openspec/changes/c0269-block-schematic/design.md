## Context

- **Source.** `docs/research/circuit-blocks.md` (2026-10-29), section 2 (gap 3: "An organised schematic
  inside a block"), section 3.3 and row c0269 of section 4. Concepts only. KiCad design blocks place a block
  as a sheet, and Altium Reuse Blocks turn ports into sheet entries. No file, layout, value or API name of
  those tools is copied. KiCad file facts come from the public format page (S-0367), and Altium facts from
  its documentation (S-0185) and the records already documented under `docs/formats/altium/`.
- **What exists on `dev` (0.6.0).**
  - `kicad-schematic`, "Hierarchical sheets of a design": one child sheet per module, sheet references
    with no pin, and "every net crosses sheets through its global labels". "Generated sheet content" puts
    one global label at each connected pin. The readable layout ("Deterministic sheet layout", "Readable
    sheet layout") flows units in rows by module and snaps two-pin satellites to IC pins.
  - The build's netlist guard reads the generated sheets with `sch_netlist.own_netlist`. Its grammar
    refuses any label that is not global and any sheet reference with pins.
  - The reader maps `hierarchical_label` to `NetLabel(kind="hierarchical")` and keeps a sheet reference's
    `pin` children as opaque slots.
  - Altium `sheets="modules"`: one sheet per module. Crossings are inferred per net, and each gives a port
    and a sheet entry named after the net. Power nets never cross (power ports are global, S-0185).
    Directions come from pin types ("Port and sheet-entry directions", `H-A-SCHX-DIR`).
  - Composition (`schematic_block`, `schematic_layout`) is design-level and Altium only. A KiCad build
    refuses it, and declarations without block mode are "unused intent".
- **What c0251 adds.** Blocks are modules. Ports have members (`net`, or `hv`/`lv`, `sda`/`scl`, ...), and
  port nets take the outside net's name. The KiCad sheet is named `<name> (<block name>)`. In Altium block
  mode, each instance gives an implicit `schematic_block`.

## Goals / Non-Goals

**Goals**

- A block's sheet shows the block's interface: its ports as hierarchical pins in KiCad and as ports and
  sheet entries in Altium, named as the block names them, the same in every instance.
- A block author decides once how the block's parts are grouped and ordered. Every instance uses that.
- Without any declaration, a block's sheet is still tidy: today's module flow.
- Net names, netlists and the build's proof stay what they are. Designs without blocks keep their bytes.

**Non-Goals**

- See the proposal.

## Decisions

### 1. Block-local groups in the DSL

```python
# Today: grouping is design-level, Altium only, and keyed by global part paths
design.schematic_layout(mode="blocks")
design.schematic_block("divider_a", members=[a_top, a_bot], title="Divider A")

# Proposed: declared once in the block, reused by every instance, KiCad and Altium
from fenolite.dsl import block, schematic_group


@block
def rc_filter(b, *, r=ohm("10k"), c=farad("100n")):
    inp = b.port("IN", direction="in")
    out = b.port("OUT", direction="out")
    gnd = b.port("GND", direction="in")
    r1 = b.part("R", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value=r)
    c1 = b.part("C", "Fenolite:Capacitor", footprint="Fenolite:Chip_0603", value=c)
    connect(inp, r1[1])
    connect(out, r1[2], c1[1])
    connect(gnd, c1[2])
    b.schematic(schematic_group("chain", r1, c1, flow="left-to-right", title="Filter", anchor=r1))
```

- `schematic_group(key, *members, title=None, anchor=None, after=None, flow="left-to-right")` is a
  frozen value of `fenolite.dsl`. A member is a part handle or a local part name of the block.
- `b.schematic(*groups)` may be called **once** per block. At the call, it raises `DslError` naming the
  block when:
  - a key does not match the module-name pattern, or is used twice;
  - a member is not a part that the block owns directly (a nested block's part belongs to the nested
    block's sheet), or is in two groups;
  - `anchor` is not a member;
  - `after` names no key of the call, or makes a cycle;
  - `flow` is neither `left-to-right` nor `top-to-bottom`;
  - `b.schematic` is called a second time.
- **Order of groups.** The order of the call, then moved so that each group comes after the group its
  `after` names. This is a stable topological order. The member order is the order given, with the anchor
  first.
- **Default group.** A block without `b.schematic`, and the parts that no group holds, form the default
  group: the units in natural path order with satellites snapped, which is exactly a module's sheet today.
- `dsl.block_schematics(design)` gives `BlockSchematic(path, block, groups)` per instance, for the
  backends. Nothing reaches the circuit model.
- **Alternatives considered.**
  - `b.schematic(column=[top, bot], title=...)` (the research sketch). Rejected: one keyword per layout
    form grows without end. `flow` plus groups covers rows and columns.
  - Reusing `Design.schematic_block` inside blocks. Rejected: it is design-level intent with Altium-only
    rules ("unused intent", KiCad refusal), which must not fire for a library block (decision 7).

### 2. Sheet names of ports

Implemented 2026-10-29: a "single-member port" is a port of kind `Net`, the one kind whose members the
model always knows (the model drops unbound members, and a harness's declared members are not in it).

A port member's **sheet name** is `<port>` for a single-member port and `<port>_<member>` otherwise
(`I2C_sda`, `I2C_scl`). The same name is used for KiCad hierarchical labels and sheet pins and for Altium
ports and sheet entries.

- `b.port` raises `DslError` when a sheet name of the new port equals a sheet name of an earlier port of
  the block, for example a port `I2C_sda` beside an `I2C` port. The clash is refused where it is written.
- *Why `_` and not `.`.* A dot in a label is how Altium sheets name harness members (S-0188, imported by
  `altium-import`), and KiCad uses dotted member names for bus groups. `_` has no such meaning in either
  tool.

### 3. KiCad: hierarchical labels and sheet pins

On the sheet of block instance `B`:

| net on `B`'s sheet | label at each of its connection points on `B`'s sheet |
|---|---|
| bound by exactly one port member `m` of `B` | hierarchical label, text = sheet name of `m`, shape from the port direction |
| bound by two or more port members of `B` | global label of the net, as today; those members get no sheet pin; `build.block-port-merged` (info) |
| any other net (local nets, escaping nets) | global label of the net, as today |

- A connection point is a pin of a unit on `B`'s sheet, or a sheet pin of a nested block's reference on
  `B`'s sheet.
- **Sheet pins.** `B`'s reference, on the parent sheet, gets one `SheetPin` per port member that has a
  hierarchical label on `B`'s sheet. Members that bind no net, or whose net has no connection point on
  `B`'s sheet, get none.
- **The parent labels a sheet pin like a pin of the net,** by the same table applied to the parent's sheet.
  The root is never a block sheet, so it always gives a global label. Every net that leaves a block
  therefore meets a global label of its circuit name on the first sheet where it is not a port net. KiCad
  names such a net after its global label (`H-K-SCH-BLOCK-PINS`, to be measured in CI). The guard
  (decision 6) checks the names before anything is written.
- **Shapes.** `in` → `input`, `out` → `output`, `inout` → `bidirectional`, for the hierarchical label and
  its sheet pin alike.
- **Geometry.** `in` pins lie on the left edge of the box and `out` and `inout` pins on the right edge.
  On each side, pins are ordered by sheet name in code-point order, at `ORIGIN_STEP` (2.54 mm) pitch,
  starting one step below the top. The box height is the larger of `REF_HEIGHT` and `ORIGIN_STEP` × (pins
  on the fuller side + 1). Positions are on the 1.27 mm grid. A pin's label on the parent is turned away from
  the box.
- **Ids.** A sheet pin is keyed `<name>:sheetpin:<module path>:<pin name>`. A hierarchical label at a pin
  is keyed `<name>:hlabel:<component path>:<pin>`, and one at a nested sheet pin
  `<name>:hlabel:sheet:<module path>:<pin name>`. KiCad uuids come from `pcb.kicad_uuid`.

Example, `examples/blocks/design.py` of c0251 (`channel` used as `ch0` and `ch1`):

```
root:                 sheet "ch0 (channel)" pins EN (bidirectional, right), GND (input, left), VIN (input, left)
                      global labels CH0_EN, GND, VIN48 at those pins
sheets/ch0.kicad_sch: hierarchical labels VIN at R_EN pin 2, EN at R_EN pin 1, GND at ...
                      global label ch0/FB at the pins of the local net
```

- **Alternatives considered.**
  - Local labels inside the block sheet and one hierarchical label per port. Rejected: whether KiCad joins
    a local and a hierarchical label of one text on one sheet is not measured, while labels of one kind and
    text on one sheet are joined like any labels (`H-K-SCH-BLOCK-PINS` covers it).
  - One sheet file shared by all instances (KiCad multi-instance sheets). Rejected for now: local nets
    would need local labels, and KiCad would name them `/<sheet name>/FB`, not the circuit's `ch0/FB`.
    The board, the lens and the guard all key on circuit names.

### 4. KiCad: groups and the shared arrangement

- `layout_units(..., groups=, widths=)`. On a block sheet, units are ordered by group (decision 1), then
  member order, then unit number. Each group starts a row. In a `top-to-bottom` group, each cell starts its
  own row at the group's left edge. Units in no group come last in natural order.
- Satellites snap as today, within a group. A satellite is snapped only to an anchor of its own group,
  so groups do not mix.
- **Shared arrangement.** For each block, instances whose sheets hold the same unit keys relative to the
  instance path, the same groups and the same sheet pins share one arrangement. `schgen` builds one
  `widths` map: per relative pin key, the longest label text over those instances. It then lays out every
  such sheet with it, so the relative origins are equal. A unit named in `schematic-placements.toml` leaves
  the flow as today, and that instance no longer shares the arrangement of the others.
- **Titles** are not drawn on KiCad sheets in this change (open question 2). `title` is used by Altium.

### 5. Altium: ports and sheet entries from block ports

With `sheets="modules"`, the crossings of the sheet of block instance `B` are:

1. one crossing per port member of `B` that has a pin on `B`'s sheet or below it, whose net is not a
   member of a `power` interface (power ports stay global, S-0185), and that is not merged (decision 3).
   It is named by the member's sheet name.
2. the inferred crossings of today for every other net that crosses `B`, named by the net name.

- Crossings are ordered by kind (ports first, in port declaration order and then member order), then by
  name in code-point order.
  Implemented 2026-10-29: the model keeps the ports of an instance ordered by name and their members by
  member name (c0251's `to_model`), so "port declaration order" is the model's order: ports by name, then
  members by name. Changing the model order would change c0251's canonical bytes.
- Port and entry I/O types keep the table of "Port and sheet-entry directions", which `H-A-SCHX-DIR` has
  measured. Declared directions are recorded and checked by c0252, but they are not written to Altium yet
  (open question 4).
- Stubs and net labels keep the **circuit net name**, on both sides. A port named `IN` with a stub label
  `SRC` joins its entry `IN` by name (S-0185), and the label names the net on each sheet. Whether Altium
  names the compiled net after the label when the port has another name is `H-A-BLOCK-ENTRIES`, which
  the kit checks.
- A sheet-name clash between a port crossing and an inferred crossing on one module (an escaping net
  named `IN` beside a port `IN`) gives `build.block-sheet-name-clash` (error) naming both, and nothing is
  written.
- A port of kind `harness` keeps today's harness rule (binary form, top-level). Other interface ports cross
  member by member.

### 6. The netlist guard reads the new items

- `own_netlist`: within one sheet, groups with hierarchical labels of one text are joined, and joined to
  the sheet pin of that name on the reference to that sheet in the parent. A sheet pin's point joins like a
  label's. Names come from global labels as before.
- `grammar_issues`:
  - `label-kind` now refuses only a label kind other than global and hierarchical, or a hierarchical label
    on a root sheet;
  - `sheet` refuses a sheet pin without a hierarchical label of its name on the child, a hierarchical
    label without a sheet pin, two sheet pins of one name on a reference, and a sheet pin off its box edge.
  - The set of reasons is unchanged.
- Read sheets: `sch.opaque_sheet_pins(ref)` gives (name, shape, point) of the opaque `pin` slots of a read
  reference, as `sch.opaque_wires` does for wires. The reader keeps its rule that a reference's `pin`
  children stay opaque.

### 7. Not composition intent

Block-local groups belong to the block, not to the design.

- They are applied by KiCad's readable layout, always.
- They are applied by Altium block composition when it is in force. Each group becomes a `schematic_block`
  keyed `<instance path>/<key>`, with the title, anchor and `after` mapped. c0251's implicit block of the
  instance keeps the parts that no local group holds, and is dropped when none remain.
- A design-level `schematic_block` that holds a part of a local group takes it. A local group left empty is
  dropped.
- Without block composition, Altium ignores them with no diagnostic. They never raise "unused intent", and
  a KiCad build never refuses them. A library block with groups therefore builds in every mode.

### 8. Model and writer

- `SheetPin(Entity)`: `name`, `shape` (`input`, `output`, `bidirectional`), `position`, `rotation`.
  Implemented 2026-10-29: c0276 had already added the stub (`SheetPin`, `SheetRef.pins`, the writer's
  `pin`, `sch.opaque_sheet_pins`), and its drawn sheets may carry `tri_state` and `passive` pins, so
  `SheetPin` refuses any shape outside those five; block pins use the first three.
- `SheetRef.pins: tuple[SheetPin, ...] = ()` (ordered), omitted when empty. Only created sheets hold
  sheet pins, and read sheets keep them opaque, as wires.
- `sch.write_schematic` writes each sheet pin as a `pin` child of its `sheet`, after the properties and
  before `instances`, with `at`, `effects` and `uuid`. It writes each hierarchical label as
  `hierarchical_label` with `shape`, `at`, `effects` and `uuid`, in the form of S-0367 for both targets
  (`H-K-SCH-BLOCK-PINS`).

### 9. Codes

| code | severity | when |
|---|---|---|
| `build.block-port-merged` | info | two or more port members of one block bind one net; that net keeps global labels on the block sheet |
| `build.block-sheet-name-clash` | error | an Altium port crossing and an inferred crossing of one module have one name |

Both join the closed set of "Generated schematic issue codes" (KiCad) or the Altium build's codes as later
codes, each with an `explain.toml` entry. `DslError` cases are listed in decisions 1 and 2. There is no new
`FEN-` code.

## Risks / Trade-offs

- **KiCad net naming through hierarchy** is the central assumption. Mitigation: the guard proves names
  without a tool, and the KiCad CI job reads the example's netlist with `kicad-cli` on both majors before
  the label rises. If KiCad names such a net otherwise, the fallback is to keep global labels on block
  sheets and add sheet pins as visual only. That is a one-table change in decision 3.
- **Rebuild churn.** The first build after this change rewrites the sheets of block instances (new labels
  and pins). The lens keeps the board, because footprint paths do not change: sheet uuids derive from module
  paths, not from content.
- **Shared arrangement and long names.** One instance with a long outside net name widens every instance's
  cells. This is accepted for sameness. A placements file can override it.
- **Altium net names with port-named entries** are unmeasured until the kit (`H-A-BLOCK-ENTRIES`).
  Until then the evidence stays `INFERRED`, and `--altium-layout grid` with `sheets="flat"` is unaffected.

## Open Questions

1. **Hierarchical labels in a block sheet for power ports too?** Recommended: yes in KiCad (uniform, and
   the global label on the parent keeps the name). Altium keeps its global power ports.
   Decided 2026-10-29: yes in KiCad (a power port is a port like any other on the block's sheet; the root
   keeps the global label), and Altium keeps its global power ports.
2. **Group titles on KiCad sheets** as text items? Recommended: later. `text` is opaque in the model today,
   and adding a text entity is its own change.
   Decided 2026-10-29: later; KiCad sheets draw no group title in this change.
3. **Shared arrangement for Altium module sheets?** Recommended: later. The Altium layout has its own
   packer, and composition already gives equal groups.
   Decided 2026-10-29: later.
4. **Declared port directions as Altium I/O types?** Recommended: not now. The measured table stays.
   Revisit with c0252's direction checks and one kit run.
   Decided 2026-10-29: not now; the measured table of `H-A-SCHX-DIR` stays.
5. **Multi-instance KiCad sheets** (one file for all instances)? Recommended: no, for the naming reason of
   decision 3.
   Decided 2026-10-29: no, for the naming reason of decision 3.

## Relation to the other changes of this batch

- **c0251:** builds on ports, members, port nets, sheet names and implicit Altium groups. It changes no c0251 rule.
- **c0252:** `Rail`, `Ground` and `Logic` ports give hierarchical pins like any port. Directions stay
  c0252's to check.
- **c0268:** independent. A recorded block's name is its id, which shows in the sheet name.
- **c0270:** a block's golden renders (c0256) include its sheet, so a change of groups is reviewed.
- **c0271:** board layout per block, unrelated to the schematic.
- **c0272:** each starter block declares its groups.
- **c0273:** none.
