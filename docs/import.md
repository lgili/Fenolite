# Importing a board as code

`fenolite import PATH --to python --out DIR` turns a KiCad or Altium board into a Fenolite project folder: a
`design.py` that rebuilds the board, its copper as tables, a vendored library and a record of where it came
from (change c0275). The command contract is `docs/cli-contract.md`, "import".

```sh
fenolite import upstream/board/board.kicad_pro --to python --out boards/board --dry-run --json \
    --licence CERN-OHL-S-2.0 --copyright "2024 The Board Authors" --source https://example.invalid/b.git \
    --revision 0123abcd --licence-file upstream/board/LICENSE --timestamp 2026-10-30T00:00:00Z
fenolite import ... --confirm --plan <plan_id>
fenolite build boards/board/design.py --out build/board --confirm
```

Converted third-party boards do not belong in the Fenolite repository: they are published, each under its
upstream licence with its `NOTICE` and `PROVENANCE.json`, in the separate `fenolite-library` repository
(c0279). Tests of the tool import boards authored for Fenolite into temporary folders only, and a residue
test flags any tracked `.py` file holding a `Converted from <URL>` line without the marker `Authored for
Fenolite`.

## Inputs

| input | read by | notes |
|---|---|---|
| `.kicad_pro`, `.kicad_pcb`, `.kicad_sch` | the KiCad readers | the board of the project is read; the project file adds the net classes and minimums, `.kicad_dru` the custom rules |
| a board below the read floor (KiCad 7 and older) | `kicad-cli pcb upgrade` on a private copy, then the readers | refused with `--no-upgrade` (exit 3, `FEN-3003`) |
| Altium `.PrjPcb`, `.PcbDoc` | Fenolite's Altium reader, converted in memory by `fenolite convert --to kicad` (verified), then the KiCad emitter | the inputs recorded are the Altium files; `--adopt` is refused |
| anything else (Eagle, EasyEDA, legacy libraries) | none | exit 2, `FEN-2001`, naming the kind |

A board without a schematic imports: the parts come from its footprints, the netlist from its pad nets.

## The folder

```
boards/board/
  design.py        # header, board, nets, classes, minimums, parts and modules, connections, placements,
                   # zones, rule areas, drawings, then copper.apply(design, nets)
  copper.py        # track_table, arc_table and via_table calls
  design.lock      # every part key and its ref (c0249)
  fp-lib-table     # project tables naming ${KIPRJMOD}/lib/...
  sym-lib-table
  lib/<nickname>.pretty/<name>.kicad_mod
  lib/<nickname>.kicad_sym
  PROVENANCE.json  # fenolite.import-provenance.v0
  LICENSE NOTICE   # copies of --licence-file, byte for byte
```

No absolute path is written anywhere. Every statement is ordered by stable keys (net names, component
paths, item keys, then coordinates), so the same inputs, flags and `--timestamp` give the same bytes on
every platform, and every emitted `.py` file is left unchanged by `ruff format` at line length 110.

## The code

- **Coordinates** are the source points minus `BOARD_ORIGIN`, the frame of `place()`, so the build writes
  the source coordinates exactly. Lengths are written `mm("12.7")` with the shortest exact decimal, angles
  as whole degrees or an exact decimal string.
- **The board** is `board(width, height)` for a rectangle at the origin, else `board(outline=…)` with
  `arc_to` steps, and one `cutout()` per inner ring, from the board's root `Edge.Cuts` items (the edges of
  footprints come back with their footprints).
- **Nets** keep their source names. The single-pad nets KiCad names `unconnected-(…)` are pads on no net and
  are not written.
- **Parts** have explicit refs: `Part("R201", "Mini:Mini_R_0603", footprint="Mini:Mini_R_0603", value="1k",
  name="R101")`. Their placements keep the source lock flags (the import does not lock what the source did
  not lock). A part's own properties (not `Reference`, `Value`, `Datasheet`, `Description`, KiCad's sheet
  fields or `fenolite.*`) are written as `properties=`.
