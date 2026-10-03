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
- Part N (change c0036) compiles the committed no-connect example in Altium Designer and uploads its
  binary schematic to the Viewer.
- Part H (change c0037) opens the committed hierarchy sample in Altium Designer: a top sheet, two module
  sheets and one signal harness.
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
| `tests/data/altium/kicad_example/altium_kicad.SchDoc` | `10c95992c6cab223fa2125493d07772a79855014bcc64553d4c757dbd88ed34a` |
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

## Part N: no-connect directives in Altium Designer

Change c0036 writes one No ERC directive (record 22, "Suppress All Violations") at the electrical end
of each pin that the design marks with `no_connect(...)`, and no wire for it. The committed files are
the build of `examples/altium_kicad/no_connect.py`, whose symbols come from the authored CC0
`FenoliteDemo.kicad_sym`. `tests/unit/lens/test_altium_no_connect_golden.py` checks that a fresh build
gives these bytes and that this table names them.

| project, library or schematic file | SHA-256 |
|---|---|
| `tests/data/altium/no_connect/altium_no_connect.PrjPcb` | `72149d0bbaebd6fc87c9e1535b28db504b3d2a40b67986d4c81243d997a31c81` |
| `tests/data/altium/no_connect/altium_no_connect.SchDoc` | `7cac02697be2a7b37dccaa0e2436786fb5dc55c550c0c03fa428197fe2aaaf4f` |
| `tests/data/altium/no_connect/altium_no_connect.SchLib` | `7ac872c78cebb8977eaaff78c29135024c4e5617991190644131c0290d990cdb` |
| `tests/data/altium/no_connect/ascii/altium_no_connect.SchDoc` | `dd04eacceb2201fb3d8b168165bde92fb6a2cf1aae581609557b09d49d69b5c3` |

- The design holds `J1` (`CONN2`), `R1` (`R_V`) and `U1` (`MCU8`) on the nets `VIN` (J1 1, R1 1, U1 1,
  U1 6), `GND` (J1 2, U1 7) and `OE_N` (R1 2, U1 5).
- `U1` pins `2` (`~{RST}`, an input), `4` (`OUT`, an output) and `8` (`TP`, a passive pin that the symbol
  hides) are marked: each has a directive at its electrical end and no wire. The directive of pin `8`
  therefore sits at the end of a pin that the sheet does not draw.
- `U1` pin `3` (`CLK`, an input) is left open and unmarked on purpose. It is the positive control: a
  compiler that reports nothing for pin `3` says nothing about the directives.
- The three directives are the last records of the schematic, each with the keys `RECORD=22`,
  `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y`, `COLOR=255`, `ISACTIVE=T`, `SUPPRESSALL=T` and
  `SYMBOL=Thin Cross` (`docs/formats/altium/schematic-ascii.md`, "No ERC directive").
- The footprints name `FenoliteDemo:<name>`, a library that does not exist, so no PCB library or PCB
  document is written; footprint messages are not part of this check.

Expected compiler messages: none that names `U1` pin `2`, `4` or `8`, and a floating-input message for
`U1` pin `3`.

Part N is recorded under the conditions of Part B: Altium Designer runs under a licence the maintainer
may use for this purpose (`LEGAL.md`, block A, P3 and P4), only Fenolite's authored files are opened or
uploaded, only generic outcomes are recorded, and no file opened or saved in the session enters the
repository. Check the SHA-256 values first and work on copies.

| step | what to do | what to note | rows |
|---|---|---|---|
| N1 | Put `altium_no_connect.PrjPcb`, `altium_no_connect.SchDoc` (binary) and `altium_no_connect.SchLib` in one folder; open the project and the schematic in Altium Designer. | Any prompt, repair offer or error; whether a No ERC directive shows at the ends of `U1` pins `2`, `4` and `8`, and its mode in the Properties panel (expected "Suppress All Violations"). | `H-A-SCH-NC-RECORD` |
| N2 | Compile the project ("Project » Validate PCB Project"). | Every message that names `U1`, with its pin. Expected: none for pins `2`, `4` and `8`; a floating-input message for pin `3`. | `H-A-SCH-NC-ERC` |
| N3 | Repeat N1 and N2 on a copy of the folder with `ascii/altium_no_connect.SchDoc` in place of the binary schematic. | The same notes as N1 and N2, for the ASCII form. | `H-A-SCH-NC-RECORD`, `H-A-SCH-NC-ERC` |
| N4 | Upload the binary `altium_no_connect.SchDoc` alone to the Altium 365 Viewer. | Whether the three directives are drawn as crosses at the marked pins. | `H-A-SCH-NC-VIEWER` |

