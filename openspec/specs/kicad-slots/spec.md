# kicad-slots Specification

## Purpose
Keep the children a typed KiCad reader does not model, in place and with a minimum format version, so a writer can re-emit them: split a node into modelled and opaque slots, rebuild it in the original order, and persist slot lists in the `kicad` extension bag of an entity without changing the model.
## Requirements
### Requirement: Split children into slots
`fenolite.backends.kicad.slots.split(node, fields, *, positional=(), min_version=None)` SHALL return one slot per child of `node`, in child order:
- a child list whose head text is a key of `fields` → `Modeled(fields[head])`
- the i-th atom that precedes the first child list, for i < `len(positional)` → `Modeled(positional[i])`
- every other child, atoms included → `Opaque(dumps(child, style="compact"), v)`, where the fragment of an atom is its text

`Modeled` and `Opaque` MUST be the types of `fenolite.model.base`.

#### Scenario: Pad with an unknown child
- **GIVEN** `(pad "1" smd rect (at 1 2) (frobnicate 3) (size 1 1))`, `fields = {"at": "position", "size": "size"}` and `positional = ("number", "type", "shape")`
- **WHEN** `split` runs with `min_version="20260206"`
- **THEN** the slots are `Modeled("number")`, `Modeled("type")`, `Modeled("shape")`, `Modeled("position")`, `Opaque("(frobnicate 3)", "20260206")`, `Modeled("size")`

#### Scenario: Opaque atom after the positional atoms
- **GIVEN** `(pad "1" smd rect locked (at 1 2))`, `fields = {"at": "position"}` and `positional = ("number", "type", "shape")`
- **WHEN** `split` runs and the node is rebuilt from a source that returns the original children
- **THEN** the fourth slot is `Opaque("locked", None)` and the rebuilt node is tree-equal to the input

#### Scenario: Opaque atom after a child list
- **GIVEN** `(fp_text reference "R1" (at 0 0) hide (effects))` with `fields = {"at": "position"}` and no positional fields
- **WHEN** it is split and rebuilt from a source that returns the original children
- **THEN** `hide` is an `Opaque` slot between the `position` slot and the opaque `(effects)` slot, and the rebuilt node is tree-equal to the input

#### Scenario: Repeated heads produce one slot each
- **GIVEN** a footprint node with three `property` children and `fields = {"property": "properties"}`
- **WHEN** `split` runs
- **THEN** there are three `Modeled("properties")` slots at the children's positions

### Requirement: Opaque minimum version
`split` SHALL accept as `min_version` a decimal version string, `None`, or a callable that receives the opaque child and returns a decimal version string or `None`. A string or `None` MUST be stored in every `Opaque` slot. A callable MUST be called once per opaque child, and its result MUST be stored in that slot. Readers MUST pass the format version of the file the node came from, either directly or as the callable's fallback. Versions MUST be compared as integers wherever they are compared.

#### Scenario: Conservative version
- **GIVEN** a node read from a file with `(version 20241229)`
- **WHEN** a reader splits it with `min_version="20241229"`
- **THEN** every opaque slot carries `"20241229"`

#### Scenario: Per-child version
- **GIVEN** a pad node with opaque children `(padstack …)` and `(frobnicate 1)`, and a callable that returns `"20240929"` for a node headed `padstack` and `"20241229"` otherwise
- **WHEN** `split` runs with that callable
- **THEN** the `padstack` slot carries `"20240929"` and the other opaque slot carries `"20241229"`

### Requirement: Order-preserving rebuild
`rebuild(head, slots, source, *, canonical=())` SHALL return a `Node` with head `head`. `source` MUST provide `items(field)` and `fields()`, the fields that have items. The children MUST be produced by walking `slots` in order:
- The k-th `Modeled(f)` slot MUST emit `source.items(f)[k]` when that item exists, and nothing otherwise.
- Items of `f` beyond the number of its slots MUST be emitted right after its last slot.
- Each `Opaque` slot MUST emit `opaque_child(slot)`, which decodes the fragment with `parse_fragment`, unchanged, at its position.

#### Scenario: Unchanged source is identity
- **GIVEN** a node `n`, its slots from `split`, and a source that returns the original children for each field
- **WHEN** `rebuild(n.head, slots, source)` runs
- **THEN** the result is tree-equal to `n`

