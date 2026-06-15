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
| Letra automática (opcional) | WhisperX sobre o stem vocal (`pip install -e ".[lyrics]"`) | **EXPERIMENTAL** — gates anti-alucinação (RMS + confiança/palavra); LRC continua a via preferida |
| XML Song2014 | gerador próprio (formato doc. na comunidade) | testado estruturalmente; emite os 32 `arrangementProperties` e a estrutura COUNT/default/END que o DLC Builder e o jogo exigem |
| Áudio `.wem` | Wwise local + projeto template do DLC Builder | Vorbis **com seek table** + correção de header (sem isto o jogo carrega mas fica mudo e sai) — Wwise 2019/2021/2022/2023 |
| PSARC | bundle para DLC Builder; PSARC só com Wwise | **Wwise é obrigatório para .wem** |

## Via Guitar Pro (alta fidelidade — recomendada)

Em alternativa à separação/transcrição por ML, carrega um **GP3/GP4/GP5** + a gravação:
notas, trastes, técnicas (bend/HO/PO/palm mute/harmónicos/vibrato/slide), tempo, compassos e
secções vêm **exatos** do ficheiro. Inclui: seleção de pistas Lead/Rhythm, offset de
sincronização com a gravação, letra (ficheiro **LRC** ou **UltraStar TXT** — timing por
sílaba/linha sincronizado com a gravação — ou letra embutida no GP), e tones (tonebase + até 4
slots, com mudanças temporizadas). Fluxo na UI: "Inspecionar pistas" → escolher pistas/opções →
criar CDLC.

Limitações honestas: **GPX/GP6/GP7 não é suportado** (o PyGuitarPro lê GP3/GP4/GP5 —
exporta como GP5 no Guitar Pro/TuxGuitar); a sincronização é manual — indicas o segundo em
que a música começa na gravação e a partitura/letra são deslocadas para esse instante (a
gravação fica intacta, pois já tem o seu intro); há um lead-in mínimo de 2s para o count-in
do DLC Builder; pistas de baixo (4/5 cordas) ainda não são suportadas.

Para afinar a sincronização há uma **ferramenta de sincronização visual** no detalhe do job
(jobs GP): dá play à gravação, o cursor percorre as notas e ouves um *tique* em cada uma —
arrasta o "Início da música" até os tiques baterem certo com a música e carrega em "Aplicar e
reconstruir".

Se a tablatura e a gravação se vão **afastando ao longo da música** (o GP foi escrito num
andamento ligeiramente diferente do gravado), ajusta o **andamento (BPM)** no painel de
sincronização: estica/comprime a música toda de uma vez. As notas movem-se sobre a forma de
onda em tempo real para confirmares o alinhamento; depois "Aplicar e reconstruir". Isto corrige
a parte linear da deriva num só passo — faz isto **antes** das correções nota-a-nota abaixo.

Se a deriva (drift) entre a partitura e o áudio aumentar ao longo da música (em vez de um
offset constante), corrige nota a nota na tablatura: **arrasta uma nota** horizontalmente para
o instante onde ela deveria tocar — fica um ponto de correção, e as notas entre pontos
consecutivos são esticadas/comprimidas proporcionalmente. Para corrigir um trecho inteiro de
uma vez, ativa "Selecionar excerto", arrasta uma caixa sobre as notas desse trecho e depois
arrasta uma delas — o excerto move-se em bloco. As notas ficam na posição corrigida no
visualizador (com grelha temporal a cada 0.25s para ajuste fino) para testares com o áudio
antes de gravares. Cada "Aplicar correções e reconstruir" soma uma nova ronda de correções às
anteriores — **abre o job mais tarde (mesmo depois de saíres e voltares) e continua a
ajustar**: as correções já aplicadas ficam no arranjo carregado e as novas somam-se a elas, em
vez de partir sempre do GP em bruto.

Leitura obrigatória: [`docs/RELATORIO-TECNICO.md`](docs/RELATORIO-TECNICO.md) (viabilidade,
arquitetura, riscos) e os relatórios de investigação com fontes em [`docs/research/`](docs/research/).

## Arquitetura

Clean Architecture: `domain/` (modelo musical puro) → `application/` (ports + use case do
pipeline) → `infrastructure/` (adapters: Demucs, Basic Pitch, librosa, ffmpeg, XML, packaging,
DB) → `interfaces/` (API FastAPI, worker Celery). Cada estágio ML é um Protocol substituível.
Para contribuir, ver [`CLAUDE.md`](CLAUDE.md) (camadas, comandos e restrições que já custaram caro).

## Execução

### Instalação num PC novo (Windows, sem Docker — recomendado)

**1. Pré-requisitos**

