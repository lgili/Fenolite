## ADDED Requirements

### Requirement: Waivers in the DSL
`Design.waive(code, *items, reason, min_gap=None, name=None)` SHALL record one waiver: the acceptance of one finding of `check` or of the copper guard, with a reason (`verification-loop`, "Waivers in the check"). The call MUST raise `DslError`, before anything is built, when:
- `code` is not `copper.short`, `copper.clearance`, `copper.zone-overlap`, or `kicad.drc.<suffix>` with a suffix that matches `[a-z0-9]+(-[a-z0-9]+)*` and is not a member of `checks.drc_json.RESERVED_SUFFIXES` (`rules-not-loaded`, `rules-unchecked`, `parity-unchecked`), which are verdicts and not findings; a `kicad.erc.*` or `parity.*` code is refused by the same rule, with a hint that only copper and DRC findings are waived;
- `items` are not one or two, an item is neither a non-empty string without `", "` nor a `Part`, or a `copper.*` code has other than two items;
- the code is `copper.short` or `kicad.drc.shorting-items` and an item holds `*`, `?` or `[`: a short is waived by exact names only;
- `reason` is empty after stripping or holds a line break;
- `min_gap` is given with a code other than `copper.clearance`, is not a positive length, or is missing from a `copper.clearance` waiver whose items hold a glob character;
- `name` is empty or holds a line break, or a waiver of that name was already recorded. The default name is `<code>:<items joined by ",">`, so the same waiver declared twice also raises.

`to_model` MUST put the waivers into `Design.findings.waivers` sorted by name, a `Part` replaced by its reference.

#### Scenario: A waiver reaches the model
- **GIVEN** a design with part `J1` and the call `design.waive("copper.clearance", "J1-3", "J1-4", reason="fixed by the mating connector", name="pitch")`
- **WHEN** `uv run pytest tests/unit/dsl/test_waivers.py -k model` converts it with `to_model`
- **THEN** `findings.waivers` holds one `Waiver(name="pitch", code="copper.clearance", items=("J1-3", "J1-4"), reason="fixed by the mating connector", min_gap=None)`

#### Scenario: Refused waivers
- **WHEN** `design.waive` is called with code `copper.short` and items `R1-1`, `R2-*`; with code `copper.clearance`, items `J1-3`, `*` and no `min_gap`; with code `kicad.drc.rules-not-loaded`; with code `kicad.drc.parity-unchecked`; with code `parity.net-conflict`; with `min_gap=mm(0.1)` and code `kicad.drc.silk-overlap`; with `reason=" "`; and twice with the same code and items
- **THEN** each call raises `DslError` naming the rule it broke

#### Scenario: Default name and parts
- **GIVEN** part `TP1` and `design.waive("kicad.drc.via-dangling", "*", reason="test point")` and `design.waive("kicad.drc.courtyards-overlap", tp1, "U1", reason="stacked by design")`
- **WHEN** the design is converted
- **THEN** the waivers are named `kicad.drc.courtyards-overlap:TP1,U1` and `kicad.drc.via-dangling:*`, in that order

### Requirement: Check severities in the DSL
`design.rules.severity(code, level)` SHALL record the severity that the target's DRC gives one of its checks, as `RuleSet.severities[code] = level` (`design-model`, "Check severities in the rules layer"). The call MUST raise `DslError` when:
- `code` is a `copper.*` code, with a hint naming `design.waive`, because a copper finding is accepted one by one and never by a severity;
- `code` is not `kicad.drc.<suffix>` with a suffix as "Waivers in the DSL" allows;
- `level` is not `error`, `warning` or `ignore`;
- `code` is `kicad.drc.clearance` and `level` is `ignore`, because the check canary needs clearance entries to prove the rules were loaded (canary reason `clearance-ignored`);
- the code was already given a severity.

Whether the target applies the key is judged when the project is written (`kicad-file-backend`, "Project files carry the check severities"). A `--target altium` build MUST write no severity and MUST report the codes in one `altium.not-lowered` info whose `where` is the kind `severity` (`backends.altium.lower`); the kind MUST NOT be in `LOSS_KINDS`, and the Altium rule table (`altium-pcb-writer`, "Rule lowering table") gains no row, because a severity is not a rule kind.

#### Scenario: A severity reaches the model
- **WHEN** `uv run pytest tests/unit/dsl/test_severities.py` converts a design with `design.rules.severity("kicad.drc.silk-overlap", "ignore")`
- **THEN** `rules.severities == {"kicad.drc.silk-overlap": "ignore"}`

#### Scenario: Refused severities
- **WHEN** `design.rules.severity` is called with (`copper.clearance`, `warning`), (`kicad.drc.silk-overlap`, `info`), (`kicad.drc.clearance`, `ignore`) and twice with (`kicad.drc.via-dangling`, `error`)
- **THEN** each call raises `DslError`, the first with a hint naming `design.waive`

#### Scenario: Severities in an Altium build
- **GIVEN** the routed blink with `design.rules.severity("kicad.drc.silk-overlap", "ignore")`
- **WHEN** `uv run pytest tests/unit/cli -k "altium and severit"` builds it with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `issues` holds one `altium.not-lowered` info whose `where` is `severity` and whose message names `kicad.drc.silk-overlap`, and the planned documents equal those of the build without the call

### Requirement: Waivers in the copper guard
The copper guard of `build` (`design-dsl`, "Copper guard before writing") SHALL apply the design's `copper.*` waivers to its findings as `verification-loop`, "Waivers in the check", matches and marks them, before its mode: a matched finding is `info` in `refuse` and in `warn` mode, so it neither refuses the build nor gains the warn note. `result.copper_check.waivers` MUST hold `matched` (name → number of findings) and `unmatched` (the names of `copper.*` waivers that matched nothing), sorted by name. The guard MUST NOT judge `kicad.drc.*` waivers and MUST NOT emit `check.waiver-unmatched`: `check` reports stale waivers.
- **The Altium target.** The copper guard of `build --target altium` (`altium-build`, "Copper guard in an Altium build") MUST apply the same waivers the same way, before its mode: a waived `copper.short` is `info`, so it does not refuse the build, and a waived finding of another code gains neither of that guard's notes. `result.copper_check.waivers` MUST hold the same two keys.

#### Scenario: A waived short builds
- **GIVEN** a design whose authored footprint `KS1` has overlapping pads `1` (net `ISENSE`) and `2` (net `PWR`) without a net-tie group, and `design.waive("copper.short", "KS1-1", "KS1-2", reason="Kelvin pad")`
- **WHEN** `uv run pytest tests/unit/cli/test_build_copper_guard.py -k waiver` runs the build with the default `--copper-check refuse`
- **THEN** the build plans its writes, the issues hold the `copper.short` with severity `info` ending with `(waived by copper.short:KS1-1,KS1-2: Kelvin pad)`, and `result.copper_check.waivers.matched` counts it

#### Scenario: Unmatched waiver listed in the build
- **GIVEN** the same design with the pads 0.5 mm apart
- **WHEN** the build runs
- **THEN** `result.copper_check.waivers.unmatched` names the waiver, and no `check.waiver-unmatched` issue is emitted

#### Scenario: A waived short builds for Altium
- **GIVEN** the design of "A waived short builds"
- **WHEN** `uv run pytest tests/unit/cli -k "altium and waiver"` builds it with `--target altium --dry-run --json`
- **THEN** the exit code is 0, the `.PcbDoc` is planned, the `copper.short` has severity `info` and ends with `(waived by copper.short:KS1-1,KS1-2: Kelvin pad)`, and without the waiver the same build exits 5
