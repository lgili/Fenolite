# KiCad schematics: census and round trips

Counts from `tests/corpus/test_schematic_census.py`, `tests/corpus/test_schematic_rt.py` and
`tests/kicad/schematic/` over the schematic rows of the corpus (use `sch`), run on 2026-10-05 with
`FENOLITE_CENSUS_OUT` naming a temporary file: `kicad-cli` 10.0.6 on macOS, and `kicad-cli` 9.0.9 in the
pinned image. Only row ids, counts and head names are recorded here, never file content. The demo files
are CC-BY-SA-4.0 (S-0023) and the third-party files Apache-2.0 (S-0027, S-0028); none is committed.

These numbers settle `H-K-SCH-READ`, `H-K-SCH-RT1` and `H-K-SCH-COMPONENTS` (`docs/hypotheses.md`).

## Rows

- 132 rows, 45294889 bytes: 114 demo schematics at tag 10.0.6,
  16 at tag 9.0.9.1 that differ from or are absent at 10.0.6, and
  2 third-party schematics. 92 rows are in the demo tree of tag 9.0.9.1
  (`sch-9`). The demo folder whose licence has a non-commercial clause is not listed.
- Fetching the 132 rows with `tools/corpus_fetch.py --uses sch` took 2 min 51 s on 2026-10-05
  (131 fetched, 1 already cached).

| use | rows |
|---|---|
| sch-9 | 92 |
| sch-bus | 72 |
| sch-multi | 9 |
| sch-old | 7 |
| sch-root | 47 |

| format version | rows |
|---|---|
| 20230121 | 5 |
| 20230221 | 1 |
| 20230819 | 1 |
| 20231120 | 10 |
| 20240602 | 1 |
| 20241209 | 5 |
| 20250114 | 99 |
| 20250610 | 8 |
| 20260101 | 2 |

Rows that carry none of `sch-bus`, `sch-multi` and `sch-old` (the acceptance list of v0.2a):
47.

Root heads over the 132 files, with the number of children:

| root head | children |
|---|---|
| bus | 2455 |
| bus_alias | 37 |
| bus_entry | 2044 |
| embedded_fonts | 33 |
| generator | 132 |
| generator_version | 125 |
| global_label | 229 |
| hierarchical_label | 799 |
| image | 49 |
| junction | 4638 |
| label | 6219 |
| lib_symbols | 132 |
| netclass_flag | 37 |
| no_connect | 1682 |
| paper | 132 |
| polyline | 493 |
| rectangle | 35 |
| rule_area | 34 |
| sheet | 97 |
| sheet_instances | 50 |
| symbol | 7448 |
| table | 1 |
| text | 852 |
| text_box | 46 |
| title_block | 103 |
| uuid | 132 |
| version | 132 |
| wire | 21120 |

## RT0 and RT1 on the demo rows

- Read: 125 of 130 demo rows. RT0 (`parse(dumps(parse(t)))` tree-equal to
  `parse(t)`) and RT1 (`sch.roundtrip_schematic`) pass on all 125, bus rows and multi-instance rows
  included. The run took 6 min 41 s.
- Not read, older than the read floor (`20231120`): `kicad-demo-10-0-6-sch-092` (20230819), `kicad-demo-9-0-9-1-sch-008` (20230121), `kicad-demo-9-0-9-1-sch-012` (20230221), `kicad-demo-9-0-9-1-sch-013` (20230121), `kicad-demo-9-0-9-1-sch-014` (20230121).
- Read per format version: `20231120` 10, `20240602` 1, `20241209` 5, `20250114` 99, `20250610` 8, `20260101` 2.
- Modelled entities over the 125 rows: 6652 symbol instances, 6952 labels,
  1659 no-connect flags, 97 sheet references, 1658 embedded symbols.
- Opaque slots: 203681 in all; per row from 22 to 6868, median 949.
- Reader issues: `kicad.sch.kept-opaque` 443, `kicad.version.dev` 16. No warning and no error.

## Third-party rows, as upgraded copies (KiCad 10.0.6)

