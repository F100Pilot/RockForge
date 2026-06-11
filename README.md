# RockForge

Pipeline áudio → arranjos Rocksmith 2014 (CDLC), construído sobre investigação verificada e
**honesto quanto aos limites** da tecnologia atual.

## O que faz (e o que não promete)

| Etapa | Tecnologia | Confiança |
|---|---|---|
| Ingestão (upload; YouTube opcional) | FastAPI / yt-dlp | — (YouTube desativado por defeito: viola o ToS) |
| Normalização | ffmpeg (loudnorm, 44.1 kHz) | determinística |
| Stem de guitarra | Demucs `htdemucs_6s` (MIT) | "okay" segundo os próprios autores; sem SDR publicado |
| Lead vs. Rhythm | heurística própria | **EXPERIMENTAL — não existe método publicado** |
| Notas (pitch/onsets/bends) | Basic Pitch (Apache-2.0) | publicada; degrada com distorção |
| BPM/beats | librosa (ISC) | publicada; inferior a trackers neuronais (escolha por licença) |
| Compasso | assumido 4/4 | **não detetado** — elo mais fraco da literatura |
| Afinação | librosa cents + heurística drop-D | requer confirmação humana |
| Cordas/trastes | otimização de playability (DP própria) | determinística, testada |
| Técnicas | bend (medido), hammer-on/pull-off (regras) | parcial — ver relatório |
| XML Song2014 | gerador próprio (formato doc. na comunidade) | testado estruturalmente |
| PSARC | bundle para DLC Builder; PSARC só com Wwise | **Wwise é obrigatório para .wem** |

Leitura obrigatória: [`docs/RELATORIO-TECNICO.md`](docs/RELATORIO-TECNICO.md) (viabilidade,
arquitetura, riscos) e os relatórios de investigação com fontes em [`docs/research/`](docs/research/).

## Arquitetura

Clean Architecture: `domain/` (modelo musical puro) → `application/` (ports + use case do
pipeline) → `infrastructure/` (adapters: Demucs, Basic Pitch, librosa, ffmpeg, XML, packaging,
DB) → `interfaces/` (API FastAPI, worker Celery). Cada estágio ML é um Protocol substituível.

## Execução

```bash
docker compose up --build   # API em http://localhost:8000 (UI em /, OpenAPI em /docs)
```

Desenvolvimento:

```bash
pip install -e ".[dev]"        # núcleo + testes (sem ML)
pip install -e ".[dev,ml]"     # com Demucs/Basic Pitch/librosa
pytest && ruff check src tests && mypy
```

## Avisos legais

- Não existe declaração oficial da Ubisoft sobre CDLC; gerar CDLC a partir de gravações
  protegidas e distribuí-las é distribuição não autorizada. Use apenas com material próprio
  ou autorizado.
- A ingestão YouTube está desativada por defeito (`ROCKFORGE_ENABLE_YOUTUBE=false`) porque
  descarregar áudio viola o ToS do YouTube.
- O empacotamento final exige o Wwise (EULA Audiokinetic, não redistribuível): o RockForge
  entrega um bundle pronto a importar no [DLC Builder](https://github.com/iminashi/Rocksmith2014.NET).
