## Context

- Fenolite has `core` and `model` (c0004) but no backend package yet. `fenolite.model.base` already defines the slot types `Modeled(field)` and `Opaque(fragment, min_version)` and the `ExtBag(min_version, payload)` extension bag. The design-model spec requires backends to re-emit opaque children verbatim at their original position.
- Every KiCad file kind this project will touch is an S-expression. Public documentation (S-0001, S-0021) states only the basics: parenthesised lists, lowercase tokens, double-quoted UTF-8 strings, no exponent in written numbers, millimetres. It does not document escapes, the pretty-printer, or what the reader rejects. Those were observed with `kicad-cli` 10.0.6 (S-0020) and on the public demo boards (S-0023, S-0024). The facts are summarised below. No KiCad source code was read for this change, and none may be read to implement it. Code is written from `docs/formats/kicad/sexpr.md` only.
- Corpus facts (S-0024, S-0025, S-0026):
  - At tag 10.0.6, only one of the 19 demo boards is in 10.0 format (`20260206`). Fifteen are 9.0 (`20241229`), and three are developer versions (8.99/9.99).
  - At tag 9.0.9.1, the boards are 9.0 format, except one that is 8.99. Most are byte-identical to their 10.0.6 counterparts; six differ or exist only at 9.0.9.1.
  - Several demo folders ship their own licence (Apache-2.0, CERN-OHL-S-2.0, CERN-OHL-P-2.0, CC-BY-SA-4.0). One folder carries CC-BY-NC-SA-4.0 with an exemption. The blanket statement (S-0023) says CC-BY-SA-4.0.
  - Two boards are 70–85 MB.
  - The third-party permissive boards (S-0027, S-0028) are KiCad 7 (`20221018`) or KiCad 5 (`20171130`) format.
- The ip-hygiene capability requires `backends/<x>/PROVENANCE.md` and one `LEGAL-ANNEX.md` row per ISO week of work under `backends/` or `docs/formats/`.
- Environment: KiCad 10.0.6 installed locally (macOS). The official Docker images (S-0029) are linux/amd64 only for 10.0.x, about 0.8 GB compressed, and run as uid 1000 by default. Running them in CI has not been tried yet. The environment hypotheses belong to c0007; this change only records the URL of the first green `kicad-10` run in `docs/formats/kicad/corpus.md`, for c0007 to cite.

## Goals / Non-Goals

**Goals:**
- A stdlib-only S-expression layer that reads every corpus file and writes it back with an identical tree (RT0). It keeps atom spelling, classifies atoms, and locates every error by file, byte offset and locator.
- A KiCad-10-style printer whose output `kicad-cli` 10.0 loads.
- A slots helper that typed readers (c0008, the board backend) use to keep unmodelled children and grandchildren in place.
- A reproducible public corpus and a CI job with the real oracle, so later changes can reach `KICAD-VERIFIED`.

**Non-Goals:**
- Typed file readers or writers, RT1/RT2, version detection and gating, the token inventory, and the `kicad-9` job (c0007/c0008 and later).
- The custom-rules (`.kicad_dru`) lexical dialect. A later change adds it as a parser option.
- Measuring byte identity with KiCad's printer, and a throughput benchmark. Both move to the typed board writer change (see Budget).
- Byte-identical 9.0-style output (long atom-list wrapping), streaming parse, and memory work for boards over 20 MB.
- CLI commands, `capabilities` entries, and `backends/base.py`/`registry.py`.

## Decisions

1. **Own lexer and parser, written from the format page.** A single compiled `re` master pattern (whitespace, `(`, `)`, quoted string, bare atom) drives an iterative stack parser. There is no recursion, and `MAX_DEPTH = 256` is enforced.
   - Rejected: `sexpdata` or similar packages. They add a runtime dependency, and they normalise spelling and numbers.
   - Rejected: copyleft libraries (licence policy).
   - Rejected: a character-by-character loop (too slow in pure Python).
   - Rejected: a recursive-descent parser (the Python recursion limit makes it fragile on adversarial input).

