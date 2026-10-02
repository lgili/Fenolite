## Context

- **What exists.** c0009 (`read_board`, the `KicadCli` runner) and c0017 (`write_board`, `embed.place_footprint`, `embed.placement_uuid`, the DRC reader, the probe module) are archived. In the canonical order, c0018, c0010, c0026, c0011, c0027 and c0013 are implemented and archived before this change, and c0020, c0021 and c0012 after it; the committed proposals of the earlier changes are the contract for the names used here. c0011 builds a model `N` from `design.py` and writes the triad with c0010's `write_triad(N, existing_project=None)`; every footprint carries a hidden `fenolite.path` property while `H-K-BUILD-PATHPROP` holds. c0027 then appends the script's user properties after that property with `embed.with_property`, vendors the footprints of every row origin, and MODIFIES four of the six c0011 requirements that this change modifies, so those copies start from c0027's text (Migration Plan). Its Open Questions hand over whether a kept footprint takes the script's user properties (Decision 22).
- **What c0011 leaves to this change.** c0011 refuses every output changed since the last build (`build.layout-exists`, FEN-7001), and its Decision 20 says that c0019 replaces this path with preservation. It gives c0019 the `moved()` call, the secondary key `fenolite.path` (uuid only if its probe refutes the property), the comparison of a built model with its board by keys for components, positions and properties (c0011 and c0013 Open Questions), and pruning of stale vendored files ("c0019 may prune"). c0010 lists "merging over an existing layout (c0019)" as a non-goal. c0018 hands over "c0019 merges user rules after Fenolite's with `parse_rules` and `print_rules`"; its `lower_rules` refuses rule sets with KiCad slots. c0012, which follows this change and c0020, says that c0019 merges `.kicad_pro` through `update_project`; c0012's `apply_sheet_keys` then runs after that merge, inside `write_triad`. c0013 leaves "board versus `.fenolite/`" to c0019, and its `check` validates the `.fenolite/` model of a built project (Decision 21).
- **Plan item 0011, part 2 (the project plan).** A rebuild over an existing board re-reads it and copies verbatim the tracks, vias, zones with fills and graphics whose nets still exist; it keeps position, rotation and side of footprints whose uuid or path did not change; a removed footprint raises `layout.orphan`; `--discard-layout` regenerates; the precedence is `locked > existing board > place() > placer`; a fill is kept while the zone's outline, net, layer and rules are unchanged, else `zone.fill-stale`. `moved(old, new)` is in the v0.1 DSL, while `lens/moved.py` stays v0.2b. c0011's Decision 1 answers c0005's open question: `lens` imports only `model` and `backends`, never `geometry`, so fill staleness must be a text digest.
- **KiCad facts.**
  - `kicad-cli pcb upgrade --force` re-saves a board in place (S-0022); 9.0 has no `pcb upgrade` (S-0037).
  - A 10.0.6 re-save keeps the uuid of every item it keeps, removes teardrop zones and a footprint's `Footprint` property, and replaces `fp_text` items by properties with new uuids (`H-K-UUID-KEEP-2`, `KICAD-VERIFIED (10.0.x)`). A Fenolite-written triad and its re-saved copy hold the same 75 uuids (its Fenolite-written half, 2026-10-02).
  - When two custom rules govern the same item, the later one wins (`H-K-DRU-ORDER`, c0018). Any rules error disables every custom rule with exit 0 (`H-K-TOK-RULES-SILENT`), and 9.0.9 drops the file for one 10.0-only construct (`H-K-TOK-RULES-DRIFT`).
- **Writer facts (living specs).** c0017's `write_board` rebuilds a read entity from its own slots and inserts a created entity in `pcb.CANONICAL_ORDER` ("Slot source for model entities"). Slots are filled by position: the k-th `Modeled` slot of a field emits the k-th item, so a removed footprint leaves its neighbours in place ("Order-preserving rebuild"). A read board of major 10 cannot be written for target 9 (`DowngradeRefusedError`, FEN-7002), and a KiCad 8 board cannot be edited (FEN-7003). "Projected fields on write" lets the writer rewrite the Reference and Value atoms (c0012, after this change, adds paper and title block); any other projected property change is refused. An opaque net reference that cannot be resolved is refused (`kicad.board.opaque-net-ref`).
- **Model facts.** The living `design-model` "Layout authority" makes the KiCad project the source of truth for layout and `.fenolite/` a regenerable cache, with the scenario "Cache is regenerable": deleting `.fenolite/` and rebuilding gives identical bytes.
- **Environment.** KiCad 10.0.6 is installed locally. The `kicad-10` job (10.0.6) and the `kicad-9` job (9.0.9) run `tests/kicad`; the `kicad-9` job has no corpus, so every proof uses the CC0 blink of c0011.
- **Working tree on 2026-10-02.** Another agent is implementing c0018: `backends/kicad/rulemap.py` exists, `dru.py` and `lowering.py` do not yet. c0010–c0013 are not started. Divergences found at implementation time are recorded by task 1.1.
- **Constraints.** Stdlib only. No model entity, field, schema, id prefix, FEN code, `kicad-file-backend` writer change or `package-layering` change. Budget 8.25 working days (roadmap: 5).

## Goals / Non-Goals

**Goals:**
- A rebuild keeps what the user did in KiCad: footprint placement and the footprint nodes themselves, routing, zones, fills while valid, board-only footprints, board settings, project keys and custom rules.
- One fixed precedence between the board, the script and Fenolite's own staging, with every override reported as an issue.
- Two rebuilds over a routed board, and a rebuild after deleting `.fenolite/`, give byte-identical files.
- `moved(old, new)` keeps the layout of a renamed part.
- Proof by `kicad-cli` 10.0.6 and 9.0.9 that a footprint moved outside Fenolite survives a rebuild with its tracks intact.

**Non-Goals:**
- Everything listed under Non-goals in the proposal.
- Judging whether the user's own fills were current (c0015's `fill` and `check` do that).
- Net renames (a net alias), module-prefix aliases, and a three-way merge with a stored base (v0.2b sync).
- Rewriting the `fenolite.path` atom of a kept footprint: an alias re-places the footprint, so its uuid follows the new path (Decision 7).

## Decisions

1. **The lens is one module; no layering change.** `lens/preserve.py` holds matching, precedence, merging, digests and the rules merge. It imports `core`, `model` and `backends` (`backends.kicad.{pcb,embed,pro,dru,versions}`), never `geometry`, `dsl` or `lens.build`. `lens/build.py` imports it; `cli/cmd_build.py` calls `read_existing` and `prepare`.
   - Positions are compared as integers and fill staleness is a digest of text, as c0011's Decision 1 settled for `lens`.
   - Rejected: the logic in `cmd_build` (the CLI would own model rules, and pure functions are easier to test). Rejected: a new package (not in the layering table).

