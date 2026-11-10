## ADDED Requirements

### Requirement: Copper of a component keeps its net

The import SHALL give each graphic of a footprint read from a component's track, arc, fill or region on a
signal layer the id of that primitive's net in `net_id`, beside its name in the pair `net`. A primitive
without a net SHALL give a graphic without `net_id`.

#### Scenario: A component region of a net

- **GIVEN** a document whose component owns a region of net `5V` on its top layer
- **WHEN** the document is read
- **THEN** the footprint holds a filled graphic on `F.Cu` whose `net_id` is the id of `5V`
