## MODIFIED Requirements

### Requirement: Artefact states
Every manifest entry SHALL carry one `state` of `manifest.STATES = ("generated", "checked", "roundtrip-ok", "oracle-verified", "native-verified")`, in rising order, and `fenolite.exports.states.assign(entries, *, stages, sheets_ok, current) -> tuple[ArtifactEntry, ...]` SHALL assign it: the highest rung a file reaches together with every lower rung that applies to its kind, with `held` saying what the next rung is missing (`<state>: <reason>`, or `""` when no higher rung applies). `stages` maps a stage name to its status and evidence level, `sheets_ok` a sheet path to its RT1 verdict, and `current` a path to the file's present SHA-256.
- **Current.** An entry is current when `current[path]` equals its `sha256` and every hash of its `from` equals the present hash of that source. A derived entry that is not current MUST be `generated` with `stale` true. A design entry whose file has another hash MUST be `generated`; `stale` is only ever true for a derived entry.
- **`generated`.** Every entry reaches it.
- **`checked`.** `model.validate` and `copper.clearance` are in `stages` with status `ok`. A derived entry (kinds `gerbers`, `drill`, `pos`, `ipcd356`, `bom`, `pnp`, `testpoints`, `render`) reaches it when it is current and the sources its `from` names (`board`: the entry of kind `kicad_pcb`; `schematic`: an entry of kind `kicad_sch`) are `checked`, and reaches no higher rung. A derived entry whose `from` is empty or names another source MUST stay `generated`: nothing says what it was made from.
- **`roundtrip-ok`.** Applies to kinds `kicad_pcb` and `kicad_sch` only: the board needs `roundtrip` with status `ok`, and a sheet needs `sheets_ok[path]` true. Every other design kind skips the rung.
- **`oracle-verified`.** No rule assigns it; every kind skips the rung. The state is reserved for a tool that is neither the producer of a file nor its format's own application.
- **`native-verified`.** The board needs `drc.kicad` with status `ok` and level exactly `KICAD-VERIFIED`. The files KiCad loads to judge the board (kinds `kicad_pro`, `kicad_dru`, `kicad_mod`, `kicad_wks`, and a `lib-table` other than `sym-lib-table`) reach it exactly when the board does. A file of kind `file` (any other file of a library folder) stops at `checked`: no tool is known to load it.
- **Schematic side.** A sheet (`kicad_sch`), a symbol library (`kicad_sym`) and the `lib-table` named `sym-lib-table` are judged by KiCad's ERC, not by its DRC. Each reaches `native-verified` when `erc.kicad` (change c0062) is in `stages` with status `ok` and level exactly `KICAD-VERIFIED`: the ERC loaded the sheets with the libraries the table names. A sheet needs `roundtrip-ok` first; a symbol library and the symbol table skip that rung. Without that stage, or with an ERC error, a sheet stops at `roundtrip-ok` and a symbol library and the symbol table at `checked`, and `held` names `erc.kicad`. `states.PENDING` MUST be empty: no role waits for a stage that `check` lacks.
- A stage that is missing from `stages`, skipped, or below the level its rule names MUST NOT give its rung, and a rung that is not reached MUST stop the ladder for that file.
- `assign` MUST be pure, MUST import nothing from `checks`, and with an empty `stages` MUST leave every entry `generated`.

#### Scenario: Board up the ladder
- **GIVEN** a board entry that is current, and `stages` with `model.validate`, `copper.clearance` and `roundtrip` `ok` and `drc.kicad` `ok` at `KICAD-VERIFIED`
- **WHEN** `uv run pytest tests/unit/exports/test_states.py -k ladder` calls `assign`
- **THEN** the board's state is `native-verified`

#### Scenario: A failed rung stops the ladder
- **GIVEN** the same stages with `roundtrip` `errors`
- **WHEN** `assign` runs
- **THEN** the board's state is `checked`, although `drc.kicad` is `ok`

#### Scenario: DRC below KICAD-VERIFIED
- **GIVEN** the stages of the first scenario with `drc.kicad` `ok` at `UNVERIFIED`
- **WHEN** `assign` runs
- **THEN** the board's state is `roundtrip-ok`

#### Scenario: Derived file of a checked board
- **GIVEN** a Gerber entry whose `from` holds the board's present hash, and a board that reaches `native-verified`
- **WHEN** `assign` runs
- **THEN** the Gerber's state is `checked`

#### Scenario: Stale artefact
- **GIVEN** a Gerber entry whose `from` holds another hash than the board's present one
- **WHEN** `assign` runs
- **THEN** its state is `generated` and `stale` is true

#### Scenario: Schematic follows the ERC
- **GIVEN** the stages of the first scenario, with and without an `erc.kicad` entry that is `ok` at `KICAD-VERIFIED`, and a sheet whose RT1 verdict is true
- **WHEN** `uv run pytest tests/unit/exports/test_states.py -k erc` calls `assign`
- **THEN** with the entry the sheet, the symbol library and `sym-lib-table` are `native-verified` with an empty `held`; without it, with status `errors`, or at another level, the sheet is `roundtrip-ok`, the other two are `checked`, and each `held` names `erc.kicad`

#### Scenario: No check, no claim
- **WHEN** `assign` runs with `stages` empty
- **THEN** every entry is `generated`, and none is `oracle-verified` under any input of the test's generator

#### Scenario: The test-point table follows its board
- **GIVEN** a `testpoints` entry whose `from` holds the board's present hash, and a board that is `checked`
- **WHEN** `uv run pytest tests/unit/exports/test_states.py -k testpoints` calls `assign`, and again after the board's hash changed
- **THEN** the entry is `checked` the first time, and `generated` and stale the second
