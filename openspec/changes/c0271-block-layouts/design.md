## Context

- **Source.** `docs/research/circuit-blocks.md` (2026-10-29), section 3.5 "The reusable layout, versioned"
  and the row c0271 of section 4. From the comparison of section 1, only concepts are taken: a block that
  carries its own laid-out sub-board, a layout applied to matching parts, and a stale layout detected rather
  than applied. No file format, key name, algorithm or text of another tool is used.
- **What exists on `dev` (0.6.0).** c0210 and c0227 (archived, `layout-reuse`): `fit_block` fits a block of a
  reference board onto target parts over quarter turns and both mirrors, `copy_copper` maps tracks, arcs,
  vias and zones through the block transform (layers mirrored through the stack when the anchor changes
  side), settling prunes free ends and islands, kept copies are locked, and group moves carry the copper
  that joins only the group's pads (`place.copper-left` for the rest).
- **What the batch gives.**
  - c0251: blocks, instances, block paths, ports and local nets; the model's `Module.block` and `Port`.
  - c0255: `inst.place(...)` sets a block pose in the parent frame; children are placed in the block frame
    and composed with the pose; level 5 of the precedence is "the strategy of the innermost frame: a layout
    strategy or a block reuse"; `b.layout(reuse=PATH, copper=False)` with parts by local path and nets by
    port (`reuse.port-unmapped`); `.fenolite/build.json` records the resolved poses; a pose change moves
    kept children rigidly (`layout.block-moved`). It leaves the mirrored pose out (non-goal, open
    question 1).
  - c0250: `edits.toml` as level 3, and the three-way merge of base, code and CAD per property.
  - c0268: the block record's `id` and `version` (`MAJOR.MINOR.PATCH`), recorded on each instance.
- **The gap.** A board file as a block asset is opaque in review, untied to a version, silently wrong when
  the part set changes, and top-side only.

## Goals / Non-Goals

**Goals**

- A layout that a reviewer reads as text, tied to the block id and version, and checked against the
  instance before it is applied.
- Applied exactly (integer nanometres), on either side, by the same composition as every other block
  placement.
- Captured from a real laid-out instance with the existing fit, under plan and confirm.

**Non-Goals**

- See the proposal. Also: no layout per parameter value (one file per block; a block whose part set
  varies with parameters ships the layout of its default set, open question 2).

## Today and proposed

```python
# c0255 today: a whole board file, fitted part by part
@block(id="Fenolite:voltage_divider", version="1.0.0", summary="Resistive divider", category="analog")
def voltage_divider(b, *, vout=volt("3.3").pct(5)):
    b.layout(reuse="voltage_divider.kicad_pcb", copper=True)
    ...


# proposed: the block's own layout file, tied to its version and parts
@block(id="Fenolite:voltage_divider", version="1.0.0", summary="Resistive divider", category="analog")
def voltage_divider(b, *, vout=volt("3.3").pct(5)):
    b.layout(reuse="layouts/voltage_divider.toml", copper=True)
    ...


a = design.use(voltage_divider, "sense_a")
a.place(mm(10), mm(8))
c = design.use(voltage_divider, "sense_b")
c.place(mm(10), mm(8), side="bottom")  # mirrored: the same layout on the other side
```

## Decisions

### 1. The file: `fenolite.block-layout.v0`

```toml
schema = "fenolite.block-layout.v0"
block = "Fenolite:voltage_divider"
block_version = "1.0.0"
parts_digest = "sha256:5d1c…"   # 64 hex digits in the file
nets_digest = "sha256:0b7e…"
licence = "Apache-2.0"
evidence = "INFERRED"

[parts.bot]
at = ["0mm", "2.5mm"]
rotation = "90deg"
side = "top"
footprint = "Fenolite:Chip_0603"

[parts.top]
at = ["0mm", "0mm"]
rotation = "90deg"
side = "top"
footprint = "Fenolite:Chip_0603"

[[tracks]]
net = "port:OUT"
layer = "F.Cu"
width = "0.25mm"
start = ["0mm", "0.8mm"]
end = ["0mm", "1.7mm"]
pads = ["top.2", "bot.1"]

[[vias]]
net = "port:LO"
at = ["0mm", "3.6mm"]
size = "0.6mm"
drill = "0.3mm"
layers = ["F.Cu", "B.Cu"]
```

