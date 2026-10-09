## ADDED Requirements

### Requirement: Differential pairs in the model
The model SHALL hold a differential pair as an `Interface` whose kind is a key of `fenolite.model.pairs.PAIR_ROLES`, and `fenolite.model.pairs` SHALL define the name rule by which two nets form a pair (`H-K-DIFFPAIR-NAMES-2`). Rules, checks, the build and the backends MUST use this module, and no other pair entity MUST exist.
- **Roles.** `PAIR_ROLES` MUST map `diff_pair` to `("p", "n")` and `usb2` to `("dp", "dn")`, the positive role first. `pair_nets(interface)` MUST return the ids of the positive and the negative net of an interface of one of those kinds, and `None` for another kind or a missing role.
- **Name rule.** `split_pair_name(name)` MUST return `PairName(base, polarity, tail)` when the name, without its longest trailing run of digits and `_` (the tail, possibly empty), ends with `P`, `N`, `+` or `-` (the polarity), `base` being the text before the polarity; otherwise it MUST return `None`. `coupled_name(name)` MUST return the base, the other polarity (`P` for `N`, `+` for `-`, and back) and the tail, or `None`. `pair_base(positive, negative)` MUST return the base when the polarity of `positive` is `P` or `+` and `negative == coupled_name(positive)`, and `None` otherwise. Letter case counts throughout.
- **Bases of a design.** `net_bases(names)` MUST map each name of `names` whose coupled name is also in `names` to its base.
- **Class values.** `NetClass` MUST gain `diff_pair_width`, `diff_pair_gap` and `diff_pair_via_gap`, each a length in nm or `None` (the default), stored in `circuit.json`. A `circuit.json` written before these fields existed MUST load with all three `None`.
- **Rules.** `RuleKind` MUST gain `diff_pair_gap`, `diff_pair_uncoupled`, `skew`, `diff_pair_skew` and `length`. `SelectorOp` and `LEAF_OPS` MUST gain `diff_pair`, a leaf whose value is a pair base, which MAY hold `*`. `RuleSubject` MUST gain `diff_pair: str | None`, the base of the subject's net when the design holds the coupled net, `None` by default.
- **Matching.** `Selector("diff_pair", v).matches(subject)` MUST be true exactly when `subject.diff_pair` is not `None` and matches `v` as a glob with its letter case, or ends with `_` and matches `v` without that `_`.
- `schemas/fenolite.model.v0/circuit.json` and `rules.json` MUST be regenerated, and `uv run python tools/gen_schemas.py --check` MUST exit 0.

#### Scenario: Names that pair
- **WHEN** `pair_base` is called on (`USB_P`, `USB_N`), (`USB+`, `USB-`), (`USB_DP`, `USB_DN`), (`D_P0`, `D_N0`), (`D_P_2`, `D_N_2`) and (`DP1`, `DN1`)
- **THEN** it returns `USB_`, `USB`, `USB_D`, `D_`, `D_` and `D`

#### Scenario: Names that do not pair
- **WHEN** `pair_base` is called on (`USB_DP`, `USB_DM`), (`USB_p`, `USB_n`), (`USB_P`, `USB-`), (`D_P1`, `D_N2`), (`D_PA`, `D_NA`) and (`USB_N`, `USB_P`)
- **THEN** it returns `None` each time, and `coupled_name("USB_DP")` is `USB_DN`

#### Scenario: Nets of a USB interface
- **GIVEN** an `Interface` of kind `usb2` with the members `dp`, `dn`, `vbus` and `gnd`, and one of kind `i2c`
- **WHEN** `pair_nets` is called on each
- **THEN** the first gives the ids of the `dp` and `dn` nets in this order, and the second `None`

#### Scenario: Pair leaf matches by base
- **GIVEN** three subjects whose `diff_pair` is `USB_`, `usb_` and `None`
- **WHEN** `Selector("diff_pair", "USB")`, `Selector("diff_pair", "USB_")` and `Selector("diff_pair", "*")` are matched against each
- **THEN** the first two match only the subject `USB_`, and the third matches `USB_` and `usb_` and not the subject without a pair

#### Scenario: Older circuit document loads
- **GIVEN** a `circuit.json` written before this change, whose class `HV` has no pair key
- **WHEN** it is loaded with `canonical.loads` and validated against the regenerated schema
- **THEN** loading succeeds, validation passes, and the three pair values of `HV` are `None`
