# Altium schematic connectivity as the import computes it

This page states, in Fenolite's own words, the rules by which `fenolite.backends.altium.adapter`
(modules `connectivity` and `netlist`, change c0043) derives nets from the drawing objects of Altium
schematic sheets. A sheet stores no netlist: nets follow from wires, junctions, electrical points and names,
and from the net identifier scope of the project.

- Sources: Altium's documentation on connectivity and multi-sheet designs (S-0185), on net labels, power
  ports and pins (S-0140), on signal harnesses (S-0186) and on buses (S-0301); the record page of a public
  converter (S-0130); KiCad's schematic importer, read for facts only and never transcribed (S-0131); the
  component link of a PCB document (S-0164); and two public projects saved by Altium Designer (S-0187,
  S-0188), fetched into the corpus cache and never committed.
- KiCad's importer converts drawings and lets KiCad's own netlister decide, so its connection rules are
  KiCad's. It is a source here only for where the electrical point of a record lies.
- All arithmetic is on `SchLength.value`, an integer count of 1/100 000 of the 10-mil unit. "Lies on a
  segment" is a zero cross product and a position inside the segment's box. No tolerance is used: no source
  states one.
- The umbrella test is `H-A-IMP-NETLIST` (`tests/corpus/test_altium_import.py -k project_sets`): the
  netlist computed from the sheets of a public project equals the pad netlist of its PCB document. A rule
  that a passing set exercises is supported by it; a rule that no set exercises stays `INFERRED`.

## Electrical points

| fact | source | label | hypothesis |
|---|---|---|---|
| A pin has one electrical point: its end away from the body, `LOCATION` moved by `PINLENGTH` in the pin's direction (`Pin.hot_end`) | S-0140, S-0130, sets of S-0187, S-0174, S-0176, S-0175 (files kept outside the repository) | CORPUS-VERIFIED (4 sets of 4 repositories; 2026-10-05) | H-A-IMP-NETLIST |
| A net label has one electrical point, its location, which is its lower-left corner; it must touch a wire, a bus or a signal harness | S-0140, S-0185 | INFERRED | H-A-SCH-NETS |
| A power port, a junction and a No ERC directive have one electrical point: their location | S-0140, S-0130 | INFERRED | H-A-SCH-NETS |
| A port has two electrical points: its location and the point `WIDTH` further along it, along X for the styles 0 to 3 and along Y for the styles 4 to 7. In the sets, 80 ports are wired at the far end along X and 14 at the location; the sets of two repositories that hold wired ports agree (S-0187, S-0175), and no port of the sets was found wired along Y | S-0130, S-0187, S-0188, S-0175 | INFERRED | H-A-IMP-PORT-ENDS |
| A sheet entry has one electrical point, on the edge of its sheet symbol that `SIDE` names, at its distance from the top-left corner. In the two hierarchical sets every one of the 251 sheet entries (sides 0 and 1) lies on a wire end or on a harness line end | S-0130, S-0131, S-0187, S-0188 | INFERRED | H-A-SCH-HIER-COMPILE |
| A harness entry has one electrical point, on the edge of its connector that `SIDE` names; the connector has one connection point, on the side `HARNESSCONNECTORSIDE` names, `PRIMARYCONNECTIONPOSITION` units below the top-left corner | S-0131, S-0187, S-0188 | INFERRED | H-A-SCH-HARN-NETS |
| Only the pins shown for a placed part's own part number and display mode take part; a pin of a part that is not placed is on no net | S-0130, S-0131 | INFERRED | H-A-SCH-NETS |

## Wires, junctions and points

