# RockForge — Relatório Técnico (Fases 2–5)

> Data: 2026-06-11. Este relatório baseia-se exclusivamente nos factos recolhidos em
> `docs/research/01-source-separation.md`, `docs/research/02-transcription.md` e
> `docs/research/03-rocksmith-cdlc.md`, onde cada afirmação tem fonte e nível de confiança.
> Convenções: **[FV]** facto verificado em fonte primária · **[INF]** inferência · **[NV]** não verificado.

---

## 1. Factos Confirmados

1. **Stem de guitarra em modelos abertos**: só o Demucs `htdemucs_6s` (MIT) produz um stem de
   guitarra "out of the box"; o repositório foi arquivado em 2025-01 e os autores classificam a
   qualidade do stem de guitarra como apenas "okay". Não existe SDR de guitarra publicado. **[FV]**
2. **Separação Lead vs. Rhythm**: não foi encontrada qualquer publicação académica
   (ISMIR/ICASSP/arXiv) que trate esta tarefa. O único produto que a anuncia é o serviço comercial
   Moises, sem métricas públicas. Não existe dataset público com etiquetas lead/rhythm. **[FV quanto
   à ausência de evidência]**
3. **Transcrição áudio→MIDI de guitarra**: Basic Pitch (Apache-2.0, ativo) é a ferramenta prática
   de referência; os modelos QMUL (ICASSP 2024 / GAPS ISMIR 2024) são o estado da arte no GuitarSet,
   mas focados em guitarra clássica e disponíveis como código de investigação. **[FV]**
4. **Áudio→tablatura (corda/traste)**: apenas código de investigação (TabCNN, FretNet, SynthTab,
   GOAT); a atribuição corda/traste é o gargalo e a generalização para guitarra elétrica/distorção
   é fraca. Não existe ferramenta de produção open-source. **[FV]**
5. **Técnicas**: bend, slide e harmónicos são detetáveis em notas isoladas (SpectroFusionNet 2025:
   99,1% controlado, 70,9% em áudio real); vibrato e pull-off têm F1 baixos; **nenhum** resultado
   publicado cobre misturas completas. **[FV]**
6. **Beat/BPM**: madmom e Beat This! lideram em precisão, mas os modelos do madmom são
   CC BY-NC-SA (não comercial) e o Essentia é AGPL; librosa (ISC) é a única opção totalmente
   permissiva. Deteção de compasso é o elo mais fraco. **[FV]**
