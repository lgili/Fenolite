# altium-project-reader Specification

## Purpose
Read the text files of an Altium project (the project file, output jobs, rule files and stack-up files) while keeping each byte for byte, load a project with its documents, and map the rules onto the neutral model where a closed scope grammar allows it.
## Requirements
### Requirement: Text forms are kept byte for byte
`fenolite.backends.altium.read.textfile.split_text(data, *, file="")` SHALL split the bytes of a text file into a `TextBytes(bom, encoding, lines)` and `TextBytes.to_bytes()` MUST return exactly `data`, for every input it accepts.
- `bom` MUST be the UTF-8 byte-order mark (`EF BB BF`) when `data` starts with it, else `b""`.
- Each `TextLine(raw, end)` MUST hold the bytes of one line and its line end, one of `b"\r\n"`, `b"\n"`, `b"\r"` or `b""` (only the last line may have `b""`). Line ends MUST NOT be normalised.
- `encoding` MUST be `utf-8` when a byte-order mark is present or when all bytes decode as UTF-8, else `latin-1`, with the warning `altium.text.encoding-assumed`. `TextLine.text(encoding)` decodes one line; the raw bytes stay the source of `to_bytes()`.
- More than one kind of line end in one file MUST add the info `altium.text.mixed-line-ends` and MUST change no byte.
- Data that starts with the compound-file signature `D0 CF 11 E0 A1 B1 1A E1`, or that holds a NUL byte, MUST raise `FormatError` naming `file`; the message for the signature MUST say that the file is a compound file and is read by the compound reader.
- `fenolite.backends.altium.read.ini.parse_ini(data, *, file="")` SHALL return an `IniDocument` whose `to_bytes()` equals `data`. Sections, keys, duplicate sections, duplicate keys, empty lines, lines before the first section and lines that are neither `[<name>]` nor `<key>=<value>` MUST be kept in file order. A key is the text before the first `=`; the value is everything after it, with its spaces.
- `IniSection.get(key)` MUST return the first value of `key`; a repeated key in one section MUST add the info `altium.text.duplicate-key`, and a line of the last kind above MUST add the info `altium.text.stray-line`. Section and key names MUST be matched exactly as written.
- `fenolite.backends.altium.read.proptext.parse_fields(text)` SHALL return a `PropRecord` whose `fields` are the `(key, value)` pairs of a `|`-separated property text in order, repeated keys included; a part without `=` is kept as a key with the value `None`.
- `textfile.text_kind(data, *, name="")` SHALL return one of `prjpcb`, `outjob`, `rul-export`, `rul-summary`, `stackup`, `compound` or `unknown`, from the content first and the extension of `name` second.

#### Scenario: Byte-order mark and LF are kept
- **GIVEN** the bytes `EF BB BF` followed by `[Design]\nVersion=1.0\n\n[Document1]\nDocumentPath=a.SchDoc\n`
- **WHEN** `parse_ini(data).to_bytes()` is called
- **THEN** the result equals `data`, `form.bom` is `EF BB BF` and every line end is `b"\n"`

#### Scenario: Unknown section and key order survive
- **GIVEN** a file with the sections `[Design]`, `[Zeta Options]` and `[Document1]`, where `[Zeta Options]` holds `B=2`, `A=1` and `B=3` in that order
- **WHEN** it is parsed and written back
- **THEN** the bytes are equal, the section's entries are `("B", "2")`, `("A", "1")`, `("B", "3")`, `get("B")` is `"2"`, and the issues hold one `altium.text.duplicate-key`

#### Scenario: Mixed line ends
- **GIVEN** `[Design]\r\nVersion=1.0\nHierarchyMode=0\r\n`
- **WHEN** it is parsed
- **THEN** `to_bytes()` equals the input and the issues hold one info `altium.text.mixed-line-ends`

#### Scenario: Bytes outside UTF-8
- **GIVEN** a project file without a byte-order mark whose `[Parameter1]` value holds the single byte `E9`
- **WHEN** it is parsed
- **THEN** `form.encoding == "latin-1"`, the value reads `é`, `to_bytes()` equals the input, and the issues hold one warning `altium.text.encoding-assumed`

#### Scenario: Compound file refused
- **GIVEN** data that starts with `D0 CF 11 E0 A1 B1 1A E1`
- **WHEN** `split_text(data, file="x.SchDoc")` is called
- **THEN** `FormatError` is raised, names `x.SchDoc` and says the file is a compound file

#### Scenario: Kind from content
- **GIVEN** the four authored fixtures of `tests/data/altium/read/` and a file named `x.RUL` whose first line starts with `DRC Rules Export File for PCB:`
- **WHEN** `text_kind` is called on each
- **THEN** the results are `prjpcb`, `outjob`, `rul-export`, `stackup` and `rul-summary`

