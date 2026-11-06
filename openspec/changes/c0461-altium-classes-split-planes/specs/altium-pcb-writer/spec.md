## ADDED Requirements

### Requirement: Kept classes, xSignals and differential pairs

Given carried storages (`PcbDocSpec.kept_storages`), the writer SHALL:
- write the records of `Classes6.Kept` into `Classes6` after its own, leaving out a record whose kind and
  casefolded name a written class holds;
- write the records of `SignalClasses.Kept` after `All xSignals`;
- write the `Board6.PinPairs` keys in `Board6` in place of `PINPAIRCOUNT=0`;
- write the records of `DifferentialPairs6` into that storage.

With `Classes6.Kept` given, the writer SHALL NOT write its own sheet component classes. It SHALL NOT write a
net class without members whose name no rule scope names.

#### Scenario: A class of another kind shares a net class's name

- **GIVEN** a spec with the net class `CELL` and a kept kind-5 class `Cell`
- **WHEN** the document is written
- **THEN** `Classes6` holds both
