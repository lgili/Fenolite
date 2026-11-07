## ADDED Requirements

### Requirement: Copper on no net and arcs on one line
The Python import SHALL write a track or an arc on no net as a row of a track or arc table that names no
net, and the build SHALL write that copper on no net. An arc whose start, mid and end lie on one line SHALL
be written as the straight track from its start to its end and reported once as `import.arc-as-track`
(info), which explains its level-5 difference; it SHALL NOT be counted as unexpressed. A via table SHALL
still name its net.

#### Scenario: A board with net-less copper and an arc on one line
- **WHEN** a KiCad board holds a track and an arc on no net and an arc whose three points lie on one line
- **THEN** `fenolite import --to python` exits 0 without `copper-without-net`, `degenerate-arc` or `arc-as-track` unexpressed
- **AND** the built board holds the net-less track and arc, and a track where the arc on one line was

### Requirement: Exact zone names
`Design.zone` with `key` SHALL accept a name that repeats another zone's name or holds surrounding spaces,
and write it as given; without `key` a name SHALL stay unique and without surrounding spaces. The Python
import SHALL write a repeated or padded zone name with `name=` beside the zone's `key=` instead of counting
it as `zone-name`.

#### Scenario: Two zones of one name and a padded name
- **WHEN** a board holds two zones named `Plane` and one named ` Pour `
- **THEN** the import counts no `zone-name` and the built board holds the same three names
