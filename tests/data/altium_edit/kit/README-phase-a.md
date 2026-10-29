# Fenolite – kit J, fase A: sessões de edição de documentos Altium (observação)

Mudança c0241 do Fenolite. Nada aqui é verificado ainda: os arquivos que você salvar mostram ao Fenolite o
que o Altium Designer muda num documento quando faz uma única edição. O Fenolite lê os arquivos salvos com
os seus próprios leitores. Nenhum arquivo salvo pelo Altium entra no repositório; só contagens, nomes de
registros, hashes e tamanhos.

## O que tem nesta pasta

- `board/`: projeto Altium gerado pelo Fenolite (`tests/data/altium_edit/edit.py`): placa de 40 × 30 mm,
  duas camadas, `R1` e `R2` (`Mini_R_0603`, Comment `1k`) e o LED `D1` em cima, a trilha `probe` de
  (10, 5) a (20, 5) mm no Top Layer em `GND`, os polígonos `GND` (Bottom Layer) e `VIN` (Top Layer) sem
  cobre derramado, o texto `FENOLITE EDIT`, uma linha e uma região em Mechanical 13 e a regra `Clearance`
  de 0,2 mm. Arquivos: `edit.PrjPcb`, `edit.PcbDoc`, `edit.PcbLib`, `edit.SchDoc`, `edit.SchLib` e
  `edit.OutJob`.
- `expected.md`: cada item que os passos citam, lido de volta de `board/edit.PcbDoc` pelo Fenolite, em mm a
  partir do canto inferior esquerdo da placa, Y para cima.
- `PART-J.md`: estes passos em inglês, como estão na página de evidência.
- `SHA256SUMS`: o SHA-256 de cada arquivo, como gerado.

## Antes de começar

- Trabalhe numa cópia desta pasta.
- A partir do J3, cada passo começa de `board/edit.PcbDoc` como o kit gravou (o J17 começa do arquivo do
  J16, J18 a J20 de `board/edit.SchDoc`, o J21 de `board/edit.PcbLib`): abra de novo com **File » Open**,
  faça só a mudança do passo e salve com **File » Save As** dentro de `board/`, com o nome indicado.
- Nunca salve os documentos do próprio kit no lugar. Quando o Altium perguntar se quer salvar `edit.PrjPcb`
  ou outro documento, responda No.
- Em cada passo anote `como esperado` ou o que foi diferente, numa frase, e qualquer mensagem que o Altium
  mostrou.

## Passos

1. **J1** Abra `board/edit.PrjPcb` e `board/edit.PcbDoc`. Salve sem mudar nada com **File » Save As** como
   `J01-resave.PcbDoc`. Esperado: o documento abre sem mensagem de reparo e salva sem mensagem.
2. **J2** Feche `J01-resave.PcbDoc`, abra de novo e salve sem mudar nada como `J02-resave.PcbDoc`.
   Esperado: abre e salva sem mensagem.
3. **J3** Selecione a trilha `probe` e, em Properties, ponha Start Y e End Y em 6 mm (sobe 1 mm). Salve como
   `J03-move-track.PcbDoc`. Esperado: só a trilha se move; a via fica em (20, 5).
4. **J4** Selecione `R1` e ponha X em 14 mm. Salve como `J04-move-component.PcbDoc`. Esperado: `R1` se move
   com os pads e os textos; as trilhas ficam onde estavam.
5. **J5** Ponha a Width da trilha `probe` em 0,3 mm. Salve como `J05-width.PcbDoc`. Esperado: só a largura
   muda.
6. **J6** Ponha o Comment de `R1` em `2k2`. Salve como `J06-comment.PcbDoc`. Esperado: o comentário de `R1`
   mostra `2k2`.
7. **J7** Troque o texto livre `FENOLITE EDIT` por `FENOLITE EDIT 2`. Salve como `J07-text.PcbDoc`.
   Esperado: o texto novo aparece.
8. **J8** Ponha a Rotation de `R2` em 90. Salve como `J08-rotate.PcbDoc`. Esperado: `R2` gira em torno da
   sua origem, com os pads e os textos.
