# Contributing · Contribuir

**English** — Bug reports, ideas and pull requests are welcome.

- **Bugs**: open an [issue](https://github.com/F100Pilot/RockForge/issues/new/choose) with the
  version (next to "RockForge" on the home page), what you did and what went wrong. For a song that
  crashes or misbehaves in Rocksmith, say whether the DLC Builder build of the same song works.
  Only attach a Guitar Pro file, a recording or a `.psarc` if you have the right to share it;
  otherwise describe it.
- **Code**: keep each change small and covered by tests. The layering rules, the constraints that
  have bitten before and the design of every feature are in [CLAUDE.md](CLAUDE.md); the test guide
  is [TESTING.md](TESTING.md). Before opening a pull request, run:
  ```bash
  pip install -e ".[dev,psarc]"
  ruff check src tests start_standalone.py build_exe.py
  mypy
  pytest
  npm ci && npm run lint
  ```
- **Two languages**: the app is in Portuguese and English. Every text a user can see and every
  server message ships in both (`web/i18n-en.js`, `tr(pt, en)` on the server;
  `tests/test_i18n.py` checks it), and so do the user guide and the CHANGELOG. Details in
  `.claude/skills/rockforge-i18n/SKILL.md`.
- **Third-party code**: if you copy a file or port code from another project, add it to
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) in the same change.
- **Security**: report vulnerabilities as described in [SECURITY.md](SECURITY.md).
- By contributing, you agree that your contribution is licensed under the [MIT licence](LICENSE).

**Português** — Relatos de erros, ideias e pull requests são bem-vindos.

- **Erros**: abre uma [issue](https://github.com/F100Pilot/RockForge/issues/new/choose) com a
  versão (ao lado de "RockForge" na página inicial), o que fizeste e o que correu mal. Para uma
  música que fecha o jogo ou se porta mal no Rocksmith, diz se a versão do DLC Builder da mesma
  música funciona. Só anexes um ficheiro Guitar Pro, uma gravação ou um `.psarc` se tiveres o
  direito de os partilhar; caso contrário, descreve-os.
- **Código**: alterações pequenas e com testes. As regras das camadas, as restrições que já
  custaram caro e o desenho de cada funcionalidade estão no [CLAUDE.md](CLAUDE.md); o guia dos
  testes é o [TESTING.md](TESTING.md). Antes de abrir um pull request, corre os comandos acima.
- **Duas línguas**: a aplicação está em português e em inglês. Todo o texto visível e as
  mensagens do servidor vão nas duas (`web/i18n-en.js`, `tr(pt, en)` no servidor; o
  `tests/test_i18n.py` verifica), e também o guia do utilizador e o CHANGELOG. Detalhes em
  `.claude/skills/rockforge-i18n/SKILL.md`.
- **Código de terceiros**: se copiares um ficheiro ou adaptares código de outro projeto,
  acrescenta-o ao [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) na mesma alteração.
- **Segurança**: vulnerabilidades, vê o [SECURITY.md](SECURITY.md).
- Ao contribuir, aceitas que a tua contribuição fica sob a [licença MIT](LICENSE).
