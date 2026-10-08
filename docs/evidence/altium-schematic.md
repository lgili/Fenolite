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
| `tests/data/altium/sample/altium_sample.SchDoc` | `fba12e59170cbbadd926a12e767745839c6808fedf3c77d163384deec430a3b0` |
| `tests/data/altium/sample/variants/altium_sample_lf.SchDoc` | `5106f8dc626bf388bfafd43bef64f88948470f67239f888497790456db32ef27` |
| `tests/data/altium/sample/variants/altium_sample_nouid.SchDoc` | `670d852303eeed40ad9834f333adf93f802b7ebfbc39548083645dce5ec6c826` |

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
| `tests/data/altium/sample/binary/altium_sample.SchDoc` | `86f5747454cca461a3eab5da270a994439d8b4f2bf4a29480d1360ca74a4ee1e` |

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
| `tests/data/altium/sample/FenoliteSample.SchLib` | `fbcf22282d5c274f7220bbe0b3c862f2fb6932aad2407a14d179da1367d6cf1e` |
| `tests/data/altium/sample/altium_sample.PrjPcb` | `082b8c32ea1318af5576405d53fd4a3362a49760d0f48081b32ce6305c547aa0` |
| `tests/data/altium/sample/binary/altium_sample.PrjPcb` | `082b8c32ea1318af5576405d53fd4a3362a49760d0f48081b32ce6305c547aa0` |
| `tests/data/altium/kicad_example/altium_kicad.PrjPcb` | `0a6f26d9afc01438b641d182ab62d40b3a57fc46773db2ac09ae2a8827808296` |
| `tests/data/altium/kicad_example/altium_kicad.SchDoc` | `1ecb0bb793cf06ecad44422d41615b624116976208f1a929d9b023ebc85e3c28` |
| `tests/data/altium/kicad_example/altium_kicad.SchLib` | `71abcfba4f4fc1d95f6ce37730817537d5432c26a78ef8e32e7b30f64d1a3b49` |

2026-10-07 (change c0134): the two files of `kicad_example` above were built again, because the four
symbols of the example library changed: `CONN2` no longer shows its pin names, which only repeated its pin
numbers; `MCU8` and `DUAL_OPAMP` have larger bodies with their pins further out, so that their pin names
do not lie on each other; the pins of `MCU8` are 5.08 mm long and 5.08 mm apart, so that its pin numbers
stand clear of the inversion bubbles of pins 2 and 5; and the two pins of `R_V` are 2.54 mm long, so that
its pin numbers stand clear of its body. The table names the new bytes; no report covers them, and no row
changed.

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
| `tests/data/altium/no_connect/altium_no_connect.SchDoc` | `80c45b5bafcd93aed4e4f9d38a29bd46dceccfed7d5819aaac401246a6474129` |
| `tests/data/altium/no_connect/altium_no_connect.SchLib` | `9b94a2d31d43d2297f1de97ccbc754b899dd6a2b44bc64520546e5a8f08d43af` |
| `tests/data/altium/no_connect/ascii/altium_no_connect.SchDoc` | `00fbe6dfcb752687b1dd036754cdd7072d84c35b6d36418105ae301f0dc81356` |

2026-10-07 (change c0134): the library and the two schematics above were built again, because `CONN2`
(`J1`) no longer shows its pin names, `MCU8` (`U1`) has a larger body with longer pins further out and
further apart, and the two pins of `R_V` (`R1`) are 2.54 mm long. The
nets, the three marked pins and the three directives are the same; the directives lie at the new ends of
the pins. The table names the new bytes; no report covers them, and no row changed.

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
| `tests/data/altium/hier/FenoliteHier.SchLib` | `28253155935529e7c62fb723739044858277e39fcd7c61eb3c5dbdfcf0cebbc3` |
| `tests/data/altium/hier/altium_hier.PrjPcb` | `5a93823a0b938462fb766cee0ce8254a7e31f29076e4fa9303f74a8ed88b30f6` |
| `tests/data/altium/hier/altium_hier.SchDoc` | `ee7353c17578de7e6c36904de4f30c8406afd1909837c92d64157067cd51d1f0` |
| `tests/data/altium/hier/altium_hier_flash.Harness` | `83c0f6606a5ac53075a7c5b8c2a2e785cb56eeb197ec9e10a920ede54c8da733` |
| `tests/data/altium/hier/altium_hier_flash.SchDoc` | `9782ddddfb92fcb6d746c6e14fd328da276643779c20398ad8b8ba9772dec46d` |
| `tests/data/altium/hier/altium_hier_mcu.Harness` | `83c0f6606a5ac53075a7c5b8c2a2e785cb56eeb197ec9e10a920ede54c8da733` |
| `tests/data/altium/hier/altium_hier_mcu.SchDoc` | `25e01b9cc051d34f391fa30b492a377f07bab53a257f0f2fc13eb40782167e67` |

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
holds `CHANNELOFFSET` per sheet and whatever later changes write into a PCB document. Expected:
after a compile on a fresh copy, without any dialog, both module sheets are children of the top sheet,
and the change order proposes no component change and no net change. The third report below found
both. Open: steps H3, H4 and H5 on the rebuilt hierarchy sample.

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

## Part O: the output job in Altium Designer

Change c0087 writes `<name>.OutJob` beside the PCB document of an Altium build. The file holds only the keys
of `docs/formats/altium/output-job.md`, "The writer's choices": the outputs, their source documents and
their containers, and no output setting. The part is named O because Part V is the Viewer's. Since change
c0138 the job also holds `OutputDefault<i>=0` on every output and the settings record of its Gerber output;
the files and the steps for that job are under "Session 2" below.

The files are built outside the repository by `fenolite build examples/blink_routed/design.py --target altium
--out DIR --confirm` and handed over; none is committed except the sample of the job's form,
`tests/data/altium/outjob/blink.OutJob`, which a unit test keeps equal to a fresh write.

| file of the build of 2026-10-06 | SHA-256 |
|---|---|
| `blink_routed.OutJob` | `9c6ff39690ef35813b3c57d9f3e3b4d7937e89c6385189749733e3e3ea722095` |
| `blink_routed.PrjPcb` | `99bcc6d91837bf0c0f55876e5be11ae444eca9c11c10bf8c6dbf56c110a8093d` |
| `blink_routed.PcbDoc` | `6691042bc82ef6250d4944f6b08ab8be16b8aeb83d39f0c6975d42cfc332333a` |
| `blink_routed.PcbLib` | `640bbcdb207a1dd724d310963f135101f6fb7525b5b59d22516a23ecaa4955ce` |
| `blink_routed.SchDoc` | `50a062c3ae03c6dec28e803f42c01d18c1e7c7c39cb439c640135611e4065c14` |
| `blink_routed.SchLib` | `44e8f59b353162278a631fa533f02197e4df3f40d88de8831cc3f111abe12e22` |

The table sent with the files (what steps O1 and O2 are read against):

