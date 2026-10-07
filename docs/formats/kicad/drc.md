# KiCad DRC reports (JSON)

`kicad-cli pcb drc --format json --severity-all -o <out> <board>` writes a report of the design rule
check. `fenolite.backends.kicad.drc.read_drc_report` reads it into the neutral `DrcReport` of
`fenolite.backends.base`. This page describes the report in Fenolite's own words. Key names come from
the schema files S-0055 (tag 10.0.6) and S-0056 (tag 9.0.9.1), which are in KiCad's GPL tree: only the
names were recorded, and the files are never vendored or read at runtime. Sources are listed in
`docs/evidence/sources.md`.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| `pcb drc` writes the JSON report with `--format json`, includes every severity with `--severity-all`, and takes the output path with `-o` (10.0 and 9.0) | S-0022, S-0037 | INFERRED | H-K-DRC-JSON |
| A report is one object with the required keys `source` (board path), `date`, `kicad_version`, `violations`, `unconnected_items`, `schematic_parity` and `coordinate_units`, and the optional keys `$schema` and `included_severities` | S-0055, S-0056 | INFERRED | H-K-DRC-JSON |
| At 10.0.6 a report may also hold `ignored_checks`: a list of objects with `key` (the settings key of a check whose severity is set to ignore) and `description`; the 9.0.9.1 schema has no such key | S-0055, S-0056 | INFERRED | H-K-DRC-JSON |
| `violations`, `unconnected_items` and `schematic_parity` are lists of violations; a violation has `type`, `description`, `severity` and `items` (required), and `excluded` (a boolean, false by default) and `comment` (optional) | S-0055, S-0056 | INFERRED | H-K-DRC-JSON |
| An item of a violation has `uuid` (the uuid of the board item), `description` and `pos`, an object with the numbers `x` and `y` | S-0055, S-0056 | INFERRED | H-K-DRC-JSON |
| `coordinate_units` is `mm`, `mils` or `in`, and every position of the report is in that unit | S-0055, S-0056 | INFERRED | H-K-DRC-JSON |
| A violation's `severity` is `error` or `warning`; `included_severities` may also list `exclusion` | S-0055, S-0056 | INFERRED | H-K-DRC-JSON |
| `type` has no enumeration in the schema, and no number of the report holds a measured distance | S-0055, S-0056 | INFERRED | H-K-DRC-JSON |
| The schema file itself has a trailing comma in its list of required keys at both tags, so it is not strict JSON | S-0055, S-0056, S-0057 | INFERRED | H-K-DRC-JSON |
| Strict JSON allows no trailing comma and no number such as `NaN` or `Infinity` | S-0057 | INFERRED | H-K-DRC-JSON |
| The library checks report `lib_footprint_issues` (footprint not found in an active library) and `lib_footprint_mismatch` (footprint differs from its library copy) | S-0038, S-0058 | INFERRED | H-K-LIB-DRC |
| `kicad-cli` 9.0.9 and 10.0.6 write strict JSON reports that hold the 7 required keys; `ignored_checks` appears in the 10.0.6 report and not in the 9.0.9 one | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRC-JSON |
| The unrouted blink placed through the model API (`tests/kicad/build/_probe_boards.py`), for target 9 on 9.0.9 and for targets 9 and 10 on 10.0.6, gives one violation type, `lib_footprint_issues` with severity `warning`, and 3 `unconnected_items`; the variant with one part moved off the board outline gives the same type, severity and count | S-0020, S-0022 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-BUILD-TRIAD |
| The custom-rule kinds of change c0071 are reported under the types `hole_to_hole`, `hole_clearance`, `annular_width`, `courtyards_overlap` (courtyard clearance), `silk_overlap` and `silk_over_copper` (silkscreen clearance) and `creepage` (10.0.6 only), each with the rule name and the limit and actual values in its `description` | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-KIND-2 |

## How Fenolite reads it

These are decisions of the reader, not facts about KiCad.

