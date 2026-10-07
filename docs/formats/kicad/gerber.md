# Gerber plots read by the zone and via probes

Fenolite writes no Gerber file: `kicad-cli` plots them (`docs/formats/kicad/cli.md`). One oracle probe,
`zone-fat9`, reads a copper plot to see how KiCad draws a zone fill. Its helper,
`tests/kicad/zones/_gerber.py`, lives in `tests/` and reads only the subset below. This page records that
subset in Fenolite's own words. Sources are listed in `docs/evidence/sources.md`; S-0125 is the Gerber
Layer Format Specification, read for facts only.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| A Gerber file is a stream of commands, each ending with `*`; extended commands are written between `%` signs | S-0125 | INFERRED | H-K-ZONE-FAT9 |
| `%FSLAX<i><d>Y<i><d>*%` sets the coordinate format: `L` means that leading zeros are omitted, `A` that coordinates are absolute, and the two digits after `X` and after `Y` give the number of integer and of decimal digits | S-0125 | INFERRED | H-K-ZONE-FAT9 |
| `%MOMM*%` sets the unit to millimetres and `%MOIN*%` to inches | S-0125 | INFERRED | H-K-ZONE-FAT9 |
| A coordinate word is `X<n>`, `Y<n>` or both, a signed integer without a decimal point, read with the decimal digits of the format statement; coordinates are modal, so an omitted `X` or `Y` keeps its last value | S-0125 | INFERRED | H-K-ZONE-FAT9 |
| `G36*` opens a region statement and `G37*` closes it; inside it, a `D02` operation moves to the start of a new contour and each `D01` operation adds a segment from the current point, and the closed contours are the filled area | S-0125 | INFERRED | H-K-ZONE-FAT9 |
| `G01*` selects linear interpolation, so a `D01` inside a region draws a straight segment | S-0125 | INFERRED | H-K-ZONE-FAT9 |
| `pcb export gerbers -l B.Cu` of `kicad-cli` 9.0.9 and 10.0.6 writes `%FSLAX46Y46*%` and `%MOMM*%`, so one coordinate unit is 1 nm, and plots each fill polygon of a zone as one `G36`/`G37` region whose Y values are the board's Y values negated | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ZONE-FAT9 |
| A fill polygon that KiCad reads as a thick outline (a `20241229` zone without `(filled_areas_thickness no)`) is plotted as a region grown by half the zone's minimum thickness, with rounded corners | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ZONE-FAT9 |
| A `D03` operation is a flash: it places the current aperture at the given point, and its coordinates are modal like those of `D01` and `D02` | S-0125 | INFERRED | H-K-VIAPROT-MASK |
| `pcb export gerbers -l F.Mask,B.Mask` of `kicad-cli` 9.0.9 and 10.0.6 plots the mask opening of a via as one flash at the via's centre (X as on the board, Y negated), and nothing for a side on which the via is tented | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-VIAPROT-MASK |
| The drill side files of `pcb export drill --format gerber --generate-tenting` of `kicad-cli` 10.0.6 are Gerber files in the same coordinate format, with the file function `Other,<Feature>-<Side>` (`Other,Tenting-Front` for example), and hold one flash per via that carries the feature | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-VIAPROT-OUTPUTS |

## What the helper reads

`region_extents(text)` requires `%FSLAX46Y46*%` and `%MOMM*%`, follows `G36`/`G37` and the `D02` and `D01`
coordinate words, and returns the bounding box of each region in nanometres. Arcs (`G02`, `G03`),
apertures, flashes and attributes are not read; a file with another coordinate format or unit is refused.

`flashes(text)` (change c0112) requires the same format and unit statements and returns the point of every
`D03` operation in nanometres, in file order; the aperture of a flash is not read. The `via-prot-*` probes
use it for the mask plots and for the drill side files.