- **Modules.** A board built by Fenolite carries each component's path (`fenolite.path`): the import
  rebuilds the modules from it, the part's key the last segment (`name=` when it is not the ref). Another
  KiCad board gives each footprint's sheet path (`sheetname`, `/power/ch1/`) as nested modules, each sheet
  name lowered to `[a-z0-9_]` (`import.sheet-renamed` when that changes it), the key the ref. A board
  without either gives a flat design whose keys are the refs. One module file per sheet (`sheets/`, a
  repeated sheet one function) is a later step: the modules are written in `design.py`.
- **Rules.** The project's net classes but `Default` become `design.rules.netclass()`; the custom rules a
  build writes for minimums, and the board-setup minimums that differ from a new project's, become
  `design.rules.minimum()`. Any other custom rule is unexpressed.
- **Zones and rule areas** are written with their outlines and settings. A zone named after its net keeps
  that name; another named zone keeps its name; an unnamed one gets `key="<net>/<n>"`. A rule area keeps
  a valid unique name, else gets `key="area/<n>"`.
- **Drawings** on silkscreen, mask, fabrication and user layers become `line`, `rect`, `circle`, `arc`,
  `polygon` and `text` calls keyed `<layer>/<kind>/<n>`. A text may also be on a copper layer, and keeps
  its knockout, bold, italic and font face, a size of two values, several lines or no character (change
  c0277); an aligned or orthogonal dimension becomes a `dimension` call with its extension offset.

## Copper tables

`copper.py` writes the tracks, arcs and vias as tables (`docs/dsl.md`, "Copper tables"): one table per net,
layer, width and lock flag for tracks and arcs, keyed `<net>/<layer>/<n>`, and per net, sizes, kind, span,
protection and lock flag for vias, keyed `<net>/via/<n>`, rows sorted by their coordinates. A net name is
escaped into the key alphabet injectively (`_` and other characters become `_` and four hex digits). Row
`i` of table `k` keeps the copper uuid the build derives for item `i` of `k`, so later builds find it.
When an upstream revision adds a segment, rows renumber and some copper gets new uuids; the geometry stays.

A via keeps its teardrop settings (change c0277): the reader leaves the `teardrops` child in the via's slot,
the import reads it and groups vias by it too, and the table says it as `teardrop=teardrop(...)`. A blind via
over both outer layers, as KiCad writes some, is a table row with `kind="blind"` and `layers=("F.Cu",
"B.Cu")`.

**Teardrop zones** are not written. KiCad draws a `padvia` teardrop zone from the teardrop settings of the
pad or via it joins, and the code keeps them: the pads' in their vendored footprints, the vias' in their
tables. The import reports them once as `import.teardrops-regenerated` (info); `fenolite fill` draws them on
the built board. When a via's settings cannot be read, or a via or footprint holding settings is left out,
every teardrop zone is counted as `teardrop`, unexpressed.

## The vendored library

The footprints are the board's own instances brought back to their origin, rotation 0 and the top side
(the derive of `fenolite library`), one `lib/<nickname>.pretty` per source nickname (`Imported` for a
footprint without one), the instance's own properties removed. An instance that still differs from the
first of its name (a moved field, an edited pad) is written as `<name>_2` and its part names that footprint
(`import.footprint-variant`). Each footprint gets a symbol drawn by Fenolite, one passive pin per pad
number, in `lib/<nickname>.kicad_sym` (`import.symbol-regenerated`); the source's symbols are not copied
until the drawn schematic of c0276 needs them. 3D models are referenced by name, not copied.

## Provenance

Every emitted `.py` file starts with four lines:

```python
# SPDX-License-Identifier: CERN-OHL-S-2.0
# SPDX-FileCopyrightText: 2024 The Board Authors
# Converted from https://example.invalid/b.git@0123abcd by Fenolite 0.7.0 on 2026-10-30;
# modified: format conversion to the Fenolite DSL. Original notices in NOTICE.
```

