# Novidades

**English:** [CHANGELOG.en.md](CHANGELOG.en.md)

As alterações de cada versão. As entradas também vão em inglês, no `CHANGELOG.en.md`.

## [Por lançar]

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
