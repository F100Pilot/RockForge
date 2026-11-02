# Novidades

**English:** [CHANGELOG.en.md](CHANGELOG.en.md)

As alterações de cada versão. As entradas também vão em inglês, no `CHANGELOG.en.md`.

## [Por lançar]

## [0.12.0 beta 2] — 2026-11-02

### Novidades

- **Slides no editor de notas, à vista e a ouvir:** na pop-up de uma nota (modo **Editar notas**), **Slide para** tem agora **Slide até ao traste** ou **Slide sem altura (para fora)**, e **Dura (s)** escolhe quanto tempo demora a deslizar — mais curto do que o sustain, a nota chega ao traste e fica a soar lá até ao fim (uma nota de slide ligada a uma nota mantida, como no Rocksmith). **Ligar à nota seguinte** faz uma nota continuar na seguinte da mesma corda sem palhetar. Na partitura, o slide é uma linha até ao fim do sustain com o traste de chegada (tracejada quando é sem altura), e as notas da pré-visualização e a fonte sintetizada deslizam até à altura de chegada.
- **Mais afinações, e uma personalizada:** em **Editar info**, a afinação de cada pista tem agora C# Standard, B Standard, Drop A#, Drop A, Double Drop D, DADGAD, Open D, Open G, Open E, Open C e Open A, e **Personalizada…**, que mostra uma nota para cada corda para escolheres qualquer afinação. Quando importas um PDF, o passo 2 do assistente diz que afinação foi lida em cada pista — uma tab que não a imprime fica em standard.
- **Fim da música:** na Partitura → Sincronização → Mais opções, **Fim da música** escolhe o segundo da gravação em que o jogo acaba a música (**= cursor** marca-o onde está o cursor). Vazio, a música vai até ao fim da gravação. Nunca acaba antes da última nota.

### Correções

- **LRC com tempo em cada palavra:** um LRC que traz o tempo de cada palavra (`[00:41.81]<00:41.81>She's <00:42.30>got …`) mostrava "<00:41.81>She's" na letra e espalhava as palavras por igual pela linha. Agora cada palavra começa no seu tempo e dura até à seguinte (ou até ao tempo que fecha a linha), e uma sílaba separada por um tempo fica ligada à palavra. Vale para um LRC carregado, escolhido no assistente ou encontrado online. Um projeto criado com um destes LRC mostra a letra certa depois de atualizar; reconstrói para a levar ao jogo.
- **Um projeto só de baixo em A220 não reconstruía:** com o baixo escrito em A220 (escolhido em Editar info, ou sozinho numa afinação abaixo de −4 meios-tons), qualquer **Aplicar e reconstruir** era recusado com "cent_offset … greater than or equal to -50": o desvio da afinação era lido do baixo como −1200, que é a forma de escrever o A220, e não um desvio da gravação. Agora lê-se o desvio da gravação, e o A220 mantém-se.
- **O Rocksmith fechava ao tocar certas músicas:** duas notas na mesma corda a menos de 30 ms uma da outra (um slide rápido para a nota em que acaba, uma tercina de fusas num andamento rápido) eram juntas num "acorde" com uma ligação e um slide que não apontavam para nada, e o jogo fechava ao carregar em tocar. Dependia do andamento, por isso parecia ligado a uma mudança de tempo num compasso em /8. Agora são duas notas ligadas, como no DLC Builder, e o **Verificar PSARC** assinala um PSARC antigo com esta falha. Para um projeto já criado, basta reconstruir.
- **A música acabava 1 segundo depois da última nota:** no jogo, a música parava 1 segundo depois da última nota da pista, mesmo que a gravação continuasse (um final só com outras guitarras, um fade, um solo de bateria). Agora vai até ao fim da gravação, ou até ao **Fim da música** que escolheres. Para um projeto já criado, basta reconstruir.
- **"Usar" um tom detetado depois de outro podia impedir a reconstrução:** cada "usar" punha todos os tons do projeto na lista de tons trocáveis, e com cinco ou mais o "Aplicar e reconstruir" era recusado ("Rocksmith supports at most 4 switchable tones"). Agora o tom escolhido toma o lugar do que substitui.
- **O baixo ficava com os tons de guitarra:** um arranjo de baixo sem tons próprios usava os tons do projeto — os detetados, que são de guitarra —, ou seja, um amplificador de guitarra no baixo. Agora o baixo só usa os tons de baixo do projeto, ou o tom de baixo standard, e a página dos Tons diz-te que os tons detetados não vão para o baixo. Os tons que escolheres para a pista de baixo continuam a ser dela.

## [0.12.0 beta 1] — 2026-11-01

### Novidades

