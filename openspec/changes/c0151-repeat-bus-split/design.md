## Outcome in one paragraph

The report of 2026-10-08 has two symptoms, the child sheet that attaches only after a dialog and the bus that does not split. Neither the corpus (no `Repeat` statement in any of its 38 schematic documents, no sheet entry or port on a bus) nor Altium's pages (one example, `Repeat(Headphone)`, with no figure text) shows a working `Repeat` bus in records. The records of the sample were therefore compared, record by record, with what the corpus holds and with what the public pages say, and each difference was ranked against the messages. The change makes the two differences that the evidence supports, and nothing else: the bus label leaves the connection point, and the project file carries the corpus's net and compile keys. The check folder separates the two.

## Context

- The sample (c0083, authored again through the schematic writer by c0146): on `two.SchDoc` the sheet symbol `Repeat(CH,1,2)` (record 15 at (70, 670) in 10-mil units, 150 wide) with the entries `VCC` (`DISTANCEFROMTOP=1`) and `Repeat(OUT)` (`=2`) on its right side; the entry `Repeat(OUT)` meets the bus `OUT[1..2]` at (220, 650), the start of the bus line; two bus entries and the labelled wires `OUT1` and `OUT2`; `U1` pins 1 and 2 on wires labelled `OUT1` and `OUT2`. On `two_ch.SchDoc` the ports `VCC` and `OUT` on the ends of `R1` pin 1 and `C12` pin 2, and `MID`.
- The warning names the point (2200 mil, 6500 mil): that is (220, 650), the connection point of the entry and the start of the bus. The bus does reach the entry: the same geometry (right side, `LOCATION.X + XSIZE`, `LOCATION.Y - 10 × DISTANCEFROMTOP`) puts 139 of the 251 corpus sheet entries on the end of a wire.
- Before this change the bus's net label `OUT[1..2]` lay at (220, 650) too: on the connection point of the sheet entry, while the label of the plain entry `VCC` lies 100 mil along its wire (230, 660).

## The messages, read against Altium's pages

From the pages of the project's violations (S-0707, "Validating your design project" and its violation pages, read 2026-10-08):

- `Missing child-sheet in <SymbolFileName> in Symbol <SymbolDesignator>`: "a sheet symbol points to a document that is missing, misspelled, or blank". The file name record says `two_ch.SchDoc`, which is the second document of the project file, letter for letter; the same symptom, a module sheet left out until the same dialog was opened, was seen on 2026-10-03 (Part H, step H7) and cured there by the order of the documents (`H-A-SCH-HIER-ORDER`). The sample's order is already the cured one (top sheet, then the child).
- `Duplicate Net Names <Object> <NetName>`, with the object `Wire`: two nets of one name; the example given is a continuity break by "ports or sheet entries with different names". Before the sync, the entry `Repeat(OUT)` named a wire net `Repeat(OUT)` (sheet entries name nets: `AllowSheetEntryNetNames`, on in five of six corpus projects).
- "Mismatched Bus or Wire Object on Wire or Bus" (the `… placed on a bus` warning): a single-signal object, by its name, connected to a bus; "for a sheet entry, edit its Name". So Altium judged the entry of channel 1, `CH1-Repeat(OUT)`, to be a wire object on a bus, by its literal name.
- `Net <name> has only one pin (Pin <pin>)`: `OUT1` holds `U1-1` alone, so `C12_CH1` pin 2 did not join it. `VCC` raised no such error, so the plain entry and the port that lies on a pin end without a wire do join across the hierarchy, and the child's ports are not floating.

## Hypotheses, ranked