- **Strict JSON.** The text is parsed with numbers kept as text; `NaN`, `Infinity` and `-Infinity`
  raise `FormatError`, and no float is ever created.
- **Keys.** A missing required key raises `FormatError` naming it. Unknown keys are ignored.
  `ignored_checks` is kept as the `key` string of each entry; `included_severities` is kept when present.
- **Positions.** `x` and `y` are converted to integer nanometres from `coordinate_units` (1 mm =
  1 000 000 nm, 1 mil = 25 400 nm, 1 in = 25 400 000 nm) with exact rational arithmetic, rounded half to
  even when the value is not a whole number of nm. They are report positions, not model geometry. Any
  other unit raises `FormatError`.
- **Strings.** `type` and `severity` stay KiCad's strings. Violations, unconnected items and parity
  items keep the order of the report.
- **Verdicts.** Every DRC verdict is read from the report. The exit code of `pcb drc` is only a load
  signal, and `--exit-code-violations` is never passed. A report without violations is never evidence
  that a library table or a rules file was loaded; such proofs carry a control that fires only when the
  file was loaded.

`drc.EVIDENCE` is `KICAD-VERIFIED` (`H-K-DRC-JSON`, settled on 9.0.9 and 10.0.6 by `tests/kicad/board/test_drc_report.py`).

## Check canary

`fenolite check` proves with a canary whether a project's custom rules were loaded
(`backends/kicad/canary.py`, `oracle.py`; change c0013). The canary applies only when the copy set holds
both `<stem>.kicad_pro` and `<stem>.kicad_dru`, and is placed only in temporary copies.

- **Rule.** A `clearance` rule named `fenolite_check_canary`, minimum 3 mm, selecting the net
  `FENOLITE_CANARY_A`, written for the running major by the rules lowering; it is appended after the
  user's bytes, which are kept unchanged, because the later rule governs.
- **Tracks.** Two `F.Cu` segments, 0.25 mm wide and 2 mm long, on nets `FENOLITE_CANARY_A` and
  `FENOLITE_CANARY_B`, 1 mm apart, starting 25 mm beyond every coordinate of the board, inserted as text
  before the root's closing parenthesis (two numbered `net` rows after the last net row in the 9.0 form).
- **Verdict.** `fired` when a `clearance` violation names exactly the two canary track uuids, `absent`
  otherwise; `inconclusive` with a reason (`placement-unproven`, `selector-unproven`, `clearance-ignored`,
  `names-taken`, `board-unparsed`, `extent-too-large`, `no-front-copper`, `no-report`, `clearance-limit`)
  when it cannot be judged; `not-applicable` without a project or rules file.
- **Report limit.** KiCad stops reporting `clearance` violations near 499 per run
  (`CLEARANCE_REPORT_LIMIT`). On a board with more, the canary's violation competes for a place and can
  be missing from a run that loaded the rules. A canary run whose report holds no canary violation and
  at least 499 `clearance` violations is `inconclusive` (`clearance-limit`), not `absent`; the run is
  not repeated (change c0051).
- **Stripping.** Every violation and unconnected item that names a canary uuid is removed before the
  report is counted (`canary_removed`); in a two-run major the counted report comes from the plain run,
  so nothing is removed.
- **Support.** `CANARY_SUPPORT` holds the majors whose probes recorded the canary firing and silenced
  by a dropped rules file (9 and 10); `CANARY_TWO_RUN`, the majors where it was not neutral (9 and 10):
  there DRC runs twice on the same copy set, a plain run giving the report and the canary run the verdict.

