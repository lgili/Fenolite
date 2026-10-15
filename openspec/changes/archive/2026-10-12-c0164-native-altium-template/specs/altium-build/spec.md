## ADDED Requirements

### Requirement: Native sheet template in an Altium build
`fenolite build` SHALL accept `--altium-template FILE.SchDot` only with an Altium target and binary
schematic output. It SHALL apply the native template to every generated sheet without conversion to
the neutral drawing-sheet model and copy its bytes unchanged into `templates/sheet.SchDot`.
The build SHALL preserve template page settings, font entries, graphic coordinates, special strings,
embedded storage and opaque properties, maintain template ownership, and rebase generated ownership
and font references. Generated sheet parameter values SHALL override matching template defaults.
The option SHALL conflict with a script's neutral drawing sheet. Unsupported or malformed templates
SHALL produce an input error and no writes. Builds without the option SHALL keep existing output.
The result SHALL report the template SHA-256 and applied sheets, and evidence SHALL remain INFERRED
until an Altium author report or verification kit proves application.

#### Scenario: Template applied without flattening
- **WHEN** a binary template holds different fonts, native page settings, owned drawings and images
- **THEN** every built sheet retains them, generated circuit references are valid, and the copied
  template is byte-identical to the input

#### Scenario: Reviewed template changes
- **WHEN** the template changes between dry run and confirmation
- **THEN** the existing plan input guard refuses confirmation and writes nothing

#### Scenario: Unsupported combination
- **WHEN** native application is requested with KiCad, ASCII output, or a neutral drawing sheet
- **THEN** the build refuses the combination without silently converting the template
