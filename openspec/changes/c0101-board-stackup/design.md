## Context

The review of 2026-10-05 of the gaps to a complex board listed the stack-up as a gap: the model has the types, and nothing constructs them for KiCad. The proposals of that review are milestone v0.4 (`docs/roadmap.md`, "v0.4: proposals on other branches"). Checked in the code of `origin/dev` at `9aba2dff` on 2026-10-07:

- `model/board.py:66-84`: `StackLayer(name, kind, thickness, material, epsilon_r, loss_tangent)` and `Stackup(layers, finish)`; `StackKind` (line 26) is `copper`, `dielectric`, `soldermask`, `silkscreen`, `solderpaste`. Nothing tells a core from a prepreg, and there is no colour.
- `backends/kicad/pcb.py:2310-2320`: a created board gets `(general (thickness T) (legacy_teardrops no))`, T being the sum of `Board.stackup` or 1.6 mm, and `(setup (pad_to_mask_clearance 0))`, never a stack-up node. `read_board` leaves `Board.stackup` `None` (living "Modelled board content"); `setup` is an opaque root slot.
- `pcb.py`, `projection()` (from line 2526) with `paper_node` and `title_block_node`: `paper` and `title_block` are root children projected into the model and rewritten when the model changed. This change follows that pattern.
- `lens/preserve.py:670`, `merge_layout`: it keeps the existing board with its root slots, so a stack-up typed into a board in KiCad survives a rebuild, and a script cannot change it.
- `analysis/current.py:117-118` and `analysis/boundary.py:81-82`: `analyze` already takes copper and board thickness from `Board.stackup` when it is set, which no KiCad read does.
- The Altium side (c0043 archived; c0085 and c0090 open on `dev`, code merged). `backends/altium/adapter/layers.py:225-291`: an Altium board fills `Board.stackup` with copper and dielectric entries only. Two functions named `stack_from_stackup` read it back, `lens/altium_copper.py:399` for a build and `backends/altium/lower.py:268` for the write of a model: both keep the copper and dielectric entries, pass every other kind over, and accept the stack-up only with exactly one dielectric between neighbouring copper layers; otherwise the document gets Fenolite's default values with one `altium.not-lowered` whose `where` is `stackup`. The kind of each dielectric comes from a table by count (`dielectric_kinds`), because the model does not state it; the record has a key for it (`DIELTYPE`, `backends/altium/libboard.py:104-105`). `checks/diff.py:227-231` and `checks/rta2.py:55` list and count the entries.
- `dsl/convert.py:186` builds a `Board` without a stack-up; the DSL has no call for one.

**Measured on 2026-10-05,** on the branch where this proposal was written (`review-roadmap-complex-board`); not repeated on `dev` at `9aba2dff`, and tasks 1.3, 1.4 and 7 record every part again as a probe. Benches: a created 50 × 30 mm board with one track per copper layer, written by `write_board` for target 9 and target 10 with 2, 4, 6 and 8 copper layers (6 and 8 with hand-built layer rows, numbered `2k + 2`), and a `(stackup …)` node inserted into `setup` by token edit, in 18 variants. Commands, each on a copy: `kicad-cli pcb upgrade --force B.kicad_pcb`; `kicad-cli pcb export gerbers -l F.Cu -o out/ B.kicad_pcb`, which also writes `B-job.gbrjob`; `kicad-cli pcb export ipc2581 -o B.xml B.kicad_pcb`; `kicad-cli pcb drc --format json --severity-all -o B.json B.kicad_pcb`. 10.0.6 is the macOS application, on 63 boards. 9.0.9 ran the first two commands on the 42 target-9 boards in one container: `docker run --rm --platform linux/amd64 -v <bench>:/p -w /p -e HOME=/tmp kicad/kicad:9.0.9@sha256:e638b79b… sh run.sh`. The corpus census read the cached boards with Fenolite's parser. None of this is committed; each part becomes a recorded probe or test.

