# public-presentation Specification

## Purpose
Present released Fenolite workflows through accurate entry points, reproducible product media and a usable first-run path, with explicit evidence limits and reviewed publication material.
## Requirements
### Requirement: Shipped capabilities lead the public page

The README SHALL explain Fenolite through workflows available in 0.5.0, show real product media, give installation and a short first-use path, and link detailed documentation. It SHALL NOT present roadmap work as available or shipped viewer features as future work.

#### Scenario: A first-time visitor tries the viewer

- **WHEN** a visitor follows the quickstart on Python 3.11 or newer
- **THEN** an authored example can be built and opened in the browser without KiCad or Altium, with external-tool prerequisites stated for verification and fabrication workflows

### Requirement: Demonstrations have reproducible provenance

Product captures SHALL come from Fenolite-authored examples or declared public inputs and SHALL record their source and generation recipe. No employer or private project content SHALL enter promotional assets. Images SHALL have alternative text and the social preview SHALL be 1280 by 640 pixels and below 1 MB.

#### Scenario: A maintainer regenerates promotional media

- **WHEN** the capture recipe runs on the release code
- **THEN** it generates actual viewer screenshots and an animation, reports browser errors, and leaves the design inputs unchanged

### Requirement: Launch materials preserve capability limits

Repository settings and bilingual launch copy SHALL describe existing features, retain the experimental status of Altium writing and conversions, and avoid adoption, safety or performance claims without evidence. Publishing SHALL remain a separate reviewed action, with existing release tags and commit history preserved.

#### Scenario: Launch draft is reviewed

- **WHEN** the maintainer opens the launch checklist
- **THEN** exact description, topics, release text, announcements and assets are available along with a record of validation and remaining publication steps
