# Altium schematic writer: the maintainer's check

This page is the protocol by which the maintainer checks, in Altium Designer, the files that
`fenolite build DESIGN.py --out DIR --target altium` writes (change c0032, capability `altium-build`,
"Altium author reports"), and the record of each report.

- What is observed is an author report: a confirmed row of `docs/hypotheses.md` gets the level
  `ALTIUM-VERIFIED(author-report; AD <major>.<minor or x>; <YYYY-MM-DD>; no artefact)`. An author report
  never promotes an operation: the `build --target altium` envelope stays `INFERRED`, and the writer stays
  experimental in `fenolite capabilities`.
- Part A uses only the committed sample files below, named by their SHA-256. Part B uses a design and
  libraries that the maintainer may use (conditions below).
- Part V uses the committed binary sample (change c0033) in the free Altium 365 Viewer, and step A7 opens
  it in Altium Designer.
- Part L (change c0034) opens the committed schematic libraries and their projects in Altium Designer.
  The Viewer refuses library files, so Part L needs Altium Designer under a licence the maintainer may
  use for it.
- `kicad-cli` cannot read a `.SchDoc` (S-0132, S-0020), so this check is the first reading of the files by
  a program other than Fenolite.

## Part A: the committed sample

The sample is the CC0 design `examples/altium_sample/design.py`. Its files are committed under
`tests/data/altium/sample/`, and `tests/unit/lens/test_altium_golden.py` checks that a fresh build gives the
same bytes and that this table names them.

| file | SHA-256 |
|---|---|
| `tests/data/altium/sample/altium_sample.PrjPcb` | `082b8c32ea1318af5576405d53fd4a3362a49760d0f48081b32ce6305c547aa0` |
| `tests/data/altium/sample/altium_sample.SchDoc` | `d4df14ba6cd1220a1b4eaed0aa266360a9364f57036312b7c36391f18125a584` |
| `tests/data/altium/sample/variants/altium_sample_lf.SchDoc` | `f5595a9dc5ecf4172cb83f4f0298fa3683fe4b59f8dcce4d28b39f816004b63c` |
| `tests/data/altium/sample/variants/altium_sample_nouid.SchDoc` | `b0fec55671a9aad36be1b9734bcfc21af8afa633978c6f8ff2a94349023877e3` |

- `altium_sample.SchDoc` is an ASCII schematic ("SCH ASCII Version 5.0") with CR LF line ends: 123 lines,
  the header and 122 records. It holds an A4 sheet, 8 components with 19 pins, 19 wire stubs, 13 power
  ports (`GND` 6, `VIN` 3, `+5V` 4) and 6 net labels (`EN`, `LED_DRV` and `LED_A`, two each). Row one
  holds `J1`, `R2`, `U2`; row two holds `D1`, `R1`, `C1`, `C2`; row three holds `U1`. The ports of `U1`
  and `U2` pins 1 and 2 alternate between a 200-mil and a 700-mil stub, so they do not overlap.
- `altium_sample_lf.SchDoc` is the same file with every CR LF replaced by LF.
  `altium_sample_nouid.SchDoc` is the same file with every `|UNIQUEID=…` field removed.
- Since change c0034 the project file lists `altium_sample.SchDoc` and, as `[Document2]`, the schematic
  library `FenoliteSample.SchLib` that the build writes beside it (committed with Part L). Part A needs
  no library: without the library file Altium lists it as missing, which is not a fault of Part A.
  `FenoliteSample.PcbLib` does not exist.
- Work on a copy of the folder, and put the two variants beside the project file when you open them.
  Check the SHA-256 values first: `Get-FileHash -Algorithm SHA256 <file>` in PowerShell, or
  `shasum -a 256 <file>`. A different value means the bytes changed on the way (for example, line ends
  converted); stop and report it.

Components of the sample, as written:

| ref | path | Design Item ID | Source | footprint | comment | unique id |
|---|---|---|---|---|---|---|
| `J1` | `J1` | `HDR2` | `FenoliteSample.SchLib` | `HDR1X2` | `HDR2` | `IPPRRKDL` |
| `R2` | `R2` | `RES` | `FenoliteSample.SchLib` | `R0603` | `10k` | `AFEHSDTW` |
| `U2` | `U2` | `DRV4` | `FenoliteSample.SchLib` | `SOT143` | `DRV4` | `AQRDAEHW` |
| `D1` | `led/D1` | `LED` | `FenoliteSample.SchLib` | `LED0603` | `red` | `QRXOCRUG` |
| `R1` | `led/R1` | `RES` | `FenoliteSample.SchLib` | `R0603` | `330` | `BCHPQUSB` |
| `C1` | `power/C1` | `CAP` | `FenoliteSample.SchLib` | `C0603` | `10uF` | `ILKHEQGD` |
| `C2` | `power/C2` | `CAP` | `FenoliteSample.SchLib` | `C0603` | `10uF` | `ENDTDWQX` |
| `U1` | `power/U1` | `LDO3` | `FenoliteSample.SchLib` | `SOT23` | `5V` | `KHUDERDO` |

`J1` has no value, so its comment is its symbol name. Every footprint is linked to
`FenoliteSample.PcbLib`.

Expected nets of the sample (compare them with the compiled nets in step A3):

| net | pins as (ref, pin) |
|---|---|
| `+5V` | (C2, 1), (R2, 1), (U1, 3), (U2, 1) |
| `EN` | (R2, 2), (U2, 4) |
| `GND` | (C1, 2), (C2, 2), (D1, 1), (J1, 2), (U1, 2), (U2, 2) |
| `LED_A` | (D1, 2), (R1, 2) |
| `LED_DRV` | (R1, 1), (U2, 3) |
| `VIN` | (C1, 1), (J1, 1), (U1, 1) |

Steps of Part A, and the rows of `docs/hypotheses.md` each settles:

| step | what to do | what to note | rows |
|---|---|---|---|
| A1 | Check the SHA-256 values of the four files. Open `altium_sample.PrjPcb`. | Any prompt, warning or error; whether `altium_sample.SchDoc` is listed among the project's source documents. | `H-A-PRJ-OPEN` |
| A2 | Open `altium_sample.SchDoc` (CR LF). | Any prompt, repair offer or error; the sheet size (A4); the 8 components with their bodies, pin numbers, designators and comments; the 13 power ports and 6 net labels. | `H-A-SCH-OPEN`, `H-A-SCH-LINEEND` |
| A3 | Compile the project ("Project » Validate PCB Project", called "Compile PCB Project" in older versions). | Every message of level error or fatal, unique-identifier messages included; the nets in the Navigator panel, compared with the table above. | `H-A-SCH-NETS`, `H-A-SCH-UID`, `H-A-PRJ-OPEN` |
| A4 | Select `U2` and open its properties and its footprint model. | Design Item ID (written `DRV4`), Source (written `FenoliteSample.SchLib`), the footprint name (written `SOT143`) and the PCB Library mode of the footprint model (expected "Library name" with `FenoliteSample.PcbLib`). | `H-A-SCH-LINK` |
| A5 | "File » Save As" with the type "Advanced Schematic ascii (*.SchDoc)" (SCH ASCII), under a new name. | Only the key names Altium added (no values), and whether the 8 `UNIQUEID` values of the table above are kept. | `H-A-SCH-UID`; data for `H-A-SCH-OPEN` |
| A6 | Open `altium_sample_lf.SchDoc`. Then open `altium_sample_nouid.SchDoc`, compile, and save it as ASCII under a new name. | Whether the LF variant opens; whether `UNIQUEID` keys appear in the saved copy of the variant without them. | `H-A-SCH-LINEEND`; data for `H-A-SCH-UID` |
| A7 | Open the binary sample `binary/altium_sample.SchDoc` (Part V) inside a copy of `binary/` with its project file, then compile the project. | Any prompt, repair offer or error when opening; every message of level error or fatal; the nets in the Navigator panel, compared with the table above. | `H-A-SCHBIN-AD`, `H-A-SCHBIN-CFB`, `H-A-SCHBIN-FRAME`, `H-A-SCHBIN-STORAGE` |