## Part H: sheets per module and harnesses in Altium Designer

Change c0037 writes, with `--altium-sheets modules`, a top sheet with one sheet symbol per top-level
module, one sheet per module with ports, and signal harnesses drawn with Altium's own harness objects. The
committed files are the build of `examples/altium_hier/design.py` (CC0-1.0, authored): `J1` on the top
sheet, `U1` and `C1` in the module `mcu`, `U2`, `C2` and `R1` in the module `flash`, and the harness `SPI`
with the entries `CS`, `MISO`, `MOSI` and `SCK`. `tests/unit/lens/test_altium_hier_golden.py` checks that a
fresh build gives these bytes and that this table names them.

| sheet, library or project file | SHA-256 |
|---|---|
| `tests/data/altium/hier/FenoliteHier.SchLib` | `3013953bfd734233a33dbd17396d1b3049c2b215f13e46d2a0c4c9d75c0c8a4a` |
| `tests/data/altium/hier/altium_hier.PrjPcb` | `ae491c3759917f8094fc3480d61e9d15a52210d67d5e8970c724f5d7216d9b60` |
| `tests/data/altium/hier/altium_hier.SchDoc` | `47ade2caca275e6d5ac7bfab73b71dc396b2c49dc76e7a58d089f6ea4b594e4d` |
| `tests/data/altium/hier/altium_hier_flash.Harness` | `83c0f6606a5ac53075a7c5b8c2a2e785cb56eeb197ec9e10a920ede54c8da733` |
| `tests/data/altium/hier/altium_hier_flash.SchDoc` | `7c51ef59965632ae74686b5c868bcb8d4c89c64b3f097a9a1dd6d72ee87d8b61` |
| `tests/data/altium/hier/altium_hier_mcu.Harness` | `83c0f6606a5ac53075a7c5b8c2a2e785cb56eeb197ec9e10a920ede54c8da733` |
| `tests/data/altium/hier/altium_hier_mcu.SchDoc` | `eed364bf61d5be9f4771fba64edd5dd6c8a0e2728573fa95bb056bc3f52d5ffe` |

- These are the files rebuilt after the reports of 2026-10-03 (below). The top sheet changed after the
  first report, and the project file after each: it now lists the top sheet, the two module sheets, the
  library and the two `.Harness` files, in that order (`H-A-SCH-HIER-ORDER`). The two module sheets,
  their `.Harness` files and the library are the bytes that the first report checked.
- `altium_hier.SchDoc` is the top sheet: the sheet symbols `flash` (entries `FLASH_WP` and `SPI`) and
  `mcu` (entries `FLASH_WP`, `RESET_N` and `SPI`), and `J1`. Each net entry has a short wire with a net
  label, and the labels join the two symbols. One signal harness line joins the entry `SPI` on the right
  side of `flash` to the entry `SPI` on the left side of `mcu`; the top sheet holds no harness connector
  and no label of an `SPI_*` net.
- `altium_hier_mcu.SchDoc` holds the ports `FLASH_WP`, `RESET_N` and `SPI`; `altium_hier_flash.SchDoc`
  holds the ports `FLASH_WP` and `SPI`. The port `SPI` has a harness block beside it: a harness line, a
  connector with four entries, and a labelled wire on each entry.
- The harness records are in the stream `Additional` of each sheet; the two `.Harness` files, one per
  module sheet, hold the line `SPI=CS,MISO,MOSI,SCK`, and the project file lists the sheets and then
  the harness files. The top sheet has no connector and so no `.Harness` file.
- `VDD` and `GND` are power ports on all three sheets and get neither a port nor a sheet entry.
  `FLASH_HOLD_N` stays on the `flash` sheet.
- The libraries `FenoliteHier.SchLib` (generic symbols, written) and `FenoliteHier.PcbLib` (not written)
  are stand-ins: a change order into a blank PCB document reports missing footprints, which is expected.
- There is no oracle: `kicad-cli` reads no schematic document. Fenolite's own readback
  (`tests/_altium_read.py`, `nets_from_project`) finds the nets below in both forms, which proves only
  that the written geometry is consistent with the fact pages.

Expected nets of the sample:

