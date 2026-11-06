## MODIFIED Requirements

### Requirement: Lossy conversions need consent
A conversion whose report has a `refuse` kind with losses SHALL raise `fenolite.convert.LossyConversionError` (`cli_code` `FEN-7001`) unless `allow_lossy` is true; the error MUST carry one `convert.lossy` issue per kind with lost items, in report order, with the kind as `where` and the counts per reason in the message. Those are the `refuse` kinds, which `refused` names, and the `report` kinds that `allow_lossy` would lose with them (change c0434), so a consent covers every loss it was shown. Its message MUST name the `refuse` kinds and, after `--allow-lossy also loses items of`, the others. With `allow_lossy` the conversion MUST complete and give one `convert.lossy` warning per kind with lost items. A `report` kind is refused too when its losses hold a reason of `report.REFUSE_REASONS`: for `rule`, `SOURCE_RULE_LOST`, a rule that a record of the source document gave (requirement "Rule records through KiCad").

#### Scenario: Exit 7 without consent
- **GIVEN** the KiCad 10.0.6 demo board `RoyalBlue54L-Feather` in the corpus
- **WHEN** `fenolite convert <board> --to altium --out out --dry-run --json` runs, and again with `--allow-lossy`
- **THEN** the first exits 7 with `FEN-7001` and issues whose `where` include `pad` and `dnp`, and the second exits 0 with a plan and `convert.lossy` warnings for the same kinds

#### Scenario: The refusal lists every loss
- **GIVEN** a conversion whose report loses one pad (a `refuse` kind) and one rule (a `report` kind)
- **WHEN** `convert_project` runs without `allow_lossy`
- **THEN** it raises `LossyConversionError` with the issues `pad` and `rule`, `refused` is `("pad",)`, and the message ends with `(pad); --allow-lossy also loses items of rule`

## ADDED Requirements

### Requirement: Rule records through KiCad
A conversion of an Altium document to KiCad SHALL write the root board property `Fenolite.Altium.Rules6` into the `.kicad_pcb` (`convert.rulecarrier`, schema `fenolite.altium-rules.v0`, packed by `backends.kicad.boardcarrier`: zlib, then base64). It holds every rule record of the document, in record order: its kind number, its keys from `RULEKIND` on, and the SHA-256 of each rule list of `<name>.kicad_dru` that the record's rules gave, as written (`dru.rule_text`). No file is written beside the board. A conversion of a KiCad board to Altium SHALL read the property when the board holds it.
- A record all of whose rule lists are in the rules file as written, or that gave none, MUST be written as it was read (`lower.write_design(source_rules=…)`). The rules it gave MUST NOT be lowered again.
- A record whose rule lists were edited or removed MUST NOT be written from the property; the rules the project holds are lowered.
- A loss of a rule that came from such a record MUST be a loss of reason `SOURCE_RULE_LOST`, which needs `--allow-lossy`. A loss of a rule that only KiCad holds stays a loss of class `report`.
- The report's `rule` row MUST count the rules the written records stand for as source and written.

#### Scenario: Every record back as it was read
- **GIVEN** a document written by Fenolite with an authored Width (its own name, priority 3), an enabled and a disabled Clearance, a Height and a Minimum Solder Mask Sliver
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0434.py` converts it to KiCad and back
- **THEN** the KiCad board's property lists every record, the Width and the enabled Clearance with the hashes of their rule lists, no file lies beside the board, and the document written back holds every record as the source does, keys and values from `RULEKIND` on, and no other

#### Scenario: A rule edited in KiCad
- **GIVEN** the same KiCad project whose Width rule list now holds `(opt 0.2mm)`
- **WHEN** it is converted back
- **THEN** the other records are written as they were read and the Width record holds `PREFEREDWIDTH=7.874mil`

#### Scenario: A rule that KiCad lost needs consent
- **GIVEN** the same project whose Width rule list holds no `opt`, which no Width record can hold
- **WHEN** it is converted back without `--allow-lossy`
- **THEN** `LossyConversionError` names the kind `rule`, while a rule that only KiCad holds and that no record can hold is reported without refusal

#### Scenario: Public row -08
- **GIVEN** `altium-third-party-pcbdoc-08`, whose 56 rule records include 48 that KiCad holds no rule for
- **WHEN** `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_rules_c0434.py` converts it to KiCad and back with `--altium-pour outline`
- **THEN** the document written back holds the 56 records as the source does and the `rule` row loses none

### Requirement: Fenolite board properties
`fenolite.backends.kicad.boardcarrier` SHALL write data a conversion carries for the way back as root properties of a KiCad board, `(property "Fenolite.Altium.<Name>" "<value>")`, the value being the base64 text of the data's zlib compression. `with_carried` MUST write every such property in name order right after `setup` (after `layers` without one), replace a property of the same name, keep the others and change no other byte; `carried` MUST give back the bytes of each. A name outside `Fenolite.Altium.<Name>` MUST raise `ValueError`.

#### Scenario: Written, replaced, read back
- **GIVEN** the committed `two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0434.py -k board_property` writes two properties and then one of them again
- **THEN** `carried` gives the newer value and the other, and the board without the property lines is the committed text

#### Scenario: KiCad keeps them
- **GIVEN** that board with a short property and one of 80 kB
- **WHEN** `uv run pytest tests/kicad/convert/test_board_carrier_oracle.py` exports it and re-saves it with `kicad-cli pcb upgrade --force` (10.0)
- **THEN** the export exits 0 and `carried` gives both values back after the re-save