- **Tocar com a guitarra (experimental):** na Partitura, **Tocar** abre um painel para ligar a guitarra — o Real Tone Cable do Rocksmith ou uma placa de som — e tocar a pista com a música, como no Rocksmith: cada nota solta fica marcada na partitura quando passa (verde certa e a tempo, amarelo certa mas cedo ou tarde com os milissegundos, vermelho a nota errada com a que se ouviu, tracejado falhada), e o painel conta as certas, as seguidas e se tocas em média cedo ou tarde. **Calibrar o atraso** mede, com 8 cliques, o atraso entre as colunas e a entrada da guitarra. Mostra também a nota que chega (serve de afinador) e pode mandar o som da guitarra para as colunas. Os **acordes** também contam: uma moldura à volta do acorde diz se foi a tempo ou errado, e marca a corda que estava noutro traste (com o traste que se ouviu) ou que não se ouviu. Conta o que está desenhado, também com a música mais lenta. Tudo corre no browser; nada sai do computador.
- **Metrónomo na Partitura:** no painel **Áudio ▾**, ao lado dos volumes da música e das notas, **Clique em cada tempo** liga um clique em cada tempo da partitura, como está desenhada — com as correções ainda por aplicar — e o 1.º tempo de cada compasso mais agudo; **Metrónomo** acerta o volume do clique. Ouve-se logo se a grelha de compassos bate com a música. A escolha e o volume ficam guardados neste browser.
- **Faixa do metrónomo nas Barras de áudio:** com o metrónomo ligado, as **Barras de áudio** ganham, entre os ataques da gravação e as notas, uma faixa com um traço por tempo — verde quando um ataque da faixa de cima (a bateria separada, por exemplo) cai nesse tempo, laranja quando o ataque mais perto está fora, cinzento sem ataque perto. A faixa diz quantos tempos batem com um ataque e se a grelha está adiantada ou atrasada em relação ao som (a mediana, em ms), e a linha de alinhamento, com o rato por cima, diz também a distância do tempo mais perto ao seu ataque.
- **Notas da pista 3D como no Rocksmith:** as notas são transparentes, só com o contorno da cor da corda (e o número do traste), e chegam inclinadas 30° (os acordes, com a sua moldura, e as cordas soltas vêm sempre na horizontal): nos últimos 3 segundos rodam devagar, no sentido dos ponteiros do relógio, até ficarem na horizontal no instante em que tocam a corda.
- **Slides na pista 3D com curva:** o rasto de um slide sai da nota e chega à nota seguinte com uma
  curva pequena, em vez de uma esquina.
- **Palm mute na pista 3D:** em vez do laço por cima da nota, uma cruz translúcida da cor da corda,
  de canto a canto dentro da nota (também quando a nota fica na corda e na barra de uma corda solta).
- **Baixo em A220:** em **Editar info**, ao lado da afinação do baixo, **Referência de afinação do baixo** escolhe **A220 (afinação grave)**, **A440 (padrão)** ou **Automático**. Em A220 o baixo fica escrito uma oitava acima, com a referência a 220 Hz — o mesmo som, que o jogo deteta melhor numa afinação grave — e o afinador do jogo pede A220. Até aqui só acontecia sozinho abaixo de −4 meios-tons (o que continua a fazer em **Automático**); agora serve também, por exemplo, para Drop C ou D Standard. Em **A440** uma afinação abaixo de −4 fica como está, com um aviso de que o jogo pode não detetar as notas mais graves.

### Correções

- **Painel Áudio cortado num ecrã estreito:** numa janela estreita (760 px), o painel **Áudio ▾** da Partitura abria a sair pela esquerda e os controlos do lado esquerdo ficavam fora de alcance. Agora os menus ficam sempre dentro da coluna e da janela.

## [0.11.1 beta 5] — 2026-10-22

### Correções

