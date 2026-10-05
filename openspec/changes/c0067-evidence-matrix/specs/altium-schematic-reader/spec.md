## MODIFIED Requirements

### Requirement: Schematic reader entry points
The package `fenolite.backends.altium.read.sch` SHALL export `read_schematic(data: bytes, *, file: str = "", codepage: str = DEFAULT_CODEPAGE, issues: list[Issue] | None = None) -> SchDocument` and `detect(data: bytes) -> str | None`, and the module `fenolite.backends.altium.read.schlib` SHALL export `read_schlib(data: bytes, *, file: str = "", codepage: str = DEFAULT_CODEPAGE, issues: list[Issue] | None = None) -> SchLibrary`.
- Both functions MUST take the file's bytes, MUST NOT open, create or change any file, and MUST return frozen dataclasses whose sequences are tuples.
- `detect` MUST return `"ascii"` when the bytes, after an optional UTF-8 byte-order mark, start with `|HEADER=`; for a compound file it MUST return `"binary"` or `"library"` from the header text of the first record of `FileHeader`; otherwise `None`. It MUST NOT look at a file name.
- `read_schematic` MUST read a schematic document and a schematic template alike (`.SchDoc`, `.SchDot`), in the binary and in the ASCII form. Given a library it MUST raise `FormatError` that names `read_schlib`; `read_schlib` given a schematic MUST raise `FormatError` that names `read_schematic`.
- The compound file MUST be opened only through `fenolite.backends.altium.read.cfb.open_compound` (change c0039), and the notes of the `CompoundFile` MUST be added to `issues`. No module of this capability parses a sector, a FAT or a directory entry.
- The modules MUST import only the standard library, `fenolite.core`, `fenolite.backends.altium.read` and themselves. They MUST NOT import the writer modules (`ascii`, `binary`, `schdoc`, `schlib`, `altsym`, `layout`, `project`) or anything under `tests/`.
- Two calls with equal arguments MUST return equal results and equal issue lists, whatever `PYTHONHASHSEED` is.
- `read.sch.HYPOTHESES` MUST hold every registered `H-A-RD-SCH-*` id and `read.sch.REFUTED` those among them whose row is refuted. `read.sch.EVIDENCE` MUST be an `Evidence` whose hypotheses are the ids of `HYPOTHESES` that are not in `REFUTED`, and whose level is the lowest level among the rows it names: a refuted row supports no claim (`verification-evidence`, "Declared levels agree with the register").

#### Scenario: Binary schematic by content
- **GIVEN** the bytes of `tests/data/altium/blink/blink.SchDoc` (a committed binary sample written by Fenolite) passed with `file="x.bin"`
- **WHEN** `detect` and `read_schematic` run
- **THEN** `detect` returns `"binary"`, and the result is a `SchDocument` with `form == "binary"` whose record 0 is a `Sheet`

#### Scenario: Library given to the schematic reader
- **GIVEN** the bytes of a schematic library
- **WHEN** `read_schematic(data, file="a.SchLib")` runs
- **THEN** it raises `FormatError` whose `file` is `a.SchLib` and whose message names `read_schlib`

#### Scenario: Neither form
- **GIVEN** the bytes `b"hello"`
- **WHEN** `detect` and `read_schematic` run
- **THEN** `detect` returns `None` and `read_schematic` raises `FormatError` with `offset` 0

#### Scenario: Reader does not import the writer
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_sch_imports.py` walks the imports of `fenolite.backends.altium.read.sch` and `read.schlib`
- **THEN** no writer module of `fenolite.backends.altium` and no `tests` module is among them