| output | type | source document | container |
|---|---|---|---|
| Gerber Files | `Gerber` | `blink_routed.PcbDoc` | `fab` (folder structure) |
| NC Drill Files | `NC Drill` | `blink_routed.PcbDoc` | `fab` |
| Pick and Place | `Pick Place` | `blink_routed.PcbDoc` | `fab` |
| Bill of Materials | `BOM_PartType` | the project | `fab` |
| Schematic Prints | `Schematic Print` | the project | `doc` (PDF) |
| PCB Prints | `PCB Print` | `blink_routed.PcbDoc` | `doc` |

1. O1: open `blink_routed.PrjPcb`; the Projects panel lists `blink_routed.OutJob`. Open it. Expected: no
   message. Settles `H-A-OUTJOB-OPEN`.
2. O2: read the outputs, their source documents and which container each is enabled for. Expected: the
   table above. Settles `H-A-OUTJOB-OPEN`.
3. O3: generate the container `fab`, then the container `doc`. Expected: no error; report the kinds of
   files produced, not the files. Settles `H-A-OUTJOB-RUN`.
4. O4: open the setup of the Gerber and of the NC drill output and read units, format and plotted layers.
   Expected: Altium's defaults, since the job holds no setting; report them in one sentence each. Settles the
   first half of `H-A-OUTJOB-OPTIONS`.

No report yet: the four rows are `INFERRED`, "pending (author report)".

**Since change c0138 (2026-10-07) the digest of the job in the table above is that of the files of session 1
only.** A build of the same script now writes a job with eight more lines (`OutputDefault<i>=0` on each of
its six outputs and the two configuration lines of the Gerber output), whose SHA-256 is in the table of
"Session 2" below; the five other files of the build keep the digests of the table. The table is left as it
is because it names the files that were opened and returned ("Returned folders of 2026-10-07").

### Session 2 (change c0138, Altium Designer 26)

The job of session 1 ran in Altium Designer 26 except for its Gerber output, which plotted no layer
(`docs/evidence/altium-pcb.md`, "Returned folders of 2026-10-07"). Change c0138 writes the complete settings
record on the Gerber output and `OutputDefault<i>=0` on every output
(`docs/formats/altium/output-job.md`, "The Gerber settings record"). **Nothing of this section has been
opened in Altium**: every row it names is `INFERRED`, "pending (author report)".

Three projects, built on 2026-10-07 outside the repository into `~/fenolite-altium-checks/session-2/O-outjob/`
(a `README.md` there repeats the steps): `blink_routed/` by `fenolite build examples/blink_routed/design.py
--target altium --out DIR --confirm` (two copper layers, no preset); `blink_routed_p6/` by the same command
with `--altium-outjob-preset precision6.toml`, a preset that holds `[gerbers]` `precision = 6`; `board6/`,
the kit sample `examples/kit/board6` built as `fenolite kit build` builds it (six copper layers, the third
an internal plane on `GND`; the `build` command gives that script two layers, so it is not used here).

| file of the build of 2026-10-07 | SHA-256 |
|---|---|
| `blink_routed/blink_routed.OutJob` | `595be494ec0a3ce8edc084cd041d86b2fe4bab9cd94f05b5a7e557864f44f950` |
| `board6/board6.OutJob` | `cffaa5da448480a99feba314a4e08a47a4f14dd27f016ad72ec5875c191a50e1` |
| `blink_routed_p6/blink_routed.OutJob` | `bb3e5505a4bc91c07dd894c984e2a8710cd7d485be89de84ced996637236d5e5` |

The five other files of `blink_routed/` and of `blink_routed_p6/` have the digests of the table of
2026-10-06 above: only the job differs from the files of session 1. The record of each job reads back with
`read_outjob` and `record_fields` to 44 fields; the unit is `Metric` in all three, the decimals are 4, 4 and 6.
The three projects were built again later on 2026-10-07, after change c0134 changed the pin texts of the
catalog symbols: the three jobs and every file of the two blink projects kept their bytes, and the
schematic document and library of `board6/` changed (the `README.md` of the folder lists every digest).

The layers each job asks Altium to plot, in the order of the record (what steps O3, O5 and O7 are read
against). **No job asks for the board outline** (unknown U5 of the facts page):

| # | `blink_routed` and `blink_routed_p6` (12) | `board6` (16) |
|---|---|---|
| 1 | Top Overlay | Top Overlay |
| 2 | Top Paste | Top Paste |
| 3 | Top Solder | Top Solder |
| 4 | Top Layer | Top Layer |
| 5 | Bottom Layer | Mid-Layer 1 |
| 6 | Bottom Solder | Internal Plane 1 |
| 7 | Bottom Paste | Mid-Layer 3 |
| 8 | Bottom Overlay | Mid-Layer 4 |
| 9 | Mechanical 13 | Bottom Layer |
| 10 | Mechanical 14 | Bottom Solder |
| 11 | Mechanical 15 | Bottom Paste |
| 12 | Mechanical 16 | Bottom Overlay |
| 13 | | Mechanical 13 |
| 14 | | Mechanical 14 |
| 15 | | Mechanical 15 |
| 16 | | Mechanical 16 |

The steps are written from Altium's documentation (S-0293, S-0605); a menu path or a dialog name may read
differently in version 26. Steps O2 and O4 above are unchanged, still open, and not repeated.

1. O1: open `blink_routed/blink_routed.PrjPcb` and then `blink_routed.OutJob`. Expected: no message. Settles
   `H-A-OUTJOB-GERBER-ACCEPT` (with O5).
2. O3: generate the container `fab`, then the container `doc`. All six output kinds are generated again,
   because every output of the job now holds one more key than the job that ran in session 1. Expected: no
   error; Gerber layer files beside the drill, pick-and-place and bill-of-materials files, and the PDF.
   Report the extensions of the files that appear in the Gerber folder, as a list, and whether the report of
   the Gerber output now names layers. Settles `H-A-OUTJOB-RUN-2` and `H-A-OUTJOB-GERBER-LAYERS`.
3. O5: open the setup of the Gerber output (double-click it, or right-click and Configure) and read three
   things: the units, the format or decimals, and which layers have their plot switch on. Expected:
   millimetres, 4 decimals, and the twelve layers of the table. Settles `H-A-OUTJOB-GERBER-ACCEPT`,
   `H-A-OUTJOB-OPTIONS-2` and, with O8, `H-A-OUTJOB-GERBER-DECIMALS`.
4. O6: in the same setup, look at what Altium offers for the board shape: whether the layer list holds an
   entry for the board outline (the documentation names one as the first entry), what it is called, and
   whether its plot switch is on. Report that. Then turn it on if it exists, close with OK, save the job
   under another name in the same folder and generate `fab` again; report whether an outline file is then
   produced and its extension. Settles no row: it is the input for the outline proposal.
5. O7: open `board6/board6.PrjPcb` and `board6.OutJob` and generate `fab`. Report the extensions, and whether
   one file is the internal plane. Settles `H-A-OUTJOB-GERBER-PLANE`.
6. O8: open `blink_routed_p6/blink_routed.PrjPcb` and its job, read units and decimals in the Gerber setup,
   generate `fab`. Expected: millimetres and 6 decimals. Report what the setup shows (a value Altium replaced
   is a result, not a failure) and whether files appear. Settles `H-A-OUTJOB-GERBER-DECIMALS`.

