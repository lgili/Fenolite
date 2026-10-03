## ADDED Requirements

### Requirement: Experimental features in capabilities
`fenolite capabilities` SHALL fill `result.experimental` with one entry per experimental feature, sorted by `name`. Each entry MUST have exactly the keys `name`, `command`, `option`, `write_kinds` and `evidence`, the last written as `{level, oracle, hypotheses}` like the `evidence` of `CapabilityReport.to_json()`.
- An experimental feature MAY change its output, its options or its issue codes in any release. Its envelopes MUST NOT carry a level that `fenolite.verify.release_verified` accepts (`verification-evidence`, "Release-verified levels").
- Listing the entries MUST NOT run an external tool, so `result.experimental` is the same with `--no-tools`. The module that defines an entry MUST be imported inside `cmd_capabilities._run`, not when `fenolite.cli.cmd_capabilities` is imported.
- An experimental feature MUST NOT appear in `result.backends` unless it is a registered `Backend` (`backend-protocol`, "Backend registry").
- `docs/cli-contract.md` MUST describe `result.experimental` under "Discovery".
- This change lists one entry: `name` `altium-schematic-writer`, `command` `build`, `option` `--target altium`, `write_kinds` `["altium_prjpcb", "altium_schdoc_ascii"]`, and the evidence of `fenolite.lens.altium.ALTIUM_BUILD_EVIDENCE` (`altium-build`, "Altium build evidence").

#### Scenario: Altium writer listed as experimental
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** the exit code is 0, `result.experimental` holds one entry whose `name` is `altium-schematic-writer`, whose `command` is `build`, whose `option` is `--target altium` and whose `evidence.level` is `INFERRED`, no entry of `result.backends` is named `altium`, and the envelope validates against `schemas/fenolite.envelope.v0.json`

#### Scenario: Same entry without tool detection
- **WHEN** `uv run fenolite capabilities --json` and `uv run fenolite capabilities --json --no-tools` run
- **THEN** both `result.experimental` values are equal

#### Scenario: Field projection
- **WHEN** `uv run fenolite capabilities --json --no-tools --fields experimental` runs
- **THEN** `result` contains only `experimental`, and the exit code is 0

#### Scenario: Experimental evidence is never release-verified
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities_experimental.py` parses the `evidence.level` of every entry with `fenolite.verify.parse_level`
- **THEN** `release_verified` of each level is `False`