1. **B1, the bus label on the connection point** (`H-A-SCHRPT-BUSLABEL`). The net label `OUT[1..2]` lay exactly on the connection point of the sheet entry `Repeat(OUT)`. A net label attaches to whatever its hotspot touches, pins included (S-0140), so Altium may have bound the bus name to the entry object itself, not only to the bus. Evidence for: it is the one record difference between the sample and the corpus that sits at the reported point; no corpus sheet entry (0 of 251) and no corpus port (0 of 208) has a label on its connection point (S-0706); the writer's own wire labels lie 100 mil along the wire; "Bus OUT[1..2]" twice in the duplicate-name message fits two objects carrying the bus name. Evidence against: none found; a bus label at a line's end is legal drawing in Altium's pages. **Changed here** (writer-wide).
2. **B2, the sync dialog renamed the port** (no row: it is a question to the maintainer). Matching an entry to a port in "Synchronize Sheet Entries and Ports" renames the port to the entry's name (S-0185, page read again 2026-10-08). If the maintainer matched `Repeat(OUT)` with `OUT`, the child then held a port `Repeat(OUT)`, which joins the entry as a plain name, and the split cannot happen; the warning and both errors follow. Evidence for: the messages fit exactly. Evidence against: the report does not say what the dialog showed or what was clicked. **Settled by the guide**: compile without the dialog, and if the child is still missing, open the dialog only to read it and cancel.
3. **A1, the first pass of the hierarchy and the project file** (`H-A-SCHRPT-ATTACH`). Altium's own full project file attaches every module sheet whatever the order (variants h, j and n of Part H), and Fenolite's minimal file needs the order; the sample's file sits between the two (`HierarchyMode` and three channel keys, no net or compile key). All six corpus projects hold `ReorderDocumentsOnCompile=1` and the four net-naming keys; Altium's default for an absent key is not documented. Evidence against: variants k and m of Part H (Altium's whole `[Design]` section, or `HierarchyMode=0` alone, in the bad order) were not reported as working, so `[Design]` alone did not cure the order case. **Changed here** for the sample only, because it is harmless and moves the file toward the corpus form; the general writer waits for step R5.
4. **A2, Altium-written bookkeeping** (no row). Every corpus schematic document holds `MINORVERSION` and a document `UNIQUEID` in its header (38 of 38), `INDEXINSHEET` on every sheet symbol (40 of 40) and port (208 of 208) and on 213 of 251 sheet entries, and `UNIQUEID` on 153 of 251 sheet entries; the sample holds none of them. Evidence against: the hierarchical builds without them attached and compiled in Altium on 2026-10-03, and `INDEXINSHEET` is not the position of a record among the sheet's objects (it differs, for some records, in 37 of the 38 corpus documents), so its value cannot be written without a guess. **Not changed**; the fallback if step R5 fails with B1 and A1 in place.
5. **B3, the documented form itself** (no row). Perhaps the entry or the bus must be named otherwise (`Repeat(OUT[1..2])`, or a bus label `OUT`). Evidence for: the warning says the entry is a wire object by its name. Evidence against: Altium's page names the entry `Repeat(Headphone)` and the bus `Headphone`, with nets `Headphone1` and `Headphone2` given to channels 1 and 2 (S-0520), and a bus needs a label `<name>[<a>..<b>]` on its line (S-0301), which is the sample's form; the page names no other form. **Not changed.**

The questions of the change order, answered from the evidence:

| question | answer | from |
|---|---|---|
| does the entry need an `IOTYPE` or a bus kind? | no bus-kind key exists in any of the 251 corpus sheet entries (keys counted); a sheet entry's properties are name, I/O type, harness type and arrow kind; bus or wire is judged by the name. `IOTYPE` is absent on 173 of 251 corpus entries and the sync dialog matches by name and I/O type, which are both unspecified on the entry and on the port | S-0706, S-0185, S-0707 |
| must the bus (record 26) end exactly on the entry? | it does: the bus line's first point is the entry's connection point, by the geometry that finds 139 corpus entries on wire ends | S-0706 |
| `OUT[1..2]` or `OUT` on the bus? | `OUT[1..2]`: a bus needs a label `<name>[<a>..<b>]` on its line; the documented example gives member `<name><i>` to channel `i` | S-0301, S-0520 |
| must the child port `OUT` be a single-wire port? | yes, and it is: a port named without a range is one signal, and each channel takes one member | S-0301, S-0520 |

## Decisions

- **The label moves for every bus block, not only for the sample.** The rule is the writer's (c0086, "Bus records"), and the corpus difference holds for ports as for entries. A bus in a cell of its own also has its label moved, for one rule; nothing connects at its start.
- **The cell grows by the label's shift**, so the label's text stays inside it; parts placed to the right move 100 mil. The alternative, keeping the cell and letting the text cross the vertical bus line, was refused: the bus line goes down from the corner, so the text would not touch it, but the writer's cells contain what they draw.
- **The project keys are written by the sample, not by `prjpcb`.** A build's project file has been confirmed in Altium in its minimal form (Part H, variant l); changing it on a hypothesis would move every build's bytes. If step R5 shows that the keys are what attaches the child, a later change moves them into the writer.
- **Values are the corpus majority**; `AllowSheetEntryNetNames=1` is also the import's default, so the import of the sample does not change. `NewIndexingOfSheetSymbols` is in three of six files with two values and is left out.

## Tests

- `tests/unit/backends/altium/test_bus_records.py`: `test_bus_label_lies_beside_the_connection_point` (the label point; no label on the start of any written bus, binary and ASCII, on the tree build); `test_four_bit_bus` now asserts that the label lies on the first run of the line past its start, where it asserted that it lay on the start.
- `tests/unit/backends/altium/adapter/test_channel_files.py::test_repeat_bus_and_project_forms`: no net label on the connection point of either entry; the bus starts on the entry and its label lies 100 mil along it; `[Design]` holds the keys in the corpus order.
- Unedited and passing: `tests/unit/backends/altium/adapter/test_repeat.py`, `test_channels.py`, `test_folder_reads_as_two_channels` (the import reads the same channels, designators and nets).
- The golden of the tree sample is written again (`FENOLITE_GOLDEN_WRITE=1`, `test_tree`): its three sheets with a bus change, `tree_power.SchDoc`, `tree.SchLib` and `tree.PrjPcb` do not.

## Bytes that moved

| file | before | after | why |
|---|---|---|---|
| `tests/data/altium/channels/two/two.PrjPcb` | `38384a5c…` | `b1b67bdf…` | the seven corpus keys; the two channel keys in corpus order |
| `tests/data/altium/channels/two/two.SchDoc` | `42e8a026…` | `917fe6fb…` | the bus label at (230, 650) instead of (220, 650); `J1`, `U1` and their wires 100 mil to the right (the bus cell is wider) |
| `tests/data/altium/channels/two/two_ch.SchDoc` | `cad7f566…` | unchanged | no bus |
| `tests/data/altium/tree/tree.SchDoc`, `tree_io.SchDoc`, `tree_io.leds.SchDoc` | golden | written again | each holds a bus drawn from a port or an entry |

## Released output

The shipped examples draw no bus, so their builds keep their bytes: the pins of `tests/unit/lens/test_build_bytes_pinned.py` do not move (83 passed). No KiCad module is edited.

## Size (design-days)

0.5: the writer change is two lines; the evidence, the check folder and the pages are the work.

## Spec deltas and archive order

- `altium-schematic-writer`: ADDED "Bus label beside the connection point", "The rest of a bus block in place" and "Project keys of the two-channel sample". The first refines the sentence "the label lies at its start" of "Bus records" (c0086, unarchived), which this requirement supersedes for the label's position. Archive after c0086, c0083 and c0146.

## Author report: Part R, step R5

The steps, the expected answers and the files with their SHA-256 are in `docs/evidence/altium-schematic.md`, "Part R", step R5. They are written from Altium's documentation; a menu path or a dialog name may read differently in version 26. Nothing is marked verified by this change.

| folder | what differs from the main folder | settles |
|---|---|---|
| `A-principal` | (the committed sample) | expected: the child nested at once, no `only one pin`, no `placed on a bus` |
| `B-projeto-antigo` | the project file of c0146 | if A attaches and B does not, A1; if B splits too, the split is B1's |
| `C-rotulo-antigo` | `two.SchDoc` of the base, with the label on the connection point | if A splits and C does not, B1 |