#### Scenario: Deleted item leaves neighbours in place
- **GIVEN** a node with children `(property A) (x 1) (property B)`, where `x` is opaque, and a source whose `properties` holds only the node for `A`
- **WHEN** it is rebuilt
- **THEN** the children are `(property A) (x 1)`

#### Scenario: Added item follows its field
- **GIVEN** the same node and a source whose `properties` holds `A`, `B`, `C`
- **WHEN** it is rebuilt
- **THEN** the children are `(property A) (x 1) (property B) (property C)`

### Requirement: Canonical insertion of new fields
`rebuild` MUST check every field returned by `source.fields()`: it MUST either have at least one slot or be listed in `canonical`, and otherwise `rebuild` MUST raise `ValueError` naming the field. A listed field that has items but no slot SHALL be inserted after the last slot whose field precedes it in `canonical`. If no such slot exists, it SHALL be inserted after the positional atoms.

#### Scenario: New field in canonical position
- **GIVEN** slots for `position` and `size`, `canonical = ("position", "rotation", "size")`, and a source whose `fields()` includes `rotation`
- **WHEN** `rebuild` runs
- **THEN** the `rotation` child appears between the `position` and `size` children

#### Scenario: Field without canonical position
- **GIVEN** a source whose `fields()` returns `colour`, which has no slot and is not in `canonical`
- **WHEN** `rebuild` runs
- **THEN** a `ValueError` naming `colour` is raised

### Requirement: Slots persist in the kicad extension bag
`to_ext(slots, base=None)` SHALL accept one slot list, which it treats as the list of relative locator `.`, or a mapping from relative locator to slot list. A relative locator is `.` for the entity node and otherwise a locator without the leading root, such as `effects[0]` or `effects[0]/font[0]`. It SHALL return an `ExtBag` whose payload holds, for each locator and in slot order:
- `("slot:<rel>:modeled", field)` for each modelled slot
- `("slot:<rel>:opaque", fragment)` for an opaque slot without a minimum version
- `("slot:<rel>:opaque@<min_version>", fragment)` for an opaque slot with a minimum version

The payload MUST start with the pairs of `base` whose key does not start with `slot:`, in their original order. It MUST keep the slot pairs of `base` for locators absent from the new slots. It MUST then order the slot groups with `.` first and the others in lexicographic order of the locator. `min_version` MUST be the greatest of `base.min_version` and every opaque minimum version in the result, compared as integers, ignoring `None`.

`from_ext(bag, at=".")` MUST return the slot list of locator `at`, and `from_ext_all(bag)` MUST return every list keyed by locator; both MUST invert `to_ext`. They MUST raise `ValueError` for a `slot:` key whose kind part, after the last `:`, is not `modeled`, `opaque` or `opaque@<digits>`. The model dataclasses and the generated schemas MUST NOT change.

#### Scenario: Round trip through ExtBag
- **GIVEN** the slots of the pad example
- **WHEN** `from_ext(to_ext(slots))` is computed
- **THEN** it equals the slots, and the bag's `min_version` is `"20260206"`

#### Scenario: Unknown grandchild of a modelled sub-list
- **GIVEN** `(gr_text "x" (at 1 2) (effects (font (size 1 1)) (justify left)))`, a reader that models the text, `at` and `effects` of the entity and only `justify` inside `effects`, and file version `"20260206"`
- **WHEN** it passes `{".": entity_slots, "effects[0]": effects_slots}` to `to_ext` and reads the bag back with `from_ext_all`
- **THEN** the `effects[0]` list is `Opaque("(font (size 1 1))", "20260206")`, `Modeled("justify")`, and the `.` list is unchanged

#### Scenario: Base version is not lowered
- **GIVEN** a `base` bag with `min_version = "20260206"` and slots whose opaque minimum versions are all `"20241229"`
- **WHEN** `to_ext(slots, base)` runs
- **THEN** the result's `min_version` is `"20260206"`

#### Scenario: Unknown slot key
- **GIVEN** an `ExtBag` whose payload contains `("slot:.:weird", "x")`
- **WHEN** `from_ext` runs
- **THEN** a `ValueError` naming `slot:.:weird` is raised

#### Scenario: Schemas unchanged
- **WHEN** `uv run python tools/gen_schemas.py --check` runs after this change
- **THEN** it exits 0

