## Why

The maintainer must build a real design for Altium Designer 26.5 with one level of hierarchy (a top
sheet with sheet symbols, one sheet per block) and signal harnesses, which group nets with different
names, such as SPI with MOSI, MISO and SCK. The Altium build writes one sheet today, and the DSL has
no such group of nets.

## What Changes

- **DSL.** `fenolite.dsl.Harness(name, members)` records a named group of nets as a model `Interface`
  of kind `harness`. No model delta.
- **Sheets.** `--altium-sheets modules` writes `<design>.SchDoc` as the top sheet and
  `<design>_<module>.SchDoc` per top-level module. Parts outside any module stay on the top sheet.
  Nested modules are flattened. The default, `flat`, writes today's bytes.
- **Net scope.** A net used on a module's sheet and on another sheet gets a port there and a sheet
  entry of the same name on the sheet symbol, each with a short labelled wire. No wire is routed.
  Nets of a `power` interface keep their power ports, which are global, and get neither.
- **Harness.** A harness whose nets leave a module is drawn on both sides as one block: a connector
  with its entries and type, labelled wires on the entries, and a signal harness line to the port or
  the sheet entry. The records go to the `Additional` stream of the binary schematic. Each sheet with
  a block gets a `.Harness` file, listed in the project file with the module sheets. The ASCII form
  writes no harness.
- **Unique ids and the change order.** Components keep their unique ids in both modes. A sheet symbol
  gets `unique_id("sheet:<module>")`. The PCB document links a part on a module sheet as
  `\<sheet symbol id>\<component id>`, the form Altium saves.
- **Evidence.** A sample (top sheet, two module sheets, one harness), golden files, a multi-sheet
  readback, and Part H of the evidence page.

## Capabilities

### Modified Capabilities (no new capability)

- `design-dsl`: ADDED "Harness interfaces in the DSL".
- `altium-schematic-writer`: eight ADDED requirements (sheets, sheet symbols, ports, harness records,
  harness files, project file, layout, readback); MODIFIED "Binary schematic form" (text of c0033)
  and "Stable component unique ids" (text of c0032).
- `altium-pcb-writer`: MODIFIED "PCB document links and nets" (text of c0035).
- `altium-build`: five ADDED requirements (option, module sheets, issue codes, sample and report,
  documentation); MODIFIED "Altium build outputs" (text of c0035).

## Non-goals

- No repeated sheets or channels, no second level of hierarchy.
- No numbered buses, no nested harnesses, no harness in the ASCII form.
- No routed wires between sheet symbols, no port direction.
- No Altium reader, no project option keys.
- No harness or hierarchy in the KiCad build: the interface stays in the model.
- No deletion of sheets left by an earlier build.

## Evidence level required

- Records 15, 16, 18, 32, 33 and 215 to 218, the `Additional` stream, the `.Harness` file and the
  two-id PCB link: `INFERRED`, from S-0130, S-0131, S-0185 and S-0186, checked against files that
  Altium saved in two public repositories (S-0187, MIT; S-0188, LGPL-3.0), read in a scratch folder
  and never committed.
- No `kicad-cli` path reads a SchDoc, so there is no oracle. Fenolite's readback checks the written
  nets and raises no label.
- Nine hypotheses (`H-A-SCH-HIER-*`, `H-A-SCH-HARN-*`) wait for the maintainer's Altium Designer 26.5
  report of Part H: `ALTIUM-VERIFIED(author-report; AD 26.5; <date>; no artefact)` per confirmed
  row. The build stays `INFERRED` and experimental.

## Impact

- Code: `dsl/interfaces.py`, `backends/altium/`, `lens/altium.py`, `cli/cmd_build.py`.
- Order: archived after c0036 (chain c0032 → c0033 → c0034 → c0035 → c0036 → c0037).
- Size: 7 design-days.
