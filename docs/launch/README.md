# Launch kit — Fenolite 0.5

Prepared on 2026-10-26 from released tag `v0.5.0` (commit `3a0bfb7d`).
These are reviewable drafts and publication instructions, not a record that the settings or posts were published.

## Repository settings

**Description**

> PCB automation in Python for engineers and AI agents. Create, inspect and convert KiCad/Altium projects, with a browser viewer.

**Website**

`https://github.com/lgili/Fenolite/blob/main/docs/index.md`

**Topics**

`pcb`, `eda`, `kicad`, `altium`, `python`, `electronics`, `hardware-as-code`, `pcb-design`,
`cli`, `ai-agents`, `pcb-viewer`, `schematic`, `design-automation`, `open-source`

After this documentation has reached the default branch, the maintainer can apply the settings using:

```bash
gh repo edit lgili/Fenolite --description "PCB automation in Python for engineers and AI agents. Create, inspect and convert KiCad/Altium projects, with a browser viewer." --homepage "https://github.com/lgili/Fenolite/blob/main/docs/index.md" --add-topic pcb --add-topic eda --add-topic kicad --add-topic altium --add-topic python --add-topic electronics --add-topic hardware-as-code --add-topic pcb-design --add-topic cli --add-topic ai-agents --add-topic pcb-viewer --add-topic schematic --add-topic design-automation --add-topic open-source
```

Use About → Edit for a manual review of the final list. Additive CLI flags preserve any existing topics;
review the result rather than assuming the original empty state remains current.

## Visuals

- [Social preview](../media/social-card.png): 1280 × 640 PNG, below 1 MB.
- [Hero screenshot](../media/hero.png): authored routed Blink example, actual viewer.
- [Starter screenshot](../media/board.png): the quickstart after direct routing.
- [Schematic screenshot](../media/schematic.png): Altium-format authored Blink fixture.
- [Animation](../media/viewer-demo.gif): twenty seconds, four actual viewer states.
- [Sources and reproduction](../media/README.md).

For the repository link preview, upload `social-card.png` in GitHub Settings → Social preview.
GitHub recommends 1280 × 640 and a file below 1 MB:
[official instructions](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview).
Topics support discovery by subject:
[official instructions](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics).

## Release and package presentation

- The `v0.5.0` tag and PyPI 0.5.0 already exist. Preserve the tag, commit and published artifacts.
- Use [v0.5.md](v0.5.md) as the short user-facing release text, with images and the detailed release record linked.
- Check for an existing GitHub Release before creating one. If missing, draft one for the existing tag;
  preview rendered links and images, and publish only after review.
- Release-page relative links must be expanded to `https://github.com/lgili/Fenolite/blob/main/…`;
  use `https://raw.githubusercontent.com/lgili/Fenolite/main/docs/media/…` for embedded images.
- Publishing a GitHub Release triggers `release.yml`. Inspect that workflow first: 0.5.0 is already on
  PyPI, and the workflow uses `skip-existing`. Do not rebuild or replace that published version for a README change.
- Package description/documentation URL changes take effect in the next package release. The existing
  PyPI distribution's embedded README does not change when the repository README changes.
- Keep technical commits and history. Summarize user benefits in release notes instead of rewriting history.

## Announcement drafts

### English

> Fenolite 0.5 is out: PCB automation in Python, for engineers and AI agents.
>
> Create PCB projects from code, open KiCad and Altium files in a browser, highlight nets and navigate
> between board and schematic. Export a standalone HTML review page or convert projects with an explicit
> report of what changed or was lost.
>
> `python -m pip install fenolite`
>
> The first example uses built-in components and needs no KiCad or Altium installation. Altium writing
> and conversions are experimental; KiCad checks and fabrication exports use KiCad's CLI.
>
> Apache-2.0. We'd like feedback from engineers trying the starter or a public example:
> https://github.com/lgili/Fenolite

### Português

> Lançamos a Fenolite 0.5: automação de projetos de PCB em Python, para engenheiros e agentes de IA.
>
> Você pode criar projetos por código, abrir arquivos KiCad e Altium no navegador, destacar nets e
> navegar entre placa e esquemático. Também pode exportar uma página HTML para revisão e converter
> projetos com um relatório explícito das alterações e perdas.
>
> `python -m pip install fenolite`
>
> O primeiro exemplo usa componentes integrados e funciona sem instalar KiCad ou Altium. A escrita
> Altium e as conversões são experimentais; verificações KiCad e exportações de fabricação usam a CLI do KiCad.
>
> Licença Apache-2.0. Queremos ouvir engenheiros que experimentem o tutorial ou um exemplo público:
> https://github.com/lgili/Fenolite

## Validation

See [measured validation and outstanding publication](validation.md), including the published-package first-use check and the existing main CI diagnosis.

## Publication checklist

- [ ] Review local screenshots, animation, copy and the support table.
- [ ] Approve the code/documentation diff; commit with the maintainer's sign-off when authorized.
- [ ] Run the required CI on the exact published branch commit; review it before merge.
- [ ] Merge the approved presentation so links and images resolve on `main`.
- [ ] Apply the reviewed repository description, website, topics and social preview.
- [ ] Review or create the GitHub Release for the existing tag, retaining its original release content when updating.
- [ ] Try installation and the tutorial from a fresh environment using the published package.
- [ ] Select an appropriate community and check its current posting rules before announcing.
- [ ] Publish the approved announcement, with the demo and tutorial link; respond to feedback.

No social post, external message, GitHub setting or release is changed by generating this kit.
