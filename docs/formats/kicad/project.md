# KiCad project files (`.kicad_pro`)

A KiCad project is a folder holding `<name>.kicad_pro` next to the board, the schematics and an
optional `<name>.kicad_dru`. `fenolite.backends.kicad.pro` reads, synthesises and updates the project
file; `fenolite.backends.kicad.triad.write_triad` always returns board, project and rules together.
This page describes the format in Fenolite's own words. Sources are listed in
`docs/evidence/sources.md`.

**There is no public specification.** The developer file-format index lists no project page (S-0065),
and the manual only says what the file is for (S-0045). Every key name below comes from files KiCad
wrote: a GUI save (S-0020), the demo projects (S-0023, S-0024) and the template projects (S-0066).
The demos and the templates are used for key names and counts only, never as content. **The packaged
templates come only from GUI saves** (see "Templates").

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| `.kicad_pro` holds the settings shared by the schematic and board editors; `.kicad_prl` holds local state that is not meant for version control | S-0045 | INFERRED | H-K-PRO-PRL |
| The file is JSON with two-space indentation, one member per line and a final newline; Fenolite's printer reproduces a KiCad 10.0.6 GUI save byte for byte | S-0020 | KICAD-VERIFIED (10.0.x; GUI save) | H-K-PRO-VERSION |
| The KiCad 10.0.6 GUI save holds `meta.version` 3 and `net_settings.meta.version` 5 | S-0020 | KICAD-VERIFIED (10.0.x; GUI save) | H-K-PRO-VERSION |
| KiCad 9.0 writes `net_settings.meta.version` 4 (demo census: 5 appears only at tag 10.0.6) | S-0024 | INFERRED | H-K-PRO-VERSION |
| Top-level keys of the 10.0.6 GUI save: `board`, `boards`, `component_class_settings`, `cvpcb`, `erc`, `libraries`, `meta`, `net_settings`, `pcbnew`, `schematic`, `sheets`, `text_variables`, `tuning_profiles` | S-0020 | KICAD-VERIFIED (10.0.x; GUI save) | H-K-PRO-VERSION |
| Tuning profiles live in the project file (`tuning_profiles` and the class key `tuning_profile`), and only 10.0 writes them | S-0020, S-0024 | KICAD-VERIFIED (10.0.x; GUI save) | H-K-PRO-TUNING |
| `net_settings` holds `classes`, `meta`, `net_colors`, `netclass_assignments` and `netclass_patterns`; the empty save has `netclass_patterns: []` and `netclass_assignments: null` | S-0020, S-0066 | KICAD-VERIFIED (10.0.x; GUI save) | H-K-PRO-VERSION |
| A class entry holds `name`, `clearance`, `track_width`, `via_diameter`, `via_drill` (millimetres), `microvia_*`, `diff_pair_*`, `priority`, colours, `wire_width`, `bus_width`, `line_style`, and at 10.0 `tuning_profile`; the `Default` class has `priority` 2147483647 | S-0020, S-0024 | KICAD-VERIFIED (10.0.x; GUI save) | H-K-PRO-VERSION |
| A pattern entry is `{"netclass": <class>, "pattern": <pattern>}`; every entry of the 19 template projects holds exactly these two keys | S-0066 | INFERRED | H-K-PRO-PATTERNS |
| A pattern is a wildcard (`*` any run, `?` one character) or a regular expression (wxWidgets advanced flavour); a net matching several patterns gets every matching class, which form an aggregate class by the priority order of Board Setup | S-0046, S-0010, S-0038 | INFERRED | H-K-PRO-PATTERNS |
| The exact-name patterns `+3V3` and `SIG1` select only themselves (`SIG10` stays out), and the entries `Net-(R1-Pad1)`, `D[0]`, `IN+`, `VCC_3.3` and `SW?_*` also select `Net-R1-Pad1`, `D0`, `INN`, `VCC_3V3` and `SW1_A`: patterns are whole-name wildcards and regular expressions | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-PATTERNS |
| A class clearance assigned by an exact-name pattern is enforced by `pcb drc`; without the project file, or without the class, it is not | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-NETCLASS |
| A project cut to `meta` and `net_settings` gives the same violations as the full file | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-MIN |
| `board.design_settings.rules` holds the board-setup minimums, among them `min_clearance`, `min_track_width`, `min_via_diameter` and `min_through_hole_diameter`; the empty save sets 0, 0.2, 0.5 and 0.3 mm | S-0020 | KICAD-VERIFIED (10.0.x; GUI save) | H-K-PRO-FLOOR |
| A `min_clearance` above a class clearance governs: HV at 0.5 mm gives no violation at a 1.0 mm gap, and does once `min_clearance` is 1.5 | S-0038, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-FLOOR |
| `kicad-cli pcb drc` and `pcb export svg` never rewrite `.kicad_pro`; 10.0.6 writes a `.kicad_prl` next to the board, 9.0.9 does not | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-PRL |
| A `.kicad_dru` next to the board is read without a project file; only the net classes need the project | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-TOK-RULES-SILENT |
| `board.design_settings.rules` also holds `min_copper_edge_clearance` (0.5 mm in the empty save); `kicad-cli` 9.0.9 and 10.0.6 apply all five minimum keys to items that no custom rule governs | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-MIN-KEYS |
| A board-wide custom rule governs below the board-setup minimums: an item between the rule's `min` and a higher minimum is not reported, although the manuals call the minimums absolute | S-0038, S-0010, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-MIN-RULE-2 |
| The project Fenolite writes from board-wide rules lets every rule value take effect | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-MIN-WRITE |
| A board-wide custom clearance rule governs the items of a class with a larger clearance: the class clearance is not applied | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-MIN-CLASS |
| Net-class track widths and via sizes are defaults for new items, not DRC limits | S-0038, S-0010 | INFERRED | H-K-PRO-MIN-CLASS |
| The class keys `diff_pair_width`, `diff_pair_gap` and `diff_pair_via_gap` are defaults of the interactive pair router and no DRC limits: a pair laid 0.15 mm apart with 0.2 mm tracks in a class of pair gap 0.4 mm and pair width 0.3 mm, and two vias of a pair 0.3 mm apart under a via gap of 0.5 mm, report nothing | S-0010, S-0038, S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-PAIR |
| A class `diff_pair_gap` below the class clearance lowers the clearance between the two nets of a pair of that class (nets that pair by name): at 0.15 mm in a class of clearance 0.2 mm and pair gap 0.1 mm there is no `clearance` violation, while two nets of the class that do not pair, and a pair in a class whose pair gap is 0.25 mm, are reported | S-0010, S-0038, S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-PAIR |
| A custom clearance rule that governs the pair replaces the class pair gap: under a board-wide rule of 0.2 mm the pair at 0.15 mm is reported, and a later clearance rule of 0.1 mm with `inDiffPair` on both sides makes it clean again; a `diff_pair_gap` rule does not lower the clearance | S-0010, S-0038, S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-PAIR |
| A board `min_clearance` above the class pair gap is a floor inside a pair, and adds a gap check at that minimum (`diff_pair_gap_out_of_range`, "netclass … (diff pair) minimum gap") unless a `diff_pair_gap` rule governs the pair: with a minimum of 0.12 mm a pair at 0.11 mm gets both violations and a pair at 0.13 mm none | S-0010, S-0038, S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-PAIR |