| fact | source | label | hypothesis |
|---|---|---|---|
| A wire end that lies on a segment of another wire connects the two wires (a T joint), without a stored junction: Altium adds the junction when it compiles. 254 such ends in the four sets that agree | S-0185, sets of S-0187, S-0174, S-0176, S-0175 (files kept outside the repository) | CORPUS-VERIFIED (4 sets of 4 repositories; 2026-10-05) | H-A-IMP-WIRE |
| Two segments that cross at a point interior to both connect only when a junction record (record 29) lies on that point. 270 crossings without a junction in three of the four sets that agree (S-0187, S-0176, S-0175): none joins two nets of the PCB document | S-0185, S-0130, sets of S-0187, S-0176, S-0175 (files kept outside the repository) | CORPUS-VERIFIED (3 sets of 3 repositories; 2026-10-05) | H-A-IMP-WIRE |
| Collinear segments that overlap connect; so do two wires that share an end point | S-0185 | INFERRED | H-A-IMP-WIRE |
| An electrical point connects to a wire when it lies on one of its segments, its ends included; no source states the case of a point inside a segment, so it is a choice of this page. No pin end of the five sets lies inside a segment (every pin on a wire is on one of its vertices), so no set exercises it | S-0185 | INFERRED | H-A-IMP-PIN-MID |
| Two electrical points at one position connect (a pin end on a pin end, a power port on a pin end) | S-0185 | INFERRED | H-A-IMP-WIRE |
| A bus (record 26), a bus entry (record 37) and a signal harness line (record 218) are not wires: they join no net by themselves | S-0301, S-0186, S-0130 | INFERRED | H-A-IMP-BUS |
| A pin whose electrical point holds a No ERC directive, and whose net holds nothing else, is a pin left open on purpose: it is a no-connect mark and is on no net (106 such pins in the five sets) | S-0130, S-0185 | INFERRED | H-A-SCH-NETS |
| A net without an identifier that holds fewer than two pins is no net: an unconnected pin, with or without a wire stub, has a pad without a net in the PCB document | S-0185, sets of S-0187, S-0174, S-0176, S-0175 (files kept outside the repository) | CORPUS-VERIFIED (4 sets of 4 repositories; 2026-10-05) | H-A-IMP-NETLIST |

## Names within a sheet

| fact | source | label | hypothesis |
|---|---|---|---|
| Net labels with one text join their nets within the sheet (399 labels repeat a name in the four sets that agree) | S-0185, sets of S-0187, S-0174, S-0176, S-0175 (files kept outside the repository) | CORPUS-VERIFIED (4 sets of 4 repositories; 2026-10-05) | H-A-IMP-WIRE |
| Names are compared without letter case. Two labels of one set differ from another label by letter case only, and their nets are one net of the PCB document; one repository does not carry a label | S-0185, S-0187 | INFERRED | H-A-IMP-WIRE |
| Power ports with one text join their nets within the sheet | S-0140, S-0185 | INFERRED | H-A-SCH-NETS |
| Identifiers of different kinds never join by name: a net label `GND` and a power port `GND` on nets that no wire joins are two nets. No sheet of the five sets holds a label and a power port of one name, so no set exercises it | S-0185 | INFERRED | H-A-IMP-DUP-NAME |
| Hidden pins with a net name: neither S-0130 nor S-0131 is recorded on a fact page with the key that holds the name, and S-0185 says that current Altium no longer supports a hidden pin with a pre-assigned net. No key is typed; a hidden pin joins by its position like any pin | S-0185 | INFERRED | H-A-IMP-HIDDEN-PIN |

## Net identifier scope

