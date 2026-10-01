## ADDED Requirements

### Requirement: Upgraded copies keep their origin
A copy of a manifest row that `kicad-cli` 10.0.6 makes with `pcb upgrade --force` SHALL count as that row's origin (`origin:kicad-demos` or `origin:third-party`) when an evidence rule needs files from two or more origins, such as `CORPUS-VERIFIED`.
- The copy MUST be made through the package runner (`KicadCli.upgrade_board`), from the cached file. It MUST be kept only in memory or under `tmp_path`, and it MUST NOT be committed (requirement "Derived corpus files stay out of the repository").
- A test that uses such copies MUST carry `needs_corpus` and `kicad_min_major(10)`.
- A hypothesis row that relies on such copies MUST say so in its result.
- If review rejects this rule, the fallback is a search of at most 0.5 day for native permissive boards in format 8.0 or newer. The fallback registers them as new rows with a new source id and `embeddable = false`.

#### Scenario: Third-party origin through upgraded copies
- **GIVEN** the cached rows `third-party-pcb-01`, `-02` and `-03`, below the read floor, and `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/board/test_board_upgraded.py -q` runs with `FENOLITE_REQUIRE=kicad,corpus`
- **THEN** each upgraded copy is read and checked as origin `third-party`, and `git status --porcelain` is unchanged afterwards

#### Scenario: Skipped on KiCad 9
- **GIVEN** the `kicad-9` job with `kicad-cli` 9.0.9 and `FENOLITE_REQUIRE=kicad`
- **WHEN** `uv run pytest tests/kicad/board/test_board_upgraded.py` runs
- **THEN** every test is skipped and none fails