## Versions

`pro.PROJECT_VERSIONS` holds the pair (`meta.version`, `net_settings.meta.version`) written per target:
(3, 4) for KiCad 9 and (3, 5) for KiCad 10. The project file stays outside `versions.FileKind`.

- `classify_project` gives `FUTURE` above `meta.version` 3 or `net_settings.meta.version` 5, and
  `SUPPORTED` otherwise, absent versions included: KiCad reads a `{}` project.
- A `FUTURE` project is read with the warning `kicad.version.future` and never edited
  (`FutureFormatError`).
- `update_project` edits only a project whose pair is one of `PROJECT_VERSIONS`; any other pair, `{}`
  and versions 1 and 2 included, raises `UnsupportedFormatError` with a hint to re-save the project in
  KiCad 9 or 10. An update keeps the existing pair, except the lossy target-9 path below.

## Templates

- `src/fenolite/backends/kicad/data/project_template_10.json` is the KiCad 10.0.6 GUI save
  `tests/data/kicad/project/empty_10.kicad_pro` with `meta.filename` set to `""`. The project was made
  from KiCad's default project template (what New Project does), opened in the KiCad 10.0.6 GUI on
  macOS, and saved once from the PCB Editor and once from the Schematic Editor.
- **Decision 5 fallback.** No 9.0.9 GUI save was made, so `project_template_9.json` is derived from
  the 10 template by these steps: remove the top-level keys `component_class_settings`,
  `tuning_profiles` and `time_domain_parameters` and the class key `tuning_profile`, and set
  `net_settings.meta.version` to 4. The 9.0 side of `H-K-PRO-VERSION` stays `INFERRED`; the 9.0.9
  oracle reads the derived file (every target-9 case below passes on 9.0.9).
