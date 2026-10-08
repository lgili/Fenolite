## Why

The maintainer opened the two-channel sample `tests/data/altium/channels/two/` in Altium Designer 26.5.0 on 2026-10-08 (session 2, step R1 of Part R, S-0615). The sheets were visible, but two things went wrong:

1. **The child sheet did not attach.** `two_ch.SchDoc` came under `two.SchDoc` in the Projects panel only after he ran "Sheet Symbol Actions » Synchronize Sheet Entries and Ports". Before that the compile said `Missing child-sheet in two_ch.SchDoc in Symbol Repeat(CH,1,2)`, and also `Duplicate Net Names Wire Repeat(OUT)`, naming the bus `OUT[1..2]` twice.
2. **The bus did not split.** After the sync the channels appeared (`R1_CH1`, `R1_CH2`, `C12_CH1`, `C12_CH2`), but the compile gave the errors `Net OUT1 has only one pin (Pin U1-1)` and `Net OUT2 has only one pin (Pin U1-2)`, and the warning `Wire Sheet Entry CH1-Repeat(OUT)(Passive) at 2200mil,6500mil placed on a bus`.

The release record of 0.3.0 (`docs/release/v0.3.md`) lists this as an open row of c0083 and reserves c0151 for it.

## Outcome in one paragraph

**The net label of every bus that the schematic writer draws from a port or a sheet entry now lies on the bus line 100 mil from the connection point, as a wire's label does, and no longer on the connection point itself; the two-channel sample is written again with that bus and with the `[Design]` keys that all six public project files of the corpus hold.** Nothing in the corpus or in Altium's documentation shows a `Repeat` statement, so the cause of the report cannot be settled from files: the design ranks five hypotheses with their evidence. The change makes the record forms that the evidence supports, and gives the maintainer a check folder with three variants so that one compile per variant settles the top two hypotheses. The tasks that need Altium stay open.

## What Changes

- **Writer: the bus label (`layout.BusBlock.label_point`, `schdoc` record 25 of a bus).** The label of a bus block lies `LABEL_OFFSET` (100 mil) right of the block's start, on the first run of the line, not at the start. The start is the connection point of a bus port or a bus sheet entry. Across the corpus, none of 251 sheet entries and none of 208 ports has a net label on its connection point (S-0706), and Altium's net label page says that a label attaches to the wire, bus or pin its hotspot touches (S-0140). The cell of the block grows by 100 mil to the right, so what is placed to its right moves by 100 mil.
- **Bytes that change.** Every written schematic document that holds a bus drawn from a port or a sheet entry: in the repository, `tests/data/altium/tree/` (`tree.SchDoc`, `tree_io.SchDoc`, `tree_io.leds.SchDoc`; the golden of `test_tree`) and the sample `tests/data/altium/channels/two/two.SchDoc`. A build without a drawn bus keeps its bytes.
- **The sample's project file (`tests/_altium_channels.project_text`).** `[Design]` holds, after `Version`, `HierarchyMode` and the three channel keys, the seven keys that name nets or order a compile and that all six corpus project files hold (`AllowPortNetNames=0`, `AllowSheetEntryNetNames=1`, `AppendSheetNumberToLocalNets=0`, `NetlistSinglePinNets=0`, `ReorderDocumentsOnCompile=1`, `NameNetsHierarchically=0`, `PowerPortNamesTakePriority=0`), with the corpus's majority value and in the corpus's order; `ChannelDesignatorFormatString` now comes before `ChannelRoomLevelSeperator`, as in every corpus file. The general project file writer (`prjpcb`) is not changed.
- **The sample is written again** by `tests/data/altium/channels/two/author.py`: `two.PrjPcb` and `two.SchDoc` change, `two_ch.SchDoc` does not.
- **The maintainer's check folder** (outside the repository): the new sample and two variants, each changing one thing back, with a guide in Brazilian Portuguese: open without synchronizing, compile, copy the messages.
- **Pages.** `docs/evidence/altium-schematic.md` (Part R: the messages of step R1 as reported, step R5 and its folder), `docs/formats/altium/connectivity.md` and `docs/formats/altium/project.md` (one fact row each), `docs/evidence/sources.md` (S-0706, S-0707), `docs/hypotheses.md` (`H-A-SCHRPT-BUSLABEL`, `H-A-SCHRPT-ATTACH`), `tests/data/MANIFEST.toml` (notes), `docs/release/v0.3.md` (the open row points here).

Size: 0.5 design-day (a size, not time).

## What is not known

- Whether either change is what Altium needs. The label on the connection point is the one difference between the sample's records and every corpus sheet that bears on the bus; it is a candidate, not a proven cause.
- What the sync dialog changed on 2026-10-08. Altium's page says that matching an entry to a port in it renames the port (S-0185). If the port `OUT` was renamed `Repeat(OUT)`, the split could fail for that reason alone. The report does not say.
- What `HierarchyMode=0` is: Altium wrote that value into a project file that had no such key (2026-10-03), so it is most likely the default, but no source names the number of each scope.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-schematic-writer`: ADDED "Bus label beside the connection point", "The rest of a bus block in place" and "Project keys of the two-channel sample".

## Non-goals

- No build writes a `Repeat` statement; no change of the import, of any reader, of the project file writer or of the PCB writers.
- No `INDEXINSHEET`, no `MINORVERSION` or `UNIQUEID` in the binary header, no `UNIQUEID` on sheet entries: the corpus holds them, but the hierarchical builds without them attached in Altium on 2026-10-03, and the meaning of `INDEXINSHEET` is not read from the corpus (its value is not the record's position among the sheet's objects). They stay a fallback if step R5 fails.
- No change of KiCad output.
- No file that Altium wrote is committed; no code or constant from any private project or organisation.

## Evidence level required

Unchanged, `INFERRED`. Own readback is supporting data; what Altium does waits for step R5 of Part R.

## Impact

- Changed: `src/fenolite/backends/altium/layout.py`, `src/fenolite/backends/altium/schdoc.py`; `tests/_altium_channels.py`, `tests/data/altium/channels/two/` (two files), `tests/data/altium/tree/` (three sheets); tests of the bus records and of the sample; `tests/unit/test_format_facts.py` lists the new family `H-A-SCHRPT-*`.
- Behaviour: **the schematic documents of an Altium build with a drawn bus change their bytes** (the bus label 100 mil along the bus, the parts to the right of the block 100 mil further right). A build without a drawn bus is byte-identical.
- Depends on: c0086 (the bus records), c0083 and c0146 (the sample). Archive after them.
