# Design: Shared pad numbers in authored footprints

`Footprint.pad(number, ..., shared=False)` stays backward-compatible. A first physical land uses the default. Any additional physical land on that same electrical terminal must pass `shared=True`; this is explicit at each repeated declaration. `shared=True` with no previous matching number and an unmarked duplicate both raise `DslError`.

The first pad retains the existing derived-ID key `library:name:pad:number`. Repeated pads use an occurrence suffix starting at `:shared:2`, so unrelated existing definitions remain byte-stable. A slotted padstack ID follows that physical pad's unique key as well. The immutable `FootprintDef` already permits multiple `Pad` records with the same number, and build net assignment already applies the pin's net to every matching pad.

The change touches only the DSL authoring guard/ID derivation, its docs, normative OpenSpec, changelog, and focused tests. The existing backend writer and canonical model need no changes.