To send back: the Altium version as `AD <major>.<minor>`, the date, one outcome per step (`as expected`, or
what differed in one sentence), and the three lists of extensions. The job saved in O6 stays in the session
folder; it is read outside the repository with `read_outjob`, and what its `Plot.Set` holds beside the written
entries is recorded as an observation on the facts page. No file that Altium wrote is committed, and an
author report never moves an operation out of `experimental`. Stating the outcome of the session of
2026-10-07 with the minor version (the Gerber output of the old job plotted nothing) settles
`H-A-OUTJOB-GERBER-EMPTY` without a new run.

#### Reports

**2026-10-08, `AD 26.5`, session 2 (S-0615).** Altium Designer 26.5.0 on the maintainer's own PC, a licence
he may use for Fenolite (`LEGAL.md`, block A), on the folder `O-outjob/` of the session pack built from
commit `695574ba` (the three jobs have the digests of the table above). His report: every output of the job
was produced, the Gerber layer files among them, where the job of session 1 produced no layer file. Per step:

- **O1 and O3.** The project and its job opened, and both containers generated their outputs, Gerber layer
  files beside drill, pick and place, bill of materials and the prints. Confirms `H-A-OUTJOB-RUN-2`
  (`ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-08; no artefact)`).
- **O3, the list.** The extensions and the count of the layer files were not reported, so
  `H-A-OUTJOB-GERBER-LAYERS` stays pending with this observation.
- **O5, O6, O7 and O8.** Not reported as values (the units, the decimals and the plotted layers of the
  setup, the board outline entry, the six-layer job with its plane, the job of precision 6):
  `H-A-OUTJOB-GERBER-ACCEPT`, `-PLANE`, `-DECIMALS` and `H-A-OUTJOB-OPTIONS-2` stay pending.
- **O-S1.** Not stated with a minor version: `H-A-OUTJOB-GERBER-EMPTY` stays pending.

The defect of session 1, a job that plotted no Gerber layer, is repaired by change c0138 as far as this
report goes: the written job now yields Gerber files in Altium Designer 26.5. No file that Altium wrote is
committed, and an author report moves no write kind out of `experimental`.

## Part W: the sheet template and the drawing sheet in Altium Designer

Change c0087 writes a sheet template (`.SchDot`) from a `*.sheet.toml` specification, and draws the same
sheet on the schematic documents of a build whose script names a drawing sheet. The files are built outside
the repository and handed over: the template by `fenolite template build
src/fenolite/templates/examples/iso5457_generic.sheet.toml --target altium --out iso5457_generic.SchDot
--confirm`, and a one-sheet project by an Altium build of the blink example with the lines
`design.sheet("A4", drawing_sheet="frames/generic.sheet.toml")` and `design.title_block(title="Blink",
revision="B", date="2026-10-06", organization="Fenolite")` after its `board()` line, the specification
copied to `frames/generic.sheet.toml`. The reference is the PDF that `kicad-cli sch export pdf` (10.0.6)
gives for the KiCad build of the same script; it is a visual reference only and settles nothing.

| file of 2026-10-06 | SHA-256 |
|---|---|
| `iso5457_generic.SchDot` (the file of 2026-10-06, whose font table holds 10 points twice; since change c0146 the same command writes each distinct font once, three fonts where there were four, and the bytes pinned in `tests/unit/backends/altium/test_schdot_write.py` are `2e91c3a6a142146a32c898f14e7cd3a05dc56c2b8782a6095bfad455138b94fb`; no template file is committed, and the file of this row was not built again) | `0b161a6e93c98e4d7b5735c1657f3ea1f689f8ab99d95a5715b9489e4ca727d1` |
| `blink.SchDoc` (the file of 2026-10-06, with the same four fonts; a build since change c0146 writes three, and this file was not built again) | `b95b062ead2024b560dfbaa811fb72106db401fa01ebaae12a01caa7ec256a43` |
| `blink.PrjPcb` | `2c0fc10e49421372d5f65721d882751188c3eb42ee6b9fa5c43c7a45ba11b00c` |
| `blink.PcbDoc` | `642ce93cdfd14136c421406e3ba261aab055fcdb437dff9cfc9fefebdd3e0a32` |
| `blink.PcbLib` | `8fca33bda63bc3846e99478aa76f20e248026aefa0addd6e6e4ce9e9314c0082` |
| `blink.SchLib` | `129dbf049df0a40cc2d1de1c1a54e7a49b2597ba35b4601db6a4d986a3e047c6` |
| `blink.OutJob` (the file of 2026-10-06; since change c0138 the same build writes eight more lines, the key `OutputDefault<i>=0` per output and the Gerber record, and the job is `0a24a3b5d6eca281058a65aad86195bc159a7635756a409f8dae7954f894b436`, the committed sample `tests/data/altium/outjob/blink.OutJob`; no step of Part W reads the job) | `e6ac379aeb0e508866b8c45e6bc1e6516da1e50a2b3cf9f6117e68a81051db9e` |

1. W1: open `iso5457_generic.SchDot`. Expected: no message; an A4 landscape sheet with a frame, reference
   zones and a title block, and no second border around it. Settles `H-A-SCHDOT-OPEN`.
2. W2: in a new schematic, set the template to that file (Design » Sheet Templates). Expected: the frame
   appears. Settles `H-A-SCHDOT-OPEN`.
3. W3: open `blink.PrjPcb` and print `blink.SchDoc` to PDF; compare it with the reference PDF: frame, zones,
   title-block lines and labels. Report each difference in one sentence (known from the files: the text
   heights and the line widths differ, see `docs/sheet-templates.md`). Settles `H-A-SCHDOT-OPEN`.
4. W4: read the title block of `blink.SchDoc`: title, revision, date and legal owner, the sheet number,
   and the sheet count where the title block shows one. Expected: `Blink`, `B`, `2026-10-06`, `Fenolite`, `1` and `1`. Then change the title in the document options
   and read it again. Expected: the new value. Settles `H-A-SCHDOT-STRINGS`.

No report yet: the two rows are `INFERRED`, "pending (author report)".


## Part Y: the complete schematic (change c0086)

Change c0086 draws each symbol from its own graphics, gives every module a sheet at any depth, writes
port and sheet-entry I/O types, buses, hidden parameters and, in the binary form, comments and parameter
values with Windows-1252 characters. **Nothing of this part has been opened in Altium.** Its seven rows
are `H-A-SCHX-*`: `H-A-SCHX-READBACK` is settled by Fenolite's own reader (`INFERRED`); the other six stay
`INFERRED` with `pending (author report)` until the steps below are reported.

2026-10-07 (change c0134): the author has since opened files of this part, built before change c0134, and
named pin names that lie on each other on five small symbols ("Author report of 2026-10-07 (opening
only)" below). Change c0134 changed the definitions of those symbols and of the others with the same
defect. The report carried out no step below, and nobody has opened the files built since: the rows are
where that section leaves them, `INFERRED`.