1. *What KiCad writes* (corpus: 16 demo boards of tag 10.0.6, 6 of tag 9.0.9.1, 3 third-party boards; 24 readable). 18 boards hold a node in `setup`: 11 with 2 copper layers, 5 with 4, 1 with 6, 1 with 8. The 6 others, all two-layer, have none and `general` thickness 1.6 mm. The 202 rows are: one per layer `F.SilkS`, `F.Paste`, `F.Mask`, `B.Mask`, `B.Paste`, `B.SilkS` (types `Top Silk Screen`, `Top Solder Paste`, `Top Solder Mask`, `Bottom Solder Mask`, `Bottom Solder Paste`, `Bottom Silk Screen`), 56 copper rows named after their layer (type `copper`), and 38 dielectric rows named `dielectric <n>` (23 `core`, 15 `prepreg`). Row children come in the order `type`, `color`, `thickness`, `material`, `epsilon_r`, `loss_tangent`. Two prepreg rows of one board hold a second sheet: the atom `addsublayer`, then that sheet's `color`, `thickness`, `material`, `epsilon_r` and `loss_tangent`. Every node ends with `copper_finish` (`None` 12, `ENIG` 3, `HAL lead-free` 2, `Immersion tin` 1) and `dielectric_constraints` (`yes` on 2); one adds `castellated_pads`. `general` thickness equals the sum of every row and sheet, masks included, on 17 boards; one states 1.6002 mm against 1.6 mm.
2. *The job file of a complete node*, the same on 9.0.9 and 10.0.6 for all 42 shared variants: one `MaterialStackup` entry per row, a sheet as entries `(1/2)` and `(2/2)`, each with `Thickness`, `Material` and `Color`; `DielectricConstant` and `LossTangent` only with `dielectric_constraints yes`, which also adds `ImpedanceControlled: true`; `Finish` is `copper_finish` verbatim (`ENEPIG` kept). `BoardThickness` is `general` thickness: 1.6 where the rows sum to 1.29, 1.725, 2.16 and 2.595 mm.
3. *An incomplete node* loads, and the job file then lists every layer with no `Thickness` at all. On both majors: copper and dielectric rows only; masks without silkscreen and paste rows; copper rows for 2 layers on a 4-layer table and for 4 on a 6-layer table; copper rows named `Top`, `Mid1`, …; two dielectric rows between neighbouring copper rows. On 10.0.6 only: copper and dielectric rows without the tail; copper rows for 6 layers on a 4-layer table; paste rows on a table without paste layers. Also on 10.0.6 only, silkscreen after mask on the top side, and a table without paste layers whose node has no paste rows, give thicknesses. The rule of Decision 5 predicts the verdict of all 53 boards with a node on 10.0.6, and it calls all 18 corpus nodes complete.
4. *No node*, both majors: copper 0.035 mm, masks 0.01 mm, n − 1 equal FR4 dielectrics of (T − 0.02 − 0.035 n) / (n − 1) for `general` thickness T: 1.51, 0.48, 0.274 and 0.1857 mm for 2, 4, 6 and 8 layers at 1.6 mm. `Finish` is `None`.
5. *Re-save on 10.0.6* (`pcb upgrade --force`): a complete node in the form of Decision 6 comes back with the same text, and `general` thickness is kept even where it differs from the sum. A copper row without thickness gets 0.035 mm, a mask 0.01 mm, a dielectric without material `FR4`, 4.5 and 0.02, a dielectric without type `core`; a node without its tail gets `(copper_finish "None") (dielectric_constraints no)`. `4.50`, `0.0200` and `0.20` become `4.5`, `0.02` and `0.2`. A mask of thickness 0, the dielectric type `laminate` and the colour `NotAColour` are kept (the job file states the colour verbatim, `Purple` as `R80G0B80`). A row named after no layer becomes `dielectric <n>`, whatever its type. 9.0.9's `pcb` command group holds `drc`, `export` and `render`, no `upgrade`.
6. *Thickness in other outputs*, 10.0.6: IPC-2581's `overallThickness` is 1.7250 on a board whose rows sum to 1.725 mm and whose `general` thickness is 1.6 mm; `ENIG` becomes `ENIG-N`. `pcb drc` reports no violation type about the stack-up on complete, incomplete and copper-only nodes.

## Goals / Non-Goals

**Goals**
- A stack-up that KiCad uses is in the model after a read, and written by every build that declares one.
- The script declares copper weights, dielectrics, mask, finish and the impedance-control flag, and a build gives a job file that states them on both majors.
- One board thickness: the sum of the stack-up, in the model, in `general` and in every export.
- `analyze` and the later changes (c0105, c0106, c0115, c0117) read thicknesses from the model.

**Non-Goals**
- Everything under "Non-goals" in the proposal.
- No other child of `setup`: via protection there is c0112's; plot settings and the rest go nowhere, because no yardstick item needs them.

## Decisions

1. **One projection of `setup`; its slot keeps the bytes.** `read_board` projects the `stackup` child of `setup` into `Board.stackup`, and `setup` stays an opaque root slot, as `paper` and `title_block` do, so RT1, `opaque_count` and the closed list of "Modelled board content" are unchanged. The writer compares the model with the projection of the slot and rewrites only on a difference. Rejected: modelling `setup` whole (plot settings, tenting, zone defaults): nothing here needs them, and c0112 owns via-protection defaults in `setup`.

2. **The model lists every row KiCad keeps, top to bottom.** Silkscreen and paste rows become entries of thickness 0, masks keep their thickness, and a dielectric row with sheets becomes one consecutive entry per sheet, each with the row's name. Rejected: copper and dielectric entries only, as the Altium import gives them: masks are part of KiCad's thickness (measurement 1), and mask and silkscreen colours are ordered from the fabricator. Rejected: sheets nested inside one entry: a second entity, and every sum would look inside it.

3. **Three fields with defaults, and three helpers.** `StackLayer.dielectric_kind: DielectricKind | None = None` (`core` or `prepreg`), `StackLayer.color: str = ""` and `Stackup.impedance_controlled: bool = False`. `Stackup.thickness()` sums the entries; `Stackup.depth(name)` gives the depths of an entry's two faces below the top face; `Stackup.between(upper, lower)` gives the entries between two others, for dielectric heights (c0105, c0115) and via lengths (c0106). Old documents load; `canonical` omits defaults. The other direction does not hold, as for every additive model key (the convention c0126 set): release 0.2.x cannot read a model document that carries `dielectric_kind`, `color` or `impedance_controlled`, because its reader refuses an unknown key. `docs/design-model.md` and the changelog say so (tasks 2.3 and 10.3), and the `board.json` that release 0.2.0 wrote, which c0126 commits as `tests/data/model/v0.2.0/blink_2layer.board.json`, must still load and serialise to its own bytes (task 2.1). Rejected: `core` and `prepreg` as `StackKind` values: the Altium adapter, both `stack_from_stackup` functions and the analyses read `kind == "dielectric"`.

