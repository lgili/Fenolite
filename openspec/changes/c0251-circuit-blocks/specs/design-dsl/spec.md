## MODIFIED Requirements

### Requirement: Design structure and names
`Design(name)`, `Module(name)` and `Part(ref, lib_id, footprint=None, value="")` SHALL build a tree whose paths name every component, and SHALL raise `DslError` at the offending call for every structural error of this list. A block instance ("Blocks in the DSL") is a module of this tree.
- A design name MUST match `^[A-Za-z0-9][A-Za-z0-9_.-]*$`, because it becomes the stem of the KiCad files. Module names, block instance names, block names, port names, local net names, local part names and refs MUST match `[A-Za-z0-9_.+-]+`.
- `Design.add(*objs)` and `Module.add(*objs)` attach parts, modules, nets and interfaces. `Module.path` is the module name at the top and `<parent path>/<name>` below. A component path is `<module path>/<ref>` (`power/ldo/C1`), or `<ref>` at the top. In a block instance, the path leaf is the part's local name ("Blocks in the DSL").
- Net names are global and literal. A module-local net is named by the script, for example `Net(f"{m.path}/FB")`. In a block, `b.net(name)` gives the net `<block path>/<name>`. A port net takes its name by the binding rule of "Connections and pin designators".
- `DslError` MUST be raised for: a duplicate component or module path; a duplicate net, net-class or interface name; two distinct `Net` objects with one name; a net in two classes; a second `place()` or `board()`; a `copper` that is not an `int` of `COPPER_COUNTS` (2, 4, 6 and 8, "Board and placements in the DSL"); one designator connected to two nets; a `side` other than `top` and `bottom`; an invalid name or ref.
- Equal refs in different modules are not a DSL error. They are left to `Design.validate()` (`model.duplicate-ref`, exit 5 from `build`). The board refs of parts in block instances are allocated so that they do not collide ("Blocks in the DSL").

#### Scenario: Paths from modules
- **GIVEN** `Module("power")` holding `Module("ldo")` holding `Part("C1", "Mini:Mini_R")`, added to a design
- **WHEN** `part.path` is read
- **THEN** it is `"power/ldo/C1"`

#### Scenario: Two nets with one name
- **WHEN** `Net("GND")` and a second `Net("GND")` are both added to one design
- **THEN** `DslError` is raised at the second `add()` naming `GND`

#### Scenario: Placed twice
- **WHEN** `r1.place(mm(1), mm(1))` is called twice
- **THEN** the second call raises `DslError`

#### Scenario: Duplicate refs in two modules
- **GIVEN** a blink variant with modules `a` and `b`, each holding a part `R1` of `Mini:Mini_R`
- **WHEN** the design is built with `fenolite build ... --dry-run`
- **THEN** the exit code is 5 and `issues` holds `model.duplicate-ref`

#### Scenario: Invalid design name
- **WHEN** `Design("my board")` is called
- **THEN** `DslError` is raised naming the pattern

#### Scenario: Local net of a nested block
- **GIVEN** a block `buck` that calls `b.net("FB")`, used as `buck1` inside a block instance `power`
- **WHEN** `to_model` runs
- **THEN** the model holds a net named `power/buck1/FB`

### Requirement: Connections and pin designators
`part[designator]` SHALL return a pin handle and `connect(net, *pins) -> Net` SHALL record that each pin joins `net`; designators MUST be stored as written and resolved only by the build ("Pins and pads in a build").
- A designator MUST be a non-empty `str` or an `int`; `part[1]` and `part["1"]` MUST name the same pin. A pin name such as `part["GND"]` is accepted as written.
- `net` MUST be a `Net`, a port net, or a net-like port handle ("Block ports in the DSL"); any other value MUST raise `DslError`. A pin argument MAY also be a port net or a net-like port handle, which binds it to `net`.
- **Port nets.** A port net has no name of its own. `connect` binds nets and port nets into groups. At `to_model`, a group holding one script-named net (a `Net` or a block-local net) MUST take that net's name. A group holding none MUST take the path of its preferred port member: an `out` port first, then the smallest path in code-point order. The path is `<owner path>/<port>` for a single-member port and `<owner path>/<port>.<member>` otherwise. Joining two script-named nets in one group MUST raise `DslError` at that call, naming both nets. There are no other implicit nets and no net merges.
- A net joins the design when it is added, or when it is connected to a pin of an added part.
- Connecting the same designator of one part to two different nets or groups MUST raise `DslError` at the second `connect`. Connecting it twice to the same net MUST keep one membership.

