# Sessão 2 no Altium Designer 26: guia único

- **Fenolite:** commit `695574b` (`695574baa4aad7a9db1d286316b1c2bcaa3c9bc6`), versão 0.2.1. **Pacote montado em:** 2026-10-08.
- Todos os arquivos foram gerados de novo a partir desse commit, com semente e data fixas
  (`COMO-FOI-GERADO.md`). Nenhum deles foi aberto no Altium antes.
- **Os passos foram escritos a partir da documentação da Altium:** o nome de um menu ou de uma janela pode
  ser outro no AD26. Se um passo não puder ser feito como está escrito, diga o que viu no lugar.
- O que já foi resolvido na sessão 1 (os projetos abrem sem pedido de reparo) não é perguntado de novo.
- Nada do que o Altium gravar entra no repositório. Arquivos salvos pelo Altium guardam caminhos da sua
  máquina e o seu usuário: não publique; leve para casa (último item).

## Ordem e tempo

Na ordem do que mais destrava a graduação da escrita Altium na 0.3.0. Pare onde o tempo acabar: cada parte
vale sozinha.

| # | parte | pasta | o que resolve | minutos |
|---|---|---|---|---|
| 1 | **K: kit de verificação** | `K-kit/` | a única coisa que gradua um tipo de arquivo (c0092, tarefa 3.1): uma corrida do kit registrada; inclui os passos de `D1` do c0144 | 70 |
| 2 | **S: os cinco símbolos** | `S-simbolos/` | o defeito que você apontou em 2026-10-07 (c0134) | 5 |
| 3 | **O: output job com Gerber** | `O-outjob/` | o Gerber que não plotava nada (c0138) | 25 |
| 4 | **X8: corpos dos componentes** | `X8-bodies/` | se a opção de corpos pode virar padrão (c0121) | 20 |
| 5 | **R: folha repetida** | `R-repeated-sheet/` | canais `Repeat` e a página preta (c0083, c0146) | 30 |
| 6 | **V: vias sem pad** | `V-vias/` | o que o Altium grava ao remover pads de via (c0132) | 15 |
| 7 | D: DRC do Altium (opcional, por último) | nenhuma: arquivo público | os 7 achados de folga do documento público `-03` (c0131) | 10 |

**Total: 165 minutos** (175 com a parte D). Antes de começar, anote a versão: Help » About, como
`AD <maior>.<menor>` (por exemplo `AD 26.5`).

Versão e data: ______________________________

---

## 1. K: kit de verificação (70 min)

Pasta `K-kit/`. O roteiro exato, em inglês, é `K-kit/STEPS.md`: siga-o em ordem; aqui está o resumo com
as respostas esperadas. Digest do kit (SHA-256 de `kit.json`):
`8600c44ad78f79beb1c94a0b3036b2778b7f73179b642190affcece0db94727a`.

Regras do kit:

- **Não altere nenhum arquivo do kit fora de `results/`.** Os arquivos pedidos vão para `results/<amostra>/`
  com o nome exato do `STEPS.md` (File » Save As). Ao fechar um projeto, se o Altium perguntar se salva,
  responda **No** (só o passo K1.5 salva o projeto, e em `results/`). No K3.1 o projeto `flat` ganha um
  documento novo: ao fechar, **não salve o projeto**.
- As respostas digitadas vão em `results/form.json` (Bloco de Notas): `"altium_version": "AD 26.x"`,
  `"os_family": "Windows"`, `"date": "2026-10-08"`; em `values`, `true`/`false` sem aspas, números sem
  aspas, textos entre aspas. Deixe `"synthetic": false` como está.
- O script `kit_script.pas` é opcional. Na sessão 1 a primeira chamada dele não existia no AD26. Faça o
  grupo K2 à mão (é rápido); se quiser testar o script, abra-o, compile e anote a linha recusada.
- Pode pular grupos (o K9 é o primeiro a pular); o que não for feito fica `skipped`, não falha.

