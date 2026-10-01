## Context

- **Custom rules files.** A `.kicad_dru` file has no root list. It is a sequence of top-level lists: `(version 1)`, then `(rule NAME …)` lists (S-0010, S-0038). A rule holds an optional `layer` clause, an optional `condition` string, one or more `constraint` lists and an optional `severity` (S-0010, S-0038). The header stays `(version 1)` in 9.0 and 10.0 (c0007, `H-K-TOK-CONSTANTS`, INFERRED because no KiCad command writes rules files).
  - A condition is an expression over the two items `A` and `B` of a check: properties such as `NetName`, `NetClass` and `Type`, functions such as `memberOfFootprint`, the operators `==`, `&&`, `||` and `!`, and `'…'` string literals inside the double-quoted condition (S-0010, S-0038).
  - Values carry units such as `mm`, `mil` and `in` (S-0010). A line that starts with `#` is a comment (S-0010).
  - When several rules match, the manuals give precedence to the rule later in the file (S-0010, S-0038). Not proved yet (`H-K-DRU-ORDER`).
  - Board-setup minimums act as floors under custom rules (S-0038). c0010 measures this; this change only records it in `rules.md`.
- **Observed behaviour** (c0007, KICAD-VERIFIED on 9.0.9 and 10.0.6):
  - rules are read only with a project file next to the board, and any error disables every custom rule with exit 0 (`H-K-TOK-RULES-SILENT`);
  - 9.0.9 drops the whole file when one rule uses one of seven 10.0-only constructs: the constraint types `bridged_mask`, `solder_mask_expansion`, `solder_paste_abs_margin`, `solder_paste_rel_margin` and `via_dangling`, and the disallow kinds `through_via` and `blind_via` (`H-K-TOK-RULES-DRIFT`);
  - every constraint type and clause of the 9.0 manual loads on both majors (`H-K-TOK-RULES-FLOOR`);
  - a single-quoted rule name makes 10.0.6 drop the file (S-0020).
- **Today's code.**
  - `versions.wrap_rules`/`rules_text` handle only the common subset: they refuse `#` lines and symbol atoms containing `'` (`kicad-version-gating`, "Rules text and the synthetic node").
  - `check_emittable(node, FileKind.RULES, target)` reports `kicad.token.too-new` for the seven 10.0 rows and `kicad.token.uninventoried` for heads and constraint values outside the 56 rules rows of `backends/kicad/data/tokens.toml`.
  - `model.rules` has `Rule(name, kind, selector_a, selector_b, layers, min, opt, max, severity, priority)`, the selector algebra `all | net | netclass | ref | layer | item_kind | and | or | not` with glob leaf values, and `RuleSet(rules)`. Priority 1 is the highest.
  - `core.units.parse_length` and `format_length` are exact in both directions.
  - The committed canary `tests/data/kicad/tokens/canary/canary.kicad_dru` holds `(rule canary (constraint clearance (min 3mm)))`.
- **Footprints.**
  - `mod.read_footprint` and `footprint_from` (c0008) read definitions with slot lists. `FORMAT_VERSIONS[FOOTPRINT]` equals the board constants (S-0030).
  - `H-K-LIB-READ` stays `INFERRED` until a writer round trip holds on manifest files from two origins (c0008).
  - `H-K-SEXPR-ESCAPES` is verified on 10.0 only, because 9.0 has no `pcb upgrade` (S-0037). 9.0 has `fp upgrade` (S-0037).
- **Upstream changes.**
  - c0009 provides `backends/base.py`, the package runner `backends/kicad/cli.py` (`KicadCli`, `run`), `layers.py`, `_fpmap.py` (pad, drill, padstack and graphic mapping parameterised by root chain), `pcb.read_board`, the authored board `tests/data/kicad/board/two_layer.kicad_pcb`, and the corpus-policy requirement "Upgraded copies keep their origin".
  - c0017 provides `pcb.write_board`, the footprint emitter `_fpmap.emit_footprint`, `embed.place_footprint`, `LossyWriteError` (FEN-7001), `drc.read_drc_report`, `KicadCli.drc`, the 9-format copies in `tests/data/libs/Mini_v9.pretty/`, `tests/kicad/_probes.py`, `tests/kicad/test_probe_results.py` and `docs/evidence/kicad/probes/<version>.json`.
  - c0014 provides the machine-checked hypothesis register.
- **Environment.** KiCad 10.0.6 is installed locally. 9.0 behaviour comes from the `kicad-9` job and the pinned 9.0.9 image (S-0029).
- **Constraints.** Stdlib only. New modules stay inside `backends.kicad`, which may import `model`, `geometry` and `backends.base`. The budget is 5.75 working days.

## Goals / Non-Goals

**Goals:**
- Write `.kicad_mod` files for target 9 or 10, and prove the codec on two corpus origins and the written mini library on both majors.
- Read and write custom rules in the full dialect, with comments in place and every unrepresentable rule kept verbatim.
- Lower the model's `RuleSet` with an order, kinds and conditions that `kicad-cli` 9.0.9 and 10.0.6 provably enforce.
- Make a silently dropped rules file impossible to miss in any proof.

**Non-Goals:**
- Everything listed under Non-goals in the proposal.
- Selector ops outside the closed table, such as the model's `layer` op, functions like `insideCourtyard`, and `?` or `[…]` globs. They give `rules.unsupported-selector`.
- Several constraints in one modelled rule, and the `outer`/`inner` layer forms. Such rules stay opaque.
- Writing rules or footprint files to disk from a command. The functions return text; the command that writes them is c0011 `build`.

## Decisions

1. **A rules proof never trusts a clean DRC.** Every oracle bench carries the canary, and a test passes only when the canary violation is in the DRC JSON (`H-K-TOK-RULES-SILENT`).
   - The canary rule is read from `tests/data/kicad/tokens/canary/canary.kicad_dru`. It is placed right after `(version 1)`, so every later rule takes precedence over it.
   - The canary pair is two 0.25 mm tracks on nets `CANARY_A` and `CANARY_B` on `F.Cu`, with centres 1 mm apart, at least 10 mm from other copper. No other bench rule matches them.
   - Probe pairs that no later rule governs are 4 mm apart, so the canary alone never flags them. Probe rules use 5 mm, except the order test (Decision 7).
   - Violations are read with c0017's `read_drc_report` and matched by type and item uuids. Bench uuids are deterministic (c0017). The canary violation is the `clearance` violation between the two canary tracks; `clearance` is the type c0007's harness already matches.
   - A report without the canary violation fails the test with "rules file not loaded". It never passes and never skips. `_bench.require_canary(report, bench)` does this with `pytest.fail`, and every rules test calls it. The hermetic `tests/kicad/rules/test_bench.py` (no `needs_kicad`) proves the failure path on a `DrcReport` built without the canary violation.
   - Rejected: judging by exit code or by an empty report (`H-K-TOK-RULES-SILENT`).
   - Rejected: a conditional canary on its own nets, because it would depend on the condition grammar under test.

