## ADDED Requirements

### Requirement: Copper guard in an Altium build
`fenolite build --target altium` SHALL judge the copper of the PCB document it is about to write with `fenolite.checks.copper.check_copper`, in `cmd_build.altium_copper_guard`, after `lens.altium.build_altium` returns its files and before `cmd_build` calls `check_existing` and returns its plan, on `--dry-run` and `--confirm` alike. The guard lives in `cli` because `lens` may not import `checks` (`package-layering`).
- **What is judged.** The planned bytes of `<name>.PcbDoc` MUST be read back with the Altium reader and adapter (`AltiumBackend.board_from_bytes`), the rules MUST be those of that document (`AltiumBackend.rules_from_bytes`, "Clearance rules of a PCB document" of `altium-verification`), and the pads MUST come from the Altium board frame. The guard MUST read and write no file. A build that plans no PCB document, or that was refused, MUST NOT be judged (`ran` false).
- **Modes.** The option is `--copper-check refuse|warn` of the KiCad target (`design-dsl`, "Copper guard before writing"), default `refuse`. With `refuse` a `copper.short` MUST keep its severity, so the build returns no planned write and exits 5. Every other copper issue of severity `error` MUST be reported with severity `warning` and ` (reported, not refused: the Altium copper guard refuses shorts)` appended to its message, and MUST NOT stop the build. With `warn` the short MUST be a warning too, with ` (copper guard in warn mode)` appended, and the build MUST plan its writes. There is no way to switch the guard off.
- **Result.** `result.copper_check` MUST hold `mode`, `ran`, `shorts`, `clearance`, `unpoured` (the zones without a fill), `rules` and `evidence`, and MUST stand after `copper` in the result. The evidence MUST be `UNVERIFIED` when `unpoured` is not 0 or an issue lowers it.

#### Scenario: Short refused
- **GIVEN** the routed blink whose script holds one more track of `LED_A` that crosses the track of `LED_DRV` on `F.Cu`
- **WHEN** it is built for Altium with `--confirm`
- **THEN** the exit code is 5, `copper.short` names the two nets, and the output folder holds no file

#### Scenario: Warn mode and clearance findings write
- **WHEN** `uv run pytest tests/unit/cli/test_build_altium_guard.py` builds that script with `--copper-check warn`, and a script whose extra track ends 0.15 mm from another net's track
- **THEN** both builds exit 0 and write the PCB document, the short is a warning that ends with `(copper guard in warn mode)`, and the clearance finding is a warning