4. **The board thickness is the sum of the stack-up.** Whenever the writer writes a node, `general` thickness is `Stackup.thickness()`. On read, a `general` thickness that differs from the sum gives `kicad.board.stackup-thickness` (warning), naming both and the outputs that state each (measurements 2 and 6); the model keeps the sum. Without a stack-up the model holds no thickness, and a created board still writes 1.6 mm. Rejected: `Board.thickness`, a second number for what the rows sum to; KiCad keeps two and its outputs disagree. Rejected: reading `general` thickness without a node: on the 6 corpus boards without one it is KiCad's untouched 1.6 mm, which c0047 refused to assume.

5. **The reader projects only a node KiCad uses.** Complete (H-K-STACKUP-COMPLETE): the rows named after layers are exactly the table's silkscreen, paste and mask layers and all its copper layers, each with its layer's type; the copper rows follow the table order; exactly one dielectric row lies between neighbouring copper rows. Every other row is a dielectric row. An incomplete node gives `Board.stackup = None` and `kicad.board.stackup-unused` (warning: the job file states no thickness). A complete node that the model cannot hold exactly gives `None` and `kicad.board.stackup-unmodelled` (info): a length that is not a whole nanometre, a copper, dielectric or mask row without thickness, a decimal that is not plain, or a dielectric row outside the outer copper rows, a case not measured. Rejected: projecting an incomplete node: the model would claim thicknesses the fabricator never sees.

6. **The writer completes the node from the layer table.** `complete(stackup, layers)` adds an entry for each silkscreen, paste and mask layer of the table that the stack-up lacks, at its place, of thickness 0. The node holds one row per entry in KiCad's order of children, consecutive dielectrics between two copper rows joined into one row with `addsublayer`, then `(copper_finish …)` (`"None"` for an empty finish) and `(dielectric_constraints yes|no)`, and goes first in `setup`. A rewritten node keeps the `edge_connector`, `castellated_pads` and `edge_plating` of the node it replaces. Both targets write the same node (measurement 2). Rejected: an omitted mask without thickness: KiCad then counts 0.01 mm (measurement 5) and `general` no longer equals its sum. Rejected: physical rows only (measurement 3).

7. **Validity lives in the model.** `Design.validate()` reports `model.stackup-order`, `model.stackup-copper` and `model.stackup-value`, so a model from any source is judged once; the build refuses on them. `write_board` refuses what it cannot write complete with `kicad.board.stackup-invalid` (error), for callers that do not validate. Rejected: checks in the DSL only: the model API and imports would pass them.

8. **The script lists entries top to bottom.** `design.stackup(*entries, finish=None, impedance_controlled=False, locked=False)` with entries of `fenolite.dsl.stack`: `silkscreen(color=…)`, `mask(t, …)`, `copper(t)`, `core(t, …)`, `prepreg(t, …)`. Copper entries take the board's copper names in order (`Design.copper_layers` of c0100), dielectrics `dielectric <gap>` and masks and silkscreens their layer names, as KiCad names them, so a rebuild compares equal names. Decimals are normalised as KiCad's re-save does (`"4.50"` → `"4.5"`). The call refuses at once what needs no target: a copper count other than the board's, a gap without a dielectric, two kinds in one gap, misplaced or repeated outer entries, floats, a copper or dielectric thickness of 0. Rejected: keyword lists (`copper=[…]`, `dielectrics=[…]`): their lengths must agree and sheets need nesting. Rejected: an ounce unit: the thickness per ounce differs by source.

9. **The rebuild rule is the zones' rule.** `backends.kicad.stackup.merge_stackup` compares `complete(script)` with the board's projection, ids aside. Equal, or no script stack-up: the board's is kept. No board stack-up (none, or unused): the script's is written. Different and unlocked: the board's wins, with `kicad.stackup.overridden` (info). Different and locked: the script's replaces it, with `kicad.stackup.forced` (warning). KiCad has no lock token for a stack-up; the lock lives in the script. The codes are `kicad.*`, so they pass the closed layout and build tables unchanged. Rejected: the script always wins: an edit in KiCad's Board Setup would be undone silently. Rejected: `layout.*` codes, which need a MODIFIED "Layout issue codes", a closed table that other proposals of v0.4 would then have to regenerate.

10. **`analyze` says where a thickness came from.** Its reading code exists; filling `Board.stackup` makes it work on KiCad boards. The reply gains `inputs.board_thickness_source` (`option`, `stackup` or `null`) and `inputs.stackup` (total and copper thicknesses). Rejected: the stack-up over the options: an option keeps winning, as c0047 decided.

11. **Outputs show what the fabricator gets.** `export --gerbers` of a board without a stack-up gives `export.stackup-default` (info) naming KiCad's default; an info plans the writes. `inspect` reports `result.stackup`. Rejected: refusing the export: a two-layer board without a stack-up is ordinary.