| net | pins as (ref, pin) |
|---|---|
| `FLASH_HOLD_N` | (R1, 2), (U2, 7) |
| `FLASH_WP` | (U1, 2), (U2, 3) |
| `GND` | (C1, 2), (C2, 2), (J1, 2), (U1, 4), (U2, 4) |
| `RESET_N` | (J1, 3), (U1, 1) |
| `SPI_CS` | (U1, 3), (U2, 1) |
| `SPI_MISO` | (U1, 5), (U2, 2) |
| `SPI_MOSI` | (U1, 6), (U2, 5) |
| `SPI_SCK` | (U1, 7), (U2, 6) |
| `VDD` | (C1, 1), (C2, 1), (J1, 1), (R1, 1), (U1, 8), (U2, 8) |

Part H is recorded under the conditions of Part B and Part L (`LEGAL.md`, block A, P3 and P4): a licence
the maintainer may use for Fenolite, only Fenolite's authored or built files opened, generic outcomes
only, no artefact. Check the SHA-256 values first and work on copies. Steps H6 and H7 build their files
with `fenolite build <script> --out <folder> --target altium --altium-sheets modules --confirm`.

| step | what to do | what to note | rows |
|---|---|---|---|
| H1 | Open `altium_hier.PrjPcb` and each of the three sheets. | Any prompt, repair offer or error. Expected: two sheet symbols with five entries in all on the top sheet, three ports on `mcu` and two on `flash`. | `H-A-SCH-HIER-OPEN`, `H-A-SCH-HIER-PRJ` |
| H2 | Look at the two harness blocks (one on each module sheet) and at the harness line on the top sheet. | Whether each harness connector shows with its entries `CS`, `MISO`, `MOSI` and `SCK` and the type `SPI`, and whether a harness line joins it to its port; whether one harness line joins the two `SPI` sheet entries on the top sheet; whether the two `.Harness` files are listed under the project. | `H-A-SCH-HARN-OPEN`, `H-A-SCH-HARN-FILE` |
| H3 | Compile the project ("Project » Validate PCB Project"). | The sheet tree of the Projects panel (it also settles the project row of H1) and every message. Expected: `altium_hier.SchDoc` on top with two children, and no message about ports, sheet entries, harnesses, duplicate or multiple net names or a conflicting harness definition; whether Altium rewrote a `.Harness` file or made one for the top sheet. | `H-A-SCH-HIER-COMPILE`, `H-A-SCH-HARN-FILE` |
| H4 | List the nets in the Navigator panel. | Expected: exactly the nine net names of the table above, each with its pins; `VDD` and `GND` on all three sheets; each `SPI_*` net with one pin on each module sheet. | `H-A-SCH-HIER-NAMES`, `H-A-SCH-HARN-NETS` |
| H5 | Add a new PCB document to the project and run "Design » Update PCB Document". | Whether the change order adds six components and nine nets and "Validate Changes" passes, apart from the missing footprints of the stand-in library. | `H-A-SCH-HIER-ECO` |
| H6 | Build `examples/altium_hier/partial.py` (a fifth entry `HOLD` whose net stays on the `flash` sheet, so it is wired on no sheet), open its project and compile it. | Every message that names the entry `HOLD`, with its level (expected: the warning "Unconnected Harness Entry", once on each module sheet); whether the nets still equal the table above. | `H-A-SCH-HARN-UNUSED` |
| H7 | Build `examples/altium_hier_board/design.py`, open its project on a fresh copy, compile it ("Project » Validate PCB Project") without opening any dialog, and from the top sheet `altium_hier_board.SchDoc` run "Design » Update PCB Document altium_hier_board.PcbDoc". | First the Projects panel: whether `altium_hier_board_driver.SchDoc` and `altium_hier_board_led.SchDoc` both show under the top sheet (the document order of the project file, with the variants below); every compile message. Then whether the change order proposes no component change and no net change: the parts of the modules `driver` and `led` link through their sheet symbols. Component classes, rooms and supply-net rules that Altium derives from the sheets are expected as additions and are not a fault. | `H-A-SCH-HIER-ECO`, `H-A-SCH-HIER-ORDER` |

Step H7 was refuted as first built (first report of 2026-10-03 below): the second module sheet was
outside the hierarchy. The second report found the cause in the project file: with Fenolite's minimal
file the schematic documents have to be listed first and together (`H-A-SCH-HIER-ORDER`). The example is
rebuilt with that order and without the padding of small sheets that the first follow-up had added. The
project file of the rebuilt example is byte for byte the one of variant l, which the maintainer saw
working, and its sheets are those of the first build. Its PCB document is not the one of variant l: it
holds `CHANNELOFFSET` per sheet and whatever later changes write into a PCB document. Open: the change
order of H7 on the rebuilt example. Expected:
after a compile on a fresh copy, without any dialog, both module sheets are children of the top sheet,
and the change order proposes no component change and no net change.

