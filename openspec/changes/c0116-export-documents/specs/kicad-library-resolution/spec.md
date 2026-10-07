## ADDED Requirements

### Requirement: 3D model location
`LibraryResolver.locate_model(path) -> ModelLocation | None` SHALL find the file that a footprint's 3D model path names, from the sources below in this order, and SHALL return the first regular file found as `ModelLocation(path, rel, file, source)`, or `None` when no source holds one. It MUST NOT raise and MUST NOT download anything.
- **`${KICAD<N>_3DMODEL_DIR}/<rel>`**, for any N, with `rel` the part after the variable:
  - `project`: `<project_dir>/3dmodels/<rel>`, the folder that `fenolite models --vendor` writes;
  - `env`: the value of `KICAD<N>_3DMODEL_DIR` in `LibraryConfig.env`, joined with `<rel>`;
  - `kicad-config`: the same variable in KiCad's `kicad_common.json` of major N, read only with `read_common`;
  - `install`: the `3dmodels` folder of the install that `install_dir` or the per-OS default gives, whatever its major, because `kicad-cli` 10.0.6 reads `KICAD9_` and `KICAD10_` paths there (`H-K-EXPORT-MODELS`);
  - `cache`: `<cache>/<tag>/kicad-packages3D/<rel>`, `<tag>` being the tag of the model pin of major N ("3D model pins"), when the file's SHA-256 equals its entry in that folder's model stamp ("3D model fetch").
- **`${KIPRJMOD}/<rel>`**: `<project_dir>/<rel>`, source `project`, when it lies inside the project folder.
- **Any other form** (an absolute path, another variable that `expand` resolves): that file, source `in-place`, `rel` `None`.
- "Library sources" is unchanged: `locate_model` defines no path variable.

#### Scenario: The vendored copy wins
- **GIVEN** a project folder holding `3dmodels/Fenolite.3dshapes/Box_2x1.step`, and `env` setting `KICAD10_3DMODEL_DIR` to `tests/data/models`, which holds the same path
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_locate_model.py -k vendored` locates `${KICAD10_3DMODEL_DIR}/Fenolite.3dshapes/Box_2x1.step`
- **THEN** the source is `project` and the file is the project's copy

#### Scenario: The environment before the install
- **GIVEN** no project copy, `env` setting `KICAD9_3DMODEL_DIR` to `tests/data/models`, and a fake install from `tests/_libs.make_install` whose `3dmodels` folder holds the same path
- **WHEN** `${KICAD9_3DMODEL_DIR}/Fenolite.3dshapes/Box_2x1.step` is located, and then again with an empty `env`
- **THEN** the first source is `env` and the second `install`

#### Scenario: A stale cache entry is not used
- **GIVEN** a cache whose `10.0.6/kicad-packages3D` holds the file and a stamp entry with another SHA-256, and no other source
- **WHEN** the path is located with major 10
- **THEN** the result is `None`, and with the stamp entry corrected the source is `cache`

#### Scenario: Not found
- **GIVEN** no source holding the file, and no value for `KICAD10_3DMODEL_DIR`
- **WHEN** the path is located
- **THEN** the result is `None` and no exception is raised

### Requirement: 3D model pins
`src/fenolite/backends/kicad/data/libraries.toml` SHALL hold one `[[models]]` table per tag of its `[[pin]]` tables, and `fenolite.backends.kicad.libcache.load_model_pins(path=None)` SHALL return them as `ModelPin(tag, major, project, commit)` values, in file order.
- `project` MUST be `kicad/libraries/kicad-packages3D` and `commit` the 40 lowercase hex digits that the tags API gives for the tag (S-0700). There MUST be exactly one model pin per tag, and its major MUST be that of the tag's `[[pin]]` tables.
- No tree hash and no file count are pinned: the models are fetched one file at a time ("3D model fetch").
- A table that breaks these rules MUST raise `ValueError` naming the file and the key. `load_pins` MUST ignore the `[[models]]` tables and return what it returned before.

#### Scenario: Model pins of both tags
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_libcache_models.py -k pins` calls `load_model_pins()`
- **THEN** it returns two pins, `10.0.6` with major 10 and `9.0.9` with major 9, each naming `kicad/libraries/kicad-packages3D` with a 40-hex commit, and `load_pins()` still returns four pins

#### Scenario: Malformed model pin
- **GIVEN** a pins file whose `[[models]]` table has a 39-hex commit
- **WHEN** `load_model_pins(path)` is called
- **THEN** `ValueError` is raised naming the file and `commit`

