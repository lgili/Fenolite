## Context

- **Where the project is.** `src/fenolite/backends/altium/` writes project files, schematics, schematic libraries, PCB libraries and PCB documents (c0032 to c0036 done; c0037 and c0038 being implemented). Its container writer is `backends/altium/cfb.py`: MS-CFB version 3, no DIFAT sector, written from `docs/formats/altium/compound-file.md`.
- **The only reader is test code.** `tests/_cfb_read.py` checks Fenolite's output. It accepts version 3 only, refuses DIFAT sectors, raises a `CfbError` with a text and no location, and holds every stream in memory. It stays as it is: it is the independent check of the writer, and here of the new reader.
- **v0.3 reads.** c0040 (schematics), c0041 (PCB), c0043 (import) and c0044 (inspect, check, diff, copy identity per stream) all start from the container. This change gives them one reader.
- **Census of public files (2026-10-03, scratch only).** 23 Altium-written files that earlier changes had already consulted, from eight repositories (S-0170, S-0171, S-0172, S-0174, S-0175, S-0176, S-0187, S-0188, S-0199, S-0200), were measured with a scratch script written from the fact page. Counts only:

  | measure | result |
  |---|---|
  | major version, minor version, sector sizes | 3, `0x003E`, 512 and 64 in all 23 |
  | header CLSID, reserved bytes, transaction signature | zero in all 23 |
  | file length | the header and whole sectors in all 23 |
  | accepted by `tests/_cfb_read.py` | 22; the other one is refused for its DIFAT sector |
  | DIFAT | one file (S-0188, 10 078 208 bytes): 154 FAT sectors, one DIFAT sector with 45 entries, FREESECT after them, next sector ENDOFCHAIN, marked DIFSECT in the FAT |
  | largest file without DIFAT | 6 730 752 bytes, 103 FAT sectors (S-0176) |
  | entry colours | red and black entries in every file |
  | root entry | a modified time in 17 files; a CLSID in the 6 schematics of S-0187; no creation time; name `Root Entry` |
  | storages | a creation or modified time on every storage of the 11 files that have storages; no CLSID, no state bits; starting sector 0 and size 0; none empty |
  | streams | zero CLSID, state bits and times; empty streams start at ENDOFCHAIN; no size above 32 bits |
  | unused entries | zero with NOSTREAM links |
  | chains | exactly as long as the size needs; no shared sector; every allocated sector has one owner |
  | trees | search-tree order holds; no entry outside a tree; names up to 31 characters |
  | version 4 | none found |

  So an Altium-written file is valid MS-CFB. What Fenolite's test reader lacks is DIFAT. What Fenolite's writer never writes, and the reader must accept, is red entries, a root CLSID, and times on the root and on storages.
- **MS-CFB (S-0145), re-read for this change.**
  - Version 4 has 4096-byte sectors, 1023 FAT sector numbers per DIFAT sector and 32 directory entries per sector. Its header is followed by 3584 zero bytes, and it counts its directory sectors.
  - The last field of a DIFAT sector names the next one, and ENDOFCHAIN ends the chain.
  - In version 3 the high 32 bits of a size must be zero. The text adds that some older writers left them uninitialised, and recommends that a parser ignore them unless its purpose is to verify a file.
  - A storage or root CLSID and state bits may be set. A storage may hold both times, the root a modified time.
- **Rules for this change.** Clean-room: the reader is written from Fenolite's fact page, after task 1.2 extends it. No reader of another project is read. The corpus files are fetched by the fetch tool at implementation time and never committed.

## Goals / Non-Goals

**Goals:**
- One product reader of compound files that later changes use without knowing sectors.
- Every public Altium-written file of the corpus reads; each tolerance is a recorded fact.
- A broken or hostile file gives a located error in bounded time and memory, never another exception.
- `fenolite inspect --streams` shows a container to a person or an agent.

**Non-Goals:**
- Everything under Non-goals in the proposal.
- Any change to the writer `backends/altium/cfb.py` or to `tests/_cfb_read.py`.

## Decisions