### Requirement: Project file read
`fenolite.backends.altium.read.project.read_project(data, *, file="")` SHALL return a `ProjectFile(ini, version, options, documents, generated, parameters, issues)` built on `parse_ini`, whose `to_bytes()` equals `data`.
- `documents` MUST hold one `ProjectDocument(index, path, kind, unique_id)` per section named `Document<n>` (n a positive decimal number) that has a `DocumentPath`, in file order; `index` is n. `generated` MUST hold the same for the sections `GeneratedDocument<n>`. The numbers need not be consecutive.
- `path` MUST be the `DocumentPath` value as written. `ProjectDocument.posix` MUST give it with `\` replaced by `/`.
- `kind` MUST come from the extension, compared without case, through the closed table `project.DOCUMENT_KINDS`:

  | extension | kind |
  |---|---|
  | `.SchDoc` | `schematic` |
  | `.PcbDoc` | `pcb` |
  | `.SchLib` | `schematic-library` |
  | `.PcbLib` | `pcb-library` |
  | `.IntLib` | `integrated-library` |
  | `.OutJob` | `output-job` |
  | `.RUL` | `rules` |
  | `.stackup` | `stackup` |
  | `.Harness` | `harness` |
  | `.SchDot` | `sheet-template` |
  | `.BomDoc` | `bom` |
  | `.PCBDwf` | `draftsman` |
  | `.Annotation` | `annotation` |

  Any other extension MUST give the kind `other` and, for a section `Document<n>`, the info `altium.project.document-kind-unknown`.
- `unique_id` MUST be the `DocumentUniqueId` value, or `""`.
- `parameters` MUST hold one `ProjectParameter(index, name, value)` per section `Parameter<n>`, from its `Name` and `Value` keys, in file order.
- `options` MUST be a `ProjectOptions` read from `[Design]`: `hierarchy_mode` (the integer of `HierarchyMode`, or `None`), `net_scope`, `output_path` (`OutputPath`), and the booleans `allow_port_net_names`, `allow_sheet_entry_net_names`, `append_sheet_number_to_local_nets` and `power_port_names_take_priority` from the keys of those names (`1` true, `0` false, anything else or absent `None`); `raw` holds every `[Design]` entry in order.
- `net_scope` MUST be looked up in the table `project.HIERARCHY_MODES`, which holds only the numbers the fact page states. A number outside it MUST give `net_scope = None` and the warning `altium.project.hierarchy-mode-unknown` naming the number. The reader MUST NOT guess a scope.
- A file without a `[Design]` section MUST give the warning `altium.project.no-design-section`; every option is then `None`.
- Every other section (variants, configurations, output groups, error reporting, class generation and any unknown one) MUST stay reachable through `ini` and MUST NOT be typed.
- The file that `prjpcb.write_prjpcb` writes MUST read back with the documents it was given.

#### Scenario: Documents and kinds
- **GIVEN** the authored fixture `tests/data/altium/read/project_utf8.PrjPcb` with `Document1` `Top.SchDoc`, `Document2` `Board.PcbDoc`, `Document4` `Jobs\Fab.OutJob` and `Document7` `notes.txt`
- **WHEN** `read_project` is called
- **THEN** the documents have the indexes 1, 2, 4, 7 and the kinds `schematic`, `pcb`, `output-job`, `other`; the third has `posix == "Jobs/Fab.OutJob"`; the issues hold one `altium.project.document-kind-unknown`

#### Scenario: Options and parameters
- **GIVEN** the same fixture, with `HierarchyMode=0`, `AllowPortNetNames=0`, `AllowSheetEntryNetNames=1` and the sections `[Parameter1]` (`Name=rev`, `Value=B`) and `[Parameter2]` (`Name=title`, `Value=`)
- **WHEN** it is read
- **THEN** `options.hierarchy_mode == 0`, `options.net_scope == "automatic"`, `options.allow_port_net_names is False`, `options.allow_sheet_entry_net_names is True`, and the parameters are `("rev", "B")` and `("title", "")`

#### Scenario: Unknown hierarchy mode
- **GIVEN** a project file with `HierarchyMode=9`
- **WHEN** it is read
- **THEN** `options.hierarchy_mode == 9`, `options.net_scope is None` and the issues hold one warning `altium.project.hierarchy-mode-unknown` naming `9`

#### Scenario: Fenolite's own project file
- **GIVEN** `write_prjpcb(schematic="a.SchDoc", pcb="a.PcbDoc", libraries=("a.SchLib",))`
- **WHEN** the bytes are read
- **THEN** the documents are `a.SchDoc`, `a.PcbDoc` and `a.SchLib` with the kinds `schematic`, `pcb` and `schematic-library`, `version == "1.0"`, `options.hierarchy_mode is None` and `to_bytes()` equals the written bytes

### Requirement: Output job read
`fenolite.backends.altium.read.outjob.read_outjob(data, *, file="")` SHALL return an `OutJobFile(ini, version, groups, issues)` whose `to_bytes()` equals `data`.
- `version` MUST be the `Version` value of `[OutputJobFile]`. Data without that section MUST raise `FormatError`.
- `groups` MUST hold one `OutputGroup(index, name, description, variant_name, media, outputs)` per section `OutputGroup<n>`, in file order, from the keys `Name`, `Description` and `VariantName`.
- `media` MUST hold one `OutputMedium(index, name, type)` per key `OutputMedium<j>`, with `type` from `OutputMedium<j>_Type` (`""` when absent).
- `outputs` MUST hold one `JobOutput(index, type, name, category, document_path, variant_name, enabled, enabled_media)` per index `i` for which any of the keys `OutputType<i>`, `OutputName<i>`, `OutputCategory<i>`, `OutputDocumentPath<i>`, `OutputVariantName<i>` or `OutputEnabled<i>` exists, in ascending `i`. `enabled` is true only for the value `1`; `enabled_media` holds each `j` for which `OutputEnabled<i>_OutputMedium<j>` is not `0`.
- An index without `OutputType<i>` MUST add the warning `altium.outjob.output-incomplete` and MUST still be listed, with `type == ""`.
- The sections `PublishSettings`, `GeneratedFilesSettings` and any other, and the keys `PageOptions<i>` and `Configuration<i>_…`, MUST stay reachable through `ini` and MUST NOT be typed. The reader MUST NOT run an output.

#### Scenario: Outputs of one group
- **GIVEN** the authored fixture `tests/data/altium/read/jobs.OutJob` with one group, the media `Print Job` (`Printer`) and `PDF` (`Publish`), and two outputs: `Schematic Print` (category `Documentation`, enabled, medium 2 set to `1`) and `Gerber` (category `Fabrication`, `OutputEnabled2=0`)
- **WHEN** `read_outjob` is called
- **THEN** `groups[0].outputs` are `(1, "Schematic Print", …, enabled=True, enabled_media=(2,))` and `(2, "Gerber", …, enabled=False, enabled_media=())`, and `to_bytes()` equals the fixture

#### Scenario: Not an output job
- **GIVEN** the bytes of a project file
- **WHEN** `read_outjob` is called
- **THEN** `FormatError` is raised naming the missing section `OutputJobFile`

### Requirement: Rule files read
`fenolite.backends.altium.read.rul.read_rule_file(data, *, file="")` SHALL return a `RuleFile(form, kind, header, records, issues)` whose `to_bytes()` equals `data`, for both forms that carry the extension `.RUL`.
- **Export form** (`kind == "export"`): each non-empty line is one record, a `|`-separated property text that holds `RULEKIND=`. A record's end mark, the pilcrow sign as the bytes `C2 B6` or the byte `B6`, MUST be recognised, kept in the raw line and left out of the last value. `header` is `""`.
- **Summary form** (`kind == "summary"`): the first line starts with `DRC Rules Export File for PCB:` and is the `header`; each further non-empty line is one record with the keys `RuleKind`, `RuleName`, `Scope` and one value key.
- `records` MUST hold one `PropRecord` per record, in file order, with every key and value as written.
- A non-empty line of an export file without `RULEKIND=` MUST be kept, listed as a record and reported with the warning `altium.rule.record-malformed`.
- Data in neither form MUST raise `FormatError`.
- `read_rule_file` MUST NOT interpret any value; "Rules onto the neutral model" does.

#### Scenario: Export form with end marks
- **GIVEN** the authored fixture `tests/data/altium/read/rules_export.RUL` with three records (Clearance, Width, ShortCircuit), each ended by `C2 B6` and LF
- **WHEN** `read_rule_file` is called
- **THEN** `kind == "export"`, the three records hold their keys in order, the last value of the first record is `10mil` without the end mark, and `to_bytes()` equals the fixture

#### Scenario: Summary form
- **GIVEN** `DRC Rules Export File for PCB: board.PcbDoc\r\nRuleKind=Width|RuleName=Width|Scope=Board|Minimum=10.00\r\n`
- **WHEN** it is read
- **THEN** `kind == "summary"`, `header` is the first line, and the one record has the fields `RuleKind`, `RuleName`, `Scope`, `Minimum` with the value `10.00` as text

#### Scenario: Unknown form
- **GIVEN** the bytes `hello\n`
- **WHEN** `read_rule_file` is called
- **THEN** `FormatError` is raised

### Requirement: Rules onto the neutral model
`fenolite.backends.altium.read.rules.map_rules(records, *, origin, summary=False)` SHALL return a `RuleMapping(ruleset, unmapped, issues)`. Each element of `records` is a field list: the `(key, value)` pairs of one rule in order, such as `PropRecord.fields`. Every input record appears exactly once: as the source of one or two rules of `ruleset`, or as one `Unmapped(index, kind, name, reason, detail)`. No record MUST be dropped: `RuleMapping.sources`, the indexes of the records that gave at least one rule, and the indexes of `unmapped` MUST be disjoint and together MUST be every index of `records`.
- Only the kinds of the closed table `rules.RULE_KIND_MAP` map:

  | `RULEKIND` | neutral kind | limits | further conditions |
  |---|---|---|---|
  | `Clearance` | `clearance` | `min` = `GAP` | `NETSCOPE=DifferentNets`; `OBJECTCLEARANCES` absent or empty; `GENERICCLEARANCE` absent or equal to `GAP`; `IGNOREPADTOPADCLEARANCEINFOOTPRINT` absent or `FALSE` |
  | `Width` | `track_width` | `min` = `MINLIMIT`, `opt` = `PREFEREDWIDTH`, `max` = `MAXLIMIT` | `NETSCOPE=AnyNet` |
  | `RoutingVias` | `via_diameter` and `via_drill` (two rules) | diameter: `MINWIDTH`, `WIDTH`, `MAXWIDTH`; drill: `MINHOLEWIDTH`, `HOLEWIDTH`, `MAXHOLEWIDTH` as `min`, `opt`, `max` | `NETSCOPE=AnyNet`; `VIASTYLE=Through Hole` |
  | `HoleSize` | `hole_size` | `min` = `MINLIMIT`, `max` = `MAXLIMIT` | `NETSCOPE=AnyNet`; `ABSOLUTEVALUES=TRUE`; `MINPERCENT` and `MAXPERCENT` are allowed and unused |

- A record maps only when all of these hold, checked in this order; the first failure gives the reason:

  | reason | when |
  |---|---|
  | `summary-form` | `summary` is true (the values of a summary record carry no unit) |
  | `malformed` | no `RULEKIND`, no `NAME`, or `PRIORITY` is not a positive integer |
  | `no-counterpart` | the kind is not in `RULE_KIND_MAP` and not in `rules.PENDING_KINDS` |
  | `no-verified-keys` | the kind is in `rules.PENDING_KINDS` (`BoardOutlineClearance`): the model has a counterpart, and no permitted source gives the record's keys |
  | `disabled` | `ENABLED` is not `TRUE` |
  | `net-scope` | `NETSCOPE` differs from the table |
  | `layer-kind` | `LAYERKIND` is not `SameLayer` |
  | `keys` | a key other than the header keys, the keys before `RULEKIND` and the kind's keys of the table is present, or a condition of the table fails |
  | `value` | a limit is missing where the table needs one (`GAP`; at least one limit otherwise), or is not a length |
  | `scope` | `SCOPE1EXPRESSION` or `SCOPE2EXPRESSION` is outside "Closed scope grammar", or `SCOPE2EXPRESSION` is not `All` for a kind other than `Clearance` |

- The header keys are the closed tuple `rules.HEADER_KEYS`: `RULEKIND`, `NETSCOPE`, `LAYERKIND`, `SCOPE1EXPRESSION`, `SCOPE2EXPRESSION`, `NAME`, `ENABLED`, `PRIORITY`, `COMMENT`, `UNIQUEID` and `DEFINEDBYLOGICALDOCUMENT`, the keys that every rule record of a PCB document holds after its common keys (`docs/formats/altium/pcb-copper.md`, c0038). So the rules that Fenolite's own writer puts in `Rules6` map without a `keys` reason.
- A mapped `Rule` MUST have: `name` = `NAME`; `priority` = `PRIORITY` (1 the highest, as in Altium); `severity = "error"`; `selector_a` from `SCOPE1EXPRESSION`; for `Clearance`, `selector_b` from `SCOPE2EXPRESSION`, `None` when it is `All`; `layers = ()`; `native_ids == {"altium": UNIQUEID}` when the record has one; `id = derived_id("rul", "altium", "<origin>:<index>:<neutral kind>")`; and `ext["altium"]` an `ExtBag` whose payload is `(("record", <the record text>),)`.
- A length MUST be a decimal number followed by `mil` or `mm` (`proptext.parse_length`). It MUST be converted exactly as a fraction and rounded half to even to the integer nanometre (`core.units.round_half_even_div`). No float MUST be used.
- For `RoutingVias`, a group (diameter or drill) without any of its three keys gives no rule; when both groups are empty the reason is `value`.
- `ruleset` MUST be a `RuleSet` with `id = derived_id("rst", "altium", origin)` and its rules in record order.
- Each `Unmapped` MUST add one info `altium.rule.unmapped` whose message names the rule, its kind and the reason, and whose `where` is `<origin>#<index>`. With `summary=True` a single info `altium.rule.summary-form` MUST be added first.
- `map_rules` MUST accept field lists from any source of the same keys, so that c0043 can pass the `fields` of the rule records of a PCB document (c0041), which hold every pair of the record. A caller MAY replace the id, the native id and the bag of a returned rule by its own (c0043 does). It MUST read the kind, name, priority, enabled state and scopes from the fields `RULEKIND`, `NAME`, `PRIORITY`, `ENABLED`, `SCOPE1EXPRESSION` and `SCOPE2EXPRESSION`.
- Fenolite MUST ship no rule values: every limit of `ruleset` comes from a record.

