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
