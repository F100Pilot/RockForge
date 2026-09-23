# ML no .exe — delegar as fases pesadas a um Python externo

## O que eu disse antes estava incompleto

Escrevi "stems, tom, letra: ❌ **nunca** no .exe". Isso só é verdade para
imports **dentro do processo**. Verificado no código:

| fase | como corre hoje | importável no .exe? |
|---|---|---|
| Demucs (stems, tom, letra) | `subprocess(sys.executable, _demucs_patcher.py)` | não precisa |
| WhisperX (letra) | `subprocess(sys.executable, _whisperx_runner.py)` | não precisa |
| Banquet (stems) | `subprocess(sys.executable, train.py)` | não precisa |
| librosa (tom, "Corrigir daqui", afinação) | `import librosa` in-process | **precisa** |

4 dos 5 já são subprocessos. O que os parte no .exe é uma coisa só:
`sys.executable` é o **próprio .exe**, não um Python — relançaria o RockForge.

## Plano

- [ ] 1. `Settings.ml_python` + override em `runtime_settings` (editável na UI)
- [ ] 2. `infrastructure/ml_python.py`: resolve o interpretador + acha os runners
      (no bundle os `.py` não existem em disco — têm de vir por `_MEIPASS`)
- [ ] 3. Trocar os 4 `sys.executable` pelo resolver
- [ ] 4. `_librosa_runner.py` standalone (padrão do `_whisperx_runner.py`, zero
      imports de rockforge) para as 3 funções librosa; in-process quando dá
- [ ] 5. `diagnostics`: sondar o Python externo por subprocesso; corrigir a
      mensagem "NÃO é possível no .exe"
- [ ] 6. `/settings` + campo na modal ⚙️ com validação ✓/✗
- [ ] 7. `rockforge.spec`: embarcar os runners como datas
- [ ] 8. Testes + docs (CLAUDE.md, README, TESTING)

## Invariantes a não partir

- Sem o Python externo configurado, o .exe comporta-se exactamente como hoje
  (503 a nomear o que falta) — nada de crash novo.
- Correr por `start.bat` não muda nada: in-process continua a ser o caminho.
- A API nunca importa torch/librosa (regra de layering do CLAUDE.md) — a sonda
  do interpretador externo é um subprocesso.

## Estado

- [x] 1. `Settings.ml_python` + override em `runtime_settings`
- [x] 2. `infrastructure/ml_python.py` (resolve / availability / runner_path / run_json)
- [x] 3. Os 4 `sys.executable` trocados — guardado por AST, verificado com mutante
- [x] 4. `_librosa_runner.py` (uma implementação, dois transportes)
- [x] 5. `diagnostics` corrigido + linha nova "Python 3.11 para o ML"
- [x] 6. `/settings` + campo na modal com ✓/✗ por extra
- [x] 7. `rockforge.spec` embarca os runners (walk, guardado por teste)
- [x] 8. Docs
