## Context

- **Source.** `docs/research/board-library.md`, sections 1 (where Fenolite stands), 4.1 (board → code)
  and 5 (c0275 depends on c0249). Maintainer decision of 2026-10-29: one separate repository,
  `fenolite-library`, holds every third-party-derived item converted to Fenolite formats, each under its
  upstream licence with `NOTICE` and `PROVENANCE.json`; the tool repository stays Fenolite-authored only.
  This change builds the converter; c0279 builds that repository.
- **What exists on `dev` (0.6.0).**
  - Readers into the model: KiCad 8 to 10 boards and schematics (`kicad-file-backend`, `kicad-schematic`),
    Altium projects and documents (`altium-import`). Files below the read floor raise `FEN-3003` with a
    `kicad-cli … upgrade` hint (`kicad-version-gating`, "Classification and read policy").
  - `KicadCli.upgrade_board` and `upgrade_schematic` (`backends/kicad/cli.py`) run `kicad-cli pcb
    upgrade` / `sch upgrade` on a copy and return the bytes; `corpus-policy`, "Upgraded copies keep
    their origin", already uses them under `tmp_path`.
  - `fenolite convert` with a `ConversionReport`, `--allow-lossy` and `FEN-7001`, verified by
    `fenolite.api.equivalent` levels 1 to 5 (`design-conversion`).
  - `fenolite library BOARD --out LIB.pretty` (`library/derive.py::derive_library`) brings each board
    footprint back to its origin, rotation 0 and top side, naming differing instances `<name>_2`.
  - DSL calls for everything the emitter writes except tables: `board(outline=…)`, `cutout`, `slot`,
    `stackup`, `netclass`, `pair`, `rules.rule`, `zone`, `rule_area`, the seven drawing calls, `Part`,
    `place`, `track`, `via`, field placements and user properties.
  - The layout lens matches footprints by uuid (`footprint_uuid(path)`), then by `fenolite.path`, then
    by alias (`layout-lens`, "Footprint matching"); script copper keeps uuids derived from its key and
    replaces equal unkeyed copper ("Script copper in a merge").
- **What the batch adds.** c0249: part keys (`name=`), explicit refs recorded in `<stem>.lock`.
  c0276: `schematic.toml`, the drawn schematic. c0277: the coverage holes and the verbatim item. c0278:
  strict fidelity levels and `verify-source`. c0279: the library repository.

## Goals / Non-Goals

**Goals**

- One command turns a KiCad or Altium board into a Fenolite project folder whose build reproduces the
  source at equivalence levels 1 to 5, or says exactly what it could not express.
- The output is readable, reviewable code: modules per sheet, named nets, compact copper.
- Every item has a key, so later builds, the lens and c0278's item-by-item proof find it again.
- The folder carries its provenance: licence, upstream URL and revision, inputs, tools, findings.
- Same inputs, flags and `--timestamp` give the same bytes on every platform.

**Non-Goals**

- See the proposal. In addition: no attempt to "improve" the board (no tidy, no re-route, no rename of
  nets or refs); no merge into an existing `design.py` (the output folder is new or emptied by the user);
  no symbol redraw.

## Decisions

### 1. Command surface

```
fenolite import upstream/board/board.kicad_pro --to python --out boards/board --dry-run --json \
    --licence CERN-OHL-S-2.0 --source https://example.invalid/board.git --revision 0123abcd \
    --copyright "2024 The Board Authors" --licence-file upstream/board/LICENSE --timestamp 2026-10-30T00:00:00Z
fenolite import ... --confirm --plan <plan_id>
fenolite import upstream/old/old.kicad_pcb --to python --out work/old --adopt --allow-lossy --dry-run
```

