## ADDED Requirements

### Requirement: Export runs through the package runner
`KicadCli.export(args, board, *, files=None, out) -> CliRun` and `KicadCli.render(board, *, side, width, height, files=None) -> CliRun` SHALL run `kicad-cli` through `KicadCli.run`: inputs copied to a fresh temporary directory, the isolated environment, and the created files returned in `CliRun.outputs`.
- `export` MUST create the folder `out` inside the run directory before the run, because `kicad-cli` does not create a missing output folder for every kind.
- Neither method MUST raise for a non-zero exit; the caller reads `returncode`.
- `KicadOracle.plot(project) -> PlotOutcome` MUST run the views of "Render views" on the project's copy set and return, per view, its name, size and SHA-256; a view that fails MUST be absent from `views` and named in `message`.
- `backends.base` MUST gain `PlotView`, `PlotOutcome` and the protocol `Plotter`, all frozen dataclasses or protocols without a dependency on `backends.kicad`.

#### Scenario: Output folder exists for the run
- **GIVEN** a fake `kicad-cli` that fails when its `-o` folder is missing
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_cli_export.py` calls `KicadCli.export([...], board, out="gerbers")`
- **THEN** the run exits 0 and `outputs` holds the fake's files under `gerbers/`

#### Scenario: Non-zero exit is returned
- **GIVEN** a fake `kicad-cli` that exits 1 for `pcb render`
- **WHEN** `KicadCli.render(board, side="top", width=400, height=300)` runs
- **THEN** no exception is raised and `returncode` is 1

#### Scenario: Plot outcome holds no bytes
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py -k plot` calls `KicadOracle.plot` with a fake
- **THEN** each view holds `name`, `bytes` (a count) and `sha256`, and the outcome holds no temporary path

### Requirement: Exports are probed on both majors
`H-K-EXPORT-FILES`, `H-K-EXPORT-REPEAT` and `H-K-EXPORT-RENDER` SHALL be settled on `kicad-cli` 9.0.9 and 10.0.6 by `tests/kicad/export/test_export_probes.py` before `exports.plan` relies on them, as the probes `export-files-<kind>`, `export-repeat-<kind>` (for `gerbers`, `drill`, `pos`, `ipcd356`), `export-render-png` and `export-render-svg`.
- `test_files` MUST compare the produced file names with the expected set for `two_layer.kicad_pcb` and for the authored project.
- `test_repeat` MUST export twice and compare `content_sha256` per file; it MUST also record, per kind, whether the two runs were byte-equal, in `docs/evidence/kicad-export.md`.
- `test_render` MUST read the PNG header and compare its width and height with the request.
- A line that differs between two runs and matches no prefix in `VOLATILE_PREFIXES` MUST fail `test_repeat` and name the line's first 40 bytes.
- `tests/kicad/export/test_export_oracle.py::test_blink_loop` MUST run `fenolite export --all --manifest --confirm` and `fenolite render --svg --png --confirm` on the built blink on both majors and check the manifest against the written files.

#### Scenario: File sets
- **WHEN** `uv run pytest tests/kicad/export/test_export_probes.py::test_files` runs on 9.0.9 and on 10.0.6
- **THEN** the four `export-files-*` probes record `equal` on both

#### Scenario: Content hashes repeat
- **WHEN** `uv run pytest tests/kicad/export/test_export_probes.py::test_repeat` runs on both majors
- **THEN** the four `export-repeat-*` probes record `equal`

#### Scenario: Headless render
- **WHEN** `uv run pytest tests/kicad/export/test_export_probes.py::test_render` runs on 10.0.6 and inside the pinned 9.0.9 image
- **THEN** `export-render-svg` records `present` on both, and `export-render-png` records `present` or `absent` per major with the tool's message

#### Scenario: Blink exports on both majors
- **WHEN** `uv run pytest tests/kicad/export/test_export_oracle.py::test_blink_loop` runs on both majors
- **THEN** the manifest lists every written artefact with its hash, and the built project folder is unchanged