### Requirement: Slot identity over the corpus
For every node of every cached, non-heavy `rt0` corpus item, splitting with a subset of its child heads as modelled fields and rebuilding with a source that returns the original children MUST give a tree-equal node. The subset MUST be chosen deterministically by `random.Random(f"{item.id}:{locator}")`, so that a failure reproduces. A failure message MUST name the item id, the locator and the subset.

#### Scenario: Identity on demo boards
- **GIVEN** the fetched corpus
- **WHEN** `uv run pytest tests/corpus/test_rt0.py::test_slot_identity` runs
- **THEN** every node of every item rebuilds tree-equal

#### Scenario: Reproducible failure
- **GIVEN** a slot-identity failure at locator `/kicad_pcb/footprint[3]` of an item
- **WHEN** the test runs again on the same cache
- **THEN** it fails at the same locator with the same subset, and the message names the item id, the locator and the subset

### Requirement: Slot source for model entities
A KiCad writer SHALL emit every model entity through `slots.rebuild`, with a `SlotSource` built from the entity's current model values (c0009's `pcb.model_source`) and with `canonical = pcb.CANONICAL_ORDER[head]`. The slot list MUST be chosen as follows:
- **Read entity.** An entity whose `kicad` bag holds slots MUST be rebuilt with the lists of `from_ext_all(bag)`: the list of `.` for the entity node and each relative list for its sub-list. Its children keep their source order, and a field new to it follows "Canonical insertion of new fields".
- **Created entity.** An entity without slots in its `kicad` bag MUST be rebuilt with the empty slot list, so its children appear exactly in canonical order, positional fields first. Its sub-lists, such as a zone's `polygon` and `filled_polygon` or a rule area's `keepout`, MUST follow the canonical order of their own heads, so `CANONICAL_ORDER` MUST hold an entry for each of them.
- A field that the source returns and that `CANONICAL_ORDER[head]` lacks MUST raise `ValueError` naming the head and the field, and so MUST a head without an entry in `CANONICAL_ORDER`.

Opaque fragments MUST be re-emitted tree-equal to their source, at their positions. The only exceptions are the changes that a `kicad-file-backend` requirement names, each applied by the writer and none by `rebuild`:
- `net` nodes rewritten into the target's form, with nets renumbered by name on every target-9 write ("Net form per target");
- the source's opaque root row `(net 0 "")`, replaced in place by the generated table's row 0 for target 9 and removed for target 10, and opaque `(net 0)` references removed for target 10 ("Net form per target");
- nodes of an `until_major = 9` inventory row converted or dropped for target 10 ("Board writing per target");
- opaque slots removed under `allow_lossy` ("Lossy writes are refused unless allowed");
- the value atom of a Reference or Value property, and spelling-only projections re-emitted from a changed model value ("Projected fields on write").

The `design-model` requirement "Slots for lossless round-trip" refers to this list for the KiCad writer.

#### Scenario: Created track in canonical order
- **GIVEN** a created `Track` on `F.Cu` with a net and no `kicad` bag
- **WHEN** it is written for target 10
- **THEN** the `segment` children appear in the order `CANONICAL_ORDER["segment"]` gives

#### Scenario: Read entity keeps its order
- **GIVEN** `two_layer.kicad_pcb` read with `read_board`, and the width of one track changed
- **WHEN** the design is written for target 9
- **THEN** that `segment` node has its children in source order with the new width, and every other node of the board is tree-equal to the source apart from the header atoms and net numbers

#### Scenario: Created zone with a fill and a rule area
- **GIVEN** the created test board `tests/_boards.py::created_board()`, whose zone has one fill and whose rule area forbids tracks
- **WHEN** it is written for target 10
- **THEN** no `ValueError` is raised, and the children of the `zone`, its `filled_polygon` and the rule area's `keepout` appear in the orders `CANONICAL_ORDER` gives for those heads

#### Scenario: Field without canonical position
- **GIVEN** a created entity whose source returns a field absent from `CANONICAL_ORDER` for its head
- **WHEN** `write_board` runs
- **THEN** a `ValueError` naming the head and the field is raised

#### Scenario: Opaque child unchanged on a same-target write
- **GIVEN** `tests/data/kicad/board/dimension.kicad_pcb` read with `read_board`, and one segment moved
- **WHEN** it is written for target 9
- **THEN** the `dimension` node is tree-equal to the source node and at its source index

