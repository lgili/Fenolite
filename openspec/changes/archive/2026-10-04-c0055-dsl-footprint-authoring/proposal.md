# c0055: DSL footprint authoring

## Why

Fenolite can assign a library footprint to a part, but a design author cannot create a footprint definition through the public DSL. The roadmap lists a footprint generator and library lint, while c0018 explicitly deferred generation from scratch. This change provides the missing first step so a board can be described from an empty design using only Fenolite's API.

## What Changes

- Add a DSL builder and a design registry for project-authored footprints.
- Resolve assigned authored footprints in the KiCad and experimental Altium build paths.
- Serialize the supported pad and graphic subset to each target's library output.

## Scope

Add a small, typed Python API to define footprint pads and drawing primitives in integer nanometres, register those definitions with a `Design`, and assign them to `Part` instances by library ID. Resolve registered definitions before external libraries in both the KiCad build and experimental Altium target. KiCad builds emit the authored `.kicad_mod` files into the project library and place the same definitions on the board; Altium builds lower the supported subset into the generated PCB library. The feature does not import or convert a source board or footprint library.

Supported authoring starts with SMD and plated through-hole pads and line, rectangle, circle, and polygon graphics. Dimensions, layers, pad numbers and library names are validated; output ordering is deterministic. Existing `Part(..., footprint="Library:Name")` remains the assignment API.

## Non-goals

3D models, custom pad primitives, non-plated holes, footprint lint, automatic pad-number mapping, footprint editors, arbitrary backend features, and changes to the canonical model or `.fenolite` files. Copper routing is a separate design concern. Do not add private board data or part-specific fixtures to Fenolite.

## Evidence level required

Authored KiCad footprint serialization must be `INFERRED` until a public-format source and an independent supported oracle verify it; Altium lowering remains `INFERRED`. Record format facts and sources before claiming `KICAD-VERIFIED` or `ALTIUM-VERIFIED(kit)`. Deterministic API validation and in-memory resolution may be `CORPUS-VERIFIED` using Fenolite-authored examples.
