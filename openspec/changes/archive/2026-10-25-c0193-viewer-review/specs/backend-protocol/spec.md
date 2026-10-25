## ADDED Requirements

### Requirement: Body models source
`fenolite.backends.base` SHALL define `BodyModel` and the `@runtime_checkable` protocol `BodyModelSource` with `body_models(path: Path) -> tuple[BodyModel, ...]`, through which a reader gives the 3D models that a board file holds for its bodies, which the model does not carry.
- `BodyModel(locator: str, name: str, format: str, data: bytes, position: Point, z: Nm, rotation: tuple[Udeg, Udeg, Udeg])` MUST be a frozen dataclass with slots:
  - `locator`: the provenance locator of the body it belongs to;
  - `format`: `step`;
  - `data`: the model file's bytes;
  - `position`: the board frame of the model;
  - `z`: the height from the face the footprint is on;
  - `rotation`: the angles about x, then y, then z, in a frame of the top face (x right, y the board frame's −y, z out of the top face).
- A model point `p` is placed at `T(position, face ± z) · F(side) · Rz · Ry · Rx · p`. `F` is the identity for a top footprint and a half turn about the x axis for a bottom one, whose model hangs below the bottom face.
- `backends.base` MUST still import only `core` and `model`. `body_models` is not an operation of "Capability reports".

#### Scenario: Altium backend is a body model source
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k body_models` checks `isinstance(AltiumBackend(), BodyModelSource)` and reads the annotations of `BodyModel`
- **THEN** the first is true and every annotation names only builtins, `typing` constructs, `fenolite.core` or `fenolite.model` types