#### Scenario: Clearance and width
- **GIVEN** two export records: `Clearance` (`NETSCOPE=DifferentNets`, scopes `All` and `All`, `PRIORITY=1`, `GAP=6mil`) and `Width` (`NETSCOPE=AnyNet`, `SCOPE1EXPRESSION=InNetClass('PWR')`, `PRIORITY=1`, `MINLIMIT=10mil`, `PREFEREDWIDTH=20mil`, `MAXLIMIT=100mil`)
- **WHEN** `map_rules(records, origin="board.RUL")` is called
- **THEN** the rule set holds a `clearance` rule with `min == 152_400`, `selector_a` `all` and `selector_b is None`, and a `track_width` rule with `min == 254_000`, `opt == 508_000`, `max == 2_540_000` and `selector_a == Selector("netclass", "PWR")`; `unmapped == ()`

#### Scenario: Via style gives two rules
- **GIVEN** a `RoutingVias` record with `VIASTYLE=Through Hole`, `MINWIDTH=25mil`, `WIDTH=25mil`, `MAXWIDTH=50mil`, `MINHOLEWIDTH=12mil`, `HOLEWIDTH=12mil`, `MAXHOLEWIDTH=28mil`
- **WHEN** it is mapped
- **THEN** the rule set holds a `via_diameter` rule (`635_000`, `635_000`, `1_270_000`) and a `via_drill` rule (`304_800`, `304_800`, `711_200`), with the same name, priority and `native_ids`, and different ids

