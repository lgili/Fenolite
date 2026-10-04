## ADDED Requirements

### Requirement: Classes in an Altium build
`lens.altium.build_altium` SHALL write the net classes of the design into the schematic and the project file, and the component classes of the module sheets into the PCB document, so that "Design » Update PCB Document" proposes no class change (`H-A-ECO-NETCLASS`, `H-A-ECO-COMPCLASS`, `H-A-ECO-ROOMS`).
- A design with a net class MUST get the directives of "Net class directives on the sheet" on every sheet, in both sheet modes and in both schematic forms, with or without a PCB document, and the `[PrjClassGen]` section of "Class generation keys of the project file".
- A build that writes a PCB document or module sheets MUST get the three class keys in the section of every schematic document, and a PCB document MUST hold the records of "Component class records": one class per sheet that holds a component, in both sheet modes.
- The net classes of the schematic and of the PCB document MUST agree: each class of `Classes6` with `KIND=0` holds exactly the nets that carry a directive of that class, for every net that has a pin.
- A net class name that the schematic cannot hold MUST give the issue `altium.text-unwritable` with severity `error`, whether or not a PCB document is planned, and no file.
- Without a PCB document, the issue `altium.not-lowered` for net classes MUST say that their rule values are kept in the model only: the members are in the schematic.
- A design without a net class, built with the single sheet and without a PCB document, MUST keep every byte it had before this change.
- No room and no "Supply Nets" rule is written (`H-A-ECO-SUPPLY`; "Change order differences are documented").

#### Scenario: Board example
- **WHEN** `fenolite build examples/altium_hier_board/design.py --out B --target altium --altium-sheets modules --confirm --json` runs into an empty folder
- **THEN** the exit code is 0; the sheets read back hold `GND` and `VIN` in the class `PWR`; `altium_hier_board.PrjPcb` ends with the `[PrjClassGen]` section and holds `ClassGenCCAutoRoomEnabled=0` three times; and `Classes6` of the PCB document holds `PWR`, `driver` and `led`

#### Scenario: Flat routed sample
- **WHEN** the routed sample is built with the single sheet
- **THEN** `routed.SchDoc` holds two directives of the class `PWR`; `routed.PrjPcb` holds the three class keys once, in the section of `routed.SchDoc`, and ends with the `[PrjClassGen]` section; and `Classes6` of `routed.PcbDoc` holds the net class `PWR` and the component class `routed` with `D1`, `R1` and `U1`

#### Scenario: Net class name the schematic cannot hold
- **WHEN** a design whose net class is named `=PWR` is built without a board
- **THEN** the build reports `altium.text-unwritable` naming the class and writes no file

#### Scenario: Design without a class keeps its bytes
- **WHEN** `uv run pytest tests/unit/lens/test_altium_golden.py tests/unit/lens/test_altium_binary_golden.py tests/unit/lens/test_altium_schlib_golden.py tests/unit/lens/test_altium_no_connect_golden.py` runs
- **THEN** it passes without any golden file of those samples being rewritten