2. **Three modules share one grammar.**
   - `rulemap.py` is a leaf that imports `core`, `model.rules`, `sexpr`, `versions` and c0009's `layers`. It holds the closed tables and the pure functions in both directions: kind map, limits, selector table per major, values, names and layer split.
   - `dru.py` imports `rulemap`. It holds the dialect front end, `read_rules`, `write_rules` and the self-check.
   - `lowering.py` imports `dru` and `rulemap`. It holds `lower_rules`. c0010 adds net classes to it.
   - Rejected: the kind map and selector table inside `lowering.py`, as the brief lists them. `lower_rules` needs `dru`'s self-check, and `dru`'s reader needs the inverse grammar, so the two modules would import each other.
   - Rejected: separate tables for reading and writing. They would drift, and only the self-check would notice, at run time.

3. **The dialect front end.** `parse_rules(text, *, file="") -> RulesDocument` works in five steps.
   1. A line whose first non-blank character is `#` becomes a `CommentItem` with its exact text and line number. It is then replaced by spaces of the same length, so offsets and line numbers elsewhere do not move.
   2. A symbol atom containing `'` outside double-quoted strings raises `FormatError` with the message `line N: …`, `locator == "line N"` and the offset. 10.0.6 drops the whole file for a single-quoted rule name (S-0020). 9.0.9 has not been observed; `H-K-DRU-QUOTE` holds that claim, and the broken control of Decision 18 settles it. The parser refuses such names either way, because a file read once may be written for either major.
   3. The blanked text is parsed with `versions.wrap_rules`.
   4. Each top-level list becomes a `VersionItem` or a `RuleItem` that keeps its exact source text. A comment line inside a list stays in that item's text, and the item is marked `has_comment`. Such an item can only stay opaque.
   5. The version comes from `versions.inspect(document.node)`. A missing version is a `FormatError` (Fenolite policy, recorded in `rules.md`). A version below 1 raises `UnsupportedFormatError`, and a version above 1 is `FUTURE`. A second `version` list, or an atom at top level, is a `FormatError`.

   More rules:
   - `document.node` is the synthetic `kicad_dru` node of the version and rule lists, without comments. It is the input of `check_emittable`.
   - `print_rules(items)` writes each item's text followed by a newline. Blank lines between items are not kept.
   - Only whole-line comments exist. A `#` after other content on a line is not a comment, so it fails as a top-level atom.
   - Rejected: a rules option in the `sexpr` parser (c0007 Decision 2).
   - Rejected: a second lexer, which would duplicate the escape and number rules of `sexpr`.
   - Rejected: dropping comments. They are the user's content.

4. **Slots of a rules file.** `RuleSet.ext["kicad"]` holds the file slot list (relative locator `.`), one slot per item in file order:
   - `Modeled("version")` for the version list;
   - `Modeled("rules")` for each lifted rule; the k-th such slot stands for `RuleSet.rules[k]`;
   - `Opaque(text, "<file version>")` for every comment line and every rule kept opaque, with its exact source text.

   Each lifted `Rule.ext["kicad"]` holds the rule's clause slots `Modeled("name")`, `Modeled("constraint")`, `Modeled("condition")`, `Modeled("layer")` and `Modeled("severity")` in file order. They record which clauses were present and where.
   - Opaque rules fragments may hold comments, so they are not S-expression fragments. `dru` walks the slots itself, with the semantics of `slots.rebuild`: the k-th modelled slot emits `rules[k]`, extra rules follow the last `rules` slot, and removed rules leave their neighbours in place. It never calls `opaque_child` on rules slots.
   - Opaque minimum versions are the file version (`"1"`). Both majors share that header, so gating uses `check_emittable` (Decision 11), not minimum versions.
   - A future file (version 2 or more) keeps every item opaque with that version, so `write_rules` refuses it with `FutureFormatError` (FEN-3002) through `versions.require_editable`.
   - Rejected: `Node.comments`, which `kicad-sexpr` allows on the root only.
   - Rejected: new model fields. The model stays unchanged.

5. **Lifting is the exact inverse of lowering.** `read_rules` lifts a rule list into a `Rule` only when every child is in the closed grammar of Decisions 8 to 10:
   - a name atom;
   - exactly one `constraint` of a mapped type, with limits allowed for its kind and values in `mm`, `mil` or `in`;
   - at most one `condition` in the closed expression grammar, up to whitespace and redundant parentheses;
   - at most one `layer` clause holding one layer name (not `outer` or `inner`);
   - at most one `severity` of `error`, `warning` or `ignore`.

   Anything else stays opaque, with the info `rules.kept-opaque` naming the first reason. More rules:
   - A lifted `hole_size` whose condition has the conjunct `A.Type == 'Via'` stays `hole_size` with an `item_kind via` selector. This is the normal form; `via_drill` is never lifted.
   - `rulemap.normal_form(rule)` is what lifting gives back: `via_drill` becomes `hole_size`, and its `selector_a` becomes `item_kind via` when it is `all`, and `and(item_kind via, <selector_a>)` otherwise, flattened when `selector_a` is itself an `and`; nested `and` and `or` items are flattened; a `selector_b` of `all` becomes `None`. The self-check (Decision 12) compares lifted rules with this form.
   - The `all` case is separate because the model refuses an `and` of fewer than two items (`model/rules.py`) and `all` below the top level is unsupported (Decision 8). Lowering writes `A.Type == 'Via'` alone, which lifts as `item_kind via`.
   - Priority is the number of rule items (lifted or opaque) after the rule, plus 1. The last rule gets priority 1, which matches the model ("1 is the highest") and the later-wins order.
   - A missing `severity` lifts as `"error"` and leaves no severity slot.
   - Ids: a rule gets `derived_id("rul", "kicad", "rule:<name>")`, and the k-th repetition of a name gets `"rule:<name>:<k>"`. The rule set gets `derived_id("rst", "kicad", "rules")`.
   - Provenance is `Provenance("kicad", file, sha256, "/kicad_dru/rule[i]", dru.EVIDENCE)`, with the locators `check_emittable` uses.
   - Rejected: approximate lifting, such as `A.NetName != 'X'` read as `not(net X)`. Every lifted form must lower back to an equivalent text, and each new form costs an oracle row.

6. **Two writers: a round-trip codec and the lowering.**
   - `write_rules(ruleset, *, target, allow_lossy, issues)` is the codec. It writes `(version 1)` first, then follows the file slots of Decision 4. Rule names are kept. Rules without slots follow in tuple order. Each rule keeps its clause order and presence. A clause the model now needs (a severity other than `error`, a layer) is inserted in the canonical order `layer`, `condition`, `constraint`, `severity`, the order of the manuals' syntax summary (S-0010; INFERRED, the order carries no meaning). A rule without slots always gets `(severity …)`, so a project severity override cannot change it.
   - `lower_rules(ruleset, *, target, allow_lossy)` is the D6 generator for rule sets without kicad slots. It sorts (Decision 7), renames (Decision 10), then calls `write_rules`, so gating and self-check are shared. A rule set with kicad slots raises `ValueError` naming `write_rules`; merging user files is c0019's work.
   - Return types. `lower_rules` returns c0017's neutral writer result `WriteResult(text, issues)`, under the brief's name `LoweredRules`, an alias, so c0010 and c0011 can use either name and no second result type exists. `write_rules`, `write_footprint` and `write_pretty` keep the brief's signatures: `str` (or `dict[str, str]`) with an `issues` out-list, the convention of c0008's readers. They are building blocks: `lower_rules` calls `write_rules`, and `write_pretty` calls `write_footprint` once per file. Every error raises in both styles, so the out-list holds what `WriteResult.issues` would hold: warnings and infos.
   - Rejected: one writer that sorts and renames read files. It would destroy the user's names and order.
   - Rejected: `lower_rules` on rule sets read from files. It would have to choose between file order and priorities.