| option | meaning |
|---|---|
| `PATH` | `.kicad_pro`, `.kicad_pcb`, `.kicad_sch` (its project is found beside it), `.PrjPcb` or `.PcbDoc` |
| `--to python` | the only target now; the word is kept so other targets can follow |
| `--out DIR` | output folder; it may not be the source folder or hold it (`FEN-2001`, as `convert`) |
| `--name NAME` | design name; default the project stem, sanitized to `DESIGN_NAME` |
| `--licence SPDX`, `--copyright TEXT` | the header's SPDX expression and upstream copyright; absent: `NOASSERTION` and `import.provenance-missing` |
| `--source URL`, `--revision REV` | upstream location for the header and `PROVENANCE.json` |
| `--licence-file FILE` (repeatable) | upstream `LICENSE`, `NOTICE`, `COPYING` files copied byte for byte |
| `--adopt` | also write the adopted board copy (decision 12) |
| `--no-upgrade` | refuse inputs below the read floor (`FEN-3003`) instead of upgrading them |
| `--no-verify` | skip the self-check of decision 11 (`import.unverified`, warning) |
| global `--allow-lossy`, `--timestamp`, `--kicad-version` | as for `convert` and `build` |

It is `mutates=True`; the MCP server exposes it by c0195's rule. `example_args` name an authored board
under `tests/data/import_python/`, so the consistency suite runs offline.
*Alternative:* `fenolite convert --to python`. Rejected: `convert` writes a CAD project and verifies it
by reading it back; this writes code and verifies it by building it. The research names `import`.

### 2. Inputs

| input | reader | notes |
|---|---|---|
| KiCad 9/10 project, board, schematic | existing readers | read-only use; nothing is edited |
| KiCad 8 | existing readers | readable (`FEN-7003` concerns edits only) |
| KiCad below the read floor | `upgrade.py` (decision 13), then the readers | unless `--no-upgrade` |
| Altium `.PrjPcb`, `.PcbDoc` (+ `.SchDoc` of the project) | `altium-import` | decision 14 |
| anything else (Eagle, EasyEDA, legacy `.mod`/`.lib`) | none | `FEN-2001` naming the file kind |

A board without a schematic still imports: parts come from footprints, the netlist from pad nets.

### 3. Output tree

```
boards/board/
  design.py            # entry: header, board, stack-up, rules, nets, top-level parts, imports below
  sheets/
    power.py           # one module per sheet; a repeated sheet is one file, called once per instance
    channel.py
  copper.py            # track, arc and via tables (decision 6)
  design.lock          # c0249: every part key → ref
  fp-lib-table         # project tables naming ${KIPRJMOD}/lib/...
  sym-lib-table
  lib/<nickname>.pretty/<name>.kicad_mod
  lib/<nickname>.kicad_sym
  LICENSE  NOTICE      # copied unchanged from --licence-file, when given
  PROVENANCE.json      # fenolite.import-provenance.v0 (decision 9)
  adopted/             # only with --adopt (decision 12)
```

- No absolute path is written anywhere; inputs are recorded by base name and SHA-256.
- `schematic.toml` and `design.load_schematic(...)` are written only once c0276 is merged; before that
  the build generates its schematic and `import.schematic-generated` (info) names the source sheet count.

### 4. Emitter architecture

- `importer.emit.plan(model, options) -> Emission`: a pure function from the source `Design` model to an
  intermediate record list (one record per emitted statement, with its file, section and sort key), then
  `importer.emit.render(emission) -> dict[str, bytes]`. No template engine and no `ast.unparse`: the
  printer writes a fixed subset of Python (calls with keyword arguments, tuples, integers, strings) in
  a style that `ruff format` leaves unchanged at line length 110 (checked by a test that runs the dev
  tool; the core does not depend on it).
- Section order of `design.py`: header, imports, `design = Design(NAME)`, board and outline, cut-outs and
  slots, stack-up, nets, net classes, pairs, rules, sheets (module calls), top-level parts and their
  placements, zones, rule areas, drawings, `copper.apply(design, nets)` with the net objects by name.
- Ordering is by stable keys only (net names, component paths, item keys, then coordinates); never by
  file order of the source, dict order, or `PYTHONHASHSEED`.
- Lengths in calls are written as `mm("12.7")` with the shortest exact decimal of the integer
  nanometres; angles as integer degrees when whole, else the exact decimal degree string that
  `as_udeg` reads back to the same microdegrees. Coordinates are in the frame of
  `place()`: the source point minus `BOARD_ORIGIN`, so the build writes the source coordinates exactly.

