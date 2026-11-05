# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The files of Part F of the maintainer's check (``docs/evidence/altium-draftsman.md``, "Part F:
Draftsman documents"; change c0172).

``part_f0(folder)`` writes round F0 (task 1.3; ``H-A-DWF-CONTAINER``, ``H-A-DWF-FIELD``) into ``folder``:

- ``blink_routed/``: the Altium project that ``fenolite build examples/blink_routed/design.py --target
  altium`` writes with a fixed seed and timestamp, without the build's ``.fenolite`` cache;
- ``README.md``: the steps F0.1 to F0.14 in Brazilian Portuguese, the maintainer's language (the same steps
  in English are round F0 of the evidence page);
- ``SHA256SUMS``: the SHA-256 of every other file.

With ``FENOLITE_ALTIUM_PART_F0=<folder outside the repository>`` the kit is written there:
``FENOLITE_ALTIUM_PART_F0=~/fenolite-altium-checks/session-6/F0-draftsman uv run pytest
tests/unit/backends/altium/test_part_f.py -k f0_kit``. Without it the kit is written under the test's own
folder. No file that Altium wrote is in the repository.
"""

from __future__ import annotations

import hashlib
import io
import json
import ntpath
import os
import posixpath
import re
import shutil
from pathlib import Path, PurePath, PureWindowsPath

import pytest

import fenolite.cli.main as cli_main
from fenolite.backends.altium import draftsman
from fenolite.backends.altium.read.draftsman import INSTANCE, NAMESPACE, decode, read_draftsman
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.cli.altium_observations import checked_files
from fenolite.exports.drawing_tables import drill_rows, stackup_block
from fenolite.model.canonical import load_dir
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[4]
HANDOVER_F0 = os.environ.get("FENOLITE_ALTIUM_PART_F0")
SCRIPT = ROOT / "examples" / "blink_routed" / "design.py"
PROJECT = "blink_routed"
FLAGS = ("--seed", "1", "--timestamp", "2026-10-16T00:00:00Z")
STEPS = 14

F0_README = """\
# Fenolite – kit F0: documentos Draftsman (observação)

Mudança c0172 do Fenolite. Nada aqui é verificado ainda: os arquivos que você salvar mostram ao Fenolite
como o Altium Designer 26.5 grava um documento Draftsman (`.PCBDwf`). Nenhum arquivo salvo pelo Altium
entra no repositório; só contagens e nomes de elementos.

## O que tem nesta pasta

- `blink_routed/`: projeto Altium gerado pelo Fenolite (`examples/blink_routed/design.py`): placa de
  50 × 30 mm, duas camadas, `U1` e `R1` em cima, `D1` embaixo, quatro trilhas, vias e um output job.
- `SHA256SUMS`: o SHA-256 de cada arquivo, como gerado.

## Antes de começar

- Trabalhe numa cópia desta pasta.
- Todo documento novo: **File » New » Draftsman Document**, template `[Default]`, projeto
  `blink_routed.PrjPcb`, documento fonte `blink_routed.PcbDoc`.
- Salve cada arquivo com **File » Save As** dentro de `blink_routed/`, com o nome indicado.
- Faça o F0.12 por último: ele move uma peça na placa.
- Em cada passo anote `como esperado` ou a mensagem que o Altium mostrou.

## Passos

1. **F0.1** Abra `blink_routed/blink_routed.PrjPcb`. Crie um documento novo e não coloque nada. Salve como
   `F0-01.PCBDwf`. Esperado: uma folha A4 vazia, salva sem mensagem.
2. **F0.2** Feche `F0-01.PCBDwf`, abra de novo e salve sem mudar nada como `F0-02.PCBDwf`. Esperado: salvo
   sem mensagem.
3. **F0.3** Abra `F0-01.PCBDwf`, coloque um Text (**Place » Text**) com `FENOLITE-1` em qualquer lugar da
   folha. Salve como `F0-03.PCBDwf`. Esperado: o texto aparece na folha.
4. **F0.4** Abra `F0-03.PCBDwf`, troque o texto por `FENOLITE-22`. Salve como `F0-04.PCBDwf`. Esperado: o
   texto novo aparece.
5. **F0.5** Abra `F0-01.PCBDwf`, coloque uma **Board Assembly View** com View Side Top. Salve como
   `F0-05.PCBDwf`. Esperado: a vista mostra o contorno, `U1` e `R1`.
6. **F0.6** Abra `F0-05.PCBDwf`, coloque uma segunda Board Assembly View com View Side Bottom. Salve como
   `F0-06.PCBDwf`. Esperado: a segunda vista mostra `D1`, visto por baixo.
7. **F0.7** Abra `F0-01.PCBDwf`, coloque uma **Drill Drawing View** (par de camadas Top – Bottom) e uma
   **Drill Table**. Salve como `F0-07.PCBDwf`. Esperado: a vista mostra os furos com símbolos e a tabela
   lista os diâmetros.
