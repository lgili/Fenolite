## ADDED Requirements

### Requirement: Designator candidates on dense boards
For each look of a part, the designator search SHALL try the twelve places beside the box of its own
courtyard at each distance from `--gap` to `--reach` (default 2 mm), in steps of the look's height, nearest
first. With `--over-body` it SHALL then try five places over the box. The looks SHALL be the angles of
`--angles` and the heights from the field's height down to `--min-size` (default: the board's least text
height) in steps of `--size-step` (default 0.1 mm), largest first (change c0493).
- `--sizes`, when given, MUST replace the height steps.
- A height below the board's least text height MUST exit 2, as `--sizes` does today.
- The search MUST stay deterministic: the same board and options give the same places.

#### Scenario: A dense grid of small parts
- **GIVEN** an authored board with a grid of two-pad 0402 parts at 1.2 mm pitch whose courtyards touch,
  and room for designators only one ring further out or at a smaller height
- **WHEN** `fenolite silk <board> --designators --dry-run` runs
- **THEN** every designator is placed, each nearer to its own part than to any other

### Requirement: Clearance model of the designator search
`fenolite silk --designators` SHALL take `--model kicad|altium` (default `kicad`) and place and check the
designators with that model (change c0493).
- In both models, other parts' courtyards MUST add to the cost and MUST NOT block a place.
- `kicad` MUST keep the other obstacles of "Designator placement".
- `altium` MUST judge a text by its ink box shrunk by half its stroke on each side, at least `--clearance`
  (default 0.15 mm) from other silkscreen strokes and texts. It MUST judge a text at least `--mask-clearance`
  (default 0.1 mm) from each pad's mask opening, which is the pad's copper grown by its own solder-mask
  expansion. It MUST NOT judge a text against the silkscreen of its own footprint or against an unplated
  hole. It MUST skip hidden designators.
- `check_designators` MUST judge with the model that placed the texts.
- The reply MUST name the model, and each `altium` rule MUST cite `H-A-SILK-DRC-MODEL`.

#### Scenario: A text over its own outline
- **GIVEN** an authored part whose silkscreen outline leaves room for its designator only across the
  outline, clear of every mask opening
- **WHEN** the search runs with `--model altium`
- **THEN** the designator is placed across its own outline
- **AND** with `--model kicad` it is placed elsewhere or reported unplaced

#### Scenario: Each pad's own mask expansion
- **GIVEN** an authored part with one pad of mask expansion 0.05 mm and one of 0.2 mm
- **WHEN** the search runs with `--model altium`
- **THEN** no placed text comes within the mask clearance of either pad's own opening

### Requirement: Unplaced designators reported
A designator the search cannot place SHALL get one `silk.no-place` naming the part, the obstacle that blocked
its cheapest place and that obstacle's kind: `pad`, `mask`, `hole`, `silk`, `text`, `courtyard`, `edge` or
`outside`. `result.unplaced` SHALL count the unplaced parts per kind (change c0493).

#### Scenario: A part with no room
- **GIVEN** an authored part enclosed by other parts' pads with no free place
- **WHEN** the search runs
- **THEN** the reply holds one `silk.no-place` for it with kind `pad`, and `result.unplaced.pad` is 1

### Requirement: Clip report per footprint
With `--clip`, the reply SHALL list `result.clip.footprints`: one row per footprint whose silkscreen was cut,
with its reference, the strokes cut, the pieces written and the pieces dropped. With `--designators --clip`
the clip SHALL run first, and the designator search SHALL see the clipped silkscreen, in one plan (change
c0493).

#### Scenario: Clip then place
- **GIVEN** an authored part whose outline crosses its pads and blocks every place of its designator
- **WHEN** `fenolite silk <board> --designators --clip --dry-run` runs
- **THEN** `result.clip.footprints` holds the part's row, and the designator is placed where the cut outline
  left room
