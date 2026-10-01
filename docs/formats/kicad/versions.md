# KiCad format versions and gating

`fenolite.backends.kicad.versions` holds the format version constants, file kind and version detection,
the read and write policy, and access to the token inventory (`tokens.md`, generated). Fenolite reads
files from KiCad 8.0 on and writes for KiCad 9.0 or 10.0 (default 10.0). Sources are listed in
`docs/evidence/sources.md`.

## Constants

Each cell gives the version, its source and the evidence level reached on 2026-10-01.

| kind | 8.0 | 9.0 | 10.0 |
|---|---|---|---|
| board `.kicad_pcb` | 20240108 (S-0030, INFERRED, `H-K-TOK-CONSTANTS`) | 20241229 (S-0030, INFERRED: 9.0 has no `pcb upgrade`; the footprint constant below is the same number) | 20260206 (S-0030, KICAD-VERIFIED: `pcb upgrade` on 10.0.6) |
| footprint `.kicad_mod` | 20240108 (S-0030, INFERRED) | 20241229 (S-0030, KICAD-VERIFIED: `fp upgrade` on 9.0.9) | 20260206 (S-0030, KICAD-VERIFIED: `fp upgrade` on 10.0.6) |
| schematic `.kicad_sch` | 20231120 (S-0031, INFERRED) | 20250114 (S-0031, INFERRED: 9.0 has no `sch upgrade`) | 20260306 (S-0031, KICAD-VERIFIED: `sch upgrade` on 10.0.6) |
| symbol library `.kicad_sym` | 20231120 (S-0031, INFERRED) | 20241209 (S-0031, KICAD-VERIFIED: `sym upgrade` on 9.0.9) | 20251024 (S-0031, KICAD-VERIFIED: `sym upgrade` on 10.0.6) |
| worksheet `.kicad_wks` | 20231118 (S-0032, INFERRED) | 20231118 (S-0032, KICAD-VERIFIED: boundary probe on 9.0.9) | 20231118 (S-0032, KICAD-VERIFIED: boundary probe on 10.0.6) |
| custom rules `.kicad_dru` | — | `(version 1)` (S-0010, INFERRED) | `(version 1)` (S-0038, INFERRED) |

The worksheet grammar is frozen: the constant is unchanged from 8.0 to 10.0.6 (S-0032), and so is the
list of names (S-0036). The rules grammar is not frozen, although its header stays `(version 1)`: the
10.0 manual adds constraint types and disallow kinds that 9.0 does not know (S-0038 against S-0010,
`H-K-TOK-RULES-DRIFT`, verified: 9.0.9 drops every custom rule when one uses them).

## Detection

- **Kind** comes from the root head (`kind_of`):
  - `kicad_pcb`, `footprint`, `kicad_sch` and `kicad_symbol_lib` give the board, footprint,
    schematic and symbol-library kinds.
  - `kicad_wks` and the legacy roots `page_layout` and `drawing_sheet` give a worksheet.
  - The synthetic `kicad_dru` node gives custom rules (see "Rules text" below).
  - The pre-6 footprint root `module` raises `UnsupportedFormatError`, with a `kicad-cli fp upgrade`
    hint.
  - `kind_for_suffix` exists only for callers that have no parsed node yet.
- **Version** is the integer of the root's `(version N)` (`detect_version`).
  - A legacy worksheet root without one reads as 0.
  - Observed: a `drawing_sheet` root without a version does not load in 10.0.6 (S-0020); a
    `page_layout` root without one does.
- **Major** (`major_for`) is the oldest major whose constant is at least the version.
  - Development versions written by nightly builds (`generator_version "8.99"`/`"9.99"`) map to the
    release that reads them.
  - Observed: `20241030` loads on 9.0.9 and 10.0.6; `20250513` and `20250907` load on 10.0.6
    (`H-K-TOK-DEV`).

## Read and write policy

- **Status** (`classify`):
  - `TOO_OLD` below the read floor (the 8.0 constants; 0 for worksheets; 1 for rules);
  - `FUTURE` above every known constant;
  - `SUPPORTED` otherwise.
