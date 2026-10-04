## ADDED Requirements

### Requirement: Net class directives on the sheet
`backends.altium.schdoc.schdoc_records` SHALL write one Parameter Set directive with a `ClassName` parameter for each `layout.ClassMark` of `SheetPlan.class_marks`, so that the schematic declares the net classes of the design (S-0310, S-0311, S-0187; `H-A-ECO-NETCLASS`).
- `project.net_class_names(design)` MUST return net name → class name for every net whose `netclass_id` names a net class of the design.
- `project.class_marks(plan, classes, sheet)` MUST return one `ClassMark` per net of `classes` that has a stub on the sheet, in code-point order of the net names. The stub is the first stub of that net in write order (`plan.links`, then `plan.stubs`). A net without a stub on the sheet gets no mark there.
- The mark's point MUST lie on the stub, 200 mil from its start when the stub is 300 mil long or longer, and 100 mil from its start otherwise, so it is never an end of the wire and never the hotspot of a net label.
- `project.plan_sheet` and `hierarchy.plan_sheets` MUST fill `class_marks` on every sheet they plan, the single sheet, the top sheet and each module sheet alike. `sheet` is the sheet's file name.
- Per mark, two records MUST be written, after the No ERC directives and in mark order:
  - the directive, with the keys in this order: `RECORD=43`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the mark's point), `COLOR=255`, `ORIENTATION=3` for a horizontal stub and no `ORIENTATION` for a vertical stub, `NAME=Parameter Set` and `UNIQUEID` = `unique_id("netclass:<sheet>:<net>")`;
  - its parameter, with the keys in this order: `RECORD=41`, `OWNERINDEX` (the index of the directive), `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the same point), `COLOR=8388608`, `FONTID=1`, `ISHIDDEN=T`, `TEXT` (the class name), `NAME=ClassName` and `UNIQUEID` = `unique_id("netclass:<sheet>:<net>:name")`.
- Both forms, ASCII and binary, MUST hold the same records. A plan without a mark MUST keep the bytes it had before this change.
- A class name that fails `ascii.text_problem(name, parameter=True)` MUST raise `ValueError`.

#### Scenario: Directive of the blink sample
- **WHEN** the single sheet of the blink sample, whose class `PWR` holds `GND` and `VIN`, is written and its records are read
- **THEN** its last four records are a record 43 at a point of a `GND` stub, a record 41 with `NAME=ClassName`, `TEXT=PWR` and `ISHIDDEN=T` owned by it, and the same pair for `VIN`

#### Scenario: One directive per sheet and net
- **WHEN** `examples/altium_hier_board/design.py` is planned with `sheets="modules"`
- **THEN** the sheet `driver` holds two marks, `GND` and `VIN`, the sheet `led` holds one mark, `GND`, and the top sheet holds none

#### Scenario: Sheet without a net class
- **WHEN** the sample of c0032, which holds no net class, is written in either form
- **THEN** the bytes equal the committed golden files of `tests/data/altium/sample/`

#### Scenario: Class name that a parameter cannot hold
- **WHEN** `project.class_marks` is given the class name `=PWR`
- **THEN** it raises `ValueError` naming the class

### Requirement: Class generation keys of the project file
`backends.altium.prjpcb.write_prjpcb(*, schematic, pcb=None, libraries=(), sheets=(), harnesses=(), net_classes=False)` SHALL write the class generation options that a clean change order needs (S-0310, S-0187, S-0188, S-0313; `H-A-ECO-PRJ-KEYS`, `H-A-ECO-ROOMS`). This requirement extends "Project file" and "Project file of a multi-sheet project", whose rules hold.
- With `sheets` not empty or with `pcb` given, the section of every schematic document, the single or top sheet and each module sheet, MUST hold three more lines after `DocumentPath`, in this order: `ClassGenCCAutoEnabled=1`, `ClassGenCCAutoRoomEnabled=0` and `ClassGenNCAutoScope=None`. The sections of the other documents MUST hold `DocumentPath` alone. A flat project needs the keys too: without them the change order of Altium Designer 26.5 proposed a room for the single sheet (report of Part E, 2026-10-04; `H-A-ECO-SHEETCLASS`).
- With `net_classes` true, the file MUST end with an empty line, `[PrjClassGen]` and the seven lines `CompClassManualEnabled=0`, `CompClassManualRoomEnabled=0`, `NetClassAutoBusEnabled=1`, `NetClassAutoCompEnabled=0`, `NetClassAutoNamedHarnessEnabled=0`, `NetClassManualEnabled=1` and `NetClassSeparateForBusSections=0`, in this order.
- With `sheets` empty, `pcb` not given and `net_classes` false, the bytes MUST hold `DocumentPath` lines only, as before this change.
- `project.write_project` MUST pass `net_classes=True` exactly when the design holds a net class.
- That Altium reads these keys from a file that holds no other option, and still takes every module sheet into the hierarchy (`H-A-SCH-HIER-ORDER`), is `H-A-ECO-PRJ-KEYS`.

#### Scenario: Project of a flat design with a net class
- **WHEN** `write_prjpcb(schematic="a.SchDoc", net_classes=True)` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=a.SchDoc\r\n\r\n[PrjClassGen]\r\nCompClassManualEnabled=0\r\nCompClassManualRoomEnabled=0\r\nNetClassAutoBusEnabled=1\r\nNetClassAutoCompEnabled=0\r\nNetClassAutoNamedHarnessEnabled=0\r\nNetClassManualEnabled=1\r\nNetClassSeparateForBusSections=0\r\n"`

