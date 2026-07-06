# RockForge

Pipeline áudio → arranjos Rocksmith 2014 (CDLC), construído sobre investigação verificada e
**honesto quanto aos limites** da tecnologia atual.

## O que faz (e o que não promete)

| Etapa | Tecnologia | Confiança |
|---|---|---|
| Ingestão (Guitar Pro; ~~upload de áudio / YouTube~~ **deprecated**) | FastAPI | — |
| Normalização | ffmpeg (loudnorm, 44.1 kHz) | determinística |
| Stem de guitarra | Demucs `htdemucs_6s` (MIT) | "okay" segundo os próprios autores; sem SDR publicado |
| Lead vs. Rhythm | heurística própria | **EXPERIMENTAL — não existe método publicado** |
| Notas (pitch/onsets/bends) | Basic Pitch (Apache-2.0) | publicada; degrada com distorção |
| BPM/beats | librosa (ISC) | publicada; inferior a trackers neuronais (escolha por licença) |
| Compasso | assumido 4/4 | **não detetado** — elo mais fraco da literatura |
| Afinação | librosa cents + heurística drop-D | requer confirmação humana |
| Cordas/trastes | otimização de playability (DP própria) | determinística, testada |
| Técnicas | bend (medido), hammer-on/pull-off (regras) | parcial — ver relatório |
| Letra automática (opcional) | WhisperX sobre o stem vocal isolado (Demucs `htdemucs` 2-stem; `pip install -e ".[lyrics]"`) | **EXPERIMENTAL** — gates anti-alucinação (RMS + confiança/palavra); LRC continua a via preferida; CPU é lento, GPU NVIDIA ≈ ferramentas online; corre num **subprocesso** (evita o deadlock CUDA do faster-whisper no Celery) |
| Deteção de tom (opcional) | Demucs `htdemucs_6s` (stem guitarra) + análise espetral (librosa) → presets Lead/Rhythm do catálogo Rocksmith | **EXPERIMENTAL** — classifica o *caráter* do som (clean/crunch/high-gain), não identifica o amp/pedal real; resultado é uma proposta que o utilizador revê e ajusta |
| XML Song2014 | gerador próprio (formato doc. na comunidade) | testado estruturalmente; emite os 32 `arrangementProperties` e a estrutura COUNT/default/END que o DLC Builder e o jogo exigem |
| Áudio `.wem` | Wwise local + projeto template do DLC Builder | Vorbis **com seek table** + correção de header (sem isto o jogo carrega mas fica mudo e sai) — Wwise 2019/2021/2022/2023 |
| PSARC | bundle para DLC Builder; PSARC só com Wwise | **Wwise é obrigatório para .wem** |

## Via Guitar Pro (alta fidelidade — recomendada)

Em alternativa à separação/transcrição por ML, carrega um **GP3/GP4/GP5 ou GP7/GP8 (`.gp`)** +
a gravação: notas, trastes, técnicas (bend/HO/PO/palm mute/harmónicos/vibrato/slide), tempo,
compassos e secções vêm **exatos** do ficheiro. Inclui: seleção de pistas Lead/Rhythm, offset de
sincronização com a gravação, letra (ficheiro **LRC** ou **UltraStar TXT** — timing por
sílaba/linha sincronizado com a gravação — ou letra embutida no GP, alinhada às notas), e tones
(tonebase + até 4 slots, com mudanças temporizadas). Fluxo na UI: "Inspecionar pistas" →
escolher pistas/opções → criar CDLC.

Limitações honestas: **só GP6 (`.gpx`) não é suportado** (container binário proprietário —
exporta como GP5 ou GP7 no Guitar Pro/TuxGuitar). GP3/GP4/GP5 são lidos pelo PyGuitarPro;
GP7/GP8 (`.gp`) têm um parser GPIF/XML nativo. A sincronização é manual — indicas o segundo em
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

### Deteção automática de tom (Lead / Rhythm)

O botão **"Detetar tom"** no painel de tons analisa a gravação e sugere tones
Lead + Rhythm do catálogo de gear do Rocksmith, prontos a usar no jogo:

1. O Demucs (`htdemucs_6s`) isola o stem de guitarra da gravação.
2. A análise espetral (librosa — zero-crossing rate, spectral contrast, centroid,
   rolloff) classifica o caráter do som numa de três categorias: **Clean**,
   **Crunch** ou **High Gain**.
3. São propostos presets curados para Lead e Rhythm (amps, cabinets e pedais reais
   do catálogo, com knobs ajustados) que correspondem à categoria detetada.