| fact | source | label | hypothesis |
|---|---|---|---|
| The scopes are Automatic, Flat, Hierarchical, Strict Hierarchical and Global. Automatic is hierarchical when the top sheet holds a sheet entry, else flat when a sheet holds a port, else global. The five projects hold `HierarchyMode=0`; the rule chooses hierarchical for two (S-0187, S-0188), flat for one (S-0175) and global for two (S-0174, S-0176), and the four sets that agree cover all three | S-0185, sets of S-0187, S-0174, S-0176, S-0175 (files kept outside the repository) | CORPUS-VERIFIED (4 sets of 4 repositories; 2026-10-05) | H-A-IMP-SCOPE |
| The top sheets are the sheets that no sheet symbol names | S-0185 | INFERRED | H-A-IMP-SCOPE |
| Power ports of one name join across every sheet, except in the strict hierarchical scope, where they join within a sheet only | S-0140, S-0185 | INFERRED | H-A-SCH-NETS |
| In the hierarchical scopes a power port on a net that also holds a port stays local to its sheet. One set holds 66 such nets (S-0187) and agrees; one repository does not carry a label | S-0185, S-0187 | INFERRED | H-A-IMP-POWER-LOCAL |
| Net labels join across sheets only in the global scope | S-0185 | INFERRED | H-A-IMP-SCOPE |
| In the flat and the global scope, ports of one name join across every sheet | S-0185 | INFERRED | H-A-IMP-SCOPE |
| In the hierarchical scopes a port joins only the sheet entry of the same name on each sheet symbol whose file name names the port's sheet | S-0185 | INFERRED | H-A-SCH-HIER-COMPILE |
| An off-sheet connector is a power port record with `ISCROSSSHEETCONNECTOR`; off-sheet connectors of one name join across the sheets that descend from one parent sheet symbol, in every scope. No sheet of the five sets holds one | S-0185, S-0130 | INFERRED | H-A-IMP-OFFSHEET |
| A sheet symbol's file name names its sheet by file name, without folder and without letter case; a name with `;` lists several sheets; a sheet named by several symbols is one instance per symbol | S-0185 | INFERRED | H-A-SCH-HIER-COMPILE |

## Net names

| fact | source | label | hypothesis |
|---|---|---|---|
| A net with several identifiers takes its name by kind: net labels, then power ports, then ports, then sheet entries; with "Power Port Names Take Priority", power ports come first. Ports and sheet entries name a net only with their options | S-0185 | INFERRED | H-A-IMP-NAME-TIE |
| With "Higher Level Names Take Priority" a candidate of a sheet nearer the top wins; among equal candidates the smallest text wins, a choice of this page | S-0185 | INFERRED | H-A-IMP-NAME-TIE |
| A net without an identifier is named after one of its pins, `Net<ref>_<pin>`; the page takes the first pin by reference and then by designator, in natural order | S-0185 | INFERRED | H-A-IMP-NAME-AUTO |
| Two nets that end with one name stay two nets: the model needs unique names, so the later one is renamed `<name>#<k>` | S-0185 | INFERRED | H-A-IMP-DUP-NAME |

## Buses and harnesses

| fact | source | label | hypothesis |
|---|---|---|---|
| A bus identifier is a net label, a port or a sheet entry whose text is `<name>[<a>..<b>]`; its members are the nets `<name><i>` for `i` from `a` to `b`, rising or falling | S-0301 | INFERRED | H-A-IMP-BUS |
| A bus needs a net label on its line; the member nets are the nets that net labels `<name><i>` name, and a bus entry is graphics | S-0301 | INFERRED | H-A-IMP-BUS |
| A bus port and the sheet entry of the same text join their members by position, member `k` with member `k` | S-0301, S-0185 | INFERRED | H-A-IMP-BUS |
| Within a harness group (signal harness lines connected as wires, the connectors on them, their ports and sheet entries), the harness entries of one name are one net. 95 harness connectors in two sets (S-0187 agrees on all 427 nets; S-0188 on 156 of 158) | S-0186, S-0187, S-0188 | INFERRED | H-A-SCH-HARN-NETS |
| A port or a sheet entry carries a harness when it touches a signal harness line or the connection point of a harness connector, whether or not its record holds `HARNESSTYPE`: 11 sheet entries of one set lie on harness line ends without that key | S-0187, S-0186 | INFERRED | H-A-SCH-HARN-NETS |
| A net label `<harness>.<entry>` on a wire names the member `<entry>` of the harness that goes by `<harness>` on that sheet (the net label on its harness line, or the name of its port or sheet entry). One sheet holds 13 such labels and no connector for them; joined this way, its nets are those of the PCB document | S-0188, S-0186 | INFERRED | H-A-SCH-HARN-NETS |
| A harness member without a net label is named `<harness>.<entry>`, a choice of this page | S-0186 | INFERRED | H-A-IMP-HARN-NAME |

## Component link

