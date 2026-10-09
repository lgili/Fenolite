## MODIFIED Requirements

### Requirement: Copper guard before writing
`fenolite build` with the KiCad target (`--target kicad`, the default) SHALL judge the copper of the triad it is about to write with `fenolite.checks.copper.check_copper` (`copper-check`) after `lens.build.build_design` returns its files and before `cmd_build` calls `check_existing` and returns its plan, on `--dry-run` and `--confirm` alike. When `build_design` refused (no files), the guard MUST NOT run. With `--target altium` this guard MUST NOT run: that branch writes no KiCad triad, and judges its PCB document with the guard of `altium-build`, "Copper guard in an Altium build".
- **What is judged.** `cmd_build` MUST read the planned `<name>.kicad_pcb` text back with `read_board`, apply the planned `<name>.kicad_pro` and `<name>.kicad_dru` texts with `copperrules.design_rules_from_texts` and `major` = the build's target (`Context.kicad_target`), take the pads from c0028's `BoardFrame.board_pads` of `KicadBackend`, and call `check_copper` with the design, `min_clearance`, `rules_over_classes` and `floor_over_rules` it gets. The guard therefore judges the bytes that will be written, preserved copper (`layout-lens`) included. It MUST read and write no file.
- **Modes.** The option `--copper-check refuse|warn` MUST default to `refuse`. With `refuse`, every copper issue MUST join the envelope's `issues` with its severity, so a `copper.short` or a `copper.clearance` error makes the build return no planned write and exit 5 ("Build command"). With `warn`, every copper issue of severity `error` MUST be reported with severity `warning` and ` (copper guard in warn mode)` appended to its message, and the build MUST plan its writes as usual. Any other value MUST exit 2 with `FEN-2001`. `--copper-check` given with `--target altium` selects the mode of that target's guard.
- **Codes.** The guard's codes are those of `checks.codes.ISSUE_CODES` (`verification-loop`, "Copper stage issue codes"). They are not build findings: they join the envelope's `issues` unchanged, as "Build issue codes" allows for codes that later requirements add, and `lens.build.BUILD_ISSUE_CODES` and `build_design` stay unchanged.
- **Result.** `result.copper_check` MUST hold `mode`, `ran`, `shorts`, `clearance` (counts of findings), `rules` (`{min_clearance, opaque_clearance_rules, unread}`) and `evidence` (`{level, oracle, hypotheses}` of `Evidence.combine(CopperReport.evidence, pcb.EVIDENCE, DesignRules.evidence)`). The `build` envelope's own evidence stays as "Build evidence" defines it.
- The option, the guard step of `cmd_build` and the `result` key are additions that "Build command" allows.
- Python callers of `build_design` are not guarded; `docs/dsl.md` MUST show the call of `check_copper` that gives them the same verdict.

#### Scenario: Blink passes the guard
- **GIVEN** an empty folder `B`
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --confirm --json` runs
- **THEN** the exit code is 0, `result.copper_check.ran` is true, and `result.copper_check.shorts` and `result.copper_check.clearance` are 0

#### Scenario: Short refused before writing
- **GIVEN** a confirmed blink build in `B` whose board got, by `tests/_coppercheck.py::bridge_pads(text, "R1", "2", "1")`, a segment on the net of `R1` pad 2 laid across `R1` pad 1
- **WHEN** the build runs again with `--confirm --json`
- **THEN** the exit code is 5, the issues hold one `copper.short` error whose `where` contains `R1-1`, and every file in `B` keeps its bytes

#### Scenario: Warn mode writes
- **GIVEN** the same edited build
- **WHEN** the build runs again with `--copper-check warn --confirm --json`
- **THEN** the exit code is 0, the files are written, and the issues hold the `copper.short` with severity `warning` and a message ending with `(copper guard in warn mode)`

#### Scenario: Unknown mode
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --copper-check off --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`