- **Too old:** `require_readable` refuses it with `UnsupportedFormatError`, CLI code `FEN-3003`, exit 3.
  The hint names the upgrade command: `kicad-cli pcb upgrade` or `sch upgrade` (both need KiCad 10.0),
  `fp upgrade` or `sym upgrade`.
- **Future:** a future file can be inspected, and `version_issues` reports `kicad.version.future`.
  `require_editable` refuses to edit it with `FutureFormatError` (`FEN-3002`, exit 3).
  - Observed with the isolated environment below: kicad-cli 9.0.9 and 10.0.6 refuse to load a board
    whose header is newer than their own (exit 3, "created with a more recent version",
    `H-K-TOK-FUTURE`). This contradicts an earlier exploratory note that 10.0.6 loads such a board.
  - Fenolite is still stricter than KiCad for rules: classifying a rules file with `(version 2)` as
    future is Fenolite policy. An exploratory run saw 10.0.6 accept such a file (S-0020; not covered
    by the fuzz).
- **Development versions** get a `kicad.version.dev` info issue: supported, above the kind's lowest
  released constant, and equal to no released constant.
- **Targets** are 9 and 10 (`check_target`).
  - It returns the header to write.
  - It refuses a target older than the input's major with `DowngradeRefusedError` (`FEN-7002`, exit 7),
    because writing for an older major would drop what that major cannot read.
  - Downgrade stays refused until a capability resolver exists.

## Token inventory and the emit check

- `tokens.md` (generated from `data/tokens.toml`) lists every board/footprint name or value
  introduced after 8.0, the tokens 10.0 reads but no longer writes, value-form changes, and the
  worksheet and rules vocabularies.
- Each row was proved on kicad-cli 9.0.9 and 10.0.6 by the token fuzz:
  `docs/evidence/kicad/token-fuzz/9.0.9.json` and `10.0.6.json`.
- `check_emittable(node, kind, target)` reports, at the exact `walk` locators:
  - headers missing or newer than the target;
  - tokens newer than the target (error);
  - tokens the target no longer writes (warning);
  - for worksheets and rules, names outside the vocabulary.

## Rules text

A custom-rules file has no root list. `wrap_rules(text)` wraps its top-level lists in a synthetic
`kicad_dru` node, and `rules_text(node)` prints them back without the wrapper. Only the common subset is
supported: `#` comment lines and single-quoted names raise `FormatError`, because the full rules
dialect needs the rules reader. Facts observed with 10.0.6 (S-0020):

- `within_diff_pairs` is written as a list, `(within_diff_pairs)`.
- `track_angle` takes a plain number.
- `solder_paste_rel_margin` accepts only a value with a length unit.

Any other form makes KiCad drop every custom rule silently, with exit 0 (`H-K-TOK-RULES-SILENT`).

## Oracle

`tools/kicad_token_fuzz.py` decides "loads" with one command per kind:

| kind | command | loads when |
|---|---|---|
| board | `pcb export svg <f> -l Edge.Cuts --mode-single -o out.svg` | exit 0 and the SVG exists (load failure: exit 3) |
| footprint | `fp export svg <dir>.pretty -o <existing dir>` | exit 0 and an SVG exists (library failure: exit 2) |
| worksheet | `pcb export svg <skeleton board> --drawing-sheet <f> …` | the output lacks "Error loading drawing sheet" (exit is always 0) |
| rules | `pcb drc --format json -o r.json` on the canary board with `canary.kicad_pro` | the canary clearance violation is in the report (errors silently disable all rules) |

- **Environment:** every run happens in a fresh temporary directory, with
  `KICAD_CONFIG_HOME=<tmp>/cfg`, `LANG=C` and `LC_ALL=C`. It has a timeout, and its output is
  sanitised.
- **Images:** the 9.0 runs use `kicad/kicad:9.0.9@sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729`,
  and the `kicad-10` CI job uses
  `kicad/kicad:10.0.6@sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec` (S-0029).
- **`kicad_min_major(N)`:** tests marked with it skip on an older kicad-cli. This covers `pcb upgrade`,
  `sch upgrade` and `pcb import`, which exist in 10.0 only (`H-K-00`, S-0022 against S-0037). The
  skip is never a failure, even with `FENOLITE_REQUIRE=kicad`.
