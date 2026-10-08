# Altium verification kit: steps

Work on this folder only, and change no file outside `results/`. Do the steps in order. A step ends in a file that Altium writes under `results/`, or in a value that you type into `results/form.json` under `values`. First fill `altium_version` (as `AD <major>.<minor>`), `os_family` and `date` of that form.

A step marked *scripted* may be done by the kit script instead: open `kit_script.pas` in Altium, focus the sample's project, run File » Run Script and choose `FenoliteKitRun`. The manual instruction of such a step is complete without the script. Before you use the script for the first time, open it in Altium's script editor and compile it: its calls were written from a rendering of Altium's documentation and it has not run in Altium. If a line is refused, report that line and do the scripted steps by hand.

A saved file may hold your user name or the path of a folder: a document that Altium saves names its own file with the folder it was saved in. `fenolite kit verify` lists what it finds; read that list before you publish anything.

Altium may write a sample's own project file again when it saves the project (step K1.5 does). `fenolite kit verify` accepts a project file of the kit that still lists exactly the sample's documents; any other file of the kit that changed fails every step of its sample.

## K1: Open and save each document kind

A file that Fenolite wrote is loaded and written again in Altium's own bytes. About 10 minutes.

- [ ] **K1.1** (`flat`): Open `flat/flat.PrjPcb` with File » Open Project and open `flat.SchDoc`. Save it with File » Save As as `results/flat/flat.SchDoc`.
  Result: file `results/flat/flat.SchDoc`. Checked: the re-saved document passes RT-A0 and RT-A1, and its import equals the import of the kit's own document at every level of `equivalent` that the document holds; the stage `parity` of `fenolite check`, run on the sample's project with the saved document in the place of the kit's own, reports what it reports on the kit's own project.
  Settles: `H-A-KIT-RESAVE`, `H-A-WRITE-SCHDOC`, `H-A-PH-ZERO-FIELDS`.

- [ ] **K1.2** (`flat`): Open `flat.PcbDoc` of the same project. Save it with File » Save As as `results/flat/flat.PcbDoc`.
  Result: file `results/flat/flat.PcbDoc`. Checked: the re-saved document passes RT-A0 and RT-A1, and its import equals the import of the kit's own document at every level of `equivalent` that the document holds; the stage `parity` of `fenolite check`, run on the sample's project with the saved document in the place of the kit's own, reports what it reports on the kit's own project.
  Settles: `H-A-KIT-RESAVE`, `H-A-WRITE-PCBDOC`, `H-A-PH-ZERO-FIELDS`.

- [ ] **K1.3** (`libs`): Open `libs/libs.PrjPcb` and open `libs.SchLib`. Save it with File » Save As as `results/libs/libs.SchLib`.
  Result: file `results/libs/libs.SchLib`. Checked: the re-saved document passes RT-A0 and RT-A1, and its import equals the import of the kit's own document at every level of `equivalent` that the document holds.
  Settles: `H-A-KIT-RESAVE`, `H-A-WRITE-SCHLIB`, `H-A-PH-ZERO-FIELDS`.

- [ ] **K1.4** (`libs`): Open `libs.PcbLib` of the same project. Save it with File » Save As as `results/libs/libs.PcbLib`.
  Result: file `results/libs/libs.PcbLib`. Checked: the re-saved document passes RT-A0 and RT-A1, and its import equals the import of the kit's own document at every level of `equivalent` that the document holds.
  Settles: `H-A-KIT-RESAVE`, `H-A-WRITE-PCBLIB`, `H-A-PH-ZERO-FIELDS`.

- [ ] **K1.5** (`flat`): With `flat.PrjPcb` focused, save the project with File » Save Project As as `results/flat/flat.PrjPcb`. Then close the project without saving anything else.
  Result: file `results/flat/flat.PrjPcb`. Checked: the re-saved document passes RT-A0 and RT-A1, and its import equals the import of the kit's own document at every level of `equivalent` that the document holds.
  Settles: `H-A-KIT-RESAVE`.

- [ ] **K1.6** (`flat`): Open `flat/ascii/flat.SchDoc` with File » Open. Save it with File » Save As as `results/flat/flat_ascii.SchDoc`, in the format that Altium offers first.
  Result: file `results/flat/flat_ascii.SchDoc`. Checked: the re-saved document passes RT-A0 and RT-A1, and its import equals the import of the kit's own document at every level of `equivalent` that the document holds; the stage `parity` of `fenolite check`, run on the sample's project with the saved document in the place of the kit's own, reports what it reports on the kit's own project.
  Settles: `H-A-KIT-RESAVE`, `H-A-WRITE-SCHDOC`.