| Software | Como instalar | Para quê |
|---|---|---|
| Git | https://git-scm.com/download/win | clonar o repositório |
| Python **3.11** (exatamente — 3.12+ não funciona: o TensorFlow exigido pelo Basic Pitch só tem wheels até 3.11) | https://www.python.org/downloads/ — ⚠️ marca **"Add Python to PATH"** | correr a app |
| ffmpeg | `winget install ffmpeg` | normalização de áudio |
| Redis | [Memurai](https://www.memurai.com/) (Developer, grátis; corre como serviço) | fila de jobs |
| Wwise (opcional) | Audiokinetic Launcher | gerar `.wem` automaticamente |
| DLC Builder (opcional) | [releases](https://github.com/iminashi/Rocksmith2014.NET/releases) | empacotar o PSARC final |

**2. Clonar e instalar** (o repo é privado — o Git pede login GitHub na primeira vez)

```cmd
cd C:\onde\quiseres
git clone https://github.com/F100Pilot/RockForge.git
cd RockForge
py -3.11 -m pip install -e ".[dev,ml]"
```

`py -3.11` escolhe explicitamente o Python 3.11 mesmo que outra versão seja a
predefinida; o `start.bat` deteta o 3.11 automaticamente. (Se só tens o 3.11,
`pip install -e ".[dev,ml]"` também serve.)

O install demora (PyTorch/Demucs/Basic Pitch, vários GB). Para a transcrição
automática de letra (opcional): `pip install -e ".[lyrics]"`.

**3. Arrancar**

```cmd
.\start.bat
```

Abre **http://localhost:8000**. O `start.bat` lança Redis + worker em segundo
plano (logs em `logs\`) e a API na janela atual; Ctrl+C para tudo.

Notas:
- O primeiro job descarrega os modelos ML (~2 GB extra, só uma vez)
- Os bundles gerados vão para `C:\Users\<utilizador>\Downloads\RockForge`
- Na lista de **Jobs** cada linha tem um botão 🗑 para remover o job (apaga
  também o bundle gerado e o ficheiro carregado, se nenhum outro job o usar);
  jobs em execução têm de terminar primeiro
- Para updates: `git pull` dentro da pasta (e `pip install -e ".[dev,ml]"` se
  o `pyproject.toml` tiver mudado)

### Via Docker (alternativa)

```bash
docker compose up --build   # API em http://localhost:8000 (UI em /, OpenAPI em /docs)
```

Nota: dentro do Docker o Wwise não está disponível — o `.wem` só é gerado na
execução nativa Windows com o Wwise instalado.

Desenvolvimento:

```bash
pip install -e ".[dev]"        # núcleo + testes (sem ML)
pip install -e ".[dev,ml]"     # com Demucs/Basic Pitch/librosa
pytest && ruff check src tests && mypy
```

## Como testar a app (fim-a-fim)

1. **Testes automáticos** (sem ML, rápidos): `pip install -e ".[dev]" && pytest` — 81 testes
   cobrem domínio, mapeamento corda/traste, XML/acordes, pipeline, API (incl. remoção de jobs),
   import GP, letra, tags e Wwise (consola simulada).
2. **Arrancar a stack**: `docker compose up --build`. Abre `http://localhost:8000`.
   O primeiro job descarrega os modelos (Demucs ~2 GB); em CPU, uma música de 4 min
   demora vários minutos na etapa `separate`.
3. **Smoke test honesto**: começa com uma gravação **tua, simples e limpa** (guitarra única,
   pouca distorção) em FLAC/WAV — é o cenário onde a transcrição tem evidência de funcionar.
   Acompanha a barra de etapas; no fim, revê a tablatura no visualizador, corrige a afinação
   se necessário e usa "Reconstruir".
4. **Validar o XML**: descarrega o bundle e abre os `arrangement_*.xml` no EOF ou importa no
   DLC Builder. Esta é a validação que conta — o formato é de facto, sem schema oficial.
5. **Com Wwise (Windows, nativo)**: corre Redis + API + worker fora do Docker
   (`uvicorn rockforge.interfaces.api.app:app` e
   `celery -A rockforge.interfaces.worker.celery_app:celery_app worker --pool=solo`),
   com `WWISEROOT` definido (o Audiokinetic Launcher define-o). O worker invoca o
   `WwiseConsole` automaticamente e o bundle inclui `audio.wem`. A conversão usa um
   projeto template com as definições compatíveis com o Rocksmith (Vorbis **com seek
   table** + correção de header, como o DLC Builder) — requer Wwise 2019/2021/2022/2023.
   Sem seek table o jogo carrega a música mas o áudio fica em silêncio e o jogo sai
   segundos depois — se isso acontecer, no DLC Builder escolhe o `audio.wav` do bundle
   (não o `audio.wem`) e deixa o DLC Builder fazer a conversão.
6. **PSARC final**: importa o bundle no DLC Builder (recomendado), ou configura
   `ROCKFORGE_PSARC_PACKER_CMD` com um comando externo que receba `{project}`.

## Avisos legais

- Não existe declaração oficial da Ubisoft sobre CDLC; gerar CDLC a partir de gravações
  protegidas e distribuí-las é distribuição não autorizada. Use apenas com material próprio
  ou autorizado.
- A ingestão YouTube está desativada por defeito (`ROCKFORGE_ENABLE_YOUTUBE=false`) porque
  descarregar áudio viola o ToS do YouTube. Para ativar (uso pessoal, só com músicas
  próprias), cria um ficheiro `.env` na raiz do projeto (ver `.env.example`) com
  `ROCKFORGE_ENABLE_YOUTUBE=true` e reinicia a API/worker — é uma decisão explícita do
  operador, e descarregar conteúdo de terceiros continua a violar o ToS.
- O empacotamento final exige o Wwise (EULA Audiokinetic, não redistribuível): o RockForge
  entrega um bundle pronto a importar no [DLC Builder](https://github.com/iminashi/Rocksmith2014.NET).

## Próximos passos

Funcionalidades propostas (ainda não implementadas) estão listadas em `TODO.md`.