```python
# SPDX-License-Identifier: CERN-OHL-S-2.0
# SPDX-FileCopyrightText: 2024 The Board Authors
# Converted from https://example.invalid/board.git@0123abcd by Fenolite 0.7.0 on 2026-10-30;
# modified: format conversion to the Fenolite DSL. Original notices in NOTICE.
from fenolite.dsl import Design, Net, Part, mm, stack

import copper
from sheets import channel, power

design = Design("board")
design.board(outline=OUTLINE, copper=4)
design.stackup(stack.copper(mm("0.035")), stack.prepreg(mm("0.2")), ...)
gnd = Net("GND")
vin = Net("VIN")
design.netclass("Power", nets=(gnd, vin), track_width=mm("0.5"), clearance=mm("0.2"))
power.sheet(design, path="power", gnd=gnd, vin=vin)
for name, refs in (("ch1", {"R101": "R101"}), ("ch2", {"R101": "R201"})):
    channel.sheet(design, path=name, refs=refs, gnd=gnd)
j1 = Part("J1", "Connector:Conn_01x02", footprint="Connector:PinHeader_1x02")
j1.place(mm("2.54"), mm("10"), rot=90, locked=True)
design.add(j1)
design.zone(gnd, layers=("In1.Cu",), key="GND/1", outline=ZONE_1, priority=0)
copper.apply(design, {"GND": gnd, "VIN": vin})
```

(`OUTLINE`, `ZONE_1` and the stack-up are written in full in the real output; elided here.)

### 5. Modules per sheet

- Each source sheet (KiCad hierarchical sheet, Altium sheet of the project tree) becomes
  `sheets/<module>.py` with one function `sheet(design, *, path, refs=None, **nets)`, which creates a
  `Module(path)`, its local nets, its parts and their placements, and returns the module. The module name
  is the sheet file stem sanitized to `[a-z0-9_]` (`import.sheet-renamed`, info, when it changes).
- **Nets.** A net is created once, in the deepest sheet that holds every pin of it, with its source name
  exactly; nets that cross a sheet boundary are passed as keyword arguments named after the sheet pin.
  Net names are never changed, so level 2 of the equivalence compares the same names.
- **Part keys** (c0249 decision 1). In a sheet used once, the key is the ref. In a repeated sheet, the key
  is the ref of the first instance in sheet order, and `refs` maps each key to the instance's ref; the
  explicit ref is given, so c0249 assigns nothing and the lock records the table.
- A board without a schematic, or a single-sheet project, writes no `sheets/` folder.
- *Alternative:* one flat file. Rejected for boards of more than one sheet: the research asks for
  modules, and a reviewer reads a sheet at a time. *Alternative:* classes per sheet. Rejected: a
  function is the smallest form the DSL already supports (`Module`).

### 6. Copper tables

New DSL calls, recorded as copper intents and resolved by the build like `track` and `via`:

```text
Design.track_table(key, *, net, layer, width, rows_nm, locked=False)     rows_nm: (x1, y1, x2, y2)
Design.arc_table(key, *, net, layer, width, rows_nm, locked=False)       rows_nm: (sx, sy, mx, my, ex, ey)
Design.via_table(key, *, net, diameter, drill, rows_nm, kind="through", layers=None, locked=False,
                 protection=None)                                        rows_nm: (x, y)
```

```python
# copper.py (excerpt, generated)
from fenolite.dsl import Design, Net, mm


def apply(design: Design, n: dict[str, Net]) -> None:
    design.track_table(
        "GND/F.Cu/1",
        net=n["GND"],
        layer="F.Cu",
        width=mm("0.25"),
        rows_nm=(
            (10_160_000, 5_080_000, 12_700_000, 5_080_000),
            (12_700_000, 5_080_000, 12_700_000, 7_620_000),
        ),
    )
    design.via_table(
        "GND/via/1",
        net=n["GND"],
        diameter=mm("0.6"),
        drill=mm("0.3"),
        rows_nm=((12_700_000, 7_620_000),),
    )
```

