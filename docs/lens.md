# Layout preservation (`fenolite.lens.preserve`)

`fenolite build` over an existing project keeps the work done in KiCad. The KiCad project is the
source of truth for layout, and `.fenolite/` is a cache the build regenerates (`docs/design-model.md`,
"Layout authority"). This page describes what a rebuild keeps, re-places and drops, in Fenolite's own
words. Facts about KiCad are in `docs/formats/kicad/board.md`; hypotheses in `docs/hypotheses.md`.

The merge is two-way: the existing board against the new build. There is no stored base, because
`.fenolite/` is not committed and is missing after a clone; a base taken from it would make the same
sources and board give different results with and without the cache.

## Keys and their order

Each part of the script carries its component path in the hidden `fenolite.path` property
(`docs/dsl.md`). A rebuild pairs each part with at most one footprint of the board, trying three keys
in turn, each over every unmatched part in path order before the next starts:

1. **uuid**: the footprint whose KiCad uuid is `footprint_uuid(path)`, the uuid the build gives it. A
   KiCad re-save keeps it (`H-K-UUID-KEEP-2`).
2. **path**: the first footprint, in board order, whose `fenolite.path` property is the part's path,
   for a footprint whose uuid changed (re-created in KiCad).
3. **alias**: a `moved(old, new)` alias, by uuid of `old`, then by property.

A footprint is matched once. A copy made in KiCad carries the same property and a new uuid: the
original wins by uuid, and the copy is an orphan. References, values and positions are never keys.

## `moved()`

`design.moved("R1", "power/R1")` says that the part now at `power/R1` was at `R1` in the last build.
The rebuild re-places it under its new path where the board had it (`layout.alias-used`); its uuid then
follows the new path, so the alias can be removed after one build. An alias that matches nothing, or
whose new path was matched by uuid or path, gives `layout.alias-unused`. Aliases are not model data:
ids and `.fenolite/` do not change. See `docs/dsl.md` for the rules on paths.

## Placement precedence

A part's placement comes from, in this order:

1. a locked `place(…, locked=True)` in the script;
2. the existing board;
3. an unlocked `place()`;
4. the build's staging row beside the outline (later, a placer).

"Locked" is the script's flag, not the board's: it is how an agent, which cannot move a part in KiCad,
forces a position. An unlocked `place()` that the board overrides is reported as
`layout.place-overridden` (info, repeated on every build); a locked one that moves a footprint as
`layout.place-forced` (warning), because the footprint is then re-placed from its definition.

**Off-board parts.** A footprint whose position lies outside the bounding box of the design's outline
counts as unplaced: it takes its `place()`, or is staged again. This applies only while the board's edge
content is absent or exactly the design's outline, so a part placed inside an outline enlarged in KiCad
is never moved.

## Kept, re-placed and dropped items

A matched footprint is **kept** when it was matched by uuid or path, its library footprint is the one
the script names, and the build placed it exactly where the board has it. Its whole node stays:
silkscreen positions, properties and pads as edited in KiCad. Its pads take the nets of the built
footprint by pad number, and the script's reference and value are written into its fields.

Otherwise it is **re-placed** by the built footprint at the effective placement: for an alias, a
changed footprint (`layout.footprint-replaced`) and a forced placement (`layout.place-forced`).

## User properties on kept footprints

The script owns its parts' user properties (`docs/dsl.md`, "User properties"). On a kept footprint, a
property of the same name (compared after `casefold`) takes the script's name and value and keeps its
uuid, position and visibility; a missing one is appended after the last property, with a uuid derived
from the component path and the property name. A property the script does not name stays: one added in
KiCad cannot be told from one the script no longer names. `--discard-layout` or a re-placement removes
it.

## Board-only footprints

A footprint without `fenolite.path` that matches no part (a mounting hole, a logo, a fiducial) was
added in KiCad. It is kept with the component that the board reader gives it, its pads take the
design's nets by name, its pins join those nets in `.fenolite/`, and `layout.board-only` names it.
`fenolite check` asks it for no symbol. A footprint that carries `fenolite.path` and matches no part is
an **orphan**: the script removed its part, so it is removed with `layout.orphan`, naming its
reference, path, uuid and position. The `.bak` of the mutation protocol keeps the previous board.

## Copper items and removed nets

Tracks, arcs, vias and zones keep their slots when they have no net or their net still exists, and take
the design's net of that name. Items on a net the design no longer has are dropped, with one
`layout.net-removed` per net giving the counts. A renamed net therefore loses its routing; a net alias
comes later. Rule areas stay.

When opaque content names a removed net (a teardrop zone, or a net inside an opaque child), the board
writer refuses with `kicad.board.opaque-net-ref` (exit 7). There are two ways out: delete that content
in KiCad, or rebuild from scratch with `--discard-layout`.

