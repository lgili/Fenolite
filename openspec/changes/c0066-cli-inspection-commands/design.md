## Context

- **Scope.** Plan D8, v0.2a: "`diff`, `roundtrip`, `fmt --check`, `explain`, `restore`, pagination, `net/region/neighbors`"; its table rows: "`--format concise|detailed`, `--limit/--cursor` (v0.2a)", "`fenolite explain <code>` (v0.2a)", "`undo: "fenolite restore <id>"` (v0.2a)", "compact views: `inspect --summary` (v0.1); `net`, `region`, `neighbors` (v0.2a)". Plan v0.2a acceptance: "`diff` of 'move a footprint by 1 mm' shows exactly one `Change`; `fmt --check` idempotent over the whole corpus". Plan appendix A, item 2: "`check`/`diff`".
- **What exists.**
  - The dispatcher (`cli/main.py`): the envelope with exactly nine top-level keys, `--fields`, the mutation protocol with one `<file>.bak` per overwritten file, and `receipt = {written, backup}`. Nothing is written besides the planned files.
  - `sexpr.dumps` in `kicad` style, idempotent by requirement, and RT0 over the corpus (c0006); RT1 for boards (`roundtrip.rt1`) and, with c0060, for schematics; RT2 through `KicadOracle.rt2` (c0020) and `rt2_erc` (c0062).
  - About twenty issue-code tables (`ISSUE_CODES` and names ending in `_ISSUE_CODES`) and the FEN registry of `cli/errors.py`; `docs/cli-contract.md` documents the codes and tests keep it complete. A code's meaning is nowhere in the package itself.
  - The board frame (c0028): `board_pads` and `placed_extents` through the `BoardFrame` protocol; the geometry kernel's exact gaps between thick shapes (c0029).
  - The layering row `analysis` (`model`, `geometry`, `backends.base`) exists, and so does the package since c0047 (archived on 2026-10-04), which holds the board analyses and `fenolite analyze`.
- **c0044** (proposed, v0.3) ADDs "Model difference report" (`checks/diff.py`: `Change`, `DiffReport`, `diff_designs`, `diff_libraries`) and "Diff command" (`--view model|records`, `--ext`, `--limit N`), and says: "v0.2a adds the schematic kinds and KiCad's tree view". It depends on five Altium changes; v0.2a's acceptance needs `diff` without them.
- **Constraints.** Every new command is read-only or goes through the mutation protocol. No tool runs except for `roundtrip --level rt2`. Stdlib only. Output holds no absolute path and no date.

## Goals / Non-Goals

**Goals:**
- Small answers to small questions, each a command an agent can call with a bounded output.
- One paging rule for every list, and exit codes that never depend on the page.
- An undo that cannot destroy anything.
- `diff` once, for every backend.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- A query language. Three fixed views cover what an agent asks while placing and routing; more come with use.

## Decisions

