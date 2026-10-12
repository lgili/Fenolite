## Why

The Altium layout currently sorts component paths and shelf-packs independent cells. It budgets space
for symbols and labels, but does not express a circuit's functional grouping or signal flow. An agent
therefore has little control between accepting a scattered drawing and arranging native documents
manually. KiCad has a separate readable layout; its behaviour is not an Altium capability.

The maintainer selected functional blocks with automatic flow and alignment as the first priority.
The agent should describe the intended reading order and block membership, while Fenolite performs
the geometry, local connections and collision checks.

## What Changes

- Add an opt-in `blocks` composition mode for generated Altium sheets. Existing cell layout remains
  the default, with unchanged native bytes when composition is not requested.
- Let a design declare named blocks, their members, reading direction, optional anchor component
  and ordering relationships. Blocks organise presentation within existing sheets; they are not
  electrical modules and do not change hierarchy or connections.
- Place related components together using actual connectivity, align their main paths, and arrange
  two-pin branches around relevant pins. Use short, verified local wires where feasible, retaining
  labels for connections that cannot be drawn safely.
- Account for visible text, pins, labels, ports, buses, harnesses and the template's occupied areas.
  Refuse impossible hard constraints instead of hiding collisions or enlarging a fixed sheet.
- Return an actionable composition report and a schematic SVG preview in the reviewed build plan.
  The preview is new schematic output; the existing board `render` command is not repurposed.
- Preserve c0164 snapshot replay and conflict refusal. Changing composition changes the generated
  baseline and must not silently replace a saved native sheet.

## Capabilities

### New Capabilities
- `schematic-composition`: block intent, deterministic composition, local wiring, diagnostics and preview.

### Modified Capabilities
- `design-dsl`: presentation-only block declarations and extraction.
- `altium-schematic-writer`: opt-in composition in the ASCII and binary writers and hierarchy planner.

## Non-goals

PCB placement; changing circuit topology or library pins; detecting circuit function from names;
complete sheet autorouting; moving components between electrical sheets; KiCad integration in this
iteration; incremental merging into c0164 snapshots; an interactive editor; vendor GUI automation;
aesthetic scores that substitute for collision, connectivity or human review.

## Evidence level required

Planning and native schematic output remain `INFERRED`. Authored fixtures must prove determinism,
geometric constraints, stable identities and electrical readback. SVG bounds and text estimates are
Fenolite choices, not proof of Altium font rendering. A native Altium review is recorded separately;
no native acceptance claim is made without it. Reuse existing public format evidence; any new format
fact must first be sourced in `docs/formats/altium/` and `docs/evidence/sources.md`.

## Impact

Changes are limited to presentation requests, composition planning, the Altium schematic emitters,
build diagnostics, documentation and synthetic tests. The core stays stdlib-only. All examples are
authored for Fenolite; no private project, template or derived fixture is used.