9. **J9** Em Properties, ponha a Layer de `D1` em Bottom Layer (flip). Salve como `J09-flip.PcbDoc`.
   Esperado: `D1` fica no lado de baixo, espelhado, com o overlay no Bottom Overlay.
10. **J10** Apague a trilha `probe`. Salve como `J10-delete-track.PcbDoc`. Esperado: a via fica.
11. **J11** Apague `R2`. Salve como `J11-delete-component.PcbDoc`. Esperado: `R2` some com os pads e os
    textos; as trilhas que chegavam nele ficam.
12. **J12** Selecione a trilha `probe` e a sua via, **Edit » Copy** com a via como ponto de referência,
    **Edit » Paste** e clique 3 mm acima da via, longe de outro cobre. Salve como `J12-copy.PcbDoc`.
    Esperado: uma segunda trilha e uma segunda via; anote a net que as cópias mostram.
13. **J13** **Place » Component**: no painel Components escolha `edit.PcbLib` (se não aparecer, acrescente
    a partir de `board/` como biblioteca de arquivo) e o footprint `Mini_R_0603`; coloque perto de (32, 22)
    e anote o designator que o Altium deu. Salve como `J13-place-component.PcbDoc`. Esperado: um componente
    a mais, com dois pads.
14. **J14** Selecione a linha e a região de Mechanical 13 e ponha a Layer delas em Mechanical 15. Salve como
    `J14-layer.PcbDoc`. Esperado: as duas aparecem em Mechanical 15.
15. **J15** **Design » Rules**, regra `Clearance`: ponha a folga mínima em 0,25 mm. Salve como
    `J15-rule.PcbDoc`. Esperado: a regra mostra 0,25 mm quando o editor é aberto de novo.
16. **J16** **Tools » Polygon Pours » Repour All**. Salve como `J16-repour.PcbDoc`. Esperado: os dois
    polígonos derramam sem mensagem.
17. **J17** Abra `J16-repour.PcbDoc` e apague o polígono `VIN` (com o cobre dele). Salve como
    `J17-delete-polygon.PcbDoc`. Esperado: `GND` mantém o cobre; anote o Pour Index que o Polygon Manager
    (**Tools » Polygon Pours » Polygon Manager**) mostra para `GND`.
18. **J18** Abra `board/edit.SchDoc`, selecione `R1` e, em Properties, aumente o X em 10 mm (para a
    direita). Salve como `J18-sch-move.SchDoc`. Esperado: `R1` se move; anote se os fios acompanharam.
19. **J19** Em `board/edit.SchDoc` troque o texto `1k` de `R1` (o Comment ou o Value, o que mostra `1k`) por
    `2k2`. Salve como `J19-sch-parameter.SchDoc`. Esperado: `R1` mostra `2k2`.
20. **J20** Em `board/edit.SchDoc` apague `R2`. Salve como `J20-sch-delete.SchDoc`. Esperado: `R2` some; os
    fios ficam.
21. **J21** Abra `board/edit.PcbLib`, footprint `Mini_R_0603`: ponha o X do pad 1 em -0,9 mm. Salve como
    `J21-library.PcbLib`. Esperado: só esse pad se move.
22. **J22** Feche o Altium, compacte a pasta sem as pastas `History` e `Project Outputs` e mande. Esperado:
    o Fenolite roda a verificação de caminhos do `fenolite kit verify` antes de ler qualquer arquivo.

## O que mandar de volta

1. A pasta inteira, compactada (sem `History` e `Project Outputs`), com os arquivos que o Altium salvou.
2. A versão do Altium Designer (**Help » About**, no formato `AD 26.5`) e a data.
3. O SHA-256 de cada arquivo mandado (os do kit estão em `SHA256SUMS`).
4. Um resultado por passo: `como esperado` ou o que foi diferente, e qualquer mensagem que apareceu.

O Fenolite só lê os arquivos depois de rodar a verificação de caminhos do `fenolite kit verify` na pasta.