1. **A new package `fenolite.backends.altium.read`, module `cfb`.** The naming contract of v0.3 puts the readers under `backends/altium/read/` (`cfb`, `sch`, `schlib`, `pcb`, `pcblib`, `project`). `read/__init__.py` holds a docstring only, so importing one reader does not import the others.
   - The reader imports `fenolite.core` and the constants and `name_key` of the sibling writer `backends.altium.cfb`. One definition of the name order serves both.
   - Rejected: adding the reader to `backends/altium/cfb.py`. The writer's file is the object of author reports; it should not change.
   - Rejected: promoting `tests/_cfb_read.py`. Its value is that it is independent of the product, strict, and written for Fenolite's own layout.
2. **Standard library only; no third-party reader.** `struct` and `memoryview`.
   - Rejected: `olefile` as a dependency or as a test oracle. The core has no runtime dependency, and a dev-only oracle would be one more reader to trust. The independent reading is `tests/_cfb_read.py` (22 of 23 census files) and the sector partition (Decision 9).
3. **Parse eagerly, copy lazily.** `open_compound` reads the header, assembles the DIFAT and the FAT, reads the directory, walks every tree and every chain, and only then returns. `read(path)` copies the sectors of one stream.
   - All structural errors appear at `open_compound`, with a location. A later `read` cannot fail on a valid `CompoundFile`.
   - Chains are kept as `(first sector, count)` runs, so a 10 MB board costs a few kilobytes of bookkeeping.
   - Rejected: a fully lazy reader. An error would then surface in c0041 while it parses a record, far from its cause.
   - Rejected: returning `dict[str, bytes]` only. c0044 needs entry metadata and the tree; large boards should not be copied twice.
4. **Paths.** A path is the names joined by `/`, which MS-CFB forbids in a name. The root is `""`. Lookup compares each name under the MS-CFB order, which is case-insensitive, and `Node.path` keeps the stored spelling.
   - This matches how the container defines identity: two children of one storage may not differ only in case.
   - Rejected: exact-case lookup. Public sources spell one storage name of a PCB library in two ways (S-0170 against the name c0035 first wrote), and a reader should not depend on it.
5. **Order of `nodes()`.** Depth-first; siblings in the MS-CFB name order; a storage before its children. It is the order of an in-order walk of each sibling tree when the tree is valid, and it is defined by sorting, so it does not depend on the tree's shape or on a broken order.
   - Rejected: directory-index order. It is the order Altium saved in, which c0044 may want, so `Node.entry` keeps the index; but it is not stable under a rewrite.
6. **Three classes of deviation.**
   - *Valid MS-CFB that Fenolite's writer never writes*: accepted, no note. The census shows Altium writes them (Context).
   - *A broken rule that leaves every stream's bytes unambiguous*: a note. The nine codes of the spec. The bytes returned are the same as if the rule held.
   - *Anything that makes the bytes ambiguous or the walk unsafe*: an error.

   The line is "can the reader return bytes that any conforming reader would also return?". High size bits, for example, are a note, because the specification itself recommends ignoring them. A shared sector is an error, because two streams would claim the same bytes and the size bound of Decision 8 would fail.
   - The census found no file that needs a note. The notes are kept, because the cost is small and the alternative, refusing a file a user holds for a zeroed-field rule, helps nobody. `H-A-RD-CFB-CLEAN` records the claim that Altium-written files are clean, and the first corpus note refutes it and becomes a fact row.
   - `strict=True` raises the first note. c0044's copy-identity level may use it.
   - Rejected: a lenient mode that guesses (a chain that ends in FREESECT read "as far as it goes", an unknown object type skipped). No source says what Altium would do with such a file.
   - Rejected: checking the red-black balance. A reader needs only the set of children.
7. **Errors.** `CompoundError(FormatError)` with `rule`, and `FormatError`'s `file`, `locator` and `offset`. The rule table `ERROR_RULES` and the note table `NOTE_CODES` are closed, and a test compares them with the pages.
   - The offset is that of the field or FAT entry that breaks the rule, so a hex viewer finds it.
   - `FormatError` already maps to `FEN-3004` and exit 3 (`cli.errors.from_exception`), with `file:locator:@offset` as `where`. No new `FEN` code.
   - Rejected: one exception class per rule. Callers switch on `rule`.
   - Rejected: returning errors as issues with a partial tree. A reader that returns half a container invites a writer to save half a design.
