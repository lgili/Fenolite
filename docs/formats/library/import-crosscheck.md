# Local import classifier and comparison

All classifier choices and tolerances below are authored for Fenolite, labelled `INFERRED`, and
covered by `H-G-LIBRARY-IMPORT`. They are screening rules, with no IPC table or acceptance claim.

| fact | source | label | hypothesis |
|---|---|---|---|
| Compare numbered copper pads by number; keep exposed pads separate and omit unnumbered paste windows. | S-1030 | INFERRED | H-G-LIBRARY-IMPORT |
| Classify two terminals as chip or molded by land extent, two or four outside rows as gullwing or nolead, lettered grids as grid, drilled dual rows as dip, and drilled rectangular grids as header. A single line of three drilled leads suggests to. | S-1030 | INFERRED | H-G-LIBRARY-IMPORT |
| A central exposed pad suggests nolead; otherwise rows suggest gullwing. Pads alone cannot establish the body or distinguish all overlapping families. Explicit packages select between compatible row families; connector series require an explicit package. | S-1030 | INFERRED | H-G-LIBRARY-IMPORT |
| Derive row coordinates, pitch and pad sizes from integer medians, and draw a reference with the existing family generator. Body and lead dimensions are nominal estimates; the imported geometry remains the build geometry. | S-1030 | INFERRED | H-G-LIBRARY-IMPORT |
| Pitch tolerance is 10 000 nm (0.01 mm); pad centre tolerance is 100 000 nm (0.10 mm) per axis. | S-1030 | INFERRED | H-G-LIBRARY-IMPORT |
| Pad size tolerance per axis is the larger of 20 percent of the reference size and 100 000 nm. Rotate rectangular pad sizes into the footprint frame before comparison. | S-1030 | INFERRED | H-G-LIBRARY-IMPORT |
| Counts, numbering and pin 1 differences are errors with an explicit package and warnings for a guess. Land and pitch differences remain warnings. Unclassified patterns give an informational finding. | S-1030 | INFERRED | H-G-LIBRARY-IMPORT |

Numbering is checked against spatially corresponding reference lands, independently of the number
used for the dimensional comparison. This catches a clockwise sequence even when both footprints
contain the same set of pin numbers. Source disagreement uses the same tolerances and gives one
warning naming the differing pads. The report includes measured and reference values in nm.
