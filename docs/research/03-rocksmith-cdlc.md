# Ecossistema CDLC de Rocksmith 2014 e empacotamento PSARC

Data da investigação: 2026-06-11. Notas de confiança: **Facto verificado** (confirmado em fonte primária), **Inferência** (deduzido de fontes), **Não verificado**.

## 1. Rocksmith Custom Song Toolkit (RSToolkit)

- **Nome/objetivo**: "Custom song toolkit for Rocksmith and Rocksmith 2014" — converte arranjos XML (do EOF) em pacotes PSARC jogáveis, incluindo geração de SNG, manifestos JSON, tons e conversão áudio via Wwise. [Fonte: https://github.com/rscustom/rocksmith-custom-song-toolkit] (Facto verificado)
- **Linguagem**: C# (~97%), com pequenos componentes Python e Ruby; plataforma Windows/.NET (corre em Mono). [Fonte: https://github.com/rscustom/rocksmith-custom-song-toolkit] (Facto verificado quanto às linguagens; suporte Mono: Inferência)
- **CLI**: Sim — existe o diretório `RocksmithToolkitCLI` no repositório, com ferramentas como `toneliberator.exe` (drag/drop) e scripts (ex.: `psarc-extract.rb`). [Fonte: https://github.com/rscustom/rocksmith-custom-song-toolkit] (Facto verificado)
- **Manutenção**: **EOL (fim de vida)**. O README declara explicitamente que o projeto "has reached it's EOL stage and should be archived". Último release: **v2.9.2.1, 14 de novembro de 2021**. Recomenda migração para o **DLC Builder** (projeto `iminashi/Rocksmith2014.NET`, em F#). [Fonte: https://github.com/rscustom/rocksmith-custom-song-toolkit] (Facto verificado)
- **PSARC**: implementação completa de pack/unpack em `RocksmithToolkitLib/PSARC/PSARC.cs` e `DLCPackage/Packer.cs`. [Fonte: https://github.com/rscustom/rocksmith-custom-song-toolkit/blob/master/RocksmithToolkitLib/PSARC/PSARC.cs] (Facto verificado)
- **Wwise**: o release 2.8.4.0 acrescentou suporte para Wwise 2013.1.x a 2016.1.x — o toolkit depende do Wwise instalado para converter áudio para .wem. [Fonte: https://github.com/rscustom/rocksmith-custom-song-toolkit/releases/tag/2.8.4.0] (Facto verificado)
- **Licença**: não visível na página principal do GitHub. (Não verificado — ver secção final)
- **Limitações**: abandonado; GUI Windows-centrada; dependência do Wwise externo para áudio.

### 1b. Sucessor: Rocksmith2014.NET / DLC Builder (iminashi)

- O próprio README do RSToolkit aponta para https://github.com/iminashi/Rocksmith2014.NET como substituto moderno para criação de CDLC. [Fonte: https://github.com/rscustom/rocksmith-custom-song-toolkit] (Facto verificado)
- (Detalhes abaixo na secção de bibliotecas, após verificação.)

## 2. Editor on Fire (EOF)

- **Nome/objetivo**: editor de "charts" para jogos de ritmo — "a song editor for Rocksmith, IMMERROCK, Drums Rock, YARG, Clone Hero, Rock Band, Phase Shift, Frets On Fire". No fluxo CDLC, é a ferramenta de **autoria**: o utilizador fornece um OGG e cria as notas/arranjos; o EOF exporta XML de arranjo Rocksmith que o Toolkit/DLC Builder empacota. [Fonte: https://github.com/raynebc/editor-on-fire; https://nickbeat.feuerherm.ca/rocksmith/a-rocksmith-cdlc-walkthrough/] (Facto verificado quanto à descrição; papel no fluxo: Inferência forte, confirmada por tutoriais da comunidade)
- **Linguagem/plataforma**: C (~91%); Windows, macOS e Linux (binários para Win/Mac; compilável em Linux). [Fonte: https://github.com/raynebc/editor-on-fire] (Facto verificado)
- **Manutenção**: ativamente mantido por raynebc; builds distribuídas via CustomsForge Ignition4 (https://ignition4.customsforge.com/eof). [Fonte: https://github.com/raynebc/editor-on-fire; https://ignition4.customsforge.com/eof] (Facto verificado quanto à distribuição; "ativo" em 2026: Inferência)
- **Licença**: ficheiro `license.txt` no repositório; tipo exato por confirmar. (Não verificado)

### 1c. DLC Builder / Rocksmith2014.NET (sucessor moderno)

- **Objetivo**: bibliotecas .NET para criação de CDLC de Rocksmith 2014, "based largely on the Song Creator Toolkit for Rocksmith". A app principal é o **DLC Builder**, GUI multiplataforma. [Fonte: https://github.com/iminashi/Rocksmith2014.NET] (Facto verificado)
- **Licença**: MIT. **Linguagem**: F# (~84%) + C# (~16%). **Plataformas**: Windows, macOS, Linux. [Fonte: https://github.com/iminashi/Rocksmith2014.NET] (Facto verificado)
- **Manutenção**: ativa — release DLC Builder v3.5.0 a 24 de julho de 2025. [Fonte: https://github.com/iminashi/Rocksmith2014.NET] (Facto verificado)
- **Capacidades**: abrir/criar PSARC, conversão áudio wav/ogg/wem, geração de dificuldade dinâmica com modelo ML.NET, processamento XML e conversão SNG, criação de projetos EOF. [Fonte: https://github.com/iminashi/Rocksmith2014.NET] (Facto verificado)
- **CLI**: as bibliotecas dão acesso programático; existem apps de consola auxiliares (Profile Debloater, Empty Title Fix), mas a oferta principal é GUI. [Fonte: https://github.com/iminashi/Rocksmith2014.NET] (Facto verificado)

## 3. DDC (Dynamic Difficulty Creator)

- **Objetivo**: processa os XML de cada arranjo e produz novas versões com níveis de dificuldade gerados automaticamente (a "dificuldade dinâmica" do Rocksmith). [Fonte: https://ddcreator.wordpress.com/dynamic-difficulty-creator/add-difficulty-levels-in-an-existing-package/] (Facto verificado)
- **Distribuição/integração**: distribuído via CustomsForge e **integrado no RSToolkit**, que tem opção de aplicar DD automaticamente aos arranjos. A comunidade afirma que os arranjos precisam de DD para o "Play Count" do Rocksmith 2014 Remastered funcionar corretamente. [Fonte: https://customsforge.com/index.php?%2Ftopic%2F2863-dynamic-difficulty-creator%2F=] (Facto verificado quanto à integração; afirmação do Play Count: Não verificado em fonte primária)
- **Ferramentas relacionadas**: **DDCImprover** (iminashi) — wrapper que processa XMLs Rocksmith 2014 e corrige um defeito do DDC (mover secções não alinhadas com o primeiro tempo do compasso). [Fonte: https://github.com/iminashi/DDCImprover] (Facto verificado)
- **Sucessão**: o DLC Builder substitui o DDC clássico por geração de DD com modelo ML.NET. [Fonte: https://github.com/iminashi/Rocksmith2014.NET] (Facto verificado)
- **Limitações**: o DDC original é um binário de linha de comandos de código fechado distribuído na comunidade (Inferência; não foi encontrado repositório de código-fonte do DDC original).

## 4. Bibliotecas Python para PSARC

Sim, existem implementações abertas de pack/unpack de PSARC **incluindo o tratamento da cifragem** dos arquivos Rocksmith (não reproduzimos chaves aqui):

- **0x0L/rs-utils** — "Scripts for Rocksmith 2014"; inclui `bin/psarc.py` para manipular arquivos PSARC; também ferramentas de conversão/inspeção. [Fonte: https://github.com/0x0L/rs-utils] (Facto verificado)
- **0x0L/rocksmith** — "A python 3 package to deal with Rocksmith 2014 resources"; faz unpack/repack sem perdas de PSARC (há issues conhecidas, ex.: #5 "Unpacking misses files"). [Fonte: https://github.com/0x0L/rocksmith; https://github.com/0x0L/rocksmith/issues/5] (Facto verificado)
- **BuongiornoTexas/rsrtools** — pacote Python (também no PyPI) para songlists e gestão de saves/perfis; o executável `welder` suporta Extract, List, Pack, Unpack e Verify de PSARC. [Fonte: https://github.com/BuongiornoTexas/rsrtools; https://pypi.org/project/rsrtools/] (Facto verificado)
- A comunidade descreve o PSARC de cada música como "uma espécie de zip cifrado" contendo áudio, metadados, arranjos, letras e artwork. [Fonte: https://justinaiken.com/2017/07/04/uncensoring_rocksmith/] (Facto verificado quanto à descrição comunitária)

## 5. Formato XML de arranjo do Rocksmith 2014

Não existe especificação oficial da Ubisoft; o formato está documentado de facto no **código-fonte das ferramentas da comunidade**:

- **Fonte primária de documentação**: a classe `Song2014` do RSToolkit (`RocksmithToolkitLib/XML/Song2014.cs`) serializa/deserializa todo o formato. Elementos confirmados no código: `ebeats`/`ebeat`, `phrases`/`phrase`, `phraseIterations`/`phraseIteration`, `sections`/`section`, `chordTemplates`/`chordTemplate`, `levels` (com `notes` e `chords` por nível de dificuldade), `anchors`/`anchor`, `handShapes`/`handShape`. A classe `SongNote2014` define atributos de nota incluindo `time`, `fret`, `bend`, `hammerOn`, `harmonic`, `accent`, `linkNext`; os restantes (`string`, `sustain`, `slideTo`, `pullOff`, `palmMute`, etc.) constam do mesmo ficheiro (porção não exibida na captura). [Fonte: https://github.com/rscustom/rocksmith-custom-song-toolkit/blob/master/RocksmithToolkitLib/XML/Song2014.cs] (Facto verificado para os elementos citados; restantes atributos: Inferência forte)
- O elemento `tuning` (afinação por corda) e metadados (título, capo, offset, comprimento) também são geridos pelo toolkit/EOF; arranjos multi-tom usam `<tonebase>` e `<tonea>`–`<toned>`. [Fonte: https://github.com/rscustom/rocksmith-custom-song-toolkit/blob/master/RocksmithToolkitLib/XML/Song2014.cs; releases do toolkit] (Inferência baseada em fontes secundárias)
- **Outras fontes de documentação**: implementação XML em F# no Rocksmith2014.NET (`Rocksmith2014.XML`) [Fonte: https://github.com/iminashi/Rocksmith2014.NET] (Facto verificado quanto à existência); scripts de 0x0L/rs-utils que geram/convertem estes XML [Fonte: https://github.com/0x0L/rs-utils] (Facto verificado quanto à existência); wikis/tutoriais da CustomsForge [Fonte: https://customsforge.com] (Não verificado em detalhe).
- O formato compilado em runtime é o **SNG** (binário cifrado); a conversão XML<->SNG é feita pelo toolkit (`Sng2014FileWriter.cs`, `sng2014.exe`) e pelo Rocksmith2014.NET. [Fonte: https://github.com/rscustom/rocksmith-custom-song-toolkit/blob/master/RocksmithToolkitLib/Sng/Sng2014FileWriter.cs] (Facto verificado)

## 6. Áudio: conversão Wwise .wem

- **O Wwise da Audiokinetic é obrigatório para criar CDLC**: o DLC Builder documenta que "Converting audio files to wem requires Wwise 2019, 2021, 2022 or 2023 to be installed" — não converte internamente. Em Windows localiza o Wwise via `WWISEROOT`/Program Files; em Linux usa Wine para correr o executável de consola do Wwise. [Fonte: https://github.com/iminashi/Rocksmith2014.NET/blob/main/samples/DLCBuilder/README.md] (Facto verificado)
- O RSToolkit clássico suportava Wwise 2013.1.x–2016.x (lógica em `RocksmithToolkitLib/Ogg/Wwise.cs`). [Fonte: https://github.com/rscustom/rocksmith-custom-song-toolkit/blob/master/RocksmithToolkitLib/Ogg/Wwise.cs; https://github.com/rscustom/rocksmith-custom-song-toolkit/releases/tag/2.8.4.0] (Facto verificado)
- A CustomsForge mantém uma página com builds/instruções de Wwise para CDLC. [Fonte: https://ignition4.customsforge.com/tools/wwise] (Facto verificado quanto à existência da página)
- **Licenciamento Wwise**: o download das ferramentas Audiokinetic exige aceitação dos termos/EULA da Audiokinetic (conta no Audiokinetic Launcher); o Wwise é gratuito para este uso não comercial, mas a redistribuição dos binários é restringida pelo EULA. (Primeira parte: Facto verificado via resultados de pesquisa; gratuitidade/restrição de redistribuição: Inferência — não confirmado o texto exato do EULA)
- **Alternativas no sentido inverso**: `ww2ogg` converte .wem existentes de volta para .ogg (extração, não criação) — não substitui o Wwise para *criar* .wem para CDLC. [Fonte: resultados de pesquisa; https://ignition4.customsforge.com/tools/wwise] (Facto verificado quanto ao papel do ww2ogg; inexistência de codificador .wem aberto: Não verificado exaustivamente)

## 7. Aspetos legais (relato factual)

### Posição da Ubisoft sobre CDLC
- **Não foi encontrada qualquer declaração oficial pública da Ubisoft** que autorize ou proíba explicitamente CDLC para Rocksmith 2014. As discussões da comunidade (Steam) notam que customs podem violar os Termos de Serviço/EULA, mas a Ubisoft nunca atuou publicamente contra a CustomsForge. [Fonte: https://steamcommunity.com/app/221680/discussions/0/666827315226576589] (Não verificado em fonte primária da Ubisoft — apenas discussões da comunidade)
- A própria CustomsForge declara que "não é de forma alguma afiliada à Ubisoft, Steam, ou à equipa de desenvolvimento do Rocksmith" e encoraja a compra de conteúdo oficial. [Fonte: https://customsforge.com/guidelines/] (Facto verificado)
- Para o **Rocksmith+**, há indicações de que não existem planos de suportar CDLC. [Fonte: discussões/resultados de pesquisa] (Não verificado em fonte primária)

### Direitos de autor sobre CDLC
- Um CDLC tipicamente contém a **gravação original protegida** (áudio extraído do CD/compra) mais uma transcrição (que é obra derivada da composição). Distribuir o PSARC com o áudio incluído constitui, em princípio, distribuição não autorizada de obra protegida, independentemente da ferramenta usada. (Inferência jurídica geral; não é aconselhamento jurídico)
- O mecanismo "Cherub Rock": a maioria dos CDLC requer que o utilizador possua o DLC oficial "Cherub Rock", usado pelo patch da comunidade como verificação/ativação de customs — apresentado pela comunidade como gesto de boa-fé para garantir alguma compra oficial. [Fonte: https://www.gameskinny.com/tips/how-to-import-almost-any-custom-song-into-rocksmith-2014/] (Facto verificado quanto ao requisito; motivação: Inferência)

### YouTube ToS e yt-dlp
- Os Termos de Serviço do YouTube proíbem descarregar conteúdo exceto pelas funcionalidades oficiais; usar yt-dlp para obter áudio do YouTube **viola o ToS** (questão contratual, não criminal — remédios: suspensão de conta/ação civil). [Fonte: https://audioutils.com/blog/is-yt-dlp-legal] (Facto verificado quanto ao teor do ToS; enquadramento legal: Inferência de fontes secundárias)
- Descarregar conteúdo protegido sem autorização é infração de direitos de autor independentemente da ferramenta; ToS e copyright são regimes distintos que se sobrepõem. [Fonte: https://audioutils.com/blog/is-yt-dlp-legal] (Facto verificado quanto ao princípio)
- **Estatuto do yt-dlp**: a ferramenta em si é distribuída legalmente; em 2020 a RIAA obteve a remoção do youtube-dl do GitHub via DMCA, mas o GitHub repô-lo semanas depois após intervenção da EFF (argumento: usos substanciais não infratores; o stream não é cifrado, logo não há "circunvenção" de DRM). O yt-dlp continua hospedado abertamente no GitHub; nenhum tribunal dos EUA se pronunciou especificamente sobre ele. [Fonte: https://www.eff.org/deeplinks/2020/11/github-reinstates-youtube-dl-after-riaas-abuse-dmca; https://en.wikipedia.org/wiki/Youtube-dl] (Facto verificado para o episódio de 2020; estado atual: Inferência de fontes secundárias)

## 8. Ecossistema CustomsForge

- **CustomsForge** é o hub central da comunidade CDLC: fóruns (https://customsforge.com) e a base de dados **Ignition4** (https://ignition4.customsforge.com), uma biblioteca de customs com dezenas de milhares de entradas (só na categoria Rock, mais de 7.000 músicas, segundo a própria página). [Fonte: https://ignition4.customsforge.com/] (Facto verificado quanto à existência; números: Não verificado com precisão)
- **Ferramentas alojadas/distribuídas**: EOF (builds oficiais), página de builds do Wwise, **CustomsForge Song Manager (CFSM)** para gerir coleções de CDLC, e **CDLC Enabler** (substituto moderno do patch do Cherub Rock). [Fonte: https://ignition4.customsforge.com/eof; https://ignition4.customsforge.com/tools/wwise; https://ignition4.customsforge.com/tools/cfsm; https://ignition4.customsforge.com/tools/cdlcenabler] (Facto verificado quanto à existência das páginas)
- **Fluxo de trabalho típico da comunidade**: EOF (autoria de notas sobre OGG) -> XML de arranjo -> DDC/DD automático -> DLC Builder ou RSToolkit (tons, metadados, Wwise->.wem, empacotamento PSARC) -> publicação no Ignition4 -> jogador instala no diretório `dlc` com o enabler ativo. [Fontes: https://nickbeat.feuerherm.ca/rocksmith/a-rocksmith-cdlc-walkthrough/; tutoriais YouTube] (Inferência consolidada de tutoriais; passos individuais verificados acima)
- Existem ainda repositórios de armazenamento de CDLC no GitHub (ex.: bandwiches/Rocksmith-CDLC), o que ilustra a distribuição informal — e juridicamente cinzenta — destes pacotes. [Fonte: https://github.com/bandwiches/Rocksmith-CDLC] (Facto verificado quanto à existência)

## O que não foi possível verificar

- **Licença exata do RSToolkit** (rscustom/rocksmith-custom-song-toolkit) — não visível na página do repositório consultada.
- **Licença exata do EOF** — existe `license.txt` no repositório raynebc/editor-on-fire, mas o tipo (GPL? custom?) não foi confirmado.
- **Data do último commit do EOF** e do RSToolkit (apenas a data do último release do toolkit, 2021-11-14, foi confirmada).
- **Texto exato do EULA da Audiokinetic** (gratuitidade para uso não comercial e restrições de redistribuição — plausível mas não confirmado na fonte primária).
- **Declaração oficial da Ubisoft sobre CDLC** — não foi encontrada nenhuma; a tolerância é inferida da inação ao longo de mais de uma década.
- **Afirmação de que DD é necessário para o Play Count do Remastered** — apenas em fontes comunitárias.
- **Números exatos do catálogo Ignition4** e quantos CDLC requerem "Cherub Rock".
- **Existência de um codificador .wem open-source** capaz de substituir o Wwise na criação (ww2ogg só faz o sentido inverso); não foi feita pesquisa exaustiva (ex.: projetos tipo "wwise_ima_adpcm").
- Atributos completos de `SongNote2014` (`string`, `sustain`, `slideTo`, `pullOff`, `palmMute`) — fortemente prováveis mas a porção do ficheiro lida não os exibia.