Without `--licence`, `--copyright` or `--source` the header says `NOASSERTION` and
`import.provenance-missing` warns; without `--timestamp` the date is today's and
`import.timestamp-missing` says the bytes are not reproducible. `PROVENANCE.json` records the design, the
licence, the holders, the upstream URL and revision, every input by base name, format, version and
SHA-256, the upgrades, the tools, the Fenolite version, the date, the copied notices, the counts of the
findings and the self-check.

## What the DSL cannot say

Before anything is written the import lists every item no DSL call expresses, by kind with examples, in
`result.unexpressed`. Without `--allow-lossy` the import exits 7 (`FEN-7001`) with one
`import.item-unexpressed` per kind and writes nothing; with it each kind is left out with that warning.
Never silently. The kinds today:

| kind | what |
|---|---|
| a root item KiCad keeps that the model does not (`group`, `generated`, `image`, `target`…) | named by its head; a teardrop zone of a type other than `padvia`, or any teardrop zone when teardrop settings were lost (below), is `teardrop` |
| `hole` | model items no emitter writes yet |
| `group` | a group holding an item the code does not write (a track, a via, a footprint or a drawing left out), named by its name; a group whose members the code writes becomes `design.group()` (change c0277) |
| `dimension`, `dimension-style` | a dimension of a kind the DSL does not say (radial, leader, centre) or on a layer it does not take; an aligned or orthogonal one whose `format` or `style` holds what `design.dimension()` does not write (a prefix, a text position…) |
| `stackup`, `title-block` | a stack-up row or a title-block field the DSL refuses (a silkscreen row with a dielectric constant or a loss tangent) |
| `custom-rule` | a `.kicad_dru` rule whose selector the DSL cannot write (a layer leaf, an undeclared class) |
| `zone-setting`, `zone-name`, `zone-layer`, `zone-outline`, `rule-area-name`, `rule-area-layer` | a zone hatch, a repeated zone name, a zone or area off the copper layers or without an outline, an area name the DSL refuses |
| `drawing`, `drawing-layer`, `text`, `text-layer` | a drawing the DSL calls refuse (a hidden text, a mirror that does not follow the layer side, a knockout off copper and silkscreen, a dashed stroke, a copper graphic on a net the code does not declare), or one on a layer they do not take |
| `copper-without-net`, `zero-length-track`, `degenerate-arc`, `via-protection`, `via-span`, `copper-layer`, `copper-count` | copper no table holds |
| `teardrop-setting` | a via's `teardrops` child the import cannot read: the via is written without it |
| `footprint` | a footprint the library derive cannot bring back |
| `pad-net-unnumbered`, `pad-net-conflict`, `outline` | a pad on a net without a number, a pad number on two nets, no closed outline |

Change c0277 (verbatim items and the DSL coverage holes) is not merged yet: until it is, its kinds stay in
this list, and each item it makes expressible removes its row. Since its first part the import also writes
(change c0277):

- **board-only parts**: footprints that share a reference, or have none a script can name (`REF**`, an
  empty one), are `Part(..., board_only=True)` named by key (`import.board-only`, info, counts those
  that gain KiCad's `board_only` attribute); a footprint with the attribute is board-only too;
- **user layers**: `design.user_layers()` up to the highest `User.<n>` of the source table, with its
  names, and the drawings on them;
- **copper graphics** with their net (`net=`), and filled shapes without an outline (`width=None`);
- **free vias** (`free=True` of their tables, which group vias by it), **smoothed zones**
  (`smoothing=`, `smoothing_radius=`), **dimensions in mils or automatic units** and the **material of a
  silkscreen** in the stack-up.

## Self-check

Unless `--no-verify`, the emitted files are built by `fenolite build` in a private temporary folder, and
the built board is compared with the source by the equivalence levels 1 to 5 (`docs/equivalence.md`)
under the profile `import` (absolute frame, no tolerance) and copper item by item: every track, arc and
via with its geometry, width or sizes, layers and lock flag. A difference an unexpressed kind explains, or
the name of a variant footprint, is accepted; any other is `import.unequal` (error): exit 5, nothing
written. `result.equivalence` is `{"levels": [1, 2, 3, 4, 5], "equivalent": true}` on success. The self-check build
runs with `--copper-check warn` and without a schematic: a board that breaks Fenolite's copper rules (one
the source already broke) is still compared, and building its code later needs `--copper-check warn` too.