## Part V: Altium 365 Viewer opens the binary sample

The binary sample is the same design written in Altium's binary form (change c0033): a compound file with
the streams `FileHeader` and `Storage`, holding the same 122 records as the ASCII sample after a binary
header record. `tests/unit/lens/test_altium_binary_golden.py` checks that a fresh build with
`form="binary"` gives the same bytes and that this table names them. The project file is a copy of the
ASCII sample's project file.

| binary file | SHA-256 |
|---|---|
| `tests/data/altium/sample/binary/altium_sample.PrjPcb` | `082b8c32ea1318af5576405d53fd4a3362a49760d0f48081b32ce6305c547aa0` |
| `tests/data/altium/sample/binary/altium_sample.SchDoc` | `80ad9ea254cf57522527128fbe4e1a0cafb18e1eb8ee0610f341548672ee1c88` |

- The free Altium 365 Viewer (S-0149) needs no Altium licence. It takes one file, or one project in a Zip
  archive, up to 200 MB.
- Upload only Fenolite's authored sample files: the two files of `binary/` and, for V3, the ASCII
  `altium_sample.SchDoc` of Part A. Never upload any other design. The sample is CC0, so no licence or
  file question arises (`LEGAL.md`, block A).
- Check the SHA-256 values before uploading, as in Part A.

| step | what to do | what to note | rows |
|---|---|---|---|
| V1 | Upload `binary/altium_sample.SchDoc` alone. | The Viewer's message, word for word, or what it renders: the sheet, the 8 components with pin numbers, designators and comments, the 13 power ports and the 6 net labels. | `H-A-SCHBIN-VIEWER`, `H-A-SCHBIN-CFB`, `H-A-SCHBIN-FRAME`, `H-A-SCHBIN-STORAGE` |
| V2 | Upload a Zip archive holding the two files of `binary/` (the project file and the binary schematic). | The same as V1. | `H-A-SCHBIN-VIEWER`, `H-A-SCHBIN-CFB`, `H-A-SCHBIN-FRAME`, `H-A-SCHBIN-STORAGE` |
| V3 | Upload the ASCII `altium_sample.SchDoc` of Part A alone, as in V1. | The same as V1. A refusal with the same message as V1 points to the upload, not to the form. | data for `H-A-SCHBIN-VIEWER` |

A Viewer report names the tool `A365 Viewer`: the Viewer shows no version.

## Part B: a design and libraries the maintainer may use

Part B is recorded only when every condition of `LEGAL.md`, block A, holds:

- the design and the libraries are ones the maintainer created or may use for this purpose (never an
  employer's or a client's files: P3);
- Altium Designer runs under a licence the maintainer may use for this purpose (never an employer's
  licence used to study the tool for Fenolite: P4);
- only generic outcomes are recorded: no file, screenshot, path, design name, library name or identifier
  of any organisation, and no file opened or saved in the session enters the repository.

When a condition does not hold, nothing of Part B is recorded; Monday's use of the writer does not depend
on it.

| step | what to do | what to note | rows |
|---|---|---|---|
| B1 | Build the design with `--target altium --confirm`. Make its libraries available (beside the project, or installed). Add a new PCB document to the project and save the project. Run "Design » Update PCB Document", then "Validate Changes" and "Execute Changes". | The components and nets added; every change marked invalid (red cross), with its message in generic terms; the key names Altium added to the project file. | `H-A-SCH-ECO`, `H-A-PRJ-KEEP` |
| B2 | Change one value in the design script and rebuild with `--target altium --confirm` (the project file is kept). Compile, and run the change order again. | The changes listed (expected: one comment changed, nothing added or removed); whether the project still lists both documents. | `H-A-SCH-RELINK`, `H-A-PRJ-KEEP` |
| B3 | On a copy, run "Tools » Update From Libraries" with full replacement. On another copy, run it with "Replace selected attributes" and graphical attributes off. | Parts listed as `<Not Found>`; whether the bodies were replaced and how many pins were left unconnected; whether every net is kept after the selected-attributes update. | `H-A-SCH-UPDATE` |

