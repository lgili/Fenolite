# Fenolite documentation

Create PCB projects from Python, inspect KiCad and Altium files, and review designs in your browser.

**New here? [Build and view your first board](quickstart.md).** Python 3.11+ is enough for the first example.

## Choose a workflow

| I want to… | Start here |
|---|---|
| Open a project, board, schematic or library in the browser | [Viewer](viewer.md) |
| Choose a built-in symbol or footprint and inspect its source/limits | [Component catalog](catalog/README.md), [coverage and pin mapping](catalog/coverage.md) |
| Place parts from reviewed device records (symbol, footprint, pin map, ratings) | [Devices](devices.md) |
| Read or write library records (pins, packages, devices, parts), versions and licences | [Library records](library-records.md) |
| Choose passives by value and ratings, and let generators pick divider or filter values | [Picking parts](picking.md) |
| Create components, connections, placement and copper in Python | [DSL](dsl.md), [copper](copper.md) |
| Generate a symbol of any size from a pin table | [Symbols from pin tables](symbols.md) |
| Convert KiCad and Altium projects; downgrade KiCad | [Conversion](conversion.md) |
| Turn a KiCad board into Fenolite code | [Import](import.md) |
| Compare designs and check what changed | [Equivalence](equivalence.md) |
| Run electrical and physical checks | [CLI contract](cli-contract.md), [analyses](analyses.md), [net roles](roles.md), [electrical contracts](contracts.md) |
| Preserve editor changes and sync placement into source | [Layout and rebuilds](lens.md) |
| Produce fabrication and assembly files | [Exports](exports.md), [assembly](assembly.md), [drawings](drawings.md) |
| Use my own sheet template | [Sheet templates](sheet-templates.md) |
| Keep a schematic drawn by hand beside the code | [Drawn schematics](drawn-schematic.md) |
| Work with Altium files | [Altium support](altium.md) |
| Let a coding agent use Fenolite | [Packaged agent guide](../src/fenolite/agent/skill/SKILL.md) |

## Examples and reference

- [Examples](../examples): authored circuits and build scripts.
- [What's in 0.5](launch/v0.5.md): a short release overview.
- [Detailed release scope and limits](release/v0.6.md) (0.6; [0.5](release/v0.5.md)).
- [CLI reference and JSON contract](cli-contract.md).
- [Model and units](design-model.md).
- [Evidence matrix](evidence/matrix.md).
- [Changelog](../CHANGELOG.md).
- [Contributing](../CONTRIBUTING.md) and [help](https://github.com/lgili/Fenolite/issues).

## Prerequisites

The core has no runtime package dependencies. Viewing supported files and building the starter do not
require KiCad or Altium. KiCad ERC, DRC, fill and fabrication workflows require `kicad-cli`; external
routers and 3D model meshing have their own prerequisites. The [quickstart](quickstart.md) separates them.
Altium writes and all conversions remain experimental in 0.6; see the input-specific report and limits.