| fact | source | label | hypothesis |
|---|---|---|---|
| A PCB component's `SOURCEUNIQUEID` is `\<sheet symbol id>…\<component id>`: the unique ids of the sheet symbols from the top sheet, then the unique id of one part of the schematic component. All 879 components of the five sets link by that path, none by designator, through one and two levels and through a sheet instantiated twelve times | S-0164, sets of S-0187, S-0188, S-0174, S-0176, S-0175 (files kept outside the repository) | CORPUS-VERIFIED (5 sets of 5 repositories; 2026-10-05) | H-A-IMP-LINK |
| A footprint model maps a pin to its pads (records 46 and 47): 111 map records of two sets name a pad other than the pin's designator or several pads. The comparison of the sets applies the map; the model's components do not carry it yet | S-0130, S-0187, S-0188 | INFERRED | H-A-IMP-LINK |
| The map of the current footprint model of a component is carried by the imported component (change c0083): a record whose `DESINTF` is the designator of a pin and whose one `DESIMP` names another pad gives the pair (pin, pad) of `Component.pin_pad_map`, and the comparisons name the pin by that pad. In the one set with such records, 5 records of one component name one other pad each and the board's pads carry those names; a sixth pin of it lists four pads | S-0130, set of S-0188 (files kept outside the repository) | INFERRED | H-A-IMP-PINMAP |
| A record that lists several pads, no pad, or a pad that another pin already stands for cannot be said by a map of one pad per pin: the pin keeps its own designator when the record lists it, else it takes the first pad listed, and the whole record is kept in the component's bag (`pin_pads`); `altium.import.pin-map` counts them (2 in the set of S-0188: pins that list two and four pads). A record whose `DESINTF` names no pin of the component is left out: 55 records of the set of S-0187 have an empty `DESINTF` and one `DESIMP` of the text `null` | S-0130, sets of S-0187, S-0188 | INFERRED | H-A-IMP-PINMAP |

## Channels

A sheet that several sheet symbols name is one channel per symbol, and a sheet symbol whose designator
is a `Repeat` statement is one channel per index (change c0083).

