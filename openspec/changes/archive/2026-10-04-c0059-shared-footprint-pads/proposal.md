# Proposal: Shared pad numbers in authored footprints

## Why

Some packages expose one electrical terminal through more than one physical copper land, such as a lead and an exposed tab, or two mechanically separated contacts that are electrically common. Fenolite's model and KiCad writer support repeated pad numbers, but `Footprint.pad()` currently rejects them, so the DSL cannot author these packages.

## What Changes

- Allow an explicit `shared=True` on `Footprint.pad()` to declare a later physical pad with the same number as an existing pad.
- Keep duplicate numbers rejected by default and reject `shared=True` when no earlier pad has that number.
- Give repeated physical pads stable, unique model IDs while keeping existing IDs unchanged for footprints with unique pad numbers.
- Add tests for validation, deterministic identity, and writer/reader round-trip.

## Non-goals

- Changing `Part.pad_map` or allowing a symbol pin to map to several differently numbered pads.
- Importing existing board geometry or generating package geometry automatically.
- Changing electrical net assignment: the existing build rule already gives every pad with the mapped number the same net.

## Evidence level required

Fenolite-authored unit tests must prove DSL behavior and deterministic KiCad footprint serialization without calling `kicad-cli`.