The two third-party rows are at format `20230121`, older than the read floor. Each was re-saved once in
memory with `sch upgrade --force` through `KicadCli.upgrade_schematic` and read as origin `third-party`.

| row | format after the upgrade | RT0 | RT1 | opaque slots | symbol instances | labels |
|---|---|---|---|---|---|---|
| third-party-sch-01 | 20260306 | pass | pass | 4161 | 225 | 96 |
| third-party-sch-02 | 20260306 | pass | pass | 4835 | 282 | 135 |

## Components against `kicad-cli sch export netlist`

`sch.hierarchy_components` against the `components` of the netlist, for every project whose root row
carries `sch-root`, with symbols left off the board left out on both sides (`sch-components-on-board` is
`absent` on both majors).

| kicad-cli | demo tree | projects compared | equal | left out | components | with a text variable |
|---|---|---|---|---|---|---|
| 10.0.6 (macOS) | 10.0.6 | 34 | 34 | 0 older than the read floor | 4164 | 7 |
| 9.0.9 (pinned image) | 9.0.9.1 | 31 | 31 | 4 older than the read floor, 0 newer than the 9.0 constant | 2818 | 5 |

- A first comparison that selected uses by project name (`sch.components`) gave equal sets for 18 of 30
  projects on 10.0.6. The other 12 hold instance data filed under another project name, a `Value` of
  `~`, or a text variable; `kicad-cli` resolves symbols by instance path. The table above is the
  comparison by instance path.
- Fixture probes on both majors: `sch-components-flat`, `sch-components-units` and
  `sch-components-hier` are `equal`.

## Generated sheets (change c0061)

Measured on 2026-10-05 with `kicad-cli` 10.0.6 (macOS) and 9.0.9 (the pinned image), each on sheets and
projects written for its own major. The probe outcomes are committed in
`docs/evidence/kicad/probes/10.0.6.json` and `9.0.9.json`; the tests are
`tests/kicad/schematic/test_naming_probes.py`, `test_generated_oracle.py` and
`tests/kicad/lens/test_update_stand_in.py`.

### Naming facts (hand-written probe sheets)

| probe | what is measured | 9.0.9 | 10.0.6 |
|---|---|---|---|
| `sch-pin-frame-<angle>-<mirror>` (12 probes) | a label at `schlayout.pin_point` leaves no `pin_not_connected`, for the angles 0, 90, 180, 270 and the mirrors none, `x`, `y`; a control with the labels of another frame leaves pins open. Both mirrors map the 32 pins onto themselves, so these probes cannot tell the order of mirror and rotation (change c0137) | `absent` (12 of 12) | `absent` (12 of 12) |
| no probe: `tests/kicad/schematic/test_pin_frame_oracle.py` (c0137) | an asymmetric three-pin symbol in the twelve frames: each pin on the net of the label at `schlayout.pin_point` (rotate, then mirror); with the labels of the mirror-first order the pins of the four mirrored instances at 90° and 270° are off their nets | owed (CI) | owed (CI) |
| `sch-unconnected-plain` | the named pins of the 32-pin IC: `unconnected-(U1-<name>-Pad<n>)` | `equal` | `equal` |
| `sch-unconnected-unnamed` | two pins without a name: `unconnected-(U1-Pad1)`, `unconnected-(U1-Pad16)` | `equal` | `equal` |
| `sch-unconnected-units` | the eight pins of the three units of `Mini_DualGate`: `unconnected-(U2C-GND-Pad7)` for a named pin, `unconnected-(U2-Pad1)` for a pin without a name | `equal` | `equal` |
| `sch-unconnected-chars` | pin names `A B`, `A/B`, `V+`, `~`, `~{RST}`, `1WIRE`, `DUP` (two pins), `A-B_C.D`, `D{0}` | `equal` | `equal` |
| `sch-label-plain`, `sch-label-chars` | 20 label texts (blank, `[ ]`, `{ }`, `( )`, quote, backslash, a non-ASCII letter, `+ . - _ : , # $ ~ =`) name their net unchanged | `equal` | `equal` |
| `sch-label-slash` | the label `mod/LED_A` names the net `mod{slash}LED_A` | `equal` | `equal` |
| `sch-parity-slash-stored` | a pad stored as `mod{slash}LED_A`: no `net_conflict` | `absent` | `absent` |
| `sch-parity-slash-raw` | the same pad stored as `mod/LED_A`: `net_conflict` | `present` | `present` |
| `sch-power-flag` | `power_pin_not_driven` with `fenolite:PWR_FLAG` on the net (reported without it) | `absent` | `absent` |
| `sch-hidden-power-joined` | two hidden power inputs `VSS`, labelled `GND` and `OTHER`, are on one net (`GND`) | `present` | `present` |
| `sch-shown-power-separate` | the same pins shown are on `GND` and `OTHER` | `equal` | `equal` |
| `sch-lib-missing` | the built blink without `sym-lib-table`: `lib_symbol_issues` | `present` | `present` |
| `sch-lib-vendored` | the built blink: `lib_symbol_issues` or `lib_symbol_mismatch` | `absent` | `absent` |
| `sch-lib-variant` | the built units design, with a pin-pad variant | `absent` | `absent` |

