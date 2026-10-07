## ADDED Requirements

### Requirement: Net length report
`fenolite.analysis.length.measure_lengths(design, *, pads, facts=None, nets=(), starts=()) -> LengthReport` SHALL measure each net of `design` whose name matches a glob of `nets` (`fnmatch.fnmatchcase`) and that has at least one pad, track, arc or via on the board, under the rules of "Analysis package and report": pure, integers in nanometres, no float, sorted, equal inputs giving equal reports.
- `LengthReport(rows, pairs, issues, summary, evidence)` MUST be a frozen dataclass with `findings() -> Findings`, as `AnalysisReport` has. `rows` MUST hold one `LengthRow(net, routed, vias, die, total, via_count, start, paths, off_path)` per measured net, sorted by net name.
- With `facts` (`backend-protocol`, "Length facts source"), `routed`, `vias`, `die`, `total` and `via_count` MUST be those of `facts.nets[net]`. Without `facts`, `routed` MUST be the sum of `segment_length` and `arc_length` over the net's tracks and arcs on copper layers, `vias` and `die` MUST be 0, `total` MUST equal `routed`, and one `analysis.input-missing` warning MUST name `length facts` and the count of vias whose height is unknown.
- `routed` MUST equal the `length` of the net's row of `views.net_list`.
- Without a measured net, `rows` MUST be empty and one `analysis.input-missing` warning MUST name `net selection`.
- `summary` MUST hold `nets` (the count of rows) and the `major`, `stackup` and `count_vias` of `facts`, each `None` without facts.
- The evidence MUST be `Evidence.combine` of `analysis.length.EVIDENCE`, which is `Evidence(Level.INFERRED, hypotheses=("H-G-NETLEN-PATH",))`, and `facts.evidence`; it MUST be `UNVERIFIED` when the report holds an `analysis.input-missing` or `analysis.item-unsupported` issue. `fenolite.analysis.EVIDENCE` does not change.

#### Scenario: Totals come from the facts
- **GIVEN** the two-layer bench of `tests/_lengthbench.py` written for target 10 and read back, its net `L_VIA2` (10 mm on `F.Cu`, a through via, 10 mm on `B.Cu`), and the facts of `KicadBackend().length_facts(design)`
- **WHEN** `uv run pytest tests/unit/analysis/test_length.py -k facts` calls `measure_lengths(design, pads=…, facts=facts, nets=("L_VIA2",))`
- **THEN** the row holds `routed == 20_000_000`, `vias == 1_580_000`, `die == 0`, `total == 21_580_000` and `via_count == 1`, and `summary.stackup` is `default`

#### Scenario: No facts
- **WHEN** the same call runs with `facts=None`
- **THEN** the row holds `total == 20_000_000`, one `analysis.input-missing` warning names `length facts` and 1, and the level is `UNVERIFIED`

#### Scenario: No selection
- **WHEN** `measure_lengths(design, pads=…, facts=facts)` runs without `nets`
- **THEN** `rows` is empty and one `analysis.input-missing` warning names `net selection`

### Requirement: Pin-to-pin length
`measure_lengths` SHALL give each row `start`, the `REF-PIN` of its start pad, and `paths`: one `PathRow(end, length, vias, layers)` per other pad of the net, sorted by `end`, where `length` is the length of the shortest path along the net's copper from the start pad to that pad, or `None` when the copper does not join them (`H-G-NETLEN-PATH`).
- **Start pad.** Among the net's pads in `pads` (c0028's `BoardPad`), sorted by `(ref, number)` as texts, the start pad MUST be the first whose `ref` or `REF-PIN` is in `starts`, else the first. A net without pads has `start` `None` and no paths.
- **Joins.** The copper of a net is its tracks and arcs on copper layers, its vias and its pads. An item end MUST join a track, an arc, a via or a pad of the net when it lies within that item's copper on a shared copper layer (a point touching the item's thick shape, `geometry-kernel`, "Exact gaps between thick shapes"). An end inside the body of a track or an arc, away from its ends, MUST split that item at the point of its centre line nearest to the end. A pad whose copper touches the body of an item that has no end inside the pad MUST join that item at the point of the item's centre line nearest to the pad's position. A via is joined like a pad: a via whose disc touches the body of an item that has no end inside the via MUST join that item at the point of its centre line nearest to the via's position, and a via whose disc touches a copper entry of a pad on a layer of its span MUST join that pad on that layer. Tracks and arcs whose copper only crosses MUST NOT be joined.
- **Weights.** A track or a part of it MUST weigh its `segment_length`; an arc or a part of it its `arc_length`, or the difference of two `arc_length_to` values. A change from layer `a` to layer `b` through a via MUST weigh `|facts.depths[a] − facts.depths[b]|`; a change of layer inside a pad MUST weigh 0, as KiCad counts a through-hole pad (`H-K-NETLEN-TOTAL`). With facts whose `count_vias` is false a change of layer through a via MUST weigh 0 too, as KiCad then counts no height, and it is not counted as unknown. A path's `length` MUST add the die lengths (`facts.die`) of its two end pads.
- **Search.** Paths MUST be found by Dijkstra on integer weights; between paths of equal length, the one whose sorted item ids come first MUST be taken. `vias` counts the vias a path goes through and `layers` lists the copper layers it runs on, in order. Without `facts`, or without the depth of a layer, a change of layer through a via MUST weigh 0 and be counted in the `analysis.input-missing` warning of "Net length report".
- **Stubs and open pads.** `off_path` MUST be the length of the net's tracks and arcs, or parts of them, that lie on no path of the row; when it is above 0, one `analysis.length-stub` info MUST give it, because KiCad's total counts it. A pad that the copper does not reach MUST have `length` `None`, and one `analysis.length-open` warning per net MUST name every such pad.
- **Agreement.** With facts of major 10, on a net whose copper is one unbranched chain from the start pad to its only other pad, `paths[0].length` MUST equal `total`. With facts of major 9 a path MAY be longer than `total` where it goes through a through via that its net does not reach on both ends, because KiCad 9 counts no height there; `docs/analyses.md` MUST say so.