## Old KiCad files

A board below the read floor is copied with its project files into a private temporary folder and
upgraded there by `kicad-cli pcb upgrade` (10.0); the source is never touched and the copies are deleted.
Each upgrade is a row of `result.upgrade` and `PROVENANCE.json` (tool version, format versions and SHA-256
before and after) and one `import.upgraded`. Without `kicad-cli` the import exits 6 with `FEN-6001` and a
hint naming `--no-upgrade`; a 9.0 `kicad-cli` has no `pcb upgrade` (`FEN-6002`).

## Adoption

`--adopt` also writes `adopted/<name>.kicad_pcb` (and a copy of the project file): the source board, the
upgraded copy when there was one, rewritten by token edits only. Each footprint takes the uuid and the
`fenolite.path` property that the build of the emitted code gives it, each pad the build's pad uuid, and
each track, arc, via, zone, rule area, drawing and text the uuid of its twin in the built board (the same
reference, the same pad index, or the same geometry: the self-check has proved every item came through).
Nothing else changes. `fenolite build design.py --out adopted` then matches every footprint by its uuid,
has no orphan and no board-only footprint, regenerates no copper, and a second build writes the same bytes.
`result.adopted` gives the board, the counts of rewritten uuids by kind, the added paths and the items left
without a twin. It needs the self-check build (`--no-verify` refuses it), and is off by default: the copy
of a third-party board belongs in the library repository or your own folder.

## Not yet

- **Sheet modules** of a KiCad hierarchy (`sheets/<module>.py`, a repeated sheet one function) and the
  **drawn schematic** (c0276) follow; an Altium document's rules and records that the model keeps opaque
  are the conversion's to report (`convert.*`).
- **Field placements** of an instance are not written as `Part.field()`: an instance whose fields moved is
  vendored as a variant footprint.

## Codes

| code | severity | when |
|---|---|---|
| `import.item-unexpressed` | warning | items of one kind no DSL call expresses (with `--allow-lossy`) |
| `import.unequal` | error | the self-check found an unexplained difference |
| `import.unverified` | warning | `--no-verify` |
| `import.schematic-generated` | info | the source has sheets; the build generates its own schematic |
| `import.footprint-variant` | info | an instance written as `<name>_2` |
| `import.symbol-regenerated` | info | symbols drawn from the pad numbers of their footprints |
| `import.sheet-renamed` | info | a KiCad sheet name changed to a module name |
| `import.upgraded` | info | a file upgraded through `kicad-cli` on a private copy |
| `import.provenance-missing` | warning | no `--licence`, `--copyright` or `--source` |
| `import.timestamp-missing` | info | no `--timestamp`: the output is not reproducible |
| `import.teardrops-regenerated` | info | teardrop zones left out because KiCad draws them again from the pad and via teardrop settings the code keeps (change c0277) |
| `import.board-only` | info | footprints that share a reference or have none a script can name, written as board-only parts named by key; the count of those that gain KiCad's `board_only` attribute (change c0277) |

## Evidence

The emitter, the tables, the keys, the provenance and the determinism are `INFERRED` (`H-G-IMPORT-CODE`):
the authored two-sheet project of `tests/data/import_python/` and the built examples import and rebuild
equal. The upgrade is measured with `kicad-cli` 10.0 in CI (`H-K-IMPORT-UPGRADE`).