8. **F0.8** Abra `F0-01.PCBDwf`, coloque uma **Layer Stack Legend**. Salve como `F0-08.PCBDwf`. Esperado:
   a legenda mostra as camadas da placa, duas de cobre.
9. **F0.9** Abra `F0-05.PCBDwf`, coloque uma tabela **Bill of Materials**. Salve como `F0-09.PCBDwf`.
   Esperado: a tabela lista `D1`, `R1` e `U1`.
10. **F0.10** Abra `F0-07.PCBDwf`, coloque uma **Note** com duas entradas, `FENOLITE NOTE ONE` e
    `FENOLITE NOTE TWO`, e uma **Linear Dimension** entre a borda esquerda e a direita do contorno na
    vista de furação. Salve como `F0-10.PCBDwf`. Esperado: a nota numerada 1 e 2 e a cota com a largura
    da placa, 50 mm (1968,5 mil).
11. **F0.11** Abra `F0-01.PCBDwf`, acrescente uma segunda folha. Salve como `F0-11.PCBDwf`. Esperado: duas
    folhas vazias.
12. **F0.12** (por último) Abra `blink_routed.PcbDoc`, mova `R1` 5 mm para a direita e salve o PCB. Abra
    `F0-05.PCBDwf` e rode **Tools » Import Changes From blink_routed.PcbDoc**. Salve como `F0-12.PCBDwf`.
    Esperado: a vista mostra `R1` no lugar novo.
13. **F0.13** Abra `F0-10.PCBDwf` e salve com **File » Save As**, tipo template de documento Draftsman,
    como `F0-13.DwfDot`. Esperado: salvo sem mensagem.
14. **F0.14** Abra `F0-10.PCBDwf`, **File » Export to PDF** (um arquivo, todas as folhas) como
    `F0-14.pdf`. Esperado: um PDF de uma página com as vistas, a tabela, a nota e a cota.

## O que mandar de volta

1. A pasta inteira, compactada, com os arquivos que o Altium salvou e o projeto como o Altium deixou.
2. A versão do Altium Designer (**Help » About**, no formato `AD 26.5`) e a data.
3. Um resultado por passo: `como esperado` ou a mensagem que apareceu.

O Fenolite só lê os arquivos depois de rodar a verificação de caminhos do `fenolite kit verify` na pasta.
"""
"""The kit's ``README.md``: the steps of round F0 of ``docs/evidence/altium-draftsman.md`` in Brazilian
Portuguese."""


def build_project(
    out: Path, monkeypatch: pytest.MonkeyPatch, *, script: Path = SCRIPT, flags: tuple[str, ...] = ()
) -> dict[str, bytes]:
    """Build the routed blink for Altium through the command line; the files without the build's cache."""
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(out.parent / "kicad-config"))
    monkeypatch.setattr("sys.stdout", io.StringIO())
    monkeypatch.setattr("sys.stderr", io.StringIO())
    argv = [
        "build",
        str(script),
        "--out",
        str(out),
        "--target",
        "altium",
        "--confirm",
        "--json",
        *FLAGS,
        *flags,
    ]
    assert cli_main.main(argv) == 0
    return {
        path.relative_to(out).as_posix(): path.read_bytes()
        for path in sorted(out.rglob("*"))
        if path.is_file() and ".fenolite" not in path.relative_to(out).parts
    }


def part_f0(folder: Path, monkeypatch: pytest.MonkeyPatch, scratch: Path) -> dict[str, str]:
    """Write round F0 into ``folder``; the SHA-256 of every file by its path relative to ``folder``."""
    files = build_project(scratch / "build", monkeypatch)
    project = folder / PROJECT
    project.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (project / name).write_bytes(data)
    (folder / "README.md").write_text(F0_README, encoding="utf-8")
    sums: dict[str, str] = {}
    # sorted by the posix name, not by Path: a Windows path compares without case (blink_routed < README)
    files = {
        p.relative_to(folder).as_posix(): p
        for p in folder.rglob("*")
        if p.is_file() and p.name != "SHA256SUMS"
    }
    for name in sorted(files):
        sums[name] = hashlib.sha256(files[name].read_bytes()).hexdigest()
    (folder / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sums.items()), encoding="utf-8"
    )
    return sums


