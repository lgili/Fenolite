## ADDED Requirements

### Requirement: Signed body volume contract
The model SHALL add optional signed z_min/z_max integer-nm fields to ComponentBody as an authoritative interval in its mounted-face frame, positive outwards from the board surface. Both bounds MUST be present together and ordered. Existing height/standoff remain compatible when the interval is absent; old nonnegative validation MUST still apply then unless projection_unknown explicitly states that preserved source heights are not geometry. A signed interval MUST not be synthesized by silently clamping native heights to zero.

#### Scenario: Surface-spanning volume
- **GIVEN** an independently authored body crosses its mounting plane
- **WHEN** it is serialized and validated
- **THEN** the signed bounds survive and its below-surface extent remains represented

#### Scenario: Legacy invalid body
- **GIVEN** an old body has invalid height/standoff and no signed interval
- **WHEN** model validation runs
- **THEN** the existing invalid-body finding remains

### Requirement: Native body projection and unknown geometry
The native adapter SHALL derive signed bounds and mounted-face orientation only from evidenced body kind, projection and coordinate semantics. Source reader records and embedded/linked model references MUST be retained without unbounded raw-record duplication in extensions. Every component body passed to the adapter MUST remain a ComponentBody; ambiguous or malformed extents SHALL set projection_unknown=true and issue a located finding. When a transform is not evidenced or a model has no known volume, it MUST report unknown geometry and retain the native data rather than drop the body or invent a volume.

#### Scenario: Unproved native projection
- **GIVEN** an authored body record uses a projection form with no documented mapping
- **WHEN** import runs
- **THEN** the native bytes and resource references are retained and volume analysis is explicitly unknown

### Requirement: Board and opposite-face volume analysis
Volume analysis SHALL transform bodies through footprint position, rotation and side, account for known board thickness, holes/cutouts and named allowed penetrations, and distinguish actual intersection from conservative envelope overlap. A through-body penetration MUST not become legal solely because footprints are on opposite faces. Unknown height, thickness or assembly geometry MUST prevent a qualified-clear result for the corresponding check.

#### Scenario: Opposite-face interference
- **GIVEN** known authored volumes on opposite faces intersect through the board plane outside allowed penetrations
- **WHEN** volume analysis runs
- **THEN** the intersection is reported

#### Scenario: Missing thickness
- **GIVEN** an enclosure/body check requires board thickness that was not supplied
- **WHEN** analysis runs
- **THEN** the check is marked incomplete, not passed