#### Scenario: Fenolite's own rules map
- **GIVEN** the field lists of the five rules that c0038's writer puts in `Rules6` of the blink sample (`Clearance_PWR`, `Clearance`, `Width_PWR`, `Width`, `RoutingVias`), each with the common keys before `RULEKIND` and every header key
- **WHEN** `map_rules(records, origin="blink.PcbDoc")` is called
- **THEN** `unmapped == ()` and the rule set holds two `clearance` rules, two `track_width` rules, one `via_diameter` rule and one `via_drill` rule

#### Scenario: Every other kind is reported
- **GIVEN** five records: `ShortCircuit`, `PlaneConnect`, `BoardOutlineClearance`, a disabled `Width`, and a `Clearance` whose `OBJECTCLEARANCES` is not empty
- **WHEN** they are mapped
- **THEN** the rule set is empty, `unmapped` has five entries with the reasons `no-counterpart`, `no-counterpart`, `no-verified-keys`, `disabled` and `keys` in record order, and the issues hold five infos `altium.rule.unmapped`

#### Scenario: Rounding to the nanometre
- **GIVEN** a `Clearance` record with `GAP=3.937mil`
- **WHEN** it is mapped
- **THEN** `min == 100_000` (99 999.8 nm rounded half to even) and no float appears in the rule