- `pro.TEN_ONLY_PATHS` is the key paths of the 10 template absent from the 9 template, list items
  written `*`.

## Synthesis

`synthesize_project(design, *, target, board_name)` starts from a fresh copy of the target's template:

- `meta.filename` is `<board_name>.kicad_pro`;
- `net_settings.classes` is the template's `Default` entry, then one entry per model `NetClass` other
  than `Default`, sorted by name; a model class named `Default` updates the first entry;
- `net_settings.netclass_patterns` holds one exact-name entry per net whose class is not `Default`,
  sorted by net name. No assignment is ever written;
- every other key keeps its template value, `boards` (`[]`) included.

Class values are written by `lowering.lower_netclass` from the `Default` entry of the project being
written: the seven values of `lowering.NETCLASS_KEYS` as exact millimetre texts (`clearance`,
`track_width`, `via_diameter`, `via_drill`, and since change c0104 `diff_pair_width`, `diff_pair_gap` and
`diff_pair_via_gap`), every other key copied. A model value of `None` keeps the value of the `Default`
entry, so a class without pair values carries the template's 0.2, 0.25 and 0.25 mm. The three pair
values have no board-setup minimum and get no floor warning; what a pair gap does to the clearance inside
a pair is in the facts above, and `checks.clearance` follows it (`copper.md`). Both templates hold the
three keys in every class entry, so both targets write them. A value below its
board-setup minimum is still written, with the warning `kicad.project.below-floor`, because the
minimum governs. The minimums themselves are written first ("Board-setup minimums").

## Board-setup minimums

`board.design_settings.rules` (`pro.MINIMUM_POINTER`) holds the board-setup minimums. Five of them are
derived from the design's board-wide rules (change c0026); the other 14 members are kept verbatim.

| rule kind (normal form) | key, targets 9 and 10 |
|---|---|
| `clearance` | `min_clearance` |
| `track_width` | `min_track_width` |
| `via_diameter` | `min_via_diameter` |
| `hole_size` (with `via_drill`) | `min_through_hole_diameter` |
| `edge_clearance` | `min_copper_edge_clearance` |

These are Fenolite's choices on top of the facts above:

- **Board-wide.** A rule is board-wide when its normal form has selector `all`, no second selector and
  no layers. A `via_drill` rule on `all` selects vias only, so it is not board-wide.
- **Value.** Per kind, the governing board-wide rule is the last one in KiCad's order
  (`H-K-DRU-ORDER`). With severity `error` and a `min`, its key gets the least `min` among it and the
  later rules of its kind, so no rule's `min` is below the written minimum. Rules before it never
  govern and do not count. Otherwise the key is kept (`kicad.project.minimum-kept`). Without a
  board-wide rule of the kind, nothing is written.
