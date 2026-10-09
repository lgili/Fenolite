## MODIFIED Requirements

### Requirement: Component bodies in an Altium build
`fenolite build --target altium` SHALL accept `--altium-bodies off|extruded` (default `extruded`, since change c0155), and with `extruded` SHALL write the component bodies of the board's footprints as `altium-pcb-writer` requires ("Component bodies are reported", "Extruded component body records", "Component bodies of a library footprint").
- `lens.altium.build_altium`, `lens.altium.write_model`, `lower.from_design`, `lower.write_design` and `AltiumBackend.write` MUST take the same choice as `bodies="off" | "extruded"`. Another value MUST exit 2 on the command line and raise `ValueError` in the library. The default of `lens.altium.build_altium` MUST be `extruded`, as the command's; `lens.altium.write_model`, `lower.from_design`, `lower.write_design`, `AltiumBackend.write` and `AltiumBackend.model_roundtrip` MUST keep `off` as their default (the rewrite of a read document and the round trips).
- The option MUST be refused with exit 2 and `FEN-2001` for another target, as the other `--altium-…` options are.
- The result of the command MUST hold `pcb` (the accounting that change c0085 specified and that only the library's build summary held until change c0121: `null` without a PCB document), after `copper`, and `result.pcb` MUST hold `bodies` (the value used) after its other keys; `result.pcb.written.body` MUST count the bodies written and `result.pcb.not_lowered.body` the bodies not written, and their sum MUST be the number of bodies of the board's footprints.
- With `off`, every file of the build MUST equal the file built before change c0121, byte for byte, and each body is reported with the option named in the message. With `extruded`, the default, a design whose footprints hold no extruded body with an outline MUST also give those bytes.
- Every issue of a body MUST be `altium.not-lowered` (info) with `where` `body/<id>`; no issue code is added. `docs/cli-contract.md` MUST list the option, its default and `result.pcb.bodies`, and `docs/altium.md` MUST say what is written of a body, what is not, that the option is on by default since the maintainer's decision of 2026-10-09, on the author report of step X8 (`H-A-PCBX-BODY-OPEN`), and that `off` gives the earlier files.
- The bodies written are those of the model: a build MUST NOT add a body to a footprint that has none.

#### Scenario: Without the option
- **WHEN** `uv run pytest tests/unit/lens -k "altium and samples"` builds the committed samples of earlier changes, `board6` among them, without the option
- **THEN** every file equals the committed one (their footprints hold no extruded body with an outline), and `result.pcb.bodies` is `extruded`

#### Scenario: Off on the command line
- **GIVEN** the script `examples/blink_2layer/design.py`, whose footprints hold no body
- **WHEN** `uv run pytest tests/unit/cli/test_build_altium.py -k bodies_option` builds it for Altium without the option, with `--altium-bodies off` and with `--altium-bodies extruded`
- **THEN** `result.pcb.bodies` is `extruded` without the option and the value given otherwise, no body is counted, and the three builds give the same five files

#### Scenario: Sample with bodies
- **WHEN** `uv run pytest tests/unit/lens/test_altium_bodies.py -k body2` builds the sample without the option and with `--altium-bodies extruded`
- **THEN** every built file equals the committed file under `tests/data/altium/body2/`, `result.pcb.written.body` is 3, `result.pcb.not_lowered.body` is 1, and the one `altium.not-lowered` of a body names the body of kind `model`

#### Scenario: Refused for another target
- **WHEN** `fenolite build examples/blink_2layer/design.py --target kicad --altium-bodies extruded --dry-run --json` runs
- **THEN** the exit code is 2 and the error code is `FEN-2001`