2. **Atoms keep their text exactly as written, and cannot be built invalid.** `Atom(text, kind)`: `text` includes the quotes for strings, and `kind ∈ {symbol, string, number}` is decided only by lexical form.
   - A number fully matches `-?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?`. Anything else unquoted is a symbol. This includes `+0.8`, `0x10`, hex layer masks, `${VAR}/x.pretty`, `1.6mm` and `#PWR`.
   - `Atom.__post_init__` re-lexes `text`. It raises `ValueError` when `text` is not exactly one lexical atom (empty, whitespace, `(`, `)`, a raw CR or LF, a bad quoted string) or when `kind` differs from the lexical classification. `Atom.symbol(name)` therefore raises for a name that would read as a number or a string. The parser builds atoms through an internal unchecked constructor, because the lexer has already classified them.
   - Decoding happens on demand (`Atom.value`, `Atom.to_nm()`).
   - The reason is that RT0 must survive the spelling differences 9.0 and 10.0 actually write (`12.000000` vs `12`, S-0020) and the unquoted atoms of pre-6 files (S-0021), and that `parse(dumps(t))` must be tree-equal to `t` for every tree a caller can build.
   - Rejected: storing decoded values, which loses spelling and breaks RT0.

3. **Head is any atom; children are `Node | Atom`; offsets are bytes.** Board layer tables use numeric heads (`(0 "F.Cu" signal)`). `Node(head: Atom, children: tuple[Node | Atom, ...], offset: int | None, comments: tuple[str, ...])`.
   - Nodes are frozen, and `offset` is excluded from comparison.
   - `offset` (and `FormatError.offset`) is always the byte offset in the UTF-8 encoding, for `parse`, `parse_bytes` and `load` alike. This matches `fenolite.core.errors.FormatError` ("byte offset") and the c0008 readers. For `str` input the parser counts bytes with an ASCII fast path.
   - `comments` is meaningful only on the root. Each entry is one line whose first non-blank character is `#`, without its line ending. `dumps` raises `ValueError` for a nested node with comments.
   - `()` and a list whose first element is a list are rejected. KiCad never writes either; whether KiCad loads them is recorded, not mirrored (Decision 4).
   - Rejected: `head: str` (loses the numeric/string kind); mutable nodes (the model is immutable everywhere); character offsets (they contradict the existing `FormatError` contract).

4. **Rejections: a mirrored set and a Fenolite-only set.**
   - Mirrored rejections, observed as `kicad-cli` 10.0.6 load failures (S-0020, exit 3): empty or unbalanced input, a byte-order mark before `(`, a raw LF inside a quoted string, an atom glued after a closing quote (`"a"b`).
   - Fenolite-only rejections, not mirrored: content after the root list (KiCad observed to ignore it), `()`, a list starting with a list, a raw CR inside a quoted string, an unterminated string at end of input, nesting deeper than `MAX_DEPTH`, and invalid UTF-8. They exist because silently dropping or guessing bytes contradicts lossless round-trip. KiCad's outcome on each is observed once and recorded (`H-K-SEXPR-STRICT`), without any claim that KiCad agrees.
   - Number spellings are not lexical: `+0.8`, `0x10` and `1.6mm` parse as symbols; KiCad refuses them where a number is required (S-0020). That is a semantic oracle case (`H-K-SEXPR-NUM-READ`), not a lexical one.
   - Inside quotes the parser accepts any character except CR, LF and an unescaped `"`, so a raw VT written back by KiCad is accepted.
   - `#` comment lines before the root are accepted and preserved in `Node.comments` (KiCad skips them, S-0020). A `#` elsewhere is an ordinary atom character. An atom that starts unquoted and contains `"` is kept whole.
   - Every fixture records two expected outcomes, one per tool (Decision 12).
   - Rejected: mirroring KiCad's "ignore trailing content".

5. **String escapes (S-0020, observed 10.0.6).**
   - Decoding handles `\"`, `\\`, `\n`, `\r`, `\t`, `\v`, octal `\ooo` (1–3 digits), and hex `\xHH`. Any other backslash sequence stays literal.
   - `Atom.string(value)` escapes `"`, `\`, LF and CR as `\"`, `\\`, `\n` and `\r`, as KiCad writes them. It keeps TAB and every non-control character raw. It writes every other C0 control character, VT included, as a 3-digit octal escape, and raises `ValueError` for NUL. KiCad writes VT back raw; Fenolite escapes it so that written files carry no raw control byte other than TAB. The encoder never emits a raw newline: KiCad rejects one in a string, and its `pcb upgrade` crashes on one.
   - The decode table and the encoder output are both checked against KiCad (`H-K-SEXPR-ESCAPES`).

