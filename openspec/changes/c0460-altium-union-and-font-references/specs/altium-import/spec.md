## ADDED Requirements

### Requirement: TrueType texts keep their font

The Altium import SHALL give a text, a footprint text and a designator or comment field read from a text
record of font type 1 the record's font name as `face`, and its bold and italic bytes as `bold` and
`italic`. A text record of any other font type SHALL be read without a face, as before.

#### Scenario: A TrueType designator keeps its font

- **GIVEN** a component whose designator text record has font type 1 and the font name `Arial`
- **WHEN** the document is imported
- **THEN** the footprint's reference field has the face `Arial`

### Requirement: Union members keep their union index

The Altium import SHALL record the non-zero union index of a via (offset 70 of its record), a region (its
`UNIONINDEX`) and a component (its `UNIONINDEX`) in the item's `altium` bag under the key `union_index`.

#### Scenario: A stitching via is a union member

- **GIVEN** a via whose record holds the union index 1048581 at offset 70
- **WHEN** the document is imported
- **THEN** the via's `altium` bag holds `union_index` = `1048581`