### Requirement: 3D model fetch
`tools/kicad_libs_fetch.py --models PATH [PATH ...]` SHALL fetch, one file at a time, the official 3D models that the boards or footprint files `PATH` name as `${KICAD<N>_3DMODEL_DIR}/<rel>`, into `<cache>/<tag>/kicad-packages3D/<rel>` for the model pin of major N, and SHALL record each file in that folder's stamp `.fenolite-models.json`, a JSON object mapping `<rel>` to the file's SHA-256. `<cache>` is chosen as for the library fetch.
- A file whose stamp entry equals its SHA-256 MUST be reported `cached` and MUST NOT be requested.
- Otherwise the tool MUST ask the files API for the file's size and SHA-256 at the pinned commit (`HEAD https://gitlab.com/api/v4/projects/<project>/repository/files/<rel>?ref=<commit>`, headers `X-Gitlab-Size` and `X-Gitlab-Content-Sha256`; S-0024, S-0701), refuse a size above `MAX_MODEL_BYTES` (64 MiB) with exit 3, download the raw file of that commit into a temporary file under `<cache>/<tag>/`, and compare its size and SHA-256 with the headers. On equality it MUST move the file into place with `os.replace` and add its stamp entry; on a difference it MUST exit 5. A failed file MUST leave its target and the stamp as they were and remove the temporary file.
- A path whose N has no model pin, or that names no `${KICAD<N>_3DMODEL_DIR}`, MUST be reported `skipped`.
- `--verify` MUST re-hash every stamped file of the selected tags and exit 5 naming a file whose SHA-256 differs from its entry.
- The tool MUST print one line per model path, ending in `fetched`, `cached`, `skipped` or `failed`, MUST exit 0 when no file failed, and MUST NOT download a repository archive in this mode. The unit tests MUST replace the two requests and make none.

#### Scenario: Fetch and stamp
- **GIVEN** a board naming two models of one tag, a pins file with that tag's model pin, and request functions replaced by the test that answer with a size, a SHA-256 and bytes that match
- **WHEN** `uv run pytest tests/unit/test_libs_fetch_models.py -k fetch` runs the tool with `--cache C --models <board>`
- **THEN** it exits 0 reporting two `fetched`, both files are under `C/<tag>/kicad-packages3D/`, and the stamp maps both `<rel>` to their SHA-256

#### Scenario: Cached files are not requested
- **GIVEN** the cache fetched above and request functions that raise
- **WHEN** the tool runs again
- **THEN** it exits 0 reporting two `cached`

#### Scenario: Digest mismatch
- **GIVEN** request functions whose bytes do not have the announced SHA-256
- **WHEN** the tool runs
- **THEN** it exits 5, the target file does not exist, the stamp has no entry for it, and `C/<tag>/` holds no temporary file

#### Scenario: A model of another library
- **GIVEN** a board naming `${KIPRJMOD}/models/x.step` and `${KICAD8_3DMODEL_DIR}/y.step`
- **WHEN** the tool runs
- **THEN** both are reported `skipped`, no request is made, and the exit code is 0

## MODIFIED Requirements

### Requirement: Missing 3D models are warnings
`LibraryResolver.missing_models(fp)` SHALL locate every model path of a footprint definition with `locate_model` ("3D model location"). For each path that it does not locate it SHALL return one warning `kicad.lib.missing-3d-model`; when the path holds a variable that no source gives a value, the message MUST name the variable. It MUST NOT raise, and it MUST NOT download anything.

#### Scenario: Mini resistor model absent
- **GIVEN** `Mini:Mini_R_0603`, whose model path is `${KICAD10_3DMODEL_DIR}/Mini.3dshapes/Mini_R_0603.step`, and `KICAD10_3DMODEL_DIR` set to an empty temporary folder
- **WHEN** `missing_models` is called on it
- **THEN** it returns exactly one warning `kicad.lib.missing-3d-model`, and no exception is raised

#### Scenario: Model variable without a value
- **GIVEN** the same footprint, no library source and no `KICAD10_3DMODEL_DIR`
- **WHEN** `missing_models` is called on it
- **THEN** it returns exactly one warning `kicad.lib.missing-3d-model` whose message names `KICAD10_3DMODEL_DIR`

#### Scenario: A vendored copy is not missing
- **GIVEN** the same footprint, no `KICAD10_3DMODEL_DIR`, and a resolver whose `project_dir` holds `3dmodels/Mini.3dshapes/Mini_R_0603.step`
- **WHEN** `missing_models` is called on it
- **THEN** it returns no warning
