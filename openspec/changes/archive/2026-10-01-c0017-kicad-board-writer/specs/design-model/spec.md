## ADDED Requirements

### Requirement: Placed copies of library definitions
A backend that places a library definition into a design SHALL derive every id of the placed copy from a caller key, never from the seeded generator and never from the definition's own ids.
- The caller MUST pass a `key` that names the placement stably and is unique within the design. c0011 passes the component path.
- Every native id the backend creates for the copy MUST depend only on the key and on the locator of the node inside the definition. For KiCad it is `uuid5(FENOLITE_NS, f"kicad-place:{key}:{locator}")`.
- The Fenolite ids of the copy MUST follow "Identifier derivation" for imported objects with a native id, applied to those native ids, so that a design read back from the written file has the same ids.
- Placing the same definition again with the same key MUST give the same ids and native ids. Two keys MUST share no id and no native id. Adding or removing another placement MUST NOT change any id of a placed copy.
- The copy MUST record its definition in `FootprintInstance.lib_ref` (the definition's `lib_id`), its `component_id` MUST be the caller's component, and its pads MUST have `net_id = None` until the caller assigns nets.
- The definition MUST stay unchanged, so it can be placed again.

This is the third case of "Identifier derivation", next to imported and created objects, which this change modifies to name it.

#### Scenario: Same key, same ids
- **GIVEN** `Mini_R_0603` read from `tests/data/libs/Mini.pretty`
- **WHEN** it is placed twice with key `R1`, once in a design created with `seed=1` and once with `seed=2`
- **THEN** the two copies have equal footprint ids, pad ids and native ids, although every seeded id of the two designs differs

#### Scenario: Distinct keys share nothing
- **GIVEN** the same definition placed with keys `R1` and `R2`
- **WHEN** the ids and native ids of both copies are collected
- **THEN** the two sets are disjoint

#### Scenario: Ids survive a write and a read
- **GIVEN** a created design holding `Mini_R_0603` placed with key `R1`
- **WHEN** it is written for target 10 with `write_board` and the text is read with `read_board`
- **THEN** the re-read footprint and its pads have the ids of the placed copy

#### Scenario: Inserting a part shifts nothing
- **GIVEN** a design with placements keyed `R1` and `R3`
- **WHEN** a placement keyed `R2` is added
- **THEN** every id of the `R1` and `R3` copies is unchanged

## MODIFIED Requirements

### Requirement: Slots for lossless round-trip
Backends MUST represent every typed node they read as an ordered list of children, each `Modeled(field)` or `Opaque(fragment, min_version)`, and MUST re-emit opaque children verbatim in their original position on write.

On a write, the only changes a backend makes to an opaque child MUST be those that one of its own requirements names, and every other opaque child MUST be re-emitted unchanged. The KiCad writer's changes are listed in the `kicad-slots` requirement "Slot source for model entities": `net` nodes rewritten into the target's form, also on a same-target write, where nets are renumbered by name; nodes of rows the target no longer writes; slots removed under `allow_lossy`; the value atom of a Reference or Value property; and projections re-emitted from changed model values.

#### Scenario: Unknown child survives
- **GIVEN** a node with an opaque child unknown to the model
- **WHEN** the design is read, unchanged, and written by the same backend
- **THEN** the opaque child appears in the output at its original position

#### Scenario: Named changes only
- **GIVEN** `tests/data/kicad/tokens/skeleton.kicad_pcb` read with `read_board`
- **WHEN** it is written for target 9 with `write_board`
- **THEN** every opaque child of the text is tree-equal to its source node, except `net` nodes, whose numbers follow the code-point order of the net names

### Requirement: Identifier derivation
`id` MUST be `<prefix>_<uuid>` with the prefix table from the design. For imported objects with a native id, the uuid MUST be `uuid5(FENOLITE_NS, "<backend>:<native_id>")`; for imported objects without native id, `uuid5(FENOLITE_NS, "<backend>:<doc_native_id>:<section>:<content_hash>")`; for created objects, `uuid4` from an injectable seeded generator. A file hash MUST NOT participate in any id.

Placed copies of library definitions are a third case: their ids MUST follow "Placed copies of library definitions", derived from the caller's key and never from the seeded generator, even though the copy is created in memory.

#### Scenario: Same native id, same Fenolite id
- **GIVEN** two imports of the same file
- **WHEN** ids of a footprint with native uuid `a81c…` are compared
- **THEN** they are equal

#### Scenario: Editing another object keeps the id
- **GIVEN** a track without native id in a board
- **WHEN** a different track in the same board is moved and the board is re-imported
- **THEN** the first track's id is unchanged

#### Scenario: Seeded creation is reproducible
- **WHEN** two `Design` objects are created with `seed=7` and the same operations
- **THEN** all ids are identical

#### Scenario: Placed copies ignore the seed
- **GIVEN** two designs created with `seed=7` and `seed=8`
- **WHEN** `Mini_R_0603` is placed in each with key `R1`
- **THEN** the two placed copies have equal ids, while the other created objects of the two designs have different ids
