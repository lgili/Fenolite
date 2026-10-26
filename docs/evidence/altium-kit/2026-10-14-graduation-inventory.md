# Native kit evidence reconciliation, 2026-10-14

Published run `2026-10-13-87c930fa` settles 27 candidates listed by `kit record`.
Their register results retain historical notes and distinguish typed `form` values.
The eight former earlier-writer/AD 24.x descriptions now name Fenolite-authored
kit artifacts and the recorded AD 26.5 scope; no AD 24.x verification is claimed.
The DRC criterion compares Width/Clearance only; all seven native violations are retained.
See [publication provenance](2026-10-13-87c930fa-publication.md).

The following inventory covers every remaining write-cell hypothesis, plus
acceptance and kit families. These rows have no passing verdict in this run;
their levels remain unchanged. Already established independent evidence is
retained; its absence from this kit does not refute it or require repetition.

Task 4.1 adds 13 existing schematic/library presentation hypotheses to the
matrix's write declarations, so this inventory now covers 115 remaining rows.
Those facts were previously present only in the build envelope; their levels
and recorded observations are unchanged.

| hypothesis | current level | remaining kit support or independent criterion |
|---|---|---|
| H-A-ACC-KIT | INFERRED | No passing verdict in this run; still requires its stated proof: recorded run contains no failed step in those groups |
| H-A-ACC-V03 | KICAD-VERIFIED (10.0.x) | Independent evidence already established; no new kit verdict. Criterion: probe acceptance-v03 equals on KiCad 10.0.6 with triangle-profile exclusions |
| H-A-CONV-DIFAT | INFERRED | No passing verdict in this run; still requires its stated proof: both reads equal the source; the probe `convert-difat` `equal` on 10.0.6; T1 reported as expected |
| H-A-CONV-LIBRARY | INFERRED | No passing verdict in this run; still requires its stated proof: T5 proposes no change of footprint and T6 places one footprint from the library, both reported as expected |
| H-A-CONV-PADSTACK | INFERRED | No passing verdict in this run; still requires its stated proof: the read-back is equal per copper layer; the probe `convert-padstack` `equal` on 10.0.6; T6 reported as expected |
| H-A-CONV-SCHEMATIC | INFERRED | No passing verdict in this run; still requires its stated proof: levels 1 and 2 report no difference; T2 reported as expected (no error, the messages counted) |
| H-A-ECO-COMPCLASS | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-04; no artefact) | No passing verdict in this run; still requires its stated proof: no "Add Component Classes" and no component class member change |
| H-A-ECO-NETCLASS | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-04; no artefact) | No passing verdict in this run; still requires its stated proof: no "Remove Net Classes" and no net class member change in the change order |
| H-A-ECO-PRJ-KEYS | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-04; no artefact) | No passing verdict in this run; still requires its stated proof: both module sheets under the top sheet; "Generate Net Classes" ticked, "Component Classes" ticked and "Generate Rooms" unticked per sheet |
| H-A-ECO-ROOMS | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-04; no artefact) | No passing verdict in this run; still requires its stated proof: no "Add Rooms" in the change order |
| H-A-ECO-SHEETCLASS | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-04; no artefact) | No passing verdict in this run; still requires its stated proof: the change order of the flat routed sample lists no "Add Component Classes" and no "Add Rooms" |
| H-A-ECO-SUPPLY | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-04; no artefact) | No passing verdict in this run; still requires its stated proof: the change order is empty, or holds only "Add Rules" entries named "Supply Nets" |
| H-A-KIT-STABLE | INFERRED | No passing verdict in this run; still requires its stated proof: equal digests in the `unit` jobs of Linux, macOS and Windows |
| H-A-OUTJOB-GERBER-ACCEPT | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-09; no artefact) | No passing verdict in this run; still requires its stated proof: no message; units, format and plotted layers as the table sent. When refuted, the next candidate is the field `DocumentPath`, which one of the two public records holds |
| H-A-OUTJOB-GERBER-LAYERS | INFERRED | No passing verdict in this run; still requires its stated proof: the count of layer files equals the count of entries; the list of extensions is reported |
| H-A-OUTJOB-GERBER-RECORD | INFERRED | No passing verdict in this run; still requires its stated proof: the names and their order equal `outjob.GERBER_FIELDS` in every public job with a Gerber output; every output of the three public jobs holds `OutputDefault<i>=0` after its last container key |
| H-A-OUTJOB-READBACK | INFERRED | No passing verdict in this run; still requires its stated proof: equal groups for the default preset and for three authored jobs; the bytes are the committed sample |
| H-A-PCB-CU-CLASS | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: `PWR` with `GND` and `VIN` |
| H-A-PCB-CU-KICAD | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | Independent evidence already established; no new kit verdict. Criterion: exit 0, no error; every item within 10 nm; four copper layers with the expected types |
| H-A-PCB-CU-LOCK | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-09; no artefact) | No passing verdict in this run; still requires its stated proof: read back by Fenolite's reader: the three items locked, the others not; the author report: the three items shown locked in Altium Designer 26, the others not |
| H-A-PCB-CU-PLANE | INFERRED | No passing verdict in this run; still requires its stated proof: Internal Plane 1 on `GND` in the Layer Stack Manager; no connection line on `GND` |
| H-A-PCB-CU-REPOUR | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: two outlines; after the repour, copper on `In1.Cu` and `B.Cu` connected to `GND` |
| H-A-PCB-CU-ROUNDTRIP | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | Independent evidence already established; no new kit verdict. Criterion: every track, arc, via and zone outline within 10 nm, none added, footprints at the source's placements |
| H-A-PCB-CU-RULES | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: five rules in the rules editor; the design rule check runs |
| H-A-PCB-CU-STACK | INFERRED | No passing verdict in this run; still requires its stated proof: four signal layers in the Layer Stack Manager; no repair |
| H-A-PCB-CU-TRACK | INFERRED | No passing verdict in this run; still requires its stated proof: no prompt; no connection line on a routed net |
| H-A-PCB-CU-VIA | INFERRED | No passing verdict in this run; still requires its stated proof: three vias with the listed sizes and nets |
| H-A-PCB-CU-VIATENT | INFERRED | No passing verdict in this run; still requires its stated proof: the report names the four vias with the expected tenting; the unit test proves only that Fenolite reads back what it wrote |
| H-A-PCB-CU-VIEWER | INFERRED | No passing verdict in this run; still requires its stated proof: tracks, vias and four layers visible |
| H-A-PCB-DOC-BOTTOM | INFERRED | No passing verdict in this run; still requires its stated proof: `D1` matches its KiCad build |
| H-A-PCB-DOC-LINK | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: no component is added or removed |
| H-A-PCB-DOC-NETS | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: no net change |
| H-A-PCB-DOC-OPEN | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: no repair prompt |
| H-A-PCB-DOC-VIEWER | ALTIUM-VERIFIED(author-report; A365 Viewer; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: the outline, three components, their pads and designators are shown |
| H-A-PCB-ECO | INFERRED | No passing verdict in this run; still requires its stated proof: no footprint is reported as not found |
| H-A-PCB-GRAPHICS | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: the outlines are visible on the mapped layers |
| H-A-PCB-KICAD-DOC | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | Independent evidence already established; no new kit verdict. Criterion: exit 0; no error in the report or on stdout; equal references, pad nets and relative positions |
| H-A-PCB-KICAD-LIB | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | Independent evidence already established; no new kit verdict. Criterion: one `.kicad_mod` per footprint; pads and graphics within 10 nm |
| H-A-PCB-LIB-NAME | INFERRED | No passing verdict in this run; still requires its stated proof: the long name is shown |
| H-A-PCB-LIB-OPEN | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: the footprints are listed, with no repair prompt |
| H-A-PCB-PAD | INFERRED | No passing verdict in this run; still requires its stated proof: shapes, sizes and holes as in the page's pad table |
| H-A-PCB-PRJ | INFERRED | No passing verdict in this run; still requires its stated proof: both are listed in the project |
| H-A-PCBX-BODY-2D | CORPUS-VERIFIED | Independent evidence already established; no new kit verdict. Criterion: exact on every such body |
| H-A-PCBX-BODY-FORM | CORPUS-VERIFIED | Independent evidence already established; no new kit verdict. Criterion: every extruded body of every cached row holds every row marked "every record"; the rows come from at least three repositories; each row with exceptions holds within its stated count |
| H-A-PCBX-BODY-ID | INFERRED | No passing verdict in this run; still requires its stated proof: the counts are recorded; the row is a measurement, not a pass or fail |
| H-A-PCBX-BODY-KICAD | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-07) | Independent evidence already established; no new kit verdict. Criterion: probe `altium-pcbx-bodies` `equal` |
| H-A-PCBX-BODY-LIB | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-09; no artefact) | No passing verdict in this run; still requires its stated proof: the body is listed in the footprint with its heights |
| H-A-PCBX-BODY-OPEN | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-09; no artefact) | No passing verdict in this run; still requires its stated proof: the three bodies read as the table sent with the files |
| H-A-PCBX-BODY-READBACK | INFERRED | No passing verdict in this run; still requires its stated proof: equal for `body2`, top and bottom, at 0, 90 and 30 degrees |
| H-A-PCBX-BODY-SHORT | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-09; no artefact) | No passing verdict in this run; still requires its stated proof: the three bodies read as the table sent with the files |
| H-A-PCBX-BUILD-LOWER | INFERRED | No passing verdict in this run; still requires its stated proof: no file under `tests/data/altium/` changes; the pins move by `.fenolite/board.json` alone |
| H-A-PCBX-FPGFX | INFERRED | No passing verdict in this run; still requires its stated proof: equal within 2 nm for the own samples, on both sides |
| H-A-PCBX-FPGFX-AD | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-09; no artefact) | No passing verdict in this run; still requires its stated proof: steps G1 to G7 |
| H-A-PCBX-FPGFX-KICAD | ORACLE-VERIFIED(kicad-cli) (10.0.6, pinned image, local run; 2026-10-09) | Independent evidence already established; no new kit verdict. Criterion: equal counts per footprint and layer class on the listed rewrites |
| H-A-PCBX-FPTEXT | INFERRED | No passing verdict in this run; still requires its stated proof: position, height and `visible` read back equal |
| H-A-PCBX-HOLE | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-09; no artefact) | No passing verdict in this run; still requires its stated proof: the pad properties show plated off and the hole size |
| H-A-PCBX-KICAD | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-06) | Independent evidence already established; no new kit verdict. Criterion: probe `altium-pcbx-<kind>` `equal` for each kind KiCad imports; the kinds it does not import are listed |
| H-A-PCBX-MECH | INFERRED | No passing verdict in this run; still requires its stated proof: read back on `Mech.<n>`; a document that uses none of the twelve keeps its bytes |
| H-A-PCBX-READBACK | INFERRED | No passing verdict in this run; still requires its stated proof: equal for `board6` and for the routed samples |
| H-A-PCBX-VIA-FULL | CORPUS-VERIFIED | Independent evidence already established; no new kit verdict. Criterion: the public document holds such records, each of that form; its rewrite holds every one of them and is equal inside the scope |
| H-A-PRJ-OPEN | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: the project opens with the schematic listed, and compiles |
| H-A-RULE-CLEARANCE-CELLS | INFERRED | No passing verdict in this run; still requires its stated proof: Altium's rule check reports no violation for the pair of vias and one for a via and a track at the same distance |
| H-A-RULE-CLEARANCE-FORMS | INFERRED | No passing verdict in this run; still requires its stated proof: Altium reports each planted pair under the rule the neutral mapping gives it, and none under the inner-layer rule |
| H-A-RULE-FILE | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-09; no artefact) | No passing verdict in this run; still requires its stated proof: the import succeeds without a message and the rules of the imported kind equal those of U1 |
| H-A-RULE-PRIORITY | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-09; no artefact) | No passing verdict in this run; still requires its stated proof: the planted track inside the class is judged by the class rule `Width_PWR`, not by `Width` |
| H-A-RULE-READBACK | INFERRED | No passing verdict in this run; still requires its stated proof: equal for the example scripts that write a PCB document and for the generated rule sets |
| H-A-SCH-HARN-FILE | INFERRED | No passing verdict in this run; still requires its stated proof: no "conflicting harness definition" message; the files are not rewritten with other content |
| H-A-SCH-HARN-NETS | INFERRED | No passing verdict in this run; still requires its stated proof: each `SPI_*` net has one pin on each module sheet |
| H-A-SCH-HARN-OPEN | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: each connector shows four entries and the type `SPI`; a harness line joins it to its port or sheet entry |
| H-A-SCH-HARN-UNUSED | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: no error names `HOLD`; the nets equal the model's |
| H-A-SCH-HIER-COMPILE | INFERRED | No passing verdict in this run; still requires its stated proof: no message about ports, sheet entries or duplicate net names |
| H-A-SCH-HIER-ECO | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: H5: six components and nine nets added, validated; H7: no component or net change proposed |
| H-A-SCH-HIER-NAMES | INFERRED | No passing verdict in this run; still requires its stated proof: exactly the nine net names of the sample, each with the model's pins |
| H-A-SCH-HIER-OPEN | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: no prompt or repair offer; two sheet symbols with five entries; five ports |
| H-A-SCH-HIER-ORDER | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: on a fresh copy, after "Validate PCB Project" and without any dialog, both module sheets of the board example are under the top sheet |
| H-A-SCH-HIER-PRJ | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: the Projects panel shows the top sheet with two children |
| H-A-SCH-LINEEND | INFERRED | No passing verdict in this run; still requires its stated proof: the CR LF sample opens; the LF variant's outcome is recorded |
| H-A-SCH-LINK | INFERRED | No passing verdict in this run; still requires its stated proof: the values equal the written ones; another mode refutes the row, and its successor states the mode |
| H-A-SCH-NETS | INFERRED | No passing verdict in this run; still requires its stated proof: the 6 nets of the page's table with exactly their pins; no message of level error or fatal |
| H-A-SCH-OPEN | INFERRED | No passing verdict in this run; still requires its stated proof: no error, warning dialog or repair prompt; an A4 sheet; 8 components with 19 pins, 13 power ports and 6 net labels |
| H-A-SCH-UID | INFERRED | No passing verdict in this run; still requires its stated proof: no unique-identifier message on compile; the 8 values are kept; the outcome of the variant without ids is recorded |
| H-A-SCHBIN-AD | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: no error, warning dialog or repair prompt; the Navigator nets equal the table |
| H-A-SCHBIN-CFB | ALTIUM-VERIFIED(author-report; A365 Viewer; 2026-10-02; no artefact) | No passing verdict in this run; still requires its stated proof: the Viewer or Altium Designer opens it without an error about the file |
| H-A-SCHBIN-FRAME | ALTIUM-VERIFIED(author-report; A365 Viewer; 2026-10-02; no artefact) | No passing verdict in this run; still requires its stated proof: 8 components with their pin numbers, designators and comments, 13 power ports and 6 net labels are shown |
| H-A-SCHBIN-STORAGE | ALTIUM-VERIFIED(author-report; A365 Viewer; 2026-10-02; no artefact) | No passing verdict in this run; still requires its stated proof: no message about a missing or damaged stream or image |
| H-A-SCHBIN-VIEWER | INFERRED | No passing verdict in this run; still requires its stated proof: V1 and V2 render the sample; the V3 message or render is recorded |
| H-A-SCHDOT-READBACK | INFERRED | No passing verdict in this run; still requires its stated proof: equal for the two shipped sheet examples on each of their sizes and for the authored sheet, in both forms, and no warning of the import |
| H-A-SCHLIB-IMPLIDX | INFERRED | No passing verdict in this run; still requires its stated proof: the footprint model shows the written name and library; another mode or an empty library refutes the row |
| H-A-SCHLIB-KICAD | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | Independent evidence already established; no new kit verdict. Criterion: every symbol converts with the source's units and per-pin fields; every negative control exits non-zero |
| H-A-SCHLIB-OPEN | INFERRED | No passing verdict in this run; still requires its stated proof: no error, warning dialog or repair prompt; the SCH Library panel lists every component with its description |
| H-A-SCHLIB-PARTS | INFERRED | No passing verdict in this run; still requires its stated proof: the dual-unit symbol shows parts A and B, each with its own pins and the two power pins |
| H-A-SCHLIB-PIN | INFERRED | No passing verdict in this run; still requires its stated proof: every pin's number, name, electrical type, direction, length, shape and visibility equals the page's table |
| H-A-SCHLIB-PINBITS | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-08; no artefact) | No passing verdict in this run; still requires its stated proof: V1 shows neither text, V2 the numbers only, V3 the names only, V4 both; every Altium-saved pin of the corpus holds 0x20 |
| H-A-SCHLIB-SECTIONKEY | INFERRED | No passing verdict in this run; still requires its stated proof: the keyed symbol is listed under its full name |
| H-A-SCHX-BUS | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-09; no artefact) | No passing verdict in this run; still requires its stated proof: the nets of the bus in Altium's netlist equal the model's |
| H-A-SCHX-DIR | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-09; no artefact) | No passing verdict in this run; still requires its stated proof: no message on `tree`; one message on `tree-bad` |
| H-A-SCHX-ECO | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-09; no artefact) | No passing verdict in this run; still requires its stated proof: the counts equal the table sent |
| H-A-SCHX-GRAPHICS | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-09; no artefact) | No passing verdict in this run; still requires its stated proof: the four sample symbols match the reference pictures sent with the files; the four regenerated samples open |
| H-A-SCHX-READBACK | INFERRED | No passing verdict in this run; still requires its stated proof: equal for the `tree` sample (both forms, `flat` and `modules`) and for every example script (both forms, both symbol bodies) |
| H-A-SCHX-TEXT | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-09; no artefact) | No passing verdict in this run; still requires its stated proof: the two sample strings read as written |
| H-A-VER-RTA2-3 | INFERRED | No passing verdict in this run; still requires its stated proof: equal for every example script, both schematic forms, with no kind only counted |
| H-A-VER-RTA3 | CORPUS-VERIFIED | Independent evidence already established; no new kit verdict. Criterion: equal on every listed corpus document, from at least three repositories; the unwritten counts are recorded per kind |