### Requirement: Change order sample and author report
The golden files SHALL be rebuilt, and `docs/evidence/altium-pcb.md` SHALL hold Part E, the protocol of the change order in Altium Designer.
- The golden files whose design holds a net class, module sheets or a board MUST be rebuilt with `FENOLITE_GOLDEN_WRITE=1`: the schematic, the project file and the document of the blink and routed samples, and `altium_hier.PrjPcb`. Every other golden file MUST keep its bytes, and the pages that name a SHA-256 of a rebuilt file, or of the plane variant `p0`, MUST name the new one. A sentence of an earlier report keeps the digest it reported.
- `tests/unit/lens/test_altium_eco.py` MUST build the board example with module sheets and the routed sample, and check the scenarios of "Classes in an Altium build" on the files read back.
- Part E MUST hold these steps, each with the hypotheses it settles, on a fresh copy of each sample:
  - E1: open the project of the board example and run "Project » Validate PCB Project"; both module sheets are under the top sheet (`H-A-ECO-PRJ-KEYS`, `H-A-SCH-HIER-ORDER`);
  - E2: "Project » Project Options", tab "Class Generation": "Generate Net Classes" under "User-Defined Classes" is ticked, and each sheet has "Component Classes" ticked and "Generate Rooms" unticked (`H-A-ECO-PRJ-KEYS`);
  - E3: from the top sheet run "Design » Update PCB Document"; the change order proposes no removal of a net class, no component class and no room (`H-A-ECO-NETCLASS`, `H-A-ECO-COMPCLASS`, `H-A-ECO-ROOMS`); note every group it still proposes, the "Supply Nets" rules included (`H-A-ECO-SUPPLY`);
  - E4: the same three steps on the routed sample, a single sheet: no net class change, no component class and no room (`H-A-ECO-NETCLASS`, `H-A-ECO-SHEETCLASS`).
- A report follows "PCB author reports" of c0035: tool as `AD <major>.<minor>`, the date, one generic outcome per step, no artefact, and only Fenolite's built files opened.
- The report of 2026-10-04 (AD 26.5) MUST be recorded under "Reports": the change order of the board example lists only two "Supply Nets" rules; that of the routed sample, then without class key and component class, lists the component class `routed`, a room and two "Supply Nets" rules, and no net class removal.
- `docs/hypotheses.md` MUST register the six rows `H-A-ECO-NETCLASS`, `H-A-ECO-PRJ-KEYS`, `H-A-ECO-COMPCLASS`, `H-A-ECO-ROOMS`, `H-A-ECO-SUPPLY` and, after that report, `H-A-ECO-SHEETCLASS`; the first five carry the report's label and the sixth stays pending until step E4 is repeated. `docs/evidence/sources.md` MUST register S-0310 to S-0313. The project file of S-0313 and the files of S-0187, S-0188, S-0172, S-0175, S-0199 and S-0200 never enter the repository.

#### Scenario: Golden files after the rebuild
- **WHEN** `uv run pytest tests/unit/lens -k "golden"` runs
- **THEN** every fresh build equals its committed files, and `git diff --stat HEAD~ -- tests/data/altium/sample tests/data/altium/no_connect tests/data/altium/kicad_example` lists no file

#### Scenario: Registers hold the new rows
- **WHEN** `grep -cE '^\| H-A-ECO-' docs/hypotheses.md` and `grep -cE '^\| S-031[0-3] ' docs/evidence/sources.md` run
- **THEN** they print `6` and `4`, and `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_altium_rows.py` passes

#### Scenario: Protocol names the steps
- **WHEN** `grep -cE '^- \*\*E[1-4]' docs/evidence/altium-pcb.md` runs
- **THEN** it prints `4`

### Requirement: Change order differences are documented
`docs/altium.md` SHALL hold a section "Change order" that says what the build writes for it and what Altium may still propose.
- It MUST say that a net class is declared by a directive on each of its nets and by the project option, and that every sheet with a part gives a component class in the PCB document, named after the module or after the sheet.
- It MUST list the remaining differences with their reason: the "Supply Nets" rules, which Altium suggests for each net with a power port when its advanced setting `Schematic.AutoGenerateSupplyNetsRule` is on (S-0185, S-0312), which only add rules, and which Fenolite does not write because no permitted source holds the record; rooms, which the project key turns off and which Fenolite does not write; and the component class and room of a flat build, pending the repeat of step E4.
- It MUST say that an existing `<name>.PrjPcb` is kept, so the class keys reach only a project file that the build writes.
- The row `altium.not-lowered` of the issue table MUST match the new message for net classes.

#### Scenario: Section exists
- **WHEN** `grep -c "^## Change order" docs/altium.md` and `grep -c "AutoGenerateSupplyNetsRule" docs/altium.md` run
- **THEN** each prints `1` or more