1. **The diff engine is c0044's.** `checks/diff.py` defines `Change`, `DiffReport`, `diff_designs` and `diff_libraries` with the matching rules, paths and order of c0044's requirement, and this change adds `diff_sheets` for two `SchematicSheet`s.
   - Whichever of the two changes is implemented second finds the requirements in the living spec and turns its ADDED deltas into MODIFIED ones: c0044 adds `scope`, the records view and document inputs; this change adds sheets and the tree view. Neither removes anything of the other.
   - Rejected: waiting for c0044 (v0.2a's acceptance would depend on the Altium readers); a KiCad-only engine here (c0044 would have to widen or replace it).

2. **Matching.** Ids, native ids and provenance never take part. Named entities are matched by name (`ref`, net name, `REF-PIN`, `<library>:<name>`); copper and graphics by content. A moved footprint is one `changed` at `/footprint/<ref>/position`; a moved track is one `removed` and one `added`. For sheets: `symbol` by reference and unit, `sheet_ref` by name, `lib_symbol` by embedded name, labels and no-connect flags by content.

   - Added while implementing (2026-10-05), because the requirement says "every difference" and the kind
     lists left parts of the model out: `interface` and `module` are keyed kinds; the values a design
     holds once (outline, finish, sheet, title block) are fields of the keyless kind `design`; the
     design's name is not compared, since a board read from `a.kicad_pcb` and one read from
     `b.kicad_pcb` would otherwise always differ. A key is escaped as a JSON pointer segment, because
     KiCad net names start with `/`. "Canonical order" of unmatched content entities is the order of
     their compact canonical JSON: the model's own canonical order sorts by id, which a diff must not
     read. c0044 re-bases on this text.

3. **`fenolite diff A B`** (`mutates=False`). Each input is a KiCad board, footprint file, symbol library or schematic, or a folder with `.fenolite/meta.json`. Both must be of one family (design, library or sheet).
   - `--view model` (default): the report of Decision 1; `--ext` also compares the opaque content, as a hash.
   - `--view tree`: two KiCad files of one kind; `result.equal` is `tree_equal`, with the locator of the first difference and the counts of root children by head where they differ. It answers "did anything at all change", opaque content included, without a list.
   - A difference is a result: exit 0 either way; `result.equal` says it.
   - The list `differences` is paged (Decision 9) with a default limit of 200.

4. **`fenolite roundtrip PATH [--level rt0|rt1|rt2]`** (`mutates=False`), for a KiCad S-expression file, or a project for `rt2`.
   - `rt0`: `tree_equal(parse(dumps(parse(t))), parse(t))`, for any kind.
   - `rt1` (default): RT0, then the backend's same-version rebuild for boards (`roundtrip.rt1`) and schematics (`sch.roundtrip_schematic`); for a kind without one, the level reached is `rt0` and `result.rt1` is `not-applicable`.
   - `rt2`: RT1, then `KicadOracle.rt2` for the board of a project and `rt2_erc` for its schematic; needs `kicad-cli` (exit 6 without it).
   - `result`: `kind`, `level` (the highest level that holds), per level `passed`, `difference`, `opaque_count`; for RT2 `judged` and the counts. A level that fails gives `roundtrip.failed` (error) and exit 5: an agent runs this before it edits a file it did not write.

5. **`fenolite fmt PATH [--check]`** (`mutates=True`). The canonical print of a file is `dumps(parse(text))`.
   - `--check`: writes nothing; `result.formatted` says whether the file already is its canonical print; when it is not, `fmt.would-change` (error, exit 5) names the first differing line.
   - Without `--check`: one planned write of the canonical text, through the mutation protocol; a file already canonical plans nothing.
   - Accepted: `.kicad_pcb`, `.kicad_mod`, `.kicad_sch`, `.kicad_sym`, `.kicad_wks`. Refused with exit 2: `.kicad_pro` (JSON, kept byte for byte), `.kicad_dru` (not a single S-expression), any other file. A tree with comments below the root, which `dumps` refuses, exits 7 (`FEN-7001`).
   - The tree is unchanged by construction (RT0); only the layout changes. Identity with KiCad's own printer is measured elsewhere (`H-K-FMT-*`) and is not a goal.
   - The corpus test proves the plan's sentence: formatting a formatted file changes nothing, on every corpus file.

   - Added while implementing (2026-10-05): `fmt` and `restore` are the first commands whose examples
     act on a file of the working directory, and the consistency suite asserted an empty folder before a
     confirmed write. `tests/_cliexamples.py` now prepares the example files of the commands it names,
     and the suite compares the folder before and after; the assertion for every other command is as
     strict as it was.

6. **`fenolite explain CODE`** (`mutates=False`). `cli/data/explain.toml` holds one entry per code: `meaning` and `fix`, each one or two sentences, and `see` (a section of `docs/cli-contract.md`).
   - `cli/explain.py::TABLES` names every issue-code table of the package; `all_codes()` returns their union with the FEN registry.
   - A code built from a tool's type (`kicad.drc.<type>`, `kicad.erc.<type>`) is explained by its family entry (`kicad.drc.*`) unless it has its own.
   - A test fails for a code without an entry, an entry without a code, and a table that `TABLES` does not name (found by scanning `src/fenolite` for names that end in `ISSUE_CODES`).
   - An unknown code exits 2 with the three closest codes in the hint.
   - Rejected: generating the entries from `docs/cli-contract.md`. The package would need its docs at run time.

7. **Receipt identity.** `receipt.id` is the first 16 hex digits of the SHA-256 of the canonical JSON of the receipt's `written` and `backup` lists; `receipt.undo` is `fenolite restore - --confirm` when a backup was kept, else `null`. No clock and no random value takes part, so `--seed` and `--timestamp` runs stay byte-identical.

8. **`fenolite restore RECEIPT [--in DIR]`** (`mutates=True`). `RECEIPT` is a file that holds the envelope of a confirmed write, or its `receipt` object; `-` reads it from stdin. `--in` is the working directory that write ran in (default: the current one).
   - For every `written` entry the file must exist with the recorded `sha256`; otherwise `restore.changed-since` (error) names it and nothing is planned. One changed file refuses the whole restore: a half-undone build is worse than none.
   - For every path in `backup`, the `.bak` must exist; the plan is one write per such file with the bytes of its `.bak`. Through the mutation protocol the present content becomes the new `.bak`, so a restore can be undone with its own receipt.
   - A written file without a backup (created by that write, or written with `--no-backup`) stays as it is, with `restore.kept` (info). Fenolite deletes nothing.
   - A receipt without any backup gives `restore.nothing` (error).
   - **The receipt is the undo token.** The plan writes `fenolite restore <id>`. Finding a receipt by id needs a journal that every confirmed write would add to the output folder or to the user's home; both break what users rely on today (a folder holds only planned files; no hidden write). An agent already has the envelope it was given.
   - Rejected: a journal under `.fenolite/` of the output folder (new files in every output folder, and c0011's "the only new files are the `.bak` copies" would no longer hold); a journal in the home folder (a hidden write outside the project on every command).

9. **Paged results.** `Command` gains `paged: str | None` (the dotted path of the command's main list in `result`, or `"issues"`) and `default_limit: int | None`.
   - Global flags `--limit N` and `--cursor TOKEN`. With a limit, the dispatcher keeps `N` items of the paged list from the cursor's offset and sets `result.page = {path, limit, offset, total, next}`, `next` being the cursor of the following page or `null`.
   - A cursor is `<offset>.<first 8 hex digits of the SHA-256 of the canonical JSON of the whole list>`. A cursor whose digest does not match the present list exits 2 (`FEN-2001`, "the result changed since the cursor was issued"). Paging keeps no state: every call computes the whole result and cuts it.
   - For `"issues"` the envelope's `issues` list is cut; `result.page` describes it.
   - The exit code, `ok` and every count in `result` come from the whole result, never from the page.
   - `--limit` on a command without a paged list exits 2. `check` pages `issues`; `diff` pages `differences`; `netlist` (c0063) `nets`; `bom` and `pnp` (c0064) `lines` and `rows`; `manifest` (c0065) `artifacts`; `net`, `region` and `neighbors` their lists.

   - Added while implementing (2026-10-05): `paged` may name alternatives (`nets|net.pads`), because
     `net` returns one of two lists; and the dispatcher sets `total` and `truncated` beside a paged
     list, so `diff` keeps c0044's two keys without knowing the page.

10. **Concise output.** `--format concise|detailed` (default `detailed`). `concise` keeps, for each issue code, the first issue in order and drops the others, and adds `result.issues_summary`: per code, its severity counts and total. Paging applies after it. An agent that fixes one problem per iteration reads one issue per kind and the counts.
    - `result` is otherwise unchanged; `--fields` already trims it.

11. **Board views** (`analysis/views.py`, pure, on a `Design` and the records of the `BoardFrame` protocol):
    - `net_list(design) -> tuple[NetRow, ...]` and `net_view(design, name, *, pads) -> NetView`: class, pads (`REF-PIN`, layers, position), tracks and arcs per layer with their summed centre-line length, vias, zones, bounding box.
    - `region_view(design, box, *, pads, extents, layer=None, kinds=ALL_KINDS) -> tuple[RegionItem, ...]`: the footprints (by placed extent), pads (by copper), tracks, arcs, vias, zones and texts that touch a closed rectangle, each as `{kind, where, net, layer, box}`. "Touches" is exact for pads, tracks and vias (the gap between the item's thick shape and the rectangle is 0) and by bounding box for footprints, zones and texts.
    - `neighbors_view(design, ref, *, extents, pads, radius) -> NeighborsView`: the footprints whose extent on the same side lies within `radius` of the part's extent, sorted by distance and reference, each with `distance` (0 for touching or overlapping extents, with `overlap`), `side` and the nets it shares with the part.
    - Lengths in nm, angles in µdeg, as every command prints them.
    - The package `analysis` exists since c0047; this change adds `views.py` beside its modules and leaves its `__init__.py` and its exports alone. c0047's rule for the package holds for `views.py` too: no module names `float`, `math.sqrt` or a float literal (`board-analyses`, "Analysis package and report"), so lengths come from `math.isqrt` and the kernel's integer functions.

12. **Commands of the views** (`mutates=False`, no tool): `fenolite net PATH [NAME]`, `fenolite region PATH --box X1,Y1,X2,Y2 [--layer NAME] [--kinds a,b]`, `fenolite neighbors PATH REF [--radius L]`. Lengths on the command line need a unit (`12mm`), parsed by `core.units.parse_length`, as `place` does. An unknown net or reference exits 2 with the closest names in the hint.

13. **Two halves.** Decisions 1 to 5 (files: `diff`, `roundtrip`, `fmt`) and Decisions 6 to 12 (agent ergonomics) share only `docs/cli-contract.md`; the tasks are grouped so two implementers can take one half each.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/checks/diff.py` (new) | `Change(path, change, a, b)`; `DiffReport(equal, changes, summary)` with `to_json(limit)`; `diff_designs(a, b, *, ext=False)`; `diff_libraries(a, b, *, ext=False)`; `diff_sheets(a, b, *, ext=False)` |
| `src/fenolite/backends/kicad/sexpr.py` (extended) | `canonical(text, *, file="") -> str`; `first_line_difference(a, b) -> int \| None` |
| `src/fenolite/cli/api.py` (extended) | `Command.paged`, `Command.default_limit` |
| `src/fenolite/cli/main.py`, `output.py` (extended) | `--limit`, `--cursor`, `--format`; `page(items, limit, cursor) -> Page`; `Receipt.id`, `Receipt.undo` |
| `src/fenolite/cli/cmd__echo.py` (extended) | `--issues N`: the hidden test command produces N issues |
| `src/fenolite/cli/explain.py`, `cli/data/explain.toml` (new) | `Explanation(code, kind, meaning, fix, see, family)`; `explain(code) -> Explanation \| None`; `TABLES`; `all_codes() -> Mapping[str, tuple[str, ...]]` |
| `src/fenolite/analysis/views.py` (new) | `NetRow`, `NetView`, `RegionItem`, `NeighborsView`, `Neighbor`; `net_list`, `net_view`, `region_view`, `neighbors_view`; `ALL_KINDS` |
| `src/fenolite/cli/cmd_diff.py`, `cmd_roundtrip.py`, `cmd_fmt.py`, `cmd_explain.py`, `cmd_restore.py`, `cmd_net.py`, `cmd_region.py`, `cmd_neighbors.py` (new) | `COMMAND`s |
| `schemas/fenolite.envelope.v0.json` (regenerated) | `receipt.id`, `receipt.undo` |
| `tests/unit/checks/test_diff.py`; `tests/unit/analysis/test_views.py`; `tests/unit/cli/test_diff_cmd.py`, `test_roundtrip_cmd.py`, `test_fmt_cmd.py`, `test_explain_cmd.py`, `test_restore_cmd.py`, `test_paging.py`, `test_views_cmd.py` (new) | hermetic |
| `tests/corpus/test_fmt_idempotent.py` (new); `tests/kicad/check/test_roundtrip_cmd.py` (new) | corpus; oracle, both majors |
| `docs/cli-contract.md` (extended) | one section per command; paging, concise output, the receipt fields, the new codes |

## Sources registered by this change

None. No format fact and no tool behaviour is added. S-0350 to S-0354 stay unused.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-FMT-IDEMPOTENT | For every S-expression file of the corpus that `parse` reads, the canonical print is a fixed point: printing it again gives the same bytes, and it parses to a tree equal to the source's | `tests/corpus/test_fmt_idempotent.py` | every `rt0` row, schematic rows of c0060 included: `canonical(canonical(t)) == canonical(t)` and `tree_equal(parse(canonical(t)), parse(t))`; rows whose tree `dumps` refuses are counted by reason |

Ids used without changing their level: `H-K-FMT-INDENT`, `H-K-FMT-RESAVE`, `H-K-SEXPR-STRICT`, `H-K-RT2-STABLE`, `H-K-ERC-RT2` (c0062), `H-K-SCH-RT1` (c0060), `H-G-FRAME-CRTYD-2`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Model difference report, sheets | mechanical; the report carries no label | `test_diff.py` |
| `diff` command | the lowest level of its two readings | `test_diff_cmd.py` |
| `roundtrip` RT0 and RT1 | the reader's level | `test_roundtrip_cmd.py` |
| `roundtrip` RT2 | KICAD-VERIFIED where judged | `tests/kicad/check/test_roundtrip_cmd.py` on 9.0.9 and 10.0.6 |
| Canonical print over the corpus | CORPUS-VERIFIED, `H-K-FMT-IDEMPOTENT` | `test_fmt_idempotent.py` |
| `explain`, `restore`, paging, concise output | mechanical | unit tests, the consistency suite |
| Board views | the board read's level with `frame.EVIDENCE` | `test_views.py`, with property tests against brute-force geometry |

## Budget (13.5 days)

| work | days |
|---|---|
| registers, command skeletons in the contract page | 0.5 |
| diff engine | 1.5 |
| `diff` command, sheets, tree view | 1.5 |
| `roundtrip` command | 1.25 |
| `fmt` and the corpus test | 1.0 |
| `explain`: table, texts for every code, command, completeness test | 1.75 |
| receipt identity and `restore` | 1.25 |
| paging and concise output in the dispatcher | 1.5 |
| board views and their three commands | 2.75 |
| docs, closing | 0.5 |
| **total** | **13.5** |

Cut order: (1) the tree view of `diff`; (2) `--format concise`; (3) `neighbors`; (4) the writing mode of `fmt` (`--check` stays); (5) `roundtrip --level rt2`. Not optional: `diff` with one change for a moved footprint, RT0 and RT1 in `roundtrip`, `fmt --check` with the corpus proof, a complete `explain`, `restore`, paging of `issues`, `net` and `region`.

## Risks / Trade-offs

- [c0044 and this change both ADD two requirements] → Decision 1 and the Migration Plan; the names are equal on purpose, so the second change only adds.
- [A restore after other tools touched the files] → refused by hash; the user sees which file changed.
- [A cursor that outlives a change of the board] → refused by digest; the caller starts again from the first page.
- [`explain` texts drift from the code] → the completeness test, and each entry is two sentences, cheap to keep.
- [Paging hides errors] → counts and the exit code come from the whole result; `result.page.total` says how many items exist.
- [`region` by bounding box overstates zones] → documented per kind; zones are listed with their box, so the reader can see it.
- [`fmt` rewrites a file KiCad then rewrites again] → harmless: the tree is equal. `docs/cli-contract.md` says `fmt` is for diffs under version control, not a KiCad formatter.

## Migration Plan

- Additive: nine commands, two global flags, two receipt fields with defaults, one `result` key when paging is asked for.
- `diff --limit` of c0044 becomes the global `--limit` with `diff`'s default of 200; c0044's `total` and `truncated` keys stay and equal `result.page.total` and `next is not None`.
- If c0044 is archived first, tasks 2.1 and 2.2 of this change start from its code and the two ADDED requirements become MODIFIED (sheets, tree view). If this change is archived first, c0044 does the same in the other direction.
- c0047 created `analysis/`: task 5.1 adds `views.py` beside its modules and leaves its `__init__.py` alone.
- Rollback: remove the commands; paging flags and receipt fields can stay unused.

## Open Questions

- **Maintainer: is the receipt as undo token acceptable in place of `restore <id>`?** Default: yes (Decision 8). A journal can be added later without changing the command: `restore` would accept an id as well.
- **Should `diff` exit 5 when the inputs differ (`--fail-on-difference`)?** Default: no, as c0044 decided.
- **Per-command result schemas** (deferred by c0025). Default: not here; the envelope schema stays the only contract until a consumer needs more.
- **A default limit for `check`'s issues.** Default: none; an agent passes `--limit` or `--format concise`.
