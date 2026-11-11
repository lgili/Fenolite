## ADDED Requirements

### Requirement: Native bodies are kept through KiCad
A conversion that goes from Altium through KiCad and back to Altium SHALL write the source's extruded,
cylinder and sphere bodies as the source's records (change c0484).
- A conversion to KiCad MUST carry, in the board property `Fenolite.Altium.Bodies`, per generated model whose
  every body is an extruded body, a cylinder or a sphere of the source document:
  - the SHA-256 of the model's bytes and its footprint's place, turn and side in KiCad;
  - those bodies' records as read, each with its shape-based twin.
- The Altium writer MUST write the carried records, with the written component index, in place of the
  generated model's body when the footprint holds the same model bytes, unmoved in its frame, at the same
  place, turn and side. The generated model MUST then not be embedded.
- Otherwise the writer MUST write the generated model as before.
- A kept model MUST NOT be counted as a `model` change.
- The match MUST NOT depend on the footprint's uuid, so a script's build keeps the bodies too.

#### Scenario: The source's bodies come back
- **GIVEN** an authored Altium document with extruded, cylinder and sphere bodies, each on its own component
- **WHEN** it is converted to KiCad and back to Altium
- **THEN** each of those body records equals the source's except for its component index
- **AND** the `Models` storage holds no generated model
- **AND** the report counts no `model` change

#### Scenario: A moved footprint takes the model
- **GIVEN** the same conversion to KiCad, with one footprint moved by 1 mm
- **WHEN** the board is converted back to Altium
- **THEN** that footprint's bodies are written as its generated model body
- **AND** every other footprint keeps its source records
