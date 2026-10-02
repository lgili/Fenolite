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
written: the four values as exact millimetre texts, every other key copied. A value below its
board-setup minimum is still written, with the warning `kicad.project.below-floor`, because the
minimum governs.

## Patterns

`pro.pattern_matches(pattern, name)` follows S-0046: a whole-name wildcard match, or a whole-name
regular-expression match (Python's `re` stands in for the wxWidgets flavour; a pattern that does not
compile matches as a wildcard only). An exact net name can therefore match other nets
(`Net-(R1-Pad1)` matches `Net-R1-Pad1`). Synthesis refuses a classed net with `kicad.project.pattern-unsafe`
when its name holds `*` or `?`, or when its exact-name pattern matches another net of the design in
another class; `allow_lossy` writes it without a pattern instead (`kicad.project.dropped-pattern`).

## Updates

`update_project(existing_text, design, *, target)` changes only the managed keys:

- class entries named like a model class get their four values replaced; a value equal in nanometres
  keeps its spelling. Model classes absent from the file are appended, lowered from the file's
  `Default` entry. A class is never deleted;
- exact-name pattern entries (no `*` or `?`) naming a model net are regenerated and placed first;
  every other entry is kept verbatim after them. A kept entry or assignment that gives a model net
  another class gives `kicad.project.pattern-conflict`;
- every other key, its position and its number spelling stay as read.

For target 9, a project holding a `TEN_ONLY_PATHS` key or the pair (3, 5) is refused: with
`DowngradeRefusedError` when the board was read from a 10.0 file, else with `LossyWriteError` naming
each path (`kicad.project.too-new-key`). `allow_lossy` removes the paths, writes
`net_settings.meta.version` 4 and warns (`kicad.project.dropped-too-new`).

## Reading

`read_project(source)` returns a `ProjectInfo`; `apply_project(design, info)` gives the design the
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
| `kicad.project.unread-entry` | info | a pattern or assignment entry of unexpected shape |

## Census

Measured on 2026-10-01 and 2026-10-02 (key names and counts only): the demos hold 36 `.kicad_pro`
files at 10.0.6 and 37 at 9.0.9.1; the version pair (3, 5) appears only at 10.0.6. The 19 template
projects of S-0066 all hold (3, 4), `boards: []` and `netclass_assignments: null`. Counts from the
corpus rows are in `docs/evidence/kicad-project.md`.
