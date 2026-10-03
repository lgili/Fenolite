# examples

Designs authored for Fenolite (CC0-1.0), used as documentation and as end-to-end tests. Every
example is original work: no file, value, name or layout comes from any organisation's projects.

| example | what it shows |
|---|---|
| `blink_2layer/` | the thin DSL: a mini MCU, a resistor and an LED (bottom side) on a 50 mm × 30 mm two-layer board, from the authored mini library through the folder's own library tables; `fenolite build` turns it into a KiCad 9.0 or 10.0 project |
| `blink_official/` | the same circuit on KiCad's official libraries; DSL source only, built by a `needs_libs` test into a temporary folder |
| `altium_sample/` | the experimental Altium target (`fenolite build … --target altium`): eight parts at the top level and in two modules, a 5 V regulator, a driver with an enable pull-up and an LED, two supplies sharing `GND`, every pin connected by number; its lib ids name `FenoliteSample.SchLib` and `FenoliteSample.PcbLib`, which Fenolite does not ship; the built files are committed under `tests/data/altium/sample/` |
| `altium_kicad/` | the Altium target from KiCad symbols (change c0034): a dual amplifier with common supply pins, a controller with pins on four sides, upright resistors and a connector from the authored CC0 `FenoliteDemo.kicad_sym`, found through the folder's `sym-lib-table`; the build writes their pins and units into `altium_kicad.SchLib`, and the built files are committed under `tests/data/altium/kicad_example/` |
| `altium_hier/` | sheets per module and a signal harness for the Altium target (change c0037, `--altium-sheets modules`): a connector on the top sheet, a controller and a flash memory in two modules, an `SPI` harness between them; `partial.py` adds a harness entry whose net stays on one sheet; the lib ids name `FenoliteHier.SchLib` and `FenoliteHier.PcbLib`, which Fenolite does not ship; the built files are committed under `tests/data/altium/hier/` |
| `altium_hier_board/` | the blink circuit of `blink_2layer/` split into the modules `driver` and `led`, with its board and the same authored libraries, so the Altium build writes a PCB document whose parts link through their sheet symbols |

