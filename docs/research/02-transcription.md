# Estado da Arte (2024–2026): Transcrição Automática de Guitarra

> Investigação realizada em 2026-06-11. Cada facto está etiquetado com [Fonte: URL] e nível de confiança (Alta/Média/Baixa).
> Nota metodológica: o acesso direto a páginas (WebFetch/curl) esteve bloqueado neste ambiente de execução; os factos provêm de excertos de pesquisa web, cruzados sempre que possível. Números que não foram realmente lidos numa fonte estão explicitamente marcados como não verificados.

---

## 1. Deteção polifónica de altura (pitch) — áudio → MIDI

### Spotify Basic Pitch
- **Objetivo:** conversor áudio→MIDI leve, agnóstico ao instrumento, polifónico, com deteção de pitch bends. Paper: Bittner et al., "A Lightweight Instrument-Agnostic Model for Polyphonic Note Transcription and Multipitch Estimation", ICASSP 2022 (arXiv:2203.09893). [Fonte: https://arxiv.org/abs/2203.09893 ; https://github.com/spotify/basic-pitch] (Alta)
- **Licença:** Apache-2.0 (código; modelos incluídos no repositório oficial). [Fonte: https://github.com/spotify/basic-pitch] (Alta)
- **Manutenção:** projeto ativo da Spotify, com ports oficiais TypeScript (basic-pitch-ts) e da comunidade em PyTorch. [Fonte: https://github.com/spotify/basic-pitch-ts ; https://github.com/gudgud96/basic-pitch-torch] (Alta)
- **Precisão:** treinado/avaliado com GuitarSet, iKala, MAESTRO, MedleyDB-Pitch e Slakh; excertos de avaliação referem accuracy frame-level ~63% em tarefas monofónicas (vozes/baixo). [Fonte: https://huggingface.co/spotify/basic-pitch ; https://grokipedia.com/page/Basic_Pitch] (Média). **O F-score note-level exato no GuitarSet não pôde ser lido diretamente do paper nesta sessão** (ver secção final). (Baixa quanto a números)
- **Limitações:** genérico (não específico de guitarra); não estima corda/traste; sem técnicas além de pitch bend; tende a fragmentar notas com vibrato/bend agressivos.

### Modelos QMUL (Riley, Edwards, Dixon) — atual estado-da-arte para guitarra
- **"High Resolution Guitar Transcription via Domain Adaptation" (ICASSP 2024, arXiv:2402.15258):** adapta o modelo de transcrição de piano de alta resolução para guitarra, alinhando partituras a ativações do modelo para gerar dados de treino; obtém **resultados estado-da-arte no GuitarSet em contexto zero-shot**. Dataset associado: François Leduc (Zenodo). [Fonte: https://arxiv.org/abs/2402.15258 ; https://zenodo.org/records/10984521] (Alta)
- **GAPS (ISMIR 2024, arXiv:2408.08653):** maior dataset de guitarra real — 14 h de guitarra clássica, pares áudio-partitura alinhados, >200 intérpretes, MIDI note-level de alta resolução + vídeos; modelo benchmark associado atinge **estado-da-arte no GuitarSet em regimes supervisionado e zero-shot** (avaliação F-measure note-level a 50 ms, onsets). [Fonte: https://arxiv.org/abs/2408.08653 ; https://aim-qmul.github.io/GAPS/ ; https://zenodo.org/records/13962272 ; https://huggingface.co/datasets/xavriley/GAPS] (Alta)
- **Limitações:** foco em guitarra clássica (cordas de nylon); a saída é MIDI de alta resolução, não tablatura; valores numéricos exatos das tabelas não confirmados nesta sessão. (Baixa quanto a números)

### CREPE
- **Objetivo:** estimador de pitch **monofónico** por CNN (Kim et al., 2018). Inadequado para guitarra polifónica; útil para linhas de nota única e como componente de deteção de afinação (foi usado no sistema de deteção de afinação de Rochester, abaixo). [Fonte: https://hajim.rochester.edu/ece/sites/zduan/teaching/ece477/projects/2023/DeclanParker_McCormackChew_FinalReport.pdf] (Alta quanto a ser monofónico)
- **Licença:** MIT (repositório marl/crepe). (Média — não re-verificado diretamente nesta sessão)

### Onsets & Frames / MT3 (Google Magenta)
- **Onsets & Frames:** arquitetura de transcrição de piano (2018) que inspirou variantes para guitarra; não específica de guitarra. (Alta — facto estabelecido)
- **MT3:** transformer multi-instrumento e multi-tarefa (ICLR 2022); transcreve guitarra em misturas, mas sem corda/traste nem técnicas; código no repositório magenta/mt3 sob Apache-2.0. (Média — licença não re-verificada nesta sessão)
- **Limitações comuns:** modelos genéricos perdem detalhe fino de guitarra (bends contínuos, notas repetidas rápidas) face aos modelos QMUL acima.

### Omnizart
- **Objetivo:** toolkit "tudo-em-um" (instrumentos, voz, acordes, bateria, beat) do MCT Lab (Taiwan); publicado no JOSS. [Fonte: https://github.com/Music-and-Culture-Technology-Lab/omnizart] (Alta)
- **Manutenção:** último release PyPI = 0.5.0; sinais de manutenção parada há vários anos. [Fonte: https://pypi.org/project/omnizart/ ; https://libraries.io/pypi/omnizart] (Média)
- **Licença:** badge PyPI presente mas tipo exato não confirmado nesta sessão (geralmente citada como MIT — não verificado). (Baixa)
- **Limitações:** sem módulo de guitarra/tablatura; dependências TensorFlow antigas.

**Resposta à questão-chave 1:** o pipeline áudio→MIDI para guitarra com melhor evidência (2024–2026) é o dos modelos QMUL (High Resolution via Domain Adaptation → GAPS), estado-da-arte no GuitarSet em zero-shot e supervisionado; Basic Pitch continua a ser a opção prática mais simples (Apache-2.0, leve, pitch bends), mas com precisão inferior aos modelos dedicados. (Alta quanto à ordenação; Baixa quanto a números absolutos)

---

## 2. Tablatura (corda + traste) — áudio → tab

### TabCNN (Wiggins & Kim, ISMIR 2019)
- **Objetivo:** CNN que estima tablatura frame-level (corda+traste) a partir de CQT de guitarra acústica solo; treino/teste no GuitarSet com 6-fold cross-validation por intérprete; supera um algoritmo de multipitch estado-da-arte da época. [Fonte: https://archives.ismir.net/ismir2019/paper/000033.pdf ; https://github.com/andywiggins/tab-cnn] (Alta)
- Introduziu as métricas padrão da área: multipitch P/R/F, tablature P/R/F e TDR (tablature disambiguation rate). [Fonte: https://archives.ismir.net/ismir2019/paper/000033.pdf] (Alta)
- **Precisão:** valores exatos não lidos nesta sessão (citados habitualmente como multipitch F≈0.83 e tablature F≈0.74 — NÃO verificado aqui). (Baixa)
- **Licença/manutenção:** código académico, sem manutenção ativa. (Média)
- **Limitações:** frame-level (sem segmentação em notas), só guitarra acústica do GuitarSet, fraca generalização para guitarra elétrica/efeitos.

### FretNet (Cwitkowitz, Hirvonen & Klapuri, 2022/23)
- **Objetivo:** transcrição de tablatura com contornos de pitch contínuos — unifica estimação multipitch e transcrição, estima onsets e desvio relativo de pitch (capta implicitamente bends/vibrato) agrupados por corda/traste. [Fonte: https://arxiv.org/abs/2212.03023 ; https://github.com/cwitkowitz/guitar-transcription-continuous] (Alta)
- **Avaliação:** 6-fold cross-validation no GuitarSet; seleção de modelo por tablature F1 frame-level; números exatos não confirmados nesta sessão. [Fonte: https://github.com/cwitkowitz/guitar-transcription-continuous] (Alta quanto ao protocolo; Baixa quanto a números)
- **Limitações:** dependência do GuitarSet (pequeno: 360 excertos, 6 guitarristas); é código de investigação, não ferramenta de produção.

### SynthTab (ICASSP 2024)
- **Objetivo:** dados sintetizados em larga escala (a partir de tabs DadaGP renderizadas com amostras realistas) para pré-treinar modelos de tablatura e mitigar a escassez de dados; melhora a generalização de TabCNN-like. [Fonte: https://arxiv.org/pdf/2309.09085] (Alta quanto à existência/abordagem)

### Robustez a guitarra elétrica (2024)
- "Leveraging Real Electric Guitar Tones and Effects to Improve Robustness in Guitar Tablature Transcription" (arXiv:2405.14679): ataca a fraqueza central — modelos treinados em GuitarSet (acústica) degradam-se com tons elétricos/distorção. [Fonte: https://arxiv.org/pdf/2405.14679] (Alta quanto à existência)

### Transformer de tablatura simbólica (QMUL)
- Encoder-decoder Transformer (masked language modeling), pré-treinado em DadaGP e afinado com transcrições profissionais para atribuir corda/traste a notas (MIDI→tab); superou algoritmos concorrentes num estudo de utilizadores sobre "playability". Combinado com o transcritor GAPS dá um pipeline áudio→MIDI→tab. [Fonte: https://www.xavierriley.co.uk/publications/] (Média)

### GOAT (set. 2025)
- "GOAT: A Large Dataset of Paired Guitar Audio Recordings and Tablatures" (arXiv:2509.22655) — novo dataset de pares gravação/tablatura, orientado a destravar modelos áudio→tab em escala. [Fonte: https://arxiv.org/pdf/2509.22655] (Média — detalhes por confirmar)

### Datasets de referência
- **GuitarSet** (ISMIR 2018): 360 excertos, 6 guitarristas, anotações por corda via pickup hexafónico; ainda é o benchmark universal. [Fonte: https://archives.ismir.net/ismir2018/paper/000188.pdf] (Alta)
- **IDMT-SMT-Guitar** (Fraunhofer): ~4700 eventos de nota, 7 guitarras, estilos de palhetada (finger/picked/muted) e expressão (normal, bend, slide, vibrato, harmonics, dead-notes); disponível no Zenodo. [Fonte: https://www.idmt.fraunhofer.de/en/publications/datasets/guitar.html ; https://zenodo.org/records/7544110] (Alta; licença exata não confirmada — datasets IDMT são tipicamente não-comerciais, NÃO verificado)

**Resposta à questão-chave 2:** existe código aberto para áudio→tablatura (TabCNN, FretNet, mais SynthTab para pré-treino), mas é todo de nível investigação, avaliado quase só no GuitarSet, com tablature F-measure tipicamente bem abaixo do multipitch F (a atribuição corda/traste é o gargalo) e fraca robustez fora de guitarra acústica limpa. Não há ferramenta madura "de produção" open-source para tab com precisão publicada alta. (Alta quanto ao panorama; Baixa quanto a números)

---

## 3. Deteção de onsets

- O onset de guitarra (ataque rápido) é relativamente bem resolvido pelos detetores genéricos: madmom (RNN/CNN onset detection — estado-da-arte clássico), librosa (spectral flux), Essentia (vários métodos). [Fonte: https://github.com/CPJKU/madmom ; https://essentia.upf.edu/tutorial_rhythm_beatdetection.html] (Alta)
- Trabalho recente específico para instrumentos de ataque rápido: "Chirp Group Delay based Onset Detection in Instruments with Fast Attack" (arXiv:2408.13734), avaliado também em datasets de guitarra IDMT. [Fonte: https://arxiv.org/pdf/2408.13734] (Média)
- Nos sistemas neuronais modernos (Basic Pitch, modelos QMUL, FretNet), o onset é previsto conjuntamente com o pitch — não é necessário um detetor separado. (Alta)

---

## 4. BPM / beat / downbeat / compasso

### madmom
- **Objetivo:** beat, downbeat e meter tracking, tempo, onsets (RNN+DBN); referência open-source histórica em precisão. [Fonte: https://github.com/CPJKU/madmom ; https://arxiv.org/abs/1605.07008] (Alta)
- **Licença (VERIFICADA — atenção):** dupla. Código-fonte sob **BSD**, mas **todos os modelos/ficheiros de dados sob CC BY-NC-SA 4.0 (não comercial)**; uso comercial dos modelos exige contactar Gerhard Widmer (CP JKU). [Fonte: https://github.com/CPJKU/madmom/blob/main/LICENSE ; https://github.com/CPJKU/madmom_models] (Alta)
- **Manutenção:** lenta; último release PyPI antigo (0.16.x, 2018; dev na main), problemas conhecidos com Python/NumPy recentes. [Fonte: https://pypi.org/project/madmom/] (Média)

### Beat This! (CPJKU, ISMIR 2024)
- **Objetivo:** beat+downbeat tracker neural "Accurate Beat Tracking Without DBN Postprocessing" (Foscarin, Schlüter, Widmer); treinado em muitos datasets (incl. instrumentos solo, mudanças de compasso, clássica); citado por terceiros como tendo **os melhores F1 publicados em beat e downbeat**. [Fonte: https://github.com/CPJKU/beat_this ; https://arxiv.org/html/2407.21658v1 ; https://github.com/b451c/ReaBeat] (Alta quanto à existência e reputação; Média quanto a "melhor F1"; números exatos não confirmados)
- **Licença:** não confirmada nesta sessão (verificar pyproject/LICENSE do repo antes de uso comercial). (Baixa)

### librosa
- **Objetivo:** beat tracking por programação dinâmica (Ellis) e PLP; tempo estático/variável. Simples, mas precisão inferior aos métodos neuronais. [Fonte: https://librosa.org/doc/main/generated/librosa.beat.beat_track.html] (Alta)
- **Licença:** ISC (permissiva). [Fonte: http://librosa.org/doc/0.11.0/auto_examples/plot_dynamic_beat.html] (Média-Alta)
- **Manutenção:** ativa (0.11.0 em 2025). (Alta)

### Essentia
- **Objetivo:** RhythmExtractor2013 (multifeature/degara) para beat/BPM; TempoCNN para BPM global/local via modelos TensorFlow. [Fonte: https://essentia.upf.edu/tutorial_rhythm_beatdetection.html] (Alta)
- **Licença:** **AGPL-3.0** (núcleo; Essentia.js também AGPLv3) — viral, problemática para produtos fechados; licenças comerciais negociáveis com a UPF. [Fonte: https://program.ismir2020.net/static/final_papers/260.pdf] (Alta para Essentia.js; Média para o detalhe das exceções)

### Compasso (time signature)
- Não há ferramenta open-source madura dedicada; abordagens: (a) inferir do downbeat tracking (madmom/Beat This!); (b) classificadores recentes — "Music time signature detection using ResNet18" (2024) com o dataset **METER2800** (2800 clips de 30 s, classes 3/4/5/7). [Fonte: https://link.springer.com/article/10.1186/s13636-024-00346-6 ; https://pmc.ncbi.nlm.nih.gov/articles/PMC10700346/] (Alta quanto à existência; sem números de accuracy verificados)

**Resposta à questão-chave 4:** melhor precisão → Beat This! (ISMIR 2024) e madmom; mas madmom tem modelos CC BY-NC-SA (não comercial) e Essentia é AGPL — para uso comercial sem fricção de licença, librosa (ISC) é a única opção totalmente permissiva, à custa de precisão. Compasso continua a ser o elo fraco (derivar de downbeats ou classificador ResNet18/METER2800). (Alta)

---

## 5. Deteção de afinação (tuning)

- **Acoustic Classification of Guitar Tunings with Deep Learning** (DLfM 2024, Cardiff): classificação de afinações a partir de áudio; identifica complicações reais — capos elevam o pitch mínimo, afinações fora de A440, afinações com o mesmo perfil de intervalos transposto. [Fonte: https://orca.cardiff.ac.uk/id/eprint/170217/1/dlfm2024-4%20(2).pdf] (Alta quanto à existência)
- **Projeto U. Rochester (2023):** pipeline pitch mínimo + embeddings OpenL3 + classificador, usando CREPE; **83,6% accuracy** num conjunto de teste com Drop D, Drop C, E Standard e FMaj9. [Fonte: https://hajim.rochester.edu/ece/sites/zduan/teaching/ece477/projects/2023/DeclanParker_McCormackChew_FinalReport.pdf] (Média — projeto de curso, não peer-reviewed)
- **Prática comum:** afinação de referência (desvio de A440) estimável por histograma de desvios em cents das notas transcritas (abordagem usada em librosa `estimate_tuning`); distinguir afinação da guitarra (drop/open) a partir de áudio polifónico continua pouco resolvido. (Média — inferência da literatura)

---

## 6. Deteção de técnicas de guitarra

### Datasets
- **IDMT-SMT-Guitar:** estilos de expressão anotados: bending, slide, vibrato, harmonics, dead-notes + plucking styles (finger, picked, **muted** ≈ palm mute). [Fonte: https://www.idmt.fraunhofer.de/en/publications/datasets/guitar.html] (Alta)
- **Dataset multimodal de técnicas de guitarra elétrica (Data in Brief, 2023/24):** 549 amostras vídeo+áudio, **9 técnicas** (incl. bend, slide, hammer-on, pull-off), 3 guitarras × 3 amps simulados; baselines SVM e CNN. [Fonte: https://www.sciencedirect.com/science/article/pii/S2352340923009046 ; https://pmc.ncbi.nlm.nih.gov/articles/PMC10698518/] (Alta)
- **GuitarSet** não anota técnicas — limitação estrutural dos benchmarks de transcrição. (Alta)

### Modelos e precisão
- **SpectroFusionNet (Scientific Reports, maio 2025):** CNN com fusão de espectrogramas (MFCC+Gammatone, late fusion) para 9 classes de técnica: **99,12% accuracy** em condições controladas, mas **70,9% em áudio real-time** — forte gap de generalização. Bend, sweep picking e slide com precisão/F1 altos; **pull-off e vibrato com F1 baixos** (sobreposição espectral; técnicas dependentes de variação temporal são mais difíceis). [Fonte: https://www.nature.com/articles/s41598-025-00287-w ; https://pmc.ncbi.nlm.nih.gov/articles/PMC12081671/] (Alta)
- **FretNet** capta bends/vibrato implicitamente via contornos contínuos de pitch (sem classificar a técnica). [Fonte: https://arxiv.org/abs/2212.03023] (Alta)
- Trabalho paralelo em violino confirma a tendência da área para transcrição "technique-aware" com dados sintéticos (VioPTT, 2025). [Fonte: https://arxiv.org/pdf/2509.23759] (Média)

**Resposta à questão-chave 3 — o que é provadamente detetável:**
- **Bem detetável (evidência publicada):** bend e slide (F1 altos no SpectroFusionNet; contornos de pitch tornam-nos visíveis no sinal); harmónicos e dead notes (classes do IDMT-SMT-Guitar com classificadores SVM/CNN); palm mute aproximável pela classe "muted" do IDMT. (Alta)
- **Parcialmente detetável:** vibrato e pull-off — F1 baixos mesmo no estado-da-arte 2025; hammer-on/pull-off distinguem-se mal por espectro isolado (dependem do contexto temporal entre notas). (Alta, com base no SpectroFusionNet)
- **Não resolvido em contexto real:** todas as técnicas em gravações polifónicas/mistura completa — os resultados publicados são em notas/licks isolados; a queda 99%→71% em áudio real ilustra o problema. Não existe ferramenta open-source pronta que anote técnicas numa transcrição completa. (Alta)

---

## Tabela-resumo das ferramentas

| Ferramenta | Objetivo | Licença (verificada?) | Manutenção | Precisão publicada | Limitações |
|---|---|---|---|---|---|
| Basic Pitch | áudio→MIDI polifónico + bends | Apache-2.0 (Alta) | ativa | F GuitarSet no paper, números não confirmados | sem corda/traste |
| Modelos QMUL (HR-DA/GAPS) | áudio→MIDI guitarra alta resolução | dataset CC (Zenodo); código a confirmar | ativa (2024) | SOTA GuitarSet zero-shot e supervisionado (números n/ confirmados) | guitarra clássica |
| CREPE | pitch monofónico | MIT (Média) | estável | n/a p/ polifonia | monofónico |
| MT3 | multi-instrumento→MIDI | Apache-2.0 (Média) | parada | n/ confirmada p/ guitarra | sem tab/técnicas |
| Omnizart | toolkit transcrição | n/ confirmada | parada (0.5.0) | n/a guitarra | sem guitarra |
| TabCNN | áudio→tab frame-level | académica | parada | métricas definidas; números n/ confirmados | só GuitarSet acústico |
| FretNet | áudio→tab + contornos contínuos | académica | parada (~2023) | 6-fold GuitarSet; números n/ confirmados | investigação |
| madmom | beat/downbeat/onset/tempo | BSD código + **CC BY-NC-SA modelos** (Alta) | lenta | referência histórica | modelos não-comerciais |
| Beat This! | beat+downbeat SOTA | n/ confirmada | ativa (2024) | "melhores F1 publicados" (citação de terceiros) | números n/ confirmados |
| librosa | beat/tempo/onset/tuning | ISC (Média-Alta) | ativa | inferior a neuronais | precisão |
| Essentia | beat/BPM/TempoCNN | **AGPL-3.0** (Alta p/ js) | ativa | n/ confirmada | licença viral |
| SpectroFusionNet | classificação de 9 técnicas | paper (sem código confirmado) | 2025 | 99,12% controlado / 70,9% real | notas isoladas |

---

## O que não foi possível verificar

O acesso direto a páginas web (arXiv, GitHub, HuggingFace, ISMIR PDFs) esteve bloqueado neste ambiente; só excertos de motor de pesquisa estiveram disponíveis. Ficou por verificar:

1. **Números exatos de F-measure** do Basic Pitch no GuitarSet (paper ICASSP 2022), do TabCNN (multipitch/tablature F e TDR), do FretNet, e das tabelas do GAPS/High-Resolution (zero-shot vs supervisionado). Os valores frequentemente citados (TabCNN tab F≈0.74; GAPS onset-F >0.9) NÃO foram confirmados em fonte primária.
2. **Licenças exatas** de: Beat This! (repo CPJKU), Omnizart, MT3, código GAPS, IDMT-SMT-Guitar (Zenodo), GuitarSet (Zenodo — habitualmente citada como MIT/CC, não confirmado).
3. **Accuracy do ResNet18/METER2800** para deteção de compasso (paper de 2024 existe, números não lidos).
4. Detalhes do **GOAT** (dimensão, licença, baselines) — paper de set. 2025 identificado mas não lido.
5. Se existe **algum modelo publicado que detete palm mute em misturas completas** — não foi encontrada evidência direta; apenas a classe "muted" em notas isoladas (IDMT).
6. Estado de manutenção exato (datas de último commit/release) de cada repositório.
