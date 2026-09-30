## Context

c0006 gives the KiCad backend a lossless S-expression layer (`sexpr.Node`/`Atom`, `parse`, `dumps`, `walk`), slots, a corpus of KiCad demo boards at tags 9.0.9.1 and 10.0.6, the required-resource mode (`FENOLITE_REQUIRE`) and a `kicad-10` CI job in the official Docker image. Nothing yet says which KiCad major can read a given token. Fenolite will write for two targets, 9.0 and 10.0, and read files from 8.0 on.

Facts this design relies on (sources in `docs/evidence/sources.md`; ids S-0030 … S-0039 are registered by this change, the others are cited from earlier changes):

- Format version constants per tag (S-0030, S-0031, S-0032; read for facts only, never code):

  | file kind | 8.0 | 9.0 (9.0.0 = 9.0.9) | 10.0 (10.0.0 = 10.0.6) |
  |---|---|---|---|
  | `.kicad_pcb`, `.kicad_mod` | 20240108 | 20241229 | 20260206 |
  | `.kicad_sch` | 20231120 | 20250114 | 20260306 |
  | `.kicad_sym` | 20231120 | 20241209 | 20251024 |
  | `.kicad_wks` | 20231118 | 20231118 | 20231118 |
  | `.kicad_dru` | not assessed | `(version 1)` (S-0010) | `(version 1)` (S-0038) |

- The dated versions next to the board constant (S-0030) tell which board/footprint names each version introduced between two releases. For example, `20240929` introduced per-layer padstacks (9.0), and `20251028` made items reference nets by name (10.0). The keyword lists at each tag (S-0033, S-0034, S-0036) show whether a single name exists in that release.
- Development builds write intermediate versions with `generator_version "8.99"`/`"9.99"`. The demos include `20241030` (at 9.0.9.1 and 10.0.6), `20250513` and `20250907` (at 10.0.6).
- Observed on `kicad-cli` 10.0.6 (S-0020; to be confirmed on both majors, hypotheses below):
  - A board or footprint whose header version is newer than the binary loads silently when every token is known. When a token is unknown, KiCad only decorates the parse error with "created with a more recent version" (`H-K-TOK-FUTURE`).
  - Unknown tokens are rejected in most sections and silently ignored in `general`. A footprint library with an unknown token fails with exit 2 (`H-K-TOK-STRICT`).
  - A worksheet with a future version or an unknown token prints "Error loading drawing sheet" and still exits 0 (`H-K-TOK-WKS-ORACLE`).
  - A custom-rules file with any error silently disables every custom rule, with exit 0. Rules are read only when a project file sits next to the board (`H-K-TOK-RULES-SILENT`). A rules file with `(version 2)` was accepted.
  - A 10.0-header board that keeps the numbered net table still loads. 10.0 no longer writes that table, zone `net_name`, the `hpglpen*` plot parameters, `plotinvisibletext` or zone `filled_areas_thickness`.
- Custom-rules files have their own lexical dialect (S-0010, S-0038): several top-level lists and no root, `#` comment lines, values with units (`3mm`), and strings quoted with `"` or `'` or left bare. A single-quoted rule name made 10.0.6 drop the whole file. c0006's parser rejects content after the root and treats `'` and `#` as ordinary atom characters, so it cannot read this dialect as is.
- The custom-rules header is `(version 1)` in both manuals, yet 10.0 lists constraint types 9.0 does not have: `bridged_mask`, `solder_mask_expansion`, `solder_paste_abs_margin`, `solder_paste_rel_margin`, `via_dangling`, and the disallow kinds `through_via` and `blind_via` (S-0038 against S-0010, names confirmed in S-0034). **This contradicts the earlier assumption that the rules grammar is frozen.** Only the worksheet grammar is frozen (constant unchanged 8.0 → 10.0.6, S-0032; name list unchanged 9.0.0 → 10.0.6, S-0036).
- The public worksheet page (S-0035) does not list every name KiCad reads and writes. `generator_version`, `face`, `color`, `maxlen`, `maxheight`, `incrlabel`, `notonpage1` and the legacy roots `page_layout`/`drawing_sheet` are confirmed only by the keyword list (S-0036) and by KiCad-written worksheets.
- `kicad-cli` differs by major (S-0022 for 10.0, S-0037 for 9.0). `pcb upgrade`, `sch upgrade`, `pcb export stats` and `pcb import` exist in 10.0 only. `pcb drc --refill-zones` and `--save-board` are absent from the 9.0 documentation. `fp upgrade` and `sym upgrade` exist in both.
- The official images `kicad/kicad:9.0.9` and `:10.0.6` are linux/amd64 only, run as uid 1000 and contain Python (S-0029). The 9.0.9 image is based on Debian bookworm (Python 3.11). The images set `LANG=C.UTF-8`; a native run inherits the user's locale and KiCad configuration.

Constraints: stdlib-only core (TOML through `tomllib`); `backends.kicad` imports only `model`, `geometry`, `core`, `backends.base` and its own package; GPL sources are read for facts only, never transcribed or paraphrased, and machine-readable grammar files are never converted into Fenolite data (ip-hygiene); budget about 1.5 weeks.

## Goals / Non-Goals

**Goals:**
- Give later readers and writers one API: detect kind and version, classify it, choose a target, refuse downgrade, and list every token a node carries that the target major cannot read.
- Keep a sourced inventory of what changed after the 8.0 floor, and prove each changed row on real `kicad-cli` 9.0.9 and 10.0.6.
- Settle the environment hypotheses `H-K-00` … `H-K-03`, add the `kicad-9` CI job, and make the KiCad oracle tests aware of the running major.

**Non-Goals:**
- Typed readers or writers, the `--kicad-version` flag, capability reporting (board backend change).
- An exhaustive list of tokens 8.0 already read, and a corpus census of observed paths (board backend change, which needs RT1 over the corpus anyway).
- Inventories for schematic and symbol-library files (their version constants only); project and `.kicad_prl` files; a custom-rules reader.
- Downgrade by dropping or rewriting tokens; checking that tokens survive a KiCad re-save. RT2 belongs to a later oracle change, which adds requirements to the `kicad-oracle` capability with ADDED deltas.

