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
| `sch-pin-frame-<angle>-<mirror>` (12 probes) | a label at `schlayout.pin_point` leaves no `pin_not_connected`, for the angles 0, 90, 180, 270 and the mirrors none, `x`, `y`; a control with the labels of another frame leaves pins open | `absent` (12 of 12) | `absent` (12 of 12) |
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

