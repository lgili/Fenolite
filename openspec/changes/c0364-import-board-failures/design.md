# Design

## Non-plated holes in `model_pads`

`model_pads` is the model-only twin of the backends' `BoardPad` geometry. The KiCad frame
(`backends/kicad/frame.py:_copper`) and the Altium frame (`backends/altium/frame.py:_copper`) return no
copper entries for an `np_thru_hole` pad, and both drop, through `_entry`, an entry that `PadCopper`
refuses. `model_pads` follows both rules. No copper is invented for a non-plated hole; the `BoardPad`
keeps its position, layers and net, so the checks that read pads still see it.

## Conversion without a PCB design

`write_altium` and `prepare` hold a board everywhere (placement, holes, zones, footprints). A
schematic-only Altium to KiCad conversion is a feature of its own. Until it exists, a source whose
design has no board is bad input: `convert_project` raises `SourceError` (`FEN-3001`, exit 3) before the
direction writes anything. The message names the declared PCB documents that the read reported as
`altium.project.document-missing`, or says that the project declares no PCB document.

## Document names relative to the set's root

`given_document(path, documents)` returns the project file for a folder, else the path of the file
relative to `documents.root` when it lies under the root (POSIX form), else `path.name`. A document
given alone keeps its name, because its root is its folder.

## Explicitly empty values

`Part(value=None)`, the default, keeps today's behavior: the build gives the part the Value of its
symbol. `Part(value="")` asks for an empty value. The build, which resolves the symbol, has to learn that
intent. A field on the model's `Component` was the first design, but the model 1.0 shapes are frozen by the
maintainer's approval of c0218 (`model0-approved.json`), so the intent stays out of the model:

- `Part.value_empty` is true when the script gave `value=""`;
- `fenolite.dsl.convert.empty_value_ids(design)` lists the component ids of those parts;
- `build_design(..., empty_values=...)` passes them to `lens/build.py:_resolve`, which keeps their value
  empty, as it already does for a board-only part; `fenolite build` passes them from the script;
- the Altium build keeps today's rule (change c0044, RT-A2): the writer gives every component with an
  empty value its symbol's name as the comment;
- the model, its schemas and canonical JSON do not change.

The import emitter writes `value=""` for every source component with an empty value, except a board-only
part, which keeps its own value anyway. The Value of the vendored symbol is its name in the common case,
so leaving `value=` out would rebuild a different value.
