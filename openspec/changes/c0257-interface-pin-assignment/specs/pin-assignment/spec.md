## ADDED Requirements

### Requirement: Interface options in device records
A device record of the catalog SHALL accept `options`: each with `kind` (an interface kind), `name` (unique per device and kind) and `alternatives`, an ordered list whose entries map exactly the roles of the kind to pin names of the device. The loader MUST refuse an unknown pin, a missing or extra role and two equal alternatives with the catalog's malformed-record code.

#### Scenario: A malformed option
- **GIVEN** an authored device whose `I2C1` alternative names the pin `PB99`, which the device lacks
- **WHEN** `uv run pytest tests/unit/catalog/test_options.py -k unknown_pin` loads it
- **THEN** the load is refused naming the device, `I2C1` and `PB99`

### Requirement: Taking an interface in the DSL
`Part.take(kind, *, name=None, option=None, pins=None)` SHALL return a `TakenInterface` of that kind whose role nets exist at once and whose part pins are chosen at build time. Its take key MUST be `name`, else `<kind>#<n>` with `n` its index among takes of that kind on that part in script order. A part without a device, or whose device has no option of the kind, MUST raise `DslError` at the call.

#### Scenario: Take and connect
- **GIVEN** the authored device `Example:MCU_QFN32` of `examples/pins/` and a sensor with an `i2c` interface
- **WHEN** `uv run pytest tests/unit/dsl/test_take.py -k connect` runs `i2c = mcu.take(I2C); connect(i2c, sen.i2c)`
- **THEN** the take key is `i2c#0`, the sensor's SDA and SCL pins are on the take's role nets, and no MCU pin is connected yet

### Requirement: Deterministic pin solve
The build SHALL assign each take one alternative so that no pin serves two takes, a pin connected or marked no-connect by hand, or a fixed pin. Valid locked choices MUST be kept first; the others MUST be searched in the order part path, take key, option name, alternative index, and the first complete assignment MUST win. The result MUST NOT depend on `--seed` or the platform.

#### Scenario: Second alternative when the first is taken
- **GIVEN** a script that connects `PB7` by hand and takes one `I2C` from a device whose `I2C1` offers `PB6/PB7` and `PB8/PB9`
- **WHEN** `uv run pytest tests/unit/lens/test_pins.py -k second` builds it with `--dry-run` under seeds 1, 2 and 3
- **THEN** each `result.pins` gives `I2C1` alternative 1 on `PB8/PB9` with source `solved`, and the three results are equal

### Requirement: Pin choices in the build result
`fenolite build` SHALL return `result.pins`, sorted by key, one object per take with `key` (`<part path>/<take key>`), `kind`, `option`, `alternative`, `pins` (role to pin name) and `source` (`solved`, `locked` or `pinned`), on a dry run and on a confirmed run alike.

#### Scenario: Reviewed before writing
- **WHEN** `uv run pytest tests/unit/lens/test_pins.py -k plan` builds `examples/pins/design.py` with `--dry-run`
- **THEN** `result.pins` holds `mcu/i2c#0` and `mcu/debug`, and `result.plan` holds the planned write of `<script stem>.lock`

### Requirement: Pin choices in the lock
A confirmed build SHALL write each choice to the `[pins."<key>"]` table of `<script stem>.lock` with `kind`, `option`, `alternative`, `pins` and a human `choice` text that readers ignore. A later build MUST keep a valid locked choice, MUST solve an invalid one again with `pins.lock-stale`, and MUST drop an entry whose take no longer exists with `pins.lock-dropped`.

#### Scenario: A new take does not move a locked one
- **GIVEN** `examples/pins/` built with `--confirm`, then a second `I2C` take added to the script
- **WHEN** `uv run pytest tests/unit/lens/test_pins.py -k locked` builds again with `--dry-run`
- **THEN** `mcu/i2c#0` keeps its alternative with source `locked`, and the new take gets the remaining one

### Requirement: Frozen pin choices
With `--frozen` (c0249), a build whose solve would change, add or drop a `[pins]` entry SHALL be refused with the frozen-lock error of c0249, and nothing MUST be written.

#### Scenario: Frozen refusal
- **GIVEN** `examples/pins/` built with `--confirm`, then the hand connection of the locked pin `PB9`
- **WHEN** it is built with `--frozen --dry-run`
- **THEN** the build is refused with c0249's frozen-lock error naming `mcu/i2c#0`, and no plan is returned

### Requirement: Unsatisfiable takes are explained
When no assignment exists, the build SHALL report `pins.unsatisfiable` (error, exit 5) naming the smallest conflicting set of takes, found by dropping takes in reverse order while the rest stays unsatisfiable, and the pins they compete for. More than `max_steps` (default 100 000) candidate trials MUST give `pins.search-limit` (error).

#### Scenario: Three I2C takes on two alternatives
- **GIVEN** a device with one `I2C1` option of two alternatives sharing no pin, and a script with three `I2C` takes
- **WHEN** `uv run pytest tests/unit/lens/test_pins.py -k unsatisfiable` builds it
- **THEN** the exit code is 5 and one `pins.unsatisfiable` names the three takes and the four pins

### Requirement: Pin assignment issue codes
The build SHALL report the pin findings only with the codes of `lens.pins.PIN_ISSUE_CODES`, each with a table in `explain.toml` and a line in `docs/cli-contract.md`.

| code | severity |
|---|---|
| `pins.unsatisfiable` | error |
| `pins.option-unknown` | error |
| `pins.pinned-conflict` | error |
| `pins.search-limit` | error |
| `pins.lock-stale` | warning |
| `pins.unused-take` | warning |
| `pins.lock-dropped` | info |

#### Scenario: Closed set
- **WHEN** `uv run pytest tests/unit/lens/test_pins.py -k codes` collects every `pins.*` literal under `src/fenolite/`
- **THEN** each is a key of `PIN_ISSUE_CODES` with the severity of this table, and `fenolite explain` knows each
