# KiCad project files: census

Key names, ids, version numbers and counts only (capability corpus-policy, "Project and rules corpus
rows"). Measured on 2026-10-02 with `tests/unit/backends/kicad/test_pro.py` over the cached
`project` rows of `tests/corpus/manifest.toml` (`FENOLITE_CENSUS_OUT`). Every row reads, prints and
reads again structurally equal, with identical key order and number texts. Rows identical at both tags
are listed once, at 10.0.6; the folder with a non-commercial licence is not listed.

| | tag 10.0.6 | tag 9.0.9.1 (rows that differ from 10.0.6) |
|---|---|---|
| project rows | 35 | 17 |
| pair (3, 5) | 4 | 0 |
| pair (3, 4) | 23 | 9 |
| pair (2, 4) | 1 | 1 |
| pair (1, 3) | 7 | 7 |
| `component_class_settings` | 5 | 0 |
| `tuning_profiles` | 1 | 0 |
| class key `tuning_profile` | 4 | 0 |
| `time_domain_parameters` | 3 | 0 |
| `legacy` | 3 | 2 |
| custom rules rows | 2 | 0 (the 9.0.9.1 file equals one at 10.0.6) |

Every key of `pro.TEN_ONLY_PATHS` occurs only in 10.0.6 rows (`H-K-PRO-VERSION`, `H-K-PRO-TUNING`).
Both custom rules rows are read with `read_rules`, written for target 10 and read back equal
(`tests/unit/backends/kicad/test_dru_demos.py`).