8. **Bounds.**
   - `Limits(max_file_bytes=2**30, max_entries=2**18, max_depth=64)`. The largest public file read is 10 MB; the public viewer accepts 200 MB (S-0149); a version 3 stream cannot pass 2 GiB (S-0145). The entry limit bounds memory, since each entry becomes a `Node`. They are Fenolite's choices, listed as such on the fact page.
   - Every walk (DIFAT, chains, sibling trees, storages) keeps a visited set and uses an explicit stack. A cycle is found at its first repeat.
   - **No sector has two owners.** Each chain claims its sectors in one table. With that, the work of all chain walks together is at most one visit per sector, and the stream sizes add up to at most the file size. A small file cannot expand into a large result.
   - A size is checked against its chain before a byte is copied.
   - Rejected: a time limit. Linear work needs none, and a clock makes results depend on the machine.
   - Rejected: trusting the header's counts for allocation. Counts in a hostile header are checked against the file size first.
9. **Evidence without a writer round trip.** A container reader has no KiCad oracle that returns stream bytes. Three independent checks stand in:
   - the strict test reader gives the same streams on every corpus row without DIFAT;
   - the sector partition: every sector that the FAT allocates is owned by exactly one chain, by the FAT or by the DIFAT. A FAT assembled wrongly through a DIFAT sector cannot pass it on a 19 683-sector file;
   - the MS-CFB worked example, which no Fenolite code wrote.

   `CORPUS-VERIFIED` needs rows of at least three repositories ("Second-backend corpus rows"). The ten rows come from five.
   - `kicad-cli pcb import --format altium` (10.0) on the DIFAT board is recorded as supporting data. It reads the same container through its own reader but returns no stream to compare, so it raises no label.
   - Version 4 stays `INFERRED`. `EVIDENCE_V3` and `EVIDENCE_V4` are separate so that a version 4 file never borrows the version 3 label.
10. **Test builder `tests/_cfb_build.py`.** The product writer writes one layout. Tests need version 4, DIFAT sectors, red entries, metadata and faults. The builder lays out a container from a description (version, entries with metadata, optional extra FAT sectors) and offers named mutations (`cycle`, `share`, `cut`, `set_field`), each returning the offset it changed. It is written from the fact page and imports neither reader.
    - Rejected: extending `cfb.write_compound` with version 4 and DIFAT. That is a writer feature nobody needs yet and changes a file under author report.
    - Rejected: committed binary fixtures of broken files. A builder call states what is broken.
11. **`inspect --streams`.** A flag on the existing command, chosen by content, not by extension.
    - Each stream gets its size and SHA-256, so an agent can compare two files stream by stream before c0044 adds `diff`.
    - Without the flag, a compound file still exits 2 as today; the hint now names `--streams`. c0044 gives Altium files a `--summary`.
    - `--limit-bytes` is the only limit on the command line. The other two are API only.
    - Rejected: a new command `fenolite streams`. The contract keeps one command per verb, and this is inspection.
    - Rejected: choosing the view by extension. Four extensions share the container, and renamed files are common.
    - Rejected: an entry in `result.experimental`. Those entries describe write kinds; the view's evidence label already tells an agent what to trust. c0043 registers the backend.