| grupo | o que fazer | esperado |
|---|---|---|
| K1 (10 min) | abrir e salvar com Save As em `results/`: `flat.SchDoc`, `flat.PcbDoc`, `libs.SchLib`, `libs.PcbLib`, o projeto `flat.PrjPcb`, `flat/ascii/flat.SchDoc` (como `flat_ascii.SchDoc`), as quatro folhas de `tree` | arquivos salvos; **K1.8** = `false` (nenhum pedido de reparo, de upgrade nem erro) |
| K2 (8 min) | Project » Validate PCB Project em cada um dos 5 projetos; copiar as linhas do painel Messages para `results/<amostra>/messages.txt` (ou a linha `no messages`) | nenhuma linha de classe Error ou Fatal Error |
| K3 (8 min) | PCB nova no projeto `flat`, salva como `results/flat/eco.PcbDoc`; Design » Update PCB Document; validar, executar, salvar | **K3.2** = `0` mudanças inválidas |
| K4 (8 min) | `routed.PcbDoc`, Design » Rules; depois Tools » Design Rule Check com relatório, salvo como `results/routed/drc.html` | **K4.1** = `true` (as 5 regras da tabela do `STEPS.md`); **K4.3** = `1`; **K4.4** = `1` |
| K5 (10 min) | `board6.PcbDoc` salvo como `results/board6/board6.PcbDoc` (o documento **PCB**, não o esquemático); Layer Stack Manager; vias; keep-out; textos | **K5.2** = `6`; **K5.3** = `true`; **K5.4** = `true`; **K5.5** = `true` |
| K6 (4 min) | em `routed.PcbDoc`, Tools » Polygon Pours » Repour All; Save As `results/routed/routed.PcbDoc` | arquivo salvo |
| K7 (6 min) | abrir `routed.OutJob`; gerar `fab` e depois `doc`; nomes dos arquivos gerados, sem pastas, em `results/routed/outputs.txt` | **K7.1** = `true`; entre os nomes, arquivos Gerber de camada (agora com c0138) |
| K8 (5 min) | abrir `templates/iso5457_generic.SchDot` e salvar em `results/templates/`; ler o carimbo de `flat.SchDoc` | **K8.2** = `"Flat"`; **K8.3** = `"B"` |
| K9 (5 min) | `libs.SchDoc`, Tools » Update From Libraries (substituição completa), Save As `results/libs/libs.SchDoc` | **K9.2** = `0` |

**Passo extra do c0144 (o LED `D1`), 1 min, dentro do K3.1:** na placa `eco.PcbDoc`, clique nos dois pads
de `D1`. Esperado: pad 1 na rede `GND`, pad 2 na rede `LED_A`. E no esquemático de `flat`: a rede `GND` no
pino 2 (`K`) de `D1`.

Resposta K (grupos feitos, form.json preenchido sim/não, o que foi diferente): ______________________________

Resposta K-D1 (pads de `D1`): ______________________________

Em casa, na pasta do Fenolite: `uv run fenolite kit verify <pasta>/K-kit --json`, depois
`uv run fenolite kit record <pasta>/K-kit --out . --dry-run --json` e, se estiver certo, `--confirm`
(`docs/altium-kit.md`, "Recording a run"). Leia antes a lista `privacy` do resultado.

---

## 2. S: os cinco símbolos do c0134 (5 min)

Pasta `S-simbolos/`. Abra `simbolos.PrjPcb` e `simbolos.SchDoc` (só esquemático; as peças não têm
footprint, e o Altium pode avisar disso: ignore).

**S1.** Olhe os cinco símbolos (dê zoom). Esperado, em cada um, nenhum texto de pino sobre outro texto nem
sobre um traço:

- `Q1` `BJT_NPN`: a barra, as duas pernas inclinadas, a seta do emissor e os números 1, 2, 3, cada um ao
  lado da sua perna; nenhum nome de pino.
- `U1` `Comparator` e `U2` `Operational_Amplifier`: o triângulo com um traço de mais na entrada de cima e
  de menos na de baixo, nada no meio, os números 1 a 5 ao lado dos pinos (o 4 fica perto da borda inclinada
  de cima, sem tocar).
- `U3` `Linear_Regulator`: um quadrado com `IN` em cima à esquerda, `OUT` em cima à direita e `GND` girado
  embaixo no centro, longe um do outro; números 1, 2, 3 do lado de fora.
- `J1` `CONN2`: corpo vazio, os números 1 e 2 acima dos pinos.

Resposta S1 (`como esperado`, ou qual símbolo e o que se sobrepõe): ______________________________

---

## 3. O: output job com as configurações do Gerber (25 min)

Pasta `O-outjob/`. Na sessão 1 o job rodou, mas o Gerber não gerou nenhuma camada. Agora o job leva o
registro completo do Gerber (milímetros, casas decimais, camadas). Nenhum job pede o contorno da placa
(board outline): o passo O6 pergunta o que o Altium oferece para isso.