The pin `~` of `sch-unconnected-chars` has no name on 9.0.9 (`unconnected-(X1-Pad4)`, sheet version
`20250114`) and the name `~` on 10.0.6 (`unconnected-(X1-~-Pad4)`, `20260306`); both equal what Fenolite's
reader gives the pin, so `netnames.unconnected_name` is `equal` on both. No character class was
`different`: `netnames.PROVED_PIN_CHARS` holds letters, digits and the characters of the probe names.

### Generated projects

Both designs are built for the running major: `examples/blink_2layer` (three parts, 29 marked pins, two
power flags) and the authored units design of `tests/_schbuild.py` (a three-unit part with marked pins,
a part with a pin-pad map, a module net `mod/LED_A`).

| check | 9.0.9 | 10.0.6 |
|---|---|---|
| `sch erc --severity-all --exit-code-violations`, blink (`sch-gen-erc-blink`) | exit 0, 0 violations | exit 0, 0 violations |
| the same, units design (`sch-gen-erc-units`) | exit 0, 0 violations | exit 0, 0 violations |
| ERC controls on the blink: one label removed, the flag of `VIN` removed, `sym-lib-table` removed | `pin_not_connected`, `power_pin_not_driven`, `lib_symbol_issues` | the same |
| `pcb drc --schematic-parity`, blink and units design | 0 parity issues | 0 parity issues |
| parity controls on the blink: a pad on another net, a changed Value, a renamed reference, exchanged paths | `net_conflict`, `footprint_symbol_mismatch`, `missing_footprint` with `extra_footprint`, nothing | the same |
| `sch export netlist`: the circuit's nets with pins mapped to pads, plus one net per unconnected pad with the name the board carries | equal sets, both designs | equal sets, both designs |
| `fenolite check`: no error other than `kicad.drc.unconnected-items`, 0 assignment differences, round trip `ok` | both designs | both designs |
| a rebuild after the update stand-in: loaded, parity and ERC | 0 issues | 0 issues |

The two example projects, built and judged by hand with the same commands on 2026-10-05:

| example | symbols, labels, flags, paper | ERC 9.0.9 | ERC 10.0.6 | parity 9.0.9 | parity 10.0.6 |
|---|---|---|---|---|---|
| `examples/blink_2layer` | 5 symbols, 9 labels, 29 no-connect flags, 2 power flags, A4 | 0 violations | 0 violations | 0 issues | 0 issues |
| `examples/board_40parts` | 42 symbols, 102 labels, 40 no-connect flags, 2 power flags, A3 | 0 violations | 0 violations | 0 issues | 0 issues |

Before the blink example marked its unused pins, its ERC reported 29 `pin_not_connected` and 2
`pin_not_driven` errors on both majors, and nothing else: an unmarked open pin is a finding of the
design, which the generator does not hide.

### Re-save of a generated sheet (10.0.6, `H-K-SCH-RESAVE`)