def test_f0_kit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Round F0: the routed blink project, the README with the fourteen steps and the sums."""
    folder = Path(HANDOVER_F0).expanduser() if HANDOVER_F0 else tmp_path / "F0-draftsman"
    if HANDOVER_F0:
        assert ROOT not in folder.resolve().parents, "the kit is written outside the repository"
    sums = part_f0(folder, monkeypatch, tmp_path)
    for suffix in ("PrjPcb", "PcbDoc", "PcbLib", "SchDoc", "SchLib", "OutJob"):
        assert f"{PROJECT}/{PROJECT}.{suffix}" in sums, suffix
    assert "README.md" in sums and not [name for name in sums if ".fenolite" in name]
    board = read_pcbdoc((folder / PROJECT / f"{PROJECT}.PcbDoc").read_bytes())
    assert board.tracks and board.vias
    text = (folder / "README.md").read_text(encoding="utf-8")
    assert [int(n) for n in re.findall(r"\*\*F0\.(\d+)\*\*", text)] == list(range(1, STEPS + 1))
    listed = (folder / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert [line.split("  ", 1)[1] for line in listed] == sorted(sums)


def test_f0_readme_follows_the_evidence_page() -> None:
    """The Portuguese steps name the same files, objects and texts as round F0 of the evidence page."""
    page = (ROOT / "docs" / "evidence" / "altium-draftsman.md").read_text(encoding="utf-8")
    start = page.index("### Round F0")
    english = page[start : page.index("\n## ", start)]
    for step in range(1, STEPS + 1):
        assert f"**F0.{step}**" in english and f"**F0.{step}**" in F0_README, step
    names = set(re.findall(r"`(F0-\d\d\.\w+|FENOLITE[- ][A-Z0-9 -]+?)`", english))
    assert names and names == set(re.findall(r"`(F0-\d\d\.\w+|FENOLITE[- ][A-Z0-9 -]+?)`", F0_README))
    kinds = r"(?: View| Table| Legend| Materials| Note| Dimension)"
    objects = set(re.findall(rf"\*\*([A-Z][A-Za-z ]+?{kinds})\*\*", english))
    assert objects and all(name in F0_README for name in objects), objects


def _write_bundle(folder: Path, files: dict[str, bytes]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    sums = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}
    (folder / "SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for name, digest in sums.items()))


def part_fp(folder: Path, monkeypatch: pytest.MonkeyPatch, scratch: Path, f0: Path | None = None) -> None:
    """Prepare independent FP3-5 now; FP1-2 require the real, privacy-reviewed F0.3 control."""
    files = build_project(scratch / "build", monkeypatch)
    text = draftsman.DraftsmanItem(
        "text", "Text", (10_000_000, 10_000_000), (80_000_000, 5_000_000), texts=("FENOLITE-1",)
    )
    view = draftsman.DraftsmanItem(
        "view",
        "BoardAssemblyViewData",
        (20_000_000, 40_000_000),
        (50_000_000, 30_000_000),
        title="Authored shell",
    )
    sheet = draftsman.DraftsmanSheet("probe", "Probe", "A4", (297_000_000, 210_000_000), (text,))
    spec = draftsman.DraftsmanSpec(PROJECT, (sheet,))
    files["FP3.PCBDwf"] = draftsman.write_draftsman(spec)
    from dataclasses import replace

    spec = replace(spec, sheets=(replace(sheet, items=(text, view)),))
    files["FP4.PCBDwf"] = draftsman.write_draftsman(spec)
    files["FP5.DwfDot"] = files["FP4.PCBDwf"]
    missing = ["FP1", "FP2"]
    if f0 is not None:
        controls = checked_files(f0)
        values = [data for name, data in controls.items() if Path(name).name.casefold() == "f0-03.pcbdwf"]
        assert len(values) == 1, "exactly one real F0.3 control is required"
        xml = decode(values[0])[1]
        assert xml.count(b">FENOLITE-1<") == 1, "F0.3 must hold exactly the authored control text"
        files["FP1.PCBDwf"] = draftsman.encode(xml)
        files["FP2.PCBDwf"] = draftsman.encode(xml.replace(b">FENOLITE-1<", b">FENOLITE-22<"))
        missing = []
    page = (ROOT / "docs/evidence/altium-draftsman.md").read_text()
    steps = page[page.index("### Round FP") : page.index("### Round F1")]
    files["README.md"] = (
        "# Part F candidate probes\n\nNative acceptance is unjudged. Work on a copy.\n\n"
        + "Missing real-control probes: "
        + (", ".join(missing) or "none")
        + ".\n\n"
        + steps
    ).encode()
    files["status.json"] = (
        json.dumps({"native_verdict": "unjudged", "missing": missing}, sort_keys=True) + "\n"
    ).encode()
    _write_bundle(folder, files)


def test_fp_candidates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    given = os.environ.get("FENOLITE_ALTIUM_PART_FP")
    folder = Path(given).expanduser() if given else tmp_path / "FP-draftsman"
    assert ROOT not in folder.resolve().parents
    source = os.environ.get("FENOLITE_DWF_F0")
    part_fp(folder, monkeypatch, tmp_path, None if source is None else Path(source).expanduser())
    for name in ("FP3.PCBDwf", "FP4.PCBDwf", "FP5.DwfDot"):
        assert read_draftsman((folder / name).read_bytes()).root is not None
    assert json.loads((folder / "status.json").read_text())["native_verdict"] == "unjudged"


_TAG = re.compile(rb"<(/?)([A-Za-z_][\w.:-]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*?)(/?)>")
STYLE_LISTS = ("ArrowStyles", "FillStyles", "LineStyles")
"""The root members that hold a style list in every document of round F0 and that FP3 and FP4 lack
(``docs/formats/altium/draftsman.md``, "Round F0 as saved by Altium Designer 24.5.2.23")."""


def root_members(xml: bytes) -> tuple[bytes, list[tuple[str, bytes]], bytes]:
    """The root's start tag, its direct members as (local name, bytes) in file order, and the root's end
    tag. The three parts joined give ``xml`` back byte for byte; ``ValueError`` otherwise."""
    tags = iter(_TAG.finditer(xml))
    root = next(tags, None)
    if root is None or root.group(1) or root.group(4) or root.start() != 0:
        raise ValueError("the text does not start with the root's start tag")
    members: list[tuple[str, bytes]] = []
    depth, start, name = 1, 0, b""
    for tag in tags:
        closing, opening = bool(tag.group(1)), not tag.group(1) and not tag.group(4)
        if depth == 1:
            if closing:
                end = xml[tag.start() :]
                if end.strip() != tag.group(0):
                    raise ValueError("text after the root's end tag")
                body = xml[root.end() : tag.start()]
                joined = b"".join(data for _, data in members)
                if joined != body:
                    raise ValueError("text between the root's members")
                return xml[: root.end()], members, end
            start, name = tag.start(), tag.group(2).rsplit(b":", 1)[-1]
            if not opening:
                members.append((name.decode(), xml[start : tag.end()]))
                continue
        depth += -1 if closing else 1 if opening else 0
        if depth == 1:
            members.append((name.decode(), xml[start : tag.end()]))
    raise ValueError("the root is not closed")


def grafted(candidate: bytes, control: bytes, *, keep: tuple[str, ...] = ()) -> bytes:
    """``control``'s root with each of its members replaced by ``candidate``'s member of the same name,
    except the members named in ``keep``; a candidate member that ``control`` lacks is an error."""
    _, own, _ = root_members(candidate)
    head, members, tail = root_members(control)
    mine = dict(own)
    if set(mine) - {name for name, _ in members}:
        raise ValueError("the candidate holds a member the control lacks")
    body = b"".join(mine[name] if name in mine and name not in keep else data for name, data in members)
    return head + body + tail


def dropped(xml: bytes, member: str) -> bytes:
    """``xml`` without its root member ``member``."""
    head, members, tail = root_members(xml)
    if member not in {name for name, _ in members}:
        raise ValueError(f"no root member {member}")
    return head + b"".join(data for name, data in members if name != member) + tail


def member_order(name: str) -> tuple[bool, str]:
    """The order of a root's members in every document of round F0 and in FP3: ``Id`` first, then the
    others by name."""
    return (name != "Id", name)


def with_style_lists(xml: bytes) -> bytes:
    """``xml`` with an empty member for each of ``STYLE_LISTS`` that it lacks, in the root's member order
    (``member_order``)."""
    head, members, tail = root_members(xml)
    names = {name for name, _ in members}
    added = [(name, f"<{name}/>".encode()) for name in STYLE_LISTS if name not in names]
    ordered = sorted([*members, *added], key=lambda member: member_order(member[0]))
    if [name for name, _ in members] != [name for name, _ in ordered if name not in dict(added)]:
        raise ValueError("the root's members are not in name order")
    return head + b"".join(data for _, data in ordered) + tail


def part_fpc(folder: Path, monkeypatch: pytest.MonkeyPatch, scratch: Path, f0: Path) -> dict[str, bytes]:
    """The correction round of c0388 (task 1.1) into ``folder``: FP3 and FP4 corrected from the empty
    document of round F0 (``F0-01.PCBDwf`` of ``f0``, after the kit privacy scan), the template FPC3, the
    authored style lists of FPC4, the writer's sheet in the native document (FPC5) and the drop series
    D01 to Dnn, one probe per root member that FP3 lacks. Every probe is stored uncompressed, as FP1 and
    FP2, which open (S-1589)."""
    fp = scratch / "fp"
    part_fp(fp, monkeypatch, scratch / "fp-scratch")
    fp3 = decode((fp / "FP3.PCBDwf").read_bytes())[1]
    fp4 = decode((fp / "FP4.PCBDwf").read_bytes())[1]
    controls = checked_files(f0)
    found = [data for name, data in controls.items() if Path(name).name.casefold() == "f0-01.pcbdwf"]
    assert len(found) == 1, "exactly one empty F0.1 control is required"
    empty = decode(found[0])[1]
    lacking = [name for name, _ in root_members(empty)[1] if name not in dict(root_members(fp3)[1])]
    files = {
        path.name: path.read_bytes() for path in sorted(fp.iterdir()) if path.name.startswith(PROJECT + ".")
    }
    fpc2 = grafted(fp4, empty)
    probes = {
        "FPC1.PCBDwf": grafted(fp3, empty),
        "FPC2.PCBDwf": fpc2,
        "FPC3.DwfDot": fpc2,
        "FPC4.PCBDwf": with_style_lists(fp3),
        "FPC5.PCBDwf": grafted(fp3, empty, keep=tuple(n for n, _ in root_members(fp3)[1] if n != "Pages")),
        "FPC6.PCBDwf": grafted(fp3, empty, keep=("FormatVersion",)),
    }
    for index, member in enumerate(lacking, start=1):
        probes[f"drop/D{index:02d}-{member}.PCBDwf"] = dropped(empty, member)
    probes.update(writer_probes(load_dir(scratch / "fp-scratch/build/.fenolite"), empty))
    for name, xml in probes.items():
        files[name] = draftsman.encode(xml)
    page = (ROOT / "docs/evidence/altium-draftsman.md").read_text()
    start = page.index("### Round FPC")
    steps = page[start : page.index("\n### ", start + 1)]
    listing = "".join(f"- `D{index:02d}`: without `{member}`\n" for index, member in enumerate(lacking, 1))
    files["README.md"] = (
        "# Part F correction round (c0388, task 1.1)\n\nNative acceptance is unjudged. Work on a copy.\n\n"
        + steps
        + "\n## The drop series\n\n"
        + listing
    ).encode()
    files["status.json"] = (
        json.dumps({"drop": lacking, "native_verdict": "unjudged"}, sort_keys=True) + "\n"
    ).encode()
    files["expected.md"] = FPC_EXPECTED.encode()
    _write_bundle(folder, files)
    return files


FPC_EXPECTED = """\
# Part F correction round: the writer's findings (c0388 tasks 4.1 and 4.2)