- **Writing.** Synthesis and updates write the minimums before the classes, so
  `kicad.project.below-floor` compares class values with the written minimums. A value equal in
  nanometres keeps its text; a new value is the exact millimetre text. A missing key is appended to
  the rules object, a missing parent object to its parent, and a parent that is not an object raises
  `FormatError` with its pointer. Updates report each changed or added key
  (`kicad.project.minimum-replaced`); synthesis does not. Without a board-wide rule the text is the
  same as without rules.
- **Read-back.** `pro.project_minimums(data)` reads the five values; they are never lifted into the
  model's rules. The rules come back from `.kicad_dru`, and writing again gives the same minimums.
- **Conflicts.** `kicad.project.rule-below-minimum` would name a rule below a minimum that is not
  written, on the majors of `lowering.FLOOR_OVER_RULES`; that table is empty, because a custom rule
  governs below the minimums on 9.0.9 and 10.0.6 (`H-K-PRO-MIN-RULE-2`). After the classes,
  `lowering.class_conflicts` compares every class clearance with the governing board-wide clearance
  rule. On the majors of `RULES_OVER_CLASSES` (9 and 10, `H-K-PRO-MIN-CLASS`) a larger class clearance
  is not applied, so `kicad.project.class-shadowed` names the class, unless it is a `Default` entry
  that the model does not set, or a later clearance rule on `netclass <name>` restores it. Elsewhere
  `kicad.project.default-over-rule` would name a template `Default` clearance above the rule.
- **Not seen.** Opaque rules and rules kept verbatim by other changes are not read, and micro-via
  minimums are not written.

## Patterns

`pro.pattern_matches(pattern, name)` follows S-0046: a whole-name wildcard match, or a whole-name
regular-expression match (Python's `re` stands in for the wxWidgets flavour; a pattern that does not
compile matches as a wildcard only). An exact net name can therefore match other nets
(`Net-(R1-Pad1)` matches `Net-R1-Pad1`). Synthesis refuses a classed net with `kicad.project.pattern-unsafe`
when its name holds `*` or `?`, or when its exact-name pattern matches another net of the design in
another class; `allow_lossy` writes it without a pattern instead (`kicad.project.dropped-pattern`).

## Updates

`update_project(existing_text, design, *, target)` changes only the managed keys:

- class entries named like a model class get their seven values replaced (the four lengths and the
  three pair values); a value equal in nanometres keeps its spelling, and a key whose model value is
  `None` is left as it is. Model classes absent from the file are appended, lowered from the file's
  `Default` entry. A class is never deleted;
- exact-name pattern entries (no `*` or `?`) naming a model net are regenerated and placed first;
  every other entry is kept verbatim after them. A kept entry or assignment that gives a model net
  another class gives `kicad.project.pattern-conflict`;
- every other key, its position and its number spelling stay as read.

For target 9, a project holding a `TEN_ONLY_PATHS` key or the pair (3, 5) is refused: with
`DowngradeRefusedError` when the board was read from a 10.0 file, else with `LossyWriteError` naming
each path (`kicad.project.too-new-key`). `allow_lossy` removes the paths, writes
`net_settings.meta.version` 4 and warns (`kicad.project.dropped-too-new`). With `downgrade` (a board
read from a 10.0 file, change c0162) each top path is decided by its `project:` row of the downgrade
resolver: `same` when it holds the default below, else `design`, which needs `allow_lossy`.

### Default sections of KiCad 10

`pro.holds_default(data, path)` is true when every value at `path` (list items written `*`) equals a
value of the 10 template there, key order aside and numbers compared as written. The maintainer decided
on 2026-10-09 that a downgrade drops such a section as `same` (Open decisions, row 41).