## Decisions

1. **One module, `versions.py`, owns constants, policy and inventory access.** The interface shared with c0006 and c0008 puts `FileKind`, `detect_version`, `min_version` and `check_emittable` in `fenolite.backends.kicad.versions`. Splitting the inventory loader into its own module would create an import cycle (`FileKind` ↔ rows), so the loader and matcher live in `versions.py` too, about 450 lines. *Rejected:* a separate `tokens.py` re-exported by `versions.py` (circular import or late imports for no gain).

2. **Kinds and roots.** `FileKind` values are the file suffixes without the dot (`kicad_pcb`, `kicad_mod`, `kicad_sch`, `kicad_sym`, `kicad_wks`, `kicad_dru`). Root heads map to kinds as follows:
   - `kicad_pcb` → board; `footprint` → footprint; `kicad_sch` → schematic; `kicad_symbol_lib` → symbol library.
   - `kicad_wks`, and the legacy roots `page_layout` and `drawing_sheet`, map to worksheet.
   - The pre-6 root `module` is recognised only to raise `UnsupportedFormatError`, so the message is clear.
   - Any other root raises `FormatError`.

   A custom-rules file has no root list, so rules are represented as a synthetic `kicad_dru` node wrapping the file's top-level lists. Two helpers convert between rules text and that node:
   - `wrap_rules(text, *, file="") -> Node` refuses a line whose first non-blank character is `#`, and any symbol atom containing `'`, with a `FormatError` that names the line or offset and says the full rules dialect needs the rules reader. Otherwise it parses `(kicad_dru` + newline + text + newline + `)` with c0006's `parse`.
   - `rules_text(node) -> str` dumps each child of the synthetic root at top level (c0006 `dumps`), one after the other, ending with a newline. It never writes the `kicad_dru` wrapper.

   The fuzz harness builds rules case files by text concatenation (canary rules text, a newline, the fragment) and uses `wrap_rules` only to find the rows a fragment exercises. Authored rules files use `"` quotes, units on values and no comments.
   *Rejected:* detection by file suffix alone (content is authoritative; `kind_for_suffix` exists only for callers that have no node yet); a rules parser option in `sexpr` (the rules reader change owns the dialect).

3. **Version detection.** `detect_version` reads the integer atom of the root's first-level `(version N)` child.
   - A missing version raises `FormatError` (KiCad fails too), except under a legacy worksheet root, which yields `LEGACY_WORKSHEET_VERSION = 0`. KiCad 10.0.6 ships worksheets like this as templates.
   - A non-integer version raises `FormatError` with the node's offset.
   - `major_for(kind, v)` returns `None` when `v < READ_FLOOR[kind]`. Otherwise it returns the oldest known major whose constant is ≥ `v`, or `None` when `v` is newer than every known constant. So `20250513` maps to 10, `20241030` to 9, and `20221018` (a KiCad 7 board) to `None`.
   *Rejected:* matching only the three released constants, which would reject the development-version demos.

4. **Classification and read policy.** `classify(kind, v)` returns `TOO_OLD` when `v < READ_FLOOR[kind]`, `FUTURE` when `v` is above every known constant, and `SUPPORTED` otherwise. The floors are the 8.0 constants for board, footprint, schematic and symbol library, 0 for worksheets and 1 for rules.
   - `require_readable(info)` raises `UnsupportedFormatError` (`FEN-3003`) for `TOO_OLD`. Its `hint` names the upgrade command for the kind: `kicad-cli pcb upgrade`, `fp upgrade`, `sch upgrade` or `sym upgrade`, noting that `pcb upgrade` and `sch upgrade` need KiCad 10.0. `kind_of` gives the same hint (`fp upgrade`) for the pre-6 `module` root.
   - `require_editable(info)` also raises `FutureFormatError` (`FEN-3002`) for `FUTURE`.
   - `version_issues(info)` returns a `kicad.version.future` warning for read-only inspection of a future file. It returns a `kicad.version.dev` info issue only when the status is `SUPPORTED`, the version is above the kind's lowest released constant, and it equals no released constant. A legacy worksheet (0), an older released worksheet version and a future file therefore never get the dev issue.

   Fenolite is deliberately stricter than KiCad. KiCad reveals nothing about a future board unless a token is unknown, and it even accepts a rules file with `(version 2)`. Fenolite cannot know what a future token means, so editing such a file could lose data without any error. `docs/formats/kicad/versions.md` states that the FUTURE classification of rules `(version 2)` is Fenolite policy, not KiCad behaviour. *Rejected:* copying KiCad's leniency (silent risk of loss); refusing even to read future files (blocks harmless `check`-style inspection).

5. **Targets and downgrade.** `TARGET_MAJORS = (9, 10)`, `DEFAULT_TARGET = 10`.
   - `check_target(info, target_major)` returns the header version to write (`FORMAT_VERSIONS[kind][target]`).
   - It raises `ValueError` for a target outside `TARGET_MAJORS` (a programming error).
   - It raises `UnsupportedFormatError` (`FEN-3003`) when the input is `TOO_OLD`, and `FutureFormatError` (`FEN-3002`) when it is `FUTURE`.
   - It raises `DowngradeRefusedError` (`FEN-7002`, exit 7) when `target < major_for(kind, version)`. Its hint names the lowest allowed target.

   Downgrade stays refused until a later capability resolver exists. *Rejected:* a best-effort downgrade that drops unknown children (silent loss, violates the exit-7 contract).

6. **Gating unit is the major; the dated version is evidence.** Each row has `since_major` (8, 9 or 10). It also has `since_version` when a dated fact exists, and the loader checks it against `major_for`. `check_emittable` compares `since_major` with the target. For released targets this is equivalent to comparing versions, and it also works for rules, where every file says `(version 1)`. `min_version` returns `since_version`, or the constant of `since_major` for the kind (the read floor when that major has none), or `None` when no row matches. `min_major` returns `since_major` or `None`. *Rejected:* gating by dated version only (cannot express the rules drift).

