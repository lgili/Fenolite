## MODIFIED Requirements

### Requirement: Waivers in the check
`fenolite.checks.waivers` SHALL apply a design's waivers (`design-model`, "Waivers in the findings layer") to the findings of `check`, so that one accepted finding no longer counts as an error while it stays listed.
- **Input.** `run_checks(…, waivers=())` MUST pass the waivers to `copper_stage(…, waivers=…)`, to `drc_stage(…, waivers=…)` and to the stage `circuit.rules`, and `cmd_build` MUST apply them to its `circuit.*` issues the same way. `fenolite check` MUST pass `Design.findings.waivers` of the `.fenolite/` model of a built project, and no waiver for a native project or when `.fenolite/` cannot be loaded.
- **Document input.** `run_document_checks(…, waivers=())` ("Document check pipeline") MUST pass the waivers to its `copper.clearance` stage, and `fenolite check` on a built Altium project MUST pass the waivers of its `.fenolite/` model the same way, so one script gets the same verdict for an accepted copper finding on both targets. That pipeline has no DRC stage: a `kicad.drc.*` waiver is `unjudged` there with `stage-not-run`; its `circuit.rules` stage takes the `circuit.*` waivers. Waivers reach no other stage of either pipeline: `kicad.erc.*` and `parity.*` findings are never waived.
- **Matching.** `waiver_matches(waiver, code, names, gap=None)` MUST be true exactly when `code == waiver.code`, `len(names) == len(waiver.items)`, some one-to-one assignment of items to names has every item matching its name by `fnmatch.fnmatchcase`, and, when `waiver.min_gap` is set, `gap` is not `None` and `gap >= waiver.min_gap`. The names of a copper finding are the `where` of its two `CopperRef`s and its gap is `CopperFinding.gap`; the names of a DRC entry are the locations of its items as "DRC findings as issues" gives them, and it has no gap. A `circuit.*` finding has one name, its requirement row's id without the code, no gap, and matches only when the waiver's `digest` also equals the row's digest ("Waivers that expire").
- **Effect.** The issue of a matched finding MUST keep its code and `where`, take severity `info`, and end with ` (waived by <name>: <reason>)`, naming the first matching waiver in name order. A finding that no waiver matches is unchanged, and no finding is removed. A stage whose every error was waived MUST have status `ok`; waivers change no evidence.
- **Judged waivers.** A waiver is judged in a run when the stage of its code ran with a verdict, `copper.clearance` for a `copper.*` code, `drc.kicad` with a report for a `kicad.drc.*` code and `circuit.rules` not skipped for a `circuit.*` code, and its code is not `type_code(<oracle>, t)` for a type `t` of `UNREPEATABLE_TYPES = ("clearance", "hole_clearance", "unconnected_items", "shorting_items")`, whose entries KiCad does not repeat from run to run (`H-K-DRC-REPEAT`, `H-K-VIA-RENET`). A waiver of such a type is applied when it matches and is never judged, so two runs of `check` differ in nothing that "Check output is deterministic" does not already allow.
- **Stale waivers.** Each judged waiver that matched no finding, and whose code and items match no finding under another digest, MUST give one `check.waiver-unmatched` warning, `where` the waiver's name, whose message names its code and items and says that the finding is gone or its items were renamed. A waiver whose code and items match under another digest gives `check.waiver-expired` instead.
- **Result.** `CheckReport.waivers` and `result.waivers` of `check` MUST hold `declared` (the count), `matched` (name → number of findings matched, for judged waivers), `unmatched` (names), `expired` (names) and `unjudged` (name → `stage-not-run` or `not-repeatable`), each sorted by name.

#### Scenario: Waived clearance between two pads
- **GIVEN** a built project whose `.fenolite/` model holds the waiver `pitch` of code `copper.clearance`, items `J1-3` and `J1-4` and reason `fixed by the mating connector`, and whose board has the pads `J1-3` and `J1-4` 0.25 mm apart under a class clearance of 0.3 mm
- **WHEN** `uv run pytest tests/unit/checks/test_waivers.py -k pads` runs `fenolite check <project> --stages copper.clearance --json`
- **THEN** the `copper.clearance` issue naming the two pads has severity `info` and ends with `(waived by pitch: fixed by the mating connector)`, the exit code is 0, and `result.waivers.matched` is `{"pitch": 1}`