- [ ] **K1.7** (`tree`): Open `tree/tree.PrjPcb` and its four schematic documents. Save each with File » Save As under its own name in `results/tree/`; this step's file is `results/tree/tree.SchDoc`.
  Result: file `results/tree/tree.SchDoc`. Checked: the re-saved document passes RT-A0 and RT-A1, and its import equals the import of the kit's own document at every level of `equivalent` that the document holds.
  Settles: `H-A-KIT-RESAVE`, `H-A-WRITE-SCHDOC`, `H-A-SCHX-TREE`.

- [ ] **K1.8** (`flat`): Type whether any document of the steps K1.1 to K1.7 showed a repair prompt, an upgrade prompt or an error dialog when it was opened or saved.
  Result: form field `K1.8` (bool), expected `false`.
  Settles: `H-A-WRITE-SCHDOC`, `H-A-WRITE-PCBDOC`, `H-A-WRITE-SCHLIB`, `H-A-WRITE-PCBLIB`, `H-A-PH-CHECKSUM`, `H-A-PH-LAYOUT`, `H-A-PH-ZERO-FIELDS`.

## K2: Compile and messages

Each sample project is validated and its messages are kept. About 8 minutes.

- [ ] **K2.1** *(scripted)* (`flat`): With `flat.PrjPcb` open and focused, run Project » Validate PCB Project. Then select every row of the Messages panel, copy the rows into `results/flat/messages.txt`, one per line with the class first, or write the one line `no messages` when the panel is empty.
  Result: file `results/flat/messages.txt`. Checked: the file holds at least one line and no line of the class Error or Fatal Error.
  Settles: `H-A-KIT-COMPILE`, `H-A-KIT-SCRIPT`, `H-A-PH-NO-CACHE`, `H-A-WRITE-SCHDOC`.

- [ ] **K2.2** *(scripted)* (`tree`): With `tree.PrjPcb` open and focused, run Project » Validate PCB Project. Then select every row of the Messages panel, copy the rows into `results/tree/messages.txt`, one per line with the class first, or write the one line `no messages` when the panel is empty.
  Result: file `results/tree/messages.txt`. Checked: the file holds at least one line and no line of the class Error or Fatal Error.
  Settles: `H-A-KIT-COMPILE`, `H-A-KIT-SCRIPT`, `H-A-PH-NO-CACHE`, `H-A-SCHX-TREE`.

- [ ] **K2.3** *(scripted)* (`routed`): With `routed.PrjPcb` open and focused, run Project » Validate PCB Project. Then select every row of the Messages panel, copy the rows into `results/routed/messages.txt`, one per line with the class first, or write the one line `no messages` when the panel is empty.
  Result: file `results/routed/messages.txt`. Checked: the file holds at least one line and no line of the class Error or Fatal Error.
  Settles: `H-A-KIT-COMPILE`, `H-A-KIT-SCRIPT`, `H-A-PH-NO-CACHE`, `H-A-WRITE-PCBDOC`.

- [ ] **K2.4** *(scripted)* (`board6`): With `board6.PrjPcb` open and focused, run Project » Validate PCB Project. Then select every row of the Messages panel, copy the rows into `results/board6/messages.txt`, one per line with the class first, or write the one line `no messages` when the panel is empty.
  Result: file `results/board6/messages.txt`. Checked: the file holds at least one line and no line of the class Error or Fatal Error.
  Settles: `H-A-KIT-COMPILE`, `H-A-KIT-SCRIPT`, `H-A-PH-NO-CACHE`.

- [ ] **K2.5** *(scripted)* (`libs`): With `libs.PrjPcb` open and focused, run Project » Validate PCB Project. Then select every row of the Messages panel, copy the rows into `results/libs/messages.txt`, one per line with the class first, or write the one line `no messages` when the panel is empty.
  Result: file `results/libs/messages.txt`. Checked: the file holds at least one line and no line of the class Error or Fatal Error.
  Settles: `H-A-KIT-COMPILE`, `H-A-KIT-SCRIPT`, `H-A-PH-NO-CACHE`, `H-A-WRITE-SCHLIB`, `H-A-WRITE-PCBLIB`.

## K3: Change order into an empty board

The schematic of `flat` fills a new PCB document. About 8 minutes.

- [ ] **K3.1** (`flat`): Add a PCB document to the project `flat` with File » New » PCB and save it as `results/flat/eco.PcbDoc`. Run Design » Update PCB Document eco.PcbDoc, validate and execute the changes, and save the document.
  Result: file `results/flat/eco.PcbDoc`. Checked: the document's import equals the import of the kit's own document at levels 1 and 2 of `equivalent` (components and nets); the stage `parity` of `fenolite check`, run on the sample's project with the saved document in the place of the kit's own, reports what it reports on the kit's own project.
  Settles: `H-A-KIT-COMPILE`.

