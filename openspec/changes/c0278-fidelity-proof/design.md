## Context

- **Source.** `docs/research/board-library.md` (2026-10-29), section 4.4 (the level table and "a board
  enters the library only with a passing proof at every level, or with each difference written down and
  accepted in `PROVENANCE.json`"), section 4.5 (library CI) and row c0278 of section 5.
- **What exists on `dev` (0.6.0).**
  - `fenolite.checks.equivalence` (c0045, c0089): `compare_designs` at levels 1 to 5, `Tolerances` (nm,
    µdeg, ppm), frames, `Difference` located by `where`, exclusion profiles (`load_profiles`, `Rule`,
    `Excluded`), `difference_issues`, and the routing rule of level 5 as one table of `routing.py` "so that
    another rule can be added beside it".
  - `fenolite equivalent` and `fenolite.api.equivalent` read board, project, built and schematic sides.
    Schematic sides give a netlist only.
  - `fenolite view NEW --compare OLD` (c0184, `view/compare.py`) matches scene primitives as multisets and
    lists added, removed and moved items. The scene builders (`view/scene.py`, `view/schematic.py`,
    `view/kicad_schematic.py`) draw boards and sheets of both backends from the model.
  - The viewer's screenshot tests fail above 0.1 % differing pixels.
  - The corpus manifest declares the KiCad demo projects; derived copies stay in temporary folders.
- **What the other changes of this batch add.** c0275 writes `design.py`, `schematic.toml`, `lib/` and
  `PROVENANCE.json`; c0276 gives `DrawnSchematic`, `extract` and `resolve`; c0277 closes DSL holes; c0279
  runs the proof in the library's CI.

## Goals / Non-Goals

**Goals**

- One command proves that a script rebuilds an original, at every level the research names.
- Each level is reported, located and either equal, accepted with a reason, or a failure.
- The existing package, tolerances, exclusions and visual diff are reused, not copied.
- Existing `fenolite equivalent` calls keep their output.

**Non-Goals**

- See the proposal.

## Decisions

### 1. Today vs proposed

```
# Today: five levels, routing compared per net only, no rules, no geometry, no drawing
fenolite equivalent upstream/cm5_minima/ rebuilt/ --level 5

# Proposed: build the code, compare at every level, read accepted differences
fenolite verify-source boards/cern-ohl-s/cm5_minima/design.py --against upstream/cm5_minima/ --json
fenolite verify-source boards/cern-ohl-s/cm5_minima/design.py --against upstream/cm5_minima/ \
    --record --timestamp 2026-11-01T00:00:00Z --dry-run
fenolite verify-source ... --record --timestamp 2026-11-01T00:00:00Z --confirm --plan <plan_id>

# Proposed: single levels on two existing sides
fenolite equivalent a.kicad_pcb b.kicad_pcb --level 5 --strict
fenolite equivalent a.kicad_pcb b.kicad_pcb --level 7
fenolite equivalent a/ b/ --level S
```

A reply (abridged):

```json
{
  "result": {
    "equivalent": true,
    "levels": [
      {"level": 5, "name": "routing", "status": "equal", "strict": true, "compared": 1843},
      {"level": 7, "name": "geometry", "status": "accepted", "differences": 0, "excluded": 2},
      {"level": 8, "name": "presentation", "status": "equal", "layers": 14, "sheets": 6},
      {"level": "S", "name": "schematic", "status": "equal", "sheets": 6}
    ],
    "accepted": [{"rule": "A003", "level": 7, "kind": "text-field", "where": "board:Cmts.User:*"}]
  }
}
```

### 2. Where each level lives

| level | module | why there |
|---|---|---|
| 1 to 5, 5 strict, 6, 7 | `fenolite.checks.equivalence` (`levels.py`, `routing.py`, `strict.py`, `rules.py`, `shapes.py`) | pure, model only, the existing package rules ("Equivalence package") |
| S | `fenolite.checks.equivalence.drawn` | pure: two `DrawnSchematic` values and `model.drawn_connect.resolve` (c0276), pin points injected |
| 8 | `fenolite.view.fidelity` | needs the scene builders, which live in `view`; `checks` may not import `view` ("Allowed import edges") |
| orchestration | `fenolite.cli.cmd_verify_source` | runs the script (`cli._script`), the build (`lens`), the readers, the levels and the renderer; `cli` may import every package |

- `PRESENTATION_LEVEL = 8` and `SCHEMATIC_LEVEL = "S"` are constants of the package so that `Difference`,
  the kinds table, `difference_issues` and the exclusion rules cover them, even though `compare_designs`
  runs neither.
- `fenolite.api` gets no new function: `fenolite.api.run("verify-source", ...)` already reaches any
  command lazily ("Public API runs the commands lazily").
- **Alternatives considered.**
  - A new package `fenolite.fidelity`. Rejected: it would need a new row in "Allowed import edges" for one
    command's glue; `cli` already composes packages.
  - Level 8 inside `checks` with its own scene code. Rejected: a second drawing of every primitive would
    drift from the viewer.

### 3. Level 5 strict

- A second rule table in `strict.py`, run after the routing rule of `routing.py` when `strict=True`.
- Keys: a track by copper span and its two ends as an unordered pair; an arc by span, ends ordered, and
  mid; a via by position. Copper spans are `top`, `inner<k>`, `bottom`, as level 5 names them, so boards
  whose layers have other names compare.
- Matching: equal keys first (multiset), then, in key order, each unmatched item of `a` with the first
  unmatched item of `b` within the length tolerance on every coordinate. Deterministic and linear after
  sorting.
- Matched pairs compare width, net name (by level 2's pairing; an unpaired net compares by name), drill,
  diameter, span and type for vias, and `locked` (a notice: the lens of c0275 locks imported copper).
- `where`: `<net name>:<kind>:<span>:<points>`, points as `x,y` joined by `-`, ends in sorted order.
- Re-segmentation is a difference under strict matching on purpose: a conversion must emit the same
  segments. Comparing connectivity and length stays the non-strict rule.
- **Alternatives considered.** Merging collinear touching tracks before matching. Rejected as the default
  (it hides a writer that splits tracks); kept as open question 3.

### 4. Level 6 rules

- Entities: `NetClass` (by name), net class members (sets of net names), `Rule` of the rule set (by name),
  the `RuleSet`'s board-wide fields, `Stackup` layers (in order, by name and kind) and finish, and the
  board `Layer` table (by kind and ordinal).
- Fields come from the canonical JSON of each entity (`model.canonical`), minus `id`, `native_ids`,
  `ext` and provenance. Lengths compare with the length tolerance, text exactly, booleans exactly.
  `field` is the dotted path (`settings.clearance`), so the kinds stay closed while the model grows.
- **Alternatives considered.** One kind per field (`netclass-clearance`, ...). Rejected: every model
  change would edit the kinds table and the schema.

### 5. Level 7 exact geometry

- Items: outline rings, cut-outs and slots; zones; keep-outs; board graphics; board texts; holes;
  dimensions; and, per footprint pair of level 3, its graphics, texts and fields (c0126 instance items).
- **Normalisation** (`shapes.py`, integer only): a closed ring starts at its smallest (x, y) point and
  runs counter-clockwise (by the sign of its doubled area); a segment's ends are an unordered pair; an arc
  keeps its ends ordered and its mid; a circle its centre and radius; a rectangle as its four-point ring.
- **Zones** match by net name, layer set and normalised outline; matched zones compare name, priority and
  every field of `ZoneSettings`; fills are never compared (`H-K-FID-ZONE-OUTLINE`).
- **Texts** match by layer and text; matched texts compare position, size, thickness, rotation and
  justification. Footprint fields match by reference and field name (`field-pose`).
- `where`: `board:<layer>:<points or text>`, or `<REF>:<field name>` and `<REF>:<layer>:<points>` for
  footprint items.

### 6. Level 8 presentation

- **Scenes.** Both sides go through the viewer's scene builders: the board scene per layer, and the
  schematic scene per sheet instance. Zones are drawn by outline only (fills depend on the filler);
  footprint pads, tracks, vias, texts and graphics are drawn as the viewer draws them.
- **Masks.** `render_masks` rasterises each layer onto a grid of `pitch` (default 50 µm for boards,
  127 µm for sheets) whose origin and size are the union of both sides' bounds, so the grids align. Masks
  are run-length rows of integer intervals; polygons are filled at pixel centres with integer edge
  crossing; strokes become polygons with round ends; arcs are flattened with a fixed integer step. No float
  and no third-party package.
- **Comparison.** A pixel differs when it is inked on one side and no pixel within one pixel of it is
  inked on the other (a one-pixel tolerance for rounding). `differing × 10^6 ÷ inked` above `pixel_ppm`
  (default 1000, the 0.1 % of the viewer's screenshot tests) gives `render-pixels`, located by the box of
  the largest connected differing region. The hint lists the first three changes that `view.compare.compare`
  finds between the two scenes, so the user sees which primitive moved.
- **Why the same renderer on both sides is still a proof.** Levels 5 to 7 compare the model; level 8
  catches what the model comparison does not cover but the eye sees (a field on another layer, a hidden
  text shown, a mirrored graphic, a sheet item drawn in another place). It is `INFERRED` and says so.
- **Alternatives considered.** Rasterising `kicad-cli` SVG plots. Rejected for now: it needs an SVG
  rasteriser (a new extra) and a tool in the hermetic path; it is open question 2 and `H-K-FID-PLOT-AGREE`.

### 7. Level S

- Inputs: two `DrawnSchematic`s, each from `extract` (c0276) of the sheets of a side, and their pin points.
  For `verify-source` the built side is extracted from the written sheets, not taken from
  `schematic.toml`, so the proof covers the writer.
- Sheet instances match by path; symbols by component path and unit; wires and buses are turned into
  maximal collinear segments before matching, so a wire split differently is the same drawing; other items
  match as multisets by kind, position and text; opaque items by the SHA-256 of their fragment.
- Both drawings are resolved; a `REF-PIN` in another group gives `drawn-net`, so a junction removed gives
  `item-missing` and `drawn-net`.

**Decided 2026-10-30 (implementation):** a drawn symbol names its component by path, and an original that
Fenolite did not build has no `fenolite.path`. The two sides are therefore joined by reference, as levels 1
and 2 join them: each reference names the `fenolite.path` of its component in the build, on both sides, so a
repeated sheet of the original is one drawn sheet when the script's modules make it one. The sheets of a
matched pair of instances are compared once, at the first instance where they meet; a sheet reference's file
name is no part of the drawing. `drawn-net` compares groups over the pins both sides draw, so a symbol
missing on one side gives `symbol-missing` alone.

### 8. `fenolite verify-source`

- **Inputs.** `SCRIPT` (a design script) and `--against ORIGINAL` (a KiCad project folder or `.kicad_pro`,
  or an Altium `.PrjPcb`). Older KiCad files are refused with the readers' hint; `--upgrade` upgrades a copy
  with `kicad-cli` in the temporary folder, as c0275 does, and records `fidelity.input-upgraded` with the
  tool version and both SHA-256s.
- **Build.** The script runs as `fenolite build` runs it, for the original's KiCad major or `--target`,
  into `tempfile.TemporaryDirectory`, writing the planned files without the confirmation step. The folder
  is removed in a `finally`, signals included. No temporary path reaches the output.
- **Levels.** 1 to 7 with strict level 5, then S, then 8. `--levels 1-7,S` selects a subset. A level a
  side cannot reach is `skipped` with `fidelity.level-skipped` and a reason (`no-copper`, `no-schematic`,
  `altium-drawing-unread`).
- **Options.** `--tolerance-nm`, `--tolerance-udeg`, `--tolerance-ppm`, `--frame`, `--pixel-ppm`,
  `--render-pitch-um`, `--provenance FILE`, `--record`, `--accept KEY` with `--reason TEXT`, `--timestamp`,
  `--target`, `--upgrade`, `--kicad-cli PATH`, `--timeout SECONDS`.
- **Result** `fenolite.verify-source.v0` (proposal and spec). **Exit**: 0, or 5 when a difference is
  neither excluded nor accepted; 2 usage; 3 input; 6 tool missing with `--upgrade`.
- **Mutation.** `mutates=True` in the contract, writing only with `--record` (as `bom` writes only with
  `--out`): one planned file, the provenance file, through `--dry-run` and `--confirm --plan`.

### 9. `PROVENANCE.json`: the `fidelity` member

c0275 creates the file (`fenolite.provenance.v0`) and c0279 owns its other members. This change owns only
`fidelity`:

```json
{
  "schema": "fenolite.provenance.v0",
  "fidelity": {
    "tolerances": {"length_nm": 0, "angle_udeg": 0, "length_ppm": 0, "pixel_ppm": 1000},
    "accepted": [
      {
        "id": "A001",
        "level": 7,
        "kind": "text-field",
        "where": "board:Cmts.User:*",
        "field": "size",
        "reason": "Comment-layer text uses a font the DSL does not name yet (c0277).",
        "attribution": "fenolite",
        "decided": "2026-11-01"
      }
    ],
    "proof": {
      "fenolite": "0.7.0",
      "date": "2026-11-01T00:00:00Z",
      "script_sha256": "…",
      "against": {"cm5_minima.kicad_pcb": "…", "cm5_minima.kicad_sch": "…"},
      "levels": {"1": "equal", "5": "equal", "7": "accepted", "8": "equal", "S": "equal"}
    }
  }
}
```

- `accepted_rules(entries) -> tuple[Rule, ...]` turns entries into the package's exclusion `Rule`s (level,
  kind, glob, field; the reason is kept; the attribution is the entry's). `load_profiles` keeps its own
  validation for TOML profiles.
- Attribution: `fenolite` (a Fenolite limit, normally a c0277 hole), `upstream` (the original file holds
  something odd, e.g. a duplicated track), `tool` (a KiCad behaviour), `undecided`.
- Unused entries give `fidelity.accepted-unused`, so acceptances are removed when Fenolite improves.
- The keys of `--accept` are `<level>:<kind>:<where>`, taken from the reply; `--reason` is required.
- Writing keeps every other member's value and prints the file in canonical JSON (sorted keys, two
  spaces, newline).

### 10. The round-trip test category

- **Hermetic tier** `tests/fidelity/`: authored KiCad projects under `tests/data/fidelity/` (CC0, authored
  for Fenolite; the first one saved by the KiCad GUI per "Project fixtures saved by the KiCad GUI", so it is
  not Fenolite's own output), each read → emitted by c0275 into `tmp_path` → built → `verify-source`. Runs
  in `make check-fast` (no tool, corpus or libraries). A helper `tests/_fidelity.py::roundtrip(project,
  tmp_path)` returns the reply.
- **Corpus tier** `tests/kicad/fidelity/test_corpus_roundtrip.py` in the KiCad job: every row of use `rtf`.
  `tests/kicad/fidelity/accepted.toml` holds, per row id, allowed counts per (level, kind) and a reason,
  never an upstream name or value; a higher count fails, a lower count fails with a hint to lower it (a
  ratchet).
- **Why both.** The authored tier catches regressions on every push; the corpus tier measures real boards
  and gives the numbers of `docs/evidence/fidelity.md` and the library's benchmark.

## Codes introduced

| code | severity | when |
|---|---|---|
| `equiv.<kind>` for every new kind | error, or warning for `copper-locked` | the kinds of "Differences are located" |
| `fidelity.build-failed` | error | the script's build returned no file |
| `fidelity.accepted-unused` | warning | an accepted entry matched nothing in a level that ran |
| `fidelity.level-skipped` | info | a level a side cannot reach, with the reason |
| `fidelity.input-upgraded` | info | `--upgrade` upgraded a copy of the original |

No new `FEN-` code: usage `FEN-2001`, missing input `FEN-3001`, malformed provenance `FEN-3004`, stale plan
`FEN-4002`, missing tool `FEN-6001`.

## Hypotheses registered by this change

| id | statement | settled by |
|---|---|---|
| `H-K-FID-ZONE-OUTLINE` | KiCad keeps a zone's outline, layers, net, priority and settings unchanged when it loads, refills and saves a board, so comparing outlines and not fills is sound | KiCad CI job: `pcb upgrade --force` and a fill on the authored fixture, then level 7 |
| `H-K-FID-PLOT-AGREE` | Fenolite's rendered masks of a board layer agree with `kicad-cli pcb export svg` of that layer within the default pixel tolerance | open; settled when open question 2 is taken up |

## Evidence level per behaviour

| behaviour | level before merge |
|---|---|
| levels 5 strict, 6, 7, S | `INFERRED`, planted-edit and property tests; authored round trips |
| level 8 | `INFERRED` (one renderer on both sides) |
| zone outlines | `INFERRED` until `H-K-FID-ZONE-OUTLINE` passes in the KiCad job |
| corpus counts | recorded per row in `docs/evidence/fidelity.md` |

## Risks / Trade-offs

- **Strict level 5 is brittle by design.** A writer that splits tracks fails every board. That is the
  point of the proof; the non-strict rule remains for other uses.
- **Level 8 cost.** Large boards have many layers. Run-length masks at 50 µm keep memory linear in the
  outline; `--render-pitch-um` trades detail for time; the KiCad job measures the demo rows (task 6.2).
- **Same renderer.** Level 8 cannot catch a bug that the scene builder makes on both sides. Mitigation:
  levels 5 to 7 compare the model; `H-K-FID-PLOT-AGREE` is the later oracle.
- **Acceptance creep.** Accepted entries could hide regressions. Mitigation: globs are scoped by level and
  kind, unused entries warn, the corpus tier ratchets, and c0279's CI reviews the file.
- **c0275 not yet there.** The command and levels land first; the round-trip tier waits for c0275 (task
  0.1 records it).

## Open Questions

1. **Default pixel tolerance**: 1000 ppm, as the viewer tests, or tighter for boards? Recommended: 1000 ppm,
   per-board override through `fidelity.tolerances`.
   Decided 2026-10-29: 1000 ppm, overridden by `fidelity.tolerances.pixel_ppm` or `--pixel-ppm`.
2. **KiCad plots as a second level-8 oracle** (SVG rasterised through an optional extra)? Recommended:
   later, as its own change with `H-K-FID-PLOT-AGREE`.
   Decided 2026-10-29: later, as its own change; `H-K-FID-PLOT-AGREE` stays open.
3. **A merged-segment mode of strict level 5** for originals whose tracks KiCad split on save?
   Recommended: only as an option (`--strict-merge`), never in the library proof.
   Decided 2026-10-29: only as a later option; not built in this change, never in the library proof.
4. **Who may write accepted entries** in `fenolite-library`? Recommended: only through a reviewed pull
   request; `--accept` prints the entry, `--record` writes it.
   Decided 2026-10-29: as recommended; `--accept` lists the entry under `result.new_accepted`, `--record`
   writes it.
5. **Compare `locked` as an error** instead of a notice? Recommended: notice; c0275 locks everything, and a
   lock is lens state, not design.
   Decided 2026-10-29: a notice (`copper-locked`, warning).

## Relation to the other changes of this batch

- **c0275 board-to-code:** produces what is proved; creates `PROVENANCE.json`; its importer is the "emit"
  step of the round-trip category.
- **c0276 drawn-schematic:** provides level S's values and resolver; level S compares the extraction of the
  built sheets, so it also proves c0276's writer.
- **c0277 dsl-board-coverage:** each hole it closes removes accepted `fenolite` entries; unused entries warn.
- **c0279 board-library:** runs `verify-source --record` in CI on every Fenolite version, shows the level
  statuses in the gallery, and owns the rest of the provenance schema.
- **c0249 design-lock, c0250 manual-edit-merge:** the build in the temporary folder uses the lock and
  `edits.toml` beside the script as a normal build does.
