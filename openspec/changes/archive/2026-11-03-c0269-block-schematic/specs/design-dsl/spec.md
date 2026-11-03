## ADDED Requirements

### Requirement: Block schematic groups in the DSL
`fenolite.dsl` SHALL export `schematic_group(key, *members, title=None, anchor=None, after=None, flow="left-to-right")`, and the block builder SHALL offer `schematic(*groups)`, callable once per block. Members MUST be parts the block owns directly, each in at most one group. `anchor` MUST be a member, `after` a key of the call without a cycle, and `flow` `left-to-right` or `top-to-bottom`, else `DslError` at the call.

#### Scenario: Part of a nested block refused
- **GIVEN** a block that uses a nested block `inner` holding the part `R`
- **WHEN** it calls `b.schematic(schematic_group("g", "inner/R"))`
- **THEN** `DslError` is raised naming `inner/R` and saying that a group holds the block's own parts

#### Scenario: Cycle refused
- **WHEN** a block calls `b.schematic(schematic_group("a", r1, after="b"), schematic_group("b", c1, after="a"))`
- **THEN** `DslError` is raised naming `a` and `b`

#### Scenario: Groups reach every instance
- **GIVEN** the block `rc_filter` with one group `chain`, used as `f1` and `f2`
- **WHEN** `dsl.block_schematics(design)` is read
- **THEN** it holds `f1` and `f2`, each with the group `chain` holding that instance's parts `R` and `C`, and `to_model` gives the same model as without the call

### Requirement: Block schematic groups are not composition intent
Block-local groups SHALL NOT be composition declarations of "Schematic composition declarations": they MUST NOT be reported as unused intent, a KiCad build MUST NOT refuse them, and an Altium build without block composition MUST ignore them without a diagnostic.

#### Scenario: Library block in every mode
- **GIVEN** a design that uses `rc_filter` with its group and declares no composition
- **WHEN** it is built for KiCad, and for Altium with `--altium-layout grid`
- **THEN** both builds succeed with no unused-intent and no unsupported-composition diagnostic

### Requirement: Block-local groups in Altium composition
When block composition is in force, each block-local group SHALL give a `schematic_block` keyed `<instance path>/<key>` with its title (or key), members, anchor and `after` mapped to keys of that instance. c0251's implicit block of the instance MUST keep only the parts no local group holds, and MUST be dropped when none remain. A design-level declaration holding a part MUST take it from the local group, and an emptied local group MUST be dropped.

#### Scenario: Local groups in block mode
- **GIVEN** `rc_filter` used as `f1` and `schematic_layout(mode="blocks")`
- **WHEN** the composition intent is extracted
- **THEN** it holds one block `f1/chain` with `f1/R` and `f1/C`, and no implicit block `f1`

### Requirement: Sheet names of block ports
The sheet name of a port member SHALL be `<port>` for a single-member port and `<port>_<member>` otherwise. The builder's `port` MUST raise `DslError` when a sheet name of the new port equals a sheet name of an earlier port of the same block.

#### Scenario: Clash with an interface member
- **GIVEN** a block that declared `b.port("I2C", I2C)`
- **WHEN** it calls `b.port("I2C_sda")`
- **THEN** `DslError` is raised naming `I2C_sda` and the port `I2C`