Native acceptance is unjudged. Per finding, report what Altium shows and, after a Save As of the probe
into a copy, the member values named. FPC7 to FPC11 hold the writer's items with every member of their
round F0 rows (`docs/formats/altium/draftsman.md`, "Round F0 member values").

1. **`BoardSourceName`** (FPC7, FPC8). The writer leaves it empty, in its own default namespace
   (`...Serialization.V1.Document.Page.Item.Board`). After Import Changes, does FPC7's drill table fill?
   Does FPC8, which names `blink_routed.PcbDoc`, behave differently? In the saved copy, does the member
   keep its namespace, and what value does Altium write?
2. **Note entry ids** (FPC7, FPC9). FPC7 writes 32 hexadecimal digits, as F0 does; FPC9 writes decimal
   numbers. Do both open and show `1.` and `2.`? Which ids does the saved copy hold?
3. **Style tables** (FPC1, FPC4, FPC7). The writer points every font id at its one font style and keeps
   F0's line style ids (1 to 3) and arrow style id (1). FPC1 and FPC7 carry the control's `LineStyles` and
   `ArrowStyles`, FPC4 only empty ones. Do FPC7's table lines and dimension arrows draw? In saved copies
   of FPC1 and FPC4, which ids do `LineStyles` and `ArrowStyles` hold?
