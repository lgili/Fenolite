# c0423: Altium bodies and models reach KiCad with their pose

## Why

The maintainer's lossless goal for a private Altium board (descriptions only; no board data enters the
repository) found three losses in `convert --to kicad` and a silent import:

- **body, all of them.** `altium_to_kicad.prepare` drops every component body with "the imported body has
  no portable KiCad model file". KiCad has no body: what it shows is a model file. Extruded, cylinder and
  sphere bodies, and model bodies whose model is carried, all count as lost.
- **model, turned about X or Y** (the largest group on that board). `convert.models.placement` refuses
  them because the order of KiCad's turns was not measured (`H-K-MODEL-PLACE` measured Z only).
- **model, bottom side.** Refused because the flip of KiCad's placement was not measured.
- **Import parity.** `import --to python` converts in memory and keeps the conversion's issues, not its
  report, and `body` and `model` give no issue. So the import says nothing about these losses, and its
  library holds only the models that the conversion could place. A silent loss is the worst outcome.

## What

- **Measure KiCad's model pose.** `kicad-cli pcb export stl` of 56 authored probe boards (top and bottom,
  footprint turned 0° and 25°, offsets, turns about X, Y, Z and their combinations), run on the pinned
  9.0.9 image and on the local 10.0.6, fits one transform exactly (every vertex within 1 µm):
  `T(x, −y, face) · Rz(θ) · F · (Rz(−c) · Ry(−b) · Rx(−a) · p + o)`, where `F` is a half turn about X on
  the bottom, `θ` the footprint's angle and `(a, b, c)` and `o` the model's `rotate` and `offset`. Record it
  in `docs/formats/kicad/libraries.md` and `H-K-MODEL-POSE` as `KICAD-VERIFIED (9.0.x, 10.0.x)`.
- **Place every embedded model.** `convert.models` solves that transform for the source's
  (`H-A-BODY-MODEL-PLACE`): any turn, either side. The angles are integer µdeg and the offset is integer nm.
- **Write every body as a model file.** Each body that its model does not carry becomes a STEP file
  written by Fenolite's own writer (`backends.step`, no new dependency), beside the library and named by
  the footprint. An extruded body becomes its prism, a cylinder a faceted cylinder and a sphere a faceted
  sphere, from the record's outline and its two heights. The model type is read from the record
  (`MODEL.MODELTYPE`, S-1604). A shape whose outline or turn does not fit it becomes the prism over its
  outline, as a change with its reason. A body whose model is placed counts as changed ("carried by its
  embedded model").
- **Import parity.** The import keeps every model file and model reference that the conversion writes.
  `body` and `model` losses give `convert.lossy` warnings, which the import keeps, so a loss is never silent.
- **Proof.** An authored PCB document holds every body type: extruded, cylinder, sphere and embedded
  models. Its models are turned about X, Y and Z on the top and the bottom. Its conversion has an empty
  `body` and `model` ledger, and `kicad-cli pcb export stl` on 9.0.9 and 10.0.6 puts every model vertex where
  the source's pose puts it.

## Not in this change

- An exact cylinder or sphere surface. The faceted forms keep the sagitta at 10 µm or less; the writer's
  documented entities are planar.
- Altium's own pose facts. `H-A-BODY-MODEL-PLACE` stays as measured by c0193; no Altium run is part of this
  change.
- Writing bodies into the KiCad board as anything other than model files.
- A body of unknown geometry (`projection_unknown`, no outline, no height): it stays a loss, with its
  reason.
