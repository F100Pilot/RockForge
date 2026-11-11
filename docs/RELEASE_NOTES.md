### Fixes

- **Songsterr lets tabs be imported again ("Access declined"):** Songsterr started refusing with a 403 ("Access declined") requests that do not look like a browser's, so importing a tab and looking up its videos failed. RockForge now asks the way a browser asks, as the guitar-pro-youtube-sync tool did for the same error. If the refusal stands, the message says at which address and what to try (later, or the `.gp` exported from Songsterr). An unpublished tab is still refused at once.

- **A chord with one muted string no longer comes out fully muted in the game:** when the GP file marks only one string of a chord as dead (the X of tab), the `.psarc` muted the whole chord, and the game showed only X. Now only that string is muted. The score also shows those notes as an **X** (they used to look like an ordinary note), and the note editor has **Dead note (X)** to untick it. "Check PSARC" points out this fault in `.psarc` files built before: rebuild them.

---

### Correções

- **O Songsterr volta a deixar importar tabs ("Access declined"):** o Songsterr passou a recusar com um 403 ("Access declined") os pedidos que não parecem vir de um browser, e a importação de tabs e a procura de vídeos falhavam. O RockForge passa a pedir como um browser pede, como fez a ferramenta guitar-pro-youtube-sync para o mesmo erro. Se a recusa se mantiver, a mensagem diz em que endereço foi e o que tentar (mais tarde, ou o `.gp` exportado do Songsterr). Uma tab por publicar continua a ser recusada logo.

- **Um acorde com uma corda abafada já não sai todo abafado no jogo:** quando o ficheiro GP marca uma só corda de um acorde como abafada (o X da tablatura), o `.psarc` abafava o acorde inteiro, e no jogo apareciam só X. Agora só essa corda vai abafada. A pauta também mostra essas notas como **X** (antes apareciam como uma nota normal), e a edição de nota tem **Abafada (X)** para a desmarcar. "Verificar PSARC" aponta esta falha nos `.psarc` construídos antes: reconstrói-os.
