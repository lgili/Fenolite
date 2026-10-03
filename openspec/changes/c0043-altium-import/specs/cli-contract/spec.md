## MODIFIED Requirements

### Requirement: Backends in capabilities
`fenolite capabilities` SHALL fill `result.backends` with `CapabilityReport.to_json()` of every backend in `fenolite.backends.registry.all_backends()`, sorted by name. Each entry MUST have the keys `name`, `read_kinds`, `write_kinds`, `targets`, `default_target`, `downgrade`, `operations` and `evidence`.
- Listing backends MUST NOT run any external tool, so the entry is the same with `--no-tools`.
- The `kicad-cli` entry of `result.tools` MUST take its path from `fenolite.backends.kicad.cli.find_kicad_cli()`. Its version detection MUST stay as before, so the same machine reports the same path and version.
- `docs/cli-contract.md` MUST describe the backend entry under "Discovery".
- Two backends are listed: `altium` (change c0043), then `kicad`. A consumer MUST find a backend by its `name`, not by its position.

#### Scenario: KiCad backend listed
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** the entry of `result.backends` named `kicad` has `read_kinds` that contain `kicad_pcb`, `kicad_mod` and `kicad_sym`, its `operations` contain `detect` and `read`, and contain `write` only when its `write_kinds` is not empty, and the envelope validates against `schemas/fenolite.envelope.v0.json`

#### Scenario: Altium backend listed
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** `result.backends` holds two entries named `altium` and `kicad`, in that order; the `altium` entry has `read_kinds` `["altium_pcbdoc", "altium_pcblib", "altium_prjpcb", "altium_schdoc_ascii", "altium_schdoc_binary", "altium_schlib"]`, `write_kinds` `[]`, `targets` `[]`, `default_target` `null`, `operations` `["detect", "read"]` and `evidence.level` `INFERRED`

#### Scenario: Backend field projection
- **WHEN** `uv run fenolite capabilities --json --no-tools --fields backends` runs
- **THEN** `result` contains only `backends`, and the exit code is 0

#### Scenario: Same kicad-cli as before
- **GIVEN** `FENOLITE_KICAD_CLI` naming a fake `kicad-cli` script whose `version` prints `10.0.6`
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities_backends.py -k tool_path` runs `capabilities`
- **THEN** `result.tools.kicad-cli.path` is that script and `result.tools.kicad-cli.version` is `10.0.6`

### Requirement: Experimental features in capabilities
`fenolite capabilities` SHALL fill `result.experimental` with one entry per experimental feature, sorted by `name`. Each entry MUST have exactly the keys `name`, `command`, `option`, `write_kinds` and `evidence`, the last written as `{level, oracle, hypotheses}` like the `evidence` of `CapabilityReport.to_json()`.
- An experimental feature MAY change its output, its options or its issue codes in any release. Its envelopes MUST NOT carry a level that `fenolite.verify.release_verified` accepts (`verification-evidence`, "Release-verified levels").
- Listing the entries MUST NOT run an external tool, so `result.experimental` is the same with `--no-tools`. The module that defines an entry MUST be imported inside `cmd_capabilities._run`, not when `fenolite.cli.cmd_capabilities` is imported.
- An experimental feature MUST NOT appear in `result.backends` unless it is a registered `Backend` (`backend-protocol`, "Backend registry"). Since change c0043 the registered backend `altium` reads Altium files; it lists no write kind, so the two writers below stay experimental features and are not part of its report.
- `docs/cli-contract.md` MUST describe `result.experimental` under "Discovery".
- Two entries are listed, in this order:
  - `name` `altium-pcb-writer`, `command` `build`, `option` `--target altium`, `write_kinds` `["altium_pcbdoc", "altium_pcblib"]` (`fenolite.lens.altium.PCB_WRITE_KINDS`), and the evidence of `fenolite.lens.altium.PCB_BUILD_EVIDENCE` (`altium-build`, "PCB evidence and capabilities");
  - `name` `altium-schematic-writer`, `command` `build`, `option` `--target altium`, `write_kinds` equal to `fenolite.backends.altium.project.WRITE_KINDS` (`["altium_prjpcb", "altium_schdoc_ascii", "altium_schdoc_binary", "altium_schlib"]`, c0033 and c0034), and the evidence of `fenolite.lens.altium.ALTIUM_BUILD_EVIDENCE` (`altium-build`, "Altium build evidence").
- The two entries MUST NOT share a write kind, so each can be cut or promoted on its own.

#### Scenario: Altium writers listed as experimental
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** the exit code is 0, `result.experimental` holds two entries named `altium-pcb-writer` and `altium-schematic-writer`, in that order, each with `command` `build`, `option` `--target altium` and `evidence.level` `INFERRED`, the first with `write_kinds` `["altium_pcbdoc", "altium_pcblib"]`, the entry of `result.backends` named `altium` has an empty `write_kinds`, and the envelope validates against `schemas/fenolite.envelope.v0.json`

#### Scenario: Same entry without tool detection
- **WHEN** `uv run fenolite capabilities --json` and `uv run fenolite capabilities --json --no-tools` run
- **THEN** both `result.experimental` values are equal

#### Scenario: Field projection
- **WHEN** `uv run fenolite capabilities --json --no-tools --fields experimental` runs
- **THEN** `result` contains only `experimental`, and the exit code is 0

#### Scenario: Experimental evidence is never release-verified
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities_experimental.py` parses the `evidence.level` of every entry with `fenolite.verify.parse_level`
- **THEN** `release_verified` of each level is `False`
