# Fenolite

**PCB automation in Python, for engineers and AI agents.**

Create PCB projects from code, inspect KiCad and Altium files, and review designs in your browser.
Use the Python library or a CLI with structured JSON results, explicit write plans and conversion loss reports.

[![PyPI version](https://img.shields.io/pypi/v/fenolite.svg)](https://pypi.org/project/fenolite/)
[![CI on main](https://github.com/lgili/Fenolite/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/lgili/Fenolite/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://pypi.org/project/fenolite/)
[![Apache 2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](https://github.com/lgili/Fenolite/blob/main/LICENSE)

[**Get started**](https://github.com/lgili/Fenolite/blob/main/docs/quickstart.md) ·
[Documentation](https://github.com/lgili/Fenolite/blob/main/docs/index.md) ·
[Examples](https://github.com/lgili/Fenolite/tree/main/examples) ·
[What's in 0.5](https://github.com/lgili/Fenolite/blob/main/docs/launch/v0.5.md) ·
[Get help](https://github.com/lgili/Fenolite/issues)

![Fenolite's browser viewer showing the authored routed Blink board, copper layers and project navigation.](https://raw.githubusercontent.com/lgili/Fenolite/main/docs/media/hero.png)

*Actual Fenolite viewer, using a small example authored for this project. No KiCad or Altium installation is needed to view it.*

## Install

Requires **Python 3.11+**. It installs no other package. Heavier features are optional extras.

```bash
python -m pip install fenolite
fenolite capabilities --brief --json
fenolite init blink --confirm --json
fenolite build blink/design.py --out blink/build --confirm --json
fenolite view blink/build --serve
```

Open the local address printed by the viewer. You now have a PCB and a schematic built from
`blink/design.py`, using the built-in component catalog. No external CAD libraries are needed.
These commands create a new `blink` folder; use a fresh location.

This starter is a header, resistor and LED. It is an educational example; choose parts, ratings,
placement and rules for your own circuit before manufacturing. For reviewed write plans, a standalone
HTML export and routing, follow the [quickstart](https://github.com/lgili/Fenolite/blob/main/docs/quickstart.md).

## Three ways to use Fenolite

### Review a design in your browser

Open a KiCad or Altium project, board, schematic or library. Explore layers, highlight nets,
measure geometry and navigate between documents. Export a standalone HTML page for review.

```bash
fenolite view board.kicad_pcb --serve
fenolite view Project.PrjPcb --export review.html --confirm --json
```

![Animated Fenolite viewer demonstration: board selection and cross-probing to the matching schematic.](https://raw.githubusercontent.com/lgili/Fenolite/main/docs/media/viewer-demo.gif)

The animation uses Fenolite's authored Altium Blink fixture. See the
[viewer guide](https://github.com/lgili/Fenolite/blob/main/docs/viewer.md) for supported items,
3D prerequisites and rendering limits.

### Build from Python

Define components, connections, placement and copper in a versioned source file. Build a project
that can also be opened in its CAD editor. Preserve board edits on rebuild and sync placements back to source.

```python
from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("led")
design.board(mm(30), mm(20))
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="330")
d1 = Part("D1", "Fenolite:LED", footprint="Fenolite:Chip_0603", value="LED")
design.add(r1, d1)
connect(Net("LED_A"), r1[2], d1[1])
r1.place(mm(10), mm(10))
d1.place(mm(20), mm(10))
```

This small fragment illustrates the DSL, not a complete powered circuit. Start with the complete
[starter tutorial](https://github.com/lgili/Fenolite/blob/main/docs/quickstart.md), then explore
[authored examples](https://github.com/lgili/Fenolite/tree/main/examples) and the
[Python DSL](https://github.com/lgili/Fenolite/blob/main/docs/dsl.md).

KiCad's CLI provides ERC, DRC, zone fills and fabrication exports. Production routing uses an external
router or copper declared in the script. The built-in `direct` router is for simple demonstrations.

### Convert and compare projects

Convert between KiCad and Altium, or write a KiCad 10 project for KiCad 9. Review what was kept,
changed or lost, with a readback comparison against the source.

```bash
fenolite convert board.PcbDoc --to kicad --out converted --dry-run --json
fenolite equivalent before.kicad_pcb after.kicad_pcb --level 5 --json
```

**Conversions and Altium writes are experimental in 0.5.** Lossy conversion requires explicit consent.
Support depends on the constructs in the input; review the report and the resulting design.
Read the [conversion guide](https://github.com/lgili/Fenolite/blob/main/docs/conversion.md).

## For AI agents

The same commands return structured JSON, typed errors, evidence labels and file receipts.
A write can be previewed with `--dry-run`, then confirmed using its `--plan` identifier.

```bash
fenolite guide start --text
fenolite skill install --help
```

The package includes an agent guide and board-design practice pages. Agents can inspect parts,
query nets and geometry, build, route, check and export using the same CLI as an engineer.
See the [agent guide](https://github.com/lgili/Fenolite/blob/main/src/fenolite/agent/skill/SKILL.md)
and [CLI contract](https://github.com/lgili/Fenolite/blob/main/docs/cli-contract.md).

<details>
<summary>Full build → fabrication command loop (requires KiCad CLI)</summary>

Use a fresh folder for this complete loop. The first six lines need no external CAD tool; fill,
check, export and render require KiCad's CLI. The direct router is a demonstration router.

```fenolite-loop
fenolite capabilities --brief --json
fenolite init blink --confirm --json
fenolite build blink/design.py --out blink/build --dry-run --json
fenolite build blink/design.py --out blink/build --confirm --json
fenolite place blink/build --strategy grid --confirm --json
fenolite route blink/build --router direct --confirm --json
fenolite fill blink/build --confirm --json
fenolite check blink/build --json
fenolite export blink/build -o blink/fab --all --manifest --confirm --json
fenolite render blink/build -o blink/views --svg --png --confirm --json
```

For fabrication exports, BOM and placement tables, see [exports](https://github.com/lgili/Fenolite/blob/main/docs/exports.md)
and [assembly](https://github.com/lgili/Fenolite/blob/main/docs/assembly.md).

</details>

## Support at a glance

> **Status: version 0.5.** Python scripts build KiCad 9/10 PCB and schematic projects. The agent loop
> uses KiCad's ERC/DRC checks; conversion supports KiCad/Altium and the older KiCad major.
> Altium writes and conversions are experimental. See the [release scope and limits](https://github.com/lgili/Fenolite/blob/main/docs/release/v0.5.md).


| Workflow | What you need | Status in 0.5 |
|---|---|---|
| Build the starter; inspect and view supported files | Python 3.11+, browser for the viewer | Shipped; format-specific rendering limits apply |
| KiCad project generation | Python; KiCad 9 or 10 to open in the editor | Shipped |
| KiCad ERC, DRC, fill and fabrication export | `kicad-cli` 9 or 10 | Shipped; engineering review still required |
| External routing | A supported router and its prerequisites | Freerouting and KiCadRoutingTools integrations |
| KiCad/Altium conversion and KiCad downgrade | Requirements vary by direction | Experimental; explicit loss report |
| Altium project generation | Python; Altium for native validation | Experimental |

Linux, macOS and Windows are supported. Optional extras include `geo` for polygon operations
and `kicad-ipc` for a live KiCad session. The MCP server is not part of the published 0.5 package;
development builds include the stdlib-only server, script editing and image replies described in
[MCP documentation](https://github.com/lgili/Fenolite/blob/main/docs/mcp.md). See
[installation and prerequisites](https://github.com/lgili/Fenolite/blob/main/docs/quickstart.md).

The viewer, conversion, board panels, slots and review tools ship in 0.5. Native Draftsman writing and
Embedded Board Arrays remain gated. Detailed scope and deferred checks are in the
[release record](https://github.com/lgili/Fenolite/blob/main/docs/release/v0.5.md).

## Help and contribute

Trying Fenolite on a public or self-authored example? Tell us what worked and where you got stuck.
[Ask a question or report a bug](https://github.com/lgili/Fenolite/issues), including the version,
command and error output. Keep private designs and personal paths out of public reports.

For development, clone [the repository](https://github.com/lgili/Fenolite), run `uv sync --extra dev`
and read [CONTRIBUTING.md](https://github.com/lgili/Fenolite/blob/main/CONTRIBUTING.md).

## License

[Apache-2.0](https://github.com/lgili/Fenolite/blob/main/LICENSE).
Format knowledge comes from public sources under the project's
[clean-room rules](https://github.com/lgili/Fenolite/blob/main/LEGAL.md).
Results carry evidence labels; detailed claims live in the
[evidence matrix](https://github.com/lgili/Fenolite/blob/main/docs/evidence/matrix.md).

*Fenolite* is Portuguese for phenolic board material, the laminate many of us etched our first boards on.