4. **`ViewSideV2` of a bottom BOM** (FPC10). The writer writes `ViewSide` `Bottom` with `ViewSideV2` 0,
   the only value F0 shows (for a top view and for `All`). Does the table list `D1` only? Which
   `ViewSide` and `ViewSideV2` does the saved copy hold?
5. **Dimension snaps** (FPC7, FPC11). The snap points are the outline's corners in the PcbDoc's frame,
   with the outline's lower-left corner at (1000 mil, 1000 mil) as the build writes it, in 1/96 inch.
   Do both dimensions lie on the outline's top and left edges and read 50 mm and 30 mm? In the saved
   copy, is `HasBrokenSnaps` false, do the `SnapId` points stay, and does the vertical dimension keep
   `ExtensionsDirection` (1, 0)?
"""
"""The kit's ``expected.md``: the five findings of c0388's writer and the probes that answer them."""


def writer_probes(model: Design, control: bytes) -> dict[str, bytes]:
    """FPC7 to FPC11: the writer's sheets grafted into the empty F0.1 control as FPC1 is. FPC7 is the
    fabrication sheet; FPC8, FPC9 and FPC11 change one finding of it; FPC10 is the bottom assembly sheet.
    The routed blink has no stack-up, so one is set on the model here, only for the legend to be placed."""
    from dataclasses import replace

    from fenolite.exports.drawing_spec import DEFAULT
    from fenolite.lens.altium_draftsman import draftsman_spec
    from fenolite.model.board import StackLayer, Stackup

    assert model.board is not None
    layers = (
        StackLayer(id="sly_top", name="F.Cu", kind="copper", thickness=35_000),
        StackLayer(id="sly_core", name="core", kind="dielectric", thickness=1_530_000, material="FR4"),
        StackLayer(id="sly_bottom", name="B.Cu", kind="copper", thickness=35_000),
    )
    model = replace(model, board=replace(model.board, stackup=Stackup(id="stk_fpc", layers=layers)))
    spec = replace(
        DEFAULT, fab=replace(DEFAULT.fab, notes=("FENOLITE FPC NOTE ONE", "FENOLITE FPC NOTE TWO"))
    )
    document, _ = draftsman_spec(model, spec)
    sheets = {sheet.name: sheet for sheet in document.sheets}
    fab, bottom = sheets["fab"], sheets["assembly-bottom"]

    def graft(sheet: draftsman.DraftsmanSheet) -> bytes:
        own = draftsman.DraftsmanSpec(PROJECT, (sheet,), document.parameters, document.text_size)
        return grafted(decode(draftsman.write_draftsman(own))[1], control)

    fpc7 = graft(fab)
    empty_source = f'<BoardSourceName xmlns="{draftsman.BOARD}"></BoardSourceName>'.encode()
    named_source = empty_source.replace(b"></", f">{PROJECT}.PcbDoc</".encode())
    numbers = iter(range(1, 1000))
    decimal = re.sub(
        rb"(<NoteElement>(?:(?!</NoteElement>).)*?<Id>)[0-9a-f]{32}(</Id>)",
        lambda m: m.group(1) + str(next(numbers)).encode() + m.group(2),
        fpc7,
    )
    snaps = [i for i in fab.items if i.kind in ("DrillViewView", "LinearDimension")]
    probes = {
        "FPC7.PCBDwf": fpc7,
        "FPC8.PCBDwf": fpc7.replace(empty_source, named_source),
        "FPC9.PCBDwf": decimal,
        "FPC10.PCBDwf": graft(bottom),
        "FPC11.PCBDwf": graft(replace(fab, items=tuple(snaps))),
    }
    assert probes["FPC8.PCBDwf"] != fpc7 and decimal != fpc7 and next(numbers) == 3
    return probes


def _authored_control() -> bytes:
    """An authored stand-in for the empty F0.1 control: the root members of round F0 by name, a few
    filled, the others empty or nil; nothing of a saved document."""
    _, own, _ = root_members(decode(draftsman.write_draftsman(_probe_spec()))[1])
    names = sorted(
        {*dict(own), "ArrowStyles", "DocumentOptions", "FillStyles", "IsPanel", "LineStyles"},
        key=member_order,
    )
    filled = {
        "DocumentOptions": b"<DocumentOptions><Grid>10</Grid></DocumentOptions>",
        "FormatVersion": b"<FormatVersion>24</FormatVersion>",
        "IsPanel": b"<IsPanel>false</IsPanel>",
        "Pages": b"<Pages><Page><Id>1</Id><Items/></Page></Pages>",
        "SourceDocumentName": b"<SourceDocumentName>board.PcbDoc</SourceDocumentName>",
    }
    body = b"".join(filled.get(name, f'<{name} i:nil="true"/>'.encode()) for name in names)
    head = f'<Document xmlns="{NAMESPACE}" xmlns:i="{INSTANCE}">'.encode()
    return head + body + b"</Document>"


def _probe_spec() -> draftsman.DraftsmanSpec:
    text = draftsman.DraftsmanItem(
        "text", "Text", (10_000_000, 10_000_000), (80_000_000, 5_000_000), texts=("FENOLITE-1",)
    )
    sheet = draftsman.DraftsmanSheet("probe", "Probe", "A4", (297_000_000, 210_000_000), (text,))
    return draftsman.DraftsmanSpec(PROJECT, (sheet,))


def test_root_members_split_and_join() -> None:
    xml = decode(draftsman.write_draftsman(_probe_spec()))[1]
    head, members, tail = root_members(xml)
    assert head + b"".join(data for _, data in members) + tail == xml
    assert [name for name, _ in members] == ["Id", "FontStyles", "FormatVersion", "Pages", "Parameters",
                                             "SourceDocumentName"]  # fmt: skip
    with pytest.raises(ValueError, match="root"):
        root_members(xml[:-3])
    with pytest.raises(ValueError, match="between"):
        root_members(xml.replace(b"<FormatVersion>", b" <FormatVersion>"))


def test_correction_probes_from_an_authored_control() -> None:
    """The graft keeps the candidate's members and takes the rest from the control; the drop series takes
    one member out; the style lists are added empty, in name order."""
    control = _authored_control()
    candidate = decode(draftsman.write_draftsman(_probe_spec()))[1]
    names = [name for name, _ in root_members(control)[1]]
    fpc1 = grafted(candidate, control)
    assert [name for name, _ in root_members(fpc1)[1]] == names
    assert dict(root_members(fpc1)[1])["Pages"] == dict(root_members(candidate)[1])["Pages"]
    assert dict(root_members(fpc1)[1])["IsPanel"] == b"<IsPanel>false</IsPanel>"
    assert b"<FormatVersion>22<" in fpc1 and b"<FormatVersion>24<" in grafted(
        candidate, control, keep=("FormatVersion",)
    )
    page_only = grafted(
        candidate, control, keep=tuple(n for n in dict(root_members(candidate)[1]) if n != "Pages")
    )
    assert b"FENOLITE-1" in page_only and b"board.PcbDoc" in page_only
    assert [n for n, _ in root_members(dropped(control, "IsPanel"))[1]] == [
        n for n in names if n != "IsPanel"
    ]
    with pytest.raises(ValueError, match="no root member"):
        dropped(control, "Absent")
    with pytest.raises(ValueError, match="lacks"):
        grafted(control, candidate)
    styled = with_style_lists(candidate)
    order = [name for name, _ in root_members(styled)[1]]
    assert order == sorted(order, key=member_order) and set(STYLE_LISTS) <= set(order)
    assert dict(root_members(styled)[1])["LineStyles"] == b"<LineStyles/>"
    assert read_draftsman(draftsman.encode(styled)).root is not None


def test_writer_probes_from_an_authored_control() -> None:
    """FPC7 to FPC11 on an authored control: each probe keeps the control's members, FPC8, FPC9 and FPC11
    change one finding of FPC7, FPC10 holds a bottom BOM, and the kit's questions name every probe."""
    from _altium_job import blink_output

    model = blink_output().layout
    assert model is not None
    control = _authored_control()
    probes = writer_probes(model, control)
    names = [name for name, _ in root_members(control)[1]]
    for name, xml in probes.items():
        assert [n for n, _ in root_members(xml)[1]] == names, name
        assert read_draftsman(draftsman.encode(xml)).root is not None, name
    fpc7 = probes["FPC7.PCBDwf"]
    for kind in (b"DrillTableBoardView", b"LayerStackLegendView", b"Note", b"LinearDimension"):
        assert b'i:type="' + kind + b'"' in fpc7, kind
    assert fpc7.count(b'i:type="LinearDimension"') == 2
    assert b">blink_routed.PcbDoc</BoardSourceName>" in probes["FPC8.PCBDwf"]
    assert re.findall(rb"<NoteElement>.*?<Id>(\w+)</Id>", probes["FPC9.PCBDwf"]) == [b"1", b"2"]
    fpc10 = probes["FPC10.PCBDwf"]
    assert b"<ViewSide>Bottom</ViewSide><ViewSideV2>0</ViewSideV2>" in fpc10
    fpc11 = probes["FPC11.PCBDwf"]
    assert fpc11.count(b"<Item ") == 3 and b"DrillTableBoardView" not in fpc11
    for name in probes:
        assert name.removesuffix(".PCBDwf") in FPC_EXPECTED, name