**What the earlier reports covered.** The reports of 2026-10-02 and 2026-10-03 below were made on files
whose resolved symbols were drawn as rectangles. Since change c0086 the default build draws the symbols'
graphics (`--altium-symbols graphics`, decision of the maintainer of 2026-10-06), and the committed
schematics and schematic libraries of the samples `blink`, `kicad_example`, `no_connect` and `routed`
were regenerated in that form. The files those reports covered are kept, byte for byte, under
`tests/data/altium/generic/<sample>/` (the bytes of commit 6cdf0aea), and
`tests/unit/lens/test_altium_schematic_complete.py -k generic` checks that `--altium-symbols generic`
still builds them. The tables of Part L, Part N and of `docs/evidence/altium-pcb.md` name the SHA-256 of
the regenerated files, because their golden tests compare the default build; no earlier report says
anything about those bytes, and no row was raised because of them. The samples `sample` and `hier` use
Altium links, are drawn as rectangles in both forms, and did not change.

2026-10-07 (change c0134): the four symbols of the example library `FenoliteDemo.kicad_sym` changed, so
`kicad_example` and `no_connect` were built once more in the graphics form. Their copies under `generic/`
keep the bytes of commit 6cdf0aea: `-k generic` builds them from the library of that commit, kept as
`tests/data/altium/generic/library/FenoliteDemo.kicad_sym`. `--altium-symbols generic` on the example as
it is now gives other bytes, which no report covers.

The nets and designators of every sample are the ones it had: `test_nets_unchanged` reads each committed
project and compares it with `tests/data/altium/nets_before_c0086.json`, recorded from the files of commit
6cdf0aea.

**Files.** They are built outside the repository, into the maintainer's folder
`~/fenolite-altium-checks/c0086-part-y/` (rebuilt on 2026-10-06 after the rebase onto c0084, c0085, c0087
and c0089, with the same bytes as before it), by a script of the change's scratch area: the tree sample
through `tests/_altium_tree.py`, the four samples through their own example builds, each with the lens
defaults (no output job, no drawing sheet). None is committed beyond `tests/data/altium/tree/` (the folder
`tree/binary` below, checked by `-k tree`) and the four regenerated samples. The handover files of Parts O
and W above were built before this change, with rectangle bodies; a rebuild of them now draws the symbols'
graphics unless `--altium-symbols generic` is given.

2026-10-07 (change c0134): the table names the bytes that the same build gives since that change. The
catalog symbols `BJT_NPN`, `Comparator`, `Operational_Amplifier` and `Linear_Regulator` of the tree sample
and the four symbols of the example library changed, so 12 of the 19 files below differ from the build of
2026-10-06; the other seven are the same bytes. The files the author opened on 2026-10-07 were built
before this change ("Author report of 2026-10-07 (opening only)" below); the SHA-256 this table named
until then are in the history of this page. No report covers the new bytes.

| file | SHA-256 |
|---|---|
| `tree/binary/tree.PrjPcb` | `5f82374c7c3c16dac370815a2bc520bb026e0e30ccd55cd6b528353ec0f0ebb0` |
| `tree/binary/tree.SchDoc` | `3680dbc37c00689a9abeddd27d019eab39129c688f4614a0629b68076bbee6c1` |
| `tree/binary/tree.SchLib` | `92b40a49dc04ec9bba0b91eb00f9070a6066469c6b6f2dbc54f90519308e77d8` |
| `tree/binary/tree_io.SchDoc` | `d1c8c94aa624e99aa233cd687bdf48ac2338cf0d1be6008ba834cf8921cf05d5` |
| `tree/binary/tree_io.leds.SchDoc` | `8f197da032e893e509e0c3c88a63b33e0b3da965507dbcd00d3d0790aabe04ca` |
| `tree/binary/tree_power.SchDoc` | `d0807006fc48f66067a414eeb70eeeaf7f7a499cb4f861cbca328dd7fe56c024` |
| `tree/ascii/tree.SchDoc` | `c1223fb8609b1ea2e282dca90f0666ecd1d6a6ae827da10d8940289639dde7c5` |
| `tree/ascii/tree_io.SchDoc` | `3f80bd2aa0a7abf83ec31f6551422fe18119d6f943f7b9d404290c8b224240b4` |
| `tree/ascii/tree_io.leds.SchDoc` | `8e876d076c92dde71b6a9a2b019ceaafe58324db9fe5fdb4060fda59c735d74f` |
| `tree/ascii/tree_power.SchDoc` | `e2fe01ed1e7bf94e5dc8f1433a6d20860e1b1167ddc4a66d107f95f1919082fa` |
| `tree-bad/binary/tree_io.SchDoc` | `d1f72dc31255989fa32ab114e15acfde98e62c41ac9c4c15c9f5e94dcfbb01cb` |
| `samples/kicad_example/altium_kicad.SchDoc` | `7d6276e4c63a89e4c567476cf9bc154664306217ef9a03d1ceff71854a19ac55` |
| `samples/kicad_example/altium_kicad.SchLib` | `cbf419d33675f13d4de87fe063b9a11d802204ed6aafaecf59608317c0be517e` |
| `samples/no_connect/altium_no_connect.SchDoc` | `5b1b5bb8b1c29b2ae9833738c7f4de892ac5e18f9b3128d205223301299d2792` |
| `samples/no_connect/altium_no_connect.SchLib` | `ca9aa9fb7b50cd131fc48b42139a2f5fd68ad815dc8f3675e0492d55b7423522` |
| `samples/blink/blink.SchDoc` | `d52160144438ee1fa2026cf704e37881c2f9b98d8389ace45ac73f01e56dcf43` |
| `samples/blink/blink.SchLib` | `129dbf049df0a40cc2d1de1c1a54e7a49b2597ba35b4601db6a4d986a3e047c6` |
| `samples/routed/routed.SchDoc` | `5c7ce5f3352ce91e6970dd49753f03d9f0b39c539f56b8a79b59d5c5679e7557` |
| `samples/routed/routed.SchLib` | `db7d0c5b55210c9f7a113120595fa48427c43263cff13c76452ed44312dd0e07` |

- The ASCII tree project shares `tree.PrjPcb` and `tree.SchLib` with the binary one; its two texts with
  accented characters are replaced (`Inductor 10 uH`, `tolerance 10 %`), because the ASCII form refuses
  them. `tree-bad` is the binary tree project with one sheet changed: the port `SENSE` of `io` says
  input while its sheet entry on the top sheet says output. The four `samples` folders also hold their
  project files and, for `blink` and `routed`, the PCB library and document, which did not change.
- The tree design (`tests/data/altium/tree/design.py`): `J1`, `J2` and `U1` on the top sheet; `U2`, `L1`
  and `C1` in `power`; `U3` and `Q1` in `io`; `D1` to `D4` in `io/leds`; 13 nets; the bus `D` of `D0` to
  `D3` from `J2` to the LEDs.
- Reference for the four symbols of steps Y2 and Y3, in words, since the change builds no picture:
  `Resistor` is a zigzag of eight lines between its two pins; `LED` is a filled triangle with a bar at
  its tip and two small arrows above it; `Comparator` is an open triangle pointing right with a short
  line at its tip, a plus and a minus stroke inside at its two inputs on the left (since change c0134 it
  shows no pin names), the output on the right, supply pins above and below;
  `Connector_4` is a filled rectangle with four small open squares on its left side, one per pin.