12. **Spec placement.**
    - New capability `altium-compound-reader`.
    - `cli-contract` "Inspect command" is MODIFIED: its text says `--summary` is the only view and that every file that is not an S-expression exits 2. The full living text is copied (no active change modifies it) and edited in the first paragraph and the "Kinds" item, with two scenarios added. The view itself is the ADDED requirement "Inspect stream tree". c0044 bases its own MODIFIED text on this one, so c0039 archives first.
    - `corpus-policy` gets the ADDED requirement "Second-backend corpus rows", which c0040 to c0042 reuse for their rows.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/altium/read/__init__.py` (new) | docstring only |
| `src/fenolite/backends/altium/read/cfb.py` (new) | `open_compound(data: bytes, *, file: str = "", limits: Limits = DEFAULT_LIMITS, strict: bool = False) -> CompoundFile`; `read_compound(path: str \| os.PathLike[str], *, limits: Limits = DEFAULT_LIMITS, strict: bool = False) -> CompoundFile`; `is_compound(data: bytes) -> bool`; `class CompoundFile` (below); `@dataclass(frozen=True) class Node`; `@dataclass(frozen=True) class Header`; `@dataclass(frozen=True) class Limits`; `DEFAULT_LIMITS`; `class CompoundError(FormatError)` with `rule: str`; `ERROR_RULES: tuple[str, ...]`; `NOTE_CODES: tuple[str, ...]`; `EVIDENCE_V3`, `EVIDENCE_V4: Evidence` |
| `tests/_cfb_build.py` (new, test code) | `build(entries, *, version=3, root=…, pad_fat_sectors=0) -> Built` (`data`, `offsets`); mutations `cycle`, `share`, `cut`, `set_field` |
| `tests/unit/backends/altium/read/test_cfb_build.py`, `test_cfb_read.py`, `test_cfb_notes.py`, `test_cfb_errors.py`, `test_cfb_limits.py`, `test_cfb_fuzz.py`, `test_cfb_codes.py` (new) | the scenarios of the capability |
| `tests/corpus/test_altium_cfb.py` (new) | corpus reading, partition, census |
| `tests/corpus/manifest.toml`, `tests/corpus/test_manifest.py` (extended) | ten rows; the rules of "Second-backend corpus rows" |
| `src/fenolite/cli/cmd_inspect.py` (extended) | `--streams`, `--limit-bytes N` |
| `tests/unit/cli/test_inspect_streams.py` (new), `tests/unit/cli/test_inspect_cmd.py` (extended) | the view; the hint; the two-view usage error |
| `tests/unit/test_format_facts.py` (extended) | `ALTIUM_HYPOTHESES` accepts `H-A-RD-` |
| `docs/formats/altium/compound-file.md`, `docs/altium.md`, `docs/cli-contract.md`, `docs/hypotheses.md`, `docs/evidence/sources.md`, `src/fenolite/backends/altium/PROVENANCE.md`, `LEGAL-ANNEX.md`, `CHANGELOG.md` (extended) | facts, the reading section, the view, rows, provenance, session row, changelog |

**`CompoundFile`** (what c0040 to c0044 consume):

| member | meaning |
|---|---|
| `header: Header` | `major`, `minor`, `sector_size`, `mini_sector_size`, `sector_count`, `fat_sectors`, `difat_sectors`, `directory_entries`, `transaction` |
| `notes: tuple[Issue, ...]` | one issue per note code |
| `evidence: Evidence` | `EVIDENCE_V3` or `EVIDENCE_V4` |
| `root: Node` | the root storage |
| `nodes() -> tuple[Node, ...]` | root, then every storage and stream, depth-first |
| `node(path: str) -> Node` | `KeyError` when unknown |
| `__contains__(path: str) -> bool` | |
| `children(path: str = "") -> tuple[Node, ...]` | the children of a storage, in order; `KeyError` when unknown, `NotADirectoryError` for a stream |
| `streams() -> tuple[str, ...]`, `storages() -> tuple[str, ...]` | paths |
| `read(path: str) -> bytes` | one stream; `IsADirectoryError` for a storage |
| `as_dict() -> dict[str, bytes]` | every stream by path |
| `tree() -> tuple[cfb.Entry, ...]` | the writer's input form |

**`Node`**: `path`, `name`, `kind: Literal["root", "storage", "stream"]`, `size`, `entry`, `clsid: bytes`, `state_bits`, `created`, `modified`, `children: tuple[str, ...]`.

Typical use by a later reader:

```python
from fenolite.backends.altium.read import cfb

compound = cfb.read_compound(path)
data = compound.read("Board6/Data")
for node in compound.children("Library"):
    ...
