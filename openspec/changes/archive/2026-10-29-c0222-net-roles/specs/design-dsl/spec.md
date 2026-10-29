## ADDED Requirements

### Requirement: Net roles in the DSL
`Design` SHALL offer `net_role(net, kind, *, current=None, voltage=None, sensitive=False)`, `hot_loop(name, pads)`, `kelvin(name, element, receiver, force=())`, `gate_loop(name, drive, gate, source, ret, resistor=())`, `role_limits(*, net=None, kind=None, **limits)` and `part_class(part, cls, terminals=None)`. The calls MUST record plain data, which the build resolves after placement and stores as `declared`. A bad kind, key, unit or pad, or a name used twice, MUST raise `DslError`.

#### Scenario: Declared roles are built
- **GIVEN** the script `examples/roles/half_bridge/good.py`, which declares the bus with `current=amp(20)` and `voltage=volt(400)`
- **WHEN** `uv run pytest tests/unit/dsl/test_roles.py -k build` builds it
- **THEN** `.fenolite/rules.json` holds the bus role with `milliamps` 20000, `working_mv` 400000 and source `declared`

#### Scenario: A pad of another part is refused
- **WHEN** a script calls `design.kelvin("i", element=(r1.pad(1), r2.pad(2)), receiver=(u1.pad("IN+"), u1.pad("IN-")))`
- **THEN** `DslError` names `kelvin() 'i'` and says that both element pads must belong to one part