Variants of the example told the possible causes apart; each is a whole project folder and changes one
thing. Variants a to c are the files of the first build, where `led` was outside the hierarchy, with one
change each. Variants d to g were built from copies of the script with one edit each, by the writer of
the first build, without padding. For each variant only the Projects panel was noted, on a fresh copy,
after the project is opened and after "Project » Validate PCB Project", without any dialog: which
sheet, if any, is outside the hierarchy. The outcomes are in the second report below.

| variant | the one change | small sheet | what it tells |
|---|---|---|---|
| a | first build plus a `.PrjPcbStructure` file with the lines Altium wrote | `led` | whether a structure file alone puts `led` under the top sheet; then also whether `D1` is in the compiled design (the change order of H7) |
| b | first build with a `DocumentUniqueId` in every document section of the project file | `led` | whether document ids in the project file matter |
| c | first build with the top sheet and the sheet `led` padded to 4096 bytes by one hidden sheet parameter; the PCB document is the first build's | none | whether the size of the sheet is the cause (`H-A-SCHBIN-MINI`, since refuted) |
| d | `U1` moves to the module `led`, so `driver` holds `R1` alone | `driver` | if `driver` is now outside and `led` is a child, the small sheet is the cause, whatever its name, its symbol's position and size or its place in the project file |
| e | the module `led` is renamed `a_led`, so its sheet symbol, its sheet entry and its document come first | `a_led` | if `a_led` is still outside, neither the order of the sheet symbols, nor the order of the documents, nor being the last child listed is the cause |
| f | no board, so no PCB document | `led` | if `led` is still outside, the PCB document and its `CHANNELOFFSET` are not involved |
| g | `D1` sits between the two power nets, so no net crosses a module: no port, no sheet entry | `led` | if `led` is still outside, ports and sheet entries are not involved |

Six more variants hold the sheets, libraries and PCB document of the first build and change the project
file only. The project file that Altium saved in the first session stays with the maintainer, outside
the repository; a variant that uses it is described here by what it holds.

| variant | project file | what it tells |
|---|---|---|
| h | the project file Altium saved in full, with the structure file Altium wrote | whether Altium's own two files give the whole hierarchy on a fresh copy |
| j | the saved project file alone | whether the structure file is needed for that |
| k | Fenolite's minimal file with the whole `[Design]` section of the saved file | whether a key of `[Design]` is what the minimal file lacks |
| l | Fenolite's minimal file with the documents in the order top sheet, `driver`, `led`, PCB document, PCB library, schematic library | whether the order of the documents is the cause (`H-A-SCH-HIER-ORDER`) |
| m | Fenolite's minimal file with `HierarchyMode=0` under `[Design]` | whether that key alone is what the minimal file lacks |
| n | the saved project file with every `[Document<n>]` section cut down to `DocumentPath` | whether the per-document keys of the saved file matter |

## Recording a report

- A report gives the Altium Designer version as `AD <major>.<minor>`, or `A365 Viewer` for Part V, the
  date, and one outcome per step in generic format terms, under "Reports" below. A Viewer refusal is
  recorded with the Viewer's message.
- A confirmed row gets `ALTIUM-VERIFIED(author-report; AD <major>.<minor or x>; <YYYY-MM-DD>; no artefact)`,
  or `ALTIUM-VERIFIED(author-report; A365 Viewer; <YYYY-MM-DD>; no artefact)` for a Viewer step.
- A refuted row keeps its id, its result starts with `refuted; superseded by <successor id>` (`<id>-2`,
  or the id of the row that states the cause found), and the successor row states what Altium did.
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

### 2026-10-03, `AD 26.5`, steps A7, L4 and L5

- Tool: Altium Designer 26.5.0 under a trial licence on the maintainer's own PC, a licence the maintainer
  may use for Fenolite (`LEGAL.md`, block A). Label: `ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03;
  no artefact)`.
- Files: the binary sample `binary/altium_sample.PrjPcb` and `altium_sample.SchDoc` with
  `FenoliteSample.SchLib` beside them, and the blink project of `docs/evidence/altium-pcb.md`; Fenolite's
  authored samples only. No file opened or saved in the session enters the repository.

Outcome per step:

- **A7.** The project file opens and the binary schematic opens. The project compiles with no error, and
  the nets are as written. Confirms `H-A-PRJ-OPEN` (with the binary schematic) and `H-A-SCHBIN-AD`.
