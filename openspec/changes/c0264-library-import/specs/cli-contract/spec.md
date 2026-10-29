## ADDED Requirements

### Requirement: Library subcommand words
The first positional argument of `fenolite library` SHALL select a subcommand when it is `import`, `propose`, `check`, `review` or `fetch`, and a subcommand that is not registered yet MUST exit 2 with `FEN-2001`. Any other first argument MUST keep the board form of "Library made from a board" unchanged; a board path spelled like a word is written `./import`.

#### Scenario: The board form is unchanged
- **WHEN** `fenolite library <example board> --out lib.pretty --dry-run --json` runs
- **THEN** the reply equals the reply before this change

#### Scenario: A board folder named like a word
- **GIVEN** the example board copied into a folder `import`
- **WHEN** `fenolite library ./import --out lib.pretty --dry-run --json` runs
- **THEN** the board form runs and plans the library

### Requirement: Library import command
`fenolite library import` SHALL be a mutating command of the registry, described in `docs/cli-contract.md` ("library import") with its options, result schema `fenolite.library-import.v0` and codes. Its example arguments MUST name authored files under `tests/data/library_import/`, so the consistency suite and the MCP tool list cover it offline.

#### Scenario: Consistency suite covers the import
- **WHEN** `uv run pytest tests/consistency -q` runs
- **THEN** `library import` is planned with its example arguments, its dry run exits 4, and the confirmed plan writes only under the temporary project
