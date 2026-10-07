## ADDED Requirements

### Requirement: Waivers in the check
`fenolite.checks.waivers` SHALL apply a design's waivers (`design-model`, "Waivers in the findings layer") to the findings of `check`, so that one accepted finding no longer counts as an error while it stays listed.
- **Input.** `run_checks(…, waivers=())` MUST pass the waivers to `copper_stage(…, waivers=…)` and to `drc_stage(…, waivers=…)`. `fenolite check` MUST pass `Design.findings.waivers` of the `.fenolite/` model of a built project, and no waiver for a native project or when `.fenolite/` cannot be loaded.
- **Document input.** `run_document_checks(…, waivers=())` ("Document check pipeline") MUST pass the waivers to its `copper.clearance` stage, and `fenolite check` on a built Altium project MUST pass the waivers of its `.fenolite/` model the same way, so one script gets the same verdict for an accepted copper finding on both targets. That pipeline has no DRC stage: a `kicad.drc.*` waiver is `unjudged` there with `stage-not-run`. Waivers reach no other stage of either pipeline: `kicad.erc.*` and `parity.*` findings are never waived.
- **Matching.** `waiver_matches(waiver, code, names, gap=None)` MUST be true exactly when `code == waiver.code`, `len(names) == len(waiver.items)`, some one-to-one assignment of items to names has every item matching its name by `fnmatch.fnmatchcase`, and, when `waiver.min_gap` is set, `gap` is not `None` and `gap >= waiver.min_gap`. The names of a copper finding are the `where` of its two `CopperRef`s and its gap is `CopperFinding.gap`; the names of a DRC entry are the locations of its items as "DRC findings as issues" gives them, and it has no gap.
- **Effect.** The issue of a matched finding MUST keep its code and `where`, take severity `info`, and end with ` (waived by <name>: <reason>)`, naming the first matching waiver in name order. A finding that no waiver matches is unchanged, and no finding is removed. A stage whose every error was waived MUST have status `ok`; waivers change no evidence.
- **Judged waivers.** A waiver is judged in a run when the stage of its code ran with a verdict, `copper.clearance` for a `copper.*` code and `drc.kicad` with a report for a `kicad.drc.*` code, and its code is not `type_code(<oracle>, t)` for a type `t` of `UNREPEATABLE_TYPES = ("clearance", "hole_clearance", "unconnected_items", "shorting_items")`, whose entries KiCad does not repeat from run to run (`H-K-DRC-REPEAT`, `H-K-VIA-RENET`). A waiver of such a type is applied when it matches and is never judged, so two runs of `check` differ in nothing that "Check output is deterministic" does not already allow.
- **Stale waivers.** Each judged waiver that matched no finding MUST give one `check.waiver-unmatched` warning, `where` the waiver's name, whose message names its code and items and says that the finding is gone or its items were renamed.
- **Result.** `CheckReport.waivers` and `result.waivers` of `check` MUST hold `declared` (the count), `matched` (name → number of findings matched, for judged waivers), `unmatched` (names) and `unjudged` (name → `stage-not-run` or `not-repeatable`), each sorted by name.

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

### Requirement: Exclusions in the DRC stage
`checks.drc.drc_stage(…, exclusions=())` SHALL take the project's stored DRC exclusions (`backend-protocol`, "Stored exclusions source") and SHALL say, for each, whether KiCad still applies it, because `pcb drc` ignores an exclusion that matches nothing without a message (`H-K-DRC-EXCL`). `run_checks` MUST pass `validator.stored_exclusions(project)` when `isinstance(validator, ExclusionSource)` is true, and none otherwise.
- **Comment.** The issue of an entry that the report marks `excluded` MUST end with ` (excluded in the project: <comment>)`, or ` (excluded in the project)` when its comment is empty.
- **Live or stale.** An exclusion whose type is not in `UNREPEATABLE_TYPES` ("Waivers in the check") is live when an entry of the report has `excluded` true, its type, and item uuids equal to its own, in order and without regard to letter case, the nil uuid standing for a missing second item. Otherwise it MUST give one `check.exclusion-stale` warning: reason `moved` when an entry of that type and those uuids is reported without `excluded`, because KiCad matches the marker position to the nanometre, and `gone` otherwise. Its `where` MUST be the items' locations as "DRC findings as issues" gives them, and `@<x>,<y>` from the exclusion's position for a uuid that names no entity; its message names the type, the reason and the comment.
- **Summary.** `summary.exclusions` MUST hold the counts `stored`, `live`, `stale` and `unjudged` (exclusions of an unrepeatable type).
- Without a report no exclusion is judged, and every count but `stored` is 0.
- Exclusions belong to the KiCad pipeline. `run_document_checks` has no DRC stage, reads no exclusion and reports no `summary.exclusions`.

