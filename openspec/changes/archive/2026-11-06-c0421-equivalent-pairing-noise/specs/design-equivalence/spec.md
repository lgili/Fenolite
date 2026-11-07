## ADDED Requirements

### Requirement: Cross-backend side completion
When the two sides of `equivalent` come from different backends and no triangle is asked for, the API SHALL
complete each read design before comparing. A KiCad side with a traced project SHALL carry the project's net
classes and memberships, the custom rules of `<stem>.kicad_dru`, and its footprint graphics and texts as
model entities. An Altium side SHALL carry the flattened outline of each zone whose polygon has an arc vertex,
and the connection, thermal settings and clearance that its Polygon Connect Style and clearance rules govern;
a zone that no polygon record outlines MUST stay as read. The keep-out layers of each side SHALL be passed to
the comparison. Sides of one backend MUST be compared as read. The native project rule context SHALL run only
when both sides are KiCad.

#### Scenario: KiCad project completed
- **GIVEN** a KiCad project with net classes and a `.kicad_dru`, compared with a side of another backend
- **WHEN** the sides are completed
- **THEN** the KiCad design holds the project's classes and the file's rules, and compared with a KiCad side
  it stays as read

#### Scenario: Native context does not refuse another backend
- **GIVEN** a KiCad side whose traced project changed after it was read
- **WHEN** the native rule context runs against a side of another backend
- **THEN** the report is returned unchanged, and two such KiCad sides still refuse

### Requirement: Across-backend comparison
`compare_designs` SHALL take an `across` flag, which `equivalent` sets for sides of two backends. With it
level 6 MUST NOT report: a net class on one side only that holds no net; a net class field that one side
leaves unset; a stack-up layer of kind silkscreen, solder paste or solder mask that the other stack-up does
not state; the letter case of a stack-up layer name; a non-copper layer on one side only that no item of that side uses (a pad counted on its copper
layers); the kind of a paired mechanical and user layer; the order of non-copper layers. With it level 7 MUST
NOT report a hidden footprint field on one side only, nor a field on one side only that the other side's
component holds as a parameter of that name (with the value the field's own component holds, if any). Without the flag each of these MUST be reported as
before. A net class that holds nets, a field both sides state, a dielectric or copper stack-up layer of another
name, a used or copper layer, the copper order, a visible field that names no parameter, and a field whose
parameter value differs MUST still be reported with the flag.

#### Scenario: Unstated against stated
- **GIVEN** side `b` with an extra unused user layer, an extra member-less class, a class field side `a`
  leaves unset, mask stack-up layers side `a` does not state, and a hidden extra footprint field
- **WHEN** levels 6 and 7 run with `across`
- **THEN** nothing of these is reported, and without `across` each is reported

#### Scenario: Real differences across backends
- **GIVEN** with `across` a used extra layer, a copper layer on one side only, a class with nets on one side
  only, a class field both sides state differently, a missing dielectric, swapped copper layers and a visible
  extra field
- **WHEN** levels 6 and 7 run
- **THEN** each is reported

### Requirement: Level 6 rule pairing
Level 6 SHALL identify a rule by its name, by `<name>:<kind>` when one name holds several kinds, and by a
repeat number. A rule named `fenolite_<p>_<slug>`, optionally followed by a repeat or layer suffix, that no
rule of the other side matches by identity SHALL pair with an unmatched rule of the other side of the same
kind, priority `p` and slugged name `<slug>`, preferring the one whose other fields are equal. Such a pair MUST
compare every field except `name` and `priority`. A written name whose priority, slug or kind matches no rule
MUST stay `rule-missing`.

#### Scenario: Written names pair
- **GIVEN** side `a` with rule `GND Clearance` (priority 3) and side `b` with `fenolite_3_gnd_clearance` of
  the same kind
- **WHEN** level 6 runs
- **THEN** no `rule-missing` is reported, and another minimum on side `b` gives one `rule-field`

#### Scenario: Declared format limit
- **GIVEN** side `a` with a rule marked `kept_record=1` that side `b` does not hold
- **WHEN** level 6 runs
- **THEN** it is listed under `excluded` with rule id `declared-limit` and the comparison is equivalent; an
  unmarked rule stays `rule-missing`

#### Scenario: Wrong written priority
- **GIVEN** side `b` names the rule `fenolite_4_gnd_clearance` with priority 4
- **WHEN** level 6 runs
- **THEN** one `rule-missing` is reported on each side

### Requirement: Level 6 layer aliases and keep-out layers
A layer with no same-named layer on the other side SHALL pair with a layer of the other side whose user name
is its name, and level 7 SHALL compare the items of the pair under one name. A keep-out layer passed for a
side and held by that side only MUST NOT give `layer-missing`. A user name that names another layer MUST NOT
pair.

#### Scenario: Mechanical layer under a user name
- **GIVEN** side `a` with layer `Mech.1` holding a line and side `b` with `User.1` named `Mech.1` holding the
  same line
- **WHEN** levels 6 and 7 run
- **THEN** no `layer-missing` and no `graphic-missing` is reported, and a user name `Mech.2` reports both
  layers and both lines

### Requirement: Level 7 representation pairing
Level 7 SHALL pair, given the keep-out layers of a side, each graphic on such a layer with rule areas of the
other side by the area it keeps out (a filled shape's outline, a stroke's band of its width) on every copper
layer, comparing what the drawing keeps out. It SHALL compare the board's `Edge.Cuts` lines, arcs, polygons
and rectangles left unmatched as items that form closed rings as rings. Before level 1 it SHALL take a
board-only footprint with no reference and exactly one NPTH pad as a board hole when the other side holds an
unplated board hole at the pad's board position with its drill. A differing band, ring, position, drill or
reference MUST stay a difference.

#### Scenario: Keep-out band
- **GIVEN** side `a` with a 0.5 mm keep-out line and side `b` with the rule area of its band on both copper
  layers
- **WHEN** level 7 runs
- **THEN** no `keepout-missing` or `graphic-missing` is reported; a band of another width reports
  `keepout-missing` on both sides, and a rule area that allows vias reports one `keepout-field`

#### Scenario: Outline as segments and as a polygon
- **GIVEN** a closed outline drawn as four lines on side `a` and as one polygon on side `b`
- **WHEN** level 7 runs
- **THEN** nothing is reported, and moving one polygon vertex reports one `graphic-missing` per side

#### Scenario: Mounting hole footprint
- **GIVEN** a board hole on side `a` and a board-only footprint with one NPTH pad of the same drill at the
  same place on side `b`
- **WHEN** levels 1 to 7 run
- **THEN** nothing is reported, and another drill or a reference keeps the footprint and reports
  `hole-missing`

### Requirement: Strict level 5 straight arcs
The strict rule SHALL pair an arc of one side left unmatched with a track of the other side left unmatched
when both lie on one copper span, the track's ends are the arc's ends within the length tolerance, and the
arc's mid lies within the length tolerance of their chord; the pair SHALL be compared by the track rule and
counted with the tracks. An arc whose mid lies farther from the chord MUST stay `arc-missing` with the track
`track-missing`.

#### Scenario: Sub-micron arc written as a track
- **GIVEN** a track on side `a` and on side `b` an arc between the same ends whose mid lies 300 nm off the
  chord
- **WHEN** strict level 5 runs with a 1000 nm length tolerance
- **THEN** no `arc-missing` or `track-missing` is reported; without the tolerance, or with the mid 2000 nm
  off the chord, both are reported
