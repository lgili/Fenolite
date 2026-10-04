# Provenance of `fenolite.backends.specctra`

A codec for Specctra design files (written) and session files (read), change c0023. Every fact this
package relies on is recorded in Fenolite's own words in `docs/formats/specctra/dsn.md` and `ses.md`, with
its source from `docs/evidence/sources.md`, and the code is written from those pages.

- The format facts come from one document, S-0224, whose notice forbids copying and distribution. It was
  read on line for facts only (ADR-0006). No sentence, table, grammar production or example of it is in
  this repository, and it is neither vendored nor linked from the package.
- No third-party code was copied, transcribed or followed. The source code of Freerouting, of KiCad's
  Specctra exporter and importer, and of any other reader or writer of this format was **not** read.
- Freerouting is GPL-3.0. Fenolite runs it as a program across a process boundary; it never imports,
  vendors or downloads it. Its documentation pages were read for its arguments and settings.
- The fixtures under `tests/data/specctra/` are authored for Fenolite; none is a file written by
  Freerouting, by KiCad or taken from the reference.

| fact-or-area | public source | licence of source | date | how used |
|---|---|---|---|---|
| syntax: lists in parentheses, words, the quote character and blanks in quoted strings, numbers | S-0224 | all rights reserved; notice forbids copying (read for facts, ADR-0006) | 2026-10-04 | facts only |
| design file: order of sections, units and resolution, layers, boundaries, keep-outs, via list, default rules | S-0224 | all rights reserved; notice forbids copying (read for facts, ADR-0006) | 2026-10-04 | facts only |
| shapes (circle, path, polygon, rectangle), placement entries and locks, images, pins, padstacks | S-0224 | all rights reserved; notice forbids copying (read for facts, ADR-0006) | 2026-10-04 | facts only |
| nets, pin references, classes, wires and vias with their types | S-0224 | all rights reserved; notice forbids copying (read for facts, ADR-0006) | 2026-10-04 | facts only |
| session file: placement, pin swaps, routes, the meaning of its resolution | S-0224 | all rights reserved; notice forbids copying (read for facts, ADR-0006) | 2026-10-04 | facts only |
| Freerouting: licence, Java version, arguments, analytics setting, release 2.4.1, container image | S-0220, S-0221, S-0222, S-0223, S-0226 | GPL-3.0 (documentation pages read; the program is run as a subprocess) | 2026-10-04 | facts only; oracle once the probes run |
| `kicad-cli` exports no design file and imports no session; KiCad's editor does both | S-0022, S-0037, S-0225 | GPL-3.0-or-later tool run as a subprocess; GPL-3.0-or-later or CC-BY-3.0-or-later page | 2026-10-04 | facts only |