#### Scenario: Integer and string designators
- **GIVEN** `connect(vin, u1[1])` and `connect(vin, u1["1"])`
- **WHEN** `to_model(design)` runs
- **THEN** the net `VIN` holds one member for `U1` with `pin == "1"`

#### Scenario: Designator on two nets
- **WHEN** `connect(a, r1["1"])` is followed by `connect(b, r1["1"])`
- **THEN** `DslError` is raised naming `R1` and `1`

#### Scenario: Net given as a string
- **WHEN** `connect("GND", r1["2"])` is called
- **THEN** `DslError` is raised

#### Scenario: Port net takes the outside name
- **GIVEN** a block whose port `VIN` (kind `Net`) is connected inside to `R_EN` pin 2, used as `ch0`, and `connect(Net("VIN48"), ch0.VIN)`
- **WHEN** `to_model` runs
- **THEN** the net `VIN48` holds the pin 2 of the part at path `ch0/R_EN`, and no net named `ch0/VIN` exists

#### Scenario: Unnamed group named by its source port
- **GIVEN** two instances `buck1` and `buck2` of a block with ports `VOUT` (direction `out`) and `VIN` (direction `in`), and `connect(buck1.VOUT, buck2.VIN)` with no named net
- **WHEN** `to_model` runs, once with the instances used in this order and once in the reverse order
- **THEN** both models hold one net named `buck1/VOUT` that holds the inner pins of both ports

#### Scenario: Two named nets through a port
- **GIVEN** `connect(Net("A"), ch0.VIN)`
- **WHEN** `connect(Net("B"), ch0.VIN)` is called
- **THEN** `DslError` is raised naming `A`, `B` and `ch0/VIN`

## ADDED Requirements

### Requirement: Block decorator
`fenolite.dsl` SHALL provide `block`, an addition under "DSL package", which turns a plain function into a `BlockDef` named after the function or after `@block(name=...)`. It MUST raise `DslError` at decoration time unless the first parameter is the only positional one, every other parameter is keyword-only with a recordable default or none, and there is no `*args` and no `**kwargs`.

#### Scenario: Bad signature
- **WHEN** `@block` decorates `def bad(b, vout): ...`
- **THEN** `DslError` is raised naming `bad` and `vout` and saying that parameters must be keyword-only

#### Scenario: Variadic keywords refused
- **WHEN** `@block` decorates `def bad(b, **kw): ...`
- **THEN** `DslError` is raised naming `bad`

### Requirement: Block instances
`Design.use(block_def, name, **params)` and the builder's `use` SHALL create a `Block`, a subclass of `Module` named `name`, add it to the caller, call the block's function once with it as the first argument, and return a `BlockInstance`. Every rule of `Module` MUST hold for a `Block`. Calling a `BlockDef` directly, or a function that returns a value other than `None`, MUST raise `DslError`.

#### Scenario: Two instances, no collision
- **GIVEN** `examples/blocks/design.py`, which uses the block `channel` (one part `R_EN`, one local net `FB`) as `ch0` and `ch1`
- **WHEN** `uv run pytest tests/unit/dsl/test_blocks.py -k instances` runs `to_model`
- **THEN** the model holds the components at paths `ch0/R_EN` and `ch1/R_EN`, and the nets `ch0/FB` and `ch1/FB`

#### Scenario: Direct call refused
- **WHEN** a script calls `channel(design)` on a `BlockDef`
- **THEN** `DslError` is raised whose message names `design.use`

#### Scenario: Module scripts unchanged
- **GIVEN** `examples/blink_2layer/design.py` and the lens acceptance design of c0069, which use no block
- **WHEN** `canonical.dump_texts(to_model(design))` is computed before and after this change
- **THEN** the texts are equal