`sch upgrade --force` on the built blink (`sch-gen-resave` = `equal`: a second re-save is byte-identical
and ERC still reports nothing). The first re-save changes only the embedded symbols, which come from a
library in the 9.0 form; the order of the root items and every item Fenolite writes are kept.

| | count |
|---|---|
| bytes written by the build | 30 847 |
| bytes after the re-save | 32 287 |
| root items in another order | 0 |
| added under `lib_symbols/symbol` | `in_pos_files` 4, `duplicate_pin_numbers_are_jumpers` 4, `embedded_fonts` 1 |
| added under `lib_symbols/symbol/property` | `show_name` 26, `do_not_autoplace` 26, `hide` 9 |
| dropped | `lib_symbols/symbol/property/effects/hide` 9 (moved to the property) |

### Observations that are not probes

- 9.0.9 loads an embedded symbol whose properties hold `show_name` and `do_not_autoplace`: the blink built
  for target 9 from the 10.0 mini library with `--allow-lossy` (which removes `in_pos_files` and
  `duplicate_pin_numbers_are_jumpers`, the two tokens the inventory dates after 9.0) has an ERC without
  violations. The inventory has no row for the two property tokens; this observation is not a row.
- A design whose resistor uses a symbol authored in the script (`Local:Res`) builds a project whose ERC
  and parity are clean on both majors; the authored library is written with the header version of its
  target (`20241209` for 9.0).
- "Update PCB from Schematic" has no headless command. The stand-in of `tests/_layout_edit.py` adds
  `sheetname`, `sheetfile` and the symbol's `path`; on a board built beside its schematic it changes no
  path and no field text. The maintainer ran the real update once, on 2026-10-05 in KiCad 10.0.6, on the
  blink example built for KiCad 10: it added `sheetname` and `sheetfile` to the three footprints and
  `pinfunction` and `pintype` to their pads, and changed no position, `path`, field text, pad net, track
  or zone. `H-K-SCH-UPDATE` stays `INFERRED`: one manual run on one board.

## Netlists (change c0063)

Measured on 2026-10-05 with `kicad-cli` 10.0.6 (macOS) and 9.0.9 (the pinned image), each on projects that
`build` wrote for its own major. The probe outcomes are committed in
`docs/evidence/kicad/probes/10.0.6.json` and `9.0.9.json`; the tests are
`tests/kicad/schematic/test_netlist_facts.py`, `test_own_netlist.py` and
`tests/kicad/check/test_netlist_oracle.py`.

### The export (`H-K-NETLIST-SHAPE`)

| probe | 9.0.9 | 10.0.6 | what it says |
|---|---|---|---|
| `netlist-shape` | `equal` | `equal` | the export of the built blink holds `components` and `nets` with every head and atom the reader takes |
| `netlist-power-symbols` | `absent` | `absent` | the two `#FLG` power flags of the blink are neither components nor nodes |
| `netlist-pintype` | `equal` | `equal` | `pintype` is the electrical type of the pin, with `+no_connect` under a flag: 36 pins of the blink (29 flagged) and 12 of the units design (5 flagged) |

The root children are `version`, `design`, `components`, `libparts`, `libraries` and `nets` on 9.0.9, and
10.0.6 adds `groups` and `variants`. The date and the paths of a run lie in `design` and `libraries`
only; the source path of `design` occurs nowhere in `components` and `nets`.

### The own netlist against the export (`H-K-NETLIST-OWN`)

`netlist.differences(own_netlist(sheet), read_netlist(export))` with pin types compared; the counts are
those of the export and are equal on both versions. The sheet read back from the written file gives the
same own netlist as the generated sheet in every case.

| set | designs | components | nets | pins | `unconnected-(…)` nets | pins under a flag | differences (9.0.9 and 10.0.6) |
|---|---|---|---|---|---|---|---|
| blink (`netlist-own-blink` = `equal`) | 1 | 3 | 33 | 36 | 29 | 29 | 0 |
| units design (`netlist-own-units` = `equal`) | 1 | 3 | 9 | 12 | 5 | 5 | 0 |
| examples: `altium_hier_board`, `blink_2layer`, `blink_routed`, `board_40parts` | 4 | 49 | 179 | 248 | 127 | 69 | 0 |
| 25 generated designs, seed 20261004 (`netlist-own-generated` = `equal`) | 25 | 162 | 508 | 930 | 364 | 182 | 0 |

