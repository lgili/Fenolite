## ADDED Requirements

### Requirement: Via protection in inspect
`fenolite inspect` SHALL report the via protection of a board it reads, a KiCad board or an Altium PCB document, as an addition to the `result` of "Inspect command", through `fenolite.backends.kicad.via_protection.summary(design)` for a KiCad board and the same counts over the imported model for an Altium PCB document.
- For a KiCad board, `result.via_protection` MUST hold `default`, `effective` and `by_default`. `default` holds the eight fields of `effective_default(Board.via_protection)` as booleans, and `source`: `board` when `Board.via_protection` is set, `kicad` otherwise. `effective` holds, per field, the number of vias whose effective value (`effective(via.protection, Board.via_protection)`) is `True`. `by_default` holds, per field, how many of those take it from the default, their own value being `None`. Footprint files and symbol libraries MUST NOT carry the key.
- For an Altium PCB document (kind `altium_pcbdoc`), `result.via_protection` MUST hold the same three keys: `default` with `source` `altium` and the eight fields `false` (an Altium via carries its own tenting flags, so no default applies); `effective` with, for `tenting_front` and `tenting_back`, the number of vias whose flag is set (`altium-import`, "Via tenting of imported vias"), and 0 for the six other fields; `by_default` with 0 for every field. The envelope's evidence is that of the reading, `INFERRED` for these two fields. Altium libraries and schematic documents MUST NOT carry the key.
- The view MUST run no external tool, so "Inspect is hermetic" still holds.
- `docs/cli-contract.md` MUST describe the key under `inspect`, and say that on 10.0.6 a covering, plugging, capping or filling counted in `by_default` reaches no fabrication file.

#### Scenario: Authored board
- **WHEN** `uv run fenolite inspect tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** the exit code is 0, `result.via_protection.default` has `source` `kicad`, both tenting fields `true` and the six others `false`, and `effective` and `by_default` hold 1 for both tenting fields and 0 for the six others, the board having one via without protection children

#### Scenario: Altium PCB document
- **GIVEN** a PCB document written with four through vias whose flags are `0C`, `2C`, `4C` and `6C`
- **WHEN** `uv run pytest tests/unit/cli/test_inspect_cmd.py -k altium_via_protection` runs `inspect` on it
- **THEN** `result.via_protection.default.source` is `altium`, `effective.tenting_front` and `effective.tenting_back` are both 2, the six other fields are 0, and every field of `by_default` is 0

#### Scenario: Board with protected vias
- **GIVEN** a copy of the authored board whose `setup` holds `(tenting none)` and whose via holds `(tenting front)`
- **WHEN** `uv run pytest tests/unit/cli/test_inspect_cmd.py -k via_protection` runs `inspect` on it
- **THEN** `result.via_protection.default` has `source` `board` and both tenting fields `false`, `effective.tenting_front` is 1, `effective.tenting_back` is 0, and `by_default.tenting_front` is 0