Steps:

1. **Y1** (`tree/binary`): open the project. Expected: no repair prompt, no message; four schematic
   documents and one library in the Projects panel.
2. **Y2**: open `tree.SchLib` and look at `Resistor`, `LED`, `Comparator` and `Connector_4`. Expected: the
   shapes described above, with the pin ends on the graphics. No symbol of this library holds a circle;
   an open circle (an ellipse record without `ISSOLID`, as `Pushbutton_NO` of the catalog would give) is
   not covered by this part.
3. **Y3**: open `tree.SchDoc` and `tree_power.SchDoc`. Expected: the same graphics on the sheets, the
   designator above and the comment below each part.
4. **Y4**: "Project » Validate PCB Project", then the Navigator. Expected: no error; the tree `tree` →
   `io` → `leds`, and `tree` → `power`.
5. **Y5**: read the Messages panel for port and sheet-entry messages; then validate `tree-bad/binary`.
   Expected: none for `tree`; at least one message that names `SENSE` for `tree-bad`.
6. **Y6**: in the Navigator, list the nets of the bus `D[0..3]`. Expected: `D0` to `D3`, each with one pin
   of `J2` and one LED anode.
7. **Y7**: read the comment of `L1` (`Indutância 10 µH`) and the hidden parameter `Note` of `C1`
   (`tolerância ±10 %`, with its parameter `MPN` = `X-1`). Expected: as written. Then open `tree/ascii`
   and report whether it opens and what the comment of `L1` reads (`Inductor 10 uH`).
8. **Y8**: "Design » Update PCB Document" into a new, empty PCB document added to `tree/binary`. Report
   the number of components, nets, component classes and rooms the change order lists. Expected: 12
   components, 13 nets, the component classes `tree`, `io`, `leds` and `power`, no room.
9. **Y9**: open each of the four projects under `samples/` (the regenerated samples). Expected: each
   opens without a prompt, and its three symbols of one unit show their own graphics, with the pins where
   the rectangle form of the same library has them; `DUAL_OPAMP` of `kicad_example` has two units and
   stays two rectangles.

The maintainer reports one outcome per step (`as expected`, or what differed in one sentence), the tool as
`AD <major>.<minor>` and the date; no file that Altium wrote is committed. A step that fails refutes the
row it names: Y2, Y3 and Y9 `H-A-SCHX-GRAPHICS`; Y1 and Y4 `H-A-SCHX-TREE`; Y5 `H-A-SCHX-DIR`; Y6
`H-A-SCHX-BUS`; Y7 `H-A-SCHX-TEXT`; Y8 `H-A-SCHX-ECO`.

## Part R: channels of a `Repeat` statement (change c0083)

The import instantiates a `Repeat` statement from Altium's documentation alone: no public file of the
corpus holds one. **Nothing of this part has been opened in Altium.** It settles `H-A-IMP-RPT-COUNT`,
`H-A-IMP-RPT-NETS` and `H-A-IMP-RPT-FORMAT`; the hypothesis of the annotation file is not registered
(its reader is not written), and step R4 is what would let it be.

**Files.** The authored two-channel project `tests/data/altium/channels/two/`, in the maintainer's folder
`~/fenolite-altium-checks/session-2/R-repeated-sheet/` since 2026-10-08, with a guide in Portuguese. If
step R1 fails on opening, draw the same project by hand and go on: a top sheet with a sheet symbol whose
designator is `Repeat(CH,1,2)` on a child sheet, with the sheet entries `VCC` and `Repeat(OUT)`; the entry
`Repeat(OUT)` on a bus labelled `OUT[1..2]` whose members `OUT1` and `OUT2` go to two pins of a component;
on the child sheet `R1` and `C12`, `R1` pin 1 on the port `VCC`, `R1` pin 2 and `C12` pin 1 on a wire
labelled `MID`, `C12` pin 2 on the port `OUT`.

| file (since change c0146, 2026-10-08) | SHA-256 |
|---|---|
| `two.PrjPcb` (unchanged) | `38384a5c609a963bd3c072d9b95deea42bb137565b2664ae28bb6ddfc16c6737` |
| `two.SchDoc` | `e07048f42c930a5d1ac6d326aae2331c5b96f2da1e26d958ea09eea5a6d24112` |
| `two_ch.SchDoc` | `3bd678fdf0ef16ee9a7bcba23ba6113353244a3a8533d982f093a42526892724` |

**The first files showed a black page.** The files of 2026-10-06 (`two.SchDoc`
`53c540c9af491840b9c2a1f48f3b31910d22c9b838c9eac6473c5f72221d3ed2`, `two_ch.SchDoc`
`437e5357a673b9c0930d519538157ba2f5f0223f60877bb29218552810fb52d3`; they stay in the older folder
`~/fenolite-altium-checks/c0083-part-r/`) were authored record by record for the reader's tests. Their
sheet record held five keys (the font table, `SYSTEMFONT` and `SHEETSTYLE`) and no `AREACOLOR`; no record
held `COLOR`, `AREACOLOR` or `FONTID`; pins had length 0 and components no graphics. On 2026-10-07 the
maintainer said that the sheet showed as a page that was all black, and reported no step. What is believed,
and not confirmed: an absent area colour reads as 0, which is black, and the objects, without a colour, are
black on it (`H-A-SCHDOT-AREACOLOR`; every sheet the schematic writer writes and every sheet Altium saved holds
`AREACOLOR=16317695`).

**How the files are made now (change c0146).** The two sheets are sheet plans handed to the schematic
writer (`tests/_altium_channels.py`: `binary.write_schdoc_binary`; the top sheet placed by
`layout.layout_sheet`, the child sheet by hand from the same pieces), so they hold
what every written sheet holds: the writer's sheet record with its grids and area colour, a colour and a
font on every record that has them in a written sheet, a filled rectangle per component, pins of 200 mil,
designators and comments. No build writes a `Repeat` statement; in the sample it is the name given to the
writer's sheet symbol, `Repeat(OUT)` is the name given to its second sheet entry, and the bus the writer
draws beside that entry is labelled `OUT[1..2]`. Those records differ from a plain sheet symbol and a plain
sheet entry in their text alone. Two things differ from the first files in the drawing: every pin of the
top sheet joins its net by a labelled wire, as on every written sheet, and on the child sheet the ports
`VCC` and `OUT` lie directly on the ends of `R1` pin 1 and `C12` pin 2, without a wire (the writer draws no
wire without a net label, and a label on the net of a repeated port would name it in every channel). The
import reads the same circuit from both generations: the same modules, component and pin ids, designators,
nets and bus (`tests/unit/backends/altium/adapter/test_repeat.py`, not edited by the change); the
components now have a comment (`10k`, `100n`, `DRV2`, `CONN1`) and a library reference, which the first
files left empty. The components name no footprint, as before: step R3 is about the designators and the
nets that the change order lists. **Nothing of the new files has been opened in Altium**, and whether a
port that lies on a pin end connects in Altium as it does in the import is part of what step R1 shows (a
compile message about a floating port would say that it does not).

