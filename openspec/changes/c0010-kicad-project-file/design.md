## Context

- **No public format.** The developer file-format index lists pages for the S-expression files and the legacy formats, and none for `.kicad_pro` or `.kicad_prl` (S-0065, checked 2026-10-01). The manual says only that `.kicad_pro` holds the settings shared by the schematic and board editors, and that `.kicad_prl` holds local state that is not meant for version control (S-0045, `#project_files`). Every key name below comes from KiCad-written files, never from a specification.
- **Rules need a project file.** `kicad-cli` reads a `.kicad_dru` only when a project file with the same stem sits next to the board, and any rules error disables all custom rules with exit 0 (`H-K-TOK-RULES-SILENT`, `KICAD-VERIFIED (9.0.x, 10.0.x)`). The committed canary project `tests/data/kicad/tokens/canary/canary.kicad_pro` holds only `{}`, so KiCad accepts a project that holds nothing and defaults the rest.
- **Net classes.** Net classes are edited in Board Setup, stored per project and assigned to nets by name patterns (9.0 manual S-0010; 10.0 manual S-0038, `#board-setup-net-classes`, read manually in task 1.2). Both pages refer to the Schematic Editor manual for patterns (S-0046, 9.0 and 10.0): a pattern is a wildcard or a regular expression, a net takes every class whose pattern matches it, and several classes form an aggregate by priority. Board files carry no net-class data. The model already has `NetClass(name, clearance, track_width, via_diameter, via_drill, description)` (id prefix `cls`), `Net.netclass_id` and `Circuit.netclasses`, and `Design.validate()` reports `model.unknown-netclass`.
- **Demo census** (observed 2026-10-01 with a JSON reader, key names and counts only, not normative). The demos hold 36 `.kicad_pro` files at 10.0.6 and 37 at 9.0.9.1, and 2 and 1 `.kicad_dru` files (S-0024).
  - `meta.version` is 3 in 28 of 36 and 21 of 37 files; older demos keep 1 or 2. Pairs at 10.0.6: (3, 4) in 23, (3, 5) in 5, (1, 3) in 7, (2, 4) in 1.
  - `net_settings.meta.version` is mostly 4 at both tags; 5 appears only at 10.0.6, in 5 files (`H-K-PRO-VERSION`).
  - Top-level keys at both tags: `board`, `boards`, `cvpcb`, `erc`, `legacy` (in 3 and 4 files), `libraries`, `meta`, `net_settings`, `pcbnew`, `schematic`, `sheets`, `text_variables`. Only at 10.0.6: `component_class_settings`, `tuning_profiles`, `time_domain_parameters`.
  - `net_settings` keys: `classes`, `meta`, `net_colors`, `netclass_assignments`, `netclass_patterns`.
  - Class keys: `name`, `clearance`, `track_width`, `via_diameter`, `via_drill`, `microvia_*`, `diff_pair_*`, `priority`, `pcb_color`, `schematic_color`, `wire_width`, `bus_width`, `line_style`, plus `tuning_profile` only at 10.0.6 (`H-K-PRO-TUNING`).
  - `board.design_settings.rules` holds 26 minimum keys such as `min_clearance`, `min_track_width` and `min_via_diameter`; `board.design_settings.rule_severities` holds 64 keys across the 10.0.6 demos.
- **Template census** (observed 2026-10-01 on the 19 template projects of S-0066 installed with KiCad 10.0.6; key names and counts only, not normative): all 19 have `meta.version` 3 and `net_settings.meta.version` 4; every `netclass_patterns` entry holds exactly the keys `netclass` and `pattern`; `boards` is `[]` and `netclass_assignments` is `null` in all 19.
- **Licence.** The demos are CC-BY-SA-4.0 (S-0023) and the templates CC-BY-SA-4.0 with the library exception (S-0066). Both are measurement material only. The packaged templates come from empty projects that the maintainer saves in the KiCad GUI, which contain only KiCad's defaults.
- **Upstream changes.**
  - c0009 provides `KicadCli` (`backends/kicad/cli.py`), which copies the given files into a fresh temporary directory with an empty `KICAD_CONFIG_HOME`, `LANG=C` and `LC_ALL=C`; `read_board`; and the `kicad-file-backend` capability.
  - c0017 provides `write_board(design, *, target, allow_lossy) -> WriteResult(text, issues)`, `LossyWriteError` (`FEN-7001`), the source-major rule of its target policy (`pcb.source_info(design)`, `major_for`), `KicadCli.drc(board, *, files) -> DrcRun` and `read_drc_report(text) -> DrcReport`, whose violations carry the uuids of their items. It also provides the probe registry `tests/kicad/_probes.py` (`PROBES`, `run(probe_id)`) and the drift test against `docs/evidence/kicad/probes/<version>.json` ("Probe results per kicad-cli version": oracle tests assert on `run(…)`).
  - c0018 provides `backends/kicad/lowering.py` with `lower_rules(ruleset, *, target, allow_lossy) -> LoweredRules(text, issues)`, `backends/kicad/dru.py` with `read_rules` and `write_rules`, the `rules-model` capability, the `net` condition proved per major (`H-K-DRU-COND`), and `docs/formats/kicad/rules.md`, which records that board-setup minimums act as floors (S-0038). Its `kicad-oracle` requirement "Rules proofs carry a canary" covers custom-rule proofs on its own bench: an unconditional 3 mm canary and probe pairs more than 3 mm apart. A report without the canary fails with "rules file not loaded".
  - c0007 provides `versions` (`VersionStatus`, `TARGET_MAJORS`, `DEFAULT_TARGET`, `FutureFormatError`, `UnsupportedFormatError`, `DowngradeRefusedError`). c0014 makes the hypothesis register machine-checked.
- **Environment.** KiCad 10.0.6 (GUI and `kicad-cli`) is installed locally on macOS. 9.0.9 runs in the pinned image of the `kicad-9` job (S-0029); a 9.0.9 GUI save needs that image with a virtual display, or a contributor.
- **Constraints.** Standard library only (`json`). `backends.kicad` modules import `core`, `model` and their own package (`package-layering`). Budget 6.5 working days against the plan's one-week line.

## Goals / Non-Goals

**Goals:**
- Synthesise a complete, near-native `.kicad_pro` for a new design at target 9 or 10.
- Edit only the managed keys of an existing project and keep every other key, its order and its number spelling.
- Read net classes and their assignment back into the model.
- Prove on 9.0.9 and 10.0.6, with a three-way control and a canary, that the classes Fenolite writes are enforced.
- Ship `.kicad_pcb`, `.kicad_pro` and `.kicad_dru` only together.

**Non-Goals:**
- Everything listed under Non-goals in the proposal.
- Byte identity with KiCad's JSON printer.
- Modelling KiCad-only class keys (microvia, differential pair, colours, priority) or any other project key; they stay in the preserved file.
- Several net classes per net in the model; the reader reports them (Decision 11).