| fact | source | label | hypothesis |
|---|---|---|---|
| A `clearance` rule on its own net, appended after the user's rules, fires exactly once on two 0.25 mm `F.Cu` tracks 1 mm apart placed 25 mm beyond every board coordinate, on 9.0.9 and 10.0.6, when its run's report holds fewer than 499 `clearance` violations | S-0010, S-0038, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-CHECK-CANARY-3 |
| The canary gives no violation when the rules file is dropped (`broken.kicad_dru`) or the project sets the `clearance` severity to `ignore` | S-0038, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-CHECK-CANARY-3 |
| With the canary violations removed, the report equals a run without the canary, for the authored projects on both majors | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-CHECK-CANARY |
| KiCad can report a clearance between two tracks in some runs and not in others when one of them also runs over a pad of the other's net (observed on 10.0.6): two plain runs of such a board can differ, so a comparison first repeats its reference run | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-CHECK-CANARY |
| On demo boards with hundreds of violations, the canary tracks change other violations run after run: 9.0.9 and 10.0.6 name other partner items for some clearance violations, and sometimes report one violation more or less (`kicad-demo-10-0-6-pcb-01`, `-07`, `-13`), so the counted report comes from a separate plain run | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-CHECK-CANARY-3 |
| `pcb drc` stops reporting `clearance` violations near 499 per run: 10.0.6 reports exactly 499 on a board with more, 9.0.9 between 499 and 508; the canary's violation then competes for a place and can be missing although the rules were loaded (4 of 110 canary runs on `kicad-demo-10-0-6-pcb-01` and `-13`); below 499 it was never missing | S-0020 (measured; no statement found in S-0010, S-0022, S-0038) | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRC-LIMIT |
| Two DRC runs of one unchanged project differ at most in the report order and in entries of the types `clearance`, `hole_clearance` and `unconnected_items` (six of the 21 demo boards); every other type, the return code and the written files repeat | S-0020, S-0022 | KICAD-VERIFIED (10.0.x) | H-K-DRC-REPEAT |

## Report limits

`kicad-cli pcb drc` stops writing entries of one type at a fixed count, and the report does not say so. The
limits are measured with an authored bench (`tests/kicad/check/_limitsbench.py`, change c0141): a board of
400 mm × 400 mm with a `{}` project and a rules file, holding N copies of one small construct per type, each
giving one entry of its type and none of another. No public statement of the limits was found; KiCad's
source was not read. `fenolite.backends.kicad.drc.REPORT_LIMITS` holds them per major (499 for `clearance`
and `unconnected_items`, 199 for every other type), `KicadOracle.report_limits()` returns them, and the
canary's `CLEARANCE_REPORT_LIMIT` is the table's `clearance` value. A type that no probe measured is taken
to stop at 199. `check` marks every count that reached its limit as a lower bound (`summary.limits`,
`check.report-limit`; `docs/cli-contract.md`). The 9.0.9 rows are the measurement of 2026-10-05 and stay
`INFERRED` until the `kicad-9` job records the probes of this bench; the counts are in
`docs/evidence/kicad-check.md`, "DRC report limits per type".

