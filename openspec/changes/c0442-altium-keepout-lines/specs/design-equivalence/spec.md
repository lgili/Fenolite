## ADDED Requirements

### Requirement: Form of a drawn keep-out

When both sides of a pair of matched rule areas are drawings of a keep-out layer, level 7 SHALL also
compare their `form`: `stroke` for a track, an arc, a circle or an outline drawn with a width, and `area`
for a filled shape or an outline of width 0. A difference SHALL be one `keepout-field` difference with
field `form`. A drawing against a rule area SHALL compare no form.

#### Scenario: A keep-out line written as a region is reported

- **GIVEN** a board whose Keep-Out layer draws a line, and the same board drawing in its place the filled
  ring that the line's band covers
- **WHEN** the two are compared at level 7 with the Keep-Out layer named a keep-out layer on both sides
- **THEN** there is one `keepout-field` difference, on `form`