2. **The existing triad is read once, by the command.** `read_existing(out_dir, name)` returns the texts of `<name>.kicad_pcb`, `.kicad_pro` and `.kicad_dru`, each `None` when absent. `prepare` reads the board with `read_board(text, file="<name>.kicad_pcb")`.
   - The relative file name goes to provenance in both paths (Decision 14), so `.fenolite/` holds no absolute path and stays byte-identical.
   - Reader warnings are reported; reader infos (such as `kicad.board.kept-opaque`) are counted in `result.preserved.reader_infos`, because a KiCad-saved board can give many and `inspect` shows them.
   - Every refusal (unparsable board, future or unknown versions, KiCad 8, a major-10 board for target 9, a rules parse error) happens before the plan is returned, so `--dry-run` refuses too. `--discard-layout` reads nothing.
   - Rejected: file reads inside `build_design`, which c0011 keeps free of project I/O. Rejected: the absolute board path in provenance (residue `abs-user-path`, and outputs would depend on the folder).

3. **Two-way merge: the board is the layout authority.** Preservation compares only the existing board with the new build; it has no stored base.
   - `.fenolite/` is a regenerable cache ("Layout authority") and is not committed, so it is missing after a clone. A base taken from it would make the same sources and the same board give different results with and without the cache.
   - Rejected: a three-way merge with `.fenolite/board.json` as base (DSL moves would apply on untouched boards, but the cache would carry authority). Rejected: gating DSL moves on c0011's build record (the same objection).

4. **Matching keys and their order.** For each component path `p` of the model (its `properties["fenolite.path"]`):
   1. uuid: the footprint whose uuid is `footprint_uuid(p)` = `embed.placement_uuid(p, "/footprint")`, which a re-save keeps (`H-K-UUID-KEEP-2`);
   2. path: the first footprint, in board order, whose `fenolite.path` property is `p` (`H-K-BUILD-PATHPROP`), for footprints whose uuid changed;
   3. alias: for `moves[p] = old`, the footprint of `old` by uuid, then by property.
   - Each key runs over every unmatched component, in path order, before the next key; a footprint is matched once. A copy of a footprint made in KiCad carries the same property and a new uuid: the original wins by uuid, and the copy is an orphan.
   - If c0011's probe refuted `H-K-BUILD-PATHPROP` (no property is written), the path key and the property half of the alias key are skipped, and Decision 8 keeps every unmatched footprint (Open Questions). If c0011 applies its cut 4 instead, this change takes over the property and its probes (Open Questions).
   - Rejected: references as a key (KiCad re-annotation changes them; equal refs may exist in two modules). Rejected: uuid only (a footprint re-created in KiCad would lose its layout). Rejected: positions (a moved footprint is the case to handle).

5. **Placement precedence, and what "locked" means.** `effective_placements` applies, per part: a locked `place()`, then the existing board, then `place()`, then staging (c0011's row; c0022's placer later).
   - "Locked" is `place(…, locked=True)` in the script. Read as the board's lock flag, "locked > existing board" would be redundant, because a locked footprint is part of the existing board. Read as the script's lock, it gives an agent, which cannot move parts in KiCad, a way to force a position.
   - An unlocked `place()` that the board overrides gives `layout.place-overridden` (info, it repeats on every build) with the hint "lock the placement in the script, move the footprint in KiCad, or re-run with --discard-layout". A locked `place()` that moves a footprint gives `layout.place-forced` (warning), because the footprint is re-placed (Decision 7).
   - Rejected: DSL moves always win (GUI placement lost on every build). Rejected: the board's lock flag as "locked" (redundant, see above). Rejected: a warning for `place-overridden` (noise in steady state).

6. **Off-board parts count as unplaced.** A matched footprint whose position lies outside the box of the design's outline points counts as unplaced: it takes its `place()`, or is staged again by the build. The rule applies only when the board's edge content is that outline or absent, so the outline is known exactly.
   - c0011 stages unplaced parts beside the outline. Without this rule, a staged part would keep its slot forever, a later `place()` would lose to "existing board", and a new staged part would land on a kept one, because the row restarts at the same place.
   - A part that the user placed inside an outline enlarged in KiCad is never moved, because the rule is off for an unknown outline (`layout.outline-kept`).
   - Rejected: a `fenolite.staged` property (stale once a user moves the part). Rejected: the box of the board's own edge graphics (arcs and circles need geometry).

7. **Kept or re-placed.** A matched footprint is kept when its key is `uuid` or `path`, its `lib_ref` equals the built component's `lib_footprint_ref`, and c0011's built copy sits at the footprint's position, rotation, side and lock. Otherwise the built copy replaces it.
   - A kept footprint keeps its whole node: silkscreen positions, properties and pads as edited in KiCad, the most common GUI work after placement. Its pads take the nets of the built copy's pads by number. Its component takes the projected `properties` of the kept node, so c0017's projection check passes; the script's `ref` and `value` are written into the Reference and Value atoms by c0017's writer, because the script owns the circuit, and its user properties are the script's (Decision 22).
   - The built copy is c0011's placed copy at the effective placement, keyed by the component path, so no placement code is duplicated: `prepare` hands the board's placement to `build_design` as the part's placement (Decision 5), and a re-placed footprint lands where the board had it.
   - Re-placement happens for an alias (the uuid then follows the new path, so the alias can be removed after one build), a changed lib id (`layout.footprint-replaced`), a locked override (`layout.place-forced`) and an off-board part that its `place()` or the staging row moves to another position.
   - Rejected: re-placing every matched footprint (silkscreen and property edits lost). Rejected: moving the board's node by changing its `at` (child texts store absolute angles, so a rotation would leave them wrong, and only `embed.place_footprint` mirrors a side change). Rejected: rewriting `fenolite.path` in place for an alias (the footprint's uuid would keep naming the old path, so the alias could never be removed).

8. **Orphans go, board-only footprints stay.** An unmatched footprint that carries `fenolite.path` was built by Fenolite for a part the script no longer has: it is removed, with `layout.orphan` (warning) naming its reference, path, uuid and position. An unmatched footprint without the property was added in KiCad (a mounting hole, a logo, a fiducial): it is kept with the component that `read_board` gives it (`kicad` keys, which never collide with `dsl` keys), its pads take the design's nets by name, its pins join those nets (Decision 21), and `layout.board-only` (info) names it.
   - The `.bak` of the mutation protocol keeps the previous board.
   - Rejected: removing every unmatched footprint (GUI-only footprints destroyed). Rejected: refusing the build on orphans (the only way out would be `--discard-layout`, which loses the routing). Rejected: keeping orphans (a removed part would stay on the board).

9. **Copper items follow their nets.** Tracks, arcs, vias and zones with no net, or with a net name the design still has, are kept with all their slots and take the design's net of that name. The others are dropped, with one `layout.net-removed` (warning) per net giving the counts.
   - A renamed net therefore loses its routing; a net alias is v0.2b.
   - Opaque content that names a removed net, such as a teardrop zone or a net inside an opaque child, makes c0017's writer refuse with `kicad.board.opaque-net-ref` (exit 7, located). `docs/lens.md` says to delete it in KiCad or to use `--discard-layout`.
   - Rejected: keeping the items without a net (floating copper the user did not ask for).