The examples `altium_hier`, `altium_kicad`, `altium_sample` and `blink_official` do not build for the
KiCad target with the libraries of the repository and are not in the set. No difference was found, so no
row of c0061 (`H-K-SCH-UNCONNECTED`, `H-K-SCH-SLASH`, `H-K-SCH-POWER`) was touched. The generated set
holds the multi-unit part in 19 designs, a pin-pad map in 18, a no-connect mark in 21, a power interface
in 16, a net name with a slash in 18, a module in 18 and an open pin without a mark in 20.

### The schematic as a source of `check`

| case | pairs of `netlist.assignment_compare` | differences (9.0.9 and 10.0.6) |
|---|---|---|
| built blink, built units design | (`model`, `board`), (`model`, `schematic`), (`board`, `export`) | 0, 0, 0 |
| the same files without `.fenolite/` | (`schematic`, `board`), (`board`, `export`) | 0, 0 |
| hand sheet of c0061's power probe, pins shown, against a model with `X1-1` on `GND` and `X1-2` on `OTHER` | (`model`, `schematic`) | 0 |
| the same sheet with the two `VSS` pins hidden | (`model`, `schematic`) | a difference naming `X1-1` or `X1-2`: KiCad joins the two pins |

`fenolite netlist` gives equal nets, counts and components from its two sources for the built blink and
for the built units design on both versions; only `class` differs, which the source `fenolite` leaves
empty.
## RT2 through KiCad's ERC (change c0062)

`tests/kicad/schematic/test_corpus_rt2.py`, run three times on 2026-10-06 with `kicad-cli` 10.0.6 (macOS)
and three times with 9.0.9 (pinned image); the tables hold the first run of each. A project is a root row
(`sch-root`) with every cached row of its demo folder, rebuilt in a temporary folder; the cache is only
read. `KicadOracle.rt2_erc` runs ERC twice on the project as it is and once on a copy in which every
sheet Fenolite reads is its re-dump.

KiCad does not repeat its report item by item: for one violation it names one of the pins or labels
involved, and not the same one in every run. The reports are therefore compared by
`ErcReport.kinds()`, the sheet, type, severity and exclusion of every violation, counts included. A
project is *judged* when its two runs of the original have equal kinds, and RT2 *holds* when the re-dump
has the kinds of the first run. *exact* says whether the three reports also have equal
`ErcReport.entries()`, items and positions included; it is information and changes no verdict. These
numbers settle `H-K-ERC-RT2-2` and `H-K-ERC-REPEAT-2`, the successors of `H-K-ERC-RT2` and
`H-K-ERC-REPEAT`, which asked for equal entries and were refuted.

| | 10.0.6 | 9.0.9 |
|---|---|---|
| projects run | 34 | 35 |
| judged / holds / differs | 34 / 34 / 0 | 35 / 35 / 0 |
| not judged (the kinds of the two runs of the original differ) | 0 | 0 |
| exact, in each of the three runs | 31, 31, 31 | 35, 35, 34 |
| acceptance list (rows without `sch-bus`, `sch-multi`, `sch-old`): projects / judged / holds / exact | 24 / 24 / 24 / 24 | 24 / 24 / 24 / 24 |
| the other projects: run / judged / holds / exact | 10 / 10 / 10 / 7 | 11 / 11 / 11 / 11 |
| sheet files: re-dumped / left as they are | 111 / 0 | 87 / 4 |
| violations of the first run, all projects | 11093 | 6491 |
| seconds in all, and of the slowest project | 196.4, 105.5 | 150.4, 44.0 |

- The three runs of each major gave the same judged and holds counts; only *exact* moved.
- The four sheets left as they are on 9.0.9 are the roots older than the read floor (`sch-old`): Fenolite
  does not read them, so the third run sees the original file and the verdict says nothing about a
  re-dump. On 10.0.6 the rows of tag 10.0.6 hold no such root.
