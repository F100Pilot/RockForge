### New

- **Your guitar and your bass:** in Settings → **Tones and AI** you say which pickups you have, how strong they are and the instrument's name. The driven tones the detection and the suggestions propose now come fitted to them (hot or active pickups with less gain and the noise gate a little more closed; single coils and P90s with the noise gate more closed because of their hum; a weak guitar with a little more gain), with a mark that says what changed. It is a rule of thumb, not a measurement: check by ear.

- **Describe the sound:** in the tone editor, you write in a few words the sound you want ("AC/DC crunch") and RockForge makes a tone with the game's gear. It works with an assistant connected (below) or by copying the request into ChatGPT and pasting its answer.

- **Ask the AI without copying and pasting:** in Settings → Tones and AI you connect an assistant — **OpenRouter** (you sign in with your account; there are free models), **Google Gemini** (your key) or **Ollama** (a model on your computer, offline). Then **Ask the AI** in "Import tones from a text" and in "Describe the sound" sends the request and reads the answer. Before a paid model it says how much it should cost and asks. The key stays on your computer only and nothing is asked until you press the button.

### Fixes

- **A Songsterr tab no longer plays at the bass's tempo:** sometimes only the bass part downloaded, and the whole song took its tempo, which on Songsterr changes almost every bar, so the rest drifted from the recording. Each part is now asked for by the number Songsterr stores it under, in both places it can be, so they all arrive. Repeats with different endings (1st and 2nd time) are read too: each ending plays on its own pass. (GitHub #26)

---

### Novidades

- **A tua guitarra e o teu baixo:** em Definições → **Tons e IA** dizes que captadores tens, a força deles e o nome do instrumento. Os tons com distorção que a deteção e as sugestões propõem passam a vir ajustados para eles (captadores fortes ou ativos com menos ganho e o noise gate um pouco mais fechado; single coils e P90 com o noise gate mais fechado por causa do ruído; uma guitarra fraca com um pouco mais de ganho), com uma marca que diz o que mudou. É uma regra prática, não uma medição: confere de ouvido.

- **Descrever o som:** no editor de tons, escreves em poucas palavras o som que queres ("crunch dos AC/DC") e o RockForge faz um tom com o equipamento do jogo. Funciona com um assistente ligado (abaixo) ou copiando o pedido para o ChatGPT e colando a resposta.

- **Perguntar à IA sem copiar e colar:** em Definições → Tons e IA ligas um assistente — **OpenRouter** (entras com a tua conta; há modelos grátis), **Google Gemini** (a tua chave) ou **Ollama** (um modelo no teu computador, sem internet). Depois, **Perguntar à IA** em "Importar tons de um texto" e em "Descrever o som" envia o pedido e lê a resposta. Antes de um modelo pago diz quanto deve custar e pergunta. A chave fica só no teu computador e nada é pedido até carregares no botão.

### Correções

- **Um tab do Songsterr já não fica no andamento do baixo:** às vezes só a pista do baixo chegava a descarregar e a música inteira ficava com o andamento dele, que no Songsterr muda quase a cada compasso; o resto da música desacertava da gravação. Agora cada pista é pedida pelo número com que o Songsterr a guarda, e nos dois sítios onde pode estar, por isso chegam todas. As repetições com finais diferentes (1.ª e 2.ª vez) também passam a ser lidas: cada final toca na sua passagem. (GitHub #26)