## Part L: the schematic libraries in Altium Designer

Change c0034 writes one schematic library per library that the lib ids name. The committed files are
the sample's generic library and the build of `examples/altium_kicad/design.py`, whose symbols come
from its authored CC0 `FenoliteDemo.kicad_sym`. `tests/unit/lens/test_altium_schlib_golden.py` checks
that fresh builds give these bytes and that this table names them.

| library or project file | SHA-256 |
|---|---|
| `tests/data/altium/sample/FenoliteSample.SchLib` | `f071c2fe861fb5a80fb219ccdc8a207b2c6429094fcf4a3002f366109912fdff` |
| `tests/data/altium/sample/altium_sample.PrjPcb` | `082b8c32ea1318af5576405d53fd4a3362a49760d0f48081b32ce6305c547aa0` |
| `tests/data/altium/sample/binary/altium_sample.PrjPcb` | `082b8c32ea1318af5576405d53fd4a3362a49760d0f48081b32ce6305c547aa0` |
| `tests/data/altium/kicad_example/altium_kicad.PrjPcb` | `0a6f26d9afc01438b641d182ab62d40b3a57fc46773db2ac09ae2a8827808296` |
| `tests/data/altium/kicad_example/altium_kicad.SchDoc` | `6e7366b3be51414f7649b4354aa61a2c4636d416ead64b7b0ceb6b2cabf5ff44` |
| `tests/data/altium/kicad_example/altium_kicad.SchLib` | `ccdfe416efa57324236b30f0e7e73c0c9a3bbd229babf9aae150427feb7ed6b4` |

- `FenoliteSample.SchLib` holds the six generic symbols of the sample (`CAP`, `DRV4`, `HDR2`, `LDO3`,
  `LED`, `RES`), each of one part with the passive pins its components use, the designator `<prefix>?`
  and the footprint link. Put it beside `binary/altium_sample.PrjPcb` (or the ASCII project) to open
  the project of Part A or V with its library.