7. **Priority order.** `lower_rules` emits rules with priority 0 ("unset") first, then in descending priority, so priority 1 comes last. Ties are broken by name, then by id, a Fenolite choice recorded in `rules.md`. The later rule wins (`H-K-DRU-ORDER`), so priority 1 governs.
   - Proof on both majors: two tracks with a 2 mm gap. A 1 mm rule followed by a 3 mm rule gives the 3 mm violation, the reversed order gives none, and the canary fires in both runs.
   - The fixture `tests/data/kicad/rules/overlap.kicad_dru` stays as c0020's permanent positive control.
   - If the measured rule is not "later wins", or the majors differ, `rulemap.rule_order` follows the measurement per target, `with_canary` moves the canary to the end of the file for that target (so it still governs nothing else), and the change does not merge before the proof passes.
   - Rejected: waiting for c0020, which would ship an unproved order that every later test depends on.

8. **The selector grammar is closed and gated per major.** Side `S` is `A` for `selector_a` and `B` for `selector_b`.

   | model selector | condition text | `SELECTOR_SUPPORT` key |
   |---|---|---|
   | `all` (top level only) | no term | none: nothing to prove |
   | `net v` | `S.NetName == 'v'` | `net` |
   | `netclass v` | `S.NetClass == 'v'` | `netclass` |
   | `ref v` | `S.memberOfFootprint('v')` | `ref` |
   | `item_kind v`, v in `track`, `via`, `pad`, `zone` | `S.Type == 'Track'`, `'Via'`, `'Pad'`, `'Zone'` | `item_kind` |
   | `and(x, y, …)` | `(x && y && …)` | `and` |
   | `or(x, y, …)` | `(x \|\| y \|\| …)` | `or` |
   | `not(x)` | `!(x)` | `not` |
   | `*` inside a leaf value | the value as written | `glob` |
   | a `selector_b` other than `all` | the `B.` side | `selector_b` |
   | a non-empty `Rule.layers` (Decision 10) | `(layer "<name>")` | `layer_clause` |

   - Both sides combine as `<A> && <B>`. Each side is a leaf or a parenthesised compound, and an `all` side adds no term. `selector_b` is allowed only for `clearance`.
   - `rulemap.SELECTOR_SUPPORT` maps each key to the majors where its `dru-cond-*` probe passed. Every entry starts empty, so before the oracle has run only rules on `all` lower (brief, key decision 3). Task 5.3 adds a major to an entry only from a passing outcome on that major. A key is emitted for a target only when that target is in its entry.
   - Unit tests set the table with `monkeypatch`. Oracle tests set only the keys their bench needs, for the running major; the DRC report still judges them.
   - `rules.unsupported-selector` (error) covers: the `layer` op (use `Rule.layers`); `all` below the top level; an `item_kind` value outside the table; a value containing `'`, `"`, `?`, `[` or `]`; a `*` for a target outside the `glob` entry; a `selector_b` for a target outside its entry; and any op outside its entry. A rule with layers for a target outside the `layer_clause` entry gives `rules.unsupported-layer` (Decision 10).
   - Letter case is not a key. The conditions fixture also records whether `S.NetName == 'n1'` matches net `N1`. The model's globs are case-sensitive. If KiCad's are not, `rules.md` records it and c0011, which knows the nets, refuses names that differ only in case (Open Questions).
   - Rejected: approximations, such as the `layer` op as `existsOnLayer` or `?` read as `*`. A rule that KiCad enforces on other items than the model says is worse than a refusal.

9. **Kinds, limits, values and severity.**

   | kind | written constraint | limits |
   |---|---|---|
   | `clearance` | `clearance` | `min` |
   | `edge_clearance` | `edge_clearance` | `min` |
   | `track_width` | `track_width` | `min`, `opt`, `max` |
   | `via_diameter` | `via_diameter` | `min`, `opt`, `max` |
   | `hole_size` | `hole_size` | `min`, `max` |
   | `via_drill` | `hole_size`, with the conjunct `A.Type == 'Via'` before the selector term | `min`, `max` |

   - Limits come from S-0010 and S-0038 (INFERRED). The oracle proves the `min` limit of each kind (`H-K-DRU-KIND`). A kind refuted on a major blocks the merge until its mapping is corrected, as for order (Decision 7).
   - Another limit, or no limit at all, gives `rules.unsupported-limit` (error).
   - Values are written as `format_length(nm, "mm")`, the shortest exact decimal. They are read with `rulemap.parse_value`, which accepts only `mm`, `mil` and `in` through `core.units.parse_length`. Other units and unitless values keep the rule opaque.
   - Limits are written in the order `min`, `opt`, `max`.
   - Severity maps one to one. KiCad's `exclusion` keeps the rule opaque.
   - Rejected: rounding values, and writing mils for values that are whole mils. Exact mm keeps one spelling per value.

10. **Layers and names.**
    - An empty `Rule.layers` writes no layer clause. One layer writes `(layer "<name>")`. Several layers write one KiCad rule per layer, in tuple order, each name suffixed `_<layer slug>`. A layer name must pass c0009's `layers.is_canonical(name)`, which is true only for names the layer table matches (`F.Cu`, `In<n>.Cu`, `*.SilkS`, `User.<n>`, …), without the row-type fallback of `layers.layer_kind`. c0009 provides it for this check. Other names give `rules.unsupported-layer` (error).
    - `lower_rules` names rules `fenolite_<priority>_<slug>`. The slug is the rule name in lower case with each run of characters outside `[a-z0-9]` replaced by `_`, trimmed, or `rule` when empty. A repeated name gets `_2`, `_3`, … in emission order. Names are written as double-quoted strings.
    - Rejected: user names verbatim in `lower_rules`. Two model rules may share a name, and KiCad reports violations by rule name.
    - Rejected: one rule with `(layer outer)` for `F.Cu` plus `B.Cu`. The two are not equal on every stackup, and `outer` keeps a rule opaque on read.

