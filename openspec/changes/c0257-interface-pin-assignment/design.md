## Context

Source: `docs/research/circuit-as-code.md`, section 12 "Pin assignment at the interface level (later)",
core change L. Concept only, paraphrased from JITX's public documentation (an MCU offers interface options,
a consumer requires one, a solver picks). No code, syntax, schema or library text of JITX is used.

What exists or is proposed in this batch, and is reused:

- `I2C`, `SPI`, `UART`, `USB2` interfaces with fixed roles and `bus.attach(part, sda=...)` (`design-dsl`,
  "Typed interfaces in the DSL", "Attaching parts to interfaces").
- c0248: `Device` records in the catalog (MPN, pin functions, ratings, evidence) and `Part(device=)` with
  checked pin access.
- c0249: `<script stem>.lock`, written only through plan/confirm by `build --confirm`, and `--frozen`.
- c0251: blocks with a ref namespace, so a part path is `buck/U1`.
- c0252: parametric interfaces and `connect(interface, interface)`.
- c0247: `unused_no_connect()`.

## Goals / Non-Goals

Goals: name the function, not the pins; a choice that is deterministic, explained, reviewed in the plan and
kept in the lock; a clear finding when no choice exists.

Non-goals: swaps from routing, a general solver, firmware output, electrical compatibility (c0253).

## Decisions

### 1. Options live in the device record

```toml
# src/fenolite/catalog/devices/example_mcu_qfn32.toml  (illustrative device, authored for Fenolite)
[[options]]
kind = "i2c"
name = "I2C1"
alternatives = [
  { sda = "PB7", scl = "PB6" },
  { sda = "PB9", scl = "PB8" },
]

[[options]]
kind = "uart"
name = "UART2"
alternatives = [ { tx = "PA2", rx = "PA3" }, { tx = "PB3", rx = "PB4" } ]
```

- c0248 reserves the device key `options` for this change (refused with `FEN-3002` until it lands); this
  change defines it. Pin names in alternatives are c0248's function names.
- `kind` is a key of the interface kinds of c0252 (`i2c`, `spi`, `uart`, `usb2`, `diff_pair`); each
  alternative MUST give exactly the roles of the kind, each a pin name of the device.
- Option names are unique per device and kind; alternatives keep their file order (index 0, 1, ...).
- The loader refuses a pin name the device does not have, a missing or extra role, and two equal
  alternatives, with the catalog's malformed-record code of c0248.
- An option inherits the record's evidence; an `evidence` key per option MAY lower it.

Alternative considered: a pin-centred table ("PB7: I2C1_SDA, UART1_RX ..."), closer to datasheets. It is
longer and needs a second step to group roles into alternatives; the option-centred form is what the solve
reads. A converter from a pin table MAY come later as a catalog tool.

### 2. `take` in the DSL

Today:

```python
connect(sda, u2["PB7"], u3["SDA"], r3[2])
connect(scl, u2["PB6"], u3["SCL"], r4[2])
```

Proposed:

```python
mcu = design.part(device="Example:MCU_QFN32")
sen = design.part(device="Example:SENSOR_I2C")
i2c = mcu.take(I2C)  # one of the device's i2c alternatives, chosen at build
connect(i2c, sen.i2c)  # c0252: interface to interface
dbg = mcu.take(UART, option="UART2", name="debug")
gps = mcu.take(UART, pins={"tx": "PB3"})  # a partial pin: only alternatives with tx = PB3
mcu.unused_no_connect()  # c0247: runs after the solve, on the untaken pins
```

- `take` returns a `TakenInterface`, an `Interface` of the kind whose role nets are created at once (named
  `<part path>/<take key>/<role>` unless connected to named nets), so `connect` and `pull_up` work before
  the solve. Only the part pins are pending.
- The take key is `name` when given, else `<kind>#<n>` with `n` the index of takes of that kind on that part
  in script order. The lock key is `<part path>/<take key>`, for example `mcu/i2c#0` or `buck/U1/debug`.
- `option` restricts to one option name; `pins` to the alternatives whose roles match. An unknown option is
  `pins.option-unknown`; `pins` that no alternative matches is `pins.pinned-conflict`.
- A part without a device, or a device with no option of the kind, refuses `take` with `DslError` at the
  call, located by line.

### 3. The solve

`lens.pins.solve(takes, devices, fixed, locked, *, max_steps=100_000) -> PinSolution`:

1. Fixed pins: every pin connected by hand (`connect(net, mcu["PA0"])`) or marked no-connect before the
   solve is unavailable.
2. Locked choices are tried first: a take whose lock entry names an alternative that is still valid
   (option and pins exist, no conflict) gets it, source `locked`.
3. The other takes are ordered by (part path, take key); candidates of a take by (option name, alternative
   index), filtered by `option` and `pins`. A depth-first search with forward checking assigns one candidate
   per take so that no pin is used twice. The first complete assignment in this order wins.
