# Investigação: Separação de Fontes Musicais com foco em Extração de Stem de Guitarra (2024–2026)

> Documento de investigação para o projeto RockForge. Última atualização: 2026-06-11.
> Níveis de confiança: **[Facto verificado]** (lido diretamente na fonte), **[Inferência]** (dedução razoável), **[Não verificado]** (afirmação encontrada mas não confirmada na fonte primária).

## 1. Demucs / HTDemucs (incl. htdemucs_6s)

- **Nome**: Demucs v4 (Hybrid Transformer Demucs, HTDemucs), incl. modelo de 6 stems `htdemucs_6s`.
- **Objetivo**: Separação de fontes musicais híbrida (espectrograma + forma de onda). O `htdemucs_6s` adiciona stems de **guitarra** e piano aos 4 clássicos (vocals, drums, bass, other).
- **Licença**: MIT — **[Facto verificado]** [Fonte: https://github.com/facebookresearch/demucs]
- **Manutenção**: Repositório **arquivado a 1 de janeiro de 2025** (read-only). O autor indica que o projeto "não é mantido ativamente; só correções importantes" num fork sucessor (adefossez/demucs). — **[Facto verificado]** [Fonte: https://github.com/facebookresearch/demucs]
- **Precisão publicada**: 9,00 dB SDR global no MUSDB HQ test set; 9,20 dB com fine-tuning (modelo de 4 stems `htdemucs_ft`). **Não há SDR publicado para o stem de guitarra do `htdemucs_6s`** no README. — **[Facto verificado]** [Fonte: https://github.com/facebookresearch/demucs]
- **Limitações**: O próprio README admite, sobre o `htdemucs_6s`: "Quick testing seems to show okay quality for guitar, but a lot of bleeding and artifacts for the piano source" — i.e., guitarra "aceitável", piano com muito bleeding/artefactos. Modelo experimental, treinado em MUSDB HQ + ~800 músicas extra. — **[Facto verificado]** [Fonte: https://github.com/facebookresearch/demucs]
- **Link oficial**: https://github.com/facebookresearch/demucs (arquivado); fork mantido: https://github.com/adefossez/demucs **[Inferência: o fork sucessor é o do autor original Alexandre Défossez]**

### Checkpoints HTDemucs no ecossistema ZFTurbo
- O repositório ZFTurbo lista o HTDemucs 6-stem com SDR documentado apenas para bass (11.22), drums (10.22) e vocals (8.05) no benchmark Multisong; **guitar/piano/other marcados como "---" (sem avaliação publicada)**. — **[Facto verificado]** [Fonte: https://github.com/ZFTurbo/Music-Source-Separation-Training/blob/main/docs/pretrained_models.md]

## 2. ZFTurbo Music-Source-Separation-Training (BS-RoFormer / Mel-Band RoFormer / MDX23C / SCNet…)

- **Nome**: Music-Source-Separation-Training (framework de treino + zoo de checkpoints comunitários).
- **Objetivo**: Treinar e disponibilizar modelos SOTA de separação (bs_roformer, mel_band_roformer, MDX23C, SCNet, HTDemucs, BandIt, Apollo, BSMamba2, etc.).
- **Licença**: MIT — **[Facto verificado]** [Fonte: https://github.com/ZFTurbo/Music-Source-Separation-Training]
- **Manutenção**: Muito ativo — última release "MVSep Mega 53 Stems model" a 20 de abril de 2026. — **[Facto verificado]** [Fonte: https://github.com/ZFTurbo/Music-Source-Separation-Training]
- **Checkpoints de guitarra**: A página oficial de modelos pré-treinados do repositório **não lista checkpoints dedicados de guitarra** nem modelos lead vs. rhythm. — **[Facto verificado na página docs/pretrained_models.md]** [Fonte: https://github.com/ZFTurbo/Music-Source-Separation-Training/blob/main/docs/pretrained_models.md]. Nota: existem modelos de guitarra no serviço associado MVSep (ver secção MVSep) e checkpoints comunitários (ex.: "becruily guitar" mencionado na comunidade UVR/MVSep) — **[Não verificado: não confirmado na fonte primária]**.
- **Precisão publicada (vocais, para referência)**: MelBand RoFormer (KimberleyJensen) SDR vocal 10,98; BS RoFormer (viperx) 10,87 (benchmark Multisong do repositório). — **[Facto verificado, via documentação do repositório citada em pesquisa]** [Fonte: https://deepwiki.com/ZFTurbo/Music-Source-Separation-Training/8.6-pretrained-models]
- **Limitações**: É um framework para programadores (CLI/configs YAML); checkpoints de guitarra são sobretudo comunitários e sem SDR formal publicado em paper.
- **Link oficial**: https://github.com/ZFTurbo/Music-Source-Separation-Training

## 3. BS-RoFormer / Mel-Band RoFormer (arquiteturas, ByteDance)

- **Objetivo**: Arquiteturas transformer com band-split + rotary position embeddings; SOTA em MUSDB18 desde 2023.
- **Papers**: "Music Source Separation with Band-Split RoPE Transformer" (BS-RoFormer, ByteDance, ICASSP 2024) e "Mel-Band RoFormer for Music Source Separation" (arXiv:2310.01809). — **[Facto verificado]** [Fonte: https://arxiv.org/pdf/2310.01809]
- **Licença**: Implementação de referência aberta mais usada: lucidrains/BS-RoFormer (MIT) e ZFTurbo (MIT); a ByteDance não publicou pesos oficiais. — **[Inferência: pesos oficiais não encontrados em nenhuma fonte]**
- **Precisão publicada**: BS-RoFormer ~9,0–9,8 dB SDR médio em MUSDB18 (4 stems, conforme paper). Para guitarra: um resultado de **9,05 dB SDR para guitarra** atribuído a BS-RoFormer aparece em fontes secundárias — **[Não verificado: número encontrado em agregadores, não confirmado no paper original; o paper BS-RoFormer avalia MUSDB18 que não tem stem de guitarra]** [Fonte: https://grokipedia.com/page/BS-RoFormer]
- **Limitações**: Stem de guitarra não faz parte do benchmark MUSDB18; resultados de guitarra dependem de checkpoints treinados em datasets privados (MVSep/MoisesDB).

## 4. Spleeter (Deezer)

- **Objetivo**: Separação rápida com U-Net espectral; modelos de 2, 4 e 5 stems (o de 5 adiciona **piano**, não guitarra).
- **Licença**: MIT — **[Facto verificado]** [Fonte: https://github.com/deezer/spleeter]
- **Manutenção**: Última release v2.3.0 a 3 de setembro de 2021; sem releases novas desde então — praticamente em modo legado. — **[Facto verificado]** [Fonte: https://github.com/deezer/spleeter/releases]
- **Stem de guitarra**: **Não existe**. A guitarra fica em "other". — **[Facto verificado]** [Fonte: https://github.com/deezer/spleeter]
- **Precisão publicada**: O paper reporta SDR competitivo na MUSDB18 mas o README não publica números concretos; qualidade hoje claramente inferior a Demucs/RoFormer. — **[Facto verificado quanto à ausência de números no README; Inferência quanto à comparação]**
- **Limitações**: Tecnologia de 2019, sem stem de guitarra, bleeding elevado. **Não recomendado para o objetivo do RockForge.** — **[Inferência]**
- **Link oficial**: https://github.com/deezer/spleeter

## 5. Open-Unmix (UMX)

- **Objetivo**: Modelo de referência académico (LSTM espectral), 4 stems.
- **Licença**: MIT (código); pesos UMXL: CC BY-NC-SA 4.0 (não comercial). — **[Facto verificado]** [Fonte: https://github.com/sigsep/open-unmix-pytorch]
- **Manutenção**: Última release v1.3.0 a 16 de abril de 2024 (port para torch 2.0); manutenção lenta. — **[Facto verificado]** [Fonte: https://github.com/sigsep/open-unmix-pytorch]
- **Precisão publicada (UMXL, MUSDB18)**: vocals 7,21 / drums 7,15 / bass 6,02 / **other 4,89** dB SDR. — **[Facto verificado]** [Fonte: https://github.com/sigsep/open-unmix-pytorch]
- **Stem de guitarra**: **Não existe** — guitarra cai em "other" (o stem mais fraco). — **[Facto verificado]**
- **Link oficial**: https://github.com/sigsep/open-unmix-pytorch

## 6. MVSep (serviço + modelos ZFTurbo)

- **Objetivo**: Serviço web de separação com dezenas de algoritmos, incluindo **modelos dedicados de guitarra** (acústica + elétrica vs. resto), baseados em MDX23C, Mel-Band RoFormer e BS-RoFormer. — **[Facto verificado em fontes secundárias; página oficial bloqueou fetch (403)]** [Fonte: https://mvsep.com/en/algorithms]
- **Licença**: Serviço comercial/freemium; os modelos públicos derivados estão no repositório ZFTurbo (MIT). — **[Inferência]**
- **Benchmarks**: O MVSep mantém leaderboards SDR públicos para Piano e Guitarra (dataset "Multisong") em https://mvsep.com/quality_checker/ — **[Facto verificado quanto à existência; números concretos de guitarra não recolhidos por bloqueio 403]** [Fonte: https://mvsep.com/quality_checker/]
- **Lead vs. rhythm**: Não encontrada oferta de separação lead/rhythm no MVSep. — **[Não verificado / ausência de evidência]**
- **Link oficial**: https://mvsep.com

## 7. UVR — Ultimate Vocal Remover (GUI)

- **Objetivo**: GUI desktop open-source que agrega modelos VR Arch, MDX-Net/MDX23C e Demucs v3/v4; ferramenta de facto da comunidade de separação.
- **Licença**: MIT — **[Facto verificado]** [Fonte: https://github.com/Anjok07/ultimatevocalremovergui]
- **Manutenção**: Última release oficial v5.6 a 26 de setembro de 2023; sem releases desde então (a comunidade migrou parcialmente para forks como UVR5-UI/Gradio e para o framework ZFTurbo). — **[Facto verificado quanto à release; Inferência quanto à migração]** [Fonte: https://github.com/anjok07/ultimatevocalremovergui/releases]
- **Stem de guitarra**: O README não menciona modelos dedicados de guitarra; o acesso a guitarra faz-se via modelo Demucs `htdemucs_6s` integrado ou modelos comunitários carregados manualmente. — **[Facto verificado quanto ao README; Inferência quanto ao uso comunitário]**
- **Precisão publicada**: Sem SDR de guitarra publicado pelo projeto.
- **Link oficial**: https://github.com/Anjok07/ultimatevocalremovergui

## 8. MDX-Net / MDX23C

- **Objetivo**: Arquitetura TFC-TDF (KUIELab), popularizada pelos Music Demixing Challenges (MDX21/23). MDX23C = v3 da arquitetura.
- **Licença**: Implementações abertas (KUIELab MIT; checkpoints UVR/ZFTurbo MIT). — **[Inferência a partir dos repositórios hospedeiros]**
- **Stems**: Tipicamente vocals/instrumental e 4 stems nos checkpoints públicos; **não há checkpoint público de guitarra MDX-Net documentado com SDR** — os modelos de guitarra MDX23C conhecidos são os do MVSep (serviço). — **[Facto verificado quanto à ausência na documentação ZFTurbo/UVR]**
- **Link**: https://github.com/kuielab/sdx23 ; https://github.com/ZFTurbo/MVSEP-MDX23-music-separation-model

## 9. Moises / Music.AI (comercial)

- **Objetivo**: App/serviço comercial de separação e prática musical.
- **Oferta de guitarra**: Tem **separação dedicada de guitarra** e — único caso encontrado — **separação Lead vs. Rhythm guitar** e **Acoustic vs. Electric guitar** (cada opção divide a guitarra em 2 faixas, num total de 6: Vocals, Bass, Drums, Others + 2 guitarras). Disponível nos planos Premium e Pro (Pro com separação "Hi-Fi"). — **[Facto verificado em fontes secundárias e materiais oficiais Moises; página do blog devolveu 403 ao fetch direto]** [Fonte: https://moises.ai/newsroom/product-announcements/new-guitar-separation-models/]
- **Precisão publicada**: Nenhum SDR público para os modelos de guitarra. — **[Facto verificado: nenhuma métrica encontrada]**
- **Licença**: Proprietária; API comercial via Music.AI. A Moises publicou o dataset **MoisesDB** (240 músicas, taxonomia multi-stem incl. guitarra) para investigação. — **[Facto verificado]** [Fonte: https://arxiv.org/pdf/2307.15913]
- **Limitações**: Closed-source, sem métricas públicas, custo recorrente; sem garantia de qualidade da divisão lead/rhythm (sem benchmark independente encontrado).
- **Link oficial**: https://moises.ai

## 10. LALAL.AI (comercial)

- **Objetivo**: Serviço comercial de stem splitting (redes Phoenix → Orion → Perseus).
- **Oferta de guitarra**: Stems separados de **guitarra acústica** e **guitarra elétrica** (Orion suporta 7 stems: vocal, instrumental, drums, bass, piano e duas guitarras; Perseus, transformer-based, assumiu estes stems com melhoria anunciada de ~1 dB face ao Orion). **Não separa lead vs. rhythm** — a divisão é por tipo de instrumento (acústica/elétrica). — **[Facto verificado em blog oficial]** [Fonte: https://www.lalal.ai/blog/lalalai-perseus-supports-piano-guitars/ ; https://www.lalal.ai/blog/orion-ai-supports-4-new-stems/]
- **Precisão publicada**: Apenas claims internos ("1 dB melhor que Orion", "~15% melhor em vocais"); sem SDR em benchmark público. — **[Não verificado: números de marketing sem benchmark independente]**
- **Licença**: Proprietária, pay-per-minute.
- **Link oficial**: https://www.lalal.ai

## 11. Datasets relevantes para guitarra

- **MoisesDB** (Moises/Music.AI, ISMIR 2023): 240 faixas multitrack, taxonomia hierárquica de 11 stems. O stem "Guitar" subdivide-se em **acoustic guitar, clean electric guitar, distorted electric guitar** — **não existe etiqueta lead/rhythm**. Inclui baselines SDR (IBM, IRM, MWF, Demucs, Spleeter). — **[Facto verificado]** [Fonte: https://arxiv.org/pdf/2307.15913 ; https://github.com/moises-ai/moises-db]
- **MUSDB18/MUSDB18-HQ**: benchmark padrão, apenas 4 stems (vocals/drums/bass/other) — **não tem stem de guitarra**, pelo que a maioria dos SDR publicados na literatura não cobre guitarra. — **[Facto verificado]**
- **GuitarDuets** (arXiv 2507.01172, jul. 2025): dataset de duetos de guitarra clássica (real + sintetizado) e separação de duas guitarras com Residual Shuffle-Exchange Network — caso mais próximo de "guitarra vs. guitarra" na literatura, mas em contexto clássico, não lead/rhythm rock. — **[Facto verificado]** [Fonte: https://arxiv.org/abs/2507.01172]

---

## Respostas às questões-chave

### Q1 — Que modelos abertos produzem um stem dedicado de GUITARRA?
1. **Demucs `htdemucs_6s`** (MIT) — único modelo aberto amplamente disponível com stem de guitarra "out of the box". Qualidade admitida pelos autores como apenas "okay" para guitarra; repositório arquivado (jan. 2025); **sem SDR de guitarra publicado**. — **[Facto verificado]**
2. **Framework ZFTurbo + checkpoints comunitários/MVSep** (MIT) — arquiteturas SOTA (Mel-Band RoFormer/MDX23C) com modelos de guitarra no serviço MVSep; os docs oficiais do repositório não listam checkpoint de guitarra com SDR. — **[Facto verificado]**
3. Spleeter e Open-Unmix **não têm** stem de guitarra. — **[Facto verificado]**

### Q2 — Existe separação LEAD vs. RHYTHM guitar publicada?
- **Investigação académica**: **não foi encontrada evidência** de qualquer paper ISMIR/ICASSP/arXiv que faça separação lead vs. rhythm guitar como tarefa. O mais próximo: (a) separação hierárquica de sub-stems (arXiv 2410.20773 — sub-stems de bateria e vozes, não guitarra lead/rhythm); (b) GuitarDuets (duetos clássicos, 2 guitarras genéricas); (c) MoisesDB rotula guitarras por timbre (acústica/limpa/distorcida), não por função lead/rhythm. — **[Facto verificado quanto às pesquisas efetuadas; ausência de evidência ≠ inexistência absoluta]**
- **Comercial**: **Moises** é a única ferramenta encontrada que anuncia separação **Lead vs. Rhythm guitar** (e Acoustic vs. Electric), em planos Premium/Pro, sem métricas públicas. LALAL.AI separa apenas por tipo (acústica/elétrica). — **[Facto verificado]** [Fonte: https://moises.ai/newsroom/product-announcements/new-guitar-separation-models/]
- **Implicação para o RockForge**: separar lead/rhythm com modelos abertos exigiria treinar um modelo próprio; não há dataset público com etiquetas lead/rhythm, o que torna a tarefa de investigação, não de integração. — **[Inferência]**

### Q3 — Valores SDR publicados para stems de guitarra
- HTDemucs 6s (benchmark Multisong/ZFTurbo): guitar = "---" (não avaliado/publicado). — **[Facto verificado]**
- BS-RoFormer: 9,05 dB SDR "para guitarra" citado em fontes secundárias (Grokipedia) — **[Não verificado: não confirmado em paper; MUSDB18 não tem guitarra]**
- MVSep mantém leaderboard SDR de guitarra em https://mvsep.com/quality_checker/ (acesso direto bloqueado durante esta investigação). — **[Facto verificado quanto à existência]**
- Conclusão honesta: **praticamente não existem SDR de guitarra publicados em fontes primárias**; a métrica padrão (MUSDB18) não inclui guitarra.

---

## O que não foi possível verificar

1. **Números SDR concretos do leaderboard de guitarra do MVSep** — páginas mvsep.com devolveram HTTP 403 ao fetch automatizado; só foi confirmada a existência do leaderboard.
2. **O valor "9,05 dB SDR guitarra" do BS-RoFormer** — aparece em agregadores (Grokipedia) mas não foi localizado no paper original; tratar como não fiável.
3. **Qualidade real da separação lead/rhythm do Moises** — sem benchmark independente nem métricas publicadas; apenas marketing oficial.
4. **Detalhes/SDR dos modelos Perseus/Orion da LALAL.AI** — apenas claims relativos do blog oficial ("1 dB melhor"), sem benchmark público.
5. **Checkpoints comunitários de guitarra (ex.: "becruily guitar" Mel-Band RoFormer)** — mencionados em comunidades UVR/MVSep mas não confirmados em fonte primária com licença e métricas.
6. **Estado exato de manutenção do fork adefossez/demucs** — não inspecionado diretamente; o repo original confirma apenas "bug fixes" no sucessor.
