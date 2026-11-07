## ADDED Requirements

### Requirement: Carried board settings

Given a kept storage `Board6.Settings` (`PcbDocSpec.kept_storages`), the writer SHALL merge its fields into
the `Board6` record: a key it writes once takes the carried value, a key it does not write is written after
the carried anchor, and an owned key or a key the record holds twice keeps the writer's value. Without the
storage the record is unchanged.

The writer SHALL name a mechanical layer after the carried name when its id is in `PcbDocSpec.named_layers`
or no written primitive lies on it.

#### Scenario: The writer's owned keys win

- **GIVEN** a kept `Board6.Settings` that holds `ORIGINX`, `DISPLAYUNIT=0` and `LOOKAT.X`
- **WHEN** the document is written
- **THEN** `DISPLAYUNIT` is 0 and `ORIGINX` and `LOOKAT.X` are the writer's
