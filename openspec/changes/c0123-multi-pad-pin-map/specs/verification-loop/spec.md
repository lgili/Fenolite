## ADDED Requirements

### Requirement: Assignment comparison names every pad of a pin
`checks.assignment_compare.model_netlist(model)` SHALL give one `PadAssignment` per pad of each pin, where the pads of a pin are `Component.pads_of(pin)`: for a `PinRef` member of a net, each pad with the net's id as label; for every other pin of a component, its pad with `NO_NET`, or, for a pin of several pads, each pad with one label of the pin's own (`assignment_compare.bonded_label`), because the pads of one pin are joined inside the part and a board that names their net (`unconnected-(…)` or `Net-(…)`) has them as one block. This says, for a pin of several pads, what the bullet "Sources" of "Assignment compare stage" says for a pin of one.
- An element MUST be listed once: a pad that a net member already named is not listed again on `NO_NET`.
- For a model whose pins have one pad each the result MUST be the list, in the order, that the function gave before this requirement.
- The function MUST NOT build a mapping of one pad per pin from `pin_pad_map`.

#### Scenario: Pin of two pads
- **GIVEN** a model whose component `U1` has the pins `1` and `3`, `pin_pad_map == (("3", "3"), ("3", "EP"))`, and whose net `GND` lists pin `3`
- **WHEN** `uv run pytest tests/unit/checks/test_assignment_compare.py -k several` calls `model_netlist`
- **THEN** the elements `U1-3` and `U1-EP` are on `GND`, `U1-1` is on no net, and a board whose pads `3` and `EP` of `U1` carry `GND` compares without a difference and without an element on one side only

#### Scenario: Open pin of two pads
- **GIVEN** the same component with pin `3` on no net
- **WHEN** `model_netlist` runs
- **THEN** `U1-3` and `U1-EP` are listed with one label that is neither `NO_NET` nor a net id, and a board that holds the two pads on one net of any name compares without a difference

#### Scenario: One pad per pin
- **GIVEN** the model of "Mapped pins are named by their pads" ("Assignment compare stage")
- **WHEN** `model_netlist` runs
- **THEN** the assignments equal, in order, those the function returned before this change (a list written in the test)
