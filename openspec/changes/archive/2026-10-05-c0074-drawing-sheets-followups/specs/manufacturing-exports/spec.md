## ADDED Requirements

### Requirement: Export presets
`fenolite.exports.preset` SHALL read an export preset, a TOML file of the user's, and SHALL turn it into the arguments of each export kind, with `PRESET_SCHEMA = "fenolite.export-preset.v0"`, `read_preset(text, *, file="") -> Preset` and `arguments(kind, preset, *, stem, layers) -> tuple[str, ...]`.
- The text MUST be read with `tomllib`; a text that is not TOML, a `schema` other than `PRESET_SCHEMA`, a table other than `gerbers`, `drill` and `pos`, a key outside the table of Decision 4 of the design, or a value outside its allowed values MUST raise `FormatError` (`FEN-3004`) naming the file and the `table.key`.
- `arguments` MUST give, for each kind, c0024's arguments ("Export kinds and their arguments") with each given key replaced by its flag: the options c0024 gives keep their places, and the others follow in the order of Decision 4; a key not given MUST keep c0024's value. A key of the Excellon format given with `format = "gerber"`, and `gerber_precision` without it, MUST raise `FormatError` too. `arguments(kind, None, …)` MUST equal c0024's arguments exactly.
- Every flag a preset can give MUST be present on both majors in the probe rows `help-pcb-export-<kind>-<option>` (`H-K-EXPORT-OPTIONS`); `--check-zones`, `--board-plot-params`, `--variant` and `--generate-tenting` MUST NOT be given.
- With `pos.format`, the placement file MUST be `pos/<stem>-pos.csv`, `.pos` or `.gbr` for `csv`, `ascii` and `gerber`.
- Fenolite MUST NOT ship a preset.

#### Scenario: Protel extensions and inches
- **GIVEN** a preset with `[gerbers]` `protel_extensions = true` and `[drill]` `units = "in"`
- **WHEN** `arguments` runs for `gerbers` and for `drill`
- **THEN** the Gerber arguments hold no `--no-protel-ext`, and the drill arguments hold `--excellon-units in` with every other value of c0024

#### Scenario: Unknown key
- **GIVEN** a preset with `[drill]` `speed = 3`
- **WHEN** it is read with `file="fab.toml"`
- **THEN** `FormatError` is raised naming `fab.toml` and `drill.speed`

#### Scenario: Defaults equal no preset
- **GIVEN** a preset that gives every key its default value
- **WHEN** `arguments` runs for every kind
- **THEN** each list equals `arguments(kind, None, …)`
