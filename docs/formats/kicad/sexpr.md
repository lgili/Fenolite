# KiCad S-expression syntax

This page states, in Fenolite's own words, what `fenolite.backends.kicad.sexpr` relies on.

- The code is written from this page only. No KiCad source code was read.
- Sources are listed in `docs/evidence/sources.md`. S-0020 means behaviour observed by running
  `kicad-cli` 10.0.6 as an external program on files authored for Fenolite.
- A label other than `KICAD-VERIFIED` or `CORPUS-VERIFIED` names the hypothesis that will settle it.
- `KICAD-VERIFIED (10.0.x)` means checked with a local `kicad-cli` 10.0.6 run on 2026-10-01; the `kicad-10`
  CI job repeats the checks once it runs.
- `tests/unit/test_format_facts.py` checks the table.

| fact | source | label | hypothesis |
|---|---|---|---|
| A file is UTF-8 text holding one list. A list is `(`, a head atom, then children (atoms or lists) in order, then `)`. Space, TAB, CR and LF separate elements. | S-0001 | KICAD-VERIFIED (10.0.x) | H-K-SEXPR-LEX-10 |
| CRLF line endings load the same as LF. | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SEXPR-LEX-10 |
| An unquoted atom is any run of characters other than whitespace and parentheses that does not start with `"`. Files older than format 6 leave strings unquoted when they can (`F.Cu`, `/VCC`, `Lib:Name`). | S-0021 | KICAD-VERIFIED (10.0.x) | H-K-SEXPR-LEX-10 |
| An unquoted atom that contains `"` after its first character loads, and the atom is kept whole. | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SEXPR-LEX-10 |
| A quoted string runs from `"` to the next unescaped `"`. It may hold parentheses, TAB, other raw control characters such as VT, non-ASCII UTF-8 and backslash escapes, but no raw CR or LF. | S-0001, S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SEXPR-LEX-10 |
| A list head can be a number: the board layer table uses `(0 "F.Cu" signal)`. | S-0024 | KICAD-VERIFIED (10.0.x) | H-K-SEXPR-LEX-10 |
| Lines whose first non-blank character is `#` before the root list are skipped by KiCad. Fenolite keeps them as root comments. | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SEXPR-LEX-10 |
| KiCad refuses to load (exit 3) these inputs, and Fenolite rejects them too: empty input, unbalanced parentheses, a byte-order mark or any other character before `(`, a raw LF inside a quoted string, and an atom glued directly after a closing quote (`"a"b`). | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SEXPR-LEX-10 |
| Fenolite also rejects, without claiming KiCad does: content after the root list (KiCad was seen to ignore it), `()`, a list whose first element is a list, a raw CR inside a quoted string, an unterminated string, nesting deeper than 256 levels, and invalid UTF-8. KiCad's outcome on each is recorded in `tests/data/kicad/sexpr/EXPECT.toml`. | S-0020 | INFERRED | H-K-SEXPR-STRICT |
| Escapes read inside quoted strings: `\"`, `\\`, `\n`, `\r`, `\t` and `\v` give their characters. `\` followed by 1 to 3 octal digits, or by `x` and 2 hex digits, gives the encoded character. Any other backslash sequence stays as written (backslash included). | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SEXPR-ESCAPES |
| KiCad writes `"`, `\`, LF and CR inside strings as `\"`, `\\`, `\n` and `\r`, and writes TAB, VT and other control characters (BEL observed) raw. A backslash kept literally by the reader comes back as `\\`. | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SEXPR-ESCAPES |
| Fenolite writes strings as KiCad does for `"`, `\`, LF, CR and TAB. It writes every other C0 control character, VT included, as a 3-digit octal escape, and refuses NUL. It never writes a raw newline: KiCad rejects one, and `pcb upgrade` stops on one. | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SEXPR-ESCAPES |
| Lengths in board and footprint files are millimetres with 1 nm resolution. | S-0001 | INFERRED | H-K-SEXPR-NUM-CORPUS |
| A number is an unquoted atom matching `-?(\d+\.?\d*\|\.\d+)([eE][-+]?\d+)?`. `+0.8`, `0x10` and `1.6mm` are not numbers lexically. | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SEXPR-NUM-READ |
| Where a number is required, KiCad reads exponent (`1e-3`), leading-dot (`.8`), trailing-dot (`1.`), `-0` and over-precise numbers. It refuses to load (exit 3) when it meets `+0.8`, `+.8`, `0x10` or `1.6mm` there. | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SEXPR-NUM-READ |
| KiCad 10 writes no exponent and no trailing zeros or dot, and writes lengths with at most 6 decimals. Values that are not lengths (3D model offset, scale and rotation, pad corner ratios, angles) can carry up to 10 decimals. KiCad 9 files keep a few trailing-zero spellings (`12.000000`). Atom spelling is therefore preserved, never normalised, and `Atom.from_nm` writes at most 6 decimals. | S-0020, S-0024 | KICAD-VERIFIED (10.0.x) | H-K-SEXPR-NUM-WRITE-2 (H-K-SEXPR-NUM-WRITE, "at most 6 decimals everywhere", is refuted) |
| Corpus numbers: exponents appear only in a KiCad 5 third-party board (7 atoms); atoms with more than 6 decimals appear in a few 9.0 demo files, a development write, the worksheet and the KiCad 5 board (counts in `docs/hypotheses.md`). `Atom.to_nm()` raises on an inexact length; `to_nm(exact=False)` rounds half to even. | S-0024, S-0027, S-0028 | INFERRED | H-K-SEXPR-NUM-CORPUS |
| Every non-heavy corpus file of both origins (26 KiCad demo files, 3 third-party boards) parses, and its re-dump is tree-equal and has the same token stream (RT0). One demo board is published malformed at tag 9.0.9.1 and stays rejected. | S-0024, S-0027, S-0028 | CORPUS-VERIFIED | — |
| `dumps` output of every non-heavy corpus board loads in `kicad-cli` 10.0.6. | S-0020 | KICAD-VERIFIED (10.0.x) | — |
| Layout written by KiCad 10: one TAB per depth, LF only, and the file ends with `)` and one LF. A list holding only atoms is on one line. Atoms before the first child list stay on the head line. Each child list starts a line one depth deeper. The `)` of a list with child lists stands alone at the list's depth. | S-0020, S-0024 | INFERRED | H-K-FMT-INDENT |
| An atom that follows a child list is printed on its own line, one depth deeper. | S-0020 | INFERRED | H-K-FMT-MIXED |
| Inside `pts`, the next `(xy …)` is appended after one space while the current line is shorter than 99 columns (TAB counted as one column); otherwise it starts a new line. | S-0024 | INFERRED | H-K-FMT-XYWRAP |
| KiCad 9 wraps long atom-only lists (32-layer `layers`, `members`) at about 88 columns. KiCad 10 no longer writes the 32-layer list. Fenolite does not implement this wrap. | S-0024 | INFERRED | H-K-FMT-ATOMWRAP |
| `kicad-cli pcb upgrade --force` re-saves a board in the current format; it exists only in the 10.0 CLI. Fenolite runs it only on files that parse. | S-0022, S-0020 | KICAD-VERIFIED (10.0.x) | H-K-FMT-RESAVE |
| `kicad-cli pcb export svg -l Edge.Cuts --mode-single -o <file>` exits 3 when the board does not load, and is used as the load check. `pcb drc --exit-code-violations` is not, because a minimal board already has an outline violation. | S-0020, S-0022 | KICAD-VERIFIED (10.0.x) | H-K-SEXPR-LEX-10 |

## Model in Fenolite

- `Atom(text, kind)` keeps the exact characters, including the quotes of a string. `kind` is
  `string`, `number` or `symbol`, decided only by the lexical form.
- `Node(head, children, offset, comments)` is immutable.
  - `offset` is the byte offset of `(` in the UTF-8 input and is not part of equality.
  - `comments` exist only on the root.
- `dumps(node)` writes the KiCad 10 layout. `dumps(node, style="compact")` writes one line, and is the
  encoding of opaque fragments.
- Equality (`tree_equal`) compares heads, atom texts and kinds, order and root comments. It is the
  RT0 criterion.
- Locators look like `/kicad_pcb/footprint[1]/pad[0]`. The index counts earlier siblings with the
  same head.