12. **Presets, cut first.** `stack.preset(name)` returns the entries of `dsl/stackups/<name>.toml`, which holds its source id, URL, retrieval date and the rows as one public fabricator page states them; at most three (2, 4 and 6 copper layers). No fabricator is named in this change; file names are neutral (Open Questions). The three pages are S-0720, S-0721 and S-0722 (the block S-0620 to S-0639 was given to this group on 2026-10-07; on 2026-10-08 the coordinator of release 0.4 gave the lanes that close v0.4 the ids from S-0720 up, since parallel branches were taking ids of the S-06xx blocks, and the design is corrected to them). Rejected: presets computed to a thickness: they would ship Fenolite's own numbers.

13. **Requirements shared with other changes** (checked on `origin/dev` at `9aba2dff`, `openspec/changes/*/specs`, on 2026-10-07).
    - No open change on `dev` holds a delta of "Modelled board content", "Created board header" or "Projected fields on write"; each MODIFIED delta here is the living text with this change's edits only. c0043, c0044 and c0069 are archived.
    - "Created board header": c0100, then this change, then c0112. c0100 widens `created_layers` to 2, 4, 6 and 8 and lands first; this change depends on it for 6 and 8 layers and regenerates its delta on c0100's text (task 0.1). c0112 regenerates after this change.
    - "Modelled board content": this change, then c0103 (its board items), then c0112; the edits touch different sentences, and each later one regenerates from the living text.
    - "Projected fields on write": this change, then c0112, which regenerates.
    - A layer-count change kept by c0100's "Layer count across rebuilds", or made by c0102's "Copper layer changes across rebuilds", leaves an old node that "Stack-up on boards" calls incomplete; c0102 removes it, and the script's stack-up is then written.
    - "Stack-up across rebuilds" states its precedence over "Board content outside the design is kept" (living; c0102 modifies it), as "Zones declared in the script" does over "Copper items follow their nets". "Stack-up in inspect" adds to the living "Inspect command". c0112 edits other children of `setup`; each projection rewrites only its own child.
    - Open on `dev` and touched in code, not in a shared requirement: c0085 (`lens.altium_copper.stack_from_stackup`), c0090 (`backends.altium.lower.stack_from_stackup`, the round trips that compare models) and c0126 (the convention for additive model keys). They are archived with release 0.3.0, before this change lands.
    - Rejected: modifying "Board content outside the design is kept" and "Inspect command", which would make several proposals regenerate on each other for one sentence each.

14. **The Altium document takes what it has a key for, and names the rest.** Since c0085 a model stack-up reaches the PCB document, so a KiCad board read with a node, or a script with `stackup()`, now changes an Altium build. On `dev` such a stack-up would be handled by accident: masks are passed over without a word, a gap of two sheets drops the whole stack-up to the defaults, and a stated `core` is written as whatever the table by count says. "Stack-ups with masks, sheets and kinds in an Altium build" makes each case a rule, for both `stack_from_stackup` functions:
    - Solder mask, silkscreen and paste entries are passed over. The stack of the document holds copper and the dielectrics between.
    - A stated `dielectric_kind` is written as the dielectric's kind (`DIELTYPE` 1 or 2, a fact already recorded in `docs/formats/altium/pcb-copper.md`, "Layer stack"). An entry without one keeps the table by count, so every committed sample and every Altium import keeps its bytes.
    - A gap of two or more sheets does not fit: the document gets the default values and one `altium.not-lowered` with `where` `stackup` naming the gap, which is what `dev` does today.
    - A mask thickness above 0, a colour, a finish or the impedance flag has no recorded key: one `altium.not-lowered` (info, `where` `stackup`) lists them, and the copper and dielectric values are written.
    - The Altium import does not fill the three new fields in this change: its entries keep `dielectric_kind` `None`, so the round trips of c0090 and c0126 compare the models they compared before.
    - No row of the Altium rule table is touched: this change adds no rule kind and no selector.
    - Rejected: joining the sheets of a gap into one dielectric of their summed thickness. It is exact only when the sheets share material and permittivity, and nothing on `dev` writes it; it is an open question, not a silent approximation.
    - Rejected: a new issue code. `altium.not-lowered` with `where` `stackup` already names stack values that the document does not hold.

## Found on 2026-10-07

Implemented on the branch `v04` at `f36e08d9`, where the prerequisites of the proposal do not all hold.
What the code and the measurements of the day showed, and what was corrected in the same commit:

1. **Prerequisites.** Release 0.3.0 is not out. c0085 and c0090 are implemented and not archived; this
   change builds on their code, and none of its MODIFIED deltas builds on a delta of theirs. c0100 is not
   on the branch: everything about 6 and 8 copper layers, and the delta of "Created board header" on
   c0100's text, is open. c0126 is not on the branch: its convention for additive model keys was not
   available. What exists was followed: `canonical` omits defaults, the decoder refuses unknown keys, the
   schema is regenerated by `tools/gen_schemas.py`, and `docs/design-model.md` says "additive" per field
   group. The fixture is the `board.json` that the code of the base commit (0.2.1) wrote for
   `examples/blink_2layer`, `tests/data/model/v0.2.1/blink_2layer.board.json`, not c0126's 0.2.0 file.