- **Keys.** Top level: `schema`, `block`, `block_version`, `parts_digest`, `nets_digest`, `licence`,
  `evidence`, optional `captured_from` (a relative path, informative). Tables: `parts.<local path>` (the
  part's path relative to the instance; a nested block's part is `sub/R`, quoted), `[[tracks]]`,
  `[[arcs]]` (`start`, `mid`, `end`), `[[vias]]`, `[[zones]]` (`net`, `layers`, `outline`, the model's zone
  settings as text with units, no fill). Any other key is `FEN-3004` naming the file and the key; a higher
  schema version is `FEN-3002`. Read with `tomllib` and `parse_float=Decimal`; no float is created.
- **Units.** Lengths and angles are text with a unit, parsed exactly as c0259's records are; a length that
  is not whole nanometres or an angle that is not whole microdegrees is `FEN-3004`. `capture` writes
  millimetres with the exact digits of the nanometres and degrees with the exact digits of the
  microdegrees.
- **Frame.** The block frame of c0255 (the `place()` frame: origin, Y down). `side` is the part's side in
  a block whose pose is on the top. Layers are the model's names; `F.Cu` is the near side of the block.
- **Local nets.** `port:<PORT>`, `port:<PORT>.<member>` for a member of an interface port, `net:<name>`
  for a local net (`net:sub/FB` inside a nested block).
- **Local pads.** `pads` lists `<local path>.<pad number>` of the pads an item's ends lie on, written by
  `capture`; it is used to check the copy after the transform (decision 4), never to move geometry.
- **Licence and evidence.** A shipped (`Fenolite:`) layout is `Apache-2.0` and at most `INFERRED` until a
  KiCad DRC of its usage board raises it (c0272); a project layout may hold any licence text.
- *Alternatives considered.* A trimmed `.kicad_pcb`: rejected, not reviewable as text, KiCad-specific, and
  it brings no version or digest. Copper by pad-to-pad topology only (`from = "top.2", to = "bot.1"`):
  rejected, a track's route is the point of a layout; topology alone would need a router.

### 2. The digests

- `parts_digest` is `sha256:` and the SHA-256 of the canonical JSON of the list, sorted by local path, of
  `[local path, footprint lib id, [pad numbers sorted in code-point order]]` of every part of the instance.
