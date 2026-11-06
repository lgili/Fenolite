## MODIFIED Requirements

### Requirement: Lossy conversions need consent
A conversion whose report has a `refuse` kind with losses SHALL raise `fenolite.convert.LossyConversionError` (`cli_code` `FEN-7001`) unless `allow_lossy` is true; the error MUST carry one `convert.lossy` issue per kind with lost items, in report order, with the kind as `where` and the counts per reason in the message. Those are the `refuse` kinds, which `refused` names, and the `report` kinds that `allow_lossy` would lose with them (change c0434), so a consent covers every loss it was shown. Its message MUST name the `refuse` kinds and, after `--allow-lossy also loses items of`, the others. With `allow_lossy` the conversion MUST complete and give one `convert.lossy` warning per kind with lost items.

#### Scenario: Exit 7 without consent
- **GIVEN** the KiCad 10.0.6 demo board `RoyalBlue54L-Feather` in the corpus
- **WHEN** `fenolite convert <board> --to altium --out out --dry-run --json` runs, and again with `--allow-lossy`
- **THEN** the first exits 7 with `FEN-7001` and issues whose `where` include `pad` and `dnp`, and the second exits 0 with a plan and `convert.lossy` warnings for the same kinds

#### Scenario: The refusal lists every loss
- **GIVEN** a conversion whose report loses one pad (a `refuse` kind) and one rule (a `report` kind)
- **WHEN** `convert_project` runs without `allow_lossy`
- **THEN** it raises `LossyConversionError` with the issues `pad` and `rule`, `refused` is `("pad",)`, and the message ends with `(pad); --allow-lossy also loses items of rule`
