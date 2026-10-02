## ADDED Requirements

### Requirement: Field placements in the DSL
`Part.field(name, *, dx=None, dy=None, rot=None, layer=None, visible=None, size=None, thickness=None, justify=None, outside=None, gap=None, locked=False)` SHALL record one placement request for the field `name` of the part's footprint, and `dsl.fields(design) -> Mapping[str, tuple[FieldRequest, ...]]` SHALL return the requests of every added part, keyed by component path in path order, each tuple in name order.
- `name` MUST be `"Reference"` or `"Value"`.
- `dx` and `dy` are lengths ("DSL lengths and angles") in the board frame of "Board and placements in the DSL", measured from the part's placement point, and MUST be given together. `rot` is the field's angle on the board, in degrees, normalised to [0°, 360°).
- `layer` is `"silk"` or `"fab"`, on the part's side. `size` and `thickness` are positive lengths; `size` gives both the glyph width and height. `justify` is one or two words: `left` or `right` first, then `top` or `bottom`. `visible` and `locked` are bools.
- `outside` is `"top"`, `"bottom"`, `"left"` or `"right"`. With it, `dx`, `dy`, `rot` and `justify` MUST be `None`. `gap` is a length of at least 0 and is allowed only with `outside`.
- `DslError` MUST be raised at the call for another name, for a second `field()` call for the same name of one part, for a request that sets nothing, and for any value outside these rules.
- `FieldRequest` is a frozen dataclass with `name`, `dx`, `dy`, `rotation`, `layer`, `visible`, `size`, `thickness`, `justify`, `outside`, `gap` and `locked`, with lengths in nm, angles in µdeg and `None` for every value not given.
- `fenolite.dsl` MUST also re-export `FieldRequest` and `fields`, as "DSL package" allows, and the package keeps importing only the standard library, `core` and `model`.

#### Scenario: Requests recorded
- **GIVEN** `r1.field("Reference", outside="top", gap=mm(0.3))` and `r1.field("Value", visible=False)`
- **WHEN** `fields(design)["R1"]` is read
- **THEN** it holds the `Reference` request with `outside == "top"` and `gap == 300_000`, then the `Value` request with `visible == False`, each with `locked == False` and `None` for every other value

#### Scenario: Offset in the board frame
- **GIVEN** `u1.field("Reference", dx=mm(0), dy="-2.5mm", rot=-90, justify="left bottom", locked=True)`
- **WHEN** `fields(design)["U1"]` is read
- **THEN** its request has `dx == 0`, `dy == -2_500_000`, `rotation == 270_000_000`, `justify == "left bottom"` and `locked == True`

#### Scenario: Refused calls
- **WHEN** `r1.field("MPN", visible=True)`, `r1.field("Reference", dx=mm(1))`, `r1.field("Reference", outside="top", dx=mm(1), dy=mm(0))`, `r1.field("Reference", justify="middle")`, `r1.field("Reference")` and `r1.field("Reference", dx=1, dy=2)` are called
- **THEN** each call raises `DslError`

#### Scenario: Second request for one field
- **WHEN** `r1.field("Value", visible=False)` is called twice
- **THEN** the second call raises `DslError` naming `R1` and `Value`

#### Scenario: Import edges
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes with no `ALLOWED` change, and every import inside `src/fenolite/dsl/` is of the standard library, `fenolite.core` or `fenolite.model`

### Requirement: Field placements in a build
`lens.build.build_design` SHALL accept the keyword argument `fields: Mapping[str, Sequence[FieldRequestLike]]`, empty by default, and `cmd_build` SHALL pass `dsl.fields(design)`. `FieldRequestLike` is the structural protocol of `FieldRequest`, defined in `lens.fields`.
- After each part is placed or staged, and before its pad nets are assigned, the requests of its component path MUST be applied with `lens.fields.apply_requests(instance, requests)`, in name order, through the helpers of `kicad-file-backend` "Footprint field helpers". For each request:
  - `dx` and `dy` set the anchor `instance.position + (dx, dy)`, and `rotation` sets the board angle, through `set_field`;
  - `layer` sets `F.SilkS` or `B.SilkS` for `silk` and `F.Fab` or `B.Fab` for `fab`, by the part's side, and sets `mirrored` to whether the part is on the bottom side;
  - `visible`, `size` (as `Size(size, size)`), `thickness` and `justify` are set as given;
  - `outside` then calls `place_outside(…, side=outside, gap=gap)`, with `DEFAULT_GAP` when `gap` is `None`;
  - a value that is not given keeps the library's.
- A request for a field that the placed footprint does not hold MUST raise `FormatError` (`FEN-3004`) naming the footprint's lib id and the field.
- Every request MUST apply to the built copy, locked or not; on an existing board, `layout-lens` "Footprint fields across rebuilds" decides which survive.
- Applied requests add no issue.
- The keyword and its step are additions that "Built project files" allows, and the call of `cmd_build` one that "Build command" allows; without requests the build is the one they define.

#### Scenario: Reference above a part
- **GIVEN** a blink variant whose `design.py` calls `r1.field("Reference", outside="top")`
- **WHEN** it is built for target 10 into an empty folder and the board is read with `read_board`
- **THEN** `R1`'s `Reference` field has board angle 0, `v_justify == "bottom"` and `h_justify == "center"`, and equals the field that `place_outside(r1, "Reference", side="top")` gives for `R1`'s footprint in that board

#### Scenario: Hidden value of a bottom part
- **GIVEN** the blink, whose `D1` is on the bottom side, with `d1.field("Value", visible=False, layer="silk")`
- **WHEN** it is built for target 9 and the board is read back
- **THEN** `D1`'s `Value` field has `visible == False`, layer `B.SilkS` and `mirrored == True`

#### Scenario: Offset of a rotated part
- **GIVEN** a blink variant whose `U1` is placed with `rot=90` and calls `u1.field("Reference", dx=mm(0), dy=mm(-5), rot=0)`
- **WHEN** it is built and the board is read back
- **THEN** `field_anchor` of `U1`'s `Reference` equals `U1`'s position plus (0, −5 mm), and `field_angle` is 0

#### Scenario: Library without the field
- **GIVEN** a blink variant written in the test to `V/design.py`, whose `R1` uses a footprint authored in the test without a `Value` property and calls `r1.field("Value", visible=False)`
- **WHEN** `fenolite build V/design.py --out B --dry-run --json` runs
- **THEN** the exit code is 3, stderr carries `FEN-3004` naming the lib id and `Value`, and nothing is written

#### Scenario: Reproducible field placement
- **GIVEN** the variant of "Reference above a part"
- **WHEN** it is built twice into two empty folders
- **THEN** every file of the two folders has the same bytes