#### Scenario: The gap bound keeps a closer finding
- **GIVEN** a waiver of code `copper.clearance` with items `J1-3` and `*` and `min_gap` 150 000 nm, and a track 120 µm from `J1-3`
- **WHEN** the copper stage runs with the waiver
- **THEN** the finding stays an error and the waiver is unmatched; with the track 160 µm from the pad the finding is `info`

#### Scenario: Items match in either order
- **WHEN** `waiver_matches` is called for a waiver of items `("J1-3", "J1-4")` with the names `("J1-4", "J1-3")`, and with `("J1-3",)`
- **THEN** it returns `True` and `False`

#### Scenario: A stale waiver is reported
- **GIVEN** a waiver of code `copper.short` with items `R1-1` and `R2-1`, and a board where those pads do not touch
- **WHEN** `check --stages copper.clearance` runs
- **THEN** the issues hold one `check.waiver-unmatched` warning whose `where` is the waiver's name, and the exit code is the one the other issues give

#### Scenario: Unrepeatable and unrun waivers are not judged
- **GIVEN** a waiver of `kicad.drc.clearance`, a waiver of `kicad.drc.silk-overlap`, and a fake oracle whose report holds no entry of either type
- **WHEN** `run_checks` runs `drc.kicad`, then only `copper.clearance`
- **THEN** the first run gives one `check.waiver-unmatched` (for `silk-overlap`) and lists the other under `unjudged` as `not-repeatable`; the second gives none and lists both as `stage-not-run`

#### Scenario: A waiver on a built Altium project
- **GIVEN** the project of "Waived clearance between two pads" built with `--target altium`, whose `.fenolite/` model holds the waiver `pitch` and one more waiver of code `kicad.drc.via-dangling`
- **WHEN** `uv run pytest tests/unit/checks/test_waivers.py -k altium` runs `fenolite check <project> --stages copper.clearance --json`
- **THEN** the `copper.clearance` issue of the two pads has severity `info` and ends with `(waived by pitch: fixed by the mating connector)`, `result.waivers.matched` is `{"pitch": 1}`, and `result.waivers.unjudged` gives `stage-not-run` for the other waiver