### Requirement: Block builder
The block passed to a block's function SHALL offer `part(name, lib_id=None, *, device=None, footprint=None, value="", ref=None, prefix=None, properties=None)`, with the keywords of c0249's `design.part`, `net(name)`, `port(...)`, `use(...)` and `add(...)`, and the read-only `path`, `name` and `params`. `part` MUST create, add and return a part whose path leaf is `name`. A local part, local net or port name used twice in one block MUST raise `DslError`.

#### Scenario: Duplicate local name
- **WHEN** a block calls `b.part("R_EN", "Mini:Mini_R")` twice
- **THEN** `DslError` is raised at the second call naming `R_EN` and the block path

### Requirement: Board refs in blocks
The board ref of a part in a block SHALL be its `ref` argument when given. Otherwise it SHALL be the ref that c0249's lock records for the part's path, or, when the lock holds none, the next free ref of the part's prefix from c0249's allocator. The prefix follows c0249's rule: `prefix=`, else the device's `ref_prefix`, else the catalog symbol's prefix.

#### Scenario: Allocated and explicit refs
- **GIVEN** the block `channel` used as `ch0` and `ch1`, whose part `R_EN` gives no ref, and a part `R_SET` given `ref="R90"` in `ch0`
- **WHEN** `uv run pytest tests/unit/dsl/test_blocks.py -k refs` runs `to_model` with an empty lock
- **THEN** `ch0/R_EN` and `ch1/R_EN` have two different refs starting with `R`, and `ch0/R_SET` has the ref `R90`

### Requirement: Block instance handles
`BlockInstance` SHALL expose each port of the block as an attribute and through `port(name)`, and SHALL expose `path`, `block`, `params` and `part(local_name)`. A port name equal to one of `path`, `block`, `params`, `part`, `port` or `place` MUST raise `DslError` at `port()`.

#### Scenario: Shadowing name refused
- **WHEN** a block calls `b.port("path")`
- **THEN** `DslError` is raised naming `path`

### Requirement: Block names are unique
Two different functions with one block name SHALL NOT be used in one design. `use` MUST raise `DslError` naming the block name, while two instances of one `BlockDef` are allowed.

#### Scenario: Two functions named buck
- **GIVEN** two modules that each define `@block def buck(b): ...`
- **WHEN** a design uses both
- **THEN** `DslError` is raised at the second `use`, naming `buck`

### Requirement: Block parameters
`use` SHALL bind its keyword arguments to the block's signature, apply the defaults, and record each parameter on the block's model `Module` as a `BlockParam(name, type, text)`, ordered by name. The value MUST be a `bool`, `int`, `str`, `Length`, `Quantity`, c0246 range or `None`. An unknown, missing or unrecordable argument MUST raise `DslError` naming the parameter, before the function runs.

#### Scenario: Defaults recorded
- **GIVEN** `@block def buck(b, *, vout=volt("3.3"), current=amp(2))` used as `design.use(buck, "buck1", current=amp(1))`
- **WHEN** `to_model` runs
- **THEN** the module `buck1` has `block == "buck"` and the params `current` (`quantity`, `1A`) and `vout` (`quantity`, `3.3V`), in this order

#### Scenario: Recorded forms
- **GIVEN** a block with the parameters `on=True`, `n=3`, `tag="a"`, `gap=mm(1)` and `note=None`
- **WHEN** it is used and `to_model` runs
- **THEN** the params are `gap` (`length`, `1000000`), `n` (`int`, `3`), `note` (`none`, empty), `on` (`bool`, `true`) and `tag` (`str`, `a`)

#### Scenario: Unrecordable parameter
- **WHEN** `design.use(buck, "buck1", vout=3.3)` is called
- **THEN** `DslError` is raised naming `vout` and `float`, and the function is not called

### Requirement: Block ports in the DSL
The builder SHALL provide `port(name, kind=Net, *, direction="inout", optional=False) -> PortHandle`. `kind` MUST be `Net` or a subclass of `Interface`, and `direction` MUST be `in`, `out` or `inout`. The port MUST have the members of its kind's closed member table in `fenolite.dsl.interfaces` (`net` for `Net`), each a port net. `to_model` MUST give one model `Port` per port.

