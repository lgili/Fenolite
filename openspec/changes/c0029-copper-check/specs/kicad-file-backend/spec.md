## ADDED Requirements

### Requirement: Design rules for the copper check
`fenolite.backends.kicad.copperrules.design_rules_from_texts(design, *, project_text, rules_text, major=versions.DEFAULT_TARGET, file_stem="", issues=None) -> DesignRules` SHALL apply the texts of a project file and a rules file, each `None` when absent, to a board design read with `read_board`:
- **Project.** It MUST read `project_text` with c0010's `pro.read_project(project_text, file=f"{file_stem}.kicad_pro")`, return `pro.apply_project(design, info)` as the design, and return `info.floors.get("clearance")` as `min_clearance`.
- **Rules.** It MUST read `rules_text` with c0018's `dru.read_rules(rules_text, file=f"{file_stem}.kicad_dru")` and set the design's `rules` to the result. `opaque_clearance_rules` MUST count the rule items of `dru.parse_rules(rules_text)` that hold a `clearance` constraint and were kept opaque.
- **Tables.** `rules_over_classes` MUST be `major in lowering.RULES_OVER_CLASSES` and `floor_over_rules` MUST be `major in lowering.FLOOR_OVER_RULES["min_clearance"]`, c0026's tables measured per major (`H-K-PRO-MIN-CLASS`, `H-K-PRO-MIN-RULE`).
- **Failures.** A text that raises `FormatError` (its subclasses included) MUST be named in `unread` with the error's message, and the design MUST keep what that file would have given.
- **Issues.** The readers' issues (`kicad.project.*`, `kicad.version.*`, `rules.kept-opaque`) MUST be appended to `issues`.
- **Evidence.** `evidence` MUST be `Evidence.combine` of `pro.EVIDENCE` when a project text was read and `dru.EVIDENCE` when a rules text was read, and `Evidence()` when neither was.
- `KicadBackend.design_rules(design, project, *, issues=None)` MUST pass the texts of `<stem>.kicad_pro` and `<stem>.kicad_dru` from `project.files`, `<stem>` being the stem of `project.board`, or `None` for a file the copy set does not hold, and as `major` the major of the project file (`ProjectInfo.major`) when it has one, else `versions.DEFAULT_TARGET`. It MUST read no other file.

#### Scenario: Net-class bench applied
- **GIVEN** the bench of `tests/_netclass_bench.py` written by `write_triad` for target 10, and its board read back with `read_board`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_copperrules.py -k bench` calls `design_rules_from_texts` with the written project and rules texts
- **THEN** the design's classes are `Default` and `HV`, the nets `+3V3` and `SIG1` have the HV id, and `min_clearance` equals `info.floors.get("clearance")` of the written project

#### Scenario: Opaque clearance rule counted
- **GIVEN** a rules text holding `(version 1)`, one clearance rule whose condition is `A.Type == 'Text'` and one `track_width` rule with the same condition
- **WHEN** `design_rules_from_texts` is called with it
- **THEN** `opaque_clearance_rules` is 1, the design's `rules` holds no lifted rule, and `issues` holds two `rules.kept-opaque` infos

#### Scenario: No project files
- **WHEN** `design_rules_from_texts(design, project_text=None, rules_text=None)` is called
- **THEN** it returns `design` unchanged, `min_clearance is None`, `unread == ()` and evidence level `UNVERIFIED`

#### Scenario: Measured tables applied
- **GIVEN** `lowering.RULES_OVER_CLASSES` patched to `frozenset({10})` and `lowering.FLOOR_OVER_RULES["min_clearance"]` to `frozenset({9})`
- **WHEN** `design_rules_from_texts(design, project_text=None, rules_text=None, major=9)` and the same call with `major=10` run
- **THEN** the first gives `rules_over_classes` false and `floor_over_rules` true, and the second the reverse