## Board content and the outline rule

The layout is the existing board with its own root content: setup, stack-up, plot settings, groups,
dimensions, images, title block, paper and layers stay as KiCad wrote them. Edge graphics are kept; the
script's outline is used only when the board has none. When the edge content is not exactly the
script's rectangle, `layout.outline-kept` says so: a new size needs KiCad or `--discard-layout`. A
board whose copper layers differ from `board(copper=…)` cannot be preserved (`layout.copper-mismatch`,
error).

## Fill digests

A kept zone keeps its fills when two text digests are unchanged between the existing board and the
layout to be written; otherwise its fills are dropped with `zone.fill-stale`, and the zone needs a fill
again:

- `zone_digest`: the zone's outline, net name, layers, priority and fill settings. Fills, uuids, net
  forms and rows a KiCad major no longer writes are left out, so a target-9 and a target-10 copy give
  the same digest.
- `fill_inputs_digest`: what a rebuild can change around the zone, namely footprints and their pads,
  tracks, arcs, vias, other zones, rule areas, edge content and outline, the project's classes and
  patterns, and the rule items. Nets enter by name; ids and uuids never do.

The digests are text only (`lens` never imports `geometry`). They are conservative: a change that did
not affect the fill, such as a new rule elsewhere, still drops it. The premise, that a fill depends only
on these inputs, is `H-K-LENS-FILL`, settled later by refilling a rebuilt board.

## Project and rules files

The project file is merged by c0010's `update_project`: every key Fenolite does not own stays, a class
is never deleted, and a class the script defines takes the script's values. The rules file keeps
Fenolite's rules first and the user's rules after them, in file order, with their comments; the later
rule wins in KiCad (`H-K-DRU-ORDER`), so a user rule overrides a Fenolite rule on the same items. User
rules pass the target gating too: a 10.0-only construct is refused for target 9 (`FEN-7001`) or dropped
with `--allow-lossy`. A rules file of version 2 or more is refused (`FEN-3002`), and a rules file that
does not parse is refused with its line (`FEN-3004`).

## The normal form

Every build derives the layout it caches from the board text it writes, fresh build or rebuild. So a
rebuild over the build's own output writes identical bytes, `.fenolite/` included, and deleting
`.fenolite/` and rebuilding restores it. The first rebuild over a board saved by KiCad rewrites it in
Fenolite's form; the next one changes nothing. A board saved by KiCad 10 cannot be rebuilt for target 9
(`FEN-7002`).

## `--discard-layout`

`--discard-layout` reads no existing file and builds from scratch; the mutation protocol keeps a `.bak`
of each replaced file. Without it, only `fp-lib-table` and the vendored footprints under `lib/` are
still guarded by `build.layout-exists`: they have no merge.

## Issue codes

| code | severity | when |
|---|---|---|
| `layout.copper-mismatch` | error | the board's copper layers differ from `board(copper=…)` |
| `layout.orphan` | warning | a footprint with `fenolite.path` matched no part and is removed |
| `layout.alias-unused` | warning | a `moved()` alias matched nothing, or its part matched by uuid or path |
| `layout.place-forced` | warning | a locked `place()` re-placed a footprint whose board placement differed |
| `layout.footprint-replaced` | warning | the part's footprint changed; the footprint is re-placed |
| `layout.net-removed` | warning | items on a net the design no longer has were dropped |
| `layout.outline-kept` | warning | the board's edge content differs from the design's outline and is kept |
| `zone.fill-stale` | warning | a zone's fills were dropped because a digest changed |
| `layout.place-overridden` | info | an unlocked `place()` differs from the kept board placement |
| `layout.alias-used` | info | a part was matched through `moved()` and re-placed under its new path |
| `layout.board-only` | info | a footprint without `fenolite.path` matched no part and is kept |

## Evidence

`lens.preserve.EVIDENCE` (`INFERRED`; `H-K-LENS-KEEP`, `H-K-LENS-FILL`, `H-K-UUID-KEEP-2`,
`H-K-BUILD-PATHPROP`) joins the `build` envelope when an existing board was read, with the board
reader's evidence; the rules codec's evidence joins when an existing rules file was merged.
`H-K-LENS-KEEP` is proved by `kicad-cli` 9.0.9 and 10.0.6 on the edited blink: a footprint moved by
token edit, re-saved by `pcb upgrade --force` on 10.0.6, survives a rebuild with its route intact, its
position from `pcb export pos` and the same DRC report. The envelope stays `INFERRED`, because other
boards reach forms the oracle has not run. `result.preserved` reports what the rebuild kept, replaced,
added and dropped (`docs/cli-contract.md`).
