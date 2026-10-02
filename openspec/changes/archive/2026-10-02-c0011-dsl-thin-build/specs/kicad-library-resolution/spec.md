## ADDED Requirements

### Requirement: Project library tables are written per target
`fenolite.backends.kicad.libs.write_lib_table(table: LibTable, *, target: int = DEFAULT_TARGET) -> str` SHALL return the text of a project library table holding the rows of `table`, in their order, in the syntax of the target major.
- The root head MUST be the root name of the table's kind, the inverse of `libs.TABLE_ROOTS` (`footprint` → `fp_lib_table`, `symbol` → `sym_lib_table`), and each row MUST be written as `(lib (name …) (type …) (uri …) (options …) (descr …))`, with `(disabled)` and `(hidden)` only for rows that carry them.
- Target 10 MUST write a `(version 7)` child first and quote every atom, the form of the c0008 fixture `tests/data/libs/project/fp-lib-table` (S-0046).
- Target 9 MUST write no version child and bare atoms, quoting only an atom that cannot be written bare (empty, or holding a space, a parenthesis or a quote), the form of the 9.0.9 official tables (S-0042, S-0043).
- The text MUST end with a newline, use tab indentation, and depend only on `table` and `target`, so equal inputs give equal bytes.
- `read_lib_table` of the written text MUST give back a `LibTable` with the same rows, and `version == 7` for target 10 and `version is None` for target 9.
- A target other than 9 and 10 MUST raise `ValueError`.
- The build writes one `fp-lib-table` with a row `uri "${KIPRJMOD}/lib/<nickname>.pretty"` per vendored library; KiCad reading that table is `H-K-BUILD-LIBTABLE` (`kicad-oracle`, "Built projects pass the build oracle").

#### Scenario: Target 10 form
- **GIVEN** a `LibTable` of kind `footprint` with one row `Mini`, type `KiCad`, uri `${KIPRJMOD}/lib/Mini.pretty`, empty options and description
- **WHEN** `write_lib_table(table, target=10)` is called
- **THEN** the text starts with `(fp_lib_table` followed by `(version 7)`, and the row reads `(lib (name "Mini") (type "KiCad") (uri "${KIPRJMOD}/lib/Mini.pretty") (options "") (descr ""))`

#### Scenario: Target 9 form
- **WHEN** the same table is written with `target=9`
- **THEN** the text holds no `version` child, and the row reads `(lib (name Mini) (type KiCad) (uri ${KIPRJMOD}/lib/Mini.pretty) (options "") (descr ""))`

#### Scenario: Read back equal
- **WHEN** the texts of both targets are read with `read_lib_table`
- **THEN** both give the row `Mini` with the same `type`, `uri`, `options` and `descr`, and versions `7` and `None`

#### Scenario: Unknown target
- **WHEN** `write_lib_table(table, target=8)` is called
- **THEN** `ValueError` is raised
