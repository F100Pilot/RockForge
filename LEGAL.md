# Aviso legal · Legal notice

[Português](#português) · [English](#english)

> Isto não é aconselhamento jurídico. Descreve o que o RockForge faz, o que não
> faz e o que fica a cargo de quem o usa.
>
> This is not legal advice. It describes what RockForge does, what it does not
> do, and what is up to the person using it.

---

## Português

### Sem ligação à Ubisoft

O RockForge é um projeto independente e gratuito, feito por entusiastas. **Não
tem qualquer ligação à Ubisoft**, nem é aprovado ou patrocinado por ela.
"Rocksmith" e "Rocksmith 2014" são marcas da Ubisoft Entertainment. Neste
projeto são usadas apenas para dizer com que jogo os ficheiros funcionam.
Outras marcas que aparecem na aplicação pertencem aos respetivos donos: nomes
de amplificadores e pedais, Guitar Pro, Songsterr, YouTube, DLC Builder, Wwise.

### O que o RockForge é, e o que não contém

O RockForge é uma **ferramenta de autoria**, como o EOF ou o DLC Builder.
Converte o que lhe dás num arranjo jogável: um ficheiro Guitar Pro e uma
gravação.

O repositório e os executáveis **não contêm**:
- músicas, gravações, tablaturas nem letras de ninguém;
- áudio, notas, texturas nem executáveis da Ubisoft;
- o Wwise.

O que contém para os ficheiros carregarem no jogo é o que as ferramentas
públicas da comunidade publicam há mais de dez anos, todo listado com a origem
em `THIRD_PARTY_NOTICES.md`:
- as duas chaves AES do formato PSARC/SNG;
- o esquema `.flat`;
- a tabela de glifos da letra;
- o catálogo de equipamento.

Servem apenas a interoperabilidade: escrever ficheiros que o jogo saiba ler.

### O que fica a cargo de quem usa

- **Direitos de autor.** Uma gravação, uma composição, uma tablatura e uma
  letra são obras protegidas. Criar um CDLC para tocar em casa, com uma música
  que compraste, é uma coisa. **Distribuir** um CDLC que contém uma gravação
  protegida, sem autorização de quem tem os direitos, é distribuição não
  autorizada, seja qual for a ferramenta que o criou. Usa o RockForge com
  material teu, livre ou para o qual tens autorização. Se partilhares, a
  responsabilidade é tua.
- **O jogo.** Para o Rocksmith 2014 carregar CDLC é preciso:
  - um patch da comunidade (CDLC Enabler);
  - possuir o DLC oficial cujo AppID o ficheiro indica. Por defeito é Train,
    "Drops of Jupiter"; pode ser trocado por outro DLC que possuas, por exemplo
    Smashing Pumpkins, "Cherub Rock".

  Os termos de utilização do jogo aplicam-se a ti.
- **Wwise.** Cada utilizador instala-o pelo Audiokinetic Launcher e aceita a
  licença da Audiokinetic. O RockForge apenas chama a cópia instalada.

### Serviços online

O RockForge só contacta um serviço quando carregas no botão que o faz — com uma
exceção: para saber se há uma versão nova, pergunta às Releases do GitHub no
máximo uma vez por hora, sem enviar nada sobre ti nem sobre as tuas músicas
(desliga-se em Definições → Geral). E, **só se disseres que sim**, conta a
instalação: uma vez por versão envia um número ao acaso criado pela instalação, a
versão, o tipo de instalação e o sistema (Windows/macOS/Linux) a um servidor do
projeto (Supabase), que não guarda o endereço IP; ao desligar em Definições →
Geral, o número é esquecido e o que foi enviado é apagado. Os componentes extra do `.exe` vêm do NuGet,
do PyPI, do PyTorch e do GitHub, só quando os instalas. Os termos de cada
serviço aplicam-se a quem faz o pedido.

- **Songsterr.**
  - A importação de tablaturas e os tempos por compasso usam a API não
    documentada que o leitor do próprio Songsterr usa. Pode deixar de funcionar
    a qualquer momento.
  - As tablaturas do Songsterr são licenciadas pelas editoras. Usa-as para
    uso pessoal.
  - **Não redistribuas as tablaturas importadas nem o ficheiro GP5 que o
    RockForge gera a partir delas.**
- **YouTube** (através do yt-dlp, um extra opcional). Os termos do YouTube não
  permitem descarregar fora das funcionalidades do próprio YouTube. Serve só
  para obter, para uso pessoal, o áudio do vídeo a que os tempos do Songsterr
  pertencem.
- **LRCLIB, iTunes, MusicBrainz / Cover Art Archive, Google Imagens e qualquer
  site cujo link de imagem coles.**
  - As letras continuam a ser obras protegidas.
  - As capas pertencem aos detentores dos respetivos direitos, encontres-as onde
    as encontrares.
  - Servem para o teu projeto, não para redistribuir.

### Sem garantia

O RockForge é fornecido "tal como está", sem garantia de qualquer tipo (ver
`LICENSE`). Um ficheiro que o jogo não leia, uma conta suspensa por um serviço
ou um problema com o teu jogo não são responsabilidade dos autores.

### Se és titular de direitos

Se achas que alguma coisa neste repositório viola direitos teus, abre uma
*issue* ou contacta o dono do repositório. O pedido será analisado de boa-fé e,
se tiver fundamento, o conteúdo será corrigido ou retirado.

---

## English

### Not affiliated with Ubisoft

RockForge is an independent, free project made by enthusiasts. **It is not
affiliated with, endorsed or sponsored by Ubisoft.** "Rocksmith" and
"Rocksmith 2014" are trademarks of Ubisoft Entertainment. Here they are used
only to say which game the files work with. Other names in the app belong to
their owners: amp and pedal names, Guitar Pro, Songsterr, YouTube, DLC Builder,
Wwise.

### What RockForge is, and what it does not contain

RockForge is an **authoring tool**, like EOF or DLC Builder. It turns what you
give it into a playable arrangement: a Guitar Pro file and a recording.

The repository and the executables **do not contain**:
- anyone's songs, recordings, tabs or lyrics;
- Ubisoft audio, note data, textures or executables;
- Wwise.

What it does contain, so the files load in the game, is what the community's
public tools have published for over a decade, all listed with its origin in
`THIRD_PARTY_NOTICES.md`:
- the two PSARC/SNG AES keys;
- the `.flat` schema;
- the lyric glyph table;
- the gear catalogue.

It serves interoperability only: writing files the game can read.

### What is up to you

- **Copyright.** A recording, a composition, a tab and lyrics are protected
  works. Making a CDLC to play at home with a song you bought is one thing.
  **Distributing** a CDLC that contains a copyrighted recording, without the
  rights holder's permission, is unauthorised distribution, whatever tool made
  it. Use RockForge with your own, free or licensed material. If you share,
  the responsibility is yours.
- **The game.** For Rocksmith 2014 to load CDLC you need:
  - a community patch (CDLC Enabler);
  - to own the official DLC whose AppID the file names. The default is Train,
    "Drops of Jupiter"; it can be swapped for one you own, e.g. Smashing
    Pumpkins, "Cherub Rock".

  The game's terms apply to you.
- **Wwise.** Each user installs it through the Audiokinetic Launcher and
  accepts Audiokinetic's licence. RockForge only invokes the installed copy.

### Online services

RockForge contacts a service only when you press the button that does it — with
one exception: to know whether a new version is out, it asks GitHub's Releases
at most once an hour, sending nothing about you or your songs (turned off in
Settings → General). And, **only if you say yes**, it counts the install: once
per version it sends a random number the install made up, the version, the kind
of install and the system (Windows/macOS/Linux) to a server of the project
(Supabase), which does not keep the IP address; turning it off in Settings →
General forgets the number and deletes what was sent. The `.exe`'s extra components come from NuGet, PyPI,
PyTorch and GitHub, only when you install them. Each service's terms apply to
whoever makes the request.

- **Songsterr.**
  - Tab import and per-measure times use the undocumented API Songsterr's own
    player uses. It can stop working at any time.
  - Songsterr's tabs are licensed from publishers. Use them for personal use.
  - **Do not redistribute imported tabs or the GP5 file RockForge writes from
    them.**
- **YouTube** (through yt-dlp, an optional extra). YouTube's terms do not allow
  downloading outside YouTube's own features. It is there only to get, for
  personal use, the audio of the video the Songsterr times belong to.
- **LRCLIB, iTunes, MusicBrainz / Cover Art Archive, Google Images and any site
  whose image link you paste.**
  - Lyrics are still protected works.
  - Covers belong to their rights holders, wherever you find them.
  - They are for your project, not for redistribution.

### No warranty

RockForge is provided "as is", without warranty of any kind (see `LICENSE`).
A file the game will not read, an account suspended by a service, or a problem
with your game is not the authors' responsibility.

### If you hold rights

If you believe something in this repository infringes your rights, open an
issue or contact the repository owner. The request will be looked at in good
faith and, if well founded, the content corrected or removed.
