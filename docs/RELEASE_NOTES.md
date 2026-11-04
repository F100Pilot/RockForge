### New

- **A new progress bar while building:** in "Status and export", the steps are no longer chips with technical names (`parse_gp`, `build_arrangements`…). You now see the current step in words, "Step 2 of 6" and the percentage, a bar that fills (green at the end, red if it fails) and the six steps joined by a line: ✓ on the ones done, a turning ring on the current one, ✕ on the step it failed at. The status at the top of the project names the step in words too.

- **The separated bass is measured in tone detection:** with the help of four real basses a user sent, "Detect tone" now listens to the separated bass. When it sounds heavily distorted, the bass tones come from distorted to clean; otherwise from clean to distorted, as before. It only tells a heavily distorted bass from the rest (a light overdrive reads as clean), so there is still no percentage: listen and choose. (GitHub #16)

### Changed

- **The install counter moved to another server:** if you said yes, the install is now counted on a server of the project at Netlify instead of Supabase. It is still only a random number, the version, the kind of install and the system, with no IP address, and turning it off still deletes what was sent. The counts so far were copied over.

---

### Novidades

- **Uma barra de progresso nova na construção:** em «Estado e exportar», os passos deixaram de ser pastilhas com nomes técnicos (`parse_gp`, `build_arrangements`…). Agora vês o passo em curso por extenso, «Passo 2 de 6» e a percentagem, uma barra que avança (verde no fim, vermelha se falhar) e os seis passos ligados por uma linha: ✓ nos feitos, um anel a rodar no atual, ✕ no passo onde falhou. O estado no topo do projeto também diz o passo por extenso.

- **O baixo separado é medido na deteção de tons:** com a ajuda de quatro baixos reais enviados por um utilizador, o «Detetar tom» passou a ouvir o baixo separado. Quando soa muito distorcido, os tons de baixo aparecem do distorcido ao limpo; senão, do limpo ao distorcido, como até aqui. Só distingue um baixo muito distorcido do resto (um overdrive ligeiro lê-se como limpo), por isso continua sem percentagem: ouve e escolhe. (GitHub #16)

### Alterado

- **O contador de instalações mudou de servidor:** quem disse que sim passa a ser contado num servidor do projeto no Netlify, em vez do Supabase. Continua a ser só um número ao acaso, a versão, o tipo de instalação e o sistema, sem endereço IP, e desligá-lo continua a apagar o que foi enviado. As contagens que já existiam foram copiadas.
