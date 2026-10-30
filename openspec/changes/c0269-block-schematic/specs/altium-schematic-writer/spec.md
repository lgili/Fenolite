## MODIFIED Requirements

### Requirement: Sheets of a module tree
With `sheets="modules"`, the writer SHALL write one schematic document per module of the design at any depth: the top sheet holds one sheet symbol per top-level module, and a module's sheet holds its own components and one sheet symbol per module directly below it.
- `hierarchy.sheet_tree(design)` MUST give every module that holds a component, directly or below it, depth first with siblings in natural order, the order of `kicad-schematic` ("Hierarchical sheets of a design"). The module of a component is its component path without the last segment (`hierarchy.module_of`).
- A module's file MUST be `<name>_<module path with "." for "/">.SchDoc` beside the project (`hierarchy.sheet_file`), so a top-level module keeps the name of change c0037; the sheet symbol's name (record 32) MUST be the last segment of the module path, and its file name (record 33) the module's file. The project file MUST list the top sheet and then the module sheets in tree order.
- A net that is not a member of a `power` interface **crosses** a module when it has a pin on the module's sheet or on a sheet below it, and a pin on any other sheet. Each crossing MUST give a port on the module's sheet and a sheet entry of the same name on its sheet symbol, so a net that crosses two levels is passed through the sheet between: that sheet holds a port and, on the symbol of the module below, a sheet entry. For the sheet of a block instance, the crossings, their names and their order MUST be those of "Sheet entries from block ports"; the wire stubs and net labels keep the net names.
- A `harness` interface MUST cross only a top-level module, in the binary form, as in "Sheets of a hierarchical project"; below the first level its member nets cross as nets.
- The unique ids of sheet symbols and ports MUST be `unique_id("sheet:<module path>")` and `unique_id("port:<module path>:<name>")`, stable across builds.
- That Altium compiles such a project and shows the tree is `H-A-SCHX-TREE`.

#### Scenario: Two levels
- **GIVEN** the authored design `tree` (`tests/data/altium/tree/design.py`) with the modules `power`, `io` and `io/leds`
- **WHEN** it is built with `sheets="modules"`, in each form, and read back
- **THEN** four schematic documents exist (`tree.SchDoc`, `tree_io.SchDoc`, `tree_io.leds.SchDoc`, `tree_power.SchDoc`), the sheet of `io` holds a sheet symbol named `leds` whose file name is `tree_io.leds.SchDoc`, and the netlist of the read project equals the design's

#### Scenario: Block instance crossings
- **GIVEN** the authored design `tests/data/altium/blocks/design.py`: a block `filt` with the ports `IN` (direction `in`) and `OUT` (direction `out`) of kind `Net`, used as `f1`, whose `IN` and `OUT` are joined to the nets `SRC` and `DST`, each with a pin of a part on the top sheet
- **WHEN** it is built with `sheets="modules"` and the sheet symbol of `f1` and the sheet `blocks_f1.SchDoc` are read
- **THEN** the sheet entries and the ports are named `IN` and `OUT`, each port's I/O type equals its entry's as "Port and sheet-entry directions" gives it, and the stubs carry the net labels `SRC` and `DST`

#### Scenario: Passed through the sheet between
- **WHEN** the crossings of `tree` are read
- **THEN** `io` crosses `ALARM`, `D[0..3]`, `SENSE` and `SENSE_IN`, `io/leds` crosses `D[0..3]` and `LED_K`, and `power` crosses nothing; the sheet of `io` holds the port `D[0..3]` and, on the symbol of `leds`, the sheet entry `D[0..3]`

## ADDED Requirements

### Requirement: Sheet entries from block ports
With `sheets="modules"`, the sheet of a block instance SHALL cross first one port per port member that has a pin on that sheet or below it, is not merged and whose net is in no `power` interface, named by its sheet name, in port and member order; then the inferred crossings of its other crossing nets, named by the net, in code-point order. This replaces the net-named crossings of "Sheets of a hierarchical project" there.

#### Scenario: Escaping net still crosses
- **GIVEN** the authored block design of "Block instance crossings", with a net `TEST` that joins a pin inside `f1` and a pin on the top sheet without a port
- **WHEN** it is built with `sheets="modules"`
- **THEN** the crossings of `f1` are `IN`, `OUT` and then `TEST`, and the build reports `build.block-net-escape` for `TEST`

#### Scenario: Power port stays global
- **GIVEN** a block port whose net is a member of a `Power` interface
- **WHEN** the design is built with `sheets="modules"`
- **THEN** that port gives no port and no sheet entry, and its pins keep their power ports

### Requirement: Block sheet name clash in Altium
A port crossing and an inferred crossing of one block sheet with the same name SHALL give `build.block-sheet-name-clash` (error) naming the block path and the name, and the build MUST write nothing. The code joins the Altium build's codes as a later code.

#### Scenario: Escaping net named like a port
- **GIVEN** the authored block design with its escaping net renamed `IN`
- **WHEN** it is built for Altium with `sheets="modules"`
- **THEN** the exit code is 5, `issues` hold `build.block-sheet-name-clash` naming `f1` and `IN`, and no file is written
