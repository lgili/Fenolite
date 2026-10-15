## ADDED Requirements

### Requirement: Altium kinds in capabilities
`fenolite capabilities` SHALL list, for the backend `altium`, the kinds whose write graduated in `write_kinds`, and the others under `experimental` with, for each, the missing conditions that `graduated` returns.
- The list MUST be computed from the evidence matrix; no kind is named in the command's code.

#### Scenario: Computed from the matrix
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities_altium.py` compares `capabilities --json` with `graduated` for every Altium row
- **THEN** `write_kinds` holds exactly the graduated kinds, and each experimental kind lists what is missing

## MODIFIED Requirements

### Requirement: Experimental features in capabilities
`fenolite capabilities` SHALL fill `result.experimental` with one entry per experimental feature, sorted by `name`. Each entry MUST have the keys `name`, `command`, `option`, `write_kinds` and `evidence`; Altium entries additionally report the missing graduation conditions per kind, the last written as `{level, oracle, hypotheses}` like the `evidence` of `CapabilityReport.to_json()`.
- An experimental feature MAY change its output, its options or its issue codes in any release. Its envelopes MUST NOT carry a level that `fenolite.verify.release_verified` accepts (`verification-evidence`, "Release-verified levels").
- Listing the entries MUST NOT run an external tool, so `result.experimental` is the same with `--no-tools`. The module that defines an entry MUST be imported inside `cmd_capabilities._run`, not when `fenolite.cli.cmd_capabilities` is imported.
- An experimental feature MUST NOT appear in `result.backends` unless it is a registered `Backend` (`backend-protocol`, "Backend registry"). Since change c0043 the registered backend `altium` reads Altium files; it lists graduated write kinds, and the writers below list only their remaining experimental kinds.
- `docs/cli-contract.md` MUST describe `result.experimental` under "Discovery".
- The following entries are listed, in this order, when they have at least one experimental kind; their `write_kinds` exclude graduated kinds:
  - `name` `altium-pcb-writer`, `command` `build`, `option` `--target altium`, `write_kinds` `["altium_pcbdoc", "altium_pcblib"]` (`fenolite.lens.altium.PCB_WRITE_KINDS`), and the evidence of `fenolite.lens.altium.PCB_BUILD_EVIDENCE` (`altium-build`, "PCB evidence and capabilities");
  - `name` `altium-schematic-writer`, `command` `build`, `option` `--target altium`, `write_kinds` equal to `fenolite.backends.altium.project.WRITE_KINDS` (`["altium_prjpcb", "altium_schdoc_ascii", "altium_schdoc_binary", "altium_schlib"]`, c0033 and c0034), and the evidence of `fenolite.lens.altium.ALTIUM_BUILD_EVIDENCE` (`altium-build`, "Altium build evidence").
  - `name` `altium-support-writer`, `command` `build`, `option` `--target altium`, covering remaining matrix write kinds outside the PCB and schematic groups (currently OutJob and SchDot), with their combined write evidence.
- The entries MUST NOT share a write kind and MUST cover every experimental Altium matrix write, so each can be cut or promoted on its own.

#### Scenario: Altium writers listed as experimental
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** the exit code is 0, `result.experimental` holds entries named `altium-pcb-writer`, `altium-schematic-writer` and `altium-support-writer`, in that order, each with `command` `build`, `option` `--target altium` and `evidence.level` `INFERRED`, the first with `write_kinds` `["altium_pcbdoc", "altium_pcblib"]`, when no kind graduated, the entry of `result.backends` named `altium` has an empty `write_kinds`, and the envelope validates against `schemas/fenolite.envelope.v0.json`

#### Scenario: Same entry without tool detection
- **WHEN** `uv run fenolite capabilities --json` and `uv run fenolite capabilities --json --no-tools` run
- **THEN** both `result.experimental` values are equal

#### Scenario: Field projection
- **WHEN** `uv run fenolite capabilities --json --no-tools --fields experimental` runs
- **THEN** `result` contains only `experimental`, and the exit code is 0

#### Scenario: Experimental evidence is never release-verified
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities_experimental.py` parses the `evidence.level` of every entry with `fenolite.verify.parse_level`
- **THEN** `release_verified` of each level is `False`