- [ ] **K3.2** (`flat`): Type the number of changes of the change order of step K3.1 that were marked invalid.
  Result: form field `K3.2` (int), expected `0`.
  Settles: `H-A-KIT-COMPILE`.

## K4: Rules editor and rule check

The rules of `routed` and its two planted violations. About 8 minutes.

- [ ] **K4.1** (`routed`): Open `routed/routed.PcbDoc` and Design » Rules. Type whether the editor lists the five rules of the table below with the values of the table, and no second rule of the kinds Clearance and Width.
  Result: form field `K4.1` (bool), expected `true`.
  Settles: `H-A-RULE-KINDS`.

- [ ] **K4.2** (`routed`): Run Tools » Design Rule Check with the report file enabled and press Run Design Rule Check. Save the report that Altium writes as `results/routed/drc.html`.
  Result: file `results/routed/drc.html`. Checked: the file exists and is not empty; Fenolite's copper check finds the one planted clearance violation between `VIN` and `LED_A`, no other and no short: on the kit's own board when the step leaves a report, and on the re-saved board, with no polygon left out, when the step leaves the board.
  Settles: `H-A-KIT-DRC`.

- [ ] **K4.3** (`routed`): Type the number of violations of the report of step K4.2 that name the Width rule of the class `PWR`.
  Result: form field `K4.3` (int), expected `1`.
  Settles: `H-A-KIT-DRC`, `H-A-RULE-SCOPE`.

- [ ] **K4.4** (`routed`): Type the number of violations of the same report that name the Clearance rule between the nets `VIN` and `LED_A`.
  Result: form field `K4.4` (int), expected `1`.
  Settles: `H-A-KIT-DRC`, `H-A-RULE-SCOPE`.

## K5: Layer stack, vias, texts, keep-outs

The board items of `board6`. Component bodies are written on request only and `board6` holds none: no step of the kit reads them (step X8 of the author report does, on the sample `body2`). About 10 minutes.

- [ ] **K5.1** (`board6`): Open `board6/board6.PrjPcb` and, of its documents, **the PCB document** `board6.PcbDoc`. Save it with File » Save As as `results/board6/board6.PcbDoc`.
  Result: file `results/board6/board6.PcbDoc`. Checked: the re-saved document passes RT-A0 and RT-A1, and its import equals the import of the kit's own document at every level of `equivalent` that the document holds; the stage `parity` of `fenolite check`, run on the sample's project with the saved document in the place of the kit's own, reports what it reports on the kit's own project.
  Settles: `H-A-KIT-RESAVE`, `H-A-WRITE-PCBDOC`.

- [ ] **K5.2** (`board6`): Open Design » Layer Stack Manager. Type the number of copper layers it lists.
  Result: form field `K5.2` (int), expected `6`.
  Settles: `H-A-PCBX-STACK`.

- [ ] **K5.3** (`board6`): Select each of the three vias. Type whether they span the layers of the table below: one through, one blind, one buried.
  Result: form field `K5.3` (bool), expected `true`.
  Settles: `H-A-PCBX-VIASPAN`.

- [ ] **K5.4** (`board6`): Select the keep-out. Type whether its restrictions are vias and tracks, and no other.
  Result: form field `K5.4` (bool), expected `true`.
  Settles: `H-A-PCBX-KEEPOUT`.

- [ ] **K5.5** (`board6`): Read the four texts. Type whether each has the string, the layer and the rotation of the table below.
  Result: form field `K5.5` (bool), expected `true`.
  Settles: `H-A-PCBX-TEXT`.

## K6: Repour

The polygon of `routed` is poured by Altium. About 4 minutes.

- [ ] **K6.1** (`routed`): In `routed.PcbDoc` run Tools » Polygon Pours » Repour All. Save the document with File » Save As as `results/routed/routed.PcbDoc`.
  Result: file `results/routed/routed.PcbDoc`. Checked: the re-saved document passes RT-A0 and RT-A1, and its import equals the import of the kit's own document at every level of `equivalent` that the document holds; the stage `parity` of `fenolite check`, run on the sample's project with the saved document in the place of the kit's own, reports what it reports on the kit's own project; every polygon of the re-saved board holds poured copper; Fenolite's copper check finds the one planted clearance violation between `VIN` and `LED_A`, no other and no short: on the kit's own board when the step leaves a report, and on the re-saved board, with no polygon left out, when the step leaves the board.
  Settles: `H-A-KIT-REPOUR`, `H-A-KIT-RESAVE`, `H-A-PCBX-REPOUR`.

