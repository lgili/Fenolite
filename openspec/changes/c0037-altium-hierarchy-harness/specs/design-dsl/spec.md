## ADDED Requirements

### Requirement: Harness interfaces in the DSL
`fenolite.dsl.Harness(name, members)` SHALL record a named group of nets with different names as a model `Interface` of kind `harness`, without any model delta. This requirement extends "Interfaces in the DSL", whose rules hold for it.
- `Harness` MUST be a subclass of `Interface` defined in `fenolite.dsl.interfaces` and re-exported by `fenolite.dsl`. `name` is the harness type name and has no default. `members` maps an entry name to a `Net`, for example `Harness("SPI", {"MOSI": mosi, "MISO": miso, "SCK": sck})`.
- An empty `members`, an entry name that is not a non-empty string, or a member that is not a `Net` MUST raise `DslError`.
- `to_model` MUST give `Interface(kind="harness", name=<name>, members={<entry>: <net id>, …})` with the id `derived_id("itf", "dsl", "interface:harness:<name>")`. Member nets join the design.
- The order of the entries carries no meaning: a backend that needs one MUST sort the entry names.
- A KiCad build MUST keep a harness interface in `.fenolite/` and MUST give no issue for it; the written KiCad files MUST NOT depend on it. The Altium build lowers it (`altium-build`, "Module sheets in an Altium build").

#### Scenario: Harness becomes an interface
- **GIVEN** `Harness("SPI", {"MOSI": mosi, "MISO": miso, "SCK": sck})` on the nets `SPI_MOSI`, `SPI_MISO` and `SPI_SCK`, added to a design
- **WHEN** `to_model` runs
- **THEN** the model holds an `Interface` named `SPI` with kind `harness` and the members `MOSI`, `MISO` and `SCK` equal to the ids of the three nets, and the three nets are in the circuit

#### Scenario: Empty harness refused
- **WHEN** `Harness("SPI", {})` is called
- **THEN** it raises `DslError` naming `SPI`

#### Scenario: KiCad build ignores the harness
- **GIVEN** `examples/blink_2layer/design.py` and a variant that adds `Harness("LED", {"DRV": led_drv, "A": led_a})`
- **WHEN** both are built for KiCad with `--dry-run --json`
- **THEN** the variant's `issues` equal the example's, and the planned KiCad files outside `.fenolite/` are equal byte for byte

#### Scenario: Export
- **WHEN** `uv run python -c "from fenolite.dsl import Harness; print(Harness.__module__)"` runs
- **THEN** it prints `fenolite.dsl.interfaces`
