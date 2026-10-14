## Why

`fenolite check` reports 29 FALSE findings on the heavy public document `altium-third-party-pcbdoc-08` (28 `copper.short` and 1 `copper.clearance`; c0130's design, "Known false findings"). Seven vias meet the pour of another net on each of the four inner layers. The pour stands at the generic clearance from each via's HOLE, so Altium poured around the drill: the via has no pad on those layers. The import gives a via its one diameter on every layer of its span, so the pad it draws meets the pour. A check that reports a short the board does not have is worse than one that reports nothing; the maintainer listed the repair as c0132 on 2026-10-07.

## Outcome in one paragraph

**The fact was found in the record and the false findings are gone; no real finding is given up.** The 123 via records of that document with the long form (330 bytes of subrecord; the other 2 810 via records of the eight public documents have 299, 321 or 351) hold a non-zero byte for some inner layers in a table of thirty-two bytes at offset 209 that is zero in every other record. On all 123, a non-zero byte is where the pour of another net stands at the clearance from the hole (28 places of 28) and never where a track of the via's net ends on the via; a zero byte is where such a track ends (72 of 73). That is what Altium's documentation says of **Remove Unused Pad Shapes**: the pad shape is taken off the layers on which nothing touches the via, and a polygon then keeps its clearance to the hole. The import keeps the layers in the via's bag (`pad_removed`); the model is not changed; the copper check on Altium input gets such a via with its diameter where it has a pad and with its DRILL as diameter where it has none, so a real short through the barrel of such a via is still found. The nine further bytes of the long form are located and counted, and not explained.

## What Changes

- **Reader:** `read.pcbprims.via_pad_removed(record)` gives the layer ids whose byte in the table at 209 is not zero, for a via subrecord of at least 321 bytes. The record class is not changed.
- **Import:** a via with such layers holds the pair `("pad_removed", "<id>,<id>,…")`. Its `Via` is as before (one diameter, the same id).
- **Copper check on Altium input:** `AltiumBackend.design_rules` hands the check each such via as one via per run of layers of its span that are alike: its diameter on the layers with a pad, its drill on the layers without. The parts keep the via's id, locator and net. `checks/copper.py` is not touched.
- **Rewrite:** the written via record is the ordinary 321-byte one, with a pad on every layer; the write counts each such via under the kind `via-pad-shape` (not a loss kind: the via is written).
- **Facts:** rows on `docs/formats/altium/pcb-copper.md` (the forms of the via record over the eight documents, the table at 209, the nine bytes, what KiCad's import does with them), sources S-0600 and S-0601, hypothesis `H-A-IMP-VIA-PADLESS`.
- **The pinned test of the defect is replaced** by one that asserts the repaired state, and the numbers of `-08` on `docs/evidence/altium-roundtrip.md` are measured again.

Size: 1 design-day (a size, not time).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-pcb-reader`: ADDED "Removed pad shapes of a via record".
- `altium-import`: MODIFIED "Extension bags" (the key `pad_removed`) and "Tracks, arcs and vias" (the pair of a via).
- `altium-verification`: MODIFIED "Clearance rules of a PCB document" (a via without a pad on a layer is judged by its hole there).
- `altium-pcb-writer`: ADDED "Removed pad shapes are counted, not written".

## Non-goals

- No change of the model: a `Via` holds one diameter. The extension that would let the model say "no pad on these layers" is listed for the coordinator (design, "Out of scope").
- No change of `checks/copper.py` or of any other file under `checks/`: KiCad boards are judged exactly as in 0.2.0.
- No change of a KiCad output, of a committed sample under `tests/data/altium/`, or of the id of an imported item.
- No written long form: no fact says what its nine further bytes are, and a writer does not write bytes it cannot name.
- No reading of KiCad's importer source. `kicad-cli` was run as a subprocess on the public document; what it wrote is the fact.
- No code, constant or file from any private project or organisation.

## Evidence level required

The layout facts (lengths, offsets, counts) are `CORPUS-VERIFIED` on the eight public documents. The meaning of the table is `INFERRED` (`H-A-IMP-VIA-PADLESS`): one document holds such records, and its inner layers have the ids 2 to 5, which is also their position in the stack, so the document cannot tell an index by layer id from an index by position. The copper stage keeps the level it had.

## Impact

- Changed: `backends/altium/read/pcbprims.py`, `backends/altium/adapter/copper.py`, `backends/altium/adapter/ids.py`, `backends/altium/backend.py`, `backends/altium/lower.py`.
- Pages: `docs/formats/altium/pcb-copper.md`, `docs/formats/altium/import.md`, `docs/altium.md`, `docs/evidence/altium-roundtrip.md`, `docs/evidence/sources.md`, `docs/hypotheses.md`.
- Behaviour: `fenolite check` on an Altium document with such vias no longer reports their inner pads as shorts; `summary.items.via` of the copper stage counts the parts of such a via; a rewrite reports the kind `via-pad-shape`.
- Depends on: c0088, c0124, c0127, c0130, c0131 (this branch). Archive after them.