#### Scenario: Project with a module sheet
- **WHEN** `write_prjpcb(schematic="a.SchDoc", sheets=("a_x.SchDoc",), pcb="a.PcbDoc")` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=a.SchDoc\r\nClassGenCCAutoEnabled=1\r\nClassGenCCAutoRoomEnabled=0\r\nClassGenNCAutoScope=None\r\n\r\n[Document2]\r\nDocumentPath=a_x.SchDoc\r\nClassGenCCAutoEnabled=1\r\nClassGenCCAutoRoomEnabled=0\r\nClassGenNCAutoScope=None\r\n\r\n[Document3]\r\nDocumentPath=a.PcbDoc\r\n"`

#### Scenario: Flat project with a PCB document
- **WHEN** `write_prjpcb(schematic="x.SchDoc", pcb="x.PcbDoc")` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=x.SchDoc\r\nClassGenCCAutoEnabled=1\r\nClassGenCCAutoRoomEnabled=0\r\nClassGenNCAutoScope=None\r\n\r\n[Document2]\r\nDocumentPath=x.PcbDoc\r\n"`

#### Scenario: Unchanged without classes and sheets
- **WHEN** `write_prjpcb(schematic="altium_sample.SchDoc", libraries=("FenoliteSample.SchLib",))` is called
- **THEN** it returns the bytes of the scenario "Project with a library" of "Project file"

### Requirement: Net class directives read back
The test reader `tests/_altium_read.py` SHALL rebuild the net classes of a written sheet from its records alone, written from `docs/formats/altium/schematic-ascii.md` without importing the product's writers.
- `net_classes_from_sheet(records)` MUST return net name → class name: for each record 43 that owns a record 41 named `ClassName`, the net is the name of the net label or power port on the wire that holds the directive's location.
- A directive whose location lies on no wire, or on a wire end, or on a wire without a name, and a net that two directives put in two classes, MUST raise `ReadError`.

#### Scenario: Classes of the built samples
- **WHEN** every sheet of the built blink sample and of the built board example is read in both forms
- **THEN** the union of `net_classes_from_sheet` over the sheets of each project equals `project.net_class_names` of its design: `GND` and `VIN` in `PWR`

#### Scenario: Directive off its wire
- **WHEN** the location of a directive is moved 10 mil off its stub and the sheet is read
- **THEN** `net_classes_from_sheet` raises `ReadError`

## MODIFIED Requirements

### Requirement: Project file
`backends.altium.prjpcb.write_prjpcb(*, schematic, pcb=None, libraries=())` SHALL return the bytes of the lines `[Design]`, `Version=1.0`, an empty line, `[Document1]` and `DocumentPath=<schematic>`; then, when `pcb` is given, an empty line, `[Document2]` and `DocumentPath=<pcb>`; then for each library, i from the next free number, an empty line, `[Document<i>]` and `DocumentPath=<library>`, each line ending with CR LF, in 7-bit ASCII and without a byte-order mark (S-0132, S-0134, S-0143).
- `<schematic>`, `<pcb>` and each `<library>` are bare file names, because the files sit beside the project (S-0132). Libraries, schematic (`.SchLib`) and PCB (`.PcbLib`) alike, MUST be in the MS-CFB order of their names (`cfb.name_key`), and a name holding `/` or `\` MUST raise `ValueError`.
- That Altium takes a listed `.SchLib` as a project library, which "Tools » Update From Libraries" searches, is `H-A-SCHLIB-PRJ`. That it shows a listed `.PcbLib` and `.PcbDoc` as project documents, and that the change order finds footprints in the listed `.PcbLib`, are `H-A-PCB-PRJ` and `H-A-PCB-ECO`.
- That Altium opens this file, takes defaults for every other key, and needs no byte-order mark is `H-A-PRJ-OPEN`.
- With `pcb` given, the section of the schematic also holds the three class keys of "Class generation keys of the project file" (change c0048), after its `DocumentPath`.

#### Scenario: Project of the sample
- **WHEN** `write_prjpcb(schematic="altium_sample.SchDoc")` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=altium_sample.SchDoc\r\n"`