4. O utilizador carrega em **"Aplicar tons sugeridos"** para carregar os presets
   no editor de tons, revê/ajusta e grava com **"Aplicar e reconstruir"**.

Nota de honestidade: a análise espetral **não identifica** o amp ou pedal real
usado na gravação — classifica o *caráter* do som e sugere um match plausível do
catálogo Rocksmith. Precisa do extra `[ml]` (Demucs + librosa). Funciona em
qualquer job que tenha uma gravação.

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
| GPU NVIDIA (opcional, muito recomendado) | driver NVIDIA atualizado + build CUDA do PyTorch (ver **2b**) | acelera ML (separação/transcrição/letra) ~10–20× |
| Wwise (opcional) | Audiokinetic Launcher | gerar `.wem` automaticamente |
| DLC Builder (opcional) | [releases](https://github.com/iminashi/Rocksmith2014.NET/releases) | empacotar o PSARC final |

**2. Clonar e instalar** (o repo é privado — o Git pede login GitHub na primeira vez)

```cmd
cd C:\onde\quiseres
git clone https://github.com/F100Pilot/RockForge.git
cd RockForge
py -3.11 -m pip install -e ".[dev,ml,lyrics]"
```

`py -3.11` escolhe explicitamente o Python 3.11 mesmo que outra versão seja a
predefinida; o `start.bat` deteta o 3.11 automaticamente. (Se só tens o 3.11,
`pip install -e ".[dev,ml,lyrics]"` também serve.)

O install demora (PyTorch/Demucs/Basic Pitch/WhisperX, vários GB). O extra
`lyrics` (WhisperX) é necessário para a **deteção automática de letra** —
sem ele, "Detetar letra" reporta "indisponível". Se quiseres instalar sem
essa funcionalidade, usa `pip install -e ".[dev,ml]"`.

> **⚠️ Ingestão via YouTube — DEPRECATED.** Já **não** é oferecida na aplicação
> (o ecrã inicial só tem a via **Guitar Pro**). O download de áudio do YouTube
> viola o ToS e o yt-dlp quebra com frequência; a opção foi removida da interface.
> Os endpoints antigos (`/jobs/youtube`) podem ainda existir no backend por
> compatibilidade, mas não há forma de os usar pela UI e não são suportados.

O texto abaixo fica só como referência histórica: a ingestão via YouTube usava o
extra `youtube` (yt-dlp) — `py -3.11 -m pip install -e ".[dev,ml,lyrics,youtube]"`
— e dependia do `ROCKFORGE_ENABLE_YOUTUBE`. Descarregar áudio do YouTube viola o
ToS (ver Avisos legais).

**2b. Aceleração por GPU (NVIDIA — opcional mas muito recomendada)**

O ML (separação Demucs, transcrição Basic Pitch/WhisperX) corre por defeito em
**CPU**, onde uma música de 4 min demora vários minutos por etapa. Com uma GPU
NVIDIA o tempo cai drasticamente (a deteção de letra aproxima-se dos ~3 min das
ferramentas online).

⚠️ **O `pip install` acima instala o PyTorch só-CPU no Windows.** Para usar a
GPU tens de instalar o build **CUDA** do PyTorch (respeitando o pin `<2.5` do
extra `lyrics`).

⚠️ **Desinstala primeiro.** O build CPU e o build CUDA têm o **mesmo número de
versão** (`2.4.1`), por isso um simples `pip install torch==2.4.1 --index-url …`
é ignorado pelo pip ("já satisfeito") e ficas na mesma com o CPU. Tens de
desinstalar antes. Com CUDA 12.1:

```cmd
py -3.11 -m pip uninstall -y torch torchaudio
py -3.11 -m pip install torch==2.4.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu121
```

Confirma que ficou o build **CUDA** (repara no sufixo `+cu121` da versão):

```cmd
py -3.11 -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Deve imprimir `2.4.1+cu121 True`. Se aparecer `+cpu` ou `False`:
- `…+cpu` → o pip não substituiu o build; repete o `uninstall` acima (às vezes
  há duas cópias) e reinstala.
- `…+cu121 False` → o driver NVIDIA está em falta/desatualizado; corre
  `nvidia-smi` (deve listar a GPU e a versão de CUDA suportada) e atualiza o
  driver em https://www.nvidia.com/Download/index.aspx.

Com `True`, está pronto. O RockForge usa `ROCKFORGE_DEMUCS_DEVICE=auto`
por defeito: deteta a GPU e usa-a automaticamente, caindo para CPU quando não há
nenhuma. Podes forçar com `ROCKFORGE_DEMUCS_DEVICE=cuda` (ou `cpu`). Na deteção
de letra, o device escolhido aparece no log do painel "Letras"
(`device: cuda (GPU)`), para confirmares que a GPU está a ser usada.

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
- Para updates: `git pull` dentro da pasta (e `pip install -e ".[dev,ml,lyrics]"`
  se o `pyproject.toml` tiver mudado)

### Configuração (variáveis de ambiente)

Toda a configuração é por ambiente (cria um `.env` na raiz — ver `.env.example`).
As principais:

| Variável | Por defeito | Para quê |
|---|---|---|
| `ROCKFORGE_DEMUCS_DEVICE` | `auto` | `auto` (GPU NVIDIA se disponível, senão CPU), `cuda` ou `cpu` — device para todo o ML |
| `ROCKFORGE_WHISPERX_DEVICE` | (segue `demucs_device`) | sobrepõe o device só da deteção de letra |
| `ROCKFORGE_WHISPER_MODEL` | `small` | modelo WhisperX da letra: `tiny`/`base`/`small`/`medium`/`large-v3` (maior = mais preciso e mais lento; em CPU baixa para `base`/`tiny`) |
| `ROCKFORGE_ENABLE_YOUTUBE` | `true` | **deprecated** — a ingestão via YouTube foi removida da UI; esta flag já não tem efeito prático |
| `ROCKFORGE_WORK_DIR` | `~/Downloads/RockForge` | onde os bundles gerados são escritos |
| `WWISEROOT` | (do Audiokinetic Launcher) | localização do Wwise para gerar o `.wem` |

### Via executável standalone (sem instalar Python)

Uma alternativa ao `start.bat` para quem quer distribuir a app a outros sem pedir
que instalem Python, Redis ou dependências: um único executável (`rockforge.exe`)
que arranca tudo num processo só — API + worker em memória (sem Redis), com
ffmpeg incluído. Duplo-clique → abre o browser em `http://localhost:8000`.

**O que funciona no `.exe`:** tudo o que é Guitar Pro → CDLC, PSARC nativo,
sincronização, tones, edição de letra manual, upload de áudio — o pipeline core
completo. Se o utilizador tiver o stack ML instalado num Python 3.11 no PATH
(`pip install rockforge[ml,lyrics]`), a transcrição automática (Demucs/Basic
Pitch/WhisperX) também funciona. Se não, a app degrada com a mesma mensagem de
sempre — nenhum crash.

#### Compilar o executável

Pré-requisitos: **Python 3.11** + `pip install pyinstaller` + **ffmpeg**
(`winget install ffmpeg`).

```cmd
cd RockForge

REM 1. Instala as dependências core + psarc + PyInstaller
py -3.11 -m pip install -e ".[dev,psarc]"
py -3.11 -m pip install pyinstaller

REM 2. (Opcional) Cria a pasta ffmpeg/ com o executável para empacotar
mkdir ffmpeg
copy /b "C:\caminho\para\ffmpeg.exe" ffmpeg\ffmpeg.exe

REM 3. Compila
py -3.11 build_exe.py
```

O resultado fica em `dist\rockforge\`. Distribui essa pasta inteira (ou
comprime-a em zip). O utilizador faz duplo-clique em `rockforge.exe` e o
browser abre automaticamente.

Se não colocares o `ffmpeg.exe` dentro de `ffmpeg/`, o build avisa — a app
continua a funcionar se o utilizador tiver o ffmpeg no PATH do sistema.

#### Criar um instalador (para distribuir a outros)

Para criar um instalador `.exe` estilo Windows (wizard de instalação, atalho no
Ambiente de Trabalho, desinstalador no Painel de Controlo):

```cmd
REM Pré-requisito: instalar o Inno Setup 6 (gratuito)
REM   https://jrsoftware.org/isinfo.php

REM 1. Compila o executável (se ainda não foi feito)
py -3.11 build_exe.py

REM 2. Compila o instalador (gera Output\RockForge_Setup.exe)
py -3.11 build_exe.py --installer
```

O ficheiro `Output\RockForge_Setup.exe` é o instalador — envia esse ficheiro
único e o utilizador faz duplo-clique para instalar. Inclui tudo: o executável,
ffmpeg, templates Wwise e o catálogo de gear.

**Alternativa portátil (sem instalação):** para criar um ZIP portátil que o
utilizador só extrai e corre:

```cmd
py -3.11 build_exe.py --zip
```

Gera `dist\RockForge_portable.zip` — extrair e correr `rockforge.exe`.

#### Notas sobre o executável

- **Não inclui ML** (torch/demucs/basic-pitch/whisperx) — são vários GB e
  frágeis para empacotar. O `.exe` serve o fluxo GP e o pipeline core; a
  transcrição automática precisa do Python com as dependências ML instaladas.
- **Não inclui Wwise nem DLC Builder** (restrições de licença) — o `.exe`
  invoca-os se instalados, como sempre.
- **Tens de recompilar** (`py -3.11 build_exe.py`) sempre que alterares o código.
  Para desenvolvimento, continua a usar `start.bat` / `pip install -e .`.
- O idle-shutdown está ativo: fechar o separador do browser para a app
  automaticamente após ~30 segundos.
- Para uma **distribuição com ML incluído**, a alternativa é empacotar um Python
  portátil (`python-build-standalone`) com um venv pré-instalado — mais pesado
  (~5–10 GB) mas inclui tudo. Ver `CLAUDE.md` para detalhes.

### Via Docker (alternativa)

```bash
docker compose up --build   # API em http://localhost:8000 (UI em /, OpenAPI em /docs)
```

Nota: dentro do Docker o Wwise não está disponível — o `.wem` só é gerado na
execução nativa Windows com o Wwise instalado.

Desenvolvimento:

```bash
pip install -e ".[dev]"            # núcleo + testes (sem ML)
pip install -e ".[dev,ml]"         # com Demucs/Basic Pitch/librosa
pip install -e ".[dev,ml,lyrics]"  # + deteção automática de letra (WhisperX)
pytest && ruff check src tests && mypy
```

## Como testar a app (fim-a-fim)

1. **Testes automáticos** (sem ML, rápidos): `pip install -e ".[dev]" && pytest` — 233 testes
   cobrem domínio, mapeamento corda/traste, XML/acordes, pipeline, API (incl. remoção de jobs),
   import GP, letra, tom, deteção de device CPU/GPU, separação Demucs (comandos), PSARC nativo
   (contentor/manifestos/SNG/cifra), `.rs2dlc`, tags e Wwise (consola simulada). Guia completo
   em **[`TESTING.md`](TESTING.md)** (mapa de cobertura, como adicionar testes, e a checklist
   manual fim-a-fim que o CI não consegue cobrir).
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
- A ingestão via YouTube está **deprecated** e foi **removida da interface** (descarregar
  áudio viola o ToS do YouTube e o yt-dlp quebra com frequência). A app só ingere
  ficheiros **Guitar Pro**.
- O empacotamento final exige o Wwise (EULA Audiokinetic, não redistribuível): o RockForge
  entrega um bundle pronto a importar no [DLC Builder](https://github.com/iminashi/Rocksmith2014.NET).

## Próximos passos

Funcionalidades propostas (ainda não implementadas) estão listadas em `TODO.md`.

## Documentação (para programadores / retomar o projeto)

Se perderes o contexto e precisares de reconstruir tudo, lê por esta ordem:

| Documento | Para quê |
|---|---|
| **[`README.md`](README.md)** (este) | instalar, correr, usar, distribuir — começa aqui para preparar uma máquina |
| **[`CLAUDE.md`](CLAUDE.md)** | arquitetura (Clean Architecture), o desenho de cada funcionalidade, e as **restrições rígidas** que já custaram caro — a fonte de verdade sobre *porquê* o código está como está |
| **[`TESTING.md`](TESTING.md)** | correr/estender os 233 testes, mapa de cobertura, e a checklist manual fim-a-fim (ML, Wwise, DLC Builder, in-game) que o CI não cobre |
| **[`TODO.md`](TODO.md)** | o que está feito `[x]`, o que falta `[ ]`, e as limitações conhecidas atuais |
| **[`TONE.md`](TONE.md)** | o modelo de tom (gear) e a serialização dos `Tones` no `.rs2dlc` |
| **`docs/RELATORIO-TECNICO.md`** + **`docs/research/`** | a fundamentação com fontes por trás de cada decisão técnica |

> **Restrição crítica** (já custou um debug de várias sessões): a coluna JSON
> `Job.params` não tem tracking de mutação — escrever o **mesmo** objeto dict
> (`job.params = params`) é um no-op silencioso no SQLAlchemy. Qualquer escrita
> incremental tem de atribuir uma cópia nova (`{**params}`). Ver `CLAUDE.md` ▸
> *Hard constraints* e `TESTING.md` §8.
