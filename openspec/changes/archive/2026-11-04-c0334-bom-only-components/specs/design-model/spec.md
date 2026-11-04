## ADDED Requirements

### Requirement: Explicit BOM-only components
A canonical component MAY be explicitly BOM-only without a board footprint instance. It SHALL retain purchasing identity, reference, value, properties, DNP state and source instance BOM inclusion. The neutral model BOM SHALL include it. The default false marker SHALL preserve existing canonical bytes. This narrow path SHALL reject pinned, power, board-only and physical-placement contradictions instead of hiding them in opaque graphics.

#### Scenario: Purchasing accessory without a footprint instance
- **GIVEN** an authored pinless, non-power source accessory included in the BOM and excluded from the board
- **WHEN** it is strictly imported and rebuilt
- **THEN** the canonical model and neutral/native BOM retain the same item, the electrical pin partition is unchanged, and no physical footprint is invented

#### Scenario: A purchasing item disappears
- **WHEN** the accessory is removed or its BOM inclusion changes in one side of a comparison
- **THEN** the applicable canonical/BOM guard reports the change and cannot claim equivalent purchasing content

#### Scenario: Electrical lookalike
- **WHEN** a source instance has pins, a power role or contradictory physical flags
- **THEN** this narrow BOM-only path refuses it before staging and cannot treat it as an opaque graphic

#### Scenario: Incompatible flags between purchasing units
- **GIVEN** pinless units of one source reference have board or DNP flags that one canonical component cannot preserve
- **WHEN** strict import or source comparison reads them
- **THEN** a located existing input error refuses before a write plan, even with loss acceptance
- **AND** equal flags and independently preserved both-excluded opaque units retain their existing behavior
