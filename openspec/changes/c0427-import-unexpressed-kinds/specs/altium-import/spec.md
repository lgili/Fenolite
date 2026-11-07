## ADDED Requirements

### Requirement: Board cut-outs across the board shape
The Altium reader SHALL cut the board shape by a board cut-out whose ring has vertices both inside and
outside the shape, when the shape is lines only and the difference is one ring without holes: the shape's
`Edge.Cuts` lines become the ring's, the cut-out is not kept, and `altium.import.cutout-notch` (info) is
reported. Otherwise the shape and the cut-outs SHALL stay as read (change c0427, `H-A-CUTOUT-NOTCH`).

#### Scenario: A cut-out over the edge
- **WHEN** `uv run pytest tests/unit/backends/altium/test_cutout_notch.py -q` reads an authored board whose 3 x 4 mm cut-out crosses its left edge, and one whose cut-out lies inside
- **THEN** the first has eight `Edge.Cuts` lines with the notch and one `altium.import.cutout-notch`, the second keeps its cut-out polygon, and `import --to python` of the first is code with nothing unexpressed and equivalent

### Requirement: Line breaks of texts
The Altium reader SHALL read a CR LF pair in a text's string as one line feed (change c0427,
`H-A-TEXT-CRLF`).

#### Scenario: CR LF
- **WHEN** `uv run pytest tests/unit/backends/altium/test_cutout_notch.py -k crlf -q` runs
- **THEN** `TOP\r\nSIDE` reads as `TOP\nSIDE`
