# Proposal: c0479-altium-project-settings-carried

## Problem
An Altium project imported to Python (`import --to python`) and built back (`build --target altium`), or
converted to KiCad and back (`convert --to kicad`, then `convert --to altium`), gets a `.PrjPcb` that
`backends.altium.prjpcb.write_prjpcb` makes from nothing: `[Design]` with `Version`, the document list,
`[PrjClassGen]` and title parameters. Every other setting of the source project is lost: the net
identifier options of `[Design]` (`HierarchyMode`, `AllowPortNetNames`, `AllowSheetEntryNetNames`,
`AppendSheetNumberToLocalNets`, `PowerPortNamesTakePriority`), the compiler's error levels and connection
matrix (`[Electrical Rules Check]`, `[ERC Connection Matrix]`), annotation, comparison and difference
options, project variants, output groups, search paths, configurations and the project parameters.

On a hierarchical project whose source turns sheet-entry net names off, Altium Designer 24.5.2.23
compiles the source with no message and the built project with `Nets ... has multiple names` warnings,
because the written project falls back to Altium's default `AllowSheetEntryNetNames`; the netlist is
unchanged.

## Scope
- Read the source project's settings (every section but `Document<n>` and `GeneratedDocument<n>`, and
  `[Design]` without `Version`) when an Altium project's drawing is read for a conversion.
- Carry them in the root sheet's `Fenolite.Altium.Sheet` carrier, so they ride through the KiCad sheets
  of a conversion and the `schematic.toml` footer of an import, as the sheet records do (c0473).
- Merge them into the `.PrjPcb` that `write_prjpcb` writes for a drawn build or conversion.

- Point each `Variation<n>` of a carried project variant at the unique id path of the written component
  of its designator, since a rebuilt project gives its components and sheet symbols new unique ids.

- Keep a net label of an Altium source a net label when the project comes back from KiCad
  (`convert --to altium`): the KiCad-to-Altium writer turns a local label that shares its text with a
  hierarchical label or a power symbol of its sheet into a port or power port (`H-A-IMP-DUP-NAME`), but
  the source's own net label joined them in Altium. With the source's settings carried, such a port no
  longer names its net (`AllowPortNetNames=0`), so the nets of the round trip were renamed and Altium
  reported duplicate and unspecified ports.

Out of scope: the `.OutJob` documents, which are separate files.
