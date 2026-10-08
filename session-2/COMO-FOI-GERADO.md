# Como o pacote foi gerado

Fenolite no commit `695574baa4aad7a9db1d286316b1c2bcaa3c9bc6` (0.2.1), em 2026-10-08, com `uv sync
--all-extras`. Tudo é refeito, da raiz desse checkout, por um só script, que recebe a pasta `session-2`
(fora do checkout):

```
bash <pacote>/session-2/_gerador/gerar.sh <pacote>/session-2
```

O script está em `_gerador/gerar.sh`. Semente `0` e data `2026-01-01T00:00:00Z` em todo comando que as
aceita. Duas corridas em pastas diferentes deram os mesmos bytes (`diff -r` sem diferença). Os comandos:

| parte | comando (da raiz do checkout) |
|---|---|
| K | `uv run fenolite kit build --out K-kit --seed 0 --timestamp 2026-01-01T00:00:00Z --confirm --json` |
| O `blink_routed/` | `uv run fenolite build examples/blink_routed/design.py --target altium --out O-outjob/blink_routed --seed 0 --timestamp 2026-01-01T00:00:00Z --confirm --json` |
| O `blink_routed_p6/` | o mesmo, com `--altium-outjob-preset O-outjob/precision6.toml --out O-outjob/blink_routed_p6` |
| O `board6/` | `uv run python _gerador/vias/construir.py examples/kit/board6/design.py O-outjob/board6` (como `fenolite kit build` constrói a amostra: o `build` daria duas camadas a esse script) |
| X8 | `FENOLITE_ALTIUM_BODY2=X8-bodies uv run pytest tests/unit/lens/test_altium_bodies.py -k golden -q`; o `README.md` em inglês que o teste escreve é apagado (este guia o substitui) |
| R | `_altium_channels.files()` de `tests/`, a mesma função de `tests/data/altium/channels/two/author.py`, gravada em `R-repeated-sheet/` |
| S | `uv run fenolite build _gerador/simbolos/simbolos.py --target altium --out S-simbolos --seed 0 --timestamp 2026-01-01T00:00:00Z --confirm --json` |
| V | `uv run python _gerador/vias/construir.py _gerador/vias/vias.py V-vias` |

Depois as pastas `.fenolite/` dos builds são apagadas: não são abertas no Altium e guardam a pasta do build.

## Conferências feitas

- **Iguais ao pacote parcial anterior** (commit `f1b878e` do ramo `pack/altium-session-2`): os 12 arquivos de
  `O-outjob/blink_routed/` e `blink_routed_p6/`, `precision6.toml`, 5 dos 6 arquivos de `O-outjob/board6/`,
  os 10 de `X8-bodies/` e os 3 de `R-repeated-sheet/`.
- **Diferente, como esperado:** `O-outjob/board6/board6.SchDoc`, que ganhou o mapa de pinos do LED `D1`
  (c0144).
- **R** é byte a byte o exemplo do repositório `tests/data/altium/channels/two/` (os três SHA-256 de
  `docs/evidence/altium-schematic.md`, Parte R). **X8** `saved/` é byte a byte `tests/data/altium/body2/`.
- **K:** digest do kit (SHA-256 de `kit.json`) `8600c44ad78f79beb1c94a0b3036b2778b7f73179b642190affcece0db94727a`;
  `fenolite kit verify` no kit recém-construído: 32 passos `skipped`, nenhum problema do kit.
- **V:** `fenolite check vias.PrjPcb` passa todos os estágios (sem curto, sem diferença de paridade, RT-A0 e
  RT-A1 iguais).
- Nenhum caminho absoluto desta máquina em nenhum arquivo (busca em 8 bits e em UTF-16 nas duas
  alinhagens, com a varredura de privacidade do kit, `fenolite.verify.kit.results.privacy_scan`, e com uma
  busca simples das raízes de usuário e temporárias).

## Arquivos de `_gerador/`

- `gerar.sh`: o script acima.
- `vias/vias.py`: a placa da Parte V (seis camadas, planos nos ids 39 e 40, sinal nos ids 3 e 5).
- `vias/construir.py`: constrói um script de amostra como `fenolite kit build` (`fenolite.cli._kit.build_sample`).
- `simbolos/simbolos.py`: os cinco símbolos da Parte S; `simbolos/FenoliteDemo.kicad_sym` e
  `simbolos/sym-lib-table` são cópias de `examples/altium_kicad/` (biblioteca de exemplo do Fenolite, CC0),
  de onde vem o `CONN2`.
