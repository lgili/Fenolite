# examples

Designs authored for Fenolite (CC0-1.0), used as documentation and as end-to-end tests. Every
example is original work: no file, value, name or layout comes from any organisation's projects.

| example | what it shows |
|---|---|
| `blink_2layer/` | the thin DSL: a mini MCU, a resistor and an LED (bottom side) on a 50 mm × 30 mm two-layer board, from the authored mini library through the folder's own library tables; `fenolite build` turns it into a KiCad 9.0 or 10.0 project |
| `blink_official/` | the same circuit on KiCad's official libraries; DSL source only, built by a `needs_libs` test into a temporary folder |
