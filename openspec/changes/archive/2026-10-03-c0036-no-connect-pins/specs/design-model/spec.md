## ADDED Requirements

### Requirement: No-connect marks in the circuit model
The circuit layer SHALL record the pins that a design leaves unconnected on purpose as `Circuit.no_connects: tuple[PinRef, ...]`, the last field of `Circuit`, empty by default. A mark is a `PinRef(component_id, pin)` in the form of a net member: `pin` holds a designator as written until a build resolves it, and a pin number afterwards.
- The mark is a fact of the connection, not of the library pin: `Pin` and `PinType` are unchanged, and `Pin.etype == "no_connect"` keeps its meaning (the pin type that the symbol declares).
- A mark has no id and no entity header; `KEYS` and "Identifier derivation" are unchanged.
- `to_model` and the builds MUST store the marks in `PinRef` order without duplicates.
- The change MUST be additive. `canonical` omits the default, so a design without marks gives the `circuit.json` bytes it gave before; a `circuit.json` without the key `no_connects` MUST load with `no_connects == ()`. `SCHEMA_VERSION` stays `"0"`, and `schemas/fenolite.model.v0/circuit.json` MUST be regenerated with `tools/gen_schemas.py`, with `no_connects` as an optional array of pin references.
- `Design.validate()` MUST report, for each mark, with `where` set to `<ref>-<pin>` (or `<component id>-<pin>` when the component is unknown):
  - `model.no-connect-on-net` (error) when a net lists the same `PinRef`, the message naming the net;
  - `model.unknown-component` (error) when no component has the id;
  - `model.unknown-pin` (error) when the component holds pins and none has the number.
- A marked pin MUST NOT be counted as a member of any net: `by_net` and the net findings (`model.single-pin-net`, `model.dangling-net`) are unchanged.
- `docs/design-model.md` MUST describe the field, the two forms of `pin` and the three findings, and `docs/cli-contract.md` MUST list `model.no-connect-on-net` with the model findings.

#### Scenario: Marks survive the canonical round trip
- **GIVEN** a design whose `Circuit.no_connects` holds `PinRef(<U1 id>, "11")` and `PinRef(<U1 id>, "12")`
- **WHEN** it is written with `canonical.dump_dir`, loaded with `canonical.load_dir` and its `circuit.json` validated against the regenerated schema
- **THEN** the loaded marks equal the originals, validation passes, and `circuit.json` holds them under the key `no_connects`

#### Scenario: Circuits without marks are unchanged
- **GIVEN** a `circuit.json` written before this change, and the same design dumped after it
- **WHEN** the old file is loaded and the two texts are compared
- **THEN** loading succeeds with `no_connects == ()`, and the texts are equal byte for byte

#### Scenario: Schema is regenerated
- **WHEN** `uv run python tools/gen_schemas.py --check` and `uv run pytest tests/unit/test_schema_drift.py` run
- **THEN** both pass, and `schemas/fenolite.model.v0/circuit.json` names `no_connects` outside its `required` list

#### Scenario: Marked pin on a net
- **GIVEN** a design whose net `EN` lists `PinRef(<U1 id>, "11")` and whose `Circuit.no_connects` holds the same reference
- **WHEN** `design.validate()` runs
- **THEN** it reports one `model.no-connect-on-net` of severity `error` whose `where` is `U1-11` and whose message names `EN`

#### Scenario: Mark on a pin the component does not hold
- **GIVEN** a component `U1` with the pins `1` and `2`, and a mark `PinRef(<U1 id>, "9")`
- **WHEN** `design.validate()` runs
- **THEN** it reports one `model.unknown-pin` of severity `error` whose `where` is `U1-9`