11. **Target gating and lossy refusals.** `write_rules` checks every opaque rule and every unknown top-level list with `check_emittable` on a synthetic `kicad_dru` node holding `(version 1)` and that item. The version list is needed: without it `check_emittable` reports `kicad.version.header-missing` (error). Comment items are not checked.
    - The item text is parsed first. An item that does not parse raises `RulesSelfCheckError` with step `parse` (Decision 12), before any gating issue. Such text cannot come from `read_rules`; only a caller that built the slot by hand can produce it.
    - `kicad.token.too-new`: target 9 refuses the item. This covers the seven 10.0-only constructs, also inside preserved rules.
    - `kicad.token.uninventoried`: target 9 refuses the item as well, because nothing proves that 9.0.9 reads it. This covers `assign_component_class`, whose shape no public page documents (c0007's open question). Target 10 keeps the item and passes the warning on.
    - A refusal raises `RulesLossError`, a `LossyWriteError` (FEN-7001) that carries the issues, because 9.0.9 would silently drop the whole file (`H-K-TOK-RULES-DRIFT`). With `allow_lossy=True` the item is dropped instead, with the warning `rules.dropped-for-target` naming the rule and the token.
    - Modelled rules use only rows that exist in 9.0. Unsupported selectors, limits and layers are errors that `allow_lossy` never drops.
    - Rejected: silently stripping items.
    - Rejected: refusing every opaque rule for target 9. Most of them use 9.0 floor rows and load (`H-K-TOK-RULES-FLOOR`).

12. **Self-check before text is returned.** `write_rules` checks its own output in four steps:
    1. the text parses with `parse_rules`;
    2. `check_emittable(document.node, FileKind.RULES, target)` returns no error;
    3. `read_rules(text)` lifts every rule written from the model back to the same normal form (Decision 5): name, kind, selectors, layers, limits and severity;
    4. every comment and opaque rule comes back as the same opaque slot, in the same order.

    Any failure raises `RulesSelfCheckError` (`cli_code` `FEN-1001`, a bug), and no text is returned. `lower_rules` inherits the check through `write_rules`.
    - Rejected: trusting the writer. A silently dropped file is the failure this change exists to prevent.

13. **Issue codes and errors.** `rulemap.RULE_ISSUE_CODES` is closed:

    | code | severity | when |
    |---|---|---|
    | `rules.unsupported-selector` | error | Decision 8 |
    | `rules.unsupported-limit` | error | a limit the kind does not take, or no limit (Decision 9) |
    | `rules.unsupported-layer` | error | a layer name for which `layers.is_canonical` is false, or a layer clause for a target outside the `layer_clause` entry (Decisions 8 and 10) |
    | `rules.dropped-for-target` | warning | `allow_lossy` dropped an item the target cannot load (Decision 11) |
    | `rules.kept-opaque` | info | `read_rules` kept a rule opaque, naming the reason (Decision 5) |

    The writers also pass on `check_emittable`'s `kicad.token.uninventoried` warning for target 10.
    - `RulesLossError(LossyWriteError)` carries `issues` and `droppable`. Its hint names `--allow-lossy` only when every error is droppable. Otherwise it says to rewrite the rule with the selectors of `docs/formats/kicad/rules.md`.
    - `RulesSelfCheckError(FenoliteError)` has `cli_code = "FEN-1001"` and carries the failing step.
    - Dialect errors are `FormatError` (FEN-3004). Future files raise `FutureFormatError` (FEN-3002) on write.

14. **Fenolite ships no requirement values (D6).** The lowering writes only the rules of the user's `RuleSet`, and no default rule, table or value. An empty rule set lowers to `(version 1)` alone. The rule covers the files Fenolite writes for the user (`lower_rules`, `write_rules`, build outputs). Diagnostic oracle rules written only to temporary copies, such as the canary that c0013's `drc.kicad` stage appends (batch plan, section 6.9), are exempt, because they never reach the user's files. This is a `rules-model` requirement, not an ADR, so the next ADR number stays free for the sheet-template ADR (c0012).

15. **Footprint writer.** `write_footprint(defn, *, target=DEFAULT_TARGET, allow_lossy=False, issues=None) -> str`:
    - It calls `require_editable` on the definition, as c0017's `place_footprint` does. A definition from a future file raises `FutureFormatError`.
    - A definition without a slot list raises `ValueError`. Footprint generation from scratch is out of scope.
    - The header is `(footprint "<name>" (version V) (generator "fenolite") (generator_version "<target>.0") …)` with `V = FORMAT_VERSIONS[FileKind.FOOTPRINT][target]`. The new header atoms replace the source's `version`, `generator` and `generator_version` slots in place. Missing ones are inserted after the name, in that order.
    - The other children follow the definition's slot list. Modelled children come from c0017's footprint emitter, `_fpmap.emit_footprint(defn, root_chain=("footprint",))`. Opaque children are re-emitted verbatim.
    - Projections are reconciled in `mod.py`. c0017's reconciliation (its Decision 10) lives inside `write_board`, works on `Component.ref` and `.value`, and exposes no shared helper. `write_footprint` applies the same rule to definitions: before re-emitting a projected fragment, it projects the fragment again with `mod`'s own reader function and compares the result with the definition. An edited `properties["Reference"]` or `properties["Value"]` rewrites only that property's value atom. Any other difference (other `properties`, `keywords` from `tags`, `models` from `model`, `Graphic.width` from `stroke`, `Pad.padstack`) gives `kicad.footprint.projection-read-only` (error), naming the field and the locator.
    - `mod.WRITE_ISSUE_CODES` is the closed table of the footprint writer: `kicad.footprint.dropped-too-new` (warning) and `kicad.footprint.projection-read-only` (error). The section "Writing footprints" of `libraries.md` lists it, and a unit test checks that every `kicad.footprint.` literal in `backends/kicad` is a key, as c0008's `test_closed_set` does for `kicad.lib.`. Errors raise `LossyWriteError` (FEN-7001) with `issues` and `droppable`, true only when every error is a too-new token in an opaque slot (c0017 Decision 12).
    - The writer does not imitate KiCad's save-time sort of pads and graphics. Equality is judged on the model and on load, never on bytes.
    - The emitted node goes through `check_emittable(node, FileKind.FOOTPRINT, target)`. A `kicad.token.too-new` error raises `LossyWriteError` (FEN-7001). With `allow_lossy=True`, the smallest opaque slot holding the token is dropped, with the warning `kicad.footprint.dropped-too-new`. Any other error aborts.
    - As for c0017's embedding, a definition read from a 10.0 file may be written for target 9 when every fragment passes. There is no whole-file downgrade refusal, because gating is per fragment.
    - `write_pretty(defs, *, target=DEFAULT_TARGET, allow_lossy=False, issues=None) -> dict[str, str]` maps `"<name>.kicad_mod"` to text, sorted by name. A repeated name, or a name containing `/`, `\` or `:`, raises `ValueError`. Writing to disk is the caller's job.
    - Rejected: sorting children like KiCad's save. It is unspecified and would change user files for no gain.

16. **Board footprints as definitions.** `footprint_from(loaded, *, library=None, issues=None, root_chain=("footprint",), index=0)`:
    - With `root_chain == ("kicad_pcb", "footprint")`, `loaded.node` is a board root, and the definition is read from its `index`-th `footprint` child. The version policy is the board's (`FileKind.BOARD`). Locators are `/kicad_pcb/footprint[index]/…`.
    - When `library` is `None`, the header lib_id is split at its first colon: the library is the text before it, the name the text after it. A lib_id without a colon gives `library == ""` and the whole text as name.
    - Correction: the draft used c0008's `libs.split_lib_id`. It raises `kicad.lib.invalid-id` for a lib_id without a colon, and `libs` imports `mod.footprint_from`, so `mod` cannot import it without a cycle. `mod` splits the text itself.
    - Coordinates and angles are taken as stored: pad angles are absolute and bottom footprints stay mirrored. Board-only children (`at`, `path`, `sheetname`, `sheetfile`, the placement `uuid`, pad `net`, `pinfunction` and `pintype`) are opaque slots when present. c0009's `two_layer.kicad_pcb` has no `path` (c0009 Decision 19), so an inline board text in `test_mod_write.py` covers `path`, `sheetname` and `sheetfile`.
    - The behaviour is a `kicad-library-read` requirement ("Board footprints read as definitions"), next to c0008's "Footprint file reading", because it is footprint reading.
    - Two placements of one footprint give equal ids. Such definitions serve round trips and comparisons, not a `Library`.
    - `board_footprints(source, *, file="", issues=None) -> tuple[FootprintDef, ...]` reads every footprint of a board this way.
    - The corpus round trip covers every footprint of every non-heavy demo board that c0009 reads with 0 errors, at the board's own major, and of the `pcb upgrade --force` copies of the third-party rows made on 10.0.6 (origin `third-party`). Each one is written with `write_footprint` and re-read with `read_footprint(text, library=defn.library)`.
    - It must be equal ignoring provenance and `ext`, and the opaque fragments of the original must reappear in order, apart from the header heads the writer sets. This settles the footprint half of `H-K-LIB-READ` as `CORPUS-VERIFIED` over two origins.
    - Rejected: converting board footprints to the library frame. Flip rules are c0017's oracle, and a codec proof must not depend on them.

17. **Footprint oracle and escapes.**
    - Every `kicad-cli` call goes through c0009's package runner, `KicadCli.run(args, files=...)`, and results are read from `CliRun.outputs`. c0009's requirement "Package kicad-cli runner" asks this of every oracle test added from c0009 on, so c0008's `_libs.kicad` helper is not used. Output folders are empty folders passed in `files`.
    - On 10.0.6, `Mini.pretty` written for target 10, and on 9.0.9, `Mini_v9.pretty` written for target 9, must load with `fp export svg` (one SVG per footprint in the outputs).
    - Each must survive `fp upgrade --force -o up/<library>` into the runner's empty `up` folder and re-read equal to the original definitions, ids included, ignoring provenance and `ext`.
    - On 9.0.9, `Mini.pretty` written for target 9 with `allow_lossy=True` loads too, and one warning is reported per dropped fragment.
    - The authored 9-format `tests/data/libs/Escapes_v9.pretty/Mini_Escapes.kicad_mod` carries one property per escape form of c0006's `tests/data/kicad/sexpr/escapes.kicad_pcb`: `\"`, `\\`, `\n`, `\r`, `\t`, `\v`, `\7`, `\101`, `\x42` and the unknown `\e`, plus one non-ASCII value. Its `descr` is set through the model to the concatenation of the eight `ENCODER_VALUES` of c0006's `tests/kicad/test_sexpr_oracle.py` (`\r`, `\v` and `\x01` included), so `Atom.string` encodes it. After `fp upgrade --force` on 9.0.9, the decoded values must equal the originals.
    - These are the forms and values that prove the row on 10.0 (`test_escapes_after_upgrade`, `test_encoder_after_upgrade`), so the test settles the 9.0 half of `H-K-SEXPR-ESCAPES` for the row's whole statement.

18. **Rules oracle tests and probe records.** The tests live in `tests/kicad/rules/` (`needs_kicad`, isolated configuration, every run through c0009's runner on a copy). Benches are built by `_bench.py` through the model API and c0017's `write_board` for the running major, with a `{}` project file. They are never committed.
    - `test_rule_dialect.py`: the comments, units and selectors fixtures each load with the canary, and the `mil` and `in` rules give their violations (`H-K-DRU-DIALECT`). The broken fixture is copied verbatim and gives exit 0 without the canary, which reproduces the silent disable (`H-K-DRU-QUOTE` on 9.0.9). `dru-broken-silent` records the observed outcome per major. If 9.0.9 loads the broken fixture, the row is refuted for 9.0 with a `-2` successor, and the 9.0.9 control copies `ten_only.kicad_dru` verbatim instead, which 9.0.9 drops whole (`H-K-TOK-RULES-DRIFT`).
    - `test_rule_order.py`: Decision 7 (`H-K-DRU-ORDER`).
    - `test_rule_kinds.py`: one fixture per kind. A violation must name the probed item's uuid, with the type recorded for that kind in `rules.md` (`H-K-DRU-KIND`).
    - `test_rule_conditions.py`: one case per `SELECTOR_SUPPORT` key, plus letter case: `net`, `netclass` (`'Default'` against an absent class), `ref`, `item_kind`, layer clause, `and`, `or`, `not`, `selector_b`, glob and letter case. Each one yields exactly its expected probe-pair violations, with the canary firing (`H-K-DRU-COND`, `H-K-DRU-GLOB`).
    - `test_rule_gating.py`: `ten_only.kicad_dru` read with `read_rules`. Target 9 raises `RulesLossError`. Target 9 with `allow_lossy` drops the rule, and the file loads on 9.0.9 with the canary. Target 10 loads on 10.0.6 with the canary.
    - `dru-cond-<key>` records `present` when the probe pair's violation is present and the control pair's is absent, and `absent` otherwise. A condition case without the canary fails before it records anything. `test_rulemap.py -k support` checks that each `SELECTOR_SUPPORT` entry holds exactly the majors whose committed probe file records `present` for that key.
    - Each outcome is recorded with c0017's `_probes` helper under ids `dru-*` and `fp-write-*`. This change adds those ids, with the majors each runs on, to c0017's closed `PROBES` mapping in `tests/kicad/_probes.py`. `test_probe_results.py` compares them with `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json` in both jobs.

19. **Hand-over to later changes.**
    - c0010 extends `lowering.py` with net classes and ships `.kicad_pro` with every `.kicad_dru`. Its floor warning compares lowered net-class values with the preserved project floor; extending it to custom rules is an open question of c0010. This change adds `lower` to the KiCad backend's `operations`, because it ships `lower_rules` (c0009's design lists `lower` for c0018 and c0010). c0010 extends the lowering with net classes and leaves `operations` as it is.
    - c0011 calls `lower_rules` on the DSL's `RuleSet` and refuses on `RulesLossError`.
    - c0019 merges user rules after Fenolite's with `parse_rules` and `print_rules`.
    - c0013 appends a canary in its `drc.kicad` stage.
    - c0020 keeps `overlap.kicad_dru` as its positive control.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/kicad/rulemap.py` (new) | `KIND_MAP: Mapping[RuleKind, str]`; `LIMITS: Mapping[RuleKind, frozenset[str]]`; `ITEM_TYPES: Mapping[str, str]` (`track` → `Track`, `via` → `Via`, `pad` → `Pad`, `zone` → `Zone`); `SELECTOR_SUPPORT: Mapping[str, frozenset[int]]` (the keys of Decision 8: `net`, `netclass`, `ref`, `item_kind`, `and`, `or`, `not`, `glob`, `selector_b`, `layer_clause`; every entry empty until task 5.3); `RULE_ISSUE_CODES: Mapping[str, Severity]`; `parse_value(text: str) -> Nm`; `format_value(nm: Nm) -> str`; `slug(text: str) -> str`; `condition_text(rule: Rule, *, target: int) -> tuple[str \| None, tuple[Issue, ...]]`; `parse_condition(text: str) -> tuple[Selector, Selector \| None] \| None`; `rule_nodes(rule: Rule, *, target: int, slots: Sequence[Slot] = ()) -> tuple[tuple[Node, ...], tuple[Issue, ...]]`; `lift_rule(node: Node) -> Rule \| str` (a rule, or the reason it stays opaque); `normal_form(rule: Rule) -> Rule`; `rule_order(rules: Sequence[Rule]) -> tuple[Rule, ...]` |
| `src/fenolite/backends/kicad/dru.py` (new) | `EVIDENCE: Evidence`; `RULES_VERSION = 1`; `@dataclass(frozen=True, slots=True)` `VersionItem(version: int, text: str, line: int)`, `RuleItem(node: Node, text: str, line: int, has_comment: bool = False)`, `CommentItem(text: str, line: int)`; `RulesItem = VersionItem \| RuleItem \| CommentItem`; `RulesDocument(items: tuple[RulesItem, ...], file: str = "")` with property `node -> Node` and `version -> int`; `parse_rules(text: str, *, file: str = "") -> RulesDocument`; `print_rules(items: Iterable[RulesItem]) -> str`; `read_rules(text: str, *, file: str = "", issues: list[Issue] \| None = None) -> RuleSet`; `write_rules(ruleset: RuleSet, *, target: int = DEFAULT_TARGET, allow_lossy: bool = False, issues: list[Issue] \| None = None) -> str`; `class RulesLossError(LossyWriteError)` (`issues`, `droppable`); `class RulesSelfCheckError(FenoliteError)` (`cli_code = "FEN-1001"`, `step`, `issues`) |
| `src/fenolite/backends/kicad/lowering.py` (new) | `EVIDENCE: Evidence`; `LoweredRules = WriteResult` (an alias of c0017's `backends.base.WriteResult(text, issues)`); `lower_rules(ruleset: RuleSet, *, target: int = DEFAULT_TARGET, allow_lossy: bool = False) -> LoweredRules`; `lowered_names(rules: Sequence[Rule]) -> tuple[str, ...]` |
| `src/fenolite/backends/kicad/mod.py` | adds `write_footprint(defn: FootprintDef, *, target: int = DEFAULT_TARGET, allow_lossy: bool = False, issues: list[Issue] \| None = None) -> str`; `write_pretty(defs: Iterable[FootprintDef], *, target: int = DEFAULT_TARGET, allow_lossy: bool = False, issues: list[Issue] \| None = None) -> dict[str, str]`; `board_footprints(source: Source, *, file: str = "", issues: list[Issue] \| None = None) -> tuple[FootprintDef, ...]`; `WRITE_ISSUE_CODES: Mapping[str, Severity]`; `footprint_from` gains `root_chain: tuple[str, ...] = ("footprint",)` and `index: int = 0`; `HEADER_HEADS = ("version", "generator", "generator_version")` |
| `src/fenolite/backends/kicad/__init__.py` | re-exports `write_footprint`, `write_pretty`, `read_rules`, `write_rules`, `lower_rules` |
| KiCad backend capability report (c0009) | `write_kinds` gains `kicad_mod` and `kicad_dru`; `operations` gains `lower`; `read_kinds` unchanged (see Corrections) |
| `src/fenolite/backends/kicad/PROVENANCE.md` | rows: custom rules dialect, precedence and conditions; footprint writer header; rules oracle |
| `tests/data/kicad/rules/comments.kicad_dru`, `units.kicad_dru`, `selectors.kicad_dru`, `overlap.kicad_dru`, `ten_only.kicad_dru`, `opaque.kicad_dru`, `broken.kicad_dru` | authored CC0 fixtures, declared in `tests/data/MANIFEST.toml` |
| `tests/data/libs/Escapes_v9.pretty/Mini_Escapes.kicad_mod` | authored CC0, 9.0 format |
| `tests/unit/backends/kicad/test_mod_write.py`, `test_rulemap.py`, `test_dru.py`, `test_lowering.py` | hermetic tests |
| `tests/corpus/test_footprint_rt.py` | `needs_corpus`; the upgraded half also `needs_kicad` and `kicad_min_major(10)` |
| `tests/kicad/libs/test_mod_write_oracle.py` | `needs_kicad`, major-aware |
| `tests/kicad/rules/_bench.py`, `test_rule_dialect.py`, `test_rule_order.py`, `test_rule_kinds.py`, `test_rule_conditions.py`, `test_rule_gating.py` | `needs_kicad`, major-aware; `_bench.py` provides `bench(target, *, pairs, vias=(), parts=()) -> Bench`, `with_canary(text: str) -> str`, `canary_fired(report, bench) -> bool`, `require_canary(report, bench) -> None` (`pytest.fail` with "rules file not loaded"), `violations_between(report, a, b) -> tuple[DrcViolation, ...]` |
| `tests/kicad/rules/test_bench.py` | hermetic (no `needs_kicad`): `require_canary` fails on a report without the canary violation and passes on one with it |
| `docs/formats/kicad/rules.md` (new) | fact table, grammar tables, issue codes |
| `docs/formats/kicad/libraries.md` | section "Writing footprints" |
| `tests/kicad/_probes.py` (c0017; extended) | new `PROBES` entries: `fp-write-*`, `dru-dialect-*`, `dru-broken-silent`, `dru-order-*`, `dru-kind-*`, `dru-cond-<key>` and `dru-gating-*` |
| `docs/evidence/kicad/probes/9.0.9.json`, `10.0.6.json` | regenerated with the `dru-*` and `fp-write-*` outcomes |

Layering: `rulemap` imports `core`, `model.rules`, `model.base` and `backends.kicad.{sexpr,versions,layers}`. `dru` adds `backends.kicad.{rulemap,slots}` and c0017's `versions.LossyWriteError`. `lowering` adds `backends.kicad.dru` and `backends.base`. `mod` adds c0017's `_fpmap.emit_footprint` and never imports `libs`, which imports `mod`. Nothing imports `lowering`, so there is no cycle. All edges stay within `package-layering`.

## Sources registered by this change

None. The facts come from rows that already exist. Task 1.1 extends their "used for" cells instead of registering duplicates:

| id | URL | licence of source | used for (added text) |
|---|---|---|---|
| S-0010 | https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html | GPL-3.0-or-later or CC-BY-3.0-or-later (stated on the page) | 9.0 custom rules: rule order and precedence, condition syntax (`A`/`B`, properties, functions, operators, `'…'` literals), units, `#` comments, layer clause, severity, constraint limits |
| S-0034 | https://gitlab.com/kicad/code/kicad/-/blob/<tag>/common/drc_rules.keywords; tags 9.0.0, 10.0.6 | GPL-3.0-or-later (single names only, never converted into data) | presence of the single name `assign_component_class` at each tag |
| S-0038 | https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#custom_rule_syntax | GPL-3.0-or-later or CC-BY-3.0-or-later (stated on the page) | 10.0 custom rules: precedence, condition syntax, board-setup minimums acting as floors |

Rows of other changes cited here: S-0001 and S-0040 (footprint grammar, c0005 and c0008), S-0020 (observed `kicad-cli` 10.0.6 behaviour, c0006), S-0022 and S-0037 (`fp upgrade`, `fp export svg`, `pcb drc`), S-0029 (pinned images) and S-0030 (version constants, c0007). The DRC report structure is c0017's `docs/formats/kicad/drc.md`.

Should a new URL be needed during implementation, it takes the next free id of block S-0060 … S-0064, which the batch plan gives this change (see Corrections). No KiCad source file is read except the keyword file S-0034, for single names only.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-DRU-ORDER | When two rules of one constraint type both match an item pair, the rule later in the file governs (S-0010, S-0038) | `tests/kicad/rules/test_rule_order.py::test_later_rule_wins` | two tracks with a 2 mm gap: 1 mm then 3 mm gives the clearance violation, 3 mm then 1 mm gives none, and the canary fires in both runs, on 9.0.9 and 10.0.6 |
| H-K-DRU-DIALECT | `#` comment lines between and inside rules, values in `mm`, `mil` and `in`, and `'…'` literals inside double-quoted conditions load (S-0010, S-0038) | `tests/kicad/rules/test_rule_dialect.py::test_dialect_loads` | the canary fires for each dialect fixture, and the `mil` and `in` rules each give their violation, on 9.0.9 and 10.0.6 |
| H-K-DRU-COND | Each op of the closed selector table, a `B.` side and a layer clause select exactly the items the model selects (S-0010, S-0038) | `tests/kicad/rules/test_rule_conditions.py::test_condition` (one case per `SELECTOR_SUPPORT` key other than `glob`) | per op and per major: the probe pair's violation present, the control pair's absent, the canary present; the letter-case row is recorded either way |
| H-K-DRU-GLOB | `S.NetName == 'PWR_*'` matches every net whose name starts with `PWR_` (S-0010, S-0038) | `test_rule_conditions.py::test_condition[glob]` | the `PWR_A`/`PWR_B` violation present, the `SIG_A`/`SIG_B` pair clean, the canary present, on 9.0.9 and 10.0.6; if refuted, globs give `rules.unsupported-selector` for that major |
| H-K-DRU-QUOTE | A rules file holding a rule with a single-quoted name is dropped whole, with exit 0, by 9.0.9 as by 10.0.6 (S-0020 for 10.0.6 only) | `tests/kicad/rules/test_rule_dialect.py::test_broken_is_silent` | `broken.kicad_dru` copied verbatim onto a bench gives exit 0 and no canary violation, on 9.0.9 and 10.0.6 |
| H-K-DRU-KIND | Each lowered kind, `via_drill` as `hole_size` with `A.Type == 'Via'` included, is enforced on the items its condition selects (S-0010, S-0038) | `tests/kicad/rules/test_rule_kinds.py::test_kind` (one case per kind) | per kind and per major: one violation naming the probed item's uuid, none on the control item, the canary present |

Settled or updated, not registered: the footprint half of `H-K-LIB-READ` (`CORPUS-VERIFIED`, Decision 16), the 9.0 half of `H-K-SEXPR-ESCAPES` (Decision 17). `H-K-TOK-CONSTANTS` stays `INFERRED` for rules, because no KiCad command writes a rules file. The broken control adds supporting data to `H-K-TOK-RULES-SILENT`. The writers do not depend on an open row: a selector key is written only for the majors where its probe passed.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Footprint codec round trip | CORPUS-VERIFIED (demo boards and upgraded third-party copies; footprint half of `H-K-LIB-READ`) | `tests/corpus/test_footprint_rt.py` |
| Written mini library loads, survives a KiCad re-save and re-reads equal | KICAD-VERIFIED on 10.0.6 (local and `kicad-10`) and on 9.0.9 for target 9 (`kicad-9`) | `tests/kicad/libs/test_mod_write_oracle.py` |
| String escapes on 9.0 | KICAD-VERIFIED (9.0.x), closing `H-K-SEXPR-ESCAPES` with the ten escape forms and eight encoder values of its 10.0 proof | `test_mod_write_oracle.py::test_escapes_9` |
| Footprint gating and `allow_lossy` | mechanical (unit tests); the lossy output's load is KICAD-VERIFIED on 9.0.9 | `test_mod_write.py`, `test_mod_write_oracle.py` |
| Rules dialect (comments, units, literals) | KICAD-VERIFIED (9.0.x, 10.0.x) if `H-K-DRU-DIALECT` holds | `test_rule_dialect.py` |
| Single-quoted names drop the file | KICAD-VERIFIED (10.0.x) today (S-0020); 9.0.x by `H-K-DRU-QUOTE` | `test_rule_dialect.py::test_broken_is_silent` |
| Rule order | KICAD-VERIFIED (9.0.x, 10.0.x), `H-K-DRU-ORDER` | `test_rule_order.py` |
| Each kind | KICAD-VERIFIED per major, `H-K-DRU-KIND` | `test_rule_kinds.py` |
| Each selector op, globs, `selector_b` and the layer clause | KICAD-VERIFIED per key and major (`H-K-DRU-COND`, `H-K-DRU-GLOB`); a key is written only for the majors where it passed | `test_rule_conditions.py` |
| Target-9 refusal and lossy drop | KICAD-VERIFIED (9.0.x, 10.0.x) on top of `H-K-TOK-RULES-DRIFT` | `test_rule_gating.py` |
| Lifting, normal form, names, values, ordering, issue codes, self-check | mechanical (unit tests) | `test_rulemap.py`, `test_dru.py`, `test_lowering.py` |
| Rules header `(version 1)` | INFERRED (`H-K-TOK-CONSTANTS`) | none; no KiCad command writes rules |
| Board-setup floors | INFERRED (S-0038); measured by c0010 | none here |

`dru.EVIDENCE` and `lowering.EVIDENCE` start as `INFERRED` with hypotheses `H-K-DRU-DIALECT`, `H-K-DRU-ORDER`, `H-K-DRU-COND` and `H-K-DRU-KIND`. Task 6.2 raises them to `KICAD-VERIFIED` only when these four rows are `KICAD-VERIFIED (9.0.x, 10.0.x)`. `H-K-DRU-GLOB` is not in the list: a refuted glob is refused on that major and never written. A partly refuted `H-K-DRU-COND` keeps both constants `INFERRED`, naming the row. `mod.EVIDENCE` stays `INFERRED`, because the living requirement "Reading evidence" keeps it there until the symbol half of `H-K-LIB-READ` settles (Open Questions).

## Budget (5.75 working days; part 3 of plan item 0009, day 15)

| work | days |
|---|---|
| registers, provenance, `rules.md`, writer section of `libraries.md` | 0.75 |
| footprint writer, board footprints as definitions, corpus round trip, footprint oracle and escapes | 1.0 |
| dialect front end, `read_rules`, `write_rules`, gating, self-check | 1.25 |
| `rulemap` grammar and `lower_rules` | 1.0 |
| rules oracle: benches and canary, dialect and broken control, order, kinds, conditions, gating | 1.25 |
| closing | 0.5 |
| **total** | **5.75** |

`wks.py` moved to c0012 to make room for the oracle. The 1.25-day oracle line splits as: benches and canary 0.35, dialect and broken control 0.15, order 0.15, kinds 0.2, conditions 0.3, gating 0.1.

First cuts if the work overruns, in order:
1. the glob row and the `ref` op, whose `SELECTOR_SUPPORT` entries then stay empty, so both give `rules.unsupported-selector`;
2. the letter-case row;
3. the kind cases other than `clearance`, `track_width` and `via_drill`. `edge_clearance`, `via_diameter` and `hole_size` then keep `H-K-DRU-KIND` open, so `lowering.EVIDENCE` stays `INFERRED`. `track_width` stays because c0010's fallback canary uses it, and `via_drill` because its mapping is Fenolite's own.

Not optional: the order proof, the canary, target gating, the self-check, and the footprint round trip over two origins.

## Risks / Trade-offs

- [The condition language differs between majors] → each op is proved per major, and an op that fails on 9.0.9 is refused for target 9 only.
- [Glob semantics refuted] → exact names only; `netclass` selectors cover pattern use cases.
- [A one-sided condition is evaluated for one item order only, so `A.NetName == 'X'` misses half the pairs] → each fixture has the matched net in both positions, and `H-K-DRU-COND` records the outcome. If refuted, `rulemap` writes the mirrored `B.` term with `||` for binary kinds, proved by the same fixtures.
- [`A.NetClass` compares a composite name when a net has several classes] → c0010 assigns one class per net through exact-name patterns, so lowered designs never have several. `rules.md` records the limitation.
- [Board-setup minimums act as floors (S-0038)] → recorded in `rules.md`; c0010 warns when a lowered net-class value is below a preserved project floor, and its open question covers custom rules.
- [Upgraded copies rejected as a second origin] → the corpus round trip still runs on the demos. `H-K-LIB-READ`'s footprint half then waits for c0009's fallback search (Open Questions).
- [Blank lines and indentation of user rules files are not kept] → equality is on the model and on load. Comments, rule order and opaque text survive verbatim.
- [Overrun] → the first cuts of the budget section.

## Migration Plan

- Additive: three new modules, new functions in `mod.py`, fixtures and tests. The model, the schemas, `wrap_rules` and `rules_text` are unchanged. To roll back, remove the modules, the new `mod.py` functions and the fixtures, and restore the probe files and capability report.

## Corrections to the brief

Corrections to the brief and to the interrupted draft. Each correction is proved against the repository or the batch on disk.
- **Source block.** The brief reserves S-0070 … S-0079 because c0017's brief had fixed S-0060 and S-0061. c0017's design now uses S-0055 … S-0057 and leaves S-0060 onwards to this change, c0010 uses S-0065 and S-0080, and the batch plan gives this change S-0060 … S-0064. This change registers no source; a new URL takes S-0060.
- **`read_kinds`.** The draft added `kicad_dru` to the backend's `read_kinds`. c0009 ties `read_kinds` to `Backend.read`, whose content is a `Design` or a `Library` ("Read results"), while `read_rules` returns a `RuleSet`. So only `write_kinds` gains `kicad_dru`. `write_kinds` lists the kinds the backend's functions write, as c0017 does for `kicad_pcb`. c0010 adds `kicad_pro` to `read_kinds`; the same reading of c0009 applies there.
- **Lib_id split.** Decision 16 does not reuse `libs.split_lib_id` (it raises for a bare name, and importing it from `mod` would be a cycle).
- **Gating node.** `check_emittable` needs a version list in the synthetic node (Decision 11).
- **`H-K-DRU-KIND` and `test_rule_kinds.py`.** The brief registers ORDER, DIALECT, COND and GLOB only. This change adds KIND for three reasons. `via_drill` as `hole_size` with `A.Type == 'Via'` is Fenolite's own mapping, which only KiCad can confirm. The constraint name and limits of each kind come from the manuals (INFERRED). And c0010's fallback canary, a `track_width` rule, depends on it (c0010 design, Risks). It takes 0.2 day of the oracle line and is third in the cut order (Budget).
- **Single-quoted names on 9.0.9.** The brief says KiCad drops such a file on both majors. Only 10.0.6 was observed (c0007's design). `H-K-DRU-QUOTE` registers the 9.0.9 claim, with a fallback control (Decision 18).
- **CI.** The `kicad-9` and `kicad-10` jobs already run `tests/kicad` with `FENOLITE_REQUIRE`, so `tests/kicad/rules` needs no workflow change.

## Open Questions

- **User question (from the batch plan): do `pcb upgrade --force` copies of the third-party boards, made in a temporary folder on 10.0.6 and never committed, count as the second origin for `CORPUS-VERIFIED`?** The default is yes, through c0009's corpus-policy requirement "Upgraded copies keep their origin". If not, the footprint half of `H-K-LIB-READ` stays `INFERRED` until c0009's fallback search finds native permissive 8.0+ boards.
- **User question (from the batch plan): do you accept the re-baselined budget and cut order?** This change is 5.75 days. Its own first cuts are the glob row, the `ref` op, the letter-case row and three kind cases (Budget).
- c0007's open question on `assign_component_class` is answered: it stays opaque, is refused for target 9 (also under `allow_lossy`, where it is dropped with a warning) and kept for target 10 with the `kicad.token.uninventoried` warning.
- Raising `mod.EVIDENCE` to `CORPUS-VERIFIED` would need a MODIFIED `kicad-library-read` "Reading evidence". The default keeps it `INFERRED` until the schematic change settles the symbol half, and records the footprint half in the `H-K-LIB-READ` row.
- The brief places the kind map and selector table in `lowering.py`. This design moves them to the leaf `rulemap.py` to avoid an import cycle (Decision 2). `lower_rules` stays in `lowering.py`.
- Source ids: this change follows the batch plan's S-0060 … S-0064 instead of the brief's S-0070 … S-0079 (Corrections). It registers none.
- c0017's `backend-protocol` requirement "Write capability fields" states membership (`"kicad_pcb"` in `write_kinds`, "later writers add their kinds"), so adding `kicad_mod` and `kicad_dru` needs no delta of that requirement.
- If `H-K-DRU-COND` finds KiCad's name comparison case-insensitive, c0011 must refuse designs with net or class names that differ only in letter case. The default records the outcome here and leaves the check to c0011.
- c0013's `drc.kicad` stage needs a canary in a command, not a test. The default keeps the canary helpers in `tests/kicad/rules/_bench.py`; c0013 may move them to `src`.