- On 9.0.9 the projects are those of tag 9.0.9.1 whose sheets are at format `20250114` or older; on
  10.0.6 those of tag 10.0.6. 13 root rows are no project at tag 10.0.6 and 12 none at tag 9.0.9.1.
- Not exact on 10.0.6, in each of the three runs: `kicad-demo-10-0-6-sch-017`, `-sch-037` and `-sch-106`,
  all outside the acceptance list. A direct run on `-sch-037` gave two `multiple_net_names` entries with
  other items in the re-dump's report, and no difference when it was made again; the same two runs on
  the other two projects gave no difference.
- Not exact on 9.0.9: `kicad-demo-10-0-6-sch-035`, of the acceptance list, in the third run only (97
  violations in every run; one `power_pin_not_driven` names another pin position). With the first rule,
  equal entries, this project was not judged in the `kicad-9` job and the job failed.
- The run of 2026-10-05, judged by equal entries, had 33 of 34 projects judged on 10.0.6
  (`kicad-demo-10-0-6-sch-037` was not) and 35 of 35 on 9.0.9.

| project (root row) | list | sheet files | re-dumped / kept | 10.0.6: violations, verdict, exact | 9.0.9: violations, verdict, exact |
|---|---|---|---|---|---|
| kicad-demo-10-0-6-sch-003 | other | 8 | 8 / 0 | 203, holds, yes | not run |
| kicad-demo-10-0-6-sch-01 | acceptance | 2 | 2 / 0 | 113, holds, yes | 73, holds, yes |
| kicad-demo-10-0-6-sch-011 | acceptance | 1 | 1 / 0 | 32, holds, yes | 37, holds, yes |
| kicad-demo-10-0-6-sch-012 | acceptance | 1 | 1 / 0 | 35, holds, yes | 32, holds, yes |
| kicad-demo-10-0-6-sch-013 | other | 1 | 1 / 0 | 76, holds, yes | 55, holds, yes |
| kicad-demo-10-0-6-sch-017 | other | 15 | 15 / 0 | 3012, holds, no | not run |
| kicad-demo-10-0-6-sch-032 | other | 3 | 3 / 0 | 340, holds, yes | 281, holds, yes |
| kicad-demo-10-0-6-sch-035 | acceptance | 2 | 2 / 0 | 103, holds, yes | 97, holds, yes |
| kicad-demo-10-0-6-sch-037 | other | 3 | 3 / 0 | 1026, holds, no | not run |
| kicad-demo-10-0-6-sch-039 | other | 2 | 2 / 0 | 190, holds, yes | not run |
| kicad-demo-10-0-6-sch-041 | other | 5 | 5 / 0 | 212, holds, yes | 146, holds, yes |
| kicad-demo-10-0-6-sch-042 | acceptance | 1 | 1 / 0 | 2, holds, yes | 2, holds, yes |
| kicad-demo-10-0-6-sch-047 | acceptance | 1 | 1 / 0 | 39, holds, yes | not run |
| kicad-demo-10-0-6-sch-048 | acceptance | 1 | 1 / 0 | 8, holds, yes | 8, holds, yes |
| kicad-demo-10-0-6-sch-049 | acceptance | 1 | 1 / 0 | 47, holds, yes | 47, holds, yes |
| kicad-demo-10-0-6-sch-050 | acceptance | 1 | 1 / 0 | 18, holds, yes | 18, holds, yes |
| kicad-demo-10-0-6-sch-051 | acceptance | 1 | 1 / 0 | 28, holds, yes | not run |
| kicad-demo-10-0-6-sch-052 | acceptance | 1 | 1 / 0 | 40, holds, yes | 40, holds, yes |
| kicad-demo-10-0-6-sch-053 | acceptance | 1 | 1 / 0 | 28, holds, yes | not run |
| kicad-demo-10-0-6-sch-054 | acceptance | 1 | 1 / 0 | 21, holds, yes | not run |
| kicad-demo-10-0-6-sch-055 | acceptance | 1 | 1 / 0 | 28, holds, yes | 28, holds, yes |
| kicad-demo-10-0-6-sch-056 | acceptance | 1 | 1 / 0 | 16, holds, yes | not run |
| kicad-demo-10-0-6-sch-057 | acceptance | 1 | 1 / 0 | 123, holds, yes | not run |
| kicad-demo-10-0-6-sch-058 | acceptance | 1 | 1 / 0 | 26, holds, yes | 24, holds, yes |
| kicad-demo-10-0-6-sch-059 | acceptance | 1 | 1 / 0 | 527, holds, yes | 448, holds, yes |
| kicad-demo-10-0-6-sch-060 | acceptance | 1 | 1 / 0 | 8, holds, yes | not run |
| kicad-demo-10-0-6-sch-061 | acceptance | 1 | 1 / 0 | 18, holds, yes | not run |
| kicad-demo-10-0-6-sch-062 | acceptance | 3 | 3 / 0 | 20, holds, yes | 20, holds, yes |
| kicad-demo-10-0-6-sch-065 | acceptance | 1 | 1 / 0 | 9, holds, yes | 9, holds, yes |
| kicad-demo-10-0-6-sch-066 | acceptance | 1 | 1 / 0 | 39, holds, yes | 39, holds, yes |
| kicad-demo-10-0-6-sch-067 | acceptance | 1 | 1 / 0 | 79, holds, yes | 50, holds, yes |
| kicad-demo-10-0-6-sch-069 | other | 2 | 2 / 0 | 507, holds, yes | 376, holds, yes |
| kicad-demo-10-0-6-sch-077 | other | 8 | 8 / 0 | 584, holds, yes | 426, holds, yes |
| kicad-demo-10-0-6-sch-106 | other | 36 | 36 / 0 | 3536, holds, no | 3519, holds, yes |
| kicad-demo-9-0-9-1-sch-001 | acceptance | 1 | 1 / 0 | not run | 8, holds, yes |
| kicad-demo-9-0-9-1-sch-002 | acceptance | 3 | 3 / 0 | not run | 125, holds, yes |
| kicad-demo-9-0-9-1-sch-005 | other | 2 | 2 / 0 | not run | 127, holds, yes |
| kicad-demo-9-0-9-1-sch-007 | acceptance | 1 | 1 / 0 | not run | 28, holds, yes |
| kicad-demo-9-0-9-1-sch-008 | other | 1 | 0 / 1 | not run | 28, holds, yes |
| kicad-demo-9-0-9-1-sch-009 | acceptance | 1 | 1 / 0 | not run | 79, holds, yes |
| kicad-demo-9-0-9-1-sch-010 | acceptance | 1 | 1 / 0 | not run | 15, holds, yes |
| kicad-demo-9-0-9-1-sch-011 | acceptance | 1 | 1 / 0 | not run | 123, holds, yes |
| kicad-demo-9-0-9-1-sch-012 | other | 1 | 0 / 1 | not run | 42, holds, yes |
| kicad-demo-9-0-9-1-sch-013 | other | 1 | 0 / 1 | not run | 8, holds, yes |
| kicad-demo-9-0-9-1-sch-014 | other | 1 | 0 / 1 | not run | 19, holds, yes |
| kicad-demo-9-0-9-1-sch-015 | acceptance | 1 | 1 / 0 | not run | 8, holds, yes |
| kicad-demo-9-0-9-1-sch-016 | acceptance | 1 | 1 / 0 | not run | 106, holds, yes |