| pasta | o que é | camadas pedidas, em ordem |
|---|---|---|
| `blink_routed/` | 2 camadas de cobre, 4 decimais | Top Overlay, Top Paste, Top Solder, Top Layer, Bottom Layer, Bottom Solder, Bottom Paste, Bottom Overlay, Mechanical 13, 14, 15, 16 (12) |
| `board6/` | 6 camadas de cobre, a terceira um plano interno em GND | Top Overlay, Top Paste, Top Solder, Top Layer, Mid-Layer 1, Internal Plane 1, Mid-Layer 3, Mid-Layer 4, Bottom Layer, Bottom Solder, Bottom Paste, Bottom Overlay, Mechanical 13 a 16 (16) |
| `blink_routed_p6/` | igual a `blink_routed/`, feito com o preset `precision6.toml` (6 decimais) | as mesmas 12 |

**O1** (`blink_routed/`): abra `blink_routed.PrjPcb`, depois `blink_routed.OutJob`. Esperado: nenhuma mensagem.

Resposta O1: ______________________________

**O3** (`blink_routed/`): gere o container `fab`, depois o `doc`. Esperado: nenhum erro; arquivos de camada
Gerber desta vez, além de furação, pick and place, lista de materiais e o PDF.

Resposta O3 (extensões dos arquivos da pasta do Gerber, em lista; o relatório do Gerber cita camadas?; os
outros cinco tipos aparecem?): ______________________________

**O5** (`blink_routed/`): abra a configuração da saída Gerber (duplo clique, ou botão direito » Configure).
Esperado: milímetros, 4 decimais, as 12 camadas da tabela com a plotagem ligada.

Resposta O5 (unidade, decimais, camadas ligadas, ou `como esperado`): ______________________________

**O6** (`blink_routed/`): na mesma configuração, procure o contorno da placa na lista de camadas (a
documentação diz que é a primeira entrada). Diga se existe, o nome e se está ligado. Se existir, ligue,
OK, salve o job **com outro nome** na mesma pasta, gere `fab` de novo. Deixe o job salvo na pasta.

Resposta O6 (existe?, nome, ligado?, gerou arquivo de contorno? extensão): ______________________________

**O7** (`board6/`): abra `board6.PrjPcb` e `board6.OutJob`, gere `fab`. Esperado: um arquivo de camada
para cada uma das 16 camadas pedidas, um deles o plano interno.

Resposta O7 (extensões; algum é o plano interno?): ______________________________

**O8** (`blink_routed_p6/`): abra `blink_routed.PrjPcb` e o job, leia unidade e decimais na configuração do
Gerber, gere `fab`. Esperado: milímetros e 6 decimais (se o Altium trocou o valor, isso é um resultado,
não uma falha).

Resposta O8 (o que a configuração mostra; os arquivos aparecem?): ______________________________

**O-S1** (sem abrir nada): confirme numa frase a sessão 1, com a versão menor: "o Gerber do job antigo não
gerou nenhum arquivo de camada" (ou o que aconteceu). Isso fecha uma linha sem nova corrida.

Resposta O-S1: ______________________________

---

## 4. X8: corpos dos componentes (20 min)

Pasta `X8-bodies/`. Os mesmos arquivos em duas formas: `saved/` (35 chaves por corpo, a forma que a opção
escreve) e `short/` (só as 21 primeiras chaves; difere só no `body2.PcbDoc`). Valores esperados:

| corpo | footprint | lado | camada | altura total | altura do afastamento (standoff) | identificador |
|---|---|---|---|---|---|---|
| 1 | `U1` | Top | Mechanical 13 | 2.5 mm | 0 mm | (vazio) |
| 2 | `D1` | Bottom | Mechanical 14 | 1 mm | 0 mm | `LED` |
| 3 | `R1` | Top | Mechanical 13 | 4 mm | 0.5 mm | `STANDOFF` |

O modelo tem um quarto corpo, com modelo 3D, que o Fenolite não escreve: o documento tem três.

**X8.1** abra `saved/body2.PrjPcb` e `body2.PcbDoc`. Esperado: nenhum pedido de reparo, nenhuma mensagem.

Resposta X8.1: ______________________________

**X8.2** painel PCB no modo "3D Models" (ou selecione cada corpo em 2D). Esperado: três corpos, cada um do
footprint da tabela.

Resposta X8.2: ______________________________

**X8.3** nas propriedades de cada corpo: identificador, lado, camada, altura total, standoff. Esperado: a tabela.

Resposta X8.3: ______________________________

**X8.4** vista 3D. Esperado: três sólidos nas alturas da tabela; o corpo 2 abaixo da placa.

Resposta X8.4: ______________________________

**X8.5** repita X8.1 a X8.4 com `short/body2.PrjPcb` e `body2.PcbDoc`.

