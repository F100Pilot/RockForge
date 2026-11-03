### New

- **The bend's shape in the note editor:** besides how far it rises, you choose whether it rises across the note, rises and holds, rises, holds and releases, or is a pre-bend (which may release), and the seconds when it starts to rise, is fully up and comes back. On the score a teal line over the tail shows the shape, and the preview makes the bend sound. (GitHub #21)

### Fixes

- **A bend set in the note editor did not stay in the song:** the amount was saved but the note was not marked as a bend, so it did not show on the score and the rebuild wrote it without a bend. It is now marked, shown and heard — and bends that come from the Guitar Pro file are heard in the preview too. (GitHub #21)

- **Songsterr refused every tab with a 403:** the same address opened in the browser, but RockForge's request was refused by a page in front of the API. When that happens, RockForge now asks again the way a browser asks; if it is still refused, the message says the answer came from a protection page and not from Songsterr, and suggests the `.gp` file exported from Songsterr. Not yet tried against the real Songsterr. (GitHub #22)

- **Bass tones always distorted:** "Detect tone" offered the bass tones that were almost always distorted, even for a clean bass, because the measure it used (made for the guitar) gave a clean bass and a distorted one practically the same value. The four bass tones now come from clean to distorted, with no percentage and each with **Listen (approximation)**: they are not measured on the recording, listen to them and choose. (GitHub #16)

---

### Novidades

- **A forma do bend no editor de notas:** além de quanto sobe, escolhes se sobe ao longo da nota, sobe e fica, sobe, fica e volta, ou é um pré-bend (que pode voltar), e os segundos em que começa a subir, chega ao alto e volta. Na partitura, uma linha verde-água sobre a cauda mostra a forma, e a pré-escuta faz o bend soar. (GitHub #21)

### Correções

- **Um bend posto no editor de notas não ficava na música:** guardava-se a quantidade mas a nota não era marcada como bend, por isso não aparecia na partitura e a reconstrução escrevia-a sem bend. Agora fica marcada, aparece e ouve-se — e os bends que vêm do ficheiro Guitar Pro também se ouvem na pré-escuta. (GitHub #21)

- **O Songsterr recusava todas as tabs com um 403:** o mesmo endereço abria no browser, mas o pedido do RockForge era recusado por uma página à frente da API. Quando isso acontece, o RockForge pede outra vez como um browser pede; se mesmo assim for recusado, a mensagem diz que a resposta veio de uma página de proteção e não do Songsterr, e sugere o ficheiro `.gp` exportado do Songsterr. Ainda não foi experimentado contra o Songsterr real. (GitHub #22)

- **Tons de baixo sempre distorcidos:** «Detetar tom» propunha para o baixo tons quase sempre com distorção, mesmo para um baixo limpo, porque a medida usada (feita para a guitarra) dava praticamente o mesmo valor a um baixo limpo e a um distorcido. Os quatro tons de baixo aparecem agora do limpo ao distorcido, sem percentagem e cada um com **Ouvir (aproximação)**: não são medidos na gravação, ouve-os e escolhe. (GitHub #16)
