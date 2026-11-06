# Tasks: c0461

## 1. Diagnosis

- [x] 1.1 Census of the class kinds, the xSignal keys and the differential pairs of public rows `-01`, `-04`
  and `-07`, and of their round trip before the change (S-2204, S-2200). Proof: the scratch scripts' storage
  diff.
- [x] 1.2 KiCad 10.0.6's import of row `-01`: eight split planes as unfilled zones on `power` layers
  (S-2201).

## 2. Classes

- [x] 2.1 The conversion to KiCad carries `Classes6.Kept`, `SignalClasses.Kept`, `Board6.PinPairs` and
  `DifferentialPairs6`; c0450's carrier reads as `Classes6.Kept`. Proof:
  `uv run pytest tests/unit/convert/test_altium_classes_c0461.py -n 0 -k "carries or c0450"`.
- [x] 2.2 The writer writes them back, merging classes by kind and name. It writes none of its own sheet
  classes or an empty net class that no rule names. It drops a differential pair whose nets are gone. Proof:
  `uv run pytest tests/unit/convert/test_altium_classes_c0461.py tests/unit/convert/test_altium_storages.py -n 0`.
- [x] 2.3 The round trip of rows `-01`, `-04` and `-07` gives every carried record back byte for byte
  (S-2202).

## 3. Planes

- [x] 3.1 The conversion to KiCad counts each Split Plane polygon of a plane in the chain lost under
  `plane`. Proof: `uv run pytest tests/unit/convert/test_altium_classes_c0461.py -n 0 -k plane`.
- [ ] 3.2 `tests/corpus/test_convert_altium_census.py`: rows `-01` (8) and `-02` (5) gain `plane` losses
  (CI: corpus job).

## 4. Evidence and docs

- [x] 4.1 Rows in `pcb-records.md` and `pcb-copper.md`, the kit hazard in `altium-kit.md`, S-2200 to S-2204,
  and CHANGELOG.
- [ ] 4.2 Kit: Altium opens the round trips of rows `-01`, `-04` and `-07` with their classes, xSignals and
  differential pairs. It also checks whether Altium makes the super classes again (asked of
  altium-rounds-2).
