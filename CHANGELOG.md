# Novidades

**English:** [CHANGELOG.en.md](CHANGELOG.en.md)

As alterações de cada versão. As entradas também vão em inglês, no `CHANGELOG.en.md`.

## [Por lançar]

### Corrigido
- **O ecrã preto que piscava ao clicar em alguns botões no `.exe`**: era a janela de consola de
  cada programa que a app corre por trás (ffmpeg, o Python dos componentes extra, yt-dlp…). Passam
  todos a correr sem janela.
- **O Wwise instalado mas «não detetado»**: o RockForge procura agora também noutros discos e no
  `WWISEROOT` que o instalador do Wwise grava no registo, e quando há um Wwise que não serve diz
  qual é e porquê — o Audiokinetic Launcher instala por omissão a versão mais recente (2024/2025),
  e só o 2019–2023 converte o áudio (como no DLC Builder). Antes dizia só «ROCKFORGE_WWISE_ROOT
  não está definido».

## [0.10.0 beta 6] — 2026-10-15

### Novo
- **«Marcar a ouvir», para tabs sem sincronização** (inspetor Sincronização): dás play e carregas
  em **B** no primeiro tempo de cada compasso (ou em cada tempo), e as notas encaixam nos teus
  toques enquanto tocas. Backspace tira o último toque, Esc termina; podes abrandar a
  reprodução, e os toques são suavizados para tirar o tremor da mão. Ficam como correções
  pendentes (um Ctrl+Z desfá-los todos) até «Aplicar e reconstruir».

### Corrigido
- **No `.exe`, os componentes extra instalados não eram usados** quando a definição «Python para
  o ML» ficava vazia: o cartão dizia que estava tudo instalado e o resto da aplicação que
  faltava. Agora o RockForge encontra sozinho o Python dos componentes; um caminho escolhido à
  mão continua a ganhar.

## [0.10.0 beta 5] — 2026-10-15

Inclui o que estava preparado para a beta 4, que não chegou a ser publicada.

### Novo
- **Editor de posições da mão (FHP).** Uma faixa por baixo da pauta mostra onde o jogo põe a mão,
  e o novo modo «Posição da mão (FHP)» (tecla 0) deixa pôr, mudar (traste e largura) e apagar
  posições, pista a pista; uma nota fora da sua posição fica com um anel vermelho. As tuas
  posições vão para o `.psarc` (em todos os níveis de dificuldade) e para o projeto do DLC
  Builder; Notas ▾ → «Repor automáticas» volta às calculadas. A pista 3D segue-as.
- **Arranjo de baixo (Bass).** Escolhe a pista de baixo do ficheiro Guitar Pro no assistente
  (ou em «Editar info») e o projeto ganha um arranjo BASS, codificado como o DLC Builder o faz.
  Um baixo de 5 cordas é dobrado nas quatro cordas que perdem menos notas, com um aviso; uma
  afinação muito grave (B standard) é escrita uma oitava acima a 220 Hz, como no DLC Builder,
  para o jogo detetar as notas. A partitura, o braço e a pista 3D mostram quatro cordas. Ainda
  não foi tocado no jogo — diz-nos como corre.
- **Aviso de versão nova** na página inicial: o RockForge pergunta às Releases do GitHub, no
  máximo uma vez por dia, se há uma versão mais recente (desliga-se em Definições → Geral). Quem
  usa o `start.bat` com o git não o vê, porque se atualiza sozinho.
- **O `.exe` instala sozinho os componentes extra**: análise de áudio, deteção de tom e de letra,
  conversão de PDF e áudio do YouTube. O instalador oferece-os (marcados) e a página inicial
  também; o RockForge descarrega um Python 3.11 só seu com os pacotes (o PyTorch com CUDA quando
  há uma GPU NVIDIA) e o Deno, para os dados locais da conta, e o desinstalador apaga-os. A
  importação de PDF passa a funcionar no `.exe`.
- **O Wwise é encontrado sozinho** onde o Audiokinetic Launcher o instala, ou indica-se em
  Definições → Geral → «Pasta do Wwise». A página inicial e a última página do instalador avisam
  quando falta (a licença não permite incluí-lo).

### Alterado
- **As posições da mão automáticas foram refeitas** com base em gráficos feitos à mão: um acorde
  põe a mão onde está o indicador, as outras notas deixam a mão onde está enquanto um dedo lá
  chega, e a mão só muda na primeira nota que já não alcança. Comparadas com dois CDLC da
  comunidade, coincidem em 98% das notas (antes 80%), com o mesmo número de mudanças.
- O XML para o DLC Builder passa a levar as mesmas posições da mão automáticas que o `.psarc`
  (antes eram calculadas de duas maneiras diferentes).

