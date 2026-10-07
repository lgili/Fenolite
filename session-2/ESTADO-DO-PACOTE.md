# Sessão 2 no Altium: estado do pacote em 2026-10-08, 07:40

**Este pacote ainda NÃO está completo. Não use ainda para a sessão.** Falta montar o guia único
(`LEIA-ME.md`), reconstruir tudo a partir do `dev` final e gerar o zip. Esta nota diz o que já existe
aqui e o que falta.

## O que já existe nesta pasta

| pasta | o que é | construída de | estado |
|---|---|---|---|
| `O-outjob/` | output job com o registro de configuração do Gerber (c0138): três projetos (`blink_routed`, `board6`, `blink_routed_p6`) e um `README.md` em inglês | commit `4373dc17` (c0138, já no `dev`) | utilizável, mas será reconstruída: os esquemáticos mudam com c0134/c0144/c0146 |
| `X8-bodies/` | corpos extrudados de componentes (c0121), nas duas formas (`saved/` e `short/`), com `README.md` em inglês | commit do c0121 (já no `dev`) | utilizável; será reconstruída do `dev` final |
| `R-repeated-sheet/` | Parte R refeita com cores e corpos (c0146): `two.PrjPcb`, `two.SchDoc`, `two_ch.SchDoc`, `README.md` em português | commit `7f25ca8a` (c0146, ainda NÃO está no `dev`) | utilizável como está |
| `ViaTenting/` | tenting de vias (c0112) | ramo `v04` | **fica FORA da sessão 2**: pertence ao marco v0.4 |

## O que falta

1. **Guia único `LEIA-ME.md`** em português, com as partes em ordem de valor por minuto, os minutos de
   cada uma, a resposta esperada por passo, um formulário curto por parte e a lista de SHA-256.
2. **Reconstruir tudo do `dev` final**, depois que entrarem: c0146 (fontes e Parte R) e c0144 (os
   scripts do kit com o mapa de pads do LED). Até lá os esquemáticos das pastas acima são os antigos.
3. **Os cinco símbolos do c0134** para olhar (BJT_NPN, Comparator, Operational_Amplifier, CONN2,
   Linear_Regulator): ainda não há pasta.
4. **A placa das vias sem pad nas camadas internas** e a pergunta sobre o registro longo de via (c0132):
   ainda não há pasta.
5. **Parte D** (o DRC do próprio Altium sobre um documento público, passos D4 a D6): opcional e por
   último; o arquivo público NÃO vem no pacote: o guia dará URL, commit e SHA-256.
6. **O zip** do pacote.

## Para quem continuar este trabalho

- As regras e os textos dos passos estão no repositório: `docs/evidence/altium-pcb.md` (Partes X, U, D),
  `docs/evidence/altium-schematic.md` (Partes O, W, Y, R) e nos `design.md` das changes c0121, c0131,
  c0132, c0138 e c0146.
- A sessão 1 (`../session-1/`) não deve ser alterada.
- Nada do que o Altium gravar entra no repositório; só o registro do que foi observado.
