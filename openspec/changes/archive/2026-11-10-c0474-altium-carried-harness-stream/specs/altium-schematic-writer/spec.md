# Delta for altium-schematic-writer

## MODIFIED Requirements

### Requirement: Harness records
A harness crossing SHALL be drawn on the module sheet, and on the top sheet unless "Harness lines between sheet symbols" joins its two sheet entries by a line, as one harness block: a signal harness line, a harness connector with one harness entry per entry of the type, the type record, and a labelled wire stub on each entry whose net crosses that module. `schdoc.additional_records(plan)` SHALL return the block records of a sheet in block order: the connector, its entries in code-point order of their names, the type, then the line; and after the blocks one record 218 per line of `plan.lines` (S-0130, S-0131, S-0186, S-0187, S-0188).
- Harness connector: `RECORD=215`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the top-left corner), `XSIZE`, `YSIZE`, `LINEWIDTH=1`, `COLOR=13213327`, `AREACOLOR=16511725`, `PRIMARYCONNECTIONPOSITION=<p>`. Its connection point is on its left edge, `p` units of 10 mil below the top-left corner; no `HARNESSCONNECTORSIDE` is written.
- Harness entry: `RECORD=216`, `OWNERINDEX=<index of its connector in this list>` (omitted when 0), `OWNERINDEXADDITIONALLIST=T`, `OWNERPARTID=-1`, `SIDE=1`, `DISTANCEFROMTOP=<k>`, `COLOR=7354880`, `AREACOLOR=8454143`, `TEXTCOLOR=7354880`, `TEXTFONTID=1`, `TEXTSTYLE=Full`, `NAME=<entry name>`. Its connection point is on the connector's right edge, `k` × 100 mil below the top-left corner. The connector of a type with `m` entries is `(m + 1)` × 100 mil high, with the entries at `k` = 1 … `m`.
- Harness type: `RECORD=217`, `OWNERINDEX` (as the entries), `OWNERINDEXADDITIONALLIST=T`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the connector's top-left corner), `COLOR=8388608`, `FONTID=1`, `TEXT=<type name>`.
- Signal harness: `RECORD=218`, `OWNERPARTID=-1`, `LINEWIDTH=2`, `COLOR=15187117`, `LOCATIONCOUNT=2`, `X1`, `Y1` (the port's right end or the sheet entry's connection point), `X2`, `Y2` (the connector's connection point), 200 mil apart on one horizontal line.
- Every block of a type MUST hold all the type's entries, on every sheet, so the drawn definitions never differ. An entry whose net crosses the block's module MUST get a wire stub rightwards and a net label with the **net** name, as for a right pin, written in `FileHeader` ("Sheet symbols and sheet entries", "Ports on module sheets"). An entry whose net does not cross that module MUST get no wire and no label, on every sheet (`H-A-SCH-HARN-UNUSED`; Altium Designer 26.5 reports such an entry as the warning "Unconnected Harness Entry", maintainer's report of 2026-10-03).
- The net keeps its own name on every sheet: the label names it, not the harness (S-0131, S-0187; `H-A-SCH-HARN-NETS`).
- A plan with a harness block or a line of `plan.lines` MUST be refused by `schdoc.write_schdoc` (the ASCII form) with `ValueError`; `plan_sheets` never makes one for that form.
- No block is written in the `flat` mode.

`fenolite.backends.altium.binary.write_schdoc_binary` SHALL write the harness records of a plan (the
blocks of `plan.harnesses`, the direct-join lines of `plan.lines` and `plan.polylines`, and the records
carried from a source `Additional` stream in `plan.carried_additional`) into the document's `Additional`
stream, after its own header record, and SHALL NOT write them into the `FileHeader` stream. A carried
child's `OWNERINDEX` SHALL name its connector's index in the Additional stream (0-based after the
header), shifted behind the records `schdoc.additional_records` builds itself, and SHALL be omitted when
that index is 0. The ASCII form (`schdoc.write_schdoc`) SHALL refuse a plan with carried Additional
records, as it refuses drawn harnesses.

#### Scenario: Block of the flash sheet
- **WHEN** `additional_records` runs on the plan of `altium_hier_flash.SchDoc`
- **THEN** it returns 7 records: one 215, four 216 named `CS`, `MISO`, `MOSI` and `SCK` with `DISTANCEFROMTOP` 1 to 4 and no `OWNERINDEX`, one 217 with `TEXT=SPI`, and one 218 with `LOCATIONCOUNT=2`

#### Scenario: Line joins port and connector
- **WHEN** the port `SPI`, the record 218 and the record 215 of that sheet are read
- **THEN** the line's first point is the port's location plus its width, and its second point is `PRIMARYCONNECTIONPOSITION` units below the connector's top-left corner on its left edge

#### Scenario: Entry stubs carry net names
- **WHEN** the wires that start on the connector's right edge are read
- **THEN** there are four, at the four entries' connection points, and their labels read `SPI_CS`, `SPI_MISO`, `SPI_MOSI` and `SPI_SCK`

#### Scenario: Entry of a net that does not cross
- **WHEN** `examples/altium_hier/partial.py` (a fifth entry `HOLD` on the net `FLASH_HOLD_N`, which only the `flash` sheet uses) is written
- **THEN** each module sheet holds one block, every block holds five records 216, and no wire starts at the connection point of any `HOLD` entry

#### Scenario: Second connector names its index
- **GIVEN** a variant of the sample with a second harness `DBG` that crosses `mcu`
- **WHEN** `additional_records` runs on the plan of `altium_hier_mcu.SchDoc`
- **THEN** the entries and the type of the first block carry no `OWNERINDEX`, and those of the second block carry the index of their own record 215; on the top sheet's plan it returns the block of `DBG` and then the line of `SPI`

#### Scenario: ASCII writer refuses a block
- **WHEN** `schdoc.write_schdoc` is called on the binary-form plan of `altium_hier_flash.SchDoc`
- **THEN** it raises `ValueError` naming the harness

#### Scenario: Carried harness records return to the Additional stream
- **GIVEN** a drawn sheet whose opaque items hold a harness connector subtree (root `RECORD=215` with
  `RECORD=216` and `RECORD=217` children naming `OWNERINDEX=@0`), a second connector with one entry, and
  a signal harness line (`RECORD=218`)
- **WHEN** the project is built with `build --target altium` in the binary form
- **THEN** the written document's `FileHeader` stream holds no record of 215–218, its `Additional`
  stream holds them in order `215, 216, 217, 215, 216, 218`, the entry of the first connector names no
  owner, the entry of the second names `OWNERINDEX=3`, and the document re-reads without an
  `altium.sch.orphan-record` warning.
