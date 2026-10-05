## ADDED Requirements

### Requirement: Compound file reading
`fenolite.backends.altium.read.cfb.open_compound(data, *, file="", limits=DEFAULT_LIMITS, strict=False)` SHALL read the bytes of an MS-CFB compound file of version 3 or 4 and return a `CompoundFile` that gives every storage and every stream by its path, with the stream contents as `bytes` (S-0145, `docs/formats/altium/compound-file.md`, section "Reading"). `read_compound(path, *, limits=DEFAULT_LIMITS, strict=False)` SHALL do the same for a file on disk and pass the file name as `file`. `is_compound(data)` SHALL return whether `data` starts with the eight signature bytes. The module reads only; it writes no file and runs no tool.
- **Versions.** Major version 3 MUST be read with 512-byte sectors (sector shift 9) and major version 4 with 4096-byte sectors (sector shift 12). Sector `N` starts at byte `(N + 1) × sector size` in both versions. A FAT sector holds 128 or 1024 entries, a DIFAT sector 127 or 1023 FAT sector numbers followed by the number of the next DIFAT sector, and a directory sector 4 or 32 entries of 128 bytes.
- **DIFAT.** The FAT sectors MUST be taken from the 109 header entries and then from the chain of DIFAT sectors that starts at the header's first DIFAT sector, in order, until the header's count of FAT sectors is reached.
- **Mini stream.** A stream smaller than the header's cutoff (4096) MUST be read from the mini stream through the mini FAT, in 64-byte mini sectors; any other stream MUST be read from regular sectors through the FAT. The mini stream is the chain and the size of the root entry. A stream of size 0 has no sector, whatever its starting sector.
- **Sizes.** In version 3 the size of an entry MUST be the low 32 bits of the size field. In version 4 it is the whole field.
- **Tree.** Entry 0 MUST be the root storage. The children of a storage are every entry reached from its child id through left and right sibling links. `CompoundFile.nodes()` MUST return the root and then every storage and stream depth-first, the children of each storage in the MS-CFB name order (a shorter name first, then the upper-cased UTF-16 code units; `backends.altium.cfb.name_key`), a storage before its own children.
- **Paths.** A path is the names from the root joined by `/`; the root's path is the empty string. `node(path)`, `read(path)` and `path in compound` MUST compare each name under the MS-CFB name order, so `fileheader` finds `FileHeader`; `Node.path` and `Node.name` keep the stored spelling. An unknown path MUST raise `KeyError`, and `read` of a storage `IsADirectoryError`.
- **Nodes.** A `Node` MUST hold `path`, `name`, `kind` (`"root"`, `"storage"` or `"stream"`), `size` (0 for a storage and the root), `entry` (the directory index), `clsid` (16 bytes), `state_bits`, `created` and `modified` (the two 64-bit time fields as integers) and `children` (the child paths in order; empty for a stream).
- **Views.** `streams()` and `storages()` MUST return the paths in `nodes()` order, and `children(path="")` the child nodes of the storage at `path` in that order (`KeyError` for an unknown path, `NotADirectoryError` for a stream). `as_dict()` MUST return every stream by path. `tree()` MUST return the root's content as `backends.altium.cfb.Entry` values (`(name, data)` and `Storage`), so `cfb.write_compound(compound.tree())` writes the same storages and streams when the writer accepts them. `CompoundFile.header` MUST hold `major`, `minor`, `sector_size`, `mini_sector_size`, `sector_count`, `fat_sectors`, `difat_sectors`, `directory_entries` and `transaction`.
- **Laziness.** `open_compound` MUST check the header, the DIFAT, the FAT, the directory, the trees and every chain before it returns. `read(path)` MUST copy only the sectors of that stream.
- The result MUST depend only on `data`: two calls give equal nodes, notes and bytes.

#### Scenario: Version 3 file written by Fenolite
- **WHEN** `open_compound` reads `tests/data/altium/sample/binary/altium_sample.SchDoc`
- **THEN** `streams()` is `("Storage", "FileHeader")`, `storages()` is empty, `header.major` is 3, and `as_dict()` equals `tests/_cfb_read.read_compound` of the same bytes