| H-A-PRJ-KEEP | INFERRED | No passing verdict in this run; still requires its stated proof: both documents listed after the rebuild; the change order runs; the key names Altium added are recorded |
| H-A-SCH-ECO | INFERRED | No passing verdict in this run; still requires its stated proof: every component and net added; no change marked invalid |
| H-A-SCH-NC-ERC | INFERRED | No passing verdict in this run; still requires its stated proof: no message names pins 2, 4 or 8; a floating-input message names pin 3 |
| H-A-SCH-NC-RECORD | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: no prompt or repair offer; three directives at the ends of `U1` pins 2, 4 and 8 |
| H-A-SCH-NC-VIEWER | INFERRED | No passing verdict in this run; still requires its stated proof: three crosses at the marked pins |
| H-A-SCH-RELINK | INFERRED | No passing verdict in this run; still requires its stated proof: one modification listed, and no component added or removed |
| H-A-SCH-UPDATE | INFERRED | No passing verdict in this run; still requires its stated proof: the parts are found; the count of unconnected pins after full replacement is recorded; every net is kept after the selected-attributes update |
| H-A-SCHLIB-KICAD9 | ORACLE-VERIFIED(kicad-cli) (9.0.9, pinned image, local run; 2026-10-02) | No passing verdict in this run; still requires its stated proof: the same comparisons pass, or the failure message is recorded and the test is expected to fail on major 9 |
| H-A-SCHLIB-MULTIPART | INFERRED | No passing verdict in this run; still requires its stated proof: `U1` compiles as one component with parts A and B and no duplicate-designator or unique-id message |
| H-A-SCHLIB-PRJ | ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact) | No passing verdict in this run; still requires its stated proof: the library is listed under the project's source documents and found by the update |
| H-A-SCHLIB-SCHDOC | INFERRED | No passing verdict in this run; still requires its stated proof: the Navigator nets equal the page's tables; no message of level error or fatal |
| H-A-SCHX-PINMAP | INFERRED | No passing verdict in this run; still requires its stated proof: the relation read back equals the model's in both schematic forms and in the library, for both values of `altsym.MAP_RECORDS_FOR_EVERY_PIN`; Altium shows the written pads on the pins |
| H-A-SCHX-PINMAP-FORM | CORPUS-VERIFIED | No passing verdict in this run; still requires its stated proof: over the public project sets `altium-set:02` to `altium-set:05`: no record names the pin's own pad alone, a model with fewer records than pins exists, and every record starts at `DESIMP0` |

No write kind graduates from this reconciliation alone. Task 4.1 applies the
complete rule, including own readback, model RT-A3 and every cell hypothesis.