#### Scenario: Unbranched net through a via
- **GIVEN** the two-layer bench (target 10, default stack-up) and its net `L_VIAPAD`: pad 2 of `R7` on `F.Cu`, 9.2 mm on `F.Cu`, a through via, 9.2 mm on `B.Cu` to pad 1 of `R8`, a part on the bottom side
- **WHEN** `uv run pytest tests/unit/analysis/test_length.py -k unbranched` measures it with the facts of major 10
- **THEN** `start` is `R7-2`, the one path ends at `R8-1` with `length == 19_980_000`, `vias == 1` and layers `F.Cu`, `B.Cu`, and `total == 19_980_000`

#### Scenario: A track beyond a pad is a stub
- **GIVEN** the net `L_PASS` of the same bench: one track from (50 mm, 20 mm) to (69.2 mm, 20 mm) through pad 2 of `R16` at (50.8 mm, 20 mm), ending at pad 1 of `R17`
- **WHEN** it is measured with the facts of major 10
- **THEN** `total == 19_200_000`, the path from `R16-2` to `R17-1` is 18 400 000 nm long, `off_path == 800_000`, and one `analysis.length-stub` info names 0.8 mm

#### Scenario: Paths to two loads
- **GIVEN** the net `L_BRANCH`: pad 2 of `R9` to pad 1 of `R10` by two tracks of 9.2 mm, and a 5 mm track from the point where they meet to pad 1 of `R11`
- **WHEN** it is measured with `starts=("R9",)`
- **THEN** `start` is `R9-2`, the paths are `R10-1` with 18 400 000 and `R11-1` with 14 200 000, `off_path == 0`, and `total == 23_400_000`

#### Scenario: KiCad 9 counts no height where the path does
- **GIVEN** the four-layer bench with the stack-up of `board-frame` "Via heights per major", and its net `VIP`: a through via inside pad 2 of `R1`, 18.4 mm on `In1.Cu`, a through via inside pad 1 of `R2`
- **WHEN** it is measured with the facts of major 10 and with those of major 9
- **THEN** with 10 the total and the path are both 18 707 500; with 9 the total is 18 400 000 and the path 18 672 500

#### Scenario: A pad the copper does not reach
- **GIVEN** a net with pads `U1-1`, `U2-1` and `U3-1`, and one track joining only the first two
- **WHEN** it is measured
- **THEN** the path to `U3-1` has `length` `None`, and one `analysis.length-open` warning names `U3-1`

### Requirement: Pair skew in the length report
`LengthReport.pairs` SHALL hold one `PairRow(name, p, n, total_p, total_n, skew, path_skew)` per differential pair whose two nets both have a row, sorted by name: each interface whose kind is a key of `model.pairs.PAIR_ROLES` (c0104: `diff_pair` with `p` and `n`, `usb2` with `dp` and `dn`), named after the interface, with its nets from `pair_nets`; then each pair of measured nets that `model.pairs.net_bases` couples by name and no interface names, named after its base, the positive net as `p`. A board read from a file holds no interface, so its pairs come from names. Until `model.pairs` of change c0104 exists, `pairs` MUST be empty.
- `skew` MUST be `total_p − total_n`, so a negative skew means that `p` is the shorter net.
- `path_skew` MUST be the difference of the lengths of the two nets' paths when each net has exactly two pads and both paths exist, and `None` otherwise.