- **L4.** The sample project with `FenoliteSample.SchLib` compiles with no error. The blink project
  compiles with ERC messages that follow from its example circuit (`VIN` has one pin; unconnected inputs,
  `U1` pins 11 and 12 among them). The `altium_kicad` project is not reported, so `H-A-SCHLIB-SCHDOC` and
  `H-A-SCHLIB-MULTIPART` stay pending.
- **L5.** "Tools » Update From Libraries" works with the generated `FenoliteSample.SchLib`. Confirms
  `H-A-SCHLIB-PRJ`. Whether any pin moved and the nets after the update are not reported, so
  `H-A-SCHLIB-UPDATE` stays pending with this observation.
- **Change order.** "Design » Update PCB Document" ran without error on the blink project against
  Fenolite's own `blink.PcbDoc`: every component matched, no difference was reported and "Validate
  Changes" passed (`docs/evidence/altium-pcb.md`, step D3). Recorded as data for `H-A-SCH-ECO`, which is
  about a new PCB document and stays pending.
- **Not checked:** the change order into a new PCB document (Part B; `H-A-SCH-ECO`, `H-A-SCH-RELINK`,
  `H-A-PRJ-KEEP`), the ASCII
  form in Altium Designer (Part A, steps A1 to A6; the `H-A-SCH-*` rows) and steps L1 to L3 and L6.

### 2026-10-03, `AD 26.5`, Part H

- Tool: Altium Designer 26.5 under a trial licence on the maintainer's own PC, a licence the maintainer
  may use for Fenolite (`LEGAL.md`, block A). Label: `ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03;
  no artefact)`.
- Files: Fenolite's authored and built files only: the first build of the hierarchy sample (top sheet
  SHA-256 `f82dccdb8b0c6fc796e65b7e9b434b9a6367d0c0370c5554b540cf749988409d`, project file
  `c47f551a04d36f53a86a1ced92812abc20c12f6bac5cbd0ff8cd44239eb0a63a`, with a third file
  `altium_hier.Harness`; the module sheets and the library as in Part H above), the build of
  `partial.py` and the build of `examples/altium_hier_board/design.py` (top sheet
  `8794466c89250a0bd6b734399c38675a6c874103df44ea69072855f3523cfb7c`, sheet `led`
  `7cb9fba1e489f3280c974b0c7b31d647f512447f9769460d59faaa1ffc759078`, PCB document
  `f43f4f5ec70161f651ff37485b06274aa2606b06a29c245b32ae76d8d2130cb5`). No file opened or saved in the
  session enters the repository.

Outcome per step:

- **H1.** The three sheets open. The two sheet symbols and their entries show, and so do the ports.
  Confirms `H-A-SCH-HIER-OPEN`.
- **H2.** The harness connectors, their entries and the harness lines show. Confirms
  `H-A-SCH-HARN-OPEN`. Whether the `.Harness` files were listed is not reported separately.
