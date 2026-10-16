# Parte Q, fase A: painéis no Altium Designer 26.5

Mudança c0173 do Fenolite. Nada aqui é verificação do Altium ainda: esta fase **observa** como o Altium
grava um Embedded Board Array, para o Fenolite aprender os registros. A pasta `board/` tem a placa de teste
(40 × 30 mm, duas camadas, feita pelo Fenolite para o Fenolite). Coordenadas em milímetros a partir da
origem do documento. Trabalhe numa cópia da pasta. O texto completo, em inglês, está em `PART-Q.md`.

Para cada passo, responda `as expected` ou, numa frase, o que foi diferente.

1. **Q1** Abra `board/board.PrjPcb`. Adicione um PCB novo, `panel-a.PcbDoc`, ao projeto (mesma pasta).
   **Place » Embedded Board Array/Panelize**, escolha `board.PcbDoc` e posicione. Em Properties:
   X 5, Y 5, Rotation 0, Column Count 2, Row Count 2, Column Spacing 42, Row Spacing 32, Mirrored desligado,
   Link Location desligado. Se aparecer o diálogo de sincronizar camadas, escolha
   "Synchronize Manually Later" e anote o texto do diálogo. Salve.
   Esperado: quatro placas com 2 mm entre elas.
2. **Q2** Partindo sempre de uma cópia nova de `panel-a`, mude **uma** coisa e faça **File » Save As**:
   - `panel-cols4`: Column Count 4
   - `panel-rows3`: Row Count 3
   - `panel-spacing`: Column Spacing 45, Row Spacing 35
   - `panel-margin`: Column Margin 3, Row Margin 3 (anote se os campos de Spacing mudaram sozinhos)
   - `panel-rot90`: Rotation 90
   - `panel-mirror`: Mirrored ligado
   - `panel-link`: Link Location ligado
   - `panel-move`: X 12, Y 7

   Esperado: todos salvam; anote qualquer outro campo que mudou além do que você mudou.
3. **Q3** Em `panel-a`, adicione duas camadas mecânicas (View Configuration ou Layer Stack Manager). Na
   primeira, Layer Type = V Cut; na segunda, Layer Type = Route Tool Path. Desenhe uma trilha em cada uma.
   Salve como `panel-layers`. Esperado: salva; anote o número e o nome que o Altium deu a cada camada.
4. **Q4** Em `panel-a`, coloque um segundo array da mesma placa em X 100, Y 5, com 1 coluna e 1 linha.
   Salve como `panel-two`. Esperado: dois arrays no documento.
5. **Q5** Em `panel-a`, rode **File » Fabrication Outputs » Gerber Files** e **NC Drill Files** com os
   valores padrão. Esperado: as quatro cópias aparecem no cobre e na furação. Mande só a lista dos nomes
   dos arquivos gerados.
6. **Q6** Feche o Altium. Compacte a pasta em .zip **sem** as pastas `History` e `Project Outputs` e
   mande. O Fenolite verifica os caminhos do zip (`fenolite kit verify`) antes de ler qualquer arquivo.

Mande junto: a versão (`AD <major>.<minor>`, de Help » About), a data, e o SHA-256 de cada arquivo
enviado. Os arquivos que o Altium salva ficam fora do repositório; só fatos medidos, hashes e tamanhos
entram nele. `SHA256SUMS` tem o SHA-256 de cada arquivo desta pasta como o Fenolite a gravou.