1. R1: open `two.PrjPcb` in Altium Designer, look at both sheets, and compile the project. Expected: both
   sheets show a pale page with their objects visible (supports `H-A-SCHDOT-AREACOLOR`; the new files differ
   from the first in more than the area colour, so this does not isolate it); no error; the Navigator
   shows two channels of the child sheet, `CH1` and `CH2`. Settles `H-A-IMP-RPT-COUNT`.
2. R2: for each designator format offered in Project Options » Multi-Channel, select it, compile, and
   write down the designator of the component `R1` in both channels; then, with `$Component_$RoomName`,
   the same for each of the five room naming styles. Expected, for the formats in the order of the list:
   `R1_CH1`, `CH1_R1`, `R1A`, `R1_CHA`, `R1_1`, `R1_CH1`, `R_1_1`, `R_CH1_1` in the first channel (style
   "Flat Numeric With Names"), and for the styles `R1_CH1`, `R1_CHA`, `R1_CH1`, `R1_CHA` and, for the
   mixed style, whatever Altium shows (the import does not name it). Settles `H-A-IMP-RPT-FORMAT`.
3. R3: with the format `$Component_$RoomName` and the first style, run Design » Update PCB Document on an
   empty board, and write down the designators of the four channel components, the names of the nets of
   `C12` pin 2 in both channels and of `R1` pin 2 in both channels, and the form of the unique-id path
   of one channel component as its properties show it (only the form: where the channel index stands
   and what separates it from the unique ids, not the ids). Expected: `R1_CH1`,
   `R1_CH2`, `C12_CH1`, `C12_CH2`; `OUT1` and `OUT2`; `MID_CH1` and `MID_CH2`. Settles
   `H-A-IMP-RPT-NETS`, and gives the path form that the board link of a `Repeat` channel waits for.
4. R4: run Tools » Annotation » Annotate Compiled Sheets, rename one channel's `R1`, save, and send only
   the names of the keys of the `.Annotation` file that changed and the two designators.

The maintainer reports one generic outcome per step (`as expected`, or what differed in one sentence),
the tool as `AD <major>.<minor>` and the date. No file that Altium wrote is committed. A step that fails
refutes the row it names. The steps were written from Altium's documentation; a menu path or a dialog name
may read differently in version 26.

No report yet: the three rows are `INFERRED`, "pending (author report)". The one thing reported so far, the
black page of the first files on 2026-10-07, is no step of this part and moves no row.

**Report of 2026-10-08, `AD 26.5`, session 2, step R1 only (S-0615).** Altium Designer 26.5.0, on the files
of the table above (the folder `R-repeated-sheet/` of the session pack).

- **The page.** Both sheets show a pale page with their objects: the black page of the first files is
  gone. Confirms `H-A-SCHDOT-AREACOLOR` for what its criterion asks, without isolating the area colour.
- **The child sheet.** It attached to the sheet symbol only after Altium's "Synchronize Sheet Entries and
  Ports". After that the project compiled and showed the channels, with designators such as `R1_CH1` and
  `C12_CH1`.
- **The bus.** The bus did not split into the channels: the nets `OUT1` and `OUT2` each held one pin, and
  Altium treated the entry `Repeat(OUT)` as a wire on a bus. **An open defect, not graduated.** Whether it
  lies in the authored sheets (the entries that Altium had to synchronize, the bus that the writer draws
  beside an entry) or in the statement of `H-A-IMP-RPT-NETS` is not known; the follow-up change c0151 is
  proposed for it.
- **Steps R2, R3 and R4.** Not done: owed. `H-A-IMP-RPT-COUNT` (its board half is R3), `H-A-IMP-RPT-NETS`
  and `H-A-IMP-RPT-FORMAT` stay `INFERRED`, the first two with the observation above.

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

### 2026-10-03, `AD 26.5`, Part H, third report (step H7 on the rebuilt example)

- Tool and label as in the first report: Altium Designer 26.5.0 under a trial licence on the
  maintainer's own PC; `ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact)`.
- Files: a fresh copy of the board example as the writer builds it after the second report (project
  file SHA-256 `c7c81bd2346c6070cb6a8d5aa2be76381515391db05113a615a20c6e1e9f1350`, the bytes of variant l).
  Fenolite's built files only; no file opened or saved in the session enters the repository.

Outcome per step:

- **H7, Projects panel.** After "Project » Validate PCB Project" alone, with no dialog, both module
  sheets, `driver` and `led`, are under the top sheet. This repeats variant l on the writer's own
  output (`H-A-SCH-HIER-ORDER`) and confirms `H-A-SCH-HIER-PRJ` for this project: the top sheet, the
  module sheets, the PCB document and the libraries, with no other key. The example holds no harness
  file.
- **H7, change order.** "Design » Update PCB Document" opened an Engineering Change Order. It lists no
  component change, no pin change and no net change: `D1`, which the first report found extra on the
  board, is matched, as `R1` and `U1` are. Confirms `H-A-SCH-HIER-ECO` for parts on module sheets. The
  order proposes only:
  - Remove Net Classes (1): `PWR`. The board holds this class (change c0038) and the schematic declares
    no net class, so Altium offers to remove it. This is not a fault of the link. Change c0048 is to
    declare the net classes in the schematic and write the classes into the board; nothing is changed
    here.
  - Add Component Classes (2): `driver` and `led`; Add Rooms (2); Add Rules (2), "Supply Nets". Altium
    derives these from the sheets, as Part H expects.
- **H7, compile messages.** The dialog showed "Errors occurred during compilation of the project".
  They come from the electrical check of the blink circuit itself: the net `VIN` with one pin, and
  unconnected inputs. No message about a port, a sheet entry or the hierarchy was reported.
- **H3, H4, H5.** Not reported: the rebuilt hierarchy sample was not opened in this session. So the
  "multiple names" warnings of H3 on the rebuilt top sheet, whether Altium makes or rewrites a
  `.Harness` file, the nets in the Navigator panel and the change order into a new PCB document stay
  open. `H-A-SCH-HIER-COMPILE`, `H-A-SCH-HIER-NAMES`, `H-A-SCH-HARN-FILE` and `H-A-SCH-HARN-NETS` stay
  `INFERRED` with `pending (author report)`.
- **Not reported:** a part on the top sheet of a hierarchical project with a board (the example holds
  none), and the project of the hierarchy sample with its harness files in the order written now.

The report names no fault of the written files, so no fact changed in substance, no code changed and
no golden file was rebuilt.

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

## Author report of 2026-10-07 (opening only)

On 2026-10-07 the author reported, for the files he was given: every project opened in Altium Designer 26
(minor version not stated) with no problem, and what he sees looks right to him; on some small components
the names of pins overlap, and he does not know whether that is intended.

- **What he was given.** The session folder built from commit `bc306deb` (Parts Y, W, O, U and X, 63 files
  with their SHA-256) and the kit built from `5adad054`. The three files of Part R were in the same pack; he
  did not say that he opened them.
