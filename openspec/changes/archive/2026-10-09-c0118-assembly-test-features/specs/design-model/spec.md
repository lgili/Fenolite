## ADDED Requirements

### Requirement: Assembly and test pad properties in the model
`Pad` SHALL carry `fab_property: PadFabProperty | None = None`, where `PadFabProperty` (`fenolite.model.board`) is `Literal["bga", "fiducial_global", "fiducial_local", "test_point", "heatsink", "castellated", "mechanical", "press_fit"]`: the fabrication mark of the pad, `None` when it has none.
- The field MUST be the last field of `Pad`, so that every existing construction keeps its meaning.
- The canonical form MUST omit it when it is `None`, so a document without a mark keeps the bytes it has today and a document of an earlier release loads as it is. The other direction does not hold, and MUST be said in `docs/design-model.md` and in the changelog: releases 0.2.x and 0.3.0 cannot read a model document that carries the key `fab_property`, because their reader refuses an unknown key. `schemas/fenolite.model.v0/` MUST list it as an optional property of a pad, for board pads and library pads alike.
- The model MUST NOT check the mark against the pad's kind or layers: the DSL refuses what it can tell at the call ("Assembly and test properties on authored pads"), and KiCad's DRC judges the rest.
- `docs/design-model.md` MUST list the eight values and say that a mark is what KiCad calls the fabrication property of a pad.

#### Scenario: No mark by default
- **WHEN** `Pad(id=..., number="1", shape="rect", size=..., position=...)` is constructed
- **THEN** `fab_property is None`, and the canonical texts of a design that holds the pad have no `fab_property` key

#### Scenario: A test-point pad in board.json
- **GIVEN** a design whose footprint instance holds a pad with `fab_property="test_point"`
- **WHEN** its canonical texts are dumped and loaded again
- **THEN** `board.json` holds `"fab_property": "test_point"` for that pad, and the loaded design equals the first