```

## Integration with c0040 to c0047 (settled 2026-10-03)

**This change owns the container API.** The changes written in parallel assumed other shapes; they were aligned to the table above.

- The entry points are `open_compound(data, *, file="", limits=DEFAULT_LIMITS, strict=False)` for bytes and `read_compound(path, …)` for a file on disk. Neither takes an `issues` argument: a caller copies `CompoundFile.notes` into its own issue list.
- Members are methods (`streams()`, `storages()`, `children(path)`, `read(path)`, `as_dict()`, `tree()`), not attributes. A lookup that must not raise uses `path in compound` first.
- A reader that accepts bytes calls `is_compound(data)` before `open_compound` when it wants its own error for a file that is not a compound file; a `CompoundError` of a file with the signature is passed on unchanged.
- Consumers: c0040 (`read/sch/_container.py`), c0041 (`_open` of `read/pcb.py`), c0044 (`roundtrip`, through `open_compound` and `tree()`), and c0043 and c0046 only through the readers of c0040 and c0041. c0042 reads text files and does not import this module.
- Rejected: an attribute-style `CompoundFile.streams` mapping (c0041's first sketch). It would copy every stream on open and defeat lazy reading.

**This change owns the row ids of the second backend's corpus.** One scheme, `altium-third-party-<kind>-NN`; no row is renumbered and no URL is listed twice. The allocation over the v0.3 changes:

| kind | numbers | listed by | uses added later |
|---|---|---|---|
| `pcbdoc` | 01 to 04 | c0039 (`cfb`) | c0041: `altium-pcbdoc`; c0044: `rta` |
| `pcbdoc` | 05 (S-0174), 06 (S-0175), 07 (S-0200) | c0041 (`altium-pcbdoc`) | c0044: `rta` |
| `pcblib` | 01, 02 | c0039 (`cfb`) | c0041: `altium-pcblib`; c0044: `rta` |
| `pcblib` | 03, 04 (S-0171) | c0041 (`altium-pcblib`) | c0044: `rta` |
| `schdoc` | 01 to 04 | c0039 (`cfb`) | c0040: `altium-sch`; c0044: `rta` |
| `schdoc` | 05 to 13 | c0040 (`altium-sch`) | c0044: `rta` |
| `schlib` | 01 to 09 | c0040 (`altium-schlib`) | c0044: `rta` |
| `prjpcb`, `outjob`, `rules`, `stackup` | 01 to 03 each | c0042 (`altium-text`) | c0044: `rta` on `prjpcb` |
| `schdot` | 01 to 03 | c0046 (`altium-sch`, `altium-sheet`) | — |
| `harness` | none in v0.3 | — | the kind is reserved: no v0.3 change reads a `.Harness` file |
| next free numbers of `pcbdoc`, `schdoc`, `prjpcb` | as needed | c0043, then c0044, for project sets (`altium-set:<nn>`, `altium-import`) | c0044: `rta` |

- A row added for a project set carries only `altium`, `origin:third-party` and the set uses (and `rta`), so the counts that c0039, c0040, c0041 and c0045 state for `cfb`, `altium-sch`, `altium-schlib`, `altium-pcbdoc` and `altium-pcblib` hold after every later change.
- The repository rule for a `CORPUS-VERIFIED` label (three repositories) binds every later change. Where a kind has rows of fewer than three repositories (rule files per form, stack-up files, sheet templates), the label stays `INFERRED` and the corpus result is supporting data (c0042, c0046).

Layering: `backends.altium.read.cfb` is part of `backends.altium`. It imports `core` and `backends.altium.cfb` only, so the `backends.<x>` row holds and `ALLOWED` is unchanged. `cmd_inspect` imports the reader inside `_run`.

## Sources registered by this change

None. The range first given to this change, S-0205 to S-0212, overlaps the ranges of the active changes c0015 and c0022 (c0015 registers S-0205), so it is not used. The sources of c0040 to c0043 were moved to S-0277 to S-0308 for the same reason (integration, 2026-10-03). Every fact comes from sources already registered, whose "used for" cells task 1.1 widens:

| id | added use |
|---|---|
| S-0145 | reading: version 4 (sector shift 12, 3584 zero bytes after the header, the directory sector count, 1024 FAT entries, 1023 DIFAT entries and 32 directory entries per sector); DIFAT sectors and their chain; the recommendation to ignore the high 32 size bits in version 3; CLSID, state bits and times of root and storages; the 2 GiB limit of a version 3 stream |
| S-0149 | the viewer's 200 MB limit, as the scale for the default size limit |
| S-0170, S-0172, S-0176 | container census and corpus rows of c0039 |
| S-0171, S-0174, S-0175, S-0200 | container census of 2026-10-03 (no corpus row in c0039) |
| S-0187, S-0188, S-0199 | container census and corpus rows; S-0188's PCB document uses a DIFAT sector; S-0187's schematics carry a root CLSID |
| S-0020 | `kicad-cli` 10.0 run as a subprocess on the DIFAT row (supporting data) |

S-0187 and S-0188 are registered by c0037, and S-0199 and S-0200 by c0038. If either change has not registered its rows when task 1.1 runs, task 1.1 adds them with the text of that change's design.

**Corpus rows** (`uses = ["altium", "cfb", "origin:third-party"]`, `embeddable = false`; names appear only in the URL):

| id | source | url | commit (`ref`) | SHA-256 | licence | bytes |
|---|---|---|---|---|---|---|
| `altium-third-party-pcbdoc-01` | S-0188 | `https://raw.githubusercontent.com/raphaelchang/battman-hardware/<ref>/BMS/BMS.PcbDoc` | `db5ae48d09e9ec9523387e2190fd14671a0646ca` | `e8a87333123e36e6b0260258322bccedac466624ed7f68dfe574db11ca11e4c4` | LGPL-3.0 | 10 078 208 |
| `altium-third-party-pcbdoc-02` | S-0176 | `https://media.githubusercontent.com/media/HangX-Ma/miniFOC/<ref>/Hardware/miniFOC_driver/foc.PcbDoc` | `324ac59357440746b89ee1882f213ea987bb4438` | `55d15ca572546f1ed6cc36d9d3d6472b2b5f19137ad384d73f6369fec2efad31` | Apache-2.0 | 6 730 752 |
| `altium-third-party-pcbdoc-03` | S-0172 | `https://raw.githubusercontent.com/TobiasRothlin/AltiumPCBLibrary/<ref>/PCBLibrary/PCB1.PcbDoc` | `fdff76666ffbfa4a1ba2e3d3fe5a52c090b45cb7` | `567fd0dfdba54c04adbdd2cc19b427c894b7a94aa953aa361f3e0afc71db12b3` | Apache-2.0 | 2 793 984 |
| `altium-third-party-pcbdoc-04` | S-0199 | `https://raw.githubusercontent.com/luxonis/oak-hardware/<ref>/NG6011_Dot_projector/PCB/NG6011.PcbDoc` | `7d569e3ccdff30014a498dc6c64a2e0dcad6964c` | `bf32fd189e9850f2e9de397a567ba78934ad62e7b092184a3ad71227d5b8cf39` | MIT | 2 471 424 |
| `altium-third-party-pcblib-01` | S-0170 | `https://raw.githubusercontent.com/LanguidSmartass/altium-libs/<ref>/libs/08_Switches/Relays/Relays_EM.PcbLib` | `5e7cf90145aa20ec79ac2e0d510ccd8ff1f19a19` | `abcfc13aa6f758f0e9ceb5246e128baeae0884786fd05bfc63fb24a08f5ca961` | MIT | 99 840 |
| `altium-third-party-pcblib-02` | S-0170 | `https://raw.githubusercontent.com/LanguidSmartass/altium-libs/<ref>/libs/12_Electrical%20PCB%20related/Free%20pads/PcbLib1.PcbLib` | the same | `f29440e3cc117bf6e555ebf20fe5889608c3ff261a0d9674ae06738bc9d18195` | MIT | 119 296 |
| `altium-third-party-schdoc-01` | S-0188 | `https://raw.githubusercontent.com/raphaelchang/battman-hardware/<ref>/BMS/BMS.SchDoc` | as pcbdoc-01 | `898c4fa7b6ed567cf8946979ed39a988f2337081690b4d7e324637356ac05f91` | LGPL-3.0 | 23 040 |
| `altium-third-party-schdoc-02` | S-0188 | `…/BMS/MCU.SchDoc` in the same repository | as pcbdoc-01 | `a5741d6e892bd1a03e567cafcdd0bcfdb10c5c5da3a45c378c4efc1b7c06c419` | LGPL-3.0 | 210 432 |
| `altium-third-party-schdoc-03` | S-0187 | `https://raw.githubusercontent.com/luxonis/oak-hardware/<ref>/DM3370_RAE/PCB/TopLevel.SchDoc` | as pcbdoc-04 | `19229739534ab270829953ab901c6afd6cb26f409a31dc6402fdd987da8deb9c` | MIT | 131 072 |
| `altium-third-party-schdoc-04` | S-0187 | `…/DM3370_RAE/PCB/DM3370_USB.SchDoc` in the same repository | as pcbdoc-04 | `2ab80d1e4738d6911f4f20f0cf763779f1eeb51ac07e2a0b2be62802e0dfea2a` | MIT | 750 080 |