4. If the search exhausts, `pins.unsatisfiable` names the smallest conflicting set of takes found by
   deletion (drop takes one at a time in reverse order while the rest stays unsatisfiable), and the pins
   they compete for.
5. More than `max_steps` candidate trials is `pins.search-limit`.

Determinism: the result is a pure function of the takes, the device records, the fixed pins and the lock.
`--seed` does not enter it, so a build is identical under any seed, which keeps the
"Reproducible builds" requirement true. Alternative considered: a seeded tie-break among equal candidates,
which would spread functions over the package; rejected, because a choice that changes with the seed is
the hidden state the research warns about.

Why locked first: a reviewed choice should not move when an unrelated take is added. If a locked choice
became invalid (the device record changed, a pin got connected by hand), the take is solved again with
`pins.lock-stale` (warning), and with `--frozen` the build refuses with c0249's frozen-lock error.

### 4. Shown in the plan, recorded in the lock

`build`'s `result.pins` (dry run and confirmed run alike):

```json
"pins": [
  {"key": "mcu/i2c#0", "kind": "i2c", "option": "I2C1", "alternative": 1,
   "pins": {"scl": "PB8", "sda": "PB9"}, "source": "solved"}
]
```

sorted by `key`. The lock's planned write appears in `result.plan` like every other file, so the reviewer
sees the `[pins]` diff before `--confirm --plan`.

`<script stem>.lock` (schema `fenolite.lock.v0` of c0249), section added by this change:

```toml
[pins."mcu/i2c#0"]
kind = "i2c"
option = "I2C1"
alternative = 1
pins = { scl = "PB8", sda = "PB9" }
choice = "I2C1 on PB8/PB9"          # human text, ignored when read
```

Keys are sorted; the file is canonical text written only by `build --confirm`. A lock entry whose key no
take has any more is dropped on the next confirmed build, with `pins.lock-dropped` (info).

### 5. Codes

| code | severity | when |
|---|---|---|
| `pins.unsatisfiable` | error | no assignment exists; message names the smallest conflicting takes and their pins |
| `pins.option-unknown` | error | `option=` names no option of that kind on the device |
| `pins.pinned-conflict` | error | `pins=` matches no alternative, or names a pin fixed by hand |
| `pins.search-limit` | error | the search tried more than `max_steps` candidates |
| `pins.lock-stale` | warning | a locked choice is no longer valid and was solved again |
| `pins.unused-take` | warning | a take whose nets reach no other pin |
| `pins.lock-dropped` | info | a lock entry whose take no longer exists was removed |

They join the `build` envelope ("Build issue codes" allows later codes), with `explain.toml` tables. No new
`FEN-` code: an unsatisfiable design is a finding (exit 5), not a usage or input error.

### 6. Files and API

- `src/fenolite/dsl/take.py`: `TakenInterface`, `Part.take`.
- `src/fenolite/lens/pins.py`: `solve`, `PinSolution`, `PinChoice`, `PIN_ISSUE_CODES`.
- c0248's device schema gains `options`; c0249's lock schema gains `pins`.
- `docs/pins.md` (new), linked from `docs/dsl.md`.

### 7. Evidence per behaviour

| behaviour | level |
|---|---|
| solve | `INFERRED`, `H-G-PIN-SOLVE-DETERMINISTIC` (same `result.pins` on three platforms and under three seeds) |
| options | the device record's label; per-option `UNVERIFIED` lowers the build's evidence |
| built connectivity | unchanged: the build's own evidence |

## Relation to the other changes of this batch

c0248 holds the options, c0249 the lock and `--frozen`, c0252 the kinds and `connect`, c0251 the block
paths, c0247 `unused_no_connect` (which must run after the solve, so it is recorded at the call and applied
after), c0250 (manual edits) is how a pin swap made in KiCad comes back, as an edit of a `pins=` argument
proposed by `sync --to-source`. c0253 judges the levels of the chosen pins. c0256's `findings()` reports the
`pins.*` codes in tests.

## Risks / Trade-offs

- Exponential worst case: bounded by `max_steps`; real MCUs have few alternatives per option, and forward
  checking prunes early. Measured on an authored 64-pin device with eight takes before merge.
- Device data quality: a wrong alternative wires the board wrong. Options carry evidence, and the build's
  evidence drops to `UNVERIFIED` when an option has none.
- Readers lose the pin names in the script. Mitigation: `result.pins`, the lock and the schematic show them.

## Open Questions

1. Should `take` also cover single-pin functions (an ADC channel, a timer output)? **Recommended:** yes, as
   kind `pin` with one role `io`, in the same change, since the solve is the same.
2. Should the solve prefer alternatives near the consumer on the board? **Recommended:** no: placement is
   not known at solve time, and a layout-driven choice would depend on the board. A later change may propose
   a re-solve after placement, through the lock.
3. Is this change part of 1.0? **Recommended:** no, after 1.0 unless a reference board needs it (research,
   step 7); its design is fixed now so c0248 and c0249 leave room for `options` and `[pins]`.
