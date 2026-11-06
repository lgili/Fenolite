## MODIFIED Requirements

### Requirement: Lossy conversions need consent
A conversion whose report has a `refuse` kind with losses SHALL raise `fenolite.convert.LossyConversionError` (`cli_code` `FEN-7001`) unless `allow_lossy` is true; the error MUST carry one `convert.lossy` issue per kind with lost items, in report order, with the kind as `where` and the counts per reason in the message. Those are the `refuse` kinds, which `refused` names, and the `report` kinds that `allow_lossy` would lose with them (change c0434), so a consent covers every loss it was shown. Its message MUST name the `refuse` kinds and, after `--allow-lossy also loses items of`, the others. With `allow_lossy` the conversion MUST complete and give one `convert.lossy` warning per kind with lost items.

#### Scenario: Exit 7 without consent
- **GIVEN** the KiCad 10.0.6 demo board `RoyalBlue54L-Feather` in the corpus
- **WHEN** `fenolite convert <board> --to altium --out out --dry-run --json` runs, and again with `--allow-lossy`
- **THEN** the first exits 7 with `FEN-7001` and issues whose `where` include `pad` and `dnp`, and the second exits 0 with a plan and `convert.lossy` warnings for the same kinds

#### Scenario: The refusal lists every loss
- **GIVEN** the public document `altium-third-party-pcbdoc-01` converted to KiCad
- **WHEN** `uv run pytest tests/corpus/test_altium_rules_c0434.py` converts it back to Altium without and then with `--allow-lossy`
- **THEN** the refusal's envelope holds one `convert.lossy` issue for every kind the consented run loses, more kinds than its `refused`, and its message names the other kinds. The consented run writes 8 of the 8 rules, 3 of them changed