Resposta X8.5: ______________________________

**X8.6** salve `saved/body2.PcbDoc` com outro nome (por exemplo `saved/body2_salvo.PcbDoc`) e leve para casa.
Lá: `FENOLITE_ALTIUM_BODY2_SAVED=<esse arquivo> uv run pytest tests/unit/lens/test_altium_bodies.py -k
saved_report -s` imprime só contagens (é uma medida, não passa nem falha).

Resposta X8.6 (nome do arquivo salvo): ______________________________

**X8.7** abra `saved/body2.PcbLib`, footprint de `U1`, leia as alturas do corpo. Esperado: um corpo, 2.5 mm
de altura total, 0 mm de standoff.

Resposta X8.7: ______________________________

---

## 5. R: canais de uma instrução `Repeat` (30 min)

Pasta `R-repeated-sheet/`. Os mesmos bytes do exemplo do repositório (`tests/data/altium/channels/two/`),
agora escritos pelo gerador de esquemáticos com cor de fundo e cores (na sessão 1 a página ficou preta).
Folha de topo `two.SchDoc`: `U1`, `J1`, o símbolo de folha `Repeat(CH,1,2)` com as entradas `VCC` e
`Repeat(OUT)`, o barramento `OUT[1..2]` com os fios `OUT1` e `OUT2`. Folha filha `two_ch.SchDoc`: `R1` e
`C12`, as portas `VCC` e `OUT` encostadas nas pontas dos pinos (sem fio), o rótulo `MID`. Sem footprints:
no R3 o Altium vai avisar; o que importa são designadores e redes.

**R1** abra `two.PrjPcb`, olhe as duas folhas, compile. Esperado: fundo claro e objetos visíveis; nenhum
erro (uma mensagem de porta flutuante, "floating port", seria diferença: diga qual porta); o Navigator
mostra dois canais da folha filha, `CH1` e `CH2`.

Resposta R1: ______________________________

**R2** em Project Options » Multi-Channel, para cada formato de designador: selecione, compile, anote o
designador de `R1` nos dois canais. Depois, com `$Component_$RoomName`, o mesmo para cada um dos cinco
estilos de nome de room. Esperado no primeiro canal, estilo "Flat Numeric With Names", na ordem da lista:
`R1_CH1`, `CH1_R1`, `R1A`, `R1_CHA`, `R1_1`, `R1_CH1`, `R_1_1`, `R_CH1_1`. Estilos, com
`$Component_$RoomName`: `R1_CH1`, `R1_CHA`, `R1_CH1`, `R1_CHA` e, no estilo misto, o que o Altium mostrar.

Resposta R2: ______________________________

**R3** com `$Component_$RoomName` e o primeiro estilo, Design » Update PCB Document numa placa vazia.
Anote os designadores dos quatro componentes dos canais, as redes do pino 2 de `C12` e do pino 2 de `R1`
nos dois canais, e a forma do caminho de identificadores únicos de um componente de canal (só a forma:
onde fica o índice do canal e o que o separa, não os identificadores). Esperado: `R1_CH1`, `R1_CH2`,
`C12_CH1`, `C12_CH2`; `OUT1` e `OUT2`; `MID_CH1` e `MID_CH2`.

Resposta R3: ______________________________

**R4** Tools » Annotation » Annotate Compiled Sheets, renomeie o `R1` de um canal, salve. Envie só os nomes
das chaves do arquivo `.Annotation` que mudaram e os dois designadores. Não há valor esperado.

Resposta R4: ______________________________

---

## 6. V: vias sem pad nas camadas internas (15 min)

Pasta `V-vias/`. Placa de seis camadas de cobre, duas delas planos internos em `GND`: Top Layer,
Internal Plane 1, **Mid-Layer 2**, Internal Plane 2, **Mid-Layer 4**, Bottom Layer. As duas camadas
internas de sinal têm os ids 3 e 5, e posições 2 e 3 entre as camadas de sinal: o arquivo salvo diz qual
dos dois o Altium usa. Duas vias passantes de 0.6 mm (furo 0.3 mm):

- via **A** (rede `SIG`, em cima, entre `J1` e `J2`): trilhas só na Top Layer e na Bottom Layer;
- via **B** (rede `AUX`, embaixo, entre `J3` e `J4`): trilhas só na Top Layer e na Mid-Layer 4.

Não salve por cima de `vias.PcbDoc`: cada passo usa Save As com um nome novo, na mesma pasta.