- The SHA-256 values and sizes are those recorded when the files were first consulted (sources register; research notes of c0037 and c0038). Task 2.1 confirms each URL by fetching: the fetch tool refuses a hash that differs. A path that has moved inside the repository is corrected from the repository's tree at that commit; the hash decides.
- S-0176 is recorded as a Git LFS object, so its row uses the media URL. If another row turns out to be an LFS pointer, its URL takes the media form.
- No file is committed. No schematic library is listed: none has been consulted yet, and c0040 adds its own rows.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-RD-CFB-CORPUS | `open_compound` returns the storages and streams of public Altium-written version 3 files, byte for byte (S-0145; S-0170, S-0172, S-0176, S-0187, S-0188, S-0199) | `tests/corpus/test_altium_cfb.py` | on rows of at least three repositories: no error; every allocated sector has exactly one owner; every row without DIFAT equals `tests/_cfb_read.read_compound`; target `CORPUS-VERIFIED` |
| H-A-RD-CFB-DIFAT | The FAT of a file with more than 109 FAT sectors is assembled from the header and the DIFAT chain as the fact page says: 127 numbers per sector, the next sector last, ENDOFCHAIN at the end (S-0145, S-0188) | the same test on `altium-third-party-pcbdoc-01`; `tests/unit/backends/altium/read/test_cfb_read.py -k difat` on authored containers with one and two DIFAT sectors | the row reports 154 FAT sectors and 1 DIFAT sector, and its sector partition holds; target `CORPUS-VERIFIED`; supporting: `kicad-cli` 10.0 imports the same file with exit 0 |
| H-A-RD-CFB-CLEAN | Altium-written compound files break no MS-CFB rule that the reader reports as a note (census of 23 files, 2026-10-03) | the same corpus test, note codes per row | no row gives a note; the first note refutes the row and becomes a fact row of `compound-file.md` |
| H-A-RD-CFB-V4 | A version 4 file is read with 4096-byte sectors, 1024 FAT entries, 1023 DIFAT entries and 32 directory entries per sector, and a 64-bit size (S-0145) | `tests/unit/backends/altium/read/test_cfb_read.py -k v4` on authored containers; settled only by a public Altium-written or specification-published version 4 file | stays `INFERRED`; no public version 4 file is known |