7. **Empacotamento**: o RSToolkit clássico está em EOL (2021); o sucessor ativo é o
   DLC Builder / Rocksmith2014.NET (F#, MIT, release 2025-07), que faz XML→SNG→PSARC e DD via
   ML.NET. Existem implementações Python abertas de pack/unpack PSARC (0x0L/rocksmith, rs-utils,
   rsrtools). **[FV]**
8. **Wwise é obrigatório** para criar `.wem`: o DLC Builder exige Wwise 2019–2023 instalado
   (em Linux, via Wine). `ww2ogg` só faz o sentido inverso. Não foi encontrado codificador `.wem`
   open-source para criação. **[FV]**
9. **Formato XML de arranjo**: sem especificação oficial; documentado de facto em
   `Song2014.cs` (RSToolkit) e `Rocksmith2014.XML` (Rocksmith2014.NET): `ebeats`, `phrases`,
   `phraseIterations`, `sections`, `chordTemplates`, `levels` (notes/chords), `anchors`,
   `handShapes`; notas com `time`, `fret`, `bend`, `hammerOn`, `harmonic`, etc. **[FV]**
10. **Legal**: não existe declaração oficial da Ubisoft sobre CDLC (tolerância é inferência);
    distribuir CDLC com gravações protegidas é distribuição não autorizada; descarregar áudio do
    YouTube viola o ToS do YouTube, embora o yt-dlp em si seja distribuído legalmente. **[FV]**

## 2. Evidências

Ver os três relatórios em `docs/research/`, com URL e nível de confiança por afirmação, incluindo
a lista explícita do que **não** foi possível verificar (ex.: F-scores exatos do Basic Pitch no
GuitarSet, SDR de guitarra do BS-RoFormer, licenças de Beat This!/EOF/RSToolkit).

## 3. Limitações Conhecidas

- **Não existe método validado para separar Lead de Rhythm guitar.** Qualquer implementação será
  heurística e experimental (ex.: classificação por densidade polifónica, registo e contorno
  melódico por segmento). Não existe evidência suficiente para prometer precisão nesta etapa.
- A qualidade do stem de guitarra do `htdemucs_6s` é admitida pelos autores como apenas razoável;
  guitarras dobradas/multicamada permanecem no mesmo stem.
- A transcrição polifónica com distorção/efeitos degrada-se face aos benchmarks (treinados em
  guitarra acústica limpa — GuitarSet).
- Atribuição corda/traste a partir de áudio não é resolúvel com fiabilidade; a alternativa
  determinística é otimização de "playability" sobre o MIDI (MIDI→tab), abordagem validada pelo
  transformer QMUL **[FV quanto à abordagem; números NV]**.
- Deteção de compasso e de mudanças de tempo é o elo mais fraco da cadeia rítmica.
- Técnicas: apenas bend/slide/harmónicos têm evidência de detetabilidade, e só em notas isoladas;
  em misturas completas não há evidência suficiente.
- A criação de `.wem` não é automatizável sem instalar o Wwise (EULA Audiokinetic, sem
  redistribuição); em contentor Linux exigiria Wine + instalação manual do Wwise pelo utilizador.

## 4. Riscos Técnicos

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Stem de guitarra com bleeding/artefactos | Alta | Transcrição corrompida | Permitir upload de stem isolado; expor métrica de confiança; suportar checkpoints alternativos (BS-RoFormer/MVSep) |
| Separação lead/rhythm incorreta | Alta | Arranjos trocados/misturados | Marcar como experimental; UI de revisão humana; fallback "guitarra única" |
| Falsos positivos/negativos de notas | Alta em metal/distorção | CDLC injogável | Limiar de confiança configurável; edição manual via EOF (XML exportado é compatível) |
| BPM/compasso errado | Média | Grelha de ebeats desalinhada | Permitir BPM manual; tempo map por deteção de beats em vez de BPM fixo |
| Wwise indisponível | Certa em ambiente headless | PSARC final sem áudio válido | Saída em dois níveis: (a) pacote "pronto para DLC Builder" sempre; (b) PSARC final só quando Wwise/Wine configurado |
| Licenças (madmom NC, Essentia AGPL) | Certa se usadas | Inviabiliza uso comercial | Predefinição 100% permissiva (librosa ISC, Demucs MIT, Basic Pitch Apache-2.0); extras opcionais isolados |
| Conteúdo protegido (YouTube/CDLC) | Certa | Exposição legal do utilizador | Avisos explícitos; o serviço não redistribui áudio; ingestão YouTube desativável por configuração |

## 5. Viabilidade (resposta direta)

**É possível separar Lead e Rhythm guitar?** → **Parcialmente.**
É possível obter um stem de guitarra agregado (htdemucs_6s **[FV]**) e, sobre ele, aplicar
heurísticas de segmentação lead/rhythm — mas não existe método publicado nem dataset etiquetado,
pelo que não há base para prometer precisão. **Não existe evidência suficiente para concluir** que
uma separação lead/rhythm fiável seja alcançável com tecnologia aberta atual.

**Níveis de confiança esperados por género** — não existem benchmarks publicados por género para
esta cadeia completa; recusamos inventar percentagens. O que a evidência permite afirmar:
- *Músicas simples (guitarra única, limpa)*: cenário mais próximo do GuitarSet, onde os modelos
  reportam estado da arte **[FV; números exatos NV]** — viável com revisão humana ligeira.
- *Rock*: degradação esperada por distorção e mistura **[INF a partir de arXiv:2405.14679]**.
- *Metal*: pior caso — distorção alta, afinações baixas, riffs rápidos; sem benchmark publicado.
- *Guitarras dobradas/multicamada*: os dobros caem no mesmo stem; nenhuma tecnologia avaliada
  os separa. **[FV quanto à ausência]**

## 6. Arquitetura Recomendada

- **Backend: Python 3.11 + FastAPI.** Justificação: todo o ecossistema ML relevante (Demucs,
  Basic Pitch, librosa) é Python; FastAPI dá async nativo, OpenAPI e tipagem Pydantic. Django
  acrescenta peso (ORM/admin) sem benefício para um serviço de processamento; Node.js obrigaria a
  IPC com processos Python para todo o ML.
- **Processamento: PyTorch** (runtime do Demucs; Basic Pitch tem port PyTorch comunitário e o
  pacote oficial suporta inferência sem treino). ONNX Runtime fica como otimização futura de
  inferência; TensorFlow não é adotado como base.
- **Base de dados: PostgreSQL** em produção, **SQLite** em desenvolvimento/testes — via SQLAlchemy
  2.x, sem código específico de motor.
- **Fila: Celery + Redis** (broker e backend de resultados). Jobs de separação/transcrição duram
  minutos e não podem viver no ciclo HTTP. RabbitMQ é suportado pelo Celery se vier a ser preciso
  routing avançado; Redis cobre o caso atual com menos peças.
- **Empacotamento**: geração própria de XML de arranjo (formato Song2014) + projeto DLC Builder;
  PSARC final delegado ao DLC Builder/ferramentas comunitárias quando Wwise está disponível.
- **Padrões**: Clean Architecture (domain / application / infrastructure / interfaces), ports &
  adapters para cada estágio ML (substituíveis por checkpoints melhores sem tocar no domínio),
  tipagem forte (mypy strict), testes nas partes determinísticas.

## 7. Pipeline (Fase 4)

| # | Etapa | Input | Output | Dependências | Falhas possíveis | Mitigação |
|---|---|---|---|---|---|---|
| 1 | Ingestão | Upload (MP3/FLAC/WAV/OGG) ou URL YouTube | Ficheiro áudio bruto | FastAPI; yt-dlp (opcional, desativável) | Formato inválido; ToS YouTube | Validação de formato; flag de configuração para ingestão YouTube + aviso legal |
| 2 | Normalização | Áudio bruto | WAV 44.1 kHz estéreo, loudness normalizado | ffmpeg | Ficheiros corrompidos | Validação + erro tipado |
| 3 | Separação de stems | WAV | Stem de guitarra (+ resto) | Demucs `htdemucs_6s` (MIT) | Bleeding, artefactos | Adapter substituível; permitir upload direto de stem |
| 4 | Identificação de guitarras | Stem de guitarra | Segmentos com atividade de guitarra | librosa (energia/onsets) | Silêncio/bleeding confundido com guitarra | Limiares configuráveis |
| 5 | Lead vs. Rhythm (EXPERIMENTAL) | Stem + notas | Duas faixas candidatas | Heurística própria (densidade polifónica, registo, contorno) | Sem garantia — sem método publicado | Marcado experimental; fallback faixa única; revisão humana |
| 6 | Deteção de notas | Stem(s) | Eventos de nota (pitch, onset, duração, bends) | Basic Pitch (Apache-2.0) | Distorção degrada precisão | Limiares; troca por modelos QMUL via adapter |
| 7 | Cordas e trastes | Notas MIDI + afinação | Tablatura (corda, traste) | Otimizador próprio de playability (programação dinâmica) | Digitações implausíveis | Custo de transição afinável; testes determinísticos |
| 8 | Arranjos Rocksmith | Tab + tempo map + secções | Modelo de arranjo (lead/rhythm) | Domínio próprio | Notas fora de alcance (trastes >24, cordas) | Validação de domínio com erros explícitos |
| 9 | Geração XML | Arranjo | XML Song2014 válido | Gerador próprio (formato doc. em Song2014.cs) | Incompatibilidade de schema | Testes contra estrutura documentada; abrível no EOF |
| 10 | Empacotamento PSARC | XML + áudio + metadados | Projeto DLC Builder (sempre) / PSARC (se Wwise) | DLC Builder (MIT), Wwise (EULA) | Wwise ausente em headless | Saída de dois níveis, documentada |

Etapas transversais: BPM/beats/downbeats (librosa, ISC), afinação de referência
(`librosa.estimate_tuning` + heurística de nota mínima — deteção de drop tunings é **[NV]** e
fica marcada como necessitando validação), técnicas (apenas bend/slide via contornos de pitch do
Basic Pitch; hammer-on/pull-off inferidos por regras tempo/pitch marcados como heurísticos).

## 8. Análise de Precisão (Fase 5)

- **Realisticamente alcançável**: stem de guitarra agregado; transcrição de notas utilizável em
  material limpo/simples; tempo map por beat tracking; XML válido abrível no EOF/DLC Builder;
  digitação corda/traste plausível via otimização.
- **Experimental**: separação lead/rhythm; deteção de técnicas além de bend/slide; deteção de
  afinações drop/open; compasso automático.
- **Atualmente impossível com alta precisão**: separar guitarras dobradas/multicamada; transcrever
  metal denso sem erros; detetar palm mute em misturas; tablatura "ground truth" a partir de áudio.
- **Necessitará de intervenção humana**: revisão das notas (o XML gerado é editável no EOF),
  confirmação lead/rhythm, afinação, secções/frases para DD de qualidade, e o passo Wwise.

## 9. Plano de Implementação (Fase 6)

1. Núcleo de domínio tipado (notas, afinação, tempo map, arranjo) + testes.
2. Otimizador corda/traste (determinístico) + testes.
3. Gerador XML Song2014 + testes estruturais.
4. Adapters ML (Demucs, Basic Pitch, librosa) atrás de ports; imports tardios para arranque leve.
5. Orquestração do pipeline (use case) + Celery.
6. API REST FastAPI + persistência SQLAlchemy + UI web mínima.
7. Docker (api, worker, redis, postgres) + CI (lint, mypy, testes).