#### Scenario: Version 4 file
- **GIVEN** a version 4 container built by `tests/_cfb_build.py` with a storage `S` holding streams of 10 and 5000 bytes, and a root stream of 70 000 bytes
- **WHEN** `open_compound` reads it
- **THEN** `header.sector_size` is 4096, the three streams read back byte for byte, and `node("S").children` names the two streams in the MS-CFB order

#### Scenario: DIFAT sectors
- **GIVEN** a version 3 container built by `tests/_cfb_build.py` whose FAT needs 240 sectors, so two DIFAT sectors
- **WHEN** `open_compound` reads it
- **THEN** `header.fat_sectors` is 240, `header.difat_sectors` is 2, and a stream that lies in the sectors of the last FAT sector reads back byte for byte

#### Scenario: Cutoff boundary
- **WHEN** containers with one stream of 0, 1, 64, 65, 4095, 4096 and 4097 bytes are read, in version 3 and in version 4
- **THEN** every stream reads back byte for byte

#### Scenario: Path lookup
- **GIVEN** `tests/data/altium/blink/blink.PcbLib`
- **WHEN** `read("library/DATA")`, `node("Library").kind`, `read("Library")` and `node("Nope")` are evaluated
- **THEN** the first equals `read("Library/Data")`, the second is `"storage"`, the third raises `IsADirectoryError` and the fourth raises `KeyError`

#### Scenario: Children of a storage
- **GIVEN** the same file
- **WHEN** `children("Library")` and `children("Library/Data")` are evaluated
- **THEN** the first returns the nodes whose paths are `node("Library").children`, in that order, and the second raises `NotADirectoryError`

#### Scenario: The specification's worked example
- **WHEN** `open_compound` reads the MS-CFB section 3 example that `tests/unit/backends/altium/test_cfb_reader.py` rebuilds from the specification's tables
- **THEN** the storage and the stream of the example are returned with the example's sizes, and no note is reported

#### Scenario: Round trip through the writer
- **WHEN** `cfb.write_compound(open_compound(data).tree())` is read again, for every compound file under `tests/data/altium/`
- **THEN** both readings have equal paths, kinds and stream bytes

### Requirement: Compound file tolerances
`open_compound` SHALL accept what MS-CFB allows and Fenolite's own writer never writes, and SHALL report as a note, without refusing the file, each broken rule that leaves every stream's bytes unambiguous. `docs/formats/altium/compound-file.md` MUST record each tolerance as a fact row with its source.
- **Accepted without a note** (valid MS-CFB; all found in public Altium-written files, S-0170 to S-0176, S-0187, S-0188, S-0199, S-0200): DIFAT sectors; red and black entries; a non-zero CLSID, state bits and modified time on the root; a non-zero CLSID, state bits and times on a storage; sectors that the FAT marks as free; directory entries of type 0.
- **Notes.** A note is a `fenolite.core.errors.Issue` whose `where` is the locator. One issue is reported per code, with the count of cases and the first location in its message. `CompoundFile.notes` MUST hold them in the order of this table, which is closed (`cfb.NOTE_CODES`):

| code | severity | rule that is broken |
|---|---|---|
| `cfb.note.minor-version` | info | the minor version is not `0x003E` |
| `cfb.note.header-fields` | info | the header CLSID, the reserved bytes or the rest of a version 4 header sector are not zero; a version 3 header counts directory sectors; the count of mini FAT sectors, or of directory sectors in version 4, differs from the chain |
| `cfb.note.partial-sector` | warning | the bytes after the header are not whole sectors; no chain may use the cut sector |
| `cfb.note.fat-marks` | info | a FAT or DIFAT sector is not marked FATSECT or DIFSECT, or a FAT entry past the end of the file is not FREESECT |
| `cfb.note.high-size-bits` | info | the high 32 bits of a size are not zero in version 3; they are ignored, as the specification recommends |
| `cfb.note.long-chain` | info | a chain has more sectors than the size needs; the extra sectors are ignored |
| `cfb.note.entry-fields` | info | a stream has a CLSID, state bits or a time; a storage has a starting sector or a size; the root has a creation time or another name than `Root Entry`; a colour is not 0 or 1 |
| `cfb.note.tree-order` | warning | the sibling links of a storage do not form a search tree under the MS-CFB name order |
| `cfb.note.orphan-entries` | warning | a storage or stream entry is reached from no storage; it is not returned |