Checked on 2026-10-03: no id with the stem `H-A-RD-` exists in `docs/hypotheses.md` or in an active change.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Version 3 parsing: header, FAT, mini stream, directory, trees, paths | mechanical on authored files and the MS-CFB example; `CORPUS-VERIFIED` on public files | `test_cfb_read.py`, `tests/corpus/test_altium_cfb.py` |
| DIFAT sectors | mechanical on authored containers; `CORPUS-VERIFIED` on the DIFAT row | the same |
| Version 4 | mechanical on authored containers; the rules `INFERRED` (S-0145, `H-A-RD-CFB-V4`) | `test_cfb_read.py -k v4` |
| Tolerances and notes | mechanical; "Altium files give no note" `CORPUS-VERIFIED` or refuted | `test_cfb_notes.py`, the corpus census |
| Located errors, closed tables | mechanical: one mutation per rule | `test_cfb_errors.py`, `test_cfb_codes.py` |
| Bounds | mechanical: limits, cycles, shared sectors, fuzz | `test_cfb_limits.py`, `test_cfb_fuzz.py` |
| `inspect --streams` | mechanical; envelope evidence is `CompoundFile.evidence` | `test_inspect_streams.py` |
| Corpus rows and their policy | mechanical | `tests/corpus/test_manifest.py` |

