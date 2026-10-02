## ADDED Requirements

### Requirement: Footprint files written by Fenolite read back equal
Every editable footprint definition (one not read from a future file) read by `read_footprint` or `footprint_from` SHALL survive `write_footprint` unchanged in the model, for the major it was read at and for any other target whose emit check passes without dropping a fragment. Definitions that `write_footprint` refuses (future files, too-new fragments without `allow_lossy`) are outside this requirement.
- For such a target `t`, `read_footprint(write_footprint(defn, target=t), library=defn.library)` MUST equal `defn`, ids included, ignoring provenance and `ext`. The opaque fragments of `defn` MUST reappear in the same order, apart from the header heads `version`, `generator` and `generator_version`, which the writer sets.
- The corpus round trip (`needs_corpus`) MUST cover every footprint of every non-heavy demo board that the board reader reads with 0 errors, written at the board's own major, and every footprint of the `pcb upgrade --force` copies of the third-party rows, made on 10.0.6 in `tmp_path` and never committed (origin `third-party`). The half that needs upgraded copies MUST also carry `needs_kicad` and `kicad_min_major(10)`.
- The written mini library MUST load with `kicad-cli fp export svg`: `Mini.pretty` written for target 10 on 10.0.6, and `Mini_v9.pretty` written for target 9 on 9.0.9. After `fp upgrade --force` into a new folder, every footprint MUST re-read equal to the original definition, ids included, ignoring provenance and `ext`.
- On 9.0.9, `tests/data/libs/Escapes_v9.pretty/Mini_Escapes.kicad_mod`, written for target 9, MUST keep every decoded property value and the description after `fp upgrade --force` (the 9.0 half of `H-K-SEXPR-ESCAPES`). Its properties MUST hold the ten escape forms of `tests/data/kicad/sexpr/escapes.kicad_pcb` and a non-ASCII value, and its description, set through the model, MUST hold the eight encoder values of the 10.0 proof.
- Every `kicad-cli` call MUST go through c0009's `KicadCli.run`, with results read from `CliRun.outputs`, and outcomes MUST be recorded under `fp-write-*` probe ids.

When the corpus round trip passes over both origins, the footprint half of `H-K-LIB-READ` SHALL be recorded as `CORPUS-VERIFIED`. The symbol half stays `INFERRED`, and the readers' `EVIDENCE` is governed by "Reading evidence".

#### Scenario: Demo board footprints round trip
- **GIVEN** the cached non-heavy demo boards of tags 10.0.6 and 9.0.9.1 that the board reader reads with 0 errors
- **WHEN** `uv run pytest tests/corpus/test_footprint_rt.py -k demo` runs
- **THEN** every footprint, read with `board_footprints`, written and read again, equals the original ignoring provenance and `ext`, with its opaque fragments in the same order

#### Scenario: Upgraded third-party footprints round trip
- **GIVEN** `kicad-cli` 10.0.6 and the `pcb upgrade --force` copies of the three third-party rows in `tmp_path`
- **WHEN** `uv run pytest tests/corpus/test_footprint_rt.py -k upgraded` runs
- **THEN** every footprint of every copy round trips as above, and `git status --porcelain` is unchanged afterwards

#### Scenario: Written mini library on KiCad 10
- **GIVEN** `kicad-cli` 10.0.6 and `write_pretty` of the four definitions of `Mini.pretty` for target 10, passed to `KicadCli.run` in `files` as `Mini.pretty` with the empty folders `svg` and `up`
- **WHEN** `fp export svg Mini.pretty -o svg` and then `fp upgrade --force Mini.pretty -o up/Mini.pretty` run
- **THEN** the outputs of the first run hold four SVG files, and every footprint in the outputs of the second run re-reads equal to its original definition

#### Scenario: Written 9.0 library on KiCad 9
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and `write_pretty` of `Mini_v9.pretty` for target 9
- **WHEN** `uv run pytest tests/kicad/libs/test_mod_write_oracle.py` runs with `FENOLITE_REQUIRE=kicad`
- **THEN** the library loads, every upgraded footprint re-reads equal, and the test of `Mini.pretty` written for target 10 is skipped, not failed

#### Scenario: Escapes on KiCad 9
- **GIVEN** `kicad-cli` 9.0.9 and `Mini_Escapes` written for target 9, with one property value per escape form of `escapes.kicad_pcb` (`\"`, `\\`, `\n`, `\r`, `\t`, `\v`, `\7`, `\101`, `\x42`, `\e`) and a non-ASCII one, and a description set through the model to the concatenation of the eight encoder values (quote, backslash, line feed, carriage return, tab, vertical tab, `\x01`, non-ASCII)
- **WHEN** `fp upgrade --force` re-saves it and the result is read
- **THEN** every decoded property value and the description equal the values before the re-save

### Requirement: Board footprints read as definitions
`fenolite.backends.kicad.mod.footprint_from(loaded, *, library=None, issues=None, root_chain=("footprint",), index=0)` SHALL also accept `root_chain == ("kicad_pcb", "footprint")`. Then `loaded.node` is a board root, and the definition MUST be read from its `index`-th `footprint` child with the board's version policy (`FileKind.BOARD`) and locators `/kicad_pcb/footprint[index]/…`. `board_footprints(source, *, file="", issues=None)` SHALL return one definition per footprint of a board, in file order.
- When `library` is `None`, the header lib_id MUST be split at its first colon. A lib_id without a colon MUST give `library == ""` and the whole text as the name.
- Board-only children, when present (`at`, `path`, `sheetname`, `sheetfile`, the placement `uuid`, pad `net`, `pinfunction` and `pintype`), MUST be opaque slots of the definition or of its pads.
- Coordinates and angles MUST be taken as stored, without conversion to the library frame.
- With the default root chain, `footprint_from` MUST behave as before.

#### Scenario: Footprints placed in a board read as definitions
- **GIVEN** c0009's authored board `tests/data/kicad/board/two_layer.kicad_pcb`
- **WHEN** `board_footprints(Path(...))` is called
- **THEN** two definitions are returned, `R_0603` and `LED_THT_3mm`, both with library `Fenolite_Test`, with provenance locators under `/kicad_pcb/footprint[0]` and `/kicad_pcb/footprint[1]`, and with the `at` child, the placement `uuid` and each pad's `net` and `pintype` (and, for `LED_THT_3mm`, `pinfunction`) as opaque slots

#### Scenario: Sheet links kept opaque
- **GIVEN** an inline board text whose one footprint holds `(path "/1f2e")`, `(sheetname "Root")` and `(sheetfile "a.kicad_sch")`
- **WHEN** `board_footprints` reads it
- **THEN** the three children are opaque slots of the definition, in file order

#### Scenario: Lib_id without a colon
- **GIVEN** an inline board text whose one footprint is named `R_0603`, without a library
- **WHEN** `board_footprints` reads it
- **THEN** the definition has `library == ""` and `name == "R_0603"`
