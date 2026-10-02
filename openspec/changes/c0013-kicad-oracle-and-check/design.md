## Context

- **Scope.** Plan item 0013, part 1 (plan day 19), makes `fenolite check` the product (plan D9): one read-only command that checks a KiCad project and labels each result (v0.1 items 5 and 6). Part 2 (DRC findings as issues, assignment compare, RT2, negative tests) is c0020. Exports and the render stage are c0024. `inspect --summary` moves here from c0009, and `doctor` is the unowned v0.1 item 5.
- **`kicad-cli` writes where it runs.**
  - `pcb drc` and `pcb export` write `<stem>.kicad_prl` next to the board and never rewrite `.kicad_pro` (`H-K-PRO-PRL`, S-0045, S-0020).
  - On 10.0.6, even `kicad-cli <words> --help` creates a configuration folder under `KICAD_CONFIG_HOME` (observed, S-0020).
  - c0009's runner (`kicad-oracle`, "Package kicad-cli runner") copies its inputs into a fresh temporary directory. It strips every `KICAD*` variable, points `KICAD_CONFIG_HOME` at an empty folder inside it, sets `LANG=C` and `LC_ALL=C`, and returns every file the run created or changed, other than that configuration folder, in `CliRun.outputs`. Global library tables and user preferences are therefore absent from every run.
- **Projects.** KiCad reads rules only with a project file next to the board (`H-K-TOK-RULES-SILENT`, S-0038, S-0020) and pairs a board with `<stem>.kicad_pro` and `<stem>.kicad_dru` by stem (S-0045; checked for the copy set by `H-K-CHECK-COPYSET`). The project `fp-lib-table` names footprint libraries, usually as `${KIPRJMOD}/<rel>` (S-0045, S-0046). The drawing sheet is named at `pcbnew.page_layout_descr_file` of the project (c0010 template key; c0012 writes it).
- **Rules.**
  - A rules file with one error is dropped whole, and `pcb drc` still exits 0 (`H-K-TOK-RULES-SILENT`, S-0038, S-0020). A clean report therefore proves nothing about custom rules.
  - When several rules match, the manuals give precedence to the later one (S-0010, S-0038; `H-K-DRU-ORDER`, settled by c0018).
  - c0018's `rulemap.rule_nodes` writes one rule for a major. `SELECTOR_SUPPORT["net"]` holds the majors on which its `dru-cond-net` probe passed (`H-K-DRU-COND`).
