# Security · Segurança

**English** — Please do not report vulnerabilities in a public issue. Use GitHub's
[private vulnerability reporting](https://github.com/F100Pilot/RockForge/security/advisories/new),
with the steps to reproduce and the version affected (next to "RockForge" on the home page). Only
the latest release is supported.

RockForge is meant to run on your own computer: `start.bat` and the `.exe` listen on `127.0.0.1`
only, with no login. The Docker setup opens a network port and therefore requires
`ROCKFORGE_API_TOKEN`; read "Optional API authentication" in [CLAUDE.md](CLAUDE.md) and the Docker
section of the [technical documentation](docs/TECHNICAL.md) before exposing it to a network.

**Português** — Não relates vulnerabilidades numa issue pública. Usa o
[relato privado de vulnerabilidades](https://github.com/F100Pilot/RockForge/security/advisories/new)
do GitHub, com os passos para reproduzir e a versão afetada (ao lado de "RockForge" na página
inicial). Só a última versão publicada é suportada.

O RockForge foi feito para correr no teu computador: o `start.bat` e o `.exe` só escutam em
`127.0.0.1`, sem login. A configuração Docker abre uma porta na rede e por isso exige o
`ROCKFORGE_API_TOKEN`; lê "Optional API authentication" no [CLAUDE.md](CLAUDE.md) e a secção Docker
da [documentação técnica](docs/TECNICO.md) antes de a expor numa rede.
