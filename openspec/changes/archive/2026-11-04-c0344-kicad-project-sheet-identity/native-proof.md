# Real native GUI round trip,2026-11-02

KiCad10.0.6 on the maintainer Mac; root operated the real GUI with authorized
computer use. The first sensor v1 failed with AUTO-FIXED brokenfile: the root
schematic UUID stayed9ef0253f, but child instance paths were rewritten to stale
project-template UUIDf5a6a7c7, collapsing R2/R3 and PWR01/PWR02. That artifact was
preserved and rejected; it is not the committed source.

After the runtime binder fix, a fresh pipeline-generated v4 had project cache
UUID/name/filename matching the actual root. The GND global label shape is
explicitly bidirectional in the authored drawing, without relying on a native
repair of an unsupported/default shape.

Root opened the v4 schematic with NO auto-repair alert, saved the root, visited
both ch0/ch1 in the hierarchy tree with title confirmation and saved each,
closed the schematic, opened/saved/closed the board. Post-GUI byte hashes were
captured independently; no manual file patch supplied the passing result.

Post-GUI verify-source returns exit0: levels1–8 andS all equal, differences[] and
accepted[]. Native sch export netlist reports five actual components D1/R1/R2/
R3/U1 and exactly the same pre/post partition: SENSE0={R2.1,U1.17},
SENSE1={R3.1,U1.18}, GND={D1.1,R2.2,R3.2,U1.10}, SIG={R1.1,U1.1},
LED={D1.2,R1.2}, VIN={U1.9}. The committed fixture capture contains ONLY the
following five allowed native files, never local settings, locks or history.

| Captured file | Post-GUI SHA-256 |
|---|---|
| `sensor.kicad_pro` | `00d48c12bc24c829d99420d9058632419465526d7682fb4e7faaebb66c17ba01` |
| `sensor.kicad_sch` | `b26814d8726ca14162dc528a7f5514b55dfe29ed2f8652a42e9aecd0e9b22e43` |
| `sensor.kicad_pcb` | `f0e2c93fdeb7a8c7dccb49e1cce9ba7faaad38819780ac2f0ceb49fb3a48439c` |
| `sensor.kicad_dru` | `c8affc3960050e4932483e2c81f3fc93dc57a56f62b57f863f51d5809ec00ea3` |
| `sheets/channel.kicad_sch` | `207208aab2b0cae00111a9f359e37427af59217c1de4087cdd63ad8f22155c6d` |

All other exact-source CI and release gates remain independent. Source model
entities/schemas did not change. The70 pinned KiCad builds were compared with
the binder enabled/disabled: only each project's top_level_sheets and sheets
identity caches changed; netlist/parity/BOM/PNP and every other unversioned file
remained identical. Only the intentional file digests were updated.

Reproduce the committed source proof with:

```sh
uv run fenolite verify-source tests/data/fidelity/sensor_code/design.py --against tests/data/fidelity/sensor --json
uv run pytest tests/kicad/schematic/test_fidelity_sensor_hierarchy.py -q
```

Expected first command: exit0, all nine levels equal, no accepted/difference rows.
The native test requires KiCad10 and exports a private copy, preserving source
bytes and excluding project-local settings from the committed fixture.
