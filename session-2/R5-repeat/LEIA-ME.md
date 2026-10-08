# Verificação c0151: o barramento do `Repeat(OUT)` (Parte R, passo R5)

Altium Designer 26.5 (o mesmo da sessão 2). Tempo estimado: 10 a 15 minutos.

## O que mudou desde a sessão 2

Na sessão 2 (08/10/2026) o projeto `two.PrjPcb`:

1. só pôs `two_ch.SchDoc` debaixo de `two.SchDoc` depois de "Synchronize Sheet Entries and Ports"
   (antes: `Missing child-sheet in two_ch.SchDoc in Symbol Repeat(CH,1,2)`);
2. depois disso compilou os canais, mas deu `Net OUT1 has only one pin (Pin U1-1)`,
   `Net OUT2 has only one pin (Pin U1-2)` e o aviso
   `Wire Sheet Entry CH1-Repeat(OUT)(Passive) at 2200mil,6500mil placed on a bus`.

Agora há duas mudanças:

- **o rótulo `OUT[1..2]` do barramento** saiu de cima do ponto de conexão da sheet entry
  `Repeat(OUT)` (2200 mil, 6500 mil) e está 100 mil à direita, sobre o barramento, como os rótulos
  dos fios;
- **o `two.PrjPcb`** ganhou em `[Design]` as chaves de nomes de rede e de compilação que todos os
  projetos públicos do corpus têm (`AllowSheetEntryNetNames=1`, `ReorderDocumentsOnCompile=1` e mais
  cinco).

## As três pastas

| pasta | o que tem | serve para |
|---|---|---|
| `A-principal` | as duas mudanças (os arquivos do repositório) | o resultado esperado |
| `B-projeto-antigo` | o rótulo novo, o `two.PrjPcb` antigo | saber se o projeto é o que faz a folha filha entrar |
| `C-rotulo-antigo` | o `two.PrjPcb` novo, o `two.SchDoc` antigo (rótulo no ponto da entry) | saber se o rótulo é o que faz o barramento se dividir |

Confira os arquivos com `SHA256SUMS.txt` (no PowerShell: `Get-FileHash <arquivo>`).

## Passos (repita para A, depois B, depois C)

Use uma cópia nova de cada pasta. **Não rode "Synchronize Sheet Entries and Ports"** antes do passo 4.

1. Feche qualquer projeto aberto. Abra `two.PrjPcb` da pasta.
2. No painel Projects: `two_ch.SchDoc` aparece **debaixo** de `two.SchDoc`? (sim / não)
3. Project » Validate PCB Project (ou Compile PCB Project). No painel Messages, copie **todas** as
   mensagens (Ctrl+A, Ctrl+C no painel, e cole na resposta), ou anote pelo menos se aparece:
   - `Missing child-sheet …`
   - `Net OUT1 has only one pin …` / `Net OUT2 has only one pin …`
   - `… placed on a bus`
   - `Duplicate Net Names …`
4. **Só se a folha filha NÃO entrou no passo 2:** clique com o botão direito no sheet symbol
   `Repeat(CH,1,2)` » Sheet Symbol Actions » Synchronize Sheet Entries and Ports. **Não clique em
   nada que altere** (nem setas, nem "Add Ports"): só anote o que o diálogo lista à direita (pares já
   casados) e à esquerda (entries e portas sem par), e feche com **Cancel**. Depois compile de novo
   e copie as mensagens.
5. Só na pasta A, se compilou sem erro: no painel Navigator, a rede `OUT1` tem os pinos `U1-1` e
   `C12_CH1-2`? A rede `OUT2` tem `U1-2` e `C12_CH2-2`?

Não salve nada. Se o Altium pedir para salvar ao fechar, responda **não**.

## Resultado esperado

- **A:** a folha filha entra sozinha (passo 2: sim); nenhum `only one pin`, nenhum `placed on a
  bus`, nenhum `Missing child-sheet`; `OUT1` = `U1-1` + `C12_CH1-2`, `OUT2` = `U1-2` + `C12_CH2-2`.
- **B e C:** é o que não sabemos; por isso as pastas existem. Qualquer resultado serve.

## Resposta (copie e preencha)

```
Altium Designer 26.__ , data: __/__/2026

A-principal: filha debaixo do topo sem sincronizar? ___
  mensagens:
  (passo 4, se feito) diálogo lista à direita: ___ ; à esquerda: ___
  (passo 5) OUT1: ___ ; OUT2: ___

B-projeto-antigo: filha debaixo do topo sem sincronizar? ___
  mensagens:
  (passo 4, se feito) diálogo: ___

C-rotulo-antigo: filha debaixo do topo sem sincronizar? ___
  mensagens:
  (passo 4, se feito) diálogo: ___

Na sessão 2, o que você fez no diálogo de sincronização (casou Repeat(OUT) com OUT? clicou em
Add Ports? nada?): ___
```

A última pergunta é importante: se na sessão 2 o diálogo casou `Repeat(OUT)` com a porta `OUT`, o
Altium renomeia a porta para `Repeat(OUT)`, e isso sozinho explicaria os erros.

Nenhum arquivo salvo pelo Altium precisa voltar; só o texto da resposta.
