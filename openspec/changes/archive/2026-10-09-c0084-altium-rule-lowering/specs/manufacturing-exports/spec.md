## ADDED Requirements

### Requirement: Altium rule file export
`fenolite export` SHALL offer the kind `altium-rul` with the flag `--altium-rul`, which writes `<stem>.RUL` from the rules of the project with no external tool: `exports.altium_rul.export_rules` lowers the rules of `<stem>.kicad_dru` beside the board with `rulemap.lower` and writes them with `rulemap.write_rule_file`.
- The kind MUST NOT be part of `--all`. Selected alone it MUST need no `kicad-cli`.
- `result.rules` MUST name the rules written (`kind`, `selector`, `rule`) and the rules that were not lowered (`kind`, `selector`, `reason`). An artefact entry has no field for notes, so the result holds them.
- When the rules file cannot be read, or no rule of it has an exact Altium form, the export MUST report `export.failed` with `where` `altium-rul` and plan no file.
- The artefact's kind MUST be `altium-rul`; its manifest entry MUST name `fenolite <version>` as its tool and the level of `rulemap.EVIDENCE`, and the envelope's evidence MUST include that evidence.
- The export MUST follow "Writing files" of the CLI contract (dry run, confirm, receipt).

#### Scenario: Rule file from a built project
- **GIVEN** a KiCad project built from a script
- **WHEN** `fenolite export <dir> --out fab --altium-rul --confirm --json` runs with no `kicad-cli` on the machine
- **THEN** the receipt lists `fab/<stem>.RUL`, and reading it gives the rules that the Altium build of the same script writes into its PCB document under `result.rules.written`, with the same names and priorities

#### Scenario: No rule that can be written
- **GIVEN** a project whose only rule selects a net glob
- **WHEN** the same command runs
- **THEN** the exit code is 5, one `export.failed` has `where` `altium-rul`, `result.rules.not_lowered` holds the rule with `scope-unsupported`, and nothing is written