7. **Inventory scope: what changed since the floor, plus two closed vocabularies.** Rows cover:
   - (a) every board/footprint token name or symbol value introduced after 8.0, per the dated versions (S-0030), with the name confirmed at the tag (S-0033);
   - (b) tokens 10.0 no longer writes but still reads (`until_major = 9`): `hpglpennumber`, `hpglpenspeed`, `hpglpendiameter` and `plotinvisibletext` in plot parameters, zone `filled_areas_thickness`, zone `net_name`, and the numbered board net table (`/kicad_pcb/net`);
   - (c) form rows for value-form changes a path cannot express (items referencing nets by name, `20251028`);
   - (d) the worksheet vocabulary: the names of the public page (S-0035), plus names confirmed one by one at 9.0.0 and 10.0.6 (S-0036) and proved by the oracle, all `since_major = 8`, legacy roots included;
   - (e) the custom-rules vocabulary: the 9.0 manual's constraint types and clauses (S-0010) at `since_major = 9`, which is the rules floor major, and the constraint types and disallow kinds only in the 10.0 manual (S-0038) at `since_major = 10`.

   A `[[note]]` array lists every dated board-format version after 8.0 (S-0030). A note holds only the version and either the ids of the rows it introduced or a `no_row` reason taken from a fixed set: `"no-token-change"` (no name, and no value a released reader parses differently) or `"superseded-in-cycle"` (replaced before the next release; the later note carries the rows). Notes hold no summary, so neither the wording nor the structure of the source's comments enters the repository; the page generator names each feature from its row ids. This makes completeness against the dated versions testable.

   A board/footprint path that matches no row counts as a floor token and is not reported. This is safe for data Fenolite copies, because opaque subtrees come from a file whose major is at most the target (Decision 5). Typed writers must add a row for every token they emit.

   *Rejected alternatives:*
   - Transcribing `pcb.keywords` or `drawing_sheet.keywords` into a list: machine-readable GPL grammar files, which ip-hygiene forbids converting into Fenolite data.
   - A corpus census of every observed path now: about a day of work outside budget; it moves to the board backend change.

8. **TOML schema.** Top-level `format = 1`, `collected_at = ["9.0.9", "10.0.6"]`, then `[[token]]`, `[[form]]` and `[[note]]` arrays:
   ```toml
   [[token]]
   id = "pad-padstack"                  # unique kebab-case
   kinds = ["kicad_pcb", "kicad_mod"]
   path = "pad/padstack"                # see Decision 9
   # value = "…"                        # optional: a symbol atom directly under the node
   since_major = 9
   since_version = 20240929             # optional dated fact
   # until_major = 9                    # optional: last major that writes it
   older_readers = "reject"             # or "ignore" (older major loads and drops it)
   sources = ["S-0030", "S-0033"]
   hypothesis = "H-K-03"                # optional
   note = "per-layer (complex) padstacks"

   [[form]]
   id = "net-by-name"
   kinds = ["kicad_pcb"]
   applies_to = "net"                   # documentation only, never matched
   since_major = 10
   since_version = 20251028
   description = "items reference nets by name instead of by number"
   sources = ["S-0030"]
   hypothesis = "H-K-TOK-NETNAME"

   [[note]]
   version = 20240929
   rows = ["pad-padstack", "pad-padstack-mode", "pad-padstack-layer"]
   ```
   The loader rejects any of these with a `FormatError` that names the row id:
   - unknown keys, or a duplicate `id` across tokens and forms;
   - a duplicate (kinds, path, value);
   - `since_version` inconsistent with `since_major`, or `since_version` on a rules row;
   - an empty `sources`, or an `until_major` that is not above `since_major`;
   - a note with both or neither of `rows` and `no_row`, an unknown `no_row` reason, or an unknown row id.

   Tests check that every `S-` id and hypothesis id exists in the registers, and that every row with `since_version` cites S-0030. The evidence level is not stored in the TOML; it is computed from committed results (Decision 13), so there is one source of truth. *Rejected:* YAML (no stdlib parser); JSON (no comments, poor diffs); storing levels in the TOML (two sources of truth).

9. **Path matching.** A path is heads separated by `/`.
   - A leading `/` anchors it: it then matches only a head chain equal to it (`/kicad_pcb/net` is the board net table, not `segment/net`). Otherwise it matches a suffix of the node's head chain (`tenting/front` matches under `setup` and under `via`).
   - `#` matches a numeric head (the layer table's `(0 "F.Cu" signal)`).
   - A row with `value` matches a symbol atom that is a direct child of the matched node.
   - The most specific row wins: the longest pattern, then anchored before unanchored.

   Rows of other kinds never match, and form rows never take part in matching. This works on c0006's `Node` without a schema of KiCad's grammar. *Rejected:* XPath-like predicates (not needed for this inventory); a predicate on form rows such as "first atom is a string" (a second matching language for one row; examples name form rows explicitly instead, Decision 12).

10. **Emit check.** `check_emittable(node, kind, target_major)` walks the tree once and returns issues in document order:
    - `kicad.version.header-missing` or `kicad.version.header-too-new` (error) when the header is absent or above the target constant;
    - `kicad.token.too-new` (error) when a matched row has `since_major > target`;
    - `kicad.token.obsolete` (warning) when `until_major` is set and below the target;
    - for worksheet and rules only, `kicad.token.uninventoried` (warning) for a head or constraint value outside the vocabulary.

    `where` is exactly the locator c0006's `walk` yields (for example `/kicad_pcb/footprint[3]/pad[0]/padstack[0]`), with no prefix; `hint` names the row id and its sources. Form rows are not checked here; typed writers enforce them. *Rejected:* raising on the first problem (callers need the whole list to explain a refusal).

11. **Source discipline for rows.** Rows are written by hand from the dated versions (S-0030), public pages (S-0001, S-0010, S-0021, S-0035, S-0038) and KiCad-written files.
    - A keyword list (S-0033, S-0034, S-0036) is used only to confirm that a single name exists at a tag; no tool reads keyword files. A row whose only source is a keyword list needs a committed fuzz result that exercises it.
    - Where a token sits in the tree is taken from public pages, KiCad-written demo files, or KiCad's public QA data files at the tag (S-0039, facts only; the row's `note` names the file).
    - Examples are authored from scratch. Every placement is then proved by the 10.0 positive run (a misplaced token is rejected by 10.0).
    *Rejected:* generating rows from grammar or keyword files (forbidden); copying QA files as examples (GPL text).