- Row values are integers in nanometres in the frame of `place()`; the keyword `rows_nm` states the unit,
  because the DSL refuses bare numbers elsewhere ("has no unit") and a `mm()` per value would triple a
  table of tens of thousands of segments. Widths, diameters and drills stay `Length` values. A non-integer, a zero-length segment or a collinear arc raises
  `DslError` naming the table and the row index.
- `copper.py` groups items by (net, layer, width, locked) for tracks and arcs and by (net, diameter,
  drill, kind, layers, protection, locked) for vias; each group is one table keyed
  `<net>/<layer>/<n>` (net names escaped to the key alphabet). Rows are sorted by their coordinates.
- Row `i` of table `k` has the copper uuid the build already derives for segment `i` of intent `k`, so
  the lens treats table copper as script copper ("Script copper in a merge").
- The source `locked` flag of each item is kept (a table per flag); the emitter does not lock what the
  source did not lock, because c0278 compares the flag.
- *Alternative:* one `track()` call per segment. Rejected: the research asks for tables, and a call per
  segment makes a 30 000-segment board a 30 000-line file. *Alternative:* a data file read by the build.
  Rejected: the DSL reads no file, and tables in Python stay diffable.

### 7. Keys of unnamed items

- `zone(..., key=None)` and `rule_area(..., key=None)` gain an optional key: the zone's identity across
  builds when it has no name, written nowhere in the board. Today the name is both. A zone with a name
  keeps the name as its key; an unnamed source zone gets `key="<net>/<n>"` and `name=None` is allowed
  then. Builds of existing scripts are unchanged (no key given → today's rule).
- Drawings already take keys: the emitter uses `<layer>/<kind>/<n>`, sorted by geometry.
- Footprint fields, pads and bodies come from the vendored footprint and the field placements of the
  DSL; nothing else needs a key.

### 8. Vendored library

- Footprints: `derive_library` gains a model input (`derive_from_model(board, *, library, target)`) so
  KiCad and Altium boards share it; the CLI form of `fenolite library` is unchanged. One `.pretty` per
  source nickname; the Part keeps its source lib id. An instance that differs from the first of its name
  is written as `<name>_2` as today and its Part names that footprint, with `import.footprint-variant`
  (info). Once c0277's instance overrides exist, a difference that they express is written as an
  override of the base footprint instead.
- Symbols: from the schematic's embedded symbols through `sym.write_symbol_library`, one `.kicad_sym` per
  nickname. An Altium symbol gives its pins only (body graphics are unmapped today); the import writes
  the generator's symbol from those pins and reports `import.symbol-regenerated` (info).
- 3D models are referenced by the names the footprints hold; model files are not copied (`fenolite models
  --vendor` exists for that).

### 9. Provenance

- **Header** of every emitted `.py`, four comment lines: `SPDX-License-Identifier`, `SPDX-FileCopyrightText`,
  the conversion line (`Converted from <URL>@<REV> by Fenolite <version> on <date>;`) and `modified: format
  conversion to the Fenolite DSL. Original notices in NOTICE.` The date is the `--timestamp` date, else
  today's UTC date (then the output is not reproducible, and `import.timestamp-missing` says so).
- **`PROVENANCE.json`**, canonical JSON (sorted keys, LF, final newline):

```json
{
  "schema": "fenolite.import-provenance.v0",
  "design": "board",
  "licence": "CERN-OHL-S-2.0",
  "copyright": ["2024 The Board Authors"],
  "source": {"url": "https://example.invalid/board.git", "revision": "0123abcd"},
  "inputs": [{"file": "board.kicad_pcb", "sha256": "<64 hex>", "format": "kicad_pcb", "version": 20221018}],
  "upgrade": [{"file": "board.kicad_pcb", "tool": "kicad-cli", "tool_version": "10.0.6",
               "from_version": 20221018, "to_version": 20250114, "sha256_after": "<64 hex>"}],
  "fenolite": "0.7.0",
  "date": "2026-10-30",
  "notices": ["LICENSE"],
  "findings": {"import.footprint-variant": 2, "import.item-unexpressed": 0},
  "equivalence": {"levels": [1, 2, 3, 4, 5], "equivalent": true}
}
```

- c0279 extends this schema (licence-list verdict, proof result of c0278) under the next version.

### 10. What cannot be expressed

- The emitter asks a coverage table (`importer.coverage`) for each model item and each opaque slot of the
  source. An item no DSL call expresses is collected in `result.unexpressed` (kind, count, examples).
- Without `--allow-lossy`, any unexpressed item refuses the import: exit 7, `FEN-7001`, one issue per
  kind, nothing written ("Lossy conversions need consent", same rule as `convert`).
- With `--allow-lossy`: once c0277 is merged, each item is written as a verbatim item (`design.verbatim`)
  with its own finding; before, it is left out with `import.item-unexpressed` (warning) per kind. Never
  silently.

### 11. Self-check

After rendering, the emitted files are executed as a build would (`load_script` in a private temporary
folder with the vendored lib), the resulting model is built in memory, and `fenolite.api.equivalent`
compares it with the source model at levels 1 to 5 under a new profile `import` of
`convert/data/profiles.toml`. A difference that `result.unexpressed` explains is listed; any other is
`import.unequal` (error): exit 5, nothing written ("Error findings plan no write").

### 12. Lens adoption (`--adopt`)

- Writes `adopted/<name>.kicad_pcb` and `adopted/<name>.kicad_pro`: the source board (upgraded copy when
  decision 13 ran) rewritten by token edits only: each footprint gets the uuid `footprint_uuid(path)`,
  a `fenolite.path` property and the pad uuids the build derives; each item the code keys (tracks, arcs,
  vias, zones, rule areas, drawings) gets the uuid its key derives. Nothing else changes.
- `fenolite build design.py --out adopted` then matches every footprint by key `uuid`, has no orphan and
  no board-only footprint, regenerates no copper, and a second build writes the same bytes.
- *Alternative:* a new lens key "origin uuid" stored in the script. Rejected: it adds a lens rule for one
  use and leaks source uuids into code. *Alternative:* rewrite the user's source board in place.
  Rejected: the import never writes over its source.

### 13. Upgrade of old KiCad files

- When a board or schematic is `TOO_OLD`, `upgrade.py` copies the project's files (board, every sheet
  file, project file, tables) into a private temporary folder, runs `KicadCli.upgrade_board` /
  `upgrade_schematic` on the copies with an empty `KICAD_CONFIG_HOME`, and reads the upgraded bytes. The
  source is never touched and the copies are deleted.