#### Scenario: Project with a library
- **WHEN** `write_prjpcb(schematic="altium_sample.SchDoc", libraries=("FenoliteSample.SchLib",))` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=altium_sample.SchDoc\r\n\r\n[Document2]\r\nDocumentPath=FenoliteSample.SchLib\r\n"`

#### Scenario: Project with a PCB document and two libraries
- **WHEN** `write_prjpcb(schematic="blink.SchDoc", pcb="blink.PcbDoc", libraries=("blink.SchLib", "blink.PcbLib"))` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=blink.SchDoc\r\nClassGenCCAutoEnabled=1\r\nClassGenCCAutoRoomEnabled=0\r\nClassGenNCAutoScope=None\r\n\r\n[Document2]\r\nDocumentPath=blink.PcbDoc\r\n\r\n[Document3]\r\nDocumentPath=blink.PcbLib\r\n\r\n[Document4]\r\nDocumentPath=blink.SchLib\r\n"`

### Requirement: Project file of a multi-sheet project
`backends.altium.prjpcb.write_prjpcb(*, schematic, pcb=None, libraries=(), sheets=(), harnesses=(), net_classes=False)` SHALL list every document in its own section, an empty line, `[Document<i>]` and `DocumentPath=<file>`, numbered from 1 without a gap, in this order: the top sheet `schematic`, each module sheet of `sheets`, the PCB document `pcb` when given, the libraries, and each harness definition file of `harnesses` (S-0132, S-0134, S-0187, S-0188). This requirement extends "Project file", whose rules hold.
- `sheets` MUST be written in the order given (module-name order). The libraries and `harnesses` MUST each be written in the MS-CFB order of their names (`cfb.name_key`). A name holding `/` or `\` MUST raise `ValueError`.
- Every schematic document MUST precede every other document, and the top sheet MUST be `[Document1]`. With the minimal project file, Altium Designer 26.5 took only the first module sheet into the hierarchy when the PCB document and the libraries stood between the top sheet and the module sheets, and took both with the schematic documents listed first (variant l of step H7 of the report of 2026-10-03; `H-A-SCH-HIER-ORDER`).
- With `sheets` and `harnesses` empty, the bytes MUST equal those of "Project file": `[Document1]` is the schematic and `[Document2]` the PCB document when there is one.
- The order holds for a file that is written. An existing `<name>.PrjPcb` is kept as it is (`altium-build`, "Edited Altium outputs are not overwritten").
- With `sheets` not empty or `pcb` given, each schematic section also holds the three class keys of "Class generation keys of the project file" (change c0048); the `DocumentPath` lines and their order do not change.
- No key names the top sheet or the net scope: Altium finds the top sheet from the sheet symbols and takes its default scope (S-0185, S-0187, S-0188; `H-A-SCH-HIER-PRJ`, `H-A-SCH-HIER-COMPILE`).

#### Scenario: Project with a module sheet and a harness file
- **WHEN** `write_prjpcb(schematic="a.SchDoc", sheets=("a_x.SchDoc",), harnesses=("a.Harness",))` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=a.SchDoc\r\nClassGenCCAutoEnabled=1\r\nClassGenCCAutoRoomEnabled=0\r\nClassGenNCAutoScope=None\r\n\r\n[Document2]\r\nDocumentPath=a_x.SchDoc\r\nClassGenCCAutoEnabled=1\r\nClassGenCCAutoRoomEnabled=0\r\nClassGenNCAutoScope=None\r\n\r\n[Document3]\r\nDocumentPath=a.Harness\r\n"`: each schematic section holds the three class keys of "Class generation keys of the project file"

#### Scenario: Unchanged without sheets
- **WHEN** `write_prjpcb(schematic="blink.SchDoc", pcb="blink.PcbDoc", libraries=("blink.SchLib", "blink.PcbLib"))` is called
- **THEN** it returns the bytes of the scenario "Project with a PCB document and two libraries" of "Project file"

#### Scenario: Project of the hierarchy sample
- **WHEN** `altium_hier.PrjPcb` of the sample's `modules` build is read
- **THEN** its `DocumentPath` lines are, in order, `altium_hier.SchDoc`, `altium_hier_flash.SchDoc`, `altium_hier_mcu.SchDoc`, `FenoliteHier.SchLib`, `altium_hier_mcu.Harness` and `altium_hier_flash.Harness`

#### Scenario: Project of the board example
- **WHEN** `examples/altium_hier_board/design.py` is built with `sheets="modules"` and its project file is read
- **THEN** its `DocumentPath` lines are, in order, `altium_hier_board.SchDoc`, `altium_hier_board_driver.SchDoc`, `altium_hier_board_led.SchDoc`, `altium_hier_board.PcbDoc`, `altium_hier_board.PcbLib` and `altium_hier_board.SchLib`, so every `.SchDoc` precedes every other document