12. **Examples, skeletons and controls.** `tests/data/kicad/tokens/` holds authored CC0 files, ASCII only, declared in `tests/data/MANIFEST.toml`:
    - `skeleton.kicad_pcb`: a 9.0-format floor board with four copper layers, an Edge.Cuts outline, the numbered net table, one footprint with a through-hole and an SMD pad, one segment, one via and one zone, using 8.0 tokens only;
    - `skeleton.kicad_mod`, `skeleton.kicad_wks`, and two legacy-root worksheets (`page_layout`, `drawing_sheet`) used as `file` examples;
    - `canary/`: a 9.0-format board (header `20241229`) with the numbered net table and two tracks on nets 1 and 2, 1 mm apart; `canary.kicad_pro` = `{}`; and a rules file whose `(constraint clearance (min 3mm))` rule must fire;
    - `old/`: 8.0-format footprint, symbol library, schematic and board used by the constants test;
    - `examples.toml`.

    Each `[[example]]` has `id`, `kinds` and either `host` (a path in the skeleton), `mode` (`append` or `replace`) and `fragment` (text), or `file` (a whole authored file in the folder). An optional `exercises` lists form-row ids, validated against the inventory. The harness finds the token rows an example exercises by matching every node of the fragment in its host context (or of the whole file); form rows count only when listed in `exercises`.

    Controls are examples with an explicit `expect = {"9" = …, "10" = …}` and, where needed, a fixed `header`:
    - `positive-baseline` per kind: the skeleton alone (for rules, the canary alone). It exercises the rows matched in the skeleton itself, such as the worksheet names and the obsolete net table;
    - `negative-unknown-<context>`: an invented token at top level, in `setup`, `segment`, `footprint` and `pad`, rejected by both;
    - `lenient-general`: an invented token in `general`, loaded by both;
    - `future-header`: the board skeleton with a version far in the future;
    - `dev-header-9`: the board skeleton with header `20241030`, loaded by both (`H-K-TOK-DEV`);
    - `wks-future` and `wks-unknown`, and `rules-canary-invented` (the canary plus one invented constraint).

    *Rejected:* one example per row for rows introduced in 9.0 or rows that only load (grouped examples prove loading just as well); a predicate language for form rows.

13. **Fuzz cases, expectations and results.**
    - **Rows and S.** An example's rows are the token rows it exercises plus its `exercises` form rows. `S` is their highest `since_major` (the kind's floor major when there are none).
    - **Header version.** On an image of major `M`, the case carries header `FORMAT_VERSIONS[kind][min(M, S)]`. A 10.0 token on 9.0 therefore carries 9.0's own header, and a rejection can only come from the token. When an exercised row has `until_major < M`, a second case carries `FORMAT_VERSIONS[kind][M]`, so obsolete rows are proved under the header of the reader that no longer writes them. Worksheets always carry the worksheet constant, and rules have no header change.
    - **Baselines.** `positive-baseline` runs once per (kind, header) that any case uses on that major. A case whose header baseline did not load is `inconclusive`, as is a worksheet or rules case whose own positive control did not load.
    - **Expected outcome.** The case should load when `S ≤ M`, or when every row above `M` says `older_readers = "ignore"`. Otherwise it should be rejected.
    - **Results file.** Results go to `docs/evidence/kicad/token-fuzz/<version>.json`, where `<version>` is the version `kicad-cli version` prints (recorded under `H-K-02`):
      `{format, kicad_cli: {version, image, platform, env}, cases: [{example, kind, header_version, example_sha256, rows, expected, outcome, exit_code, detail}]}`
      - cases are sorted by (example, kind, header_version);
      - there is no timestamp;
      - `detail` is the first message line, with temporary paths replaced by `<tmp>`.
    - **Evidence per row and major.** A row is `KICAD-VERIFIED` on major `M` when no case exercising it on `M` mismatches, and:
      - if `M ≥ since_major`: at least one case on `M` exercising it has outcome `load`; for a row with `until_major < M`, one such case carries `FORMAT_VERSIONS[kind][M]`;
      - if `M < since_major`: at least one case on `M` in which it is the only exercised row with `since_major > M` has the expected outcome.

      Otherwise it is `INFERRED` on `M`. `inconclusive` cases never count. This replaces the earlier assumption that all rows of one example share `since_major`: a parent row such as `tenting` (9) and a child row such as `tenting/front` (10) can share an example, and the rejection on 9.0 is credited to the child only.
    - **Checks.** The harness `--check` compares `outcome` and `exit_code` per case with the committed file. `test_token_results.py` recomputes `rows` and `expected` from the current inventory and examples. It fails on a stale `example_sha256`, on a case whose outcome differs from its expectation, and on a required row (Decision 7 scope, spec "Examples and controls") that is not `KICAD-VERIFIED` on both 9.0.9 and 10.0.6 and names no hypothesis.
    - **Generated page.** `tools/gen_token_docs.py` renders `docs/formats/kicad/tokens.md` from the inventory and results (row, kinds, since, until, sources, level per major), with a `--check` drift mode.

    *Rejected:* re-running Docker in the `unit` job (slow, needs Docker); storing only pass/fail (loses the exit code and message needed to diagnose); crediting a rejection to every row of the example (proves nothing about the older rows).

14. **Oracle per kind.** Each case runs in a fresh temporary directory, because KiCad writes a `.kicad_prl` next to the board. Every invocation has a timeout; a timeout is outcome `timeout`, which never matches an expectation. In every mode `kicad-cli` runs with `KICAD_CONFIG_HOME=<tmp>/cfg` (empty per harness run), `LANG=C` and `LC_ALL=C`, so the user's language, default drawing sheet and settings cannot change the outcome; the results header records these variables.

    | kind | command | loaded when |
    |---|---|---|
    | board | `pcb export svg <f> -l Edge.Cuts --mode-single -o out.svg` | exit 0 and the SVG exists (load failure = exit 3) |
    | footprint | `fp export svg <dir>.pretty -o <existing dir>` | exit 0 and an SVG exists (library failure = exit 2; missing output directory still exits 0) |
    | worksheet | `pcb export svg <skeleton board> --drawing-sheet <f> …` | the output lacks "Error loading drawing sheet" (exit code is always 0) |
    | rules | `pcb drc --format json -o r.json` on the canary board with project and rules | the canary violation is present in `r.json` |

    DRC never uses `--exit-code-violations`, because a minimal board already has violations. *Rejected:* `pcb export stats` (10.0 only); `pcb upgrade` as a load test (10.0 only, writes in place).

