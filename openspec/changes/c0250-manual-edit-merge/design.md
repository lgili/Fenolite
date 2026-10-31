## Context

Section 11 of `docs/research/circuit-as-code.md` (core change G) asks that edits made in the CAD tool
survive a rebuild per property, with a three-way merge keyed by stable ids: *base* (the last build),
*code* (this build) and *CAD* (the edited file).

What Fenolite does today (0.6.0, `docs/lens.md`, `src/fenolite/lens/`):

- **Matching.** `lens.preserve.match_footprints` pairs each part with a footprint by uuid, then by the
  hidden `fenolite.path` property, then by a `moved()` alias. The component path is the identity;
  references, values and positions are never keys. This change reuses that matching unchanged.
- **Placement** (`effective_placements`): locked `place()`, then the board, then `placements.toml`, then
  `place()`, then staging. The board always beats an unlocked `place()`. A script that moves a part after
  the first build is reported (`layout.place-overridden`) and ignored.
- **Values, footprints and user properties** belong to the script. On a kept footprint, the script's
  `Value` and user properties are written into the board's node (`_apply_user_properties`). A footprint
  whose library id differs is re-placed (`layout.footprint-replaced`). `sync --to-source` warns
  (`sync.value-differs`) and the next build overwrites.
- **Field placement** (`lens.fields`): precedence locked request, board, unlocked request, library.
- **Schematic.** The build regenerates it every time (`check_existing` skips it). Only symbol positions
  survive, through `schematic-placements.toml`. A value changed in Eeschema is lost unless the user also
  ran "Update PCB from Schematic", and then it is overwritten from the board's side.
- **No base on purpose.** `docs/lens.md`: "The merge is two-way … There is no stored base, because
  `.fenolite/` is not committed and is missing after a clone; a base taken from it would make the same
  sources and board give different results with and without the cache." Any base this change adds must
  keep that property.
- **Altium.** The build writes `.SchDoc`/`.PcbDoc` from the model. `sync --target altium` captures whole
  edited sheets byte for byte (`altium-schematic-layout.json`). A changed value there is a
  `sync.altium-connectivity-changed` conflict. There is no PcbDoc merge.

What the others do (concepts only, from public pages; nothing copied): tscircuit keeps drag edits in a
separate diffable file keyed by selector and warns when code and edit disagree. atopile keys layout on
the hierarchical address. JITX 4.4 captures layout back into Python.

## Goals / Non-Goals

**Goals**

- A property changed on one side only survives: in the CAD file, in the script, or in `edits.toml`.
- A property changed on both sides to different values stops the build with an explicit, resolvable
  finding.
- Results depend only on committed files: the script, `edits.toml`, the output folder without
  `.fenolite/`.
- Every new file is canonical text, written only through plan/confirm, byte-identical across runs.
- First `position`, `rotation`, `value`, `footprint`; then `reference` and user properties.

**Non-Goals**

- Rewriting the Python script from CAD edits (an agent uses `fenolite edit`, c0196).
- Three-way merge of field placement, silkscreen, copper, zones, outline, stack-up or symbol positions.
  They keep their rules (`docs/lens.md`).
