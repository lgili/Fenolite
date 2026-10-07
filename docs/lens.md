# Layout preservation (`fenolite.lens`)

`fenolite build` over an existing project keeps the work done in KiCad. The KiCad project is the
source of truth for layout, and `.fenolite/` is a cache the build regenerates (`docs/design-model.md`,
"Layout authority"). This page describes what a rebuild keeps, re-places and drops, in Fenolite's own
words. Facts about KiCad are in `docs/formats/kicad/board.md`; hypotheses in `docs/hypotheses.md`.

The merge is two-way: the existing board against the new build. There is no stored base, because
`.fenolite/` is not committed and is missing after a clone; a base taken from it would make the same
sources and board give different results with and without the cache.

The plan calls this a lens: the script is the *view* and the board is the *complement*. Its four names
map to the modules of `fenolite.lens` like this: *adapt* is `preserve` (the view is written into the
board), *extract* is `extract` (the view's data is read out of the board), *moved* is `moved` (a key of
the view changed), and *sync* is `sync` with `placements` (the extracted data is written to the source
tree).

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
The rebuild keeps its footprint under the new path (`layout.alias-used`, see "Renamed footprints keep
their edits"); its uuid then follows the new path, so the alias can be removed after one build. An alias
that matches nothing, or whose new path was matched by uuid or path, gives `layout.alias-unused`. Aliases
are not model data: ids and `.fenolite/` do not change. See `docs/dsl.md` for the rules on paths.

## Module aliases

`design.moved("power", "supply")` on a module path renames every part under it: each part
`supply/<rest>` gets the alias `power/<rest>`. A part alias wins over a module alias for its part, and a
longer module path over a shorter one, so a module rename and a part rename inside it can be written
together. The old path must no longer be a part or a module of the design.

A module alias also renames the module's nets. A net of the board named `power/<rest>` that the design
no longer has follows to `supply/<rest>` when the design has that net ("Net aliases"). Each expanded
alias that matches nothing gives `layout.alias-unused`, so the call is removed after one build.
`result.preserved.module_aliases` lists the module aliases of a rebuild.

## Net aliases

`design.moved_net("LED_A", "LED_ANODE")` says that the net now named `LED_ANODE` was named `LED_A`. On
the rebuild, the tracks, arcs, vias and zones of the board on `LED_A` are kept and take `LED_ANODE`, and so
do the pads of board-only footprints; `layout.net-alias-used` (info) gives the counts. Without the alias
a renamed net loses its routing (`layout.net-removed`), because Fenolite never guesses a rename: two
nets with the same pins after a split or a merge would move copper to the wrong net without a word.

- An alias whose old name is not a net of the board gives `layout.net-alias-unused` (warning): remove
  it. An alias is needed for one build only.
- The exact-name pattern that Fenolite wrote for the old name in the project file is left out, so the
  net keeps its class under the new name and no stale pattern stays.
- A pure rename keeps zone fills ("Fill digests"); a rename that also moves a pin drops them.
- `result.preserved.net_aliases` lists the net aliases of a rebuild, those of module aliases included.

## Renamed footprints keep their edits

A footprint matched through an alias is kept like any other when its library footprint and its placement
are unchanged: silkscreen moved in KiCad, items added to it and its pads all stay. It takes the identity
of its new path:

- every uuid in the node that the build derived from the old path becomes the uuid derived from the new
  path, locator by locator (`lens.moved.identity_map`). A uuid that KiCad gave an item added there is
  not one of them and stays;
- its `fenolite.path` property takes the new path;
- a KiCad group that lists the footprint lists it by its new uuid. Nothing else of a group changes, and
  Fenolite never adds or removes a group.

The uuid is rewritten, instead of kept, because a part later added at the old path would get the old
uuid and take the renamed footprint's place. A rename together with a new library footprint or a locked
`place()` re-places the footprint as before; `layout.alias-used` says `kept` or `replaced`.

DRC exclusions in the project file may also name a footprint's uuid. They are not rewritten: an
exclusion of a renamed footprint has to be made again in KiCad.

## Placement precedence

A part's placement comes from, in this order:

1. a locked `place(…, locked=True)` in the script;
2. the existing board;
3. the part's entry in `placements.toml` ("placements.toml");
4. an unlocked `place()`;
5. the build's staging row beside the outline (later, a placer).

"Locked" is the script's flag, not the board's: it is how an agent, which cannot move a part in KiCad,
forces a position. An unlocked `place()` that the board overrides is reported as
`layout.place-overridden` (info, repeated on every build); a locked one that moves a footprint as
`layout.place-forced` (warning), because the footprint is then re-placed from its definition. An
unlocked `place()` that an entry of `placements.toml` overrides gives `layout.place-overridden` too, with
the hint to lock the placement or edit the file.

**Off-board parts.** A footprint whose position lies outside the bounding box of the design's outline
counts as unplaced: it takes its `place()`, or is staged again. This applies only while the board's edge
content is absent or exactly the design's outline, so a part placed inside an outline enlarged in KiCad
is never moved.

## Kept, re-placed and dropped items

A matched footprint is **kept** when its library footprint is the one the script names and the build
placed it exactly where the board has it, whatever key matched it. Its whole node stays:
silkscreen positions, properties and pads as edited in KiCad. Its pads take the nets of the built
footprint by pad number, and the script's reference and value are written into its fields.

Otherwise it is **re-placed** by the built footprint at the effective placement: for a changed
footprint (`layout.footprint-replaced`) and a forced placement (`layout.place-forced`).

## User properties on kept footprints

The script owns its parts' user properties (`docs/dsl.md`, "User properties"). On a kept footprint, a
property of the same name (compared after `casefold`) takes the script's name and value and keeps its
uuid, position and visibility; a missing one is appended after the last property, with a uuid derived
from the component path and the property name. Such a property is a field (c0030): only the slot of its
value atom changes, and a missing one is the built copy's field, added after the footprint's last field. A property the script does not name stays: one added in
KiCad cannot be told from one the script no longer names. `--discard-layout` or a re-placement removes
it.

## Footprint fields

A footprint's text fields (Reference, Value and every placed property) are modelled, so a rebuild decides
each of them (`fenolite.lens.fields.merge_fields`, change c0030). The precedence is the placement
precedence, applied per field:

1. a **locked** request of the script, `part.field(…, locked=True)`;
2. the **board's** field, as edited in KiCad;
3. an **unlocked** request;
4. the **library's** field.

So a label dragged in KiCad stays where it is on every rebuild, and `locked=True` is the way a script, or
an agent that cannot drag a label, forces a field on an existing board. `--discard-layout` starts again
from the script. It is a two-way merge without a stored base, as for footprints.

- On a **kept** footprint the board's node stays, fields included. A locked request is applied to it,
  on top of the board's field; an unlocked request whose result differs is not applied.
- On a **re-placed** footprint with the same lib id on the same side (a locked move, an alias, an
  off-board part placed again), each field the board footprint also has takes the board's position,
  rotation, layer, size, thickness, visibility, justification and mirror, unless a locked request names
  it. A field is stored relative to its footprint, so the copy is exact and a hand-placed label follows
  a forced move. The field keeps the built copy's id, uuid and slots.
- After a side change or a footprint change the built copy's fields are used: the library's, with every
  request applied.
- User properties follow "User properties on kept footprints": their values are the script's and their
  placement the board's. Requests never name them.
- **A missing `Reference` or `Value`** (c0077). A board built before Fenolite generated the two fields
  for catalog and authored footprints holds footprints without them. A kept footprint whose node lacks
  one gains the built copy's field, with its id, uuid and placement and with the script's reference or
  value as its text, before the node's first field, `Reference` before `Value`
  (`lens.preserve._apply_mandatory_fields`). The built copy has the script's requests applied, so a
  request reaches an added field. A field the node has is never touched by this rule, and everything
  else of the node stays. No issue is raised; `build --dry-run` lists the board as changed, and the
  build after that changes nothing.

No issue is raised. `result.preserved.fields` holds three sorted lists of `"<component path>:<field>"`:

| list | meaning |
|---|---|
| `kept` | an unlocked request differs from the board's field; the board wins (lock the request to force it) |
| `forced` | a locked request changed a board field |
| `carried` | a field of a re-placed footprint took the board's values |

All three are empty on a first build and on a rebuild of an unedited board.

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
`layout.net-removed` per net giving the counts. A renamed net therefore loses its routing unless the
script names the rename ("Net aliases"). Rule areas stay.

When opaque content names a removed net (a teardrop zone, or a net inside an opaque child), the board
writer refuses with `kicad.board.opaque-net-ref` (exit 7). There are two ways out: delete that content
in KiCad, or rebuild from scratch with `--discard-layout`.

## Script copper in a merge

Copper declared by the script (`docs/copper.md`) is derived output: its source is the intents, and
every build regenerates it from the effective placements. It is told from copper drawn in KiCad by its
version-8 uuid. `merge_layout` therefore handles it before the net rule above:

- an existing track, arc or via with a copper uuid is dropped; the build's copy takes its place, with
  `kicad.copper.regenerated` (info) when a field differs, or nothing takes it, with `kicad.copper.stale`
  (warning), when its intent is gone;
- an existing item without a copper uuid that equals a script item is dropped as a duplicate
  (`kicad.copper.duplicate`, info);
- every other item stays and follows its net, as described above;
- the build's script copper follows the kept items in the layout, in the built order.

So a footprint moved in KiCad pulls its script copper along on the next build, an intent removed from the
script removes its copper, and copper drawn in KiCad stays. `result.copper` counts the three outcomes.

Two precedence models are used on purpose; each kind of item follows one of them (fields and script
zones share the footprints' model):

| item | model | who wins | marker | when its declaration is gone |
|---|---|---|---|---|
| footprint (c0019) | edited in place | the board, unless `place()` is locked | `fenolite.path` | `layout.orphan`, removed |
| script copper (c0028) | derived output | the script, always | the copper uuid | `kicad.copper.stale`, removed |
| footprint field (c0030) | edited in place | the board, unless the request is locked | the field name in its footprint | the board's field stays |
| script zone (c0031) | edited in place | the board, unless `zone()` is locked | the uuid of the zone's own name | `kicad.zone.orphan`, removed |

A footprint placement is the thing a user edits, and nothing derives it. A track's geometry is a
function of the pads it joins, which the board owns: a kept edit of a script track would point at old
pad positions after a move. To keep a hand edit, redraw the copper in KiCad, where it is board copper.

## Zones

A zone declared with `Design.zone()` (`docs/dsl.md`, "Zones") is edited in place, like a footprint: after
the first build the board owns it, and the script wins only when it says so. `merge_layout` hands the
zones to `fenolite.backends.kicad.zones.merge_zones` before the net rule of "Copper items and removed
nets", which keeps applying to every zone the script never declared.

- **Matching is by uuid, never by name.** A script zone gets the KiCad uuid that derives from its name
  (`zones.script_zone_uuid`), and a re-save keeps it. A zone drawn in KiCad has a random uuid, so two
  zones may share a name without being confused.
- **What is compared:** the outline, the layers, the net name, the priority, the lock and the effective
  settings (`ZoneSettings.effective()`, so a value without effect never counts).
- **The board wins.** A matched board zone is kept with everything KiCad wrote in it, and takes the
  design's net of its name. When the script differs, `kicad.zone.overridden` (info) names the zone and
  the values, with the hint to lock the zone, edit it in KiCad or use `--discard-layout`.
- **A locked zone wins.** With `locked=True` in the script, a differing board zone is replaced by the
  script's (`kicad.zone.forced`, warning). The replacement takes the board zone's fills, and the fill
  digests then decide whether they are still current; a changed setting drops them.
- **New zones** are added after the board's zones, in name order.
- **Removed zones.** A board zone that carries the uuid of its own name was written by a script. When
  the script no longer declares it, it is removed (`kicad.zone.orphan`, warning). A zone drawn in KiCad,
  or one renamed in KiCad (its uuid no longer derives from its name), is never removed this way.
- **A kept zone whose net left the design** takes the script's net for that zone.

| you want | do |
|---|---|
| tune a pour in KiCad and keep it | edit it there; the next build keeps it and tells you where the script differs |
| make the script the authority for one zone | `zone(..., locked=True)`; KiCad shows the zone as locked |
| drop a pour | remove its `zone()` call |
| hand a pour over to KiCad for good | rename it in KiCad, then remove the `zone()` call |

### Pad zone connections

A script may say how zones connect to a pad with `part.zone_connection()` (`docs/dsl.md`, "Zones").
On a rebuild the precedence is the one of zones and of fields, per pad that a request names:

1. a **locked** request, `part.zone_connection(…, locked=True)`;
2. the setting the **pad carries on the board**, as set in KiCad's pad properties;
3. an **unlocked** request;
4. the pad of the **library** footprint.

The step runs on the merged layout, after the fields (`fenolite.backends.kicad.zones.keep_pad_connections`,
one kept footprint at a time).

- On a **kept** footprint, a pad that already has the requested setting stays as it is. A pad without
  a setting of its own takes the request, locked or not, so a request added after the first build
  applies. A pad with another setting keeps it under an unlocked request (`kicad.pad.zone-overridden`,
  info, with the hint to lock the request, edit the pad in KiCad or use `--discard-layout`) and takes
  the request's value under a locked one (`kicad.pad.zone-forced`, warning).
- A **re-placed** or **new** footprint is the built copy: the library's pads with every request applied.
  A pad edit made in KiCad is not carried to a re-placed footprint.
- A pad that no request names stays as the board has it on a kept footprint.
- A pad set back to "from parent" in KiCad carries no setting, so the next build gives it the
  request's value again. To keep a pad on the zone's own connection, remove the request.

`result.preserved.pad_zones` holds two sorted lists of `"<component path>:<pad number>"`: `kept` (an
unlocked request differs from the setting of a board pad, which wins) and `forced` (a locked request
replaced the setting of a board pad). Both are empty on a first build and on a rebuild of an unedited
board.

## Stack-up across rebuilds

`design.stackup()` declares the stack-up of the board (`docs/dsl.md`, "Stack-up"). When a build merges
an existing board, `backends.kicad.stackup.merge_stackup` decides it, as for zones (change c0101). The
script's stack-up is completed from the layer table (one entry of thickness 0 for each silkscreen, paste
and mask layer it leaves out) and compared with the board's projected one, ids aside:

| script | board | written | code |
|---|---|---|---|
| none | any | the board's, with its text | none |
| declared | none, or a node KiCad ignores | the script's | none |
| declared | equal | the board's, with its text | none |
| declared, unlocked | different | the board's, with its text | `kicad.stackup.overridden` (info) |
| declared, `locked=True` | different | the script's | `kicad.stackup.forced` (warning) |

- For the `stackup` child of `setup` and the `thickness` of `general` this rule replaces "board content
  outside the design is kept"; every other child of `setup` stays as the board has it.
- KiCad has no lock for a stack-up: the lock lives in the script. An edit in KiCad's Board Setup therefore
  survives a rebuild until the script locks its own.
- `result.stackup.source` says whose stack-up the written board holds (`script` or `board`).
- The codes are `kicad.*` codes: they pass through the closed layout and build tables unchanged. The
  normal-form pass does not decide again, so a rebuild over the build's own output writes the same bytes.

## Board content and the outline rule

The layout is the existing board with its own root content: setup, stack-up, plot settings, groups,
dimensions, images, title block, paper and layers stay as KiCad wrote them. Edge graphics are kept; the
script's outline is used only when the board has none. When the edge content is not exactly the
script's rectangle, `layout.outline-kept` says so: a new size needs KiCad or `--discard-layout`. A
board whose copper layers differ from `board(copper=…)` cannot be preserved (`layout.copper-mismatch`,
error).

**Layer count.** A board of 2, 4, 6 or 8 copper layers keeps its layout when its copper layer names are
those of the script's count (`F.Cu`, `In1.Cu` … `B.Cu`), with the board's own layer rows unchanged.
When they differ, the message names the board's layers, their count and the script's count, and
nothing is written. If the board holds the table of an allowed count, the hint names both ways:
`design.board(..., copper=<the board's count>)` keeps the board's layout, and `--discard-layout`
creates the board on the script's count without it. A board that got two more layers in KiCad's
board setup is the usual case: a four-layer board with `In3.Cu` and `In4.Cu` added is rebuilt, layout
kept, once the script says `copper=6`. For a table that Fenolite does not create (ten layers, or an
inner layer under another name) the hint names `--discard-layout` only. A change of the count never
keeps the layout.

The paper and the title block are the board's too, unless the script declares them with
`design.sheet()` or `design.title_block()`: a declared one is written again from the script on every
build (`docs/dsl.md`, "Drawing sheet and title block").

An outline read from a board is what KiCad takes as its outline: endpoints closer than 10 µm are one
point, and edge items inside footprints count (`backends.kicad.outline.board_outline`).

## Fill digests

A kept zone keeps its fills when two text digests are unchanged between the existing board and the
layout to be written; otherwise its fills are dropped and its fill flag is cleared, with
`zone.fill-stale`, and the zone needs a fill again:

- `zone_digest`: the zone's outline, net name, layers, priority, its effective settings
  (`ZoneSettings.effective()`, as canonical JSON) and the text of its other opaque children. Fills,
  the fill flag, the lock, uuids, net forms and rows a KiCad major no longer writes are left out, so a
  target-9 and a target-10 copy give the same digest, and so does a setting that cannot change the
  fill, such as a hatch value of a solid fill.
- `fill_inputs_digest`: what a rebuild can change around the zone, namely footprints and their pads,
  tracks, arcs, vias, other zones, rule areas, edge content and outline, the project's classes and
  patterns, and the rule items. Nets enter by name; ids and uuids never do.

The existing board is digested after its net names are mapped through the net aliases of the build,
and an exact-name pattern of the old project file enters under the new name, so a pure rename keeps the
fills.

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
still guarded by `build.layout-exists`: they have no merge. `placements.toml` still applies: it is
source, like the script.

## placements.toml

`placements.toml` is the committed copy of a layout's placements. It lives beside the design script,
`fenolite sync --to-source` writes it and `fenolite build` reads it. With it, the placements of a layout
can be rebuilt from the source tree alone; routing stays in the board.

```toml
# Written by fenolite sync --to-source.
schema = "fenolite.placements.v0"

[part."power/R1"]
x = 12.7
y = 30
rotation = 90
side = "top"
locked = false
```

- **Form.** One table `[part."<component path>"]` per part, in path order. `x` and `y` are required;
  `rotation` defaults to 0, `side` to `"top"` and `locked` to false. No other key is allowed.
- **Frame.** `x` and `y` are millimetres in the frame of `place()`: the written position minus
  `BOARD_ORIGIN`. They are whole nanometres; `rotation` is degrees in [0, 360), whole microdegrees. The
  file is read with exact decimal numbers and printed from integers, so no float is ever created.
- **`locked`** is the footprint's lock in KiCad. The build writes it, and it gives the entry no
  precedence: only `place(…, locked=True)` in the script forces a position.
- **Precedence.** An entry wins over an unlocked `place()` and loses to the board and to a locked
  `place()` ("Placement precedence"). An entry that differs from the placement the board keeps gives
  `layout.source-stale` (info): run `sync` again. An entry that names no part gives
  `layout.source-unknown` (warning).
- **Errors.** A file that is not TOML, or whose `schema` is missing or different, stops the build with
  `FEN-3004` (exit 3). A wrong table or key gives `layout.source-invalid` (error) naming the table and the
  key, and nothing is written.
- **Staged parts are not in the file.** A part staged beside the outline has no placement worth
  keeping, and an entry would hide its `layout.unplaced` warning.
- **Both targets** read the file: an Altium build places a part from it as a KiCad build does.
- `result.preserved.source` reports the file read, the parts placed from it (`used`) and its `stale` and
  `unknown` tables. `.fenolite/build.json` records the file's SHA-256.

To drop the file, delete it.

## sync

`fenolite sync DESIGN.py --out DIR --to-source` reads the board in `DIR`, matches it with the script as
a build does, and writes `placements.toml` beside the script when its text would change
(`fenolite.lens.sync.plan_sync`; `docs/cli-contract.md`, "sync"). It also says, before any build, what
the next build would drop or overwrite:

| code | severity | when |
|---|---|---|
| `sync.would-change` | error | with `--check`, a file would change |
| `sync.orphan` | warning | a footprint with `fenolite.path` matches no part; the next build removes it |
| `sync.net-dropped` | warning | the board holds copper on a net that no design net or alias covers; the next build drops it |
| `sync.value-differs` | warning | the board's value, library footprint or user property of a matched part differs from the script's; the next build writes the script's |
| `sync.symbol-off-grid` | warning | a symbol's position or frame cannot be written to `schematic-placements.toml` |

- **`--check`** writes nothing and gives one `sync.would-change` per file that would change, so the
  command exits 5 when the committed file is stale. Run it in CI.
- **Both files.** The second file of `sync` is `schematic-placements.toml`, the symbol placements of the
  generated schematic (`docs/schematic.md`, "Placements file"). `sync` reads `DIR/<name>.kicad_sch` and
  every sheet file it names, takes each symbol whose `fenolite.path` is a component path of the script,
  and writes one table per unit: `x` and `y` of the symbol origin in millimetres, `rotation` when it is
  not 0 and `mirror` when the symbol is mirrored (`fenolite.lens.schplacements`). `result.symbols` is the
  number of tables, or `null` when `DIR` holds no schematic (a build with `--schematic skip`); then the
  file is not planned.
- **Off the grid.** A symbol whose origin is not on the 1.27 mm grid, or whose rotation and mirror the
  schematic writer does not produce, gives `sync.symbol-off-grid` (warning) and no table: the next build
  places it automatically. Symbols without `fenolite.path` (power flags, symbols drawn in KiCad) are not
  in the file.
- A schematic edited in KiCad is replaced by the next build, so run `sync` first: the build then draws
  the schematic again with every symbol where the file says.

## Issue codes

| code | severity | when |
|---|---|---|
| `layout.copper-mismatch` | error | the board's copper layers differ from `board(copper=…)`; the message names both counts, the hint `copper=<the board's count>` when it is 2, 4, 6 or 8, and `--discard-layout` |
| `layout.source-invalid` | error | a table or key of `placements.toml` is invalid |
| `layout.orphan` | warning | a footprint with `fenolite.path` matched no part and is removed |
| `layout.alias-unused` | warning | a part alias, given or expanded from a module alias, matched nothing, or its part matched by uuid or path |
| `layout.net-alias-unused` | warning | a `moved_net(old, new)` alias names no net of the board |
| `layout.source-unknown` | warning | a table of `placements.toml` names no part of the design |
| `layout.place-forced` | warning | a locked `place()` re-placed a footprint whose board placement differed |
| `layout.footprint-replaced` | warning | the part's footprint changed; the footprint is re-placed |
| `layout.net-removed` | warning | items on a net the design no longer has were dropped |
| `layout.outline-kept` | warning | the board's edge content differs from the design's outline and is kept |
| `zone.fill-stale` | warning | a zone's fills were dropped because a digest changed |
| `layout.place-overridden` | info | an unlocked `place()` differs from the kept board placement or from the `placements.toml` entry that wins |
| `layout.alias-used` | info | a part was matched through an alias and kept or re-placed under its new path |
| `layout.net-alias-used` | info | items of a board net were kept under the net's new name |
| `layout.source-stale` | info | a `placements.toml` entry differs from the kept board placement |
| `layout.board-only` | info | a footprint without `fenolite.path` matched no part and is kept |
| `kicad.copper.stale` | warning | script copper whose intent is gone was removed (`docs/copper.md`) |
| `kicad.copper.regenerated` | info | script copper was edited in KiCad, or its pads moved, and was replaced |
| `kicad.copper.duplicate` | info | an item equal to script copper was removed |
| `kicad.zone.forced` | warning | a locked `zone()` replaced a board zone that differed from it |
| `kicad.zone.orphan` | warning | a zone the script wrote for a `zone()` it no longer declares was removed |
| `kicad.zone.overridden` | info | an unlocked `zone()` differs from the kept board zone |
| `kicad.pad.zone-unknown-pad` | error | a `zone_connection()` request names a pad number or index that the footprint does not have |
| `kicad.pad.zone-forced` | warning | a locked `zone_connection()` replaced the setting that a pad of a kept footprint carries |
| `kicad.pad.zone-overridden` | info | an unlocked `zone_connection()` differs from the setting of a kept pad, which stays |

## Evidence

`lens.preserve.EVIDENCE` (`INFERRED`; `H-K-LENS-KEEP`, `H-K-LENS-FILL`, `H-K-UUID-KEEP-2`,
`H-K-BUILD-PATHPROP`) joins the `build` envelope when an existing board was read, with the board
reader's evidence; the rules codec's evidence joins when an existing rules file was merged.
`H-K-LENS-KEEP` is proved by `kicad-cli` 9.0.9 and 10.0.6 on the edited blink: a footprint moved by
token edit, re-saved by `pcb upgrade --force` on 10.0.6, survives a rebuild with its route intact, its
position from `pcb export pos` and the same DRC report. The envelope stays `INFERRED`, because other
boards reach forms the oracle has not run. `result.preserved` reports what the rebuild kept, replaced,
added and dropped (`docs/cli-contract.md`).