2. **A loss tangent may be 0.** Two solder mask rows of the corpus hold `(loss_tangent 0)`, as KiCad
   writes it. "A plain decimal above 0" would have made KiCad's own boards invalid, so
   `model.stackup-value`, the reader's exact-value rule and the script accept a loss tangent of 0;
   `epsilon_r` stays above 0 (a reader that meets 0 gives `kicad.board.stackup-unmodelled`).
3. **`FLOOR_HEADS` gains seven names, not eight.** `type` is in the skeleton, and the living requirement
   and its test keep `FLOOR_HEADS` disjoint from the skeleton. The names are sourced from S-0021 (read
   again) and S-0058; S-0033 was not read.
4. **Explain entries: eight, not eleven.** No `model.*` code has an entry: they are in no `*ISSUE_CODES`
   table, and `tests/unit/cli/test_explain_cmd.py` refuses an entry without one.
5. **Re-save adds constants (Context, measurement 5).** On 10.0.6 a written dielectric that states a
   material and no constants comes back with `(epsilon_r 4.5) (loss_tangent 0.02)`. The writer still adds
   nothing the script does not give (the DSL requirement). The consequence is documented: after KiCad
   saves such a board, a rebuild reports `kicad.stackup.overridden` and keeps the board's stack-up, until
   the script states the constants or locks. `H-K-STACKUP-RESAVE` and `pcb-stackup-resave` name the
   defaults. A dielectric row without a thickness comes back with `(thickness 0)`; the
   `pcb-stackup-resave-defaults` bench gives that row a thickness.
6. **The bench module is `tests/_stackbench.py`.** A hermetic half under `tests/unit` cannot import a
   module of `tests/kicad/board`; the other benches with a hermetic half live in `tests/`.
7. **`dsl/stack.py` imports the DSL's errors and lengths** besides the standard library, `fenolite.core`
   and `fenolite.model`: `DslError` and DSL lengths live in `fenolite.dsl`.
8. **Refusal of a stack-up that was accepted.** A created board whose model holds a stack-up now gets the
   node, so a stack-up that cannot be written complete is refused (`kicad.board.stackup-invalid`), where
   the writer took only its sum for `general` before. No command of the released code builds such a
   board (the script had no stack-up, and no command writes an Altium import as a KiCad board), so no
   built file changes: the blink and the routed blink build byte-equal files for targets 9 and 10 before
   and after this change (18 files each, `.fenolite/` included).
9. **Rows of a node the table does not hold.** A row named after an outer or copper layer that the table
   does not hold (paste rows on a table without paste layers, the probe `nopaste`) makes the node
   incomplete, as Decision 5 intends; the reader therefore treats such a name as a layer name, not as the
   name of a dielectric row.
10. **`source` of equal stack-ups is `script`.** When the script's stack-up equals the board's, the
    board's entities and text are kept and `result.stackup.source` is `script`, so a second build gives
    the result of the first.
11. **What stops the writes of `export`.** At `f36e08d9` `cmd_export.py` planned its writes only when
    the run reported no issue at all (`if not issues`): an error, a warning or an info alike planned
    nothing, though only errors reached that test. c0116, which landed first, changed the test to
    "no error": its warnings (`kicad.lib.missing-3d-model`, `export.model-unread`,
    `export.page-too-small`) never hold the files back, and its requirement and tests say so. On that
    rule the stack-up info passes without a change of the test, so this change keeps c0116's line and
    does not make a warning stop the writes again (an earlier form of this change did, before c0116 was
    on the branch: that would have dropped c0116's behaviour). The MODIFIED delta of `cli-contract`
    "Export command" is regenerated on c0116's text and adds one sentence (only an error stops the
    writes; an info does not) and two scenarios; the tests pin an authored info that is not the
    stack-up one, an error that writes nothing, and c0116's rule for a warning.
