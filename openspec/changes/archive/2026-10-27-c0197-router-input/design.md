## Context

c0175's design, decision 1 ("Router input fidelity"), holds the decisions of this change; they are not
repeated here. `write_dsn` lowers the rules of `design.rules` over the written classes in `_lower_rules`
(`src/fenolite/backends/specctra/dsn.py`): values combine by maximum; a one-sided clearance calls
`raise_clearance` on its classes; a width rule with `opt` sets every named class (all of them for `all`) to
`opt`. `fenolite route --order GLOB` is repeatable and matches one `fnmatch` glob per tier.

## Decisions

1. **What "a width of its own" is.** A class holds a width of its own when its model class sets
   `track_width`, or when an earlier width rule that names it set `opt`. The default rule's width (the nets
   without a class) has none of its own: it becomes `opt`.
2. **Unclassed nets against a one-sided rule.** The Specctra subset pairs classes only, so the nets without a
   class cannot be kept `min` away from the named class without raising the default rule for every net. They
   keep the default clearance, and one `specctra.rule-not-sent` (info) names the rule and says how to keep it
   (give those nets a class). The existing message for a pair with `Default` is the same.
3. **Self clearance by order.** For each class, the clearance against itself is the value of the last rule (in
   the board's order) whose two sides both include it; the class's own clearance (`NetClass.clearance` or the
   default) is a floor, as every class value is.
4. **Tiers.** Each `--order` value is split on commas and stripped; a net takes the index of the first value
   one of whose globs matches it. An empty glob (`"A,,B"`, `","`) is `FEN-2001`.

## Risks / Trade-offs

- A board whose author relied on a board-wide `opt` to force every net wider gets narrower classes. The info
  issue names every class that kept its width, and a rule that names the classes keeps the old behaviour.

## Open Questions

None: the maintainer accepted c0175's package 1 as written (its design, decision 1) when he chose to start it
on 2026-10-26.
