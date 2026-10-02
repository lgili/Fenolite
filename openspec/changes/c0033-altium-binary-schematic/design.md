## Context

- **c0032** (committed on main, being implemented in a separate worktree, not archived) writes `<name>.PrjPcb` and an ASCII `<name>.SchDoc` from a DSL design. Its names this change builds on: `backends.altium.ascii` (`HEADER_TEXT`, `header_record`, `format_record`, `encode_records`), `schdoc.schdoc_records(plan)` and `write_schdoc(plan)`, `project.write_project`, `plan_sheet`, `WRITE_KINDS`, `EVIDENCE`, `lens.altium.build_altium`, `generic_pins`, `ALTIUM_ISSUE_CODES`, `ALTIUM_BUILD_EVIDENCE`, `EXPERIMENTAL`, `cmd_build --target`, which maps the write kind from the extension, the golden files in `tests/data/altium/sample/`, the protocol page `docs/evidence/altium-schematic.md` and `tests/unit/test_altium_rows.py`.
- **Report of 2026-10-02 (maintainer).** KiCad 10.0.6's schematic import (GUI) read the ASCII sample: 8 components, 13 power ports, 6 net labels, and nets equal to the protocol table. The Altium 365 Viewer refused every uploaded file with a message about supported design files. No Altium Designer report yet.
- **The Viewer.** Its page lists Altium schematics (`*.SchDoc`) among the inputs, accepts one file or one project in an archive, up to 200 MB, and says nothing about the ASCII form (S-0149). Binary is Altium's default and recommended save format (S-0133). A third-party writer reports checking its "native binary" output in the Viewer (S-0143). So the binary form is very likely what the Viewer reads, and it is the only route to a check on a machine without an Altium licence.
- **The binary form (public facts, `altium_binary_facts`, recorded in `docs/formats/altium/` by task 1.2).**
  - The file is an MS-CFB compound file; readers tell it from the ASCII form by the CFB signature (S-0002, S-0131).
  - Root streams: `FileHeader` (required by KiCad's reader), `Storage` (read unconditionally by python-altium, always written by AltiumSharp) and an optional `Additional` (S-0002, S-0130, S-0131, S-0142, S-0147).
  - Each record is a 32-bit little-endian word, with the length in the low bits and the type in the top byte, then the payload. Type 0 is a property list: the ASCII line's text plus a NUL that the length counts (S-0130, S-0147, S-0148).
  - The header text is `Protel for Windows - Schematic Capture Binary File Version 5.0` (S-0130, S-0131).
  - Pins in a schematic document are text records; binary pins are a schematic-library feature (S-0131, S-0142).
  - `Storage` without images is the record `|HEADER=Icon storage` (S-0130, S-0142).
- **MS-CFB** is a normative, public specification. Its notice allows copies to develop implementations, and it is a Covered Specification of the Open Specification Promise (S-0145, S-0146). Python's standard library has no CFB codec (`msilib` was Windows-only and is removed in 3.13; PEP 594, consulted).
- **Tools.** `kicad-cli` has no schematic import and picks its schematic reader by extension (S-0132, S-0020). Its PCB import parses a CFB header and directory before it looks for PCB streams, so it is at most a smoke test of the container. `olefile` is not installed.
- **Rules for this change.** ADDED requirements only. c0032's requirements are ADDED by an active change, so changing them would be a MODIFIED delta of a requirement that does not yet exist in `openspec/specs/`. Each ADDED requirement here names the c0032 requirement it extends. Archive order: c0032 first, then c0033.

## Goals / Non-Goals

**Goals:**
- `build --target altium` writes the binary schematic by default; `--altium-format ascii` keeps c0032's bytes.
- A stdlib MS-CFB v3 writer with deterministic bytes, covering both the mini-stream path and the regular-sector path.
- An independent stdlib reader in `tests/` that checks every MS-CFB rule the writer relies on, plus a round trip to c0032's record list.
- A binary sample early, for the maintainer's Viewer check; then the build option, documentation and closing.

**Non-Goals:**
- Everything listed under Non-goals in the proposal.
- Any change to what c0032 writes in the ASCII form, including its records, layout, links, unique ids, project file, golden files and variants.

## Decisions

1. **Binary is the default; `--altium-format {binary,ascii}` selects the form.**
   - Binary is Altium's default and recommended form (S-0133) and the form the Viewer is expected to read (Context). On Monday the maintainer starts from what Altium itself writes, while ASCII stays one flag away.
   - c0032's ASCII bytes stay reachable and tested: its golden files are the ASCII build.
   - The option is a usage error with `--target kicad`, so it is never silently ignored.
   - Rejected: ASCII by default with `--altium-format binary`. It needs fewer test edits, but it keeps the default on the form the Viewer refused, and agents would rarely pass the flag.
   - Rejected: a target value `altium-binary`. The target names the tool, not the encoding, and two values would double c0032's target rules.
   - Rejected: `--format`. It reads like an output format of the envelope.
   - Rejected: choosing the form from the file name. Both forms use `.SchDoc` (S-0133).
2. **One default in one place.** `backends.altium.project.DEFAULT_FORM = "binary"` and `SchematicForm = Literal["binary", "ascii"]`. `write_project`, `build_altium` and `cmd_build` take `form` with that default.
   - Every c0032 test that reads the schematic as text passes `form="ascii"` (task 3.2).
   - Task 2.2 adds the keyword with `DEFAULT_FORM = "ascii"`, and task 3.2 flips it to `"binary"` together with the CLI option, the write kind and the test switch, so every task leaves the suite green.
   - Rejected: keeping `"ascii"` as the backend default and `"binary"` in the CLI. Two defaults for one choice are a trap.
3. **Fenolite's own CFB writer, `backends/altium/cfb.py`, with the standard library only** (`struct`). One fixed layout is written:
   - the header, then the FAT sectors, the directory, the mini FAT, the mini stream, then each large stream, every chain over consecutive sectors;
   - FAT sectors counted as a fixed point that covers themselves;
   - streams under 4096 bytes in the mini stream (a reader decides by size, so the writer has no choice), larger ones in regular sectors;
   - every entry black, which MS-CFB names as the simplest valid tree; a binary search tree over the streams built from the middle of each sorted run;
   - zero CLSIDs, state bits and timestamps, all allowed for root and streams.

   Bytes depend only on the streams.
   - Rejected: `olefile`. It is a dependency, its README documents no way to create a container, and `pyproject.toml` `dependencies` stays empty.
   - Rejected: `msilib` (Windows-only, removed).
   - Rejected: CFB version 4 (4096-byte sectors). Version 3 is what AltiumSharp writes and what the spec's example uses (S-0142, S-0145).
   - Rejected: copying the scratch probe of the format research. Code is written from Fenolite's fact page.
4. **No DIFAT sectors; refuse larger output.** The header lists 109 FAT sectors, about 7 MB of file. Beyond that, `CompoundTooLarge` is raised and the build reports `altium.schematic-too-large` (error, exit 5). A schematic that size has thousands of parts and already gets a custom sheet.
   - Rejected: DIFAT now. It is more code and tests for designs nobody builds yet. Open Question.
5. **Streams: `FileHeader` and `Storage`, nothing else.**
   - `FileHeader` holds the binary header record (exact `WEIGHT`, as in c0032), then `schdoc_records(plan)` unchanged.
   - `Storage` holds only `|HEADER=Icon storage`, with no weight key; per S-0142, Altium omits the key when there are no images.
   - Rejected: adding `Additional`. It is optional, and sources disagree on its content (S-0002 against S-0131).
   - Rejected: omitting `Storage`. One reader opens it unconditionally (S-0147).
6. **Framing reuses c0032's record text.** `binary.frame_record(fields)` is `format_record(fields)` in ASCII, a NUL, and the length word with type 0. So both forms share every key, value, order and text check, and the round trip compares records field for field.
   - Payloads stay below 65 536 bytes, where all three sources agree on the length word (S-0130, S-0142, S-0148).
   - Rejected: writing pins as binary records. The schematic-document readers expect text pins (S-0131, S-0142).
   - Rejected: a `%UTF8%` path. Texts stay 7-bit, as in c0032.
7. **The test reader is independent.** `tests/_cfb_read.py` is written from `docs/formats/altium/compound-file.md`, before `cfb.py` is read, and never imports it.
   - It checks every rule in "Compound files read back" and is itself checked against the MS-CFB worked example, rebuilt from the values in the spec's tables. That gives the reader one input that the writer did not make.
   - Rejected: a reader in `src/` (reading Altium files is v0.3).
   - Rejected: `kicad-cli pcb import` as a gate. It depends on a message text and never reads our streams.
   - Rejected: an `olefile` dev extra. It may come later if the Viewer disagrees with our reader (Open Questions).
8. **Write kind and result.** The binary schematic has the write kind `altium_schdoc_binary`, chosen by form, not by extension. `result.schematic_format` names the form. The build record keeps c0032's schema, so a rebuild that only switches the form is not an edit.
9. **Evidence.** `binary.EVIDENCE` is `INFERRED` with every `H-A-SCHBIN-*` row; `ALTIUM_BUILD_EVIDENCE` combines it and stays `INFERRED`.
   - A Viewer render is an Altium-side reading of the file, with no compile and no change order, recorded as `ALTIUM-VERIFIED(author-report; A365 Viewer; <date>; no artefact)`. The Viewer shows no version, so the tool field names the product.
   - Rows close only on the committed bytes. Only the CC0 sample is uploaded, so no licence or file question arises (`LEGAL.md` A).
10. **Sample first.** Task 2.2 commits the binary sample from `write_project(form="binary")` and the protocol's Part V, before the build option exists, so the maintainer can run the Viewer check the same evening. Reader hardening, the CLI option and documentation follow while the maintainer tests.
11. **Spec placement.** ADDED requirements in c0032's capabilities `altium-schematic-writer` and `altium-build`, each naming the c0032 requirement it extends. No `cli-contract` delta: the capabilities entry is covered by "Altium schematic format option", and `docs/cli-contract.md` is updated by task 3.3.
    - Rejected: MODIFIED deltas of c0032's requirements, because they do not exist in `openspec/specs/` until c0032 archives.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/altium/cfb.py` (new) | `write_compound(streams: Sequence[tuple[str, bytes]]) -> bytes`; `class CompoundTooLarge(ValueError)`; `SIGNATURE`, `SECTOR_SIZE = 512`, `MINI_SECTOR_SIZE = 64`, `MINI_STREAM_CUTOFF = 4096`, `MAX_FAT_SECTORS = 109`, `ENDOFCHAIN`, `FREESECT`, `FATSECT`, `NOSTREAM` |
| `src/fenolite/backends/altium/binary.py` (new) | `HEADER_TEXT` (binary header text); `STORAGE_HEADER_TEXT = "Icon storage"`; `MAX_PAYLOAD = 65535`; `header_record(count: int) -> tuple[Field, ...]`; `frame_record(fields: Sequence[Field]) -> bytes`; `file_header_stream(records: Sequence[Sequence[Field]]) -> bytes`; `storage_stream() -> bytes`; `write_schdoc_binary(plan: SheetPlan) -> bytes`; `EVIDENCE: Evidence` |
| `src/fenolite/backends/altium/project.py` (extended) | `SchematicForm`; `DEFAULT_FORM = "binary"`; `write_project(..., form: SchematicForm = DEFAULT_FORM)`; `WRITE_KINDS` gains `altium_schdoc_binary` |
| `src/fenolite/backends/altium/PROVENANCE.md` (extended) | rows for the container, framing, streams and the Viewer |
| `src/fenolite/lens/altium.py` (extended) | `build_altium(..., form: SchematicForm = DEFAULT_FORM)`; summary key `schematic_format`; row `altium.schematic-too-large`; `ALTIUM_BUILD_EVIDENCE` combined with `binary.EVIDENCE` |
| `src/fenolite/cli/cmd_build.py` (extended) | `--altium-format {binary,ascii}` (default: none, meaning `DEFAULT_FORM` with `--target altium`); write kind by form; `result.schematic_format` |
| `tests/_cfb_read.py` (new, test code) | `read_compound(data: bytes) -> dict[str, bytes]`; `class CfbError(ValueError)`; `deframe(stream: bytes) -> list[list[tuple[str, str]]]` |
| `tests/unit/backends/altium/test_cfb.py`, `test_cfb_reader.py`, `test_binary.py` (new) | writer rules, reader rules and negative controls with the spec example, framing and round trip |
| `tests/unit/lens/test_altium_binary_golden.py` (new) | binary golden files and their SHA-256 on the protocol page |
| `tests/unit/lens/test_altium_build.py`, `test_altium_issues.py`, `test_altium_determinism.py`, `test_altium_golden.py`, `tests/unit/cli/test_build_altium.py`, `test_capabilities_experimental.py` (extended) | form option, new code, binary determinism; ASCII tests pass `form="ascii"` |
| `tests/unit/test_altium_rows.py`, `tests/unit/test_format_facts.py` (extended) | stem `H-A-SCHBIN-`; tool field `A365 Viewer` |
| `tests/data/altium/sample/binary/altium_sample.SchDoc`, `altium_sample.PrjPcb` (new, authored) | binary golden sample and project copy, in `tests/data/MANIFEST.toml` |
| `docs/formats/altium/compound-file.md`, `schematic-binary.md` (new) | fact tables |
| `docs/evidence/altium-schematic.md`, `docs/altium.md`, `docs/cli-contract.md`, `docs/evidence/sources.md`, `docs/hypotheses.md`, `LEGAL-ANNEX.md`, `CHANGELOG.md` (extended) | Part V and A7, the form option, sources, rows, session row, changelog |

Layering: `cfb` and `binary` import `core`, `model` and their sibling modules only, so the `backends.<x>` row holds and `ALLOWED` is unchanged.

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0145 | https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-cfb/53989ce4-7b05-4f8d-829b-d08d6148375b ([MS-CFB] v12.0, 2024-04-23, with its section pages) | Microsoft Open Specifications notice: copyright; copies allowed to develop implementations; no trade secrets | the compound file: header, sector numbers, FAT, mini FAT and mini stream, the 4096 cutoff, directory entries, the red-black tree and its all-black form, zero CLSIDs and times, the worked example of section 3 |
| S-0146 | https://learn.microsoft.com/en-us/openspecs/dev_center/ms-devcentlp/1c24c7c8-28b0-4ce1-a47d-95fe1ff504bc (Open Specification Promise, revised 2023-02-24) | Microsoft promise (patent non-assert); page (c) Microsoft | [MS-CFB] is a Covered Specification |
| S-0147 | https://github.com/vadmium/python-altium/blob/master/altium.py | WTFPL v2 | the record length counts the NUL; `FileHeader` and `Storage` are opened unconditionally, `Additional` only when present; other streams give a warning |
| S-0148 | https://gitlab.com/kicad/code/kicad/-/blob/master/common/io/altium/altium_binary_parser.cpp and `…/altium_binary_parser.h` | GPL-2.0-or-later (facts only; nothing transcribed or followed) | the length word: low 24 bits the length, a non-zero top byte a binary record; the final NUL is checked |
| S-0149 | https://www.altium.com/documentation/altium-365/viewers/standalone-viewer | Altium documentation, all rights reserved (read for facts) | the Viewer's file types, single file or one project per archive, 200 MB limit |

Extended "used for" cells, with no new id:
- **S-0002**: the CFB signature of the binary form, its three streams and the `Storage` entry layout.
- **S-0130**: section "OLE compound document": streams, record framing, the binary header text, `Storage`.
- **S-0131** (`sch_io_altium.cpp`): binary detection by signature, the required `FileHeader`, an optional `Storage`, the header check, and binary pins only in the library path.
- **S-0133**: SCH Binary 5.0 is the recommended save format.
- **S-0142**: AltiumSharp writes schematic containers as CFB v3, the word `(type << 24) | length`, text pins, and always a `Storage` stream.
- **S-0143**: a writer reports checking its native binary output in the Viewer; altiumts lists the binary schematic as read-only.

Consulted, not registered (no requirement relies on them): PEP 594 (https://peps.python.org/pep-0594/, `msilib` removed) and olefile (https://github.com/decalage2/olefile). The GPL KiCad files are read for facts only, recorded in Fenolite's words in `docs/formats/altium/`, and the code is written from those pages (`LEGAL.md` A2, P2). If a URL is already registered at implementation time, the existing id is cited and the freed id stays unused.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-SCHBIN-CFB | An Altium reader accepts the compound file as Fenolite writes it: version 3, 512-byte sectors, zero CLSIDs and timestamps, an all-black directory tree, a root size of whole mini sectors, no DIFAT sector (S-0145) | kit request (author report, steps V1, V2 or A7 of `docs/evidence/altium-schematic.md`) on the committed binary sample | the Viewer or Altium Designer opens it without an error about the file |
| H-A-SCHBIN-FRAME | A `FileHeader` with the binary header text and length-prefixed, NUL-terminated text records, pins included, is read with all its objects (S-0130, S-0131, S-0142, S-0147, S-0148) | kit request (author report, V1, V2 or A7) | 8 components with their pin numbers, designators and comments, 13 power ports and 6 net labels are shown |
| H-A-SCHBIN-STORAGE | A `Storage` stream holding only the icon-storage header, with no `Additional` stream, is accepted (S-0130, S-0142, S-0147) | kit request (author report, V1, V2 or A7) | no message about a missing or damaged stream or image |
| H-A-SCHBIN-VIEWER | The Altium 365 Viewer renders Fenolite's binary schematic, uploaded alone and in a Zip with its project file; its outcome for the ASCII sample uploaded the same way is recorded (S-0149) | kit request (author report, V1 to V3) | V1 and V2 render the sample; the V3 message or render is recorded |
| H-A-SCHBIN-AD | Altium Designer opens the binary sample without a prompt and compiles it into exactly the six nets of the protocol table (S-0131, S-0133) | kit request (author report, A7) | no error, warning dialog or repair prompt; the Navigator nets equal the table |

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Container header, FAT, mini FAT, directory, tree, padding, cutoff, size limit | mechanical (independent test reader with negative controls; spec example); the rules `INFERRED` (S-0145) | `test_cfb.py`, `test_cfb_reader.py` |
| Framing, header text, `Storage`, same records as ASCII | mechanical (round trip, field for field); the form `INFERRED` | `test_binary.py` |
| Determinism of the binary build | mechanical | `test_altium_determinism.py` |
| `--altium-format`, write kinds, `schematic_format`, form switch, new code | mechanical | `test_build_altium.py`, `test_altium_build.py`, `test_altium_issues.py`, `test_altium_existing.py` |
| ASCII bytes unchanged | mechanical (c0032 golden files) | `test_altium_golden.py` |
| The Viewer renders the binary sample | `ALTIUM-VERIFIED(author-report; A365 Viewer; <date>; no artefact)` on the committed bytes | Part V |
| Altium Designer opens and compiles the binary sample | `ALTIUM-VERIFIED(author-report; AD <x.y>; <date>; no artefact)` | step A7 |
| The `build --target altium` envelope | `INFERRED`, experimental | `ALTIUM_BUILD_EVIDENCE` |

## Size (design-days)

| work | design-days |
|---|---|
| 1. sources, hypotheses, fact pages, provenance, row and fact tests | 0.5 |
| 2. CFB writer with the core of the test reader; framing, `Storage`, binary sample and Part V | 1.25 |
| 3. reader hardening and spec example; build option, CLI, capabilities and ASCII test switch; documentation | 1.0 |
| 4. the maintainer's report and its fixes | 0.25 |
| 5. closing | 0.25 |
| **total** | **3.25** |

The format research estimated 3.0 for the writer, reader, framing and documentation. The extra 0.25 is the report round. This is a size, not a calendar estimate. Cut order: (1) the spec-example fixture (−0.25); (2) V3 and the ASCII comparison (no saving in code, only in the protocol). Not optional: the writer, both storage paths, the reader's rule checks, the round trip, the default and the sample.

## Risks / Trade-offs

- [The Viewer still refuses] → V3 tells a format problem from an upload problem: if the binary sample is refused the same way as the ASCII one, the cause is the upload, not the form. The protocol records the exact message. KiCad's GUI import of the binary sample is a second, manual reading of the container; it is recorded as data, with no label.
- [Altium wants something we omit: a root CLSID, `Additional`, a weight in `Storage`] → Each is a row of `H-A-SCHBIN-*`; a refusal names the successor, and the fix is a few bytes in `cfb.py` or `binary.py`; `--altium-format ascii` remains for Altium Designer.
- [Writer and test reader share a misreading of MS-CFB] → The reader is written first from the fact page and is checked against the spec's own worked example; the Viewer is the independent check.
- [Binary by default changes c0032's outputs before c0032 is reported on in Altium Designer] → ASCII stays one flag away with byte-identical output; A7 checks the binary form in Altium Designer as well.
- [c0032's tests churn] → One task switches them to `form="ascii"`; the ASCII golden files do not change.
- [Size limit] → about 7 MB; refused with a clear code; DIFAT is an Open Question.

## Migration Plan

- Additive: two new modules, a keyword with a default, a CLI option, a write kind, a result key, an issue-code row, golden files, pages and tests. The ASCII bytes of c0032 are unchanged with `--altium-format ascii`.
- The default schematic of `--target altium` becomes binary. c0032 is experimental, and this lands before any release that ships it.
- Rollback: set `DEFAULT_FORM = "ascii"`, or remove the modules; nothing else depends on them.

## Open Questions

- **Default form.** Default: binary. If the Viewer and Altium Designer refuse binary but open ASCII, the fix flips `DEFAULT_FORM`.
- **DIFAT for very large schematics.** Default: refuse past 109 FAT sectors; add DIFAT when a real design needs it.
- **A second CFB reader (`olefile` in a dev extra).** Default: no; reconsider if the Viewer disagrees with our reader.
- **`WEIGHT` of the binary header.** Default: the exact record count, as in c0032. One open-source writer writes 0 (S-0142), and no reader checks it.
- **Root CLSID.** Default: zero (S-0145 allows it). Whether Altium writes one is unknown; `H-A-SCHBIN-CFB` settles whether it matters.
- **KiCad GUI import of the binary sample.** Default: recorded as data on the protocol page, with no label.