- No red-black balance rule is checked.
- With `strict=True`, the first note MUST be raised as a `CompoundError` whose `rule` is the note's code.
- Hypothesis `H-A-RD-CFB-CLEAN`: public Altium-written files give no note.

#### Scenario: Root and storage metadata kept
- **GIVEN** a container built by `tests/_cfb_build.py` with a root CLSID, a root modified time, a storage with both times, and red and black entries
- **WHEN** `open_compound` reads it
- **THEN** `notes` is empty, and the nodes hold that CLSID and those times

#### Scenario: High size bits ignored
- **GIVEN** a version 3 container whose stream entry of 100 bytes has `0xFFFFFFFF` in the high 32 bits of its size
- **WHEN** `open_compound` reads it
- **THEN** the stream has 100 bytes and `notes` holds exactly `cfb.note.high-size-bits`

#### Scenario: One note per code
- **GIVEN** a container with three stream entries that carry a modified time
- **WHEN** `open_compound` reads it
- **THEN** `notes` holds one `cfb.note.entry-fields` issue whose message names 3 cases and the first stream's path

#### Scenario: Strict mode
- **WHEN** the container of "High size bits ignored" is read with `strict=True`
- **THEN** `CompoundError` is raised with `rule` `cfb.note.high-size-bits` and the locator of that stream

### Requirement: Located compound file errors
A file that `open_compound` cannot read SHALL raise `cfb.CompoundError`, a `fenolite.core.errors.FormatError`, which names the broken rule and locates it. No other exception type may leave `open_compound` or `read_compound` for any input bytes, except `OSError` from reading the file.
- `CompoundError.rule` MUST be a code of the closed table `cfb.ERROR_RULES`. `file` is the given name. `locator` MUST be one of `header`, `difat[<i>]`, `fat`, `directory[<entry index>]`, `stream:<path>`, `storage:<path>`, `mini-fat` and `mini-stream`. `offset` MUST be the byte offset in the file of the field or sector that breaks the rule, or `None` when the rule concerns the file as a whole.
- The message MUST start with the rule code and name the value found.

| rule | when |
|---|---|
| `cfb.signature` | the file has at least 8 bytes and bytes 0 to 7 are not the signature |
| `cfb.truncated` | the file has fewer than 8 bytes, or has the signature and is shorter than its 512-byte header |
| `cfb.header` | the major version is not 3 or 4; the sector shift does not match it; the byte order is not `0xFFFE`; the mini sector shift is not 6; the cutoff is not 4096 |
| `cfb.difat` | a DIFAT or FAT sector number is outside the file or repeats; the DIFAT chain has a cycle, or does not give the header's count of FAT sectors |
| `cfb.chain` | a chain names a sector outside the file, repeats a sector, reaches FREESECT, FATSECT or DIFSECT, or is shorter than its size needs |
| `cfb.shared-sector` | two chains use the same sector or mini sector |
| `cfb.directory` | entry 0 is not a root storage; an object type is not 0, 1, 2 or 5; a link names an entry outside the directory, the root or an entry of type 0; an entry is reached twice; a stream has a child |
| `cfb.name` | a name length is odd, below 2 or above 64; the name is not valid UTF-16 or lacks its NUL; the name is empty or holds `/`, `\`, `:`, `!` or NUL |
| `cfb.duplicate-name` | two children of one storage are equal under the MS-CFB name order |
| `cfb.size` | a size is larger than its chain or than the file; the mini stream is shorter than a mini chain needs |
| `cfb.limit` | a limit of "Bounded reading of hostile files" is passed |

- The CLI maps `CompoundError` to `FEN-3004` and exit 3 through `FormatError` (`cli-contract`).

#### Scenario: Cycle in a chain
- **GIVEN** a container built by `tests/_cfb_build.py` in which the FAT entry of the last sector of the stream `Data` points back to its first sector
- **WHEN** `open_compound(data, file="x.PcbDoc")` runs
- **THEN** `CompoundError` is raised with `rule` `cfb.chain`, `locator` `stream:Data`, `file` `x.PcbDoc` and `offset` equal to the byte offset of that FAT entry

#### Scenario: One mutation per rule
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_cfb_errors.py` reads one mutated container per rule of the table
- **THEN** each raises `CompoundError` with that rule, a locator of the listed forms and the expected offset