**V1** abra `vias.PrjPcb` e `vias.PcbDoc`; abra o Layer Stack Manager. Esperado: nenhuma mensagem; as seis
camadas de cobre na ordem acima. Depois File » Save As `vias_0_antes.PcbDoc` sem mudar nada.

Resposta V1 (nomes das camadas como aparecem): ______________________________

**V2** rode a ferramenta de remover formas de pad não usadas (na documentação: "Remove Unused Pad Shapes",
no menu Tools; pode estar em outro lugar no AD26), só para vias, com a opção de manter as camadas de início
e fim **desligada**. Anote as opções da janela e como vieram. Esperado: a via A perde o pad na Mid-Layer 2
e na Mid-Layer 4; a via B perde na Mid-Layer 2 e na Bottom Layer. Save As `vias_1_removido.PcbDoc`.

Resposta V2 (opções da janela; de que camadas cada via perdeu o pad): ______________________________

**V3** restaure as formas de pad (a documentação diz que a ferramenta restaura), rode de novo com a opção
de manter início e fim **ligada**. Esperado: a via B mantém o pad na Bottom Layer; a via A como no V2.
Save As `vias_2_pontas.PcbDoc`.

Resposta V3: ______________________________

Leve os três arquivos `vias_*.PcbDoc` para casa: os bytes 209 a 240 do registro de cada via e os nove bytes
a mais do registro longo serão lidos com o Fenolite (c0132, tarefa 4.3).

---

## 7. D: o DRC do próprio Altium num documento público (opcional, 10 min)

O arquivo **não** vem no pacote. Baixe:

- URL: `https://raw.githubusercontent.com/TobiasRothlin/AltiumPCBLibrary/fdff76666ffbfa4a1ba2e3d3fe5a52c090b45cb7/PCBLibrary/PCB1.PcbDoc`
- commit: `fdff76666ffbfa4a1ba2e3d3fe5a52c090b45cb7` (licença Apache-2.0; linha `altium-third-party-pcbdoc-03` do corpus)
- SHA-256: `567fd0dfdba54c04adbdd2cc19b427c894b7a94aa953aa361f3e0afc71db12b3` (confira antes de abrir:
  `certutil -hashfile PCB1.PcbDoc SHA256` no Windows)

Abra só para ler: **não salve**. O Fenolite acha 7 violações de folga, todas entre o pad `J2-1` (quadrado,
passante, 1.62 mm, rede `NetJ2_1`) e sete segmentos da trilha da rede `Net*_4` (0.127 mm) na Bottom Layer,
com folga de 126 991 a 126 992 nm contra a regra `Clearance_2` de 5 mil (127 000 nm).

**D4** abra o documento, **não** refaça os polígonos, Tools » Design Rule Check só com as regras Clearance.

Resposta D4: ______________________________

**D5** uma linha: "o Altium mostra N violações da regra `Clearance_2` entre o pad `J2-1` e a rede `Net*_4`"
(N de 0 a 7).

Resposta D5: ______________________________

**D6** selecione o pad `J2-1`; tamanhos X e Y como o painel de propriedades mostra, em mil, com todos os
dígitos. (O Fenolite lê 63.7795 mil.)

Resposta D6: ______________________________

---

## Pergunta sem Altium (1 min)

**Q-c0144** O catálogo deve aplicar sozinho um mapa pino-pad para `LED`, `Diode` e `Zener_Diode` nos três
footprints conhecidos (ânodo no pad 2, cátodo no pad 1) quando a peça não dá `pad_map`? Opções: (a) mapa
padrão; (b) só um aviso no build, nomeando o mapa a escrever (a recomendação); (c) nada.

Resposta Q-c0144: ______________________________

## Ao terminar

Compacte a pasta `session-2` inteira, como ficou (com o que o Altium gravou), e leve para casa. Não
publique esse zip.

## Formulário de resposta (copie para a mensagem)

```
Versao e data: AD 26.? / 2026-10-08
K: grupos feitos=  ; form.json preenchido=  ; diferencas=
K-D1:
S1:
O1:
O3:
O5:
O6:
O7:
O8:
O-S1:
X8.1:
X8.2:
X8.3:
X8.4:
X8.5:
X8.6:
X8.7:
R1:
R2:
R3:
R4:
V1:
V2:
V3:
D4:
D5:
D6:
Q-c0144:
```

## SHA-256 de cada arquivo do pacote

Gerado depois de tudo; não inclui este arquivo nem `SHA256SUMS.txt`, que tem a mesma lista para conferir
com `sha256sum -c SHA256SUMS.txt` (na pasta `session-2`).

