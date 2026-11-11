# Tasks: c0484-altium-native-bodies-kept

- [x] 1.1 Carry the body records of each generated model in a conversion to KiCad (`models3d.body_records`,
  `models.place_models`, `models.bodies_text`, `to_kicad`), and write them back in its place
  (`models.read_bodies`, `models.footprint_models`, `lower._place_model`, `pcbdoc.body_records`), with unit
  tests.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_altium_native_bodies_c0484.py -q -n 0`
- [x] 1.2 Maintainer board (private, codes and counts only): F2 and F5 hold 175 model bodies, 18 extruded
  bodies and 3 cylinders, as the source does, and F2-eq and F5-eq exit 0.
  - Result 2026-11-11: source, F2 and F5 each hold 196 body records (175 type 1, 18 type 0, 3 type 2);
    F2-eq and F5-eq exit 0.
- [x] 1.3 The F2 project opens in Altium 24.5 with its bodies drawn as the source's.
  - Result 2026-11-11: Altium 24.5.2.23 opens the source, F2 and F5 boards with 262 components and 196
    component bodies each (175 generic models, 18 extruded, 3 cylinders); the bodies' model type, overall
    height and layer are the same list in all three.
