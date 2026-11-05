# c0389: design

## Task 6.1: the kit script creates its log

In run `2026-11-05-e28d0bb1` (S-1590) the script's `LogLine` called `Append` on `results/script.log` inside
`Try`-`Except` with `Rewrite` as the handler. Altium Designer 24.5.2.23 still showed the `EInOutError`
dialog ("The specified file was not found") and the script stopped. A handler that Altium does not reach
cannot choose between the two calls, so the script now asks first: `FileExists` on the log's path selects
`Rewrite` when the file is missing and `Append` otherwise. No exception is raised on either path.

`FileExists` is not on the DelphiScript functions page (S-0501). The DelphiScript "Statements & Operators"
page of Altium's public documentation (S-1591, read on 2026-11-05) calls `FileExists` with a file name in a
DelphiScript example and acts on its truth value. That page is the call's source; the name was read, and
nothing of the example was copied.

The other way, a kit that ships an empty `results/script.log`, was not taken: the task asks the script to
create the log, and a person who empties `results/` before a run would hit the same stop again.

`H-A-KIT-SCRIPT` stays `INFERRED` until group K2 is run again in Altium (task 6.1 stays open for that run).
