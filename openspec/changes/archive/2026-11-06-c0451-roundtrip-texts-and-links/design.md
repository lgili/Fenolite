# Design: c0451

## Library links through KiCad

The KiCad project of a conversion holds one derived footprint library and one generated symbol per
component, so the source's names have no place in KiCad's own links. Two hidden footprint properties carry
them: `Altium Footprint` (`<library>:<pattern>` as read) and `Altium Symbol` (`<library>:<symbol>`). A
property of a created footprint needs a field to hold it, so each is a hidden field on `F.Fab` at the
footprint's origin, with the Reference field's size. The KiCad → Altium conversion reads them from the
component's properties, sets the written links, and drops the two properties.

Both links come back whole, so the round trip's components hold the source's links. The way back gives
each link the `.PcbLib` or `.SchLib` of its library (the form of an Altium link; the import reads it
without), so the writer files each footprint and symbol under its source library: the derived footprints
of one source library go to a `.PcbLib` of that name (`lower.derived_library`, `project.write_project(...,
extra_footprints=...)`), the symbols to a `.SchLib` of that name (`project.schlib_name`, as before), and
each component links the file the project ships. A KiCad link never ends with `.PcbLib`, so a KiCad design
keeps its one `<name>.PcbLib`. Two components of one symbol link whose embedded symbols differ fall back to
`PART_<ref>` in the design's library (`schematic.inputs`). A link is stale when the KiCad footprint was
swapped: the footprint link comes back only while the KiCad link's item is the name the conversion derived
from the source pattern (`library_name`, perhaps with a variant suffix `_<n>`); otherwise both properties
are dropped and the component is written as before.

The alternative, a KiCad library nickname per source library pointing at the one derived folder, keeps the
footprint library in KiCad's own link, but not the symbol, and changes every library table of a conversion.

## Special strings

KiCad shows `${NAME}` as typed while the project does not define it, as Altium shows an unknown special
string. Writing `.MY_TAG` as `${MY_TAG}` lets a KiCad user define it, and gives the way back one rule:
`${NAME}` is `.NAME`. KiCad's predefined variables of a board go back to the predefined special strings of
the same meaning (S-1870, S-1871), in the case the Altium documentation writes.