## Size (design-days)

| work | design-days |
|---|---|
| 1. sources, hypotheses, fact page, provenance | 0.5 |
| 2. corpus rows and manifest rules | 0.5 |
| 3. test builder; reader: header, DIFAT, FAT, directory, trees, chains, paths, views | 1.5 |
| 4. notes, strict mode, errors with locations, limits, fuzz | 1.0 |
| 5. corpus test, census and labels | 0.5 |
| 6. `inspect --streams` and documentation | 0.5 |
| 7. closing | 0.25 |
| **total** | **4.75** |

This is a size, not a calendar estimate. Cut order: (1) `--limit-bytes` (−0.1); (2) `tree()` and the writer round trip (−0.15), which c0044 would then add. Not optional: DIFAT, both versions, located errors, the bounds and the corpus test.

## Risks / Trade-offs

- [A corpus URL or path differs from the recorded one] → The hash decides. Task 2.1 corrects the path at the same commit, or swaps the row for another census file of the same repository and records it.
- [A corpus file needs a note or breaks a rule] → It refutes `H-A-RD-CFB-CLEAN` and becomes a fact row. If it is an error, the rule moves to a note only when the bytes stay unambiguous; otherwise the row is tagged out with the reason, and the design is amended.
- [The reader and the test reader share a misreading] → They were written at different times from the page, the test reader is checked by an Altium reader through the writer, and the MS-CFB example and the sector partition do not depend on either.
- [Version 4 is never exercised by a real file] → It stays `INFERRED` and labelled per file. All 23 census files are version 3; the cost of version 4 is one sector-size parameter.
- [Case-insensitive lookup hides a spelling a later writer must keep] → `Node.name` keeps the stored spelling, and `tree()` returns it.
- [Limits refuse a legitimate file] → They are parameters, and `--limit-bytes` raises the one a user meets. The error names the limit.
- [Memory on large files] → `read_compound` holds the file once; stream reads copy one stream. Memory mapping is an Open Question.
- [Concurrent changes c0040 to c0044 assume other names] → The API table above is the contract; their designs cite it.

## Migration Plan

- Additive: a new package, a flag on `inspect`, ten manifest rows, tests and pages.
- `inspect` without `--streams` behaves as before, except for the hint of the `FEN-2001` error on a compound file.
- `tests/_cfb_read.py` and `backends/altium/cfb.py` are unchanged.
- Rollback: remove `backends/altium/read/`, the flag and the rows. Nothing else depends on them until c0040.
- Archive order: c0037 and c0038 first (their source rows), then c0039, then c0040 to c0044. c0044's MODIFIED "Inspect command" copies this change's text.

## Open Questions

- **Default limits.** Default: 1 GiB, 262 144 entries, 64 levels. Lower the file limit to 256 MiB if a user never needs more than the viewer's 200 MB.
- **Memory mapping in `read_compound`.** Default: no; read the file once. Reconsider when a board above 100 MB appears in the corpus.
- **A public version 4 file.** Default: none is searched for in this change beyond the census. c0041 adds it as a row if its corpus search finds one, and that settles `H-A-RD-CFB-V4`.
- **Orphan entries.** Default: a warning note, and the entries are not returned. If a corpus file holds data only in orphans, add `CompoundFile.orphans()`.
- **`result.experimental` entry for reading.** Default: none; c0043 registers the backend in `result.backends`.
- **For the maintainer: more corpus rows.** Default: the ten rows above. The other 13 census files (S-0171, S-0174, S-0175, S-0200 and the rest of S-0187 and S-0188) can be added by c0040 and c0041 with their own tags.