```
b2f16165f361b5f08824871ed1185f86123c0e436a258da4446bc03bbb9a5c80  COMO-FOI-GERADO.md
0b6467aa90fce5002b746d6f4e66800718a87424c2d70e69bfc58f8dee686c77  K-kit/STEPS.md
cffaa5da448480a99feba314a4e08a47a4f14dd27f016ad72ec5875c191a50e1  K-kit/board6/board6.OutJob
c92105d2c9f0b745151e83eca2e783fd30c729f6af1621cebac485e55dba118b  K-kit/board6/board6.PcbDoc
4a6e40784c51a52705a653ad7410b524790a98d38c16d2dde68fc6b5e2cbbbde  K-kit/board6/board6.PcbLib
914dc3d485a8d978d5da7d7f6116eedf4d1e1cad2646b05499baff7b59bc8a88  K-kit/board6/board6.PrjPcb
d1da22ae6e1e3c6af4379a65081597abf11782fecc1320026412521a11205915  K-kit/board6/board6.SchDoc
b1b5ec08350ce0722e4b230e769fb33bdd51e19aef1c8dcd691dbca3dabe635b  K-kit/board6/board6.SchLib
223d81cddd80aa7ba92cae850ce6960a7c978df38e89b6a3949eed037fdf2f84  K-kit/flat/ascii/flat.SchDoc
bc50bf17eeee8468ef64cc0b1e8cc3e432d304783a22615444a5736170d024ef  K-kit/flat/flat.OutJob
afe2c1d88355f2cc7d01a72f3b068c423da753b053fd4e264bca6925323b4b87  K-kit/flat/flat.PcbDoc
915a7bda444af16a5ba320e58090c14f2b1585fc85f507ba441548f479181f63  K-kit/flat/flat.PcbLib
bd813f7dce782d70c0257a43f66a26522910e85baa75e14a989cf7016cae911c  K-kit/flat/flat.PrjPcb
61621bd0df59b6fdb6a78110c1e8c82a7d65bf7506c935654ba250141dfa62e8  K-kit/flat/flat.SchDoc
4dc74d175fc8d657b721f934f259af9ea8ea00fd6d09f26e16aeacc8e3b075f7  K-kit/flat/flat.SchLib
8600c44ad78f79beb1c94a0b3036b2778b7f73179b642190affcece0db94727a  K-kit/kit.json
685ab54f38e643789f2f3abb87d9a590854957d685c42a5067eec8375e26d197  K-kit/kit_script.pas
ae63cff1abc233662b18f9a16715d3fde9bf474381a93fe14d58d9d3a2b8617a  K-kit/libs/libs.OutJob
a7218f03522a6039d8da3aa871cb960d7265fb2a5737077840ae7c4f93ba8c97  K-kit/libs/libs.PcbDoc
8be5fe6fdf43941dccabbcf749de1fb1707a4234d16cf41820199061a32b6ea5  K-kit/libs/libs.PcbLib
d46c93b5982d70173f18ae94863cee275d9f6e580f40fbfa7583916e6bfb209e  K-kit/libs/libs.PrjPcb
e45aaacef8fb058c29c7924207e82eda6649e96045f122aaab59162f74ceeade  K-kit/libs/libs.SchDoc
ad07d14d835901d6ac896d5536a318fc9d76f08ee2826fd708ebe7d64cf38799  K-kit/libs/libs.SchLib
153b929d1adecaa755c445fde2f790411b46e5bf5bcf6de7976cfec5e53c266e  K-kit/results/board6/expected.txt
c1506946369b5e0bbcd5ff259809a9a20faeac2701877d492b27f74b1424e4b4  K-kit/results/flat/expected.txt
eba6886caecc67274fffd74392ff20e22a69d876c1f43d8285392007ea24233f  K-kit/results/form.json
309075515492359e3a11e210f99147b9507b528c18cfbac247c1bb457929ee4e  K-kit/results/libs/expected.txt
708c0f5fd07bfd4c491cb785ca4bbc942323495305096b1f9c3158a2a0e55564  K-kit/results/routed/expected.txt
1d3c5462dfe6313b626fb7daac56a54da762ed6cd8a8155e0d072a7d99d67095  K-kit/results/templates/expected.txt
141f11c332efe7db4380cf194192c14c48207c310c99e4ba45a4a1a4bf36ba2e  K-kit/results/tree/expected.txt
8485443bdab65e9e1f601306ae534612479eeace34a7b43bac3d18a8fec9e105  K-kit/routed/routed.OutJob
1667a11afaef4705ede9a4d5a50d1806366848baf82cbcb6e528497d43fce375  K-kit/routed/routed.PcbDoc
1374b3a043a9102f0baa32c00c8c8ffd4b571d1c9d78bc4de99401f47f69d23d  K-kit/routed/routed.PcbLib
679f5e8755d29ebb0f3304e8c40cf2df3ccfb88e4484aea512bb5ecdba94624c  K-kit/routed/routed.PrjPcb
e5a21ed8e1db91e489b21d1b63d897e051d8a5d830ca2c3e655f645b8bcaf0ee  K-kit/routed/routed.SchDoc
49f4359baa386865872328c5a1b4151ec46dedda9b97d6b09bf58a08681be82e  K-kit/routed/routed.SchLib
2e91c3a6a142146a32c898f14e7cd3a05dc56c2b8782a6095bfad455138b94fb  K-kit/templates/iso5457_generic.SchDot
5f82374c7c3c16dac370815a2bc520bb026e0e30ccd55cd6b528353ec0f0ebb0  K-kit/tree/tree.PrjPcb
3680dbc37c00689a9abeddd27d019eab39129c688f4614a0629b68076bbee6c1  K-kit/tree/tree.SchDoc
92b40a49dc04ec9bba0b91eb00f9070a6066469c6b6f2dbc54f90519308e77d8  K-kit/tree/tree.SchLib
d1c8c94aa624e99aa233cd687bdf48ac2338cf0d1be6008ba834cf8921cf05d5  K-kit/tree/tree_io.SchDoc
8f197da032e893e509e0c3c88a63b33e0b3da965507dbcd00d3d0790aabe04ca  K-kit/tree/tree_io.leds.SchDoc
d0807006fc48f66067a414eeb70eeeaf7f7a499cb4f861cbca328dd7fe56c024  K-kit/tree/tree_power.SchDoc
595be494ec0a3ce8edc084cd041d86b2fe4bab9cd94f05b5a7e557864f44f950  O-outjob/blink_routed/blink_routed.OutJob
6691042bc82ef6250d4944f6b08ab8be16b8aeb83d39f0c6975d42cfc332333a  O-outjob/blink_routed/blink_routed.PcbDoc
640bbcdb207a1dd724d310963f135101f6fb7525b5b59d22516a23ecaa4955ce  O-outjob/blink_routed/blink_routed.PcbLib
99bcc6d91837bf0c0f55876e5be11ae444eca9c11c10bf8c6dbf56c110a8093d  O-outjob/blink_routed/blink_routed.PrjPcb
50a062c3ae03c6dec28e803f42c01d18c1e7c7c39cb439c640135611e4065c14  O-outjob/blink_routed/blink_routed.SchDoc
44e8f59b353162278a631fa533f02197e4df3f40d88de8831cc3f111abe12e22  O-outjob/blink_routed/blink_routed.SchLib
bb3e5505a4bc91c07dd894c984e2a8710cd7d485be89de84ced996637236d5e5  O-outjob/blink_routed_p6/blink_routed.OutJob
6691042bc82ef6250d4944f6b08ab8be16b8aeb83d39f0c6975d42cfc332333a  O-outjob/blink_routed_p6/blink_routed.PcbDoc
640bbcdb207a1dd724d310963f135101f6fb7525b5b59d22516a23ecaa4955ce  O-outjob/blink_routed_p6/blink_routed.PcbLib
99bcc6d91837bf0c0f55876e5be11ae444eca9c11c10bf8c6dbf56c110a8093d  O-outjob/blink_routed_p6/blink_routed.PrjPcb
50a062c3ae03c6dec28e803f42c01d18c1e7c7c39cb439c640135611e4065c14  O-outjob/blink_routed_p6/blink_routed.SchDoc
44e8f59b353162278a631fa533f02197e4df3f40d88de8831cc3f111abe12e22  O-outjob/blink_routed_p6/blink_routed.SchLib
cffaa5da448480a99feba314a4e08a47a4f14dd27f016ad72ec5875c191a50e1  O-outjob/board6/board6.OutJob
c92105d2c9f0b745151e83eca2e783fd30c729f6af1621cebac485e55dba118b  O-outjob/board6/board6.PcbDoc
4a6e40784c51a52705a653ad7410b524790a98d38c16d2dde68fc6b5e2cbbbde  O-outjob/board6/board6.PcbLib
914dc3d485a8d978d5da7d7f6116eedf4d1e1cad2646b05499baff7b59bc8a88  O-outjob/board6/board6.PrjPcb
d1da22ae6e1e3c6af4379a65081597abf11782fecc1320026412521a11205915  O-outjob/board6/board6.SchDoc
b1b5ec08350ce0722e4b230e769fb33bdd51e19aef1c8dcd691dbca3dabe635b  O-outjob/board6/board6.SchLib
5ca224ec34844a59e21b30f2f7285adf2fc32712da85063995f21e11ca34926c  O-outjob/precision6.toml
38384a5c609a963bd3c072d9b95deea42bb137565b2664ae28bb6ddfc16c6737  R-repeated-sheet/two.PrjPcb
e07048f42c930a5d1ac6d326aae2331c5b96f2da1e26d958ea09eea5a6d24112  R-repeated-sheet/two.SchDoc
3bd678fdf0ef16ee9a7bcba23ba6113353244a3a8533d982f093a42526892724  R-repeated-sheet/two_ch.SchDoc
2e64aa1653167d6053ffc9bece294e7bfafffa412f4ed12b69f2fddaa2ba5d12  S-simbolos/simbolos.PrjPcb
096af8c3ded27aa3ee2d5945acf55d2224d798963327771532141e5fafdf04cf  S-simbolos/simbolos.SchDoc
b95b11e676eee6699a433009647710e4abe466b455b9f9619964c4e7097bd57c  S-simbolos/simbolos.SchLib
45eb3274f419406f89cad3b9048ab8dcf6693730e88ffa4a803ca42fb5c0ead3  V-vias/vias.OutJob
a96f07f53e7e8f062fa85c747b7ce977cf573df03bcda6927e831769fa344daa  V-vias/vias.PcbDoc
367bfe5b2b9e5d23e4abdc47157075537ebb0e43cc8f2fd5433b7e92fe8eda86  V-vias/vias.PcbLib
f1e65236ea39e65ce0d4be5286e241424c7abf25b733ffe8a42d55809deaf527  V-vias/vias.PrjPcb
e7e1f9c9d57a6bd0f4737983582a2202ee330c3575c6caac1bc05c326123b57e  V-vias/vias.SchDoc
465af019c5a8ade3b0ca67cadd1638f0177b5195a507bf23ec0ea9b9cccf5aa2  V-vias/vias.SchLib
bee5811bc7a1b43c589722a5b95d1bf1a784aa78f38a5abad8e035156fded2f2  X8-bodies/saved/body2.PcbDoc
9432b8ab5f7801c7c9399a9e943dd272d4b02d2fbfa0586cc34c53e3666b991d  X8-bodies/saved/body2.PcbLib
e0b2cca3f3635c5ec50edca85d6dbae0d527a03d3e94447945e874a607769591  X8-bodies/saved/body2.PrjPcb
cfea41d60f7c34fe5ee9ee620ea25acee8d130ac0d2c1dccc2b26ecc030629ab  X8-bodies/saved/body2.SchDoc
53cc1b8f2b0bd2f79bf51f7d4b3e6c011f296ac77e13b39c1669f5dbfc500b07  X8-bodies/saved/body2.SchLib
6becb1923051aa3b312cc97eaf8230fab0a50b30d7187253c55411ebe3e8175f  X8-bodies/short/body2.PcbDoc
9432b8ab5f7801c7c9399a9e943dd272d4b02d2fbfa0586cc34c53e3666b991d  X8-bodies/short/body2.PcbLib
e0b2cca3f3635c5ec50edca85d6dbae0d527a03d3e94447945e874a607769591  X8-bodies/short/body2.PrjPcb
cfea41d60f7c34fe5ee9ee620ea25acee8d130ac0d2c1dccc2b26ecc030629ab  X8-bodies/short/body2.SchDoc
53cc1b8f2b0bd2f79bf51f7d4b3e6c011f296ac77e13b39c1669f5dbfc500b07  X8-bodies/short/body2.SchLib
b0e0575f4ec0c176b48deb303087a070f01ca488a4b11277d0063dcefee9742b  _gerador/gerar.sh
9392dd19a5cdab2efa6bfdb7c1c1ec49a5926e370a8859fa72a8a96ab45807c3  _gerador/simbolos/FenoliteDemo.kicad_sym
f1d05563089e174f3718a255facf71e616edf6d4eff312eb52c55f48ddc08cb7  _gerador/simbolos/simbolos.py
9c41716b8c594d84ae662d0aeed6a0636cdef45ce9a7663bf785703032708e80  _gerador/simbolos/sym-lib-table
46f2b32345c509a75058574e865639f93405fc3dd46d510df99ccaf67fda1ab3  _gerador/vias/construir.py
cb47c95f11d816275c03f8b7919ef5afb599483599058ddf35018dadc10a6427  _gerador/vias/vias.py
```