- **H3.** "Compile successful, no errors found", with four warnings on the top sheet
  `altium_hier.SchDoc`, one per SPI member: `Nets Wire SPI_CS has multiple names (Net Label SPI_CS, Sheet
  Entry flash-SPI.CS(Passive), Sheet Entry mcu-SPI.CS(Passive))`, and the same for `SPI_MISO`, `SPI_MOSI`
  and `SPI_SCK`. No message about a port, about a sheet entry without a port, or about a conflicting
  harness definition. So Altium uses the hierarchical scope without a project key and reads both sheet
  symbols, but the criterion of `H-A-SCH-HIER-COMPILE` (no message about net names) is not met: on the
  top sheet each wire had a net label and, from the harness block beside each sheet entry, the names
  `SPI.CS` and so on. No such warning names a module sheet, where a port has the same block.
  - Fix: the top sheet now joins the two `SPI` sheet entries by one signal harness line and holds no
    block and no `SPI_*` label (`docs/formats/altium/schematic-binary.md`, "Harness lines between sheet
    symbols"). The files of Part H above are the rebuilt ones. `H-A-SCH-HIER-COMPILE` stays pending
    until H3 is repeated on them.
  - Whether Altium rewrote a `.Harness` file is not reported, so `H-A-SCH-HARN-FILE` stays pending with
    the observation that no conflicting definition was reported. Whether the Projects panel showed two
    children is not reported either, so `H-A-SCH-HIER-PRJ` stays pending.
- **H4.** Not reported in detail: `H-A-SCH-HIER-NAMES` and `H-A-SCH-HARN-NETS` stay pending.
- **H5.** Not reported in detail: `H-A-SCH-HIER-ECO` stays pending.
- **H6.** The project of `partial.py` compiles with no error. It gives the four warnings of H3 and four
  warnings `Unconnected Harness Entry SPI-HOLD`: two on the top sheet and one on each module sheet, one
  per connector. So a harness entry without a wire is a warning, not an error. Confirms
  `H-A-SCH-HARN-UNUSED`; the nets were not listed, as in H4. This answers the open question on bare
  entries: they stay drawn. On the rebuilt top sheet there is no connector, so two of the four are
  expected to go.
- **H7.** Refuted as built. "Design » Update PCB Document" on the project of the board example reported
  7 differences and "None of the 7 differences detected can be resolved by automatically generated
  ECOs": one extra component, `D1`, on the PCB document's side; two extra pins in nets, `D1-1` in `GND`
  and `D1-2` in `LED_A`, on the PCB side; and, on the schematic's side, one extra component class
  `driver`, one extra room `driver` and two extra rules "Supply Nets". The maintainer then confirmed that
  the Projects panel does not show the sheet `altium_hier_board_led.SchDoc` under the top sheet: it is
  outside the hierarchy, so `D1` is not in the compiled schematic. `R1` and `U1`, on the sheet `driver`,
  match their board components through the two-id link, which is the first observation in favour of
  `H-A-SCH-HIER-ECO`.
  - The maintainer then ran "Sheet Symbol Actions » Synchronize Sheet Entries and Ports" on the sheet
    symbol `led`. The dialog named the file `altium_hier_board_led.SchDoc`, showed one existing link,
    `LED_A` (I/O type unspecified, no harness type), and no unmatched sheet entry or port. Nothing was
    changed; after the dialog was closed, the sheet `led` was under the top sheet. So Altium finds the
    content consistent, and its first pass over the project skipped that sheet.
  - On a fresh copy, "Project » Validate PCB Project" alone did not bring the sheet `led` under the top
    sheet; only the dialog did.
  - After the dialog and "Save All", two files had changed, and no schematic file. Altium wrote a new
    `altium_hier_board.PrjPcbStructure` (the top document, then one line per sheet symbol, `driver` and
    `led`, each with its file name), and it saved the project file in its full form: UTF-8 with a
    byte-order mark, `HierarchyMode=0` and many more keys under `[Design]`, and 14 more keys per
    document. `DocumentUniqueId` there holds eight letters for the top sheet, the PCB document and the
    sheet `led`, and is empty for the two libraries and for the sheet `driver`. None of these ids is in
    a file Fenolite wrote. The maintainer kept the two saved files outside the repository; only these
    facts are recorded (`docs/formats/altium/project.md`).
  - Reading: the three documents with an id are those Altium had loaded in full (the top sheet, the PCB
    document, and `led` through the dialog). `driver` has no id and was a child from the start, so the
    pass that builds the hierarchy does not load a sheet in full, and that pass reads `driver` and not
    `led`. The ids are a result of loading, not the reason for the difference.
  - The cause is **not proven**. The built files were read again with `tests/_altium_read.py`,
    `tests/_altium_pcb_read.py` and a second compound-file reader: the top sheet holds the sheet symbol
    `led` with the same keys as the symbol `driver`; its file-name record is
    `altium_hier_board_led.SchDoc`, letter for letter the name of the project file's sixth document; the
    sheet `led` holds `D1`, its port `LED_A` and its two stubs; the board's `D1` holds
    `\<id of the sheet symbol led>\<id of D1>` and the path `altium_hier_board\led`; and the readback
    finds the model's four nets. The hierarchy sample, whose two module sheets Altium compiled as
    children, differs in three ways only: its project holds no PCB document, its top sheet holds a
    part, and each of its module sheets is larger than 4096 bytes. In the board example the sheet
    `led` holds one part and is stored whole in the compound file's mini stream, as the top sheet is.
    The sheet entry and port of `led` have the same keys and values as those of `driver` (name `LED_A`,
    right side, first slot, no I/O type, no style, no harness type), which is also what a recent saved
    sheet holds (S-0187).
  - First reading, `H-A-SCHBIN-MINI`, refuted by the second report below: the `FileHeader` stream of the sheet `led` is 2303 bytes, under
    the compound file's cutoff of 4096 bytes, so it lies in the mini stream. The sheet `driver` (8817
    bytes) was a child. Every sheet that Altium took as a child in any report holds 4096 bytes or more,
    and so does every sheet Altium saved that was read (14 929 bytes at least, because a saved sheet
    starts with some 27 hidden parameters). A full load, which the dialog needs, reads the sheet. Against
    it: the top sheet of the example is also under 4096 bytes, and Altium read its sheet symbol
    `driver`; whether the top sheet was open in the editor at that moment is not reported. This is an
    inference from sizes, not an observation of the cause, and the variants below test it.
  - First fix, withdrawn after the second report: the binary form padded a sheet under 4096 bytes with
    one hidden sheet parameter as its last record. The example was rebuilt that way, with the top sheet
    and the sheet `led` padded, and tested again (second report below).
  - The component classes, the room and the supply-net rules on the schematic's side are objects that
    Altium derives from the sheets and offers to add to the board. They are no fault of the files, and
    Fenolite writes none of them into the PCB document. That none of the seven differences could become
    a change order suggests that the comparison ran towards the schematic ("Update Schematics"), which
    the wording of the first protocol allowed; step H7 now names the command and its starting sheet.
  - One difference from a saved board was found on the way and corrected: `CHANNELOFFSET` counts the
    parts of one sheet (S-0188), and the PCB document held the index over the whole board, so `D1` had
    the offset 2 on a sheet of one part (`docs/formats/altium/pcb-document.md`). Nothing shows that
    this explains the sheet outside the hierarchy.
  - New test: `tests/unit/lens/test_altium_pcb.py` reads the built project as a second program finds
    it (`component_links`, `board_link_problems`): every board link resolves to a schematic component
    through an existing sheet symbol whose file the project lists, every module sheet is reachable from
    the top sheet, and a module without a crossing still gets its sheet symbol. It passes on the files
    of this report, so it does not explain H7 either.
  - `H-A-SCH-HIER-ECO` and `H-A-SCH-HIER-PRJ` stayed pending with this observation, `H-A-SCHBIN-MINI`
    was registered as pending, and H7 was opened again on the rebuilt example, with the notes and the
    variants that Part H lists.