@pytest.mark.skipif(
    not (os.environ.get("FENOLITE_ALTIUM_PART_FPC") and os.environ.get("FENOLITE_DWF_F0")),
    reason="the correction round needs the reviewed F0 folder and a folder outside the repository",
)
def test_fpc_correction_kit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = Path(os.environ["FENOLITE_ALTIUM_PART_FPC"]).expanduser()
    assert ROOT not in folder.resolve().parents
    files = part_fpc(folder, monkeypatch, tmp_path, Path(os.environ["FENOLITE_DWF_F0"]).expanduser())
    probes = [name for name in files if name.endswith((".PCBDwf", ".DwfDot"))]
    assert len([name for name in probes if name.startswith("drop/")]) == len(
        json.loads(files["status.json"])["drop"]
    )
    for name in probes:
        assert read_draftsman(files[name]).root is not None, name


def _library_prefix(library: PurePath, source: PurePath) -> str:
    """Keep the same library source when a candidate kit is authored on another drive."""
    if library.drive.casefold() != source.drive.casefold():
        return library.as_posix()
    path_module = ntpath if isinstance(library, PureWindowsPath) else posixpath
    relative = path_module.relpath(str(library), str(source)).replace("\\", "/")
    return "${KIPRJMOD}/" + relative


@pytest.mark.parametrize(
    "library,source,expected",
    [
        ("D:/checkout/libs", "C:/scratch/source", "D:/checkout/libs"),
        ("C:/checkout/libs", "C:/scratch/source", "${KIPRJMOD}/../../checkout/libs"),
    ],
)
def test_candidate_library_reference_across_drives(library: str, source: str, expected: str) -> None:
    assert _library_prefix(PureWindowsPath(library), PureWindowsPath(source)) == expected


