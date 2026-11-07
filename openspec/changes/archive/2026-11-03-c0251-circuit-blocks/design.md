## Context

- **Source.** `docs/research/circuit-as-code.md` (2026-10-29), section 4 "Blocks with ports and
  parameters" and core change D. That page compares JITX (Python API 4.x), atopile 0.14 and tscircuit with
  Fenolite 0.6.0. Only concepts are taken. No code, grammar, schema, library element name, constant or
  table of those projects is copied, whatever their licence.
- **What exists on `dev` (0.6.0).**
  - `dsl/module.py`: `Container` (shared by `Design` and `Module`) holds `children`, `pending_nets` and
    `pending_interfaces`. `Module(name)` has a `path` (`<parent path>/<name>`) and nothing else.
  - `dsl/part.py`: `Net(name)` with a global literal name; `connect(net, *pins)`. A designator can be on
    one net only, and "There are no implicit nets and no net merges" (`design-dsl`, "Connections and pin
    designators").
  - `dsl/convert.py`: `to_model` gives one model `Module(path, parent, component_ids)` per DSL module, with
    the id `derived_id("mod", "dsl", "module:<path>")`. A component path is `<module path>/<ref>`, kept in
    the property `fenolite.path`.
  - `dsl/interfaces.py`: `Interface(name, kind, members)` and its subclasses `Power`, `DiffPair`,
    `Harness`, and the buses `I2C`, `SPI`, `UART`, `USB2`, recorded as model `Interface` entities.
  - The readable KiCad schematic writes one child sheet per module (`design-dsl`, "Hierarchical sheets in a
    build"). The Altium block composition takes `schematic_block(key, members=...)` declarations
    (`design-dsl`, "Schematic composition declarations").
  - Equal refs in two modules are `model.duplicate-ref` (exit 5). A repeated circuit therefore numbers its
    refs by hand.
- **Today vs proposed.** Today, from the pattern of `examples/yardstick/design.py`, reduced:

  ```python
  vin, gnd = Net("VIN48"), Net("GND")  # global, closed over


  def channel(n, x, y):
      m = Module(f"ch{n}")
      en = Net(f"CH{n}_EN")  # names by hand
      r = Part(f"R{n * 100 + 1}", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="10k")
      connect(en, r[1])
      connect(vin, r[2])  # vin is global: nothing says the block needs it
      m.add(r)
      return m


  design.add(*(channel(n, 10 * n, 0) for n in range(8)))
  ```

  Proposed:

  ```python
  from fenolite.dsl import block, Net, Rail, Ground, connect, ohm, volt, amp


  @block
  def channel(b, *, r_en=ohm("10k"), vmax=volt("60")):
      """One buck channel. Ports: VIN, GND, EN."""
      vin = b.port("VIN", Rail, direction="in")
      gnd = b.port("GND", Ground, direction="in")
      en = b.port("EN", Net, direction="out", optional=True)
      fb = b.net("FB")  # becomes ch3/FB
      r = b.part("R_EN", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value=r_en)
      connect(en, r[1])
      connect(vin, r[2])  # a port is net-like
      ...


  vin48 = Net("VIN48")
  gnd = Net("GND")
  for n in range(8):
      ch = design.use(channel, f"ch{n}", r_en=ohm("10k"))
      connect(vin48, ch.VIN)
      connect(gnd, ch.GND)
  ```

  `ch3/R_EN` gets its ref (`R17`, say) from `<script stem>.lock` (c0249). The model's module `ch3` records
  `block = "channel"` and `params = r_en: 10kΩ, vmax: 60V`.

## Goals / Non-Goals

**Goals**

- A reusable circuit states its interface (ports with a type and a direction) and its parameters, and the
  build reports a port that nobody wired.
- Two instances of one block never collide in net names or refs, without the user numbering anything.
- The model records which block made each module, with which parameters, so that `inspect`, the viewer
  and later changes (c0255 layout per block, c0256 tests) can read it.
- No magic: a block is an ordinary function, and stepping through it in a debugger shows ordinary calls.
- Zero change for scripts that do not use blocks: same API, same model bytes.

**Non-Goals**

- See the proposal. Also: no parameter solver, no inference of ports from usage, and no hidden "current
  block" state. Every object still joins the design through an explicit call (`add`, `part`, `net`,
  `port`, `use`).

## Decisions

### 1. A block is a decorated function

```python
@block  # or @block(name="buck")
def buck(b, *, vout=volt("3.3"), current=amp(2)): ...
```

- `@block` inspects the signature once and raises `DslError` at decoration time when any of these fails:
  - exactly one positional parameter (the builder) comes first;
  - every other parameter is keyword-only;
  - there is no `*args` and no `**kwargs`;
  - every default is a recordable value (decision 3).
- It returns a `BlockDef(name, function, signature)`. The block name is the function's `__name__`, or the
  `name=` given, and MUST match the module-name pattern.
- Calling a `BlockDef` directly raises `DslError` ("use design.use(buck, name, ...)"). A block's function
  never runs outside an instance, so its objects always have a parent.
- The function's return value MUST be `None`. Anything else raises `DslError`, because the instance
  object, not a return value, is what the caller gets (decision 2).
- **Alternatives considered.**
  - A class with `__init__` parameters and ports as attributes (JITX's form). Rejected: attribute order and
    class-body evaluation are the magic the research refuses, and an instance must still be named and
    added.
  - A metaclass that collects class attributes. Rejected for the same reason.
  - Plain functions that take `Module` (today's pattern). Rejected: no ports, no recorded parameters, no
    checks.

### 2. Instances: `design.use` and `b.use`; `Block` is a `Module`

- `design.use(block, name, **params) -> BlockInstance` and the builder's `b.use(...)` do these steps:
  1. create `Block(name, block_def, params)`, a subclass of `Module`;
  2. add it to the caller (the design, or the enclosing block);
  3. bind and record the parameters (decision 3);
  4. call the function with the block as `b` and the bound keyword arguments;
  5. return the instance.

  If the function raises, the block stays added and partly filled, and the error propagates. Scripts do not
  catch `DslError`, and the build reports it as `FEN-3004`.
- `Block` keeps every `Module` behaviour: its `path`, `add()`, its sheet in the readable KiCad schematic,
  its model `Module` entity. Code that walks modules (`register_tree`, `to_model`, `schgen`) sees a block
  as a module and needs no change, except to read the new fields.
- The builder `b` offers:
  - `b.part(name, lib_id=None, *, device=None, footprint=None, value="", ref=None, prefix=None,
    properties=None, ...)`, with the keywords of c0249's `design.part(name=...)`:
    it creates a part named `name`, adds it to the block and returns it;
  - `b.net(name)`: a local net (decision 5);
  - `b.port(...)`: decision 4;
  - `b.use(...)`: a nested instance;
  - `b.add(...)`: as `Module.add`;
  - read-only `b.path`, `b.name`, `b.params`.
- `BlockInstance` offers:
  - each port as an attribute (`inst.VIN`) and through `inst.port("VIN")`;
  - `inst.path`, `inst.block` (the `BlockDef`) and `inst.params` (a read-only mapping);
  - `inst.part(name)`, which returns the block's part of that local name, for placement and for c0255.

  A port name that equals an attribute of `BlockInstance` (`path`, `block`, `params`, `part`, `port`,
  `place`) raises `DslError` at `b.port`.
- **Alternative considered:** a separate `Block` class that does not inherit `Module`. Rejected: every
  module-walking reader would need a second case, and the KiCad sheets would not come for free.

### 3. Parameters recorded in the model

- `inspect.Signature.bind(**params)` followed by `apply_defaults()`. An unknown or missing keyword raises
  `DslError` naming the block and the parameter.
- **Recordable types**, closed. Each value becomes a `BlockParam(name, type, text)`:

  | Python value | `type` | `text` |
  |---|---|---|
  | `bool` | `bool` | `true` / `false` |
  | `int` | `int` | decimal |
  | `str` | `str` | the string |
  | `Length` | `length` | integer nanometres, decimal |
  | `Quantity` | `quantity` | `Quantity.text()` |
  | c0246 range | `range` | c0246's canonical range text |
  | `None` | `none` | empty |

  Any other value (a part, a net, a list, a float, a function) raises `DslError`: "parameter `x` of block
  `buck`: a `list` cannot be recorded; pass a recordable value or build the object inside the block". A
  `bool` is tested before `int`.
- The model `Module` gains `block: str` (empty for a plain module) and
  `params: tuple[BlockParam, ...]`, ordered by name. Both are omitted from `circuit.json` when empty.
- **Why record them.** A reviewer, `inspect`, the viewer and c0256's tests can see which parameters made
  an instance. c0249's lock can hold picks per instance. c0253's checks can explain a finding with the
  parameter that set the limit.
- **Alternative considered:** recording `repr()` of any value. Rejected: `repr` is not canonical, and
  floats would enter the model.

### 4. Ports: name, interface type, direction

```python
vin = b.port("VIN", Rail, direction="in")  # Rail, Ground, Logic: c0252
bus = b.port("I2C", I2C)  # direction defaults to "inout"
en = b.port("EN")  # kind Net: a single net
```

- `b.port(name, kind=Net, *, direction="inout", optional=False) -> PortHandle`. The arguments:
  - `name`: the module-name pattern, unique within the block;
  - `kind`: `Net`, or an `Interface` subclass of `fenolite.dsl.interfaces`, or of `fenolite.dsl` for
    c0252's classes;
  - `direction`: one of `in`, `out`, `inout`;
  - `optional`: silences `build.port-unused` for that port.
- **Members.** A port of kind `Net` has one member, `net`. A port of an interface kind has the members of
  that kind's closed member table, which this change writes into `fenolite.dsl.interfaces`:

  | kind | members |
  |---|---|
  | `power` | `hv`, `lv` |
  | `diff_pair` | `p`, `n` |
  | `i2c` | `sda`, `scl` |
  | `uart` | `tx`, `rx` |
  | `usb2` | `dp`, `dn`, `vbus`, `gnd` |
  | `spi` | `sck`, `mosi`, `miso`, `cs0` |

  A `Harness` port and an `SPI` port with more chip selects take `members=(...)`, `selects=n` or `cs=n`.
  c0252 adds `ground` (`gnd`), `logic` (`io`) and the parameters.
- Each member of a port is a **port net** (decision 6). A `PortHandle` is net-like when it has one member,
  or when c0252's kind table names one main member (`power` → `hv`). `connect(port, pins...)` and
  `connect(net, port)` then work on that member. `handle["sda"]` or `handle.sda` gives the port net of one
  member, usable wherever a `Net` is accepted.
- Inside the block, a port is wired like a net. Outside, `inst.VIN` is the same handle.
- **Direction** is recorded and read by c0252's checks (an `out` power port is a source). This change
  checks direction only for the kind `Net`: an `out` port of kind `Net` bound to another `out` port gives
  no finding here (c0252 owns logic levels).
- **Alternative considered:** the research sketch's `provides=True`. Replaced by one `direction` argument
  that also serves logic and buses.

### 5. Local nets

- `b.net(name)` returns a `Net` named `<block path>/<name>`, for example `buck1/FB` or `power/buck1/FB` when
  nested. It is added to the block (`pending_nets`). `name` MUST match the module-name pattern, which keeps
  `/` out of it.
- A plain `Net("X")` created inside a block function is still a global net named `X`, as today. A global
  net that joins pins inside and outside the block without passing through a port gives
  `build.block-net-escape` (decision 7). The warning names the net and the block, and its hint is "declare
  a port".

### 6. Port nets and their binding

The one mechanism that lets a block wire to something it cannot name.

- A port net is a `Net` whose name is not fixed when it is created. `connect()` binds port nets and nets
  into **groups**: `connect(x, port_net)`, `connect(port_net, pin)` with `x` a net or a port net, and c0252's
  member-wise `connect` of whole interfaces.
- At `to_model` (and at any earlier query of `net.name`), each group gets one name. A group holds at most
  one script-named net (`Net("X")`, `b.net`, c0252's `design.rail`):
  - a group with exactly one script-named net takes its name;
  - a group with none takes the path of its preferred port member, `<owner path>/<port>` for a
    single-member port and `<owner path>/<port>.<member>` otherwise. The preferred member is an `out` port
    member first, then the smallest path in code-point order. The name therefore does not depend on the
    order of the calls.
- Joining two script-named nets in one group raises `DslError` at the `connect` call that would join them,
  naming both nets and the port. This keeps the rule that Fenolite never merges named nets.
- A designator on two different groups is still refused ("Connections and pin designators").
- **Example.** `connect(p1.VOUT, p2.VIN)` with no outside net gives the net `buck1/VOUT` if `VOUT` is an
  `out` port. `connect(v33, p1.VOUT)` gives `3V3`.
- **Alternatives considered.**
  - Merging named nets (atopile's alias). Rejected: a typo would silently join two nets.
  - Requiring the outside net to be passed as a parameter. Rejected: nets are not recordable parameters,
    and that is today's closure problem in another form.

### 7. Build checks: port used, net escape

| code | severity | when |
|---|---|---|
| `build.port-unused` | warning | a port that is not `optional` has, in the group of a member, no pin, net, port or interface outside its block |
| `build.block-net-escape` | warning | a script-named net that no port of block B binds holds pins of parts inside B and outside B |

- Both are computed by `lens.build` from the DSL tree, after `to_model`. They join the closed set of
  "Build issue codes" as later codes. Each names the block path and the port or net. Both can be waived
  (c0114).
- "Outside" means not owned, directly or through nested blocks, by that block. A port of a nested block
  inside B is inside B.
- **Why warnings.** A warning matches the existing `build.i2c-pullup-missing`. An unused enable input may be
  intended; `optional=True` states that.

### 8. Ref namespace

- The first argument of `b.part` is the **local name**, the leaf of the component path (`buck1/U`). It
  is c0249's `name=` of `design.part`, follows the ref pattern and is unique in the block.
- The board ref (`Component.ref`) is, in order:
  1. `ref=` when given (global, checked like any ref);
  2. the ref that c0249's `<script stem>.lock` records for the path;
  3. the next free ref of the part's prefix from c0249's allocator. The prefix follows c0249's rule:
     `prefix=`, else the device's `ref_prefix`, else the catalog symbol's prefix.

  `Part(...)` objects added to a block with `b.add` are named by their `ref` argument, which becomes the
  local name, and get board refs in the same way.
- `<script stem>.lock` (c0249, `fenolite.lock.v0`) keys refs by path. Blocks add keys, not a schema change:

  ```toml
  schema = "fenolite.lock.v0"
  [refs]
  "buck1/L" = "L1"
  "buck1/U" = "U1"
  "buck2/L" = "L2"
  "buck2/U" = "U2"
  "ch3/R_EN" = "R17"
  ```

- A plain `Module` keeps hand refs: its part's ref is its ref, and `model.duplicate-ref` still applies.
- **Alternative considered:** per-instance ref offsets (`ref_base=300`, the yardstick's `n*100+k`).
  Rejected for the default; open question 4.

### 9. Schematic groups from the block path

- **KiCad.** Each block instance already gets a child sheet as a module (`sheets/<path>.kicad_sch`). This
  change sets the sheet's displayed name to `<name> (<block name>)`, for example `buck1 (buck)`. The sheet
  file name is unchanged, so `layout-lens` keeps the footprint paths.
- **Altium block composition.** When `schematic_layout(mode="blocks")` or `--altium-layout blocks` is in
  force, each block instance that holds parts gives an implicit `schematic_block`:
  - key: its path;
  - members: the parts it owns directly;
  - title: `<path> (<block name>)`;
  - anchor and `after`: none.

  A declared `schematic_block` with the same key replaces the implicit one. A part that a declared block
  holds is removed from the implicit block, so the rule "every member assigns all its symbol units" keeps
  holding. Implicit groups never raise "unused intent": without block mode they are not made.
- **Alternative considered:** a new presentation entity for groups. Rejected: the module tree already is
  the grouping.

### 10. Model

- `fenolite.model.circuit`:
  - `Module` gains `block: str = ""` and `params: tuple[BlockParam, ...] = ()`;
  - `BlockParam(name, type, text)` is a frozen value object;
  - `Port(Entity)` has these fields:
    - `name`;
    - `owner`: the id of a module, or of a component for c0252's device ports;
    - `kind`;
    - `direction`;
    - `members: dict[str, str]`: member → net id, a member without a net left out;
    - `optional: bool = False`;
  - `Circuit.ports: tuple[Port, ...] = ()`.

  Each new field is omitted when empty or default. A `circuit.json` written by 0.6.0 loads, validates
  against the regenerated schema and is written back with the same bytes.
- **Ids.** Prefix `prt` in `core/ids.py`. The key is `port:<owner path>:<port name>`, where the owner path is
  the module path, or the component path for a device port. It is added to `fenolite.dsl.KEYS` and to the
  table of `design-model`, "Identifier derivation".
- `Design.validate()` gains no code. A bad direction or two params with one name are a `ValueError` when
  the value object is built.
- Example `circuit.json` fragment (ids shortened):

  ```json
  {"modules": [{"block": "buck", "id": "mod_…", "params": [
      {"name": "current", "text": "2A", "type": "quantity"},
      {"name": "vout", "text": "3.201V..3.399V", "type": "range"}], "path": "buck1"}],
   "ports": [{"direction": "out", "id": "prt_…", "kind": "power",
      "members": {"hv": "net_…(3V3)", "lv": "net_…(GND)"}, "name": "VOUT", "owner": "mod_…"}]}
  ```

  The range text is c0246's. The example only shows the shape.

### 11. Codes and errors

- New build issue codes: `build.port-unused` and `build.block-net-escape`, both warnings, with
  `explain.toml` entries.
- New `DslError` cases, each raised at the offending call and reported by `cmd_build` as `FEN-3004`:
  - a bad block signature;
  - a direct call of a `BlockDef`;
  - an unknown, missing or unrecordable parameter;
  - a return value other than `None`;
  - a duplicate port, local net or local part name;
  - a port name that shadows an instance attribute;
  - two named nets joined through port nets;
  - two different functions with one block name in one design.
- No new `FEN-` code.

## Risks / Trade-offs

- **Port-net naming surprises.** A net called `buck1/VOUT` on the board when the user expected `3V3`.
  Mitigation: the rule is documented, `inspect` shows it, and naming the outside net (`connect(v33, ...)`)
  fixes it. The name is deterministic.
- **Rebinding renames nets.** Connecting a previously unnamed group to a named net renames its copper.
  `layout-lens` already carries copper of a renamed net through `moved_net`. The hint of `layout.net-removed`
  names `moved_net`.
- **Two module flavours.** `Module` (hand refs) and `Block` (allocated refs) differ in ref rules. Mitigation:
  `docs/dsl.md` recommends blocks for anything repeated and keeps `Module` for grouping.
- **Ref churn without the lock.** Allocated refs depend on c0249's lock. Without a confirmed lock, refs are
  allocated in path order. That is deterministic but changes when a block is inserted. c0249's `--frozen`
  covers releases.

## Open Questions

1. **Should a block run alone for unit tests?** Recommended: no direct call. c0256 adds
   `fenolite.testing.instantiate(block, **params)`, which wraps a throwaway design.
   Decided 2026-10-29: no direct call; c0256 adds `fenolite.testing.instantiate`.
2. **Should `build.port-unused` be an error?** Recommended: a warning in 0.7. Revisit after the examples and
   one maintainer board use blocks.
   Decided 2026-10-29: a warning in 0.7.
3. **Should `build.block-net-escape` become an error?** Recommended: a warning now. A closed-over global
   `GND` is common in migrated scripts.
   Decided 2026-10-29: a warning.
4. **Ref offsets per instance** (`design.use(..., refs_from=300)`)? Recommended: not now. The lock gives
   stable refs; offsets can be a later keyword that c0249's allocator honours.
   Decided 2026-10-29: not now; the lock gives stable refs.
5. **Port arrays** (`b.port("CH", Logic, count=4)`)? Recommended: later, with c0257 pin assignment. A loop
   with f-string names works today.
   Decided 2026-10-29: later, with c0257.
6. **Block name in the model: the function name, or a qualified `module.qualname`?** Recommended: the
   function name, or `@block(name=)`. Script module names are not stable, and two functions with one name in
   one design are refused.
   Decided 2026-10-29: the function name, or `@block(name=)`.

## Relation to the other changes of this batch

- **c0246 (A):** a range is a recordable parameter (`type = "range"`). The text is c0246's.
- **c0247 (J):** helpers such as `series`, `decouple` and `unused_no_connect` take port nets like nets. No
  change is needed in c0247.
- **c0248 (B):** `b.part(name, device=...)` is c0248's device part inside a block. c0252 adds device ports.
- **c0249 (C):** allocates and freezes the refs of block paths (decision 8). Its lock keys are paths.
- **c0250 (G):** edits merged per property are keyed by path, so block-local paths are stable keys.
- **c0252 (E):** builds on the ports and port nets defined here. It adds `Rail`, `Ground` and `Logic`,
  port parameters (`voltage`, `current`, `reference`), interface-to-interface `connect`, device ports and
  the `circuit.rules` checks. Implementation order: c0251 tasks 1 to 3, then c0252.
- **c0253 (F):** reads `Module.params` to explain contracts.
- **c0255 (I):** block pose, strategy and layout reuse per block path.
- **c0256 (K):** block tests.