| fact | source | label | hypothesis |
|---|---|---|---|
| A board component of a channel links to its sheet component by the unique-id path through the channel's sheet symbol; its `SOURCEDESIGNATOR` is the sheet's designator, equal for all channels, and the designator shown on the board is the channel's | S-0164, set of S-0188 (files kept outside the repository) | CORPUS-VERIFIED (1 set; 2026-10-06) | H-A-IMP-RPT-BOARD |
| The project file's `[Design]` holds `ChannelDesignatorFormatString`, `ChannelRoomNamingStyle` and `ChannelRoomLevelSeperator` (spelled so). With `$Component_$RoomName`, style `0` and separator `_`, the 84 channel components of the set are named `<designator>_<designator of the channel's sheet symbol>`, as its board names them | S-0452, set of S-0188 | CORPUS-VERIFIED (1 set; 2026-10-06) | H-A-IMP-RPT-FORMAT |
| A designator format is text with the keywords `$Component`, `$ComponentPrefix`, `$ComponentIndex`, `$RoomName`, `$ChannelPrefix`, `$ChannelIndex` and `$ChannelAlpha`; eight formats are predefined. Two room naming styles are flat (the room is named by the channel alone) and three join the sheet symbols of the path with the level separator | S-0452 | INFERRED | H-A-IMP-RPT-FORMAT |
| The numbers `0` and `1` of `ChannelRoomNamingStyle` are the two flat styles and `2` to `4` the three path styles, in the order the documentation lists them | S-0452 (order of the page), set of S-0188 (style `0` only) | INFERRED | H-A-IMP-RPT-FORMAT |
| A sheet symbol whose designator is `Repeat(<channel identifier>, <first index>, <last index>)` stands for one channel of its sheet per index from the first to the last; the last index is above the first, no index is negative, and the first may be any number, 0 included. No public file of the corpus holds such a statement: the import reads it from the designator text of the sheet symbol (record 32), where a sheet symbol's designator is | S-0520 | INFERRED | H-A-IMP-RPT-COUNT |
| A sheet entry named `Repeat(<NAME>)` connects each channel to one member of the bus `<NAME>` of the parent sheet: the first channel to the first member, the second to the second, and so on; a sheet entry of any other name is one net for all channels | S-0520 | INFERRED | H-A-IMP-RPT-NETS |
| `$ChannelPrefix` is the designator of the sheet symbol, for a `Repeat` statement its channel identifier; `$ChannelIndex` is the channel index; `$ChannelAlpha` is the channel index "expressed as a character"; a channel of a `Repeat` statement is named by the identifier followed by the index (`CIN1`). The page reads the character as `A` for 1 to `Z` for 26, a choice of this page; no source gives a character to another index | S-0520 | INFERRED | H-A-IMP-RPT-FORMAT |
| The five room naming styles are, in the order of the documentation, flat numeric with names, flat alpha with names, numeric name path, alpha name path and mixed name path; a path style joins the channel names of every sheet symbol of the path (identifier and index). The page takes "numeric" as the index written as a number and "alpha" as the character of `$ChannelAlpha`; what the mixed style writes for a `Repeat` channel is `UNKNOWN` | S-0452, S-0520 | INFERRED | H-A-IMP-RPT-FORMAT |
| A net without an identifier that lies inside one channel takes its system name from the channel's designator, `Net<channel designator>_<pin>`: the board of the set names its 24 such nets so (`NetD9_11_A`) | S-0185, set of S-0188 (files kept outside the repository) | CORPUS-VERIFIED (1 set; 2026-10-06) | H-A-IMP-RPT-NETS |
| The designator format also names the nets inside a channel. That a net label local to a channel is renamed by the format as a designator is (`MID_CH1`) is the reading of this page: no file of the corpus holds such a label | S-0520 | INFERRED | H-A-IMP-RPT-NETS |
| The documentation writes the unique-id path of a board component as `\SheetSymbolUID\SchComponentUID` for several sheet symbols and as `\ChannelIndex+SheetSymbolUID\SchComponentUID` for a `Repeat` statement, without an example. How the index and the unique id are joined is `UNKNOWN`: no public file shows such a path | S-0520 | UNKNOWN | H-A-IMP-RPT-COUNT |

- **What the import resolves.** `$Component`, `$ComponentPrefix`, `$ComponentIndex`, `$ChannelPrefix` (the
  designator of the channel's sheet symbol, the channel identifier of a `Repeat` statement) and
  `$RoomName`; for a channel of a `Repeat` statement also `$ChannelIndex` and `$ChannelAlpha` (indexes 1
  to 26). A plain sheet symbol has no index: there a format with one of the two, like a `$` that starts no
  keyword and a style outside `0` to `4`, is not guessed (`altium.import.channel-naming`, names
  `<designator>@<channel>`). Neither is, for a `Repeat` channel: the mixed style, a flat style under a
  `Repeat` statement higher up (two rooms would get one name), and a format without `$RoomName`,
  `$ChannelIndex` and `$ChannelAlpha` (two channels would get one designator).
- **Ids of a `Repeat` channel.** A `Repeat` statement has one unique id for all its channels. The import
  names channel `i` of the sheet symbol `<uid>` by `<uid>[<i>]` in its native ids
  (`cmp:\<uid>[<i>]\<component uid>`, `module:\<uid>[<i>]`), a form of this import and not Altium's; the
  module is named `<identifier>[<i>]` and its bag holds `sheet_symbol` and `channel_index`.
- **Board link of a `Repeat` channel.** No path is tried: the form is `UNKNOWN` (row above). A board
  component links to a component of a `Repeat` channel only when its own designator is the channel
  designator of the format and its `SOURCEDESIGNATOR` the designator of the sheet
  (`altium.import.linked-by-designator`); the components left without a board component are counted by
  `altium.import.channel-naming`.
- **Nets of a `Repeat` channel.** A sheet entry `Repeat(NAME)` joins the port `NAME` of channel `k`
  (counted from 0) to member `k`, in identifier order, of the bus identifier `NAME[a..b]` of the parent
  sheet: the one on the bus line the entry lies on, else another net label of that bus name. A missing bus
  and a bus with fewer members than channels give `altium.import.channel-naming`. The statement never
  names a net.
- **Order of sources.** The board first (`project.link`), then the format. The annotation file of a
  project is not read: the one annotation file that a corpus project lists (set of S-0188) is empty at
  the registered commit (0 bytes, measured on 2026-10-06), so the form of such a file is `UNKNOWN`. An
  absent or empty one changes nothing.
- **Not instantiated.** A `Repeat(…)` statement that has not the form above, whose first index is above
  its last, or whose channels would bring the project above 256 sheet instances (`MAX_CHANNELS`, a bound of
  this import) gives one instance (`altium.import.repeated-sheet`).

## Result per project set

`tests/corpus/test_altium_import.py -k project_sets` (2026-10-05, macOS, local corpus cache, with
`FENOLITE_HEAVY=1` for set 01, whose PCB document is a heavy row): 5 passed. Counts and row ids only. A pair
`(component, pad)` is compared when the sheets hold the pin and the PCB document the pad; a pin stands for
its pads through the pin-to-pad map of its footprint model.

| set | project row | sheets (instances) | scope | nets (PCB document) | linked by path | by designator | equal by members | also by name | differing groups | pads without a pin | result |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `altium-set:01` | `altium-third-party-prjpcb-01` (S-0187) | 18 (18) | hierarchical | 447 (427) | 540 | 0 | 427 | 425 | 0 | 40 | agrees |
| `altium-set:02` | `altium-third-party-prjpcb-02` (S-0188) | 13 (24) | hierarchical | 163 (158) | 248 | 0 | 156 | 116 | 6 | 18 | known difference |
| `altium-set:03` | `altium-third-party-prjpcb-04` (S-0174) | 1 (1) | global | 30 (30) | 23 | 0 | 30 | 30 | 0 | 0 | agrees |
| `altium-set:04` | `altium-third-party-prjpcb-05` (S-0176) | 1 (1) | global | 34 (34) | 41 | 0 | 34 | 34 | 0 | 4 | agrees |
| `altium-set:05` | `altium-third-party-prjpcb-06` (S-0175) | 4 (4) | flat | 18 (18) | 27 | 0 | 18 | 18 | 0 | 0 | agrees |

- **Set 02, the known difference.** Two pins of two four-pin components are unwired on the sheet
  `altium-third-party-schdoc-02` (no wire, label or port within 15 units of either end) and carry a net in
  `altium-third-party-pcbdoc-01`. Each gives three differing groups: the sheet's net without the pin, the
  pin alone, and the PCB document's net with it. Every other net of the set agrees. The cause lies in the
  project's own files, not in a rule of this page, so the set carries `altium-import:known-diff` and the
  rules that only it exercises (a sheet instantiated more than once, dotted harness labels) stay `INFERRED`.
- **More schematic nets than PCB nets.** The sheets name nets that hold no pad (a label on a stub) and, in
  set 02, the nets of a sheet that twelve sheet symbols name once per instance.
- **Names.** In the four sets that agree, 507 of 509 nets of the PCB document have the name the import
  gives them, the system names `Net<ref>_<pin>` included (124 nets of those sheets carry one); `H-A-IMP-NAME-TIE` and
  `H-A-IMP-NAME-AUTO` stay `INFERRED` by this change's evidence table (names are supporting data). In set
  02, 116 nets have the board's name since 2026-10-06 (92 before): the 24 nets without an identifier inside
  one channel are now named after the channel's designator (change c0083), and `altium.import.duplicate-net-name`
  is given 23 times instead of 45. The other nets of the repeated sheet still differ by name.
- **Census of the rules exercised**, summed over the five sets: junctions 735; wire ends inside another wire
  320; crossings without a junction 292; labels that repeat a name 406; ports wired at the far end 80 and at
  the location 14; nets with a port and a power port 66; harness connectors 95, harnesses 43; dotted harness
  labels 13; no-connect marks 106; instances of repeated sheets 11. Zero in every set: buses, off-sheet
  connectors, a label and a power port of one name, a pin end inside a wire segment.
