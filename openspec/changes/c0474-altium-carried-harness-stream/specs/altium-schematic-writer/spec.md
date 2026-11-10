# Delta for altium-schematic-writer

## MODIFIED Requirements

### Requirement: Harness records of a written document
`fenolite.backends.altium.binary.write_schdoc_binary` SHALL write the harness records of a plan (the
blocks of `plan.harnesses`, the direct-join lines of `plan.lines` and `plan.polylines`, and the records
carried from a source `Additional` stream in `plan.carried_additional`) into the document's `Additional`
stream, after its own header record, and SHALL NOT write them into the `FileHeader` stream. A carried
child's `OWNERINDEX` SHALL name its connector's index in the Additional stream (0-based after the
header), shifted behind the records `schdoc.additional_records` builds itself, and SHALL be omitted when
that index is 0. The ASCII form (`schdoc.write_schdoc`) SHALL refuse a plan with carried Additional
records, as it refuses drawn harnesses.

#### Scenario: Carried harness records return to the Additional stream
- **GIVEN** a drawn sheet whose opaque items hold a harness connector subtree (root `RECORD=215` with
  `RECORD=216` and `RECORD=217` children naming `OWNERINDEX=@0`), a second connector with one entry, and
  a signal harness line (`RECORD=218`)
- **WHEN** the project is built with `build --target altium` in the binary form
- **THEN** the written document's `FileHeader` stream holds no record of 215–218, its `Additional`
  stream holds them in order `215, 216, 217, 215, 216, 218`, the entry of the first connector names no
  owner, the entry of the second names `OWNERINDEX=3`, and the document re-reads without an
  `altium.sch.orphan-record` warning.
