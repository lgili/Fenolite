# c0461: Altium classes of every kind and split planes through KiCad

## Why

The c0450 kit in Altium Designer 24.5 found round-trip losses (S-2200):
- **Classes.** `Classes6` carried only the component classes (`KIND=1`). Public row `-01` (BMS) loses its
  class `Cell`, a class of component classes (kind 5). Row `-04` (NG6011) loses `USBD`, `USBRX_B/C` and
  `USBTX_B/C`. These are xSignal classes (kind 10) in the storage `SignalClasses`, and the xSignals they name
  are `PINPAIR` keys of `Board6` (S-2204). Row `-07` also loses `USB3` (kind 6) and its `DifferentialPairs6`.
- **Classes added.** The way back adds the writer's own sheet classes (`BMS`, `PWR/PWR`, …) beside the
  source's, and KiCad's empty `Default` net class.
- **Split planes.** Row `-01` loses its 8 split planes. Fenolite's conversion to KiCad gives an internal
  plane no zone, and its report has no row for it. KiCad's own import makes each Split Plane polygon an
  unfilled zone of its net on a `power` layer (S-2201).

## What

- The conversion to KiCad carries:
  - every record of `Classes6` that is neither a net class nor a super class, as `Classes6.Kept`. c0450's
    `Classes6.Component` reads as `Classes6.Kept`;
  - the records of `SignalClasses` that are not super classes, as `SignalClasses.Kept`;
  - the `PINPAIR` keys of `Board6`, as `Board6.PinPairs`;
  - `DifferentialPairs6`, whole.
- The conversion back writes them as they were:
  - Classes join `Classes6`. A class whose kind and name the writer already wrote is skipped: a net class
    `CELL` and a kind-5 `Cell` stand side by side.
  - The xSignal classes follow `All xSignals`.
  - The `PINPAIR` keys stand in place of `PINPAIRCOUNT=0`.
  - A differential pair is written only when the document holds both of its nets; otherwise it is an
    `altium-storage` loss.
- Members are written as the source held them. The conversion keeps the board's designators and net names,
  and Altium-saved documents hold members that name nothing (S-2204).
- When the classes are carried, the writer does not write its own sheet classes, and does not write a net
  class without members whose name no rule scope names.
- The conversion to KiCad counts each Split Plane polygon of an internal plane in the chain lost under
  `plane`. It counts the plane itself when the plane holds none. `plane` is a refused kind.
- The kit notes that c0444's BMS pass b hangs Altium (S-2203).

## Not in this change

- Bringing split planes back. KiCad holds them as zones on `power` layers. A rebuild would need three
  things: the import to make those zones, the KiCad target to type plane layers `power`, and the Altium
  writer to write a zone on a `(Multiple Nets)` plane as a Split Plane polygon. This touches the import of
  every board that has planes. Proposed as a follow-up.
- Super classes. The writer writes none, as before (c0035). The kit should check whether Altium makes them
  again.

## Impact

- Code:
  - `convert/altium_storages.py`, `convert/altium_to_kicad.py`, `convert/to_kicad.py` and
    `convert/to_altium.py`;
  - `backends/altium/pcbdoc.py` and `backends/altium/docboard.py`.
- Docs:
  - `docs/formats/altium/pcb-records.md` and `pcb-copper.md`;
  - `docs/altium-kit.md` ("Known hazards");
  - `docs/evidence/sources.md` (S-2200 to S-2204);
  - `CHANGELOG.md`.
- Tests:
  - `tests/unit/convert/test_altium_classes_c0461.py` and `test_altium_storages.py`;
  - `tests/corpus/test_convert_altium_census.py` (rows `-01` and `-02` gain `plane` losses).
