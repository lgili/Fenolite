## ADDED Requirements

### Requirement: Pair and escape routes pass the oracle
Pair routing and the escape of fine-pitch parts SHALL be proved with KiCadRoutingTools at `PINNED_TAG`, Freerouting `PINNED_VERSION` and `kicad-cli` 9.0.9 and 10.0.6, gate first, on benches authored for Fenolite (`tests/routing/_pairbench.py`, `tests/routing/_escapebench.py`) and built by Fenolite for targets 9 and 10, in tests marked `needs_router`, `needs_freerouting` and `needs_kicad`.
- **Pairs** (`H-K-KRT-PAIR`): on the pair bench (two pairs and four single nets between two headers of 1.27 mm pitch; class pair width 0.2 mm and gap 0.15 mm; a board minimum width of 0.15 mm; rules `diff_pair_gap` 0.13 mm to 0.17 mm, `diff_pair_uncoupled` 6 mm and `diff_pair_skew` 0.1 mm), after the pair steps of "KiCadRoutingTools routes pairs" and `route.py` for the single nets, `pcb drc` of the board's major MUST report no unconnected item, no `diff_pair_gap_out_of_range`, no `diff_pair_uncoupled_length_too_long`, and no type of severity error that the unrouted bench lacks other than `skew_out_of_range`, whose items and values are recorded. Outcomes `krt-pair-t9` and `krt-pair-t10`.
- **Names** (`H-K-KRT-PAIRNAMES`): on the name bench (five pairs named `A_P`/`A_N`, `B+`/`B-`, `C_P0`/`C_N0`, `DP1`/`DN1`, `E_DP`/`E_DN`), the forms that `route_diff.py` routes coupled at the gap are recorded as `krt-pair-names`, and `routingtools.PAIR_NAME_FORMS` MUST equal them.
- **Escape** (`H-K-KRT-ESCAPE`, `H-G-DSN-FANOUT`): on the QFN bench (a QFN-48 of 0.5 mm pitch, 40 signal nets) and the BGA bench (a BGA-121 of 0.8 mm pitch, 96 signal nets, a board-wide `hole_clearance` rule of 0.15 mm), both with plane layers (c0107), each router runs with and without its escape (KiCadRoutingTools: `qfn_fanout.py` on the QFN, `bga_fanout.py --escape-method dogbone` on the BGA, then `route.py`; Freerouting with and without its fanout stage, neck-down off), at most 900 s per run. Each outcome `krt-escape-<bench>-t<M>` and `dsn-escape-<bench>-t<M>` MUST record the open connections of signal nets, the error types the unrouted bench lacks, the vias whose centre lies inside a pad and the wall time. It is `equal` when no signal connection is open, `improved` when the escape leaves fewer open signal connections than the run without it, each only with no new error type and no via inside a pad, and `different` otherwise.
- **Freerouting facts**: `dsn-pair-ignored` (`H-G-DSN-PAIR`): the session's routes are equal with and without `pair` lists; `dsn-narrow-fanout` and `dsn-narrow-off` (`H-G-DSN-NARROW`): on the QFN bench with four signal layers, a wire narrower than its class with the fanout stage on, and none with the stage and neck-down off.
- **Verdict.** The feature `pairs` of KiCadRoutingTools MUST be declared only when `krt-pair-t9` and `krt-pair-t10` are `equal`, and the feature `escape` only when its escape outcomes are `equal` or `improved` on both benches and both majors. Otherwise the register row MUST be refuted with a successor naming the open connections or the violations, and the requirement of the step that is not built MUST be removed from this change before it is archived.
- The outcomes MUST be recorded in `docs/evidence/routing.md`, `docs/evidence/routing/freerouting-2.4.1.json` and `docs/evidence/routing/krt-v0.22.1.json`, and MUST NOT be written to `docs/evidence/kicad/probes/`.
- **Loop**: `build`, `route` with pairs, `fill` (10.0.6) and `build` again MUST keep every routed item, and a further `build` MUST change no byte.

#### Scenario: Pair gate on 10.0
- **GIVEN** `FENOLITE_KRT` naming a checkout at `PINNED_TAG`
- **WHEN** `uv run pytest tests/routing/test_pair_gate.py -rA` runs on the local KiCad 10.0.6
- **THEN** `krt-pair-t10` and `krt-pair-names` are recorded, and `krt-pair-t10` is `equal`

#### Scenario: Pair gate on 9.0
- **WHEN** the same command runs inside the pinned 9.0.9 image with the tool mounted
- **THEN** `krt-pair-t9` is recorded for the target-9 bench, judged without a refill

#### Scenario: Escape benches
- **WHEN** `uv run pytest tests/routing/test_escape_gate.py -rA` runs on 10.0.6 with both tools
- **THEN** the eight outcomes of 10.0.6 are recorded with their open connections, error types and wall times

#### Scenario: Freerouting facts
- **GIVEN** `FENOLITE_FREEROUTING_JAR` naming the pinned jar
- **WHEN** `uv run pytest tests/routing/test_pair_gate.py -k dsn_pair -rA` and `uv run pytest tests/routing/test_escape_gate.py -k narrow -rA` run
- **THEN** `dsn-pair-ignored`, `dsn-narrow-fanout` and `dsn-narrow-off` are recorded

#### Scenario: Skipped without the tools
- **GIVEN** neither `FENOLITE_KRT` nor `FENOLITE_FREEROUTING_JAR`
- **WHEN** `uv run pytest tests/routing -m "needs_router or needs_freerouting" -rs` runs
- **THEN** every test of this requirement is skipped with a reason naming the variable

### Requirement: Pair coupling in KiCad's DRC is probed
How KiCad's DRC counts coupled length SHALL be pinned by probes run with `kicad-cli` alone (`H-K-DRU-PAIRCOUPLE`), on an authored bench whose script copper holds one pair routed 0.15 mm apart and one routed 1.07 mm apart, judged with four rules files: a `diff_pair_gap` rule of 0.13 mm to 0.17 mm alone, a `diff_pair_uncoupled` rule of 3 mm alone, both, and none.
- With the gap rule present, every segment outside its range MUST count as uncoupled: the wide pair is reported with an uncoupled length equal to its routed length. Without a gap rule, parallel segments 1.07 mm apart MUST count as coupled.
- The probes `dru-pair-couple-<case>` MUST be recorded in the probe files of both majors.

#### Scenario: Four rules files
- **WHEN** `uv run pytest tests/kicad/rules/test_pair_coupling.py -rA` runs on the local KiCad 10.0.6 and inside the pinned 9.0.9 image
- **THEN** the gap rule alone reports only `diff_pair_gap_out_of_range`, on the wide pair; the uncoupled rule alone reports at most the wide pair, with an uncoupled length below its routed length; both rules report the wide pair with an uncoupled length equal to its routed length; no rule reports nothing; and the outcomes are equal on both majors
