# Investigação 04 — Wwise (licenciamento), Songsterr e CDLC.ai

Data: 2026-06-11. Idioma: pt-PT. Cada facto está marcado com fonte e nível de confiança
(Facto verificado / Inferência / Não verificado).

---

## 1. Audiokinetic Wwise — licenciamento e redistribuição

### 1.1 O que a EULA permite redistribuir

- A EULA da Wwise (texto integral de uma cópia pública do `LICENSE.txt` incluída num jogo
  open-source) distingue entre o **"Deployment Software"** (bibliotecas runtime + headers,
  em código-objeto) e a **aplicação de authoring**. Apenas o Deployment Software pode ser
  redistribuído, e só **embebido num jogo desenvolvido pelo licenciado** ("Licensee
  Developed Game"). [Fonte: https://github.com/etodd/lasercrabs/blob/master/external/wwise/LICENSE.txt]
  — Facto verificado (texto de EULA real, embora possa ser de versão antiga).
- A EULA proíbe explicitamente distribuir "the AUDIOKINETIC Wwise Technology, or any
  portion thereof, in stand-alone form". Ou seja, **não é permitido empacotar a ferramenta
  de authoring nem o conversor de linha de comandos (WwiseConsole/WwiseCLI) dentro de uma
  aplicação de terceiros**. [Fonte: https://github.com/etodd/lasercrabs/blob/master/external/wwise/LICENSE.txt]
  — Facto verificado (para essa versão da EULA); Inferência ao extrapolar para a versão atual,
  mas é consistente com tudo o que o ecossistema CDLC faz (todas as ferramentas exigem que o
  utilizador instale o Wwise por si).
- A licença é "worldwide, paid-up, nonexclusive, non-transferable", não pode ser
  sublicenciada, e está ligada a um projeto/título específico; partilhar ou transferir a
  licença de projeto viola o Master License Agreement. [Fonte: https://github.com/etodd/lasercrabs/blob/master/external/wwise/LICENSE.txt ; https://www.audiokinetic.com/en/licensing/faq/]
  — Facto verificado (EULA) / Não verificado no detalhe (a página FAQ da Audiokinetic devolve
  403 a fetch automatizado; o resumo vem de excertos de pesquisa).

### 1.2 Uso automatizado / server-side

- A EULA analisada **não contém cláusulas explícitas** sobre uso em servidor, cloud ou
  automatizado; o âmbito do license grant é "uso interno durante o desenvolvimento" de um
  jogo, com distribuição limitada ao jogo final com o runtime embebido. Usar o
  WwiseConsole num backend SaaS para converter áudio de utilizadores **não está coberto
  pelo grant** e seria, na melhor interpretação, uma zona cinzenta; na pior, uma violação
  (uso fora do "Licensee Title" registado, sem possibilidade de sublicença).
  [Fonte: https://github.com/etodd/lasercrabs/blob/master/external/wwise/LICENSE.txt]
  — Facto verificado quanto à ausência de cláusulas nesse texto; Inferência quanto à
  conclusão jurídica (não somos advogados; seria preciso contactar a Audiokinetic).

### 1.3 Nível gratuito

- Desde 1 de abril de 2022 existe a **licença Indie gratuita**: acesso completo à
  plataforma, **sem limite de assets/sons**, para projetos com orçamento total de produção
  **inferior a 250 000 USD**. Exige registo do projeto no site da Audiokinetic e aprovação
  (1–2 dias úteis); suporte é pago à parte e não há acesso ao código-fonte completo.
  [Fonte: https://blog.audiokinetic.com/en/free-wwise-indie-license/ ; https://blog.audiokinetic.com/en/free-wwise-for-indie-developers/ ; https://www.gamedeveloper.com/audio/wwise-audio-middleware-is-now-free-to-use----within-limits]
  — Facto verificado.
- Importante: esta licença gratuita é **por projeto de jogo** ("Licensee Title"), não uma
  licença genérica para usar o conversor em qualquer pipeline. Usá-la para alimentar um
  serviço de conversão para terceiros não corresponde ao caso de uso previsto.
  — Inferência (a partir dos termos acima).

### 1.4 Como as ferramentas CDLC do Rocksmith integram o Wwise

- O **Rocksmith 2014 DLC Builder** (iminashi/Rocksmith2014.NET) **exige que o utilizador
  instale o Wwise 2019, 2021, 2022 ou 2023** (apenas o pacote "Authoring") e usa-o para
  converter áudio para `.wem`. No Windows, localiza a instalação via **variável de ambiente
  `WWISEROOT`** (definível pelo Wwise Launcher) ou no caminho por omissão em Program Files;
  o caminho do executável de consola também pode ser definido manualmente na configuração.
  [Fonte: https://github.com/iminashi/Rocksmith2014.NET/blob/main/samples/DLCBuilder/README.md]
  — Facto verificado (README lido diretamente).
- No **Linux, o DLC Builder usa Wine para executar o executável de consola do Wwise**
  ("Wwise console executable", i.e. `WwiseConsole.exe`); foi testado com ficheiros do
  Wwise 2022 copiados de uma instalação Windows. O README não nomeia literalmente
  "WwiseConsole.exe", apenas "the Wwise console executable".
  [Fonte: https://github.com/iminashi/Rocksmith2014.NET/blob/main/samples/DLCBuilder/README.md]
  — Facto verificado.
- O toolkit clássico (rscustom/rocksmith-custom-song-toolkit) tem a mesma abordagem: o
  ficheiro `RocksmithToolkitLib/Ogg/Wwise.cs` invoca a CLI do Wwise instalada pelo
  utilizador; o mecanismo documentado na issue #85 é criar um projeto Wwise temporário e
  correr `WwiseCLI.exe projeto.wproj -GenerateSoundBanks` (nas versões recentes do Wwise o
  executável passou a chamar-se `WwiseConsole.exe`).
  [Fonte: https://github.com/rscustom/rocksmith-custom-song-toolkit/blob/master/RocksmithToolkitLib/Ogg/Wwise.cs ; https://github.com/rscustom/rocksmith-custom-song-toolkit/issues/85]
  — Facto verificado (comando citado na issue); a mudança de nome WwiseCLI→WwiseConsole é
  Inferência a partir do README do DLC Builder e da documentação Wwise.
- O CustomsForge mantém uma página "Wwise Builds for Rocksmith CDLC" (builds/instruções de
  instalação do Wwise para criadores de CDLC) — ou seja, a comunidade aponta os utilizadores
  para instalarem o Wwise oficial, e não distribui o conversor embebido.
  [Fonte: https://ignition4.customsforge.com/tools/wwise] — Não verificado em detalhe
  (página devolve 403 a fetch automatizado; só título/descrição via pesquisa).

### 1.5 Existe encoder open-source de .wem compatível com Rocksmith?

- **Não foi encontrado nenhum encoder open-source capaz de CRIAR .wem (Wwise Vorbis)**.
  Tudo o que existe em open source é no sentido inverso (descodificação):
  - **ww2ogg** (hcs64) converte Wwise RIFF/RIFX Vorbis → Ogg Vorbis (com
    `packed_codebooks_aoTuV_603.bin` + `revorb`). [Fonte: https://github.com/hcs64/ww2ogg]
    — Facto verificado.
  - **WolvenKit/wwise-audio-tools**: biblioteca + CLI **wem → ogg** (sucessor moderno de
    ww2ogg/revorb); não codifica. [Fonte: https://github.com/WolvenKit/wwise-audio-tools]
    — Facto verificado.
  - Portas do ww2ogg em Rust e .NET — todas só descodificam.
    [Fonte: https://lib.rs/crates/ww2ogg ; https://libraries.io/nuget/Ww2Ogg.Core] — Facto verificado.
  - **sound2wem** (EternalLeo) parece "converter qualquer áudio para .wem", mas é apenas um
    script wrapper que **exige a instalação do Wwise** (pede para instalar Wwise e FFmpeg na
    primeira execução). [Fonte: https://github.com/EternalLeo/sound2wem] — Facto verificado.
  - A issue #85 do toolkit ("Generate WEM files in toolkit") ficou "on hold" sem nenhuma
    solução independente do Wwise. [Fonte: https://github.com/rscustom/rocksmith-custom-song-toolkit/issues/85]
    — Facto verificado.
- O formato está documentado pela comunidade (templates `W2013_wem_format.bt`, wiki "Wwise
  audio file format"), o que mostra que o *parsing* é conhecido, mas a codificação Wwise
  Vorbis (codebooks empacotados, granularidade própria) nunca foi reimplementada em aberto.
  [Fonte: https://github.com/rscustom/rocksmith-custom-song-toolkit/wiki/Wwise-audio-file-format]
  — Facto verificado quanto à documentação; Inferência quanto ao motivo.
- Conclusão prática: **a única via para gerar .wem compatível com Rocksmith continua a ser
  o WwiseConsole oficial instalado pelo utilizador** (nativamente ou via Wine). — Inferência
  forte, consistente com todas as fontes acima.

---

## 2. Songsterr — o que oferece realmente

- O Songsterr é um site de tablaturas (guitarra, baixo, bateria) com reprodução síncrona.
  **As tabs são contribuídas por utilizadores**: a própria ajuda do site afirma que "all
  tabs are contributed by users" e que "Songsterr doesn't do the transcriptions themselves";
  a submissão é feita por upload de ficheiros **Guitar Pro**.
  [Fonte: https://www.songsterr.com/help] — Facto verificado (texto citado em resultados de
  pesquisa; a página devolve 403 a fetch direto automatizado).
- **Novidade (≈2025–2026)**: o Songsterr lançou uma funcionalidade de **geração automática de
  tabs por IA** ("Generate Tabs with AI", página /new), para subscritores premium: o
  utilizador cola um link do YouTube (ou gravação própria) e recebe tabs geradas para
  guitarra, baixo e bateria, que deve rever antes de publicar.
  [Fonte: https://www.songsterr.com/new ; https://www.talkbass.com/threads/songsterr-recently-released-an-automated-ai-tab-writing-feature.1667303/ ; https://www.heise.de/en/news/Songsterr-uses-AI-to-create-fairly-accurate-guitar-tabs-from-your-own-recordings-10356152.html]
  — Facto verificado (múltiplas fontes independentes), embora os detalhes exatos do plano
  premium não tenham sido confirmados diretamente (403 no site).
- **Separação de stems**: o Songsterr **não oferece separação de stems como produto** (não
  há download de stems). A crença do utilizador está parcialmente certa apenas no sentido
  técnico: pipelines de transcrição automática como o do Songsterr tipicamente usam
  separação de fontes (p.ex. htdemucs de 6 stems) como passo interno antes da deteção de
  notas — mas o Songsterr não documenta publicamente o seu pipeline interno nem expõe stems
  ao utilizador. [Fonte: https://audio2guitar.com/blog/best-free-ai-guitar-tab-generators-2026 (descrição genérica de pipelines) ; https://www.songsterr.com/new]
  — A ausência de produto de stems: Inferência bem suportada; o uso interno de htdemucs
  pelo Songsterr especificamente: **Não verificado** (não há divulgação oficial).
- Resumo: o Songsterr é, na essência, um **site de tabs feitas por humanos**, agora com um
  gerador de tabs por IA (premium, a partir de YouTube/gravações) — **não é um serviço de
  separação de stems**. — Inferência consolidada das fontes acima.

---

## 3. CDLC.ai — existe e o que afirma

- **O serviço existe**: cdlc.ai apresenta-se como "AI-powered Rocksmith 2014-compatible
  DLC builder". [Fonte: https://cdlc.ai/] — Facto verificado quanto à existência (aparece em
  pesquisa com título e descrição oficiais); **o site bloqueia fetch automatizado (HTTP 403)**,
  pelo que os detalhes abaixo vêm apenas de snippets de pesquisa.
- Afirmações do serviço (segundo a meta-descrição/snippets do site e FAQ):
  - O utilizador carrega uma faixa "que possui ou tem direitos sobre" e o serviço trata de
    **transcrição, metadados e empacotamento num .psarc** pronto para Rocksmith 2014.
    [Fonte: https://cdlc.ai/] — Facto verificado (snippet oficial); Não verificado em detalhe.
  - **Transcrição de baixo** disponível, e geração de **guitarra lead e rhythm** anunciada
    como "live" — escolhe-se o instrumento ao carregar/editar a faixa.
    [Fonte: https://cdlc.ai/ ; https://cdlc.ai/faq] — Não verificado (apenas snippets).
  - Recomenda **FLAC sem perdas** para máxima precisão de transcrição.
    [Fonte: https://cdlc.ai/faq] — Não verificado (snippet).
  - A FAQ cobre "supported audio formats, exports, revisions, and the CDLC.ai workflow".
    [Fonte: https://cdlc.ai/faq] — Não verificado (apenas meta-descrição).
- **Stack técnico / modelos**: nenhuma divulgação encontrada (nem nos snippets, nem em
  artigos de terceiros). — Não verificado / sem dados.
- **Preços**: não foi possível obter (site bloqueado a fetch; nenhuma fonte terceira com
  preços encontrada). — Não verificado / sem dados.
- **Como resolve o problema do .wem/Wwise**: não divulgado publicamente nos materiais
  acessíveis. Dado que gerar .psarc exige áudio .wem, ou usam Wwise no servidor (questão
  de licenciamento — ver secção 1.2) ou outra técnica não divulgada. — Não verificado;
  Inferência quanto ao dilema.
- **Feedback da comunidade**: pesquisas dirigidas a Reddit e CustomsForge por "cdlc.ai"
  **não devolveram qualquer discussão, análise ou avaliação de qualidade**. Não há
  evidência pública de adoção ou de qualidade dos resultados. — Facto verificado quanto à
  ausência de resultados nas pesquisas efetuadas (2026-06-11); pode existir discussão não
  indexada.

---

## O que não foi possível verificar

1. O texto **atual** da EULA/Master License Agreement da Wwise no site da Audiokinetic —
   audiokinetic.com devolve 403 a fetch automatizado; a análise baseia-se numa cópia
   pública da EULA (repositório lasercrabs) e em excertos das FAQs via pesquisa. A posição
   da Audiokinetic sobre uso server-side/automatizado do WwiseConsole teria de ser
   confirmada diretamente com a empresa.
2. As páginas songsterr.com/help, /new e /about diretamente (403); o conteúdo foi obtido
   via snippets de pesquisa e fontes secundárias (TalkBass, heise, BassBuzz).
3. Se o Songsterr usa internamente separação de stems (e qual modelo) no seu gerador de
   tabs por IA — não há divulgação oficial.
4. Todo o detalhe do CDLC.ai além de snippets: preços, modelos/stack, qualidade real dos
   .psarc gerados, como produzem .wem, quem opera o serviço. O site bloqueia fetch
   automatizado e não existe feedback comunitário indexado (CustomsForge/Reddit).
5. A versão exata do executável ("WwiseConsole.exe" vs "WwiseCLI.exe") usada pelo DLC
   Builder — o README diz apenas "Wwise console executable"; a issue #85 do toolkit antigo
   documenta `WwiseCLI.exe <proj>.wproj -GenerateSoundBanks`.

## Fontes principais

- https://github.com/etodd/lasercrabs/blob/master/external/wwise/LICENSE.txt
- https://www.audiokinetic.com/en/licensing/faq/
- https://blog.audiokinetic.com/en/free-wwise-indie-license/
- https://blog.audiokinetic.com/en/free-wwise-for-indie-developers/
- https://www.gamedeveloper.com/audio/wwise-audio-middleware-is-now-free-to-use----within-limits
- https://github.com/iminashi/Rocksmith2014.NET/blob/main/samples/DLCBuilder/README.md
- https://github.com/rscustom/rocksmith-custom-song-toolkit/issues/85
- https://github.com/rscustom/rocksmith-custom-song-toolkit/blob/master/RocksmithToolkitLib/Ogg/Wwise.cs
- https://github.com/hcs64/ww2ogg
- https://github.com/WolvenKit/wwise-audio-tools
- https://github.com/EternalLeo/sound2wem
- https://www.songsterr.com/help
- https://www.songsterr.com/new
- https://www.talkbass.com/threads/songsterr-recently-released-an-automated-ai-tab-writing-feature.1667303/
- https://www.heise.de/en/news/Songsterr-uses-AI-to-create-fairly-accurate-guitar-tabs-from-your-own-recordings-10356152.html
- https://cdlc.ai/ e https://cdlc.ai/faq
- https://ignition4.customsforge.com/tools/wwise
