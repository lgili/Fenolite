## ADDED Requirements

### Requirement: Altium classes of every kind through KiCad

A conversion of an Altium design to KiCad SHALL carry as board properties:
- every record of `Classes6` that is no net class and no super class (`Classes6.Kept`);
- the records of `SignalClasses` that are no super class (`SignalClasses.Kept`);
- the `PINPAIR` keys of `Board6` (`Board6.PinPairs`);
- `DifferentialPairs6`.

The conversion back SHALL write each carried record as it was, its members unchanged. It SHALL leave out a
class whose kind and name the writer wrote, and a differential pair whose two nets the written document
does not hold. Each such pair SHALL be counted lost under `altium-storage`. A board property
`Classes6.Component` of change c0450 SHALL read as `Classes6.Kept`.

#### Scenario: Classes of every kind survive the round trip

- **GIVEN** an Altium document that holds:
  - a component class;
  - a class of component classes (kind 5), one of whose members names nothing;
  - a net class whose name differs from it in case alone;
  - a class of differential pairs;
  - an xSignal class and its xSignal;
  - a differential pair of two nets of the board
- **WHEN** it is converted to KiCad and back to Altium
- **THEN** each of those records comes back byte for byte, and the xSignal keys stand in `Board6`
- **AND** no `Default` net class and no sheet class of the writer stand beside them

### Requirement: Internal planes on the way to KiCad

A conversion of an Altium design to KiCad SHALL count each Split Plane polygon of an internal plane in the
copper chain lost under `plane`, with a reason. It SHALL count the plane itself when the plane holds none.

#### Scenario: A split plane is counted lost

- **GIVEN** a four-layer Altium document whose second layer is a plane on `GND`, with its one Split Plane
  polygon
- **WHEN** it is converted to KiCad
- **THEN** the report holds one `plane` loss, a refused kind