- **What the report is.** An author report of opening and looking, on files that Fenolite wrote, with a
  licence the author may use for Fenolite.
- **What it is not.** It is not the numbered steps of the Parts. No value was read back (rules and scopes, the
  layer stack, via spans, text positions, keep-out restrictions, title-block fields, outputs and containers),
  and no compile, change order, rule check, repour or output-job run was reported. When this was written no
  file that Altium saved had been received; the folders came back later the same day (next section).
- **A second answer, the same day.** Asked whether any repair, upgrade or conversion prompt appeared
  when he opened the kit's files, and for his minor version, the author answered: "nenhum erro ou pedido
  de restaurar foi feito, tudo abriu como projeto Altium. E meu Altium é o 26" (no error and no request
  to restore was made, everything opened as an Altium project; my Altium is 26). The answer does not use
  the word upgrade and gives no minor version.
- **What it moves.** No level. The two rows whose criterion is opening alone, `H-A-PH-CHECKSUM` and
  `H-A-PH-LAYOUT`, are stated for the author's earlier writer with a value as reported, and the second
  for another version of the tool; this report is about files that Fenolite's writers wrote and names no
  value. Change c0092 restates that family for Fenolite's writers, and the answer above is then the
  author report for the restated rows. The rows whose first step is opening carry a dated partial note in
  `docs/hypotheses.md` (`H-A-SCHX-GRAPHICS`, `H-A-SCHDOT-OPEN`, `H-A-OUTJOB-OPEN`, `H-A-RULE-KINDS`,
  `H-A-PH-CHECKSUM`, `H-A-PH-LAYOUT`), and `H-A-PCB-DOC-OPEN`, which was settled on 2026-10-03, names the
  further documents. Every row that needs a value, one of Altium's engines or the recorded kit run is where
  it was.
- **Observation: names of pins that overlap.** The author named the symbols the same day: `BJT_NPN`,
  `Comparator`, `Operational_Amplifier`, `CONN2` and `Linear_Regulator`, and asked for a correction. A scan of the
  session's schematic libraries with Fenolite's own reader shows where a shown name can collide: a small
  transistor body with three shown names, the triangle of a comparator or an operational amplifier with
  names on four of five pins, and a two-pin connector whose name and number are the same text. The Altium
  writer honours a symbol's hidden pin names, so the likely cause is in the symbol definitions, which leave
  names visible on small discrete symbols; KiCad would then show the same. Change c0134 corrects the
  definitions; the samples it regenerates are new files that this report does not cover.
  2026-10-07, with change c0134: 26 catalog symbols and the four of the example library changed, the
  regenerated files are named with their SHA-256 in Parts L, N and Y above, and the five projects of the
  kit get other schematic bytes on their next build. Nobody has looked at any of them in Altium, and the
  width that the change assumes for Altium's pin text is not measured.
- The steps of the Parts were written from Altium's documentation; a menu path or a dialog name may read
  differently in version 26.

## Returned folders of 2026-10-07

Later on 2026-10-07 the author returned the two folders he had been given, after working in them by hand in
Altium Designer 26 (minor version not stated). He said of the session that all went right, that he saved
some files of the kit, and that the sheet of Part R showed as a page that was all black. Nothing that Altium
wrote is in this repository; the folders were read outside it, on 2026-10-07, with Fenolite's own readers and
`fenolite kit verify` at commit `6f6227eb`.

**What came back.**

- The session folder: its 64 files unchanged, and 21 new ones. A project structure file stands beside nine of
  the ten projects, the mark that Altium compiled them; the project of Part U has none. Under the project of
  Part O are the files that the written output job produced. The reply form of the session's guide was not
  filled, and no note came with the folder.
- The kit: the project file of the sample `flat` rewritten in place by Altium, and saved documents of three
  samples: a schematic document, a PCB document and the project file of `flat`; a schematic library and a
  schematic document of `libs`; a schematic document of `board6`. The kit's form is as built: every value empty.

**What the files show.**

- **Every saved document reads back to the model that was written.** Fenolite's import of each of the five
  saved compound documents equals its import of the file it wrote. The one model difference is on the PCB
  document: a rule `HoleSize` that Altium adds by default. Altium's save adds its own bookkeeping (identifiers
  on records, default parameters of the sheet, default classes and rules around the written ones, further
  storages) and keeps what was written: the nets, the components, the five written rules in keys, values and
  order, the two written classes, the six title-block values, the class settings of the project file.
