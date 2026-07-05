# Banquet — separação fina de guitarras (protótipo / spike)

**Estado: EXPERIMENTAL, fora do fluxo principal.** Nada aqui é importado pela
app nem pelo worker. É um banco de ensaio para avaliares o modelo **Banquet**
numa gravação tua *antes* de decidirmos integrá-lo no RockForge.

## Porquê

O separador atual (`DemucsSeparator`, `htdemucs_6s`) junta **todas as
guitarras** numa só stem "guitarra". O **Banquet** foi treinado no **MoisesDB**,
que trata **guitarra elétrica**, **acústica**, **limpa** e **distorcida** como
classes distintas — por isso consegue isolar, p.ex., a acústica da elétrica, o
que o nosso Demucs não faz.

- Repo: <https://github.com/kwatcharasupat/query-bandit> — **licença MIT**.
- Paper: *A Stem-Agnostic Single-Decoder System for Music Source Separation
  Beyond Four Stems* (arXiv 2406.18747). No MoisesDB **bate o htdemucs_6s** nas
  stems de guitarra e piano, com ~25M parâmetros.
- Pesos: Zenodo <https://zenodo.org/records/13694558> (usar `ev-pre-aug.ckpt`).

## O limite que NÃO desaparece (honestidade)

O Banquet separa por **classe de instrumento**, não por faixa/papel. **Duas
guitarras da mesma classe** a tocar ao mesmo tempo (ex.: Lead + Rhythm ambas
distorcidas) **continuam a não se separar** — não há assinatura espetral que as
distinga. O Banquet ajuda quando as guitarras são de **tipos diferentes**
(acústica vs. elétrica, ou limpa vs. distorcida). Para duas iguais, o caminho
continua a ser a **fonte sintetizada por arranjo** que já existe na app.

## É "query-based"

Dás-lhe um **clip de referência** (`--query`) do instrumento a extrair — um
excerto curto de guitarra acústica limpa, de elétrica distorcida, etc. O modelo
usa esse exemplo para saber que classe isolar. Guarda alguns clips de referência
por classe (ver `queries/` — cria a pasta e mete lá os teus exemplos).

## Como correr

1. Clona e instala o Banquet (precisa de PyTorch; GPU fortemente recomendada):
   ```bash
   git clone https://github.com/kwatcharasupat/query-bandit.git
   cd query-bandit
   pip install -r requirements.txt   # confirma o ficheiro de deps no repo
   export CONFIG_ROOT="./config"
   ```
2. Descarrega `ev-pre-aug.ckpt` de <https://zenodo.org/records/13694558>.
3. Corre a inferência — comando nativo do repo (o wrapper aqui só o monta):
   ```bash
   python train.py inference_byoq \
     --ckpt_path=/caminho/ev-pre-aug.ckpt \
     --input_path=/caminho/musica.wav \
     --output_path=/caminho/saida/guitarra.wav \
     --query_path=/caminho/queries/eletrica-distorcida.wav \
     --batch_size=12 \
     --use_cuda=true
   ```
   (batch 12 cabe tipicamente numa RTX 4090; baixa o `--batch_size` se faltar
   memória, ou `--use_cuda=false` para CPU — lento.)

Ou usa o wrapper deste diretório, que valida caminhos e monta o comando:
```bash
python experiments/banquet/run_banquet.py \
  --repo /caminho/query-bandit \
  --ckpt /caminho/ev-pre-aug.ckpt \
  --input /caminho/musica.wav \
  --query /caminho/queries/eletrica-distorcida.wav \
  --out /caminho/saida/guitarra.wav
# --cpu para forçar CPU; --batch-size N para ajustar
```

## Se a qualidade for boa → integração

O passo seguinte seria um adaptador `BanquetSeparator` a implementar o port
`application.ports.StemSeparator` (a par do `DemucsSeparator`), com o Demucs a
manter-se por defeito e o Banquet como opção "separação fina" na UI, com clips
de referência embutidos por classe. Fica registado no `TODO.md`.