6. **Numbers in integer nanometres, no floats.**
   - `Atom.to_nm(*, exact=True)` parses the decimal-millimetre spelling with integer arithmetic. Exponents are accepted because KiCad reads them. A value that is not a whole number of nm raises `ValueError` when `exact`; otherwise it is rounded half-even (`core.units.round_half_even_div`).
   - `Atom.from_nm(nm)` writes what 10.0 writes: at most 6 decimals, no exponent, no trailing zeros or dot, and `-0` → `0`.
   - `Atom.integer(n)` and `Atom.to_int()` handle counts and versions.
   - Angles and other units are left to the typed readers.
   - Rejected: `float`, because the model forbids floats and they lose exactness.

7. **Two printers and a fragment codec.**
   - `dumps(node)` (style `"kicad"`) follows the 10.0 layout observed on 10.0.6 writes and on the 9.0 corpus (S-0020, S-0024):
     - one TAB per depth, LF only, and the file ends with `)\n`
     - root comments first, one per line
     - atoms that come before the first child list stay on the head line
     - a list with only atoms is one line
     - each child list goes on its own line one depth deeper, and the closing `)` sits alone at the parent's depth
     - an atom that follows a child list goes on its own line (`H-K-FMT-MIXED`)
     - `xy` children of `pts` are packed by one rule: the next `(xy …)` is appended after one space if and only if the current line is shorter than 99 columns, counting a TAB as one column (`H-K-FMT-XYWRAP`)
   - `dumps(node, style="compact")` writes one line, with single spaces and no newline. It omits root comments. It is used for opaque fragments and diagnostics.
   - `dumps(atom)` returns `atom.text` in both styles. `parse_fragment(text, *, file="")` reads exactly one list or exactly one atom, with optional surrounding whitespace and no comments, and returns a `Node` or an `Atom`. Together they are the codec of opaque fragments, which may be bare atoms (`locked`, `hide`).
   - Correctness is gated by RT0 and by "kicad-cli loads". Byte identity with KiCad is not measured in this change (Budget).
   - Rejected: reproducing the original whitespace (a trivia-preserving tree). It costs twice the memory, and typed writers will print new content anyway.

8. **Equality and diagnostics.**
   - `tree_equal(a, b)` compares heads, atom text and kind, child order and root comments. It ignores offsets and whitespace. This is RT0.
   - `first_difference(a, b)` returns the locator of the first mismatch.
   - Locators have the form `/kicad_pcb/footprint[12]/pad[0]`. The index counts siblings with the same head, starting at 0. `walk(node)` yields `(locator, node)`, and `FormatError.locator` uses the same form.

9. **Slots.**
   - `split(node, fields, *, positional=(), min_version=None)` maps each child to a slot:
     - a child list whose head is in `fields` → `Modeled(fields[head])`, once per occurrence
     - the i-th atom before the first child list, for i < `len(positional)` → `Modeled(positional[i])`
     - everything else, atoms included → `Opaque(dumps(child, style="compact"), v)`
   - `min_version` is a decimal version string, a callable `(child) -> str | None` called once per opaque child, or `None`. The callable lets c0008 pass c0007's per-token `min_version(kind, path)` (an `int`, converted with `str`) and fall back to the file version. Versions are compared as integers everywhere.
   - `SlotSource` has two methods: `items(field)` and `fields()`, the fields that currently have items.
   - `rebuild(head, slots, source, *, canonical=())` walks the slots in order:
     - The k-th `Modeled(f)` emits `source.items(f)[k]` if it exists and nothing if the item was deleted.
     - Extra items of `f` follow its last occurrence.
     - Every field in `source.fields()` must have a slot or be listed in `canonical`; otherwise `ValueError` names it. A field with items but no slot is inserted after the last present field that precedes it in `canonical`. If none precedes it, it goes after the positional atoms.
     - `Opaque` fragments are decoded with `parse_fragment` (`opaque_child`) and emitted in place.
   - Rejected: emitting all items of a field at its first occurrence, because it reorders children interleaved with opaque ones and breaks RT1.
   - Rejected: storing `Node` objects in the model, because `model` must not import `backends` (package-layering).

