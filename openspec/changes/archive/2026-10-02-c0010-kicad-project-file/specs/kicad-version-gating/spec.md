## ADDED Requirements

### Requirement: Project file versions
`fenolite.backends.kicad.pro` SHALL expose `PROJECT_VERSIONS = {9: (3, 4), 10: (3, 5)}`, the pairs (`meta.version`, `net_settings.meta.version`) that Fenolite writes for each target in `TARGET_MAJORS`, together with `classify_project(meta_version, net_settings_version)` and `project_major(meta_version, net_settings_version)`. The project file is JSON and MUST stay outside `FileKind`: `FileKind` keeps exactly its six values, `FORMAT_VERSIONS` is unchanged, and `kind_for_suffix` returns `None` for a `.kicad_pro` name.
- `classify_project` MUST return `FUTURE` when `meta.version` is greater than 3 or `net_settings.meta.version` is greater than 5, and `SUPPORTED` otherwise, absent versions included, because KiCad reads a `{}` project (`H-K-TOK-RULES-SILENT`).
- `project_major` MUST return the target whose pair equals the given pair, and `None` for any other pair.
- A `FUTURE` project MUST be readable, with the warning `kicad.version.future`, and MUST NOT be edited: `update_project` MUST raise `FutureFormatError` (`FEN-3002`).
- `update_project` MUST raise `UnsupportedFormatError` (`FEN-3003`) for a `SUPPORTED` project whose pair is not in `PROJECT_VERSIONS`, `{}` and versions 1 and 2 included, with a `hint` saying to re-save the project in KiCad 9 or 10 or to synthesise a new one.
- An update MUST keep the existing pair, except the lossy target-9 path of "Project files are gated by target" in `kicad-file-backend`.
- Every pair MUST cite its source in `docs/formats/kicad/project.md` and carry the evidence level it has reached (`H-K-PRO-VERSION`).

#### Scenario: Pairs per target
- **GIVEN** the packaged `pro` module
- **WHEN** `PROJECT_VERSIONS[9]` and `PROJECT_VERSIONS[10]` are read
- **THEN** they equal `(3, 4)` and `(3, 5)`

#### Scenario: Synthesised versions follow the target
- **GIVEN** any design
- **WHEN** it is synthesised with `board_name="b"` for target 9 and for target 10
- **THEN** the target-9 text has `meta.version` 3 and `net_settings.meta.version` 4, and the target-10 text has 3 and 5

#### Scenario: Future project is read-only
- **GIVEN** a project text with `"meta": {"version": 4}`
- **WHEN** `read_project(text)` and then `update_project(text, design, target=10)` are called
- **THEN** the status is `FUTURE`, the issues hold `kicad.version.future`, and the update raises `FutureFormatError` with `cli_code == "FEN-3002"`

#### Scenario: Older project readable, not editable
- **GIVEN** a project text with `meta.version` 2
- **WHEN** it is read and then updated for target 10
- **THEN** the read succeeds with status `SUPPORTED` and `major is None`, and the update raises `UnsupportedFormatError` whose `hint` names KiCad 9 or 10

#### Scenario: Project stays outside FileKind
- **WHEN** `kind_for_suffix("bench.kicad_pro")` is called and the members of `FileKind` are listed
- **THEN** the call returns `None` and `FileKind` has exactly the six members `kicad_pcb`, `kicad_mod`, `kicad_sch`, `kicad_sym`, `kicad_wks` and `kicad_dru`