@pytest.mark.parametrize("changed", ["unchanged", "symbol", "table"])
def test_rooted_candidate_library_input_invalidates_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed: str
) -> None:
    libraries = tmp_path / "libraries"
    libraries.mkdir()
    for name in ("Mini_v9.pretty", "Mini_v9.kicad_sym"):
        original = ROOT / "tests/data/libs" / name
        if original.is_dir():
            shutil.copytree(original, libraries / name)
        else:
            shutil.copyfile(original, libraries / name)
    source = tmp_path / "source"
    source.mkdir()
    for name in ("fp-lib-table", "sym-lib-table"):
        text = (SCRIPT.parent / name).read_text(encoding="utf-8")
        text = text.replace("${KIPRJMOD}/../../tests/data/libs", libraries.as_posix())
        (source / name).write_text(text, encoding="utf-8")
    script = source / "design.py"
    script.write_bytes(SCRIPT.read_bytes())
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "config"))

    def invoke(*args: str):
        out, error = io.StringIO(), io.StringIO()
        monkeypatch.setattr("sys.stdout", out)
        monkeypatch.setattr("sys.stderr", error)
        code = cli_main.main(
            [
                "build",
                str(script),
                "--out",
                str(tmp_path / "build"),
                "--target",
                "altium",
                "--json",
                *FLAGS,
                *args,
            ]
        )
        return code, json.loads(out.getvalue()), json.loads(error.getvalue() or "{}")

    code, reply, error = invoke("--dry-run")
    assert code == 0, (reply, error)
    if changed != "unchanged":
        library = libraries / "Mini_v9.kicad_sym" if changed == "symbol" else source / "sym-lib-table"
        library.write_bytes(library.read_bytes() + b"\n")
    code, _reply, error = invoke("--confirm", "--plan", reply["result"]["plan_id"])
    if changed == "unchanged":
        assert code == 0, error
        assert (tmp_path / "build" / f"{PROJECT}.SchDoc").is_file()
    else:
        assert code == 4 and error["code"] == "FEN-4002"
        assert not (tmp_path / "build").exists()