10. **Slots persist in the `kicad` extension bag, per relative locator; the model is unchanged.**
    - One entity may need several slot lists: its own node, and modelled sub-lists that are not entities (`effects` of a text, `stroke` of a graphic, `tenting` of a via). Each list is keyed by its locator relative to the entity node: `.` for the node itself, otherwise the locator form without the leading root (`effects[0]`, `effects[0]/font[0]`).
    - Pair keys are `slot:<rel>:modeled`, `slot:<rel>:opaque` and `slot:<rel>:opaque@<min_version>`. They are parsed by splitting off the last `:`, so a locator may itself contain `:`.
    - `to_ext(slots, base=None) -> ExtBag` takes one slot list (meaning `{".": slots}`) or a mapping from relative locator to slot list. It keeps the foreign pairs of `base` first, in their order, and the slot pairs of `base` for locators absent from the mapping. It then writes one group per locator, `.` first and the rest in lexicographic order. `ExtBag.min_version` becomes the maximum of `base.min_version` and every opaque minimum version in the bag, ignoring `None`.
    - `from_ext(bag, at=".")` returns the slot list of one locator; `from_ext_all(bag)` returns all of them as a dict. The one-list form keeps c0008's `from_ext(fp.ext["kicad"])` valid.
    - No dataclass changes, so there is no schema regeneration. The drift test proves this.
    - Rejected: a new `slots` field on `Entity`. It would be a model change and would break the schema v0 for a backend concern.
    - Rejected: making a whole sub-list opaque whenever it has an unknown grandchild (the sub-list is no longer modelled) or dropping the grandchild (lossy).

11. **Corpus.**
    - Manifest rows cover every `.kicad_pcb` under `demos/` at tags 10.0.6 and 9.0.9.1 (a file identical at both tags is listed once, with the other tag in `notes`). The only exclusion is the board whose folder licence has a non-commercial clause. The 9.0.9.1 rows stay here because c0007 relies on c0006 for the 9.0 demo boards.
    - One schematic, one symbol library, one footprint, one footprint-library table and one worksheet come from 10.0.6.
    - Three Apache-2.0 third-party boards (`20221018` ×2, `20171130`) are included.
    - Naming rule, decided here: vendor, product and project names appear only inside URLs, in `docs/evidence/sources.md` and in the manifest `url` field. Manifest ids use a closed pattern, `kicad-demo-<tag>-<kind>-NN` or `third-party-<kind>-NN` (tag with dots as dashes, kind in `pcb|sch|sym|mod|fplib|wks`). `notes`, `docs/formats/kicad/corpus.md`, test output and commit messages describe rows without names.
    - Origin: every row carries exactly one `origin:kicad-demos` or `origin:third-party` value in `uses`. No manifest key is added.
    - Licence reading:
      - `license` is the blanket `CC-BY-SA-4.0` for demos, `Apache-2.0` for third-party rows.
      - A folder licence, where one exists, goes into `license_variant`.
      - All rows are `embeddable = false`.
    - `uses` labels:
      - `rt0` on every row
      - `oracle` on boards
      - `heavy` on files over 20 MB, which are excluded from the PR job and from local corpus tests unless `FENOLITE_HEAVY=1`
    - A 10.0-format board set needs derived copies: the oracle tests copy a fetched board into `tmp_path` and run `kicad-cli pcb upgrade --force` there. Nothing derived is written to the repository or the corpus cache, and a residue check detects committed copies by shared identifiers.
    - `tools/corpus_fetch.py` gains `--uses TAG` / `--exclude-uses TAG` and URL-unquotes cached file names.
    - `tests/_corpus.py` exposes `CorpusItem(id, path, license, uses, origin, heavy)`. With `corpus` in `FENOLITE_REQUIRE`, a missing non-heavy `rt0` item fails the run, and a `CORPUS-VERIFIED` label is only reported when items from two origins passed.

12. **Oracle tests: cheapest load command, recorded expectations per tool.**
    - `pcb export svg -l Edge.Cuts --mode-single -o <file>` exits 3 on a load failure, and the SVG must exist. `pcb drc --exit-code-violations` is not usable because a minimal board already raises an outline violation (S-0020, S-0022).
    - Fixtures under `tests/data/kicad/sexpr/` are listed in `tests/data/kicad/sexpr/EXPECT.toml` with `file`, `class` (`mirror`, `unmirrored` or `semantic`), `expect_parse` (`accept` or the rule name in the message), `expect_kicad_10` (exit code) and an optional `expect_kicad_9`, plus the hypothesis id. Each `unmirrored` or `semantic` fixture is the minimal board with one construct inserted.
    - The test asserts that each tool's observed outcome equals its recorded expectation. Only the `mirror` class additionally requires "parser rejects ⇔ KiCad exits 3", and a unit test checks that on the table without KiCad. A fixture with no expectation for the running major is skipped with a message.
    - `pcb upgrade --force` exists only in the 10.0 CLI (S-0022) and is used only on files known to parse, since it crashes on a raw newline in a string.
    - The re-save check compares `parse(upgrade(orig))` and `parse(upgrade(dumps(parse(orig))))` with `tree_equal` after masking the values of `uuid` and `tstamp` atoms, because KiCad gives fresh identifiers to items of old boards that have none. It first upgrades the original twice; a board whose two masked upgrades differ is listed as non-deterministic and excluded, and the list is recorded under `H-K-FMT-RESAVE`.
    - Every run happens in `tmp_path`, because KiCad writes a `.kicad_prl` next to the board.