- **DRC report.** c0017 adds `KicadCli.drc(board, *, files=None) -> DrcRun`, which runs `pcb drc --format json --severity-all -o <out> <board>` through the runner, and `drc.read_drc_report` with the neutral `DrcReport` in `backends/base.py` (`H-K-DRC-JSON`; key names S-0055, S-0056). Verdicts come only from the report, and `--exit-code-violations` is never passed (c0017, "DRC verdicts come from the JSON report").
- **Command sets.** `pcb import`, `pcb upgrade`, and `pcb drc --refill-zones` and `--save-board` exist only in 10.0 (`H-K-00`, `H-K-01`; S-0022, S-0037). Both majors have `pcb drc --format json --severity-all` and `pcb export ipcd356|pos|svg` (S-0022, S-0037).
- **Strict reader.** Fenolite refuses some boards that KiCad loads: trailing content, a list that starts with a list, a CR inside a string, invalid UTF-8 (`H-K-SEXPR-STRICT`; `tests/data/kicad/sexpr/unmirrored/*`, outcomes in `EXPECT.toml`).
- **Round trip.** RT1 (c0009 Decision 3; `kicad-file-backend`, "Same-version rebuild") holds when the rebuilt tree equals the parsed tree, when the canonical JSON of a re-read equals the first read without provenance, and when `opaque_count` and `opaque_digests` agree. Today RT1 exists only as test code. `sexpr.first_difference(a, b)` (c0006, `kicad-sexpr`) already locates the first differing node.
- **Coordinates.** Board coordinates are 32-bit integers in nm, so items stay within about ±2 147 mm (S-0010).
- **Other tools.** `java -version` prints a version string in the JEP 223 scheme, with the legacy `1.<major>` form before Java 9 (S-0081). `docker --version` prints the client version. `docker version --format '{{.Server.Version}}'` prints the daemon version, and fails when no daemon answers (S-0080).
- **Upstream changes.** The five committed changes are authoritative for the names they create. c0009, c0014 and c0017 were archived on 2026-10-01, so `backend-protocol` (c0017's "Write capability fields" and "Neutral DRC report" included), `kicad-file-backend` ("DRC report reading" included) and the runner and DRC requirements of `kicad-oracle` are living. This change ADDs requirements to them and MODIFIES one, "Write capability fields" as c0010 leaves it (Decision 20). c0018 and c0010 are not archived yet.
  - c0009: `backends/base.py` (`Backend`, `ReadResult` with `.design`, `CapabilityReport`, `BackendOperation`, in which `validate` is reserved for this change by Decision 1), `registry.for_path`, `KicadBackend`, `CAPABILITIES`; `backends/kicad/cli.py` (`find_kicad_cli`, `MACOS_KICAD_CLI`, `KicadCli`, `CliRun`, `KicadCliError`, `KicadCliVersionError`); `pcb.py` (`read_board`, `rebuild_board`, `opaque_count`, `opaque_digests`, `ISSUE_CODES`, `EVIDENCE`); `tests/data/kicad/board/two_layer.kicad_pcb`.
  - c0017: `DrcItem`, `DrcViolation`, `DrcReport`; `drc.read_drc_report`; `KicadCli.drc`, `DrcRun`; `pcb.CANONICAL_ORDER`; "Net form per target"; `tests/kicad/_probes.py` (`PROBES`, `run`, the closed outcomes), `docs/evidence/kicad/probes/<version>.json`, `FENOLITE_PROBES_WRITE=1`; `tests/kicad/board/_triad.py`; `tests/data/libs/Mini_v9.pretty/`; `docs/formats/kicad/drc.md`.
  - c0018: `rulemap.rule_nodes`, `SELECTOR_SUPPORT`, `rule_order`; `dru.parse_rules`; the `rules-model` exemption of diagnostic rules on temporary copies (its Decision 14); `tests/data/kicad/rules/broken.kicad_dru` and `ten_only.kicad_dru`; the hand-over "c0013 appends a canary in its `drc.kicad` stage".
  - c0010: `pro.read_project` (`ProjectInfo.data`), `_json.loads`, `_json.get`, `triad.write_triad`; the `project` corpus rows and `tools/corpus_fetch.py --uses project`.
  - c0011 (sibling, read in its final text; archives before this change): the `cli-contract` rule "Refusals carry their issues" (Decision 12); `libs.write_lib_table(table, *, target)` (Decision 19); `fenolite build` writes the triad, `lib/<nickname>.pretty/`, a `${KIPRJMOD}` `fp-lib-table`, the six layer files under `.fenolite/` (`canonical.dump_texts`, the same bytes as `dump_dir`) and `.fenolite/build.json`; `Power(hv, lv)` becomes `Interface(kind="power", members={"hv": <net id>, "lv": <net id>})`; `examples/blink_2layer/design.py`.
  - Archived: c0008 `libs.read_lib_table` (`LibTable`, `LibRow`); c0007 `versions` (`inspect`, `FormatInfo`, `kind_for_suffix`, `TARGET_MAJORS`, `FutureFormatError`, `UnsupportedFormatError`); c0006 `sexpr` (`parse`, `Node.offset` in UTF-8 bytes, `tree_equal`, `first_difference`) and `FormatError`; c0004 `canonical.dump_dir`, `load_dir`, `LAYER_FILES`, `Design.validate`, `Evidence.combine`, `FENOLITE_NS`; c0002 `Command`, `Result`, `Context` and the FEN registry; c0014 `verify.proposed_ids` and the register guard.
- **Environment.** KiCad 10.0.6 is installed locally. 9.0.9 runs in the pinned image (`kicad-9` job, which fetches no corpus). The `kicad-10` job fetches only `rt0` rows.
- **Constraints.** Stdlib only. `checks` may import only `core`, `model`, `geometry` and `backends.base` (`package-layering`). The roadmap gives this change 7 days.

## Goals / Non-Goals

**Goals:**
- `fenolite check` v0: a fixed pipeline `model.validate` → `erc.lite` → `drc.kicad` → `roundtrip`, with evidence per stage, the envelope at the lowest level, and exit 5 on any error issue.
- Read-only for real: `kicad-cli` sees only a closed copy set, every file under the project keeps its SHA-256 and `st_mtime_ns`, and nothing is created there.
- A clean DRC never counts as proof that custom rules loaded: a canary scoped to its own nets decides it, in the same run.
- `checks` reaches KiCad only through the injected `Validator` and `Oracle`.
- `inspect --summary` and `doctor`: cheap read-only views of one file and of the installed tools.
- The three unknowns (copy set, canary, help grammar) are settled by probes first, each with a fallback decided now.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- `ci-baseline` changes: real demo projects are not fetched in CI (Open Questions).
- Library environment pass-through: `check` runs without global tables (c0021).
- Staleness of `.fenolite/` against the board (c0019).
- A plug-in stage registry, parallel stages, or a cache of DRC results.
- Any change to `capabilities`: it stays static.
- The commands `fenolite export` and `fenolite render`, `fenolite-artifacts.json` and the `render` stage (c0024).
- The runner's Docker mode, and any inspection or pull of images by `doctor`, which only reports `docker` and its daemon version (c0015).
- `examples/board_40parts`, `AGENTS.md` and `agent/SKILL.md` updates, and the v0.1 checklist run (c0025).
- The commands `diff`, `roundtrip`, `fmt`, `explain` and `restore`, and the generated evidence matrix (v0.2a).
- The 9.0 half of `H-K-SEXPR-ESCAPES` (c0018).

## Decisions

1. **Probe-first order.** Three unknowns gate the design: (a) which files `pcb drc` reads; (b) whether a canary placed beyond the board fires and changes nothing else; (c) whether `--help` text yields a reliable command matrix. Task group 2 settles them on 9.0.9 and 10.0.6, with projects assembled in `tmp_path`, pinned as `check-*` probes, before groups 3 to 6 rely on them.
   - Each unknown has a fallback decided now: Decision 3 (copy set), Decisions 5 and 6 (canary), Decision 17 (help grammar).
   - Groups 1, 2.1 and 3.1 depend only on c0009 and c0017, so they can start before c0018 and c0010 merge. Task 3.2 starts after c0010 merges, because it relies on `KicadBackend.lower` and on c0010's membership pins.
   - Rejected: writing the oracle first and probing at the end, the order that made c0006 to c0008 overrun.

2. **Injection through `backends.base`.** `checks` imports only `core`, `model`, `geometry` and `backends.base`, enforced by `tests/unit/test_import_graph.py`. Two protocols carry KiCad into it:
   - `Validator`: the backend operation `validate(path) -> Validation(read, roundtrip)`. `KicadBackend` satisfies it, and `CAPABILITIES.operations` lists `"validate"`.
   - `Oracle`: `name`, `version()` and `drc(project: ProjectSet) -> DrcOutcome`. `KicadOracle` satisfies it.
   - `cli/cmd_check.py` narrows `registry.for_path(board)`, typed `Backend | None`, with `isinstance(backend, Validator)` (`Validator` is `@runtime_checkable`; no validating backend gives `FEN-2001`), and wires it with `KicadOracle(KicadCli(path, timeout=…))`.
   - Pyright proves the fit on real statements: `_VALIDATOR: Validator = KicadBackend()` in `backends/kicad/backend.py`, and the `run_checks(…, oracle=KicadOracle(…))` call in `cmd_check.py`.
   - Facts (the canary state, the files KiCad wrote, the evidence of the run) come from the oracle. Policy (severities, issue codes, statuses) lives in `checks`.
   - Rejected: the roadmap's `netlist` and `upgrade` on the `Oracle` now. Nothing here consumes them, and their neutral result types are c0020's design; c0020 ADDs them to `backend-protocol`.
   - Rejected: `checks` importing `backends.kicad` (a forbidden edge).
   - Rejected: an abstract oracle base class. A `Protocol` keeps backends independent, as c0009 chose for `Backend`.

3. **Copy set planned here, copied by the runner.** `projectset.project_set(path)` returns a `ProjectSet` that maps relative names to source paths, the board included. c0017's `KicadCli.drc(board, files=…)` copies them into c0009's fresh temporary directory; the board goes only in the positional argument, and `files` holds the other entries (Decision 6), because the runner lets a `files` entry override the board of the same name.
   - **Board resolution.** `resolve_board(path)` accepts a `.kicad_pcb`; a `.kicad_pro` (the board of its stem); or a folder with exactly one `.kicad_pro` (the board of its stem), else exactly one `.kicad_pcb`. Several candidates, or none, raise `ProjectResolutionError` (`FEN-2001`) with the candidates. A missing path, or a project without its board, raises `FEN-3001`.
   - **Included.** The board; `<stem>.kicad_pro` and `<stem>.kicad_dru` when present; the top-level `fp-lib-table` (read with c0008's `read_lib_table`) and every library folder a row names as `${KIPRJMOD}/<rel>` inside the root, copied under `<rel>`; the drawing sheet named at `WORKSHEET_POINTER` (read with c0010's `read_project` and `_json.get`) when it is a `${KIPRJMOD}` or relative path inside the root.
   - **Never included.** `.kicad_prl`, `.kicad_sch`, `sym-lib-table`, backups, `fp-info-cache`, `.fenolite/`, `native/` and every other file.
   - **Rows.** A `${KIPRJMOD}` row whose resolved folder lies outside the root is skipped as `outside-root`; another variable as `variable`; a path without a variable as `relative` (`H-K-LIB-RELPATH` is c0021's); a `Table` row as `nested-table`; a folder that does not exist as `missing`; a library folder or drawing sheet whose first path part is `config` as `reserved-name`, because c0009's runner reserves `config` (`CONFIG_DIR`) for `KICAD_CONFIG_HOME` and raises `ValueError` for such a `files` key. Absolute rows and an absolute drawing-sheet path stay as written, and KiCad reads them in place. Disabled rows are left alone. The copied `fp-lib-table` is the user's file, byte for byte.
   - **Size.** `MAX_COPY_BYTES = 256 MiB`. The board, project, rules file and table are always included. The drawing sheet, then the library folders in table order, are skipped as `too-large` when adding them would pass the limit.
   - **Unreadable project.** When `read_project` raises, the project file is still copied (KiCad decides), and the drawing sheet is not looked up.
   - **Reporting.** Each skip is a `SkippedFile(name, reason)`. The `drc.kicad` stage reports it as `check.copy-skipped` (info), and `result.project.skipped` lists it. Skips do not lower the stage evidence: global tables are absent in every run anyway, and this stage claims no library parity.
   - **Fallback.** `H-K-CHECK-COPYSET` compares DRC on the copy set with DRC on a copy of the whole folder. If it is refuted, the missing kind joins the include list; a whole-folder copy under `MAX_COPY_BYTES` is the last resort.
   - Rejected: the roadmap's `KicadCli.project_copy(project_dir)` copying by itself. It would duplicate the runner's temporary-folder lifecycle and clean-up.
   - Rejected: always copying the whole folder (unbounded size; it carries the user's `.kicad_prl` state into the run).
   - Rejected: adding a `{}` project for board-only input. It changes what KiCad reads; the board is checked as KiCad would check it alone.

4. **Read-only by construction and by proof.** `check`, `inspect` and `doctor` are `mutates=False` and return no `PlannedWrite`. `kicad-cli` sees only copies. Canary files are staged in a private temporary folder (`tempfile.mkdtemp(prefix="fenolite-check-")`), which must not lie under the project root, and are removed in a `finally` block.
   - **Proof.** `tests/_projects.py::tree_snapshot(root)` records every path under the root (files and folders, by `lstat`), and the SHA-256 and `st_mtime_ns` of every file. It must be equal before and after the command, and no `.fenolite/`, `native/` or `*.kicad_prl` may appear.
   - At unit level, a fake `kicad-cli` writes `x.kicad_prl` and rewrites its input board. At oracle level, real runs on 9.0.9 and 10.0.6.
   - The files KiCad wrote in the copy are reported by name, sorted, as `summary.tool_writes` of `drc.kicad` (supporting data for `H-K-PRO-PRL`).
   - Rejected: running in place and deleting `.kicad_prl` afterwards (c0009 Decision 2 already rejects it; it would also change folder mtimes).

5. **A scoped canary rule, placed where it governs.** The canary applies only when the copy set holds both `<stem>.kicad_pro` and `<stem>.kicad_dru`; without a rules file there is nothing to prove, and its state is `not-applicable`.
   - **Rule.** `canary_rule_text(major)` builds `Rule(id=derived_id("rul", "kicad", "check-canary"), name=CANARY_RULE_NAME, kind="clearance", selector_a=Selector("net", "FENOLITE_CANARY_A"), min=CANARY_MIN_NM)` (3 mm). It lowers it with c0018's `rulemap.rule_nodes(rule, target=major)`, which returns nodes and issues, and prints the nodes with `sexpr.dumps`. It returns `None` when `SELECTOR_SUPPORT["net"]` lacks the major or `rule_nodes` returns an issue.
   - **Position.** `append_rule(rules, rule_text, *, major)` works on the bytes of the user's file and appends the rule after them, because the later rule governs (`H-K-DRU-ORDER`). If c0018's measurement finds that the earlier rule governs on a major (its Decision 7; `rule_order` follows the measurement), the rule goes right after the `(version N)` node there instead. Either way, the user's bytes are kept and never re-printed, and are never decoded as a whole. A file of whitespace only gets `(version 1)` before the rule. When the `(version N)` offset is needed and the bytes do not parse, the rule is appended at the end: KiCad then drops the broken file, and the verdict `absent` stands.
   - **Tracks.** `inject_board(data)` adds two `segment`s on `F.Cu`, width `CANARY_WIDTH_NM` (0.25 mm), 2 mm long, at y = 0 and y = `CANARY_PITCH_NM` (1 mm). They start at x = M + `CANARY_MARGIN_NM` (25 mm). M is the largest absolute number of the `at`, `xy`, `start`, `end`, `mid` and `center` nodes outside footprints, plus twice the largest one inside footprints, so it bounds every absolute coordinate, rotated footprints included. Their nets are `FENOLITE_CANARY_A` and `FENOLITE_CANARY_B`, and their uuids are `CANARY_UUIDS = (uuid5(FENOLITE_NS, "kicad-canary:A"), uuid5(FENOLITE_NS, "kicad-canary:B"))`. Children follow c0017's `CANONICAL_ORDER["segment"]`, and the net form is the board's own (c0017, "Net form per target").
   - **Text insertion.** `inject_board` takes and returns bytes. The board is parsed with `sexpr.parse_bytes`, which turns invalid UTF-8 into `FormatError` (never `UnicodeDecodeError`), and UTF-8 text is inserted at two byte offsets (`Node.offset` counts UTF-8 bytes). In the numbered net form, two `net` rows with the next two free numbers go before the root child that follows the last root `net` row. The two segments go before the root's closing parenthesis. Every other byte, and every net number, is kept.
   - **Inert by construction.** The gap between the tracks (0.75 mm) violates only the canary rule. Every user item is at least 25 mm away, more than the rule's 3 mm. The rule selects only a net that no user item carries.
   - **Proven per major.** `CANARY_SUPPORT: frozenset[int]` holds the majors on which the probe `check-canary-fired` recorded `present` and `check-canary-broken` recorded `absent`. `CANARY_TWO_RUN: frozenset[int]` holds the majors on which `check-canary-neutral` recorded `different` (Decision 6). Both start empty, and task 2.4 fills them from the committed probe files, as c0018 fills `SELECTOR_SUPPORT`. A unit test keeps the constants and the probe files in step.
   - Rejected: c0018's unconditional bench canary (`_bench.with_canary`). It would flag every user pair closer than 3 mm. c0018's `_bench.py` helpers stay in `tests`, which answers c0018's open item.
   - Rejected: the canary rule first in the file. A later, broad user rule could govern the canary pair and fake "not loaded".
   - Rejected: re-printing the board with `sexpr.dumps`. It changes every byte, so a KiCad verdict would no longer be about the user's file.
   - Rejected: the exit code or stderr as the signal (`H-K-TOK-RULES-SILENT`).
   - Rejected: always two runs, one plain and one with the canary. It doubles the DRC time.
   - Rejected: a separate canary board. It loses rules errors that depend on the board, such as a rule naming a layer the board lacks.

6. **Canary verdict and staging in `KicadOracle.drc`.** The oracle decides the state in this order, before any run:
   1. no `<stem>.kicad_pro` or no `<stem>.kicad_dru` in the copy set: `not-applicable`;
   2. the major is not in `CANARY_SUPPORT`: `inconclusive`, `placement-unproven`;
   3. `canary_rule_text(major)` is `None`: `inconclusive`, `selector-unproven`;
   4. the project sets `/board/design_settings/rule_severities/clearance` to `ignore` (`clearance_ignored`, read with `_json.loads` and `_json.get`; an unreadable project counts as not ignored): `inconclusive`, `clearance-ignored`;
   5. the rules text already contains `CANARY_RULE_NAME`, or the board already has a net named `FENOLITE_CANARY_A` or `FENOLITE_CANARY_B` or an item with a canary uuid: `inconclusive`, `names-taken`;
   6. `inject_board` raises `FormatError` (invalid UTF-8 included): `inconclusive`, `board-unparsed`; it raises `CanaryError` with `extent-too-large` (x + 2 mm over 2 000 mm, inside the range of S-0010) or `no-front-copper` (no `F.Cu` in the layer table): that reason.
   - When the canary applies, the oracle writes the injected board and the augmented rules file into its private folder, under their original names, and calls `KicadCli.drc(<staged board>, files=<project.files without the board key, the rules entry replaced by the staged rules>)`. Otherwise it calls `KicadCli.drc(<original board>, files=<project.files without the board key>)`. The board is never also a key of `files`.
   - After the run: no report gives `inconclusive`, `no-report`; a `clearance` violation whose items are exactly the two canary uuids gives `fired`; any other report gives `absent`.
   - `strip_canary(report)` removes every violation and unconnected item that names a canary uuid (the clearance violation, and any dangling-track warning) and returns their count as `canary_removed`. The stage only ever sees the stripped report.
   - `tool_writes` is the sorted names of `CliRun.outputs` other than the report.
   - `DrcOutcome.evidence`, when a report exists, takes the level and hypotheses of `Evidence.combine(drc.EVIDENCE, oracle.EVIDENCE)` and the oracle `kicad-cli <version>` of the run; `UNVERIFIED` otherwise. c0017's `drc.EVIDENCE` (`H-K-DRC-JSON`) covers the report reader. `oracle.EVIDENCE` (`H-K-CHECK-COPYSET`, `H-K-CHECK-CANARY`) starts `INFERRED` and is raised in task 9.2 only when both rows are `KICAD-VERIFIED (9.0.x, 10.0.x)`, so the stage claims no more than its weakest hypothesis. On a refuted major the constant cites the `-2` successor id. A timeout gives `outcome="timeout"`, `returncode=None` and no report, never an exception.
   - **Fallbacks.** If neutrality fails on a major, that major joins `CANARY_TWO_RUN` and runs DRC twice: a plain run gives the report, the canary run gives the verdict (+0.5 day, taken from the first cut). If the canary does not fire on a major, `CANARY_SUPPORT` lacks it, the state there is `inconclusive` (`placement-unproven`), and the register row records it with a `-2` successor for another placement.
   - Rejected: creating a rules file when the project has none. It proves nothing about the user's rules.
   - Rejected: re-reading a project that Fenolite cannot parse as JSON to find the severity. The conservative reading keeps the run going; a wrong `absent` there is a visible `kicad.drc.rules-not-loaded`, never a silent pass.

7. **Rules verdict to issue.** The codes start with `f"{oracle.name}.drc."`, so `checks` names no backend; the names are the roadmap's.

   | canary state | issue |
   |---|---|
   | `absent` | `rules-not-loaded`: `error` on built input (Fenolite wrote those rules and promised a coherent triad, c0010 Decision 12), `info` on native input (KiCad behaves the same for its user) |
   | `not-applicable` with a `<stem>.kicad_dru` and no `<stem>.kicad_pro` | `rules-not-loaded`, same severities (`H-K-TOK-RULES-SILENT`: no project file, no rules) |
   | `inconclusive` | `rules-unchecked` (warning), with `canary_reason` in the message; none for `no-report`, which gives `check.oracle-failed` |
   | `fired`, or `not-applicable` without a rules file | none |

   - `rules-not-loaded` and `rules-unchecked` set the stage evidence to `UNVERIFIED`.
   - Rejected: `error` on native input. It punishes a state that the project owner may accept, and KiCad would show the same result.

8. **Built or native.** The input is built when `<root>/.fenolite/meta.json` or `<root>/.fenolite/build.json` exists, `<root>` being the board's folder; its model is `canonical.load_dir(<root>/.fenolite)`. `meta.json` is the layer file that `load_dir` needs first, and c0011 says that `build.json` marks a built project; either one is enough. Then `model.validate` and `erc.lite` use the `.fenolite/` model (the plan: "only Fenolite's model (DSL or `.fenolite/`)"), the rules verdict uses built severities, and `roundtrip` still runs on the board.
   - A `.fenolite/` that `load_dir` cannot load gives one `check.cache-unreadable` warning. `model.validate` and `erc.lite` are then skipped (`cache-unreadable`), and the other stages run.
   - `check` never writes `.fenolite/`, and reports no staleness in v0.1 (c0019).
   - Rejected: the board's `generator` atom. A KiCad GUI save rewrites it, which would demote a built project after the first manual move, the v0.1 workflow.
   - Rejected: `.fenolite/build.json` alone as the marker. A `.fenolite/` written by `dump_dir` (tests, later importers) has no build record, yet the stages need only the model.

9. **DRC is counted, not judged, until c0020.** The stage reports the canary verdict and counts the stripped report: `violations`, `by_type`, `by_severity`, `unconnected`, `excluded`, with `summary.violations_judged = false`. The requirement says that `violations_judged` is `true` exactly when the run maps violations to issues, so c0020's `checks/drc_json.py` (per-violation `kicad.drc.<type>` issues with a REF-PIN `where`) sets it to `true` through its own ADDED `verification-loop` requirement, and needs no MODIFIED delta of this one.
   - Rejected: aggregated `kicad.drc.<type>` issues now. That family is c0020's, and an aggregate would force a MODIFIED there. c0011's built blink also carries `unconnected_items` until routing (c0016).
   - Rejected: one aggregate `kicad.drc.violations` issue, which c0020 would have to remove.
   - The gap is internal: the next tag waits for c0019 and c0020.

10. **Pipeline, statuses and evidence per stage.** `STAGE_ORDER` fixes the order of the stages, and `--stages` selects a subset; unselected stages are left out of `result.stages`.
    - `StageStatus` is `ok` (ran, no error issue), `errors` (ran, at least one) or `skipped`, with a `reason` from `native-input`, `read-refused` and `cache-unreadable`.
    - **Stage evidence.** `model.validate` on native input: `Validation.read.evidence` (`pcb.EVIDENCE`: `INFERRED`, `H-K-PCB-READ`); on built input: `INFERRED` (Fenolite's own model rules, no format claim). `erc.lite`: `INFERRED`, `H-K-CHECK-ERC`. `drc.kicad`: `DrcOutcome.evidence`, lowered to `UNVERIFIED` by a rules issue (Decision 7). `roundtrip`: `Validation.read.evidence`. A skipped stage carries `UNVERIFIED`.
    - **Envelope.** `Evidence.combine` of the stages that ran and of the stages skipped for `read-refused` or `cache-unreadable`, because their input failed. A stage skipped for `native-input` does not count. With nothing to combine, the envelope is `UNVERIFIED`.
    - This departs from the roadmap brief ("`Evidence.combine` of the stages that ran"): a refused read or an unreadable cache means part of the input went unchecked, and an envelope from the other stages alone would overclaim.
    - **Result.** `result.project` holds `board`, `built`, `files` and `skipped` (names relative to the root). `result.stages[]` holds `{name, status, reason, evidence, summary}`. Issues go to the envelope's `issues`: the input issues first (`check.read-refused`, `check.cache-unreadable`), then each stage's in stage order.
    - Rejected: `passed`/`failed`. `ok` does not overclaim while DRC is counted only.
    - Rejected: every skipped stage counting as `UNVERIFIED`. By-design skips, such as `erc.lite` on native input, would hide the real level.
    - **Extensible by ADDED requirements.** The requirements fix what this change defines and leave room for later stages and codes: `STAGE_ORDER` holds the four stages in this relative order and admits inserted stages; `ISSUE_CODES` holds at least Decision 11's rows, and every emitted code is a key; `violations_judged` follows Decision 9. c0020 (`netlist.assignment_compare` before `roundtrip`, `kicad.drc.<type>`), c0024 (`render`) and c0015 (`zone.unfilled`) then extend `check` through ADDED requirements, with no MODIFIED delta of these.
    - Rejected: a plug-in stage registry. No third-party stage exists in v0.1; later changes insert their stages by editing `STAGE_ORDER`.
    - Rejected: fixed four-stage and closed-table requirements. Each of c0020, c0024 and c0015 would then need a MODIFIED delta of this change's text.

11. **Issue table.** `checks.codes.ISSUE_CODES` holds every code that `checks` emits, at least the rows below; a later change adds its own rows through an ADDED requirement. `docs/cli-contract.md` documents every key. `model.*` codes and reader codes (`kicad.board.*`, `kicad.version.*`) pass through unchanged and are not in it. A unit test checks that every code literal under `src/fenolite/checks/` is a key of the table.

    | code | severity | when |
    |---|---|---|
    | `check.read-refused` | error | the board read raised a format error (Decision 12) |
    | `check.cache-unreadable` | warning | `.fenolite/` fails `load_dir` |
    | `check.footprint-unresolved` | error | a non-DNP component has an empty `lib_footprint_ref` or no footprint instance |
    | `check.symbol-unresolved` | error | a built component, DNP or not, has an empty `lib_symbol_ref` (a DNP part still has a symbol) |
    | `check.rt1-failed` | error | RT1 failed; `where` is `RoundTrip.difference` |
    | `check.oracle-failed` | error | no DRC report, or a timeout (`retryable: true`) |
    | `check.copy-skipped` | info | a named project file or folder was left out of the copy |
    | `<oracle>.drc.rules-not-loaded` | error (built), info (native) | Decision 7 |
    | `<oracle>.drc.rules-unchecked` | warning | Decision 7 |
    | `erc.lite.output-conflict` | warning | Decision 15 |
    | `erc.lite.power-undriven` | warning | Decision 15 |
    | `erc.lite.floating-pin` | warning | Decision 15 |

    `doctor` has its own three codes (Decision 17): `doctor.tool-missing`, `doctor.tool-unsupported` and `doctor.help-unparsed`, all warnings, kept in `cmd_doctor.ISSUE_CODES`.

12. **Fenolite cannot read, KiCad can** (`H-K-SEXPR-STRICT`). A `FormatError` (`FEN-3004`) from `validator.validate`, or its subclass `UnsupportedFormatError` (`FEN-3003`, a board older than the read floor), becomes `check.read-refused` (error). `FEN-3002` never reaches this path: `read_board` reads a newer board with `kicad.version.future` (living "Board version policy"), and, when `drc.kicad` is selected, Decision 13's pre-flight refuses it with `FEN-6002` before any stage. The message starts with the FEN code, and `where` is the error's own location, `file:locator:@offset` with empty parts left out (as `FormatError` and the living "Library errors map to registered codes" join it), `file` relative to the root.
    - The reader locates some refusals and not others: `list-starting-with-list` and `cr-in-string` carry a locator, while `trailing-content` and `invalid-utf8` carry only the offset. Tests assert the file name and `@<offset>` for every fixture, and the locator only where the reader gives one.
    - Stages that need the board model are skipped (`read-refused`): `roundtrip` always, and `model.validate` on native input. On built input, `model.validate` and `erc.lite` use the `.fenolite/` model and run.
    - `drc.kicad` still runs. When the canary applies, it is `inconclusive` (`board-unparsed`).
    - `check` exits 3 with the read error's code only when no DRC report exists: KiCad failed too, or `drc.kicad` was not selected.
    - **Exit 3 keeps the issues.** The dispatcher builds the envelope of an exception with an empty `issues` list, and c0011's ADDED `cli-contract` requirement "Refusals carry their issues" (archived before this change) fills it from the exception's `issues`. `cmd_check` therefore raises `ReadRefusedError(FormatError)` with the read error's message, `file`, `locator`, `offset` and `hint`, and `issues = CheckReport.issues`. The dispatcher reads `cli_code` from the exception's type, so an `UnsupportedFormatError` becomes `UnsupportedReadRefusedError(ReadRefusedError)` with `cli_code = "FEN-3003"`; a plain `FormatError` keeps the `FEN-3004` fallback. The envelope's `issues` then equal `CheckReport.issues` on exit 3 too: `check.read-refused`, then the issues of the stages that ran on the `.fenolite/` model, and `check.oracle-failed` when KiCad refused as well. `result` stays as the dispatcher builds it for an exception.
    - Rejected: re-raising the read error. Its envelope would have no issues, against "Check stages and statuses".
    - The probe `check-unparsed-drc` records whether KiCad writes a report for `unmirrored/trailing-content.kicad_pcb` on each major.
    - Rejected: exit 3 whenever Fenolite cannot read. It hides the verdict that KiCad can give.
    - Rejected: skipping silently.

13. **Exit codes and pre-flight.** `check` exits 0 without error issues and 5 with any (`FEN-5001`). Usage errors exit 2 (`FEN-2001`: ambiguous folder, unknown or empty stage). A missing path exits 3 (`FEN-3001`), as does Decision 12.
    - **Pre-flight**, when `drc.kicad` is selected, after usage and path errors and before any stage: `find_kicad_cli(--kicad-cli)` must find a binary, else exit 6 with `FEN-6001` and a hint naming `--stages model.validate,erc.lite,roundtrip` and `FENOLITE_KICAD_CLI`. Its major must be in `TARGET_MAJORS`, else `FEN-6002`. When the board parses, its header version (`versions.inspect`) must not be above `FORMAT_VERSIONS[FileKind.BOARD][<tool major>]`, else `FEN-6002`. This covers a header of a newer major and a `FUTURE` header, for which `FormatInfo.major` is `None`. When the board does not parse, this last check is skipped, and a refusal by KiCad becomes `check.oracle-failed`.
    - `--timeout` defaults to 300 s, because DRC of a large board takes longer than the runner's 120 s default.
    - Rejected: skipping DRC with exit 0 when `kicad-cli` is missing. An agent would read it as a pass.
    - Rejected: letting 9.0 fail on a 10.0 board and reporting `check.oracle-failed`. A typed error with a hint is cheaper to act on.

14. **RT1 in `src`.** `backends/kicad/roundtrip.py::rt1(text, *, file="")` implements c0009 Decision 3 exactly:
    - (a) `tree_equal(rebuild_board(read_board(t)), parse(t))`;
    - (b) the canonical JSON of `read_board(dumps(rebuild_board(read_board(t))))` equals that of `read_board(t)`, with every `provenance` set to `None`;
    - (c) equal `opaque_count` and `opaque_digests`.
    - `RoundTrip.difference` is `sexpr.first_difference(rebuilt, parsed)` when (a) fails, else `model` or `opaque`, and `""` when RT1 passes. It is the `where` of `check.rt1-failed`.
    - `KicadBackend.validate(path)` reads the file once, returns `Validation(read, rt1(text))` for a board, and raises `ValueError` naming the kind otherwise. `rt1` raises the reader's errors unchanged.
    - RT1 runs on the board, the layout authority (`design-model`, "Layout authority"), for native and built input alike.
    - Rejected: calling c0009's test helper. Tests are not shipped.
    - Rejected: a new locator function. c0006's `first_difference` already gives the bare `kicad-sexpr` locator.
    - Rejected: comparing the board with `.fenolite/` (c0019's lens).

15. **ERC lite: three warnings on built input, with a removal deadline.** Board-derived pin types (c0009 Decision 12) carry no power flags, so on native input the stage is skipped (`native-input`). Pins of DNP components are ignored.
    - `erc.lite.output-conflict`: a net with two or more member pins whose `etype` is `output` or `power_out`.
    - `erc.lite.power-undriven`: a net with a `power_in` member pin, no `power_out` member pin, and an id that is no value of the `members` of any `Interface` with `kind == "power"` (c0011's `Power(hv, lv)`, which acts as KiCad's power flag).
    - `erc.lite.floating-pin`: a pin whose `etype` is not `no_connect` and that no net lists, reported once per pin (`where` = `REF-PIN`). This follows KiCad's unconnected-pin check (S-0046). The built blink gives one per unused `U1` pin.
    - `REMOVE_IN = (0, 2)` and `check_removal(version)`, which raises `RuntimeError` naming `erc.lite` and `REMOVE_IN` when `version` is at least `REMOVE_IN`. One unit test calls it with `fenolite.__version__` patched to `0.2.0` under `pytest.raises`; another calls it with the live version, so the suite fails once the package reaches 0.2 and the stage is removed or replaced by `sch erc` (v0.2a).
    - Evidence `INFERRED` (`H-K-CHECK-ERC`, pending until `sch erc` replaces the stage).
    - Rejected: error severity. An `INFERRED` heuristic must not fail `check` by itself, and connector-fed rails without `Power()` would.
    - Rejected: `sch erc` now (v0.2a schematic change).

16. **`inspect --summary` is header and counts only, and hermetic.** Boards, footprint files and symbol libraries (file or `.kicad_symdir`) are read through `registry.for_path(FILE).read`. `.kicad_sch` and `.kicad_wks` are parsed and reported header-only through `versions.inspect`, with root-child counts by head; their version status is reported, never raised. `.kicad_pro`, `.kicad_dru` and files that are not S-expressions exit 2 with `FEN-2001` (v0.2a).
    - `counts`: boards `footprints`, `pads`, `nets`, `tracks`, `arcs`, `vias`, `zones`, `fills`, `keepouts`, `graphics`, `texts`; footprints `pads`, `graphics`, `models`; symbol libraries `symbols`, `units`, `pins`; header-only kinds `{head: count}`.
    - `opaque_count` is `pcb.opaque_count` for boards (c0009 Decision 14), `null` otherwise. `model.*` findings are counted by severity in `model_findings`, not reported as issues, so a demo board with duplicate references (`kicad-demo-10-0-6-pcb-08`) still exits 0.
    - Evidence: the reader module's `EVIDENCE`; header-only kinds `INFERRED` (`H-K-TOK-CONSTANTS`).
    - Rejected: `model.*` findings as issues. `inspect` describes a file; `check` judges it.

17. **`doctor` probes; `capabilities` stays static.**
    - **Candidates.** `kicad_cli_candidates(explicit)` lists each `--kicad-cli PATH` (`explicit`), `FENOLITE_KICAD_CLI` (`env`), `kicad-cli` in each `PATH` entry (`path`) and `MACOS_KICAD_CLI` (`macos-app`). It keeps existing files only, deduplicated by resolved path, with the first source. `selected` marks the resolved path of `find_kicad_cli(<first --kicad-cli or None>)`. An explicit path or `FENOLITE_KICAD_CLI` naming a missing file gives `doctor.tool-missing` naming it, because `find_kicad_cli` then returns `None` (living "Package kicad-cli runner", "Missing override").
    - **Matrix.** `MATRIX` is a closed tuple of `MatrixEntry(command, options)`: `pcb drc` (`--format`, `--severity-all`, `--schematic-parity`, `--refill-zones`, `--save-board`), `pcb upgrade`, `pcb import`, `pcb render`, `pcb export` `ipcd356`, `pos`, `svg`, `gerbers`, `drill`, `stats`, `ipc2581` and `odb`, `fp upgrade`, `sym upgrade`, `sch erc`, `sch export netlist`, `jobset run`.
    - `command_matrix(cli)` reads the root page (`kicad-cli --help`), then the page of each group that exists (`pcb`, `pcb export`, `fp`, `sym`, `sch`, `sch export`, `jobset`), then `pcb drc --help` for its options: at most nine pages per binary. A command exists when its last word is a subcommand on its parent's page; an absent parent makes its rows absent without a run.
    - **Grammar.** `parse_help` reads the `Usage:` line: its `{a,b,…}` group gives the subcommands of a group, and its `[--name …]` groups the long options of a leaf. The grammar is recorded in `docs/formats/kicad/cli.md` from observed runs (`H-K-CLI-HELP`). No KiCad or argument-parser source is read, and unit tests use authored synthetic pages.
    - Every `kicad-cli` call, `--help` included, goes through c0009's `KicadCli`. Each row is recorded as the probe `check-help-<words>[-<option>]` (for example `check-help-pcb-drc-refill-zones`), outcome `present` or `absent`.
    - **Java and Docker.** `java -version` (stderr, first line) gives `path`, `version` and `major` per JEP 223 (S-0081): `1.8.0_402` gives 8, `17.0.2` gives 17. `docker --version` gives `path` and `version`; `docker version --format '{{.Server.Version}}'` gives `daemon`, or `null` on a non-zero exit (S-0080). Both run with `subprocess.run` and a 15 s timeout; they are not `kicad-cli`.
    - **Issues.** `doctor.tool-missing` for each absent tool, `doctor.tool-unsupported` for a candidate whose major is not in `TARGET_MAJORS`, `doctor.help-unparsed` naming each page that did not parse. All are warnings, so `doctor` exits 0.
    - `--no-run` lists the candidates and runs no tool. Versions and matrices are then `null`.
    - **Evidence.** Capped by `helpmatrix.EVIDENCE` (`INFERRED`, `H-K-CLI-HELP`, until task 9.2). Each `result.kicad_cli[]` entry that ran carries its own evidence: `helpmatrix.EVIDENCE` with oracle `kicad-cli <version>` when all its pages parsed, else `UNVERIFIED`. The envelope has one oracle, because `Evidence.oracle` is a single string: `helpmatrix.EVIDENCE` with `kicad-cli <version>` of the selected candidate (of the first that ran when none is selected) when every page of every candidate that ran parsed; `UNVERIFIED` otherwise, with `--no-run`, or when no candidate ran.
    - **Fallback.** If `H-K-CLI-HELP` is refuted on a major, the row gets a `-2` successor, the parser follows the measured form, and rows whose detection no probe confirmed report `"unknown"`.
    - Rejected: a hard-coded matrix per major. It would not detect a changed binary.
    - Rejected: walking the whole help tree with committed matrix files. More pages and files, and no consumer.
    - Rejected: extending `capabilities`. It is static and hermetic by contract; `doctor` is where tools run.

18. **Determinism.** Two `check --json` runs on the same project with the same `kicad-cli` give byte-identical stdout apart from `elapsed_ms`.
    - Left out: the report `date`, temporary paths, the home directory and absolute paths. `input.path` is the board name relative to the project root, and every other path is too.
    - Fixed orders: stages by `STAGE_ORDER`; issues within a stage by code, `where`, then message; `project.files`, `project.skipped`, `tool_writes` and the keys of `by_type` and `by_severity` sorted.
    - The canary uuids and net numbers are deterministic (Decision 5).

19. **Proof matrix without a new committed board.** Hermetic unit tests with fakes cover every mechanism: a fake `kicad-cli` (`tests/_fakecli.py`), and fake `Validator` and `Oracle` classes in `tests/unit/checks/`.
    - Every hermetic test of `check` and `doctor` patches `cli.MACOS_KICAD_CLI` to a missing path, as `tests/unit/cli/test_capabilities.py` and `test_cli_runner.py` already do: `find_kicad_cli` and `kicad_cli_candidates` also look at the macOS bundle, which exists on the development machine. Otherwise a real KiCad would run inside a unit test, and "No kicad-cli" would not exit 6.
    - `tests/_projects.py::authored_project(tmp_path, *, major, built=False, rules="one-rule", project=True, decoys=True, cli=None)` writes into `tmp_path`: c0010's `write_triad` of c0017's triad design for the major; `libs/Mini.pretty` (10) or `libs/Mini_v9.pretty` (9) with a `${KIPRJMOD}` `fp-lib-table` written by c0011's `libs.write_lib_table(table, target=major)`, the per-target form that KiCad reads (`H-K-BUILD-LIBTABLE`; target 9 bare atoms and no version, target 10 `(version 7)` and quoted atoms), never by hand; decoys (`notes.txt`, a `sym-lib-table` and a `.kicad_prl`). With a `cli`, the `.kicad_prl` is the one KiCad wrote in a first run (`CliRun.outputs`); without one, hermetic tests get an authored minimal JSON file. The built variant gives each component a `lib_symbol_ref` and writes `.fenolite/` with `dump_dir`, so the clean project has no error issue.
    - `rules` is `"one-rule"` (one authored clearance rule on a user net), `"broken"` (c0018's `broken.kicad_dru`, or `ten_only.kicad_dru` on 9.0.9 if `H-K-DRU-QUOTE` is refuted there) or `None`.
    - The native variant is `two_layer.kicad_pcb` with a `{}` project and the authored one-rule file.
    - `demo_project(tmp_path, item)` puts a cached `rt0` demo board in a folder with a `{}` project and a `(version 1)` rules file.
    - Only `tests/kicad/check/test_check_built.py` needs c0011's `build`. `tests/_projects.py` needs c0011's `write_lib_table`, and the exit-3 envelope test of task 6.1 its dispatcher rule; the roadmap already orders c0011 before this change. Demo boards run on 10.0.6 in `kicad-10`; real demo projects (c0010's `project` rows) run locally, and the run is recorded in `docs/evidence/kicad-check.md` (counts only).
    - Every 9.0.9 proof uses projects assembled in `tmp_path`, so the `kicad-9` no-corpus rule holds.
    - **Example arguments from any folder.** `tests/consistency/test_cli_consistency.py` runs each command's `example_args` in the current working directory, and c0011's scenario "Consistency suite" runs it from a temporary one. `check` and `inspect` therefore take `cli/_examples.EXAMPLE_BOARD`, the absolute path of `two_layer.kicad_pcb` resolved from `fenolite.__file__` at import, as c0011 locates `_minimal.py` through `fenolite.dsl.__file__`. The suite runs only from a source checkout, where the path exists. Output stays deterministic: `input.path` and `result.project` names are relative to the board's folder, and `inspect` reports the file name only in `input.path`. `test_hermetic_examples.py` changes to an empty `tmp_path` before it runs the examples.
    - Rejected: a packaged copy of the board. Two copies of one fixture, and a board in the wheel with no other consumer.

20. **No new FEN code, no model change, no ADR, and one MODIFIED delta.** Usage errors reuse `FEN-2001`, missing input `FEN-3001`, read errors their own codes (`FEN-3002` to `FEN-3004`), findings `FEN-5001`, tools `FEN-6001` and `FEN-6002`. `Design`, `Issue`, `Evidence` and the layer files are used as they are, and `tools/gen_schemas.py --check` stays clean. The new neutral types live in `backends/base.py`, and stage results only in the envelope's `result`.
    - **The one MODIFIED delta.** c0010 MODIFIES "Write capability fields" first (c0017's exact pin becomes membership with `lower`), and its scenario "Write operation advertised and implemented" says that `validate` is still absent. This change's ADDED "Validation operation" contradicts that text, so `specs/backend-protocol/spec.md` MODIFIES it again.
      - Base: c0010's MODIFIED version of this requirement, which archives before this change. It turns the exact tuple into membership, adds `lower` and the generic `lower(design, *, name, target=None, allow_lossy=False, issues=None) -> dict[str, str]` contract, and ties `KicadBackend.lower` to `write_triad`. c0018 leaves `operations` unchanged; c0011 and c0012 have no `backend-protocol` delta.
      - Change: `validate` joins `operations` exactly when the backend satisfies `Validator`; everything c0010 states (membership, `lower` and its contract) is kept word for word. This is what the living "Capability reports" already says ("`operations` MUST list exactly the operations the backend implements"). The order of the tuple is not pinned.
      - Scenarios: "KiCad write fields in capabilities" checks membership; "Write operation advertised and implemented" checks that every other listed operation is a callable method; the new "Later operations by membership" checks that `lower` and `validate` are listed and callable. "Default target among the targets" and "Write result is immutable" are copied unchanged.
      - Because this text contains all of c0010's, archiving this change after c0010 undoes nothing. Task 9.1 still re-checks it against the version living at this change's archive.
      - Tests: task 3.2 updates the three pinned tests (`test_registry.py::test_kicad_capability_report`, `test_base_types.py::test_capability_write_advertised_and_implemented`, `test_capabilities_backends.py`) in the same commit as `validate`.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/base.py` (c0009; extended) | `@dataclass(frozen=True, slots=True) class RoundTrip(level: Literal["RT1"], passed: bool, tree_equal: bool, model_equal: bool, opaque_equal: bool, opaque_count: int, difference: str = "")` (`ValueError` when `passed` is not the conjunction of the three); `class Validation(read: ReadResult, roundtrip: RoundTrip)`; `@runtime_checkable class Validator(Protocol)`: `name: str`, `validate(path: Path, *, issues: list[Issue] \| None = None) -> Validation`; `SkipReason = Literal["outside-root", "variable", "relative", "missing", "nested-table", "too-large", "reserved-name"]`; `class SkippedFile(name: str, reason: SkipReason)`; `class ProjectSet(root: Path, board: str, files: Mapping[str, Path], skipped: tuple[SkippedFile, ...] = (), has_project: bool = False, has_rules: bool = False)` (`ValueError` when `board` is not a key of `files` or a key is not a relative POSIX name); `CanaryState = Literal["fired", "absent", "inconclusive", "not-applicable"]`; `class DrcOutcome(report: DrcReport \| None, tool_version: str, canary: CanaryState, canary_reason: str = "", canary_removed: int = 0, tool_writes: tuple[str, ...] = (), outcome: Literal["exit", "timeout"] = "exit", returncode: int \| None = 0, message: str = "", evidence: Evidence = Evidence())`; `class Oracle(Protocol)`: `name: str`, `version() -> str`, `drc(project: ProjectSet) -> DrcOutcome`. All dataclasses frozen. |
| `src/fenolite/backends/kicad/roundtrip.py` (new) | `rt1(text: str, *, file: str = "") -> RoundTrip` |
| `src/fenolite/backends/kicad/backend.py` (c0009; extended) | `KicadBackend.validate(path: Path, *, issues: list[Issue] \| None = None) -> Validation`; `CAPABILITIES.operations` gains `"validate"`; `_VALIDATOR: Validator = KicadBackend()` (checked by pyright) |
| `src/fenolite/backends/kicad/projectset.py` (new) | `MAX_COPY_BYTES = 256 * 2**20`; `WORKSHEET_POINTER = "/pcbnew/page_layout_descr_file"`; `class ProjectResolutionError(FenoliteError)` (`cli_code = "FEN-2001"`, `candidates: tuple[str, ...]`, `hint`); `class ProjectNotFoundError(FenoliteError)` (`cli_code = "FEN-3001"`); `resolve_board(path: Path) -> Path`; `project_set(path: Path, *, max_bytes: int = MAX_COPY_BYTES) -> ProjectSet` |
| `src/fenolite/backends/kicad/canary.py` (new) | `CANARY_NETS = ("FENOLITE_CANARY_A", "FENOLITE_CANARY_B")`; `CANARY_UUIDS: tuple[str, str]`; `CANARY_RULE_NAME = "fenolite_check_canary"`; `CANARY_MIN_NM = 3_000_000`; `CANARY_WIDTH_NM = 250_000`; `CANARY_PITCH_NM = 1_000_000`; `CANARY_LENGTH_NM = 2_000_000`; `CANARY_MARGIN_NM = 25_000_000`; `CANARY_MAX_X_NM = 2_000_000_000`; `CANARY_SUPPORT: frozenset[int]`; `CANARY_TWO_RUN: frozenset[int]`; `CanaryReason = Literal["placement-unproven", "selector-unproven", "clearance-ignored", "names-taken", "board-unparsed", "extent-too-large", "no-front-copper", "no-report"]`; `class CanaryError(FenoliteError)` (`reason: CanaryReason`); `canary_rule_text(major: int) -> str \| None`; `append_rule(rules: bytes, rule_text: str, *, major: int) -> bytes` (raises `CanaryError("names-taken")`); `inject_board(data: bytes, *, file: str = "") -> bytes` (raises `FormatError`, invalid UTF-8 included, or `CanaryError`); `clearance_ignored(project_text: str) -> bool`; `canary_fired(report: DrcReport) -> bool`; `strip_canary(report: DrcReport) -> tuple[DrcReport, int]` |
| `src/fenolite/backends/kicad/oracle.py` (new) | `class KicadOracle`: `__init__(self, cli: KicadCli)`, `name = "kicad"`, `version() -> str`, `major() -> int`, `drc(project: ProjectSet) -> DrcOutcome`; `EVIDENCE: Evidence` (`INFERRED`, `H-K-CHECK-COPYSET`, `H-K-CHECK-CANARY`, until task 9.2); `DrcOutcome.evidence` is `Evidence.combine(drc.EVIDENCE, EVIDENCE)` with the oracle `kicad-cli <version>` of the run |
| `src/fenolite/backends/kicad/cli.py` (c0009; extended) | `CandidateSource = Literal["explicit", "env", "path", "macos-app"]`; `@dataclass(frozen=True, slots=True) class CliCandidate(path: Path, source: CandidateSource)`; `kicad_cli_candidates(explicit: Sequence[str \| os.PathLike[str]] = ()) -> tuple[CliCandidate, ...]` |
| `src/fenolite/backends/kicad/helpmatrix.py` (new) | `@dataclass(frozen=True, slots=True) class MatrixEntry(command: tuple[str, ...], options: tuple[str, ...] = ())`; `MATRIX: tuple[MatrixEntry, ...]`; `class HelpPage(subcommands: frozenset[str], options: frozenset[str])`; `parse_help(text: str) -> HelpPage \| None`; `row_key(command: tuple[str, ...], option: str = "") -> str` (`"pcb drc --refill-zones"`); `probe_id(command: tuple[str, ...], option: str = "") -> str` (`"check-help-pcb-drc-refill-zones"`); `class CommandMatrix(version: str, rows: Mapping[str, bool], unparsed: tuple[str, ...])`; `command_matrix(cli: KicadCli) -> CommandMatrix`; `EVIDENCE: Evidence` (`INFERRED`, `H-K-CLI-HELP`, until task 9.2) |
| `src/fenolite/checks/__init__.py` (new) | re-exports `STAGE_ORDER`, `StageResult`, `CheckReport`, `run_checks`, `ISSUE_CODES` |
| `src/fenolite/checks/stages.py` (new) | `STAGE_ORDER = ("model.validate", "erc.lite", "drc.kicad", "roundtrip")` (later changes may insert stages); `StageStatus = Literal["ok", "errors", "skipped"]`; `StageSkip = Literal["native-input", "read-refused", "cache-unreadable"]`; `@dataclass(frozen=True, slots=True) class StageResult(name: str, status: StageStatus, evidence: Evidence, issues: tuple[Issue, ...] = (), summary: Mapping[str, object] = field(default_factory=dict), reason: str = "")` with `to_json() -> dict[str, object]`; `class CheckReport(stages: tuple[StageResult, ...], issues: tuple[Issue, ...], evidence: Evidence, read_error: FenoliteError \| None = None, drc_reported: bool = False)`; `run_checks(*, project: ProjectSet, stages: Sequence[str], model: Design \| None, built: bool, validator: Validator \| None, oracle: Oracle \| None, cache_error: str = "") -> CheckReport` |
| `src/fenolite/checks/validate.py` (new) | `validate_stage(design: Design, *, built: bool, evidence: Evidence) -> StageResult` |
| `src/fenolite/checks/erc_lite.py` (new) | `ERC_RULES = ("output-conflict", "power-undriven", "floating-pin")`; `erc_lite(design: Design) -> tuple[Issue, ...]`; `erc_stage(design: Design) -> StageResult`; `EVIDENCE` (`INFERRED`, `H-K-CHECK-ERC`); `REMOVE_IN = (0, 2)`; `check_removal(version: str) -> None` (raises `RuntimeError` from `REMOVE_IN` on) |
| `src/fenolite/checks/drc.py` (new) | `drc_stage(oracle: Oracle, project: ProjectSet, *, built: bool) -> StageResult` |
| `src/fenolite/checks/roundtrip.py` (new) | `roundtrip_stage(validation: Validation) -> StageResult` |
| `src/fenolite/checks/codes.py` (new) | `ISSUE_CODES: Mapping[str, tuple[Severity, ...]]` (at least Decision 11's rows, with the literal prefix `<oracle>`); `oracle_code(oracle: str, suffix: str) -> str` |
| `src/fenolite/cli/cmd_check.py` (new) | `class ReadRefusedError(FormatError)` (`issues: tuple[Issue, ...]`; `FEN-3004` through the `FormatError` fallback); `class UnsupportedReadRefusedError(ReadRefusedError)` (`cli_code = "FEN-3003"`) (Decision 12); `COMMAND` (`check`, `mutates=False`; `PATH`, `--stages`, `--kicad-cli PATH`, `--timeout SECONDS`; `example_args = (EXAMPLE_BOARD, "--stages", "model.validate,erc.lite,roundtrip")`) |
| `src/fenolite/cli/cmd_inspect.py` (new) | `COMMAND` (`inspect`, `mutates=False`; `FILE`, `--summary`; `example_args = (EXAMPLE_BOARD, "--summary")`) |
| `src/fenolite/cli/_examples.py` (new; no `cmd_` prefix, so `discover` skips it) | `EXAMPLE_BOARD: str`, the absolute path `Path(fenolite.__file__).resolve().parents[2] / "tests/data/kicad/board/two_layer.kicad_pcb"` (Decision 19) |
| `src/fenolite/cli/cmd_doctor.py` (new) | `COMMAND` (`doctor`, `mutates=False`; `--kicad-cli PATH` repeatable, `--no-run`; `example_args = ("--no-run",)`); `ISSUE_CODES`; `java_major(version_line: str) -> int \| None`; `java_info(path: Path) -> dict[str, object]`; `docker_info(path: Path) -> dict[str, object]` |
| `src/fenolite/backends/kicad/PROVENANCE.md` | rows of task 1.2 |
| `tests/_projects.py` (new) | `authored_project(tmp_path: Path, *, major: int, built: bool = False, rules: Literal["one-rule", "broken"] \| None = "one-rule", project: bool = True, decoys: bool = True, cli: KicadCli \| None = None) -> Path`; `native_project(tmp_path: Path, *, rules: Literal["one-rule", "broken"] \| None = "one-rule") -> Path`; `demo_project(tmp_path: Path, item: CorpusItem) -> Path`; `tree_snapshot(root: Path) -> dict[str, tuple[str, str, int]]` |
| `tests/_fakecli.py` (new) | `fake_kicad_cli(folder: Path, *, version: str = "10.0.6", help_pages: Mapping[str, str] \| None = None, drc_report: str \| None = None, writes: Sequence[str] = (), rewrite_input: bool = False, sleep: float = 0.0) -> Path` (a `#!/bin/sh` wrapper around a Python script, as in c0009's runner tests) |
| `tests/unit/backends/test_base_types.py` (extended); `tests/unit/backends/kicad/test_roundtrip.py`, `test_projectset.py`, `test_canary.py`, `test_oracle.py`, `test_helpmatrix.py`, `test_cli_candidates.py` (new) | hermetic tests |
| `tests/unit/checks/` (new: `fakes.py`, `test_stages.py`, `test_validate_stage.py`, `test_erc_lite.py`, `test_drc_stage.py`, `test_roundtrip_stage.py`, `test_codes.py`) | hermetic tests with fake `Validator` and `Oracle` |
| `tests/unit/cli/test_check_cmd.py`, `test_check_readonly.py`, `test_inspect_cmd.py`, `test_doctor_cmd.py`, `test_hermetic_examples.py` (new); `tests/unit/backends/test_registry.py`, `tests/unit/backends/test_base_types.py`, `tests/unit/cli/test_capabilities_backends.py` (updated pins; Decision 20) | hermetic tests |
| `tests/kicad/check/test_help_matrix.py`, `test_copy_set.py`, `test_canary.py`, `test_check_oracle.py`, `test_read_refused.py`, `test_check_built.py`, `test_check_demos.py` (new) | `needs_kicad`, major-aware; demos `needs_corpus` and `slow` |
| `tests/kicad/_probes.py` (c0017; rows added); `docs/evidence/kicad/probes/9.0.9.json`, `10.0.6.json` (regenerated) | probes `check-copyset`, `check-canary-fired`, `check-canary-neutral`, `check-canary-broken`, `check-canary-ignored`, `check-unparsed-drc`, `check-help-*` |
| `docs/formats/kicad/cli.md` (new) | help grammar, matrix rows per version, the `--help` side effect, copy-set facts; fact tables with sources, labels and hypotheses |
| `docs/formats/kicad/drc.md` (c0017; section added) | "Check canary": rule, placement, verdict, stripping, reasons |
| `docs/cli-contract.md` | `check`, `inspect`, `doctor`; the stage table and the issue tables |
| `docs/evidence/kicad-check.md` (new) | the local demo-project run: stage statuses, canary states, `tool_writes`, timings; counts only |

Layering: `backends.base` still imports only `core` and `model`. `backends.kicad.{roundtrip,projectset,canary,oracle,helpmatrix}` import `core`, `model`, `backends.base` and modules of their own package (`pcb`, `sexpr`, `versions`, `libs`, `pro`, `_json`, `rulemap`, `drc`, `cli`); none of them is imported by `pcb`, `rulemap` or `pro`, so there is no cycle. `checks` imports `core`, `model` and `backends.base` only. The commands import `checks`, `backends` and `model`. Every edge stays within `package-layering`, unchanged.

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0080 | https://docs.docker.com/reference/cli/docker/version/ | to verify on the page | `docker version` and its `--format` template: the client version, and `{{.Server.Version}}` for the daemon, which fails when no daemon answers (`doctor`) |
| S-0081 | https://openjdk.org/jeps/223 | to verify on the page | the Java version-string scheme from Java 9 on (`$MAJOR.$MINOR.$SECURITY`) and the legacy `1.<major>` form before it (`doctor`) |

Rows of other changes cited here: S-0010 (rule precedence, coordinate range), S-0020 (observed `kicad-cli` 10.0.6 behaviour), S-0022 and S-0037 (CLI manuals 10.0 and 9.0), S-0024 and S-0058 (demo files), S-0066 (template projects, c0010), S-0038 (custom rules), S-0045 (project files, configuration folders), S-0046 (library tables; the unconnected-pin check of the schematic editor), S-0055 and S-0056 (DRC report keys, c0017). Task 1.1 widens the "used for" cell of S-0020 (help pages and their `Usage:` grammar on 10.0.6, the configuration folder that `--help` writes under `KICAD_CONFIG_HOME`, and KiCad reports on boards Fenolite refuses), S-0022 and S-0037 (help pages and the command matrix), S-0038 (the check canary), S-0045 (stem pairing, `.kicad_prl`, the configuration folder written by `--help`) and S-0046 (library rows in the copy set, ERC lite). If a URL above is already registered when this change is implemented, the existing id is cited and the row is not duplicated. S-0082 to S-0084 stay unused. No KiCad source file is read for this change: help text comes from running the binary (S-0020) and from the published manuals.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-CHECK-COPYSET | `kicad-cli pcb drc` reads only the board, `<stem>.kicad_pro`, `<stem>.kicad_dru`, the project `fp-lib-table` and the `${KIPRJMOD}` library folders it names, so DRC on that copy set equals DRC on a copy of the whole project folder (S-0045, S-0022, S-0037) | `tests/kicad/check/test_copy_set.py::test_copy_set_equals_folder` | for the authored built project with a KiCad-written `.kicad_prl`, a `sym-lib-table` and `notes.txt`: equal multisets of (type, severity, excluded, sorted item uuids) over violations and unconnected items, on 9.0.9 and 10.0.6; probe `check-copyset` = `equal`; the local demo-project run on 10.0.6 is supporting data |
| H-K-CHECK-CANARY | A `clearance` rule selecting net `FENOLITE_CANARY_A`, appended after the user's rules, fires exactly once on two 0.25 mm `F.Cu` tracks 1 mm apart placed 25 mm beyond every board coordinate; it gives no canary violation when the rules file is dropped or the project sets the `clearance` severity to `ignore`; and every other violation is unchanged once the violations naming a canary uuid are removed (S-0010, S-0038) | `tests/kicad/check/test_canary.py::test_canary_fires`, `::test_canary_neutral`, `::test_canary_broken_rules`, `::test_canary_ignored` | on 9.0.9 and 10.0.6 for the authored built project and the native `two_layer` project, and on 10.0.6 for the 21 readable non-heavy demo boards with a `{}` project and a `(version 1)` rules file: one canary `clearance` violation; equal multisets without canary uuids against a run without the canary; no canary violation with `broken.kicad_dru` (`ten_only.kicad_dru` on 9.0.9 if `H-K-DRU-QUOTE` is refuted there) or with the severity set to `ignore`; probes `check-canary-fired` = `present`, `check-canary-neutral` = `equal`, `check-canary-broken` = `absent`, `check-canary-ignored` = `absent`. A major where neutrality fails takes the two-run fallback of Decision 6, recorded in the row |
| H-K-CLI-HELP | `kicad-cli <words> --help` exits 0 and prints a `Usage:` line whose `{a,b,…}` group lists a group's subcommands and whose `[--name …]` groups list a leaf's long options, so the matrix read from help text matches the documented command sets (S-0022, S-0037; observed on 10.0.6, S-0020) | `tests/kicad/check/test_help_matrix.py::test_matrix_matches_facts` | every page that `command_matrix` reads parses on 9.0.9 and 10.0.6; `pcb import`, `pcb upgrade`, and `pcb drc --refill-zones` and `--save-board` are present exactly on 10.0.6, agreeing with `H-K-00` and `H-K-01`; `pcb drc --format`, `--severity-all`, `pcb export ipcd356`, `pos` and `svg` are present on both; every row is recorded as a `check-help-*` probe |
| H-K-CHECK-ERC | Each `erc.lite` finding on an authored circuit matches a `kicad-cli sch erc` violation on the same pins of the same circuit drawn as a schematic, with `Interface(kind="power")` acting as a power flag (S-0046) | placeholder `tests/kicad/sch/test_erc_lite_vs_sch_erc.py::test_erc_lite_subset` (v0.2a schematic change) | one `sch erc` violation per finding, on the same pins, on 10.0.6; the row closes when `sch erc` replaces `erc.lite` |

The register rows get backend `kicad`, level `INFERRED` and result `pending` in task 1.1. The first three rows gate the design, each with the fallback of Decisions 3, 6 and 17; `erc.lite` does not depend on `H-K-CHECK-ERC`, which only bounds its claim. Ids used without changing their level: `H-K-SEXPR-STRICT` (supporting data from the probe `check-unparsed-drc`), `H-K-TOK-RULES-SILENT` (the broken-rules control under `check`), `H-K-PRO-PRL` (`tool_writes`), `H-K-TOK-RULES-SILENT` (rules need a project file next to the board), `H-K-DRC-JSON`, `H-K-DRU-ORDER`, `H-K-DRU-COND`, `H-K-DRU-QUOTE`, `H-K-PCB-READ`, `H-K-TOK-CONSTANTS`, `H-K-LIB-RELPATH`, `H-K-BUILD-LIBTABLE` (c0011), `H-K-00` and `H-K-01`. No id owned by c0012, c0015 or c0020 is cited.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Copy set equals the folder | KICAD-VERIFIED (9.0.x, 10.0.x), `H-K-CHECK-COPYSET` | `test_copy_set.py`; probe `check-copyset` |
| Canary fires, stays neutral, is silenced by a dropped file or an ignored severity | KICAD-VERIFIED (9.0.x, 10.0.x), `H-K-CHECK-CANARY` | `test_canary.py`; four `check-canary-*` probes |
| Help grammar and matrix rows | KICAD-VERIFIED (9.0.x, 10.0.x), `H-K-CLI-HELP` | `test_help_matrix.py`; `check-help-*` probes |
| `drc.kicad` stage | `Evidence.combine(drc.EVIDENCE, oracle.EVIDENCE)`, oracle `kicad-cli <version>`, when a report exists and the canary fired or no rules file exists (KICAD-VERIFIED once `H-K-DRC-JSON`, `H-K-CHECK-COPYSET` and `H-K-CHECK-CANARY` are); UNVERIFIED otherwise | `test_check_oracle.py`, `test_check_built.py` on 9.0.9 and 10.0.6 |
| Rules verdict (built error, native info, rules without a project) | KICAD-VERIFIED (9.0.x, 10.0.x) for the three cases | `test_check_oracle.py -k rules` |
| KiCad reports on boards Fenolite refuses | observed per major and recorded; supporting data for `H-K-SEXPR-STRICT`, whose level stays | `test_read_refused.py`; probe `check-unparsed-drc` |
| Read-only guarantee | mechanical (fake `kicad-cli`), observed with 9.0.9 and 10.0.6 and on 21 demo boards | `test_check_readonly.py`, `test_check_oracle.py -k read_only`, `test_check_demos.py` |
| RT1 in `src`, `roundtrip` stage | mechanical (unit tests); the stage carries the reader's INFERRED (`H-K-PCB-READ`); RT1 on 21 demo boards is supporting data | `test_roundtrip.py`, `test_check_demos.py` |
| `model.validate` | native: INFERRED (`H-K-PCB-READ`); built: INFERRED (model rules, no format claim) | `tests/unit/checks -k validate_stage` |
| `erc.lite` | INFERRED (`H-K-CHECK-ERC`, pending) | `tests/unit/checks -k erc_lite` |
| `inspect --summary` | the reader's level; header-only kinds INFERRED (`H-K-TOK-CONSTANTS`) | `test_inspect_cmd.py` |
| `doctor` matrix | `helpmatrix.EVIDENCE` (KICAD-VERIFIED once `H-K-CLI-HELP` is), oracle of the selected candidate, when every page parsed; UNVERIFIED otherwise and with `--no-run` | `test_doctor_cmd.py`, `test_help_matrix.py` |
| Java and Docker detection | mechanical (no format claim; S-0080, S-0081) | `test_doctor_cmd.py` |
| Determinism | mechanical, observed with 9.0.9 and 10.0.6 | `test_check_oracle.py -k deterministic` |

`canary.CANARY_SUPPORT` lists a major only when its probes pass on that major. `helpmatrix.EVIDENCE` starts `INFERRED` and becomes `KICAD-VERIFIED` in task 9.2 only when `H-K-CLI-HELP` is `KICAD-VERIFIED (9.0.x, 10.0.x)`; `doctor` never claims more. `oracle.EVIDENCE` starts `INFERRED` and becomes `KICAD-VERIFIED` in task 9.2 only when `H-K-CHECK-COPYSET` and `H-K-CHECK-CANARY` are `KICAD-VERIFIED (9.0.x, 10.0.x)`; the `drc.kicad` stage combines it with c0017's `drc.EVIDENCE`, so lowest wins. A constant whose row is refuted on a major cites the `-2` successor id there. This change does not merge while `H-K-CHECK-COPYSET`, `H-K-CHECK-CANARY` or `H-K-CLI-HELP` is below `KICAD-VERIFIED` on 9.0.9 or 10.0.6, unless the fallback of Decision 3, 6 or 17 is applied and recorded for that major.

## Budget (about 1.75 weeks; the roadmap gives 7 days)

| work | days |
|---|---|
| sources, hypotheses, provenance, `cli.md` skeleton | 0.5 |
| probes: help grammar and `check-help-*` | 0.5 |
| probes: copy set, `tests/_projects.py` | 0.5 |
| probes: canary (fired, neutral, broken, ignored, unparsed) | 1.0 |
| neutral types, RT1 in `src`, `validate` | 0.75 |
| `KicadOracle`, fake `kicad-cli` | 0.5 |
| `checks` package | 1.25 |
| `check` command | 0.75 |
| `inspect` | 0.5 |
| `doctor`, candidates | 0.5 |
| oracle proofs, built blink, demo boards | 1.0 |
| docs | 0.25 |
| closing | 0.5 |
| **total** | **8.5** |

The overrun against the roadmap's 7 days (the plan's "check 1.5" line shared with c0020, plus the `check`/`inspect`/`doctor` share of "cli 1") is stated here and in the proposal. Cut order: (1) the local demo-project run moves to c0020; (2) the `MATRIX` shrinks to the `H-K-00`/`H-K-01` rows plus versions; (3) `inspect` keeps boards only; (4) demo canary-neutrality runs stop at 5 boards. The two-run fallback of Decision 6 (+0.5 day), if needed, is paid by cut (1). Not optional: the read-only proofs, the copy set, the canary with its broken-rules control on both majors, the `roundtrip` stage, the read-refused path, the injection layering and `doctor` detection.

## Risks / Trade-offs

- [The canary does not fire beyond the board, or changes another violation] → settled first by `H-K-CHECK-CANARY` in task group 2; text insertion keeps every user byte and net number; `CANARY_SUPPORT` and `CANARY_TWO_RUN` carry the outcome per major (Decision 6).
- [c0018 has not proven the `net` selector on a major] → canary `inconclusive` (`selector-unproven`), `kicad.drc.rules-unchecked`, stage `UNVERIFIED` on that major: visible, never silent.
- [A user rule governs the canary pair, or the canary rule governs user items] → the rule is placed where it takes precedence (`H-K-DRU-ORDER`) and selects only new nets; a name collision gives `names-taken` instead of a wrong verdict.
- [The copy set misses a file KiCad reads] → `H-K-CHECK-COPYSET` compares with a whole-folder copy on both majors before `projectset.py` is final; the missing kind joins the list; a size-capped whole-folder copy is the last resort.
- [A project vendors large libraries] → `MAX_COPY_BYTES` skips them with `check.copy-skipped`; the `lib_footprint_*` counts then carry no claim.
- [An agent reads a DRC pass while violations exist, until c0020] → `summary.violations_judged = false` and the counts sit in the stage; a missing canary on a built project is an error; the next tag waits for c0020.
- [`erc.lite` false positives] → warnings only, `INFERRED`, built input only, removal enforced at 0.2.
- [DRC on 21 demo boards is slow in `kicad-10`] → `slow` marker and timings in `docs/evidence/kicad-check.md`; if the job grows by more than 10 minutes, canary-neutrality demo runs drop to 5 boards, and the other boards run `--stages roundtrip,drc.kicad` once.
- [9.0.9 help pages follow another grammar] → `doctor.help-unparsed` names the page; `H-K-CLI-HELP` gets a `-2` successor and the parser follows the measured form; unconfirmed rows report `"unknown"`.
- [c0011's final text changes again on `.fenolite/` or `Power`] → detection is one function and the power exemption one predicate; only `test_check_built.py` depends on c0011's build output.
- [Users without KiCad get exit 6 by default] → the hint names `--stages model.validate,erc.lite,roundtrip`, and `doctor` explains what is missing.
- [Upstream slips: c0010 and c0018 are the last of the committed batch] → groups 1, 2.1 and 3.1 and most of group 5 depend only on c0009 and c0017; task 3.2 waits for c0010.
- [Overrun, as in c0006 to c0008] → 8.5 days stated in the proposal, with the cut order of "Budget".

## Migration Plan

- Additive: new modules, the `checks` package, three commands, `validate` in the KiCad `operations`, probe rows and docs. No model, schema or FEN-code change. To roll back, remove the modules and commands, drop `validate` from `operations` with its pinned tests, and remove the `check-*` probe rows from the probe files. A rollback also reverts this change's MODIFIED "Write capability fields" to c0010's text, which keeps `lower` and says `validate` is absent.

## Open Questions

- **Oracle surface.** The roadmap lists `drc`, `netlist` and `upgrade`. The default ships `drc` only; c0020 ADDs `netlist` and `upgrade` to `backend-protocol` with its pad-net partition type.
- **DRC findings and later stages.** The requirements are written to be extended (Decision 10): c0020 adds per-violation issues, its codes and `netlist.assignment_compare` through ADDED `verification-loop` requirements, and its mapping makes `violations_judged` `true` under this change's own rule; c0024 adds `render` and c0015 `zone.unfilled` the same way. c0020 keeps `kicad.drc.rules-not-loaded` and `kicad.drc.rules-unchecked` reserved (no KiCad type maps to them). If a later change still needs to alter a requirement of this change, it MODIFIES it with the full text copied. To confirm in c0020's brief.
- **Built marker (c0011).** c0011's final text writes the layer files with `dump_texts` and says that `.fenolite/build.json` marks a built project. The default accepts `meta.json` or `build.json` (Decision 8); a `build.json` without loadable layer files gives `check.cache-unreadable`. `Power(hv, lv)`, the `members` keys `hv` and `lv`, and `examples/blink_2layer` match c0011's final text. Task 7.2 runs the built-blink test only after c0011 merges.
- **`erc.lite` severity.** The plan implies errors. The default is warnings on built input only, until `sch erc` replaces the stage (v0.2a). To confirm.
- **v0.1 item 1, "RT1 equals the model".** The default reads it as RT1 on the built board, with no cache-staleness finding in v0.1 (c0019's lens). To confirm.
- **Key projection of a built design (c0011's hand-over).** c0011's Open Questions give c0013 the comparison of a built model with its board by keys (reference, pad number, net name). This change declines it: RT1 here is c0009's same-version rebuild of the board, and a model-to-board comparison is a staleness lens. The default owners are c0019's lens for components, positions and properties, and c0020's `netlist.assignment_compare` for pad nets; c0011's hermetic readback test covers the build until then. c0011 can update its own Open Question.
- **Demo projects in CI.** `kicad-10` fetches only `rt0` rows, so CI covers demo boards and authored projects, and real demo projects are a local run. The default adds no `ci-baseline` delta here; c0021 or c0025 adds `--uses project`, so only one unarchived change modifies that requirement at a time.
- **Global library tables.** They are absent in `check` (empty `KICAD_CONFIG_HOME`), so `lib_footprint_*` counts may differ from the GUI. The default keeps the run isolated and only counts them; an opt-in pass-through is c0021's decision.
- **Project pointers.** `/pcbnew/page_layout_descr_file` and `/board/design_settings/rule_severities/clearance` are key names seen in KiCad's own project files (the template projects of S-0066, which c0010 surveys, and the demo projects of S-0058), `INFERRED`; `check-canary-ignored` proves the second one's effect. c0012 names the first `pro.PAGE_LAYOUT_POINTER`. The default keeps `projectset.WORKSHEET_POINTER` local, so this change does not depend on c0012. The separate test `test_projectset.py::test_worksheet_pointer_matches_pro` skips with the reason "pro.PAGE_LAYOUT_POINTER not defined yet (c0012)" while the name is absent, and asserts that the two are equal once it exists, which c0012's task 7.1 checks with `-rs`. The general severity semantics stay c0020's.
- **"Write capability fields" (resolved).** c0010 MODIFIES it (membership, `lower` and its generic contract); c0018 leaves `operations` unchanged; this change's MODIFIED text is c0010's plus `validate` (Decision 20). Task 9.1 re-checks it before archive.
- **Budget.** 8.5 working days against the roadmap's 7, with the cut order of "Budget".
- **Register guard (c0014).** This design cites `H-K-CHECK-COPYSET`, `H-K-CHECK-CANARY`, `H-K-CLI-HELP` and `H-K-CHECK-ERC` before task 1.1 registers them, as "Ids proposed by active changes" allows. Task 1.1 is the first implementation commit.
- **c0009's code beyond its design.** The committed `cli.py` has `CliRun.ok` and a `hint` argument on `KicadCliVersionError`, which c0009's design table does not list. The default uses only the designed names. `capabilities --no-tools` (living `cli-contract`) and its `detect_tools()`, which runs `kicad-cli version`, `java -version` and `docker --version` directly, stay unchanged. `doctor` names its flag `--no-run`, because it still lists candidates, and sends every `kicad-cli` call through `KicadCli`. Moving `detect_tools()` onto the runner is left to a later `cli-contract` change.
- **Working tree.** c0017 is archived: `KicadCli.drc`, `DrcRun` and `backends/kicad/drc.py` exist in commit 89a0c99. Another agent is implementing c0018 and c0010 in the same tree; `rulemap.py`, `dru.py` and `pro.py` do not exist yet. The default follows the committed proposals, and each task starts only when the names it uses exist (Decision 1 gives the order).
- **Locator.** `sexpr.first_difference` already exists (c0006, living `kicad-sexpr`). The default reuses it in RT1 instead of the `roundtrip.first_difference` of the roadmap brief.
