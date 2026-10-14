# Novidades

**English:** [CHANGELOG.en.md](CHANGELOG.en.md)

As alterações de cada versão. As entradas também vão em inglês, no `CHANGELOG.en.md`.

## [Por lançar]

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
