## Context

The DSL connects pins with `connect(net, *pins)` and marks open pins with `no_connect(*pins)`
(`src/fenolite/dsl/part.py`). Designators are stored as written; the build (`lens.build.build_design`)
resolves them against the library symbol, because the DSL reads no library ("DSL package"). So the DSL
does not know how many pins a part has, which are power inputs, or what pins exist at all. Placement
intent is `Design.near(key, parts, anchor, within=...)`, lowered to `RuleSet.proximity` and judged by
the `placement.rules` stage of `fenolite check`.

The research page `docs/research/circuit-as-code.md`, section 6 and core change J, proposes:

```python
series(vin, f1, d1, vprot)  # two-terminal chain: vin-F1-D1-vprot
decouple(rail, gnd, capacitor(farad("100n")), near=mcu.vdd)  # also records a near() intent
u1.unused_no_connect()  # every pin with no net and no "must connect" flag
r1.a, r1.b  # two-pin parts get named ends (a/b, or the device's +/-)
```

Concepts come from atopile (a series bridge through two-terminal parts), tscircuit (per-pin connections;
a resistor that names the pin it pulls up) and JITX (`no_connect()` on a port). No code, grammar or name
of theirs is copied.

### Today and proposed

Today (the blink, `examples/blink_2layer/design.py`, and the research page's sensor board):

```python
connect(vin, u1[9])
connect(gnd, u1[10], d1[1])
connect(led_drv, u1[1], r1[1])
connect(led_a, r1[2], d1[2])
no_connect(*(u1[pin] for pin in range(1, 33) if pin not in (1, 9, 10)))  # 29 pins by hand

connect(sda, u2["PB7"], u3["SDA"], r3[2])
connect(scl, u2["PB6"], u3["SCL"], r4[2])
connect(v33, r3[1], r4[1], c3[1])
connect(gnd, c3[2])
design.near("dec", c3, u2.pad(4), within=mm(3))
```

Proposed (this change only; devices, blocks and value-picked parts come later in the batch):

```python
connect(vin, u1[9])
connect(gnd, u1[10])
series(led_drv, r1, led_a, (d1.b, d1.a), gnd)  # LED anode is pin 2 of Mini_LED: turned around
connect(led_drv, u1[1])
u1.unused_no_connect()  # the same 29 marks, resolved at build

pull_up(I2C(sda, scl), v33, r3, r4)  # R3 on SDA, R4 on SCL, both to 3V3
decouple(v33, gnd, c3, near=u2.pad(4), within=mm(3))  # C3 between 3V3 and GND, rule decouple/C3
```

### Relation to the other changes of the batch

| change | relation |
|---|---|
| c0246 quantity-ranges | implemented together (step 1); independent code |
| c0248 device-catalog | a device may name its two ends and flag pins `must_connect`; Decisions 1 and 6 read them through one hook |
| c0251 circuit-blocks | helpers work inside a block unchanged: they take parts and nets, and the generated joint nets take the parts' paths |
| c0252 parametric-interfaces | widens `pull_up`'s target to `Logic`/bus interfaces and lets `decouple` take a `Rail` |
| c0254 parametric-part-selection | lets a helper take a value (`farad("100n")`) and pick the part |
| c0255 relative-placement | may place the capacitor of a `decouple` rule; this change only records the rule |

## Goals / Non-Goals

**Goals**
- Shorter scripts for series chains, decoupling, pull resistors and unused pins, lowering to what exists.
- Unused pins marked from the resolved symbol, so a wrong pin number cannot hide a pin.
- A must-connect guard so that "mark the rest" never marks a supply pin.

**Non-Goals**
- Creating parts, choosing values, default distances, placement, interface-to-interface connection.
- A model change: the lowering produces nets, `Circuit.no_connects` and `RuleSet.proximity`.

## Decisions

### 1. Named ends `a` and `b`

`Part.a` and `Part.b` are read-only properties returning `self["1"]` and `self["2"]`, and setting
`Part.two_terminal = True`. Every helper of this change sets it too for the parts it takes.

- The build checks every part with `two_terminal` after library resolution: a symbol whose pin count is
  not two gives `build.not-two-terminal` (error, exit 5, nothing written), naming the ref and the count.
  A two-pin symbol numbered otherwise (`A`, `K`) already fails with `build.unknown-pin` on `1`.
- **Device ends (c0248).** When a part comes from a catalog device that declares its ends (for example
  `ends = ["+", "-"]` or `["A", "K"]`), `a` and `b` name those pins instead. c0248 owns that field; this
  change defines the lookup `Part._end(index)` that c0248 extends, and nothing else.
- Pins named `a` or `b` of a device are reached with `part["a"]`; c0248 decides whether attribute pin
  access may shadow the ends (open question 3).

*Alternatives.* `r1.p1`/`r1.p2`: clearer about numbering, but less natural for polarised parts once
devices name them. `r1.ends` returning a pair: fine for unpacking, clumsy in calls. Inferring two-pin
parts from the lib id: the DSL reads no library.

### 2. `series(*chain) -> tuple[Net, ...]`

- The first and last items are `Net`s, and at least one part lies between them.
- Between them an item is a `Part` (entered at `a`, left at `b`), a tuple `(in_pin, out_pin)` of two
  distinct pin handles of one part (to turn it around or use other pins), or a `Net` that names the joint
  between the parts on either side. Two `Net`s next to each other are refused (that would merge nets).
- Two parts next to each other are joined by a new `Net` named `<left path>-<right path>`
  (`F1-D1`, `psu/F1-psu/D1`). A name that another net of the design already has raises `DslError` at the
  connection, by the existing rule "two distinct nets are named".
- Every check runs before the first `connect`, so a refused call connects nothing. The function returns
  the new nets in chain order.

*Alternatives.* An operator (`vin >> f1 >> d1 >> vprot`): compact, but operator overloading on `Net` and
`Part` surprises readers and type checkers. Unnamed joint nets left for the build to name: the names would
then depend on the build and could not be used in rules.

### 3. `decouple(rail, ground, *capacitors, near=None, within=None, severity="error")`

- Each capacitor joins `rail` at `a` and `ground` at `b` (two-terminal; for a polarised capacitor whose
  pin 1 is the positive pin, `a` is positive; a device's named ends override, Decision 1).
- `near` and `within` are given together or not at all. With them, each capacitor gets one rule
  `design.near("decouple/<capacitor path>", capacitor, near, within=within, severity=severity)`, so all of
  `near()`'s checks apply (key pattern, duplicate key, sides, positive `within`). `near` takes what
  `near()`'s `anchor` takes: a `part.pad(...)`, a part, a module, or a list of them. A pin handle such as
  `mcu.vdd` is refused with `near()`'s hint `part.pad(<number>)` until c0248 gives pins their pads in the
  DSL (open question 1).
- The design is the capacitor's design; a capacitor not yet added to a design, with `near` given, raises
  `DslError` asking to add it first.
- There is no default `within`: a distance is an engineering choice that Fenolite does not ship.

*Alternatives.* One rule for all capacitors of a call: fewer rules, but one finding would hide which
capacitor is far. A default distance from an application note: not a public standard; refused by the
clean-room rules.

### 4. `pull_up(target, rail, *resistors)` and `pull_down(target, ground, *resistors)`

- `target` is a `Net` (one resistor) or an `I2C` (two resistors: the first on `sda`, the second on
  `scl`). Any other interface raises `DslError` naming its kind; c0252 widens this.
- Each resistor joins its signal net at `a` and `rail` (or `ground`) at `b`: the first net argument takes
  `a`, as in `decouple`.
- The number of resistors must equal the number of target nets; a signal net equal to `rail` is refused;
  a `Quantity` or `Range` given instead of a part raises `DslError` saying a value does not choose a part.
- Nothing is recorded beyond the connections: c0253 recognises pull-ups from the topology.

### 5. `Part.unused_no_connect(*, keep=())`

- Records a request on the part (`Part.unused_request: frozenset[str]`, the `keep` designators as
  written). A second call on one part raises `DslError`. `keep` items are designators (`str` or `int`).
- `dsl.convert.unused_marks(design) -> Mapping[str, tuple[str, ...]]` gives the requests by part path,
  and `dsl.convert.two_terminal(design) -> tuple[str, ...]` the paths of Decision 1, in path order. They
  are side channels of the build, like `heights()` and `pad_zones()`: `to_model` is unchanged, and the
  build stores the resolved marks in `Circuit.no_connects`.
- `connect` and `no_connect` stay allowed after the request; it applies to what is open when the build
  runs.

*Alternative.* A model field for the request: it would be meaningless after a build resolved it, and
every reader of the model would have to ignore it. Marking in the DSL from a pin count given by the user:
the error the helper removes would come back.

### 6. Resolution at build, and must-connect pins

After nets and explicit marks are resolved ("No-connect marks in a build"), for each requested part, in
pin-number order of the resolved symbol:

1. `keep` designators resolve like any designator (number first, then name); an unknown one gives
   `build.unknown-pin`.
2. A pin is skipped when a net lists it, it is already marked, it is in `keep`, or its type is
   `no_connect` (the symbol already says it is open).
3. A **must-connect** pin gives `build.must-connect-unconnected` (error, exit 5, nothing written), naming
   the ref, the pin number and the pin name, with the hint "connect it, or list it in keep=". A pin is
   must-connect when its type is `power_in`, or when the part comes from a catalog device that flags the
   pin `must_connect = true` (c0248 adds the flag to the device's pin table; the build asks one function,
   `must_connect_pins(component, device)`, which c0248 extends).
4. Every other pin becomes a mark `PinRef(<component id>, <pin number>)`.

The new marks join the explicit ones without duplicates and follow every rule of explicit marks: they
reach `.fenolite/circuit.json`, become no-connect flags of the schematic, and leave the board bytes
unchanged. The Altium build (`lens/altium.py`) applies the same resolution, so both targets get one set
of marks.

Why `power_in`: KiCad's own electrical rules treat an undriven power input as an error, and marking one as
intentionally open would silence that. It is a Fenolite choice about pin types, not an engineering
number.

### 7. Issue codes

| code | severity | when |
|---|---|---|
| `build.not-two-terminal` | error | a part used through `a`/`b` or a helper has a symbol with other than two pins |
| `build.must-connect-unconnected` | error | `unused_no_connect` meets an open must-connect pin |

Both join `lens.build.BUILD_ISSUE_CODES` and the Altium build's codes, `docs/cli-contract.md`, and
`src/fenolite/cli/data/explain.toml`. No `FEN-` code is added.

### 8. Files and public API

- New `src/fenolite/dsl/wiring.py`: `series`, `decouple`, `pull_up`, `pull_down`; imports `dsl.part`,
  `dsl.interfaces` and `dsl.errors` only (an addition under "DSL package").
- `dsl/part.py`: `Part.a`, `Part.b`, `Part.two_terminal`, `Part.unused_no_connect`, `Part.unused_request`.
- `dsl/convert.py`: `unused_marks`, `two_terminal`.
- `dsl/__init__.py` re-exports `series`, `decouple`, `pull_up`, `pull_down`.
- `lens/build.py`, `lens/altium.py` and the callers that pass `heights` today (`cli/cmd_build.py`,
  `cli/cmd_silk.py`, `exports/impedance.py`) pass the two side channels.

## Evidence level per behaviour

| behaviour | level before merge |
|---|---|
| helpers lower to nets, marks and rules | unit tests on `to_model` |
| unused marks equal explicit marks | `KICAD-VERIFIED`: the blink rewritten with `u1.unused_no_connect()` keeps every pinned digest of `tests/unit/lens/test_build_bytes_pinned.py`, and CI's KiCad job runs ERC on it |
| new codes stop the build | build tests (no `kicad-cli` needed) |

## Risks / Trade-offs

- **Generated net names** (`F1-D1`) may collide with a user's net or read oddly in KiCad. Mitigation:
  a collision is an error, and a `Net` between parts names the joint (open question 2).
- **Pin-type quality.** A symbol that types a supply pin `passive` escapes the must-connect guard.
  Mitigation: device flags (c0248) cover reviewed parts; `docs/dsl.md` says what is checked.
- **Hidden power pins** of some library symbols are handled like any pin: open and `power_in` gives the
  error. That is the intended, safe direction.

## Open Questions

1. Should `decouple(near=...)` accept a pin handle (`mcu.vdd`) as the research sketch writes? *Recommended:*
   not in this change; c0248 gives device pins their pads in the DSL, and then `near()` and `decouple` can
   take a pin handle of a device part.
2. Is `<left path>-<right path>` the right joint name? *Recommended:* yes; it is unique per pair of parts,
   readable in KiCad, and replaceable by a `Net` in the chain.
3. Should `part.a`/`part.b` win over device pins named `a`/`b` under c0248's attribute access?
   *Recommended:* the ends win, and such pins use `part["a"]`; c0248 confirms.
4. Should `unused_no_connect` also exist on a module or the design (all parts at once)? *Recommended:*
   not yet; marking a whole board hides forgotten connections, which is what the guard is for.