### Corrigido
- **No `.exe`, os botões «Descarregar» não faziam nada** (nem davam erro): a janela própria
  bloqueava as descargas. Agora abre a janela «Guardar como».
- **O capo do ficheiro Guitar Pro era ignorado.** Passa a ser lido (GP3-5 e GP7/8): os trastes
  passam a contar a partir da pestana, como no Rocksmith, e o arranjo leva o capo.
- **Sem Wwise, o `.psarc` levava o WAV inteiro** (uns 30 MB) num sítio que o jogo não lê. Já não
  leva: o áudio fica no bundle para o DLC Builder e a aplicação diz que falta o Wwise.
- Um nível de dificuldade só com cordas soltas ficava sem âncora no `.psarc` (apanhado pela
  verificação do PSARC num baixo cujas notas mais simples são as fundamentais soltas).

## [0.10.0 beta 3] — 2026-10-15

### Novo
- Botão **«Paga-me um café»** (PayPal) na página inicial e um cartão **Apoiar o projeto** em
  Definições → Geral. O RockForge continua gratuito.
- **Vídeo tutorial** (português e inglês) e um GIF no README.

## [0.10.0 beta 2] — 2026-10-15

### Distribuição
- **Instalador e zip portátil para Windows** nas Releases, construídos e testados
  automaticamente (o `.exe` arranca e cria um projeto antes de ser publicado), com um
  `SHA256SUMS.txt`. Não precisam de Python e trazem o ffmpeg (uma versão LGPL, com a sua licença
  e o link para o código-fonte).
- Licenças esclarecidas: o código adaptado do alphaTab está em dois ficheiros próprios, sob
  MPL-2.0; o resto é MIT.
- Corrigido no `.exe`: um projeto sem tons próprios não gerava o `.psarc` (faltavam no pacote os
  tons por defeito do DLC Builder). Encontrado pelo teste automático do `.exe`.

### Novo
- **Pista 3D com a simbologia do Rocksmith:** a nota deixa de ter o número do traste — o
  número do traste no braço passa a âmbar e brilha à medida que se aproxima uma nota desse
  traste, e fica aceso enquanto ela soa ("Traste na nota" volta a pôr o número na nota). As
  letras das técnicas dão lugar aos símbolos do jogo: ▼ hammer-on e ▲ pull-off na nota; por
  cima, laço (palm mute), anel com ponto (harmónico), olho (pinch), V largo (tapping), bloco com
  entalhe / com bico (slap / pop) e chevrons ˄ para a força do bend; moldura dupla (acento);
  rasto ondulado (vibrato) e em zigue-zague (tremolo picking).
- **Desfazer / Refazer** em tudo o que está pendente: correções de sincronização, andamento,
  notas, letra, secções, tons e opções da construção, em qualquer página do projeto (botões na
  barra de cima, Ctrl+Z, Ctrl+Shift+Z ou Ctrl+Y). Antes só se podia desfazer o último apagar
  de notas.
- **As alterações por aplicar ficam guardadas automaticamente** neste browser: fechar a
  aplicação antes de "Aplicar e reconstruir" já não as perde, e ao reabrir o projeto pergunta
  se as queres recuperar.
- **Repetir um trecho (A–B)** no transporte: marca A e B no cursor (ou [ e ]) e a reprodução
  fica nesse trecho até desligares (L); o trecho aparece na partitura. Com a velocidade, serve
  para ouvir um passo devagar até a sincronização bater.
- **Atalhos de teclado à vista:** **?** (ou o botão da tecla) mostra-os todos; **1–9** escolhem o
  modo da partitura, com o número ao lado de cada um no menu Modo ▾.
- **Notas ligadas:** um slide legato do Guitar Pro (a nota de chegada sem nova palhetada) chega ao
  jogo como em Rocksmith — a nota corre até à seguinte sem ataque novo, nos XML do DLC Builder e
  no PSARC. Na partitura, um arco por cima da nota. A exportação "Guitar Pro com as notas
  editadas" volta a escrevê-lo como slide legato.
- **Arpejos:** notas soltas em let ring sobre a forma de um acorde (pelo menos três, em três
  cordas, numa só posição da mão) passam a aparecer no jogo com a forma do acorde por cima, como
  nos arpejos das músicas originais. O Guitar Pro não marca arpejos, por isso são deduzidos; na
  partitura ficam com uma chaveta "arpejo C" por baixo.
- A verificação do PSARC ("Antes de usar", na página Exportar) confere também as ligações e os
  arpejos.
- A barra de cima do projeto já não sobrepõe o estado aos botões "Editar info"/"Versão anterior"
  em ecrãs estreitos: o estado e o "Pendente" encolhem e "Descarregar" fica só com o ícone.

