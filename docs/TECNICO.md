**English:** [TECHNICAL.md](TECHNICAL.md) · [Página inicial](../README.pt.md)

# RockForge — documentação técnica

Pipeline Guitar Pro → arranjos Rocksmith 2014 (CDLC), construído sobre investigação verificada e
**honesto quanto aos limites** da tecnologia atual.

> Projeto independente e gratuito, **sem qualquer ligação à Ubisoft**. Não contém músicas: és tu
> que trazes o ficheiro Guitar Pro e a gravação, e os direitos sobre eles são da tua conta — ver
> [Avisos legais](#avisos-legais) e [`LEGAL.md`](../LEGAL.md). Licença MIT ([`LICENSE`](../LICENSE));
> componentes de terceiros em [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).

**Como usar:** o [Guia do utilizador](GUIA.md) explica o programa passo a passo — criar um
projeto, sincronizar, editar notas, tons, letra, capa, exportar e instalar no jogo, e os
problemas mais comuns. Este documento trata de instalar, correr, compilar e testar.

## O que faz (e o que não promete)

| Etapa | Tecnologia | Confiança |
|---|---|---|
| Ingestão (Guitar Pro) | FastAPI | — |
| Notas/trastes/técnicas/tempo/secções | parser Guitar Pro (GP3/4/5 via PyGuitarPro; GP7/8 nativo) | **exatos** do ficheiro |
| Normalização (gravação) | ffmpeg (ganho linear, 44.1 kHz) | determinística |
| Stem de guitarra (separação/deteção de tom) | Demucs `htdemucs_6s` (MIT) | "okay" segundo os próprios autores; sem SDR publicado |
| BPM/onset e afinação (cents) da gravação — só sincronização automática GP | librosa (ISC) | publicada; requer confirmação humana |
| Letra automática (opcional) | WhisperX sobre o stem vocal isolado (Demucs `htdemucs` 2-stem; `pip install -e ".[lyrics]"`) | **EXPERIMENTAL** — gates anti-alucinação (RMS + confiança/palavra); LRC continua a via preferida; CPU é lento, GPU NVIDIA ≈ ferramentas online; corre num **subprocesso** (evita o deadlock CUDA do faster-whisper no Celery) |
| Deteção de tom (opcional) | Demucs `htdemucs_6s` (stem guitarra) + análise espetral (librosa) → presets Lead/Rhythm do catálogo Rocksmith | **EXPERIMENTAL** — classifica o *caráter* do som (clean/crunch/high-gain), não identifica o amp/pedal real; resultado é uma proposta que o utilizador revê e ajusta |
| XML Song2014 | gerador próprio (formato doc. na comunidade) | testado estruturalmente; emite os 32 `arrangementProperties` e a estrutura COUNT/default/END que o DLC Builder e o jogo exigem |
| Áudio `.wem` | Wwise local + projeto template do DLC Builder | Vorbis **com seek table** + correção de header (sem isto o jogo carrega mas fica mudo e sai) — Wwise 2019/2021/2022/2023 |
| PSARC | bundle para DLC Builder; PSARC só com Wwise | **Wwise é obrigatório para .wem** |

## Via Guitar Pro (alta fidelidade)

Carrega um **GP3/GP4/GP5 ou GP7/GP8 (`.gp`)** +
a gravação: notas, trastes, técnicas (bend/HO/PO/palm mute/harmónicos/vibrato/slide), tempo,
compassos e secções vêm **exatos** do ficheiro. Inclui: seleção de pistas Lead/Rhythm, offset de
sincronização com a gravação, letra (ficheiro **LRC** ou **UltraStar TXT** — timing por
sílaba/linha sincronizado com a gravação — ou letra embutida no GP, alinhada às notas), e tones
(tonebase + até 4 slots, com mudanças temporizadas). Fluxo na UI: "Novo projeto" →
ficheiro → pistas → gravação → detalhes → "Criar CDLC" (passo a passo no
[Guia do utilizador](GUIA.md#4-criar-um-projeto-novo-projeto)).
A interface também pode ser mudada para inglês (seletor PT/EN na página inicial ou
⚙️ Definições → Idioma · Language).

**Sem ficheiro Guitar Pro?** O passo 1 também aceita o **PDF** da tablatura ou uma **imagem**
dela (PNG/JPEG/WebP; vários ficheiros = uma pista cada): o RockForge converte-a num GP5 com o
conversor do [PDF-to-GP5](https://github.com/F100Pilot/PDF-to-GP5) (o extra `[pdf]`) e o
assistente continua como com um ficheiro Guitar Pro. A leitura de imagens (OCR) é experimental:
lê as técnicas escritas (H/P, P.M., let ring, harmónicos), os slides, o vibrato, as
ligaduras, os bends e o ritmo impresso (também como nos livros de tabs); os avisos indicam os
compassos com o ritmo estimado pelo espaçamento. Confere as notas e o ritmo na partitura.

Limitações honestas: **só GP6 (`.gpx`) não é suportado** (container binário proprietário —
exporta como GP5 ou GP7 no Guitar Pro/TuxGuitar). GP3/GP4/GP5 são lidos pelo PyGuitarPro;
GP7/GP8 (`.gp`) têm um parser GPIF/XML nativo. A sincronização é manual — indicas o segundo em
que a música começa na gravação e a partitura/letra são deslocadas para esse instante (a
gravação fica intacta, pois já tem o seu intro); há um lead-in mínimo de 2s para o count-in
do DLC Builder; uma pista de baixo de 4/5 cordas dá o arranjo Bass (um baixo de 5 cordas é
dobrado em quatro).

Para afinar a sincronização, a página **Partitura** toca a gravação com as notas por cima (e um
*tique* em cada nota): acerta o **início da música**, depois o **andamento (BPM)** se a
partitura se afasta por igual, e por fim corrige onde ainda foge — o modo recomendado é
**"Corrigir daqui"**: clicas na nota onde a partitura começa a fugir e o RockForge mede o
andamento da gravação daí em diante. Há também arrastar notas, mover um excerto, alinhar um
compasso ao cursor ou a outra pista, e uma pista principal cujas correções passam para as
outras. Tudo fica pendente até "Aplicar e reconstruir", e as correções somam-se de
reconstrução em reconstrução. Passo a passo no
[Guia do utilizador](GUIA.md#6-sincronizar-as-notas-com-a-gravação).

### Pista 3D (como no Rocksmith)

Na página Partitura, marca **Pista 3D** (ao lado de "Braço"): as notas da pista
escolhida descem para as cordas como no Rocksmith, com o headstock e a afinação
escrita na pestana, brilho quando a nota chega à corda (e a nota fica pousada nela
enquanto soa), acordes com o nome, e a câmara a seguir a zona do braço. Como no
Rocksmith, a nota não tem número: o número do traste no braço passa de branco a
âmbar, com halo, à medida que se aproxima uma nota desse traste (2 s antes), no
máximo no ataque, e fica aceso enquanto ela soa, sem mudar de sítio nem de tamanho
("Traste na nota" volta a pôr o número na nota). As técnicas têm os símbolos do
Rocksmith: ▼ hammer-on e ▲ pull-off na face da nota (também quando ela fica na
corda); uma cruz translúcida dentro da nota (palm mute); por cima, anel com ponto (harmónico), olho (pinch), V largo
(tapping), bloco com entalhe / com bico (slap / pop) e chevrons ˄ para a força do
bend; moldura dupla a brilhar (acento); rasto ondulado (vibrato) e em zigue-zague
(tremolo picking). Segue a gravação e as correções de sincronização ainda por
aplicar, tal como a partitura. Usa o three.js, incluído na aplicação (funciona sem
internet); precisa de WebGL no browser.

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

**Volume do tom:** como no DLC Builder, 0.1–36 e **maior = mais alto** (os tons
do jogo andam por 18–20). Os tons sugeridos já vêm nesse nível.

**Tons por parte de cada pista.** A deteção mede também o som **ao longo da
música** (onde está limpo, onde distorce mais). O cartão **"Sugestões por
secção"** lê isso contra o que cada pista toca em cada secção (acordes e palm
mute → ritmo; notas soltas com bends/ligados ou agudas → solo; acordes a soar
num trecho limpo → limpo) e propõe um tom para cada parte, com o porquê e a
confiança. **"Aplicar a esta pista"/"a todas"** põe esses tons e as trocas no
projeto; com **"Mesmos tons em todas as pistas"** desmarcado, cada pista tem o
seu tom base, extras e trocas (como no jogo, os tons são por arranjo).
Em **"Trocar os tons sugeridos"** podes ficar com os pontos de troca que a app
detetou mas pôr os tons que queres: cada tom sugerido troca-se por um tom do
projeto, da biblioteca ou de um PSARC que já tens. As trocas escolhidas ficam
guardadas no projeto.

Nota de honestidade: a análise espetral **não identifica** o amp ou pedal real
usado na gravação — classifica o *caráter* do som e sugere um match plausível do
catálogo Rocksmith. Precisa do extra `[ml]` (Demucs + librosa). Funciona em
qualquer job que tenha uma gravação.

**Tons das tuas músicas.** Como no DLC Builder: no editor de tons, **"Procurar
nos teus PSARC"** lê a pasta `dlc` do Rocksmith (oficiais e CDLC; a pasta do
jogo inclui também `songs.psarc`) e lista os tons de cada música com o gear
exato. Pesquisa por música, artista, tom ou equipamento, ou escolhe um artista
na lista (ou clica no nome dele num tom) para ver só os tons das músicas dele; **"Usar neste
projeto"** copia o tom, **★** guarda-o na biblioteca. Os ficheiros só são lidos
(apenas os manifestos), e voltar a ler a pasta só abre os novos. Precisa do
extra `[psarc]`.

Leitura obrigatória: [`docs/RELATORIO-TECNICO.md`](RELATORIO-TECNICO.md) (viabilidade,
arquitetura, riscos) e os relatórios de investigação com fontes em [`docs/research/`](research/).

## Arquitetura

Clean Architecture: `domain/` (modelo musical puro) → `application/` (ports + use case do
pipeline Guitar Pro) → `infrastructure/` (adapters: Demucs, librosa, ffmpeg, XML, packaging,
DB) → `interfaces/` (API FastAPI, worker Celery). Cada estágio ML é um Protocol substituível.
Para contribuir, ver [`CLAUDE.md`](../CLAUDE.md) (camadas, comandos e restrições que já custaram caro).

## Software externo (o que instalar, e o que perdes sem cada coisa)

O RockForge **não distribui** as ferramentas de que depende: o Wwise não pode
ser redistribuído (licença da Audiokinetic), o stack de ML são gigabytes, e o
ffmpeg vem melhor do sistema. Cada ausência degrada em condições — mas o
sintoma aparece sempre mais à frente e parece um bug da app ("o PSARC não é
jogável", "a deteção de letra não faz nada").

Por isso há um sítio que te diz o que tens: **⚙️ Definições → 🩺 Software
externo** (ou `GET /system-check`). Mostra o que está instalado nesta máquina,
o que cada falta te custa, e o comando para instalar.

| Software | Preciso para | Sem ele | Instalar |
|---|---|---|---|
| **ffmpeg** | tudo — a gravação é normalizada por aqui | **nenhum job acaba** | `winget install ffmpeg` |
| **Wwise** 2019/2021/2022/2023 | converter o áudio para `.wem` → `.psarc` **jogável** | o bundle para o DLC Builder sai na mesma; o `.psarc` fica sem áudio | Audiokinetic Launcher + `ROCKFORGE_WWISE_ROOT` |
| **`[psarc]`** (cryptography, Pillow) | escrever o `.psarc` nativo e a capa em DDS | só sai o bundle, sem crash | `pip install -e ".[psarc]"` |
| **`[ml]`** (Demucs, librosa) | separar stems, detetar tom, "Corrigir daqui" | esses botões respondem 503 a dizer o que falta | `pip install -e ".[ml]"` |
| **`[lyrics]`** (WhisperX) | transcrever a letra da gravação | a letra continua a vir do GP, de um LRC, ou do editor | `pip install -e ".[ml,lyrics]"` |
| **`[youtube]`** (yt-dlp) + **Deno** | descarregar o áudio do vídeo do YouTube em que o Songsterr marcou os tempos (o YouTube exige resolver um desafio em JavaScript: o solucionador vem no `yt-dlp[default]`, o motor é o Deno) | carregas tu o MP3 desse vídeo | `pip install -U "yt-dlp[default]"` e `winget install DenoLand.Deno` |
| **`[pdf]`** (PDF-to-GP5, com OCR) | criar o projeto a partir de um PDF ou de uma imagem da tab | o PDF/imagem é recusado a dizer o que instalar; GP e Songsterr funcionam | `pip install -e ".[pdf]"` (precisa do git; o `start.bat` instala-o à parte) |
| **PyTorch CUDA** | GPU: minutos em vez de dezenas de minutos | corre tudo em CPU | ver §2b |
| **Patch de CDLC** (`D3DX9_42.dll`) | o Rocksmith aceitar *qualquer* CDLC | a música **nunca aparece** na lista | CustomsForge, na pasta do jogo |

Só o **ffmpeg** é obrigatório. Duas notas honestas sobre a tabela: o patch de
CDLC só é verificado quando a app encontra o jogo — nas bibliotecas do Steam
deste computador, ou na pasta que indicares em ⚙️ Definições → Geral → «Pasta do
Rocksmith 2014»; e se o PyTorch instalado é a build CUDA ou a de CPU não se sabe
— exigia importar o torch no processo da API, o que é proibido de propósito.
Nesses casos o painel diz **ⓘ desconhecido**, não ✅ nem ❌.

### Os componentes extra no `.exe`: instala-os a aplicação

O `.exe` leva o núcleo (**GP → PSARC**) e o seu próprio ffmpeg. **Tem o seu próprio Python**: um
executável PyInstaller só vê os pacotes que traz dentro, por isso não consegue *importar* o
Demucs, o WhisperX, o librosa, o PDF-to-GP5 nem o yt-dlp. Não precisa: todas essas fases correm em
**subprocesso** noutro Python. Por isso a aplicação **instala ela própria esse Python**
(`infrastructure/components.py`):

1. **Python 3.11.9** — o pacote oficial `python` do NuGet (um Python completo e relocável, da
   equipa de lançamentos do CPython: sem instalador, sem registo), em
   `%LOCALAPPDATA%\RockForge\components\python`;
2. **PyTorch** — a versão CUDA 12.1 (`torch==2.4.1`) quando há um driver NVIDIA (`nvidia-smi`),
   senão a de CPU do PyPI;
3. os pacotes dos extras **`[ml]`, `[lyrics]`, `[youtube]` e `[pdf]`** — exatamente os do
   `pyproject.toml`, guardados na compilação; o URL `git+` do conversor de PDF passa a ser o
   arquivo do GitHub, por isso não é preciso git;
4. o **Deno** (o motor JavaScript do yt-dlp) em `components\tools`, posto no PATH ao arrancar.

Depois o *Python ML* passa a apontar para lá. Começa pela tarefa marcada do instalador «Instalá-los
no primeiro arranque» (`rockforge.exe --install-components`), por **Instalar agora** na página
inicial, ou por ⚙️ **Definições → Software → Instalar componentes extra**, com o registo no ecrã;
correr outra vez repara (não volta a descarregar e confirma os pacotes). Cerca de 1 GB a
descarregar, ou 3 GB com uma GPU NVIDIA. O desinstalador apaga `components`. O conversor de PDF
corre através do `gpimport/_pdf_runner.py` nesse Python.

**O Wwise não pode vir assim** — a licença da Audiokinetic proíbe distribuí-lo e o Launcher
precisa de conta, e só o 2019–2023 tem modelo (o Launcher oferece primeiro o 2024/2025: escolhe o
2023.1). O RockForge procura-o onde o Launcher o instala
(`Program Files (x86)\Audiokinetic\Wwise <2019|2021|2022|2023>…`, o mais recente primeiro), na
pasta `Audiokinetic` de qualquer disco, em qualquer pasta `Wwise…` até duas abaixo da raiz de um
disco e no `WWISEROOT` do registo,
senão em ⚙️ Definições → Geral → «Pasta do Wwise» ou `ROCKFORGE_WWISE_ROOT`/`WWISEROOT`; a página
inicial avisa enquanto faltar, e a última página do instalador também.

Um Python teu continua a servir: indica em *Python ML* um Python 3.11 com
`pip install -e ".[ml,lyrics]"` (a partir de uma cópia do RockForge); um caminho indicado à mão
nunca é substituído pelos componentes.

| | `.exe` | `start.bat` (Python 3.11) |
|---|---|---|
| GP → bundle + `.psarc` | ✅ | ✅ |
| ffmpeg | ✅ incluído | do sistema |
| Wwise / patch de CDLC | instalas tu | instalas tu |
| stems, tom, letra, "Corrigir daqui", PDF, YouTube | ✅ depois dos componentes extra | ✅ (o `start.bat` instala os extras) |
| atualizações | a página inicial avisa quando sai uma versão nova | `git pull` a cada arranque |

### Extra: sincronizar pelos tempos do Songsterr

É opcional e fica fechado no passo 3 do assistente, em **➕ Extra**; sem ele,
tudo funciona como antes.


O Songsterr guarda o instante de **cada compasso** num vídeo do YouTube, marcado
por pessoas. No passo 3 do assistente, cola o link da música no Songsterr e
carrega em **Procurar**: escolhes o vídeo e o RockForge usa esses tempos para
alinhar a partitura — sem acertos à mão, mesmo com o andamento a variar.

- O RockForge vai buscar **só os tempos**. O MP3 é o teu e tem de ser
  **convertido desse mesmo vídeo do YouTube** (o link aparece no assistente).
  O áudio que o próprio Songsterr disponibiliza é **outro** e não bate com os
  tempos.
- O ficheiro GP tem de ser **o tab do Songsterr** (exportado de lá), para o
  compasso 5 de um ser o compasso 5 do outro. Se não bater, o projeto avisa.
- Se cortaste o início do MP3, ajusta "Início da música" nesse valor.
- A API do Songsterr não é pública: pode mudar sem aviso. Se deixar de
  responder, o RockForge diz isso e o resto continua a funcionar.

## Execução

### Instalação num PC novo (Windows, sem Docker — recomendado)

**1. Pré-requisitos**

| Software | Como instalar | Para quê |
|---|---|---|
| Git | https://git-scm.com/download/win | clonar o repositório |
| Python **3.11** (exatamente — 3.12+ não funciona: o stack ML/letra `torch<2.5`/demucs/whisperx só tem wheels até 3.11) | https://www.python.org/downloads/ — ⚠️ marca **"Add Python to PATH"** | correr a app |
| ffmpeg | `winget install ffmpeg` | normalização de áudio |
| Redis (opcional) | [Memurai](https://www.memurai.com/) (Developer, grátis; corre como serviço — a instalação pede administrador) | worker separado; sem Redis, o `start.bat` corre as tarefas dentro da API |
| GPU NVIDIA (opcional, muito recomendado) | driver NVIDIA atualizado + build CUDA do PyTorch (ver **2b**) | acelera ML (separação de stems/deteção de tom/letra) ~10–20× |
| Wwise (opcional) | Audiokinetic Launcher | gerar `.wem` automaticamente |
| DLC Builder (opcional) | [releases](https://github.com/iminashi/Rocksmith2014.NET/releases) | empacotar o PSARC final |

**2. Clonar e instalar**

```cmd
cd C:\onde\quiseres
git clone https://github.com/F100Pilot/RockForge.git
cd RockForge
py -3.11 -m pip install -e ".[dev,ml,lyrics]"
```

`py -3.11` escolhe explicitamente o Python 3.11 mesmo que outra versão seja a
predefinida; o `start.bat` deteta o 3.11 automaticamente. (Se só tens o 3.11,
`pip install -e ".[dev,ml,lyrics]"` também serve.)

O install demora (PyTorch/Demucs/WhisperX, vários GB). O extra
`lyrics` (WhisperX) é necessário para a **deteção automática de letra** —
sem ele, "Detetar letra" reporta "indisponível". Se quiseres instalar sem
essa funcionalidade, usa `pip install -e ".[dev,ml]"`.

**2b. Aceleração por GPU (NVIDIA — opcional mas muito recomendada)**

O ML (separação Demucs, letra WhisperX) corre por defeito em
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

Serve qualquer GPU NVIDIA que o PyTorch 2.4 (CUDA 12.1) consiga usar — GeForce, de
estação de trabalho (RTX A/Quadro) ou de centro de dados (T4, A100…), apareça ou não
no Gestor de Tarefas (uma placa em modo TCC não aparece). Com várias, usa a primeira;
`CUDA_VISIBLE_DEVICES` escolhe outra. GPUs AMD e Intel não servem (só a build CUDA).

**3. Arrancar**

```cmd
.\start.bat
```

O `start.bat`:
1. atualiza o código (`git pull`; sem Git ou sem rede, usa a versão local);
2. instala/atualiza as dependências (`[ml,lyrics,psarc,youtube]`) quando o
   `pyproject.toml` mudou desde a última vez — na primeira vez demora;
3. recusa arrancar se a porta 8000 já estiver ocupada (o RockForge já a correr);
4. lança Redis + worker em segundo plano (logs em `logs\`) e a API na janela atual;
   sem Redis instalado (ex.: um portátil do trabalho sem permissões de
   administrador), as tarefas correm dentro da própria API, uma de cada vez, e
   fechar o separador espera que acabem;
5. abre **http://localhost:8000** no Chrome (ou no browser predefinido, se não
   houver Chrome). Ctrl+C, ou fechar o separador, para tudo.

Notas:
- O primeiro job descarrega os modelos ML (~2 GB extra, só uma vez)
- Os bundles gerados vão para `C:\Users\<utilizador>\Downloads\RockForge`
- Na lista de **Jobs** cada linha tem um botão 🗑 para remover o job (apaga
  também o bundle gerado e o ficheiro carregado, se nenhum outro job o usar);
  jobs em execução têm de terminar primeiro
- Updates: o `start.bat` faz o `git pull` e reinstala as dependências quando
  o `pyproject.toml` muda; para forçar a reinstalação, apaga `logs\pyproject.installed`

### Configuração (variáveis de ambiente)

Toda a configuração é por ambiente (cria um `.env` na raiz — ver `.env.example`).
As principais:

| Variável | Por defeito | Para quê |
|---|---|---|
| `ROCKFORGE_DEMUCS_DEVICE` | `auto` | `auto` (GPU NVIDIA se disponível, senão CPU), `cuda` ou `cpu` — device para todo o ML |
| `ROCKFORGE_WHISPERX_DEVICE` | (segue `demucs_device`) | sobrepõe o device só da deteção de letra |
| `ROCKFORGE_WHISPER_MODEL` | `small` | modelo WhisperX da letra: `tiny`/`base`/`small`/`medium`/`large-v3` (maior = mais preciso e mais lento; em CPU baixa para `base`/`tiny`) |
| `ROCKFORGE_WORK_DIR` | `~/Downloads/RockForge` | onde os bundles gerados são escritos; para a mudar, move a pasta inteira e aponta isto para o sítio novo — no arranque seguinte cada projeto encontra lá os seus ficheiros |
| `WWISEROOT` | (do Audiokinetic Launcher) | localização do Wwise para gerar o `.wem` |

### Via executável standalone (sem instalar Python)

Uma alternativa ao `start.bat` para quem quer distribuir a app a outros sem pedir
que instalem Python, Redis ou dependências: um único executável (`rockforge.exe`)
que arranca tudo num processo só — API + worker em memória (sem Redis), com
ffmpeg incluído. Duplo-clique → abre numa janela própria (no browser, se a
janela não puder abrir).

**O que funciona no `.exe`:** tudo o que é Guitar Pro → CDLC, PSARC nativo,
sincronização, tons, edição de letra manual — o pipeline core completo. A deteção
de stems/tom/letra (Demucs/WhisperX), o *Corrigir daqui*, a importação de PDF e o
áudio do YouTube também funcionam depois de a aplicação instalar os componentes
extra (ver "Os componentes extra no `.exe`" acima). Sem eles, a app diz o que
falta — nenhum crash.

#### Compilar o executável

Pré-requisitos: **Python 3.11** + `pip install pyinstaller` + **ffmpeg**
(`winget install ffmpeg`).

```cmd
cd RockForge

REM 1. Instala as dependências core + psarc + janela nativa + PyInstaller
py -3.11 -m pip install -e ".[dev,psarc,desktop]"
py -3.11 -m pip install pyinstaller

REM 2. (Opcional) Cria a pasta ffmpeg/ com o executável para empacotar
mkdir ffmpeg
copy /b "C:\caminho\para\ffmpeg.exe" ffmpeg\ffmpeg.exe

REM 3. Compila
py -3.11 build_exe.py
```

O resultado fica em `dist\rockforge\`. Distribui essa pasta inteira (ou usa
`--zip` / `--installer` abaixo). O utilizador faz duplo-clique em
`rockforge.exe` e a app abre **numa janela própria** — sem separador do browser
e sem janela preta de consola.

O extra `[desktop]` é o que dá a janela nativa (pywebview, que usa o **Edge
WebView2** já incluído no Windows — não empacota um segundo browser). **Sem ele
o build continua a funcionar**, mas cai no comportamento antigo: serve e abre o
browser predefinido. O `build_exe.py` avisa se faltar, para não passares por
isso sem dar conta.

Se não colocares o `ffmpeg.exe` dentro de `ffmpeg/`, o build avisa — a app
continua a funcionar se o utilizador tiver o ffmpeg no PATH do sistema.

**Onde ver os erros:** em `%USERPROFILE%\Downloads\RockForge\logs\`: o
`rockforge.log` é o registo técnico (em rotação, ver
[VERSIONING.md](VERSIONING.md#technical-log)), e o `console.log` o que o `.exe`
sem consola teria escrito (as três execuções anteriores ficam como
`console.log.1`…`.3`). São o primeiro sítio a consultar se o `.exe` não
arrancar. Definições → Geral → Sobre o RockForge → "Copiar informação para
relatório" junta as suas últimas linhas.

#### Verificar o build antes de distribuir

**Faz sempre estas três verificações.** Um `.exe` já foi distribuído com a
interface completamente morta: o `rockforge.spec` listava os ficheiros da UI à
mão, e quando o JavaScript saiu do `index.html` para o `web/app.js` a lista não
acompanhou. O `index.html` carregava um `/app.js` que não estava no bundle, e o
resultado era uma página que abre e não faz absolutamente nada. Nenhum teste
olhava para o spec, por isso nada apanhou o erro até alguém abrir a app.

```cmd
REM 1. ANTES de compilar — o teste que garante que o spec recolhe tudo o que
REM    está em web\. Se falhar, o .exe vai sair partido; não compiles.
py -3.11 -m pytest tests\test_standalone_spec.py -v

REM 2. DEPOIS de compilar — os ficheiros da UI têm de estar dentro do bundle.
REM    Devem aparecer o index.html, o app.js e as 6 imagens de gear.
dir /s /b dist\rockforge\_internal\web

REM 3. Corre o .exe e confirma que a interface está VIVA (não basta abrir):
REM    - a versão aparece no canto (vem de uma chamada à API, prova que o JS correu)
REM    - clicar em "Novo projeto" abre o assistente de 4 passos
REM    - F12 → Console não mostra erros (o 404 do favicon é normal)
dist\rockforge\rockforge.exe
```

Se a página abrir mas nenhum botão responder, é este o problema: o `/app.js`
está a dar 404. Confirma-o em `F12 → Network`.

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

- **Não inclui ML** (torch/demucs/whisperx) — são vários GB e
  frágeis para empacotar. O `.exe` serve o fluxo GP e o pipeline core; a
  deteção de stems/tom/letra precisa do Python com as dependências ML instaladas.
- **Não inclui Wwise nem DLC Builder** (restrições de licença) — o `.exe`
  invoca-os se instalados, como sempre.
- **Tens de recompilar** (`py -3.11 build_exe.py`) sempre que alterares o código.
  Para desenvolvimento, continua a usar `start.bat` / `pip install -e .`.
- O idle-shutdown está ativo: fechar o separador do browser para a app
  automaticamente após ~3 segundos. **Se houver trabalho a decorrer** (uma
  build, uma separação de stems, uma deteção de letra) a app espera que termine
  antes de sair — fechar o separador a meio de uma build já não a cancelava
  deixando o projeto preso em "running" para sempre.
- Para uma **distribuição com ML incluído**, a alternativa é empacotar um Python
  portátil (`python-build-standalone`) com um venv pré-instalado — mais pesado
  (~5–10 GB) mas inclui tudo. Ver `CLAUDE.md` para detalhes.

#### Publicar uma versão (os downloads no GitHub)

O `.github/workflows/release.yml` constrói os downloads para Windows numa máquina Windows do
GitHub, para ninguém ter de os construir à mão. Para publicar a versão X.Y.Z (uma beta é
`X.Y.Z-beta.N`):

1. Põe a versão no `pyproject.toml` (na forma PEP 440, p. ex. `0.10.0b2`), no
   `src/rockforge/__init__.py` e no `installer.iss` (`0.10.0-beta.2`), e dá aos dois changelogs
   uma secção `## [X.Y.Z beta N]` — o `tests/test_release_version.py` falha se não baterem — e
   escreve o `docs/RELEASE_NOTES.md` (só as novidades e os bugs resolvidos, em inglês e depois em
   português).
2. Envia esse commit para o `main`. **Mais nada**: quando o CI passa no `main` e a versão do
   `installer.iss` ainda não tem tag, o workflow cria a tag `vX.Y.Z-beta.N` e a release (uma
   pre-release, se for beta) nesse commit, constrói e testa os downloads e anexa-os — cerca de
   meia hora depois. Um commit que não muda a versão não publica nada.

Uma tag enviada à mão (`git tag v0.10.0-beta.2 && git push origin v0.10.0-beta.2`), ou uma
release criada no GitHub com uma tag nova, continua a arrancar o mesmo workflow.

Uma pre-release nunca aparece no quadro "Releases" da página inicial do repositório — esse quadro
só mostra a última release definitiva. As pre-releases estão na página Releases.

O workflow instala a app, junta um ffmpeg **LGPL** (com o seu `LICENSE.txt` e um `SOURCE.txt`
com o link para o código exato; recusa uma versão GPL), compila o instalador, **arranca o
`rockforge.exe` já construído e cria um projeto com ele** (um GP5 e um som inventados,
confirmados pela verificação de PSARC da própria app), e só então cria a Release no GitHub —
uma pre-release, se for beta, com o `docs/RELEASE_NOTES.md` como texto — e anexa
`RockForge-<versão>-Setup.exe`, `RockForge-<versão>-portable.zip` e `SHA256SUMS.txt`. Corrido à
mão (*Actions → Release → Run workflow*) é um ensaio: os ficheiros ficam como artefactos dessa
execução e nada é publicado; com a tag de uma release que já existe (*release_tag*), anexa-lhe
os ficheiros. Os ficheiros não têm assinatura digital, por isso o SmartScreen
avisa na primeira vez.

### Via Docker (alternativa)

Esta é a única via que abre uma porta de rede (`8000:8000`) — ao contrário do
`start.bat`/executável standalone (ambos ligados a `127.0.0.1`), a API aqui não
tem autenticação nenhuma por defeito. Cria um `.env` (fica fora do git) ao lado
do `docker-compose.yml` com um segredo:

```bash
echo "ROCKFORGE_API_TOKEN=$(openssl rand -hex 32)" > .env
docker compose up --build   # API em http://localhost:8000 (UI em /, OpenAPI em /docs)
```

O browser pede as credenciais nativamente (utilizador tanto faz, o token como
password) na primeira visita. Sem o `.env`, o `docker compose up` recusa-se a
arrancar — é intencional, para nunca correr exposto sem proteção.
A ligação é HTTP simples: fora da tua rede, põe um proxy com TLS à frente, ou
publica a porta só em `127.0.0.1` (`"127.0.0.1:8000:8000"`).

Fora do Docker, o RockForge só responde a `localhost`/`127.0.0.1` — uma página
web que aponte o seu domínio para o teu computador é recusada. Para lhe chegares
por outro nome, junta-o a `ROCKFORGE_ALLOWED_HOSTS` (ver `.env.example`); o
compose põe `*`, e é o token que o protege.

Nota: dentro do Docker o Wwise não está disponível — o `.wem` só é gerado na
execução nativa Windows com o Wwise instalado.

Desenvolvimento:

```bash
pip install -e ".[dev,psarc]"      # núcleo + testes (sem ML) — usa SEMPRE este
pip install -e ".[dev,ml]"         # com Demucs/librosa
pip install -e ".[dev,ml,lyrics]"  # + deteção automática de letra (WhisperX)
pytest && ruff check src tests start_standalone.py build_exe.py && mypy
```

O extra `[psarc]` não é opcional para testar: sem o `cryptography`, 17 testes do
PSARC nativo (o container encriptado e o binário SNG) saltam-se sozinhos em
silêncio e a suíte fica verde sem nunca os ter corrido.

## Como testar a app (fim-a-fim)

1. **Testes automáticos** (sem ML, rápidos): `pip install -e ".[dev,psarc]" && pytest` — a suíte
   cobre domínio, XML/acordes, use case GP, API (incl. remoção de jobs),
   import GP, letra, tom, deteção de device CPU/GPU, separação Demucs (comandos), PSARC nativo
   (contentor/manifestos/SNG/cifra), `.rs2dlc`, tags e Wwise (consola simulada). Guia completo
   em **[`TESTING.md`](../TESTING.md)** (mapa de cobertura, como adicionar testes, e a checklist
   manual fim-a-fim que o CI não consegue cobrir).
2. **Arrancar a stack**: `docker compose up --build`. Abre `http://localhost:8000`.
   A deteção opcional de stems/tom/letra descarrega os modelos (Demucs ~2 GB) na primeira
   utilização; em CPU, uma música de 4 min demora vários minutos na etapa `separate`.
3. **Smoke test honesto**: em "Novo projeto", usa um **GP3/GP4/GP5 ou GP7/GP8** + a
   gravação, escolhe as pistas Lead/Rhythm e cria o CDLC. Abre o job, afina a sincronização
   no visualizador (início da música, BPM, arrastar notas) e usa "Aplicar e reconstruir".
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

O texto completo está em [`LEGAL.md`](../LEGAL.md). Em resumo:

- **Sem ligação à Ubisoft.** "Rocksmith" é marca da Ubisoft Entertainment e é usada aqui só para
  dizer com que jogo os ficheiros funcionam. Não existe declaração oficial da Ubisoft sobre CDLC.
- **Não contém músicas nem conteúdo da Ubisoft.** Do formato do jogo, o RockForge traz apenas o
  que as ferramentas públicas da comunidade publicam há anos (chaves do PSARC/SNG, esquema
  `.flat`, tabela de glifos, catálogo de equipamento), para os ficheiros que escreve serem
  legíveis pelo jogo. A origem de cada peça está em
  [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).
- **Os direitos sobre o que crias são da tua conta.** Gerar CDLC a partir de gravações protegidas
  e distribuí-los é distribuição não autorizada. Usa apenas material próprio, livre ou
  autorizado.
- **Serviços online.** São contactados só quando carregas no botão, e os termos de cada um
  aplicam-se a ti:
  - **Songsterr**: API não documentada; as tablaturas são licenciadas, para uso pessoal; não
    redistribuas as tablaturas importadas nem o GP5 gerado a partir delas.
  - **YouTube** (yt-dlp, extra opcional): os termos não permitem descarregar; uso pessoal.
  - **LRCLIB / iTunes / MusicBrainz**: letras e capas pertencem aos detentores dos direitos.
- **Wwise.** O empacotamento final exige o Wwise (EULA Audiokinetic, não redistribuível): cada
  utilizador instala-o. O RockForge também entrega um bundle pronto a importar no
  [DLC Builder](https://github.com/iminashi/Rocksmith2014.NET).
- **Sem garantia** (licença MIT).

## Licença

O RockForge é distribuído sob a licença MIT — ver [`LICENSE`](../LICENSE). Código e dados de
terceiros mantêm as suas licenças (Rocksmith2014.NET e three.js: MIT; lógica adaptada do alphaTab:
MPL-2.0; PyGuitarPro: LGPL-3.0; …), todos listados em
[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md). Quem distribuir o `.exe` ou o instalador tem de
incluir esse ficheiro e o `LICENSE`, e, se lá puser o `ffmpeg.exe`, cumprir a licença dessa build
do ffmpeg.

## Próximos passos

Funcionalidades propostas (ainda não implementadas) estão listadas em `TODO.md`.

## Documentação (para programadores / retomar o projeto)

Se perderes o contexto e precisares de reconstruir tudo, lê por esta ordem:

| Documento | Para quê |
|---|---|
| **[`README.pt.md`](../README.pt.md)** | a página inicial: o que faz, como começar, onde está cada documento |
| **[`docs/TECNICO.md`](TECNICO.md)** (este; inglês: [`docs/TECHNICAL.md`](TECHNICAL.md)) | instalar, correr, compilar, distribuir e testar — começa aqui para preparar uma máquina |
| **[`docs/GUIA.md`](GUIA.md)** (inglês: [`docs/GUIDE.en.md`](GUIDE.en.md)) | o guia do utilizador: como trabalhar com a aplicação, página a página |
| **[`CLAUDE.md`](../CLAUDE.md)** | arquitetura (Clean Architecture), o desenho de cada funcionalidade, e as **restrições rígidas** que já custaram caro — a fonte de verdade sobre *porquê* o código está como está |
| **[`TESTING.md`](../TESTING.md)** | correr/estender a suíte de testes, mapa de cobertura, e a checklist manual fim-a-fim (ML, Wwise, DLC Builder, in-game) que o CI não cobre |
| **[`TODO.md`](../TODO.md)** | o que está feito `[x]`, o que falta `[ ]`, e as limitações conhecidas atuais |
| **[`TONE.md`](../TONE.md)** | o modelo de tom (gear) e a serialização dos `Tones` no `.rs2dlc` |
| **[`docs/RELATORIO-TECNICO.md`](RELATORIO-TECNICO.md)** + **[`docs/research/`](research/)** | a fundamentação com fontes por trás de cada decisão técnica |
| **[`LEGAL.md`](../LEGAL.md)** · **[`LICENSE`](../LICENSE)** · **[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)** | aviso legal (Ubisoft, direitos de autor, serviços online), a licença MIT e a origem/licença de tudo o que vem de terceiros — atualiza o último sempre que incluíres ou adaptares código ou dados de outro projeto |

> **Restrição crítica** (já custou um debug de várias sessões): a coluna JSON
> `Job.params` não tem tracking de mutação — escrever o **mesmo** objeto dict
> (`job.params = params`) é um no-op silencioso no SQLAlchemy. Qualquer escrita
> incremental tem de atribuir uma cópia nova (`{**params}`). Ver `CLAUDE.md` ▸
> *Hard constraints* e `TESTING.md` §8.
