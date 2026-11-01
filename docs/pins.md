# Pin assignment at the interface level

Change c0257. A microcontroller usually offers each peripheral on several pin sets. A Fenolite script can
name the function instead of the pins: the device record *offers* interface options, the script *takes*
one interface from a part, and `fenolite build` chooses the pins, shows the choice and keeps it in the
design lock. The concept (a device offers options, a consumer requires one, a solver picks) is taken from
JITX's public documentation, paraphrased; no code, syntax or schema of it is used. Unlike JITX, the pins are
chosen at build time and recorded, never left as hidden state until routing.

## Options in a device record

A device record (`docs/devices.md`) may hold `[[options]]` tables:

```toml
[[options]]
kind = "i2c"
name = "I2C1"
alternatives = [
  { scl = "PB6", sda = "PB7" },
  { scl = "PB8", sda = "PB9" },
]
```

- `kind` is one of `i2c` (roles `scl`, `sda`), `spi` (`miso`, `mosi`, `sck`), `uart` (`rx`, `tx`), `usb2`
  (`dn`, `dp`), `diff_pair` (`n`, `p`) and `pin` (`io`: a single-pin function, such as an ADC channel or a
  timer output).
- `name` is unique per device and kind. `alternatives` keep their file order (index 0, 1, ...); each maps
  exactly the roles of the kind to function names of the device.
- An option inherits the record's evidence label; an `evidence` key may lower it. A build that takes an
  `UNVERIFIED` option says so in its evidence.
- An unknown pin, a missing or extra role, one pin for two roles, two equal alternatives and an option
  declared twice are refused with `FEN-3004`, naming the device, the option and the pin.

## Taking an interface

```python
mcu = design.part(name="mcu", device="Example:MCU_QFN32")
sen = design.part(name="sen", device="Example:SENSOR_I2C")
i2c = mcu.take(I2C)  # one of the device's i2c alternatives, chosen at build
connect(i2c, sen.i2c)  # interface to interface (c0252)
dbg = mcu.take(UART, option="UART2", name="debug")
gps = mcu.take(UART, pins={"tx": "PB3"})  # only the alternatives with tx = PB3
adc = mcu.take("pin", option="ADC")  # a single-pin function: net-like, connect(net, adc)
mcu.unused_no_connect()  # applied after the solve, on the pins no take was given
```

- `part.take(kind, *, name=None, option=None, pins=None)` takes `I2C`, `SPI`, `UART`, `USB2`, `DiffPair` or
  a kind text. It returns a `TakenInterface`, a port of the part whose role nets exist at once, named
  `<part path>/<take key>/<role>` unless joined to a named net; `connect`, `pull_up` and the other helpers
  work before the solve. Being a port, a taken UART crosses `tx` and `rx` with another UART port.
- The take key is `name`, else `<kind>#<n>` with `n` the index of the take among the takes of that kind on
  that part, in script order. The lock key is `<part path>/<take key>`: `mcu/i2c#0`, `buck/U1/debug`.
- `option` keeps one option; `pins` (role → function name or pin handle) keeps the alternatives that match.
- A part without a device, a device without an option of the kind, an unknown role and a name taken twice
  raise `DslError` at the call. An unknown option and `pins` that match nothing are findings of the build.
- `fenolite build` solves the takes against the lock (and `fenolite sync` against the lock beside the
  script); `to_model` alone solves takes never applied against an empty lock, as it assigns refs.

## The solve

`fenolite.lens.pins.solve` is a pure function of the takes, the device records, the fixed pins and the lock:

1. Every function connected by hand, or marked no-connect, before the solve is unavailable.
2. A take whose lock entry is still valid (option, alternative and pins unchanged, within the take's
   filters, no pin fixed or already taken) keeps it: source `locked`, or `pinned` when the take gives `pins`.
3. The other takes, ordered by (part path, take key), get their candidates in the order (option name,
   alternative index); a depth-first search with forward checking assigns one candidate per take so that
   no pin serves two takes. The first complete assignment wins: source `solved` (`pinned` with `pins`).
4. No assignment: `pins.unsatisfiable`, naming the smallest conflicting set of takes (found by dropping
   takes one at a time in reverse order while the rest stays unsatisfiable) and the pins they compete for.
5. More than 100 000 candidate trials: `pins.search-limit`.

`--seed` does not enter the solve: a build is identical under any seed and on every platform
(`H-G-PIN-SOLVE-DETERMINISTIC`). A locked choice never moves when an unrelated take is added; one that
became invalid is solved again with `pins.lock-stale`.

## Shown in the result, recorded in the lock

`result.pins` (dry run and confirmed run alike), sorted by key:

```json
"pins": [
  {"key": "mcu/i2c#0", "kind": "i2c", "option": "I2C1", "alternative": 1,
   "pins": {"scl": "PB8", "sda": "PB9"}, "source": "solved"}
]
```

The lock `<script stem>.lock` (`docs/dsl.md`, "Reference designators and the design lock") records each
choice; its write is planned like every other file, so the reviewer sees the `[pins]` diff before
`--confirm --plan`:

```toml
[pins."mcu/i2c#0"]
kind = "i2c"
option = "I2C1"
alternative = 1
pins = { scl = "PB8", sda = "PB9" }
choice = "I2C1 on PB8/PB9"
```

`choice` is human text, ignored when read and written again from the other keys. A design with a take
gets a lock even when every part has an explicit ref. The changes of the section are listed in
`result.lock.changes` with the reasons `solved`, `stale` and `dropped`; an entry whose take is gone is
dropped with `pins.lock-dropped`. Under `--frozen` any new, changed or dropped choice is refused with
`FEN-7004` and one `lock.changed` naming the take, and nothing is written.

## Codes

| code | severity | when |
|---|---|---|
| `pins.unsatisfiable` | error | no assignment exists; the message names the smallest conflicting takes and their pins |
| `pins.option-unknown` | error | `option=` names no option of that kind on the device |
| `pins.pinned-conflict` | error | `pins=` matches no alternative, or names a pin fixed by hand |
| `pins.search-limit` | error | the search tried more than 100 000 candidates |
| `pins.lock-stale` | warning | a locked choice is no longer valid and was solved again |
| `pins.unused-take` | warning | a take whose nets reach no other pin |
| `pins.lock-dropped` | info | a lock entry whose take no longer exists was removed |

An error stops the build's writes (exit 5). `fenolite explain <code>` describes each.

## Not done

No pin swap during routing and no write-back from the board (a manual swap goes through change c0250),
no general constraint solver, no preference for pins near the consumer (placement is not known at solve
time), no alternate-function register values and no firmware output. Electrical compatibility of the
chosen pins is change c0253's.

`examples/pins/` builds an MCU, an I2C sensor and a debug header this way.