10. **Board content outside the design is kept.** The layout's `Board` is the existing board with its root slots, so setup, stack-up, plot settings, groups, dimensions, images, title block and paper survive; c0012, which comes after this change, reads title block and paper from the board.
    - Edge graphics are kept as they are; the script's outline is used only when the board has none. When they differ from the script's rectangle, `layout.outline-kept` (warning) says so; a new size needs KiCad or `--discard-layout`.
    - A different copper layer set is `layout.copper-mismatch` (error): preserving a board on another stack-up is not defined.
    - Rejected: the script's outline always wins (outline work done in KiCad lost). Rejected: a Fenolite-owned outline recognised by uuid (a resize in KiCad keeps the uuids, so the user's resize would be overwritten). Rejected: rebuilding the layer table from the script (stack-up work lost).

11. **Fill staleness: two text digests.** A kept zone keeps its fills when `zone_digest` of the zone and `fill_inputs_digest` of the board are both equal for the existing board (with the existing project and rules texts) and for the layout (with the texts this build writes); otherwise its fills are dropped with `zone.fill-stale`.
    - `zone_digest` covers the roadmap's list: outline points or opaque polygon text, net name, layers, priority and the opaque fill-settings text.
    - `fill_inputs_digest` adds what a rebuild can change around the zone: footprints and their pads, tracks, arcs, vias, other zones, rule areas, edge graphics and outline, the net classes that `pro.read_project` reads from the project text, and the rule items of the rules text. Nets enter by name; ids, uuids, provenance and slots never do.
    - The project plan asks that "outline, net, layer and rules" be unchanged; a zone-only digest would keep a fill under a pad that the rebuild moved or added, which KiCad's DRC then reports. The digests are symmetric and need no record. A fill that was already stale in the user's board stays as it was: judging KiCad's own fills is c0015's work.
    - `H-K-LENS-FILL` states the premise, that a fill depends only on these inputs; c0015 settles it by refilling a rebuilt board on 10.0.6.
    - Rejected: the zone-only digest (it is cut 2). Rejected: digests recorded in `.fenolite/` (cache-dependent, and fills made in KiCad have no record). Rejected: refilling here (c0015 needs `kicad-cli` 10).

12. **The project is merged by c0010.** `build_design` passes the existing project text to `write_triad(…, existing_project=…)`. c0010's `update_project` keeps every key Fenolite does not own, never deletes a class and regenerates the patterns of the model's nets. c0012, which follows this change and c0020, adds its `apply_sheet_keys` after it. A class defined in the script overrides values given to it in KiCad, because the script owns its classes.
    - Rejected: synthesising a new project (KiCad settings lost). Rejected: a second merge in `lens` (c0010 already owns the rules for project keys).

13. **User rules stay after Fenolite's.** `merge_rules(lowered, existing, *, target, file, allow_lossy, issues)` takes the items of `parse_rules(lowered)`, then every item of `parse_rules(existing)` except its version item and the rules named `fenolite_*` (c0018's lowered names), prints them with `print_rules`, and passes the text through `write_rules(read_rules(text), target=…)`.
    - The later rule wins (`H-K-DRU-ORDER`), so a user rule overrides a Fenolite rule on the same items.
    - `write_rules` applies c0018's target gating and self-check to user rules: a 10.0-only construct is refused for target 9 (`RulesLossError`, FEN-7001) or dropped with `--allow-lossy`, instead of making KiCad 9 drop every rule silently (`H-K-TOK-RULES-DRIFT`). Comments and opaque rules stay verbatim; a rule that c0018 lifts into the model is written in Fenolite's spelling (`8mil` becomes `0.2032mm`), and is stable from then on.
    - An existing file of version 2 or more is refused (FEN-3002); one that does not parse is refused with its line (FEN-3004).
    - Rejected: `print_rules` alone (no gating). Rejected: editing a `RuleSet`'s slots (c0018's `lower_rules` refuses rule sets with slots by design). Rejected: splitting by anything other than c0018's name prefix.

14. **Preservation is the build's normal form.** `BuildOutput.layout` and `.fenolite/` are always `merge_layout` of the built model with `read_board` of the board text the build writes, whatever the path:
    - fresh build: the board text is c0011's `write_triad(N)`, unchanged;
    - rebuild: the board text is `write_board` of the merged layout.
    - So a rebuild over the build's own output reads the same text, merges to the same layout and writes the same bytes, `.fenolite/` included; deleting `.fenolite/` and rebuilding restores it ("Layout authority"). The first rebuild over a board saved by KiCad rewrites it in Fenolite's form, and the next one changes nothing.
    - Provenance in `.fenolite/` holds the SHA-256 of the written board, never of the input, which is why the cache is merged with the written text and not with the input board.
    - The cost is one extra `read_board` and merge per build.
    - Rejected: dumping `N` on fresh builds and the merge on rebuilds (the first rebuild would change `.fenolite/`, and "Cache is regenerable" would fail). Rejected: merging the cache with the input board (a second rebuild over a KiCad-saved board would change `.fenolite/`). Rejected: an identity-preserving merge that swaps in `N`'s entities when equal (fragile).