#### Scenario: Summary records are never mapped
- **GIVEN** the records of a summary-form file with three rules
- **WHEN** `map_rules(records, origin="out.RUL", summary=True)` is called
- **THEN** the rule set is empty, `unmapped` has three entries with the reason `summary-form`, and the first issue is `altium.rule.summary-form`

#### Scenario: The count holds on the corpus
- **GIVEN** the fetched rule files of the corpus
- **WHEN** `uv run pytest tests/corpus/test_altium_text.py -k rules` runs
- **THEN** for each file `sources` and the indexes of `unmapped` are disjoint and together are every record index

### Requirement: Closed scope grammar
`fenolite.backends.altium.read.scope.parse_scope(text)` SHALL return a neutral `Selector`, or a string that says why the expression is outside the grammar. It MUST accept only this grammar, with the spellings as written here:

| expression | selector |
|---|---|
| `All` | `all` |
| `InNet('v')` | `net v` |
| `InNetClass('v')` | `netclass v` |
| `InComponent('v')` | `ref v` |
| `IsTrack`, `IsVia`, `IsPad` | `item_kind track`, `via`, `pad` |
| `x And y And …`, `x && y && …` | `and(x, y, …)` |
| `x Or y Or …`, `x \|\| y \|\| …` | `or(x, y, …)` |
| `Not x` | `not(x)` |
| `(x)` | `x` |

- Spaces around tokens MUST be ignored. A value `v` MUST be non-empty and MUST NOT hold `'`, `*`, `?`, `[` or `]`, because a neutral leaf value is a glob.
- One parenthesis level MUST hold one kind of operator: an expression that mixes `And`, `Or` and `Not` without parentheses is refused, because no permitted source states the precedence. `Not` MUST be followed by a leaf or a parenthesised expression and MUST be the whole of its level.
- `All` below the top level, `OnLayer` and every other layer function, every other function or field comparison, and any text left over MUST be refused. A scope MUST never be approximated.

#### Scenario: Class and item kind
- **GIVEN** `InNetClass('HV') And (Not IsVia)`
- **WHEN** `parse_scope` is called
- **THEN** it returns `and(netclass HV, not(item_kind via))`

#### Scenario: Mixed operators without parentheses
- **GIVEN** `InNet('A') Or InNet('B') And IsTrack`
- **WHEN** `parse_scope` is called
- **THEN** it returns a string that names the mixed operators, and a rule with this scope is `Unmapped` with the reason `scope`

#### Scenario: Layer and wildcard refused
- **GIVEN** the expressions `OnLayer('Top Layer')` and `InNet('PWR*')`
- **WHEN** `parse_scope` is called on each
- **THEN** both return a string, the first naming `OnLayer` and the second the character `*`