12. **Rebased on the tip of the first wave (`7392159d`).** c0100 is on the branch, not archived.
    "Created board header" is regenerated on the text of c0100's delta (its `created_layers` for 2,
    4, 6 and 8, `inner_rows` and `created_count` kept word for word), with this change's edits applied
    again; "Modelled board content" and "Projected fields on write" stand on the living text, since
    no implemented change modifies them (c0103 and c0112 are proposals and regenerate after this
    change); "Export command" is regenerated on c0116's delta (item 11). `Design.stackup()` takes
    its copper names from c0100's `Design.copper_layers` (Decision 8), and the helper this change had
    for them is gone. The created test board carries a stack-up for each of the four counts. c0123
    changed the model and the schemas: the schemas are regenerated with the tool, and the fixture of
    release 0.2.1 still loads and serialises to its own bytes (no wave-1 change brought another
    old-document convention; `tests/unit/model/test_copper_lock.py` waits for c0126's fixture).
    The benches of 6 and 8 layers and the six-layer build are `equal` on 10.0.6; their 9.0.9 side is
    left to the one image run of the wave.
13. **Not done.** Presets (the first cut; no page was read), the widening of six "used for" cells
    (`docs/evidence/sources.md` is append-only for the lanes of the night), `docs/roadmap.md` (the
    coordinator's), and the unit suite on Python 3.11.
14. **Done on 2026-10-08, on `v04` at `04ef42a`.** The presets: three pages of one fabricator, one per
    copper count (2, 4 and 6), each a whole stack-up table with millimetre values, registered as
    S-0720 to S-0722; the files are `two-layer-1.6mm`, `four-layer-1.6mm` and `six-layer-1.6mm`. A
    page states a silkscreen thickness, which the file keeps and the stack-up does not take (a
    silkscreen row has none). The six "used for" cells are widened (task 1.1), `docs/roadmap.md` is
    updated, and the unit suite runs on Python 3.11 (task 10.1).

## Found on 2026-10-08

The full suite on `3336325e` failed 17 cases of `tests/kicad/board/test_layer_tables.py` and the probe
check that runs the same benches, with `kicad.board.stackup-invalid`: "the copper entries ['F.Cu',
'B.Cu'] are not the board's copper layers". `make check-fast` does not run `tests/kicad`.

1. **The bench was wrong, not the writer.** c0100's `tests/kicad/board/_layertables.py` takes
   `created_board(2)` and replaces only its layer table by the table of 2, 3, 4, 6 or 8 copper layers.
   It is a created design, not a read one. Since this change the created test board carries a stack-up
   ("Found on 2026-10-07", item 12), so the bench wrote a two-copper stack-up under another table: the
   case of the scenario "Copper entries that do not fit the table" and of item 8, which the writer must
   refuse. The bench now removes the stack-up, so its probes judge the table alone and KiCad derives its
   default, exactly as c0100 measured; c0100's requirement "Created layer tables are probed on both
   majors" says so. The stack-up on each count is this change's own bench (`pcb-stackup-*`, task 7.1)
   and the triad's (`created_board(n)`). No probe outcome changed and none was recorded again.
2. **The writer drops no stack-up to fit a table, read or declared.** Considered and rejected: letting
   the writer of a read board leave out a stack-up whose copper entries are not the table's, with a
   warning. The writer cannot tell a read stack-up from a declared one (a merged build is written by the
   same path as a read board, and `Board.stackup` carries no mark of who chose it), no command reaches
   the writer in that state today (a build over a board of another copper count stops at
   `layout.copper-mismatch`, c0100), and thicknesses and materials would leave the file on a warning.
   The refusal is now stated for both kinds of board and pinned by
   `test_layer_table_changed_under_a_stackup`.
3. **For c0102** ("Copper layer changes across rebuilds", `kicad.layers.stackup-reset`). Its layer merge
   has to do both halves itself, before `merge_stackup` and before the writer: remove the `stackup`
   child from the `setup` fragment, and set `Board.stackup` to `None`. Setting the model field alone
   does not remove the node: under the new table the old node is one "that KiCad ignores"
   (`project_stackup` gives `None` for it), so the writer sees no difference from the model and keeps
   the `setup` fragment as it is, as the scenario "A node KiCad ignores" requires. Measured on
   `stackup_four.kicad_pcb` read, given `created_layers(2)` and `stackup=None`: the written `setup`
   still holds the four-copper node. Leaving the model field set gives the refusal of item 2.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/model/board.py` | `DielectricKind`; `StackLayer.dielectric_kind`, `.color`; `Stackup.impedance_controlled`; `Stackup.thickness()`, `.depth(name)`, `.between(upper, lower)` |
| `src/fenolite/model/design.py` | `model.stackup-order`, `model.stackup-copper`, `model.stackup-value` |
| `schemas/fenolite.model.v0/board.json` | regenerated |
| `src/fenolite/backends/kicad/stackup.py` (new) | `TYPES`, `project_stackup`, `complete`, `stackup_node`, `rewrite_setup`, `values`, `merge_stackup`, `StackupMerge`, `MERGE_ISSUE_CODES`, `EVIDENCE` |
| `src/fenolite/backends/kicad/pcb.py` | the projection, the created node, the rewrite, three read and two write codes, `FLOOR_HEADS` |
| `src/fenolite/dsl/stack.py` (new) | `StackEntry`, `silkscreen`, `mask`, `copper`, `core`, `prepreg`, `preset` |
| `src/fenolite/dsl/design.py`, `dsl/convert.py`, `dsl/__init__.py` | `Design.stackup`, `StackupSpec`; `Board.stackup` in `to_model`; keys `stackup`, `stack_layer`; `stackup_locked(design)`; `stack` re-exported |
| `src/fenolite/dsl/stackups/*.toml` (new, cut first) | presets |
| `src/fenolite/lens/build.py`, `cli/cmd_build.py` | `build_design(…, lock_stackup=False)`, the merge step, `result.stackup` |
| `src/fenolite/cli/cmd_analyze.py`, `cmd_export.py`, `exports/codes.py`, `cmd_inspect.py` | `inputs.board_thickness_source`, `inputs.stackup`; `export.stackup-default`; `result.stackup` |
| `src/fenolite/lens/altium_copper.py`, `src/fenolite/backends/altium/lower.py` | both `stack_from_stackup`: the stated dielectric kind; the info for values without a key; the gap named in the message of a stack-up that does not fit |
| `src/fenolite/cli/data/explain.toml` | one entry per new code of a table (eight; "Found on 2026-10-07") |
| `tests/_boards.py` | `created_board()` with a stack-up (every new floor name) |
| `tests/data/kicad/board/stackup_four.kicad_pcb` (authored, declared in `tests/data/MANIFEST.toml`) | a four-layer node with a sheet, colours, `ENIG`, constraints |
| `tests/_stackbench.py`, `tests/kicad/board/test_stackup_oracle.py` | benches and probes |
| `tests/unit/model/test_stackup.py`, `tests/unit/backends/kicad/test_stackup_{read,write,merge}.py`, `tests/unit/dsl/test_stackup_dsl.py`, `tests/unit/lens/test_build_stackup.py`, `tests/unit/lens/test_altium_stackup.py`, `tests/unit/backends/altium/test_lower_stackup.py`, `tests/corpus/test_stackup_census.py` | tests |
| `docs/formats/kicad/board.md`, `docs/design-model.md`, `docs/dsl.md`, `docs/lens.md`, `docs/altium.md`, `docs/analyses.md`, `docs/exports.md`, `docs/cli-contract.md`, `docs/evidence/kicad-stackup.md` | facts, census and user docs |

## Sources used

No new source for the KiCad facts: S-0021 (the stack-up token names), S-0058 (demo boards: type strings, child order, sheets), S-0020 and S-0029 (the oracles), and the download page of S-0125 (the job file format). Task 1.1 widens their "used for" cells. S-0033 (a keyword list in KiCad's source tree) was named here at first and is not used: the names come from S-0021 and S-0058, and since 2026-10-08 no third-party source code is cited as a format fact. No new source for the Altium part: `DIELTYPE` is a fact of `docs/formats/altium/pcb-copper.md` already. Each preset adds one row with its URL, terms and date (task 9.1), under the reserved ids S-0620, S-0621 and S-0622.

## New names

- Model fields: `StackLayer.dielectric_kind`, `StackLayer.color`, `Stackup.impedance_controlled`; type `DielectricKind`; methods `Stackup.thickness()`, `depth()`, `between()`.
- Script: `Design.stackup`, `fenolite.dsl.stack` (`silkscreen`, `mask`, `copper`, `core`, `prepreg`, `preset`, `PRESETS`, `StackEntry`), `StackupSpec`, `stackup_locked`; keys `stackup` and `stack_layer` of `fenolite.dsl.KEYS`.
- Issue codes (eleven): `model.stackup-order`, `model.stackup-copper`, `model.stackup-value`; `kicad.board.stackup-unused`, `kicad.board.stackup-unmodelled`, `kicad.board.stackup-thickness`; `kicad.board.stackup-invalid`, `kicad.board.stackup-rewritten`; `kicad.stackup.overridden`, `kicad.stackup.forced`; `export.stackup-default`.
- Result keys: `result.stackup` of `build` and of `inspect`; `inputs.board_thickness_source` and `inputs.stackup` of `analyze`.
- Hypotheses: `H-K-STACKUP-JOB`, `H-K-STACKUP-COMPLETE`, `H-K-STACKUP-DEFAULT`, `H-K-STACKUP-RESAVE`. Source ids: S-0720, S-0721, S-0722 (presets; Decision 12). No CLI flag.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-STACKUP-JOB | For a complete node, the job file of `pcb export gerbers` states one entry per row and sheet with its thickness, material and colour, the dielectric constant and loss tangent only under `dielectric_constraints yes` (which sets `ImpedanceControlled`), `copper_finish` as `Finish` and `general` thickness as `BoardThickness`, alike on 9.0.9 and 10.0.6 (S-0020, S-0029, S-0125) | `tests/kicad/board/test_stackup_oracle.py -k job` | `pcb-stackup-job-<n>` `equal` for n = 2, 4, 6, 8 and `build-stackup-job` `equal`, on both majors |
| H-K-STACKUP-COMPLETE | KiCad uses a node for the job file only when it is complete as Decision 5 states; otherwise the board loads and the job file states no thickness (S-0020, S-0029) | `… -k complete` | the seven `pcb-stackup-incomplete-<case>` (`physical`, `nosilk`, `fewer`, `more`, `names`, `twodiel`, `nopaste`) `absent`, and `pcb-stackup-order` and `pcb-stackup-nopaste-table` `present`, on both majors |
| H-K-STACKUP-DEFAULT | Without a node the job file states 0.035 mm copper, 0.01 mm masks and equal FR4 dielectrics that fill `general` thickness, finish `None`; 10.0.6 gives an incomplete row its defaults on re-save (S-0020, S-0029) | `… -k default` | `pcb-stackup-default-<n>` `equal` on both majors; `pcb-stackup-resave-defaults` `equal` on 10.0.6 |
| H-K-STACKUP-RESAVE | 10.0.6's `pcb upgrade --force` keeps a node in the written form and `general` thickness as written; IPC-2581's `overallThickness` is the sum of the rows (S-0020) | `… -k resave` | `pcb-stackup-resave` and `pcb-stackup-ipc-thickness` `equal` on 10.0.6 |

All four start `INFERRED`, with the measurements above as their first record. Ids used without a change of level: `H-K-PCB-WRITE`, `H-K-EXPORT-FILES`, `H-K-FMT-MIXED` (the `addsublayer` layout).

## Evidence level per behaviour (before merge)

| behaviour | level | proof |
|---|---|---|
| node written and stated by the job file | KICAD-VERIFIED (9.0.x, 10.0.x) | `pcb-stackup-job-*`, `build-stackup-job` |
| completeness rule of the reader | KICAD-VERIFIED (9.0.x, 10.0.x) | `pcb-stackup-incomplete-*`, `pcb-stackup-order`, `pcb-stackup-nopaste-table` |
| default of a board without a node | KICAD-VERIFIED (9.0.x, 10.0.x) | `pcb-stackup-default-*` |
| re-save and IPC-2581 thickness | KICAD-VERIFIED (10.0.x) | `pcb-stackup-resave*`, `pcb-stackup-ipc-thickness` |
| projection, model, script, merge | mechanical | unit tests and the corpus census |
| `analyze` | INFERRED, as c0047 | unit tests |
| presets | INFERRED, sourced | `tests/unit/dsl/test_stackup_presets.py` |
| the Altium document of a stack-up with masks, sheets and kinds | mechanical on a recorded fact (`DIELTYPE`); the Altium build keeps its level | `tests/unit/lens/test_altium_stackup.py`, `tests/unit/backends/altium/test_lower_stackup.py` |

`stackup.EVIDENCE` names the four hypotheses; a build that writes a node combines it into its evidence.

## Risks / Trade-offs

- **New warnings on read.** A board whose node KiCad ignores now warns, and so does one whose `general` thickness differs from its rows (1 of 18 corpus nodes). Both state facts the job file already carries.
- **`.fenolite/board.json` changes** for boards that hold a node. It is a cache; a rebuild writes it once.
- **A mask of thickness 0** in the job file when the script declares none. Documented; the fix is `stack.mask(t)`.
- **The created test board changes** (`created_board()` gains a node); tests that compare its text are updated with the floor names.
- **Altium imports and written samples are validated.** The three `model.stackup-*` findings run on every model, Altium imports included; task 2.2 runs the import tests, the six-layer sample `board6` and the round-trip tests of c0090, and records any finding.
- **Altium builds of a board with a KiCad stack-up change.** A stated `core` or `prepreg` is now written, and a gap of two sheets gives the default values with an info, as on `dev`. A design whose stack-up holds none of the new fields keeps its bytes.
- **The completeness rule is measured on eight incomplete cases.** A case it calls complete that KiCad ignores would show as a job file without thicknesses; the oracle probes catch the cases listed, and `build-stackup-job` catches it for every node Fenolite writes.

## Migration Plan

- Additive: a design without `stackup()` builds the same bytes, `.fenolite/` included; old `board.json` files load.
- Release 0.2.x cannot read a model document that carries `dielectric_kind`, `color` or `impedance_controlled`: its reader refuses an unknown key. The changelog and `docs/design-model.md` say so.
- Boards read with a node gain `Board.stackup`; their RT1 text is unchanged.
- Rollback: remove the projection and the writer branch; the model fields stay, defaulted.

## Budget (9 days)

| part | days |
|---|---|
| probes recorded, registers, bench module | 0.75 |
| model: fields, helpers, findings, schema | 0.75 |
| reader: projection, sheets, completeness, codes, corpus census | 1.25 |
| writer: completion, created node, rewrite, refusal, floor names, created board | 1.25 |
| script: `stack`, `Design.stackup`, `to_model` | 1.0 |
| build and rebuild: merge, lock, `result.stackup` | 0.75 |
| oracle tests on both majors | 0.75 |
| `analyze` reply | 0.25 |
| export note | 0.25 |
| `inspect` | 0.25 |
| presets | 1.0 |
| the Altium document: stated kinds, the info, both functions, `altium.md` | 0.25 |
| documentation and closing | 0.5 |

Cut order: (1) presets, 1.0 day; (2) `inspect`, 0.25; (3) the export note, 0.25, which leaves 7.5 days; (4) `silkscreen()` and `color=` in the script, which the reader and writer keep, about 0.25 of the script part, which leaves 7.25. Never cut: reader, writer, script call, rebuild rule, thickness, the oracle, and the Altium rule (a KiCad stack-up must not reach the Altium document by accident).

## Open Questions

- **An ounce unit for copper?** Default: no; the script gives a thickness.
- **May a preset's file name carry the fabricator's name?** Default: no; neutral names, and `docs/dsl.md` lists each with its source URL.
- **Should a rebuild correct a `general` thickness that differs from the rows of an unchanged node?** Default: no; the warning names it, and a locked script stack-up rewrites both.
- **Should `build` warn when a design declares no stack-up?** Default: no; `export` notes it, where the job file is made.
- **Should edge connector, castellation and edge plating be modelled for c0117's notes?** Default: no; kept as read.
- **Should the sheets of one gap be joined into one Altium dielectric when they share material and permittivity?** Default: no; the stack-up then does not fit and the info names the gap (Decision 14).
- **Should the Altium import fill `dielectric_kind` from `DIELTYPE`?** Default: not in this change; it would change every imported model and the fixtures of c0090 and c0126.