| fact | source | label | hypothesis |
|---|---|---|---|
| 10.0.6 writes at most 499 entries of violations of type `clearance` per run: 700 copies of the bench construct give 499 | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-LIMITS |
| 10.0.6 writes at most 499 entries of the list `unconnected_items` per run: 700 copies of the bench construct give 499 | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-LIMITS |
| 10.0.6 writes at most 199 entries of violations of type `track_dangling` per run: 700 copies of the bench construct give 199 | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-LIMITS |
| 10.0.6 writes at most 199 entries of violations of type `via_dangling` per run: 700 copies of the bench construct give 199 | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-LIMITS |
| 10.0.6 writes at most 199 entries of violations of type `copper_edge_clearance` per run: 700 copies of the bench construct give 199 | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-LIMITS |
| 10.0.6 writes at most 199 entries of violations of type `track_width` per run: 700 copies of the bench construct give 199 | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-LIMITS |
| 10.0.6 writes at most 199 entries of violations of type `hole_to_hole` per run: 700 copies of the bench construct give 199 | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-LIMITS |
| 10.0.6 writes at most 199 entries of violations of type `hole_clearance` per run: 700 copies of the bench construct give 199 | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-LIMITS |
| 10.0.6 writes at most 199 entries of violations of type `annular_width` per run: 700 copies of the bench construct give 199 | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-LIMITS |
| 10.0.6 writes at most 199 entries of violations of type `silk_overlap` per run: 700 copies of the bench construct give 199 | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-LIMITS |
| 10.0.6 writes at most 199 entries of violations of type `courtyards_overlap` per run: 700 copies of the bench construct give 199 | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-LIMITS |
| 10.0.6 writes at most 199 entries of violations of type `lib_footprint_issues` per run: 700 copies of the bench construct give 199 | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-LIMITS |
| 10.0.6 writes at most 199 entries of violations of type `shorting_items` per run: 700 copies of the bench construct give 199 | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-LIMITS |
| 9.0.9 stops writing violations of type `clearance` at 499 or a few more per run (500 on the board of nine benches; 499 to 508 on the bench of `H-K-DRC-LIMIT`) | S-0020, S-0029 | INFERRED | H-K-DRC-LIMITS |
| 9.0.9 writes at most 499 entries of the list `unconnected_items` per run: 700 copies give 499 | S-0020, S-0029 | INFERRED | H-K-DRC-LIMITS |
| 9.0.9 writes at most 199 entries of violations of type `track_dangling` per run: 700 copies give 199 | S-0020, S-0029 | INFERRED | H-K-DRC-LIMITS |
| 9.0.9 writes at most 199 entries of violations of type `via_dangling` per run: 700 copies give 199 | S-0020, S-0029 | INFERRED | H-K-DRC-LIMITS |
| 9.0.9 writes at most 199 entries of violations of type `copper_edge_clearance` per run: 700 copies give 199 | S-0020, S-0029 | INFERRED | H-K-DRC-LIMITS |
| 9.0.9 writes at most 199 entries of violations of type `track_width` per run: 700 copies give 199 | S-0020, S-0029 | INFERRED | H-K-DRC-LIMITS |
| 9.0.9 writes at most 199 entries of violations of type `hole_to_hole` per run: 700 copies give 199 | S-0020, S-0029 | INFERRED | H-K-DRC-LIMITS |
| 9.0.9 writes at most 199 entries of violations of type `silk_overlap` per run: 700 copies give 199 | S-0020, S-0029 | INFERRED | H-K-DRC-LIMITS |
| 9.0.9 writes at most 199 entries of violations of type `courtyards_overlap` per run: 700 copies give 199 | S-0020, S-0029 | INFERRED | H-K-DRC-LIMITS |
| 9.0.9 writes at most 199 entries of violations of type `lib_footprint_issues` per run: 700 copies give 199 | S-0020, S-0029 | INFERRED | H-K-DRC-LIMITS |
| On 9.0.9 the limits of `hole_clearance`, `annular_width` and `shorting_items` are taken to be the 199 of the other types; no run measured them there | S-0020, S-0029 | INFERRED | H-K-DRC-LIMITS |
| A type under its limit is written in full: 150 copies of `track_dangling`, of `silk_overlap` and of the unconnected construct give 150 entries each (10.0.6) | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-LIMITS |
| `--all-track-errors` does not lift the limit: 700 dangling tracks give 199 `track_dangling` entries with and without it (10.0.6) | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-LIMITS |
| The limits are per type and independent: one board that holds 700 copies of each of the thirteen constructs gives each type its own limit (10.0.6) | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-LIMITS |
| No key of the report says that a type was cut: its top-level keys are `$schema`, `coordinate_units`, `date`, `ignored_checks`, `included_severities`, `kicad_version`, `schematic_parity`, `source`, `unconnected_items` and `violations` (10.0.6) | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-LIMITS |

## Findings

`fenolite check` turns every violation and unconnected item of the counted report into one issue
(`checks/drc_json.py`; change c0020). What follows are facts about KiCad's report, then Fenolite's
mapping. Facts the mapping relies on are settled per major by `tests/kicad/check/test_drc_facts.py`
before the mapping is used.