- **The output job runs, except for its Gerber output.** NC drill, pick and place, the bill of materials and a
  schematic and PCB print of two pages were produced, each into the container of its kind. The drill files
  hold 7 holes of 0.3 mm and 2 of 0.9 mm, which are the seven vias and the two pads of the through-hole part of
  the written board; the three placement rows hold the three components on their sides at the positions of the
  model (Altium reports the centre of a part's pads, not its reference point). **No Gerber layer file was
  produced**: the report of that output names no layer, and its aperture files are empty, with no error
  message. The written job holds no settings record for the Gerber output (a decision of change c0087: the
  job holds outputs, sources and containers and no setting), and for this one output Altium's default
  plots nothing. That is a defect of the written job. Change c0138 writes the settings record of the Gerber
  output, with the plotted layers taken from the board.
- **The kit.** `fenolite kit verify` on the folder as returned fails every step of the sample `flat` for one
  reason: step K1.5 (save the project under another name) made Altium rewrite the kit's own project file,
  which then differs from its digest. With that file restored from the history copy that Altium left beside
  it, steps K1.1, K1.2, K1.3, K1.5 and K9.1 pass (the saved schematic document, PCB document, schematic
  library and project file are read and are equal to the samples at the levels the steps name), and no step
  fails on a difference. The other steps have no file or no form value. This is not a recorded kit run:
  `fenolite kit record` refuses a folder whose kit files changed and whose form is empty. The defects this
  showed in the kit itself (the step that rewrites a kit file, wrong expected values printed for integer
  steps, a path that the kit's privacy check does not list, a step that cannot tell an update from a save) are
  change c0139.
- **Part R, the black page.** The two sheets of Part R were authored record by record, outside the schematic
  writer, and their sheet record holds no area colour and their objects no colour; every sheet that the
  schematic writer writes, and every sheet Altium saved, holds an area colour. An absent colour most likely
  reads as black. The files of Part R are to be authored again with the writer's colours; until then Part R
  has no outcome. 2026-10-08, change c0146: they are authored again, through the schematic writer itself, and
  are in the folder of session 2 (Part R above, with the new SHA-256); nobody has opened them.
- **Two equal fonts are saved as one.** The schematic document of the kit sample `flat` was written with a
  font table of four entries, the first two both Times New Roman of size 10 (the system font, and the first
  font of the drawing sheet, declared without looking at it); the copy that Altium saved holds three, and
  the labels of the drawing sheet name the renumbered entries (S-0610; one file). Change c0146 makes the
  writer hold each distinct font once: 10, 5 and 7 points for that sample. That is all the change claims;
  whether a table with equal entries is an error for Altium is not known (`H-A-SCHDOT-FONT-MERGE`).

**What it moves.** No level. The reply form was not filled, so no row that needs a value read from a dialog or
a message panel has its value; the kit rows need a recorded run. Recorded in `docs/hypotheses.md` as
observations, with the rows left where they were: `H-A-OUTJOB-RUN` (five kinds generated, the Gerber kind
not) and `H-A-OUTJOB-OPTIONS` (the default of the Gerber output plots no layer), both waiting for the author
to state the outcome and his minor version; `H-A-KIT-SCRIPT` (the author reports that the first call of the
script probe, `Client.GetServerRecordCount`, is not known to Altium Designer 26; he did not go on with the
script). The structure files of Part Y list the sheet tree of step Y4, and five of the six outputs of Part O
exist: both support their rows and settle neither, because the step's own report is missing.

What the saved files show of the formats (keys that Altium adds, drops or reorders on a save) is input for
the format pages and is recorded there in a change of its own.

## Pin visibility bits (author reports of 2026-10-08, change c0148)

Two author reports of the same day, in Altium Designer 26, settle what bits 0x08 and 0x10 of a pin's
`PINCONGLOMERATE` mean (`H-A-SCHLIB-PINBITS`). The photos are the maintainer's and are not committed.

**First report: files written before change c0148 (S-0612).** In session 2 the maintainer looked at the
LED `D1` of the kit sample `flat` (the catalog LED; its pins written with `PINCONGLOMERATE` 18 and 16,
0x10 set and 0x08 clear, meant as "number shown, name hidden"). The Properties panel (Pins) marked both
numbers hidden and both names visible, and the names K and A were drawn on the sheet. The LED
`Mini:Mini_LED` of a build of `examples/blink_routed` (pins written with 2 and 0, no bit set) showed both
names and both numbers. On the narrow LED body the two visible names crossed over, each ending past the
middle, so K stood beside the anode pin and A beside the cathode, and the maintainer read the LED as
reversed. The electrical side was right: PCB pad 1 is `GND` (cathode), pad 2 `LED_A`, and Altium listed
"Pin 1 = K, Pin 2 = A" by pad number from the map records. The overlapping pin names of the report of
2026-10-07 (above) most likely have the same cause: Fenolite wrote 0x08 to show a name, and Altium showed
the names that the symbols meant hidden.

**Second report: the check project `tests/data/altium/pinbits/` (S-0613).** The public sources read the
two bits as show flags (S-0130, S-0131), and every pin that Altium saved in the corpus holds bit 0x20, which
Fenolite never wrote (S-0614, table below). The check project holds the catalog LED four times, every pin
with 0x20 set: V1 0x20, V2 0x20 | 0x10, V3 0x20 | 0x08, V4 0x20 | 0x18. Opened in Altium Designer
Professional 26.5.0, V1 showed neither number nor name, V2 the numbers only, V3 the names only, V4 both:
the expected answer.

| file | SHA-256 |
|---|---|
| `pinbits.PrjPcb` | `da8fcf56f329256a9932eec8ee3e6203bc0f836f04d75d77e8e5fa6cef521cde` |
| `pinbits.SchDoc` | `d0cc87c9cc2b3c8f074bde153a3a9b04323fdf3c383323927e3e9b1fa98ef491` |
| `pinbits.SchLib` | `1211bea9e16da5a98b1bf4430c109c03404da4c5e4b16bdc6c5a614a6ea3e68b` |

**Corpus census (S-0614; measured 2026-10-08 with Fenolite's own reader; held by `tests/corpus/test_altium_pin_bits.py`).** 4 175 pins: 2 974 in 36 of the
38 schematic documents (two hold no pin) and 1 201 in the 9 libraries. Every one holds 0x20. By the bits
0x08 and 0x10 and the number of pins of the owning component:

| pins of | owner | neither | 0x10 only | 0x08 only | both |
|---|---|---|---|---|---|
| documents | at most 3 pins | 1 233 | 105 | 17 | 12 |
| documents | more than 3 pins | 47 | 77 | 69 | 1 414 |
| libraries | at most 3 pins | 75 | 40 | 24 | 2 |
| libraries | more than 3 pins | 4 | 493 | 134 | 429 |

The small components of the documents are resistors, capacitors and test points whose pins are named `1`
and `2`; the large ones name their pins (`VCC`, `EN`, `TX1_P`). Read as show flags, the split is the usual
one: passives hide pin texts, integrated circuits show them.

**What it settles.** With 0x20 set, 0x08 shows the name and 0x10 the number; without 0x20, Altium
Designer 26 reads the same two bits as hide flags (only the values 0, 2, 16 and 18 were seen without 0x20).
Change c0148 writes 0x20 on every pin with the two bits as show flags, and the reader takes them as show
flags with 0x20 and as hide flags without it. Files written before 0.3.0 show pin names that their symbols
meant hidden and hide numbers that were meant shown; built again, their pins take the form of the check project. Nobody has
opened a rebuilt kit or session file in Altium yet.

**What moved in this page.** The tables that name committed files (`tests/data/altium/…`) carry the new
digests; every committed schematic document and library differs from its former bytes in bit 0x20 of each
pin alone (`tests/_pin_bits.py`). The tables that name the files in the maintainer's session folders
(Parts L, N, W, Y and R) keep the digests of what he was given: those files hold pins without 0x20.

## Session 2 of 2026-10-08

The maintainer's second session of Altium work, in Altium Designer 26.5.0 on his own PC (S-0615), on the
session pack built from commit `695574ba`. What it gave for the schematic side:

- **Part O** (change c0138): every output of the job with the Gerber settings record was produced, Gerber
  layer files among them; `H-A-OUTJOB-RUN-2` is confirmed and the rows that need a value of the setup stay
  pending (Part O, "Reports").
- **Part P** (change c0148): the pin visibility bits, recorded under "Pin visibility bits" above.
- **Part S** (change c0134): the five symbols the author named on 2026-10-07 (`BJT_NPN`, `Comparator`,
  `Operational_Amplifier`, `Linear_Regulator`, `CONN2`), on the sheet `simbolos.SchDoc` of the pack. His
  answer to step S1: "ficou bom" (it looked good). No pin text over another text or a line was reported.
  No register row names this check: change c0134 registered none, and `H-A-SCHX-GRAPHICS` asks for the
  four symbols of Part Y against their pictures, which this step did not compare. The pack's symbols hold
  pins without bit 0x20 (it was built before change c0148).
- **Part R** (changes c0083 and c0146): step R1 only, under Part R above. The sheets are no longer black;
  the bus of `Repeat(OUT)` does not split into the channels, an open defect.
- **Not done, owed:** steps R2 to R4 of Part R, the Part K kit run (see `docs/evidence/altium-kit/README.md`
  for the maintainer's decision on it), and Parts X8, V and G of the PCB page.

The maintainer also stated, for the record of 0.3.0, that the schematic libraries, PCB libraries,
schematic documents and PCB documents that Fenolite writes were opened and compiled in Altium Designer 24
before and in 26 now. That is an author report of opening and compiling without a step, a value or a
version beyond the major; it raises no row and no release claim.
