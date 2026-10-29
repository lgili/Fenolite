## Why

A reusable circuit in Fenolite 0.6.0 is a Python function that closes over global nets and names
everything by hand. `examples/yardstick/design.py` numbers its refs `n*100+k`, builds net names with
f-strings and passes `Module` objects around only to prefix paths. Nothing says which nets a sub-circuit
expects from outside, which keyword arguments made it, or whether a net that should have been wired to it
was forgotten. `Module(name)` is a named container: it has no ports, no parameters, no local nets and no
ref namespace.

The research of 2026-10-29 (`docs/research/circuit-as-code.md`, section 4 and core change D) compares this
with JITX (a circuit class with ports and constructor parameters; ports that dissolve into the one port
they connect to; schematic groups labelled by path), atopile (a module with interface children and a check
that a block's port is used from outside) and tscircuit (a subcircuit isolates its nets and refs). It
proposes blocks as plain decorated Python functions with typed ports, and rejects class-body and metaclass
magic, which JITX's own documentation lists as a source of mistakes. Only the concepts are taken; no code,
grammar, schema or library text of these projects is copied.

## What Changes

- **Blocks.** `@block` marks a plain function `def name(b, *, param=default, ...)`. The first argument is a
  builder; every other argument is keyword-only. `@block` checks the signature when it decorates and
  returns a `BlockDef`. A `BlockDef` cannot be called directly.
- **Instances.** `design.use(block, name, **params)`, and `b.use(...)` inside a block, run the function once
  with a fresh `Block`, a subclass of `Module` whose path is `<parent path>/<name>`. They return a
  `BlockInstance` whose ports are attributes (`p1.VIN`).
- **Parameters recorded.** The keyword arguments, with the defaults applied, are recorded on the model
  `Module` as typed canonical texts (int, bool, str, length, quantity, and c0246's range). An argument that
  cannot be recorded raises `DslError`.
- **Typed ports.** `b.port(name, kind=Net, *, direction="inout", optional=False)` declares a port. A port
  has a name, an interface type and a direction (`in`, `out`, `inout`). Its type is a single net (`Net`) or
  any interface class of `fenolite.dsl.interfaces`: today's `Power`, `I2C`, `SPI`, `UART`, `USB2`,
  `DiffPair` and `Harness`, and c0252's `Rail`, `Ground` and `Logic`. Each member of a port is a **port
  net**: a net without a name of its own, which takes the name of the outside net it is connected to.
- **Local nets.** `b.net("FB")` gives a net named `<block path>/FB`, so two instances never collide.
- **Ref namespace.** A part inside a block is named locally (`b.part("U", ...)`, path `buck1/U`). Its
  board ref comes from c0249's lock and allocator unless `ref=` is given. Two instances of one block
  therefore never type the same ref.
- **Checks.** Two build warnings join the closed build set. `build.port-unused`: a port that is not
  `optional` has nothing outside its block on its net. `build.block-net-escape`: a script-named net joins
  pins inside and outside a block without passing through a port of that block.
- **Schematic groups from the block path.** A block instance is a module, so the readable KiCad schematic
  already gives it a sheet; the sheet is titled with the block name. In Altium block composition, each
  instance gives an implicit `schematic_block` keyed by its path.
- **Model.** `Module` gains `block` and `params`. A new `Port` entity (`circuit.ports`) records the owner,
  kind, direction and member nets of each port. Ports get the id prefix `prt`, keyed by
  `port:<owner path>:<port name>`. Every new field is omitted when empty, so a design without blocks writes
  the same `.fenolite/` bytes as before.
- `Module` keeps its API and behaviour unchanged: refs typed by hand, global literal net names.

## Capabilities

### New Capabilities

None. Blocks are part of the DSL and the model.

### Modified Capabilities

- `design-dsl`:
  - MODIFIED "Design structure and names" (blocks, block-local nets and names).
  - MODIFIED "Connections and pin designators" (port nets and their binding).
  - ADDED "Blocks in the DSL", "Block parameters", "Block ports in the DSL", "Block checks in a build" and
    "Schematic groups from blocks".
- `design-model`:
  - MODIFIED "Identifier derivation" (the `port` row).
  - ADDED "Blocks and ports in the circuit model".

## Dependencies

- **c0246 quantity-ranges:** a range is a recordable parameter type, and its canonical text is the one
  c0246 defines.
- **c0248 device-catalog:** `b.part(name, device=...)` is c0248's `design.part(device=...)` used inside a
  block.
- **c0249 design-lock:** block-local refs are allocated and frozen by c0249's `<script stem>.lock`. This change
  adds no lock key; it adds block paths as lock keys.
- **c0252 parametric-interfaces** is implemented with or after this change (step 4 of the research order).
  It adds `Rail`, `Ground` and `Logic`, port parameters, and `connect()` between whole interfaces, all on
  the port nets defined here.
- Later: c0255 relative-placement gives a block a pose and a layout strategy, and c0256 design-testing
  instantiates a block alone for tests.

## Non-goals

- No class-based blocks, metaclass, class-body declarations or decorators on methods.
- No arrays of ports or instances (`count=`). A Python loop over `design.use` is the array.
- No block layout, pose or layout reuse (c0255). No block library or package manager.
- No change of `Module`'s behaviour, and no change of a model written by a script without blocks.
- No new command.

## Evidence level required

- Block mechanics (paths, port nets, parameters in the model): `KICAD-VERIFIED`, because the built board of
  the block example reads back through `kicad-cli` with the connectivity of the script ("Built boards read
  back with the same connectivity").
- `build.port-unused` and `build.block-net-escape`: `INFERRED`. They are structural judgements on the
  script.

## Impact

- New:
  - `src/fenolite/dsl/block.py` (`block`, `BlockDef`, `Block`, `BlockInstance`, `PortHandle`, parameter
    recording).
  - `src/fenolite/dsl/portnets.py` (the binding of port nets and their naming rule).
  - `examples/blocks/` (the yardstick channel written as a block, two instances, and a nested block).
  - `tests/unit/dsl/test_blocks.py`, `test_block_ports.py`, `test_block_params.py`.
  - `tests/unit/lens/test_build_blocks.py`.
- Changed:
  - `dsl/module.py` (`Container` holds ports).
  - `dsl/part.py` (`connect` takes port handles; port nets).
  - `dsl/design.py` (`use`).
  - `dsl/convert.py` (`KEYS` row `port`, `Module.block` and `params`, `Port` entities, port-net names).
  - `dsl/schematic.py` (implicit block groups).
  - `model/circuit.py` (`Module` fields, `Port`, `Circuit.ports`).
  - `core/ids.py` (prefix `prt`).
  - `lens/build.py` (the two codes).
  - `schematic` sheet titles.
  - `schemas/` (regenerated).
  - `cli/data/explain.toml`.
  - `docs/dsl.md`, `docs/design-model.md`, `docs/schematic-composition.md`.
  - The agent guide pages `design-script` and `dsl-reference` (generated).
  - `CHANGELOG.md`.
- Size: about 8 design-days.