- `kicad-cli` missing: exit 6 `FEN-6001`, hint naming `--no-upgrade` and the install. A `kicad-cli` whose
  major has no `pcb upgrade` (9.0): exit 6 `FEN-6002` naming 10.0.
- Each upgrade is one row of `result.upgrade` and of `PROVENANCE.json` (tool version, versions before and
  after, SHA-256 before and after) and one `import.upgraded` (info).

### 14. Altium inputs

The Altium reader gives a `Design` model; the emitter is the same. Altium-only content the model keeps as
opaque records (rules the model does not map, unions, rooms) is "unexpressed" (decision 10), and
c0277's verbatim item does not cover Altium records (they are KiCad text), so they stay findings.

### 15. Result and codes

`result` (schema `fenolite.import.v0`): `source` (`file`, `backend`, `versions`), `out`, `files`,
`modules`, `counts` (parts, nets, tracks, arcs, vias, zones, rule_areas, drawings, tables),
`unexpressed`, `upgrade`, `equivalence`, `provenance` (`licence`, `source`, `revision`), `adopted`
(`null` without `--adopt`); `files` and `unexpressed` are paged by `--limit`.

| code | severity / exit | when |
|---|---|---|
| `import.item-unexpressed` | warning (with `--allow-lossy`) | items of one kind no DSL call expresses |
| `import.unequal` | error, exit 5 | the self-check found an unexplained difference |
| `import.unverified` | warning | `--no-verify` |
| `import.schematic-generated` | info | no drawn schematic yet (c0276) |
| `import.footprint-variant` | info | an instance written as `<name>_2` |
| `import.symbol-regenerated` | info | an Altium symbol drawn from its pins |
| `import.sheet-renamed` | info | a sheet stem changed to a module name |
| `import.upgraded` | info | a file upgraded through `kicad-cli` |
| `import.provenance-missing` | warning | no `--licence`, `--copyright` or `--source` |
| `import.timestamp-missing` | info | no `--timestamp`: output not reproducible |
| `FEN-7001` | exit 7 | unexpressed items without `--allow-lossy` |
| `FEN-2001` | exit 2 | output over the source; unsupported input kind |
| `FEN-3003` | exit 3 | old input with `--no-upgrade` |
| `FEN-6001` / `FEN-6002` | exit 6 | `kicad-cli` missing / without `pcb upgrade` |