#### Scenario: Interface port
- **GIVEN** a block with `b.port("I2C", I2C)` whose members are connected inside to a sensor's `SDA` and `SCL` pins, used as `sen`, and the nets `SDA` and `SCL` outside connected to `sen.I2C.sda` and `sen.I2C.scl`
- **WHEN** `to_model` runs
- **THEN** the nets `SDA` and `SCL` hold the sensor pins, and the model holds a `Port` named `I2C`, kind `i2c`, direction `inout`, whose members are the ids of `SDA` and `SCL`

#### Scenario: Bad direction
- **WHEN** a block calls `b.port("EN", direction="both")`
- **THEN** `DslError` is raised naming `both`

### Requirement: Net-like ports
A port with one member, or whose kind names a main member, SHALL be net-like: `connect` MUST accept it as its net or as a pin argument and act on that member. `handle[member]` and `handle.<member>` MUST give the port net of a member of any port.

#### Scenario: Port as a net
- **GIVEN** a block with `en = b.port("EN")` and `connect(en, r[1])`
- **WHEN** it is used as `ch0` with `connect(Net("CH0_EN"), ch0.EN)` and `to_model` runs
- **THEN** the net `CH0_EN` holds pin 1 of `ch0/R_EN`

### Requirement: Unused block ports
The build SHALL give the warning `build.port-unused`, which joins the closed build set as a code added under "Build issue codes", for each port that is not `optional` when no group of its members holds a pin, net, port or interface outside its block. Outside means not owned by the block, directly or through nested blocks. The issue MUST name the block path and the port.

#### Scenario: Port nobody wired
- **GIVEN** `examples/blocks/design.py` with the line that connects `GND` to `ch1.GND` removed
- **WHEN** it is built with `--dry-run --json`
- **THEN** `issues` hold one `build.port-unused` naming `ch1` and `GND`, and the exit code is 0

#### Scenario: Optional port
- **WHEN** the port `EN` of `channel` is declared with `optional=True` and left unwired in `ch1`
- **THEN** `issues` hold no `build.port-unused` naming `ch1` and `EN`

### Requirement: Nets that escape a block
The build SHALL give the warning `build.block-net-escape`, which joins the closed build set as a code added under "Build issue codes", for each script-named net that holds pins of parts inside and outside a block when no port of that block binds the net. The issue MUST name the net and the block path. A design without blocks MUST NOT give it.

#### Scenario: Global net closed over
- **GIVEN** a block whose function connects a part to a global `Net("VIN48")` that pins outside the block also use, with no port
- **WHEN** the design is built with `--dry-run --json`
- **THEN** `issues` hold one `build.block-net-escape` naming `VIN48` and the block path

### Requirement: Block sheets in KiCad
The child sheet that the readable KiCad schematic writes for a block instance SHALL be displayed with the name `<instance name> (<block name>)`, and its file name MUST stay the one of "Hierarchical sheets in a build". A design without blocks MUST keep its schematic bytes.

#### Scenario: Sheet named after the block
- **GIVEN** `examples/blocks/design.py`
- **WHEN** it is built for target 10 with `--confirm --json`
- **THEN** `sheets/ch0.kicad_sch` is written, and the root sheet's reference to it has the `Sheetname` `ch0 (channel)`

### Requirement: Block groups in Altium composition
When block composition is in force ("Composition selection and backwards compatibility"), each block instance that owns parts directly SHALL give an implicit `schematic_block`. Its key is the instance path, its members are the parts the instance owns directly minus those of declared blocks, and its title is `<path> (<block name>)`. A declared block with the same key MUST replace it. Without block composition, no implicit block is made.

#### Scenario: Implicit Altium groups
- **GIVEN** `examples/blocks/design.py` with `schematic_layout(mode="blocks")`
- **WHEN** `uv run pytest tests/unit/dsl/test_blocks.py -k schematic` extracts the composition intent
- **THEN** it holds one block per instance, keyed `ch0` and `ch1`, each holding that instance's parts

#### Scenario: No mode, no implicit intent
- **WHEN** the same design is built for Altium without block composition
- **THEN** no unused-intent diagnostic is given, and the native documents equal those of the grid layout