15. **Where `kicad-cli` comes from.**
    - `--kicad-cli PATH` runs the given binary; by default the harness uses `FENOLITE_KICAD_CLI`, then `kicad-cli` on `PATH`, then the macOS bundle path already used by `tests/_resources.py`.
    - `--docker IMAGE` re-runs the harness inside the image: `docker run --rm -u <uid>:<gid> -e HOME=/tmp -e PYTHONPATH=/w/src -v <repo>:/w -w /w IMAGE python3 tools/kicad_token_fuzz.py --kicad-cli kicad-cli …`. The harness and `fenolite` are stdlib-only, so the image's Python is enough if it is 3.11 or newer; `H-K-02` checks that the harness runs there. `HOME=/tmp` is safe because the skeletons use no library.
    - The results file name comes from the first line of `kicad-cli version`, restricted to `[0-9A-Za-z.+-]`. `H-K-02` records the exact output of both images, so the committed names are known before merge.

    *Rejected:* driving a long-running container with `docker exec` per case (more plumbing, same result); installing KiCad 9 on the runner (another install path to maintain; the official image is the reference).

16. **CLI error mapping without touching `core`.** The three error classes carry a class attribute `cli_code` (`FEN-3002`, `FEN-3003`, `FEN-7002`) and an instance attribute `hint`. The dispatcher in `cli/main.py` maps an exception raised by a command as follows:
    - a `FenoliteError` whose `cli_code` is registered → that code;
    - a `FormatError` without `cli_code` → the new code `FEN-3004` ("malformed input file"; hint "the message and `where` locate the problem"), because `FEN-3001` means a missing or unreadable file;
    - anything else → `FEN-1001`, unchanged.

    The message is `exc.message` for a `FormatError` and `str(exc)` otherwise, so the location is not repeated. `where` is built from `file`, `locator` and offset in `FormatError`'s own order. The exception's `hint`, when not empty, replaces the registry hint. `FEN-3003` ("input format version older than the oldest supported"), `FEN-3004` and `FEN-7002` ("target format version older than the input; downgrade is not supported") are added to the registry. *Rejected:* a `code` field on `core.errors.FenoliteError` (changes `core-primitives` for one consumer); importing backend modules from `cli/errors.py` (couples the CLI to a backend); reusing `FEN-3001` for parse errors (misleading hint).

