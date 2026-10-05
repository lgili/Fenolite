## MODIFIED Requirements

### Requirement: Offline Fenolite-authored standard catalog
Fenolite SHALL ship a deterministic, offline catalog of Fenolite-authored generic schematic symbols
and reusable standard-package footprints under the reserved `Fenolite:` namespace. The catalog
MUST incrementally cover the common component families and standard package styles listed in its
coverage matrix, including passives, discrete and optoelectronic semiconductors, protection,
power/control ICs and electromechanical interfaces. Every entry MUST have a stable lib id, kind,
category, summary, evidence level and public source ids for factual electrical or physical claims.
Definitions MUST NOT be copied or vendored from another CAD library or private project. The catalog
MUST NOT claim complete coverage of commercial parts, choose a package for a part, or assert
manufacturing qualification. Non-standard or proprietary geometry remains project-authored unless
it is separately specified as a reusable generic package with public evidence.

#### Scenario: Catalog covers the published family matrix
- **WHEN** the catalog coverage check runs
- **THEN** every family and standard package style marked in the current coverage matrix has at
  least one discoverable, Fenolite-authored entry or an explicit documented reason it is not
  representable by the current model
- **AND** no private project BOM row or third-party CAD definition is required to build those entries

#### Scenario: A custom package stays project-authored
- **GIVEN** a component package with a non-standard mechanical interface or insufficient public
  evidence
- **WHEN** the catalog coverage is extended
- **THEN** the generic catalog does not claim that geometry as a standard package
- **AND** the user can define it through the project-authored symbol and footprint APIs

#### Scenario: Generic symbols do not select a package
- **GIVEN** a part assigned to a generic catalog symbol that supports multiple package styles
- **WHEN** the design is built
- **THEN** package selection remains explicit on the part and no footprint is silently inferred

### Requirement: Source and evidence labels
Each factual symbol pin map, polarity claim or physical package dimension in the catalog SHALL cite
one or more public sources registered in `docs/evidence/sources.md`. A land pattern not explicitly
specified by those sources MUST be labelled `INFERRED` in catalog metadata and the definition
description. A writer/readback check MUST NOT upgrade an inferred dimension's evidence level.
Public sources MUST be sufficient for each claim; private board data and copied CAD library content
MUST NOT be used as provenance.

#### Scenario: Every family pack has independent provenance
- **WHEN** the catalog source check runs
- **THEN** it fails for an unregistered source id, a factual claim without supporting provenance,
  or an inferred footprint without an inferred-land description
- **AND** it rejects catalog provenance that points to a private board artifact or third-party CAD
  library file

### Requirement: Physically separated and oriented footprint lands
Every shipped surface-mount footprint SHALL use land shapes, dimensions, pitch, orientation and
numbering traceable to an official package or land-pattern drawing. Pads with different numbers
MUST have positive copper clearance. A footprint courtyard MUST contain its body and all pads, and
silkscreen graphics MUST NOT cross copper. Multiple shapes carrying one pad number MAY form one
documented terminal, provided their copper remains connected. Where an official example uses a
rounded rectangle but the current model provides only a rectangle, the approximation SHALL remain
labelled `INFERRED`.

#### Scenario: A package is serialized and checked
- **WHEN** any built-in footprint is serialized and read back
- **THEN** its pad shapes, positions, sizes, numbers and graphic layers match the source-backed
  definition
- **AND** no two pads with different numbers overlap
- **AND** its courtyard contains every pad and the body outline

#### Scenario: Multi-sided packages follow the manufacturer's top view
- **WHEN** the 32-lead LQFP or a five-lead SOT package is inspected from the top
- **THEN** pad numbers progress around the body in the order shown by its cited official drawing
- **AND** pads on perpendicular sides have perpendicular long axes

### Requirement: Connected, legible schematic symbol drawings
Every built-in schematic symbol SHALL have pin stems oriented from their wire-attachment points
toward and into a visible body or terminal graphic. Generic symbols SHALL use consistent line
weight, aligned pin positions, readable functional labels and recognizable electrical motifs without
copying a third-party CAD definition. Polarity and amplifier input/supply labels SHALL match the
graphic. Families without a device-specific pinout SHALL remain explicitly conceptual.