| fact | source | label | hypothesis |
|---|---|---|---|
| A fresh KiCad 10.0.6 project writes `component_class_settings` as `{"assignments": [], "meta": {"version": 0}, "sheet_component_classes": {"enabled": false}}`, `tuning_profiles` as `{"meta": {"version": 0}, "tuning_profiles_impedance_geometric": []}` and the class key `tuning_profile` as `""`: the GUI save `empty_10` (the 10 template) holds these, and so does the project that the `pcbnew` module of the pinned image `kicad/kicad:10.0.6` saves for a new board (`NewBoard` and `SaveBoard`, run as a subprocess in the container on 2026-10-09; meta `version` 3, `net_settings.meta.version` 5) | S-0020, S-0029 | KICAD-VERIFIED (10.0.x; GUI save) | H-K-PRO-TUNING |
| The two demo projects of format 10 hold the same `component_class_settings` and every class `tuning_profile` `""`; `pic_programmer` holds the same `tuning_profiles` and `CM5_MINIMA_3` none (measured on 2026-10-09 on the project files the corpus rebuilds) | S-0023, S-0024 | CORPUS-VERIFIED | H-K-DOWN-DEMOS |

## Reading

`read_project(source)` returns a `ProjectInfo` whose `ProjectClass` entries hold the seven lowered
values in nm, the three pair values among them; `apply_project(design, info)` gives the design the
project's classes (ids `derived_id("cls", "kicad", "netclass:<name>")`) and each net the matching class
of highest priority (lowest `priority`, ties in file order). Several candidates give
`kicad.project.multiple-classes`, because KiCad aggregates them while the model keeps one class per
net.

## Issue codes

| code | severity | when |
|---|---|---|
| `kicad.project.below-floor` | warning | a lowered class value is below its board-setup minimum |
| `kicad.project.pattern-unsafe` | error | a classed net name holds `*` or `?`, or its exact-name pattern matches a net of another class |
| `kicad.project.dropped-pattern` | warning | under `allow_lossy`, such a net written without a pattern |
| `kicad.project.too-new-key` | error | a `TEN_ONLY_PATHS` key or the pair (3, 5) in a project written for target 9 |
| `kicad.project.dropped-too-new` | warning | such a key removed under `allow_lossy` |
| `kicad.project.multiple-classes` | warning | on read, several classes match one net |
| `kicad.project.unknown-class` | warning | a pattern or assignment names a class absent from `classes` |
| `kicad.project.pattern-conflict` | warning | on update, a kept entry gives a model net another class |
| `kicad.project.inexact-value` | info | a class value or floor that is not a whole number of nm |
| `kicad.project.unlowered-field` | info | a non-empty `NetClass.description` |
| `kicad.project.unread-entry` | info | a pattern or assignment entry of unexpected shape, or a tuning profile or layer entry that cannot be read into an impedance target (c0105) |
| `kicad.project.minimum-replaced` | info | an update writes a minimum that is absent, not a number, or different in nanometres |
| `kicad.project.minimum-kept` | info | the governing board-wide rule has a severity other than `error` or no `min` |
| `kicad.project.rule-below-minimum` | warning | a rule asks for less than a minimum that is not written, on a major of `FLOOR_OVER_RULES` |
| `kicad.project.class-shadowed` | warning | a board-wide clearance rule overrides a larger class clearance |
| `kicad.project.default-over-rule` | warning | the template `Default` clearance stays above a board-wide clearance rule, on a major outside `RULES_OVER_CLASSES` |
| `kicad.project.unknown-check` | error | a check severity names a code whose key is not a `rule_severities` key of the target's template (c0114); droppable |
| `kicad.project.dropped-check` | warning | with `--allow-lossy`, that severity was left out |
| `kicad.project.profile-reassigned` | warning | a class of an impedance target named another non-empty tuning profile, and the build set its key to the target (c0105) |

## Census

Measured on 2026-10-01 and 2026-10-02 (key names and counts only): the demos hold 36 `.kicad_pro`
files at 10.0.6 and 37 at 9.0.9.1; the version pair (3, 5) appears only at 10.0.6. The 19 template
projects of S-0066 all hold (3, 4), `boards: []` and `netclass_assignments: null`. Counts from the
corpus rows are in `docs/evidence/kicad-project.md`.