- `altium_kicad.SchLib` holds `CONN2` (two pins on the left), `R_V` (an upright resistor: one pin up,
  one down, names hidden), `MCU8` (pins on four sides; `~{RST}` written `R\S\T\` with an inverted
  edge, `CLK` with a clock edge, `~{OE}` inverted, and the hidden pin `8`) and `DUAL_OPAMP` (parts A and
  B of three pins each, and the Part Zero power pins `8` VCC and `4` VEE). `DUAL_OPAMP` and `MCU8` link
  the footprint `SOIC8` of `FenoliteDemo` (no such library exists). Every body is a synthesised
  rectangle.
- `altium_kicad.SchDoc` is the binary schematic of the example: `U1` is placed twice (parts A and B),
  the up and down pins have vertical stubs, and its nets are those of the table below.
- `kicad-cli sym upgrade` converts both libraries with the written pins and units on 10.0.6 and 9.0.9
  (`tests/kicad/altium/test_schlib_oracle.py`); KiCad is not Altium, so that settles only
  `H-A-SCHLIB-KICAD` and `H-A-SCHLIB-KICAD9`.

Expected nets of the example (pins `U2` 2, 4 and 8 are left unconnected):

| net | pins as (ref, pin) |
|---|---|
| `FB_A` | (U1, 1), (U1, 2), (U1, 5) |
| `FB_B` | (U1, 6), (U1, 7), (U2, 3) |
| `GND` | (J1, 2), (R2, 2), (U1, 4), (U2, 7) |
| `OE_N` | (R2, 1), (U2, 5) |
| `SIG` | (R1, 2), (U1, 3) |
| `VIN` | (J1, 1), (R1, 1), (U1, 8), (U2, 1), (U2, 6) |

Part L is recorded only when every condition of Part B holds: Altium Designer runs under a licence the
maintainer may use for this purpose (`LEGAL.md`, block A, P3 and P4). A result obtained with a licence
the maintainer may not use for it, such as an employer's, is not recorded, and the rows stay pending.
Only generic outcomes and key names are recorded; no file opened or saved in the session enters the
repository. Check the SHA-256 values first and work on copies.

| step | what to do | what to note | rows |
|---|---|---|---|
| L1 | Open `FenoliteSample.SchLib` and `altium_kicad.SchLib`. | Any prompt, repair offer or error; the components listed in the SCH Library panel and their descriptions. | `H-A-SCHLIB-OPEN`; `H-A-SCHLIB-SECTIONKEY` when a library with a keyed symbol is added |
| L2 | In `altium_kicad.SchLib`, look at each component's pins (Pin Editor) and parts. | Per pin: number, name, electrical type, direction, length, shape (`MCU8` pins 2, 3 and 5) and the hidden pin `8` of `MCU8`; parts A and B of `DUAL_OPAMP` and whether pins `8` and `4` show on both parts. | `H-A-SCHLIB-PIN`, `H-A-SCHLIB-PARTS` |
| L3 | Open the footprint model of `DUAL_OPAMP` and of `RES`. | The footprint name (written `SOIC8`, `R0603`) and the PCB Library mode with its library (expected "Library name" with `FenoliteDemo` and `FenoliteSample.PcbLib`). | `H-A-SCHLIB-IMPLIDX`, `H-A-SCH-LINK` |
| L4 | Open `altium_kicad.PrjPcb` with its schematic and library beside it, check that the library is listed under the project, and compile ("Project » Validate PCB Project"). Do the same with `binary/altium_sample.PrjPcb` and `FenoliteSample.SchLib`. | Whether each library is listed as a project document; every message of level error or fatal; the nets in the Navigator panel, compared with this table and Part A's; whether `U1` compiles as one component of two parts. | `H-A-SCHLIB-PRJ`, `H-A-SCHLIB-SCHDOC`, `H-A-SCHLIB-MULTIPART` |
| L5 | On a copy of each project, run "Tools » Update From Libraries" with full replacement. | Components listed as not found; whether any pin moved off its stub; the nets after the update, compared with the tables. | `H-A-SCHLIB-UPDATE`, `H-A-SCHLIB-PRJ` |
| L6 | Save a copy of each library under a new name in Altium. | Only the names of the keys Altium added or removed in `FileHeader` and in a component's records (no values). | data for `H-A-SCHLIB-OPEN` |

## Recording a report

- A report gives the Altium Designer version as `AD <major>.<minor>`, or `A365 Viewer` for Part V, the
  date, and one outcome per step in generic format terms, under "Reports" below. A Viewer refusal is
  recorded with the Viewer's message.
- A confirmed row gets `ALTIUM-VERIFIED(author-report; AD <major>.<minor or x>; <YYYY-MM-DD>; no artefact)`,
  or `ALTIUM-VERIFIED(author-report; A365 Viewer; <YYYY-MM-DD>; no artefact)` for a Viewer step.
- A refuted row keeps its id, its result starts with `refuted; superseded by <id>-2`, and a successor row
  states what Altium did.
- Without a report, a row stays `INFERRED` with a result that starts with `pending (author report)`.
- `tests/unit/test_altium_rows.py` checks the form of these rows.

## Reports

### 2026-10-02, `A365 Viewer`, Part V

- Tool: the free Altium 365 Viewer (web), `A365 Viewer`; it shows no version.
- File: the committed binary sample `binary/altium_sample.SchDoc`, uploaded alone from a local copy whose
  SHA-256 equals the value in Part V. Only Fenolite's authored sample was uploaded.

Outcome per step:

- **V1.** Opened and rendered, with no error about the file. One sheet in the expected two-row layout:
  all 8 components with generic bodies, pin numbers, designators and comments (J1 HDR2, R2 10k, U2 DRV4,
  D1 red, R1 330, C1 10uF, C2 10uF, U1 5V); the power ports of VIN, GND and +5V in their bar and ground
  styles; the net labels of EN, LED_DRV and LED_A on their wire stubs. Confirms `H-A-SCHBIN-CFB`,
  `H-A-SCHBIN-FRAME` and `H-A-SCHBIN-STORAGE`; `H-A-SCHBIN-VIEWER` also needs V2.
- **V2.** Not reported.
- **V3.** Observation of the same day, made before the binary sample existed: the Viewer refused every
  ASCII sample upload with the generic message "Please ensure all supported design or manufacturing
  files are included in the upload. Note that library files are not currently supported." Recorded as
  data for `H-A-SCHBIN-VIEWER`.
- **A7.** Not checked: the Viewer neither compiles a project nor runs a change order, so
  `H-A-SCHBIN-AD` stays pending.

- The ASCII refusal concerns the Viewer only. The `H-A-SCH-*` and `H-A-PRJ-*` rows concern Altium
  Designer (Part A) and stay pending; no writer behaviour changes for it.
- The report names no fault of the binary sample. It was made on the earlier binary bytes, SHA-256
  `2dada3a9095802ae98c4ab77cda9f4dda907e3fc6daa03dfd1af98b159e33007`, laid out in two rows. c0032
  task 4.2 later changed only the stub lengths and positions of the records (same records, keys,
  container and framing), so the confirmed rows stand; V2 and A7 use the bytes of Part V above.

### 2026-10-02, KiCad 10.0.6 schematic import (supporting data, not Altium)

- Tool: KiCad 10.0.6 on macOS, schematic editor, "Import non-KiCad schematic" (the GUI importer;
  `kicad-cli` still cannot read a `.SchDoc`, S-0020). File: the committed ASCII sample
  `altium_sample.SchDoc` (CR LF), from a local copy of Part A.
- Outcome: it opened. It showed the 8 components with their designators and comments, the 13 power
  ports and the 6 net labels, and the nets read from the drawing equal the table of expected nets
  exactly: `J1` VIN and GND; `R2` +5V and EN; `U2` +5V, GND, LED_DRV and EN; `D1` GND and LED_A; `R1`
  LED_DRV and LED_A; `C1` VIN and GND; `C2` +5V and GND; `U1` VIN, GND and +5V.
- Cosmetic fault: the power ports of adjacent pins overlap, on `U1` and `U2` pins 1 and 2 (100 mil
  apart). Fixed by staggering the port stubs of adjacent pins (c0032 task 4.2, fact in
  `docs/formats/altium/schematic-ascii.md`); the files above are the rebuilt ones.
- KiCad also marks the free end of each net-label stub with its dangling-end square. That is KiCad's
  marker for a wire end that touches nothing else; the stub ends where it should, so nothing changes.
- KiCad is not Altium: this import is supporting data for the writer's geometry and settles no
  `H-A-*` row.

### Status of Part A and Part B

- No Altium Designer run of Part A or Part B has been reported. Every `H-A-SCH-*` and `H-A-PRJ-*` row
  stays `INFERRED` with `pending (author report)`.
- No Part L report exists: the `H-A-SCHLIB-*` rows other than the two oracle rows stay `INFERRED` with
  `pending (author report)`. The maintainer may hold only a work licence, whose results are not
  recorded (`LEGAL.md`, P4).
- The Altium 365 Viewer's refusal of the ASCII files (V3 above) concerns the Viewer only.