| fact | source | label | hypothesis |
|---|---|---|---|
| A violation's `type` equals the key under `/board/design_settings/rule_severities` that sets the severity of its check: a `clearance` entry is governed by `clearance`, a short between nets by `shorting_items`, a missing connection by `unconnected_items` | S-0055, S-0056, S-0058 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRC-TYPES |
| A project's `rule_severities` value sets the severity of its entries: `error` and `warning` are reported as set, and `ignore` removes them from the report | S-0010, S-0038 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-SEV |
| At 10.0.6 a key set to `ignore` is listed in `ignored_checks`; the 9.0.9.1 schema has no such list | S-0055, S-0056 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-SEV |
| An item of a violation names a pad, a track or a footprint by the `uuid` it has in the board file | S-0055, S-0056 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRC-UUID |
| A violation that involves a distance carries the measured value only in its `description`, in the report's `coordinate_units` | S-0055, S-0056 | INFERRED | H-K-DRC-MEASURED |

These are Fenolite's choices, not facts about KiCad:

- **Codes.** `<oracle>.drc.<suffix>`, where the suffix is the type in lower case with `_` and every other
  character outside `[a-z0-9-]` replaced by `-`, runs of `-` collapsed and the ends trimmed (`unknown`
  when empty): `shorting_items` gives `kicad.drc.shorting-items`. A type whose suffix would be
  `rules-not-loaded` or `rules-unchecked` becomes `type-<suffix>`, so a KiCad type never takes a
  rules-verdict code. `summary.types` maps each code to KiCad's raw type.
- **Severities.** An excluded entry gives `info`; `error` and `warning` stay; any other string gives
  `error`, so a schema change is loud. Project severities reach the issue through the report.
- **Locations.** Each item's uuid is looked up among the native ids of the re-read board: a numbered pad
  gives `REF-PIN`, an unnumbered pad or a footprint `REF`, any other item its locator in the board file.
  A uuid that names no item or several, and every item when the board could not be read, gives
  `@<x>,<y>`, the report position in millimetres. A location is never guessed.
- **Messages.** `<type>: <description>`, with the temporary folder of the run replaced by `<tmp>` and
  the home directory by `~`.
- **Parity.** `schematic_parity` entries are findings like the others since v0.2a (`docs/formats/kicad/erc.md`,
  "Parity in the DRC run"); what each type means is under "Schematic parity" below.

## Schematic parity

What `pcb drc --schematic-parity` reports, measured on 9.0.9 and 10.0.6 with the blink that `build` writes
and with the public demos (change c0072). Fenolite's own comparison (`checks/parity.py`) follows these
facts, and `tests/kicad/check/test_parity_agreement.py` compares its counts with KiCad's.

