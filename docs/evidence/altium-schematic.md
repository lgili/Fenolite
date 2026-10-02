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
- `kicad-cli` cannot read a `.SchDoc` (S-0132, S-0020), so this check is the first reading of the files by
  a program other than Fenolite.

## Part A: the committed sample

The sample is the CC0 design `examples/altium_sample/design.py`. Its files are committed under
`tests/data/altium/sample/`, and `tests/unit/lens/test_altium_golden.py` checks that a fresh build gives the
same bytes and that this table names them.

| file | SHA-256 |
|---|---|
| `tests/data/altium/sample/altium_sample.PrjPcb` | `608d67d64ad32c26dc8c91d67cf271a26ab797d09c1ba4e4115451c75032c50d` |
| `tests/data/altium/sample/altium_sample.SchDoc` | `4321d13f3f51f4088611676ac2c787a12df6970b39679aa570caa6e083915bc4` |
| `tests/data/altium/sample/variants/altium_sample_lf.SchDoc` | `ae32cc71f50a4eaf55f4704f9a8ed173d73391a2977f2dc9f45c80e778fcaaec` |
| `tests/data/altium/sample/variants/altium_sample_nouid.SchDoc` | `dade6d1fb12846fa5b6bf7f03162178d8ddc5e3a397aa58ed071182778980fe3` |

- `altium_sample.SchDoc` is an ASCII schematic ("SCH ASCII Version 5.0") with CR LF line ends: 123 lines,
  the header and 122 records. It holds an A4 sheet, 8 components with 19 pins, 19 wire stubs, 13 power
  ports (`GND` 6, `VIN` 3, `+5V` 4) and 6 net labels (`EN`, `LED_DRV` and `LED_A`, two each). Row one
  holds `J1`, `R2`, `U2`, `D1`; row two holds `R1`, `C1`, `C2`, `U1`.
- `altium_sample_lf.SchDoc` is the same file with every CR LF replaced by LF.
  `altium_sample_nouid.SchDoc` is the same file with every `|UNIQUEID=…` field removed.
- The project file lists `altium_sample.SchDoc` only. The libraries the sample names,
  `FenoliteSample.SchLib` and `FenoliteSample.PcbLib`, do not exist; Part A needs none.
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

## Recording a report

- A report gives the Altium Designer version as `AD <major>.<minor>`, the date, and one outcome per step
  in generic format terms, under "Reports" below.
- A confirmed row gets `ALTIUM-VERIFIED(author-report; AD <major>.<minor or x>; <YYYY-MM-DD>; no artefact)`.
- A refuted row keeps its id, its result starts with `refuted; superseded by <id>-2`, and a successor row
  states what Altium did.
- Without a report, a row stays `INFERRED` with a result that starts with `pending (author report)`.
- `tests/unit/test_altium_rows.py` checks the form of these rows.

## Reports

None yet.