#### Scenario: Comment of an excluded entry
- **GIVEN** a fake oracle whose report holds one `via_dangling` entry with `excluded` true and comment `test point`
- **WHEN** `uv run pytest tests/unit/checks/test_drc_stage.py -k exclusion` runs the stage
- **THEN** its `kicad.drc.via-dangling` issue has severity `info` and ends with `(excluded in the project: test point)`

#### Scenario: A moved exclusion
- **GIVEN** the same report with `excluded` false, and a stored exclusion of type `via_dangling` naming the via's uuid and the nil uuid at another position
- **WHEN** the stage runs with that exclusion
- **THEN** it reports one `check.exclusion-stale` warning with reason `moved`, and `summary.exclusions` is `{"stored": 1, "live": 0, "stale": 1, "unjudged": 0}`

#### Scenario: A gone exclusion and an unrepeatable one
- **GIVEN** a report without any entry, and two stored exclusions, one of type `courtyards_overlap` and one of type `clearance`
- **WHEN** the stage runs
- **THEN** it reports one `check.exclusion-stale` warning, with reason `gone`, for the courtyard exclusion only, and `summary.exclusions.unjudged` is 1

### Requirement: Waiver and exclusion issue codes
`fenolite.checks.codes.ISSUE_CODES` SHALL also hold these keys with these severities ("Check issue codes"), and `docs/cli-contract.md` MUST document each, together with the `info` severity of a waived finding ("Copper stage issue codes") and the keys of `result.waivers`. `src/fenolite/cli/data/explain.toml` MUST hold one table for each (`cli-contract`, "Explain command"), and one for each of the two project codes of `kicad-file-backend`, "Project files carry the check severities".

| code | severity | when |
|---|---|---|
| `check.waiver-unmatched` | warning | a judged waiver matched no finding |
| `check.exclusion-stale` | warning | a stored KiCad exclusion of a repeatable type no longer applies, `moved` or `gone` |

#### Scenario: Literals are keys
- **WHEN** `uv run pytest tests/unit/checks -k codes` collects every issue-code literal under `src/fenolite/checks/`
- **THEN** `check.waiver-unmatched` and `check.exclusion-stale` are keys of `ISSUE_CODES` with severity `warning`

#### Scenario: Codes documented
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** both codes and `result.waivers` appear in `docs/cli-contract.md`

#### Scenario: Codes explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs, and then `uv run fenolite explain check.waiver-unmatched --json`
- **THEN** the test passes with a table for `check.waiver-unmatched`, `check.exclusion-stale`, `kicad.project.unknown-check` and `kicad.project.dropped-check`, and the command exits 0 with a non-empty `result.meaning` and `result.fix`

## MODIFIED Requirements

### Requirement: Copper stage issue codes
`fenolite.checks.codes.ISSUE_CODES` SHALL also hold these keys with these severities ("Check issue codes"), and `docs/cli-contract.md` MUST document each. The build guard (`design-dsl`, "Copper guard before writing"; for the Altium target `altium-build`, "Copper guard in an Altium build") emits the same codes into the `build` envelope, where they pass through unchanged as `design-dsl` "Build issue codes" allows for codes that later requirements add. The severity `info` of the first three codes is that of a finding a waiver accepted ("Waivers in the check"); the copper check itself never gives it.

| code | severity | when |
|---|---|---|
| `copper.short` | error, info | copper of two nets touches or overlaps on a shared copper layer; `info` when waived |
| `copper.clearance` | error, warning, info | a gap below the clearance in force; the governing rule sets the severity; `info` when waived |
| `copper.zone-overlap` | warning, info | zones of different nets and equal priority overlap on a shared layer; `info` when waived |
| `copper.rules-incomplete` | warning | a clearance rule stayed opaque, a project file was not read, or no rules source was given |
| `copper.item-unsupported` | warning | copper items left out of the check, per kind |
| `copper.clearance-unset` | info | item pairs judged for shorts only, because no clearance is in force |

#### Scenario: Copper literals are keys
- **WHEN** `uv run pytest tests/unit/checks -k codes` collects every issue-code literal under `src/fenolite/checks/`
- **THEN** each `copper.*` literal is a key of `ISSUE_CODES` with the severities of this table

#### Scenario: Copper codes documented
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** the six `copper.*` codes appear in `docs/cli-contract.md`

#### Scenario: The check never gives info for a finding
- **GIVEN** the boards of `tests/unit/checks/test_copper.py`
- **WHEN** `check_copper` runs on each without any waiver
- **THEN** no `copper.short`, `copper.clearance` or `copper.zone-overlap` issue has severity `info`
