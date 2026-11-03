# c0349: Explicit physical root edges beside a logical outline

An outline closed through footprint Edge.Cuts may join nearby endpoint coordinates. The writer then fails to recognize five footprint edges in the Tiny reproduction and duplicates them as root graphics. Pure clustering cannot establish ownership: an intentional parallel edge one nanometre away is a counterexample.

Preserve ownership explicitly with existing Board.graphics and allow line/arc DSL calls on Edge.Cuts. Accept logical outline plus physical root edges only when complete deterministic reconstruction exactly matches the logical outline; emit the physical edges without synthetic duplicates. No new model field or approximate comparison is introduced.

The root agent approved this revised scope before runtime changes. Required authored negatives and exact source geometry remain gates. Full CI and archival remain pending until the exact integrated commit passes.
