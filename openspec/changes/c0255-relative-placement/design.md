## Context

- **Source.** `docs/research/circuit-as-code.md`, section 10 ("Placement in code: relative, anchored,
  per block"), core change I. Clean-room: only the concepts are taken (positions relative to parts, pads
  and the board; a block as a rigid group; layouts per group; a block shipped with its layout). No code,
  property name, expression syntax or layout algorithm of tscircuit, JITX or atopile is used.
- **What exists on `dev` (0.6.0, `da300adf`).**
  - `Part.place(x, y, rot=0, side="top", locked=False, *, anchor=None)` in the board frame (origin at the
    outline's top-left corner, Y down; written at `BOARD_ORIGIN`). `anchor` is already taken: a
    `MechanicalIntent` that requires `locked=True` ("Board and placements in the DSL").
  - `part.pad(n)` (`PadRef`) and `part.at(dx, dy)` (`AnchorRef`) for copper intents, resolved by the build
    after placement.
  - `lens.preserve.effective_placements`: locked `place()`, then the board, then `placements.toml`, then
    `place()`, then staging ("Placement precedence").
  - The staging row (`STAGING_OFFSET`, `STAGING_GAP`, `footprint_extent`: the courtyard box, else the pad
    boxes).
  - `placement/`: legality, grid, constrained and region placement; `reuse/`: c0210's rigid fit and copper
    copy, c0227's net-partition pairing, zone copy and group moves with their copper.
  - `package-layering`: `placement` → `model`, `geometry`, `backends.base`; `lens` → `model`, `backends`;
    `cli` may import anything and injects what other packages need.
- **From this batch.** c0251: `@block` functions, `design.use(block, "name", ...)` returning an instance
  handle, ports, local nets, block paths (`buck1/U`). c0250: `edits.toml`, which generalises
  `placements.toml` and becomes level 3.

## Goals / Non-Goals

**Goals**

- Place a part where a designer says it goes ("right of U1's VDD pad, 0.5 mm away, pad 1 in line")
  without computing coordinates, and have that hold when the reference moves in the script.
- Move a block as one piece, arrange its unplaced parts, or bring its proven layout.
- One written precedence for every placement source, so a reader can predict where a part lands.
- Integer nanometres, deterministic, recorded, byte-identical builds.

**Non-Goals**

- See the proposal. In addition: no placement that depends on routing; no relative rotation ("turn like
  U1"): `rot` stays absolute in the frame of the request.

## Today and proposed

**Today (0.6.0):**

```python
u1.place(mm(14), mm(15), rot=90)
c5.place(mm("16.35"), mm("13.2"))  # computed by hand from U1's VDD pad; wrong once U1 moves
j1.place(mm(2), mm(15), rot=90)  # 2 mm from the left edge, also by hand
# a repeated channel: every part placed by hand at n*10 mm offsets
```

**Proposed:**

```python
board = design.board(mm(40), mm(30))                     # now returns a BoardRef
u1.place(mm(14), mm(15), rot=90)
c5.place(right_of=u1.pad("VDD"), gap=mm("0.5"), by=c5.pad(1))   # pad 1 of C5, 0.5 mm right of VDD
j1.place(left=board.left + mm(2), center_y=board.center_y, rot=90)
sen.place(right_of=mcu, gap=mm(3))                       # courtyards 3 mm apart, centres aligned

@block
def buck(b, ...):
    u = b.part("U", device="Example:BUCK_6V_2A"); u.place(mm(0), mm(0))   # block frame
    l = b.part("L", device=inductor(...)); l.place(right_of=u, gap=mm(1))
    b.layout(row(gap=mm(1)))                             # the block's other parts, in a row
    ...

p1 = design.use(buck, "buck1"); p1.place(mm(10), mm(8))           # the whole block, rigidly
p2 = design.use(buck, "buck2"); p2.place(below=p1, gap=mm(2), align="start")
p3 = design.use(buck, "buck3"); p3.layout(reuse="blocks/buck.kicad_pcb", copper=True)
p3.place(right_of=p1, gap=mm(4))
```

## Decisions

### 1. `place()` takes references; the build resolves them

`Part.place(x=None, y=None, rot=0, side="top", locked=False, *, anchor=None, right_of=None,
left_of=None, above=None, below=None, gap=0, align="center", left=None, right=None, top=None,
bottom=None, center_x=None, center_y=None, by=None)`.

- The call records a `RelativeRequest` (plain data, `dsl/relative.py`); `placements(design)` keeps
  returning only absolute `Placement`s, and the new `relative_requests(design)` returns the others.
- The build resolves every request after the footprints are known, because a box needs the footprint
  (`dsl` imports no geometry and knows no footprint). This is the pattern of copper intents and generated
  copper.
- **Why `by` and not `anchor`.** `anchor` already means a mechanical intent of a locked part. Giving the
  word a second meaning by type would break the reading of existing scripts. `by=c5.pad(1)` reads as
  "placed by its pad 1".
- **Alternative considered:** computed positions in the script (`u1.pad("VDD").x + mm("0.5")`). Rejected:
  the script cannot know pad positions without importing geometry and the libraries, and the value would
  be frozen at script time instead of following the effective placement of the reference.

### 2. References and edges

- **References:** a `Part` (inside a block, also `inst.part(name)` of c0251), a `PadRef` (`u1.pad("VDD")`; with several pads of that number, `index=`),
  a block instance (c0251), and the `BoardRef` that `design.board(...)` now returns (also
  `design.board_ref`). Each has the edges `left`, `right`, `top`, `bottom`, `center_x`, `center_y`.
- **Edge expression:** an edge plus or minus a length (`board.left + mm(2)`); nothing else. A plain length
  is a coordinate of the frame.
- **Relations:** `right_of=R` puts the subject's box left edge at `R.right + gap`; `left_of` its right
  edge at `R.left − gap`; `above` its bottom edge at `R.top − gap`; `below` its top edge at
  `R.bottom + gap` (Y down). `gap` is a length, default 0 (courtyards touching is legal).
- **Alignment** on the other axis: `align="center"` (default), `"start"` (left or top edges equal) or
  `"end"`. With `by=pad`, the cross axis aligns the subject pad's centre with the reference's centre.

### 3. Axis determination

Each axis is set by exactly one source: X by `x`, `left`, `right`, `center_x`, `right_of` or `left_of`;
Y by `y`, `top`, `bottom`, `center_y`, `above` or `below`. A relation also gives its cross axis by
`align` unless that axis is set explicitly, which then wins. Two sources for one axis, no source for an
axis, `align` without a relation, `gap` without a relation, or `x`/`y` given positionally together with an
edge key of the same axis raise `DslError` at the call.

### 4. Measuring boxes and integer arithmetic

- A part's box is `footprint_extent` (the courtyard box, else the pad boxes) turned by `rot` and mirrored
  for the bottom side, in the frame; with `by=pad`, the subject's box is that pad's box instead (a
  pad's centre is its position).
- A block instance's box is the union of its placed children's boxes in the frame of the request; the
  board's box is `outline.outline_box`.
- A turn that is not a quarter turn takes the axis-aligned bounds of the turned box, rounded outward to
  whole nanometres. A centre is `(a + b) // 2` (floor). The part's position is then the translation that
  puts its box where the request says. Everything is integer nanometres.

### 5. Resolution order

- A request depends on the parts and blocks it references. Requests are resolved in topological order,
  ties by component path in code-point order.
- A cycle is `layout.relative-cycle` (error, the build writes nothing), naming the paths of the cycle.
- A reference that has no placement when its turn comes (staged, or itself unresolved) gives
  `layout.relative-unresolved` (warning) and the part is staged.
- Evaluation order inside one frame: levels 1 to 3 of the precedence; absolute requests; the strategy
  of the frame for parts with no request (decision 8); then the relative requests, which may reference
  parts that the strategy placed; then staging. Which source *wins* for a part is the precedence
  (decision 10); this is only the order in which positions become known.

### 6. Locked relative requests

A locked relative request (level 1) must be stable without the board: every reference must be locked
(absolute or relative, recursively), a locked block, or the board. Otherwise `placements` conversion
raises `DslError` naming the unlocked reference. This keeps "locked" meaning "the script decides",
whatever was edited in KiCad.

### 7. Block pose and rigid group

- `inst.place(x=None, y=None, rot=0, locked=False, **relation)` on a c0251 instance sets the block's
  **pose** (translation and rotation in the parent frame); relations use the block's box. `b.place(...)`
  is not offered inside the body: a block does not place itself.
- Children's requests (absolute, relative, strategy results) are in the **block frame** and composed with
  the pose. Without a pose, the pose is the identity, so a block written today with board coordinates
  builds unchanged.
- References inside a block body must be in the same block (siblings, nested instances); a reference to
  a part outside the block, or to the board, is a `DslError`: such a part would not move with its block.
  Relations of the instance itself may reference anything in the parent frame.
- **Rigid move of a kept layout.** `.fenolite/build.json` records each block's resolved pose. When the
  new pose differs, every child whose placement comes from the board or the placements file is moved by
  `new ∘ old⁻¹`, with its copper as c0227's group move does (copper joined only to the block's pads
  moves; other copper stays with `place.copper-left`), and the build gives `layout.block-moved` (info).
  Locked children follow their posed request anyway.
- A turn that is not a quarter turn rounds each coordinate half to even (the geometry kernel's rule);
  quarter turns are exact.
- **Not in this change:** a block mirrored to the other side (open question 1).

### 8. Layout strategies

`row(gap=0, align="start")`, `column(gap=0, align="start")`, `grid(columns, gap=0)` and
`pack(width, gap=0)`, each with an optional `at=(x, y)` origin in the frame (default `(0, 0)`), set by
`b.layout(...)` (the block's default), `inst.layout(...)` (this instance, which wins) or
`design.layout(...)` (the top level).

- A strategy places the frame's parts that no other source places and that have no request, plus nested
  instances that have no pose (as one box each), in the order they were created in the body.
- **row**: boxes left to right from `at`, `gap` apart, aligned on their top edges (`start`), centres or
  bottom edges. **column**: top to bottom, aligned on left edges, centres or right edges.
- **grid**: cells of the largest box's size plus `gap`, `columns` per row, each box centred in its cell.
- **pack**: shelf packing within `width`: boxes sorted by height, tallest first, then creation order;
  each placed at the right of the previous on the current shelf if it fits, else on a new shelf under the
  tallest box of the shelf, `gap` apart. A box wider than `width` gets its own shelf and
  `layout.strategy-overflow` (warning).
- Rotation and side are those of the part's library definition (0°, top) unless the part's request gives
  only `rot` or `side` (`place(rot=90)` with no position keeps the strategy and turns the part).
- A block with a strategy and no pose, at the top level without `design.layout`, is staged as **one box**
  in the staging row, its parts in their strategy positions, so the group is never scattered.

### 9. Block layout reuse

`b.layout(reuse=PATH, copper=False)` or `inst.layout(reuse=PATH, copper=False)`; `PATH` is relative to
the file that defines the block (body) or to the script (instance).

- **Reference board.** Any board that `read_board` reads (KiCad or Altium), laid out for the block alone:
  typically the build of a bench script whose top is one instance of the block. Its footprints carry the
  block-local path (`fenolite.path` = `U`, `L`, `FB_top`) and its nets are named by the block's ports and
  local nets.
- **Parts by path.** Reference part `U` is the instance's `buck3/U`. A child without a reference part is
  left to staging with `reuse.unknown-part` (warning here, since the rest of the block is still placed).
- **Transform.** The reference positions, taken in the `place()` frame of the reference board, are
  composed with the block pose. There is no search: c0210's per-part fit runs under this transform only,
  to check the pads (`reuse.no-fit` for a footprint that differs).
- **Nets by port.** Reference net `VIN` (a port) maps to the parent net connected to the instance's
  `VIN`; a local net `FB` maps to `buck3/FB`. A reference net that is neither is `reuse.port-unmapped`
  (error) when `copper=True`, and is ignored otherwise. No majority vote, unlike c0210's inference.
- **Copper.** With `copper=True`, c0210's `copy_copper` and c0227's zone copy run with this explicit net
  map, settle as c0210 does, and the kept copies are locked items of the build.
- Reuse is level 5: it places only children that no level 1 to 4 source placed. A rebuilt instance keeps
  its board layout like any other part (level 2).

### 10. The precedence, written down

1. A locked `place()`, absolute or relative, composed with its block poses.
2. The existing board (a kept footprint), moved rigidly when its block's pose changed (decision 7).
3. The placements file (`placements.toml`; `edits.toml` once c0250 lands).
4. An unlocked `place()`, absolute or relative, composed with its block poses.
5. The strategy of the innermost enclosing frame that has one: a layout strategy or a block reuse.
6. The build's staging (a strategy group without a pose as one box).

This list goes into `docs/lens.md`, "Placement precedence", and into the `placement` page of the agent
guide.

### 11. Recording

- `result.placement.relative`: per resolved part, `path`, `request` (the canonical text, e.g.
  `right_of=U1.pad(VDD) gap=0.5mm by=pad(1)`), `refs` (the reference positions used) and `at`,
  `rotation`, `side`; `result.placement.blocks`: per block, its pose and its strategy.
- `.fenolite/build.json` records the resolved poses (needed by decision 7) and a SHA-256 of the resolved
  relative placements.
- Two builds of equal inputs give equal records and equal bytes.

### 12. Codes

| code | severity | when |
|---|---|---|
| `layout.relative-cycle` | error | relative requests reference each other in a cycle |
| `layout.relative-unresolved` | warning | a reference has no placement; the part is staged |
| `layout.strategy-overflow` | warning | a box wider than a `pack` width, or a strategy group beyond the outline |
| `layout.block-moved` | info | a block's pose changed and its kept children moved with it |
| `reuse.port-unmapped` | error | a reference net of a block reuse is neither a port nor a local net |

The first four join `layout`'s issue codes (`lens`), the last `reuse.codes.ISSUE_CODES`; each is
explained by `fenolite explain`. No new `FEN-` code: argument errors are `DslError` (the build's
`FEN-3004`).

### 13. Packages

- `placement/relative.py`: boxes, relations, topological resolution; `placement/strategies.py`: the
  four strategies. Pure functions over model types and boxes.
- `lens.preserve.effective_placements` gains a `resolver` parameter; `cmd_build` injects the placement
  resolver and the reuse adapter, because `lens` may not import `placement` or `reuse`. No import edge
  changes.

### 14. Evidence

- `placement.relative.EVIDENCE` is `INFERRED` with `H-G-REL-RESOLVE` (a resolved position satisfies its
  request exactly, measured on the written board by the same box function).
- A KiCad test builds `examples/relative/` for targets 9 and 10, reads the board back and checks every
  relation on the read-back footprints: `KICAD-VERIFIED` for "the written board holds the resolution".

## Relation to the other changes of the batch

- **c0251** gives blocks, instances and paths; poses, strategies and reuse attach to its instance handle
  and block builder. Task 0.1 records its final names.
- **c0250**: level 3 becomes `edits.toml`, and level 2 becomes c0250's three-way merge of base, code and
  CAD per property. A resolved relative position is the *code* side of that merge: when a reference moves
  in the script and the follower was not moved by hand, the follower follows (c0250, open question 6,
  recommends resolving against the merged positions of the references, which decision 5 does). c0250
  also holds a delta of "Placement precedence"; whichever change archives second regenerates its MODIFIED
  block from the living text and keeps both edits.
- **c0247**: `decouple(..., near=u.VIN)` records a `near()` rule; a later change may let it also place the
  capacitor with `right_of`/`by` when the part has no request (open question 3).
- **c0254** is the other half of step 6; independent.
- **c0256**: tests read `result.placement.relative` and assert relations on the model.
- **c0245** (viewer) can draw block outlines from `result.placement.blocks`.

## Risks / Trade-offs

- **Board wins over unlocked relative requests** (until c0250). After the first build a part stays where
  the board has it, even when its reference moves in the script; this is today's rule for `place()`.
  With c0250's three-way merge, the follower follows unless it was moved by hand. A designer who
  wants the relation to hold locks it (decision 6) or rebuilds with `--discard-layout`. The `placement`
  guide page says so, and `layout.place-overridden` names the relation.
- **Non-quarter turns** introduce rounding of up to 1 nm per coordinate; reported positions are the
  rounded ones, and the relation test allows that 1 nm.
- **Rigid moves with copper** reuse c0227 code on a build path for the first time; the build's copper
  guard still runs after them.

## Open questions

1. **Mirrored block pose** (`inst.place(..., side="bottom")`, flipping every child to the other side).
   Recommended: a later change, after a reference board needs it; it touches layer mapping of reused
   copper.
2. **Creation order or path order for strategies.** Recommended: creation order (what the author reads),
   with path order only as the order of staging, as today.
3. **Should `near=` of c0247's helpers place?** Recommended: no in this change; a helper that both checks
   and places hides which one failed. Keep `near()` a rule and write the relation explicitly.
4. **Relations to parts on the other side.** `right_of` measures in the top view whatever the sides.
   Recommended: keep the top view, as the board frame already is.
