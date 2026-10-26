## ADDED Requirements

### Requirement: Component bodies in an Altium build
`fenolite build --target altium` SHALL accept `--altium-bodies off|extruded` (default `off`), and with `extruded` SHALL write the component bodies of the board's footprints as `altium-pcb-writer` requires ("Component bodies are reported", "Extruded component body records", "Component bodies of a library footprint").
- `lens.altium.build_altium`, `lens.altium.write_model`, `lower.from_design`, `lower.write_design` and `AltiumBackend.write` MUST take the same choice as `bodies="off" | "extruded"`. Another value MUST exit 2 on the command line and raise `ValueError` in the library.
- The option MUST be refused with exit 2 and `FEN-2001` for another target, as the other `--altium-…` options are.
- The result of the command MUST hold `pcb` (the accounting that change c0085 specified and that only the library's build summary held until this change: `null` without a PCB document), after `copper`, and `result.pcb` MUST hold `bodies` (the value used) after its other keys; `result.pcb.written.body` MUST count the bodies written and `result.pcb.not_lowered.body` the bodies not written, and their sum MUST be the number of bodies of the board's footprints.
- With `off`, every file of the build MUST equal the file built before this change, byte for byte, and each body is reported as before with the option named in the message. With `extruded`, a design whose footprints hold no body MUST also give those bytes.
- Every issue of a body MUST be `altium.not-lowered` (info) with `where` `body/<id>`; this change adds no issue code. `docs/cli-contract.md` MUST list the option and `result.pcb.bodies`, and `docs/altium.md` MUST say what is written of a body, what is not, that the option is off by default and why (`H-A-PCBX-BODY-OPEN` is not settled).
- The bodies written are those of the model: a build MUST NOT add a body to a footprint that has none.

#### Scenario: Without the option
- **WHEN** `uv run pytest tests/unit/lens -k "altium and samples"` builds the committed samples of earlier changes, `board6` among them, without the option
- **THEN** every file equals the committed one, and `result.pcb.bodies` is `off`

#### Scenario: Sample with bodies
- **WHEN** `uv run pytest tests/unit/lens/test_altium_bodies.py -k body2` builds the sample with `--altium-bodies extruded`
- **THEN** every built file equals the committed file under `tests/data/altium/body2/`, `result.pcb.written.body` is 3, `result.pcb.not_lowered.body` is 1, and the one `altium.not-lowered` of a body names the body of kind `model`

#### Scenario: Refused for another target
- **WHEN** `fenolite build examples/blink_2layer/design.py --target kicad --altium-bodies extruded --dry-run --json` runs
- **THEN** the exit code is 2 and the error code is `FEN-2001`
