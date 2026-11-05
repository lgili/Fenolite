## ADDED Requirements

### Requirement: Designed gallery pages
`fenolite library gallery` SHALL write an index page with a card grid, a text search and filters by kind and
licence, a light and dark theme and a link to the benchmark page; every card MUST show a thumbnail, the
title, the kind, the licence and the attribution. Each item page MUST show the item's images, the
attribution line, a facts table, the `fenolite get` command with a copy control, the proof result, the
evidence level and links to the item's LICENSE and NOTICE. The site MUST NOT load anything from another
origin.

#### Scenario: Index page structure
- **GIVEN** the release fixture
- **WHEN** the gallery is written
- **THEN** `index.html` holds one card per visible item with its thumbnail, kind and licence, the search
  field, the kind and licence filters and the theme control, and no page refers to another origin

#### Scenario: Item page structure
- **GIVEN** the release fixture
- **WHEN** the gallery is written
- **THEN** the page of the demo footprint holds its image, the facts table with its pad count, the
  `fenolite get` command with a copy button, the proof result and the LICENSE and NOTICE links

### Requirement: Item images drawn by Fenolite
The gallery SHALL draw symbol items as an SVG of the symbol, footprint items as an SVG of their land with
pin 1 marked, and device items as the images of their symbol and footprint side by side. Board views and
block sheets SHALL come from `--renders DIR`; a block's `schematic.kicad_sch` SHALL be drawn by Fenolite,
cropped and without its drawing sheet. The same inputs MUST give the same bytes.

#### Scenario: Images for each kind
- **GIVEN** the release fixture and a renders folder with the board's views and the block's schematic
- **WHEN** the gallery is written with `--renders`
- **THEN** the symbol, footprint, device, board and block pages each show at least one image, and the
  footprint image marks pad 1

#### Scenario: Block sheet drawn by Fenolite
- **GIVEN** a renders folder with the block's `schematic.kicad_sch`
- **WHEN** the gallery is written
- **THEN** the block page shows `schematic.svg` drawn from that sheet, and an unreadable sheet gives a
  placeholder naming the error instead

#### Scenario: Deterministic site
- **GIVEN** the same release, root and renders folder
- **WHEN** the gallery is planned twice
- **THEN** every planned file has the same bytes

### Requirement: Image placeholders
An item whose image cannot be made SHALL get a placeholder that names why, and `result.placeholders` MUST
list the item and the reason; the site is still written.

#### Scenario: Missing board render
- **GIVEN** the release fixture and no renders folder
- **WHEN** the gallery is written
- **THEN** the board page shows a placeholder saying no render was supplied, and `result.placeholders`
  holds the board with that reason