| fact | source | label | hypothesis |
|---|---|---|---|
| A footprint whose reference was renamed gives one `missing_footprint` (no item; the text is `Missing footprint <ref> (<value>)`) and one `extra_footprint` (the footprint as item); a copied footprint with a new reference gives one `extra_footprint`; a project that agrees gives no entry | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PARITY-TYPES |
| A changed value and a changed library id give one `footprint_symbol_mismatch` each, two when both differ | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PARITY-TYPES |
| A pad on another net gives one `net_conflict` with the pad as item; so does a pad on no net whose pin has a net | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PARITY-TYPES |
| A footprint that takes another's reference gives one `duplicate_footprints` (both footprints as items) and one `missing_footprint` for the reference it lost; the symbol is compared with the footprint of that reference that comes first on the board | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PARITY-TYPES |
| Components and footprints are matched by reference; `n` footprints of one reference give `n - 1` `duplicate_footprints`, footprints without a reference included; a footprint with the attribute `board_only` is never extra and never a duplicate, and it still stands for the component of its reference | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PARITY-OWN |
| A net name with `{slash}` in the schematic's netlist and with `/` on the board is one net; a second pad of the number of a pin on no net may carry that pin's net name followed by `_<n>` | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PARITY-OWN |
| A pin whose number no pad has gives a `net_conflict` with the footprint as item (`No pad found for pin <n> …`); a pad on a net whose number no pin has gives a `net_conflict` with the pad as item; a pin without a number and a pad without a number are not compared | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PARITY-OWN |
| A footprint whose do-not-populate or exclude-from-BOM flag differs from its symbol's gives one `footprint_symbol_mismatch` (`Footprint attributes don't match symbol: …`) | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-PARITY-OWN |
| 10.0.6 also reports `footprint_symbol_field_mismatch` for a field whose text differs between the footprint and the symbol; Fenolite does not compare fields | S-0020 | INFERRED | H-K-PARITY-OWN |

- **Severities.** Every parity entry is a warning by KiCad's defaults; the project's severities apply.
- **Keys.** An entry is compared by its type and its first item: the reference of a footprint, or
  `REF-PAD` of a pad. A missing footprint has no item, so its reference is read from its text.
- **Published demos.** The demos of tag 9.0.9.1 disagree with their schematics as published (61
  `footprint_symbol_mismatch` on `pic_programmer`), so a probe on a demo counts what an edit adds.

## RT2

RT2 says that KiCad's DRC gives the same violations for a board and for Fenolite's re-dump of it
(`KicadOracle.rt2`, `checks/rt2.py`; change c0020). It is an opt-in stage of `fenolite check`.

| fact | source | label | hypothesis |
|---|---|---|---|
| `pcb upgrade --force` re-saves a board in place in the 10.0 format; 9.0 has no `pcb upgrade` | S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-00 |
| The upgrades of an original and of its re-dump are equal trees once `uuid` and `tstamp` are masked, except for `third-party-pcb-02` (format 20171130), whose two upgrades differ | S-0020, S-0022 | KICAD-VERIFIED (10.0.x) | H-K-FMT-RESAVE |
| A 10.0.6 re-save drops or replaces some item uuids, so report items of the original and of the re-dump cannot be paired by uuid | S-0020, S-0022 | KICAD-VERIFIED (10.0.x) | H-K-UUID-KEEP-2 |
| Two `pcb drc --format json --severity-all` runs on one file give equal violations and unconnected items, item uuids left out, on boards with few violations (16 of the 24 corpus boards on 10.0.6, the 5 `rt2-9` boards on 9.0.9) | S-0020, S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-RT2-STABLE-2 |
| On boards with hundreds of violations, two runs on one file can differ: KiCad names other partner items, lists other items, reports one conflict as `clearance` in one run and as `hole_clearance` in the next, and sometimes gives another total (8 of the 24 corpus boards on 10.0.6; counts in `docs/evidence/kicad-rt2.md`) | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-RT2-STABLE-2 |

These are Fenolite's choices:

- **Normalisation.** On 10.0, unless turned off, the original and the re-dump are each re-saved with
  `pcb upgrade --force` in a private copy before DRC; on 9.0 the files are checked as they are.
  `third-party-pcb-02` runs without normalisation.
- **Runs.** DRC runs twice on the original and once on the re-dump, with the project's files, so custom
  rules apply to both sides. No check canary is added. When the re-dump report differs from the
  original's, each side runs three more times, so that a difference can be told from KiCad's own spread.
- **Keys.** A violation is keyed by its group (`violations` or `unconnected_items`), type, severity,
  `excluded` and the sorted descriptions and positions of its items; uuids are left out. A key whose
  count differs between the runs of one side is unstable: it is left out of both sides and counted.
- **Verdict.** RT2 holds when the remaining keys have equal counts. A difference is a failure only when
  no key is unstable, that is when every run of each side gave the same report. Otherwise RT2 is not
  judged on that board: the stage says so, reports no failure and carries no evidence.

## Net ties (c0114)

What `pcb drc` reports on a footprint that holds `net_tie_pad_groups`, measured on the bench of
`tests/kicad/check/_tiebench.py`: one board written by Fenolite, every footprint an authored definition
with `Footprint.net_tie`, a `{}` project (KiCad's `Default` class, 0.2 mm), and a control pair of tracks
whose `clearance` violation must be in the report. Only `shorting_items`, `clearance`,
`solder_mask_bridge` and `unconnected_items` are counted. The 9.0.9 half was not run by this change: the
labels name 10.0.x, and the `kicad-9` job records the same probes.

| fact | source | label | hypothesis |
|---|---|---|---|
| A footprint with `net_tie_pad_groups` gets no `shorting_items` and no `clearance` between two of its pads, whether the two share a group or not: pads of one group that overlap, pads of one group 0.1 mm apart, three pads of one group, and pads of two groups or outside every group that overlap or sit 0.15 mm apart | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-NETTIE-DRC |
| Between two pads of such a footprint that overlap and share no group, `solder_mask_bridge` is still reported; between two pads of one group it is not | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-NETTIE-DRC |
| With the token, a pad is not judged against a filled copper polygon of its own footprint (the form of the footprints of KiCad's own net-tie library); without it the polygon, which has no net, is reported against each pad it touches, with `solder_mask_bridge` and with `shorting_items` or `clearance` at an actual distance of 0 (both types in one run on 10.0.6) | S-0020, S-0018 | KICAD-VERIFIED (10.0.x) | H-K-NETTIE-DRC |
| A track is judged against the pads of a net-tie footprint as against any pad: a track of the net of pad 1 that ends 0.1 mm from pad 2 gives `clearance` (the track and pad 2) and `unconnected_items` (pad 1 and the track), with the token and without it | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-NETTIE-DRC |
| The group string `"1,2"` is read as `"1, 2"` is | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-NETTIE-DRC |
| Without the token, two overlapping pads of two nets give `shorting_items` and `solder_mask_bridge`, and two pads 0.1 mm apart give `clearance` | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-NETTIE-DRC |

Fenolite's copper check follows the first row only for two pads of one group (`copper.md`, "Supported
cases"): a touch between a tied pad and a pad the designer did not tie is a defect, so it stays a finding.

## Stored exclusions (c0114)

A project file stores the DRC exclusions of its board in `board.design_settings.drc_exclusions`
(`project.md`, "Stored exclusions"). Measured on the bench of `tests/kicad/check/_exclcases.py`: two
tracks 0.1 mm apart, a lone via at (30.123456, 20.654321) mm, and project files that differ only in that
list, each key built from the report of a first run. The 9.0.9 half was not run by this change.

| fact | source | label | hypothesis |
|---|---|---|---|
| `pcb drc` applies a stored exclusion only when its type, its position in nanometres and its two uuids in order equal those of a violation: the position is that of the violation's first item, and the second uuid of an entry of one item is the nil uuid | S-0020, S-0055 | KICAD-VERIFIED (10.0.x) | H-K-DRC-EXCL |
| A position that is 1 nm off, another uuid, or the two uuids of a clearance entry in the other order exclude nothing, and the report says nothing about the key | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-EXCL |
| An excluded entry keeps its severity and gains `excluded: true` and `comment`, the text stored with the key (empty for a key stored as a plain string); an entry that is not excluded carries no `excluded` key | S-0020, S-0055 | KICAD-VERIFIED (10.0.x) | H-K-DRC-EXCL |
| A run does not write the project file | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRC-EXCL |

`fenolite check` therefore says what the tool does not (`cli-contract.md`, "Waivers"): the issue of an
excluded entry ends with its comment, and a stored exclusion that no longer applies is reported as
`check.exclusion-stale`, `moved` when an entry of its type and uuids is reported again and `gone` when
none is. Exclusions of the types `clearance`, `hole_clearance`, `unconnected_items` and `shorting_items`
are not judged, because KiCad does not repeat their entries from run to run (`H-K-DRC-REPEAT`,
`H-K-VIA-RENET`). Fenolite reads exclusions and never writes one: the key needs the marker position,
which the report gives only as item positions.
