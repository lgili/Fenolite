# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Monta o kit da Part T (c0160 5.3, c0166 2.1) no seu PC, a partir do clone do Fenolite.

Os dois demos públicos do KiCad (vme-wren e complex_hierarchy, CC-BY-SA) não são publicados no
repositório: este script baixa os dois pelo corpus e converte os três casos para Altium.

Uso, dentro do clone do Fenolite (branch release-0.5.0), com o KiCad 10 instalado:

    uv sync --all-extras
    uv run python <caminho>/montar_part_t.py --out <pasta-nova>
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

IDS = (
    "kicad-demo-10-0-6-pcb-02 kicad-demo-10-0-6-pcb-18 kicad-demo-10-0-6-sch-01 kicad-demo-10-0-6-sym-01 "
    "kicad-demo-10-0-6-mod-01 kicad-demo-10-0-6-fplib-01 kicad-demo-10-0-6-mod-62 kicad-demo-10-0-6-mod-63 "
    "kicad-demo-10-0-6-mod-64 kicad-demo-10-0-6-mod-65 kicad-demo-10-0-6-mod-66 kicad-demo-10-0-6-mod-67 "
    "kicad-demo-10-0-6-mod-68 kicad-demo-10-0-6-mod-69 kicad-demo-10-0-6-mod-70 kicad-demo-10-0-6-pro-02 "
    "kicad-demo-10-0-6-dru-02 kicad-demo-10-0-6-pro-35 kicad-demo-9-0-9-1-pro-17 kicad-demo-10-0-6-sch-010 "
    "kicad-demo-10-0-6-sch-106"
).split()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    repo = Path.cwd()
    if not (repo / "tools" / "corpus_fetch.py").is_file():
        sys.exit("rode dentro da pasta do clone do Fenolite")
    out = args.out.resolve()
    if out.exists():
        sys.exit(f"{out} já existe: escolha uma pasta nova")
    subprocess.run([sys.executable, "tools/corpus_fetch.py", "--only", *IDS], check=True)
    sys.path[:0] = sorted({os.path.dirname(p) for p in glob.glob(str(repo / "tests/**/_*.py"), recursive=True)})
    from _corpus import manifest_items
    from _schprojects import project_folder, roots

    src = out / "src"
    (src / "DIFAT").mkdir(parents=True)
    for use in ("rt0", "project"):
        for item in manifest_items(use):
            if item.path.name.startswith("vme-wren.") and item.path.suffix != ".kicad_sch" and item.path.is_file():
                shutil.copy(item.path, src / "DIFAT" / item.path.name)
    row = next(r for r in roots(10) if Path(r.path).stem == "complex_hierarchy")
    folder = project_folder(out / "tmp", row, 10)
    assert folder is not None, "complex_hierarchy não está no cache do corpus"
    shutil.copytree(folder, src / "SCHEMATIC")
    shutil.rmtree(out / "tmp")
    (src / "PADSTACK").mkdir()
    shutil.copy(repo / "tests/data/kicad/convert/padstack.kicad_pcb", src / "PADSTACK" / "padstack.kicad_pcb")
    cases = {"PADSTACK": src / "PADSTACK", "SCHEMATIC": src / "SCHEMATIC", "DIFAT": src / "DIFAT" / "vme-wren.kicad_pcb"}
    for name, source in cases.items():
        with open(out / f"{name}.json", "w", encoding="utf-8") as reply:
            run = subprocess.run(
                [sys.executable, "-m", "fenolite", "convert", str(source), "--to", "altium", "--out", str(out / name),
                 "--allow-lossy", "--confirm", "--json", "--seed", "1", "--timestamp", "2026-10-16T00:00:00Z"],
                stdout=reply, check=False,
            )  # fmt: skip
        print(f"{name}: exit {run.returncode}")
    shutil.rmtree(src)
    print(f"pronto: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