## Check severities (c0114)

`board.design_settings.rule_severities` gives each DRC check a severity (`error`, `warning` or `ignore`),
by the check's key.

| fact | source | label | hypothesis |
|---|---|---|---|
| 10.0.6 applies exactly the 62 `rule_severities` keys of the packaged template of 10: with every one at `ignore`, `ignored_checks` lists those 62 and no entry remains on a bench whose control run fires six checks | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-PRO-SEV-KEYS |
| 10.0.6 ignores a key outside that set without a message: `overlapping_pads` and an invented key at `ignore` are not listed and change nothing | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-PRO-SEV-KEYS |
| A severity that the project writer sets from the design reaches the report: `via_dangling` at `error` makes the entry an `error`, where the template gives `warning` | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-PRO-SEV-KEYS |
| The packaged template of 9 holds the same 62 keys as that of 10, from which it was derived; which keys 9.0.9 applies cannot be read from a run, because its report lists no ignored check | S-0029 | INFERRED | H-K-PRO-SEV-KEYS |
| Six keys of the templates appear in no demo project of tag 9.0.9.1 (`footprint_symbol_field_mismatch`, `missing_tuning_profile`, `text_on_edge_cuts`, `track_not_centered_on_via`, `track_on_post_machined_layer`, `tuning_profile_track_geometries`), and two keys absent from the templates appear in most (`hole_near_hole`, `overlapping_pads`): a demo project holds the keys of the KiCad that last saved it | S-0058 | INFERRED | H-K-PRO-SEV-KEYS |

The last row is the census that change c0114 states (2026-10-05); this change did not run it again. For
target 9 a key of a check that 9.0.9 lacks would therefore be written and have no effect.

- **Key rule.** The key of the finding code `kicad.drc.<suffix>` is the suffix with `-` as `_`
  (`kicad.drc.silk-overlap` → `silk_overlap`). `pro.SEVERITY_KEYS[target]` is the key set of the target's
  packaged template: exact for 10, `INFERRED` for 9.
- **Writing.** `synthesize_project` and `update_project` set the key of each code of
  `RuleSet.severities` (`design.rules.severity()`). A key the design does not name keeps its template
  value on synthesis and its file value on an update, its position included.
- **Unknown key.** A code whose key is outside `SEVERITY_KEYS[target]` is refused with
  `kicad.project.unknown-check` (`FEN-7001`, droppable), because KiCad would ignore it silently; with
  `--allow-lossy` it is left out and reported as `kicad.project.dropped-check`.

## Stored exclusions (c0114)

`board.design_settings.drc_exclusions` lists the DRC entries the user excluded in KiCad.

| fact | source | label | hypothesis |
|---|---|---|---|
| An entry is the string `<type>\|<x>\|<y>\|<uuid>\|<uuid>`, `x` and `y` in integer nanometres and the nil uuid for a missing second item, or a list of that string and a comment; `pcb drc` applies both forms | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRC-EXCL |

A public demo project of tag 10.0.6 stores five exclusions in the list form, each with its comment
(S-0058; the reading that change c0114 states, not run again here).

`read_project` returns them as `ProjectInfo.exclusions` (`StoredExclusion`: type, position, the two
uuids, comment), in file order; an entry of another shape is skipped with `kicad.project.unread-entry`.
`KicadBackend.stored_exclusions(project)` reads the project file of a copy set and returns `()` when it
is missing or cannot be read. Nothing writes the list: `update_project` keeps it verbatim, and when
KiCad applies an entry is in `drc.md`, "Stored exclusions".

## Tuning profiles (c0105)

A KiCad 10 tuning profile is an entry of `tuning_profiles.tuning_profiles_impedance_geometric`; a class
names it by its key `tuning_profile`. Fenolite writes one profile per impedance target of the design
(`backends/kicad/tuning.py`; guide `docs/impedance.md`), and reads back the profiles a class names.

