## ADDED Requirements

### Requirement: Conservative LibrePCB legacy metadata and pads
The bounded 0.1 seed SHALL select a unique unlocalized name alongside well-formed unique locale alternatives. It SHALL accept a scalar drill only when zero and unaccompanied by a hole. An absent package_pad MAY use the pad UUID only when declared by the package. Ambiguous names, unknown references and nonzero or malformed legacy drills SHALL remain explicit refusals.

#### Scenario: Localized metadata preserves the default
- **GIVEN** an authored element with one default name and distinct valid localized names
- **WHEN** it is read
- **THEN** its default name is kept and no translated text replaces it

#### Scenario: Ambiguous defaults refuse
- **WHEN** two unlocalized names or duplicate locale identities are present
- **THEN** the element is explicitly refused

#### Scenario: Legacy surface pad binds safely
- **GIVEN** a zero scalar drill and pad UUID declared in its package
- **WHEN** the footprint is seeded
- **THEN** its exact surface pad geometry and package mapping are retained

#### Scenario: Drill information cannot disappear
- **WHEN** a scalar drill is nonzero, malformed or coexists with a hole
- **THEN** the footprint is refused without a fabricated surface pad

#### Scenario: Declared reference prefix remains visible
- **GIVEN** an authored component declaring a valid prefix
- **WHEN** symbol and device records are seeded
- **THEN** both keep that prefix; a missing field alone uses U and an invalid field is refused

### Requirement: Numeric internal function normalization is reversible
The seed converter SHALL normalize an ASCII numeric internal function name to
Pin_<original>, without changing the symbol's visible pin name, pin number,
UUID relationship or electrical mapping. It SHALL refuse identifier collisions
and other invalid names. It SHALL emit library.seed-function-normalized and
record the ordered UUID/original/normalized map in the existing dated provenance
modification_notice and NOTICE. Geometry and evidence SHALL remain unchanged.

#### Scenario: Numeric resistor functions
- **WHEN** authored signals named 1 and 2 map to two symbol pins and package pads
- **THEN** device functions are Pin_1 and Pin_2, symbol names/numbers remain 1/2,
  and replay preserves the same partition and source-bound normalization map

#### Scenario: Legal identifier collision
- **WHEN** signals 1 and Pin_1 would share a normalized identifier
- **THEN** the device is refused explicitly and no device is planned

### Requirement: Signed cardinal pin angles retain exact orientation
The seed converter SHALL canonicalize only exact cardinal pin rotations modulo
360 degrees, preserve a source-bound map in warning and existing provenance
notice, and refuse noncardinal input without rounding.

#### Scenario: Signed cardinal and near-cardinal
- **WHEN** a source pin has rotation -90deg
- **THEN** it emits270deg with the same native orientation and partition
- **WHEN** it has45deg or -90.0001deg
- **THEN** its component and dependent devices are explicitly refused