### 2026-10-03, `AD 26.5`, Part H, second report (step H7 and the Projects panel)

- Tool and label as in the first report: Altium Designer 26.5 under a trial licence on the maintainer's
  own PC; `ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact)`.
- Files: Fenolite's built files only, and the project file and structure file that Altium itself saved
  from them in the first session, which stay with the maintainer. The rebuilt board example of the
  first follow-up (project file `0b4ec6e1f9fc65e3f2a5efb3487b804049866290709bec354373bc2b227eef43`, top
  sheet `028fe92271350f4226fe8beece0921d575bc98d061fb1c6ef7e94e2169c45f0f` and sheet `led`
  `8b0bc40f61d665d7aa504d39c1c7ea9c1f0611b2747290d9dda4bbd4326e621f`, both padded), the hierarchy
  sample, and the variants a to n of Part H. Every test used a fresh copy of the project and only
  "Project » Validate PCB Project", with no dialog. No file opened or saved in the session enters the
  repository.

Outcome:

- **The padded example and variant c.** The second module sheet is still outside the hierarchy. The
  size of the sheet is not the cause: `H-A-SCHBIN-MINI` is refuted.
- **Variant d** (the small sheet is `driver`) fails as well. **Variants a, b, f and g** all fail: a
  structure file, document ids, the absence of a PCB document and the absence of ports change nothing.
- **Variant e** (the module of `D1` is named `a_led`, so its document is listed before `driver`):
  `a_led` is in the hierarchy and `driver` is outside. Only the first module sheet listed joins.
- **The hierarchy sample** works: both module sheets, `flash` and `mcu`, are under the top sheet. The
  maintainer's note gives its documents as top sheet, `flash`, `mcu`, schematic library. The project
  file built for that session (SHA-256
  `b30f01387b972880235e3391da7fc93e0e5edc78af488d139dc75b318bacbead`) lists the schematic library
  second, before the two module sheets, then the two `.Harness` files; it holds no PCB document and no
  PCB library. The two statements differ, and the report does not settle which documents in between
  stop the second sheet.
- **Variants h, j and n** work: with the project file that Altium saved in full, with or without its
  structure file, and with its `[Document<n>]` sections cut down to `DocumentPath`, both module sheets
  are children, although the documents keep the first build's order.
- **Variant l** works: Fenolite's minimal file with the documents in the order top sheet, `driver`,
  `led`, PCB document, PCB library, schematic library (SHA-256
  `c7c81bd2346c6070cb6a8d5aa2be76381515391db05113a615a20c6e1e9f1350`). Both module sheets are under the
  top sheet.