def part_accept(folder: Path, monkeypatch: pytest.MonkeyPatch, scratch: Path) -> None:
    """A native-gate override exists only in this candidate kit, never as a command option."""
    source = scratch / "source"
    source.mkdir(parents=True)
    for name in ("fp-lib-table", "sym-lib-table"):
        text = (SCRIPT.parent / name).read_text()
        text = text.replace(
            "${KIPRJMOD}/../../tests/data/libs", _library_prefix(ROOT / "tests/data/libs", source)
        )
        (source / name).write_text(text)
    script = source / "design.py"
    script.write_text(
        SCRIPT.read_text() + "\nfrom fenolite.dsl import stack\n"
        'design.stackup(*stack.preset("two-layer-1.6mm"))\n'
        'design.title_block(title="Fenolite Draftsman bench", revision="F", date="2026-11-01")\n'
    )
    spec = scratch / "drawing.toml"
    spec.write_text(
        'schema = "fenolite.drawing-spec.v0"\n[fab]\nnotes = ["Authored fab one", "Authored fab two"]\n'
        '[assembly]\nnotes = ["Authored assembly one", "Authored assembly two"]\n'
    )
    monkeypatch.setattr(draftsman, "NATIVE_WRITE", True)
    files = build_project(
        scratch / "build",
        monkeypatch,
        script=script,
        flags=("--altium-draftsman", "on", "--drawing-spec", str(spec)),
    )
    model = load_dir(scratch / "build/.fenolite")
    expected = [
        "# Candidate acceptance: expected model values",
        "",
        "Native outcomes are unjudged.",
        "",
        "## Drill counts",
        "",
    ]
    expected += [f"- {row.drill} nm: {row.count} hole(s), plated={row.plated}" for row in drill_rows(model)]
    stack = stackup_block(model, 1_500_000)
    expected += ["", "## Stack-up", ""]
    expected += [] if stack is None else [" | ".join(row) for row in stack.rows]
    expected += [
        "",
        "## Parts",
        "",
        ", ".join(sorted(c.ref for c in model.circuit.components)),
        "",
        "Native generic Table, dimensions and exact table filters are pending F0; board rows use Texts.",
    ]
    files["expected.md"] = ("\n".join(expected) + "\n").encode()
    page = (ROOT / "docs/evidence/altium-draftsman.md").read_text()
    start = page.index("### Round F1")
    files["README.md"] = page[start : page.index("\n## ", start)].encode()
    files["drawing.toml"] = spec.read_bytes()
    _write_bundle(folder, files)


def test_accept_candidate_kit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    given = os.environ.get("FENOLITE_ALTIUM_PART_F")
    folder = Path(given).expanduser() if given else tmp_path / "F-draftsman-accept"
    assert ROOT not in folder.resolve().parents
    part_accept(folder, monkeypatch, tmp_path)
    scope = draftsman.written_scope(read_draftsman((folder / f"{PROJECT}.PCBDwf").read_bytes()).root)
    assert len(scope.sheets) == 3 and any(i.name == "layer-stack-legend" for i in scope.items("view"))
    assert len(scope.items("note")) == 2
    assert all(len(i.texts) == 2 for i in scope.items("note"))
    assert (folder / "SHA256SUMS").is_file() and "U1" in (folder / "expected.md").read_text()


@pytest.mark.skipif(
    not os.environ.get("FENOLITE_ALTIUM_F8"), reason="a real native F8 save has not been supplied"
)
def test_f8_saved_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    given = Path(os.environ["FENOLITE_ALTIUM_F8"]).expanduser()
    checked = checked_files(given.parent)
    saved = draftsman.written_scope(read_draftsman(checked[given.name]).root)
    part_accept(tmp_path / "accept", monkeypatch, tmp_path)
    candidate = draftsman.written_scope(
        read_draftsman((tmp_path / "accept" / f"{PROJECT}.PCBDwf").read_bytes()).root
    )
    assert len(saved.sheets) == len(candidate.sheets)
    for expected, observed in zip(candidate.sheets, saved.sheets, strict=True):
        assert expected.paper == observed.paper
        for item in expected.items:
            assert any(
                (item.kind, item.side, item.title, item.texts) == (i.kind, i.side, i.title, i.texts)
                for i in observed.items
            )