## Hierarchy and wires (change c0070)

Measured on 2026-10-06 with `kicad-cli` 10.0.6 (macOS) and 9.0.9 (the pinned image). The probe outcomes
are committed in `docs/evidence/kicad/probes/10.0.6.json` and `9.0.9.json`; the tests are
`tests/kicad/schematic/test_hierarchy_probes.py` and `test_hierarchy_oracle.py`.

### Facts (hand-written sheets)

A root with one resistor names `sheets/a.kicad_sch`, which names its own child; each sheet has one
resistor with the global labels `VCC` and `SIG`, and no sheet symbol has a pin. The wire sheet has two
resistors whose pins 1 are joined by one wire with the label `MID` at one end. A hand-written sheet has
no symbol table, so ERC reports `lib_symbol_issues` for it; that type is not counted.

| probe | 9.0.9 | 10.0.6 | what it says |
|---|---|---|---|
| `sch-hier-file-parent` | `present` | `present` | a child named `b.kicad_sch` from `sheets/a.kicad_sch` is loaded, at the sheet path `/a/b/` |
| `sch-hier-file-project` | `absent` | `absent` | the same child named `sheets/b.kicad_sch` from there is dropped: no symbol in the netlist, no ERC finding, exit 0 of both commands |
| `sch-hier-global` | `equal` | `equal` | `VCC` and `SIG` hold the pins of the three sheets; the `tstamps` of the sheet paths are `/<uuid of a>/` and `/<uuid of a>/<uuid of b>/` |
| `sch-wire-ends` | `equal` | `equal` | the two wired pins are the net `MID`, without an ERC finding |
| `sch-wire-middle` | `absent` | `absent` | a pin that ends in the middle of the wire is on `unconnected-(R3-Pad1)`, with `pin_not_connected` |