## Decisions

1. **The project file is JSON and stays outside `FileKind`.** `pro.py` owns `PROJECT_VERSIONS = {9: (3, 4), 10: (3, 5)}`, the pairs (`meta.version`, `net_settings.meta.version`) written per target, under an ADDED `kicad-version-gating` requirement "Project file versions". `FileKind`, `FORMAT_VERSIONS`, `kind_of` and `kind_for_suffix` are unchanged, and `kind_for_suffix("x.kicad_pro")` stays `None`.
   - Rejected: a MODIFIED `FileKind` with a pseudo-header for JSON. It would change a closed set, its tests and every function keyed on S-expression roots.

2. **Exact JSON preservation.** `_json.loads` uses the `json` module with `parse_int` and `parse_float` hooks that return `JsonNumber(text)`, a `parse_constant` hook for `NaN`, `Infinity` and `-Infinity` (the module routes them there, not to `parse_float`), and an `object_pairs_hook` that keeps key order. No float ever exists.
   - A syntax error raises `FormatError` with `offset`, the UTF-8 byte offset of `JSONDecodeError.pos`. The module gives no path for it.
   - A duplicate key in one object, `NaN` or `Infinity`, and a root that is not an object raise `FormatError` with a JSON-pointer `locator` (`""` for the root). The hooks see no path, so the pair hook and `parse_constant` return markers, and a walk after parsing turns the first marker into the error with its pointer.
   - `JsonNumber` is a frozen dataclass whose `text` must match the JSON number grammar.
   - `_json.dumps` prints two-space indentation, one member or element per line, `"key": value`, `{}` and `[]` for empty containers, strings escaped by `json` with non-ASCII text kept as UTF-8, and a final newline. This is the layout of the GUI saves (task 3.3).
   - Tests compare structure, with numbers compared as text. Byte identity with KiCad's printer is not a goal.
   - Rejected: plain `json.loads`, which turns `0.2000` into a float and loses its spelling. Rejected: a printer tuned to KiCad's bytes, which has no source and no consumer.

3. **Version policy.** `classify_project(meta_version, net_settings_version)` returns `FUTURE` when `meta.version > 3` or `net_settings.meta.version > 5`, and `SUPPORTED` otherwise, absent versions included, because KiCad reads `{}`. A `FUTURE` project is read with the warning `kicad.version.future` (the `kicad-version-gating` code) and never edited.
   - `project_major()` returns the target whose pair matches exactly, else `None`.
   - `update_project` edits only a project whose pair is in `PROJECT_VERSIONS`. Otherwise it raises `FutureFormatError` (`FEN-3002`) for a future project and `UnsupportedFormatError` (`FEN-3003`) for any other pair, `{}` included. The hint says to re-save the project in KiCad 9 or 10, or to let Fenolite synthesise a new one.
   - An update keeps the existing pair, except the lossy target-9 path of Decision 10. KiCad 10 reads a (3, 4) project (the 10.0.6 run of the target-9 bench proves it, Decision 14), so an update never bumps a version it cannot migrate.
   - Rejected: editing older projects (version 1 or 2). Their net-class layout differs, and only KiCad's own migration is safe.

4. **Templates come only from GUI saves.** The maintainer creates an empty project named `empty_10` in the KiCad 10.0.6 GUI on macOS and `empty_9` in 9.0.9 (the pinned image with a virtual display, or a contributor), opens the PCB Editor and the Schematic Editor once, and saves before quitting. KiCad's new-project template is a short version-1 file whose `board.design_settings.rules` is empty, and 9 of the 28 version-3 demos at 10.0.6 lack the floor keys, so a save without the editors may miss the defaults this design needs. The two `.kicad_pro` files are committed as `tests/data/kicad/project/empty_10.kicad_pro` and `empty_9.kicad_pro` (CC0, `origin = "authored"`, notes with version, operating system, date and SHA-256). Only the `.kicad_pro` files are kept.
   - `backends/kicad/data/project_template_10.json` and `project_template_9.json` equal their fixture, except that `meta.filename` is `""`. A unit test asserts this, and that each fixture has `meta.version` 3 and the four floor keys of Decision 7 in `board.design_settings.rules`.
   - KiCad stores the `Default` class `priority` as 2147483647 (27 of the 28 version-3 demos at 10.0.6, 20 of 21 at 9.0.9.1, all 19 templates; the remaining demo holds -1), which the residue pattern `numeric-code` flags under `tests/data/`. A `[[waiver]]` in `tools/residue/scope.toml` covers `tests/data/kicad/project/*.kicad_pro` for that pattern only; saving again removes path or user-name hits, not this value.
   - The key diff of the two fixtures goes into `docs/formats/kicad/project.md` as fact rows. It defines `TEN_ONLY_PATHS` (Decision 10).
   - The demo projects and the template repository (S-0066) are used for the key-name census only, never as template content.
   - Rejected: a hand-written minimal project. `H-K-PRO-MIN` shows that KiCad reads one, but a GUI save keeps every default KiCad would write, so a synthesised file stays close to native.
   - Rejected: a template taken from a demo or from S-0066 (share-alike content inside a package data file).

5. **Fallback when no 9.0.9 GUI save is possible.** `project_template_9.json` is derived from the 10 template by removing every path of the 10.0-only set observed in the census (top-level `component_class_settings`, `tuning_profiles`, `time_domain_parameters`, and the class key `tuning_profile`) and by setting `net_settings.meta.version` to 4. The derivation is a script step recorded in `project.md`. The 9.0 side of `H-K-PRO-VERSION` then stays `INFERRED`, with the census as supporting data. The 9.0.9 oracle (Decision 14) runs unchanged and shows whether 9.0.9 reads the derived file.

6. **Synthesis.** `synthesize_project(design, *, target, board_name)` starts from a fresh copy of the target's template and fills:
   - `meta.filename` = `"<board_name>.kicad_pro"`;
   - `net_settings.classes`: the template's `Default` entry first, then one entry per model `NetClass` other than `Default`, sorted by name (Decision 7). A model class named `Default` updates the four values of the first entry;
   - `net_settings.netclass_patterns`: one exact-name entry `{"netclass": <class name>, "pattern": <net name>}` per model net whose `netclass_id` names a class other than `Default`, sorted by net name (Decision 8);
   - every other key keeps the template value: `boards` (`[]`), `netclass_assignments`, `text_variables` and `pcbnew.page_layout_descr_file` (filled by c0012).
   - A net with `netclass_id = None` is in `Default` and gets no pattern.
   - An empty GUI save has `netclass_patterns: []` (every template project of S-0066 with only the `Default` class has an empty list), so the template holds no path below `/net_settings/netclass_patterns/*`. `pro.PATTERN_ENTRY_PATHS` names the three paths a pattern entry adds (the entry, its `netclass` and its `pattern`); they are the only key paths synthesis may add to the template's, and the test "No key outside the template" allows them.
   - A `netclass_id` that names no class is a model error that `Design.validate()` reports as `model.unknown-netclass`. Callers validate first: c0011's `build` stops on it with exit 5, like every model error. A caller that skips validation reaches `ConsistencyError` naming `model.unknown-netclass`, which the CLI maps to `FEN-1001` on purpose, because reaching it is a caller bug.
   - Rejected: listing the board in `boards`. No public source says what an entry holds, every observed file has `[]`, and KiCad pairs board and project by file stem.

