# Part T — projetos convertidos (c0160 5.3 e c0166 2.1)

Três projetos KiCad convertidos para Altium pelo `fenolite convert --to altium`. Os dois demos públicos do
KiCad não podem ser publicados no repositório, então você monta o kit no seu PC (precisa do KiCad 10
instalado, para o netlist do esquemático):

```powershell
cd <clone do Fenolite>
git fetch origin release-0.5.0
git checkout release-0.5.0
uv sync --all-extras
uv run python <esta pasta>\montar_part_t.py --out C:\fenolite-testes\part-T
```

O script baixa os demos pelo corpus e cria `DIFAT/`, `SCHEMATIC/`, `PADSTACK/` e um `<caso>.json` para
cada um. Se o `kicad-cli` não for achado, defina antes
`$env:FENOLITE_KICAD_CLI = "C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"`. Trabalhe sempre em cópias.

| pasta | o que é |
|---|---|
| `DIFAT/` | o demo público `vme-wren` (placa grande: documento DIFAT) |
| `SCHEMATIC/` | o demo público `complex_hierarchy` (esquemático com folhas filhas repetidas) |
| `PADSTACK/` | placa de 4 camadas feita para o Fenolite, pads com formas diferentes por camada |

`<caso>.json` é o relatório da conversão (o que foi mantido, mudado ou perdido).

| passo | o que fazer | o que reportar |
|---|---|---|
| T1 | Abrir os três projetos: PCB, esquemático e bibliotecas | abriu? alguma mensagem de erro? |
| T2 | Compilar cada projeto; olhar as instâncias das folhas e a conectividade | resultado da compilação |
| T3 | Repour dos polígonos em cada PCB | resultado do repour |
| T4 | DRC em cada placa convertida | contagem por categoria de regra |
| T5 | Update PCB from schematic e olhar o ECO (**não executar**) | trocas de footprint inesperadas |
| T6 | Colocar um footprint do PcbLib numa placa rascunho; olhar padstack e máscaras dos conectores | resultado da colocação, pads e máscara |

Mande: versão do Altium (major.minor), data e um resultado curto por passo. Sem prints, sem projeto de
origem, sem dados do empregador.