13. **CI job `kicad-10`.** Job-level `container: kicad/kicad:10.0.6@sha256:<index digest>` with `options: --user 0`, and these steps in this order:
    1. `actions/checkout@v4`
    2. `astral-sh/setup-uv`
    3. `kicad-cli version`
    4. `uv sync --locked --extra dev`
    5. `actions/cache` of `~/.cache/fenolite/corpus`, keyed on `hashFiles('tests/corpus/manifest.toml')`
    6. `uv run python tools/corpus_fetch.py --uses rt0 --exclude-uses heavy`
    7. `uv run pytest tests/kicad tests/corpus -q` with `FENOLITE_REQUIRE=kicad,corpus`

    Required-resource mode turns the `needs_kicad`/`needs_corpus` skips into failures, so a broken image cannot pass silently. `tests/unit/test_ci_workflow.py` checks this order and these values textually, because the dev extra has no YAML parser.
    - Rejected: a `docker run` wrapper per `kicad-cli` call. It needs host↔container path mapping and pays a container start per call.
    - Rejected: distribution packages of KiCad. They are not the official image and their versions drift.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/__init__.py` | package marker, docstring only |
| `src/fenolite/backends/kicad/__init__.py` | re-exports `Atom`, `AtomKind`, `Node`, `parse`, `parse_bytes`, `parse_fragment`, `load`, `dumps`, `tree_equal`, `first_difference`, `walk` |
| `src/fenolite/backends/kicad/PROVENANCE.md` | provenance table with the five columns `fact-or-area \| public source \| licence of source \| date \| how used` |
| `src/fenolite/backends/kicad/sexpr.py` | `class AtomKind(StrEnum): SYMBOL, STRING, NUMBER`; `@dataclass(frozen=True, slots=True) class Atom(text: str, kind: AtomKind)` validated in `__post_init__`, with `value: str` (property), `to_nm(*, exact: bool = True) -> int`, `to_int() -> int`, classmethods `symbol(name: str)`, `string(value: str)`, `from_nm(nm: int)`, `integer(n: int)`; `@dataclass(frozen=True, slots=True) class Node(head: Atom, children: tuple[Node \| Atom, ...] = (), offset: int \| None = None, comments: tuple[str, ...] = ())` with `name: str`, `atoms() -> tuple[Atom, ...]`, `nodes(name: str \| None = None) -> tuple[Node, ...]`, `find(name: str) -> Node \| None`, `with_children(children) -> Node`; `MAX_DEPTH: int = 256`; `parse(text: str, *, file: str = "") -> Node`; `parse_bytes(data: bytes, *, file: str = "") -> Node`; `parse_fragment(text: str, *, file: str = "") -> Node \| Atom`; `load(path: str \| os.PathLike[str]) -> Node`; `dumps(x: Node \| Atom, *, style: Literal["kicad", "compact"] = "kicad") -> str`; `tree_equal(a: Node, b: Node) -> bool`; `first_difference(a: Node, b: Node) -> str \| None`; `walk(node: Node) -> Iterator[tuple[str, Node]]` |
| `src/fenolite/backends/kicad/slots.py` | `class SlotSource(Protocol)`: `items(self, field: str) -> Sequence[Node \| Atom]`, `fields(self) -> Iterable[str]`; `MinVersion = str \| Callable[[Node \| Atom], str \| None] \| None`; `split(node: Node, fields: Mapping[str, str], *, positional: Sequence[str] = (), min_version: MinVersion = None) -> tuple[Slot, ...]`; `rebuild(head: Atom, slots: Sequence[Slot], source: SlotSource, *, canonical: Sequence[str] = ()) -> Node`; `opaque_child(slot: Opaque) -> Node \| Atom`; `to_ext(slots: Sequence[Slot] \| Mapping[str, Sequence[Slot]], base: ExtBag \| None = None) -> ExtBag`; `from_ext(bag: ExtBag, at: str = ".") -> tuple[Slot, ...]`; `from_ext_all(bag: ExtBag) -> dict[str, tuple[Slot, ...]]`; `SLOT_PREFIX = "slot:"` |
| `tests/unit/backends/kicad/test_sexpr_*.py`, `test_slots*.py` | unit and property tests |
| `tests/unit/test_format_facts.py` | fact-table check of `docs/formats/kicad/*.md` |
| `tests/strategies.py` | adds `sexpr_trees()` (comments on the root only), `kicad_strings()` |
| `tests/_corpus.py` | `CorpusItem(id, path, license, uses, origin, heavy)`, `corpus_items(use: str, *, heavy: bool = False) -> list[CorpusItem]` |
| `tests/corpus/test_rt0.py` | RT0, independent token-stream check, number census, slot identity |
| `tests/kicad/test_sexpr_oracle.py`, `tests/kicad/test_rt0_oracle.py` | `needs_kicad` tests (fixture outcomes, escapes, encoder, re-dump loads, re-save, number census of upgraded copies) |
| `tests/conftest.py` | `FENOLITE_REQUIRE` required-resource mode; `pytest_plugins = ["pytester"]` |
| `tests/data/kicad/sexpr/**` | authored CC0 fixtures and `EXPECT.toml`, declared in `tests/data/MANIFEST.toml` |
| `tests/residue/test_derived_corpus.py` | detector for committed copies of corpus boards |
| `tools/corpus_fetch.py` | `--uses`, `--exclude-uses`; unquoted file names |
| `tests/corpus/manifest.toml` | rows of Decision 11 |
| `.github/workflows/ci.yml` | job `kicad-10` |
| `docs/formats/kicad/sexpr.md`, `docs/formats/kicad/corpus.md` | fact table `\| fact \| source \| label \| hypothesis \|`; corpus description and first green `kicad-10` run |
| `docs/evidence/sources.md`, `docs/hypotheses.md`, `LEGAL-ANNEX.md`, `CHANGELOG.md` | rows and results |

Layering: `backends.kicad` imports only `fenolite.core` (errors, units) and `fenolite.model.base`. That is within the allowed edges, and no layering change is needed.

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0020 | https://www.kicad.org/download/ (kicad-cli 10.0.6 run as an oracle) | GPL-3.0-or-later tool, run as subprocess, nothing copied | observed reader rejections, escapes, number spelling, printer layout, exit codes |
| S-0021 | https://dev-docs.kicad.org/en/file-formats/sexpr-pcb/index.html | not stated on the page (to verify) | pre-6 files quote strings only when needed; third-party generator names |
| S-0022 | https://docs.kicad.org/10.0/en/cli/cli.html | to verify on the page | `pcb export svg`, `pcb upgrade`, `--exit-code-violations` |
| S-0023 | https://gitlab.com/kicad/code/kicad/-/raw/10.0.6/LICENSE.README | licence notice | demos are CC-BY-SA-4.0 |
| S-0024 | https://gitlab.com/api/v4/projects/kicad%2Fcode%2Fkicad/repository/tree?path=demos&ref=10.0.6&recursive=true (also `ref=9.0.9.1`); `HEAD` https://gitlab.com/api/v4/projects/kicad%2Fcode%2Fkicad/repository/files/<path>?ref=<tag> | API metadata | tree API: demo file lists; files API `HEAD` (`X-Gitlab-Size`, `X-Gitlab-Content-Sha256`): sizes and SHA-256 |
| S-0025 | https://gitlab.com/kicad/code/kicad/-/tree/10.0.6/demos (per-folder licence files) | per folder | licence variants of demo folders |
| S-0026 | https://gitlab.com/api/v4/projects/kicad%2Fcode%2Fkicad/repository/tags | API metadata | tag → commit (10.0.6 `caf7377e9cb6`, 9.0.9.1 `70b072d9f77f`) |
| S-0027 | third-party Apache-2.0 board repository (URL in `docs/evidence/sources.md` only) | Apache-2.0 (hardware) | third-party board row |
| S-0028 | two third-party Apache-2.0 board repositories (URLs in `docs/evidence/sources.md` only) | Apache-2.0 | third-party board rows |
| S-0029 | https://hub.docker.com/r/kicad/kicad | image GPL-3.0-or-later (OCI label) | tags, architecture, digests, default user |

## Hypotheses registered by this change

| id | statement | test that settles it | criterion |
|---|---|---|---|
| H-K-SEXPR-LEX-10 | `kicad-cli` 10.0.6 exits 3 on the `mirror` reject fixtures (empty, unbalanced, BOM, raw LF in a string, glued atom) and loads the `mirror` accept fixtures (CRLF, `#` line before the root, numeric heads, bare symbols, `"` inside an unquoted atom) | `tests/kicad/test_sexpr_oracle.py::test_fixture_outcomes` in `kicad-10` | every `mirror` fixture's exit equals `expect_kicad_10` |
| H-K-SEXPR-LEX-9 | the same on `kicad-cli` 9.0.9 | the same test in the `kicad-9` job (c0007) | every `mirror` fixture's exit equals `expect_kicad_9` |
| H-K-SEXPR-STRICT | KiCad 10.0.6's outcome on each Fenolite-only rejection (Decision 4) is known and stable | `test_fixture_outcomes`, class `unmirrored` | each outcome is recorded in `EXPECT.toml` and reproduced; no agreement is claimed |
| H-K-SEXPR-ESCAPES | The decode table of Decision 5 (octal 1–3 digits, hex 2 digits, unknown escapes literal) matches KiCad 10.0.6, and KiCad decodes what `Atom.string` writes | `test_sexpr_oracle.py::test_escapes_after_upgrade`, `::test_encoder_after_upgrade` | decoded values of the escape fixture and of the encoder board equal the values in KiCad's re-saved file |
| H-K-SEXPR-NUM-READ | `kicad-cli` 10.0.6 loads exponent, leading-dot, trailing-dot, `-0` and over-precise numbers where a number is required, and exits 3 on `+0.8`, `+.8`, `0x10` and `1.6mm` there | `test_fixture_outcomes`, class `semantic` | every `semantic` fixture's exit equals `expect_kicad_10` |
| H-K-SEXPR-NUM-WRITE | Files written by `kicad-cli` 10.0.6 contain no exponent and no number with more than 6 decimals | `tests/kicad/test_rt0_oracle.py::test_number_census_upgraded` (census of `pcb upgrade --force` copies made at test time) | 0 and 0 |
| H-K-SEXPR-NUM-CORPUS | No number atom in the corpus has an exponent or more than 6 decimals | `tests/corpus/test_rt0.py::test_number_census` | 0 and 0 in both origins; otherwise counts are recorded per origin and format version |
| H-K-FMT-INDENT | KiCad 10 layout = Decision 7 (TAB indent, atom-only lists on one line, head atoms on the head line, `)` alone) | byte-identity measurement over upgraded boards (typed board writer change) | 100 % byte-identical, or each differing line class recorded |
| H-K-FMT-XYWRAP | KiCad appends the next `xy` iff the current line is shorter than 99 columns (TAB = 1) | same measurement | no differing line inside `pts` |
| H-K-FMT-ATOMWRAP | Long atom-only lists wrap at about 88 columns (seen in 9.0 writes); unknown for 10.0 | same measurement, 9.0 files | differences counted; the rule is implemented only if 10.0 wraps |
| H-K-FMT-MIXED | An atom following a child list is printed on its own line | same measurement | 0 differing lines of that class |
| H-K-FMT-RESAVE | `pcb upgrade --force` of an original board and of its re-dump yield equal trees once `uuid`/`tstamp` values are masked | `test_rt0_oracle.py::test_resave_equal` | equal for every non-heavy `oracle` board that loads and upgrades deterministically; non-deterministic boards listed |

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Parse of well-formed files, including legacy unquoted atoms and numeric heads | CORPUS-VERIFIED | RT0 over KiCad demos + third-party boards (two origins), `tests/corpus/test_rt0.py` |
| Mirrored lexical rejections and acceptances match KiCad | KICAD-VERIFIED (10.0.6, `H-K-SEXPR-LEX-10`); INFERRED for 9.0 (`H-K-SEXPR-LEX-9`) | `test_fixture_outcomes` in `kicad-10` |
| Fenolite-only rejections | mechanical (unit tests); KiCad's outcome recorded under `H-K-SEXPR-STRICT` | `test_sexpr_parse.py`, `test_fixture_outcomes` |
| String escape decoding and `Atom.string` encoding | KICAD-VERIFIED (10.0.6); INFERRED for 9.0 (the 9.0 CLI has no re-save command) | `test_escapes_after_upgrade`, `test_encoder_after_upgrade` |
| KiCad's reading of number spellings | KICAD-VERIFIED (10.0.6, `H-K-SEXPR-NUM-READ`) | `test_fixture_outcomes` |
| KiCad 10 writes ≤ 6 decimals, no exponent (basis of `from_nm`) | KICAD-VERIFIED (10.0.6, `H-K-SEXPR-NUM-WRITE`) | `test_number_census_upgraded` |
| Corpus numbers fit exact nm (`to_nm(exact=True)`) | CORPUS-VERIFIED if `H-K-SEXPR-NUM-CORPUS` holds in both origins, else INFERRED with counts; conversion itself mechanical | `test_number_census`, unit tests |
| `dumps` output loads in `kicad-cli` | KICAD-VERIFIED (10.0.6) | `test_rt0_oracle.py::test_redump_loads` |
| Re-save equivalence | KICAD-VERIFIED if `H-K-FMT-RESAVE` holds, otherwise INFERRED with the differences recorded | `test_resave_equal` |
| Byte identity with KiCad's printer | INFERRED (`H-K-FMT-INDENT`, `-XYWRAP`, `-ATOMWRAP`, `-MIXED`), not measured here | deferred |
| Slot split/rebuild identity | CORPUS-VERIFIED (identity rebuild of every node of the non-heavy corpus) + mechanical tests | `test_rt0.py::test_slot_identity`, `tests/unit/backends/kicad/test_slots.py` |
| Slot persistence in `ExtBag` | mechanical (UNVERIFIED as a format claim; no format involved) | `test_slots_ext.py` |

## Budget

The plan gave this change about half a week. Review showed that the scope does not fit, so the budget is re-estimated at about one week, and two items move out now instead of "if needed".

| work | days |
|---|---|
| sources, hypotheses, provenance, `sexpr.md` with fact test | 0.5 |
| atoms, scanner, parser, rejections, fragment codec | 1.25 |
| printers, equality, locators, properties, fixtures | 0.75 |
| slots and extension bag | 0.5 |
| fetch options, manifest rows, `corpus.md`, RT0 and residue tests | 1.0 |
| oracle tests | 0.5 |
| required-resource mode and `kicad-10` job | 0.5 |
| closing | 0.25 |
| **total** | **5.25** |

Moved out: the byte-identity measurement (`test_byte_identity_kicad10`, `docs/evidence/kicad-fmt-identity.md`) and the 5 MB throughput benchmark go to the typed board writer change, which prints new content and needs both. The `H-K-FMT-*` rows stay registered as `INFERRED`.

## Risks / Trade-offs

- [Pure-Python parse of multi-megabyte boards is slow or memory-hungry] → one regex scanner, interned symbol heads, `slots=True` dataclasses, no validation on parser-built atoms. Files over 20 MB are tagged `heavy` and run only with `FENOLITE_HEAVY=1`. Slot identity costs about depth × file size, which is acceptable below 20 MB. Streaming is a non-goal.
- [The Docker image does not run in GitHub's job container (uid, HOME, Node for actions)] → the first job run shows it. The fallback is the `docker run` wrapper of Decision 13, whose alternatives were rejected only for cost.
- [Corpus URLs move or tags are re-pointed] → rows pin tag and SHA-256, and the commit goes in `notes`. The fetch fails loudly on a hash mismatch.
- [Fenolite-only rejections refuse a file KiCad opens] → the message names the byte offset and the rule. No such file is in the corpus. KiCad's outcome is recorded under `H-K-SEXPR-STRICT`.
- [A printer rule is wrong for some construct] → correctness is gated by "kicad-cli loads" and by RT0, never by byte identity.
- [KiCad assigns random identifiers to old boards on load, so re-save comparison is noisy] → `uuid`/`tstamp` values are masked and a double upgrade of the original detects remaining non-determinism.
- [The budget still overruns] → the `unmirrored` fixtures beyond trailing content and invalid UTF-8 are dropped first, then the 9.0.9.1-only rows. Parser, slots, RT0 and the `kicad-10` job are not optional.
- [Local Python cannot verify HTTPS certificates on some macOS installs] → documented in `docs/formats/kicad/corpus.md`. CI on Ubuntu is unaffected.

## Migration Plan

- Additive. No persisted data, model field or schema changes. If needed, rollback removes the `backends/` package and the `kicad-10` job.

## Open Questions

- The 10.0.6 demo set contains only one 10.0-format board. Upgraded copies made in `tmp_path` serve as the 10.0 measurement set until permissively licensed 10.0 boards are found. The default is yes.
- Making `kicad-10` a required status check is a repository setting outside this spec. The maintainer decides after the first green runs.