### Built projects

Each project is built for the running major and judged on copies: ERC, the parity test, the netlist
export against `sch_netlist.own_netlist` of the sheet tree, and the footprint paths against the netlist.

| set | designs | child sheets | satellites | ERC | parity | netlist differences | paths |
|---|---|---|---|---|---|---|---|
| nested design (`U1`; `power` with `ldo` inside; `io`), every open pin marked | 1 | 3 | 0 | 0 violations | 0 | 0 | equal |
| lens acceptance design (`sch-hier-oracle-acceptance` = `equal`) | 1 | 2 | 0 | as the flat form | 0 | 0 | equal |
| 25 generated designs, seed 20261005, `modules=True` (`sch-hier-oracle-generated` = `equal`) | 25 | 50 | 29 | no type counted more often than on the flat form | 0 | 0 | equal |

- **ERC by comparison.** The acceptance design and the generated designs leave pins open, which ERC
  reports on any sheet. They are compared with the same design built with `--schematic-layout grid`:
  no violation type is counted more often. On 10.0.6 the counts are equal for all 26 designs. On 9.0.9
  one generated design (index 3) has 24 `pin_not_connected` on its readable sheets and 25 on the flat
  sheet: `U4` pin 27, which is on no net in the script and alone on `unconnected-(…)` in both exports,
  is reported on the flat sheet only. Looked at for an hour on 2026-10-06, in the pinned image:
  - it repeats (five runs), and does not depend on the order of the symbols in the file or on the
    uuid of `U4`; nothing else lies on the pin's point (no pin, label, flag, wire or sheet symbol);
  - it is not the wires or the sheet symbol: the root without every wire, or without its sheet
    symbol, still lacks the finding;
  - 9.0.9 always reports 24 of the 25 open pins of this project, and which one it leaves out changes
    with content that has nothing to do with the pin: with one or two lone global labels added far
    away it reports pin 27 and leaves out pin 16 of `U4` instead; with three or four it leaves out
    pin 27 again. Taking away one unrelated resistor, power flag or label has the same effect;
  - no other finding lies at the position of the one left out, on any sheet.
  So one `pin_not_connected` is lost inside 9.0.9's ERC report, not in the schematic: the export lists
  both pins on their own `unconnected-(…)` nets. Why 9.0.9 loses it was not found (no KiCad source was
  read). The oracle therefore asks that the sheets add no finding, and judges connectivity by the
  netlist, which is equal.
- **Paths.** For a part of several units the netlist lists one `tstamps` per unit, in KiCad's order;
  the footprint path is the sheet path joined with one of them (Fenolite writes the lowest unit's).
- **Controls.** With the `Sheetfile` of one child edited to a missing file, ERC reports only
  `isolated_pin_label` for the label that lost its other pin (nothing about the sheet), and the netlist
  misses the parts of that sheet. With one snap wire removed, ERC reports `pin_not_connected`.
- **Not measured.** What "Update PCB from Schematic" writes for a part of a module (no headless
  update; `H-K-SCH-HIER-PATH`, the update half).