### Requirement: Stack-up file read
`fenolite.backends.altium.read.stackup.read_stackup(data, *, file="")` SHALL return a `StackupFile(form, record, version, layers, issues)` whose `to_bytes()` equals `data`.
- The file is one property text. After an optional byte-order mark it MUST start with `|STACKUPVERSION=`, else `FormatError` is raised. `version` is that value as text; `record` holds every field in order.
- `layers` MUST hold one `StackEntry(index, name, layer_id, kind, thickness, dielectric_type, epsilon_r, material, component_placement)` per index `i` of the keys `LAYER_V<g>_<i><KEY>` that has a `COPTHICK` or a `DIELHEIGHT` key, in ascending `i`, which is the order from top to bottom.
- `kind` MUST be `copper` for an entry with `COPTHICK` and `dielectric` for one with `DIELHEIGHT`. `thickness` is that length in nanometres (`proptext.parse_length`, `mil` or `mm`). `epsilon_r` is the `DIELCONST` text as written, never a float. `dielectric_type` is the integer of `DIELTYPE`, `material` the `DIELMATERIAL` text, `component_placement` the integer of `COMPONENTPLACEMENT`, `layer_id` the integer of `LAYERID`; an absent key gives `None` or `""`.
- A length that does not parse MUST give `thickness = None` and the warning `altium.stackup.length-unreadable`.
- Keys with more than one generation number `<g>` in one file MUST give the warning `altium.stackup.unknown-form`; the entries are then read from the highest `<g>`.
- Every other key (sub-stacks, impedance profiles, via spans, entries without a thickness, and keys this requirement does not name) MUST stay in `record` and MUST NOT be typed.

#### Scenario: Two copper layers
- **GIVEN** the authored fixture `tests/data/altium/read/two_layer.stackup`: entries 0 (`Top Overlay`, no thickness), 1 (`Top Layer`, `COPTHICK=0.035mm`, `COMPONENTPLACEMENT=1`), 2 (`Dielectric 1`, `DIELTYPE=1`, `DIELCONST=4.8`, `DIELHEIGHT=1.5mm`, `DIELMATERIAL=FR-4`) and 3 (`Bottom Layer`, `COPTHICK=1.4mil`), with no line end
- **WHEN** `read_stackup` is called
- **THEN** `layers` has the indexes 1, 2, 3, the kinds `copper`, `dielectric`, `copper`, the thicknesses `35_000`, `1_500_000` and `35_560`, `layers[1].epsilon_r == "4.8"`, and `to_bytes()` equals the fixture

#### Scenario: Not a stack-up file
- **GIVEN** the bytes of an output job
- **WHEN** `read_stackup` is called
- **THEN** `FormatError` is raised naming `STACKUPVERSION`

### Requirement: Project loading
`fenolite.backends.altium.read.project.load_project(path)` SHALL read the project file at `path` and the text companions it lists, and SHALL return an `AltiumProject(root, name, project, documents, outjobs, rule_files, stackups, rules, issues)`. It is the entry point for the import change (c0043).
- `root` is the folder of `path`. `documents` MUST hold one `LoadedDocument(document, file, present)` per `ProjectFile.documents` entry, where `file` is `root / document.posix` and `present` says whether it is a file.
- A document whose path is absolute, starts with a drive letter or `\\`, or leaves `root` through `..` MUST NOT be opened: `file` is `None`, and the warning `altium.project.document-outside` names the document index, not the path.
- A listed document that is not a file MUST add the warning `altium.project.document-missing`. Paths MUST be resolved as written; when no file of that spelling exists and exactly one file of `root` matches without case, that file is used.
- Present documents of the kinds `output-job`, `rules` and `stackup` MUST be read with `read_outjob`, `read_rule_file` and `read_stackup` and stored in `outjobs`, `rule_files` and `stackups` as `(document index, result)` pairs. A `FormatError` of a companion MUST NOT fail the load: it adds the warning `altium.project.companion-unreadable` naming the document index and the error.
- `rules` MUST hold one `(document index, RuleMapping)` per rule file, from `map_rules(file.records, origin=<document posix path>, summary=file.kind == "summary")`.
- Documents of every other kind MUST be listed and not opened. `generated` documents MUST NOT be opened.
- `issues` MUST hold the issues of the project file, then those of each companion in document order.
- A project file that cannot be read MUST raise `FormatError`; a missing `path` MUST raise `FileNotFoundError`.
- `load_project` MUST NOT write anything and MUST NOT import `fenolite.backends.altium.read.cfb` or any reader of compound files.

#### Scenario: Project with companions
- **GIVEN** a folder with the authored fixtures: a project file that lists `Top.SchDoc` (absent), `jobs.OutJob`, `rules_export.RUL` and `two_layer.stackup`
- **WHEN** `load_project(folder / "project_companions.PrjPcb")` is called
- **THEN** `outjobs`, `rule_files`, `stackups` and `rules` each hold one entry with the right document index, `documents[0].present is False`, and the issues hold one `altium.project.document-missing` followed by the companions' issues