### Segurança
- Um título, nome de tom, secção ou letra vindos de fora (ficheiro GP, Songsterr, LRCLIB, CDLC
  de outras pessoas) já não conseguem correr código na página: o texto passou a ser escapado
  também dentro dos atributos.
- O servidor só responde a `localhost`/`127.0.0.1`: uma página web que aponte o seu domínio
  para o teu computador (DNS rebinding) é recusada. Outros nomes juntam-se em
  `ROCKFORGE_ALLOWED_HOSTS`. Um pedido com `Origin: null` conta como vindo de outro site.
- Todas as respostas levam `X-Content-Type-Options: nosniff` e não podem ser mostradas dentro
  de outro site.
- Docker: a imagem passa a gerar o `.psarc` (faltava o `[psarc]`).

### Corrigido
- O áudio de um ficheiro GP8 em `.opus`, `.webm`, `.aac`, `.mp4` ou `.wma` (e um download do
  YouTube nesses formatos) era encontrado mas a construção recusava-o. Agora há uma só lista de
  formatos, e também se podem carregar.
- "Aplicar e reconstruir" com duplo clique criava duas versões.
- Uma resposta atrasada de um projeto que já fechaste (ou de outro que abriste a seguir) reabria-o;
  e a deteção de tom/stems continuava a consultar o projeto novo depois de mudares.
- `1:60` na duração das letras encontradas e `[00:60.00]` no LRC exportado.
- Um silêncio inicial negativo era aceite ao criar o projeto e desalinhava as correções depois de
  mudar o andamento.
- Saiu a caixa "Lead/Rhythm (exp.)", que já não fazia nada.
- **O desvio da afinação chega ao jogo.** "Detetar afinação" media quantos cents a gravação está
  afastada do Lá 440 Hz, mas o valor nunca chegava ao `.psarc` (saía sempre 0). Agora há um campo
  "Desvio da afinação (cents)" (−50 a +50) em Exportar → Opções da construção, preenchido pela
  deteção ou à mão, igual em todas as pistas. Os seis números "Afinação (MIDI)", que também não
  faziam nada, saíram: a afinação das cordas muda-se em "Editar info".

## [0.10.0 beta 1] — 2026-10-14

Primeira versão pública, em beta: pronta a usar, mas à espera de mais testes no jogo e
num PC sem Python antes da 1.0.0.

### Criar um projeto
- Ficheiros Guitar Pro 3, 4, 5 e 7/8 (`.gp`): notas, trastes, técnicas, andamentos, secções e
  letra lidos do ficheiro; repetições, voltas e saltos D.S./D.C. pela ordem em que se tocam; os
  pontos de sincronização e o áudio de um ficheiro Guitar Pro 8.
- Sem ficheiro Guitar Pro: a tab importada de um link do Songsterr (com os tempos de cada compasso
  no vídeo), ou um PDF ou imagem da tab convertidos pelo PDF-to-GP5.
- A gravação: um ficheiro de áudio, o áudio dentro do ficheiro GP8, ou o áudio de um vídeo do
  YouTube.
- Assistente de 4 passos e um modo de lote para álbuns inteiros; álbum, ano, capa e letra
  sincronizada procurados online e escolhidos por ti.

### Sincronizar e editar
- Início da música, ajuste do BPM, "Corrigir daqui", arrastar notas e trechos, alinhar compassos,
  andamento por compasso, e uma pista principal cujas correções passam para as outras.
- Cada pista marcada como sincronizada à parte.
- Editor de notas (trastes, técnicas, inserir, apagar, copiar e colar) e de secções na partitura.
- Pista 3D ao estilo do Rocksmith.

### Tons e letra
- Editor de tons com o equipamento do jogo, biblioteca de tons, e os tons das músicas da tua pasta
  `dlc`.
- Tons por pista, mudanças de tom, deteção do tom e sugestões de tom para cada parte.
- Letra do ficheiro GP, do LRCLIB ou da gravação (WhisperX), acertada à voz e editável ao lado da
  partitura.

### Para o jogo
- `.psarc` nativo e jogável (com o Wwise) e projeto do DLC Builder, sempre os dois.
- Dificuldade dinâmica, dedilhação dos acordes e formas de mão.
- Verificação do `.psarc` e instalação na pasta `dlc` do jogo.
- Exportar de volta para Guitar Pro: os andamentos corrigidos numa cópia do teu ficheiro, ou as
  notas editadas num GP5 novo.

### Distribuição
- Licença MIT, avisos de terceiros e aviso legal; página inicial, guia do utilizador e
  documentação técnica em português e inglês; mensagens do `start.bat` nas duas línguas.