#### Scenario: Pair one millimetre apart
- **GIVEN** a design with a `diff_pair` interface `SK` of the nets `SK_P`, one 20 mm track, and `SK_N`, one 21 mm track, and no pads
- **WHEN** `uv run pytest tests/unit/analysis/test_length.py -k pair` measures `SK_*`
- **THEN** `pairs` holds one row `SK` with `total_p == 20_000_000`, `total_n == 21_000_000`, `skew == -1_000_000` and `path_skew is None`

### Requirement: Length kind in the analyze command
`fenolite analyze` SHALL accept `length` in `--kinds` as a fourth kind that is not in the default set, so that without `--kinds` the command runs the three kinds of "Analyze command" and its reply holds no `lengths`.
- Options: `--net GLOB` (repeatable) and `--from REF` or `--from REF-PIN` (repeatable). Each MUST be a usage error (`FEN-2001`, exit 2) when `length` is not among the kinds. The major whose counting applies is the global `--kicad-version` (`Context.kicad_target`, 10 by default), which every command already takes.
- With `length`, the command MUST call `measure_lengths` with the pads of the backend when it satisfies `BoardFrame`, the facts of the backend when it satisfies `LengthSource` (with the project files next to the board and `major` from `Context.kicad_target`), and `nets` and `starts` from `--net` and `--from`.
- `result.lengths` MUST hold the rows and `result.pairs` the pair rows, as JSON objects with the field names of the records; `result.summary.length` MUST hold the report's summary, and `result.inputs` MUST gain `nets`, `from` and `kicad_version` when the kind runs (a reply without the kind holds none of the three). The report's issues join the envelope's `issues`; none has severity `error`, so the kind alone exits 0.
- The command stays read-only and runs no tool, as "Analyze command" states; `docs/cli-contract.md` MUST document the kind and its options under `analyze`.
- On input whose backend does not satisfy `LengthSource` (an Altium PCB document: no public source recorded here says how Altium counts a via or a die length), the kind MUST run without facts: routed lengths and paths with via changes weighing 0, the `analysis.input-missing` warning of "Net length report", `result.summary.length.major` `null` and the level `UNVERIFIED`. `--kicad-version` then changes nothing.

#### Scenario: Length of a net
- **GIVEN** the two-layer bench of `tests/_lengthbench.py` written for target 10 in `tmp_path`
- **WHEN** `uv run pytest tests/unit/cli/test_analyze_length.py -k bench` runs `fenolite analyze <board> --kinds length --net L_VIA2 --json`
- **THEN** the exit code is 0, `result.lengths` holds one row with `total == 21_580_000`, `result.summary.length.stackup` is `default`, and `result.inputs.kicad_version` is 10; with `--kicad-version 9` the total is 21 545 000

#### Scenario: Default kinds unchanged
- **WHEN** `fenolite analyze tests/data/kicad/board/two_layer.kicad_pcb --temp-rise 10 --copper-thickness 35um --json` runs
- **THEN** `result` holds `current` and `distances` and no `lengths`

#### Scenario: Usage errors
- **WHEN** `fenolite analyze <board> --net X --json` and `fenolite analyze <board> --kinds current --from R1 --temp-rise 10 --json` run
- **THEN** both exit 2 with `FEN-2001`

### Requirement: Length analysis issue codes
`fenolite.analysis.codes.ISSUE_CODES` SHALL also hold these keys, which are codes this capability emits ("Findings and issue codes"), and `docs/cli-contract.md` MUST document them under `analyze`; each MUST have a table in `src/fenolite/cli/data/explain.toml`. `analysis.input-missing` and `analysis.item-unsupported` keep their meaning for the length kind.

| code | severity | meaning |
|---|---|---|
| `analysis.length-open` | warning | pads of a measured net that its copper does not join to the start pad |
| `analysis.length-stub` | info | copper of a measured net on no path from its start pad, with its length |

#### Scenario: Codes in the table
- **WHEN** `uv run pytest tests/unit/analysis/test_findings.py -k length_codes` reads `ISSUE_CODES` and calls `issue("analysis.length-stub", "x", severity="warning")`
- **THEN** both codes are keys with the severities of this table, and the call raises `ValueError`

#### Scenario: Codes documented
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** `analysis.length-open` and `analysis.length-stub` appear in `docs/cli-contract.md`