17. **Environment probes and constants.** `tests/kicad/test_environment.py` (`needs_kicad`) checks `kicad-cli` help output per major:
    - `H-K-00`: `pcb --help` lists `import` iff the major is 10.
    - `H-K-01`: `pcb drc --help` lists `--refill-zones` and `--save-board` iff the major is 10.
    - `H-K-02`: `kicad-cli version` parses and its first line is recorded; the board positive baseline exports an SVG. This passes in both CI jobs.
    - `H-K-03`: settled by the padstack examples (`front_inner_back` and `custom` modes) loading on both majors.

    `tests/kicad/test_version_constants.py` checks the constants against the files each upgrade command writes (Decision 12's `old/` files):
    - `fp upgrade --force` and `sym upgrade --force` on both majors;
    - `pcb upgrade --force` and `sch upgrade --force`, marked `kicad_min_major(10)`;
    - the worksheet boundary: the constant loads, and constant + 1 prints the future-version error.

    A test marked `needs_corpus` and `kicad_min_major(10)` loads the development-version demos `20250513` and `20250907` in 10.0.6. The `20241030` mapping to 9 is proved by the `dev-header-9` control on 9.0.9 (`H-K-TOK-DEV`).

18. **Major-aware KiCad tests and the `kicad-9` job.** `tests/_resources.py` gains `kicad_cli_version() -> tuple[int, int, int] | None`, parsed once from `kicad-cli version`. A marker `kicad_min_major(N)`, registered in `pyproject.toml`, skips a test when the running major is below `N`. This skip names both majors and is never turned into a failure by required-resource mode, because the resource is present and simply older.
    - Every test under `tests/kicad/` that runs `pcb upgrade`, `sch upgrade` or `pcb import`, or that loads a 10.0-format fixture unchanged, carries the marker. This change audits c0006's tests: `test_escapes_after_upgrade`, `test_resave_equal` and `test_byte_identity_kicad10` get `kicad_min_major(10)`. `test_lexical_mirror` and `test_number_spellings` rewrite the fixture header to the running major's board constant in `tmp_path` (text substitution; fixtures without a header run unchanged), so they run on 9.0 too.
    - The `kicad-9` job uses c0006's container mechanism with `kicad/kicad:9.0.9` pinned by index digest, `FENOLITE_REQUIRE=kicad` and no corpus fetch. Its `needs_corpus` tests therefore skip.
    - The token fuzz check is the pytest test `tests/kicad/test_token_fuzz.py::test_committed_results`, which runs the harness `--check` against the committed file for the running version. Both jobs already run `tests/kicad`, so c0006's ordered step list for `kicad-10` stays as it is.

    *Rejected:* a separate `tests/kicad9/` folder (duplicates fixtures and drifts); failing on an older major in required mode (the job would be red from its first run).

19. **The inventory file name and the residue check.** The shared interface fixes `backends/kicad/data/tokens.toml`, but `tests/residue/test_no_token_list.py` rejects any path that looks like a token list. The check gains an allow-list with exactly `src/fenolite/backends/kicad/data/tokens.toml`, and a content check that the file holds only `format = 1`, `collected_at` and `[[token]]`, `[[form]]` and `[[note]]` tables whose rows cite registered public sources. The residue-scan capability gets an ADDED requirement for this. *Rejected:* renaming the file (reopens a decision shared with c0006 and c0008); a waiver in `scope.toml` (waivers cover scan patterns, not the name check).

## Hypotheses registered by this change

| id | statement | test that settles it | criterion |
|---|---|---|---|
| H-K-00 | `kicad-cli pcb import` exists in 10.0 and not in 9.0 | `tests/kicad/test_environment.py -k import` | listed iff major 10, in both jobs |
| H-K-01 | `pcb drc --refill-zones` and `--save-board` exist in 10.0 only | `test_environment.py -k refill` | listed iff major 10, in both jobs |
| H-K-02 | The pinned images run `kicad-cli` in a GitHub job container, print a parseable version and run the harness | `kicad-9` and `kicad-10` jobs, `test_environment.py -k version` | both jobs green; exact `kicad-cli version` output recorded (the 10.0 result is c0006's first `kicad-10` run) |
| H-K-03 | Pads with `(padstack (mode front_inner_back) …)` and `(mode custom)` load on both majors | fuzz examples `pad-padstack-front-inner-back`, `pad-padstack-custom` | `load` on 9.0.9 and 10.0.6 |
| H-K-TOK-CONSTANTS | The constants no command writes (board 9, schematic 9, all 8.0, rules) are those read in S-0030 … S-0032, S-0010, S-0038 | `test_version_constants.py` where a command writes the constant; none otherwise | written header equals the constant; the rest stay `INFERRED` |
| H-K-TOK-DEV | Development versions are read by the next release | control `dev-header-9`; `test_version_constants.py -k dev_demos` | `20241030` loads on 9.0.9; `20250513` and `20250907` load on 10.0.6 |
| H-K-TOK-FUTURE | 10.0.6 loads a far-future board header when every token is known; 9.0.9 behaviour unknown | control `future-header` | outcome recorded on both; policy unaffected |
| H-K-TOK-STRICT | Unknown tokens are rejected at top level and in `setup`, `segment`, `footprint` and `pad`, and ignored in `general` | controls `negative-unknown-*`, `lenient-general` | as stated on both majors |
| H-K-TOK-RULES-DRIFT | 9.0.9 disables custom rules that use a constraint type or disallow kind found only in the 10.0 manual; 10.0.6 accepts them | examples of the 10.0 rules rows | canary absent on 9.0.9, present on 10.0.6 |
| H-K-TOK-RULES-SILENT | Rules are read only with a project file next to the board, and any error disables all custom rules with exit 0 | controls `positive-baseline` (rules) and `rules-canary-invented` | canary present alone, absent with the invented constraint, exit 0, on both |
| H-K-TOK-RULES-FLOOR | Every constraint type and clause of the 9.0 manual loads on 9.0.9 and 10.0.6 | rules examples, where authored | each exercised row loads; unexercised rows stay `INFERRED` |
| H-K-TOK-WKS-ORACLE | With the isolated environment, a worksheet load error prints "Error loading drawing sheet" and exits 0 on both majors | controls `wks-future`, `wks-unknown` | message present and exit 0 on both |
| H-K-TOK-NETNAME | 9.0.9 rejects nets referenced by name in a 9.0-header board; 10.0.6 loads them | form example `net-by-name` | `reject` on 9.0.9, `load` on 10.0.6 |
| H-K-TOK-OBSOLETE | 10.0.6 still reads the tokens it no longer writes, under its own header | obsolete examples and baselines at `20260206` | `load` |

## Sources registered by this change

GitLab URLs are `https://gitlab.com/kicad/code/kicad/-/blob/<tag>/<path>`, with the tags written in the URL cell.

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0030 | `pcbnew/pcb_io/kicad_sexpr/pcb_io_kicad_sexpr.h`; tags 8.0.0, 9.0.0, 9.0.9, 10.0.0, 10.0.6 | GPL-3.0-or-later (facts only) | board/footprint constants; dated versions and the names each introduced |
| S-0031 | `eeschema/sch_file_versions.h`; same tags | GPL-3.0-or-later (facts only) | schematic and symbol-library constants |
| S-0032 | `include/drawing_sheet/ds_file_versions.h`; same tags | GPL-3.0-or-later (facts only) | worksheet constant |
| S-0033 | `common/pcb.keywords`; tags 8.0.0, 9.0.0, 10.0.6 | GPL-3.0-or-later (single names only) | board/footprint name confirmation |
| S-0034 | `common/drc_rules.keywords`; tags 9.0.0, 10.0.6 | GPL-3.0-or-later (single names only) | rules name confirmation |
| S-0035 | https://dev-docs.kicad.org/en/file-formats/sexpr-worksheet/index.html | not stated on the page (to verify) | worksheet names and placement |
| S-0036 | `common/drawing_sheet/drawing_sheet.keywords`; tags 9.0.0, 10.0.6 | GPL-3.0-or-later (single names only) | worksheet names absent from S-0035; vocabulary unchanged 9.0.0 → 10.0.6 |
| S-0037 | https://docs.kicad.org/9.0/en/cli/cli.html | to verify on the page | 9.0 command set |
| S-0038 | https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#custom_rule_syntax | to verify on the page | 10.0 rules syntax, constraint types, disallow kinds |
| S-0039 | `https://gitlab.com/kicad/code/kicad/-/tree/10.0.6/qa/data` | GPL-3.0-or-later (facts only) | token placement |

Cited from other changes, never re-registered: S-0001 (common syntax), S-0010 (9.0 pcbnew manual, custom rules section; c0005), S-0020 (`kicad-cli` 10.0.6 as an oracle; c0006), S-0021 (dev-docs board page; c0006), S-0022 (10.0 CLI page; c0006), S-0029 (the `kicad/kicad` image, used for 9.0.9 and 10.0.6; c0006). A URL already registered is cited by its existing id.

## Files and public API

New:
- `src/fenolite/backends/kicad/versions.py`
  ```python
  class FileKind(StrEnum): BOARD="kicad_pcb"; FOOTPRINT="kicad_mod"; SCHEMATIC="kicad_sch"
                           SYMBOL_LIB="kicad_sym"; WORKSHEET="kicad_wks"; RULES="kicad_dru"
  READ_MAJORS: tuple[int, ...] = (8, 9, 10)
  TARGET_MAJORS: tuple[int, ...] = (9, 10)
  DEFAULT_TARGET: int = 10
  FORMAT_VERSIONS: Mapping[FileKind, Mapping[int, int]]
  READ_FLOOR: Mapping[FileKind, int]
  ROOT_HEADS: Mapping[str, FileKind]
  LEGACY_WORKSHEET_VERSION: int = 0
  GENERATOR: str = "fenolite"
  class VersionStatus(StrEnum): TOO_OLD="too-old"; SUPPORTED="supported"; FUTURE="future"
  @dataclass(frozen=True, slots=True)
  class FormatInfo: kind: FileKind; version: int; major: int | None; status: VersionStatus
                    generator: str | None; generator_version: str | None
  class FutureFormatError(FormatError): cli_code = "FEN-3002"        # .hint
  class UnsupportedFormatError(FormatError): cli_code = "FEN-3003"   # .hint names the upgrade command
  class DowngradeRefusedError(FenoliteError): cli_code = "FEN-7002"  # .source_major, .target_major, .hint
  def kind_for_suffix(name: str) -> FileKind | None
  def kind_of(node: Node, *, file: str = "") -> FileKind
  def detect_version(node: Node, *, file: str = "") -> int
  def major_for(kind: FileKind, version: int) -> int | None
  def classify(kind: FileKind, version: int) -> VersionStatus
  def inspect(node: Node, *, file: str = "") -> FormatInfo
  def require_readable(info: FormatInfo, *, file: str = "") -> None
  def require_editable(info: FormatInfo, *, file: str = "") -> None
  def version_issues(info: FormatInfo) -> tuple[Issue, ...]
  def check_target(info: FormatInfo, target_major: int) -> int
  def wrap_rules(text: str, *, file: str = "") -> Node
  def rules_text(node: Node) -> str
  @dataclass(frozen=True, slots=True)
  class TokenRow: id; kinds: frozenset[FileKind]; pattern: tuple[str, ...]; anchored: bool
                  value: str | None; since_major: int; since_version: int | None
                  until_major: int | None; older_readers: Literal["reject", "ignore"]
                  sources: tuple[str, ...]; hypothesis: str | None; note: str
  @dataclass(frozen=True, slots=True)
  class FormRow: id; kinds; applies_to: str; since_major; since_version; description; sources; hypothesis
  @dataclass(frozen=True, slots=True)
  class Note: version: int; rows: tuple[str, ...]; no_row: str | None
  @dataclass(frozen=True, slots=True)
  class Inventory: tokens: tuple[TokenRow, ...]; forms: tuple[FormRow, ...]; notes: tuple[Note, ...]
                   collected_at: tuple[str, ...]
      def match(self, kind: FileKind, chain: Sequence[str], value: str | None = None) -> TokenRow | None
      def form(self, form_id: str) -> FormRow            # KeyError for an unknown id
  def load_inventory(text: str | None = None, *, file: str = "") -> Inventory   # cached for the packaged file
  def min_version(kind: FileKind, token_path: str, *, value: str | None = None) -> int | None
  def min_major(kind: FileKind, token_path: str, *, value: str | None = None) -> int | None
  def check_emittable(node: Node, kind: FileKind, target_major: int) -> tuple[Issue, ...]
  ```
- `src/fenolite/backends/kicad/data/tokens.toml` (package data, loaded through `importlib.resources`).
- `tools/kicad_token_fuzz.py`: `uv run python tools/kicad_token_fuzz.py [--kicad-cli PATH | --docker IMAGE] [--only ID …] (--write DIR | --check DIR) [--timeout S]`. It exits 0 when every outcome matches, 5 on mismatches, 6 when `kicad-cli` is missing or unusable, and 2 on usage errors. Importable functions: `load_examples(text) -> list[Example]`, `exercised_rows(example, inventory, skeletons) -> tuple[str, ...]`, `build_cases(inventory, examples, major) -> list[Case]`, `run_case(case, runner) -> Outcome`, `kicad_env(tmp) -> dict[str, str]`, `sanitise(text, tmp) -> str`, `probe_version(runner) -> str`, `row_levels(inventory, results) -> dict[str, dict[int, Level]]`.
- `tools/gen_token_docs.py` (`--check`).
- `tests/_fuzzmod.py` (loads the harness module for tests, like `tests/_scanmod.py`).
- `tests/unit/backends/kicad/test_versions.py`, `test_rules_text.py`, `test_inventory.py`, `test_check_emittable.py`, `test_token_examples.py`, `test_fuzz_harness.py` (fake runner), `test_token_results.py`, `test_token_docs.py`; `tests/unit/cli/test_library_errors.py`.
- `tests/kicad/test_token_fuzz.py` (`needs_kicad`, `slow`), `tests/kicad/test_environment.py`, `tests/kicad/test_version_constants.py`; `tests/unit/test_kicad_major_marker.py` (`pytester`).
- `tests/corpus/test_fmt_identity_9.py` (`needs_corpus`; see task 5.2).
- `tests/data/kicad/tokens/…` (Decision 12).
- `docs/formats/kicad/versions.md`, `docs/formats/kicad/tokens.md` (generated), `docs/evidence/kicad/token-fuzz/<9.0 version>.json` and `<10.0 version>.json`.

Modified:
- `src/fenolite/cli/errors.py` (three codes) and `src/fenolite/cli/main.py` (mapping).
- `tests/residue/test_no_token_list.py` (allow-list and content check, Decision 19).
- `tests/_resources.py` (`kicad_cli_version`), `tests/conftest.py` (`kicad_min_major`), `pyproject.toml` (marker registration only), `tests/README.md`.
- c0006's `tests/kicad/test_sexpr_oracle.py` and `tests/kicad/test_rt0_oracle.py` (markers and header rewrite, Decision 18); `tests/unit/test_ci_workflow.py` (created by c0006; extended).
- `src/fenolite/backends/kicad/PROVENANCE.md`, `LEGAL-ANNEX.md`, `docs/evidence/sources.md` (S-0030 … S-0039), `docs/hypotheses.md`, `docs/evidence/kicad-fmt-identity.md`, `docs/cli-contract.md` (codes table), `tests/data/MANIFEST.toml`, `.github/workflows/ci.yml`, `CHANGELOG.md`.
- No change to `fenolite.model` or `schemas/`; the wheel already ships every file under `src/fenolite`.

## Evidence level per behaviour (before merge)

| behaviour | level required | how |
|---|---|---|
| Constants: footprint 9/10, board 10, symbol library 9/10, schematic 10 | KICAD-VERIFIED | `test_version_constants.py` (upgrade commands) |
| Constant: worksheet 9/10 | KICAD-VERIFIED | future-boundary probe |
| Constants: board 9, schematic 9, all 8.0 and rules | INFERRED | `H-K-TOK-CONSTANTS` |
| Development versions map to the next release | KICAD-VERIFIED (9: `dev-header-9` on 9.0.9; 10: demos on 10.0.6) | `H-K-TOK-DEV` |
| Board/footprint rows introduced in 10.0, rules rows only in the 10.0 manual | KICAD-VERIFIED on 9.0.9 (attributable rejection) and 10.0.6 (load) | committed fuzz results (`H-K-TOK-RULES-DRIFT` for rules) |
| Board/footprint rows introduced in 9.0 | KICAD-VERIFIED loads on 9.0.9 and 10.0.6; "8.0 cannot read it" stays INFERRED from S-0030 (8.0 is not a target) | committed fuzz results |
| Form rows | KICAD-VERIFIED on both, or INFERRED under their hypothesis | `net-by-name` (`H-K-TOK-NETNAME`) |
| Obsolete rows (`until_major = 9`) | KICAD-VERIFIED on 10.0.6 under header `20260206` | fuzz (`H-K-TOK-OBSOLETE`) |
| Worksheet vocabulary | KICAD-VERIFIED on both (every row exercised) | skeleton and examples (`H-K-TOK-WKS-ORACLE`) |
| Rules rows of the 9.0 manual | KICAD-VERIFIED where exercised, else INFERRED | `H-K-TOK-RULES-FLOOR` |
| Future header, strict and lenient sections | KICAD-VERIFIED on both | controls (`H-K-TOK-FUTURE`, `H-K-TOK-STRICT`) |
| `H-K-00`, `H-K-01`, `H-K-02`, `H-K-03` | KICAD-VERIFIED on both majors | environment tests, CI jobs |
| c0006 lexical mirror on 9.0 (`H-K-SEXPR-LEX`) | KICAD-VERIFIED on 9.0.9 | `kicad-9` job |
| c0006 escapes on 9.0 (`H-K-SEXPR-ESCAPES`) | INFERRED on 9.0 (no `pcb upgrade` in 9.0) | recorded in the row |
| Detection, classification, downgrade refusal, emit check, rules text helpers, CLI mapping, major marker | mechanical (unit tests) | no oracle applies |

## Budget (about 1.5 weeks)

| work | days |
|---|---|
| sources, hypotheses, provenance rows | 0.25 |
| `versions.py` constants, detection, policy, errors, hints, CLI mapping | 1.0 |
| residue allow-list, rules text helpers | 0.25 |
| inventory loader, matcher, `check_emittable` | 1.0 |
| rows: 9.0, 10.0 notes, 10.0 rows, obsolete and form rows, worksheet and rules | 1.5 |
| skeletons, controls, examples | 1.0 |
| harness: case building and attribution; runner, results, Docker | 1.25 |
| major marker and c0006 audit, runs on 10.0.6 and 9.0.9, reconciliation, environment and constants tests | 1.25 |
| CI job, docs page, closing | 0.5 |
| **total** | **8.0** |

The total is half a day over the planned 1.5 weeks. If the budget holds, the first cut is the 9.0 half of the `H-K-FMT-ATOMWRAP` measurement (task 5.2), and the second is any rules floor example beyond the canary (those rows stay INFERRED under `H-K-TOK-RULES-FLOOR`).

## Risks / Trade-offs

- [A 10.0-only token missing from the inventory passes `check_emittable` for target 9, because unmatched board paths count as floor tokens] → every dated version (S-0030) must have a note with rows or a `no_row` reason, which the tests check. The board backend change adds a corpus census that fails when a path seen in 10.0-written files never appears in 9.0-written ones. Typed writers must add a row for everything they emit.
- [9.0 accepts a 10.0 token but ignores it (lenient section)] → the fuzz shows a load where rejection was expected. The row is then set to `older_readers = "ignore"`. Gating still refuses the token for target 9, because ignoring it would lose data.
- [9.0 refuses future headers outright, which would make every negative trivially true] → 10.0 tokens run on 9.0 with 9.0's own header (Decision 13), and the `future-header` control records the behaviour (`H-K-TOK-FUTURE`).
- [A skeleton that does not load under one header would be blamed on the example's token] → one positive baseline per header used, and dependent cases become `inconclusive` (Decision 13).
- [Rules and worksheet oracles report errors only indirectly] → a canary rule and message detection in a fixed locale, each with its own negative control. If a control does not behave as expected, the case is `inconclusive` and the rows stay INFERRED.
- [The 9.0 image is amd64 only; Apple-silicon machines use emulation] → the committed results come from CI or from an emulated local run; the harness never depends on timing.
- [Committed results drift from a new image patch release] → results are keyed by the exact `kicad-cli` version, and the image is pinned by digest. A bump means a new results file in the same pull request.
- [kicad-cli error text may reveal local paths] → `detail` is sanitised and the residue scan runs over `docs/evidence/`.
- [A later change adds a 10.0-only test without the marker] → the `kicad-9` job fails on its pull request; `tests/README.md` documents the marker next to `needs_kicad`.
- [The rules manual's `assign_component_class` shape is not public enough to author an example] → the row is left out and listed as an open question rather than guessed.

## Migration Plan

Nothing to migrate: no persisted data and no model change. Rollback means removing the module, data, tools, tests, the marker and the CI job; the three error codes are additions.

## Open Questions

- Is `assign_component_class` (10.0 rules lexer, S-0034) documented with a usable shape in the 10.0 manual? If not, it stays out of the inventory until the rules reader change.
- Are "tuning profiles" (a 10.0 DRC check name) stored in the board file or the project file? If the board file, a row is added; otherwise the project-file change owns it.
