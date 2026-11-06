## ADDED Requirements

### Requirement: A graphic's net in its stored spelling

A copper graphic read from a KiCad 10 board SHALL take the net its `(net "…")` slot names whether the slot
holds the net's model name or the spelling the board stores (`{slash}` for a slash), and the importer SHALL
name that net by its model name (change c0425).

#### Scenario: A region on a slash net keeps its net

- **GIVEN** the two-layer board with its net `GND` renamed `A1/GND` and a filled `F.Cu` polygon on it
- **WHEN** it is written for KiCad 10 or 9 and read back
- **THEN** the polygon holds the net `A1/GND` and the board is equivalent to the design, with no
  `copper-no-net`

#### Scenario: The import names the slash net

- **WHEN** `import --to python` reads that KiCad 10 board
- **THEN** it exits 0, equivalent, and the script declares `Net("A1/GND")` and no `{slash}`

#### Scenario: The copies of a netted region keep their nets

- **GIVEN** an Altium board with a free region on `GND`, placed 3 × 2 times by an embedded board array
- **WHEN** it is converted to KiCad
- **THEN** no difference is unexplained
