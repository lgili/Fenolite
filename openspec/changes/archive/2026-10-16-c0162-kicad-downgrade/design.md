## Context

**Scope.** Milestone v0.5a, second item: "controlled KiCad downgrade (capability resolver)". A controlled downgrade writes a project that KiCad 10 saved for KiCad 9, and for each construct 9 cannot hold either writes 9's own form, drops it because 9 behaves the same without it, drops it and reports the loss, or refuses without consent. The roadmap's "capability resolver" is the table that decides which, per construct. This change registers the downgrade as a direction of c0159's `convert`; it needs c0159.

**What exists** (checked on `origin/dev` at `f802b60`, 2026-10-09):

| where | what |
|---|---|
| `src/fenolite/backends/kicad/versions.py:321` `check_target` | refuses a target older than `major_for(info.kind, info.version)` with `DowngradeRefusedError` (`FEN-7002`, exit 7) |
| `src/fenolite/backends/kicad/pcb.py:3189` `write_board` | calls `check_target` for a board read from a file; then `_pcbwrite.gate` runs `check_emittable` and splits too-new tokens into droppable (inside an opaque slot) and errors; `allow_lossy` removes each droppable **slot**, the outermost opaque node that holds the token (`_pcbwrite.py:238` `owner`, `:270` `remove`) |
| `src/fenolite/backends/kicad/pro.py:861` `_gate_nine` | a project written for 9 with keys of `TEN_ONLY_PATHS` (11: 6 `component_class_settings`, 4 `tuning_profiles`, 1 `net_settings`): `DowngradeRefusedError` when the board was read at 10, else `LossyWriteError` or dropped with `allow_lossy` |
| `src/fenolite/backends/kicad/sch.py` `rebuild_schematic`, `gate_created` | a read schematic is rebuilt at its own version only; created sheets are gated for their target |
| `src/fenolite/backends/kicad/data/tokens.toml`; `docs/formats/kicad/tokens.md` | 233 token rows, 63 with `since_major = 10` (12 board, 19 board and footprint, 17 schematic, 8 symbol library, 7 rules), 2 form rows (`net-by-name` since 10, `sch-hide-bool` since 9), notes that name 9's form for several rows ("8.0 and 9.0 write (island) without a value"; "9.0.9 loads the bare (power) only"; "9.0.9 loads convert in its place"; "9.0 writes (tenting front back)"); every row proved on 9.0.9 and 10.0.6 by the token fuzz (`docs/evidence/kicad/token-fuzz/`) |
| `backends/kicad/backend.py` `capabilities()` | `downgrade == "unsupported"` (`backend-protocol`, "Write capability fields") |
| `docs/formats/kicad/versions.md:69` | "Downgrade stays refused until a capability resolver exists." |
| `layout-lens`, "Refusals"; `kicad-oracle`, "Downgrade refused after a 10.0 save" | `build` refuses a board of major 10 for target 9, before any write; this change keeps that |