- **Acordes com atraso a tocar na Partitura:** o som de cada nota era feito no momento em que tocava, no próprio fio da página, e num acorde sustentado isso parava a pauta dezenas de milissegundos — o acorde saía atrasado e o cursor dava um salto. Agora as notas dos segundos seguintes são preparadas antes, em segundo plano, e cada uma é agendada para o instante exato da gravação — antes saía quando o ecrã reparava que a nota tinha passado, em média 19 ms depois. E um acorde de seis cordas só soava as três primeiras: agora soam todas.
- **Letra cada vez mais desfasada (tabs do Songsterr e ficheiros GP):** uma nota ligada (prolongada) da linha da voz recebia uma sílaba, e cada ligadura empurrava todas as palavras seguintes uma nota. Numa letra escrita como uma só linha, sem pontos onde recomeçar, as palavras acabavam dezenas de segundos fora do sítio, e a "Voz (sintetizada)" com elas. Agora uma nota ligada não recebe sílaba, como no Songsterr. Num projeto já criado: página Letra → **Voltar à letra da pauta** e depois **Aplicar e reconstruir**.
- **Início da música (Partitura → Sincronização):** o valor pode ser escrito diretamente. Antes, cada tecla aplicava o número e o campo reescrevia-se logo, por isso era quase impossível escrever um valor. Agora escreves o segundo (com vírgula ou ponto, ou em minutos, 1:02.5) e carregas Enter. ↑/↓ acertam 0,01 s (Shift 0,1 s, Alt 0,001 s) e Esc desiste. Os botões **−**/**+** ao lado dão o ajuste fino: 1 ms por clique (Shift 10 ms, Alt 100 ms), e repetem enquanto estiverem carregados.
- **Letra das tabs do Songsterr presa às notas da guitarra:** o Songsterr mostra a letra por cima de todas as pistas, por isso o texto pode vir na pista da guitarra. Quando vinha, as sílabas seguiam as notas da guitarra em vez das da voz e ficavam à espera sempre que a guitarra parava, o que atrasava a letra. Agora seguem a pista de voz sempre que a tab tem uma, e o aviso da importação diz quando isto acontece. Um projeto já criado guarda o ficheiro antigo: importa a tab outra vez, num projeto novo.

## [0.11.1 beta 4] — 2026-10-21

### Novidades

- **Duas pistas** (Partitura, por baixo da pauta): mostra outra pista por baixo da partitura, no mesmo eixo do tempo. Seleciona notas numa delas — uma a uma ou com uma caixa — e passa-as (ou copia-as) para a outra, exatamente onde estavam, mesmo que as duas pistas tenham correções de sincronização diferentes. Com afinações diferentes, o traste muda para o som ficar o mesmo. Fica pendente até "Aplicar e reconstruir" e Ctrl+Z desfaz.
- **Acertar pelos ataques** (Partitura → Sincronização → Início da música): compara as notas com os ataques da gravação e move a pista inteira pela diferença — para uma pista toda adiantada ou atrasada a mesma quantidade, como acontece com os tempos de alguns vídeos do Songsterr. Recusa adivinhar quando o ritmo é tão regular que há dois encaixes possíveis, e avisa quando a diferença cresce ao longo da música (aí é o andamento). Fica pendente até "Aplicar e reconstruir".
- **Capa de qualquer sítio:** no passo 4 do assistente e na página Capa, **Ou de outro sítio** abre uma pesquisa no Google Imagens com a banda e o álbum (ou o título) e aceita o link da imagem que lá encontrares, de qualquer site público, ou a própria imagem colada com Ctrl+V. WebP, GIF e outros formatos são convertidos para PNG. Só são descarregadas imagens de sites públicos: um link para dentro da tua rede ou do teu computador é recusado.

### Correções

- **Letra das tabs do Songsterr atrasada:** uma nota de ornamento (grace) na linha vocal não recebia sílaba, e cada sílaba a seguir caía uma nota mais tarde, cada vez mais atrasada ao longo da música. Agora uma nota de ornamento recebe a sua sílaba, como no Songsterr e no Guitar Pro (também em ficheiros GP7/GP8). As notas de ornamento das tabs do Songsterr passam a vir no ficheiro, em vez de serem descartadas. Um projeto já criado guarda o ficheiro antigo: importa a tab outra vez, num projeto novo.

## [0.11.1 beta 3] — 2026-10-21

### Correções

- **Partitura, braço e pista 3D a tocar adiantados:** durante a reprodução, o cursor e as notas acesas iam à frente do que se ouve, pelo atraso da saída de som do computador (dezenas de milissegundos com colunas ou auscultadores com fio, algumas centenas com Bluetooth). Uma pista certa parecia ter as notas adiantadas, e acertá-la a olho deixava-a atrasada no jogo. Agora o que se vê acompanha o que se ouve; a pausa para onde se estava a ouvir.
- **Braço da guitarra:** clicar numa nota da partitura acende só essa nota no braço. Antes, a nota anterior também ficava acesa quando as duas estavam a menos de 0,16 s uma da outra (uma nota curta ficava acesa esse tempo mínimo, mesmo depois de a seguinte começar).
- **Tabs do Songsterr — passo 3:** depois de importar uma tab do Songsterr, escolher outro ficheiro no passo 1 (um GP teu ou um PDF) já não leva consigo os tempos dessa tab, do vídeo nem o áudio dele. Se ir buscar os vídeos ao Songsterr falhar, o assistente diz que falhou (em vez de dizer que não há vídeos) e deixa tentar de novo em «Procurar vídeos». Uma transferência do áudio do vídeo que acabe depois de escolheres o andamento da tab já não passa a ser a gravação. Uma mudança de andamento numa posição do compasso que o RockForge não sabe ler passa a ser avisada.

## [0.11.1 beta 2] — 2026-10-21

### Novidades

- **Partitura:** sem nenhum modo escolhido, clicar numa nota leva o cursor a essa nota, e o braço mostra-a e escolhe-a ("Todas as notas").
- **Sincronização:** o início da música, as correções, as secções, as mudanças de tom, a letra e o silêncio inicial passam a ajustar-se ao milissegundo (três casas decimais).
- **Pista 3D — bends:** um bend passa a ver-se em verde-água. O rasto da nota sobe seguindo o bend (subir, segurar, soltar, pré-bend) e, quando a nota chega às cordas, sobe na corda à medida que é dobrada, até uma moldura tracejada na altura que o bend tem de alcançar — um tom sobe um espaço de corda.
- **Marcar a ouvir — cada ataque:** um novo modo, "Toco em cada ataque", marca com a tecla B cada palhetada que ouves, sem mexer na partitura. Os toques ficam a verde por cima da pauta e guardados com o projeto, por pista; a partitura mostra as notas sem toque e os toques sem nota, com "Diferença anterior/seguinte". Para corrigir, "Ataques marcados" em "Encaixar em" leva as notas que arrastas ou acrescentas para os toques, e "Encaixar as notas selecionadas nos toques" leva cada nota ou acorde ao toque mais perto. Pedido de Liam.

### Correções

- **Tabs do Songsterr — sincronização:** uma tab importada do Songsterr perdia as casas decimais do andamento (117,85 BPM ficava 117) e as mudanças de andamento a meio do compasso, por isso começava certa e ia-se afastando da gravação. Agora as notas seguem o andamento da própria tab, compasso a compasso, como no leitor do Songsterr. No passo 3 escolhes com que gravação vais tocar — o MP3 do Songsterr (ou outra que siga a tab) ou o áudio de um vídeo do YouTube — e cada opção diz com que gravação bate; se carregares um ficheiro teu com os tempos de um vídeo, aparece um aviso.
- **Pasta de trabalho mudada de sítio:** depois de mover a pasta de dados do RockForge (para outro disco ou outro computador), os projetos antigos deixavam de encontrar o bundle, a gravação, o ficheiro GP e os stems. No arranque, o RockForge passa a procurá-los na pasta nova.
- **Songsterr:** um vídeo cujas marcações começam antes do início do vídeo (uma contagem marcada em tempos negativos) era recusado ao criar o projeto. Agora é aceite, e cada compasso fica na sua marcação. Contribuição de mongrelx (#5).
- **Arranjo sem notas:** quando a pista GP escolhida para um arranjo não tem notas (uma pista de voz, de bateria ou vazia), o erro diz agora qual arranjo e qual pista, e o que fazer, em vez de só "arrangement has no notes".
- **Braço — "Só as iguais à escolhida":** sem nenhuma nota escolhida, mostrava todas as notas do braço. Agora só aparecem as equivalentes à nota escolhida (no braço ou clicada na partitura), e nada até escolheres uma.

## [0.11.1 beta 1] — 2026-10-20

### Novidades

- **Braço — Todas as notas:** um novo interruptor ao lado de "Braço" mostra o nome de todas as notas da afinação da pista. Clica numa nota para ver onde mais está o mesmo som e a mesma nota noutra oitava. Podes mostrar o nome com ou sem a oitava, e só as notas iguais à escolhida ou só as naturais.
- **Tons:** já podes mudar o tempo em que um tom entra. Arrasta a marca laranja da mudança na partitura, escreve os segundos na lista "Tons de cada pista", ou põe o cursor no sítio e carrega em "= cursor".

### Correções

- **Lote (álbum):** os projetos criados em lote voltam a trazer os palm mutes e as notas abafadas da partitura. Com as versões mais recentes de uma das bibliotecas da app, perdiam-se sem aviso.
- **Secções:** as secções que editaste passam a acompanhar uma correção de sincronização feita antes da mesma reconstrução, como as mudanças de tom. Antes, as notas mudavam de sítio e a secção ficava no tempo antigo. "+ Adicionar no cursor" põe a secção exatamente onde o cursor está, mesmo com uma correção pendente.
- **Tons:** uma mudança de tom passa a acompanhar uma correção de sincronização feita antes da mesma reconstrução. Antes, as notas mudavam de sítio e a troca ficava no tempo antigo.
- **Rocksmith:** duas músicas cujos nomes começam pelas mesmas 30 letras (por exemplo, duas versões ao vivo) já não se substituem uma à outra no jogo, e o mesmo para títulos sem letras latinas (cirílico, japonês…). Atenção: estas músicas mudam de identificador ao serem reconstruídas e o jogo começa o progresso delas do zero. As músicas de nome curto não mudam.

## [0.11.0 beta 4] — 2026-10-18

### Correções

- **Projetos e ficheiros:**
  - Uma pista chamada "Lead/Rhythm" já não vai para os dois arranjos (a construção falhava).
  - Um ficheiro .gp bloqueado no Guitar Pro é recusado com uma mensagem, em vez de um erro interno.
  - Um projeto novo recusado já não deixa a gravação esquecida no disco.
  - Não se apaga um projeto enquanto corre uma deteção ou separação nele.
- **Partitura importada:**
  - Um slide de entrada no traste 1 já não transforma uma nota anterior num slide de segundos.
  - Os trilos guardam a dedilhação e o slide final.
  - O capo já não leva alvos de slide para lá do traste 24.
  - Uma linha de letra GP7 num compasso que nunca toca já não aparece no início.
- **Exportar para Guitar Pro:**
  - Notas muito rápidas na mesma corda já não estragam o ficheiro.
  - O arredondamento do BPM já não acumula desvio, e o andamento de compassos sem notas já não se perde.
  - Uma correção de andamento ganha a um andamento deixado noutra pista.
- **Letras:**
  - As sílabas UltraStar da mesma palavra ficam ligadas.
  - Uma linha LRC com vários tempos é cantada em cada um.
- **DLC Builder:** o bend de meio tom e o acorde todo abafado passam a ser escritos no XML.
- **Versões:** ao apagar a versão anterior, os instrumentos separados só passam para uma versão que usa a mesma gravação, e as versões irmãs continuam a encontrá-los.
- **Transferências:** duas transferências do pacote ao mesmo tempo já não o estragam.
- **Tons:** um tom com valores inválidos é recusado logo, em vez de fazer falhar a construção.
- **Windows:** etiquetas ou caminhos em japonês ou cirílico já não fazem falhar a construção.
- **.exe:**
  - Sem WebView2, volta a desligar-se quando se fecha o separador do browser.
  - A instalação dos componentes já não fica parada para sempre num download que encrava.
- **Editor:**
  - A seleção de notas e o ↑/↓ já não passam para a outra pista.
  - Abrir outro projeto depressa já não mostra a partitura ou a gravação do anterior.
  - A pista 3D fechada enquanto carrega já não arranca.

## [0.11.0 beta 3] — 2026-10-18

### Novidades

- **Juntar duas pistas: escolhe os compassos** (Novo projeto → Pistas, e Editar info). Uma grelha
  com os compassos da música diz quais entram no arranjo; por defeito, só os compassos em que o
  arranjo não tem notas — assim um LEAD com poucas notas recebe as partes do RHYTHM só onde está
  calado. Clica, arrasta ou Shift+clique para escolher. Experimental.

### Correções

- **Mover notas e acordes sem estragar o andamento.** Para mudar notas de sítio usava-se o modo
  "Arrastar", que é uma ferramenta de sincronização: cada arrasto estica o tempo à volta, muda o
  BPM dos compassos e não deixa uma nota passar a outra. Agora, em **Editar notas**, arrastar uma
  caixa no espaço vazio (ou Ctrl+clique) seleciona um acorde ou várias notas, e arrastar uma delas
  move-as todas — podem passar por outras notas e o andamento não muda. O "Arrastar" diz o que
  faz e avisa quando uma nota tenta passar a vizinha.
- **O que mudavas durante uma deteção já não se perde.** Enquanto corria "Detetar letra",
  "Detetar tom" ou "Separar instrumentos", uma capa carregada, "Marcar como sincronizada", a pista
  principal, os tons trocados ou "Instalar no jogo" eram desfeitos pela linha de progresso seguinte.
- **No .exe, a deteção de letra funciona.** Falhava sempre, ao fim de minutos de separação.
- **Um título ou artista com acento ("Canção", "Beyoncé") já tem .psarc** quando o Wwise está
  instalado. O nome interno da música passa a ser só letras sem acento (as músicas com acento
  ganham um novo nome interno; reinstala-as no jogo).
- **Editar uma nota já não lhe tira o slide**, nem a curva do bend, a ligação à nota seguinte ou a
  dedilhação. Colar notas também mantém o slide.
- **As ferramentas de sincronização já não dobram a partitura** quando usadas depois de acertar o
  "Início": "Arrastar", "Marcar", "Mover seguintes", "Corrigir daqui" e "Marcar a ouvir" fixam o
  início e o fim da música. Antes, as notas a seguir perdiam o acerto e a reconstrução podia falhar
  com "beats must be in chronological order"; agora, se uma correção dobrar o tempo, a mensagem diz
  em que ponto.
- **O encaixe "Cursor" funciona** (levava as notas para o último tempo da música).
- **"Guitar Pro com as notas editadas" mantém o capo.**
- **"Verificar PSARC" já não acusa falha** numa música com slap, pop ou tap.
- **Uma capa recusada (grande demais ou que não é imagem) já não apaga a capa que havia.**
- **Um projeto (.rfproj) ou ficheiro de sincronização com um valor errado é recusado** a dizer qual,
  em vez de deitar abaixo a página inicial.
- **Ficheiros GP7/8 com um piano (duas pautas) antes da guitarra** já leem a pista certa.

## [0.11.0 beta 2] — 2026-10-18

### Novidades

- **Juntar duas pistas num só arranjo** (Novo projeto → Pistas, e Editar info): para uma parte que
  o ficheiro dividiu em duas pistas — o Songsterr faz isto muitas vezes com um só guitarrista — as
  notas da segunda pista entram no arranjo escolhido. Têm de ter a mesma afinação e o mesmo capo;
  onde as duas tocam a mesma corda ao mesmo tempo, fica a nota do arranjo.
- **Barras de áudio: uma linha para ver se estão alinhadas.** Com o rato por cima das barras ou
  da partitura, uma linha desce pelas duas faixas e as barras dizem quanto a nota mais próxima está
  antes ou depois do ataque ("Nota 20 ms antes do ataque", verde quando bate). **Ctrl + roda do
  rato** faz zoom onde está o rato.

## [0.11.0 beta 1] — 2026-10-18

### Novidades

- **Contar as instalações, só se disseres que sim**: a página inicial pergunta uma vez se a
  instalação pode contar, para se saber quantas pessoas usam o RockForge (o GitHub só mostra
  downloads). Envia, uma vez por versão, um número ao acaso, a versão, o tipo de instalação e o
  sistema — nada sobre ti nem sobre as tuas músicas, e o endereço IP não é guardado. Desliga-se
  em Definições → Geral → **Contar esta instalação**, e o que foi enviado é apagado.
- **Exportar e importar o projeto** (Exportar → **Projeto RockForge (.rfproj)**; página inicial →
  **Importar projeto**): o projeto inteiro num ficheiro — a gravação, o ficheiro Guitar Pro, a
  capa, todas as correções e, se quiseres, os instrumentos separados — para o abrir noutro
  computador, guardar uma cópia ou enviá-lo a alguém. Ao importar fica um projeto novo, que é
  construído outra vez.
- **Barras de áudio por cima da partitura** (Partitura → **Barras de áudio**): uma faixa com a
  gravação e outra com o som das notas da pista, no mesmo eixo do tempo. Onde os picos das duas
  não caem juntos, a partitura está fora de tempo. As barras da gravação mostram os **ataques**
  — cada batida um pico estreito, mesmo numa guitarra distorcida — ou o **volume**, do que está
  a tocar, da mistura completa ou de um instrumento separado (a guitarra, o baixo… e, para os
  ataques, a bateria); as das notas seguem as correções ainda por aplicar. Ligadas sem nada
  separado, perguntam primeiro se queres separar os instrumentos (no fim passam para o da pista);
  **Cancelar** mostra o volume da mistura sem separar nem analisar nada.
- **Pista 3D: a zona da mão acende quando uma nota bate nas cordas**, como no Rocksmith — um
  retângulo com brilho à volta dos trastes onde está a mão (2–5, por exemplo), que fica aceso
  enquanto a nota soa.

## [0.10.0 beta 17] — 2026-10-18

### Novidades

- **Os tons importados de um texto aparecem num gráfico**, como o das sugestões por secção: em
  cada pista, uma faixa com o tom que soa em cada momento, as secções por baixo e, depois de
  **Detetar tom**, a distorção da gravação por cima, para comparares. Aparece ao ler a resposta e
  fica em **Tons de cada pista** depois de aplicar (também com os tons que marcas à mão); clicar
  numa parte leva o cursor para lá.

## [0.10.0 beta 16] — 2026-10-17

### Novo
- **Novidades depois de cada atualização:** ao abrir uma versão nova, a página inicial lista tudo
  o que mudou desde a versão que usaste da última vez — as mesmas entradas destas notas — até
  carregares em "Percebido". Em Definições → Geral → Sobre o RockForge, "Novidades desta versão"
  mostra-as de novo.
- **Selecionar do cursor até ao fim** (Notas ▾, ou Shift+End): todas as notas da pista daí até ao
  fim ficam selecionadas, e no modo "Arrastar" arrastar uma move-as todas. A pedido de um
  utilizador, para acertar a música do princípio para o fim.
- **Um só andamento** (Sincronização → Andamento): quando a partitura muda de andamento a meio e
  a gravação não, põe todos os compassos da pista no mesmo BPM, com o início no sítio.
- **Guia: sincronizar passo a passo**, numa tab que nunca foi sincronizada (andamento, primeiro
  compasso, e acertar ao longo da música).

### Corrigido
- **Arrastar uma seleção esticava as notas antes dela:** com outra correção pendente (por exemplo
  o "Início"), as notas entre essa correção e a seleção eram arrastadas aos poucos com ela, e as
  que vinham a seguir à seleção perdiam a correção. Agora só a seleção se move.

## [0.10.0 beta 15] — 2026-10-17

### Novo
- **Importar tons de um texto** (página Tons): "Copiar o pedido" prepara um pedido para o
  ChatGPT (ou outro assistente) com a música, as pistas, as secções com compassos e tempos e o
  equipamento do jogo; colas a resposta e "Ler a resposta" mostra os tons — amplificador, coluna,
  pedais, racks e as regulações — e onde entra cada um em cada pista, dito por compasso, secção ou
  tempo. Cada adaptação fica à vista (um equipamento lido como o mais parecido, um controlo fora
  dos limites, um tom a mais numa pista); "Aplicar" muda os tons como uma edição tua, com
  desfazer, e grava-se com "Aplicar e reconstruir".

## [0.10.0 beta 14] — 2026-10-17

### Novo
- **Estrela no GitHub:** um botão "Dar uma estrela" ao lado de "Paga-me um café" (e em
  Definições → Geral → Apoiar o projeto) abre o RockForge no GitHub. Depois do primeiro projeto
  construído, a página inicial pergunta uma vez, com discrição, se podes dar uma estrela — com
  "Agora não" (mais uma vez daqui a 30 dias) e "Não perguntar mais". Nada é enviado.

## [0.10.0 beta 13] — 2026-10-17

### Novo
- **Legenda da partitura:** o interruptor "Legenda" (ao lado de "Braço" e "Pista 3D") mostra o que
  quer dizer cada marca da partitura, desenhada como aparece — notas, anéis, caudas, compassos,
  secções, tons, correções, posição da mão, separadores das pistas e os ataques da gravação (as
  bolas e os traços laranja). O cartão "Ataques da gravação" mostra os seus quatro.
- **Sobre o RockForge** (Definições → Geral): a versão e que build dela está a correr (o commit,
  quando foi construída, como foi instalada), e **"Copiar informação para relatório"**, que põe na
  área de transferência o build, o sistema, o software externo encontrado e o fim do registo
  técnico, para um relatório de erro — sem palavras-passe, tokens nem o teu nome de utilizador.
- **Registo técnico** em `logs/` dentro da pasta de trabalho (`rockforge.log`, e
  `rockforge-worker.log` para um worker separado): cada linha com a hora, o nível e a parte da
  aplicação, em rotação para nunca passar de ~12 MB. Um erro inesperado passa a dar um id que podes
  citar, e o mesmo id está no registo. O nível é o `ROCKFORGE_LOG_LEVEL`.

### Alterado
- **Os números de versão seguem o Semantic Versioning**, `0.10.0-beta.13` e assim por diante, com
  as fases dev, beta, release candidate e estável e regras fixas para o que vem a seguir
  (`docs/VERSIONING.md`). Cada bug encontrado, cada correção e cada versão ficam registados com um
  identificador permanente em `tracking/` (`BUG_LOG.md`, `FIX_LOG.md`, `RELEASE_LOG.md`), com todo o
  histórico, e uma versão só é publicada se cumprir os critérios de lançamento
  (`docs/RELEASE_PROCESS.md`).
- A saída da consola do `.exe` passou para `logs/console.log`, com as três execuções anteriores
  guardadas; o `start.bat` guarda o `logs\worker.log` anterior como `worker.prev.log`.

### Corrigido
- **Pista 3D apanhava a roda do rato:** ao deslocar a página com o rato por cima da pista 3D, a
  roda passava a fazer zoom na pista. Agora a roda só mexe na câmara depois de clicares na pista;
  Esc ou um clique fora largam-na.
- **"Não tenho o Wwise" com o Wwise instalado:** a variável `WWISEROOT` que o Audiokinetic Launcher
  deixa no Windows aponta muitas vezes para outra versão (o 2024/2025), e o RockForge tomava-a como
  definitiva, sem procurar o 2023.1 instalado ao lado. Agora só a pasta escolhida por ti em
  Definições é definitiva. Uma conversão do Wwise que falha também já não diz "Wwise não
  encontrado": mostra o erro do próprio Wwise. E um .psarc sem som já não aparece como "PSARC
  jogável" em "Antes de usar".

## [0.10.0 beta 12] — 2026-10-17

### Novo
- **Editar notas — arrastar e mudar o traste com as setas:** no modo "Editar notas", arrasta uma
  nota para outro tempo ou outra corda; ↑/↓ sobem ou descem um traste à última nota clicada (com
  Ctrl, uma oitava), e ela soa. Com Shift, arrastar duplica a nota ou o acorde e leva a cópia. O fim da cauda de uma nota
  arrasta-se para mudar a duração (sustain).

### Corrigido
- **Uma nota apagada continuava a soar até reconstruir:** o clique das notas, a fonte "sintetizada"
  e o braço tocavam a partitura como foi construída. Agora tocam o que está no ecrã, com as
  edições por aplicar.
- **Inserir uma nota num solo criava um acorde:** a nota nova encaixava no tempo inteiro mais
  perto, que num solo rápido é o da nota anterior. Agora encaixa no máximo em semicolcheias (com
  Alt, livre).
- **"Início da música" depois da sincronização automática:** mudar o início só ajustava o
  primeiro troço da música. Agora desloca a pista inteira, com as correções que já lá estavam.

## [0.10.0 beta 11] — 2026-10-17

### Corrigido
- **Acordes "pintados" de cima a baixo no jogo:** um acorde com cordas soltas e sem sustain (um
  power chord 0-0-0 numa afinação drop, por exemplo) ia sem as notas de acorde que o jogo usa para
  o desenhar, e aparecia como um bloco de cor sólido. Agora vai como o DLC Builder o escreve.
  A verificação do PSARC (Exportar → "Antes de usar") aponta o problema num PSARC antigo — basta reconstruir.

## [0.10.0 beta 10] — 2026-10-16

### Novo
- **Pista 3D com câmara livre:** arrasta para rodar a vista até 120° para cada lado e de rente à
  pista (0°) até vista de cima (90°); a roda do rato aproxima ou afasta e um duplo clique repõe.
  Os mesmos eixos estão em "Câmara", e a vista fica guardada.
- **Ataques da gravação — escolher o instrumento:** "Medir em" escolhe um instrumento separado
  (por omissão a guitarra, e o baixo na pista Bass) ou a mistura. Sem instrumentos separados,
  pede confirmação antes de medir na mistura. Num instrumento separado, os restos baixinhos dos
  outros (que a separação deixa) já não aparecem como ataques falsos.

### Corrigido
- **Ataques da gravação com "Silêncio inicial":** num projeto com silêncio inicial, os ataques
  apareciam atrasados nesse tempo, e notas sincronizadas ficavam entre os traços. A
  sincronização automática tinha o mesmo desvio.
- **Recarregar ficheiro GP com o áudio do ficheiro:** a guitarra separada e a deteção de tons da
  gravação antiga já não passam para a nova versão (descreviam outra gravação).

## [0.10.0 beta 9] — 2026-10-16

### Novo
- **Ataques da gravação** (inspetor Sincronização): marca por cima da pauta onde a gravação tem
  ataques e realça as diferenças com a tab — notas sem ataque perto e ataques fortes sem nota —,
  com «Diferença anterior/seguinte» para lá chegar. Para tabs com o ritmo errado. Mede no stem
  de guitarra quando os instrumentos já foram separados, senão na mistura. Diz quando se toca,
  não que notas; não muda nada na partitura.

### Corrigido
- **As notas longas soam o tempo todo na pré-escuta**: o som das notas no editor (o toque de cada
  nota e a fonte «sintetizada») tocava todas as notas como uma palhetada curta, mesmo as
  sustentadas. Agora cada nota dura a sustentação que se vê na pauta; as curtas soam como antes.

## [0.10.0 beta 8] — 2026-10-16

### Alterado
- **O aviso «Há uma versão nova» chega mais depressa**: a app pergunta ao GitHub no máximo uma vez
  por hora (era uma vez por dia), e uma página que fica aberta volta a perguntar de hora a hora.

### Corrigido
- **Uma capa do teu computador logo ao criar o projeto**: o passo 4 do «Novo projeto» só deixava
  escolher um resultado da pesquisa online ou «Sem capa». Agora também aceita uma imagem JPEG ou
  PNG do computador, que vai na primeira construção (antes, só na página Capa, depois de criar).
- **No `.exe`, a GPU nunca era usada**: a app perguntava ao próprio `.exe` se havia uma GPU, e
  o `.exe` não traz o PyTorch (está no Python dos componentes extra) — por isso a separação de
  stems e a deteção de tons e de letra corriam sempre no CPU, mesmo com uma NVIDIA. Agora a
  pergunta é feita ao Python dos componentes.

## [0.10.0 beta 7] — 2026-10-15

### Novo
- **Sincronizar automaticamente, com andamento variável — experimental** (inspetor
  Sincronização): analisa a gravação e leva cada compasso para onde as suas notas soam, deixando o
  andamento mudar ao longo da música. Mantém os tempos da partitura (não lê a música ao dobro ou à
  metade), fica como correções pendentes que se desfazem com um Ctrl+Z, e lista os compassos a
  verificar de ouvido (os que vêm depois de uma pausa e os que não bateram certo). Pode errar:
  testado em gravações sintéticas, ainda não em músicas reais.
- **Ícone próprio**: uma palheta de guitarra laranja com uma bigorna e uma faísca. Aparece no
  `.exe`, na barra de tarefas, nos atalhos, no instalador e no separador do browser.

### Corrigido
- **Nenhum modo vem selecionado ao entrar num projeto.** O «Corrigir daqui» estava ligado por
  omissão, e o primeiro clique numa nota re-temporizava a música; agora um clique só seleciona ou
  move o cursor até escolheres um modo.
- **O ecrã preto que piscava ao clicar em alguns botões no `.exe`**: era a janela de consola de
  cada programa que a app corre por trás (ffmpeg, o Python dos componentes extra, yt-dlp…). Passam
  todos a correr sem janela.
- **O Wwise instalado mas «não detetado»**: o RockForge procura agora também em qualquer disco
  (até duas pastas abaixo da raiz, como `I:\Rocksmith\Wwise_…`) e no `WWISEROOT` que o
  instalador do Wwise grava no registo, e quando há um Wwise que não serve diz qual é e porquê —
  o Audiokinetic Launcher instala por omissão a versão mais recente (2024/2025), e só o 2019–2023
  converte o áudio (como no DLC Builder). Antes dizia só «ROCKFORGE_WWISE_ROOT não está
  definido».
- **Notas curtas sem rasto de sustentação**: cada colcheia e semicolcheia saía com a duração
  escrita no Guitar Pro como sustentação, por isso o jogo desenhava um rasto atrás de todas as
  notas de um riff. Agora, como nos charts feitos à mão, só uma nota de um tempo ou mais tem
  sustentação, a não ser que o rasto faça falta (slide, nota ligada, bend, vibrato, let ring,
  tremolo, trilo).
- **As casas (1.ª/2.ª vez) no regresso de um D.C./D.S.**: as repetições já não se repetiam nesse
  regresso, mas a 1.ª casa tocava outra vez antes da 2.ª. Agora segue a convenção habitual — sem
  repetições e só a última casa — e, como um ficheiro Guitar Pro não diz qual se pretende, o
  aviso do projeto diz que foi essa a assumida.

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