7. **Net-class lowering.** `lowering.lower_netclass(cls, *, base, floors)` returns a copy of `base`, the `Default` entry of the project being written (the template's for synthesis, the existing file's for an update), with:
   - `name` = `cls.name`;
   - `clearance`, `track_width`, `via_diameter` and `via_drill`, each the exact millimetre text of the nanometre value (`format_length(nm, "mm")` without its unit) as a `JsonNumber`, or the base value when the model field is `None`. Project lengths are millimetres (the GUI saves; `H-K-PRO-NETCLASS` brackets the unit);
   - every other key (microvia, differential pair, colours, `priority`, line style, and `tuning_profile` in a 10.0 file) as in `base`.
   - A non-empty `description` adds the info `kicad.project.unlowered-field`; no project key holds it.
   - A value below its floor adds the warning `kicad.project.below-floor` naming the class, the field, the value and the floor, and the value is still written. Floors come from `board.design_settings.rules`: `min_clearance`, `min_track_width`, `min_via_diameter` and `min_through_hole_diameter` (key names confirmed in the GUI saves by task 3.3). The warning exists because the floor, not the class, governs (`H-K-PRO-FLOOR`).
   - Rejected: refusing a value below the floor. KiCad accepts it, and the user may raise the floor later.

8. **Exact-name patterns, refused when they could over-match.** Fenolite writes one pattern per classed net, equal to the net name, and never writes an assignment.
   - Documented reading (S-0046, the Schematic Editor manual of 9.0 and 10.0, to which the board-setup pages S-0010 and S-0038 refer for patterns): a pattern matches a net as a wildcard (`*` any run, `?` one character) or as a regular expression (wxWidgets advanced flavour); the manual's own example is that `net*` also matches `ne`. An exact name holding a regular-expression metacharacter can therefore match other nets: `Net-(R1-Pad1)` also matches `Net-R1-Pad1`, `D[0]` matches `D0`, `IN+` matches `INN`, `VCC_3.3` matches `VCC_3V3`.
   - `pattern_matches(pattern, name)` models this reading. It is true when the wildcard match holds (whole name, case-sensitive, `*` and `?` the only special characters), or when the pattern compiles as a Python regular expression and `re.fullmatch` matches the name. A pattern that does not compile (`+3V3`) matches as a wildcard only. Python's `re` stands in for the wxWidgets flavour, and whole-name matching is assumed; both are `INFERRED` (`H-K-PRO-PATTERNS`).
   - A classed net gives the error `kicad.project.pattern-unsafe` when its name holds a character of `UNSAFE_PATTERN_CHARS` (`*` and `?`, wildcards by definition), or when its exact-name pattern, read with `pattern_matches`, matches another net of the design that is not in the same class. Without `allow_lossy` this raises `LossyWriteError` (`FEN-7001`, exit 7, `droppable=True`). With it, the net gets no pattern and falls back to `Default`, with the warning `kicad.project.dropped-pattern`.
   - Refusing is the safe default: an over-matching pattern would silently give another net the class. The check covers the nets of the design only (Open Questions).
   - The oracle measures the reading (Decision 14). The pattern case adds the raw entries `Net-(R1-Pad1)`, `D[0]`, `IN+` and `VCC_3.3`, whose decoys `Net-R1-Pad1`, `D0`, `INN` and `VCC_3V3` are expected to fire (S-0046). The anchoring decoy `SIG10`, beside the synthesised pattern `SIG1`, is expected not to fire. If a major measures otherwise, `pattern_matches` follows the measurement for both targets, and a successor of `H-K-PRO-PATTERNS` with the suffix `-2` records it (c0014 Decision 5).
   - Rejected: refusing every name with a regular-expression metacharacter. `+3V3` and `Net-(R1-Pad1)`, KiCad's usual net-name forms, would always need `allow_lossy`. Rejected: escaping, which has no public rule and depends on the unmeasured flavour. Rejected: writing `netclass_assignments`. The template census shows them `null`, and their writer and semantics are not documented.