- Reading Altium documents as a CAD side (follow-up, open question 3).
- Merging two CAD files edited by two people (that is git's job on the board file).

## Decisions

### 1. Identity is the component path

Every key is `<component path>#<property>`. The path is already the matching key of the lens, and
`moved()` already carries it across renames, so a base entry follows an alias (its old path is looked
up). References are never keys, so a re-annotation in KiCad is an edit of `reference`, not a new part.
c0249 makes references stable through `<script stem>.lock`. c0251's blocks give instance paths
(`buck1/L`). Neither changes the key.

*Alternatives:* key by reference, as tscircuit does with selectors (rejected: a rename orphans the
edit). Key by KiCad uuid (rejected: a footprint re-created in KiCad gets a new uuid, while the path
property survives).

### 2. The base record lives in the output folder, beside `.fenolite/`

`<out>/fenolite-base.json` is written by every build as an ordinary planned write. It is listed in the
receipt, and its hash is in `.fenolite/build.json`, so a hand edit is refused (`build.layout-exists`).

The research sketch put the base in `.fenolite/`. That folder is git-ignored. After a clone, the same
script and board would merge differently with and without the cache, which `docs/lens.md` rejects. The
output folder itself is committed: it is the layout authority (`docs/design-model.md`). A file in it
travels with the board it describes. `.fenolite/` keeps the last build's model, and the merge may use it
for messages only, never for decisions.

*Alternatives considered:*

- **`.fenolite/`.** Rejected for clones, see above.
- **A hidden `fenolite.base` property on every footprint and symbol.** This also travels with the board.
  Rejected: `read_board` projects every property into `Component.properties` (`design-dsl`, "User
  properties on built footprints"), so digests would enter the model and `.fenolite/circuit.json`. It is
  also state hidden in the CAD file, which the research lists under "what we deliberately do not copy".
  And KiCad's update from the schematic may rewrite footprint properties (`H-K-SCH-UPDATE`).
- **`<script stem>.lock` (c0249).** Rejected. The lock is one per design and records decisions (refs, picks).
  The base is one per output folder and records an observation: a KiCad folder and an Altium folder of
  the same design, or two variant folders, each have their own last-written state. It would also churn
  the lock on every code change.

A missing or foreign base record is "no base". The merge then falls back, per property, to today's
two-way rule (decision 4). So upgrading never changes a result silently, and the first build writes the
record.

### 3. The base holds two halves: what the build was given and what it wrote

For each property the record keeps `code` (the code-side value the build used, after `edits.toml`) and
`out` (the value it wrote into the CAD file). One value is not enough:

- After a kept CAD edit, `out` ≠ `code`. The next build must see "code unchanged, CAD unchanged".
- For positions, `code` is the *request* (`place()` or an edit, `null` without one), while `out` is the
  written position, staging included. A staged part whose staging slot shifts because a part was added
  keeps its hand position: code `null` is unchanged and CAD equals `out`.

"Code changed" compares with `code`; "CAD changed" compares with `out`.

```json
{
  "parts": {
    "R1": {
      "footprint": {"code": "Mini:Mini_R_0603", "out": "Mini:Mini_R_0603"},
      "position": {"code": [120000000, 110000000], "out": [120000000, 110000000]},
      "rotation": {"code": [0, "top"], "out": [0, "top"]},
      "value": {"code": "330", "out": "4k7"}
    }
  },
  "schema": "fenolite.base.v0",
  "target": "kicad"
}
```

This `R1` had its value changed to `4k7` in KiCad and kept. Canonical JSON (sorted keys, no date)
holds integer nanometres and microdegrees and never a float.

### 4. The rule, per property

| base | code | CAD | result |
|---|---|---|---|
| A | A | A | A |
| A | A | B | B: CAD edit kept (`edit.unrecorded` until `sync` records it) |
| A | B | A | B: code wins (`edit.code-wins`, info) |
| A | B | B | B |
| A | B | C | conflict `sync.conflict`, exit 5, unless `--take` |

The rows are exactly the research table. These rules come on top of it:

- **Removed request.** Code `null`, base set: the CAD value stays. Removing `place()` never moves a part.
- **No base.** Today's rule: the board wins for position and rotation, the code for value, footprint,
  reference and properties. `sync.value-differs` stays for that case only.
- **Locked script request** (`place(locked=True)`): the code always wins, with `layout.place-forced`.
- **Footprint locked in KiCad** (`(locked yes)`): a code change over an unchanged board position is a
  `cad-locked` conflict, not a silent move.

Behaviour change: once a base exists, a changed unlocked `place()` moves an untouched part. Today it is
ignored with `layout.place-overridden`. This is the second half of "manual edits that survive": script
edits survive too. A part moved by hand is still never moved by an unchanged script.

### 5. Properties and their phases

`PROPERTIES = (position, rotation, value, footprint, reference)` plus `property:<name>`.

- `position` is x and y. `rotation` is rotation and side together, because a flip mirrors the footprint
  and its rotation then reads differently. So "rotated in the script, moved by hand" merges.
- `value` is the `Value` text the build writes (`Component.value`). With c0246, ranges stay in the
  model; the text is what is compared.
- `footprint` is the library footprint id. A footprint swapped in KiCad keeps the board's node: the
  merged design carries the board's id, so `merge_layout` keeps the node instead of re-placing it. The id
  must resolve through the project's libraries; otherwise the existing library errors apply (exit 3).
- `reference` and user properties are phase 2 (decision 11).
- The KiCad lock, field placement, pads, silkscreen and copper are not merged properties.

### 6. Code side = script + `edits.toml`; edits record what they were made over

The code side of a property is the script's value, replaced by its edit in `edits.toml`. Each edit keeps
the script's value at the time it was recorded (`over`):

- Script still equals `over`: the edit applies.
- Script changed, and differs from the edit: a `stale-edit` conflict. The engineer changed the script
  under a hand edit.
- Script changed to the edit's value: the edit is redundant. It applies, and the next `sync` drops it.

`edits.toml` holds only differences from the script. A part whose board position equals its `place()`
has no entry. Without that, every synced part would pin its position and a later `place()` change would
always be stale. Parts without `place()` that are placed (by hand or by `fenolite place`) are recorded,
as in `placements.toml`. Staged parts are not.

### 7. `edits.toml` (`fenolite.edits.v0`)

Today (0.6.0), `placements.toml`:

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

Proposed, `edits.toml` (example authored for Fenolite):

```toml
# Written by fenolite sync --to-source.
schema = "fenolite.edits.v0"

[part."buck1/L"]
x = 12.7
y = 30
rotation = 90
side = "top"
value = "6u8"
footprint = "Fenolite:IND_4x4"

[part."buck1/L".over]
unplaced = true            # the script gave no place() when the edit was recorded
value = "4u7"
footprint = "Fenolite:IND_3x3"

[part."sensor/R_pull_sda"]
reference = "R12"          # phase 2: re-annotated in KiCad
properties = { "Part number" = "PN-2K2" }

[part."sensor/R_pull_sda".over]
reference = "R3"
properties = { "Part number" = "PN-4K7" }
```

- The table form, the position keys, the units (millimetres, degrees, exact decimals read with
  `parse_float=Decimal`), the frame of `place()` and the printing rules are those of `placements.toml`.
  A placements table with an `over` table holding `unplaced = true` is an edits table.
- `locked` is printed only when true. It is the KiCad lock, never a precedence (as before).
- Numbers stay bare (mm, degrees) rather than unit strings such as `"12.7mm"` (open question 2).

**Migration.** The build reads `edits.toml`, and otherwise `placements.toml`, whose entries are position
edits without `over`: they never go stale, which is today's behaviour. With both files present,
`placements.toml` is ignored (`edit.legacy-file`). `sync` writes only `edits.toml` and carries the legacy
entries it cannot take from the board (`sync.placements-migrated`). The user deletes `placements.toml`.

### 8. CAD sides: the board and the schematic

`position` and `rotation` come from the board. `value`, `footprint`, `reference` and user properties
come from the board footprint and from the symbol with the same `fenolite.path`. Each side is compared
with `out` separately, since one build writes the same value into both:

- Only the schematic changed (edited in Eeschema, PCB not updated): the schematic's value wins, and the
  build writes it into both, so the regenerated schematic keeps it.
- Both changed to the same value (KiCad's update from the schematic): no conflict.
- Both changed differently: a `sides-disagree` conflict, resolved with `--take board` or
  `--take schematic`.

`read_existing` gains the schematic texts (root and child sheets) when the schematic exists. `sync`
already reads them. A `--schematic skip` project has one side.

### 9. Conflicts

`Conflict(key, base, code, cad, sides, reason)` with reasons `both-changed`, `stale-edit`, `cad-locked`,
`sides-disagree`. Each is reported as `sync.conflict` (error) by both `build` and `sync`. The name is
the research's: the finding is about the source being out of sync with the CAD file. `where` is the key.
The message gives the three values in edits-file units, and the hint gives the two takes:

```
sync.conflict  R1#value: base '330', script '470', board '4k7' (both changed)
  hint: fenolite build ... --take code:R1#value   or   --take cad:R1#value
```

A build with a conflict plans no write (exit 5, as every error finding). `sync` with a conflict writes
nothing. `result.preserved.edits.conflicts` and `sync`'s `result.conflicts` carry the records for the
viewer.

### 10. `--take` is a build option; `sync` only records

```
fenolite build design.py --out B --take cad:R1#value --dry-run      # one property
fenolite build design.py --out B --take code:buck1/L --dry-run      # every conflict of one part
fenolite build design.py --out B --take schematic:R1#value ...      # sides-disagree
fenolite build design.py --out B --take code --dry-run              # every conflict
```

- Grammar: `SIDE[:TARGET]`, repeatable. `SIDE` ∈ `code`, `cad`, `board`, `schematic`. `TARGET` is a
  path or a key. The most specific take wins. Contradictions are a usage error. An unused take gives
  `edit.take-unused`.
- Only the build writes the CAD file. So only the build can make the choice stick: the base record then
  holds the written value, and the next build has no conflict.
- `sync` derives `edits.toml` from "what would the next build write, minus the script". After a
  `--take cad`, `sync` records the edit. After a `--take code`, the board equals the script, so `sync`
  drops a stale edit.
- The loop is always: build (resolve), then sync (record).

*Alternative:* `--take` on `sync` too. Rejected. `sync --take code` cannot change the board, so the
conflict would come back at the next build unless the choice were stored somewhere new. Two commands
that both resolve would make the order matter.

### 11. References and user properties (phase 2)

- **Reference.** The code side is the hand ref or c0249's locked ref. A KiCad re-annotation is captured
  as `reference` in `edits.toml`, which c0249 treats as a hand ref (hand refs win), so the lock records
  it at the next build. Two equal decided refs give the build's existing duplicate error.
- **User properties.** Only properties the script names are merged. One added in KiCad stays opaque, as
  today (`layout-lens`, "Kept and re-placed footprints"). A named property removed in KiCad counts as
  changed to `""`.
- Until phase 2 lands, both keep their current rules.

### 12. Locked items, in one place

| lock | effect |
|---|---|
| `place(…, locked=True)` | position and rotation always from the code; `layout.place-forced` when the board differed |
| `part.field(…, locked=True)` | unchanged: field placement is not a merged property |
| KiCad `(locked yes)` on a footprint | a code change over an unchanged board position is a `cad-locked` conflict; a kept placement keeps the board's lock |
| `build --frozen` (c0249) | any `--take` and any `edit.unrecorded` are refused as a lock change is (exit 7) |

### 13. Altium

- An Altium build applies `edits.toml` over the script: values, footprints, properties and positions.
  So an edit recorded from KiCad reaches the Altium output.
- It writes its own base record (`target = "altium"`), so a later Altium CAD side has a base.
- The sheet snapshot of `sync --target altium` is unchanged. A snapshot made before an edit was applied
  conflicts (`build.altium-layout-conflict`) as any source change does today.
- Reading values, footprints and positions from saved `.SchDoc`/`.PcbDoc` as a CAD side is open
  question 3.

### 14. Viewer (check-overlay, c0245)

- `view --check` accepts a `build` or `sync` reply and marks each `sync.conflict` on the footprint of its
  path. The Messages entry shows key, reason and the three values.
- When c0245's workbench is present, Properties shows base, code and CAD. Under `--serve --edit`,
  "Take code" and "Take CAD" run `build --take … --dry-run` into its Pending panel. Apply runs
  `--confirm --plan`. Undo is a new build with the other take.
- Without c0245, the two command lines are offered to copy. The viewer never writes by itself.

### 15. Modules and data flow

`src/fenolite/lens/edits.py` (pure; imports stdlib, `core`, `model`, `backends`, `lens.placements`):
`read_base`, `write_base`, `read_edits`, `write_edits`, `parse_takes`, `merge_property`,
`merge_properties`, `capture_edits`, `EDIT_ISSUE_CODES`, `EVIDENCE`.

**Build** (`cmd_build`):

1. Read the script.
2. Read `edits.toml` (or `placements.toml`).
3. Read `<out>/fenolite-base.json`.
4. Read the existing triad and schematic.
5. `prepare` runs `match_footprints`, then `merge_properties` (value, footprint, reference, properties)
   and `effective_placements` (position, rotation) with the same base and takes.
6. `build_design` runs on the merged design.
7. Write the board, the schematic, `.fenolite/` and `fenolite-base.json`.

A conflict is an error issue, so nothing is written.

**Sync** (`cmd_sync`):

1. Read the script, `edits.toml` (or `placements.toml`), the base, the board and the schematic.
2. `capture_edits` computes the edits.
3. Plan `edits.toml` and `schematic-placements.toml`.

`--check` flags staleness and conflicts.

### Today vs proposed, end to end

Today:

```
$ fenolite build design.py --out B --confirm              # writes R1 value 330
  ... engineer sets R1 to 4k7 in KiCad, swaps L1 to a 4x4 package ...
$ fenolite sync design.py --out B --to-source --dry-run
  sync.value-differs  R1: value is '4k7' on the board and '330' in the script; the next build writes the script's
$ fenolite build design.py --out B --confirm              # 4k7 and the 4x4 swap are gone
```

Proposed:

```
$ fenolite build design.py --out B --confirm              # 4k7 and the 4x4 node kept; edit.unrecorded x2
$ fenolite sync design.py --out B --to-source --confirm   # edits.toml: R1 value 4k7 over 330, L1 footprint
  ... later the script changes R1 to 470 ...
$ fenolite build design.py --out B --dry-run              # exit 5
  sync.conflict  R1#value: base '330', script '470', edits.toml '4k7' (stale-edit)
$ fenolite build design.py --out B --take code:R1#value --dry-run   # review, then --confirm --plan ID
$ fenolite sync design.py --out B --to-source --confirm   # drops the stale R1 edit
```

The design script itself does not change: no new DSL name is needed. `place()` gains meaning (decision 4).

## Issue codes

| code | severity | where |
|---|---|---|
| `sync.conflict` | error | build and sync; `EDIT_ISSUE_CODES` and `SYNC_ISSUE_CODES` |
| `edit.take-unused` | warning | build |
| `edit.legacy-file` | warning | build |
| `edit.base-invalid` | warning | build and sync |
| `edit.unrecorded` | info | build |
| `edit.code-wins` | info | build |
| `edit.base-missing` | info | build and sync |
| `sync.placements-migrated` | info | sync |
| `sync.value-differs` | warning | sync, now only without a base |

No new `FEN-` code. Format errors of `edits.toml` are `FEN-3004`, as for `placements.toml`. A
malformed `--take` is `FEN-2001`. A refusal under `--frozen` uses c0249's code.

## Hypotheses registered by this change

- `H-K-EDIT-SCH-VALUE`: a value, footprint field or reference changed in KiCad's schematic editor and
  saved is read back by `sch.read_schematic` as that property's text, with nothing else changed that
  matters to the merge. Proof: a KiCad kit case of the maintainer. Until then, `INFERRED`, with tests on
  token edits.

## Evidence level per behaviour

| behaviour | level before merge |
|---|---|
| three-way rule, takes, edits file, base record | `INFERRED` (unit tests, property tests) |
| merged boards and schematics accepted by KiCad | `kicad-cli` 9.0.9 and 10.0.6 load them; DRC and ERC report nothing new (oracle tests) |
| schematic edits read correctly | `INFERRED` (`H-K-EDIT-SCH-VALUE`) |
| envelope | `INFERRED`, `lens.edits.EVIDENCE` |

## Relation to the other changes of this batch

- **c0249 design-lock** (step 2, before this): refs and picks in `<script stem>.lock`, `--frozen`. This
  change reads lock refs as the code side of `reference` and feeds `edits.toml` refs back as hand refs.
  `--frozen` refuses takes and unrecorded edits. Phase 1 (position, rotation, value, footprint) does not
  need c0249.
- **c0246 quantity-ranges:** values stay text in edits. A range is checked by c0253 against the edited
  text.
- **c0248 device-catalog:** a footprint edit on a `device=` part may leave the device's packages (open
  question 4).
- **c0251 circuit-blocks:** instance paths are the keys. Block parameters never appear in edits.
- **c0253 electrical-contracts:** the checks read the merged model, so an edited `6u8` is judged
  ("kept, and flagged by circuit checks if out of range").
- **c0254 parametric-part-selection:** a picked part edited in CAD (open question 5).
- **c0255 relative-placement:** a relative request is resolved to nm before the merge. Its resolved value
  is the code side, so a part placed `right_of(U1)` follows U1 unless it was moved by hand. It must be
  resolved against the merged anchor position (open question 6).
- **c0256 design-testing:** `fenolite.testing` asserts on the merged model.
- **c0245 viewer** (other branch): shows conflicts and offers takes (decision 14).
- **c0069 sync, c0196 edit, c0241 Altium edit sessions:** reused or untouched, as stated above.

## Risks / Trade-offs

- **Behaviour change of `place()`** after the first build (decision 4). Mitigation: CHANGELOG and
  `docs/lens.md`; `edit.code-wins` names every move; only parts the user did not move are affected.
- **Base record drift.** If someone restores an old board from git without its base record, the merge
  may misclassify. Mitigation: both files are in one folder and one commit. A foreign record is ignored
  with a warning. `--take` resolves what remains.
- **Byte churn on upgrade.** The first build after this change writes `fenolite-base.json`, and
  `tests/data/lens/sync_minimal/` gains it. Committed fixtures are regenerated in one task.
- **Footprint ids from KiCad's global libraries** may not resolve in CI. Mitigation: the existing library
  errors name them, and vendoring copies them once resolved.
- **Two CAD sides** add a read of the schematic to every rebuild. It is the reader that `sync` already
  runs. The cost is measured in task 4.3.

## Open Questions

1. **Base location.** The research named `.fenolite/`; this design uses `<out>/fenolite-base.json`
   (decision 2). *Recommended:* the output-folder file, to keep the clone-independence principle of
   `docs/lens.md`.
   Decided 2026-10-30: the output-folder file `<out>/fenolite-base.json` (implemented so).
2. **Units in `edits.toml`.** Bare millimetres and degrees (as `placements.toml`) or unit strings
   (`"12.7mm"`, `"90deg"`, as the research sketch)? *Recommended:* bare numbers on write. Reading unit
   strings can come once c0246's parser exists, as a compatible addition.
   Decided 2026-10-30: bare numbers; unit strings may be read later as a compatible addition.
3. **Altium CAD side.** Read values and footprints from saved `.SchDoc` parameters and positions from
   `.PcbDoc` (c0041 reader), with the generated baselines as base? *Recommended:* a follow-up change,
   after this one and after c0241's Part J facts. The snapshot replay rules need their own design.
   Decided 2026-10-30: a follow-up change; an Altium build has no CAD side here.
4. **Footprint edit on a `device=` part (c0248).** *Recommended:* allowed when the device lists the
   footprint. Otherwise keep it with a warning from c0248's checks; never a silent revert.
   Decided 2026-10-30: as recommended; the merge keeps the edited footprint, c0248's checks judge it.
5. **Value edit on a picked part (c0254).** *Recommended:* the edit wins over the pick and marks the
   part as fixed in the lock, and c0253 judges it. c0254 states it.
   Decided 2026-10-30: as recommended; the edit wins over the pick (the pick side is c0254's to state).
6. **Relative placement (c0255).** *Recommended:* resolve relative requests against the merged positions
   of their anchors, in path order, so a hand-moved anchor carries its followers.
   Decided 2026-10-30: as recommended (`lens.preserve.resolving` resolves against the decided positions).
7. **A script-side lock for values** (`part.lock("value")`)? *Recommended:* no. `--take code` once is
   enough, because the base then records the choice.
   Decided 2026-10-30: no script-side value lock; `--take code` once records the choice in the base.