- **Variants k and m** (the minimal file with Altium's `[Design]` section, or with `HierarchyMode=0`)
  were not reported as working.

Reading and consequences:

- With the minimal project file, the schematic documents have to be listed together, the top sheet
  first and then the module sheets, before the PCB document and the libraries. When other documents
  stand between the top sheet and the module sheets, Altium takes only the first module sheet. The full
  project file that Altium saves is accepted in the other order as well; why is not known, and
  Fenolite does not need it. This is `H-A-SCH-HIER-ORDER`, confirmed by variant l, and the facts are in
  `docs/formats/altium/project.md`.
- The project file writer now lists the top sheet, the module sheets in module-name order, the PCB
  document, the libraries and the harness files. For the board example it gives the bytes of variant l.
  A build without module sheets keeps its bytes. An existing project file is still kept as it is, so a
  folder that holds a project file of the first build needs that file deleted before the next build.
- The padding of small sheets is removed, with its hidden parameter: the sheets of the board example
  are again the bytes of the first build (top sheet
  `8794466c89250a0bd6b734399c38675a6c874103df44ea69072855f3523cfb7c`, sheet `led`
  `7cb9fba1e489f3280c974b0c7b31d647f512447f9769460d59faaa1ffc759078`). `CHANNELOFFSET` per sheet stays:
  a saved board holds it that way (S-0188), whatever the cause of H7 was.
- New test: `tests/unit/lens/test_altium_pcb.py::test_hier_board_project_lists_the_schematics_first`
  checks that in a multi-sheet build every schematic document precedes every other document of the
  project file, with the top sheet first.
- Still open: the change order of step H7 on the rebuilt example (`H-A-SCH-HIER-ECO`: `D1` is expected
  to match now that its sheet is compiled), the Projects panel of the hierarchy sample in the order
  written now with its harness files (`H-A-SCH-HIER-PRJ`), and steps H3 to H5.

### 2026-10-03, `AD 26.5`, Part N

- Tool: Altium Designer 26.5.0 under a trial licence on the maintainer's own PC, a licence the maintainer
  may use for Fenolite (`LEGAL.md`, block A). Label: `ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03;
  no artefact)`.
- Files: a build of the blink example with `no_connect` on `U1` pins `11` and `12`, written outside the
  repository, in the binary form. It is not the committed sample of Part N (`altium_no_connect`, `U1`
  pins `2`, `4` and `8`): the two marked pins are those whose messages the report of steps A7, L4 and L5
  names. Fenolite's authored example only; no file opened or saved in the session enters the repository.

Outcome per step:

- **N1, on the blink variant.** The schematic opened, and a No ERC cross shows at the end of each of the
  two marked pins. Confirms `H-A-SCH-NC-RECORD` for the binary form. The directive's mode in the
  Properties panel and a directive at the end of a hidden pin (pin `8` of the committed sample) were not
  reported.
- **N2, on the blink variant.** After "Project » Validate PCB Project" no message names `U1` pin `11` or
  `12`. In the build without the marks the same pins gave a floating-input message and a "no driving
  source" message for the nets `NetU1_11` and `NetU1_12`, so the unmarked build is the positive control
  for the suppression. Whether the messages of the other, unmarked pins stayed was not reported, so the
  half "only for that pin" of `H-A-SCH-NC-ERC` is not settled: the row stays pending with this
  observation.
- **N3.** Not reported: the ASCII form.
- **N4.** Not reported: the Viewer (`H-A-SCH-NC-VIEWER` stays pending).
- **Not reported:** the committed sample of Part N with its control pin `3`.

The report names no fault, so no fact of `docs/formats/altium/schematic-ascii.md` changed in substance
and no golden file was rebuilt.

### Status of Part A and Part B

- No Altium Designer run of the ASCII sample (Part A, steps A1 to A6) or of Part B has been reported.
  Every `H-A-SCH-*` row and `H-A-PRJ-KEEP` stay `INFERRED` with `pending (author report)`; `H-A-PRJ-OPEN`
  is confirmed with the binary schematic (report of 2026-10-03).
- Part L is reported for steps L4 and L5 of the sample only: the `H-A-SCHLIB-*` rows other than
  `H-A-SCHLIB-PRJ` and the two oracle rows stay `INFERRED` with `pending (author report)`. A result made
  with a work licence is not recorded (`LEGAL.md`, P4).
- The Altium 365 Viewer's refusal of the ASCII files (V3 above) concerns the Viewer only.
- Part N is reported for steps N1 and N2 on a blink variant, in the binary form (report of 2026-10-03):
  `H-A-SCH-NC-RECORD` is confirmed for the binary form; `H-A-SCH-NC-ERC` and `H-A-SCH-NC-VIEWER` stay
  `INFERRED` with `pending (author report)`. The committed sample of Part N, the ASCII form (N3) and the
  Viewer (N4) are not reported.