#### Scenario: Path outside the project folder
- **GIVEN** a project file whose `Document2` is `..\..\shared\Fab.OutJob`
- **WHEN** it is loaded
- **THEN** that document has `file is None`, nothing outside the folder is opened, and the issues hold one `altium.project.document-outside` naming document 2

#### Scenario: Unreadable companion
- **GIVEN** a project file that lists `bad.RUL`, a file holding `hello`
- **WHEN** it is loaded
- **THEN** the load succeeds, `rule_files == ()`, and the issues hold one `altium.project.companion-unreadable` naming the document index

#### Scenario: No compound reader
- **GIVEN** the modules of `fenolite.backends.altium.read` named `textfile`, `ini`, `proptext`, `project`, `outjob`, `rul`, `rules`, `scope` and `stackup`
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_text_imports.py` runs
- **THEN** none of them imports `fenolite.backends.altium.read.cfb` or `fenolite.backends.altium.cfb`, and each imports only the standard library, `fenolite.core`, `fenolite.model` and its sibling text modules

### Requirement: Text reader issue codes
`fenolite.backends.altium.read.textfile.TEXT_READ_CODES` SHALL be this closed mapping, and every issue of the modules of this capability MUST use one of its codes with the severity given:

| code | severity | when |
|---|---|---|
| `altium.text.encoding-assumed` | warning | no byte-order mark and the bytes are not UTF-8; read as Latin-1 |
| `altium.text.mixed-line-ends` | info | more than one kind of line end |
| `altium.text.duplicate-key` | info | a key repeated in one section |
| `altium.text.stray-line` | info | a line that is neither a section, a key nor empty |
| `altium.project.no-design-section` | warning | a project file without `[Design]` |
| `altium.project.hierarchy-mode-unknown` | warning | a `HierarchyMode` outside `HIERARCHY_MODES` |
| `altium.project.document-kind-unknown` | info | a document extension outside `DOCUMENT_KINDS` |
| `altium.project.document-missing` | warning | a listed document is not a file |
| `altium.project.document-outside` | warning | a document path leaves the project folder |
| `altium.project.companion-unreadable` | warning | a listed companion raised `FormatError` |
| `altium.outjob.output-incomplete` | warning | an output without its type |
| `altium.rule.record-malformed` | warning | a line of an export file without a rule kind |
| `altium.rule.summary-form` | info | a summary-form file: its rules are not mapped |
| `altium.rule.unmapped` | info | one rule that is not mapped, with its reason |
| `altium.stackup.unknown-form` | warning | more than one generation of layer keys |
| `altium.stackup.length-unreadable` | warning | a thickness that is not a length |

No issue of this capability MUST have the severity `error`: malformed input raises `FormatError`, which the CLI maps to `FEN-3004`. An issue message MUST NOT hold a path outside the project folder.

#### Scenario: Closed set
- **GIVEN** the issues produced by the unit cases of this capability and the `altium.text.`, `altium.project.`, `altium.outjob.`, `altium.rule.` and `altium.stackup.` literals in `src/fenolite/backends/altium/read/*.py`
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_text_codes.py` runs
- **THEN** every produced code is a key of `TEXT_READ_CODES` with the table's severity, and the set of literals of the nine text modules equals the keys of `TEXT_READ_CODES`

### Requirement: Altium text corpus rows
`tests/corpus/manifest.toml` SHALL contain twelve rows for the text files, under the rules of `corpus-policy` "Second-backend corpus rows" (change c0039): three project files (`altium-third-party-prjpcb-01` to `-03`), three output jobs (`altium-third-party-outjob-01` to `-03`), three rule files (`altium-third-party-rules-01` in the export form, `-02` and `-03` in the summary form) and three stack-up files (`altium-third-party-stackup-01` to `-03`).
- Each row MUST hold the uses `altium`, `altium-text` and `origin:third-party`, a 40-digit commit as `ref`, `embeddable = false` and the licence of its repository (MIT or LGPL-3.0 for these rows), registered as S-0187, S-0188 and S-0297 to S-0299. The rows MUST NOT hold `cfb`: the files are not compound files.
- `tests/corpus/test_altium_text.py`, marked `needs_corpus`, SHALL for every row: read the file with the reader of its kind, assert `to_bytes()` equals the fetched bytes, and assert that no issue code is outside `TEXT_READ_CODES`. For the project rows it SHALL also assert at least one document of the kind `schematic` or `pcb`; for the rule rows the partition rule of "Rules onto the neutral model"; for the stack-up rows at least two `copper` entries with a thickness.
- The test MUST print no path, header line or value of a corpus file: its messages name rows by id and give counts and key names only.
- No corpus file and nothing derived from one MUST be committed.

#### Scenario: Corpus identity
- **GIVEN** the twelve rows fetched with `uv run python tools/corpus_fetch.py --uses altium-text`
- **WHEN** `uv run pytest tests/corpus/test_altium_text.py` runs
- **THEN** every row passes the identity, code and kind checks

#### Scenario: Corpus absent
- **GIVEN** an empty corpus cache
- **WHEN** the same command runs
- **THEN** every test is skipped with the message `run: uv run python tools/corpus_fetch.py`

#### Scenario: Row schema
- **GIVEN** the manifest with the twelve rows
- **WHEN** `uv run pytest tests/corpus/test_manifest.py` runs
- **THEN** it passes: every `altium-text` row matches the id pattern of the second-backend rows, holds `altium` and `origin:third-party`, and holds neither `cfb` nor `rt0`

### Requirement: Text file facts are documented
The facts this capability relies on SHALL be recorded in Fenolite's own words, each row with a source id of `docs/evidence/sources.md`, an evidence label and, below `CORPUS-VERIFIED`, a hypothesis `H-A-RD-PRJ-*`:
- `docs/formats/altium/project.md`: a section "The project file as Altium saves it" (sections, document keys, parameters, the `[Design]` options, the hierarchy-mode table, encoding and line ends) beside the writer's rows, which stay.
- `docs/formats/altium/output-job.md`: sections and keys of an output job.
- `docs/formats/altium/rule-file.md`: the two forms, the header keys, the kind table with every rule kind seen and whether it maps, the closed scope grammar, the length rule and the reasons.
- `docs/formats/altium/stackup-file.md`: the record, the layer keys and the units.

`src/fenolite/backends/altium/PROVENANCE.md` MUST gain one row per area. `tests/unit/test_format_facts.py` MUST accept the stem `H-A-RD-` on the Altium pages. The tables `DOCUMENT_KINDS`, `HIERARCHY_MODES`, `RULE_KIND_MAP` and `PENDING_KINDS` MUST equal the tables of the pages.

#### Scenario: Fact tables checked
- **GIVEN** the four pages and the source register
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** every row has a registered S-id, a valid label and, where needed, a registered hypothesis

#### Scenario: Code tables follow the pages
- **GIVEN** the tables of `docs/formats/altium/project.md` and `rule-file.md`
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_text_tables.py` runs
- **THEN** `DOCUMENT_KINDS`, `HIERARCHY_MODES`, `RULE_KIND_MAP` and `PENDING_KINDS` hold exactly the rows of the pages

### Requirement: Text reader evidence
The levels of this capability SHALL be: `CORPUS-VERIFIED` for parsing and byte identity of project files and output jobs, once "Altium text corpus rows" passes on their rows, which come from three repositories per kind; `INFERRED` for rule files, stack-up files and project parameters (`H-A-RD-PRJ-RUL-EXPORT`, `H-A-RD-PRJ-RUL-SUMMARY`, `H-A-RD-PRJ-STACKUP`, `H-A-RD-PRJ-PARAM`) while their rows come from fewer than three repositories, as `corpus-policy` "Second-backend corpus rows" requires, with the corpus result recorded as supporting data; `INFERRED` for the meaning of rule keys and scopes (`H-A-RD-PRJ-RULE-MAP`, `H-A-RD-PRJ-SCOPE`) and for the hierarchy-mode numbers (`H-A-RD-PRJ-HIER`).
- No `kicad-cli` command reads these files, so no row MUST be labelled `ORACLE-VERIFIED`.
- `H-A-RD-PRJ-HIER` MUST be raised only by the maintainer's author report (`docs/evidence/altium-project-read.md`), to `ALTIUM-VERIFIED(author-report; …)`; such a row never raises an operation to verified.
- A corpus result MUST NOT raise a mapping row: reading a key is not proof of its meaning.
- `docs/hypotheses.md` MUST hold the rows `H-A-RD-PRJ-INI`, `-DOCS`, `-PARAM`, `-HIER`, `-ENC`, `-OUTJOB`, `-RUL-EXPORT`, `-RUL-SUMMARY`, `-RULE-MAP`, `-SCOPE` and `-STACKUP`, each with its test or kit request.
- `H-A-RD-PRJ-ENC` ("every corpus row without a byte-order mark is ASCII or UTF-8") is refuted by the corpus: two rows of one repository are not UTF-8. The row MUST stay, refuted, with the successor `H-A-RD-PRJ-ENC-2` (a file without a byte-order mark is 7-bit ASCII, UTF-8 or text of a single-byte code page, typed as Latin-1 with `altium.text.encoding-assumed`), which MUST stay `INFERRED` while its text that is not UTF-8 comes from fewer than three repositories and no permitted source names the code page. The fact-page row on encodings MUST name `H-A-RD-PRJ-ENC-2`.

#### Scenario: Register rows
- **GIVEN** `docs/hypotheses.md`
- **WHEN** `uv run pytest tests/unit/test_hypotheses_register.py` runs
- **THEN** the eleven rows and the successor `H-A-RD-PRJ-ENC-2` exist, `H-A-RD-PRJ-ENC` is refuted with that successor, every id cited in the live text is registered, and no `H-A-RD-PRJ-*` row has an `ORACLE-VERIFIED` level

#### Scenario: Mapping stays inferred
- **GIVEN** the corpus tests have passed and no author report exists
- **WHEN** the rows `H-A-RD-PRJ-RULE-MAP`, `H-A-RD-PRJ-SCOPE` and `H-A-RD-PRJ-HIER` are read
- **THEN** their level is `INFERRED`
