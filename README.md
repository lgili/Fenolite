# Testes do mantenedor antes da release 0.5.0

Branch só com os kits; não tem código e não roda CI. Para baixar no outro PC:

```powershell
git clone --branch testes-altium --single-branch https://github.com/lgili/Fenolite.git fenolite-testes
```

(ou no GitHub: branch `testes-altium` » **Code » Download ZIP**). Descompacte cada zip numa pasta de
trabalho e siga o `README.md` de dentro dele. Os kits foram gerados do branch `release-0.5.0` em
2026-10-16/17. Nunca mande prints com dados do empregador nem projetos que não sejam estes.

| # | arquivo | o que é | change / task | o que me mandar |
|---|---|---|---|---|
| 1 | `01-part-S-slots.zip` | Part S, slots e cut-outs, passos S1–S8 | c0168 5.2 | versão do Altium, data, um resultado por passo; o `regions/slots-saved.PcbDoc` do S7 |
| 2 | `02-part-T/` | Part T, três projetos convertidos (você monta com o script), passos T1–T6 | c0160 5.3, c0166 2.1 | um resultado por passo e por projeto |
| 3 | `03-kit-K1-K9.zip` | kit de verificação (`STEPS.md`, K1–K9) na árvore da release | c0092 6.2 (`H-A-ACC-KIT`) | a pasta `results/` (ou a saída de `uv run fenolite kit verify <pasta>`) |
| 4 | `04-kicad-c0105.zip` | perfis de impedância salvos pelo KiCad 10.0.6 com a interface gráfica | c0105 1.4 | o `bench.kicad_pro` salvo |
| 5 | `05-draftsman-F0.zip` | Draftsman: 14 variações para salvar (F0.1–F0.14) | c0172 1.4 | a pasta inteira zipada, versão e data |
| 6 | `06-painel-Q1-Q6.zip` | painel: Embedded Board Array salvo (Q1–Q6) | c0173 2.4 | a pasta zipada sem `History` e `Project Outputs`, versão e data |

## Sem kit neste branch

7. **Pedidos restantes da c0166 (3.1 a 3.6)**, no pacote que você já tem no Windows
   (`build/finalize_manual_altium.py`):
   - 3.1 esquemático: pedidos A/B/L/N/H que o kit não cobriu;
   - 3.2 PCB: pedidos D/C, contagens do X8.6 e a medida do via longo;
   - 3.3 Repeat: R5 (R1–R4 já passaram em 2026-10-14);
   - 3.4 OutJob, template/borda, modo de hierarquia, exportação de regras;
   - 3.5 (opcional) DRC plantado e as duas matrizes de clearance;
   - 3.6 Viewer V2/N4/C5, se tiver acesso (senão me diga que não tem).
8. **Agente real (c0081 4.2 e 4.3):** rodar a tarefa `led-indicator` uma vez com o agente que você usa; me
   dizer o custo mostrado e se quer rodar as outras quatro tarefas do lote.
9. **Revisão (c0092 5.2):** ler o bloco "v0.3 acceptance" de `docs/roadmap.md` (no branch `release-0.5.0`);
   aprovado como está, ou o que mudar.

## Ordem sugerida

Os itens 5 (Draftsman F0) e 6 (painel Q1–Q6) destravam código que ainda falta escrever; comece por eles.
Depois 1, 2 e 3 no Altium, 4 no KiCad, e por fim 7 a 9.