**Measured on 2026-10-09** (no `kicad-cli`; probe scripts kept with the change's working notes, not committed; task 1.1 turns them into tests):

1. *Boards.* Of the 18 KiCad 10.0.6 demo boards, 2 have a format of major 10: `CM5_MINIMA_3` (20250513) and `pic_programmer` (20260206); the other 16 are 9 (20241229, one 20241030), which `--kicad-version 9` already writes. With `check_target`'s source-major refusal bypassed, `write_board(target=9)` raised `LossyWriteError`, every issue droppable:
   - `CM5_MINIMA_3`: 1 384 too-new tokens: `tenting/front` 634, `tenting/back` 634, `duplicate_pad_numbers_are_jumpers` 112, `covering`, `plugging`, `capping`, `filling` 1 each. With `allow_lossy`, 746 nodes removed: 633 `tenting`, 112 `duplicate_pad_numbers_are_jumpers` and **1 `setup`**: the four via-protection tokens sit inside `setup`, the outermost opaque slot.
   - `pic_programmer`: 139 tokens: `footprint/units` 63, `duplicate_pad_numbers_are_jumpers` 63, `point` 7, the six via-protection tokens 1 each; 134 nodes removed: 63 `units`, 63 `duplicate_pad_numbers_are_jumpers`, 7 `point` and 1 `setup`.
   - Both written boards read back equal to the source at level 5 of `equivalent`: what was dropped is nothing that levels 1 to 5 compare. Whether 9.0.9 loads them was not run.
2. *Schematics.* Of the 114 schematic sheets of the demo projects, 10 have a format of major 10 (8 at 20250610, 2 at 20260101). `check_emittable(root, SCHEMATIC, 9)` on their trees gives: `body_style` 124, `in_pos_files` 124, `duplicate_pin_numbers_are_jumpers` 99, `in_pos_files` of a library symbol 29, `power global` 27, `body_styles` 1, and the header 10.
3. *Found on the way.* `RoyalBlue54L-Feather` (format 9) is refused even for target 9: 4 `kicad.board.opaque-net-ref` errors (an opaque `(net 41)` names `Net-(U1-P1.00/XL1)`, which is not a net of the design). Not a downgrade; the maintainer decided on 2026-10-09 (open question 4) that it gets a correction change of its own in v0.5a, after this one: c0163.

## Goals / Non-Goals

**Goals**
- A KiCad 10 project written for KiCad 9 on request, with each construct of 10 resolved by a stated, tested rule, and a report of what changed and what was lost.
- No coarse loss: a drop removes the construct, not the node that holds it.
- Every resolver row proved on 9.0.9 by a bench of its own.

**Non-Goals**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **The resolver table.** `src/fenolite/backends/kicad/data/downgrade.toml` holds one row per token row with `since_major` above a target in `TARGET_MAJORS`, per form row, and per key path of `TEN_ONLY_PATHS`. A row has `id` (the inventory row or `project:<path>`), `target` (9), `action` and, when the action depends on the value, `when` (a value) and `else` (the action for other values). Actions:
   - `rewrite`: the construct is written in the target's form, given by `form` (an S-expression template with the captured values) and its sources; reported as `changed`;
   - `same`: dropped; the target behaves as the source with that value (a default); reported as `changed`;
   - `presentation`: dropped; a drawing, a text or metadata changes, nothing that is made or checked; reported as `lost`, class `report`;
   - `design`: dropped; what is manufactured or checked changes; reported as `lost`, class `refuse`: needs `allow_lossy`.
   `resolver.load()` checks the table against `tokens.toml` and `pro.TEN_ONLY_PATHS`: a missing row, an unknown id, a `rewrite` without `form` or sources is an error of the unit suite. The initial actions (task 2.1 writes them; the bench of each row may change it, never towards less consent):

   | rows | action |
   |---|---|
   | `tenting-front`, `tenting-back` | `rewrite` to `(tenting front back)` with the sides that are `yes` (inventory note, S-0030) |
   | `island-yes`, `island-no` | `rewrite` to `(island)` for `yes`; `same` for `no` (note: "8.0 and 9.0 write (island) without a value") |
   | `sch-lib-power-global`; `sch-lib-power-local`, `sym-power-local` | `rewrite` to `(power)`; `design` for `local` (9 has no local power symbol: the net would join globally) |
   | `sch-symbol-body-style` | `rewrite` to `convert` (note: "9.0.9 loads convert in its place") |
   | `via-buried` | `rewrite` to 9's blind-and-buried via type, when its span is the same (task 1.2 settles the form on 9.0.9) |
   | `net-by-name` (form) | `rewrite`: nets by number with a net table, as target 9 boards are written today (`_pcbwrite.place_table`) |
   | `footprint-duplicate-pad-numbers-are-jumpers`, `sym-jumpers-duplicate` | `same` when `no`, `design` when `yes` |
   | `sch-symbol-in-pos-files`, `sch-lib-in-pos-files` | `same` when `yes` (9 puts every symbol in the position files), `design` when `no` |
   | `covering`, `plugging`, `capping`, `filling` | `same` when the value is the absent default (task 1.2 records it), else `design` (via protection is manufactured) |
   | `via-backdrill`, `via-tertiary-drill`, `via-front-post-machining`, `via-back-post-machining`, `pad-property-pressfit`, `pad-die-delay`, `variants`, `footprint-variant`, `sch-instance-variant`, `footprint-jumper-pad-groups`, `sym-jumper-pin-groups`, the 7 rules rows | `design` |
   | `project:tuning_profiles`, `project:component_class_settings`, `project:net_settings/classes/*/tuning_profile` (and their sub-paths) | `same` when the key holds what a fresh KiCad 10 project writes there (`pro.holds_default`, the 10 template), else `design`; first `design` for every value, corrected by the maintainer on 2026-10-09 (task 6.1) |
   | `fill-hatch` and its two siblings, `hatch-position`, `textbox-knockout`, `gr-rect-radius`, `sch-rectangle-radius`, `sym-rectangle-radius`, `barcode`, `footprint-units`, `point`, `table-uuid`, `group-lib-id`, `sch-table-uuid`, `sch-fill-*`, `sym-fill-hatch`, `sch-lib-body-styles`, `sym-body-styles`, `sch-rule-area-*`, `sch-group` | `presentation` |
   | `project:net_settings/meta/version` | `rewrite` to 9's version pair (`pro.PROJECT_VERSIONS[9]`) |

   Rejected: one action per file kind ("drop all, report"): the measurement shows the cost, the whole `setup` of two boards. Rejected: computing the action from KiCad's behaviour at run time (a 9.0.9 run per write): Fenolite writes without a tool; the bench settles each row once per major.
2. **Edits at the token's node.** The resolver works on the tree after the writer built it and before the emit check: for each `check_emittable` issue of code `kicad.token.too-new` it finds the row, then rewrites or removes **the node the issue locates** (its locator, not `_pcbwrite.owner`), inside opaque slots too. The emit check then runs again and must find no error; a remaining error is a defect of the table (a unit test on the benches). `_pcbwrite.remove` keeps its slot-level use for `allow_lossy` without `downgrade`, so no existing output changes.
3. **Downgrade on request.** `check_target(info, target, *, downgrade=False)` returns the target's header when `downgrade` is true and the source is newer; without it the refusal stays, its hint now "convert it with 'fenolite convert <project> --to kicad --kicad-version 9'". `write_board`, `mod.write_footprint`, `sym.write_symbol_library`, `sch.retarget_schematic` (new: a read sheet rebuilt for an older target), `pro.update_project` and `dru.write_rules` take `downgrade=False`. `build` never passes it: a layout saved by 10 is not silently rebuilt for 9 (`layout-lens`, "Refusals", unchanged).
4. **The direction.** c0159's KiCad to KiCad direction accepts an older target: it reads the project (board, root schematic and its sheets, the project-local footprint and symbol libraries named by the project's library tables, the project and rules files), writes each with `downgrade=True` for the target, and adds one report row per resolver id with the counts per action. `presentation` and `design` rows are losses (`report` and `refuse`); `rewrite` and `same` rows are `changed`. The verification compares the source and the reading of the written board at level 5 under the profile `kicad-downgrade` (frame `absolute`, tolerance 0: the same model in another header) and the written schematic at level 2 (c0158's schematic side).
5. **Capabilities.** `KicadBackend.capabilities().downgrade` is `"supported"`; `capabilities.conversions` gains `kicad` to `kicad` with `targets [9, 10]` and `downgrade: true`. The meaning of `FEN-7002` becomes "target format version older than the input, and no downgrade was asked".
6. **Benches.** Each resolver row of a board, footprint, schematic or symbol kind gets a bench: an authored minimal file holding the 10 construct (as the token fuzz authors its cases), saved by `kicad-cli` 10.0.6 (`pcb upgrade` or `sch upgrade`), downgraded by Fenolite, loaded by 9.0.9; the bench compares the DRC (or ERC) of 9.0.9 on the downgraded file with the DRC of 10.0.6 on the source, by violation type, and for `rewrite` and `same` rows also the model of 10.0.6's `pcb upgrade` of the downgraded file with the source at level 5. A row whose bench differs moves to `design` (more consent), never the reverse without a new bench.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/backends/kicad/data/downgrade.toml` (new) | the resolver table |
| `src/fenolite/backends/kicad/resolver.py` (new) | `Row`, `Action`, `load()`, `resolve(root, kind, target) -> Resolution(root, rows, counts)`, `EVIDENCE` |
| `src/fenolite/backends/kicad/versions.py` | `check_target(..., downgrade=False)`; the new hint |
| `src/fenolite/backends/kicad/pcb.py`, `mod.py`, `sym.py`, `sch.py`, `pro.py`, `dru.py` | `downgrade=False`; `sch.retarget_schematic` |
| `src/fenolite/backends/kicad/backend.py` | `downgrade == "supported"` |
| `src/fenolite/convert/to_kicad.py`, `data/profiles.toml` | the older-target branch; the profile `kicad-downgrade` |
| `tools/gen_token_docs.py`, `docs/formats/kicad/tokens.md` | a column `downgrade` with each row's action |
| `docs/formats/kicad/versions.md` | "Downgrade" replaces "Downgrade stays refused…" |
| `tests/unit/backends/kicad/test_downgrade_resolver.py` (new; `test_resolver.py` is the library resolver's) | closure of the table, edits at the node, the measured counts |
| `tests/kicad/downgrade/_downbench.py`, `test_rows.py`, `test_demos.py` (new) | `H-K-DOWN-ROWS`, `H-K-DOWN-DEMOS` |

## Sources registered by this change

None expected: the facts are those of the inventory (S-0030, S-0031, S-0033, S-0039, S-0024, S-0368) and the two pinned `kicad-cli` images (S-0020, S-0029). A row whose 9 form no registered source states takes the next free id of S-0740 to S-0759, or stays `design`.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-DOWN-ROWS | For each row of `downgrade.toml`, a bench holding the KiCad 10 construct, downgraded by Fenolite, loads in `kicad-cli` 9.0.9; its DRC or ERC by violation type equals 10.0.6's on the source; and for `rewrite` and `same` rows, 10.0.6's upgrade of the downgraded file equals the source at level 5 (S-0020, S-0029, S-0030, S-0031) | `tests/kicad/downgrade/test_rows.py` | probe `down-row-<id>` `equal` for every row; a row that differs is moved to `design` |
| H-K-DOWN-DEMOS | The KiCad 10.0.6 demo projects of format 10 (`CM5_MINIMA_3`, `pic_programmer`), converted for KiCad 9, load in 9.0.9 with their DRC and ERC by type equal to 10.0.6's on the source, apart from the `design` rows the report names, and `pcb upgrade` of the written board gives the source at level 5 (S-0058, S-0029) | `tests/kicad/downgrade/test_demos.py` | probe `down-demos` `equal` for both projects |

Both start `INFERRED`. Ids used without changing their level: `H-K-TOK-CONSTANTS`, `H-K-TOK-NETNAME`, `H-K-SCH-TOKENS`, `H-K-PCB-WRITE`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| the table is closed and loads | mechanical | `test_downgrade_resolver.py` |
| each row's action | `KICAD-VERIFIED (9.0.x, 10.0.x)` per row (`H-K-DOWN-ROWS`); a row without a passing bench is `design` | `test_rows.py` in both pinned images |
| edits at the node; no coarse drop | mechanical; the measured counts as a corpus test | `test_downgrade_resolver.py`, `tests/corpus/test_downgrade_census.py` |
| the demo projects | `KICAD-VERIFIED (9.0.x, 10.0.x)` (`H-K-DOWN-DEMOS`) | `test_demos.py` |
| the refusal without `downgrade` | mechanical | the existing refusal tests, unchanged but for the hint |

## Risks / Trade-offs

- **A `same` row hides a real loss** if the default is not 9's behaviour. The bench compares DRC, ERC and the model after an upgrade; a doubt makes the row `design`.
- **The benches are many** (about 60 rows). They are generated from the table, one minimal file per row, as the token fuzz is; one run per major.
- **9.0.9 is the only 9 checked.** Every row names 9.0.9; another 9.0.x release is assumed to read the same format (the format version is the same).
- **Schematic re-target is new code** (today a read sheet is rebuilt only at its version). Its tests are RT1 at the target: the re-targeted sheet, read back, holds the model of the source minus the reported rows.

## Migration Plan

- No output changes without `downgrade=True`; the only visible change of an existing path is the hint of `FEN-7002`.
- `capabilities` reports `downgrade: "supported"` for the KiCad backend.

## Budget (8.5 days)

| part | days |
|---|---|
| entry check, measurements as tests, the default values of the via-protection rows and the 9 via form on 9.0.9 | 1.0 |
| the table, its closure, the token-doc column | 1.0 |
| the resolver: edits at the node for boards and footprints | 1.25 |
| schematics and symbol libraries: re-target and resolver | 1.5 |
| project and rules files | 0.5 |
| the direction in `convert`, the profile, the report rows | 0.75 |
| benches and the row probes on both majors | 1.5 |
| demo projects, documentation, closing | 1.0 |
| **total** | **8.5** |

Cut order: (1) schematics and symbol libraries (the board, footprints, project and rules downgrade; a schematic of major 10 is then a `design` loss "schematic not converted", and the user re-saves it); (2) the `rewrite` rows beyond `tenting`, `island`, `power` and `net-by-name` (moved to `design`). Not cut: the table and its closure, the edits at the node, the benches of the rows kept.

## Open questions

All answered on 2026-10-09: the maintainer accepted every recommended answer (`docs/roadmap.md`, Open decisions row 40).

1. **Is a downgrade only a `convert` (never `build --kicad-version 9` on a project saved by 10)?** Recommended: yes; `build` keeps the refusal and its hint names `convert`. A build that silently drops a 10 construct of the user's layout is the failure the refusal exists for. Decided by the maintainer on 2026-10-09: yes; a downgrade is only a `convert`, and `build` keeps the refusal with a hint that names `convert`.
2. **Are dropped via-protection values (covering, plugging, capping, filling) `design`?** Recommended: yes unless the value is the default; they reach the fabrication outputs. Decided by the maintainer on 2026-10-09: yes, unless the value is the default.
3. **Is a dropped position-file flag (`in_pos_files no`) `design`?** Recommended: yes; the placement file changes. Decided by the maintainer on 2026-10-09: yes; the placement file changes.
4. **The follow-up for `RoyalBlue54L-Feather` (opaque `(net N)` that names no net of the design, refused at its own target)?** Recommended: a correction change of its own in v0.5a, after this one, with the census of the corpus boards that hold such a reference. Decided by the maintainer on 2026-10-09: a correction change of its own in v0.5a, after this one, with the census of the corpus boards that hold such a reference: c0163.