9. **Update in place.** `update_project(existing_text, design, *, target)` parses the file, checks it (Decisions 3 and 10), and changes only:
   - classes: an entry whose name matches a model class gets its four values replaced. A value equal in nanometres to the file value keeps its original spelling. A model class absent from the file is appended (lowered from the file's `Default`, sorted by name among the appended ones). Entries without a model class are kept verbatim; an update never deletes a class;
   - patterns: exact-name entries (no `*` or `?`) whose pattern equals a model net name are regenerated as in Decision 6 and placed first. Every other entry is kept verbatim, in order, after them;
   - a kept pattern entry or assignment that matches a model net (by `pattern_matches`) with a different class gives the warning `kicad.project.pattern-conflict`, because KiCad 9 and 10 give a net every matching class (S-0046);
   - the check of Decision 8 runs on the regenerated entries, with the same errors.

   Every other key, its position and its number spellings stay as read, `meta.filename` and `boards` included.
   - Rejected: re-synthesising and merging unknown keys back. That loses the user's order and spellings and edits keys Fenolite does not own.
   - Rejected: deleting classes the model lacks. They may come from the GUI, and an unused class is harmless.

10. **Target gating.** `TEN_ONLY_PATHS` is the set of key paths present in the 10 template and absent from the 9 template, with list items written `*` (for example `/tuning_profiles` and `/net_settings/classes/*/tuning_profile`). Synthesis for target 9 starts from the 9 template, so it never emits one. For `update_project(…, target=9)`:
    - a project whose pair is (3, 5) or that holds a `TEN_ONLY_PATHS` key, for a board whose source major is 10 (c0017's target policy, `pcb.source_info(design)`): `DowngradeRefusedError(FileKind.BOARD, 10, 9)` (`FEN-7002`). The project has no `FileKind` (Decision 1), and the board's source major is what drives the refusal, so the error names the board;
    - the same project for a board of major 9 or a created board: `LossyWriteError` (`FEN-7001`, `droppable=True`), listing one `kicad.project.too-new-key` error per path, plus one with `where` `/net_settings/meta/version` for the pair (3, 5), so a (3, 5) project without a 10-only key is not refused with an empty list. With `allow_lossy`, each path is removed, `net_settings.meta.version` becomes 4, and each of those errors becomes the warning `kicad.project.dropped-too-new`.
    - `droppable` is True for both project errors (`pattern-unsafe` and `too-new-key`), because `allow_lossy` resolves each of them, as for c0018's `RulesLossError`. c0017's hint then names `--allow-lossy`.

    For target 10, every key is kept.

11. **Reading and applying.** `read_project(source)` parses and classifies the file and returns a `ProjectInfo`: the parsed tree, the version pair, status, major, classes (four values in nm), patterns, assignments and floors. `apply_project(design, info)` returns a new `Design`:
    - `Circuit.netclasses` is replaced by one `NetClass` per `classes` entry, in file order, with id `derived_id("cls", "kicad", "netclass:<name>")`, provenance `file` plus the JSON pointer of the entry, and values parsed with `parse_length(text, default_unit="mm")`. A value that is not a whole number of nm reads as `None` with the info `kicad.project.inexact-value`.
    - Each net's candidates are the classes of its `netclass_assignments` entry (a string or a list of strings) and of every pattern entry that `pattern_matches` its name (Decision 8). `fnmatch` is not used, because it treats `[` as a set and knows no regular expressions.
    - KiCad gives a net with several classes an aggregate class that takes each property from the highest-priority class that sets it, priority following the order of the Board Setup dialog (S-0046, S-0010, S-0038). The model holds one class per net, so the net gets the candidate of highest priority: the lowest `priority` value, ties in `classes` order (`INFERRED`; the GUI saves give the fallback `Default` the largest value). It also gets the warning `kicad.project.multiple-classes`, naming every candidate and saying that KiCad aggregates them. A pattern or assignment that names an absent class gives `kicad.project.unknown-class` and is skipped. An entry of another shape gives the info `kicad.project.unread-entry` and is skipped.
    - A net with no match keeps `netclass_id = None`, which means `Default`.
    - Rejected: modelling composite classes before a consumer needs them.

12. **Coherent triad.** `triad.write_triad(design, *, name, target, existing_project=None)` returns exactly `{"<name>.kicad_pcb", "<name>.kicad_pro", "<name>.kicad_dru"}`:
    - the board from c0017's `write_board`;
    - the rules from c0018's `lower_rules` (an empty `RuleSet` when `design.rules is None`, which gives `(version 1)` only);
    - the project from `update_project(existing_project, …)` when one is given, else from `synthesize_project`.

    Issues of the three writers are appended to `issues`, and an error of any writer aborts the whole set. No function in `src` writes or reads `.kicad_prl`. Every `kicad-cli` run on a generated set, in `src` and in the oracle tests, goes through c0009's `KicadCli`, which works on a temporary copy. c0011 `lens/build.py` is the first product caller.
    - Capability report. `write_kinds` gains `kicad_pro`; `read_kinds` stays unchanged. c0009 ties `read_kinds` to `Backend.read`, whose content is a `Design` or a `Library` ("Read results"), and `KicadBackend.detect` finds no kind for `.kicad_pro` (`kind_for_suffix` gives `None`), while `read_project` returns a `ProjectInfo`. c0018 reads c0009 the same way for `kicad_dru`.
    - `operations` gains `"lower"`, as c0018 Decision 19 hands over to this change. `KicadBackend.lower(design, *, name, target=None, existing_project=None, allow_lossy=False) -> dict[str, str]` returns `write_triad(…)` (`target=None` means `default_target`), because rules and classes are only lowered as a coherent set. The `Backend` protocol is unchanged, as for c0017's `write`. c0009's tests `tests/unit/backends/test_registry.py` and `tests/unit/cli/test_capabilities_backends.py` pin `operations`, so task 4.4 updates them in the same commit.
    - Rejected: letting callers assemble the set. A board without its project silently loses its classes and rules (`H-K-TOK-RULES-SILENT`).

13. **Issue codes.** The closed table lives in the leaf module `backends/kicad/proerrors.py` (`ISSUE_CODES` and `project_issue(code, message, *, where=, hint=)`, which takes the severity from the table), as `liberrors.py` does for libraries. `lowering` and `pro` both import it, and `pro.ISSUE_CODES` re-exports the same mapping. `lower_netclass` therefore uses these codes, not c0018's `RULE_ISSUE_CODES`, which governs the rule issues of `lower_rules`, `read_rules` and `write_rules`:

    | code | severity | when |
    |---|---|---|
    | `kicad.project.below-floor` | warning | a lowered class value is below its `board.design_settings.rules` minimum |
    | `kicad.project.pattern-unsafe` | error | a classed net name holds a character of `UNSAFE_PATTERN_CHARS`, or its exact-name pattern matches a net of another class (Decision 8) |
    | `kicad.project.dropped-pattern` | warning | under `allow_lossy`, such a net written without a pattern (it falls back to `Default`) |
    | `kicad.project.too-new-key` | error | a `TEN_ONLY_PATHS` key in a project written for target 9 |
    | `kicad.project.dropped-too-new` | warning | such a key removed under `allow_lossy` |
    | `kicad.project.multiple-classes` | warning | on read, several distinct classes match one net; the model keeps the highest-priority one |
    | `kicad.project.unknown-class` | warning | a pattern or assignment names a class absent from `classes` |
    | `kicad.project.pattern-conflict` | warning | on update, a kept pattern entry or assignment gives a model net another class |
    | `kicad.project.inexact-value` | info | a class value or floor that is not a whole number of nm |
    | `kicad.project.unlowered-field` | info | a non-empty `NetClass.description` |
    | `kicad.project.unread-entry` | info | a pattern or assignment entry of unexpected shape, kept and ignored |

    Errors that stop reading are exceptions: `FormatError` (Decision 2; `meta`, `net_settings` or a class that is not an object, `classes` that is not a list, a class without a string `name`, a version that is not an integer), `FutureFormatError`, `UnsupportedFormatError`, `DowngradeRefusedError`, `LossyWriteError` and `ConsistencyError`. No new `FEN-` code is needed.

14. **Net-class oracle: a bench, a scoped canary and three ways.** A clean DRC proves nothing (`H-K-TOK-RULES-SILENT`), so every case carries a canary and a no-project control. `tests/_netclass_bench.py` builds the bench through the model and writes it with `write_triad` as `bench.*`:
    - a 60 × 100 mm outline; F.Cu tracks 0.25 mm wide and 20 mm long, in rows 5 mm apart;
    - each of `+3V3`, `SIG1`, the anchoring decoy `SIG10`, the pattern nets `Net-(R1-Pad1)`, `D[0]`, `IN+` and `VCC_3.3`, their decoys `Net-R1-Pad1`, `D0`, `INN` and `VCC_3V3`, and `SW1_A` runs beside its own `GND` track with a 1.0 mm gap;
    - class HV, clearance 2 mm, assigned in the model to `+3V3` and `SIG1`, so synthesis writes their exact-name patterns and passes the check of Decision 8; every other row is in `Default` in the model;
    - a canary rule, 3 mm clearance restricted by a `net` condition to `CANARY_A`, whose track runs 0.75 mm from the `CANARY_B` track, at least 10 mm from other copper.

    **Departure from c0018's canary.** The committed canary rule applies to every pair. Here it would flag every 1.0 mm row, whatever the precedence between custom rules and classes, so case (c) could not tell a class from the canary. This bench therefore scopes the canary with the `net` condition that c0018 settles per major (`H-K-DRU-COND`). c0018's requirement "Rules proofs carry a canary" covers custom-rule proofs on its own bench. This proof judges net classes and does not reuse that bench. Every other part of that requirement still applies: the canary must fire in every case that loads the project, a report without it fails with "rules file not loaded", and the test never passes or skips on it.

    Violations are attributed by the uuids of their items as `read_drc_report` returns them, never by description text or exit code. Cases, each on 10.0.6 (target 10 and target 9 sets) and 9.0.9 (target 9 set):
    - (a) full set: a `clearance` violation for each HV row, and the canary;
    - (b) the same set without `bench.kicad_pro`: neither;
    - (c) the set synthesised without HV: the canary only;
    - minimal: `bench.kicad_pro` cut to `meta` and `net_settings` gives the same violations as (a) (`H-K-PRO-MIN`);
    - patterns: (a) plus raw entries → HV added by the test: `Net-(R1-Pad1)`, `D[0]`, `IN+`, `VCC_3.3` and the wildcard `SW?_*`. Each of those rows and `SW1_A` fires. The decoys `Net-R1-Pad1`, `D0`, `INN` and `VCC_3V3` are expected to fire too, since S-0046 reads patterns as regular expressions as well (`H-K-PRO-PATTERNS`);
    - anchor: in (a), `SIG10` is expected not to fire, because whole-name matching is assumed (`H-K-PRO-PATTERNS`);
    - floor: HV at 0.5 mm gives no HV violation with the template floor, and HV violations once `min_clearance` is 1.5 in the project; the canary fires in both (`H-K-PRO-FLOOR`).

    **Probes.** Each case is a probe of c0017's `tests/kicad/_probes.py`, and the tests assert on `run(…)`. Ids are `pro-<case>-t<target>`, with `<case>` one of `full`, `noproject`, `noclass`, `minimal`, `patterns`, `decoys`, `anchor`, `floor-template` and `floor-raised`. Target-10 probes run on major 10, target-9 probes on 9 and 10. Each case watches some rows: the four decoy rows for `decoys` (run on the `patterns` set), `SIG10` for `anchor` (run on the full set), the four raw-entry rows and `SW1_A` for `patterns`, and the HV rows `+3V3` and `SIG1` otherwise. Outcomes use c0017's closed set:
    - `present`: every watched row has its HV violation;
    - `absent`: no watched row has one;
    - `equal`: for `minimal`, the same violations, by type and item uuids, as `full`;
    - `different`: any other mix;
    - `inconclusive`: the canary is missing in a case that loads the project, or present in `noproject`.

    Expected outcomes: `present` for `full`, `patterns`, `decoys` (as documented by S-0046) and `floor-raised`; `absent` for `noproject`, `noclass`, `anchor` and `floor-template`; `equal` for `minimal`. A pure function `judge(report, *, case, design)` of `tests/_netclass_bench.py` computes the outcome from a `DrcReport`, and `assert_loaded(outcome, case)` fails with "rules file not loaded" on `inconclusive`; `tests/unit/test_netclass_bench.py` checks both on authored report texts, so the canary path is proved without KiCad. `test_project_files.py` runs `pcb drc` (`KicadCli.drc`) and `pcb export svg` (`KicadCli.run`) on the target-9 set and reads `CliRun.outputs`, which lists every file a run created or changed. It adds `pro-file-drc` and `pro-file-export` (`equal` when `bench.kicad_pro` is absent from `outputs`) and `pro-prl-drc` and `pro-prl-export` (`present` when `bench.kicad_prl` is in `outputs`, else `absent`, recorded as measured). Tasks 7.1 to 7.3 regenerate `docs/evidence/kicad/probes/10.0.6.json` and `9.0.9.json` with `FENOLITE_PROBES_WRITE=1`, so a later image with other behaviour fails `tests/kicad/test_probe_results.py`.
    - Rejected: judging by `--exit-code-violations`, and a bench without a no-project control.

15. **Evidence of GUI-saved facts.** No `kicad-cli` command writes `.kicad_pro` (`H-K-PRO-PRL`). The GUI saves are therefore the only KiCad-written evidence of key names, defaults and version pairs. They count as `KICAD-VERIFIED` with the scope "GUI save", because the file is recorded with the exact KiCad version, date and SHA-256, and the corpus test checks that the committed bytes still match that hash. Each such fact is also exercised by `kicad-cli` reading the synthesised file in the oracle.

16. **Corpus rows and census.** `tests/corpus/manifest.toml` gains one row per distinct demo `.kicad_pro` and `.kicad_dru` at 10.0.6 and 9.0.9.1 (S-0024), with ids `kicad-demo-<tag>-pro-NN` and `kicad-demo-<tag>-dru-NN`, `uses = ["project", "origin:kicad-demos"]` and `embeddable = false`. They never carry `rt0` or `oracle`.
    - `tests/unit/backends/kicad/test_pro.py` round-trips every cached project row (`needs_corpus`) and writes a key-name census to the file named by `FENOLITE_CENSUS_OUT`, never to a tracked file.
    - `tests/unit/backends/kicad/test_dru_demos.py` reads and re-writes every cached rules row with c0018's `read_rules`/`write_rules`.
    - The `kicad-10` job keeps fetching `--uses rt0`, so these are local measurements; task 8.2 copies the counts into `docs/evidence/kicad-project.md`.

17. **Tuning profiles live in the project file** (`H-K-PRO-TUNING`). This answers c0007's open question. `tuning_profiles` and the class key `tuning_profile` are 10.0-only project keys, preserved verbatim and never synthesised, and the board inventory gains no row. The settling data are the two GUI saves and the census.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/kicad/_json.py` (new) | `@dataclass(frozen=True, slots=True) class JsonNumber(text: str)`; `JsonValue = JsonObject \| list[JsonValue] \| str \| JsonNumber \| bool \| None`; `JsonObject = dict[str, JsonValue]`; `loads(text: str, *, file: str = "") -> JsonObject`; `dumps(data: JsonObject) -> str`; `get(data: JsonObject, pointer: str) -> JsonValue \| None`; `key_paths(data: JsonObject) -> frozenset[str]` (list items as `*`); `structural_equal(a: JsonValue, b: JsonValue) -> bool` (numbers compared as text); imports only `core` |
| `src/fenolite/backends/kicad/pro.py` (new) | `PROJECT_VERSIONS: Mapping[int, tuple[int, int]] = {9: (3, 4), 10: (3, 5)}`; `PROJECT_READ_MAX = 3`; `NET_SETTINGS_READ_MAX = 5`; `classify_project(meta_version: int \| None, net_settings_version: int \| None) -> VersionStatus`; `project_major(meta_version: int \| None, net_settings_version: int \| None) -> int \| None`; `read_project_text(text: str, *, file: str = "") -> JsonObject`; `write_project_text(data: JsonObject) -> str`; `template(target: int) -> JsonObject` (a fresh copy); `TEN_ONLY_PATHS: frozenset[str]`; `PATTERN_ENTRY_PATHS: frozenset[str]` (`/net_settings/netclass_patterns/*` and its `netclass` and `pattern` keys); `@dataclass(frozen=True, slots=True) class ProjectClass(name: str, clearance: Nm \| None = None, track_width: Nm \| None = None, via_diameter: Nm \| None = None, via_drill: Nm \| None = None)`; `class ProjectInfo(file: str, data: JsonObject, meta_version: int \| None, net_settings_version: int \| None, status: VersionStatus, major: int \| None, classes: tuple[ProjectClass, ...], patterns: tuple[tuple[str, str], ...], assignments: tuple[tuple[str, tuple[str, ...]], ...], floors: dict[str, Nm])`; `read_project(source: str \| os.PathLike[str], *, file: str = "", issues: list[Issue] \| None = None) -> ProjectInfo`; `apply_project(design: Design, info: ProjectInfo, *, issues: list[Issue] \| None = None) -> Design`; `synthesize_project(design: Design, *, target: int = DEFAULT_TARGET, board_name: str, allow_lossy: bool = False, issues: list[Issue] \| None = None) -> str`; `update_project(existing_text: str, design: Design, *, target: int = DEFAULT_TARGET, allow_lossy: bool = False, issues: list[Issue] \| None = None) -> str`; `project_floors(data: JsonObject, *, issues: list[Issue] \| None = None) -> dict[str, Nm]`; `pattern_matches(pattern: str, name: str) -> bool`; `UNSAFE_PATTERN_CHARS: frozenset[str]` (`*` and `?`); `ISSUE_CODES` (re-exported from `proerrors`); `EVIDENCE: Evidence` |
| `src/fenolite/backends/kicad/proerrors.py` (new) | `ISSUE_CODES: Mapping[str, Severity]` (Decision 13); `project_issue(code: str, message: str, *, where: str = "", hint: str = "") -> Issue`; imports only `core` |
| `src/fenolite/backends/kicad/lowering.py` (c0018; extended) | `NETCLASS_KEYS: Mapping[str, str]` (model field → class key); `FLOOR_KEYS: Mapping[str, str]` (model field → `board.design_settings.rules` key); `lower_netclass(cls: NetClass, *, base: JsonObject, floors: Mapping[str, Nm], issues: list[Issue] \| None = None) -> JsonObject` |
| `src/fenolite/backends/kicad/triad.py` (new) | `TRIAD_SUFFIXES = (".kicad_pcb", ".kicad_pro", ".kicad_dru")`; `write_triad(design: Design, *, name: str, target: int = DEFAULT_TARGET, existing_project: str \| None = None, allow_lossy: bool = False, issues: list[Issue] \| None = None) -> dict[str, str]` |
| `src/fenolite/backends/kicad/data/project_template_10.json`, `project_template_9.json` (new) | packaged templates (Decision 4 or 5) |
| `src/fenolite/backends/kicad/__init__.py` | re-exports `read_project`, `apply_project`, `synthesize_project`, `update_project`, `write_triad`, `PROJECT_VERSIONS` |
| `src/fenolite/backends/kicad/backend.py` (c0009; extended) | `CAPABILITIES`: `write_kinds` gains `"kicad_pro"`, `operations` gains `"lower"`, `read_kinds` unchanged; `KicadBackend.lower(design: Design, *, name: str, target: int \| None = None, existing_project: str \| None = None, allow_lossy: bool = False) -> dict[str, str]` (calls `write_triad`) |
| `src/fenolite/backends/kicad/PROVENANCE.md` | rows for project roles, key names and defaults, versions, patterns and floors, census |
| `tests/data/kicad/project/empty_10.kicad_pro`, `empty_9.kicad_pro` (new) | GUI-saved CC0 fixtures, declared in `tests/data/MANIFEST.toml` |
| `tests/corpus/manifest.toml`, `tests/corpus/test_manifest.py` | `project` rows; the id rule for project rows; the GUI-save notes rule for `tests/data/kicad/project/` |
| `tests/_netclass_bench.py` (new) | `bench_design(*, target: int, hv_clearance: Nm \| None = 2_000_000) -> Design` (`None` = no HV class); `ROWS: Mapping[str, str]` (net → neighbour net, every row of Decision 14); `HV_NETS: tuple[str, ...]` (`+3V3`, `SIG1`); `RAW_PATTERNS: tuple[str, ...]` (`Net-(R1-Pad1)`, `D[0]`, `IN+`, `VCC_3.3`, `SW?_*`); `DECOYS: tuple[str, ...]` (`Net-R1-Pad1`, `D0`, `INN`, `VCC_3V3`); `ANCHOR = "SIG10"`; `track_uuid(design: Design, net: str) -> str`; `judge(report: DrcReport \| None, *, case: str, design: Design) -> str`; `assert_loaded(outcome: str, case: str) -> None` |
| `tests/unit/test_netclass_bench.py` (new) | hermetic checks of `judge` and `assert_loaded` (canary missing, canary in `noproject`) |
| `tests/kicad/_probes.py` (c0017; extended) | the `pro-*` probes of Decision 14 |
| `docs/evidence/kicad/probes/9.0.9.json`, `10.0.6.json` (c0017; regenerated) | outcomes of the `pro-*` probes |
| `tests/unit/backends/kicad/test_project_json.py`, `test_pro_versions.py`, `test_project_fixtures.py`, `test_pro.py`, `test_lowering_netclass.py`, `test_pro_synth.py`, `test_pro_update.py`, `test_write_triad.py`, `test_pro_read.py`, `test_dru_demos.py` (new); `test_versions.py` (one case added) | hermetic tests, plus the `needs_corpus` parts of `test_pro.py` and `test_dru_demos.py` |
| `tests/kicad/project/test_netclass_drc.py`, `test_project_files.py` (new) | `needs_kicad`, major-aware |
| `docs/formats/kicad/project.md` (new), `docs/formats/kicad/corpus.md` | format facts; the `project` use |
| `docs/evidence/kicad-project.md` (new) | census counts (key names and numbers only) |

Layering: `_json` and `proerrors` import only `core`; `lowering` keeps c0018's imports (`dru`, `rulemap`) and adds `model`, `_json` and `proerrors`; `pro` imports `core`, `model`, `versions`, `pcb` (`source_info`, Decision 10), `_json`, `proerrors` and `lowering`; `triad` imports `pcb`, `lowering` and `pro`. All are `backends.kicad` modules importing `core`, `model` and their own package, as `package-layering` allows. Neither `lowering` nor `pcb` imports `pro`, so there is no cycle.

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0065 | https://dev-docs.kicad.org/en/file-formats/index.html | not stated on the page (checked 2026-10-01) | the developer file-format index lists no `.kicad_pro` or `.kicad_prl` page; the project file has no public specification |
| S-0066 | https://gitlab.com/kicad/libraries/kicad-templates/-/tree/10.0.6 (tags 9.0.0, 9.0.9, 10.0.0 and 10.0.6 point to one commit, `3ed4538b0f96`) | CC-BY-SA-4.0 with the library exception (`LICENSE.md`; to verify on the page) | key-name census of the 19 template projects only (version pairs, pattern entry keys, `boards` and `netclass_assignments` values); never template content |

Both ids come from the block S-0065 … S-0069 that the batch assigns to this change; S-0067 to S-0069 stay unused. The brief's id for the template repository lay outside the block and is moved into it (Corrections to the brief). Rows of other changes whose "used for" cell this change extends, instead of registering the URL again:
- S-0010 (9.0 manual): net classes in Board Setup, stored per project, assigned by name pattern.
- S-0038 (10.0 manual): `#board-setup-net-classes` (pattern assignment) and board-setup minimums as floors.
- S-0045 (10.0 manual, also `/9.0/`): `#project_files`, the roles of `.kicad_pro` and `.kicad_prl`.
- S-0046 (Schematic Editor manual 10.0, also `/9.0/`): pattern-based net-class assignment (wildcards and regular expressions, `net*` also matching `ne`), several classes per net, and the aggregate class taken by priority order.
- S-0020: files saved by the KiCad 10.0.6 GUI from the same download (project fixtures).
- S-0029: the pinned 9.0.9 image used for the 9.0.9 GUI save.

Also cited: S-0023 (demo licence), S-0024 (demo file lists and hashes), S-0025 (per-folder licences) and S-0026 (tag commits), all c0006. If a URL above is already registered when this change is implemented, the existing id is cited and the row is not duplicated. No KiCad source file is read for this change.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-PRO-VERSION | `meta.version` is 3 on 9.0 and 10.0; `net_settings.meta.version` is 4 on 9.0 and 5 on 10.0 (census, S-0024, S-0066) | `tests/unit/backends/kicad/test_project_fixtures.py::test_version_pairs`; `tests/kicad/project/test_netclass_drc.py::test_full_set`; supporting: the census of `test_pro.py` | `empty_9` holds (3, 4) and `empty_10` holds (3, 5); the full set fires on 9.0.9 (3, 4) and on 10.0.6 (3, 5 and 3, 4); the census finds 5 only in 10.0.6 rows |
| H-K-PRO-MIN | A project holding only `meta` and `net_settings` is read, with defaults for everything else (S-0045, `H-K-TOK-RULES-SILENT`) | `tests/kicad/project/test_netclass_drc.py::test_minimal_project` | the same violations (type and item uuids) as the full set, on 9.0.9 and 10.0.6 |
| H-K-PRO-NETCLASS | A class clearance assigned by an exact-name pattern is enforced by `pcb drc` (S-0010, S-0038) | `tests/kicad/project/test_netclass_drc.py::test_three_way` | (a) every HV row and the canary fire; (b) neither; (c) only the canary; on 9.0.9 and 10.0.6 |
| H-K-PRO-PATTERNS | A pattern matches a net as a wildcard (`*`, `?`) or as a whole-name regular expression (S-0046): a name without metacharacters (`+3V3`, `SIG1`) matches only itself, and a name with them also matches other names | `tests/kicad/project/test_netclass_drc.py::test_patterns` | `+3V3` and `SIG1` fire and `SIG10` does not; the raw entries `Net-(R1-Pad1)`, `D[0]`, `IN+`, `VCC_3.3` and `SW?_*` make their rows and `SW1_A` fire; the decoys `Net-R1-Pad1`, `D0`, `INN` and `VCC_3V3` fire; on 9.0.9 and 10.0.6 |
| H-K-PRO-FLOOR | A `board.design_settings.rules` minimum above a class value governs, so the class value below the floor is not enforced (S-0038) | `tests/kicad/project/test_netclass_drc.py::test_floor` | HV 0.5 mm: no HV violation with the template floor, a violation on every HV row with `min_clearance` 1.5; the canary fires in both; on 9.0.9 and 10.0.6 |
| H-K-PRO-TUNING | Tuning profiles are stored in the project file (`tuning_profiles`, class `tuning_profile`) and only by 10.0 (census) | `tests/unit/backends/kicad/test_project_fixtures.py::test_tuning_profiles` | both keys in `empty_10`, neither in `empty_9`; the census finds them only in 10.0.6 rows |
| H-K-PRO-PRL | `kicad-cli` writes a `.kicad_prl` next to a board and never rewrites `.kicad_pro` in `pcb drc` and `pcb export` runs (S-0045, S-0020) | `tests/kicad/project/test_project_files.py::test_prl_and_pro` | `bench.kicad_pro` absent from `CliRun.outputs` (SHA-256 unchanged) after `pcb drc` and after `pcb export svg`, on 9.0.9 and 10.0.6; whether `bench.kicad_prl` is in `outputs` after each run is recorded |

Synthesis writes no wildcard; its over-match check uses `pattern_matches` (Decision 8). Reading pattern forms other than the bench entries, assignments and the choice among several classes stays `INFERRED` whatever `H-K-PRO-PATTERNS` shows.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| JSON preservation: order, number spellings, unknown keys | mechanical (unit tests); the round trip of the cached demo projects is supporting data | `test_project_json.py`, `test_pro.py` |
| Version pair written per target | KICAD-VERIFIED (9.0.x, 10.0.x; GUI save) with `kicad-cli` reading the synthesised file; the 9.0 side `INFERRED` under Decision 5 (`H-K-PRO-VERSION`) | `test_project_fixtures.py`, `test_netclass_drc.py` |
| Synthesised classes are enforced | KICAD-VERIFIED on 10.0.6 (local and `kicad-10`) and 9.0.9 (`kicad-9`) (`H-K-PRO-NETCLASS`, `H-K-PRO-MIN`) | `test_netclass_drc.py` |
| Exact-name patterns and the over-match check | KICAD-VERIFIED (9.0.x, 10.0.x) for the bench names and their characters (`+`, `-`, `(`, `)`, `[`, `]`, `.`, `_`, digits); INFERRED for other characters and for the check on other designs (`H-K-PRO-PATTERNS`) | `test_netclass_drc.py::test_patterns`, `test_pro_synth.py` |
| Reading patterns, assignments and the class of highest priority | KICAD-VERIFIED for the bench entries only; otherwise INFERRED (S-0046, `H-K-PRO-PATTERNS`) | `test_pro_read.py` |
| Floor warning | KICAD-VERIFIED (9.0.x, 10.0.x) for `min_clearance` (`H-K-PRO-FLOOR`); INFERRED for the other three floors (S-0038) | `test_netclass_drc.py::test_floor`, `test_lowering_netclass.py` |
| Update rules and target gating | mechanical (unit tests); the target-9 synthesised file loads on 9.0.9 (KICAD-VERIFIED) | `test_pro_update.py`, `test_netclass_drc.py` |
| Tuning profiles in the project file, 10.0 only | KICAD-VERIFIED (10.0.x; GUI save) (`H-K-PRO-TUNING`), with the census as supporting data | `test_project_fixtures.py` |
| `.kicad_pro` untouched by `kicad-cli` | KICAD-VERIFIED (9.0.x, 10.0.x) (`H-K-PRO-PRL`) | `test_project_files.py` |
| Triad always complete, never `.kicad_prl` | mechanical (unit tests) | `test_write_triad.py`; `git status --porcelain` after the oracle |
| Corpus rows and fixture notes | mechanical | `tests/corpus/test_manifest.py` |
| Oracle outcomes pinned per `kicad-cli` version | mechanical (drift test over the `pro-*` probes) | `tests/kicad/test_probe_results.py` in `kicad-9` and `kicad-10` |

`pro.EVIDENCE` is `INFERRED` (`H-K-PRO-PATTERNS`), because a user's project may use forms the oracle has not run. Every `Provenance` created by `apply_project` carries it.

## Budget (about 1.5 weeks; the plan line was one week)

| work | days |
|---|---|
| sources, hypotheses, provenance, `project.md` | 0.75 |
| GUI fixtures, key diff, templates | 1.0 |
| JSON codec | 0.75 |
| synthesis, update, `write_triad` | 1.0 |
| reading and applying | 0.5 |
| net-class lowering and floor warning | 0.5 |
| three-way, pattern and floor oracle, `.kicad_pro` probe | 1.0 |
| version requirement, corpus rows and census | 0.5 |
| closing | 0.5 |
| **total** | **6.5** |

The plan's one-week line is a calendar week at partial dedication, so 6.5 working days is an overrun, stated here and in the proposal. Cut first: the demo round-trip census (task 6.2) and the floor case (task 7.2, floor part). The three-way net-class proof is not optional.

## Risks / Trade-offs

- [No 9.0.9 GUI save can be made] → Decision 5. The 9.0.9 DRC proof does not depend on the GUI fixture.
- [KiCad silently ignores a synthesised project] → the no-project control (b) and the class-removed control (c) detect a file that was not read, and the templates are KiCad's own saves.
- [The canary or the bench interacts with the class under test] → the canary is scoped to one net, rows are 5 mm apart, and violations are attributed by item uuids.
- [c0018 refutes the `net` condition on a major (`H-K-DRU-COND`)] → the scoped canary cannot be written there. The bench then uses an unconditional canary of another kind, `track_width` with a 0.3 mm minimum, whose `track_width` violations on every 0.25 mm track do not touch clearance. c0018 settles the kind (`H-K-DRU-KIND`) before this change starts.
- [A major reads patterns otherwise than S-0046 says (no regular expressions, another flavour, no anchoring)] → `pattern_matches` follows the measurement for both targets with a `-2` successor, so the over-match check refuses more or fewer names. If `SIG10` fires, the bench writes `SIG1` as a raw entry, as the pattern case does.
- [Number-spelling edge cases in user projects: exponents, `-0`, long decimals] → `JsonNumber` keeps the text, and an unchanged value is never re-formatted.
- [Copying `priority` from `Default` gives every class the same priority] → one class per net is written, so priority does not decide anything Fenolite writes; the GUI save records the default value, and an Open Question tracks it.
- [The GUI save contains a local path or user name] → task 3.1 inspects the file and saves again if needed; the manifest test refuses absolute paths in its strings, and the residue scan runs on it with a waiver only for KiCad's `priority` value 2147483647 (Decision 4).
- [Overrun] → the cuts above; codec, synthesis, update gating and the three-way proof are not optional.

## Migration Plan

- Additive: three new modules, two package data files, one extended module and new tests. The model, the schemas, `FileKind` and the CLI are unchanged. To roll back, remove the modules, the templates and the `project` corpus rows; c0017's triad tests keep their `{}` project.

## Open Questions

- Can the author save an empty project from the KiCad 9.0.9 GUI (the pinned image with a virtual display, another machine, or a contributor), and one from the local 10.0.6 GUI? The default, when 9.0.9 is not possible, is Decision 5: the 9 template is derived from the 10 one, and the 9.0 side of `H-K-PRO-VERSION` stays `INFERRED`.
- The brief listed the board list among the managed keys. This design writes the template value of `boards` (`[]`) and keeps it on update, because no public source says what an entry holds and all observed files have `[]`. The default stays so until a source or an observation shows KiCad writing entries.
- Should `priority` of new classes follow the order of classes instead of copying `Default`? The default is to copy `Default`, and task 3.3 records its value.
- Should the `kicad-10` job also fetch the `project` rows? The default is no: the census is a local measurement, and corpus measurements in CI belong to c0020.
- Should `write_triad` also warn when a lowered custom rule is below a floor? c0018 expects the warning for preserved floors; the default is classes only in this change, because `H-K-PRO-FLOOR` measures classes. A follow-up can extend it to rules with `INFERRED` evidence.
- c0009's capability report lists lowering as unavailable until c0018 and c0010 land. c0018 leaves `operations` unchanged (its Decision 19), so this change adds `"lower"` (Decision 12). c0017 and c0018 check `write_kinds` by membership, so adding `kicad_pro` needs no delta of their requirements.
- c0014's cited-id scan covers active changes. Its Decision 8 (`proposed_ids`) accepts, inside this change's folder, the ids of the table "Hypotheses registered by this change", so the `H-K-PRO-*` ids pass before task 1.1 registers them. Every other id cited here must already be registered. This is why the severity hypothesis of c0020 is not named by id.
- The over-match check of Decision 8 covers the nets of the design. A net added later in KiCad can still fall under an exact-name pattern read as a regular expression. The default accepts this: the user adds that net, and the check runs again when the board is read back and updated.

## Corrections to the brief

- **Pattern semantics.** The brief's `H-K-PRO-PATTERNS` expects names such as `+3V3` and `Net-(R1-Pad1)` to match literally. The registered source S-0046 (Schematic Editor manual 9.0 and 10.0, to which the board-setup pages refer) says patterns are wildcards and regular expressions, and that `net*` also matches `ne`. Decision 8 therefore keeps the brief's rule (exact-name patterns only, `*` and `?` refused with `kicad.project.pattern-unsafe`) and adds the over-match check; the bench expects the decoys to fire; the hypothesis is restated.
- **Source id of the template repository.** The brief fixes S-0080, outside the block S-0065 … S-0069 that the batch assigns to this change. c0017 and c0018 also moved their brief ids into their own blocks, so a later change taking the next blocks cannot collide. The template repository is S-0066; S-0067 to S-0069 stay unused.
