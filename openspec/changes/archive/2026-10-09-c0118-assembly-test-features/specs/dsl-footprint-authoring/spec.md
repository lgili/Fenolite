## ADDED Requirements

### Requirement: Assembly and test properties on authored pads
`Footprint.pad(…, fab_property=None)` SHALL set the mark of an authored pad: `None`, or a value of `fenolite.model.board.PadFabProperty`, stored as `Pad.fab_property` of the definition and written by the footprint writer ("Assembly and test pad properties on boards and footprints").
- Any other value MUST raise `DslError` naming `fab_property`.
- `castellated` and `mechanical` MUST be refused with `DslError` on a pad whose kind is not `thru_hole`: KiCad's DRC reports such a pad as `padstack` (`H-K-PAD-FABPROP`).
- A pad declared without the keyword MUST be unchanged, and the bytes of its footprint file MUST NOT change.

#### Scenario: A marked BGA ball
- **GIVEN** `fp = Footprint("Local", "Ball", kind="smd")`
- **WHEN** `fp.pad("A1", at=(mm(0), mm(0)), size=(mm(0.3), mm(0.3)), shape="circle", fab_property="bga")` is called and the footprint is written for target 10
- **THEN** the definition's pad has `fab_property == "bga"` and the written pad holds `(property pad_prop_bga)`

#### Scenario: Refused marks
- **GIVEN** an SMD footprint
- **WHEN** a pad is declared with `fab_property="castellated"`, and another with `fab_property="fiducial"`
- **THEN** both raise `DslError`, the first naming `castellated` and `thru_hole`, the second naming `fab_property`