15. **`BuildOutput.design` keeps c0011's meaning.** `design` stays the model built from the script at the given placements; `layout` is new. c0011's tests on `design` (placed-copy ids, layers keyed `dsl`, the outline entity) keep their meaning.
    - c0011's readback test keeps comparing `design` with fresh builds, where `design` and the written board agree; `test_preserve_readback.py` compares `layout` with rebuilt boards, where kept footprints come from the board.
    - Rejected: replacing `design` with the layout (c0011's "Placement of built parts" and "Identifier derivation" scenarios would change meaning).

16. **The refusal is narrowed, not removed.** c0011's `check_existing` still guards `fp-lib-table` and the vendored footprints under `lib/`, which have no merge: an edited file there is refused with `build.layout-exists` unless `--discard-layout`. The board, project and rules files are merged instead. `--discard-layout` means a fresh build.
    - Rejected: dropping the refusal (edits to vendored footprints silently overwritten). Rejected: merging `fp-lib-table` rows (no v0.1 consumer).

17. **Aliases in the DSL.** `Design.moved(old, new)` records an alias and `dsl.moves(design)` returns them, new path to old path. Malformed paths, `old == new` and repeated paths raise `DslError` at the call; a `new` that is not an added part, or an `old` that still is one, raise it in `moves`, which also refuses chains.
    - Aliases are not model data: `to_model` and every id are unchanged.
    - Component paths only; module-prefix aliases and `lens/moved.py` are v0.2b.
    - Rejected: a free `moved()` object added with `add()` (a second kind of member for one mapping). Rejected: aliases in the model (no entity exists for them, and schemas would change).

18. **One closed table of codes.** `PRESERVE_ISSUE_CODES` lives in `preserve.py`, and c0011's `BUILD_ISSUE_CODES` includes it (MODIFIED "Build issue codes"), so the build keeps one closed set.

    | code | severity | why this severity |
    |---|---|---|
    | `layout.copper-mismatch` | error | the board cannot be preserved on another stack-up |
    | `layout.orphan` | warning | the design asked for the removal, but a placed footprint is lost |
    | `layout.alias-unused` | warning | a likely typo in `moved()` |
    | `layout.place-forced` | warning | the footprint's edits in KiCad are lost |
    | `layout.footprint-replaced` | warning | the footprint's edits in KiCad are lost |
    | `layout.net-removed` | warning | routing is lost |
    | `layout.outline-kept` | warning | the script's `board()` size has no effect |
    | `zone.fill-stale` | warning | the zone needs `fill` again |
    | `layout.place-overridden` | info | the documented precedence, repeated on every build |
    | `layout.alias-used` | info | confirms a rename |
    | `layout.board-only` | info | a footprint the script does not know, kept |

    - `zone.*` is shared with c0015's `zone.unfilled`; `layout.*` with c0011's `layout.unplaced`.

19. **Evidence is honest.** `preserve.EVIDENCE` is `INFERRED` (`H-K-LENS-KEEP`, `H-K-LENS-FILL`, `H-K-UUID-KEEP-2`, `H-K-BUILD-PATHPROP`) and joins the envelope, with `pcb.EVIDENCE`, only when an existing board was read; `dru.EVIDENCE` joins when an existing rules text was merged. `H-K-LENS-KEEP` becomes `KICAD-VERIFIED` for the edited blink only.
    - Rejected: `KICAD-VERIFIED` for arbitrary rebuilds (other boards reach forms the oracle has not run).

20. **Oracle: a token-edit proxy, re-saved on 10.0.6, probes first.** `tests/_layout_edit.py::edit_blink` moves `D1` 4 mm to the right, then routes `LED_A` from `R1` pad 2 by one `F.Cu` segment to a via and one `B.Cu` segment to `D1` pad 2, with fixed uuids. On 10.0.6 the edited target-10 board is re-saved with `pcb upgrade --force`, the stand-in for a GUI save; 9.0 has no re-save, so target-9 cases rebuild the edited text.
    - Survival is judged by `pcb export pos`, by the identity of the edited items, and by an unchanged DRC report: the same (type, severity) multiset and the same `unconnected_items` count before and after the rebuild. A clean report is not required, because the hand-made route may carry violations of its own; they must not change.
    - `lens-resave-t10` and `lens-rewrite-t9`/`-t10` run first, before the lens code, with stop rules (the kicad-oracle requirement); `lens-keep-t9`/`-t10` record the result.
    - A target-9 board re-saved by 10.0.6 is of major 10, so a target-9 rebuild is refused (FEN-7002, c0017); the oracle checks this refusal and the target-10 rebuild.
    - Rejected: the DRC exit code as a verdict. Rejected: requiring a clean DRC (see above). Rejected: GUI automation (no headless GUI; the maintainer's GUI move is supporting data, Open Questions).

21. **Board-only components stay in the cache, with their pins on their nets, and `check` asks them for no symbol.** A board-only footprint keeps the component that `read_board` synthesises from it: pins from its pad numbers, the board's properties, an empty `lib_symbol_ref` and no `fenolite.path`. That component reaches `.fenolite/`, because the cache is the layout (Decision 14).
    - `merge_layout` makes each of its pins a member of the design's net that a pad of its number takes. The layout's circuit and the written board then agree on every pad. c0020's `model_netlist` gives a pin that no net lists `NO_NET`, so a pin left out would give `netlist.assignment-differs` against its pad on `GND`, and c0013's `erc.lite.floating-pin` would warn. A numbered pad on no net still gives that warning, as for any unconnected pin; it does not fail `check`.
    - c0013's "Model validation stage" asks every component of built input for a symbol (`check.symbol-unresolved`, error), so a kept mounting hole would make `fenolite check` exit 5. This change MODIFIES that requirement: a component whose `properties` hold no `fenolite.path` key is board-only and is asked for no symbol. The key is the one that tells orphans from board-only footprints (Decision 8), so the lens and `check` share one definition. `checks` may not import `backends.kicad` (`package-layering`), so `checks/validate.py` spells the key as a literal, and a unit test pins it to `embed.PATH_PROPERTY`.
    - No script part loses the check: every built component carries the key while `H-K-BUILD-PATHPROP` holds, and c0011 resolves every `lib_symbol_ref` or fails the build (`FEN-3001`), so a script part never lacks a symbol anyway (Open Questions for the refuted row).
    - c0020's netlist compare needs no change of its text: its (`model`, `board`) pair reads net members, which now hold these pins.
    - c0013 archives before this change (the canonical order), so the delta copies c0013's ADDED text in full and edits only the symbol rule and its scenarios (Migration Plan).
    - Rejected: leaving board-only components out of the cached circuit. `Design.validate()` reports `model.unknown-component` (error) for a footprint whose component id names no component, so the footprints would need their component ids cleared; `.fenolite/` would then differ from the model of the written board (Decision 14, and c0011's "Built project files" dumps `BuildOutput.layout`); c0020 would report their pads as `netlist.uncovered` (`not-in-model`); and later readers of `.fenolite/`, such as exports, would miss parts placed in KiCad. Rejected: KiCad's `board_only` footprint attribute as the marker (a footprint added in KiCad may lack it, and setting it would change a footprint kept verbatim). Rejected: the provenance or the id backend as the marker (implicit; no model rule names them). Rejected: dropping the symbol check on built input (c0013's rule stays for script parts).

22. **The script owns user properties, also on kept footprints.** c0027 writes a part's user properties (a part number, a supplier code) as hidden properties after `fenolite.path`; its Open Questions leave kept footprints to this change. `merge_layout` treats the property slots that the built copy holds after its `fenolite.path` slot as the script's:
    - a kept node's property of the same name (after `str.casefold()`, as c0027 compares names) takes the script's name and value and keeps every other child: its uuid, its position and its visibility as edited in KiCad;
    - a missing one is appended after the node's last property, as the built copy has it, with the uuid `embed.placement_uuid(<path>, "/footprint/property:<name>")`. An index-derived uuid could repeat that of a stale property left by an earlier build, and a name-derived one stays stable on later rebuilds;
    - properties that the script does not name stay, including one that it no longer names: it cannot be told from one added in KiCad. `--discard-layout` or a re-placement removes it.
    - Property nodes are opaque slots, so the lens edits the slot and sets the component's `properties` to the projection of the edited node; "Projected fields on write" passes unchanged, and no writer delta is needed. An unedited board gives the same bytes, so the normal form holds (Decision 14). c0030 later reads placed properties as fields whose text stays in the component; the rule then reads the same: the value is the script's, placement and appearance are the board's.
    - Fields (Reference, Value), positions and every other board edit stay as Decisions 5 and 7 say; field placement is c0030's.
    - Rejected: the board wins (c0027's question). A part number changed in the script would never reach a footprint kept from the board, so the board, the BOM and the script would disagree until `--discard-layout`, which loses the layout. Rejected: replacing the whole property node from the built copy (a property shown or moved in KiCad would be reset on every build). Rejected: re-placing a footprint whose user properties changed (every KiCad edit of the footprint lost for a BOM change). Rejected: removing every property that the script does not name (properties added in KiCad would be lost).

23. **Extension points instead of exhaustive texts.** c0028 (copper intents, script copper in a merge), c0029 (the copper guard of `build`), c0030 (field placements) and c0031 (zones) extend the build and the merge through ADDED requirements. So the texts that this change owns say where they may be extended:
    - "DSL package", "Built project files", "Build command" and "Build evidence" (MODIFIED here) each gain one sentence: later requirements MAY add modules and re-exported names, keyword-only arguments with defaults and steps, `build` options, steps of `cmd_build` and `result` keys, or evidence that joins only when used, and each names the requirement it extends;
    - "Build issue codes" (MODIFIED here) lets every `kicad.*` code through, so the codes of c0028 (`kicad.copper.*`, `kicad.frame.*`) and c0031 (`kicad.zone.*`) pass, and gains one sentence: later requirements MAY add codes that join the `build` envelope unchanged, such as the `copper.*` codes of c0029's guard, and each names this requirement. "Layout issue codes" lets every `kicad.*` code through in the same way, the backend merges' codes included.
    - "Kept and re-placed footprints" lets later requirements change named slots, such as fields (c0030), "Copper items follow their nets" lets them take named items out of its rule, such as script copper (c0028) and script zones (c0031), and "Layout preservation evidence" lets them add `result.preserved` keys (c0030's `fields`); each names the requirement and what it adds or takes.
    - Rejected: MODIFIED chains through every later change. Each would copy these long texts again, after c0021's MODIFIED "Build command", and every edit here would ripple through four changes.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/lens/preserve.py` (new) | `@dataclass(frozen=True, slots=True) class ExistingProject(board: str \| None = None, project: str \| None = None, rules: str \| None = None)`; `read_existing(out_dir: Path, name: str) -> ExistingProject`; `footprint_uuid(path: str) -> str`; `class PlacementLike(Protocol)` (`at: Point`, `rotation: Udeg`, `side: Side`, `locked: bool`; the structural twin of c0011's `PlacementRequest`); `@dataclass(frozen=True, slots=True) class KeptPlacement(at: Point, rotation: Udeg, side: Side, locked: bool)`; `@dataclass(frozen=True) class FootprintMatch(path: str, footprint: FootprintInstance, key: Literal["uuid", "path", "alias"])`; `@dataclass(frozen=True) class LayoutMatch(matches: Mapping[str, FootprintMatch], orphans: tuple[FootprintInstance, ...], board_only: tuple[FootprintInstance, ...], unused_aliases: tuple[tuple[str, str], ...])`; `match_footprints(design: Design, board: Design, *, moves: Mapping[str, str] = {}) -> LayoutMatch`; `effective_placements(placements: Mapping[str, PlacementLike], match: LayoutMatch, *, design: Design, board: Design) -> tuple[Mapping[str, PlacementLike], tuple[Issue, ...]]`; `@dataclass(frozen=True) class Prepared(existing: ExistingProject, board: Design \| None, match: LayoutMatch \| None, placements: Mapping[str, PlacementLike], issues: tuple[Issue, ...], reader_infos: int)`; `prepare(design: Design, placements: Mapping[str, PlacementLike], existing: ExistingProject, *, name: str, moves: Mapping[str, str] = {}) -> Prepared`; `@dataclass(frozen=True) class Merged(design: Design, issues: tuple[Issue, ...], summary: Mapping[str, object])`; `merge_layout(built: Design, board: Design, match: LayoutMatch) -> Merged`; `zone_digest(design: Design, zone: Zone) -> str`; `fill_inputs_digest(design: Design, *, project: str \| None, rules: str \| None) -> str`; `drop_stale_fills(board: Design, layout: Design, *, existing: ExistingProject, project: str, rules: str) -> tuple[Design, tuple[Issue, ...]]`; `merge_rules(lowered: str, existing: str, *, target: int, file: str = "", allow_lossy: bool = False, issues: list[Issue] \| None = None) -> str`; `PRESERVE_ISSUE_CODES: Mapping[str, Severity]`; `EVIDENCE: Evidence` |
| `src/fenolite/lens/build.py` (c0011; extended) | `build_design(…, prepared: Prepared \| None = None) -> BuildOutput`; `BuildOutput.layout: Design \| None`; `BUILD_ISSUE_CODES` includes `PRESERVE_ISSUE_CODES`; `summary["preserved"]` with the keys of "Layout preservation evidence" |
| `src/fenolite/cli/cmd_build.py` (c0011; extended) | `read_existing` and `prepare` unless `--discard-layout`; `check_existing` without the triad files; `result.preserved`; a `DslError` from `moves` becomes `DesignScriptError` |
| `src/fenolite/dsl/design.py` (c0011; extended) | `Design.moved(old: str, new: str) -> None` |
| `src/fenolite/dsl/convert.py` (c0011; extended) | `moves(design: Design) -> Mapping[str, str]` |
| `src/fenolite/dsl/__init__.py` (c0011; extended) | re-exports `moves` |
| `docs/lens.md` (new) | keys, `moved()`, precedence and the off-board rule, kept, re-placed and dropped items, board-only footprints, outline rule, digests, project and rules merge, normal form, `--discard-layout`, codes, evidence |
| `src/fenolite/checks/validate.py` (c0013; extended) | `validate_stage` reports `check.symbol-unresolved` on built input only for components whose `properties` hold the key `fenolite.path`, written as a literal (Decision 21); signature unchanged |
| `tests/unit/checks/test_validate_stage.py` (c0013; extended) | the MODIFIED scenario "Unresolved footprint and symbol", the board-only case, and the literal key equal to `embed.PATH_PROPERTY` |
| `docs/dsl.md`, `docs/cli-contract.md` (c0011's and c0013's pages) | `Design.moved` and `moves`; `result.preserved`; the narrowed `build.layout-exists`; board-only components exempt from `check.symbol-unresolved` |
| `docs/formats/kicad/board.md` | fact rows: a re-saved moved footprint keeps its uuid and `fenolite.path`; Fenolite's rewrite of an edited board keeps its DRC report (`H-K-LENS-KEEP`) |
| `docs/hypotheses.md`, `LEGAL-ANNEX.md`, `src/fenolite/backends/kicad/PROVENANCE.md` | rows of this change; session row; one `oracle` row for `pcb upgrade --force`, `pcb export pos` and `pcb drc` on rebuilt boards (S-0022, S-0037) |
| `docs/evidence/kicad/probes/9.0.9.json`, `10.0.6.json` | `lens-*` outcomes |
| `tests/_layout_edit.py` (new) | `move_footprint(text: str, ref: str, dx: Nm, dy: Nm) -> str`; `add_items(text: str, *items: str) -> str`; `edit_blink(text: str) -> str`; `EDIT_UUIDS: tuple[str, str, str]` (the two segments and the via); `add_filled_zone(text: str, *, net: str, layer: str) -> str` |
| `tests/unit/test_layout_edit.py` (new) | hermetic tests of the helper |
| `tests/unit/dsl/test_moved.py` (new) | aliases |
| `tests/unit/lens/test_preserve_match.py`, `test_preserve_place.py`, `test_preserve_footprints.py`, `test_preserve_copper.py`, `test_preserve_board.py`, `test_preserve_fills.py`, `test_preserve_rules.py`, `test_preserve_issues.py`, `test_preserve_determinism.py`, `test_preserve_readback.py`, `test_build_preserve.py` (new) | hermetic preservation tests |
| `tests/unit/cli/test_build_preserve_command.py` (new) | command flow, narrowed refusal, `result.preserved`, `fenolite check` of a rebuilt board with a board-only footprint |
| `tests/kicad/lens/test_lens_probes.py`, `test_preserve_oracle.py` (new); `tests/kicad/_probes.py` (c0017; extended) | `needs_kicad`, major-aware; `lens-*` probe entries |

Layering: `lens.preserve` imports `core`, `model` and `backends.kicad.{pcb,embed,pro,dru,versions}`; `lens.build` imports `lens.preserve` (its own package); `cli` imports any package; `dsl` keeps `core` and `model`; `checks` keeps `core`, `model`, `geometry` and `backends.base`. Every edge is in `package-layering`, so `ALLOWED` in `tests/unit/test_import_graph.py` is unchanged.

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| — | none | — | no new public source is needed; S-0085 … S-0089 stay unused |

Extended "used for" cells, with no new id (task 1.1):
- **S-0022** (`kicad-cli` 10.0 manual): `pcb upgrade --force` as the stand-in for a GUI save in the layout oracle.
- **S-0037** (`kicad-cli` 9.0 manual): no `pcb upgrade` in 9.0, so target-9 cases rebuild the edited text.
- **S-0010** and **S-0038** (board editor manuals): zone properties and refilling, as background for `H-K-LENS-FILL` (to verify on the pages; if the pages do not say it, the premise rests on the hypothesis only).

Rows of other changes cited here: S-0020 (`kicad-cli` 10.0.6 as an oracle), S-0055 and S-0056 (DRC report keys). No KiCad source file is read. If a URL above is already registered when this change is implemented, the existing id is cited and no row is added.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-LENS-KEEP | A footprint of a built board moved by token edit, with a route and a via added on its net by token edit, survives `fenolite build` over that board: it keeps its uuid and `fenolite.path` through a `pcb upgrade --force` re-save on 10.0.6 (S-0022; builds on `H-K-UUID-KEEP-2` and `H-K-BUILD-PATHPROP`), and on the rebuilt board `pcb export pos` gives its moved position and the DRC report holds the same (type, severity) multiset and `unconnected_items` count as the edited board's (S-0022, S-0037, S-0055, S-0056) | `tests/kicad/lens/test_preserve_oracle.py::test_moved_footprint_survives` (probes `lens-resave-t10`, `lens-rewrite-t9`, `lens-rewrite-t10`, `lens-keep-t9`, `lens-keep-t10`) | on 10.0.6 for target 10 (re-saved) and target 9 (edited text), and on 9.0.9 for target 9 (edited text; 9.0 has no re-save, S-0037): every check holds, and a second rebuild writes the same bytes |
| H-K-LENS-FILL | A zone fill depends only on the inputs that `zone_digest` and `fill_inputs_digest` cover, so a fill that is current on a board stays current on a rebuild whose two digests are unchanged (S-0010, S-0038) | placeholder `tests/kicad/fill/test_fill_oracle.py::test_kept_fill_matches_refill` (zone-fill change, c0015) | on 10.0.6: the blink filled by `kicad-cli` 10, then rebuilt without a change to the digests, keeps fills equal to those that `pcb drc --refill-zones --save-board` computes for the rebuilt board on a copy |

Cited, not settled here: `H-K-UUID-KEEP-2`, `H-K-BUILD-PATHPROP` (c0011), `H-K-DRU-ORDER` (c0018), `H-K-TOK-RULES-SILENT`, `H-K-TOK-RULES-DRIFT`, `H-K-PCB-READ`, `H-K-PCB-WRITE`, `H-K-PRO-PATTERNS`. No behaviour depends on an open row except through the stop rules of Decision 20 and the `H-K-BUILD-PATHPROP` fallback of Decisions 4 and 21.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Matching keys, order, aliases, orphans, board-only footprints | mechanical (unit tests) | `tests/unit/lens/test_preserve_match.py`, `test_preserve_footprints.py` |
| The script's user properties on kept footprints (Decision 22) | mechanical (c0009 reader, c0017 writer) | `test_preserve_footprints.py`, `test_preserve_determinism.py` |
| Board-only pins on their pads' nets; no symbol asked of board-only components by `check` | mechanical (unit and command tests) | `test_preserve_footprints.py`, `tests/unit/checks/test_validate_stage.py`, `tests/unit/cli/test_build_preserve_command.py` |
| Placement precedence and the off-board rule | mechanical (unit tests) | `test_preserve_place.py` |
| Copper items by net, board content, outline rule, copper check | mechanical (c0009 reader, c0017 writer) | `test_preserve_copper.py`, `test_preserve_board.py` |
| Digests and stale fills | mechanical; the premise `INFERRED` (`H-K-LENS-FILL`) until c0015 | `test_preserve_fills.py` |
| Rules merge, gating of user rules | mechanical; gating inherits c0018's labels (`H-K-DRU-*`) | `test_preserve_rules.py` |
| Project merge | inherits c0010 (`INFERRED`, `H-K-PRO-PATTERNS`) | `test_build_preserve.py` |
| `Design.moved`, `moves` | mechanical (unit tests) | `tests/unit/dsl/test_moved.py` |
| Normal form, byte-identical rebuilds, regenerated cache | mechanical | `test_preserve_determinism.py` |
| Built model against the written board by keys (components, positions, properties) | mechanical (c0009 reader) | `test_preserve_readback.py` |
| A moved footprint survives a rebuild with its tracks intact (`H-K-LENS-KEEP`) | KICAD-VERIFIED on 10.0.6 (local and `kicad-10`; targets 10 re-saved and 9) and 9.0.9 (`kicad-9`, target 9) | `tests/kicad/lens/test_preserve_oracle.py` |
| A target-9 board re-saved by 10.0.6 is refused for target 9 | KICAD-VERIFIED (10.0.x) | `test_preserve_oracle.py::test_downgrade_refused` |
| The `build` envelope over an existing board | INFERRED (Decision 19) | `preserve.EVIDENCE` |

`lens.preserve.EVIDENCE` stays `INFERRED` after this change, even when `H-K-LENS-KEEP` is `KICAD-VERIFIED`: it covers the edited blink, not every board.

## Budget (about 2.5 weeks; the plan line "dsl/preserve 1.5 weeks" is shared with c0011)

| work | days |
|---|---|
| 1. registers, docs skeletons, `board.md` rows | 0.5 |
| 2. edit helper and probes first | 0.5 |
| 3. DSL aliases | 0.5 |
| 4. matching, preparation and precedence | 1.0 |
| 5. merge: footprints, user properties, orphans, board-only pins, copper items, board content; the symbol rule of `check` | 1.5 |
| 6. digests and stale fills | 0.5 |
| 7. rules merge and project pass-through | 0.5 |
| 8. build and command integration, normal form | 1.0 |
| 9. command-level scenarios, determinism and readback suites | 1.0 |
| 10. oracle on both majors, probe files | 0.75 |
| 11. closing | 0.5 |
| **total** | **8.25** |

The roadmap gives about 5 days, and the plan line "dsl/preserve 1.5 weeks" is shared with c0011 (8.5 days). This change is re-baselined at 8.25 working days, stated here and in the proposal; Decisions 21 and 22 added 0.25 day each to group 5. Cut order, to 7.5. A cut first edits or removes the requirements and scenarios named with it, so that no requirement is archived without its code:
1. The `lens-rewrite-*` probes are dropped, and `lens-resave-t10` is asserted inside the oracle test (−0.25).
   - kicad-oracle "Preserved layouts pass the oracle": the rule "Probes first" and its stop rules are removed; "Re-save" asserts what `lens-resave-t10` probed (uuids and `fenolite.path` kept after `pcb upgrade --force`); the scenario "Probe outcomes pinned" lists only `lens-keep-t9` and `lens-keep-t10`.
   - Task 2.2, the probe list of `H-K-LENS-KEEP` and Decision 20 follow.
2. `fill_inputs_digest` is dropped, and fills follow `zone_digest` alone, the roadmap's literal digest (−0.25).
   - layout-lens "Layout lens module": `fill_inputs_digest` leaves the public names.
   - layout-lens "Zone fills and the staleness digest": its first sentence names `zone_digest` only; the `fill_inputs_digest` rule and the rule on the texts each side is digested with are removed; the scenarios "A removed part drops fills" and "A class change drops fills" are removed, because neither changes `zone_digest`; "Digests ignore ids and formats" keeps `zone_digest` only.
   - layout-lens "Layout facts are documented": "the two digests" becomes "the zone digest".
   - `drop_stale_fills` loses its `existing`, `project` and `rules` parameters, `H-K-LENS-FILL` is restated for `zone_digest`, and Decision 11 follows.
3. The off-board rule is dropped, so a staged part needs a locked `place()` to move (−0.25).
   - layout-lens "Placement precedence": the off-board clause for matched parts, the rule that defines "off the board" and the sentence on designs without an outline are removed. The scenario "A staged part placed by the script" calls `place(…, locked=True)` and expects `layout.place-forced`; "A staged part stays staged" expects no `layout.unplaced`.
   - design-dsl "Build issue codes" (MODIFIED): `layout.unplaced` takes back c0011's "when" text, "a part was staged beside the outline".
   - layout-lens "Layout facts are documented": `docs/lens.md` no longer covers an off-board rule. Decision 6 follows.

Not optional: matching, precedence, kept, re-placed, orphan and board-only footprints with their pins and the symbol rule of `check`, copper by net, board content, the project and rules merge, the normal form, byte identity, and the oracle on both majors.

## Risks / Trade-offs

- [c0018, c0010, c0011, c0027 or c0013 names drift while they are implemented] → The committed proposals are the contract; task 1.1 re-checks every consumed name and records each divergence in the pull request.
- [A re-save drops the uuid or the `fenolite.path` of a moved footprint] → `lens-resave-t10` runs first with a stop rule; `H-K-UUID-KEEP-2` already holds for unmoved footprints.
- [Fenolite's rewrite of a KiCad-saved board changes its DRC report] → `lens-rewrite-*` run first with a stop rule; c0020's RT2 stage generalises the check later.
- [Opaque content names a removed net] → c0017's writer refuses with a located `kicad.board.opaque-net-ref` (exit 7); `docs/lens.md` gives the two ways out.
- [A board saved by KiCad 10 cannot be rebuilt for target 9] → c0017's FEN-7002 with its hint; the oracle tests the refusal and the target-10 rebuild; `docs/lens.md` says so.
- [The digests drop fills after a change that did not affect them, such as whitespace in a rules file] → Conservative by design; the agent loop runs `fill` after every build (the loop order of `docs/roadmap.md`: build, place, route, fill, check), and `zone.fill-stale` says why.
- [An orphan removal loses a placed footprint] → `layout.orphan` names it with its position, the `.bak` keeps the previous board, and `moved()` covers renames.
- [`update_project` is not idempotent on its own output] → The rebuild-twice tests cover the project file; a difference is a c0010 defect, reported there.
- [The KiCad GUI changes a footprint in a way the token proxy does not (for example re-creating it)] → the path key covers a new uuid; the maintainer's GUI move is supporting data (Open Questions).
- [DRC reports differ between two runs on the same board] → The probes and the oracle compare multisets; a `different` outcome stops the change until it is explained. The general stability measure belongs to c0020's RT2 stage.
- [Overrun; c0008 took about three times its line] → The cut order of "Budget".

## Migration Plan

- Additive code: a new module, new keywords on `build_design`, a new `BuildOutput` field, a new DSL call and result key. Behaviour change: an edited board, project or rules file is merged instead of refused (`FEN-7001` remains for `fp-lib-table` and vendored footprints). The model, the schemas, the FEN codes and the writers are unchanged. To roll back, remove `lens/preserve.py` and the extensions, and restore the texts that the six MODIFIED `design-dsl` requirements copy (c0027's for four, c0011's for two) and c0013's text of "Model validation stage"; built projects stay valid KiCad projects.
- Archive order: "Built project files", "Build command", "Build issue codes" and "Build evidence" copy c0027's MODIFIED text (c0011's ADDED text with c0027's edits: `vendor`, `record`, `--vendor`, the property and vendoring codes and evidence); "DSL package" and "Edited outputs are not overwritten" copy c0011's ADDED text, which c0027 leaves alone; the MODIFIED `verification-loop` requirement "Model validation stage" copies c0013's ADDED text (Decision 21). `openspec validate --strict` accepts them now, but `openspec archive` fails unless the requirements already exist, and archiving before c0027 would drop c0027's edits. So this change MUST be archived after c0011, c0027 and c0013, as the canonical order does (c0010, c0026, c0011, c0027, c0013, then this change; c0020, c0021 and c0012 follow). c0021 then MODIFIES "Build command" on this change's text, and c0028, c0029, c0030 and c0031 extend these requirements through ADDED requirements that name them. c0012 and c0013 leave `design-dsl` unchanged. No other active change modifies "Model validation stage".
- Edits to the base texts, per MODIFIED requirement; task 8.1 checks the copies against this list. The four c0027 copies keep c0027's edits, and each edit below is applied to c0027's wording of the same sentence. The sentences that let later requirements extend a text come from Decision 23.
  - `design-dsl` "DSL package" (Decision 17): `convert.py` lists `moves`, and `fenolite.dsl` re-exports it; "no `moved()` (c0019)" leaves the list of absent features, and a sentence names `Design.moved(old, new)`; a sentence lets later requirements add modules and re-exported names, each naming this one; new scenario "Aliases exported".
  - "Build command" (Decisions 2, 16, 17 and 19): the command also converts with `moves` and prepares preservation unless `--discard-layout`; `result` gains `preserved`; the `DslError` rule covers `moves`; a new rule gives the `prepare` call and the `build_design` arguments with and without `--discard-layout`; `check_existing` gets every planned file except the board, project and rules files; a sentence lets later requirements add `build` options, steps of `cmd_build` and `result` keys, each naming this one; new scenario "Rebuild over an edited board". "Rebuild is identical" keeps its text and now runs through preservation.
  - "Built project files" (Decisions 12 to 15): `build_design` gains `prepared=None`; the steps gain the merge and its validation, `write_triad` of the merged layout with the existing project text, `merge_rules`, `drop_stale_fills` with a second `write_board`, and the layout derived from the written board text; `BuildOutput` gains `layout`, with `design` and `layout` defined; the `.fenolite/` texts come from `BuildOutput.layout`; a sentence lets later requirements add keyword-only arguments with defaults and steps, each naming this one; new scenarios "Cache texts come from the layout" and "Existing project text is merged".
  - "Edited outputs are not overwritten" (Decisions 5 and 16): "until c0019 preserves layouts" becomes the exception for the board, project and rules files, and the check names `fp-lib-table` and the vendored footprints under `lib/`; "edited, for example in KiCad, or found without a record" becomes "edited, or found without a record", because a board edited in KiCad no longer reaches the check; a new rule keeps the three triad files out of the check; under `--discard-layout` the build also preserves nothing. The scenario "DSL edit needs no flag" changes `R1`'s value instead of moving `R1`, because the board now wins over an unlocked `place()` (Decision 5), and expects the new value. "Edited board refused" becomes "Edited board is merged, not refused"; the new "Edited vendored footprint refused" carries the refusal; "Discarding the layout" and "Lossy flag does not skip the check" move from the board to the vendored footprint, and "Lost record" to `fp-lib-table`.
  - "Build issue codes" (Decisions 2, 6, 16 and 18): `BUILD_ISSUE_CODES` holds every row of `PRESERVE_ISSUE_CODES`; the pass-through list gains the readers, with `kicad.board.*` and `kicad.version.*`, because the existing board's reader warnings are reported (Decision 2); `build.layout-exists` names `fp-lib-table` and the vendored footprints; the "when" text of `layout.unplaced` gains "its footprint being new or off the board" (Decision 6); "Closed set enforced" accepts the severities of `PRESERVE_ISSUE_CODES`; new scenario "Preservation codes are build codes". Decision 23: every `kicad.*` code passes through (the list of writers, readers and the resolver becomes examples), and a sentence lets later requirements add codes that join the `build` envelope, each naming this one; "Closed set enforced" exempts those codes.
  - "Build evidence" (Decision 19): `lens.preserve.EVIDENCE` and `pcb.EVIDENCE` join when an existing board was read, and `dru.EVIDENCE` when an existing rules text was merged; a sentence lets later requirements add evidence that joins only when used, each naming this one; new scenario "An existing board adds the preservation rows".
  - `verification-loop` "Model validation stage" (c0013; Decision 21): `check.symbol-unresolved` applies to components whose `properties` hold a `fenolite.path` key; a new rule exempts board-only components; "Unresolved footprint and symbol" gives its first component that key; new scenarios "Board-only component not asked for a symbol" and "Rebuilt blink with a mounting hole added in KiCad".

## Open Questions

- **A real GUI move on 10.0.6 (question to the maintainer).** Besides the automated stand-in, will the maintainer move one footprint in the KiCad 10.0.6 GUI and record it as supporting evidence? The default: the automated proxy (token edit plus `pcb upgrade --force` on 10.0.6, the token edit alone on 9.0.9) is the acceptance. If a GUI-saved board of the CC0 blink is provided before task 10.1, it becomes the authored fixture `tests/data/kicad/lens/blink_gui_move.kicad_pcb` (declared in `MANIFEST.toml`), `test_gui_move_survives` runs over it on 10.0.6, and the result column of `H-K-LENS-KEEP` names it; otherwise the row says that no GUI move was recorded.
- **Meaning of "locked".** The default reads it as `place(…, locked=True)` in the script (Decision 5). The alternative, the board's lock flag, makes the order redundant.
- **Fill digest beyond the roadmap's list.** The default adds `fill_inputs_digest`, because the project plan's words include "rules" and a moved pad makes a fill stale. Cut 2 falls back to the roadmap's list.
- **Orphans and board-only footprints.** The default removes orphans with a warning and keeps footprints without `fenolite.path`, with their components in `.fenolite/`, their pins on their pads' nets, and no symbol asked of them by `check` (Decision 21). To confirm.
- **If c0011 refuted `H-K-BUILD-PATHPROP`.** The default matches by uuid and by alias uuid only, keeps every unmatched footprint as board-only, and never reports `layout.orphan`; the acceptance line "removed parts raise `layout.orphan`" is then recorded as not met in v0.1. No component then carries the key, so `check` asks no component of a built project for a symbol; script parts lose nothing, because c0011 fails a build whose symbol does not resolve (Decision 21).
- **If c0011 applies its cut 4.** c0011's cut order can move `fenolite.path` and `H-K-BUILD-PATHPROP` to this change. The default takes them over as c0011 specifies them, before task 4.1: `embed.with_property` and `embed.PATH_PROPERTY`; the probes `build-pathprop-t9` and `build-pathprop-t10` with their stop rule; the row `H-K-BUILD-PATHPROP`; c0011's `kicad-file-backend` requirement "Path property on placed footprints" as an ADDED requirement here; and the property in c0011's "DSL to model", "Placement of built parts" and "Build evidence", as MODIFIED deltas of c0011's archived text. Cost +0.5 day, total 8.75. Matching, the orphan rule and the board-only marker then stay as specified. The alternative, matching by uuid and alias uuid only, is the fallback of the previous question: no `layout.orphan`, and every unmatched footprint kept as board-only.
- **Board versus `.fenolite/` in `check` (c0013's hand-over).** The default adds no `check` stage in v0.1: every build rewrites `.fenolite/` from the written board (Decision 14), and `test_preserve_readback.py` covers the comparison by keys that c0011 and c0013 assigned here (components, positions, properties). A staleness stage belongs to the v0.2b sync.
- **`Design.sheet()` (c0011 and c0012 left it to "c0019 or v0.2a").** The default leaves it to v0.2a; this change keeps the board's title block and paper.
- **Stale vendored files (c0011: "c0019 may prune").** The default prunes nothing, because the mutation protocol never deletes; they stay harmless.
- **User properties on kept footprints (c0027's hand-over).** Default: the script owns them (Decision 22); a property that the script no longer names stays on a kept footprint until `--discard-layout` or a re-placement. The alternative, the board wins, is rejected there.
- **Values and references edited in KiCad.** The default writes the script's values and references over them, because the script owns the circuit; footprints keep every other edit.
- **Lifted user rules are respelled.** The default accepts c0018's codec spelling (`8mil` becomes `0.2032mm`). Verbatim lifted rules would need a gating-only function in `dru.py`, a c0018 follow-up.
- **Budget.** 8.25 working days against the roadmap's 5, with the cut order of "Budget" (8.75 if c0011's cut 4 applies). To accept.
- **Hand-overs.** c0015 settles `H-K-LENS-FILL` with the placeholder test named in its row, and reuses `zone.fill-stale` beside its `zone.unfilled`. c0022's placer moves staged parts onto the board, after which the board placement wins. c0016's routes are kept by net like any track. c0020's RT2 stage generalises the DRC comparison of Decision 20, and its (`model`, `board`) netlist pair relies on board-only pins being net members (Decision 21). c0012, after this change and c0020, runs `apply_sheet_keys` after the project merge of Decision 12. The default: each later change cites these rules instead of restating them.
- **Divergence check against the working tree (2026-10-02).** c0018 is being implemented (`rulemap.py` exists; `dru.py` and `lowering.py` do not yet); c0010–c0013 are not started. The names used here are those of their committed proposals; task 1.1 re-checks them.
