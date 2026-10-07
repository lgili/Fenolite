# Parte R: canais de uma instrução `Repeat` (Fenolite, mudanças c0083 e c0146)

Um projeto de dois canais para o Altium Designer 26: uma folha de topo com um símbolo de folha
`Repeat(CH,1,2)` e a folha filha que ele repete. Estes arquivos substituem os da pasta antiga
`c0083-part-r`, cuja folha apareceu como uma página toda preta. A causa provável, ainda não confirmada:
aquelas folhas não tinham cor de fundo nem cor nos objetos. As folhas novas são escritas pelo próprio
gerador de esquemáticos do Fenolite, com a cor de fundo, as cores, os corpos dos componentes e os pinos de
uma folha comum.

Os passos foram escritos a partir da documentação da Altium e podem aparecer de forma diferente na
versão 26 (um caminho de menu ou o nome de uma janela pode ser outro). Nada destes arquivos foi aberto no
Altium antes.

## O que abrir

1. `two.PrjPcb` (o projeto).
2. `two.SchDoc` (a folha de topo): os componentes `U1` e `J1`, o símbolo de folha `Repeat(CH,1,2)` com as
   entradas `VCC` e `Repeat(OUT)`, e o barramento `OUT[1..2]` com os fios `OUT1` e `OUT2`.
3. `two_ch.SchDoc` (a folha filha): `R1` e `C12`, as portas `VCC` e `OUT` encostadas diretamente nas pontas
   dos pinos (sem fio), e o rótulo de rede `MID`.

Os componentes não têm footprint. No passo R3 o Altium vai avisar disso; o que interessa são os
designadores e os nomes das redes que ele lista.

## Passos, resposta esperada e linha para preencher

Para cada passo escreva `como esperado`, ou em uma frase o que foi diferente.

**Versão do Altium (`AD <maior>.<menor>`) e data:** ______________________________

### R1: abrir e compilar

Abra `two.PrjPcb`, olhe as duas folhas e compile o projeto.

Esperado: as duas folhas aparecem com fundo claro e os objetos visíveis (não uma página preta); nenhum
erro na compilação (uma mensagem sobre porta flutuante, "floating port", seria uma diferença: diga qual
porta); o painel Navigator mostra dois canais da folha filha, `CH1` e `CH2`.

Resposta R1: ____________________________________________________________

### R2: formatos de designador

Em Project Options » Multi-Channel, para cada formato de designador da lista: selecione, compile e anote
o designador do componente `R1` nos dois canais. Depois, com o formato `$Component_$RoomName`, faça o
mesmo para cada um dos cinco estilos de nome de room.

Esperado no primeiro canal, com o estilo "Flat Numeric With Names", na ordem da lista de formatos:
`R1_CH1`, `CH1_R1`, `R1A`, `R1_CHA`, `R1_1`, `R1_CH1`, `R_1_1`, `R_CH1_1`. Para os estilos, com
`$Component_$RoomName`: `R1_CH1`, `R1_CHA`, `R1_CH1`, `R1_CHA` e, no estilo misto, o que o Altium mostrar
(o Fenolite não dá nome para esse caso).

Resposta R2: ____________________________________________________________

### R3: atualizar a placa

Com o formato `$Component_$RoomName` e o primeiro estilo, rode Design » Update PCB Document em uma placa
vazia. Anote: os designadores dos quatro componentes dos canais; os nomes das redes do pino 2 de `C12` nos
dois canais e do pino 2 de `R1` nos dois canais; e a forma do caminho de identificadores únicos de um
componente de canal, como as propriedades dele mostram (só a forma: onde fica o índice do canal e o que o
separa dos identificadores, não os identificadores).

Esperado: `R1_CH1`, `R1_CH2`, `C12_CH1`, `C12_CH2`; `OUT1` e `OUT2`; `MID_CH1` e `MID_CH2`.

Resposta R3: ____________________________________________________________

### R4: anotação

Rode Tools » Annotation » Annotate Compiled Sheets, renomeie o `R1` de um dos canais e salve. Envie só os
nomes das chaves do arquivo `.Annotation` que mudaram e os dois designadores.

Esperado: não há valor esperado; este passo é o que permite escrever o leitor desse arquivo.

Resposta R4: ____________________________________________________________

## O que enviar

Só as respostas acima. Não envie nenhum arquivo que o Altium tenha gravado.

## SHA-256

- `two.PrjPcb`: `38384a5c609a963bd3c072d9b95deea42bb137565b2664ae28bb6ddfc16c6737`
- `two.SchDoc`: `e07048f42c930a5d1ac6d326aae2331c5b96f2da1e26d958ea09eea5a6d24112`
- `two_ch.SchDoc`: `3bd678fdf0ef16ee9a7bcba23ba6113353244a3a8533d982f093a42526892724`
