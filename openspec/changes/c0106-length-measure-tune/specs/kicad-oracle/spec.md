## ADDED Requirements

### Requirement: Net length parity canaries
`tests/kicad/length/test_length_parity.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-NETLEN-TOTAL`, `H-K-NETLEN-STACKUP`, `H-K-NETLEN-RULES`, and `H-K-NETLEN-VIA10` on 10.0.x or `H-K-NETLEN-VIA9` on 9.0.x, on the benches of `tests/_lengthbench.py` written for the running major: two layers without a stack-up, with a stack-up and with `use_height_for_length_calcs` set to `false`; four layers without a stack-up and with the explicit stack-up of the design's Context; six and eight layers without a stack-up; pads at vias; and the rules benches. DRC MUST be judged only from the JSON report, and every rules file MUST hold the scoped canary of c0071.
- **Totals.** For each net of a case, the test MUST run `pcb drc` once with the rule `length (max T − 1 µm)` and once with `length (max T + 1 µm)`, `T` being the net's total in `length_facts` for the running major. Probe `length-total-<case>`, or `length-via-<case>` for a via case, MUST record `equal` when the first run reports the net and the second does not, and `different` otherwise. The `actual` that the first run prints MUST be written to `docs/evidence/length.md`.
- **Rules.** On the rules benches the stage `length.rules` MUST name the same nets, with `length.out-of-range` and `length.skew-out-of-range`, as KiCad's `length_out_of_range` and `skew_out_of_range` violations; probe `length-rules-<case>` records `equal` or `different`. Until the stage exists (it needs the rule kinds of change c0104), the test MUST compare KiCad's violations with the nets that `H-K-NETLEN-RULES` predicts, and no `length-rules-*` probe is registered.
- **A node that is not read.** For the four-layer bench whose stack-up node lost its silkscreen and paste rows, probe `length-via-four-unprojected` MUST record `equal` when KiCad counts the thicknesses of that node (the bracket built from the totals of the explicit stack-up) and `different` otherwise; `length_facts` MUST say `none` for that board.
- A run whose canary does not fire MUST fail. The outcomes MUST be recorded in both probe files, and the facts MUST be written to `docs/formats/kicad/length.md` with S-0020, S-0029 and their labels. A `different` outcome MUST stop the part it settles and be written into the register row.

#### Scenario: Both majors
- **WHEN** `uv run pytest tests/kicad/length/test_length_parity.py -rA` runs on the local KiCad 10.0.6 and inside the pinned 9.0.9 image
- **THEN** every `length-total-*`, `length-via-*` and `length-rules-*` probe records `equal`, and the canary fires in every run

#### Scenario: The two majors count a via apart
- **GIVEN** the four-layer bench with the explicit stack-up and its net of a through via between `F.Cu` and `In1.Cu`
- **WHEN** the test runs on each major
- **THEN** the total that passes the bracket is 20 153 750 nm on 10.0.6 and 20 000 000 nm on 9.0.9

### Requirement: Meanders pass the oracle
`tests/kicad/length/test_meander_oracle.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-NETLEN-MEANDER` on three designs built with `build_design` for the running major: a segment along an axis meandered to a target, a pair on four layers with a via step matched with `match`, and a segment at 30° meandered to a target. Each board MUST be written with the scoped canary and, for each meandered net, the two length rules of "Net length parity canaries" around its target.
- Probe `length-meander-<case>` MUST record `equal` when KiCad reports the net with the rule 1 µm below the target, does not report it with the rule 1 µm above, and reports no violation that the same design built without the meander lacks, apart from the length rules; `different` otherwise.
- For the pair, a skew rule judged within the pair with `max 0.001mm` MUST give no violation.

#### Scenario: Meanders on both majors
- **WHEN** `uv run pytest tests/kicad/length/test_meander_oracle.py -rA` runs on the local KiCad 10.0.6 and inside the pinned 9.0.9 image
- **THEN** the three `length-meander-*` probes record `equal`, and the canary fires in every run