#### Scenario: Not a compound file
- **WHEN** `open_compound` reads the ASCII schematic `tests/data/altium/sample/altium_sample.SchDoc` and an empty byte string
- **THEN** the first raises `cfb.signature` with `offset` 0 and the second `cfb.truncated`

### Requirement: Bounded reading of hostile files
`open_compound` SHALL finish in time and memory proportional to the size of `data` for any input, and SHALL refuse input past its limits before doing the work.
- `cfb.Limits` MUST hold `max_file_bytes` (default 1 073 741 824), `max_entries` (default 262 144 directory entries) and `max_depth` (default 64 levels of storages). `cfb.DEFAULT_LIMITS` is `Limits()`. Passing a limit MUST raise `CompoundError` with rule `cfb.limit`, naming the limit and the value found. `read_compound` MUST compare the file size with `max_file_bytes` before it reads the file.
- Every chain walk MUST record the sectors it visits and stop at a repeat, so a cycle costs at most one visit per sector. The DIFAT walk and the directory tree walks MUST do the same for DIFAT sectors and entries.
- Every sector and every mini sector MUST belong to at most one chain. So the sizes of all streams add up to at most the size of the file, and `as_dict()` can never return more bytes than `data` holds.
- Trees MUST be walked without recursion that grows with the input.
- A size MUST be checked against its chain before any byte is copied.

#### Scenario: Shared sectors refused
- **GIVEN** a container in which 1000 stream entries of 1 MiB name the same starting sector
- **WHEN** `open_compound` reads it
- **THEN** `CompoundError` is raised with rule `cfb.shared-sector`, and no stream is returned

#### Scenario: Sibling cycle
- **GIVEN** a container in which the right sibling of an entry is that entry's parent in the sibling tree
- **WHEN** `open_compound` reads it
- **THEN** `CompoundError` is raised with rule `cfb.directory`

#### Scenario: Deep nesting
- **GIVEN** a container with 100 nested storages
- **WHEN** `open_compound` reads it with the default limits, and again with `Limits(max_depth=128)`
- **THEN** the first raises `cfb.limit` naming `max_depth`, and the second returns a node at depth 100

#### Scenario: File size limit on disk
- **GIVEN** a file of 2000 bytes and `Limits(max_file_bytes=1000)`
- **WHEN** `read_compound` runs with `Path.read_bytes` patched to fail
- **THEN** `CompoundError` is raised with rule `cfb.limit`

