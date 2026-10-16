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
import os
import re
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main
from fenolite.backends.altium.read.pcb import read_pcbdoc

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


def build_project(out: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    """Build the routed blink for Altium through the command line; the files without the build's cache."""
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(out.parent / "kicad-config"))
    monkeypatch.setattr("sys.stdout", io.StringIO())
    monkeypatch.setattr("sys.stderr", io.StringIO())
    argv = ["build", str(SCRIPT), "--out", str(out), "--target", "altium", "--confirm", "--json", *FLAGS]
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
    for path in sorted(p for p in folder.rglob("*") if p.is_file() and p.name != "SHA256SUMS"):
        sums[path.relative_to(folder).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
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