## K7: Output job

The output job of `routed` opens and generates its containers. About 6 minutes.

- [ ] **K7.1** (`routed`): Open `routed.OutJob` from the Projects panel. Type whether it opens without a message and lists the six outputs of the table below.
  Result: form field `K7.1` (bool), expected `true`.
  Settles: `H-A-OUTJOB-OPEN`.

- [ ] **K7.2** (`routed`): Generate the container `fab`, then the container `doc`. Write the names of the generated files, one per line and without their folders, into `results/routed/outputs.txt`.
  Result: file `results/routed/outputs.txt`. Checked: the file holds at least one line, and no line holds a folder.
  Settles: `H-A-OUTJOB-RUN`, `H-A-OUTJOB-RUN-2`.

## K8: Sheet template and special strings

The sheet template and the title block of `flat`. About 5 minutes.

- [ ] **K8.1** (`kit`): Open `templates/iso5457_generic.SchDot` with File » Open. Save it with File » Save As as `results/templates/iso5457_generic.SchDot`.
  Result: file `results/templates/iso5457_generic.SchDot`. Checked: the file exists and is not empty.
  Settles: `H-A-SCHDOT-OPEN`.

- [ ] **K8.2** (`flat`): Open `flat.SchDoc` and read the title block. Type the title it shows.
  Result: form field `K8.2` (text), expected `Flat`.
  Settles: `H-A-SCHDOT-STRINGS`.

- [ ] **K8.3** (`flat`): Type the revision that the same title block shows.
  Result: form field `K8.3` (text), expected `B`.
  Settles: `H-A-SCHDOT-STRINGS`.

## K9: Libraries

The schematic of `libs` is updated from the libraries that Fenolite wrote. About 5 minutes.

- [ ] **K9.1** (`libs`): Open `libs.SchDoc` and run Tools » Update From Libraries with full replacement for every part. Save the document with File » Save As as `results/libs/libs.SchDoc`.
  Result: file `results/libs/libs.SchDoc`. Checked: the document's import equals the import of the kit's own document at levels 1 and 2 of `equivalent` (components and nets); the stage `parity` of `fenolite check`, run on the sample's project with the saved document in the place of the kit's own, reports what it reports on the kit's own project.
  Settles: `H-A-SCHLIB-UPDATE`.

- [ ] **K9.2** (`libs`): Type the number of parts that the update of step K9.1 reported as not found.
  Result: form field `K9.2` (int), expected `0`.
  Settles: `H-A-SCHLIB-UPDATE`.

## Values the steps read

Rules of `routed` (step K4.1). The values are shown in the unit Altium is set to.

| kind | scope | second scope | value |
|---|---|---|---|
| Clearance | net `VIN` | net `LED_A` | 1.5 mm |
| Clearance | all | all | 0.15 mm |
| Clearance | net class `PWR` | all | 0.2 mm |
| Width | net class `PWR` | | minimum and preferred 0.6 mm, maximum 2 mm |
| Width | all | | minimum 0.15 mm, preferred 0.25 mm, maximum 2 mm |

Planted violations of `routed` (steps K4.3 and K4.4): one `VIN` track that is 0.5 mm wide, and one `VIN`
via and one `LED_A` via whose edges are 0.6 mm apart.

Vias of `board6` (step K5.3), in millimetres from the upper-left corner of the outline:

| via | position | net | span |
|---|---|---|---|
| 1 | (10, 18.81) | `VIN` | top layer to bottom layer (through) |
| 2 | (38, 9) | `LED_A` | top layer to the first inner layer (blind) |
| 3 | (20, 24) | `GND` | first inner layer to the plane below it (buried) |

Texts of `board6` (step K5.5):

| string | layer | rotation |
|---|---|---|
| `Tensão 5 V` | Top Overlay | 0 |
| `BOARD6 REV A` | Bottom Overlay | 0, mirrored |
| `ASSEMBLY TOP` | Mechanical 13 | 0 |
| `BOTTOM` | Mechanical 14 | 90, mirrored |

Outputs of `routed.OutJob` (step K7.1):

| output | source | container |
|---|---|---|
| Gerber Files | `routed.PcbDoc` | `fab` |
| NC Drill Files | `routed.PcbDoc` | `fab` |
| Pick and Place | `routed.PcbDoc` | `fab` |
| Bill of Materials | the project | `fab` |
| Schematic Prints | the project | `doc` |
| PCB Prints | `routed.PcbDoc` | `doc` |
