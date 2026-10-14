**English:** [GUIDE.en.md](GUIDE.en.md)

# Guia do utilizador

Como usar o RockForge, do ficheiro da música até tocá-la no Rocksmith 2014. Para instalar,
vê o [README](../README.md). Cada ferramenta da aplicação tem também um **ⓘ** com a sua
explicação curta; este guia junta tudo pela ordem em que se trabalha.

**Conteúdo**

1. [O caminho em resumo](#1-o-caminho-em-resumo)
2. [Antes de começar](#2-antes-de-começar)
3. [A página inicial](#3-a-página-inicial)
4. [Criar um projeto (Novo projeto)](#4-criar-um-projeto-novo-projeto)
5. [A página do projeto](#5-a-página-do-projeto)
6. [Sincronizar as notas com a gravação](#6-sincronizar-as-notas-com-a-gravação)
7. [Editar notas e secções](#7-editar-notas-e-secções)
8. [Tons](#8-tons)
9. [Letra](#9-letra)
10. [Capa e informação da música](#10-capa-e-informação-da-música)
11. [Exportar, verificar e instalar no jogo](#11-exportar-verificar-e-instalar-no-jogo)
12. [Um álbum de uma vez (Lote)](#12-um-álbum-de-uma-vez-lote)
13. [Definições](#13-definições)
14. [Atalhos de teclado](#14-atalhos-de-teclado)
15. [Problemas comuns](#15-problemas-comuns)

---

## 1. O caminho em resumo

1. **Novo projeto**: escolhe o ficheiro da música (Guitar Pro, PDF/imagem da tab, ou um link
   do Songsterr) e a gravação, e atribui as pistas Lead/Rhythm.
2. **Partitura**: ouve a gravação com as notas por cima e acerta a sincronização. Quando bater
   certo, marca cada pista como sincronizada.
3. **Tons**, **Letra**, **Capa**: o que quiseres acrescentar (nada disto é obrigatório).
4. **Aplicar e reconstruir** sempre que mudares algo — só a reconstrução grava as mudanças no
   PSARC.
5. **Exportar**: confirma o "Antes de usar", carrega em **Instalar no jogo** (ou descarrega o
   PSARC) e toca.

Nada é inventado em silêncio: o que a aplicação não sabe ou não consegue fazer aparece como
aviso.

## 2. Antes de começar

- **Arrancar:** no Windows, `start.bat` (atualiza, instala o que falta e abre a página), ou o
  `rockforge.exe`, que abre numa janela própria.
- **O que está instalado:** ⚙️ **Definições → Software** mostra cada ferramenta externa, se está
  instalada e o que perdes sem ela. Só o **ffmpeg** é obrigatório. Para um **PSARC jogável** é
  preciso o **Wwise** (sem ele sai só o bundle para o DLC Builder); para separar instrumentos,
  detetar tom ou letra e usar "Corrigir daqui", o extra de ML.
- **Para a música aparecer no jogo:** o Rocksmith precisa do **patch de CDLC**
  (`D3DX9_42.dll` na pasta do jogo). Indica a pasta do jogo em ⚙️ **Definições → Geral →
  Pasta do Rocksmith 2014** para a aplicação o confirmar e para "Instalar no jogo" funcionar.
- **Idioma:** PT/EN no topo da página inicial, ou em Definições → Geral.
- **Fechar:** fechar a janela/separador desliga o RockForge. Se houver uma construção a meio,
  espera que termine.

## 3. A página inicial

- Cada **projeto** é um cartão com capa, título, artista e um estado: pronto, em curso, com
  erro, "Sincronizada" (quando marcaste todas as pistas) ou "Tons standard".
- Filtros (**Todos / Prontos / Em curso / Com erro**) e uma caixa de pesquisa.
- O primeiro cartão aceita um ficheiro Guitar Pro arrastado: abre o assistente já com ele.
- No topo: **Lote (álbum)**, **Novo projeto** e ⚙️ **Definições**.

## 4. Criar um projeto (Novo projeto)

Quatro passos; a barra da esquerda mostra onde estás e deixa voltar atrás.

### Passo 1 — Ficheiro

Uma de três origens:

- **Ficheiro Guitar Pro**: GP3, GP4, GP5 ou GP7/GP8 (`.gp`). As notas, trastes, técnicas,
  tempo, compassos e secções vêm exatamente do ficheiro. Só o GP6 (`.gpx`) não é lido —
  exporta-o como GP5 ou GP7 no Guitar Pro/TuxGuitar.
- **PDF ou imagem da tablatura** (PNG, JPEG, WebP): é convertida num GP5 pelo conversor do
  PDF-to-GP5. Vários ficheiros = uma pista cada, pela ordem (até 7). A leitura de imagens (OCR)
  é experimental: confere as notas e o ritmo na partitura depois de criar — os avisos indicam os
  compassos com o ritmo estimado pelo espaçamento, que são os primeiros a conferir.
- **Link do Songsterr** ("… ou importa a tab do Songsterr"): descarrega a tab e cria um GP5 com
  ela, letra incluída quando a tab a tem. As pistas de bateria e as notas de ornamento ficam de
  fora (a aplicação diz quantas). Só tabs publicadas.

Carrega em **Seguinte** para ver as pistas.

### Passo 2 — Pistas

Atribui uma pista do ficheiro a cada arranjo: **Lead**, **Rhythm**, **Combo**, e, se quiseres,
**Lead alternativo** / **Rhythm alternativo** (no jogo aparecem como LEAD 2 / RHYTHM 2). Basta
um. Deixa vazios os que a música não tem. Pistas de baixo ainda não são suportadas.

### Passo 3 — Gravação

- **A gravação** (o áudio da música). Se o ficheiro for um Guitar Pro 8 com o áudio lá dentro,
  "Usar o áudio que vem dentro do ficheiro GP" fica marcado — é a opção mais precisa, porque é
  o áudio com que o ficheiro foi sincronizado.
- **Não tens o áudio?** Cola o link de um vídeo do YouTube e carrega em **Descarregar o áudio**.
  Se o YouTube recusar, ver [Problemas comuns](#15-problemas-comuns). (Uso pessoal: descarregar
  vai contra os termos do YouTube.)
- **Início da música na gravação (s)**: o segundo em que se ouve a 1ª nota. Um valor aproximado
  chega — afina-se depois na partitura. Num GP8 sincronizado e no Songsterr vem preenchido.
- **Silêncio inicial (s)**: segundos de silêncio extra antes da música no jogo. 0 = nenhum.
- **Extra — sincronizar pelos tempos do Songsterr** (opcional): o Songsterr guarda o instante
  de cada compasso em vídeos do YouTube, marcado por pessoas. **Procurar vídeos**, escolhe um,
  e as notas seguem esse vídeo compasso a compasso. Duas condições: a gravação tem de ser o
  áudio **desse** vídeo (o link passa para "Não tens o áudio?" para o descarregares) e o
  ficheiro tem de ser a tab do Songsterr. Depois de importar do Songsterr no passo 1, isto
  vem feito: vídeo escolhido e áudio descarregado.

### Passo 4 — Detalhes

- **Título, Banda, Álbum, Ano.** Vêm do ficheiro ou das etiquetas do áudio quando existem.
- **Álbum, ano e capa → Procurar online**: lista resultados do iTunes e do MusicBrainz;
  escolhe o certo (ou "Sem capa"). Fan remixes e versões feitas por IA raramente lá estão.
- **Letra sincronizada → Procurar letra online** (LRCLIB): escolhe uma letra com tempos, ou
  nenhuma. Se o ficheiro GP já trouxer letra, nada é escolhido sozinho. Também podes carregar um
  ficheiro **LRC** ou **UltraStar TXT** (tem sempre prioridade).
- **Importar palm mute / slap / pop / tap**: desliga se não quiseres essas técnicas no chart.

**Criar CDLC** cria o projeto e começa a construção. Os tons e a capa podem ficar para depois.

## 5. A página do projeto

- **Barra de cima:** ← volta à página inicial; o título com **Editar info** e, depois de uma
  reconstrução, **Versão anterior**; o estado (clica para ir a Exportar); o número de
  alterações pendentes; **Aplicar e reconstruir**; **Descarregar**.
- **Barra da esquerda:** as páginas **Partitura**, **Tons**, **Letra**, **Capa**, **Exportar**,
  e **Definições** em baixo.
- Enquanto a construção corre, vês o progresso em Exportar; quando acaba, a Partitura abre
  sozinha.

### Aplicar e reconstruir

Tudo o que mudas (sincronização, notas, secções, tons, letra, afinação) fica **pendente**: vês
e ouves o resultado na partitura, mas o PSARC só muda quando carregas em **Aplicar e
reconstruir**. Cada reconstrução cria uma **versão nova** do projeto e pergunta se pode apagar
a anterior quando a nova ficar pronta. Se a reconstrução falhar, a anterior fica.

### A página Partitura

- **Transporte:** play/pausa (ou Espaço), tempo, velocidade (25–100 %) e **Áudio ▾**:
  - volumes da música e das notas, **Tique por nota**;
  - **Fonte de áudio**: a mistura completa; **«pista» (sintetizada)**, as notas dessa pista
    tocadas sozinhas e limpas, boas para conferir a sincronização de cada pista;
    **Voz (sintetizada)**, a melodia em que a letra do GP é cantada; e, depois de
    **Separar instrumentos** (Demucs, demora minutos), as faixas separadas. A faixa "guitarra"
    junta todas as guitarras: Lead e Rhythm não se separam da gravação;
  - **Testar tom**: ouve as notas com o carácter de um tom teu (aproximação — o som real só
    existe no jogo).
- **Separadores das pistas:** com os nomes que o jogo lhes dá (LEAD, RHYTHM, COMBO, LEAD 2…).
  Ficam **verdes** quando marcas a pista como sincronizada.
- **Modo ▾**: o que acontece ao clicar numa nota (ver secções 6 e 7). **Notas ▾**: copiar,
  colar, apagar, desfazer, limpar edições. **Encaixar**: a grelha para onde as notas arrastadas
  saltam (compasso, tempo, ½, ¼, tercina, ou o cursor).
- **A partitura:** o eixo é o tempo da gravação. Clicar no fundo move o cursor. Os compassos
  têm número; um compasso a âmbar tem o andamento alterado pelas tuas correções.
- **Braço** mostra o braço da guitarra; **Pista 3D** mostra as notas a descer como no
  Rocksmith (segue também as correções ainda por aplicar). **− / + / Repor**: zoom.
- **Inspetor (à direita):** **Sincronização**, **Secções** e **Letra**.

## 6. Sincronizar as notas com a gravação

Faz por esta ordem, numa pista de cada vez (em cima, no inspetor **Sincronização**):

### Passo 1 — Início da música

O segundo em que se ouve a 1ª nota **desta pista**. Três maneiras:

- escrever o valor (ou usar o deslizador);
- pôr o cursor onde a nota soa e carregar em **= cursor**;
- **Detetar 1ª nota**: clica no botão, depois na onda onde a 1ª nota soa, e por fim nessa nota.

### Passo 2 — Andamento

Se a partitura se vai afastando por igual ao longo da música (o ficheiro foi escrito num BPM
ligeiramente diferente), muda o **BPM**. As notas deslizam sobre a onda em tempo real.
**Repor GP** volta ao andamento do ficheiro.

### Passo 3 — Correções na partitura

Para o que sobra, escolhe um modo em **Modo ▾** e clica onde a partitura foge:

| Modo | O que faz |
|---|---|
| **Corrigir daqui** (recomendado) | Ouve até a partitura começar a fugir e clica nessa nota. Fica tudo o que está antes no sítio, e o RockForge mede o andamento da gravação daí em diante e estica só o resto. Repete ao longo da música. |
| **Arrastar** | Arrasta uma nota para onde deve tocar. Com várias notas selecionadas, movem-se em bloco. Alt ao arrastar = sem encaixe. |
| **Marcar** | Dá play e clica na nota no momento em que a ouves: ela vai para o cursor. |
| **Excerto** | Desenha uma caixa sobre um trecho e move-o em bloco. |
| **Mover seguintes** | Esta nota e todas as seguintes vão para o cursor; as anteriores ficam. |
| **Alinhar compasso** | Clica numa nota ou na linha de um compasso: encosta esse compasso ao cursor (**= cursor**), ao mesmo compasso de outra pista (**= pista**), ou muda o BPM desse compasso até outro (**Andamento**). |

As correções ficam na lista do passo 3 (podes escrever o tempo exato de cada uma ou apagá-la)
até **Aplicar e reconstruir**. Uma correção marcada "⚠ cruza a anterior" contradiz outra e
tem de ser corrigida antes de reconstruir.

### Marcar como sincronizada

Quando a pista bate certo com a gravação, em **Estado da sincronização** carrega em **Marcar
esta pista como sincronizada**: o separador fica verde. Com todas marcadas, o projeto conta
como sincronizado. Um ficheiro sincronizado no Guitar Pro 8 ou pelos tempos do Songsterr deve
já bater certo, mas só tu o confirmas, a ouvir.

### Várias pistas

- **Pista principal:** escolhe uma; o que acertares nela passa para as outras com a mesma
  diferença de tempo (se a Lead passa de 0 para 1 s, uma pista que estava nos 30 s passa para
  31 s). Cada pista pode ainda ser acertada sozinha.
- **Aplicar a sincronização a todas as pistas:** aplica o mesmo andamento e as mesmas correções
  a todas.
- **Sincronizar por compasso** (em Mais opções): alinha um compasso ao cursor ou ao mesmo
  compasso de outra pista — útil para uma pista que só entra a meio.

### Mais opções

- **Silêncio inicial**: empurra música e notas para a frente.
- **Recarregar ficheiro GP**: depois de corrigires uma nota no Guitar Pro e exportares de novo.
  Mantém sincronização, tons, letra e afinação. Se o ficheiro novo trouxer áudio, passa a ser
  essa a gravação.
- **Guardar os ajustes → Exportar / Importar**: guarda início, andamento, correções, afinação e
  letra num JSON, para não os refazer se recriares o projeto.

## 7. Editar notas e secções

### Selecionar

Clique = uma nota; **Shift+clique** = um intervalo; **Ctrl+clique** = junta ou tira uma nota;
clique no fundo = limpa a seleção. O modo **Excerto** seleciona com uma caixa.

### Editar notas (modo ✏️ Editar notas)

- Clica numa nota: muda corda, traste, sustain, técnicas (hammer-on, pull-off, harmónico, palm
  mute, vibrato, tapping, slap, pop, acento), bend e slide; **Guardar** ou **Remover nota**.
- **Duplo-clique** num espaço vazio insere uma nota (corda pela altura do clique, tempo na
  grelha mais próxima). Só se podem pôr notas dentro dos compassos que o ficheiro tem.
- Uma nota editada e ainda não reconstruída tem um anel tracejado.

### Apagar, copiar, colar

- **Delete** (ou **Apagar** / Notas ▾ → **Apagar seleção**) apaga as notas selecionadas.
  **Ctrl+Z** desfaz o último apagar.
- **Ctrl+C / Ctrl+V** (ou Notas ▾): copia a seleção e cola-a no cursor, nesta pista ou noutra.
- Notas ▾ → **Limpar esta pista / Limpar em todas** descarta as edições de notas.

### Secções (intro, verso, refrão…)

Servem para a navegação e o Riff Repeater. No inspetor **Secções**: **+ Adicionar no cursor**,
ou o modo **Secção** e um clique numa nota. O nome e o tempo editam-se na lista.

### Levar as edições para o Guitar Pro

Em Exportar: **Guitar Pro com as notas editadas** cria um GP5 novo só com a pista atual, tal
como está no RockForge (os tempos são arredondados à grelha de compassos; a aplicação diz
quanto). **Guitar Pro com os andamentos corrigidos** escreve só as mudanças de andamento numa
cópia do teu ficheiro, que fica com todas as pistas.

## 8. Tons

Sem tons teus, cada pista leva o **tom standard** do DLC Builder (Lead e Combo: Marshall Plexi;
Rhythm: Orange AD50), e a aplicação diz "Tons standard".

### Criar ou editar um tom

**Criar / editar tons** abre o editor: **+ Novo tom**, escolhe amplificador, cabine e efeitos,
roda os botões (arrasta, escreve o valor, ou duplo-clique para o valor de origem). **Volume:
maior = mais alto** (0,1–36). **Guardar tom**.

- **Biblioteca**: guarda um tom (★) para o usares noutros projetos; **Carregar** copia-o para
  este.
- **Tons das tuas músicas**: lê a pasta `dlc` do Rocksmith e lista os tons de todas as tuas
  músicas (oficiais e CDLC), com pesquisa por artista e por palavras. **Usar neste projeto**
  copia um tom.

### Que tom toca cada pista

Em **Tons de cada pista**:

- **Mesmos tons em todas as pistas**, ou desmarca para cada pista ter os seus (escolhe a pista
  nos separadores);
- **Tom base**: o tom com que a pista começa;
- **Tons para onde pode trocar** (máx. 4 — o limite do jogo);
- **Mudanças de tom**: na partitura, modo **Mudança de tom** e clica na nota onde a troca deve
  acontecer.

É isto que vai para o jogo, depois de **Aplicar e reconstruir**.

### Detetar o tom e as sugestões

- **Detetar tom** separa a guitarra (Demucs, minutos) e classifica o carácter do som (limpo,
  crunch, distorcido), propondo presets do catálogo do jogo ordenados pela semelhança. Não
  identifica o amplificador real.
- **Sugestões por secção** propõe um tom para cada parte de cada pista (limpo, rhythm, lead),
  pela gravação e pelo que a pista toca. Uma sugestão **não muda nada** até carregares em
  **Aplicar a esta pista** ou **Aplicar a todas as pistas**. Em cada linha podes trocar o tom
  sugerido por um teu (do projeto, da biblioteca ou dos teus PSARC); escolher "(o sugerido)"
  desfaz a troca.

## 9. Letra

A letra pode vir:

- **do ficheiro GP** (ou do Songsterr): cada sílaba na sua nota, e segue as tuas correções de
  sincronização;
- **do LRCLIB**: **Procurar letra online** → **Usar** numa letra com tempos;
- **da gravação**: **Detetar letra na gravação** (WhisperX; experimental, demora minutos);
- de um ficheiro LRC/UltraStar, ou escrita à mão.

**Acertar à gravação:** se a letra está toda adiantada ou atrasada, **1ª palavra = cursor** ou
−/+. Se sai do tempo a meio, **Sincronizar com a gravação** mede na voz da gravação o tempo de
cada palavra (as palavras ficam as que estão; precisa do extra de ML).

**Palavras:** a tabela edita texto, tempo, duração e fim de linha (é o fim de linha que faz o
jogo mudar de linha). **Exportar LRC** guarda a letra; **Voltar à letra da pauta** troca o que
está no editor pela letra do ficheiro GP.

**Ao lado da partitura:** no inspetor **Letra**, clica numa palavra na partitura para a acertar
sem mudar de página: **Daqui em diante = cursor** (a palavra vai para o cursor e as seguintes
acompanham), **Só esta = cursor**, ◀ ▶, −/+.

## 10. Capa e informação da música

- **Capa:** arrasta uma imagem JPG/PNG, ou **Procurar capa online** e escolhe um resultado
  (pode também preencher o álbum e o ano). Vai para o PSARC na próxima reconstrução.
- **Editar info** (barra de cima): título, artista, álbum, ano; e as pistas e afinações do
  Guitar Pro. Mudar só o texto não reconstrói; mudar pistas ou afinação reconstrói.

## 11. Exportar, verificar e instalar no jogo

### Antes de usar

Uma lista do que falta ou pode correr mal, cada linha com um botão para o resolver:

- **PSARC jogável** (precisa do Wwise);
- **PSARC verificado**: confere o ficheiro contra as regras cuja falha já fez o jogo fechar ou
  esconder a música. Não substitui tocar a música;
- **Tons**, **Capa**, **Sincronização** (confirma cada pista, ou **Está sincronizada**),
  **Letra**;
- **AppID / propriedade**: o PSARC usa o AppID de uma DLC que o jogador tem de possuir.

Nada é bloqueado: podes descarregar na mesma.

### Descarregar

- **PSARC para o jogo**: o ficheiro a pôr na pasta `dlc` do Rocksmith.
- **Bundle DLC Builder**: XML, áudio e projeto `.rs2dlc` para abrir no DLC Builder
  (Open project), se quiseres acabar lá.

### Instalar no jogo

**Instalar no jogo** copia o PSARC para `dlc\RockForge\` na pasta do jogo e apaga a cópia de
uma versão anterior da mesma música que o RockForge lá tenha posto. Ficheiros que puseste lá à
mão nunca são apagados (a aplicação avisa se a música ficaria repetida). Com o jogo aberto a
cópia pode falhar: fecha-o e tenta de novo.

### Opções da construção

Afinação (com **Detetar afinação** na gravação), importar palm mute / slap / tap, e
**Dificuldade dinâmica** (desliga para uma única dificuldade com todas as notas, se o DD der
problemas numa música).

## 12. Um álbum de uma vez (Lote)

**Lote (álbum)** cria vários projetos de uma vez: escolhe vários ficheiros GP e as gravações.
Cada GP fica com a gravação do mesmo nome (`faixa1.gp5` ↔ `faixa1.mp3`), ou pela ordem quando
os nomes não batem; um GP8 com áudio dentro não precisa de gravação. Banda, álbum e ano são
partilhados. As pistas Lead/Rhythm são escolhidas pelo nome; confere-as depois em **Editar
info** de cada projeto.

## 13. Definições

- **Geral**: idioma; pasta do Rocksmith 2014.
- **Software**: o que está instalado, o que falta e o comando para instalar.
- **Python ML**: só no `.exe` — o caminho de um Python 3.11 com `rockforge[ml,lyrics]`, para o
  `.exe` poder separar instrumentos e detetar tom e letra.
- **Stems**: o motor de separação (Demucs; Banquet em testes).
- **Volume**: o volume alvo da música no jogo (LUFS). −12 por defeito; −10/−9 se ficar baixo ao
  lado do DLC oficial; −16 é o mais limpo.
- **GPU**: se a GPU deu um erro, o RockForge passa para a CPU; **Reativar GPU** depois de
  corrigires os drivers.

## 14. Atalhos de teclado

Na partitura, fora de campos de texto:

| Tecla | Faz |
|---|---|
| Espaço | play / pausa |
| ← / → (Shift = passo maior) | recua / avança |
| Home | vai ao início |
| + / − | zoom |
| Shift+clique · Ctrl+clique | seleciona um intervalo · junta ou tira uma nota |
| Delete | apaga a seleção |
| Ctrl+Z | desfaz o último apagar |
| Ctrl+C · Ctrl+V | copia a seleção · cola no cursor |
| Alt (a arrastar) | sem encaixe |
| Esc | fecha um menu ou popup |

## 15. Problemas comuns

| Problema | O que ver |
|---|---|
| A música **não aparece** no jogo | O patch de CDLC (`D3DX9_42.dll`) está na pasta do jogo? (Definições → Software.) O AppID usado é de uma DLC que tens? O PSARC está em `dlc` (ou `dlc\RockForge`)? |
| Só sai o bundle, **sem PSARC jogável** | Falta o Wwise (2019/2021/2022/2023) — Definições → Software. |
| As notas fogem da música | Secção 6: início, depois BPM, depois "Corrigir daqui". Num ficheiro que não é exatamente a gravação (outra versão, compassos a mais), a correção tem de ser no próprio ficheiro. |
| O YouTube recusa o download | Instala o solucionador e um motor JavaScript: `pip install -U "yt-dlp[default]"` e `winget install DenoLand.Deno`, e reinicia. Se pedir sessão, escolhe **firefox** em "Sessão do browser" (a do Chrome não se lê no Windows). Ou carrega tu o MP3 do vídeo. |
| O Songsterr diz que a tab não está publicada | Só tabs publicadas podem ser lidas; escolhe outra tab da mesma música. |
| Erro de certificado ao procurar letra, capa ou Songsterr | Confirma a data e hora do PC, o antivírus (análise de HTTPS) e `pip install --upgrade certifi`. |
| "Detetar letra/tom" ou "Separar instrumentos" não fazem nada | Falta o extra de ML (Definições → Software). No `.exe`, indica um Python em Definições → Python ML. Na CPU demora vários minutos. |
| Mudei algo e o jogo não mudou | Carregaste em **Aplicar e reconstruir** e instalaste a versão nova? Em Exportar, "No jogo está uma versão anterior" quer dizer que não. |
| A reconstrução falhou | A mensagem fica em Exportar; a versão anterior mantém-se. Uma nota fora dos compassos do ficheiro, ou correções de sincronização que se cruzam, são as causas mais comuns. |
| O som está baixo ou com ruído no jogo | Definições → Volume (volume alvo); no editor de tons, o Volume (maior = mais alto), o ganho do amplificador e o noise gate. |
