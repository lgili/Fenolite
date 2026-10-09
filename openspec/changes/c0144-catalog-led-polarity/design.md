## Context

**What was read, on 2026-10-08.** The two datasheets that the register rows S-0412 and S-0413 name. The fetch tool returned each PDF file and no text of it; page 1 of each was rendered locally and read as a drawing.

| | APT1608SURCK (S-0412) | APT2012SURCK (S-0413) |
|---|---|---|
| URL | `https://www.kingbrightusa.com/images/catalog/spec/apt1608surck.pdf` | `https://www.kingbrightusa.com/images/catalog/spec/apt2012surck.pdf` |
| title | "APT1608SURCK 1.6 x 0.8 mm SMD Chip LED Lamp" | "APT2012SURCK 2.0 x 1.25 mm SMD Chip LED Lamp" |
| spec, revision, date | DSAD0926 / 1203001764, V.22A, 04/08/2023 | DSAD0945 / 1203001884, V.21A, 03/17/2025 |

- The package drawing of each numbers the terminals 1 (left) and 2 (right) and names a "Polarity mark".
- A diode symbol between "1" and "2" has its bar at terminal 1: terminal 1 is the cathode, terminal 2 the anode.
- The figure "Recommended soldering pattern" holds neither a number nor a polarity; the pad numbers follow the package drawing.
- The land dimensions are the catalog's (0.8 / 0.85 / 0.8 mm; 1.25 / 1.1 / 1.25 by 1.1 mm).

**The register rows should be amended by the coordinator.** S-0412 and S-0413 say "pin 1 is cathode" under "page 1" and are dated 2026-10-05. They do not say that the terminals are numbered in the package drawing only, that the polarity is read from the diode symbol and the polarity mark, and that the soldering pattern is unnumbered; nor the revisions above and the reading of 2026-10-08. `docs/evidence/sources.md` is append-only in this batch, so no row was changed here and none was added. Amended on 2026-10-09 (task 3.2): both rows now hold the reading of 2026-10-08 above.

**In the repository.** The footprint builder puts pad 1 on the left with the fabrication-layer cathode mark on the left, as the datasheet, the summary ("pin 1 cathode") and `docs/catalog/sources.md` say. The other diode lands use pad 1 anode and pad 2 cathode with the mark on the right (`DO35`, `DO41`, `SOD123`, `SOD123F`, `SOD323`, `SOD523`, `DO214AA`, `DO214AB`), which fits the symbols. `SOD128_Nexperia_CFP5` has pad 1 at the cathode and the warning. KiCad's own convention for LED and diode symbols and footprints is not recorded in this repository's pages, and no KiCad library file was read for this change.

**Who used the pair.** The four kit samples, by pin number and without a map. The `fenolite init` starter, the tasks of the agent evaluation and `tests/_catalog_design.py` put `Fenolite:LED` on `Chip_0603` or `Chip_0805`, which have no polarity.

## Decisions

1. **The warning goes into the catalog pages, not into the footprint's summary.** The summary is the footprint's description: a build writes it into `lib/Fenolite.pretty/<name>.kicad_mod`, into the board file and into `.fenolite/board.json` (measured on a KiCad build of the kit sample `flat`). A longer summary would move those bytes in every released user's project that holds one of the two lands, and the rebuild would report `build.library-changed`. No committed digest, golden or schema pins the summary; the files of users' builds do. The summary already states the fact ("pin 1 cathode"); the pages add what to do about it. `fenolite catalog show` therefore shows the fact and not the advice.
2. **The kit samples carry the map and connect by name.** `pad_map={"1": "2", "2": "1"}` puts the anode (pin 1) on pad 2 and the cathode (pin 2) on pad 1; `d1["K"]` is on `GND` and `d1["A"]` on `LED_A`. Measured before and after on the four samples (`fenolite build --target altium`, stored model, `check --stages roundtrip.rta2` exit 0 on all eight builds): every pad of every board keeps its net (`D1` pad 1 `GND`, pad 2 `LED_A`); the schematic had `GND` on pin 1 `A` and now has it on pin 2 `K`.
3. **What moves in the kit** (`fenolite kit build`, before and after, `diff -r`): the five schematic documents `board6/board6.SchDoc`, `flat/flat.SchDoc`, `flat/ascii/flat.SchDoc`, `libs/libs.SchDoc` and `routed/routed.SchDoc`, and `kit.json` (for the four samples: `digest`, the `sha256` and `size` of the schematic documents, `script_sha256`). Each sheet gains the two pin-map records (record 47; the ASCII sheet's `WEIGHT` goes from 154 to 156) that an Altium build writes for a mapped part since c0135 and c0123, and the LED's symbol moves on the sheet, because its nets are on the other pins. No `SchLib`, `PcbLib`, `PcbDoc`, `PrjPcb` or `OutJob` moves: the library holds the map only when every part of the symbol links the footprint that the symbol names, and the catalog's `LED` names none. The kit is not released; no test, page or register holds one of these digests (searched by value), and `tests/data/MANIFEST.toml` lists the scripts without a hash, so nothing was regenerated.
4. **One test names the lands.** `tests/unit/catalog/test_polarity_notes.py` finds every two-pad catalog land whose pad 1 lies on the side of its cathode mark, holds the list to the three known ones, and holds each to its warning in both pages: a new land of this kind fails until it is named and documented.

## Known gaps

- `DO214AC` has no cathode mark on the fabrication layer, unlike `DO214AA` and `DO214AB`; its pads follow the generic convention (pad 2 cathode). Not fixed here.
- The kit sample `libs` connects `D2` (`Fenolite:Diode` on `DO214AC`) with `VIN` on pin 2 `K` and `VCC` on pin 1 `A`, a series diode drawn against the current. It is a library sample, not a circuit; not changed here.

## Open question for the maintainer

**Should the catalog apply a default pin-to-pad map for a known symbol and footprint pair** (`LED`, `Diode`, `Zener_Diode` on the two Kingbright lands and on `SOD128_Nexperia_CFP5`: anode to pad 2, cathode to pad 1) when the part gives no `pad_map`?

- For: the pair then cannot be wired wrongly by a script that connects by pin name, which is what an agent writes.
- Against, and the reason it is not done here: a design of a 0.2.x user that wired one of these lands by pin number without a map (as the kit did: `GND` on `d1[1]`) has a right board today. With a default map its two nets would swap pads on the next build, silently, on a board that may be made already.
- Recommendation: do not apply a map silently. Report the pair instead: a build warning (a new code, for example `build.polarity-unmapped`) for a part of one of the three symbols on one of the three lands without a `pad_map`, naming the map to write. It moves no byte of any build, tells the released user and the agent alike, and leaves the decision in the script. That is a change of its own (an issue code, its `explain` entry, the closed set of `design-dsl`), proposed after this one if the maintainer agrees.

**Answer of the maintainer (2026-10-08): a default map** ("deixa padrão automático", leave it automatic by default). The catalog applies `{"1": "2", "2": "1"}` to a part of one of these pairs that gives no `pad_map`, keeps an explicit map, and reports each such part with the warning `build.pad-map-default`, so the released user whose nets would swap pads is told on the next build. Implemented by change c0147 (`catalog-default-pad-map`), whose MODIFIED delta replaces this change's clause "The catalog MUST NOT apply a pin-to-pad map by itself". The recommendation above (a warning only) was not taken.

## Evidence

`INFERRED`: the polarity is read from the manufacturer's public datasheets (S-0412, S-0413), not measured on a part; the builds are proved by Fenolite's own readers (`H-A-VER-RTA2-3`). Nothing was opened in Altium for this change.
