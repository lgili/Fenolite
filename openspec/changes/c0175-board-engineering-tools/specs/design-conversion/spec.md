## ADDED Requirements

### Requirement: Mask and paste of imported pads
A pad read from an Altium document SHALL be given mask and paste layers by its kind when it is converted to KiCad: a surface pad its side's copper, paste and mask layers; a plated through-hole pad both mask layers and no paste; an unplated hole both mask layers.
- A pad's mask and paste expansion, whether it comes from the document's rules or is set on the pad, MUST become the pad's mask and paste margins when the model holds them, and MUST be listed as a loss of kind `pad-margin` otherwise.
- A pad marked in the document as having no paste opening, or a tented pad, MUST keep that state.
- `docs/conversion.md` MUST no longer say that converted pads have no mask or paste opening.

#### Scenario: Openings after conversion
- **GIVEN** an authored Altium document with a surface pad, a through-hole pad and an unplated hole, saved by the maintainer's kit
- **WHEN** `uv run pytest tests/unit/convert/test_pad_layers.py` converts it to KiCad
- **THEN** the surface pad holds `F.Cu`, `F.Paste` and `F.Mask`, the through-hole pad holds `*.Cu` and both masks without paste, the hole holds both masks, and `kicad-cli` DRC reports no `solder_mask_bridge` that the source did not hold

### Requirement: Model placement of imported footprints
The footprint model SHALL hold for each 3D model its path, offset, rotation and scale, and the KiCad footprint writer SHALL write them for a footprint that was read from another format.
- A model embedded in an Altium document MUST be extracted beside the converted library as a file, named by the footprint and the model's id, and referenced with its placement.
- The placement MUST be computed so that the model stands on the pads as in the source: the source's offset and height, then its rotations about Z, Y and X, in that order.
- A model that cannot be placed MUST be listed as a loss of kind `model` with the reason.

#### Scenario: A rotated body
- **GIVEN** an authored Altium library whose footprint holds an embedded model turned by 90° about Z and raised by 0.5 mm
- **WHEN** it is converted to KiCad
- **THEN** the written footprint names the extracted model with an offset of 0.5 mm in Z and a rotation of 90° about Z, and `kicad-cli` loads the library without error

### Requirement: Library made from a board
`fenolite library BOARD --out LIB [--diff LIBRARY]` SHALL write each footprint as placed on the board, brought back to its own origin, rotation 0 and the top side, into a library of the board's backend, under the mutation protocol.
- Two placed instances of one footprint name that differ after that transform MUST be written as two footprints, the second with a suffix, and reported with `library.instances-differ` (warning).
- `--diff LIBRARY` MUST report per footprint how the library differs from the board's instances (pads, silkscreen, courtyard, models, fields) and write nothing.

#### Scenario: Silkscreen edited on the board
- **GIVEN** an authored board whose instances of `R_0603` have their silkscreen clipped, and a library with the unclipped footprint
- **WHEN** `fenolite library <board> --out lib.pretty --diff old.pretty --json` runs
- **THEN** the reply names `R_0603` with a silkscreen difference, and nothing is written
