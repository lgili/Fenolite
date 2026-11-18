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
- A part left without a place SHALL be tried again, once the texts that stay are known, on places every
  quarter of the look's height along each side and between the rings, in at most four rounds; it MAY move
  one placed text, or the text that stays of another part without a place, which then takes that place.
- A designator that keeps its own height and stroke, already below the board's minimum text size, MUST NOT
  stop the write: it is reported with `silk.below-minimum` (warning) and written at its new place. A text
  the search made smaller than the minimum MUST still be `silk.check-failed`.

#### Scenario: Texts already below the minimum
- **GIVEN** the dense grid whose designators are all 0.6 mm high, below the board's 0.8 mm minimum
- **WHEN** `fenolite silk <board> --designators --dry-run` runs
- **THEN** each placed designator keeps 0.6 mm and gets one `silk.below-minimum`, no `silk.check-failed` is
  reported, and the board is planned for writing

#### Scenario: A place between the slots
- **GIVEN** a part whose places above it, centred and flush with either end, meet a line, and walls on its
  other sides
- **WHEN** the search runs
- **THEN** the designator is placed above the part, slid along the side clear of the line

#### Scenario: A dense grid of small parts
- **GIVEN** an authored board with a grid of two-pad 0402 parts at 1.2 mm pitch whose courtyards touch,
  and room for designators only one ring further out or at a smaller height
- **WHEN** `fenolite silk <board> --designators --dry-run` runs
- **THEN** every designator is placed, each nearer to its own part than to any other

### Requirement: Clearance model of the designator search
`fenolite silk --designators` SHALL take `--model kicad|altium` (default `kicad`) and place and check the
designators with that model (change c0493).
- In both models, other parts' courtyards MUST add to the cost and MUST NOT block a place, unless the
  board's `.kicad_dru` holds a `silk_clearance` rule with no condition and no layer clause: KiCad's DRC
  applies it to silkscreen against courtyards, so every courtyard, the part's own included, MUST then be kept
  that rule's `min` away, and `--gap` MUST default to at least it, counted from the courtyard's ink.
- `--clearance` and `--mask-clearance` MUST default to the largest `min` of the board's `silk_clearance`
  rules, else the project's `min_silk_clearance` when above 0, else 0.15 mm and 0.1 mm. An option MUST win.
  `result.settings.sources` MUST say for `clearance`, `mask_clearance`, `gap` and `courtyard` whether the
  value came from an `option`, a `rule`, the `board` setup or the `default`.
- Both models MUST judge a text against the silkscreen of its own footprint.
- `kicad` MUST keep the other obstacles of "Designator placement".
- `altium` MUST judge a text by its ink and by the box Altium measures: from half a stroke left of and below
  the corner the Altium writer stores, `characters × height − height / 3 + 2 × stroke` along the text and
  `height + 1.5 × stroke` up. It MUST keep a text at least `--clearance` from other silkscreen strokes and
  texts, and at least `--mask-clearance` from each pad's mask opening, which is the pad's copper grown by its
  own solder-mask expansion, or the hole of an unplated pad that opens the mask. It MUST NOT judge a text
  against an unplated hole. It MUST skip hidden designators.
- `check_designators` MUST judge with the model that placed the texts.
- The reply MUST name the model, and each `altium` rule MUST cite `H-A-SILK-DRC-MODEL`.

#### Scenario: A text over its own outline
- **GIVEN** an authored part whose silkscreen outline leaves room for its designator only across the
  outline, clear of every mask opening
- **WHEN** the search runs with `--model altium` or `--model kicad`
- **THEN** the designator is reported unplaced with kind `silk`

#### Scenario: Clearances from the board's rules
- **GIVEN** an authored board whose `.kicad_dru` holds `silk_clearance (min 0.2mm)` with no condition
- **WHEN** `fenolite silk <board> --designators --dry-run` runs
- **THEN** `clearance`, `mask_clearance`, `gap` and `courtyard` are 0.2 mm with source `rule`, and every placed
  designator keeps 0.2 mm from every courtyard's ink
- **AND** `--clearance 0.3mm` gives 0.3 mm with source `option`, and without the file the defaults with
  source `default`

#### Scenario: Altium's text box
- **GIVEN** a centred designator placed with `--model altium`
- **WHEN** its box is computed from the corner the Altium writer stores
- **THEN** its ink and that box both keep `--mask-clearance` from each pad's own mask opening

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