#### Scenario: Native projects have no waivers
- **GIVEN** the native `two_layer` project
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages copper.clearance --json` runs
- **THEN** `result.waivers.declared` is 0 and the `copper.short` of its fill and pad stays an error

#### Scenario: A waived rating on the circuit stage
- **GIVEN** the `bad` variant of `examples/circuit/sensor` with `design.waive("circuit.rating-voltage", "C1:voltage", reason="bench is current-limited", digest=<the row's digest>)`, built in `tmp_path`
- **WHEN** `uv run pytest tests/unit/checks/test_waivers.py -k circuit` runs `fenolite check <dir> --stages circuit.rules --json` and builds it with `--dry-run --json`
- **THEN** in both replies the `circuit.rating-voltage` issue of `C1` has severity `info` and ends with `(waived by circuit.rating-voltage:C1:voltage: bench is current-limited)`, and `result.waivers.matched` of the check names the waiver once

## ADDED Requirements

### Requirement: Waivers that expire
Each requirement row SHALL carry `digest`: the first 16 hexadecimal digits of the SHA-256 of the canonical JSON of its `id`, the ranges of its value and limit, the limit's kind and both sources. Each `circuit.*` issue's hint MUST end with `digest <digest>`. A `circuit.*` waiver whose code and item match a finding under another digest MUST NOT waive it and MUST give one `check.waiver-expired` warning naming the waiver, both digests and the row.

#### Scenario: A changed rating expires the waiver
- **GIVEN** the project of "A waived rating on the circuit stage", then its capacitor's device record edited from `abs_max` 16 V to 20 V and the project built again
- **WHEN** `uv run pytest tests/unit/checks/test_waivers.py -k expired` runs `fenolite check <dir> --stages circuit.rules --json`
- **THEN** the `circuit.rating-voltage` issue of `C1` is an error again with the limit 10 V, one `check.waiver-expired` warning names the waiver and both digests, `result.waivers.expired` names it, and the exit code is 5

### Requirement: Circuit waiver codes
`checks.codes.ISSUE_CODES` SHALL hold `check.waiver-expired` (warning), documented in `docs/cli-contract.md` and `explain.toml`, and every `circuit.*` code of c0252 and c0253 SHALL also allow `info`, the severity of a waived finding.

#### Scenario: Waived severities are allowed
- **WHEN** `uv run pytest tests/unit/checks -k codes` reads `ISSUE_CODES`
- **THEN** `check.waiver-expired` is a key with severity `warning`, and every key that starts with `circuit.` allows `info`

### Requirement: Voltage propagation through links
After the stated sources of c0253, a net without a stated voltage SHALL take the hull of the stated voltages of the nets it reaches through links: two-net parts of class `ferrite`, `fuse` or `net_tie`, a `jumper` whose class the user stated, and a `resistor` or `shunt` whose `value_range` is exactly 0 Ω. No other part MAY be crossed. A stated net keeps its value; linked stated nets that do not overlap give `circuit.value-conflict`. `design.contracts(propagate=False)` turns it off.

#### Scenario: An analog rail behind a ferrite
- **GIVEN** the `good` variant of `examples/circuit/ferrite`: the rail `3V3` at 3.201 V to 3.399 V, a ferrite `FB1` from `3V3` to `3V3A`, no voltage set on `3V3A`, and a sensor port `vdda` (`in`, 1.71 V to 3.6 V) on `3V3A`
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_propagate.py` runs the stage
- **THEN** `3V3A` has the voltage 3.201 V to 3.399 V, the row of `vdda` passes, and no `circuit.rail-unset` names `3V3A`; in the `bad` variant, where a 10 Ω resistor replaces `FB1`, `3V3A` has no voltage and one `circuit.rail-unset` names it

### Requirement: Origins of applied values
Every voltage and current bound SHALL record its origin: `declared` (a design rail or an `out` port), `rig`, `role`, `requirements`, `option` (`--current`) or `propagated`, the last with `via` (the link references in order) and `from` (the stated net). The requirement row's `value` MUST hold `origin`, and its text form MUST read `propagated via <refs> from <net>`.

#### Scenario: The origin of a propagated value
- **GIVEN** the `good` variant of `examples/circuit/ferrite`
- **WHEN** `fenolite check <dir> --stages circuit.rules --json` runs
- **THEN** the row of the sensor's `vdda` has `value.origin` `{"from": "3V3", "kind": "propagated", "via": ["FB1"]}`, and the row of a part on `3V3` has `value.origin.kind` `declared`

### Requirement: Decidable stages of requirement rows
Each requirement row SHALL carry `decidable`: `build` for `circuit.*` rows, `place` for `roles.loop-area` and `roles.gate-loop`, `route` for every other judged `roles.*` row. A `place` row is reached when every component of its subject is inside the board outline, a `route` row when also no net of its subject has an open connection. A row not reached that does not fail MUST have status `deferred`, MUST give no issue, and is counted in `summary.deferred`; a failing row stays `fail`.

#### Scenario: Track width before routing
- **GIVEN** a built project whose net `VBUS` has a confirmed role with `milliamps` 2000 and still one open connection, and whose parts are inside the outline
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_decidable.py` runs `fenolite check <dir> --stages roles.rules,circuit.rules --json`
- **THEN** the row `roles.width-current:VBUS` has status `deferred` and `decidable` `route`, no `roles.width-current` names `VBUS`, `summary.deferred` of `roles.rules` is `{"route": 1}`, and no row of `circuit.rules` is deferred

### Requirement: Stable requirement row ids
A requirement row id SHALL be built from references, port paths, net names, interface names and expectation ids only, in the closed forms of `design.md` (decision 7), and never from entity ids, positions or seeds. Two builds of one design with different seeds, or with its statements reordered, MUST give the same ids.

#### Scenario: Ids survive a reordered script
- **GIVEN** `examples/circuit/sensor/bad.py` and a copy whose part and connect statements are reordered, built with `--seed 1` and `--seed 2`
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_matrix.py -k stable` collects the row ids of `circuit.rules`
- **THEN** the four sorted id lists are equal