## Risks / Trade-offs

- **Huge outputs.** A 10-layer board yields tens of thousands of table rows. Tables keep it to one line
  per segment; `copper.py` may still be megabytes. Acceptable: it is data, diffable, and c0278 proves it.
- **Table rows renumber** when an upstream revision adds a segment, so a re-import gives some copper new
  uuids. The lens then regenerates that copper (same geometry). Content-hash keys were rejected: they
  change on every move, which is worse for review.
- **Variant footprints change lib ids** (`<name>_2`). Reported, and c0277's overrides remove most cases.
- **Licence data is the user's statement.** `--licence` is written as given; c0279's CI checks it against
  the allow-list. The tool repository never holds converted boards (corpus-policy requirement).

## Open questions

1. *Lock the placements of an imported board (`place(locked=True)`) as the research's sketch does?*
   Recommended: no; keep the source flag, because c0278 compares it and an unlocked placement still
   lands where the code says on a fresh build.
   Decided 2026-10-29: no; the source flag is kept (the recommended answer).
2. *Coordinates relative to `BOARD_ORIGIN` or a `board(origin=…)` argument?* Recommended: relative to
   `BOARD_ORIGIN` (no new DSL), accepting negative coordinates for boards drawn left of it.
   Decided 2026-10-29: relative to `BOARD_ORIGIN` (the recommended answer).
3. *Default `--adopt` on?* Recommended: off; the adopted copy is a derived third-party file, which belongs
   only in the library repository or the user's own folder.
   Decided 2026-10-29: off (the recommended answer).

## Relation to the batch

- **c0249**: part keys and the lock (dependency). **c0250**: an adopted board is the CAD side of later
  edits. **c0264/c0266**: unrelated stores; vendored `lib/` stays per board.
- **c0276**: adds `schematic.toml` to the output and drops `import.schematic-generated`.
- **c0277**: verbatim items and the coverage the emitter uses; each c0277 item removes a row from
  `importer.coverage`'s "unexpressed" list.
- **c0278**: `verify-source` re-runs decision 11 at levels 5 strict to 8 and S.
- **c0279**: runs this command in the library CI from pinned upstream revisions, checks licences, and
  extends `PROVENANCE.json`.

## Evidence

| behaviour | level before merge | hypothesis |
|---|---|---|
| emitter, tables, keys, provenance, determinism | `INFERRED` (authored boards) | `H-G-IMPORT-CODE` |
| upgrade on copies | `KICAD-VERIFIED` (10.0.x) | `H-K-IMPORT-UPGRADE` |
| adoption | `KICAD-VERIFIED` (9.0.x, 10.0.x) | `H-K-IMPORT-ADOPT` |
| Altium inputs | `INFERRED` (Fenolite-written documents) | `H-A-IMPORT-CODE` |

## Decided: the skill folder budget (2026-10-30)

The circuits-as-code batches (c0252 to c0269) add commands, guide lines and DSL names that take the skill
folder past 300 000 bytes (312 592 bytes at batch 3). The folder budget of "Page budgets and size" rises to
400 000 bytes in this change, beside the 800-line limit of generated pages; the per-page limits stay.
