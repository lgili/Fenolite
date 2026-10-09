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
    because writing for an older major would drop what that major cannot read, unless the caller asks
    for a downgrade (`downgrade=True`, below); the hint names `fenolite convert`.

## Downgrade

A downgrade writes a file that KiCad 10 saved for KiCad 9 (change c0162). It is asked for with
`downgrade=True` on `check_target`, `pcb.write_board`, `mod.write_footprint` and `mod.write_pretty`,
`sch.retarget_schematic`, `sym.retarget_symbol_library`, `pro.update_project` and `dru.write_rules`; only
`fenolite convert` asks for it (`docs/conversion.md`). `build`, `place`, `route` and `fill` never do: a
layout saved by 10 is not silently rebuilt for 9. Without `downgrade` every output is unchanged.

**The capability resolver.** `data/downgrade.toml` holds one row per token row of `tokens.md` newer than
9, per such form row, per key path of the KiCad 10 project template that the 9 template lacks
(`pro.TEN_ONLY_PATHS`, ids `project:<path>`), for the project's net settings version, and for the
constructs the board writer decides (`npth-front-back`). `resolver.load()` refuses a missing row, an
unknown or repeated id and an incomplete `rewrite`. Each row has an action, and may hold the values
`when` for which it holds and an action `else` for the others:

| action | the downgrade | reported as |
|---|---|---|
| `rewrite` | writes the construct in 9's form | `changed` |
| `same` | drops it: 9 behaves as the source with that value | `changed` |
| `presentation` | drops it: a drawing, a text or metadata changes, nothing that is made or checked | `lost` (`report`) |
| `design` | drops it: what is made or checked changes; needs `--allow-lossy` | `lost` (`refuse`) |

The actions of every row are in the column `downgrade` of `tokens.md` and its section "Downgrade of
project keys". The maintainer decided on 2026-10-09 that a dropped via-protection value is `design`
unless it is the default, and so is a dropped position-file flag (`in_pos_files no`).

**Edits at the node.** `resolver.resolve(root, kind, target)` edits, for each `kicad.token.too-new` issue
of `check_emittable`, the node that the issue locates, inside opaque content too: a `rewrite` replaces it,
the other actions remove it. Two rows edit the parent of the located node: `tenting-front` and
`tenting-back` (one `tenting` holds both sides) and `hatch-position` (the zone `property` that holds it).
No node that only holds a construct is removed: a board keeps its `setup`. The board writer emits the
modelled vias and zone fills in 9's form itself and records their edits (`via protection`, `island`), it
writes the nets by number with a net table (`net-by-name`), and it gives every zone
`(filled_areas_thickness no)`.

| fact | source | label | hypothesis |
|---|---|---|---|
| The absent default of `covering`, `plugging`, `capping` and `filling` is `no`: 10.0.6 re-saves a board of format 10 without them with `no` in `setup` and nothing on a via (each value the board's), and a board of format 9 with `no` on every via; 9.0.9 rejects them | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DOWN-ROWS |
| 9.0 has one type for blind and buried vias: `(via blind …)` with an inner span loads in 9.0.9 with the DRC of the buried via in 10.0.6, which reads it back as a blind via of that span | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DOWN-ROWS |
| 10.0.6 reads 9's `(tenting front)` on a via or a pad as `(front yes) (back none)` and drops `(tenting none)` there, while in `setup` it reads it as `(front yes) (back no)`; a via's or pad's side `no` has no 9 form | S-0020, S-0029 | KICAD-VERIFIED (10.0.x) | H-K-DOWN-ROWS |
| 9.0.9 refuses a zone `property` left with its `layer` alone, and 10.0.6 does not load its own save of a silkscreen zone with `hatch_position` (the property on the layer `UNDEFINED`) | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DOWN-ROWS |
| A zone of format 10 has no `filled_areas_thickness`; written for 9 without `(filled_areas_thickness no)`, its fill is grown by `min_thickness / 2` (the converted `pic_programmer` gave clearance violations in 9.0.9 and 10.0.6) | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ZONE-FAT9 |
| 10.0.6 reads an `np_thru_hole` pad of a board of format 9 with every copper layer, whatever its `layers` say (`"F&B.Cu"`, `"F.Cu" "B.Cu"`): a hole restricted to the outer layers of a board with inner layers has no 9 form (row `npth-front-back`, `design`) | S-0020, S-0029 | KICAD-VERIFIED (10.0.x) | H-K-DOWN-DEMOS |
| A label on a single pin is `label_dangling` or `global_label_dangling` in 9.0.9's ERC and `isolated_pin_label` in 10.0.6's | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-TYPES |

**Benches.** Each row of a board, footprint, schematic or symbol kind has a bench
(`tests/kicad/downgrade/_downbench.py`): the row's fuzz example in the fuzz skeleton at the header of 10,
saved by 10.0.6 (`tests/data/kicad/downgrade/`; a construct 10.0.6 does not write back keeps its authored
file), with a variant per other value of a `when` row. Fenolite downgrades it; 9.0.9 loads it and its DRC
or ERC by type equals 10.0.6's on the source; for `rewrite` and `same`, 10.0.6's re-save of the downgraded
file gives the source (level 5 for a board, the tree for a schematic or a library). The probes
`down-row-<bench>` record each outcome; the rules rows (every one `design`: 9.0.9 drops the whole rules
file on a constraint it does not know) and the project rows have no bench. The demo projects of format 10
are the probe `down-demos` (`H-K-DOWN-DEMOS`).

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
