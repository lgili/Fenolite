## ADDED Requirements

### Requirement: Layer texts in memory
`fenolite.model.canonical.dump_texts(design) -> dict[str, str]` SHALL return the six layer files of "One file per layer" as a mapping from file name (`meta.json`, `circuit.json`, `board.json`, `rules.json`, `manufacturing.json`, `findings.json`) to text, without touching the file system.
- `dump_dir(design, path)` MUST write exactly the texts of `dump_texts(design)`, encoded as UTF-8, so its output bytes do not change.
- A command that writes the layer files through the mutation protocol, such as `build`, MUST take them from `dump_texts` and MUST NOT call `dump_dir`.
- `load_dir` MUST read only the six layer files, so another file in the same folder, such as `.fenolite/build.json`, is ignored and does not count as a layer file.

#### Scenario: Same bytes as dump_dir
- **GIVEN** the model of the built blink design
- **WHEN** `uv run pytest tests/unit/model/test_dump_texts.py` compares `dump_texts(design)` with the files `dump_dir(design, tmp_path)` writes
- **THEN** the keys are the six layer file names and each text, encoded as UTF-8, equals the bytes of the file with that name

#### Scenario: Nothing written
- **GIVEN** an empty temporary working directory
- **WHEN** `dump_texts(design)` is called
- **THEN** the directory is still empty

#### Scenario: Build record ignored on load
- **GIVEN** a folder written by `dump_dir` that also holds a `build.json`
- **WHEN** `load_dir` reads it
- **THEN** it returns the design without error, equal to the design read from the same folder without `build.json`