#### Scenario: A user places any catalog symbol
- **WHEN** the symbol is serialized and read back
- **THEN** each pin direction and stem reaches a visible body or terminal graphic
- **AND** pin numbers, names, graphic order and visibility settings survive the round trip
- **AND** diode cathodes, polarized capacitor positives and amplifier input/supply signs agree with
  the drawn marks

#### Scenario: Selected resistor and Zener drawings
- **WHEN** the generic resistor and Zener diode are rendered from catalog definitions
- **THEN** the resistor has a continuous zigzag between its pin stems instead of a rectangle
- **AND** the Zener cathode has one continuous bent stroke with no full-height straight stroke
  under the bends

#### Scenario: Optocoupler, header and polarized capacitor drawing review
- **WHEN** these generic symbols are rendered from catalog definitions
- **THEN** the optocoupler contains a recognizable LED, two optical arrows and a separate
  phototransistor, with its A/K/C/E pin stems joined to the appropriate graphic
- **AND** each two-, three- or four-circuit header contact is square and has exactly one external
  pin stem, with no circular contact graphic
- **AND** only the polarized and electrolytic capacitor variants have one heavier plate opposite
  the marked positive plate

#### Scenario: Complete visual family review
- **WHEN** all 26 catalog symbols are rendered on one gallery sheet
- **THEN** passive and protection contours remain readable at normal schematic scale and their
  pin stems meet the intended body graphics
- **AND** multi-circuit connectors show grouped housings, separate square contacts and one
  external stem per circuit; the single terminal has a square socket form
- **AND** conceptual IC blocks carry readable functional pin names without interior decorative
  signals, while amplifier supply stems meet their triangular bodies
- **AND** prior explicit preferences for zigzag resistance, Zener cathode, optocoupler internals
  and weighted polarized capacitor plate remain intact

#### Scenario: Distinct coupled choke, discharge tube and dual LED symbols
- **WHEN** the three newly covered generic families are discovered and rendered
- **THEN** the common-mode choke has two winding paths that do not electrically join, with four
  conceptual terminals and a separate magnetic-core cue
- **AND** the gas discharge tube has two opposing electrodes with a visible insulating gap and
  two non-polar terminals
- **AND** the dual LED has two anode branches, one shared cathode and a clear common-cathode
  description; it does not imply a physical package pinout or select a footprint

### Requirement: Published 100-variant footprint target
Fenolite SHALL publish and ultimately ship exactly 100 distinct, discoverable footprint variants
from the c0076 target inventory. The inventory SHALL disclose its public-board sampling method,
snapshot, package-family normalization and limits. An entry SHALL NOT be described as a measured
worldwide top-100 package. Existing definitions count toward the total only once. An unresolved
variant slot is a plan, not a usable footprint. Each shipped definition MUST satisfy the source,
evidence, geometry, serialization, clearance and explicit-assignment requirements above.

#### Scenario: The inventory is audited before implementation
- **WHEN** the target inventory is reviewed
- **THEN** it contains exactly 100 unique slots, identifies the 14 existing catalog entries and
  clearly marks every remaining slot as unimplemented
- **AND** the selection method and public sources can be reproduced without private project data

#### Scenario: A provisional slot becomes a catalog entry
- **WHEN** a package variant is implemented
- **THEN** its final ID identifies the sourced body, pitch, pin count and special pad features
  needed to distinguish it from other variants
- **AND** its registered official drawing supports numbering and land geometry, or any authored
  approximation is visibly marked `INFERRED`
- **AND** focused geometry, readback, discovery and offline-build checks pass before the slot is
  marked implemented

#### Scenario: The 100-variant target is complete
- **WHEN** c0076 is proposed for merge
- **THEN** all 100 inventory slots resolve to distinct built-in footprints with the required
  evidence, previews and checks
- **AND** aliases sharing identical lands do not inflate the count