- `nets_digest` is the SHA-256 of the canonical JSON of the sorted list of `[local path, pad number, local
  net]`, with `nc` for a pad on no net and `global:<name>` for a pad on a script-named net that no port binds
  (c0251's `build.block-net-escape`).
- Both are computed from the built model after part selection (c0254) and footprint resolution, so a
  parameter that adds a part, a project default that changes the case, or a pick of another footprint
  changes `parts_digest`; a value change (61.9 kΩ to 64.9 kΩ in one case) changes neither.
- Pad geometry is not in the digest: a footprint whose lands changed size keeps its positions, and the
  copper check of decision 4 judges the copper.
- *Alternative considered.* One digest of everything. Rejected: a different net map must still allow the
  placement, and the finding must say which half differs.

### 3. Applied as level 5

`b.layout(reuse="layouts/x.toml", copper=False)` or `inst.layout(reuse=..., copper=False)`; the path is
relative to the file that defines the block (body) or to the script (instance), as c0255. The suffix
`.toml` selects this file kind; any other suffix keeps c0255's board reuse.

For each instance with such a layout, the build:

1. reads the file; another `block` id or another MAJOR of `block_version` than the instance's record is
   `reuse.layout-block` (error, the build writes nothing);
2. computes the instance's digests; a different `parts_digest` is `reuse.layout-stale` (warning) naming the
   instance, both digests and the first difference (a part added or removed, a footprint changed), and the
   layout is not applied: its children fall to level 6 (staging);
3. places each child that no level 1 to 4 source places at its layout position composed with the block
   pose (decision 5), exactly, with no search;
4. with `copper=True` and an equal `nets_digest`, maps each item's local net to the instance net (a port
   to the parent net joined to it, a local net to `<instance>/<name>`, as c0255's "Nets mapped by port"),
   maps the geometry with the same transform and the layers through the stack (mirrored on the bottom,
   c0210's rule; an unknown layer drops the item as `layer-unknown`), checks that every end listed in
   `pads` lies on its pad (else the item goes as c0227's `pad-lost`), then settles the copper as c0210
   does; kept copies are locked items with uuids derived from `block-layout:<instance path>:<item key>`;
5. with a different `nets_digest`, places the parts and copies no copper: `reuse.layout-nets` (warning);
6. with equal digests and an older MINOR or PATCH, applies the layout with `reuse.layout-older` (info).

`fenolite blocks show` (c0268) gains `layout`: the path that the body's `b.layout(reuse=...)` names when
c0268's describe runs the block with its defaults, or `null`.

`result.placement.blocks` (c0255) gains per instance `layout`: `{path, sha256, status}` with status
`applied`, `stale`, `nets-differ`, `older` or `refused`. `.fenolite/build.json` records the applied file's
SHA-256 per instance.

### 4. Copper checks on apply

- The c0210 settling runs unchanged: `tidy.prune`, islands, and the copper check before and after; a new
  finding drops the item with its code, reported as `reuse.copper-dropped` (info), as today.
- `pads` lets the build tell a moved land from a wrong layout: an end that no longer lies on its pad after
  a footprint's land changed is `pad-lost`, not a short.

### 5. Mirrored block poses

`inst.place(x=None, y=None, rot=0, locked=False, *, side="top", **relation)` gains `side`.

- With `side="bottom"`, a child's block-frame placement `(x, y, θ, s)` becomes `(−x, y)` with the side
  `s` flipped and the rotation that the model's footprint flip gives (`H-G-FLIP`), then the pose's turn and
  translation apply: `pose = T(x0, y0) ∘ R(rot) ∘ M`. Each pad of a mirrored instance is therefore the
  mirror image, about the pose's vertical axis, of the same pad on a top instance with the same pose.
- Copper of a block layout maps through the same transform, with each layer mapped to its mirror in the
  stack (`F.Cu` to `B.Cu`, inner layers to their mirror), as c0210 maps a reference whose anchor changed
  side.
- c0255's relations of a mirrored instance use its mirrored box. A rigid move whose old and new poses differ
  in side moves kept children with the mirror included and their copper with mirrored layers; the build
  gives c0255's `layout.block-moved`.
- Locked relative requests inside a mirrored block are composed the same way; nothing else changes.
- *Alternative considered.* Mirroring about the horizontal axis. Rejected: the flip of a single footprint to
  the bottom is about the vertical axis in the board's top view, and a block must flip as its parts do.

### 6. `fenolite blocks capture BOARD --instance PATH`

`fenolite blocks capture BOARD --instance PATH [-o FILE] [--origin pose|anchor] [--anchor LOCAL]
[--copper/--no-copper] [--dry-run | --confirm --plan ID]`

1. Reads the output folder `BOARD` (the board and `.fenolite/`): the instance's module must be a block
   instance with a recorded block id and version, else `FEN-2001` naming the closest instance paths.
2. Every part of the instance must be on the board, else `blocks.capture-unplaced` (error).
3. **Frame.** `--origin pose` (the default when the build recorded a pose other than the identity) takes
   each placement through the inverse of the pose, mirror included. `--origin anchor` (the default
   otherwise) translates so that the anchor part (`--anchor`, by default the smallest local path) lies at
   the origin, keeping rotations and sides.
4. **Copper** (unless `--no-copper`) is chosen by c0227's group rule: per net, each joined group of tracks,
   arcs and vias that holds a pad of the instance and no other pad, and each zone whose stored fill joins
   pads of the instance only. Copper that joins a pad outside the instance stays out and gives
   `blocks.capture-copper-left` (info) naming the net; a pad on a script-named net that no port binds gives
   `blocks.capture-escape` (warning).
5. **Round trip.** The layout is applied in memory to the instance through the frame of step 3, and
   c0210's `fit_block` fits the board's instance (reference) onto the applied one (target) with a tolerance of
   1 µm; a part without a fit, or a copied item that the settling drops, is `blocks.capture-check-failed`
   (error), and nothing is written.
6. **Output.** `-o FILE`, or `<folder of the block's module>/layouts/<name>.toml` when that folder lies under
   the working directory; for a block of the installed package, `-o` is required (`FEN-2001`). A vendored
   library block (c0273) lies under the working directory, so the default writes into its vendored folder,
   which then differs from its pin (c0279's `library.item-modified` on the next `fenolite get`). The file is written through the plan and confirm protocol with a receipt; keys in
   a fixed order, parts by local path, items by layer, net and coordinates, so equal inputs give equal bytes.

`result.capture`: `instance`, `block`, `version`, `file`, `parts`, `tracks`, `arcs`, `vias`, `zones`,
`left` (the nets whose copper stayed out). The command does not edit the block's Python; its hint names the
`b.layout(reuse=...)` line to add.

The recommended way to capture a library block is a **bench script** whose top is one instance with every
port taken to a connector, so that no port copper reaches another part (c0272's usage examples).

### 7. Precedence, c0255 and c0250

- A block layout is level 5 of c0255's precedence, the same level as a strategy or a board reuse, and an
  instance's `inst.layout(...)` wins over the body's `b.layout(...)`. Per part, a locked `place()` (1), the
  board (2), `edits.toml` (3) and an unlocked `place()` (4) win; the layout places what is left.
- **Before c0250**, a part kept from the board stays where the board has it, and the copies of the first
  build stay with the board; when the layout file's SHA-256 differs from the one `build.json` recorded,
  the build gives `reuse.layout-changed` (info) naming the instance, so the user knows the file is not
  being followed (`--discard-layout` or a pose change re-applies it).
- **With c0250**, the layout's resolved positions and copies are the *code side* of the three-way merge, as
  c0255's resolved relative positions are: a part or copy the user did not move in CAD follows a new layout;
  one moved by hand keeps its CAD position under c0250's rule, and a conflict is c0250's. `reuse.layout-changed`
  is then given only for kept items that the merge did not update.
- `fenolite sync --to-source` (c0250) writes hand moves of block parts to `edits.toml` by path; it never
  writes a layout file. Capturing is the explicit step that turns a hand layout into a block asset.

### 8. Codes

| code | severity | when |
|---|---|---|
| `reuse.layout-block` | error | the layout names another block id or another major version |
| `reuse.layout-stale` | warning | `parts_digest` differs; the layout is not applied |
| `reuse.layout-nets` | warning | `nets_digest` differs; parts placed, no copper copied |
| `reuse.layout-older` | info | applied; captured for an older minor or patch version |
| `reuse.layout-changed` | info | the file changed since the build that applied it and kept items do not follow it |
| `blocks.capture-unplaced` | error | a part of the instance is not on the board |
| `blocks.capture-check-failed` | error | the round trip leaves a pad beyond 1 µm or drops a copied item |
| `blocks.capture-escape` | warning | a pad of the instance is on a script-named net that no port binds |
| `blocks.capture-copper-left` | info | copper of a net joins a pad outside the instance and stays out |

The `reuse.*` codes join `fenolite.reuse.codes.ISSUE_CODES`; the `blocks.*` codes join c0268's block codes.
Each is explained by `fenolite explain` and listed in `docs/cli-contract.md`, "Block layouts". No new `FEN-`
code.

### 9. Files and packages

- `src/fenolite/reuse/blocklayout.py`: `BlockLayout` (frozen), `read_block_layout(path)`,
  `write_block_layout(layout) -> bytes`, `parts_digest(...)`, `nets_digest(...)`,
  `apply_block_layout(layout, instance, pose, stack) -> LayoutApplication`, `capture_block_layout(...)`.
  Pure over model types; `reuse` keeps its import edges (`model`, `geometry`, `backends.base`, `tidy`).
- `cli/cmd_build.py` injects the adapter into c0255's resolver, as it injects board reuse.
- `cli/cmd_blocks.py` (c0268) gains the verb `capture`.
- c0255's `placement/relative.py` composes the mirrored pose; `dsl/block.py` accepts `side=`.
- `docs/formats/fenolite/block-layout.md` documents the format (Fenolite's own; evidence `INFERRED`).

### 10. Evidence

| behaviour | level before merge |
|---|---|
| reading, digests, refusals | `INFERRED`, unit tests |
| apply, mirrored pose | `INFERRED`, `H-G-BLOCK-LAYOUT`: every applied pad within 1 nm of the transform, measured on authored blocks |
| capture round trip | `INFERRED`, unit tests on authored boards |
| built boards | `KICAD-VERIFIED` read-back on targets 9 and 10 (`tests/kicad/blocks/test_block_layouts.py`) |
| laid-out usage boards | `KICAD-VERIFIED` with `H-K-BLOCK-LAYOUT-DRC`: KiCad DRC finds no violation and no unconnected item inside the block, both sides |

## Risks / Trade-offs

- **A stale layout stages parts.** A warning, not an error, keeps a parameter study building; `check`
  reports the staged parts. c0270's usage builds fail on any warning, so a shipped block never ships a
  stale layout.
- **Footprint land changes** keep positions and may drop copper (`pad-lost`); the KiCad DRC test of each
  shipped layout catches it in CI.
- **Mirrored rigid moves** run c0227's group move with a mirror for the first time; the build's copper guard
  still runs after them, and the KiCad test covers a block flipped between two builds.
- **Captured copper on ports.** Copper of a port that also reaches outside parts is left out; capturing from
  a bench script avoids it, and `blocks.capture-copper-left` says what was left.

## Open Questions

1. Should `reuse.layout-stale` be an error? **Recommended:** a warning; an error would stop every build that
   explores parameters. A release gate reads the warning in `issues`, and c0270's usage builds refuse it.
2. Several layouts per block, chosen by parameters (`layouts/voltage_divider.0402.toml`)? **Recommended:**
   later; the digest names the part set, so a lookup by digest among several files is a small extension.
3. Should a layout file live in the design lock? **Recommended:** no; the lock pins the block version
   (c0268), and the file ships with that version. `build.json` records the SHA-256 for review.
4. Should `capture` also edit the block's Python? **Recommended:** no; Fenolite does not rewrite scripts.

## Relation to the other changes of this batch

- **c0255** gives poses, level 5 and the port net map; this change adds the file kind, the mirrored pose
  (its open question 1) and the capture. Whichever change archives second regenerates the delta of
  `placement-in-code`.
- **c0268** gives the block id and version this file is tied to, and the `fenolite blocks` group.
- **c0269** (block schematic) is independent.
- **c0270** tests layouts: `PartView.at` and `read_block_layout` in a block's tests; the KiCad DRC test runs in
  `tests/kicad/blocks/`.
- **c0272** ships one layout per starter block, captured from its usage example.
- **c0273**: a library block item ships its layouts in its item folder; capturing into a vendored copy edits it.
- **c0250**: decision 7.
