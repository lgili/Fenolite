## ADDED Requirements

### Requirement: Compatibility characters folded
`ascii.fold(text)` SHALL replace each character that is neither 7-bit ASCII nor in Windows-1252 by its Unicode NFKC form
when that form is all in Windows-1252, and SHALL report whether it changed the text. `text_problem(form="binary")`
MUST accept a text whose fold fits. A writer of new text (a library description, a sheet value) MUST write the
folded text in both twins, and MUST give `altium.text-folded` (warning) naming the field, the source text and the
written text; a character that neither fits nor folds MUST be refused by the writer's text check instead of being
written as `?`. `record_bytes` keeps the bytes of a carried text, whose `%UTF8%` twin holds it exactly (change
c0504).

#### Scenario: Degree Celsius in a description
- **GIVEN** an authored design with a part whose description is `-40 ℃`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_text_forms.py -k fold` builds it in the binary form and
  reads it back
- **THEN** the description reads `-40 °C`, its record holds `%UTF8%COMPONENTDESCRIPTION` before
  `COMPONENTDESCRIPTION`, and the issues hold one `altium.text-folded`

#### Scenario: No fold fits
- **WHEN** `text_problem("1 kΩ", form="binary")` judges the text, and a build holds a description `Résistance 1 kΩ`
- **THEN** the reason names U+03A9, and the build is refused with `altium.text-unwritable` and writes nothing

### Requirement: Component description in the binary form
A component's description (`COMPONENTDESCRIPTION`) SHALL be a text that may hold Windows-1252 characters in the binary
form, as the comment and parameter values may. The ASCII form MUST keep refusing it with the reason that the binary
form carries it (change c0504).

#### Scenario: A degree sign kept
- **GIVEN** an authored design with a part whose description is `-40 °C to 125 °C`
- **WHEN** it is built in the binary form and read back
- **THEN** the description returns that string unchanged, with no `altium.text-folded`
