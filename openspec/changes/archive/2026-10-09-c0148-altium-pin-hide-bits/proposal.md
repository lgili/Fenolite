## Why

On 2026-10-08, in session 2, the maintainer looked in Altium Designer 26 at the LED `D1` of the kit sample `flat` (the catalog LED, its pins written with `PINCONGLOMERATE` 18 and 16, meant as "number shown, name hidden"). Altium showed the opposite: both names visible, both numbers hidden. A symbol written with 2 and 0 (no bit) showed both. On the narrow LED body the visible names K and A crossed over, so he read the LED as reversed; the pads and the pin map were right. The overlapping pin names of the report of 2026-10-07 most likely have the same cause.

The fact pages record, as `INFERRED` from S-0130 and S-0131, that bit 0x08 shows a pin's name and 0x10 its number, and Fenolite writes so. A census of the corpus (S-0614) found that every one of the 4 175 pins Altium saved holds bit 0x20, which Fenolite never writes, and that read as show flags the bits give the usual picture (passives hide pin texts, integrated circuits show them). A check project with 0x20 set on every pin (`tests/data/altium/pinbits/`) was opened the same day in Altium Designer 26.5.0: 0x20 alone showed nothing, 0x30 the numbers, 0x28 the names, 0x38 both (S-0613).

So with 0x20 set the two bits are show flags, and without it Altium Designer 26 reads them as hide flags.

## Outcome in one paragraph

**The writer sets bit 0x20 on every pin and keeps 0x08 and 0x10 as show flags, as Altium saves pins; the reader takes the two bits as show flags with 0x20 and as hide flags without it.** What a symbol means to show does not change; only the encoding does. Every Altium schematic and library that Fenolite writes changes its pin bytes; the files of 0.2.x show pin names that were meant hidden and must be built again.

## What Changes

- **`altsym.AltiumPin.conglomerate`**: direction | 0x20 | 0x04 (hidden) | 0x08 (name shown) | 0x10 (number shown). Both writers (`schdoc`, `schlib`) and both forms take it from there; the generic bodies of Altium links too.
- **`read.sch.records.Pin.name_shown` and `designator_shown`**: show flags with 0x20 set, hide flags with 0x20 clear (`SHOW_FLAGS`). `direction` and `hidden` are unchanged. The adapter does not map these two attributes into the model, so no import changes.
- **Samples and pins**: every committed Altium schematic document and library written by the product changes its pin bytes and is written again by its own tool (the golden tests' write mode, the authoring scripts); the Altium pins of `tests/unit/lens/test_build_bytes_pinned.py` move, each with the reason beside it. No KiCad pin moves.
- **New sample**: `tests/data/altium/pinbits/` (the check project and its `author.py`), with a test that it reads back as Altium showed it, and tests of the writer's and the reader's bits.
- **Pages**: fact rows of `docs/formats/altium/schematic-library.md` and `schematic-ascii.md` (a note in `schematic-records.md`); `docs/hypotheses.md` (`H-A-SCHLIB-PINBITS`, a note on `H-A-SCHLIB-PIN`); `docs/evidence/sources.md` (S-0612, S-0613, S-0614); `docs/evidence/altium-schematic.md` ("Pin visibility bits").

Size: 1 design-day (a size, not time).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-schematic-writer`: MODIFIED "Generic component bodies" (the conglomerate of a generic pin) and "Binary pin record" (bit 0x20, the meaning of the bits, two scenarios).
- `altium-schematic-reader`: ADDED "Pin visibility bits".

## Non-goals

- No change to what a symbol shows: `pin_names_hidden`, `pin_numbers_hidden`, an empty name or `~` hide as before.
- No change to the KiCad backend, the model, the design language or the catalog's symbols.
- No change to the catalog's legibility rule of c0134: it measures the texts the model means to show, which is now what Altium shows.
- No bit other than 0x20, 0x08 and 0x10 is claimed; 0x40 stays as recorded.

## Evidence level required

- With 0x20 set: `ALTIUM-VERIFIED(author-report)` (AD 26.5.0, 2026-10-08, S-0613), with the corpus census (`CORPUS-VERIFIED`, S-0614) and S-0130/S-0131 behind it.
- With 0x20 clear: `ALTIUM-VERIFIED(author-report)` (AD 26, 2026-10-08, S-0612), on the values 0, 2, 16 and 18 only.
- A rebuilt kit or session file has not been opened in Altium; the check project has.

## Impact

- Changed: `src/fenolite/backends/altium/altsym.py`, `src/fenolite/backends/altium/read/sch/records.py`, `src/fenolite/backends/altium/schlib.py` (evidence tuple); committed Altium samples and their tests; the pages above; `CHANGELOG.md`.
- Behaviour: **every Altium schematic document and library that a build writes changes its pin bytes** (`PINCONGLOMERATE` + 0x20). In Altium, pin names and numbers are shown and hidden as the symbol means; a file of 0.2.x shows the names its symbols meant hidden and hides numbers meant shown, until it is built again.