#### Scenario: Mutated bytes never escape
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_cfb_fuzz.py` reads containers with random byte changes, cuts and extensions (Hypothesis, fixed seed in CI)
- **THEN** every call returns a `CompoundFile` or raises `CompoundError`, and for every returned file the stream sizes add up to at most the input size

### Requirement: Compound reader on public files
The reader SHALL be measured on public files that Altium wrote, listed in `tests/corpus/manifest.toml` (`corpus-policy`, "Second-backend corpus rows"), and its evidence SHALL follow the result.
- `tests/corpus/test_altium_cfb.py` (marker `needs_corpus`) MUST read every cached row whose `uses` holds `altium` and `cfb`. For each row it MUST check: no error; the notes; that every sector the FAT allocates belongs to exactly one chain, to the FAT or to the DIFAT; and, for a row without DIFAT sectors, that `as_dict()` equals `tests/_cfb_read.read_compound`. For a row with DIFAT sectors, which the test reader refuses, the sector check is the proof that the FAT was assembled through the DIFAT sectors.
- The test MUST write, only to the file named by `FENOLITE_CENSUS_OUT`, per row id: the major version, the counts of sectors, FAT sectors, DIFAT sectors, storages, streams, red entries, entries with a CLSID and entries with a time, and the note codes. It reports ids and counts only, never a name or a stream's content.
- `H-A-RD-CFB-CORPUS` and `H-A-RD-CFB-DIFAT` are confirmed at `CORPUS-VERIFIED` when the test passes on rows of at least three repositories, one of them with DIFAT sectors. `H-A-RD-CFB-CLEAN` is confirmed when no row gives a note, and refuted by the first note, which is then recorded as a fact row. `H-A-RD-CFB-V4` stays `INFERRED` until a public version 4 file is read.
- `CompoundFile.evidence` MUST be `cfb.EVIDENCE_V3` for a version 3 file and `cfb.EVIDENCE_V4` for a version 4 file. Both start as `INFERRED`, with `H-A-RD-CFB-CORPUS` and `H-A-RD-CFB-DIFAT`, and with `H-A-RD-CFB-V4`. `EVIDENCE_V3` becomes `CORPUS-VERIFIED` only when the first two rows are confirmed.
- `kicad-cli` 10.0 importing the DIFAT row with exit 0 is recorded as supporting data in the `H-A-RD-CFB-DIFAT` row. It raises no label, because it gives no stream bytes to compare.

#### Scenario: Corpus rows read
- **GIVEN** the cached rows with `uses` `altium` and `cfb`, and `FENOLITE_REQUIRE=corpus`
- **WHEN** `uv run pytest tests/corpus/test_altium_cfb.py -q` runs
- **THEN** every row reads with no error, every row without DIFAT sectors equals the test reader's streams, and the row `altium-third-party-pcbdoc-01` reports 154 FAT sectors and 1 DIFAT sector

#### Scenario: Corpus absent
- **GIVEN** an empty corpus cache and no `FENOLITE_REQUIRE`
- **WHEN** the same test runs
- **THEN** every case is skipped with the corpus hint, and the run exits 0

#### Scenario: Evidence by version
- **WHEN** a version 3 and a version 4 container are opened
- **THEN** the first has `evidence` `cfb.EVIDENCE_V3`, the second `cfb.EVIDENCE_V4`, and the second names `H-A-RD-CFB-V4` with level `INFERRED`

### Requirement: Compound reader is documented
The facts the reader relies on SHALL be rows of `docs/formats/altium/compound-file.md`, in the fact-table form that `tests/unit/test_format_facts.py` checks.
- The page MUST gain the sections "Version 4", "DIFAT sectors", "Reading: tolerances and notes", "Reading: limits" and "What public files hold". The existing DIFAT row of "Header and sectors" keeps its text and its label follows `H-A-RD-CFB-DIFAT`.
- Every tolerance and every note of "Compound file tolerances" MUST be one row with its source: S-0145 for a rule of the specification, and the source ids of the files for what Altium-written files hold. A reader choice that no source states, such as the default limits, MUST be listed under "Fenolite's choices", not in a fact table.
- A row below `KICAD-VERIFIED` and `CORPUS-VERIFIED` MUST name an `H-A-RD-CFB-*` row or an earlier `H-A-*` row. `ALTIUM_HYPOTHESES` of `tests/unit/test_format_facts.py` MUST accept the stem `H-A-RD-`.
- `src/fenolite/backends/altium/PROVENANCE.md` MUST gain a row for the reader: its sources, that the files are fetched and never committed, and that no reader code of another project was read.
- `docs/altium.md` MUST describe reading a container and the `inspect --streams` view.

#### Scenario: Fact page checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py` runs
- **THEN** it passes, and `compound-file.md` holds a row for each code of `cfb.NOTE_CODES`

#### Scenario: Codes and page agree
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_cfb_codes.py` compares `cfb.NOTE_CODES` and `cfb.ERROR_RULES` with the tables of `compound-file.md` and `docs/altium.md`
- **THEN** each code appears in both, and no page names a code the module lacks