| fact | source | label | hypothesis |
|---|---|---|---|
| A profile written with `profile_name`, `type`, `target_impedance`, `enable_time_domain_tuning`, `layer_entries` (each `signal_layer`, `top_reference_layer`, `bottom_reference_layer`, `width`, `diff_pair_gap`, `delay`), `via_prop_delay` and `via_overrides` is loaded by `pcb drc` 10.0.6 and judged (measured 2026-10-05, design of c0105; owed: probe `pro-tuning-width` on kicad-cli 10); the keys `frequency`, `model_solder_mask` and `net_chain_bridge_prop_delay` with `meta.version` 2 are loaded with the same findings (measured 2026-10-05). Whether a GUI save writes the same key set is not known (owed: the GUI save of `H-K-PRO-TUNING-KEYS`) | S-0020 | INFERRED | H-K-PRO-TUNING-KEYS |
| `type` 1 makes a profile check the pair gap of its class (`diff_pair_gap_out_of_range`) and not its single tracks; `type` 0 checks single tracks (measured 2026-10-05, design of c0105; owed: probes `pro-tuning-gap`, `pro-tuning-single-under-diff` and `pro-tuning-width` on kicad-cli 10) | S-0020 | INFERRED | H-K-PRO-TUNING-DRC |
| A profile whose layer entries lack the two reference keys is not loaded: DRC reports `missing_tuning_profile` for the class that names it | S-0020 | INFERRED | H-K-PRO-TUNING-DRC |
| A width written `350000.0` is loaded, and the keys of later schemas with `meta.version` 2 are loaded without a change in the findings | S-0020 | INFERRED | H-K-PRO-TUNING-DRC |
| `pcb upgrade --force` leaves a project with profiles byte for byte unchanged: `kicad-cli` never saves a project, so the key set a GUI save writes is not observable headless | S-0020, S-0022 | INFERRED | H-K-PRO-TUNING-KEYS |

What Fenolite writes, for target 10 only (`tuning.apply_profile_keys`, called by `write_triad` after
`apply_sheet_keys`):

- `lower_profile(target)`: `profile_name` the target's name; `type` 0 or 1; `target_impedance` the exact
  text of `ohms` (`0` when empty); `enable_time_domain_tuning` false; one layer entry per layer in stack
  order (with one reference, it is `bottom_reference_layer` and `top_reference_layer` is `""`; with two,
  the upper one is the top); `width` and `diff_pair_gap` as integers of nanometres (`0` for a single
  target); `delay` 0; `via_prop_delay` 0; `via_overrides` empty. This is the key set of `meta.version` 0,
  which the 10.0.6 template holds. The key names and kinds are those of the bench that `pcb drc` 10.0.6
loaded on 2026-10-05; no source document states them (the maintainer's clean-room correction of 2026-10-08 withdrew the one
first cited, a page of KiCad's source code).
- A profile named like a target is replaced in place, the other targets are appended sorted by name, and
  every other profile is kept, structurally equal and with its number spellings. None is deleted.
- The class key of each class of a target is set to the target's name; a class that named another
  non-empty profile gives `kicad.project.profile-reassigned`. A class without a target keeps its key.
- `tuning.PROFILE_KEY_PATHS` are taken out of the template-value, added-path and keep rules of
  "Synthesis" and "Updates". For target 9 and for a design without targets the text is returned
  unchanged, and the paths stay in `TEN_ONLY_PATHS`.

Reading (`read_project`, `apply_project`): `ProjectInfo.profiles` holds the profiles and
`ProjectInfo.class_profiles` the class keys. Each profile that a class names becomes an
`ImpedanceTarget` of those classes: kind from `type`, `ohms` the decimal text of `target_impedance` (`""`
for 0), no tolerance, one row per entry with copper layers. An entry that lacks a key of the written form,
has a width or gap that is not a whole number of nanometres, or names a layer the board does not have, is
skipped with `kicad.project.unread-entry`. A profile that no class names stays in the file only.
