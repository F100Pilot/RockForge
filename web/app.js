// A stroke icon from the sprite at the top of index.html. A declaration, not a
// const: some tables near the top of this file build their markup at load.
function icon(name, cls = '') {
  return `<svg class="ic${cls ? ' ' + cls : ''}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
}

// ── Modern file inputs ───────────────────────────────────────────────────────
document.querySelectorAll('.file-drop').forEach(drop => {
  const inp = drop.querySelector('input[type="file"]');
  const txt = drop.querySelector('.file-drop-text');
  const placeholder = txt.textContent;
  txt.dataset.default = placeholder;  // so the wizard reset can restore it
  inp.addEventListener('change', () => {
    if (inp.files.length) {
      txt.textContent = inp.files[0].name;
      drop.classList.add('has-file');
    } else {
      txt.textContent = placeholder;
      drop.classList.remove('has-file');
    }
  });
  drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('drag-over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('drag-over'));
  drop.addEventListener('drop', () => drop.classList.remove('drag-over'));
});

// ── "Novo projeto" creation wizard ────────────────────────────────────────────
// Steps: 1 GP file (→ inspect), 2 tracks, 3 recording+offset, 4 details.
// Step 1 is its own form (submit = inspect); steps 2-4 share gpJobForm
// (submit = create). Nav is a shared footer; "Seguinte" on step 1 triggers the
// inspect, which advances to step 2 on success.
let wizardStep = 1;
const WIZARD_MAX = 4;

function setWizardStep(n) {
  wizardStep = Math.min(WIZARD_MAX, Math.max(1, n));
  document.querySelectorAll('#newJobOverlay .wizard-pane').forEach(p => {
    p.hidden = Number(p.dataset.step) !== wizardStep;
  });
  document.querySelectorAll('#wizardSteps .wz-dot').forEach(d => {
    const s = Number(d.dataset.s);
    d.classList.toggle('active', s === wizardStep);
    d.classList.toggle('done', s < wizardStep);
  });
  // Step 1 has no data yet → hide "Anterior"; last step swaps "Seguinte" for "Criar".
  document.getElementById('wizardPrev').style.visibility = wizardStep > 1 ? '' : 'hidden';
  document.getElementById('wizardNext').style.display = wizardStep < WIZARD_MAX ? '' : 'none';
  document.getElementById('wizardCreate').style.display = wizardStep < WIZARD_MAX ? 'none' : '';
  if (wizardStep === WIZARD_MAX) maybeAutoAlbumSearch();
}

// Validate the current step before advancing. Returns true if OK.
function validateWizardStep() {
  if (wizardStep === 1) {
    if (!document.querySelector('#gpInspectForm input[name=file]').files.length && !songsterrImported) {
      toast('Escolhe um ficheiro Guitar Pro ou importa a tab do Songsterr.'); return false;
    }
  } else if (wizardStep === 2) {
    const anyTrack = ['lead_track', 'rhythm_track', 'combo_track', 'alt_lead_track', 'alt_rhythm_track']
      .some(n => document.querySelector(`#gpJobForm select[name=${n}]`).value !== '');
    if (!anyTrack) { toast('Atribui pelo menos uma pista.'); return false; }
  } else if (wizardStep === 3) {
    if (!usingEmbeddedAudio() && !ytAudio && !document.querySelector('#gpJobForm input[name=audio]').files.length) {
      toast('Escolhe a gravação (áudio) da música ou descarrega a do vídeo.'); return false;
    }
  }
  return true;
}

// A GP8 file can carry its own recording — the exact audio its sync points were
// made against. When it does, the wizard uses it instead of asking for an
// upload (an upload of the ORIGINAL file can start earlier: tools that build
// these files trim the intro before embedding, and that is a constant offset).
function usingEmbeddedAudio() {
  const row = document.getElementById('gpEmbeddedAudioRow');
  return !row.hidden && document.getElementById('useEmbeddedAudio').checked;
}
function applyEmbeddedAudioChoice() {
  // The GP8 file's own audio, or the chosen YouTube video's (fetched), both
  // stand in for an upload.
  const provided = usingEmbeddedAudio() || !!ytAudio;
  document.getElementById('gpAudioUploadField').hidden = provided;
  // `required` would block the submit on a field the user never needs to fill.
  document.querySelector('#gpJobForm input[name=audio]').required = !provided;
}
// The chosen YouTube video's audio, fetched by /youtube/audio: {token, videoId, name, size}.
let ytAudio = null;
document.getElementById('useEmbeddedAudio').addEventListener('change', applyEmbeddedAudioChoice);

// Songsterr's per-measure timestamps for the chosen video (null = not used).
// Only the times travel; the recording is the user's own.
let songsterrSong = null;
let songsterrPoints = null;
const SONGSTERR_FEATURES = {
  alternative: 'vídeo alternativo', backing: 'backing track', solo: 'solo', playthrough: 'playthrough',
};
function resetSongsterr() {
  songsterrSong = null; songsterrPoints = null;
  document.getElementById('songsterrBlock').open = false;  // an extra: closed unless wanted
  document.getElementById('songsterrLink').value = '';
  document.getElementById('songsterrVideo').hidden = true;
  document.getElementById('songsterrInfo').textContent = '';
  ytAudio = null;
  document.getElementById('ytAudioRow').hidden = true;
  document.getElementById('ytAudioInfo').textContent = '';
  document.getElementById('ytCookies').value = '';
}
function applySongsterrVideo() {
  const sel = document.getElementById('songsterrVideo');
  const info = document.getElementById('songsterrInfo');
  const v = songsterrSong && sel.value !== '' ? songsterrSong.videos[Number(sel.value)] : null;
  songsterrPoints = v ? v.points : null;
  document.getElementById('ytAudioRow').hidden = !v;
  // Audio fetched for ANOTHER video does not match these times.
  if (ytAudio && (!v || ytAudio.videoId !== v.video_id)) {
    ytAudio = null;
    document.getElementById('ytAudioInfo').textContent = '';
    applyEmbeddedAudioChoice();
  }
  if (!v) { info.textContent = 'Tempos do Songsterr não usados.'; return; }
  const start = v.points[0];
  // Bar 1's instant in THAT video — right as the start when the MP3 is the
  // whole video; a trimmed copy starts earlier, and the user adjusts.
  document.querySelector('#gpJobForm input[name=offset_s]').value = start.toFixed(3);
  info.innerHTML = `${icon('check')} ${v.points.length} compassos com tempo marcado. Os tempos são do vídeo ` +
    `<a href="${esc(v.url)}" target="_blank" rel="noopener">${esc(v.url)}</a> — a gravação tem de ser o áudio desse vídeo ` +
    '(descarrega-o abaixo, ou carrega um MP3 convertido dele; o áudio do próprio Songsterr é outro e não bate). ' +
    `O compasso 1 começa em <b>${start.toFixed(3)} s</b> desse vídeo; já pus esse valor em "Início da música". ` +
    'Se o teu MP3 foi cortado no início, ajusta-o.';
}
document.getElementById('songsterrVideo').addEventListener('change', applySongsterrVideo);
document.getElementById('songsterrFetch').addEventListener('click', () => fetchSongsterrVideos());
async function fetchSongsterrVideos() {
  const link = document.getElementById('songsterrLink').value.trim();
  const info = document.getElementById('songsterrInfo');
  const sel = document.getElementById('songsterrVideo');
  if (!link) { toast('Cola o link da música no Songsterr.'); return; }
  info.textContent = 'a procurar no Songsterr…';
  try {
    songsterrSong = await getJSON(`/songsterr?song=${encodeURIComponent(link)}`);
  } catch (err) {
    songsterrSong = null; songsterrPoints = null; sel.hidden = true;
    info.textContent = `Erro: ${err.message || err}`;
    return;
  }
  sel.innerHTML = '<option value="">— não usar os tempos do Songsterr —</option>' +
    songsterrSong.videos.map((v, i) =>
      `<option value="${i}">${esc(v.feature ? (SONGSTERR_FEATURES[v.feature] || v.feature) : 'Vídeo principal')}` +
      ` · ${v.points.length} compassos · ${esc(v.url)}</option>`).join('');
  sel.value = '0';
  sel.hidden = false;
  applySongsterrVideo();
  return true;
}

async function downloadYtAudio() {
  const sel = document.getElementById('songsterrVideo');
  const v = songsterrSong && sel.value !== '' ? songsterrSong.videos[Number(sel.value)] : null;
  if (!v) return;
  const info = document.getElementById('ytAudioInfo');
  const btn = document.getElementById('ytAudioBtn');
  const browser = document.getElementById('ytCookies').value;
  btn.disabled = true;
  info.textContent = `A descarregar o áudio de ${v.url}… (pode demorar um minuto)`;
  try {
    const b = await getJSON('/youtube/audio', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video_id: v.video_id, cookies_browser: browser || null }),
    });
    ytAudio = { token: b.audio_token, videoId: v.video_id, name: b.name, size: b.size_bytes };
    info.innerHTML = `${icon('check')} Áudio do vídeo descarregado (${(b.size_bytes / 1048576).toFixed(1)} MB) — ` +
      'vai ser usado como gravação; não precisas de carregar nenhum ficheiro.';
  } catch (err) {
    ytAudio = null;
    info.textContent = `Não consegui descarregar: ${err.message}. ` +
      'Podes tentar de novo com a sessão de um browser, ou carregar um MP3 do vídeo.';
  } finally {
    btn.disabled = false;
    applyEmbeddedAudioChoice();
  }
}
document.getElementById('ytAudioBtn').addEventListener('click', downloadYtAudio);

function openNewJobModal() {
  document.getElementById('newJobOverlay').hidden = false;
  document.getElementById('gpInspectForm').reset();
  document.getElementById('gpJobForm').reset();
  document.getElementById('gpEmbeddedAudioRow').hidden = true;  // until a file says it has one
  applyEmbeddedAudioChoice();
  resetSongsterr();
  resetWizardAlbum();
  songsterrImported = false;
  document.getElementById('songsterrImportInfo').textContent = '';
  document.querySelectorAll('#newJobOverlay .file-drop').forEach(d => {
    d.classList.remove('has-file');
    const t = d.querySelector('.file-drop-text');
    if (t) t.textContent = t.dataset.default || t.textContent;
  });
  gpToken = null;
  setWizardStep(1);
}
function closeNewJobModal() { document.getElementById('newJobOverlay').hidden = true; }
document.getElementById('newJobClose').addEventListener('click', closeNewJobModal);
document.getElementById('wizardPrev').addEventListener('click', () => setWizardStep(wizardStep - 1));
document.getElementById('wizardNext').addEventListener('click', () => {
  if (!validateWizardStep()) return;
  // Step 1's "Seguinte" runs the inspect; its success handler advances to step 2.
  if (wizardStep === 1) {
    if (songsterrImported && !document.querySelector('#gpInspectForm input[name=file]').files.length) {
      setWizardStep(2); return;
    }
    document.getElementById('gpInspectForm').requestSubmit(); return;
  }
  setWizardStep(wizardStep + 1);
});
// Modals that hold typed input (new project, batch, info edit, tones,
// settings) close ONLY from their own ✕/Cancelar — never from a click on the
// backdrop. A press that starts in a field (selecting text, a trackpad tap
// that drifts) and is released outside the box is dispatched as a click on
// the backdrop, so "click outside to close" threw away a half-filled wizard.
// Only the read-only ⓘ box and the confirm dialog still close from outside.
//
// A file dropped anywhere that is not a drop zone must not reach the browser:
// its default action is to OPEN the file, navigating away from the app (the
// wizard and everything typed in it gone).
const isDropZone = t => !!(t && t.closest) && !!t.closest('.file-drop, #homeDrop');
document.addEventListener('dragover', e => {
  if (isDropZone(e.target)) return;
  e.preventDefault();
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'none';
});
document.addEventListener('drop', e => { if (!isDropZone(e.target)) e.preventDefault(); });
document.querySelectorAll('[data-new]').forEach(b => {
  b.addEventListener('click', () => openNewJobModal(b.dataset.new));
});
// The home page's drop card: a Guitar Pro file dropped on it opens the wizard
// with that file already chosen, as if it had been picked in step 1.
const homeDrop = document.getElementById('homeDrop');
homeDrop.addEventListener('dragover', e => { e.preventDefault(); homeDrop.classList.add('drag-over'); });
homeDrop.addEventListener('dragleave', () => homeDrop.classList.remove('drag-over'));
homeDrop.addEventListener('drop', e => {
  e.preventDefault();
  homeDrop.classList.remove('drag-over');
  if (!e.dataTransfer || !e.dataTransfer.files.length) return;
  openNewJobModal('gp');
  const inp = document.querySelector('#gpInspectForm input[type=file]');
  inp.files = e.dataTransfer.files;
  inp.dispatchEvent(new Event('change'));
});
fetch('/version').then(r => r.json()).then(d => {
  document.getElementById('appVersion').textContent = 'v' + d.version;
}).catch(() => {});

// ── Batch processing: several (GP, audio) pairs, created one job at a time ───
// No new backend endpoint — this loops the same /gp/inspect + /jobs/gp calls
// the single-project wizard makes, so each pair gets exactly the same
// auto-pick-tracks / metadata-fallback behavior as creating one job by hand.
let batchPairs = [];  // [{gp: File, audio: File|null, status: 'pending'|'working'|'done'|'error', jobId, error}]

function batchStem(f) { return f.name.replace(/\.[^.]+$/, '').toLowerCase(); }

function pairBatchFiles(gpFiles, audioFiles) {
  const audioByStem = new Map(audioFiles.map(f => [batchStem(f), f]));
  const used = new Set();
  const pairs = gpFiles.map(gp => {
    const m = audioByStem.get(batchStem(gp));
    if (m && !used.has(m)) { used.add(m); return { gp, audio: m, status: 'pending' }; }
    return { gp, audio: null, status: 'pending' };
  });
  // Fill unmatched GP files with leftover audio files, in the order both were chosen.
  const leftover = audioFiles.filter(f => !used.has(f));
  let li = 0;
  for (const p of pairs) if (!p.audio && li < leftover.length) p.audio = leftover[li++];
  return pairs;
}

function renderBatchPairs() {
  const el = document.getElementById('batchPairsList');
  const submitBtn = document.getElementById('batchSubmit');
  if (!batchPairs.length) {
    el.innerHTML = '<span class="meta">Escolhe os ficheiros GP e as gravações acima.</span>';
    submitBtn.disabled = true;
    return;
  }
  const STATUS_ICO = { pending: icon('clock'), working: icon('clock'), done: icon('check'), error: icon('x') };
  el.innerHTML = batchPairs.map(p => `<div class="anchor-row">
    ${STATUS_ICO[p.status] || ''} <b>${esc(p.gp.name)}</b> → ${p.audio ? esc(p.audio.name) : '<span style="color:#e88">sem gravação — não vai ser criado</span>'}
    ${p.error ? `<span style="color:#e88">(${esc(p.error)})</span>` : ''}
  </div>`).join('');
  submitBtn.disabled = !batchPairs.some(p => p.audio && p.status === 'pending');
}

function openBatchModal() {
  document.getElementById('batchGpFiles').value = '';
  document.getElementById('batchAudioFiles').value = '';
  document.getElementById('batchArtist').value = '';
  document.getElementById('batchAlbum').value = '';
  document.getElementById('batchYear').value = '';
  batchPairs = [];
  renderBatchPairs();
  document.getElementById('batchOverlay').hidden = false;
}
function closeBatchModal() { document.getElementById('batchOverlay').hidden = true; }
document.getElementById('openBatchModal').addEventListener('click', openBatchModal);
document.getElementById('batchClose').addEventListener('click', closeBatchModal);
document.getElementById('batchClose2').addEventListener('click', closeBatchModal);
function refreshBatchPairing() {
  const gpFiles = [...document.getElementById('batchGpFiles').files];
  const audioFiles = [...document.getElementById('batchAudioFiles').files];
  batchPairs = gpFiles.length ? pairBatchFiles(gpFiles, audioFiles) : [];
  renderBatchPairs();
}
document.getElementById('batchGpFiles').addEventListener('change', refreshBatchPairing);
document.getElementById('batchAudioFiles').addEventListener('change', refreshBatchPairing);

document.getElementById('batchSubmit').addEventListener('click', async () => {
  const submitBtn = document.getElementById('batchSubmit');
  submitBtn.disabled = true;
  const artist = document.getElementById('batchArtist').value.trim();
  const album = document.getElementById('batchAlbum').value.trim();
  const year = document.getElementById('batchYear').value.trim();
  let okCount = 0, errCount = 0;
  for (const p of batchPairs) {
    if (!p.audio || p.status !== 'pending') continue;
    p.status = 'working';
    renderBatchPairs();
    try {
      const inspectForm = new FormData();
      inspectForm.append('file', p.gp);
      const insR = await fetch('/gp/inspect', { method: 'POST', body: inspectForm });
      const insBody = await insR.json();
      if (!insR.ok) throw new Error(insBody.detail || 'falha ao inspecionar o GP');
      const jobForm = new FormData();
      jobForm.append('gp_token', insBody.gp_token);
      jobForm.append('audio', p.audio);
      if (artist) jobForm.append('artist', artist);
      if (album) jobForm.append('album', album);
      if (year) jobForm.append('year', year);
      // Track fields left blank on purpose: the backend's auto_pick_tracks
      // heuristic (name-based) fills Lead/Rhythm in, same as a lone-track pick
      // in the normal wizard when nothing is assigned.
      const jobR = await fetch('/jobs/gp', { method: 'POST', body: jobForm });
      const jobBody = await jobR.json();
      if (!jobR.ok) throw new Error(jobBody.detail || 'falha ao criar o projeto');
      p.status = 'done';
      p.jobId = jobBody.id;
      okCount++;
    } catch (e) {
      p.status = 'error';
      p.error = (e && e.message) || 'erro';
      errCount++;
    }
    renderBatchPairs();
  }
  toast(`Lote concluído: ${okCount} criado(s)${errCount ? `, ${errCount} com erro` : ''}.`, errCount ? 'err' : 'ok');
  refreshJobs();
});

// ── "Definições" modal (stem-separator backend + Banquet paths) ───────────────
function toggleBanquetConfig() {
  const on = document.querySelector('input[name=sepBackend]:checked')?.value === 'banquet';
  document.getElementById('banquetConfig').style.display = on ? '' : 'none';
}
function renderBanquetValidation(b) {
  const ok = '<span style="color:#3fdc8a">✓</span>', bad = '<span style="color:#e88">✗</span>';
  document.getElementById('sVrepo').innerHTML = b.repo_ok ? ok : bad;
  document.getElementById('sVckpt').innerHTML = b.ckpt_ok ? ok : bad;
  document.getElementById('sVqueries').innerHTML = b.queries_ok ? ok : bad;
  const names = b.query_names || [];
  document.getElementById('sQueryNames').textContent = names.length
    ? `Stems detetados: ${names.join(', ')}` : '';
}
// Which extras the interpreter that will actually RUN the ML has — asked of
// IT, in a subprocess, not of the API process (which must never import torch,
// and in the .exe is a different Python entirely).
function renderMlPythonInfo(i) {
  const el = document.getElementById('sMlPythonInfo');
  if (!el) return;
  const ok = '<span style="color:#3fdc8a">✓</span>', bad = '<span style="color:#e88">✗</span>';
  if (!i.path) {
    // In the .exe there is no fallback: its own interpreter is the executable.
    el.innerHTML = i.frozen
      ? '<span style="color:#e0a54a">Por definir — sem isto o .exe não faz stems, tom, letra nem «Corrigir daqui».</span>'
      : 'Vazio: usa o próprio Python do RockForge.';
    return;
  }
  if (!i.python_ok) {
    el.innerHTML = `${bad} esse caminho não arrancou como Python — aponta ao <code>python.exe</code> do Python 3.11.`;
    return;
  }
  el.innerHTML = `${ok} Python encontrado &nbsp; ` +
    `${i.ml_ok ? ok : bad} <code>[ml]</code> (stems, tom, «Corrigir daqui») &nbsp; ` +
    `${i.lyrics_ok ? ok : bad} <code>[lyrics]</code> (letra) &nbsp; ` +
    `${i.torch_ok ? ok : bad} PyTorch`;
}

function fillSettings(s) {
  for (const r of document.querySelectorAll('input[name=sepBackend]'))
    r.checked = r.value === (s.stem_separator || 'demucs');
  document.getElementById('sBanquetRepo').value = s.banquet_repo || '';
  document.getElementById('sBanquetCkpt').value = s.banquet_ckpt || '';
  document.getElementById('sBanquetQueries').value = s.banquet_queries || '';
  document.getElementById('sLoudness').value = s.loudness_target ?? -12;
  document.getElementById('gpuOk').style.display = s.gpu_broken ? 'none' : '';
  document.getElementById('gpuBroken').style.display = s.gpu_broken ? '' : 'none';
  document.getElementById('sWhisperxCompute').value = s.whisperx_compute_type || '';
  document.getElementById('sMlPython').value = s.ml_python || '';
  renderMlPythonInfo(s.ml_python_info || {});
  toggleBanquetConfig();
  renderBanquetValidation(s.banquet || {});
}
// The external-software report. `found` is a TRI-STATE: null means "cannot be
// checked from here" (the CDLC loader patch — we don't know where the game is;
// a CUDA build of torch — only importing it would tell), which is a different
// and more honest answer than "missing", so it gets its own marker.
const SYS_MARK = { true: icon('check'), false: icon('x'), null: icon('info') };

function renderSystemCheck(data) {
  const el = document.getElementById('sysCheck');
  if (!el) return;
  const rows = (data.requirements || []).map(r => {
    const mark = SYS_MARK[String(r.found)] || icon('info');
    // Only spell out the cost and the fix for what is actually missing or
    // unknown — a wall of install commands next to every ✅ is noise.
    const gap = r.found !== true;
    const why = gap
      ? `<div class="meta" style="margin-left:1.4rem">${esc(r.without_it)}</div>` +
        `<div class="meta" style="margin-left:1.4rem"><b>Instalar:</b> <code>${esc(r.install)}</code></div>`
      : '';
    const flag = (r.required && r.found === false)
      ? ' <b style="color:var(--err,#e05a5a)">OBRIGATÓRIO</b>' : '';
    return `<div style="margin:.35rem 0">
      <div>${mark} <b>${esc(r.name)}</b>${flag}</div>
      <div class="meta" style="margin-left:1.4rem">${esc(r.detail)}</div>${why}</div>`;
  });
  const missing = data.missing_required || [];
  const banner = missing.length
    ? `<div class="meta" style="color:var(--err,#e05a5a);margin-bottom:.4rem">
         ${icon('alert')} Falta software <b>obrigatório</b> (${missing.map(esc).join(', ')}) —
         nenhum job vai chegar ao fim até o instalares.</div>`
    : '';
  el.innerHTML = banner + rows.join('');
}

async function loadSystemCheck() {
  const el = document.getElementById('sysCheck');
  if (el) el.textContent = 'a verificar…';
  try {
    renderSystemCheck(await getJSON('/system-check'));
  } catch {
    if (el) el.textContent = 'não foi possível verificar (o servidor não respondeu)';
  }
}

async function openSettings() {
  document.getElementById('settingsInfo').textContent = '';
  try {
    fillSettings(await getJSON('/settings'));
  } catch { /* keep defaults */ }
  document.getElementById('settingsOverlay').hidden = false;
  loadSystemCheck();
}
document.getElementById('sysCheckRefresh').addEventListener('click', loadSystemCheck);
function closeSettings() { document.getElementById('settingsOverlay').hidden = true; }
document.getElementById('openSettings').addEventListener('click', openSettings);
document.querySelectorAll('[data-open-settings]').forEach(b => b.addEventListener('click', openSettings));
document.getElementById('settingsClose').addEventListener('click', closeSettings);
document.getElementById('gpuReset').addEventListener('click', async () => {
  try {
    const r = await fetch('/gpu-reset', { method: 'POST' });
    const b = await r.json();
    if (!r.ok) { toast(b.detail || 'erro', 'err'); return; }
    fillSettings(b);
    toast('GPU reativada — a próxima deteção vai tentar a GPU.', 'ok');
  } catch { toast('falha ao reativar a GPU', 'err'); }
});
for (const r of document.querySelectorAll('input[name=sepBackend]'))
  r.addEventListener('change', toggleBanquetConfig);
document.getElementById('settingsSave').addEventListener('click', async () => {
  const backend = document.querySelector('input[name=sepBackend]:checked')?.value || 'demucs';
  const payload = {
    stem_separator: backend,
    banquet_repo: document.getElementById('sBanquetRepo').value.trim(),
    banquet_ckpt: document.getElementById('sBanquetCkpt').value.trim(),
    banquet_queries: document.getElementById('sBanquetQueries').value.trim(),
    loudness_target: parseFloat(document.getElementById('sLoudness').value),
    whisperx_compute_type: document.getElementById('sWhisperxCompute').value,
    ml_python: document.getElementById('sMlPython').value.trim(),
  };
  const r = await fetch('/settings', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  const b = await r.json();
  if (!r.ok) { toast(b.detail || 'erro', 'err'); return; }
  fillSettings(b);  // re-renders ✓/✗ from the saved values
  loadSystemCheck();  // the ML rows follow the interpreter, so they change too
  const info = document.getElementById('settingsInfo');
  if (backend === 'banquet' && !b.banquet.ready)
    info.innerHTML = '<span style="color:#e0a54a">Guardado — mas o Banquet ainda não está pronto (verifica os ✗ acima).</span>';
  else
    info.textContent = 'Guardado.';
  toast('Definições guardadas.', 'ok');
});

// ── The project's pages (the rail on the left of the project view) ──────────
// Exportar lives outside #review: it is also what shows while a job builds,
// when the other pages have nothing to show and their rail buttons are off.
const PROJECT_PAGES = ['partitura', 'tons', 'letras', 'capa', 'exportar'];
function showSection(name) {
  for (const s of PROJECT_PAGES) {
    const el = document.getElementById('section' + s.charAt(0).toUpperCase() + s.slice(1));
    if (el) el.hidden = (s !== name);
  }
  for (const btn of document.querySelectorAll('.pv-rail [data-section]'))
    btn.classList.toggle('active', btn.dataset.section === name);
  const view = document.getElementById('detail');
  view.dataset.page = name;
  view.scrollTop = 0;
}
document.querySelectorAll('.pv-rail [data-section]').forEach(b =>
  b.addEventListener('click', () => showSection(b.dataset.section)));
document.querySelectorAll('[data-goto]').forEach(b =>
  b.addEventListener('click', () => showSection(b.dataset.goto)));
function setReviewReady(ready) {
  document.getElementById('review').style.display = ready ? '' : 'none';
  document.querySelectorAll('.needs-review').forEach(el => { el.hidden = !ready; });
  for (const btn of document.querySelectorAll('.pv-rail [data-section]'))
    if (btn.dataset.section !== 'exportar') btn.disabled = !ready;
  // Rebuilding needs a built chart to edit, as before (the button used to
  // live inside #review), and "pending" describes edits to that chart.
  document.getElementById('applyAll').hidden = !ready;
  document.getElementById('pendingChangesInfo').hidden = !ready;
}
// The Partitura page's right-hand inspector: Sincronização | Secções.
function showInspector(name) {
  document.getElementById('inspSync').hidden = name !== 'sync';
  document.getElementById('inspSections').hidden = name !== 'sections';
  document.querySelectorAll('.pv-seg [data-insp]').forEach(b => {
    b.classList.toggle('active', b.dataset.insp === name);
    b.setAttribute('aria-selected', String(b.dataset.insp === name));
  });
}
document.querySelectorAll('.pv-seg [data-insp]').forEach(b =>
  b.addEventListener('click', () => showInspector(b.dataset.insp)));

// ── "Estado do PSARC" completeness checklist ─────────────────────────────────
// Reads the signals JobOut already exposes (psarc_available, has_tones,
// cover_art, sync_edited, lyrics_status) and surfaces what would leave the
// bundle incomplete or poor, each with a jump-button to fix it. Nothing is
// blocked (honesty principle): the user can still download, but won't silently
// ship a tone-less / cover-less / unsynced PSARC.
const COMPLETE_ACTIONS = {
  tones: () => { showSection('tons'); openToneBuilder(); },
  cover: () => { showSection('capa'); },
  sync:  () => { showSection('partitura'); showInspector('sync'); },
  syncok:   () => setSyncConfirmed(true),
  syncundo: () => setSyncConfirmed(false),
  lyrics: () => { showSection('letras'); },
};

async function setSyncConfirmed(confirmed) {
  if (!selectedJob) return;
  try {
    const j = await getJSON(`/jobs/${selectedJob.id}/sync-confirmed`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirmed }),
    });
    selectedJob.sync_confirmed = j.sync_confirmed;
    renderCompleteness(selectedJob);  // also re-sets the top bar's status chip
  } catch (err) {
    toast(`Não foi possível guardar: ${err.message}`);
  }
}

function renderCompleteness(j) {
  const el = document.getElementById('completeness');
  if (!el) return;
  if (!(j.status === 'completed' && j.bundle_available)) { el.innerHTML = ''; return; }
  const isGp = j.source_type === 'gp';
  const rows = [];

  if (j.psarc_available)
    rows.push({ state: 'ok', ico: 'check', title: 'PSARC jogável gerado', note: '.psarc pronto para o jogo.' });
  else
    rows.push({ state: 'err', ico: 'x', title: 'PSARC não gerado', short: 'gerar o PSARC (Wwise)',
      note: 'Só saiu o bundle (DLC Builder). Falta o Wwise/.wem para produzir o .psarc jogável — vê o README.' });

  if (j.has_tones)
    rows.push({ state: 'ok', ico: 'check', title: 'Tons definidos', note: 'O som in-game usa os teus tons.' });
  else
    rows.push({ state: 'warn', ico: 'wave', title: 'Sem tons definidos', short: 'tons', act: 'tones', actLabel: 'Detetar / criar tom',
      note: 'O DLC Builder vai marcar "tone missing" e o som será um default.' });

  if (j.cover_art)
    rows.push({ state: 'ok', ico: 'check', title: 'Capa do álbum', note: 'Incluída no bundle.' });
  else
    rows.push({ state: 'warn', ico: 'image', title: 'Sem capa', short: 'capa', act: 'cover', actLabel: 'Carregar capa',
      note: 'O albumArt fica vazio (sem arte no jogo).' });

  if (isGp) {
    if (j.sync_edited)
      rows.push({ state: 'ok', ico: 'check', title: 'Sincronização ajustada', note: 'Fizeste pelo menos uma correção de início/andamento.' });
    else if (j.sync_confirmed)
      rows.push({ state: 'ok', ico: 'check', title: 'Sincronização confirmada', act: 'syncundo', actLabel: 'Desfazer',
        note: 'Confirmaste que as notas batem com a gravação.' });
    else
      rows.push({ state: 'warn', ico: 'timer', title: 'Confirmaste a sincronização?', short: 'confirmar a sincronização',
        act: 'syncok', actLabel: 'Está sincronizada', act2: 'sync', act2Label: 'Abrir partitura',
        note: 'Não há ajustes de início/andamento. Se já ouviste e as notas batem com a gravação (p. ex. vinha sincronizada do Guitar Pro), confirma aqui.' });
  }

  if (j.has_lyrics)
    rows.push({ state: 'ok', ico: 'check', title: 'Letra incluída', note: 'A letra vai aparecer no jogo.' });
  else
    rows.push({ state: 'info', ico: 'mic', title: 'Letra (opcional)', act: 'lyrics', actLabel: 'Detetar / editar',
      note: 'Sem letra — o arranjo de vocais não é obrigatório.' });

  rows.push({ state: 'info', ico: 'key', title: 'AppID / propriedade',
    note: 'O .psarc usa o AppID de uma DLC específica; o jogador tem de a possuir para a música aparecer na lista. Causa nº1 de "não aparece no jogo".' });

  const alerts = rows.filter(r => r.state === 'warn' || r.state === 'err');
  let html = '<div class="complete-card"><h4>Antes de usar</h4>';
  const parts = alerts.map(r => r.short || r.title.toLowerCase());
  if (alerts.length)
    html += `<div class="complete-banner">${icon('alert')} Ainda falta: <b>${esc(parts.join(', '))}</b>. Podes descarregar na mesma, mas o PSARC fica mais pobre.</div>`;
  setStatusChip(alerts.length ? 'warn' : 'ok',
    alerts.length ? `Falta: ${parts.join(', ')}` : 'Pronto a usar', alerts.length ? 'alert' : 'check');
  for (const r of rows) {
    const cls = r.state === 'err' ? ' err' : r.state === 'warn' ? ' warn' : r.state === 'ok' ? ' ok' : '';
    const acts = [[r.act, r.actLabel], [r.act2, r.act2Label]].filter(([a]) => a)
      .map(([a, label]) => `<button type="button" class="secondary" data-act="${esc(a)}">${esc(label)}</button>`);
    const btn = acts.length > 1 ? `<span class="complete-acts">${acts.join('')}</span>` : acts.join('');
    html += `<div class="complete-row${cls}"><span class="complete-ico">${icon(r.ico)}</span>`
      + `<span class="complete-body"><span class="complete-title">${esc(r.title)}</span>`
      + `<span class="complete-note">${esc(r.note)}</span></span>${btn}</div>`;
  }
  html += '</div>';
  el.innerHTML = html;
  el.querySelectorAll('[data-act]').forEach(b =>
    b.addEventListener('click', () => COMPLETE_ACTIONS[b.dataset.act] && COMPLETE_ACTIONS[b.dataset.act]()));
}

// ── ⓘ info modal ─────────────────────────────────────────────────────────────
const INFO = {
  'stems': {
    title: 'Fonte de áudio (stems + sintetizada)',
    body: '<p>O dropdown "Fonte de áudio" tem três tipos de fonte:</p>' +
      '<p><strong>Mistura completa</strong> — a gravação original.</p>' +
      '<p><strong>… (sintetizada)</strong> — uma referência limpa das notas de cada arranjo (Lead/Rhythm), gerada a partir do próprio ficheiro. É uma guitarra <em>isolada</em> e limpa dessa faixa, útil para conferir o sync de cada arranjo por ouvido. Não precisa do Demucs e está sempre disponível. Reflete a sincronização pendente no momento em que a escolhes — volta a escolhê-la para atualizar depois de mais edições.</p>' +
      '<p><strong>Stems separados</strong> (botão "Separar instrumentos") — usa o Demucs para separar a gravação real por instrumento (guitarra, baixo, voz, piano, outros; a bateria é descartada). Sola a <strong>guitarra</strong> para ouvir melhor as notas reais. <em>Limite honesto:</em> o Demucs separa por <em>tipo</em> de instrumento — a faixa "guitarra" é <strong>todas as guitarras misturadas</strong>; não é possível separar a Lead da Rhythm a partir da gravação. Requer o extra <code>[ml]</code> e demora alguns minutos.</p>'
  },
  'tone-preview': {
    title: 'Testar tom na partitura',
    body: '<p>Ouve os <strong>tons que criaste</strong> aplicados às notas (no tique por nota e na fonte "sintetizada"), para comparares o <em>carácter</em> — limpo, crunch, distorcido — sem teres de entrar no Rocksmith de cada vez que ajustas uma definição.</p>' +
      '<p><strong>Voz simples (sem tom)</strong> = só o tique seco da nota, sem coloração. Ao escolher um tom, as notas passam por uma <strong>simulação de guitarra</strong>: corda dedilhada (Karplus-Strong) + distorção (conforme o ganho do tom) + cabine (EQ de corpo e corte de agudos).</p>' +
      '<p><strong>Seguir partitura</strong>: se marcaste mudanças de tom na música, esta opção troca automaticamente de tom em cada ponto, tal como o criaste — e o <strong>tom atual aparece na partitura</strong> (etiqueta âmbar 🎸 em cada mudança + junto ao BPM). Ou escolhe um tom específico para o ouvir sozinho em toda a música. O seletor fica desativado até criares o primeiro tom.</p>' +
      '<p>Nota: dois tons só soam <em>diferentes</em> se o gear diferir (ganho, EQ do amp, pedais). Dois tons com as <strong>mesmas definições</strong> soam iguais — é esperado. Em "Seguir partitura", se não marcaste nenhuma mudança, toca sempre o tom base.</p>' +
      '<p><strong>Limite honesto:</strong> o RockForge <em>não</em> modela amplificadores. Isto é uma <strong>aproximação do carácter</strong> (ganho/distorção + brilho), calculada a partir dos descritores do tom, do knob de Gain do amp e dos pedais de drive — <strong>não é o som real</strong> do amp/cabine. O som verdadeiro só existe no jogo / DLC Builder, que gera o áudio a partir do gear que gravamos no bundle.</p>'
  },
  'tone-library': {
    title: 'Biblioteca de tons',
    body: '<p>Guarda um tom que afinaste (amp + cabine + efeitos) na <strong>biblioteca</strong> para o reutilizares noutros projetos, sem teres de o reconstruir a cada música — tal como a biblioteca de tons do DLC Builder.</p>' +
      '<p><strong>★ Guardar na biblioteca</strong> guarda o tom em edição; <strong>⬇ Carregar</strong> adiciona o tom escolhido a este projeto (fica editável, e uma cópia — não afeta o original na biblioteca); 🗑 remove-o da biblioteca.</p>' +
      '<p>A biblioteca é partilhada por todos os projetos (guardada em <code>work_dir/tone_library.json</code>). Guardar um tom com uma chave já existente substitui o anterior.</p>'
  },
  'new-job': {
    title: 'Criar um novo projeto',
    body: `<p><strong>A partir de Guitar Pro</strong>: notas, trastes, técnicas e secções vêm <b>exatas</b> do ficheiro GP3/GP4/GP5/GP7. Assistente de 4 passos: <b>Ficheiro</b> (escolhe o GP e inspeciona as pistas) → <b>Pistas</b> (atribui Lead/Rhythm/Combo) → <b>Gravação</b> (o áudio + o início aproximado) → <b>Detalhes</b> (título/banda, opcionais).</p>
<p>Os <b>tons</b>, a <b>capa</b> e a <b>sincronização fina</b> fazem-se depois de criar. O projeto mostra um checklist <b>"Estado do PSARC"</b> com o que ainda falta.</p>`
  },
  'batch': {
    title: 'Processamento em lote',
    body: '<p>Cria vários projetos de uma vez a partir de vários ficheiros Guitar Pro + as gravações correspondentes — útil para converter um álbum inteiro sem repetir o assistente música a música.</p>' +
      '<p><strong>Emparelhamento:</strong> cada ficheiro GP é associado à gravação com o <strong>mesmo nome</strong> (sem extensão) — ex. <code>faixa1.gp5</code> com <code>faixa1.mp3</code>. Quando não há correspondência pelo nome, o RockForge empareha pela <strong>ordem</strong> em que escolheste os ficheiros. Confirma a lista de pares antes de criar.</p>' +
      '<p><strong>Pistas Lead/Rhythm:</strong> cada projeto usa a mesma heurística automática do assistente normal (escolhe as pistas de 6 cordas pelo nome — "lead"/"rhythm") em vez de perguntares música a música. Se uma escolha ficar errada, corrige depois em "Editar info" desse projeto (não precisas de recriar o lote todo).</p>' +
      '<p>Banda/álbum/ano ficam <strong>partilhados</strong> por todos os pares; título/artista específicos vêm do próprio ficheiro GP ou das tags do áudio, como no assistente normal.</p>' +
      '<p>Os projetos são criados um a um (mesmo caminho que criar um único projeto, repetido); acompanha o progresso na lista de pares e depois na lista de projetos.</p>'
  },
  'gp-format': {
    title: 'Formatos Guitar Pro suportados',
    body: '<p>Suportados: <strong>GP3, GP4, GP5</strong> (via PyGuitarPro) e <strong>GP7/GP8 (.gp)</strong> (parser GPIF nativo).<br><strong>Só GP6 (.gpx) não é suportado</strong> — exporta como GP5 ou GP7 no Guitar Pro ou TuxGuitar antes de importar.</p>'
  },
  'gp-offset': {
    title: 'Início da música na gravação (s)',
    body: '<p>O segundo em que a primeira nota é ouvida na tua gravação. A partitura e a letra são deslocadas para esse instante (a gravação fica intacta — o teu intro serve de lead-in).<br>Ouve a gravação, anota a que segundo entra a música e escreve esse valor. Se a partitura e o áudio ainda estiverem dessincronizados, ajusta o valor e reconstrói.<br>Mínimo de 2s de lead-in (exigido pelo DLC Builder); se puseres menos, o silêncio em falta é acrescentado automaticamente.</p>'
  },
  'lead-in': {
    title: 'Silêncio inicial (s)',
    body: '<p>Silêncio extra acrescentado mesmo no início, <strong>por cima</strong> do lead-in automático de 2s. Empurra a música inteira (áudio + notas + letra) para a frente em conjunto — útil para teres uns segundos de silêncio antes da música começar no jogo.<br>0 = nenhum. Podes alterar depois no painel de sincronização e reconstruir.</p>'
  },
  'lrc': {
    title: 'Letra sincronizada (LRC / UltraStar)',
    body: '<p>Para timing exato de letra usa um ficheiro <strong>LRC</strong> (<code>[mm:ss.xx]texto</code>) ou um <strong>.txt do UltraStar Creator</strong> (timing por sílaba, convertido automaticamente a partir do BPM/GAP do ficheiro).<br>A letra embutida no GP só tem tempo ao nível da linha; usa o painel "Letras" após a criação para afinar o timing por palavra.</p>'
  },
  'tuning': {
    title: 'Afinação e BPM',
    body: '<p>Offsets em relação ao E standard por corda (grave→agudo). A estimativa automática de afinações drop/open é apenas heurística — verifica e corrige se necessário antes de reconstruir.<br>"Detetar afinação" usa librosa para medir o desvio em cents; os valores MIDI são calculados a partir desse desvio.</p>'
  },
  'sync-offset': {
    title: 'Sincronização — início e tique',
    body: '<p>Dá play à gravação: o cursor percorre as notas e ouves um <strong>tique</strong> em cada nota. Ajusta o slider "Início da música" até os tiques baterem certo com a gravação.<br><strong>Este valor é por pista</strong> — muda de separador (Lead/Rhythm/Combined) e o campo passa a mostrar e corrigir o início dessa pista, sem mexer nas outras. Útil quando o Lead e o Rhythm foram tabulados com um pickup/compasso de entrada diferente. A afinação continua partilhada por todos.<br>"Início = cursor" trava o valor na posição do leitor; "Detetar 1ª nota" é o mesmo fluxo guiado de 3 cliques. A correção fica pendente e grava com o botão normal "Aplicar e reconstruir".</p>'
  },
  'bar-sync': {
    title: 'Sincronizar por compasso',
    body: `<p>Útil quando uma pista só entra a tocar mais tarde na música — por exemplo, o Rhythm tem compassos de silêncio no início e a primeira nota real coincide com o <b>compasso 7</b>. "Início desta pista" só alinha a 1ª nota; este painel deixa-te alinhar <b>qualquer compasso</b>, escolhido pelo número.</p>
<p><b>= cursor:</b> escolhe o compasso, dá play/pausa exatamente onde ele deve soar, e clica — o compasso escolhido (e tudo depois dele) alinha com o cursor.</p>
<p><b>Sincronizar com outra pista:</b> como o número do compasso é o mesmo em todas as pistas do ficheiro Guitar Pro (vêm da mesma partitura), se já tiveres o Lead bem sincronizado podes alinhar o compasso 7 do Rhythm diretamente com o compasso 7 do Lead — sem teres de ouvir/procurar à mão.</p>
<p>Como as outras ferramentas de sincronização, cria uma correção pendente por pista — grava com "Aplicar e reconstruir".</p>`
  },
  'sync-tempo': {
    title: 'Sincronização — andamento',
    body: '<p>Se a tabulatura e a gravação se vão afastando ao longo da música (o GP foi escrito num andamento ligeiramente diferente do que foi gravado), ajusta o <strong>andamento</strong>: estica/comprime a música toda de uma vez. As notas movem-se sobre a forma de onda para confirmares o alinhamento.</p>'
  },
  'auto-sync': {
    title: 'Sincronização automática',
    body: '<p>Deteta o andamento e o início da gravação (como o CDLC.AI) e propõe um ajuste. Os valores ficam em pré-visualização — confirma na partitura e clica em "Aplicar e reconstruir".<br><b>Dica importante:</b> se já tiveres corrido <b>"Separar instrumentos"</b>, a deteção do andamento passa a ser feita na <b>bateria isolada</b> — muito mais fiável em música rápida e densa (na mistura completa, o detetor de batidas engana-se no nível métrico). Separa primeiro para um resultado bem melhor.<br>Requer o extra <code>ml</code> (librosa). Refina depois com os modos manuais.</p>'
  },
  'auto-sync-dynamic': {
    title: 'Sincronização dinâmica (segue o andamento real)',
    body: '<p>A sincronização automática acima aplica UM andamento médio — não chega quando o tempo da gravação varia (o problema típico das tabs de IA). Esta segue a <b>curva de andamento real</b>: usa a grelha de batidas para o tempo local, e afina cada âncora encaixando as notas da própria tab nos ataques do áudio.<br><b>Corre "Separar instrumentos" primeiro:</b> a grelha de batidas passa a vir da <b>bateria isolada</b> e os ataques da <b>guitarra isolada</b> — muito mais fiável que a mistura completa (onde o detetor de batidas se engana no andamento). Sem separação, usa a mistura e avisa-te.<br><b>Começa na primeira nota:</b> define primeiro o início no Passo 1 (ou com "🎯 Detetar 1ª nota") — a primeira âncora é exatamente esse ponto e o alinhamento aplica-se daí para a frente.<br>Substitui as correções pendentes da pista atual por esta proposta; fica em pré-visualização — vê o <b>♩BPM por compasso</b> na partitura (âmbar = alterado pelas âncoras) e confirma com "Aplicar e reconstruir".<br><b>Limite honesto:</b> secções onde as notas da tab não batem com o áudio são assinaladas com ⚠ — aí o problema é o conteúdo da tab (notas/compassos errados), que nenhuma sincronização corrige; ajusta essas partes no Guitar Pro. Requer o extra <code>ml</code> (librosa).</p>'
  },
  'export-gp': {
    title: 'Exportar Guitar Pro corrigido',
    body: '<p>Escreve as correções de <b>andamento</b> que aceitaste numa <b>cópia</b> do teu ficheiro Guitar Pro, para a correção ficar permanente no próprio Guitar Pro e não só no RockForge. <b>O teu ficheiro original nunca é alterado.</b><br>Tudo o resto é preservado: notas, técnicas, afinação, faixas, secções, letra — e as mudanças de andamento que tu próprio tenhas escrito também sobrevivem.<br><b>Formatos:</b> <code>.gp3</code>/<code>.gp4</code>/<code>.gp5</code> e <code>.gp</code> (GP7/8). O <code>.gpx</code> (GP6) <b>não é escrito por ferramenta nenhuma</b> — nem o Guitar Pro o exporta para si próprio; exporta como GP5 ou GP7 primeiro.<br><b>Limite honesto:</b> os formatos binários (gp3/4/5) guardam o andamento como número <b>inteiro</b>, por isso 119,085 fica 119 — dizemos-te sempre o que foi mesmo escrito. O <code>.gp</code> mantém as casas decimais.<br><b>Só andamento:</b> um <b>salto</b> não é exprimível como mudança de BPM (seria preciso inserir/remover um compasso), por isso não vai no ficheiro — corrige esse no Guitar Pro.</p>'
  },
  'analyse-sync': {
    title: 'Analisar sincronização',
    body: '<p>Não corrige nada — <b>diagnostica</b>. Todas as outras ferramentas respondem "onde deve ficar cada nota"; esta responde <b>"que tipo de problema é este"</b>, que é o que decide a correção certa.<br>Encaixa as notas da tab nos ataques reais da gravação e analisa a curva de desvio:<br>• <b>Desvio progressivo</b> — a diferença cresce a um ritmo constante: o andamento da tab não é bem o da gravação. Corrige-se com um <b>BPM novo, só naquele troço</b>.<br>• <b>Salto</b> — a diferença dá um degrau: compasso a mais/menos, pausa em falta, repetição. <b>Nunca</b> se corrige com BPM — isso espalharia um erro local por música que estava correta.<br>• <b>Diferença estrutural</b> — as notas da tab não correspondem ao áudio ali; nenhuma correção temporal resolve, é o conteúdo que está errado.<br><b>Separa os instrumentos primeiro:</b> as notas são encaixadas nos ataques da <b>guitarra isolada</b>, bem mais fiável que a mistura.<br>Cada conclusão é aceite ou rejeitada individualmente e só entra em pré-visualização — o "Aplicar e reconstruir" continua a ser quem grava.<br><b>Limite honesto:</b> num trecho de ritmo muito regular, um compasso a mais/menos pode ser matematicamente indistinguível de notas em falta — aí verás "sincronizado" e notas sem par, não um salto.</p>'
  },
  'sync-from-stem': {
    title: 'Sincronizar pela bateria (IA)',
    body: '<p>O equivalente ao MIDI do RIPX, mas <b>feito dentro do RockForge</b> — sem exportares nada de um DAW. Corre um detetor de batidas <b>neural</b> (muito mais fiável que o automático normal em música rápida e densa, onde o detetor clássico se engana no nível métrico) sobre a gravação, deteta o <b>início de cada compasso</b> e alinha cada compasso da tab a esse tempo real — a mesma âncora-por-compasso do mapa de tempo MIDI.<br><b>Corre "Separar instrumentos" primeiro:</b> a deteção passa a ser feita na <b>bateria isolada</b> (o sinal de batida mais limpo); sem separação usa a mistura completa e avisa-te.<br>Respeita o <b>Passo 1</b> (fixa a 1.ª nota, o alinhamento cresce daí) e fica em pré-visualização — revê o <b>♩BPM por compasso</b> na partitura e confirma com "Aplicar e reconstruir".<br><b>Limite honesto:</b> é uma <b>estimativa neural</b>, forte mas não é verdade absoluta como um MIDI do RIPX conferido à mão — se falhar em material invulgar, importa o MIDI. Requer o extra <code>beatthis</code> (Beat This! + torch); pode demorar algum tempo.</p>'
  },
  'sync-from-midi': {
    title: 'Importar mapa de tempo (MIDI)',
    body: '<p>Quando a sincronização automática não fica perfeita, dá-lhe a <b>verdade em vez de uma estimativa</b>: um MIDI com o andamento por compasso (exportado do RIPX ou de qualquer DAW a partir da mesma gravação). Em vez de adivinhar o tempo pelo áudio, o RockForge lê o mapa de tempo do MIDI e alinha <b>cada compasso da tab ao seu tempo real</b> — uma âncora por compasso, o "BPM por compasso".<br>Continua a respeitar o <b>Passo 1</b>: fixa a 1.ª nota e o alinhamento cresce daí. Fica em pré-visualização — revê na partitura e confirma com "Aplicar e reconstruir".<br><b>Para resultar:</b> o MIDI tem de começar no 1.º compasso da tab (corta um intro que a tab não tenha) e ter a mesma estrutura de compassos. A precisão é a da deteção do RIPX. Só formato PPQ (o normal).</p>'
  },
  'tab-viewer': {
    title: 'Partitura — legenda',
    body: '<p>● nota · ▮ nota de acorde (ligadas por barra vertical) · sigla sobreposta = técnica:<br>B bend · H hammer-on · P pull-off · S slide · HA harmónico · PM palm mute · V vibrato · T tapping · SL slap · PO pop · A acento<br>Passa o cursor sobre a nota para ver a lista completa.<br>Cor = corda (igual ao Rocksmith): <span style="color:#e6483c">E</span> <span style="color:#f5dc3c">A</span> <span style="color:#3f9bdc">D</span> <span style="color:#f0973c">G</span> <span style="color:#5cc24a">B</span> <span style="color:#b56cdc">e</span> (grave→agudo). Eixo X em segundos.</p>'
  },
  'sync-modes': {
    title: 'Modos de correção da partitura',
    body: `<p><strong>Arrastar nota:</strong> arrasta uma nota horizontalmente para o instante correto — cria um ponto de correção; as notas entre pontos são esticadas/comprimidas.</p>
<p><strong>Encaixar nos tempos (beats):</strong> com o encaixe ligado, a nota salta de beat em beat (a grelha da partitura, mostrada com marcas no fundo) em vez de deslizar de forma contínua. Mantém <strong>Alt</strong> premido durante o arrasto para colocar livremente (afinação sub-beat). Escolhe <strong>"Cursor de reprodução"</strong> na grelha para arrastar a nota diretamente para a posição atual do leitor (em vez do beat mais próximo) — a forma mais fiável de alinhar com o cursor.</p>
<p><strong>Marcar no cursor:</strong> clica numa nota para a ancorar na posição atual do cursor de reprodução — útil para alinhar enquanto o áudio toca.</p>
<p><strong>Selecionar excerto:</strong> arrasta uma caixa sobre as notas e depois arrasta uma delas — o excerto move-se em bloco (também com encaixe nos beats).</p>
<p><strong>Mover seguintes:</strong> pausa o áudio no instante certo e clica na nota deslocada — essa nota e todas as seguintes deslocam-se em bloco para o cursor.</p>
<p><strong>Novo beat (detetar):</strong> clica numa nota onde o andamento muda — o RockForge mede o andamento da gravação a partir desse instante e re-espaça as notas seguintes.</p>
<p><strong>Alinhar compasso:</strong> pausa a gravação onde um compasso deve soar e clica numa nota — abre um popup com o número do compasso (o da nota, já escolhido). Confirma com "= cursor" e esse compasso alinha-se ao cursor, arrastando as notas seguintes; ou "= pista" para o alinhar ao mesmo compasso de outra pista já sincronizada. Feito várias vezes ao longo da música, corrige o desvio compasso a compasso.</p>
<p><strong>Secção:</strong> clica numa nota para nomear onde começa uma secção (intro/verso/refrão…) — nada a ver com sincronização, é só estrutura da música. Ver o painel "🏷️ Secções" abaixo.</p>
<p><strong>Editar notas:</strong> clica numa nota existente para a editar (traste, sustain, técnicas, bend, slide) ou removê-la; <strong>duplo-clique</strong> no pentagrama vazio insere uma nota nova, encaixada na grelha de sincronização (um clique simples no vazio move o cursor, como nos outros modos). Muda o <em>conteúdo</em> da partitura — as notas deixam de vir só do ficheiro Guitar Pro — e fica pendente (contorno tracejado verde-água) até "Aplicar e reconstruir".</p>`
  },
  'sections': {
    title: 'Secções da música',
    body: '<p>Marca e nomeia a estrutura da música (intro/verso/refrão/solo…) diretamente na partitura — útil para navegar e para o <strong>Riff Repeater</strong> no jogo, sem teres de voltar ao Guitar Pro.</p>' +
      '<p><strong>Adicionar:</strong> ativa o modo "Secção" e clica numa nota para a nomear, ou usa "+ Adicionar no cursor" para marcar a posição atual do leitor sem precisares de acertar numa nota.</p>' +
      '<p><strong>Editar:</strong> a lista abaixo tem o tempo e o nome de cada secção editáveis diretamente — muda o número para reposicionar, o texto para renomear, ou remove-a.</p>' +
      '<p>As secções são <strong>partilhadas por todos os arranjos</strong> (Lead/Rhythm/Combined) — tal como as mudanças de tom, marcadas uma vez e aplicadas a todos. Ficam em pré-visualização (etiqueta 🏷️ verde-água na partitura) até confirmares com "Aplicar e reconstruir"; sem qualquer edição, a música mantém as secções que já vinham do ficheiro Guitar Pro.</p>'
  },
  'lyrics': {
    title: 'Deteção automática de letra',
    body: '<p>Isola a voz com o Demucs e transcreve com o WhisperX — pode demorar alguns minutos (Demucs na CPU é lento).<br>Requer <code>pip install -e ".[lyrics]"</code>.<br>Depois podes editar palavras e tempos à mão, ou criar tudo manualmente sem detetar.</p>'
  },
  'album-lookup': {
    title: 'Álbum, ano e capa automáticos',
    body: '<p>Procura a música pelo <strong>título e banda</strong> no iTunes e no MusicBrainz (capas do Cover Art Archive) e mostra os álbuns onde ela aparece. <strong>Escolhes tu</strong> o certo: o clique preenche o álbum e o ano e usa essa capa.</p>' +
      '<p>A pesquisa é por texto, por isso pode trazer versões de outros artistas, compilações ou reedições — cada cartão mostra a faixa encontrada e a fonte para o veres. "Sem capa" não usa imagem nenhuma. Precisa de internet; sem ela, preenche à mão como antes.</p>' +
      '<p>A capa escolhida é descarregada quando o projeto é criado. Num projeto que já existe, usa "Procurar capa online" na página Capa.</p>'
  },
  'lyrics-lookup': {
    title: 'Procurar a letra e sincronizá-la',
    body: '<p>Procura a letra no <strong>LRCLIB</strong> (base de dados aberta de letras) pelo título e banda do projeto. Muitas letras vêm <strong>sincronizadas</strong> por linha; outras são <strong>só texto</strong>.</p>' +
      '<p><strong>Usar</strong> carrega a letra sincronizada no editor com os tempos da versão em que foi feita (normalmente a oficial). Se a tua gravação é essa versão, já bate certo; se tem uma introdução diferente, <strong>1ª palavra = cursor</strong> (põe o cursor onde começa a voz) ou os botões −/+ deslocam a letra toda.</p>' +
      '<p><strong>Sincronizar com a gravação</strong> usa o WhisperX para medir na voz da <em>tua</em> gravação o tempo de <em>cada palavra</em> da letra que está no editor — as palavras ficam as certas, só os tempos são medidos. Numa letra só texto procura na música inteira (menos fiável). Precisa dos extras <code>[ml,lyrics]</code> e demora alguns minutos.</p>' +
      '<p>A letra fica pendente até "Aplicar e reconstruir". Remixes de fãs e músicas feitas por IA raramente estão no LRCLIB — aí usa "Detetar letra" ou escreve-a no editor.</p>'
  },
  'songsterr-import': {
    title: 'Importar a tab do Songsterr',
    body: '<p>Em vez de um ficheiro Guitar Pro, cola o link da música no <strong>Songsterr</strong>. O RockForge descarrega as pistas da tab e cria com elas um ficheiro Guitar Pro 5, que segue o caminho normal (escolhes as pistas no passo 2).</p>' +
      '<p>No passo 3 aparecem os <strong>vídeos do YouTube</strong> dessa música com o tempo de cada compasso marcado por pessoas. Escolhe um e carrega o <strong>MP3 convertido desse mesmo vídeo</strong> — o RockForge não descarrega áudio. Com isso, as notas seguem a gravação compasso a compasso, sem acertos manuais.</p>' +
      '<p>Limites: a API do Songsterr não é pública e pode mudar; as pistas de bateria ficam de fora; notas de ornamento (grace) não são incluídas; a letra não vem (procura-a na página Letra). O ficheiro criado pode ser exportado e aberto no Guitar Pro.</p>'
  },
  'youtube-audio': {
    title: 'Áudio do vídeo do YouTube',
    body: '<p>Os tempos por compasso do Songsterr foram marcados num vídeo do YouTube, por isso a gravação que bate certo com eles é o <strong>áudio desse vídeo</strong>. Este botão descarrega-o com o <strong>yt-dlp</strong> e usa-o como gravação do projeto — já não precisas de o converter à mão.</p>' +
      '<p><strong>Se o YouTube recusar</strong> (erro 403 ou "confirma que não és um robô"), escolhe em "Sessão do browser" um browser onde tenhas o YouTube aberto e tenta de novo: o yt-dlp usa essa sessão.</p>' +
      '<p>Precisa do yt-dlp instalado (<code>pip install yt-dlp</code>); se o YouTube mudar e os downloads falharem, atualizar o yt-dlp costuma resolver. Descarregar do YouTube vai contra os termos do YouTube fora das funções que ele oferece — usa só para uso pessoal, com música a que tens direito.</p>'
  },
  'cover-art': {
    title: 'Capa do álbum',
    body: '<p>Imagem JPG ou PNG incluída no bundle como <code>cover.*</code> e referenciada no <code>rockforge.rs2dlc</code> — usa-a como capa ao abrir o projeto no DLC Builder (que gera as texturas DDS do jogo).<br>O upload não reconstrói o bundle — clica em "Aplicar e reconstruir" na tab Partitura para incluir a capa.</p>'
  },
  'tones': {
    title: 'Tons (amp, cabine, efeitos)',
    body: `<p>Define os tons da CDLC com <strong>gear real</strong> (amplificador, cabine e pedais/racks da biblioteca do Rocksmith). São gravados no <code>rockforge.rs2dlc</code> e no <code>.psarc</code>, por isso funcionam no jogo sem teres de os recriar no DLC Builder.</p>
<p><strong>Criar:</strong> clica em "+ Criar / editar tons", depois "+ Novo tom". Escolhe o amplificador e a cabine (obrigatórios) e adiciona efeitos opcionais. Cada botão de knob vem com o valor por defeito do catálogo.</p>
<p><strong>Atribuir:</strong> escolhe o <strong>Tom base</strong> (o que toca no início) e marca até <strong>4</strong> tons "extra" que poderás trocar ao longo da música.</p>
<p><strong>Trocar a meio:</strong> com o modo "Mudança de tom" ativo, clica numa nota na partitura para colocar lá uma troca para um dos tons extra.</p>
<p>Os tons são <strong>por arranjo</strong> (Lead/Rhythm/Combined) e só se aplicam a projetos de Guitar Pro. Sem tons definidos, o DLC Builder marca "tone missing" e resolves com a biblioteca dele.</p>`
  },
};

document.getElementById('infoClose').addEventListener('click', () => {
  document.getElementById('infoOverlay').hidden = true;
});
document.getElementById('infoOverlay').addEventListener('click', e => {
  if (e.target.id === 'infoOverlay') document.getElementById('infoOverlay').hidden = true;
});
document.addEventListener('click', e => {
  const btn = e.target.closest('.info-btn');
  if (!btn || !btn.dataset.info) return;
  const info = INFO[btn.dataset.info];
  if (!info) return;
  document.getElementById('infoTitle').textContent = info.title;
  document.getElementById('infoBody').innerHTML = info.body;
  document.getElementById('infoOverlay').hidden = false;
});

const STD = [40, 45, 50, 55, 59, 64];
let selectedJob = null, arrangements = [], currentArr = 0, pollTimer = null;
let arrangementsLoadedFor = null;  // job id whose chart+audio are already loaded (avoids re-decoding on every poll)
// Visual sync (GP): MIN_LEAD must match gp_pipeline.MIN_LEAD_S.
const MIN_LEAD = 2.0;
let tabPx = 80, tabH = 280, scoreShift = 0, offsetLive = 0;
// Tempo (BPM) live-preview: builtScale is the tempo_scale baked into the
// arrangement currently loaded; tempoScaleLive is the value being previewed;
// gpBpm is the GP file's original tempo (before any scaling).
let builtScale = 1, tempoScaleLive = 1, gpBpm = 0;
// Extra intro silence the current bundle was built with (seconds). Adds to the
// lead-in so the viewer's notes/playhead stay aligned after a rebuild with it.
let leadInBuilt = 0;
const BASE_PX = 80;
let zoomLevel = 1.25;  // start 25% more zoomed in than the base scale
// Staff layout constants (showArr recomputes H/SB/ROW/R identically every
// call — they never vary with zoom/song) hoisted here so the note editor's
// click handler can convert a click's Y position to a string index without
// duplicating showArr's internals.
const STAFF_H = 304, STAFF_SB = STAFF_H - 59, STAFF_ROW = 40, NOTE_R = 13;

function setZoom(z) {
  // Keep the currently-centered time in view across the zoom change — tabPx
  // (px/second) changes but #tabwrap's scrollLeft doesn't, so without this the
  // same pixel offset silently jumps to a different part of the song, making
  // zoom useless for framing one fast passage precisely.
  const wrap = document.getElementById('tabwrap');
  const centerT = arrangements.length ? xToTime(wrap.scrollLeft + wrap.clientWidth / 2) : 0;
  zoomLevel = Math.min(8, Math.max(0.25, z));
  document.getElementById('zoomLevel').textContent = `${Math.round(zoomLevel * 100)}%`;
  if (arrangements.length) {
    showArr(currentArr);
    wrap.scrollLeft = Math.max(0, timeToX(centerT) - wrap.clientWidth / 2);
  }
}
document.getElementById('zoomIn').addEventListener('click', () => setZoom(zoomLevel * 1.5));
document.getElementById('zoomOut').addEventListener('click', () => setZoom(zoomLevel / 1.5));
document.getElementById('zoomReset').addEventListener('click', () => setZoom(1));
document.getElementById('zoomLevel').textContent = `${Math.round(zoomLevel * 100)}%`;
let audioCtx = null, syncRaf = null, tickIdx = 0;
// Decoded recording peaks for the tab-viewer waveform: max |amplitude| per
// 1/WAVE_HZ second bin, plus the audio duration. Reset per job.
let wavePeaks = null, waveDuration = 0;
// Web Audio playback engine. We play the recording through an
// AudioBufferSourceNode (decoded once for the waveform), NOT the <audio>
// element: the element seeks by estimating a byte offset from time, which is
// accurate near the start but drifts further in for VBR/seek-table-less
// sources — exactly the "aligned from the start, off in the middle" symptom.
// A buffer source seeks sample-accurately and its clock is audioCtx.currentTime,
// so playback, the waveform and the notes share one exact timeline.
let playBuffer = null;       // decoded recording (null => use <audio> fallback)
let audioSourceName = '';    // '' => full mix; else a Demucs stem name (guitar/…)
let playGain = null;         // GainNode for music volume control
let playSource = null;       // active AudioBufferSourceNode while playing
let playFade = null;         // per-source GainNode for the anti-click seek/pause fade
let playStartCtx = 0;        // audioCtx.currentTime when the current source started
let playStartOffset = 0;     // buffer offset (s) the current source started at
let playing = false;         // buffer-backend transport state
let pausedAt = 0;            // buffer-backend position (s) while paused/stopped
let playbackRate = 1.0;      // playback speed (<1 slows down; lowers pitch on the buffer source)
// A buffer source stopped/started mid-waveform (every seek/pause) is a hard
// amplitude discontinuity — an audible click. Scrubbing back and forth stacks
// those clicks into "noise". A ~6 ms gain ramp at start (fade in) and before
// stop (fade out) removes it; on a seek the outgoing fade-out and the incoming
// fade-in briefly overlap into a click-free crossfade.
const AUDIO_FADE_S = 0.006;
// Most note ticks one animation frame may sound (see the drain loop in
// syncFrame): a stalled frame must not fire its whole backlog at one instant.
const MAX_TICKS_PER_FRAME = 3;
let seekDragging = false, seekWasPlaying = false;
const WAVE_HZ = 100;
// Default to the re-tempo mode: it is the workflow that actually holds up on
// real material. The user supplies the one thing every automatic tool got wrong
// — WHERE the drift starts — and the machine answers the easy, reliable
// question: what is the recording's tempo from here? It also pins the clicked
// note where it already is, so nothing before the click can move.
let syncMode = 'newbeat'; // 'drag' | 'tap' | 'excerpt' | 'newbeat' | ...
let snapToBeats = true;   // note drag snaps to the beat grid (hold Alt = free drag)
let snapDiv = 1;          // snap grid: 'bars' | 1 (beat) | 2/3/4 (subdivisions per beat)
let snapPositions = [];   // grid display-positions cached for the duration of one drag
let selectionAnchor = null;  // chart time of the last plainly-clicked note (Shift-range pivot)
// Guided "detect first note" flow: null → idle; 'audio' → waiting for the click
// on the waveform where the 1st note sounds; 'note' → waiting for the click on
// the 1st note to align it there. firstNoteAudioT is that recording second.
// Always pins the CURRENT arrangement's first note (a per-track anchor) —
// see setTrackStart.
let firstNoteFlow = null;
let firstNoteAudioT = 0;
let currentPlayheadT = 0; // display time of playhead; updated by syncFrame and seeks
// In-app lyrics editor rows: {time, length, lyric, lineBreak}. lyric excludes
// the trailing "+" — lineBreak controls whether it's re-appended on save.
let lyricsEvents = [];
// Tone editor state (GP jobs). jobTones: full gear dicts (see gear_catalogue
// .tone_from_dict); toneBase/toneNames reference them by key; toneChanges are
// the timed switches placed on the partitura ({time(bundle s), name(key)}).
let gearCatalogue = null;     // {amps, cabinets, pedals, racks, descriptors}
let jobTones = [];            // [{key,name,volume,descriptors,amp,cabinet,pre,post,racks}]
let toneBase = null;
let toneNames = [];
let toneChanges = [];
let editingToneKey = null;    // key of the tone open in the builder form
let toneLibrary = [];         // cross-project saved tones (GET /tone-library)
// Section-editor state (GP jobs). Shared across arrangements (like
// toneChanges) — bundle-clock {time, name} pairs. songSections is seeded from
// arrangements[0].sections on load (whatever the GP file authored, or a prior
// override); sectionsTouched gates whether it's sent on rebuild at all, so an
// untouched job never overwrites GP-authored sections with their own mirror.
let songSections = [];
let sectionsTouched = false;
let lyricsPollTimer = null;
// Current cent_offset (fine-tuning deviation from A440), pre-filled from the
// built arrangement and updated by "Detetar afinação" / sent on rebuild.
let centOffsetLive = 0;

const esc = t => { const d = document.createElement('span'); d.textContent = t ?? ''; return d.innerHTML; };

function toast(message, kind = 'err') {
  const el = document.createElement('div');
  el.className = `toast ${kind === 'ok' ? 'ok' : ''}`;
  el.textContent = message;
  document.getElementById('toasts').appendChild(el);
  setTimeout(() => el.remove(), 5000);
}

// A last-resort net: anything that still escapes surfaces as a toast instead of
// a silent console error, so a failed action is never invisible to the user.
window.addEventListener('unhandledrejection', ev => {
  const msg = (ev.reason && ev.reason.message) || String(ev.reason || '');
  if (msg) toast(`erro: ${msg}`, 'err');
});

// ---- Server reachability ----------------------------------------------------
// The app deliberately shuts itself down when the tab closes (see
// ROCKFORGE_IDLE_SHUTDOWN_S), and a machine can sleep, so the API really can
// vanish while this page stays open. Before this, every fetch that went
// `(await fetch(...)).json()` threw an unhandled rejection and the action just
// did nothing — indistinguishable from a broken feature. getJSON() surfaces it
// once, as a persistent banner, instead of failing silently N times.
let serverOffline = false;

function setServerOffline(down) {
  if (down === serverOffline) return;
  serverOffline = down;
  let el = document.getElementById('serverOffline');
  if (down) {
    if (!el) {
      el = document.createElement('div');
      el.id = 'serverOffline';
      el.setAttribute('role', 'status');
      el.style.cssText = 'position:fixed;left:0;right:0;top:0;z-index:999;padding:.5rem 1rem;' +
        'background:#7a2520;color:#fff;font-size:.85rem;text-align:center';
      el.textContent = 'Sem ligação ao RockForge — a app terminou ou perdeu-se a rede. ' +
        'Reinicia o start.bat e recarrega esta página.';
      document.body.appendChild(el);
    }
  } else if (el) {
    el.remove();
  }
}

// Fetch + parse JSON, raising on a non-2xx so a failure can never be mistaken
// for an empty result. Network errors flip the offline banner.
async function getJSON(url, opts) {
  let r;
  try {
    r = await fetch(url, opts);
  } catch (err) {
    setServerOffline(true);
    throw err;
  }
  setServerOffline(false);
  if (!r.ok) {
    let detail = `HTTP ${r.status}`;
    try {
      const body = await r.json();
      if (body && body.detail) detail = typeof body.detail === 'string'
        ? body.detail : JSON.stringify(body.detail);
    } catch { /* not a JSON error body; keep the status */ }
    throw new Error(detail);
  }
  return r.json();
}

function confirmModal(text) {
  const overlay = document.getElementById('confirmOverlay');
  document.getElementById('confirmText').textContent = text;
  overlay.hidden = false;
  return new Promise(resolve => {
    const cleanup = result => { overlay.hidden = true; resolve(result); };
    document.getElementById('confirmOk').onclick = () => cleanup(true);
    document.getElementById('confirmCancel').onclick = () => cleanup(false);
    overlay.onclick = e => { if (e.target === overlay) cleanup(false); };
  });
}

function closeDetail() {
  selectedJob = null;
  arrangementsLoadedFor = null;
  clearTimeout(pollTimer);
  clearInterval(lyricsPollTimer);
  stopArrangementPreview();
  stopPlayback();
  playBuffer = null; playGain = null; pausedAt = 0; playing = false;
  const au = document.getElementById('syncAudio');
  if (au) { au.removeAttribute('src'); au.load(); }
  document.getElementById('detailOverlay').hidden = true;
  sectionShownFor = null;
  refreshJobs();
}
document.getElementById('detailClose').onclick = closeDetail;

// ── Edit song info (title/artist/album/year) ──
const TUNING_PRESETS = {
  'Manter': null,
  'Standard E': [0, 0, 0, 0, 0, 0],
  'Eb Standard': [-1, -1, -1, -1, -1, -1],
  'Drop D': [-2, 0, 0, 0, 0, 0],
  'D Standard': [-2, -2, -2, -2, -2, -2],
  'Drop C#': [-3, -1, -1, -1, -1, -1],
  'Drop C': [-4, -2, -2, -2, -2, -2],
  'C Standard': [-4, -4, -4, -4, -4, -4],
  'Drop B': [-5, -3, -3, -3, -3, -3],
};
const STD_MIDI = [40, 45, 50, 55, 59, 64];
function _presetFromOffsets(off) {
  for (const [name, o] of Object.entries(TUNING_PRESETS)) {
    if (o && o.every((v, i) => v === off[i])) return name;
  }
  return 'Manter';
}

async function openMetaEdit() {
  if (!selectedJob) return;
  document.getElementById('metaTitle').value = selectedJob.title || '';
  document.getElementById('metaArtist').value = selectedJob.artist || '';
  document.getElementById('metaAlbum').value = selectedJob.album || '';
  document.getElementById('metaYear').value = selectedJob.year ?? '';
  const gp = document.getElementById('metaGp');
  gp.style.display = 'none';
  document.getElementById('metaOverlay').hidden = false;
  document.getElementById('metaTitle').focus();
  // GP jobs: load the track list + current arrangements so the user can re-map
  // tracks to arrangements and re-tune each, all rebuilt on save.
  try {
    const [tr, arrs] = await Promise.all([
      fetch(`/jobs/${selectedJob.id}/gp-tracks`).then(r => r.ok ? r.json() : null),
      fetch(`/jobs/${selectedJob.id}/arrangements`).then(r => r.ok ? r.json() : []),
    ]);
    if (!tr) return;  // not a GP job (or file gone) — leave the GP section hidden
    const opts = '<option value="">—</option>' + tr.tracks
      .filter(t => !t.is_percussion && t.string_count === 6)
      .map(t => `<option value="${t.index}">${t.index}: ${esc(t.name)}</option>`).join('');
    const SLOTS = [['lead', 'Lead'], ['rhythm', 'Rhythm'], ['combo', 'Combo'],
                   ['alt_lead', 'Lead alternativo'], ['alt_rhythm', 'Rhythm alternativo']];
    document.getElementById('metaTracks').innerHTML = SLOTS.map(([slot, label]) =>
      `<div class="field" style="flex:1 1 11rem"><label>Pista ${label}</label>
        <select data-slot="${slot}" style="width:100%">${opts}</select></div>`).join('');
    for (const [slot] of SLOTS) {
      const v = tr.assignment[slot];
      if (v !== null && v !== undefined)
        document.querySelector(`#metaTracks select[data-slot="${slot}"]`).value = String(v);
    }
    const presetOpts = Object.keys(TUNING_PRESETS)
      .map(n => `<option value="${n}">${n}</option>`).join('');
    document.getElementById('metaTunings').innerHTML = arrs.map(a => {
      const ov = (tr.tuning_overrides || {})[a.kind];
      const cur = ov ? _presetFromOffsets(ov.map((m, i) => m - STD_MIDI[i])) :
                       _presetFromOffsets(a.tuning_offsets);
      return `<div class="field" style="flex:1 1 11rem"><label>Afinação ${esc(a.kind)}</label>
        <select data-kind="${esc(a.kind)}" style="width:100%">${presetOpts}</select></div>`
        .replace(`value="${cur}"`, `value="${cur}" selected`);
    }).join('');
    gp.style.display = '';
  } catch { /* leave the GP section hidden on any error */ }
}
// Reached from onclick="openMetaEdit()" inside the job-row template strings,
// which ESLint cannot trace — inline handlers resolve through global scope, so
// say so explicitly instead of leaving it looking unused.
window.openMetaEdit = openMetaEdit;

function closeMeta() { document.getElementById('metaOverlay').hidden = true; }
document.getElementById('metaClose').onclick = closeMeta;
document.getElementById('metaCancel').onclick = closeMeta;
document.getElementById('metaSave').onclick = async () => {
  if (!selectedJob) return;
  const title = document.getElementById('metaTitle').value.trim();
  const artist = document.getElementById('metaArtist').value.trim();
  if (!title || !artist) { alert('Título e artista são obrigatórios.'); return; }
  const yearRaw = document.getElementById('metaYear').value.trim();
  const body = {
    title, artist,
    album: document.getElementById('metaAlbum').value.trim(),
    year: yearRaw ? parseInt(yearRaw, 10) : null,
  };
  const r = await fetch(`/jobs/${selectedJob.id}/metadata`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!r.ok) { alert('Erro ao guardar a informação.'); return; }
  selectedJob = await r.json();
  // GP: if the arrangements/tuning section is shown, a change there needs a full
  // rebuild (re-parse) — fork a new job with the new track map + tunings.
  const gp = document.getElementById('metaGp');
  if (gp.style.display !== 'none') {
    const tracks = {};
    for (const sel of document.querySelectorAll('#metaTracks select[data-slot]'))
      tracks[sel.dataset.slot] = sel.value === '' ? null : parseInt(sel.value, 10);
    const tuning_overrides = {};
    for (const sel of document.querySelectorAll('#metaTunings select[data-kind]')) {
      const off = TUNING_PRESETS[sel.value];
      if (off) tuning_overrides[sel.dataset.kind] = off.map((v, i) => STD_MIDI[i] + v);
    }
    const rr = await fetch(`/jobs/${selectedJob.id}/rebuild`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tracks, tuning_overrides }),
    });
    if (!rr.ok) { const e = await rr.json(); alert(e.detail || 'Erro ao reconstruir.'); return; }
    const nj = await rr.json();
    closeMeta();
    toast('Arranjos/afinação aplicados — a reconstruir.', 'ok');
    refreshJobs(); selectJob(nj.id);
    return;
  }
  closeMeta();
  // Refresh the header + the job list titles (no chart reload needed).
  renderDetailHead(selectedJob);
  refreshJobs();
};

// ── Home: the projects as cards ──────────────────────────────────────────────
let jobsCache = [];
let jobFilter = 'all';
const JOB_FILTERS = {
  all: () => true,
  ready: j => j.status === 'completed',
  busy: j => j.status === 'pending' || j.status === 'running',
  failed: j => j.status === 'failed',
};
// What a card says about its project: the same gaps the Exportar page lists.
function jobCardStatus(j) {
  if (j.status === 'failed') return ['err', 'Falhou', 'x'];
  if (j.status === 'pending') return ['run', 'Na fila…', 'clock'];
  if (j.status === 'running') return ['run', 'A construir…', 'clock'];
  if (!j.bundle_available) return ['warn', 'Sem ficheiros', 'alert'];
  const gaps = [];
  if (!j.psarc_available) gaps.push('PSARC');
  if (!j.has_tones) gaps.push('tons');
  if (!j.cover_art) gaps.push('capa');
  return gaps.length ? ['warn', `Falta: ${gaps.join(', ')}`, 'alert'] : ['ok', 'Pronto a jogar', 'check'];
}
function renderJobCards() {
  const grid = document.getElementById('jobsGrid');
  grid.querySelectorAll('.proj-card, .home-empty').forEach(el => el.remove());
  const q = (document.getElementById('jobSearch').value || '').trim().toLowerCase();
  const shown = jobsCache.filter(JOB_FILTERS[jobFilter])
    .filter(j => !q || `${j.title} ${j.artist}`.toLowerCase().includes(q));
  if (jobsCache.length && !shown.length) {
    grid.insertAdjacentHTML('beforeend', '<p class="home-empty">Nenhum projeto corresponde a este filtro.</p>');
  }
  for (const j of shown) {
    const [kind, text, ico] = jobCardStatus(j);
    const card = document.createElement('article');
    card.className = 'proj-card';
    card.innerHTML = `
      <button type="button" class="proj-open" aria-label="Abrir ${esc(j.title)}">
        <div class="proj-cover">${j.cover_art ? `<img src="/jobs/${j.id}/cover" alt="" loading="lazy">` : icon('music')}</div>
        <div class="proj-meta">
          <div class="proj-title">${esc(j.title)}</div>
          <div class="proj-artist">${esc(j.artist)}</div>
          <span class="pv-chip ${kind}">${icon(ico)}${esc(text)}</span>
        </div>
      </button>
      <button type="button" class="proj-del" title="Remover projeto" aria-label="Remover ${esc(j.title)}">${icon('trash')}</button>`;
    card.querySelector('.proj-open').onclick = () => selectJob(j.id);
    const img = card.querySelector('.proj-cover img');
    if (img) img.onerror = () => { img.replaceWith(document.createRange().createContextualFragment(icon('music'))); };
    card.querySelector('.proj-del').onclick = async () => {
      const running = j.status === 'running';
      const msg = running
        ? `O projeto "${j.title}" ainda está a correr. Forçar a remoção? Só o deves fazer se estiver encravado (o worker morreu ou pendurou) — apaga também o bundle gerado.`
        : `Remover o projeto "${j.title}"? Isto apaga também o bundle gerado.`;
      const ok = await confirmModal(msg);
      if (!ok) return;
      const url = running ? `/jobs/${j.id}?force=true` : `/jobs/${j.id}`;
      const r = await fetch(url, { method: 'DELETE' });
      if (!r.ok && r.status !== 204) { toast((await r.json()).detail || 'erro'); return; }
      if (selectedJob && selectedJob.id === j.id) closeDetail();
      refreshJobs();
    };
    grid.appendChild(card);
  }
}
document.querySelectorAll('.home-filters [data-filter]').forEach(b => b.addEventListener('click', () => {
  jobFilter = b.dataset.filter;
  document.querySelectorAll('.home-filters [data-filter]').forEach(x => x.classList.toggle('active', x === b));
  renderJobCards();
}));
document.getElementById('jobSearch').addEventListener('input', renderJobCards);

async function refreshJobs() {
  try {
    jobsCache = await getJSON('/jobs');
  } catch {
    return;  // the offline banner already says why; don't blank the cards
  }
  renderJobCards();
}

// The project view's top bar: title, and a line with artist/album/year and
// the actions on the song's details.
function renderDetailHead(j) {
  const bits = [j.artist, j.album, j.year].filter(Boolean).map(esc).join(' · ');
  document.getElementById('detailHead').innerHTML =
    `<div class="pv-title">${esc(j.title)}</div>
     <div class="pv-sub"><span>${bits}</span>
       <button type="button" onclick="openMetaEdit()" title="Editar título, artista, álbum, ano">${icon('edit')}Editar info</button>
       ${j.rebuilt_from ? `<button type="button" onclick="selectJob('${j.rebuilt_from}')" title="Abrir a versão de onde esta foi reconstruída — a anterior nunca é apagada">${icon('undo')}Versão anterior</button>` : ''}
     </div>`;
}
// The chip beside the title: what the project still needs, at a glance.
// Clicking it opens the Exportar page, where each gap has its fix.
function setStatusChip(kind, text, ico) {
  const chip = document.getElementById('pvStatusChip');
  chip.className = `pv-chip ${kind}`;
  chip.innerHTML = `${icon(ico)}${esc(text)}`;
  chip.title = text;
  chip.hidden = false;
}
document.getElementById('pvStatusChip').addEventListener('click', () => showSection('exportar'));
let sectionShownFor = null;  // the job whose first "ready" view opened Partitura

async function selectJob(id, { poll = false, force = false } = {}) {
  let j;
  try {
    j = await getJSON(`/jobs/${id}`);
  } catch (err) {
    // Keep the poll alive across a blip: the banner already says the server is
    // unreachable, and dropping the timer here would leave a job that finished
    // meanwhile stuck showing "running" until the user clicks something.
    if (poll) { clearTimeout(pollTimer); pollTimer = setTimeout(() => selectJob(id, { poll }), 2500); }
    else toast(`não foi possível abrir o projeto: ${err.message}`, 'err');
    return;
  }
  selectedJob = j;
  document.getElementById('detailOverlay').hidden = false;
  renderDetailHead(j);

  const bar = document.getElementById('stagesBar');
  const idx = j.stages.indexOf(j.stage);
  bar.innerHTML = j.stages.map((s, i) => {
    let cls = 'stage';
    if (j.status === 'completed' || (idx >= 0 && i < idx)) cls += ' done';
    else if (i === idx && j.status === 'running') cls += ' now';
    return `<span class="${cls}">${s}</span>`;
  }).join('');

  // An error stays in plain sight; the pipeline's technical warnings fold
  // into one line, so they no longer push everything else down the page.
  const warns = j.warnings || [];
  document.getElementById('warnings').innerHTML =
    (j.error ? `<div class="errbox">${icon('x')} ${esc(j.error)}</div>` : '') +
    (warns.length
      ? `<details class="pv-warn"><summary>${warns.length} ${warns.length === 1 ? 'aviso técnico' : 'avisos técnicos'}</summary>` +
        warns.map(w => `<div class="warnbox">${esc(w)}</div>`).join('') + '</details>'
      : '');

  if (j.status === 'completed' && j.bundle_available) renderCompleteness(j);
  else {
    renderCompleteness(j);
    if (j.status === 'failed') setStatusChip('err', 'Falhou', 'x');
    else if (j.status === 'completed') setStatusChip('warn', 'Concluído sem ficheiros', 'alert');
    else setStatusChip('run', j.status === 'pending' ? 'Na fila…' : `A construir…${j.stage ? ` ${j.stage}` : ''}`, 'clock');
  }

  const dl = document.getElementById('downloads');
  dl.innerHTML = '';
  if (j.psarc_available)
    dl.innerHTML += `<a class="dl-card" href="/jobs/${j.id}/psarc">${icon('gamepad')}<b>PSARC para o jogo</b><span>pronto a copiar para a pasta dlc do Rocksmith</span></a>`;
  if (j.bundle_available)
    dl.innerHTML += `<a class="dl-card" href="/jobs/${j.id}/bundle">${icon('package')}<b>Bundle DLC Builder</b><span>XML, áudio e projeto .rs2dlc para abrir no DLC Builder</span></a>`;
  if (j.bundle_available && !j.psarc_available) dl.innerHTML += `<span class="meta">PSARC requer Wwise — ver README</span>`;
  if (!j.bundle_available) dl.innerHTML = '<span class="meta">Os ficheiros aparecem aqui quando a construção terminar.</span>';
  document.getElementById('noteCountsInfo').textContent =
    `Notas por pista: ${Object.entries(j.note_counts || {}).map(([k, v]) => `${k} ${v}`).join(' · ') || '—'}`;

  // A job that is still building (or failed) only has its Exportar page.
  const ready = j.status === 'completed' && j.bundle_available;
  if (!ready) { setReviewReady(false); showSection('exportar'); }
  else if (sectionShownFor !== j.id) showSection('partitura');
  sectionShownFor = ready ? j.id : null;

  loadCoverArt(j);

  document.getElementById('muteChk').checked = j.import_mutes !== false;
  document.getElementById('ddChk').checked = j.dynamic_difficulty !== false;
  if (j.status === 'completed' && j.bundle_available) {
    // Load arrangements (heavy: decodes the full recording, resets the audio
    // <src>) only ONCE per job. Re-running it on every status poll would reset
    // au.src — stopping playback — and null wavePeaks, making the waveform
    // flicker. force=true is used after a rebuild, when the chart did change.
    if (force || arrangementsLoadedFor !== id) {
      arrangementsLoadedFor = id;
      try {
        await loadArrangements(id);
      } catch (e) {
        arrangementsLoadedFor = null;  // allow a retry on the next click
        toast('erro a carregar arranjos: ' + (e && e.message || e));
      }
    }
  } else {
    arrangementsLoadedFor = null;
    setReviewReady(false);
    clearInterval(lyricsPollTimer);
    lyricsEvents = [];
  }

  // Re-arm with setTimeout (not setInterval): the next poll is scheduled only
  // after this one finishes, so a slow render can't stack overlapping calls.
  clearTimeout(pollTimer);
  if (j.status === 'pending' || j.status === 'running')
    pollTimer = setTimeout(() => selectJob(id, { poll: true }), 2500);
  refreshJobs();
}

async function loadArrangements(id) {
  arrangements = await getJSON(`/jobs/${id}/arrangements`);
  syncAnchorsByKind = {};  // fresh pending corrections per arrangement
  tempoScaleByKind = {};
  // Seed the pending note edits from the ones ALREADY COMMITTED for each
  // arrangement, instead of starting empty. applyAll() always sends the whole
  // dict, so starting empty meant a rebuild for any unrelated reason (a tuning
  // change, say) sent {} and the backend — which REPLACES the stored value —
  // silently erased every note edit the user had applied.
  noteOverridesByKind = {};
  for (const a of arrangements) {
    if (a.note_overrides && a.note_overrides.length) {
      noteOverridesByKind[a.kind] = a.note_overrides.map(o => ({ ...o }));
    }
  }
  // Snapshot of what is ALREADY built, so "pendente" means changed-since-build
  // rather than "this job has note edits" (which it now legitimately does).
  noteOverridesBuilt = JSON.stringify(noteOverridesByKind);
  noteClipboard = [];  // avoid pasting a previous song's notes into this one
  syncAnchors = [];
  selectedTimes = new Set();
  currentArr = 0;  // reset before initSync redraws, so a stale index can't go out of range
  wavePeaks = null; waveDuration = 0;
  stopPlayback(); playBuffer = null; playGain = null; pausedAt = 0;
  if (!arrangements.length) return;
  setReviewReady(true);
  const a0 = arrangements[0];
  centOffsetLive = a0.cent_offset;
  songSections = (a0.sections || []).map(s => ({ time: s.time, name: s.name }));
  sectionsTouched = false;
  document.getElementById('tuningInfo').innerHTML =
    `<p class="meta">offsets: [${a0.tuning_offsets.join(', ')}] · desvio: <span id="centOffsetVal">${a0.cent_offset.toFixed(1)}</span> cents · BPM médio: ${a0.average_bpm.toFixed(1)}</p>`;
  document.getElementById('tuningInputs').innerHTML = STD.map((std, i) =>
    `<input type="number" min="20" max="80" value="${std + a0.tuning_offsets[i]}" data-string="${i}">`).join('');
  document.getElementById('detectTuningInfo').textContent = '';
  document.getElementById('arrTabs').innerHTML = arrangements.map((a, i) =>
    `<button type="button" class="${i ? '' : 'active'}" onclick="showArr(${i})">${a.kind} (${a.note_count}n/${a.chord_count}c)</button>`).join('');
  document.getElementById('applyToAllLabel').style.display = arrangements.length > 1 ? '' : 'none';
  document.getElementById('applyToAllChk').checked = false;
  initSync(selectedJob);
  showArr(0);
  document.getElementById('tabwrap').scrollLeft = 0;
  renderSectionsList();
  updateClipboardInfo();
  updateSelectionInfo();
  await loadLyrics(id);
  await loadTones(id);
  // Resume polling if tone detection is in progress.
  if (selectedJob && selectedJob.tone_detection_status === 'detecting') {
    document.getElementById('toneDetectionWrap').style.display = '';
    pollToneDetection();
  }
}

// String colors low E -> high e: red, yellow, blue, orange, green, purple.
const STRING_COLORS = ['#e6483c', '#f5dc3c', '#3f9bdc', '#f0973c', '#5cc24a', '#b56cdc'];
// Standard tuning MIDI (low→high: E A D G B e) and note names, so the staff can
// label each string with its REAL pitch = standard + the arrangement's tuning
// offset (e.g. Drop C# shows C# G# C# F# A# D# instead of E A D G B e).
const STD_TUNING_MIDI = [40, 45, 50, 55, 59, 64];
const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
function stringLabel(str, offsets) {
  const off = (offsets && offsets[str] != null) ? offsets[str] : 0;
  const midi = STD_TUNING_MIDI[str] + off;
  return NOTE_NAMES[((midi % 12) + 12) % 12];
}

// Short on-tab labels for each technique (fallback / tooltip text).
const TECH_ABBR = {
  bend: 'B', hammerOn: 'H', pullOff: 'P', slide: 'S', harmonic: 'HA',
  palmMute: 'PM', vibrato: 'V', tap: 'T', slap: 'SL', pluck: 'PO', accent: 'A',
};

// Graphical tab-notation glyphs drawn above a note for its techniques.
// Expressive techniques get a real symbol (bend arrow, vibrato wave, slide
// line, hammer/pull slur, harmonic diamond); the rest fall back to a short
// text badge. Each glyph is authored around a local origin (0,0) that sits
// just above the note and extends upward (negative y).
// Bend and vibrato are NOT here: they're drawn at the note itself (bend = a
// rising curved arrow from the note; vibrato = a wavy sustain line), not as a
// small glyph above it.
const TECH_GLYPH = {
  slide: '<line x1="-6" y1="0" x2="6" y2="-8" stroke="#fff" stroke-width="1.6"/>',
  harmonic: '<path d="M0,-11 L5,-5 L0,1 L-5,-5 Z" fill="none" stroke="#fff" stroke-width="1.4"/>',
  hammerOn: '<path d="M-6,-2 q6,-6 12,0" fill="none" stroke="#fff" stroke-width="1.4"/><text x="0" y="-8" fill="#fff" font-size="8" font-weight="700" text-anchor="middle">h</text>',
  pullOff: '<path d="M-6,-2 q6,-6 12,0" fill="none" stroke="#fff" stroke-width="1.4"/><text x="0" y="-8" fill="#fff" font-size="8" font-weight="700" text-anchor="middle">p</text>',
};
const TECH_TEXT = { palmMute: 'P.M.', tap: 'T', slap: 'SL', pluck: 'PO', accent: '›' };

function techGlyphs(techs, cx, topY) {
  const slot = 15, n = techs.length;
  let out = '';
  techs.forEach((t, i) => {
    const gx = cx - (n - 1) * slot / 2 + i * slot;
    const body = TECH_GLYPH[t]
      || `<text x="0" y="-2" fill="#fff" font-size="9" font-weight="700" text-anchor="middle">${TECH_TEXT[t] || TECH_ABBR[t] || t}</text>`;
    out += `<g transform="translate(${gx},${topY})">${body}</g>`;
  });
  return out;
}

// A vibrato note's held time is drawn as a wave (the sustain line itself
// oscillating) instead of a straight bar — the standard vibrato notation.
// Path of alternating half-wavelength bumps from (x,y) rightwards over width w.
function sustainWave(x, y, w) {
  const amp = 4, half = 6;
  let d = `M${x.toFixed(1)},${y}`, cur = x, up = true;
  while (cur < x + w - 0.5) {
    const nx = Math.min(cur + half, x + w);
    const mid = (cur + nx) / 2;
    d += ` Q${mid.toFixed(1)},${(y + (up ? -amp : amp)).toFixed(1)} ${nx.toFixed(1)},${y}`;
    cur = nx; up = !up;
  }
  return d;
}

// Bend magnitude → tab label (semitones: 1=½, 2=full/whole step, 3=1½…).
function bendLabel(semis) {
  if (!semis) return '';
  if (semis === 1) return '½';
  if (semis === 2) return 'full';
  return `${Math.floor(semis / 2)}${semis % 2 ? '½' : ''}`;
}

// Bend: a near-vertical arrow rising from the note, curving right near the top,
// with the bend amount ("full", "½", …) above the arrowhead — the standard
// Guitar-Pro/tab bend notation. Rises in fixed px so it reads at any zoom.
function bendArrow(x, y, r, label) {
  const x0 = x, y0 = y - r + 2;          // start just inside the note's top
  const rise = 30, tipX = x + 9, tipY = y0 - rise;
  let out = `<path d="M${x0},${y0} C${x0},${(y0 - rise * 0.6).toFixed(1)} ${tipX},${(y0 - rise * 0.5).toFixed(1)} ${tipX},${tipY + 5}" fill="none" stroke="#fff" stroke-width="2"/>`;
  out += `<path d="M${tipX - 4},${tipY + 6} L${tipX},${tipY} L${tipX + 4},${tipY + 6} Z" fill="#fff"/>`;
  if (label) out += `<text x="${tipX}" y="${tipY - 3}" fill="#fff" font-size="10" font-weight="700" text-anchor="middle">${label}</text>`;
  return out;
}

// Per-measure tempo of an arrangement: the AUTHORED value from the GP file and
// the EFFECTIVE one after the pending offset/tempo/anchor edits. Pulled out of
// showArr so the score's amber "this bar was re-tempoed" labels and the
// "Exportar GP corrigido" button read the SAME numbers — two implementations
// would silently drift and the exported file would not match what was shown.
function barTempoTable(a, warp) {
  const tbeats = a.beats || [];
  const barList = a.bars || [];
  // Beats per bar in ONE merge walk over the two sorted lists. Counting them
  // inside barBpm rescanned every beat for every bar — O(bars × beats), ~85k
  // iterations on a 146-bar song, paid on every single redraw.
  const beatsInBar = new Array(barList.length).fill(0);
  for (let bi = 0, k = 0; bi < barList.length; bi++) {
    const t0 = barList[bi].time;
    const t1 = bi + 1 < barList.length ? barList[bi + 1].time : Infinity;
    while (k < tbeats.length && tbeats[k] < t0 - 1e-6) k++;
    let n = 0;
    while (k + n < tbeats.length && tbeats[k + n] < t1 - 1e-6) n++;
    beatsInBar[bi] = n;
    k += n;
  }
  const barBpm = (bi) => {
    const t0 = barList[bi].time;
    const t1 = bi + 1 < barList.length ? barList[bi + 1].time : null;
    if (t1 == null || t1 <= t0) return bi > 0 ? barBpm(bi - 1) : { eff: 0, auth: 0 };
    const n = beatsInBar[bi];
    if (!n) return { eff: 0, auth: 0 };
    const auth = Math.round(n * 60 / (t1 - t0));
    const dur = warp(previewScale(t1)) - warp(previewScale(t0));
    const eff = dur > 0.01 ? Math.round(n * 60 / dur) : auth;
    return { eff, auth };
  };
  return { beatsInBar, barBpm };
}

// The bars whose tempo the pending sync actually changed — exactly the ones the
// score draws in amber. `changed` uses the same >= 2 BPM threshold as the label,
// so what you see marked is what gets written.
const GP_EXPORT_MIN_BPM = 10.5, GP_EXPORT_MAX_BPM = 399.5;  // the endpoint's own bounds

function retempoedBars(a) {
  const { barBpm } = barTempoTable(a, buildTimeWarp(syncAnchors));
  const out = [];
  for (let bi = 0; bi < (a.bars || []).length; bi++) {
    const { eff, auth } = barBpm(bi);
    if (eff > 0 && Math.abs(eff - auth) >= 2) {
      out.push({ measure: a.bars[bi].measure, bpm: eff, auth });
    }
  }
  return out;
}

function showArr(i) {
  if (i !== currentArr) { loadArrSync(i); stopArrangementPreview(); }  // tab change: swap in that chart's own sync state
  currentArr = i;
  for (const [idx, btn] of document.querySelectorAll('#arrTabs button').entries())
    btn.classList.toggle('active', idx === i);
  const a = arrangements[i];
  const applyKindEl = document.getElementById('applyKind');
  if (applyKindEl) applyKindEl.textContent = a.kind;
  const svg = document.getElementById('tabsvg');
  viewOrigin = isGpJob() ? Math.max(0, MIN_LEAD - offsetLive) : 0;  // bundle time at the left edge (0s)
  // Size the chart to the FULL song, not just the last NOTE: a track that rests
  // through the outro (e.g. a lead that stops at bar 120 of 146) still has all
  // its bars/beats in the grid, and the recording keeps playing — so extend the
  // width to the last bar/beat and the recording length too, or those trailing
  // (empty) bars + waveform tail get clipped off the right edge.
  const lastNote = a.notes.length ? Math.max(...a.notes.map(n => n.time + n.sustain)) : 0;
  const lastBar = (a.bars && a.bars.length) ? a.bars[a.bars.length - 1].time : 0;
  const lastBeat = (a.beats && a.beats.length) ? a.beats[a.beats.length - 1] : 0;
  const audioEnd = (waveDuration || 0) + viewOrigin;  // recording end, in bundle time
  const dur = Math.max(lastNote, lastBar, lastBeat, audioEnd, 10);
  // SB = staff bottom (string-0 line). The band between SB and H holds the
  // chord-name row, kept wide enough that names never touch the lowest notes.
  const px = BASE_PX * zoomLevel, ROW = STAFF_ROW, R = NOTE_R, W = Math.max(900, dur * px + 60);
  const H = STAFF_H, SB = STAFF_SB;
  tabPx = px; tabH = H;
  svg.setAttribute('width', W);
  svg.setAttribute('height', H);  // includes the chord-name band below the staff
  let s = '';
  s += waveformSvg(W, H, px);  // audio reference, drawn behind staff + notes
  for (let str = 0; str < 6; str++) {
    const y = SB - str * ROW;
    s += `<line x1="30" y1="${y}" x2="${W-10}" y2="${y}" stroke="#3a3c45"/>`;
    s += `<text x="6" y="${y+5}" fill="${STRING_COLORS[str]}" font-size="15" font-weight="700">${stringLabel(str, a.tuning_offsets)}</text>`;
  }
  // Timeline grid: quarter-second ticks for fine drag alignment, whole-second
  // ticks (small label) and 5s major ticks (larger label).
  for (let q = 0; q <= dur * 4; q++) {
    const t = q / 4;
    const x = 30 + t * px;
    const isMajor = q % 20 === 0; // every 5s
    const isSecond = q % 4 === 0; // every 1s
    const stroke = isMajor ? '#6a6f7d' : isSecond ? '#4a4e59' : '#33363f';
    s += `<line x1="${x}" y1="14" x2="${x}" y2="${SB}" stroke="${stroke}" stroke-width="${isMajor ? 1 : 0.5}"/>`;
    if (isMajor) s += `<text x="${x}" y="12" fill="#666" font-size="12">${t}s</text>`;
    else if (isSecond) s += `<text x="${x}" y="12" fill="#454852" font-size="9">${t}</text>`;
  }
  const barWarp = buildTimeWarp(syncAnchors);
  // Snap grid (the note-drag targets) — faint short ticks at each grid position,
  // shown while snapping is on so the "jumps" land on something visible.
  if (snapToBeats) {
    for (const bt of snapGridTimes()) {
      const x = timeToX(barWarp(previewScale(bt)));
      if (x < 24 || x > W - 4) continue;
      s += `<line x1="${x}" y1="${SB-12}" x2="${x}" y2="${SB}" stroke="#5b6572" stroke-width="1" opacity=".45"/>`;
    }
  }
  // Bar (measure) lines + numbers — drawn through the same previewScale+warp
  // as the notes so they track pending sync edits. Helps spot exactly which
  // measure drifts from the recording.
  const tbeats = a.beats || [];
  const barList = a.bars || [];
  // EFFECTIVE BPM of each measure — beats in [downbeat, next downbeat) × 60 /
  // the measure's WARPED duration, i.e. the tempo the bar will actually play
  // at after the pending offset/tempo/anchor edits (a dynamic-sync anchor that
  // locally re-tempos a passage shows its new BPM right on the bars it spans).
  // Amber = the pending sync changed this bar's tempo vs the authored GP value.
  // Beats per bar, precomputed in ONE merge walk over the two sorted lists.
  // Counting them inside barBpm rescanned every beat for every bar — O(bars ×
  // beats), ~85k iterations on a 146-bar song and ~360k on a long one, paid on
  // every single redraw.
  const { barBpm } = barTempoTable(a, barWarp);
  // Label spacing. Bar lines are always drawn, but the TEXT beside them is
  // dropped when it would collide with the previous label: on a dense chart
  // (or when zoomed out) numbers and BPMs otherwise pile into an unreadable
  // wall. The full BPM label needs more room than a bare bar number.
  let lastBpmX = -999, lastNumX = -999;
  for (let bi = 0; bi < barList.length; bi++) {
    const b = barList[bi];
    const x = timeToX(barWarp(previewScale(b.time)));
    if (x < 24 || x > W - 4) continue;
    s += `<line x1="${x}" y1="30" x2="${x}" y2="${SB}" stroke="#5a6a8a" stroke-width="1" opacity=".55"/>`;
    const bb = barBpm(bi);
    if (bb.eff > 0 && x - lastBpmX > 64) {
      const changed = Math.abs(bb.eff - bb.auth) >= 2;  // pending sync re-tempos this bar
      s += `<text x="${x+3}" y="42" font-size="11" font-weight="700">`
        + `<tspan fill="#7d8aa5">${b.measure}</tspan>`
        + `<tspan fill="${changed ? '#f2b84b' : '#b58cff'}" font-size="10"> &#9833;${bb.eff}</tspan></text>`;
      lastBpmX = lastNumX = x;
    } else if (x - lastNumX > 26) {
      s += `<text x="${x+3}" y="42" fill="#7d8aa5" font-size="11" font-weight="700">${b.measure}</text>`;
      lastNumX = x;
    }
  }
  // Tempo-change markers (♩=NNN): where the beat spacing changes, the GP's
  // authored BPM changed. Derived from the beat grid so mid-song tempo changes
  // are visible on the tab (matching how Guitar Pro shows them). Rare in GP
  // (usually step changes), so a ≥3 BPM jump avoids float-jitter markers.
  // Highlight where the authored tempo changes with a dashed line (the BPM
  // value itself is now on every measure number above).
  let lastBpm = 0;
  for (let i = 0; i + 1 < tbeats.length; i++) {
    const iv = tbeats[i + 1] - tbeats[i];
    if (iv <= 0.02) continue;
    const bpm = Math.round(60 / iv);
    if (Math.abs(bpm - lastBpm) < 3) continue;
    lastBpm = bpm;
    const x = timeToX(barWarp(previewScale(tbeats[i])));
    if (x < 24 || x > W - 4) continue;
    s += `<line x1="${x}" y1="44" x2="${x}" y2="${SB}" stroke="#b58cff" stroke-width="1.5" stroke-dasharray="3,3" opacity=".6"/>`;
  }
  // Tone-change markers: where the tone switches on the score (amber), labelled
  // with the tone name — so you can see which tone plays where. The base tone is
  // labelled at the start.
  if (jobTones.length && (toneBase || toneChanges.length)) {
    const tName = k => (jobTones.find(t => t.key === k) || {}).name || k;
    const marks = toneChanges  // already time-sorted (see loadTones)
      .map(c => ({ x: timeToX(barWarp(previewScale(c.time))), name: tName(c.name) }));
    if (toneBase) marks.unshift({ x: 32, name: tName(toneBase) });
    for (const m of marks) {
      if (m.x < 24 || m.x > W - 4) continue;
      if (m.x > 34) s += `<line x1="${m.x}" y1="44" x2="${m.x}" y2="${SB}" stroke="#e0a54a" stroke-width="1.5" stroke-dasharray="4,2" opacity=".7"/>`;
      const lw = m.name.length * 6.4 + 20;
      s += `<rect x="${m.x + 1}" y="${SB + 20}" width="${lw.toFixed(0)}" height="16" rx="4" fill="#14151a" opacity=".8"/>`;
      s += `<use href="#i-wave" x="${m.x + 4}" y="${SB + 22}" width="12" height="12" style="color:#e0a54a"/>`;
      s += `<text x="${m.x + 19}" y="${SB + 32}" fill="#e0a54a" font-size="11" font-weight="700">${esc(m.name)}</text>`;
    }
  }
  // Section markers (song structure — intro/verso/refrão…): a labeled marker
  // spanning the FULL staff height (distinct from the tone-change band below
  // the staff), teal, so the structure is visible at a glance while scrolling.
  for (const sec of songSections) {
    const x = timeToX(barWarp(previewScale(sec.time)));
    if (x < 24 || x > W - 4) continue;
    s += `<line x1="${x}" y1="14" x2="${x}" y2="${SB}" stroke="#3ddcc4" stroke-width="1.5" stroke-dasharray="5,3" opacity=".65"/>`;
    const lw = sec.name.length * 6.2 + 16;
    s += `<rect x="${x + 1}" y="4" width="${lw.toFixed(0)}" height="15" rx="4" fill="#14151a" opacity=".85"/>`;
    s += `<use href="#i-tag" x="${x + 3}" y="5" width="12" height="12" style="color:#3ddcc4"/>`;
    s += `<text x="${x + 18}" y="15" fill="#3ddcc4" font-size="11" font-weight="700">${esc(sec.name)}</text>`;
  }
  // Lyrics editor times are in recording-time (un-padded); shift to the display
  // timeline the same way the notes do — by viewOrigin AND the intro silence
  // (leadInBuilt) — so words line up with their notes after a lead-in rebuild.
  for (let li = 0; li < lyricsEvents.length; li++) {
    const e = lyricsEvents[li];
    const word = e.lyric.trim();
    if (!word) continue;
    const x = timeToX(e.time + viewOrigin + leadInBuilt);
    const active = currentPlayheadT >= e.time + leadInBuilt
      && currentPlayheadT <= e.time + e.length + leadInBuilt;
    const brk = e.lineBreak;  // the in-game "+" — this word ends a lyric line
    s += `<g class="lyric-word" data-li="${li}" style="cursor:grab">`;
    s += `<text x="${x}" y="26" fill="${active ? '#ff7a45' : '#9aa0ad'}" font-size="13" font-weight="${active ? '700' : '400'}" text-anchor="middle">${esc(word)}</text>`;
    // A line-break word gets a STRONGER connector (solid amber, thicker) so the
    // in-game line wrap is visible on the score; a mid-line word keeps the faint
    // dashed tick.
    s += `<line x1="${x}" y1="30" x2="${x}" y2="${SB}" stroke="${brk ? '#ffb020' : (active ? '#ff7a45' : '#454852')}" stroke-width="${brk ? 2 : 1}" ${brk ? '' : 'stroke-dasharray="2,4"'} opacity="${brk ? '.6' : '.35'}"/>`;
    if (brk) s += `<text x="${x + 7}" y="18" fill="#ffb020" font-size="12" font-weight="700">¶</text>`;
    s += `</g>`;
  }
  // Merge in pending note-editor edits (add/edit/delete) for THIS arrangement
  // — a purely visual, additive step: everything else in showArr (dur, drag
  // mechanics, playback/synth) still reads a.notes untouched, so a pending
  // note edit only affects what's drawn, not sync/playback, until a rebuild
  // actually bakes it into the built arrangement.
  const pendingNoteOv = noteOverridesByKind[a.kind] || [];
  const notes = pendingNoteOv.length ? mergeNoteOverrides(a.notes, pendingNoteOv) : a.notes;
  const pendingKeys = new Set(pendingNoteOv.map(o => `${o.time.toFixed(6)}:${o.string}`));
  // group simultaneous notes (chords) so they get a connecting bracket
  const groups = [];
  for (const n of notes) {
    const last = groups[groups.length - 1];
    if (last && n.chord && Math.abs(n.time - last.time) < 0.03) last.notes.push(n);
    else groups.push({ time: n.time, notes: [n] });
  }
  // Preview the cumulative effect of the sync anchors set so far: notes are
  // drawn at their warped (corrected) time, while data-t keeps the original
  // chart time so new anchors stay in the backend's coordinate system.
  // Notes are placed at parse+offset+tempo position (previewScale), then the
  // pending sync anchors warp that *display* position — the same space the
  // backend uses, so anchors round-trip exactly through a rebuild even with a
  // tempo/offset change still pending.
  const warp = buildTimeWarp(syncAnchors);
  let lastChordX = -999;
  const lastTechX = [-999, -999, -999, -999, -999, -999];
  for (const g of groups) {
    const sel = selectedTimes.has(g.time) ? ' selected' : '';
    const dispT = warp(previewScale(g.time));
    s += `<g class="note-grp${sel}" data-t="${g.time}">`;
    if (g.notes.length > 1) {
      const x = timeToX(dispT);
      const ys = g.notes.map(n => SB - n.string * ROW);
      s += `<line x1="${x}" y1="${Math.min(...ys)}" x2="${x}" y2="${Math.max(...ys)}" stroke="#9aa0ad" stroke-width="2"/>`;
      // Derived chord name (best-effort, from the notes' pitches). Drawn in the
      // dark band below the staff (a fixed chord row, well clear of the lowest
      // string's notes) so names never overlap the notes and all line up.
      const cn = g.notes.find(n => n.chord_name);
      // Skip a name that would overlap the previous one. Chord names are wide
      // and centred, so on a dense chart every group printing its own turned the
      // row into an unreadable smear; the omitted ones are still identifiable
      // from the fret numbers.
      if (cn && x - lastChordX > Math.max(30, cn.chord_name.length * 7)) {
        s += `<text x="${x}" y="${H - 16}" fill="#ffd479" font-size="13" font-weight="700" text-anchor="middle">${esc(cn.chord_name)}</text>`;
        lastChordX = x;
      }
    }
    for (const n of g.notes) {
      const x = timeToX(dispT), y = SB - n.string * ROW;
      const color = STRING_COLORS[n.string];
      const tech = n.techniques.length > 0;
      const vibrato = n.techniques.includes('vibrato');
      const bend = n.techniques.includes('bend');
      const susW = n.sustain > 0.05 ? n.sustain*px*(tempoScaleLive/builtScale) : 0;
      // A note with a pending (unbuilt) note-editor edit gets a dashed cyan
      // ring so it reads as "not yet rebuilt", same spirit as the amber
      // "changed by pending sync" bar-BPM marker above.
      const pending = pendingKeys.has(`${n.time.toFixed(6)}:${n.string}`);
      s += `<g class="note-single" data-string="${n.string}">`;
      if (vibrato)  // held time drawn as an oscillating line (min width so it reads as a wave)
        s += `<path d="${sustainWave(x, y, Math.max(susW, 24))}" fill="none" stroke="${color}" stroke-width="2.5" opacity=".8"/>`;
      else if (susW > 0)
        s += `<rect x="${x}" y="${y-3}" width="${susW}" height="6" fill="${color}" opacity=".4" rx="3"/>`;
      const shape = n.chord
        ? `<rect class="note-shape" x="${x-R}" y="${y-R}" width="${R*2}" height="${R*2}" rx="4" fill="${color}"${tech ? ' stroke="#fff" stroke-width="2.5" stroke-dasharray="3,3"' : ''}/>`
        : `<circle class="note-shape" cx="${x}" cy="${y}" r="${R}" fill="${color}"${tech ? ' stroke="#fff" stroke-width="2.5" stroke-dasharray="3,3"' : ''}/>`;
      s += shape;
      if (pending) s += `<circle cx="${x}" cy="${y}" r="${R+3}" fill="none" stroke="#3ddcc4" stroke-width="1.5" stroke-dasharray="2,2"/>`;
      s += `<text x="${x}" y="${y+5}" fill="#14151a" font-size="14" font-weight="700" text-anchor="middle">${n.fret}</text>`;
      if (bend) s += bendArrow(x, y, R, bendLabel(n.bend_semitones));  // rising arrow + amount
      if (tech) {
        // bend/vibrato are drawn at the note itself, not as glyphs above it
        const gt = n.techniques.filter(t => t !== 'vibrato' && t !== 'bend');
        // Per STRING spacing: a run of palm mutes printed "P.M." over every
        // single note, which is both unreadable and redundant — the dashed ring
        // on the note itself already marks it, and the tooltip lists them all.
        if (gt.length && x - (lastTechX[n.string] ?? -999) > 30) {
          s += techGlyphs(gt, x, y - R - 4);
          if (n.string >= 0 && n.string < 6) lastTechX[n.string] = x;
        }
        s += `<title>${n.techniques.join(', ')}</title>`;
      }
      s += `</g>`;
    }
    s += `</g>`;
  }
  // Sync anchors (drift corrections). Drawn in a distinct teal — NOT the
  // playhead's orange — with a numbered pin below the staff, so they read as
  // "correction points" and never blur into the playhead. A faint ghost tick
  // marks where the point was; a short connector near the bottom (out of the
  // note area) shows the shift to where it now sits.
  const ANCHOR = '#22c1c3';
  let anchorNo = 0;
  for (const [origT, newT] of syncAnchors) {  // already in display coordinates
    anchorNo++;
    const x1 = timeToX(origT), x2 = timeToX(newT);
    const moved = Math.abs(x2 - x1) > 0.5;
    if (moved)
      s += `<line x1="${x1}" y1="30" x2="${x1}" y2="${SB}" stroke="${ANCHOR}" stroke-width="1" stroke-dasharray="2,4" opacity=".4"/>`;
    s += `<line x1="${x2}" y1="30" x2="${x2}" y2="${SB}" stroke="${ANCHOR}" stroke-width="1.5" opacity=".85"/>`;
    if (moved)
      s += `<line x1="${x1}" y1="${SB-5}" x2="${x2}" y2="${SB-5}" stroke="${ANCHOR}" stroke-width="2" marker-end="url(#anchorArrow)"/>`;
    s += `<circle cx="${x2}" cy="${SB+13}" r="8.5" fill="${ANCHOR}"/>`;
    s += `<text x="${x2}" y="${SB+17}" fill="#08343a" font-size="11" font-weight="700" text-anchor="middle">${anchorNo}</text>`;
  }
  s += `<defs><marker id="anchorArrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 z" fill="${ANCHOR}"/></marker></defs>`;
  const phX = 30 + currentPlayheadT * tabPx;
  s += `<line id="playhead" x1="${phX}" y1="0" x2="${phX}" y2="${H}" stroke="#ff7a45" stroke-width="2" opacity=".9"/>`;
  // "Detect first note" marker: the recording point where the 1st note sounds.
  if (firstNoteFlow === 'note') {
    const mx = 30 + firstNoteAudioT * tabPx;
    s += `<line x1="${mx}" y1="0" x2="${mx}" y2="${H}" stroke="#3fdc8a" stroke-width="2" stroke-dasharray="5,3"/>`;
    s += `<text x="${mx+4}" y="52" fill="#3fdc8a" font-size="11" font-weight="700">1ª nota</text>`;
  }
  svg.innerHTML = s;
  invalidateLyricWords();  // the nodes the playhead frame highlights were just replaced
  syncResetPointer();
  renderAnchorsList();
  updateSyncOffsetDisplay();
  updateBarSyncPanel();
  updateNoteEditsInfo();
  drawFretboard();  // redraw the neck (tuning labels) + refresh the active notes
  updateFretboard(playheadDisplay(audioTime()));
  updateLiveBpm(playheadDisplay(audioTime()));
}
window.showArr = showArr;

// ---- Manual drift correction (drag a note, or a selected excerpt, to where
// it should play) ----
// syncAnchors: [(chartTime, correctedTime), ...] in the chart's currently
// displayed timeline; sent to /rebuild as sync_anchors. Each arrangement
// (tab) has its OWN pending set — corrections to Lead never touch Rhythm — so
// syncAnchors is a reference into syncAnchorsByKind for the current tab.
let syncAnchors = [];
let syncAnchorsByKind = {};  // kind -> pending [(chartTime, correctedTime), ...]
let tempoScaleByKind = {};   // kind -> pending tempoScaleLive (null = use builtScale)
// selectedTimes: chart times (g.time) of note-groups currently selected for
// a multi-note excerpt drag.
let selectedTimes = new Set();

// Note editor (add/edit/delete notes + techniques directly on the score).
// Unlike sync anchors/tone changes/sections, note edits are genuinely
// per-arrangement (Lead and Rhythm have different note content), so this is
// keyed by kind with no shared/job-level list. Bundle-clock times, placed
// directly on the already-warped display (same convention as tone_changes/
// sections) — no prior GP-authored default to lose, so (like tone_changes)
// the whole dict is just sent as-is on every rebuild; an untouched job sends
// {} and nothing changes.
let noteOverridesByKind = {};  // kind -> pending [{time,string,fret,sustain,techniques,bend_semitones,slide_to_fret,deleted}, ...]

// Merge pending note-editor overrides on top of the built notes for display
// (mirrors _apply_note_overrides in gp_pipeline.py — keyed by (time,string),
// deleted=true removes, otherwise upserts). Purely a rendering-time view:
// does not mutate a.notes.
function mergeNoteOverrides(baseNotes, overrides) {
  const byKey = new Map(baseNotes.map(n => [`${n.time.toFixed(6)}:${n.string}`, { ...n }]));
  for (const ov of overrides) {
    const key = `${ov.time.toFixed(6)}:${ov.string}`;
    if (ov.deleted) { byKey.delete(key); continue; }
    byKey.set(key, {
      time: ov.time, string: ov.string, fret: ov.fret, sustain: ov.sustain,
      chord: false, chord_name: null,
      techniques: ov.techniques.slice(), bend_semitones: ov.bend_semitones || 0,
    });
  }
  const merged = [...byKey.values()].sort((a, b) => a.time - b.time || a.string - b.string);
  // Chord flag = "another note sounds at the same instant". merged is sorted by
  // time, so a simultaneous partner is always an immediate NEIGHBOUR — a linear
  // sweep suffices. (This used to be `merged.some(...)` per note, i.e. O(n^2):
  // on a 3000-note chart ~4.5M comparisons on EVERY redraw, and it switched on
  // permanently after the first note edit, which is what made the score crawl
  // and the audio stutter the longer you edited.)
  for (let i = 0; i < merged.length; i++) {
    const prev = merged[i - 1], next = merged[i + 1];
    merged[i].chord = (!!prev && Math.abs(prev.time - merged[i].time) < 0.03)
                   || (!!next && Math.abs(next.time - merged[i].time) < 0.03);
  }
  return merged;
}

// Nearest sync-grid chart time to a click's DISPLAY x — used to place a new
// note exactly on a real beat/subdivision, reusing the same grid note-drag
// snapping already uses. Returns the grid point's ORIGINAL (unwarped) chart
// time, matching note.time's coordinate space — found by forward-projecting
// each grid candidate to display space rather than inverting the click (the
// warp+tempo chain isn't cheaply invertible), which needs no new machinery.
function nearestGridChartTime(displayX) {
  const grid = snapGridTimes();
  if (!grid.length) return xToTime(displayX);
  const warp = buildTimeWarp(syncAnchors);
  let best = grid[0], bestDist = Infinity;
  for (const t of grid) {
    const d = Math.abs(timeToX(warp(previewScale(t))) - displayX);
    if (d < bestDist) { bestDist = d; best = t; }
  }
  return best;
}

// ---- Copy/paste notes: duplicate a selected excerpt elsewhere in the score
// (the same arrangement, or a different tab — e.g. copy a riff from Lead
// into Rhythm) without re-entering it note by note. The clipboard is plain
// in-memory JS state (not the OS clipboard) — session-only, like every other
// pending-edit state in this viewer.
let noteClipboard = [];  // [{dTime, string, fret, sustain, techniques, bend_semitones}, ...]
let noteOverridesBuilt = '{}';  // JSON of the note edits already baked into the build

function updateClipboardInfo() {
  const el = document.getElementById('clipboardInfo');
  const btn = document.getElementById('pasteNotes');
  if (!el || !btn) return;
  el.textContent = noteClipboard.length ? `${noteClipboard.length} nota(s) copiada(s)` : '';
  btn.disabled = !noteClipboard.length;
}

// Copies the CURRENTLY SELECTED notes (selectedTimes, from Shift+click/
// Ctrl+click/Excerto — the same selection "Excerto" drag already uses) from
// this arrangement's live (pending-edits-merged) note list, normalized to
// relative offsets from the earliest copied note so paste can re-anchor them
// anywhere.
function copySelectedNotes() {
  if (!selectedTimes.size) { toast('seleciona notas primeiro (Shift+clique ou modo Excerto)', 'err'); return; }
  const a = arrangements[currentArr];
  if (!a) return;
  const pendingOv = noteOverridesByKind[a.kind] || [];
  const merged = pendingOv.length ? mergeNoteOverrides(a.notes, pendingOv) : a.notes;
  const times = [...selectedTimes];
  const picked = merged.filter(n => times.some(t => Math.abs(t - n.time) < 0.03));
  if (!picked.length) { toast('nada selecionado para copiar', 'err'); return; }
  const minTime = Math.min(...picked.map(n => n.time));
  noteClipboard = picked.map(n => ({
    dTime: n.time - minTime, string: n.string, fret: n.fret, sustain: n.sustain,
    techniques: (n.techniques || []).slice(), bend_semitones: n.bend_semitones || 0,
  }));
  updateClipboardInfo();
  toast(`${noteClipboard.length} nota(s) copiada(s).`, 'ok');
}

// Pastes the clipboard at the current playhead, snapped to the sync grid
// (nearestGridChartTime) — only the anchor note snaps; the rest keep their
// original relative spacing, so a copied riff's own rhythm is preserved.
function pasteNotesAtCursor() {
  if (!noteClipboard.length) { toast('nada copiado ainda', 'err'); return; }
  if (!arrangements[currentArr]) return;
  const anchor = nearestGridChartTime(timeToX(currentPlayheadT + viewOrigin));
  for (const c of noteClipboard) {
    upsertNoteOverride({
      time: anchor + c.dTime, string: c.string, fret: c.fret, sustain: c.sustain,
      techniques: c.techniques.slice(), bend_semitones: c.bend_semitones,
      slide_to_fret: null, deleted: false,
    });
  }
  showArr(currentArr);
  toast(`${noteClipboard.length} nota(s) colada(s) — pendente até "Aplicar e reconstruir".`, 'ok');
}

document.getElementById('copyNotes')?.addEventListener('click', copySelectedNotes);
document.getElementById('pasteNotes')?.addEventListener('click', pasteNotesAtCursor);

function currentKind() {
  return arrangements[currentArr] ? arrangements[currentArr].kind : null;
}

// Chart time of the current arrangement's very first note — the anchor point
// "Início da música" (Step 1) pins independently per track.
function currentArrFirstNoteTime() {
  const notes = arrangements[currentArr] ? arrangements[currentArr].notes : [];
  return notes.length ? Math.min(...notes.map(n => n.time)) : null;
}

// Refresh Step 1's "Início da música" field/slider for the CURRENT
// arrangement: shows this track's first note's effective landing time (raw
// recording seconds), reflecting any pending per-track anchor — NOT the
// job-level offsetLive directly (though with no anchor yet, on the common
// track whose first note starts at its own timeline's beginning, the two
// coincide). Does not touch offsetLive itself.
function updateSyncOffsetDisplay() {
  const kindEl = document.getElementById('syncOffsetKind');
  if (!kindEl || !isGpJob() || !arrangements.length) return;
  kindEl.textContent = `(${currentKind() || ''})`;
  const chartT = currentArrFirstNoteTime();
  const v = chartT == null ? 0 : buildTimeWarp(syncAnchors)(previewScale(chartT)) - viewOrigin;
  document.getElementById('syncOffset').value = v.toFixed(2);
  document.getElementById('syncOffsetRange').value = Math.max(0, v);
}

// ---- Sync by bar number (for a track whose real content only starts several
// measures in — e.g. Rhythm rests until bar 7). Generalizes the per-track
// "Início" tools (which only pin the very first note) to ANY chosen bar, and
// additionally lets that bar be aligned directly to the SAME bar number of
// another, already-synced arrangement — sound, because bar numbers come from
// one shared song-level measure header in the GP file (parser.py), so bar N is
// the same musical instant across every track before any per-track correction.

// previewScale()/buildTimeWarp(syncAnchors) operate on the CURRENTLY loaded
// arrangement's live globals; these variants read arrangement `idx`'s own
// tempo (live pending, else built) and pending anchors, regardless of which
// tab is on screen — needed to compute "where does the reference track's bar
// N currently sit" without switching tabs.
function arrangementPreviewScale(idx, t) {
  if (!isGpJob()) return t;
  const a = arrangements[idx];
  if (!a) return t;
  const built = a.tempo_scale || 1;
  const live = (a.kind in tempoScaleByKind) ? tempoScaleByKind[a.kind] : built;
  return (t - scoreShift) * (live / built) + Math.max(offsetLive, MIN_LEAD);
}
function arrangementDisplayTime(idx, t) {
  const a = arrangements[idx];
  if (!a) return t;
  return buildTimeWarp(syncAnchorsByKind[a.kind] || [])(arrangementPreviewScale(idx, t));
}
// Raw (server) chart time of a bar's downbeat in arrangement `idx`, or null.
function barChartTime(idx, measure) {
  const a = arrangements[idx];
  const b = a && (a.bars || []).find(x => x.measure === measure);
  return b ? b.time : null;
}

// Refresh the bar-sync panel's selectors for the current tab: every bar of
// THIS arrangement, and every OTHER arrangement as a sync-reference option.
function updateBarSyncPanel() {
  const panel = document.getElementById('barSyncPanel');
  if (!panel) return;
  if (!isGpJob() || !arrangements.length) { panel.style.display = 'none'; return; }
  panel.style.display = '';
  const bars = arrangements[currentArr].bars || [];
  const barSel = document.getElementById('barSyncBar');
  const prevBar = barSel.value;
  barSel.innerHTML = bars.map(b => `<option value="${b.measure}">Compasso ${b.measure}</option>`).join('');
  if (bars.some(b => String(b.measure) === prevBar)) barSel.value = prevBar;

  const others = arrangements.map((a, i) => ({ a, i })).filter(o => o.i !== currentArr);
  document.getElementById('barSyncRefRow').style.display = others.length ? '' : 'none';
  const refSel = document.getElementById('barSyncRefArr');
  const prevRef = refSel.value;
  refSel.innerHTML = others.map(o => `<option value="${o.i}">${esc(o.a.kind)}</option>`).join('');
  if (others.some(o => String(o.i) === prevRef)) refSel.value = prevRef;
}

// Pin a bar's downbeat of the current arrangement to `target` (a bundle-time
// display position) via a single anchor — the shared primitive behind BOTH the
// "Sincronizar por compasso" panel AND the click-a-note bar-align popup. The
// anchor origin is the UNwarped previewScale time (the warp's domain, same as
// 'drag'/setTrackStart). Multiple such pins compose into a piecewise drift
// correction. Returns false if the bar doesn't exist.
function alignBarTo(measure, target) {
  const chartT = barChartTime(currentArr, measure);
  if (chartT == null) return false;
  setAnchor(previewScale(chartT), target);
  renderAnchorsList();
  updatePendingChangesInfo();
  showArr(currentArr);
  return true;
}
// Target display time = another arrangement's SAME bar, at its own live sync.
function refBarTarget(refIdx, measure) {
  const refChartT = barChartTime(refIdx, measure);
  return refChartT == null ? null : arrangementDisplayTime(refIdx, refChartT);
}

(function wireBarSync() {
  const barSel = document.getElementById('barSyncBar');
  const fromCursor = document.getElementById('barSyncFromCursor');
  const refSel = document.getElementById('barSyncRefArr');
  const fromRef = document.getElementById('barSyncFromRef');
  const info = document.getElementById('barSyncInfo');
  if (!fromCursor) return;

  fromCursor.addEventListener('click', () => {
    if (!isGpJob()) return;
    const measure = parseInt(barSel.value, 10);
    if (!alignBarTo(measure, currentPlayheadT + viewOrigin)) { toast('compasso não encontrado', 'err'); return; }
    info.textContent = `Compasso ${measure} alinhado com o cursor (${currentPlayheadT.toFixed(2)}s).`;
    toast(`Compasso ${measure} alinhado com o cursor`, 'ok');
  });

  fromRef.addEventListener('click', () => {
    if (!isGpJob()) return;
    const measure = parseInt(barSel.value, 10);
    const refIdx = parseInt(refSel.value, 10);
    if (isNaN(refIdx) || !arrangements[refIdx]) { toast('escolhe uma pista de referência', 'err'); return; }
    const target = refBarTarget(refIdx, measure);
    if (target == null || !alignBarTo(measure, target)) {
      toast(`compasso ${measure} não existe nas duas pistas`, 'err'); return;
    }
    const refKind = arrangements[refIdx].kind;
    info.textContent = `Compasso ${measure} alinhado com o compasso ${measure} de ${refKind} (${(target - viewOrigin).toFixed(2)}s).`;
    toast(`Compasso ${measure} sincronizado com ${refKind}`, 'ok');
  });
})();

// ---- Click-a-note bar-align popup ('baralign' mode) ----
// A faster entry to alignBarTo for doing MANY corrections: click a note, a
// small floating popup opens with the bar numbers (the note's own bar
// pre-selected); confirm "= cursor" (or "= pista") and that bar snaps to the
// cursor / the reference track, dragging the following notes into place.
function openBarAlignPopup(chartT, clientX, clientY) {
  const a = arrangements[currentArr];
  if (!a || !(a.bars && a.bars.length)) { toast('sem compassos nesta pista', 'err'); return; }
  const pop = document.getElementById('barAlignPopup');
  const barSel = document.getElementById('baBar');
  barSel.innerHTML = a.bars.map(b => `<option value="${b.measure}">Compasso ${b.measure}</option>`).join('');
  const containing = [...a.bars].filter(b => b.time <= chartT + 1e-6).pop();
  if (containing) barSel.value = String(containing.measure);
  const others = arrangements.map((x, i) => ({ x, i })).filter(o => o.i !== currentArr);
  document.getElementById('baRefWrap').style.display = others.length ? '' : 'none';
  document.getElementById('baRefArr').innerHTML =
    others.map(o => `<option value="${o.i}">${esc(o.x.kind)}</option>`).join('');
  pop.hidden = false;
  // Position near the click, clamped to the viewport.
  const w = pop.offsetWidth, h = pop.offsetHeight;
  let x = clientX + 10, y = clientY + 10;
  if (x + w > window.innerWidth - 8) x = clientX - w - 10;
  if (y + h > window.innerHeight - 8) y = window.innerHeight - h - 8;
  pop.style.left = Math.max(8, x) + 'px';
  pop.style.top = Math.max(8, y) + 'px';
}
function closeBarAlignPopup() { document.getElementById('barAlignPopup').hidden = true; }

(function wireBarAlignPopup() {
  const pop = document.getElementById('barAlignPopup');
  if (!pop) return;
  document.getElementById('baCancel').addEventListener('click', closeBarAlignPopup);
  document.getElementById('baToCursor').addEventListener('click', () => {
    const m = parseInt(document.getElementById('baBar').value, 10);
    if (alignBarTo(m, currentPlayheadT + viewOrigin)) {
      toast(`Compasso ${m} alinhado ao cursor`, 'ok');
      closeBarAlignPopup();
    }
  });
  document.getElementById('baToRef').addEventListener('click', () => {
    const m = parseInt(document.getElementById('baBar').value, 10);
    const refIdx = parseInt(document.getElementById('baRefArr').value, 10);
    const target = refBarTarget(refIdx, m);
    if (target == null) { toast(`compasso ${m} não existe nessa pista`, 'err'); return; }
    if (alignBarTo(m, target)) {
      toast(`Compasso ${m} alinhado a ${arrangements[refIdx].kind}`, 'ok');
      closeBarAlignPopup();
    }
  });
  // Dismiss on Escape or a click that's neither the popup nor a note (a note
  // click reopens/repositions it via the SVG handler).
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeBarAlignPopup(); });
  document.addEventListener('pointerdown', e => {
    if (!pop.hidden && !pop.contains(e.target) && !e.target.closest('.note-grp')) closeBarAlignPopup();
  });
})();

// ---- Note editor ('editnotes' mode): add/edit/delete a note + its
// techniques directly on the score, without going back to Guitar Pro. ----
// TECH_CHECK_IDS maps each checkbox to its Technique value string (the same
// strings ArrangementNoteOut already uses for n.techniques).
const TECH_CHECK_IDS = [
  ['neHammerOn', 'hammerOn'], ['nePullOff', 'pullOff'], ['neHarmonic', 'harmonic'],
  ['nePalmMute', 'palmMute'], ['neVibrato', 'vibrato'], ['neTap', 'tap'],
  ['neSlap', 'slap'], ['nePluck', 'pluck'], ['neAccent', 'accent'],
];
let neContext = null;  // { time, string } of the popup currently open, or null

// ---- Note-edit bookkeeping --------------------------------------------------
// The list shown here is BOTH the edits already committed to the job (seeded in
// loadArrangements) and the ones pending in this session — they are the same
// thing to the backend, which stores the whole dict. Clearing is therefore a
// real edit: it takes effect on the next "Aplicar e reconstruir".
function noteEditCounts() {
  const kind = currentKind();
  const mine = (noteOverridesByKind[kind] || []).length;
  let total = 0;
  for (const k of Object.keys(noteOverridesByKind)) total += (noteOverridesByKind[k] || []).length;
  return { mine, total, kind };
}

function updateNoteEditsInfo() {
  const el = document.getElementById('noteEditsInfo');
  const one = document.getElementById('clearNoteEdits');
  const all = document.getElementById('clearNoteEditsAll');
  if (!el || !one || !all) return;
  const { mine, total, kind } = noteEditCounts();
  el.textContent = total
    ? `${mine} nesta pista (${kind}), ${total} no total`
    : 'nenhuma';
  one.disabled = !mine;
  all.disabled = !total;
}

async function clearNoteEdits(everyArrangement) {
  const { mine, total, kind } = noteEditCounts();
  const n = everyArrangement ? total : mine;
  if (!n) return;
  const where = everyArrangement ? 'de todas as pistas' : `da pista ${kind}`;
  if (!await confirmModal(
    `Descartar ${n} edição(ões) de notas ${where}?\n\n` +
    'Inclui as que já foram aplicadas em reconstruções anteriores. ' +
    'As notas voltam ao que está no ficheiro Guitar Pro assim que fizeres ' +
    '"Aplicar e reconstruir".')) return;
  if (everyArrangement) noteOverridesByKind = {};
  else delete noteOverridesByKind[kind];
  updateNoteEditsInfo();
  updatePendingChangesInfo();
  showArr(currentArr);
  toast(`${n} edição(ões) descartada(s) — pendente até "Aplicar e reconstruir".`, 'ok');
}

document.getElementById('clearNoteEdits').addEventListener('click', () => clearNoteEdits(false));
document.getElementById('clearNoteEditsAll').addEventListener('click', () => clearNoteEdits(true));

function findBuiltNoteAt(chartTime, string) {
  const a = arrangements[currentArr];
  if (!a) return null;
  return a.notes.find(n => n.string === string && Math.abs(n.time - chartTime) < 0.03) || null;
}
function findPendingNoteOverrideAt(chartTime, string) {
  const list = noteOverridesByKind[currentKind()] || [];
  return list.find(o => o.string === string && Math.abs(o.time - chartTime) < 0.03 && !o.deleted) || null;
}

function openNoteEditPopup(chartTime, string, clientX, clientY) {
  const a = arrangements[currentArr];
  if (!a) return;
  const pending = findPendingNoteOverrideAt(chartTime, string);
  const existing = findBuiltNoteAt(chartTime, string);
  const base = pending || existing;
  neContext = { time: chartTime, string };

  document.getElementById('nePopupTitle').textContent = base ? 'Editar nota' : 'Nova nota';
  const stringSel = document.getElementById('neString');
  stringSel.innerHTML = [0, 1, 2, 3, 4, 5]
    .map(i => `<option value="${i}">${esc(stringLabel(i, a.tuning_offsets))}</option>`).join('');
  stringSel.value = String(string);
  document.getElementById('neFret').value = base ? base.fret : 0;
  document.getElementById('neSustain').value = base ? base.sustain : 0.25;
  const techs = base ? (base.techniques || []) : [];
  for (const [id, val] of TECH_CHECK_IDS) document.getElementById(id).checked = techs.includes(val);
  document.getElementById('neBend').value = base ? (base.bend_semitones || 0) : 0;
  const slideTo = base ? (base.slide_to_fret ?? null) : null;
  document.getElementById('neSlideTo').value = slideTo == null ? '' : slideTo;
  document.getElementById('neDelete').style.display = base ? '' : 'none';

  const pop = document.getElementById('noteEditPopup');
  pop.hidden = false;
  const w = pop.offsetWidth, h = pop.offsetHeight;
  let x = clientX + 10, y = clientY + 10;
  if (x + w > window.innerWidth - 8) x = clientX - w - 10;
  if (y + h > window.innerHeight - 8) y = window.innerHeight - h - 8;
  pop.style.left = Math.max(8, x) + 'px';
  pop.style.top = Math.max(8, y) + 'px';
}
function closeNoteEditPopup() { document.getElementById('noteEditPopup').hidden = true; neContext = null; }

// Upsert (or push) a pending override for the CURRENT arrangement, keyed by
// (time, string) — matches _apply_note_overrides' merge key on the backend.
function upsertNoteOverride(ov) {
  const k = currentKind();
  if (!k) return;
  if (!noteOverridesByKind[k]) noteOverridesByKind[k] = [];
  const list = noteOverridesByKind[k];
  const i = list.findIndex(o => o.string === ov.string && Math.abs(o.time - ov.time) < 0.03);
  if (i >= 0) list[i] = ov; else list.push(ov);
}

(function wireNoteEditPopup() {
  const pop = document.getElementById('noteEditPopup');
  if (!pop) return;
  document.getElementById('neCancel').addEventListener('click', closeNoteEditPopup);
  document.getElementById('neSave').addEventListener('click', () => {
    if (!neContext) return;
    const string = parseInt(document.getElementById('neString').value, 10);
    const fret = parseInt(document.getElementById('neFret').value, 10);
    if (isNaN(fret) || fret < 0 || fret > 24) { toast('traste inválido (0-24)', 'err'); return; }
    const sustain = Math.max(0, parseFloat(document.getElementById('neSustain').value) || 0);
    const techniques = TECH_CHECK_IDS.filter(([id]) => document.getElementById(id).checked).map(([, v]) => v);
    const bend_semitones = Math.max(0, parseFloat(document.getElementById('neBend').value) || 0);
    const slideRaw = document.getElementById('neSlideTo').value.trim();
    const slide_to_fret = slideRaw === '' ? null : parseInt(slideRaw, 10);
    // Changing the string moves the note: delete the old (time, oldString)
    // slot and upsert the new one, so the merge key stays consistent.
    if (string !== neContext.string) {
      upsertNoteOverride({
        time: neContext.time, string: neContext.string, fret: 0, sustain: 0,
        techniques: [], bend_semitones: 0, slide_to_fret: null, deleted: true,
      });
    }
    upsertNoteOverride({
      time: neContext.time, string, fret, sustain, techniques,
      bend_semitones, slide_to_fret, deleted: false,
    });
    closeNoteEditPopup();
    showArr(currentArr);
    toast('Nota guardada — pendente até "Aplicar e reconstruir".', 'ok');
  });
  document.getElementById('neDelete').addEventListener('click', () => {
    if (!neContext) return;
    upsertNoteOverride({
      time: neContext.time, string: neContext.string, fret: 0, sustain: 0,
      techniques: [], bend_semitones: 0, slide_to_fret: null, deleted: true,
    });
    closeNoteEditPopup();
    showArr(currentArr);
    toast('Nota removida — pendente até "Aplicar e reconstruir".', 'ok');
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeNoteEditPopup(); });
  document.addEventListener('pointerdown', e => {
    if (!pop.hidden && !pop.contains(e.target) && !e.target.closest('#tabsvg')) closeNoteEditPopup();
  });
})();

function renderAnchorsList() {
  const el = document.getElementById('syncAnchorsList');
  if (!syncAnchors.length) { el.innerHTML = ''; updatePendingChangesInfo(); return; }
  // The target time is an editable number (not just text) so a correction can
  // be typed exactly instead of only ever being set by dragging.
  // A correction CROSSES the previous one when a later point in the score is
  // sent to an earlier instant in the recording. The timeline would have to fold
  // back on itself, so the backend refuses to build it — flag it here, while it
  // can still be fixed, instead of failing at "Aplicar e reconstruir".
  el.innerHTML = syncAnchors.map(([o, n], i) => {
    const crosses = i > 0 && n <= syncAnchors[i - 1][1];
    const warn = crosses
      ? ` <span style="color:#e6483c" title="Esta correção manda um ponto MAIS À FRENTE da partitura para um instante ANTERIOR ao da correção acima — impossível de aplicar. Corrige o valor ou remove uma delas.">⚠ cruza a anterior</span>`
      : '';
    return `<div class="anchor-row"${crosses ? ' style="border-left:3px solid #e6483c;padding-left:.4rem"' : ''}>Correção ${i+1}: ${o.toFixed(2)}s →
     <input type="number" step="0.01" value="${n.toFixed(2)}" data-i="${i}" class="anchor-edit" style="width:6rem">s
     <button type="button" data-i="${i}" class="anchor-remove">remover</button>${warn}</div>`;
  }).join('') + `<div class="anchor-row">
     <button type="button" id="clearAnchors" class="secondary">Limpar correções pendentes</button></div>`;
  el.querySelectorAll('.anchor-edit').forEach(inp => inp.addEventListener('change', () => {
    const i = parseInt(inp.dataset.i, 10);
    const v = parseFloat(inp.value);
    if (!isNaN(v)) syncAnchors[i][1] = v;
    renderAnchorsList();  // a typed value can create/clear a crossing — re-flag
    showArr(currentArr);
    updatePendingChangesInfo();
  }));
  el.querySelectorAll('.anchor-remove').forEach(b => b.addEventListener('click', () => {
    syncAnchors.splice(parseInt(b.dataset.i, 10), 1);
    renderAnchorsList();
    showArr(currentArr);  // redraw so the removed correction's marker disappears
    updatePendingChangesInfo();
  }));
  document.getElementById('clearAnchors').addEventListener('click', () => {
    syncAnchors.length = 0; renderAnchorsList(); showArr(currentArr);
  });
}

// The single "Aplicar e reconstruir": commits afinação (shared) + the job-level
// offset_s (frozen since creation; per-track start is a pending anchor, below)
// + the CURRENT arrangement's tempo and pending drift anchors (which include
// any "Início da música" edit for this tab) in one rebuild. Other arrangements
// keep their own already-committed sync untouched.
async function applyAll() {
  if (!selectedJob) return;
  const midi = [...document.querySelectorAll('#tuningInputs input')].map(i => parseInt(i.value, 10));
  const applyToAll = document.getElementById('applyToAllChk').checked;
  const r = await fetch(`/jobs/${selectedJob.id}/rebuild`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tuning_midi: midi.some(isNaN) ? null : midi,
      cent_offset: centOffsetLive,
      split_lead_rhythm: document.getElementById('splitChk').checked,
      offset_s: offsetLive,
      lead_in_s: Math.max(0, parseFloat(document.getElementById('leadInS').value) || 0),
      arrangement: currentKind(),
      tempo_scale: tempoScaleLive,
      sync_anchors: syncAnchors.length ? syncAnchors : null,
      apply_to_all: applyToAll,
      import_mutes: document.getElementById('muteChk').checked,
      dynamic_difficulty: document.getElementById('ddChk').checked,
      lyrics_events: lyricsEvents.length ? serializeLyrics() : null,
      // Send the FULL current tone state for GP jobs (even when empty) so that
      // clearing tones/changes actually persists — null would mean "keep the
      // old value". Non-GP jobs have no tones, so send null to skip the guard.
      tones: isGpJob() ? jobTones : null,
      tone_base: isGpJob() ? (toneBase || '') : null,
      tone_names: isGpJob() ? toneNames : null,
      tone_changes: isGpJob() ? toneChanges : null,
      // Only sent once the user actually touches the section editor — untouched,
      // null leaves each arrangement's own GP-authored sections alone (unlike
      // tones, which never had a prior non-user-supplied default to lose).
      section_overrides: (isGpJob() && sectionsTouched) ? songSections : null,
      // Genuinely per-arrangement (unlike tone_changes/sections) — sent as
      // one dict covering every tab's pending edits from this session, same
      // no-prior-default reasoning as tone_changes (an untouched job sends {}).
      note_overrides: isGpJob() ? noteOverridesByKind : null,
    }),
  });
  const b = await r.json();
  if (r.ok) {
    toast('A reconstruir…', 'ok');
    if (applyToAll) {
      syncAnchorsByKind = {};
      tempoScaleByKind = {};
    } else {
      syncAnchors.length = 0;
      const kind = currentKind();
      if (kind) delete tempoScaleByKind[kind];
    }
    noteOverridesByKind = {};  // baked into the new build regardless of applyToAll
    noteOverridesBuilt = '{}';
    selectJob(b.id, { force: true });
  }
  else toast(b.detail || 'erro');
}
document.getElementById('applyAll').addEventListener('click', applyAll);

// Reload the GP file into the current job (keeping all sync/tone/lyric/tuning
// overrides). Forks a new job on the backend, same as a rebuild.
const reloadGpBtn = document.getElementById('reloadGpBtn');
const reloadGpInput = document.getElementById('reloadGpInput');
reloadGpBtn.addEventListener('click', () => { if (isGpJob()) reloadGpInput.click(); });
reloadGpInput.addEventListener('change', async () => {
  const file = reloadGpInput.files[0];
  if (!file || !selectedJob) return;
  const info = document.getElementById('reloadGpInfo');
  const prev = info.textContent;
  info.textContent = 'A recarregar…';
  reloadGpBtn.disabled = true;
  try {
    const fd = new FormData();
    fd.append('gp', file);
    const r = await fetch(`/jobs/${selectedJob.id}/reload-gp`, { method: 'POST', body: fd });
    const b = await r.json();
    if (r.ok) { toast('GP recarregado — a reconstruir…', 'ok'); selectJob(b.id, { force: true }); }
    else toast(b.detail || 'erro ao recarregar o GP');
  } finally {
    reloadGpInput.value = '';  // allow re-selecting the same filename
    reloadGpBtn.disabled = false;
    info.textContent = prev;
  }
});

// Export / import the hand-tuned sync state as a portable JSON file, so manual
// anchors/tempo/offset/tuning/lyrics/tracks survive re-creating a job.
// Bake the sync corrections back into a COPY of the Guitar Pro file, so the fix
// is permanent in Guitar Pro itself and not only inside RockForge. The bars sent
// are exactly the ones the score draws in amber (retempoedBars → the same
// barTempoTable the drawing uses), so what is shown is what gets written.
//
// Honest limit, surfaced in the UI and again in the result: ONLY tempo is
// exportable. A jump — a constant shift of the whole passage — cannot be
// expressed as a BPM change (it would need a bar inserted or removed), so it
// stays a RockForge-side correction.
// Generate a NEW Guitar Pro file from the built arrangement — the note editor's
// edits and the corrected timeline included. The trade against the tempo-only
// export above (which patches a copy of the user's own file) is that this one
// carries ONE track: the report repeats that every time, not just on failure.
document.getElementById('exportArrGpBtn').addEventListener('click', async () => {
  if (!selectedJob) return;
  const a = arrangements[currentArr];
  if (!a) { toast('abre um arranjo primeiro'); return; }
  const btn = document.getElementById('exportArrGpBtn');
  btn.disabled = true;
  try {
    const b = await getJSON(
      `/jobs/${selectedJob.id}/export-arrangement-gp?arrangement=${encodeURIComponent(a.kind)}`,
      { method: 'POST' });
    const notes = [`<b>${b.notes_written} nota(s)</b> em ${b.measures} compasso(s)`];
    if (b.quantized) notes.push(`${b.quantized} ajustada(s) à grelha (máx ${b.max_shift_ms} ms)`);
    if (b.notes_dropped) notes.push(`${b.notes_dropped} fora dos compassos, não escrita(s)`);
    document.getElementById('exportGpInfo').innerHTML =
      `${notes.join(' — ')} em <code>${esc(b.filename)}</code>. ` +
      esc(b.warnings.join(' '));
    const link = document.createElement('a');
    link.href = `/jobs/${selectedJob.id}/corrected-gp`;
    link.download = b.filename;
    link.click();
    toast(`GP gerado: ${b.notes_written} nota(s).`, 'ok');
  } catch (err) {
    toast(`falha ao gerar o GP: ${err.message}`);
  } finally {
    btn.disabled = false;
  }
});

document.getElementById('exportGpBtn').addEventListener('click', async () => {
  if (!selectedJob) return;
  const a = arrangements[currentArr];
  if (!a) { toast('abre um arranjo primeiro'); return; }
  const bars = retempoedBars(a);
  if (!bars.length) {
    toast('nenhum compasso mudou de andamento — não há nada para escrever no ficheiro GP');
    return;
  }
  // The endpoint bounds BPM to (10, 400); a wild warp can push a bar outside it.
  // Drop those rather than letting the whole export 422, and say how many.
  const writable = bars.filter(b => b.bpm > GP_EXPORT_MIN_BPM && b.bpm < GP_EXPORT_MAX_BPM);
  const dropped = bars.length - writable.length;
  if (!writable.length) {
    toast('os andamentos corrigidos estão fora do intervalo que o Guitar Pro aceita (10-400 BPM)');
    return;
  }
  const btn = document.getElementById('exportGpBtn');
  btn.disabled = true;
  try {
    const b = await getJSON(`/jobs/${selectedJob.id}/export-gp`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ corrections: writable.map(c => ({ measure: c.measure, bpm: c.bpm })) }),
    });
    const rounded = b.applied.filter(x => x.rounded).length;
    const notes = [];
    if (dropped) notes.push(`${dropped} compasso(s) fora de 10-400 BPM ignorado(s)`);
    if (rounded) notes.push(`${rounded} arredondado(s) — este formato guarda o tempo como inteiro`);
    document.getElementById('exportGpInfo').innerHTML =
      `<b>${b.applied.length} compasso(s)</b> escritos em <code>${esc(b.filename)}</code>` +
      (notes.length ? ` — ${esc(notes.join('; '))}` : '') +
      '. Só o <b>tempo</b> é exportável: um desfasamento constante continua a ser uma correção só do RockForge.';
    // Download the copy. Same-origin navigation, so the Basic-auth credentials
    // (when ROCKFORGE_API_TOKEN is set) ride along as on any other link.
    const link = document.createElement('a');
    link.href = `/jobs/${selectedJob.id}/corrected-gp`;
    link.download = b.filename;
    link.click();
    toast(`GP corrigido: ${b.applied.length} compasso(s).`, 'ok');
  } catch (err) {
    toast(`falha ao exportar o GP: ${err.message}`);
  } finally {
    btn.disabled = false;
  }
});

document.getElementById('exportSyncBtn').addEventListener('click', async () => {
  if (!selectedJob) return;
  try {
    const r = await fetch(`/jobs/${selectedJob.id}/sync-state`);
    const b = await r.json();
    if (!r.ok) { toast(b.detail || 'erro ao exportar sync'); return; }
    const name = (b.song || selectedJob.id).replace(/[^\w.-]+/g, '_');
    const blob = new Blob([JSON.stringify(b, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${name}.sync.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    toast('Sync exportado.', 'ok');
  } catch { toast('erro ao exportar sync'); }
});

const importSyncInput = document.getElementById('importSyncInput');
document.getElementById('importSyncBtn').addEventListener('click', () => {
  if (selectedJob) importSyncInput.click();
});
importSyncInput.addEventListener('change', async () => {
  const file = importSyncInput.files[0];
  if (!file || !selectedJob) return;
  try {
    const payload = JSON.parse(await file.text());
    if (!payload || typeof payload.sync !== 'object')
      { toast('ficheiro de sync inválido'); return; }
    const r = await fetch(`/jobs/${selectedJob.id}/import-sync`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const b = await r.json();
    if (r.ok) { toast('Sync importado — a reconstruir…', 'ok'); selectJob(b.id, { force: true }); }
    else toast(b.detail || 'erro ao importar sync');
  } catch { toast('erro ao ler o ficheiro de sync'); }
  finally { importSyncInput.value = ''; }
});

// ============ Tones: gear builder + base/extra/changes ============
async function loadGearCatalogue() {
  if (gearCatalogue) return gearCatalogue;
  try {
    gearCatalogue = await getJSON('/gear-catalogue');
  } catch {
    gearCatalogue = { amps: [], cabinets: [], pedals: [], racks: [], descriptors: {} };
  }
  return gearCatalogue;
}

function descriptorNameToCode(name) {
  const d = (gearCatalogue && gearCatalogue.descriptors) || {};
  return d[name] || null;
}
function descriptorCodeToName(code) {
  const d = (gearCatalogue && gearCatalogue.descriptors) || {};
  for (const [name, c] of Object.entries(d)) if (c === code) return name;
  return code;
}
function gearByKey(list, key) { return (list || []).find(g => g.key === key) || null; }

async function loadTones(id) {
  await loadGearCatalogue();
  previewToneTouched = false;  // new project: let the preview default to the score's tones
  try {
    const t = await getJSON(`/jobs/${id}/tones`);
    jobTones = t.tones || [];
    toneBase = t.tone_base || null;
    toneNames = t.tone_names || [];
    // Kept sorted by time at its two disordering mutation sites (here + the
    // add-marker push below) so the many read paths — including activeToneKeyAt,
    // called once per note in the synth render — don't each re-sort a copy.
    toneChanges = (t.tone_changes || []).slice().sort((a, b) => a.time - b.time);
  } catch {
    jobTones = []; toneBase = null; toneNames = []; toneChanges = [];
  }
  renderTonePanel();
}

function renderTonePanel() {
  const isGp = selectedJob && selectedJob.source_type === 'gp';
  document.getElementById('tonePanel').style.display = selectedJob ? '' : 'none';
  document.getElementById('detectTones').style.display = selectedJob ? '' : 'none';
  document.getElementById('openToneBuilder').style.display = isGp ? '' : 'none';
  if (!selectedJob) return;

  const chips = document.getElementById('toneChips');
  chips.innerHTML = jobTones.length
    ? jobTones.map(t => `<span style="background:#23252e;border:1px solid var(--line);border-radius:999px;padding:.1rem .55rem">${esc(t.name || t.key)}</span>`).join('')
    : '<span class="meta">Nenhum tom definido — clica em "+ Criar / editar tons".</span>';

  const baseSel = document.getElementById('toneBaseSel');
  baseSel.innerHTML = '<option value="">—</option>' +
    jobTones.map(t => `<option value="${esc(t.key)}">${esc(t.name || t.key)}</option>`).join('');
  baseSel.value = toneBase || '';

  const extra = document.getElementById('toneExtraChecks');
  extra.innerHTML = jobTones.length
    ? jobTones.map(t => `<label class="check"><input type="checkbox" class="tone-extra" value="${esc(t.key)}" ${toneNames.includes(t.key) ? 'checked' : ''}> ${esc(t.name || t.key)}</label>`).join('')
    : '<span class="meta">—</span>';

  renderToneChangesList();
  populatePreviewTones();
}

// Keep the "Testar tom" selector in sync with the CREATED tones. Disabled when
// the user hasn't created any tone (nothing to preview). With tones, it offers
// "Seguir partitura" (mirror the tones marked on the score, switching per note)
// plus each individual tone to audition alone. Defaults to following the score
// when tones are marked, unless the user has chosen otherwise.
function populatePreviewTones() {
  const sel = document.getElementById('previewTone');
  if (!sel) return;
  const prev = sel.value;
  const hasTones = jobTones.length > 0;
  let html = '<option value="">Voz simples (sem tom)</option>';
  if (hasTones) {
    html += '<option value="__follow__">Seguir partitura (tons marcados)</option>' +
      jobTones.map(t => `<option value="${esc(t.key)}">${esc(t.name || t.key)}</option>`).join('');
  }
  sel.innerHTML = html;
  sel.disabled = !hasTones;
  sel.title = hasTones ? '' : 'Cria um tom primeiro ("+ Criar / editar tons")';
  const valid = ['', '__follow__', ...jobTones.map(t => t.key)];
  if (previewToneTouched && valid.includes(prev)) {
    sel.value = prev;  // respect the user's explicit choice across tone edits
  } else {
    sel.value = hasTones && (toneBase || toneChanges.length || toneNames.length) ? '__follow__' : '';
  }
  previewToneKey = sel.value;
}

document.getElementById('previewTone').addEventListener('change', async e => {
  previewToneKey = e.target.value;
  previewToneTouched = true;
  // The synthesized audio source bakes the voice in, so re-render it if active.
  if (selectedJob && audioSourceName.startsWith('synth:')) {
    const at = currentPlayheadT, wasPlaying = audioIsPlaying();
    stopPlayback();
    await decodeWaveform(selectedJob.id);
    audioSeek(at);
    if (wasPlaying) audioPlay();
  }
});

document.getElementById('toneBaseSel').addEventListener('change', e => {
  toneBase = e.target.value || null;
  if (arrangements.length) showArr(currentArr);  // refresh the on-score tone markers
});
document.getElementById('toneExtraChecks').addEventListener('change', e => {
  if (!e.target.classList.contains('tone-extra')) return;
  const checked = [...document.querySelectorAll('.tone-extra:checked')].map(c => c.value);
  if (checked.length > 4) { e.target.checked = false; toast('Máximo de 4 tons extra.'); return; }
  toneNames = checked;
  if (arrangements.length) showArr(currentArr);
});

function renderToneChangesList() {
  const el = document.getElementById('toneChangesList');
  if (!toneChanges.length) {
    el.innerHTML = '<span class="meta">Sem mudanças de tom. Ativa o modo "Mudança de tom" e clica numa nota.</span>';
  } else {
    const sorted = toneChanges;  // already time-sorted (see loadTones)
    el.innerHTML = sorted.map((c, i) => {
      const name = (jobTones.find(t => t.key === c.name) || {}).name || c.name;
      return `<div class="anchor-row">↪ ${c.time.toFixed(2)}s → <b>${esc(name)}</b>
        <button type="button" class="tone-change-rm" data-i="${i}">remover</button></div>`;
    }).join('');
    el.querySelectorAll('.tone-change-rm').forEach(b => b.addEventListener('click', () => {
      const target = sorted[parseInt(b.dataset.i, 10)];
      toneChanges = toneChanges.filter(c => c !== target);
      renderToneChangesList();
    }));
  }
  // Keep the on-score tone markers (amber 🎸) in sync with the changes list —
  // adding/removing a change (or deleting/renaming a tone) redraws the score.
  if (arrangements.length) showArr(currentArr);
}

function placeToneChange(chartTime) {
  if (!toneNames.length) { toast('Marca primeiro tons "extra" para poder trocar.'); return; }
  const opts = toneNames.map((k, i) => {
    const n = (jobTones.find(t => t.key === k) || {}).name || k;
    return `${i + 1}) ${n}`;
  }).join('\n');
  const pick = prompt(`Trocar para qual tom?\n${opts}`, '1');
  if (pick === null) return;
  const idx = parseInt(pick, 10) - 1;
  if (isNaN(idx) || idx < 0 || idx >= toneNames.length) { toast('Escolha inválida.'); return; }
  toneChanges.push({ time: chartTime, name: toneNames[idx] });
  toneChanges.sort((a, b) => a.time - b.time);  // keep the sorted invariant (see loadTones)
  renderToneChangesList();
  toast('Mudança de tom adicionada.', 'ok');
}

// ---- Section editor (song structure markers: intro/verso/refrão…) ----
// songSections is shared across every arrangement (like toneChanges) — see
// the state declaration above for why sectionsTouched gates the rebuild send.
function renderSectionsList() {
  const el = document.getElementById('sectionsList');
  if (!el) return;
  if (!songSections.length) {
    el.innerHTML = '<span class="meta">Sem secções. Usa "+ Adicionar no cursor" ou o modo "Secção" (clica numa nota).</span>';
  } else {
    el.innerHTML = songSections.map((s, i) => `<div class="anchor-row">
      <input type="number" step="0.01" value="${s.time.toFixed(2)}" data-section-time="${i}" style="width:6rem">s
      <input type="text" value="${esc(s.name)}" data-section-name="${i}" style="width:10rem">
      <button type="button" class="section-rm" data-i="${i}">remover</button></div>`).join('');
    el.querySelectorAll('[data-section-time]').forEach(inp => inp.addEventListener('change', () => {
      const i = parseInt(inp.dataset.sectionTime, 10);
      const v = parseFloat(inp.value);
      if (!isNaN(v)) songSections[i].time = Math.max(0, v);
      songSections.sort((a, b) => a.time - b.time);
      sectionsTouched = true;
      renderSectionsList();
    }));
    el.querySelectorAll('[data-section-name]').forEach(inp => inp.addEventListener('change', () => {
      const i = parseInt(inp.dataset.sectionName, 10);
      songSections[i].name = inp.value.trim() || 'Secção';
      sectionsTouched = true;
      renderSectionsList();
    }));
    el.querySelectorAll('.section-rm').forEach(b => b.addEventListener('click', () => {
      songSections.splice(parseInt(b.dataset.i, 10), 1);
      sectionsTouched = true;
      renderSectionsList();
    }));
  }
  // Keep the on-score section markers in sync with the list — adding/renaming/
  // removing/redraws the score, same as the tone-change list does.
  if (arrangements.length) showArr(currentArr);
}

function placeSectionMarker(chartTime) {
  const name = prompt('Nome da secção:', 'Nova secção');
  if (name === null) return;
  songSections.push({ time: chartTime, name: name.trim() || 'Secção' });
  songSections.sort((a, b) => a.time - b.time);
  sectionsTouched = true;
  renderSectionsList();
  toast('Secção adicionada.', 'ok');
}

document.getElementById('addSectionAtCursor')?.addEventListener('click', () => {
  if (!arrangements.length) return;
  songSections.push({ time: currentPlayheadT + viewOrigin, name: 'Nova secção' });
  songSections.sort((a, b) => a.time - b.time);
  sectionsTouched = true;
  renderSectionsList();
});

// ---- Tone builder modal ----
function openToneBuilder() {
  if (!selectedJob || selectedJob.source_type !== 'gp') { toast('Tons só se aplicam a projetos Guitar Pro.'); return; }
  loadGearCatalogue().then(() => {
    renderToneListEditor();
    loadToneLibrary();
    document.getElementById('toneEditForm').style.display = 'none';
    document.getElementById('toneEditEmpty').style.display = '';
    editingToneKey = null;
    document.getElementById('toneOverlay').hidden = false;
  });
}
function closeToneBuilder() {
  document.getElementById('toneOverlay').hidden = true;
  renderTonePanel();  // reflect any new/removed tones in the panel
}
document.getElementById('openToneBuilder').addEventListener('click', openToneBuilder);
document.getElementById('toneClose').addEventListener('click', closeToneBuilder);

function renderToneListEditor() {
  const el = document.getElementById('toneListEditor');
  el.innerHTML = jobTones.length
    ? jobTones.map(t => `<button type="button" class="secondary tone-pick ${t.key === editingToneKey ? 'active-mode' : ''}" data-key="${esc(t.key)}" style="text-align:left">${esc(t.name || t.key)}</button>`).join('')
    : '<span class="meta">Ainda sem tons.</span>';
  el.querySelectorAll('.tone-pick').forEach(b =>
    b.addEventListener('click', () => editToneInForm(b.dataset.key)));
}

async function loadToneLibrary() {
  try {
    const r = await fetch('/tone-library');
    toneLibrary = r.ok ? ((await r.json()).tones || []) : [];
  } catch { toneLibrary = []; }
  populateToneLibSelect();
}
function populateToneLibSelect() {
  const sel = document.getElementById('toneLibSelect');
  if (!sel) return;
  const prev = sel.value;
  sel.innerHTML = '<option value="">—</option>' +
    toneLibrary.map(t => `<option value="${esc(t.key)}">${esc(t.name || t.key)}</option>`).join('');
  if (toneLibrary.some(t => t.key === prev)) sel.value = prev;
}
document.getElementById('toneLibLoad').addEventListener('click', () => {
  const key = document.getElementById('toneLibSelect').value;
  const src = toneLibrary.find(t => t.key === key);
  if (!src) { toast('Escolhe um tom da biblioteca.'); return; }
  // Copy into this project. If the key already exists here, suffix it so the
  // load never silently overwrites a tone the user already dialled.
  const tone = JSON.parse(JSON.stringify(src));
  if (jobTones.some(t => t.key === tone.key)) {
    let n = 1, base = tone.key;
    while (jobTones.some(t => t.key === tone.key)) tone.key = `${base}_${++n}`;
  }
  jobTones.push(tone);
  editingToneKey = tone.key;
  editToneInForm(tone.key);
  renderToneListEditor();
  renderTonePanel();
  toast('Tom carregado da biblioteca.', 'ok');
});
document.getElementById('toneLibDelete').addEventListener('click', async () => {
  const key = document.getElementById('toneLibSelect').value;
  if (!key) { toast('Escolhe um tom da biblioteca.'); return; }
  const r = await fetch(`/tone-library/${encodeURIComponent(key)}`, { method: 'DELETE' });
  if (!r.ok) { toast('Não foi possível remover.'); return; }
  toneLibrary = (await r.json()).tones || [];
  populateToneLibSelect();
  toast('Removido da biblioteca.', 'ok');
});
document.getElementById('teSaveLibrary').addEventListener('click', async () => {
  const tone = jobTones.find(t => t.key === editingToneKey);
  if (!tone) { toast('Guarda o tom primeiro (Guardar tom).'); return; }
  const r = await fetch('/tone-library', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(tone),
  });
  if (!r.ok) { toast('Não foi possível guardar na biblioteca.'); return; }
  toneLibrary = (await r.json()).tones || [];
  populateToneLibSelect();
  toast('Guardado na biblioteca.', 'ok');
});

function populateGearSelect(sel, items, selectedKey, placeholder, filter) {
  const q = (filter || '').trim().toLowerCase();
  let list = items || [];
  if (q) list = list.filter(g => `${g.name} ${g.key}`.toLowerCase().includes(q));
  // Always keep the current selection in the list, so filtering never silently
  // drops (and thus changes) the chosen gear.
  if (selectedKey && !list.some(g => g.key === selectedKey)) {
    const cur = (items || []).find(g => g.key === selectedKey);
    if (cur) list = [cur, ...list];
  }
  // Cabinets share one display name across all mic/position variants (e.g.
  // "Marshall1960A" appears ~9×), so show the FULL key (Cab_Marshall1960A_57_Cone)
  // — the exact config name from the tone file — to tell them apart. Other gear
  // (amps/pedals/racks) keep their friendly name.
  const label = g => (g.key.includes('Cab_') ? g.key : g.name);
  sel.innerHTML = (placeholder ? `<option value="">${placeholder}</option>` : '') +
    list.map(g => `<option value="${esc(g.key)}">${esc(label(g))}</option>`).join('');
  if (selectedKey) sel.value = selectedKey;
  if (q && !list.length) sel.innerHTML = '<option value="">— sem resultados —</option>';
}

// Map a knob value to the dial's rotation: min -> -135°, max -> +135° (270° sweep).
function knobAngle(v, min, max) {
  const frac = (max === min) ? 0 : (v - min) / (max - min);
  return -135 + Math.max(0, Math.min(1, frac)) * 270;
}
function renderKnobs(container, gearItem, values) {
  if (!gearItem || !gearItem.knobs || !gearItem.knobs.length) {
    container.innerHTML = ''; container.style.display = 'none'; return;  // no empty faceplate
  }
  container.style.display = '';
  container.innerHTML = gearItem.knobs.map(k => {
    const v = (values && k.key in values) ? values[k.key] : k.default;
    return `<div class="knob" data-min="${k.min}" data-max="${k.max}" data-step="${k.step}" data-default="${k.default}" title="${esc(k.name)} — arrasta para rodar, ou escreve o valor; duplo-clique repõe">
      <div class="knob-dial" style="transform:rotate(${knobAngle(v, k.min, k.max).toFixed(1)}deg)"></div>
      <span class="knob-name">${esc(k.name)}</span>
      <input type="number" class="knob-val" data-knob="${esc(k.key)}" min="${k.min}" max="${k.max}" step="${k.step}" value="${v}">
    </div>`;
  }).join('');
  container.querySelectorAll('.knob').forEach(wireKnob);
}
function wireKnob(knob) {
  const dial = knob.querySelector('.knob-dial');
  const input = knob.querySelector('.knob-val');
  const min = parseFloat(knob.dataset.min), max = parseFloat(knob.dataset.max);
  const step = parseFloat(knob.dataset.step) || 1;
  const spin = () => { dial.style.transform = `rotate(${knobAngle(parseFloat(input.value) || min, min, max).toFixed(1)}deg)`; };
  const decimals = (String(step).split('.')[1] || '').length;
  const apply = raw => {
    let v = Math.max(min, Math.min(max, raw));
    v = Math.round(v / step) * step;                       // snap to the knob's step
    v = Math.max(min, Math.min(max, parseFloat(v.toFixed(4))));
    input.value = decimals ? v.toFixed(decimals) : String(v);
    spin();
  };
  input.addEventListener('input', spin);                    // typing turns the dial
  dial.addEventListener('dblclick', () => apply(parseFloat(knob.dataset.default)));
  dial.addEventListener('pointerdown', e => {
    e.preventDefault();
    dial.setPointerCapture(e.pointerId);
    const startY = e.clientY, startV = parseFloat(input.value) || min;
    const sens = (max - min) / 150;                         // ~150px of drag = full sweep
    const move = ev => apply(startV - (ev.clientY - startY) * sens);
    // pointercancel (tab/window blur mid-drag, a touch gesture the browser
    // cancels) never fires pointerup — without also cleaning up here, `move`
    // stays attached and the NEXT drag stacks another listener on top, so each
    // later turn spins 2x/3x as fast for the same pixel delta.
    const up = () => {
      dial.removeEventListener('pointermove', move);
      dial.removeEventListener('pointerup', up);
      dial.removeEventListener('pointercancel', up);
    };
    dial.addEventListener('pointermove', move);
    dial.addEventListener('pointerup', up);
    dial.addEventListener('pointercancel', up);
  });
}
function readKnobs(container) {
  const out = {};
  container.querySelectorAll('input[data-knob]').forEach(i => { out[i.dataset.knob] = parseFloat(i.value); });
  return out;
}

function gearListFor(category) {
  return category === 'rack' ? gearCatalogue.racks : gearCatalogue.pedals;
}

// Per-gear hand-made knob positions (fractions of the bundled image) so the
// functional knobs sit exactly ON the drawn knobs. `name` matches the catalogue
// knob's display name; coords are pixels in the WxH source image. Only gear
// listed here uses the aligned overlay — everything else uses the generic strip.
// TODO (see TODO.md): map the remaining racks/pedals/amps one by one.
const KNOB_LAYOUTS = {
  'Rack_StudioCompressor': { w: 588, h: 120, knobs: [
    { name: 'Threshold', x: 103, y: 60, r: 13 },  // drawn as "Input"
    { name: 'Attack',    x: 302, y: 35, r: 9 },
    { name: 'Release',   x: 391, y: 60, r: 13 },
    { name: 'Ratio',     x: 479, y: 60, r: 13 },
  ] },
};

function wireAlignedKnob(oknob, input, g) {
  const min = g.min, max = g.max, step = g.step || 1;
  const decimals = (String(step).split('.')[1] || '').length;
  const ptr = oknob.querySelector('.ptr');
  const spin = () => { ptr.style.transform =
    `translateX(-50%) rotate(${knobAngle(parseFloat(input.value) || min, min, max).toFixed(1)}deg)`; };
  const apply = raw => {
    let v = Math.max(min, Math.min(max, raw));
    v = Math.round(v / step) * step;
    v = Math.max(min, Math.min(max, parseFloat(v.toFixed(4))));
    input.value = decimals ? v.toFixed(decimals) : String(v);
    spin();
  };
  spin();
  input.addEventListener('input', spin);
  oknob.addEventListener('dblclick', () => apply(parseFloat(g.default)));
  oknob.addEventListener('pointerdown', e => {
    e.preventDefault();
    oknob.setPointerCapture(e.pointerId);
    const startY = e.clientY, startV = parseFloat(input.value) || min;
    const sens = (max - min) / 150;
    const move = ev => apply(startV - (ev.clientY - startY) * sens);
    // See wireKnob's comment above: pointercancel must also clean up, or an
    // interrupted drag leaves `move` attached and the next drag stacks another.
    const up = () => {
      oknob.removeEventListener('pointermove', move);
      oknob.removeEventListener('pointerup', up);
      oknob.removeEventListener('pointercancel', up);
    };
    oknob.addEventListener('pointermove', move);
    oknob.addEventListener('pointerup', up);
    oknob.addEventListener('pointercancel', up);
  });
}

// Render a gear that HAS a layout: picture with knobs overlaid at the drawn
// positions, value inputs (with data-knob so readKnobs still works) below.
function renderAlignedEffect(panel, gearItem, layout, values) {
  panel.className = 'te-eff-panel gear-aligned';
  const W = layout.w, H = layout.h;
  const byName = {}; (gearItem.knobs || []).forEach(k => { byName[k.name] = k; });
  const matched = layout.knobs.filter(kn => byName[kn.name]);
  let ov = `<div class="rack-overlay"><img class="te-eff-img" src="/gear-image/${encodeURIComponent(gearItem.key)}" alt="">`;
  let vr = '<div class="te-eff-knobs rack-values">';
  matched.forEach((kn, i) => {
    const g = byName[kn.name];
    const v = (values && g.key in values) ? values[g.key] : g.default;
    ov += `<div class="oknob" data-i="${i}" title="${esc(kn.name)} — arrasta ou escreve o valor"
      style="left:${(kn.x / W * 100).toFixed(3)}%;top:${(kn.y / H * 100).toFixed(3)}%;width:${(2 * kn.r / W * 100).toFixed(3)}%">
      <div class="hit"></div><div class="ptr"></div></div>`;
    vr += `<div class="vcell" style="left:${(kn.x / W * 100).toFixed(3)}%">
      <span class="vname">${esc(kn.name)}</span>
      <input type="number" class="knob-val" data-knob="${esc(g.key)}" min="${g.min}" max="${g.max}" step="${g.step}" value="${v}"></div>`;
  });
  panel.innerHTML = ov + '</div>' + vr + '</div>';
  const oknobs = panel.querySelectorAll('.oknob');
  const inputs = panel.querySelectorAll('.rack-values input[data-knob]');
  matched.forEach((kn, i) => wireAlignedKnob(oknobs[i], inputs[i], byName[kn.name]));
}

// Render a gear WITHOUT a layout: the plain generic knob strip (no image).
function renderGenericEffect(panel, gearItem, values) {
  panel.className = 'te-eff-panel';
  panel.innerHTML = '<div class="te-eff-knobs tuninggrid knob-face" style="border-radius:6px"></div>';
  renderKnobs(panel.querySelector('.te-eff-knobs'), gearItem, values);
}

function renderEffectGear(panel, gearItem, values) {
  const layout = gearItem && KNOB_LAYOUTS[gearItem.key];
  if (layout) renderAlignedEffect(panel, gearItem, layout, values);
  else renderGenericEffect(panel, gearItem, values);
}

function addEffectRow(category, gearKey, values) {
  const wrap = document.getElementById('teEffects');
  const row = document.createElement('div');
  row.className = 'te-effect';
  row.style = 'border:1px solid var(--line);border-radius:8px;padding:.4rem .5rem';
  row.innerHTML = `
    <div class="anchor-row" style="flex-wrap:wrap">
      <select class="te-eff-cat">
        <option value="pre">Pré-pedal</option>
        <option value="post">Pós-pedal</option>
        <option value="rack">Rack</option>
      </select>
      <input type="text" class="te-eff-search" placeholder="procurar…" style="min-width:8rem;font-size:.8rem;padding:.22rem .45rem">
      <select class="te-eff-gear" style="min-width:11rem"></select>
      <button type="button" class="icon te-eff-rm">remover</button>
    </div>
    <div class="te-eff-panel"></div>`;
  wrap.appendChild(row);
  const catSel = row.querySelector('.te-eff-cat');
  const gearSel = row.querySelector('.te-eff-gear');
  const searchEl = row.querySelector('.te-eff-search');
  const panelEl = row.querySelector('.te-eff-panel');
  catSel.value = category || 'pre';
  const fillGear = (selKey, vals) => {
    populateGearSelect(gearSel, gearListFor(catSel.value), selKey, null, searchEl.value);
    renderEffectGear(panelEl, gearByKey(gearListFor(catSel.value), gearSel.value), vals);
  };
  fillGear(gearKey, values);
  catSel.addEventListener('change', () => { searchEl.value = ''; fillGear(null, null); });
  searchEl.addEventListener('input', () =>
    populateGearSelect(gearSel, gearListFor(catSel.value), gearSel.value, null, searchEl.value));
  gearSel.addEventListener('change', () =>
    renderEffectGear(panelEl, gearByKey(gearListFor(catSel.value), gearSel.value), null));
  row.querySelector('.te-eff-rm').addEventListener('click', () => row.remove());
}

function blankFormDefaults() {
  document.getElementById('teName').value = '';
  document.getElementById('teVolume').value = '-15';
  document.getElementById('teDescriptors').value = '';
  document.getElementById('teAmpSearch').value = '';
  document.getElementById('teCabSearch').value = '';
  const amps = gearCatalogue.amps, cabs = gearCatalogue.cabinets;
  populateGearSelect(document.getElementById('teAmp'), amps, amps[0] && amps[0].key, null);
  renderKnobs(document.getElementById('teAmpKnobs'), amps[0], null);
  setGearImage('teAmpImg', amps[0] && amps[0].key, 'amp');
  populateGearSelect(document.getElementById('teCab'), cabs, cabs[0] && cabs[0].key, null);
  setGearImage('teCabImg', cabs[0] && cabs[0].key, 'cabinet');
  document.getElementById('teEffects').innerHTML = '';
}

function showEditForm() {
  document.getElementById('toneEditForm').style.display = '';
  document.getElementById('toneEditEmpty').style.display = 'none';
}

function newToneInForm() {
  editingToneKey = null;
  blankFormDefaults();
  showEditForm();
  renderToneListEditor();
}

function editToneInForm(key) {
  const t = jobTones.find(x => x.key === key);
  if (!t) return;
  editingToneKey = key;
  document.getElementById('teName').value = t.name || '';
  document.getElementById('teVolume').value = t.volume != null ? t.volume : -15;
  document.getElementById('teDescriptors').value = (t.descriptors || []).map(descriptorCodeToName).join(', ');
  document.getElementById('teAmpSearch').value = '';
  document.getElementById('teCabSearch').value = '';
  populateGearSelect(document.getElementById('teAmp'), gearCatalogue.amps, t.amp && t.amp.key, null);
  renderKnobs(document.getElementById('teAmpKnobs'), gearByKey(gearCatalogue.amps, t.amp && t.amp.key), t.amp && t.amp.knobs);
  setGearImage('teAmpImg', t.amp && t.amp.key, 'amp');
  populateGearSelect(document.getElementById('teCab'), gearCatalogue.cabinets, t.cabinet && t.cabinet.key, null);
  setGearImage('teCabImg', t.cabinet && t.cabinet.key, 'cabinet');
  const eff = document.getElementById('teEffects');
  eff.innerHTML = '';
  for (const p of (t.pre || [])) if (p) addEffectRow('pre', p.key, p.knobs);
  for (const p of (t.post || [])) if (p) addEffectRow('post', p.key, p.knobs);
  for (const p of (t.racks || [])) if (p) addEffectRow('rack', p.key, p.knobs);
  showEditForm();
  renderToneListEditor();
}

document.getElementById('newTone').addEventListener('click', newToneInForm);

// A brand-neutral SVG placeholder per gear TYPE (our own art), shown when the
// user hasn't supplied their own picture. Purely decorative.
function genericGearSvg(type) {
  const amber = '#ffb454', panel = '#23252e', line = '#3a3d47', grille = '#14151a';
  if (type === 'cabinet') {
    return `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 320 130'>
      <rect x='6' y='6' width='308' height='118' rx='8' fill='${panel}' stroke='${line}'/>
      <rect x='18' y='18' width='284' height='94' rx='5' fill='${grille}' stroke='${line}'/>
      ${[95, 225].map(cx => `<circle cx='${cx}' cy='65' r='38' fill='#1a1c23' stroke='${line}' stroke-width='2'/><circle cx='${cx}' cy='65' r='13' fill='#2a2c35' stroke='${amber}' stroke-width='1.5'/>`).join('')}
    </svg>`;
  }
  if (type === 'pedal' || type === 'rack') {
    return `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 320 130'>
      <rect x='95' y='10' width='130' height='110' rx='10' fill='${panel}' stroke='${line}'/>
      <circle cx='132' cy='44' r='12' fill='#2a2c35' stroke='${amber}' stroke-width='1.5'/>
      <circle cx='188' cy='44' r='12' fill='#2a2c35' stroke='${amber}' stroke-width='1.5'/>
      <circle cx='160' cy='60' r='4' fill='${amber}'/>
      <rect x='112' y='80' width='96' height='30' rx='6' fill='${grille}' stroke='${line}'/>
    </svg>`;
  }
  // Amp faceplate (NO drawn knobs — the real rotary knobs overlay it, so they
  // always match the gear's actual controls). A brushed-metal strip + grille.
  return `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 320 130'>
    <defs><linearGradient id='fp' x1='0' y1='0' x2='0' y2='1'>
      <stop offset='0' stop-color='#3a3d47'/><stop offset='1' stop-color='#22242c'/></linearGradient></defs>
    <rect x='4' y='10' width='312' height='110' rx='10' fill='#1a1c23' stroke='${line}'/>
    <rect x='12' y='18' width='296' height='94' rx='6' fill='url(#fp)' stroke='${line}'/>
    <rect x='222' y='26' width='78' height='78' rx='5' fill='${grille}' stroke='${line}'/>
    <rect x='24' y='26' width='150' height='16' rx='3' fill='#101116' stroke='${line}'/>
    <text x='99' y='38' fill='${amber}' font-family='sans-serif' font-size='10' text-anchor='middle' opacity='.7' letter-spacing='3'>AMPLIFIER</text>
  </svg>`;
}
// Show a gear picture (work_dir/gear_images/<key> or the bundled web/gear_images)
// if one exists. A REAL photo carries its own drawn knobs, so the panel switches
// to the stacked "picture above, functional knobs below" layout (`.gear-photo`)
// to avoid doubling them; the generic knob-less SVG faceplate keeps the overlay.
// `photoOnly` (effects): with no real image, show NOTHING (the generic pedal SVG
// HAS drawn knobs, so it must not back the knob strip) — keep the plain strip.
function applyGearImageEl(img, key, type, photoOnly) {
  if (!img) return;
  const panel = img.closest('.gear-panel, .te-eff-panel');
  const setPhoto = on => { if (panel) panel.classList.toggle('gear-photo', on); };
  img.onload = () => { img.style.display = ''; setPhoto(img.dataset.real === '1'); };
  img.onerror = () => {
    img.onerror = null; img.dataset.real = '0'; setPhoto(false);
    if (photoOnly) { img.removeAttribute('src'); img.style.display = 'none'; }
    else img.src = 'data:image/svg+xml,' + encodeURIComponent(genericGearSvg(type));
  };
  if (photoOnly && !key) {                         // no gear picked → show nothing
    img.onerror = null; img.dataset.real = '0'; setPhoto(false);
    img.removeAttribute('src'); img.style.display = 'none'; return;
  }
  img.dataset.real = key ? '1' : '0';
  img.src = key ? '/gear-image/' + encodeURIComponent(key)
                : 'data:image/svg+xml,' + encodeURIComponent(genericGearSvg(type));
}
function setGearImage(imgId, key, type) {
  applyGearImageEl(document.getElementById(imgId), key, type, false);
}
document.getElementById('teAmp').addEventListener('change', e => {
  renderKnobs(document.getElementById('teAmpKnobs'), gearByKey(gearCatalogue.amps, e.target.value), null);
  setGearImage('teAmpImg', e.target.value, 'amp');
});
document.getElementById('teCab').addEventListener('change', e => setGearImage('teCabImg', e.target.value, 'cabinet'));
// Search bars filter the amp / cabinet lists (keeping the current pick visible).
document.getElementById('teAmpSearch').addEventListener('input', e => {
  if (!gearCatalogue) return;
  const sel = document.getElementById('teAmp');
  populateGearSelect(sel, gearCatalogue.amps, sel.value, null, e.target.value);
  setGearImage('teAmpImg', sel.value, 'amp');
});
document.getElementById('teCabSearch').addEventListener('input', e => {
  if (!gearCatalogue) return;
  const sel = document.getElementById('teCab');
  populateGearSelect(sel, gearCatalogue.cabinets, sel.value, null, e.target.value);
  setGearImage('teCabImg', sel.value, 'cabinet');
});
document.getElementById('teAddEffect').addEventListener('click', () => addEffectRow('pre', null, null));

function slugify(s) {
  return (s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'tom';
}

document.getElementById('teSave').addEventListener('click', () => {
  const name = document.getElementById('teName').value.trim();
  if (!name) { toast('Dá um nome ao tom.'); return; }
  const ampKey = document.getElementById('teAmp').value;
  const cabKey = document.getElementById('teCab').value;
  if (!ampKey || !cabKey) { toast('Escolhe amplificador e cabine.'); return; }

  const descriptors = document.getElementById('teDescriptors').value
    .split(',').map(s => s.trim()).filter(Boolean)
    .map(descriptorNameToCode).filter(Boolean);

  const pre = [], post = [], racks = [];
  document.querySelectorAll('#teEffects .te-effect').forEach(row => {
    const cat = row.querySelector('.te-eff-cat').value;
    const gearSel = row.querySelector('.te-eff-gear');
    if (!gearSel.value) return;
    const pedal = { key: gearSel.value, knobs: readKnobs(row.querySelector('.te-eff-knobs')) };
    (cat === 'rack' ? racks : cat === 'post' ? post : pre).push(pedal);
  });

  let key = editingToneKey;
  if (!key) {
    key = slugify(name);
    let n = 1, base = key;
    while (jobTones.some(t => t.key === key)) key = `${base}_${++n}`;
  }
  const tone = {
    key, name,
    volume: parseFloat(document.getElementById('teVolume').value) || -15,
    descriptors,
    amp: { key: ampKey, knobs: readKnobs(document.getElementById('teAmpKnobs')) },
    cabinet: { key: cabKey, knobs: {} },
    pre, post, racks,
  };
  const i = jobTones.findIndex(t => t.key === key);
  if (i >= 0) jobTones[i] = tone; else jobTones.push(tone);
  editingToneKey = key;
  renderToneListEditor();
  renderTonePanel();
  toast('Tom guardado.', 'ok');
});

document.getElementById('teDelete').addEventListener('click', () => {
  if (!editingToneKey) { document.getElementById('toneEditForm').style.display = 'none'; document.getElementById('toneEditEmpty').style.display = ''; return; }
  jobTones = jobTones.filter(t => t.key !== editingToneKey);
  if (toneBase === editingToneKey) toneBase = null;
  toneNames = toneNames.filter(k => k !== editingToneKey);
  toneChanges = toneChanges.filter(c => c.name !== editingToneKey);
  editingToneKey = null;
  document.getElementById('toneEditForm').style.display = 'none';
  document.getElementById('toneEditEmpty').style.display = '';
  renderToneListEditor();
  renderTonePanel();
  toast('Tom removido.', 'ok');
});

// ---- Lyrics editor ----
function renderLyricsRows() {
  document.getElementById('lyricsSyncRow').hidden = !lyricsEvents.length;
  const tb = document.getElementById('lyricsRows');
  tb.innerHTML = lyricsEvents.map((e, i) => `
    <tr data-i="${i}">
      <td><input type="number" step="0.01" min="0" value="${e.time.toFixed(2)}" class="ly-time" style="width:5.5rem"></td>
      <td><input type="text" value="${esc(e.lyric)}" class="ly-text" style="width:100%"></td>
      <td style="text-align:center"><input type="checkbox" class="ly-break" ${e.lineBreak ? 'checked' : ''}></td>
      <td><input type="number" step="0.01" min="0.1" value="${e.length.toFixed(2)}" class="ly-length" style="width:5rem"></td>
      <td><button type="button" class="icon ly-remove" title="Remover" aria-label="Remover">${icon('x')}</button></td>
    </tr>`).join('');
  tb.querySelectorAll('tr').forEach(tr => {
    const i = parseInt(tr.dataset.i, 10);
    const redraw = () => { if (arrangements.length) showArr(currentArr); };
    tr.querySelector('.ly-time').addEventListener('change', e => { lyricsEvents[i].time = parseFloat(e.target.value) || 0; redraw(); });
    // 'change' only (fires on blur/Enter) — an 'input' handler here rebuilt the
    // WHOLE score SVG on every keystroke, which froze typing on a long song.
    tr.querySelector('.ly-text').addEventListener('change', e => { lyricsEvents[i].lyric = e.target.value; redraw(); });
    tr.querySelector('.ly-break').addEventListener('change', e => { lyricsEvents[i].lineBreak = e.target.checked; redraw(); });
    tr.querySelector('.ly-length').addEventListener('change', e => { lyricsEvents[i].length = Math.max(0.1, parseFloat(e.target.value) || 0.1); redraw(); });
    tr.querySelector('.ly-remove').addEventListener('click', () => { lyricsEvents.splice(i, 1); renderLyricsRows(); redraw(); });
  });
}

function eventsToRows(events) {
  return events.map(e => {
    const lineBreak = e.lyric.endsWith('+');
    return { time: e.time, length: e.length, lyric: lineBreak ? e.lyric.slice(0, -1) : e.lyric, lineBreak };
  });
}

function serializeLyrics() {
  return lyricsEvents
    .filter(e => e.lyric.trim())
    .map(e => ({ time: e.time, length: e.length, lyric: e.lineBreak ? `${e.lyric}+` : e.lyric }));
}

const LYRICS_STATUS_LABEL = {
  none: '', detecting: 'a iniciar (a carregar modelos ML)…', normalizing: 'a normalizar áudio…',
  separating: 'a isolar a voz (Demucs) — pode demorar vários minutos…',
  transcribing: 'a transcrever (WhisperX)…',
  aligning: 'a sincronizar a letra com a gravação (WhisperX)…',
  ready: 'deteção concluída', empty: 'nenhuma letra detetada',
  unavailable: 'deteção indisponível (extra "lyrics" não instalado)',
};
// Stage start/end percentages and expected duration (ms) for smooth interpolation.
const LYRICS_STAGES = {
  detecting:    { start: 0.02, end: 0.08, dur: 60000 },
  normalizing:  { start: 0.08, end: 0.15, dur: 30000 },
  separating:   { start: 0.15, end: 0.80, dur: 300000 },
  transcribing: { start: 0.80, end: 0.98, dur: 90000 },
  aligning:     { start: 0.80, end: 0.98, dur: 60000 },
};
const LYRICS_DETECTING_STATUSES = new Set(['detecting', 'normalizing', 'separating', 'transcribing', 'aligning']);

// How long (ms) each stage is allowed before we flag it as stuck.
const LYRICS_STUCK_MS = { detecting: 5*60*1000, normalizing: 10*60*1000, separating: 30*60*1000, transcribing: 15*60*1000, aligning: 15*60*1000 };
let _lyricsLastStatus = null, _lyricsStatusSince = 0;

function updateLyricsProgress(status, log, forceStuck) {
  const wrap = document.getElementById('lyricsProgressWrap');
  const bar  = document.getElementById('lyricsProgressBar');
  const pct  = document.getElementById('lyricsProgressPct');
  const logEl = document.getElementById('lyricsLog');

  if (status !== _lyricsLastStatus) { _lyricsLastStatus = status; _lyricsStatusSince = Date.now(); }

  const isActive = LYRICS_DETECTING_STATUSES.has(status);
  const elapsed  = Date.now() - _lyricsStatusSince;
  const stuck    = forceStuck || (isActive && elapsed > (LYRICS_STUCK_MS[status] || 8*60*1000));

  if (status in LYRICS_STAGES) {
    wrap.style.display = '';
    const stage = LYRICS_STAGES[status];
    const t = Math.min(elapsed / stage.dur, 1);
    const eased = t < 1 ? t * (2 - t) : 1;
    const frac = stage.start + (stage.end - stage.start) * eased;
    const pctVal = Math.round(frac * 100);
    bar.style.width = `${pctVal}%`;
    pct.textContent  = `${pctVal}%`;
    bar.className    = stuck ? 'stuck' : (isActive ? 'active' : '');
  } else {
    wrap.style.display = 'none';
    bar.style.width = '0%';
    pct.textContent = '';
    bar.className = '';
  }
  if (log && log.length) {
    logEl.textContent = log.join('\n');
    logEl.scrollTop = logEl.scrollHeight;
  } else if (status === 'detecting') {
    logEl.textContent = 'a aguardar o worker…';
  } else {
    logEl.textContent = '';
  }
}

async function loadLyrics(id) {
  const r = await fetch(`/jobs/${id}/lyrics`);
  if (!r.ok) return;
  const body = await r.json();
  lyricsEvents = eventsToRows(body.events);
  renderLyricsRows();
  document.getElementById('lyricsInfo').textContent = LYRICS_STATUS_LABEL[body.status] || '';
  updateLyricsProgress(body.status, body.log);
  clearInterval(lyricsPollTimer);
  if (LYRICS_DETECTING_STATUSES.has(body.status)) {
    const startedAt = Date.now();
    lyricsPollTimer = setInterval(async () => {
      if (!selectedJob) { clearInterval(lyricsPollTimer); return; }
      const rr = await fetch(`/jobs/${selectedJob.id}/lyrics`);
      if (!rr.ok) return;
      const b = await rr.json();
      let label = LYRICS_STATUS_LABEL[b.status] || '';
      const elapsed = Date.now() - _lyricsStatusSince;
      const stuckMs = LYRICS_STUCK_MS[b.status] || 8*60*1000;
      const isStuck = LYRICS_DETECTING_STATUSES.has(b.status) && elapsed > stuckMs;
      if (b.status === 'detecting' && !b.log.length && Date.now() - startedAt > 30000)
        label += ' — sem resposta do worker há mais de 30s; verifica logs/worker.log';
      if (isStuck)
        label += ` — sem progresso há ${Math.round(elapsed/60000)} min; verifica logs/worker.log`;
      document.getElementById('lyricsInfo').textContent = label;
      updateLyricsProgress(b.status, b.log, isStuck);
      if (!LYRICS_DETECTING_STATUSES.has(b.status)) {
        clearInterval(lyricsPollTimer);
        lyricsEvents = eventsToRows(b.events);
        // A failed alignment must not cost the lyrics it was aligning: they
        // may exist only in the editor (loaded from LRCLIB, not yet rebuilt).
        if (lyricsBeforeAlign && b.status !== 'ready') {
          lyricsEvents = lyricsBeforeAlign;
          toast('A sincronização não correu — a letra ficou como estava. Vê o registo acima.');
        }
        lyricsBeforeAlign = null;
        renderLyricsRows();
      }
    }, 3000);
  }
}

async function detectLyrics() {
  if (!selectedJob) return;
  const r = await fetch(`/jobs/${selectedJob.id}/detect-lyrics`, { method: 'POST' });
  const b = await r.json();
  if (!r.ok) { toast(b.detail || 'erro'); return; }
  toast('A detetar letra… (pode demorar)', 'ok');
  await loadLyrics(selectedJob.id);
}
document.getElementById('detectLyrics').addEventListener('click', detectLyrics);

// ── Lyrics found online (LRCLIB) + synchronising them to the recording ───────
// Found → CHOSEN → placed. An entry with timestamps goes straight into the
// editor (its times are those of the release it was made from); the tools
// below then line it up with THIS recording: shift it, or have WhisperX
// measure every word on the vocals (/detect-lyrics with align_lines).
let lyricsCandidates = [];
let lyricsBeforeAlign = null;  // the editor's rows while an alignment runs
const redrawScore = () => { if (arrangements.length) showArr(currentArr); };

const fmtMinSec = s => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;

// Plain lyrics (no timing) as alignment lines.
const plainLines = text => text.split(/\r?\n/).map(t => t.trim()).filter(Boolean)
  .map(t => ({ time: null, text: t }));

// The editor's words regrouped into the lines they end ("+"), each at the time
// of its first word — what alignment needs to know where to look.
function editorLines() {
  const lines = [];
  let cur = null;
  for (const e of [...lyricsEvents].sort((a, b) => a.time - b.time)) {
    const w = e.lyric.trim();
    if (!w) continue;
    if (!cur) cur = { time: e.time, text: '' };
    cur.text += w.endsWith('-') ? w.slice(0, -1) : (cur.text && !cur.joinNext ? ` ${w}` : w);
    cur.joinNext = w.endsWith('-');
    if (e.lineBreak) { lines.push({ time: cur.time, text: cur.text }); cur = null; }
  }
  if (cur) lines.push({ time: cur.time, text: cur.text });
  return lines;
}

function renderLyricsCandidates() {
  const el = document.getElementById('lyricsResults');
  el.replaceChildren();
  for (const c of lyricsCandidates) {
    const card = document.createElement('div');
    card.className = 'lyr-card';
    const body = document.createElement('div');
    body.className = 'lyr-body';
    const title = document.createElement('b');
    title.textContent = `${c.track} — ${c.artist}`;
    const meta = document.createElement('span');
    meta.className = 'lyr-meta';
    const badge = document.createElement('span');
    badge.className = 'lyr-badge ' + (c.synced ? 'synced' : 'plain');
    badge.textContent = c.instrumental ? 'instrumental' : c.synced ? 'sincronizada' : 'só texto';
    let len = '';
    if (c.duration) {
      len = fmtMinSec(c.duration);
      if (waveDuration) {
        const gap = waveDuration - c.duration;
        len += Math.abs(gap) < 2 ? ' (igual à tua gravação)'
          : ` (a tua gravação: ${fmtMinSec(waveDuration)}, ${gap > 0 ? '+' : '−'}${Math.round(Math.abs(gap))} s)`;
      }
    }
    meta.append(badge, [c.album, len].filter(Boolean).join(' · '));
    const preview = document.createElement('span');
    preview.className = 'lyr-preview';
    preview.textContent = (c.plain || '').split('\n').filter(Boolean).slice(0, 2).join('\n');
    body.append(title, meta, preview);
    const acts = document.createElement('div');
    acts.className = 'lyr-acts';
    const btn = (label, fn) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'secondary'; b.textContent = label;
      b.addEventListener('click', fn);
      acts.append(b);
    };
    if (c.synced) btn('Usar', () => useLyricsCandidate(c));
    else if (c.plain) btn('Sincronizar com a gravação', () => alignLyrics(plainLines(c.plain), 'só texto'));
    card.append(body, acts);
    el.append(card);
  }
}

document.getElementById('lyricsSearch').addEventListener('click', async () => {
  if (!selectedJob) return;
  const info = document.getElementById('lyricsSearchInfo');
  const btn = document.getElementById('lyricsSearch');
  btn.disabled = true;
  info.textContent = 'A procurar…';
  try {
    const q = `title=${encodeURIComponent(selectedJob.title || '')}&artist=${encodeURIComponent(selectedJob.artist || '')}`
      + (waveDuration ? `&duration=${waveDuration.toFixed(1)}` : '');
    const r = await getJSON(`/lyrics-lookup?${q}`);
    lyricsCandidates = r.candidates || [];
    info.textContent = lyricsCandidates.length
      ? `${lyricsCandidates.length} resultado(s) no LRCLIB — escolhe a versão da tua gravação.`
      : `Nada encontrado no LRCLIB para "${r.searched_title}" de ${r.searched_artist}. `
        + 'Remixes de fãs e músicas feitas por IA raramente lá estão — usa "Detetar letra" ou escreve-a no editor.';
  } catch (err) {
    lyricsCandidates = [];
    info.textContent = `Não consegui procurar agora (${err.message}).`;
  } finally {
    btn.disabled = false;
  }
  renderLyricsCandidates();
});

async function useLyricsCandidate(c) {
  if (lyricsEvents.length && !(await confirmModal('Substituir a letra que está no editor por esta?'))) return;
  try {
    const r = await getJSON('/lyrics/parse', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: c.synced, offset_s: 0 }),
    });
    lyricsEvents = eventsToRows(r.events);
  } catch (err) {
    toast(`Não foi possível usar esta letra: ${err.message}`);
    return;
  }
  renderLyricsRows();
  redrawScore();
  document.getElementById('lyricsSearchInfo').textContent =
    'Letra carregada com os tempos do LRCLIB. Ouve-a na partitura: se estiver adiantada ou atrasada, '
    + 'usa "1ª palavra = cursor"; se sair do tempo a meio, "Sincronizar com a gravação".';
  toast('Letra carregada — "Aplicar e reconstruir" para a incluir.', 'ok');
}

function shiftLyrics(delta) {
  if (!lyricsEvents.length || !Number.isFinite(delta) || !delta) return;
  const first = Math.min(...lyricsEvents.map(e => e.time));
  const d = Math.max(delta, -first);  // never before the recording starts
  for (const e of lyricsEvents) e.time = Math.round((e.time + d) * 1000) / 1000;
  renderLyricsRows();
  redrawScore();
}
document.getElementById('lyricsFirstToCursor').addEventListener('click', () => {
  if (!lyricsEvents.length) return;
  // Same clock as "+ palavra": the playhead minus the built lead-in.
  const target = Math.max(0, currentPlayheadT - leadInBuilt);
  shiftLyrics(target - Math.min(...lyricsEvents.map(e => e.time)));
});
const lyricsStep = () => Math.abs(parseFloat(document.getElementById('lyricsShift').value) || 0.5);
document.getElementById('lyricsShiftBack').addEventListener('click', () => shiftLyrics(-lyricsStep()));
document.getElementById('lyricsShiftFwd').addEventListener('click', () => shiftLyrics(lyricsStep()));

async function alignLyrics(lines, what) {
  if (!selectedJob || !lines.length) return;
  const msg = what === 'só texto'
    ? 'Esta letra não tem tempos: o WhisperX vai procurar cada palavra na voz da música inteira (alguns minutos, precisa dos extras ML). Continuar?'
    : 'O WhisperX vai medir na gravação o tempo de cada palavra desta letra (alguns minutos, precisa dos extras ML). Substitui os tempos atuais. Continuar?';
  if (!(await confirmModal(msg))) return;
  try {
    await getJSON(`/jobs/${selectedJob.id}/detect-lyrics`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ align_lines: lines }),
    });
  } catch (err) {
    toast(`Não foi possível sincronizar: ${err.message}`);
    return;
  }
  toast('A sincronizar a letra com a gravação… (pode demorar)', 'ok');
  lyricsBeforeAlign = lyricsEvents.map(e => ({ ...e }));
  await loadLyrics(selectedJob.id);
}
document.getElementById('lyricsAlign').addEventListener('click', () => alignLyrics(editorLines(), 'editor'));

// ── Tone detection ───────────────────────────────────────────────────────────

async function detectTones() {
  if (!selectedJob) return;
  const r = await fetch(`/jobs/${selectedJob.id}/detect-tones`, { method: 'POST' });
  const b = await r.json();
  if (!r.ok) { toast(b.detail || 'erro'); return; }
  toast('A detetar tom… (pode demorar)', 'ok');
  document.getElementById('toneDetectionWrap').style.display = '';
  document.getElementById('toneDetectionLog').textContent = 'a iniciar…';
  document.getElementById('toneDetectionResult').innerHTML = '';
  pollToneDetection();
}

let _toneDetectionPoll = null;
function pollToneDetection() {
  if (_toneDetectionPoll) clearInterval(_toneDetectionPoll);
  _toneDetectionPoll = setInterval(async () => {
    if (!selectedJob) return;
    const r = await fetch(`/jobs/${selectedJob.id}/detected-tones`);
    if (!r.ok) return;
    const d = await r.json();
    document.getElementById('toneDetectionLog').textContent = (d.log || []).join('\n');
    if (d.status === 'ready') {
      clearInterval(_toneDetectionPoll);
      _toneDetectionPoll = null;
      renderToneDetectionResult(d);
    } else if (d.status === 'unavailable') {
      clearInterval(_toneDetectionPoll);
      _toneDetectionPoll = null;
      document.getElementById('toneDetectionResult').innerHTML =
        '<span class="meta" style="color:#e88">Deteção falhou — vê o log acima.</span>';
    }
  }, 3000);
}

// Keeps the last detection payload so per-candidate "usar" buttons can look up
// a tone dict by its key (the ranked candidate lists live here).
let _lastToneDetection = null;

function _profileBar(label, value) {
  const pct = Math.round((Number(value) || 0) * 100);
  return `<div class="tone-prof-row"><span>${esc(label)}</span>` +
    `<span class="tone-prof-track"><span class="tone-prof-fill" style="width:${pct}%"></span></span>` +
    `<span class="tone-prof-val">${pct}%</span></div>`;
}

function _candidateList(role, candidates) {
  if (!candidates || !candidates.length) return '';
  const rows = candidates.map(c => {
    const m = Math.round(Number(c.match) || 0);
    return `<div class="tone-cand"><span class="tone-cand-name">${esc(c.name || c.key)}</span>` +
      `<span class="tone-cand-match" title="Semelhança estimada com o gravado">${m}%</span>` +
      `<button type="button" class="secondary tone-cand-use" data-role="${esc(role)}" data-key="${esc(c.key)}">usar</button></div>`;
  }).join('');
  const title = role === 'lead' ? 'Lead — tons semelhantes' : 'Rhythm — tons semelhantes';
  return `<div class="tone-cand-group"><div class="meta" style="margin:.4rem 0 .2rem">${esc(title)} ` +
    `<span class="meta">(ordenados por semelhança)</span></div>${rows}</div>`;
}

function renderToneDetectionResult(d) {
  _lastToneDetection = d;
  const cat = d.category || '?';
  const catLabel = { clean: 'Limpo (Clean)', crunch: 'Crunch', high_gain: 'Distorcido (High Gain)' }[cat] || cat;
  const p = d.profile || {};
  let profileHtml = '';
  if (p && (p.gain_level !== undefined)) {
    profileHtml = `<div class="tone-prof" style="margin-top:.4rem">` +
      _profileBar('Ganho/distorção', p.gain_level) +
      _profileBar('Brilho', p.brightness) +
      _profileBar('Graves', p.low_end) +
      `</div>`;
  }
  const el = document.getElementById('toneDetectionResult');
  el.innerHTML =
    `<div style="margin-top:.3rem"><strong>Categoria detetada:</strong> ${esc(catLabel)}</div>` +
    profileHtml +
    `<div class="anchor-row" style="margin-top:.4rem">` +
    `<button type="button" id="applyDetectedTones" class="secondary">Aplicar melhores (Lead + Rhythm)</button></div>` +
    `<div class="meta" style="margin-top:.3rem">Não encontraste o tom certo? Experimenta os semelhantes abaixo — cada um dá a sua % de semelhança com o gravado.</div>` +
    _candidateList('lead', d.lead_candidates) +
    _candidateList('rhythm', d.rhythm_candidates);
  document.getElementById('applyDetectedTones').addEventListener('click', () => applyDetectedTones(d));
  el.querySelectorAll('.tone-cand-use').forEach(btn => {
    btn.addEventListener('click', () => applyOneTone(btn.dataset.role, btn.dataset.key));
  });
}

// Look up a candidate tone dict by role + key in the last detection payload.
function _findCandidate(role, key) {
  const list = (role === 'lead' ? _lastToneDetection.lead_candidates : _lastToneDetection.rhythm_candidates) || [];
  return list.find(c => c.key === key) || null;
}

// Apply one candidate for a role, replacing only that role's RF-detected tone
// (so picking a different Lead doesn't wipe the Rhythm the user already chose).
function applyOneTone(role, key) {
  if (!_lastToneDetection) return;
  const tone = _findCandidate(role, key);
  if (!tone) { toast('Tom não encontrado.'); return; }
  const prefix = role === 'lead' ? 'RFLead_' : 'RFRhythm_';
  jobTones = jobTones.filter(t => !t.key.startsWith(prefix));
  jobTones.push(tone);
  if (role === 'lead') toneBase = tone.key;
  toneNames = jobTones.map(t => t.key);
  renderTonePanel();
  toast(`Tom "${tone.name || tone.key}" aplicado — "Aplicar e reconstruir" para gravar.`, 'ok');
}

function applyDetectedTones(detected) {
  if (!detected.lead || !detected.rhythm) { toast('Sem tons detetados.'); return; }
  const lead = detected.lead;
  const rhythm = detected.rhythm;
  // Merge into current tones, replacing any existing RF-detected ones.
  jobTones = jobTones.filter(t => !t.key.startsWith('RF'));
  jobTones.push(lead, rhythm);
  toneBase = lead.key;
  toneNames = [lead.key, rhythm.key];
  renderTonePanel();
  toast('Tons sugeridos aplicados — "Aplicar e reconstruir" para gravar.', 'ok');
}

document.getElementById('detectTones').addEventListener('click', detectTones);

// ── Stem separation (selectable audio source for fine-tuning) ─────────────────

const STEM_LABELS = {
  guitar: 'Guitarra', bass: 'Baixo',
  vocals: 'Voz', piano: 'Piano', other: 'Outros',
};

let availableStems = [];  // Demucs stem names present on disk (drums excluded)

// Rebuild the "Fonte de áudio" <select> from three groups: the full mix, a
// synthesized clean reference per arrangement (Lead/Rhythm/Combined — needs no
// Demucs), and any separated recording stems. Keeps the current pick if it
// still exists, else falls back to the full mix.
function populateAudioSources() {
  const sel = document.getElementById('audioSource');
  if (!sel) return;
  const prev = sel.value;
  const values = [''];
  let html = '<option value="">Mistura completa</option>';
  for (const a of arrangements) {
    const v = `synth:${a.kind}`;
    values.push(v);
    html += `<option value="${esc(v)}">${esc(a.kind)} (sintetizada)</option>`;
  }
  for (const name of availableStems) {
    values.push(name);
    html += `<option value="${esc(name)}">${esc(STEM_LABELS[name] || name)}</option>`;
  }
  sel.innerHTML = html;
  sel.value = values.includes(prev) ? prev : '';
  audioSourceName = sel.value;
}

async function separateStems() {
  if (!selectedJob) return;
  const r = await fetch(`/jobs/${selectedJob.id}/separate-stems`, { method: 'POST' });
  const b = await r.json();
  if (!r.ok) { toast(b.detail || 'erro'); return; }
  toast('A separar instrumentos… (pode demorar minutos)', 'ok');
  document.getElementById('stemsStatus').textContent = 'a iniciar…';
  pollStems();
}

let _stemsPoll = null;
function pollStems() {
  if (_stemsPoll) clearInterval(_stemsPoll);
  _stemsPoll = setInterval(async () => {
    if (!selectedJob) return;
    const r = await fetch(`/jobs/${selectedJob.id}/stems`);
    if (!r.ok) return;
    const d = await r.json();
    const st = document.getElementById('stemsStatus');
    if (d.status === 'ready') {
      clearInterval(_stemsPoll); _stemsPoll = null;
      availableStems = d.stems || [];
      populateAudioSources();
      st.textContent = `${availableStems.length} stems prontos (a guitarra é todas as guitarras juntas)`;
    } else if (d.status === 'unavailable') {
      clearInterval(_stemsPoll); _stemsPoll = null;
      st.textContent = 'separação falhou — precisa do extra [ml] (Demucs).';
      st.style.color = '#e88';
    } else if (d.status && d.status !== 'none') {
      const label = { detecting: 'a iniciar', normalizing: 'a normalizar áudio',
        separating: 'a separar (Demucs)…' }[d.status] || d.status;
      st.textContent = label + '…';
    }
  }, 3000);
}

// Populate the audio-source selector for a job: the synthesized per-arrangement
// references are always available (no Demucs); separated stems are added if the
// job already has them (so reopening doesn't re-run Demucs).
async function loadStems(id) {
  availableStems = [];
  audioSourceName = '';
  document.getElementById('stemsStatus').textContent = '';
  document.getElementById('stemsStatus').style.color = '';
  populateAudioSources();
  try {
    const r = await fetch(`/jobs/${id}/stems`);
    if (!r.ok) return;
    const d = await r.json();
    if (d.status === 'separating' || d.status === 'normalizing' || d.status === 'detecting') {
      document.getElementById('stemsStatus').textContent = 'separação em curso…';
      pollStems();
    } else if ((d.stems || []).length) {
      availableStems = d.stems;
      populateAudioSources();
    }
  } catch { /* ignore */ }
}

document.getElementById('separateStems').addEventListener('click', separateStems);
document.getElementById('audioSource').addEventListener('change', async e => {
  audioSourceName = e.target.value;
  if (!selectedJob) return;
  // Re-decode the chosen source; keep the playhead where it was.
  const at = currentPlayheadT;
  const wasPlaying = audioIsPlaying();
  stopPlayback();
  await decodeWaveform(selectedJob.id);
  audioSeek(at);
  if (wasPlaying) audioPlay();
});

function loadCoverArt(j) {
  if (capaResultsFor !== j.id) {
    capaResultsFor = j.id;
    capaCandidates = [];
    document.getElementById('capaResults').replaceChildren();
    document.getElementById('capaSearchInfo').textContent = '';
  }
  const img = document.getElementById('coverArtPreview');
  const info = document.getElementById('coverArtInfo');
  if (j.cover_art) {
    img.src = `/jobs/${j.id}/cover?t=${Date.now()}`;
    img.hidden = false;
    info.textContent = 'capa carregada — substitui o ficheiro para alterar.';
  } else {
    img.hidden = true;
    img.src = '';
    info.textContent = 'sem capa.';
  }
}

document.getElementById('coverArtFile').addEventListener('change', async ev => {
  if (!selectedJob) return;
  const file = ev.target.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  const r = await fetch(`/jobs/${selectedJob.id}/cover`, { method: 'POST', body: fd });
  const b = await r.json();
  if (!r.ok) { toast(b.detail || 'erro'); return; }
  selectedJob.cover_art = b.cover_art;
  loadCoverArt(selectedJob);
  toast('Capa carregada — "Aplicar e reconstruir" para a incluir no bundle.', 'ok');
  ev.target.value = '';
});

// ── Album, year and cover lookup (wizard step 4 + the Capa page) ──────────────
// /album-lookup asks iTunes and MusicBrainz/Cover Art Archive by title + band
// and returns candidates; the USER picks one — nothing is filled from a guess
// they cannot see. Each card shows the matched track and the source, so a
// wrong match (a cover version, a compilation) is visible before it is used.
const ALBUM_KIND = { album: 'álbum', ep: 'EP', single: 'single', compilation: 'compilação' };
const ALBUM_SOURCE = { itunes: 'iTunes', musicbrainz: 'MusicBrainz' };

async function lookupAlbums(title, artist) {
  const q = `title=${encodeURIComponent(title)}&artist=${encodeURIComponent(artist)}`;
  const r = await getJSON(`/album-lookup?${q}`);
  lastAlbumLookup = r;
  return r.candidates || [];
}
let lastAlbumLookup = null;

// Said when a search comes back empty: WHAT was searched (the main artist,
// without the featuring credit) and why a real answer can be "nothing" — a
// fan remix, a cover or an AI-made song is simply not in these catalogues.
function albumNothingFound() {
  const r = lastAlbumLookup || {};
  const what = r.searched_title ? `"${r.searched_title}" de ${r.searched_artist}` : 'este título e banda';
  const down = (r.failures || []).length
    ? ` (não consegui perguntar a ${r.failures.map(f => f.split(':')[0]).join(', ')}.)` : '';
  return `Nada encontrado para ${what} no iTunes nem no MusicBrainz${down}. ` +
    'Remixes de fãs, versões e músicas feitas por IA não estão nestes catálogos — ' +
    'corrige o título/banda e procura de novo, ou carrega a capa à mão.';
}

// Build the grid with DOM calls, not innerHTML: the URLs and names come from
// third-party services.
function renderAlbumGrid(el, candidates, selected, onPick, { withNone = false } = {}) {
  el.replaceChildren();
  const card = (idx, artChild, title, lines) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'album-card' + (idx === selected ? ' selected' : '');
    b.dataset.idx = String(idx);
    const art = document.createElement('div');
    art.className = 'album-art';
    art.append(artChild);
    const t = document.createElement('b');
    t.textContent = title;
    b.append(art, t);
    for (const line of lines) {
      const s = document.createElement('span');
      s.textContent = line;
      b.append(s);
    }
    b.addEventListener('click', () => onPick(idx));
    el.append(b);
    return b;
  };
  const placeholder = name => {
    const d = document.createElement('div');
    d.innerHTML = icon(name);
    return d.firstElementChild;
  };
  candidates.forEach((c, i) => {
    let art = placeholder('image');
    if (c.thumb_url) {
      art = document.createElement('img');
      art.alt = '';
      art.loading = 'lazy';
      art.src = c.thumb_url;
      // No cover at that address (common on the Cover Art Archive): say so on
      // the card instead of showing a broken image.
      art.addEventListener('error', () => {
        c.cover_broken = true;
        art.replaceWith(placeholder('image'));
      });
    }
    const meta = [c.year, ALBUM_KIND[c.kind] || c.kind].filter(Boolean).join(' · ');
    card(i, art, c.album, [meta, `"${c.track}" · ${ALBUM_SOURCE[c.source] || c.source}`]);
  });
  if (withNone && candidates.length)
    card(-1, placeholder('x'), 'Sem capa', ['não usar nenhuma imagem']);
}

// Wizard step 4: searched once automatically on arrival (title and band are
// normally already there from the GP file), again on demand.
let wzAlbumCandidates = [];
let wzAlbumPick = null;          // index into wzAlbumCandidates, -1 = no cover
let wzAlbumAutoDone = false;

function resetWizardAlbum() {
  wzAlbumCandidates = [];
  wzAlbumPick = null;
  wzAlbumAutoDone = false;
  document.getElementById('wzAlbumResults').replaceChildren();
  document.getElementById('wzAlbumInfo').textContent = '';
  document.getElementById('wzCoverUrl').value = '';
}

function pickWizardAlbum(idx, { fillEmptyOnly = false } = {}) {
  const form = document.getElementById('gpJobForm');
  wzAlbumPick = idx;
  const c = wzAlbumCandidates[idx];
  document.getElementById('wzCoverUrl').value = c && c.cover_url ? c.cover_url : '';
  if (c) {
    const album = form.querySelector('input[name=album]');
    const year = form.querySelector('input[name=year]');
    if (!fillEmptyOnly || !album.value.trim()) album.value = c.album;
    if (c.year && (!fillEmptyOnly || !year.value.trim())) year.value = String(c.year);
  }
  renderAlbumGrid(document.getElementById('wzAlbumResults'), wzAlbumCandidates, idx,
    i => pickWizardAlbum(i), { withNone: true });
}

async function searchWizardAlbum() {
  const form = document.getElementById('gpJobForm');
  const title = form.querySelector('input[name=title]').value.trim();
  const artist = form.querySelector('input[name=artist]').value.trim();
  const info = document.getElementById('wzAlbumInfo');
  if (!title || !artist) { info.textContent = 'Preenche o título e a banda para procurar.'; return; }
  const btn = document.getElementById('wzAlbumSearch');
  btn.disabled = true;
  info.textContent = 'A procurar…';
  try {
    wzAlbumCandidates = await lookupAlbums(title, artist);
  } catch (err) {
    wzAlbumCandidates = [];
    info.textContent = `Não consegui procurar agora (${err.message}). Podes preencher à mão.`;
    document.getElementById('wzAlbumResults').replaceChildren();
    return;
  } finally {
    btn.disabled = false;
  }
  if (!wzAlbumCandidates.length) {
    info.textContent = albumNothingFound();
    document.getElementById('wzAlbumResults').replaceChildren();
    document.getElementById('wzCoverUrl').value = '';
    return;
  }
  info.textContent = `${wzAlbumCandidates.length} resultado(s) — escolhe o álbum e a capa certos.`;
  // Preselect the best guess but never overwrite what the user (or the GP
  // file) already typed; clicking a card is an explicit choice and does.
  pickWizardAlbum(0, { fillEmptyOnly: true });
}
document.getElementById('wzAlbumSearch').addEventListener('click', searchWizardAlbum);

function maybeAutoAlbumSearch() {
  if (wzAlbumAutoDone) return;
  wzAlbumAutoDone = true;
  searchWizardAlbum();
}

// Capa page: the same candidates, applied to an existing project.
let capaCandidates = [];
let capaResultsFor = null;   // results belong to one project

async function applyCapaCandidate(idx) {
  const c = capaCandidates[idx];
  if (!selectedJob || !c) return;
  renderAlbumGrid(document.getElementById('capaResults'), capaCandidates, idx, applyCapaCandidate);
  const info = document.getElementById('capaSearchInfo');
  const done = [];
  try {
    if (c.cover_url && !c.cover_broken) {
      info.textContent = 'A descarregar a capa…';
      const b = await getJSON(`/jobs/${selectedJob.id}/cover-from-url`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: c.cover_url }),
      });
      selectedJob.cover_art = b.cover_art;
      loadCoverArt(selectedJob);
      done.push('capa');
    }
    if (document.getElementById('capaFillMeta').checked) {
      const j = await getJSON(`/jobs/${selectedJob.id}/metadata`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: selectedJob.title, artist: selectedJob.artist,
          album: c.album, year: c.year ?? selectedJob.year ?? null,
        }),
      });
      Object.assign(selectedJob, { album: j.album, year: j.year });
      renderDetailHead(selectedJob);
      refreshJobs();
      done.push('álbum e ano');
    }
  } catch (err) {
    info.textContent = `Não foi possível: ${err.message}`;
    toast(`Não foi possível aplicar: ${err.message}`);
    return;
  }
  info.textContent = done.length ? `Aplicado: ${done.join(' + ')}.` : 'Esse resultado não tem capa.';
  if (done.length) toast('Aplicado — "Aplicar e reconstruir" para o incluir no bundle.', 'ok');
}

document.getElementById('capaSearch').addEventListener('click', async () => {
  if (!selectedJob) return;
  const info = document.getElementById('capaSearchInfo');
  const grid = document.getElementById('capaResults');
  const btn = document.getElementById('capaSearch');
  btn.disabled = true;
  info.textContent = 'A procurar…';
  try {
    capaCandidates = await lookupAlbums(selectedJob.title || '', selectedJob.artist || '');
  } catch (err) {
    capaCandidates = [];
    grid.replaceChildren();
    info.textContent = `Não consegui procurar agora (${err.message}).`;
    return;
  } finally {
    btn.disabled = false;
  }
  info.textContent = capaCandidates.length
    ? `${capaCandidates.length} resultado(s) — clica no certo para o aplicar.`
    : albumNothingFound();
  renderAlbumGrid(grid, capaCandidates, null, applyCapaCandidate);
});

document.getElementById('addLyricRow').addEventListener('click', () => {
  // Store the un-padded recording-clock time (the playhead is in padded display
  // time), so a new word lands under the cursor and round-trips through rebuild.
  lyricsEvents.push({
    time: Math.max(0, currentPlayheadT - leadInBuilt), length: 0.5, lyric: '', lineBreak: false,
  });
  renderLyricsRows();
});

document.getElementById('sortLyrics').addEventListener('click', () => {
  lyricsEvents.sort((a, b) => a.time - b.time);
  renderLyricsRows();
});

document.getElementById('exportLrc').addEventListener('click', () => {
  if (!lyricsEvents.length) { toast('Sem letras para exportar.'); return; }
  const sorted = [...lyricsEvents].sort((a, b) => a.time - b.time);
  let lines = [];
  let currentLine = [];
  for (const e of sorted) {
    const word = e.lyric.trim();
    if (!word) continue;
    if (!currentLine.length) currentLine = [e];
    else currentLine.push(e);
    if (e.lineBreak) {
      const first = currentLine[0];
      const m = Math.floor(first.time / 60);
      const s = (first.time - m * 60).toFixed(2).padStart(5, '0');
      const text = currentLine.map(w => w.lyric.trim()).join(' ');
      lines.push(`[${String(m).padStart(2,'0')}:${s}]${text}`);
      currentLine = [];
    }
  }
  if (currentLine.length) {
    const first = currentLine[0];
    const m = Math.floor(first.time / 60);
    const s = (first.time - m * 60).toFixed(2).padStart(5, '0');
    const text = currentLine.map(w => w.lyric.trim()).join(' ');
    lines.push(`[${String(m).padStart(2,'0')}:${s}]${text}`);
  }
  const lrc = lines.join('\n') + '\n';
  const blob = new Blob([lrc], { type: 'text/plain' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  const title = selectedJob ? (selectedJob.title || 'lyrics') : 'lyrics';
  a.download = `${title}.lrc`;
  a.click();
  URL.revokeObjectURL(a.href);
  toast('LRC exportado.', 'ok');
});

function updatePendingChangesInfo() {
  const el = document.getElementById('pendingChangesInfo');
  if (!el) return;
  const parts = [];
  const builtOffset = selectedJob ? (selectedJob.offset_s || 0) : 0;
  if (Math.abs(offsetLive - builtOffset) > 0.01) parts.push('offset');
  if (Math.abs(tempoScaleLive - builtScale) > 0.001) parts.push('andamento');
  if (syncAnchors.length) parts.push(`${syncAnchors.length} ponto(s) de correção`);
  if (JSON.stringify(noteOverridesByKind) !== noteOverridesBuilt) parts.push('edições de notas');
  el.textContent = parts.length ? `Pendente: ${parts.join(', ')}` : '';
}

// Piecewise-linear remap from (chartTime, correctedTime) anchors — JS port of
// gp_pipeline._build_time_warp. A single anchor is a uniform shift applied
// everywhere; with two or more anchors (an excerpt drag), notes outside the
// anchor range are left untouched (identity) — only the excerpt between the
// first and last anchor is rigidly shifted/stretched.
function buildTimeWarp(anchors) {
  if (!anchors.length) return t => t;
  const pts = [...anchors].sort((a, b) => a[0] - b[0]);
  return function (t) {
    if (pts.length === 1) {
      const [x0, y0] = pts[0];
      return t + (y0 - x0);
    }
    if (t < pts[0][0]) return t;
    if (t > pts[pts.length - 1][0]) return t;
    // Binary search for the bracketing pair. This runs for every note, beat,
    // bar and grid point on every redraw AND every playhead frame, so a linear
    // scan made the whole viewer slow down in proportion to how many drift
    // corrections the user had placed — exactly the "fica mais lenta enquanto
    // corrijo" symptom.
    let lo = 0, hi = pts.length - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (pts[mid][0] <= t) lo = mid; else hi = mid;
    }
    const [x0, y0] = pts[lo], [x1, y1] = pts[hi];
    if (x1 === x0) return t + (y0 - x0);
    return y0 + (y1 - y0) * (t - x0) / (x1 - x0);
  };
}

function setAnchor(origT, newT) {
  const i = syncAnchors.findIndex(([o]) => Math.abs(o - origT) < 0.05);
  if (i >= 0) syncAnchors[i] = [origT, newT];
  else syncAnchors.push([origT, newT]);
  // Keep them in CHART order. They used to sit in insertion order, so the list
  // could show "Correção 4: 196.93s" above "Correção 5: 195.88s" — the numbering
  // implied an order the music does not have, and a correction that crossed
  // another was invisible until the rebuild rejected it. The warp itself sorts
  // internally (here and in the backend), so this changes no timing — only what
  // the user is shown, and the numbering that follows from it.
  syncAnchors.sort((a, b) => a[0] - b[0]);
}

// Chart-time positions of the current snap grid: measure downbeats ('bars'),
// whole beats (1), or beats subdivided into 2/3/4 (interpolated between real
// ebeats, so tempo changes are respected). Feeds both the drawn grid and snap.
function snapGridTimes() {
  const a = arrangements[currentArr];
  if (!a || snapDiv === 'cursor') return [];  // 'cursor' snaps live in snapDisplay, no grid
  if (snapDiv === 'bars') return (a.bars || []).map(b => b.time);
  const beats = a.beats || [];
  const div = Number(snapDiv);
  if (div <= 1 || beats.length < 2) return beats.slice();
  const out = [];
  for (let i = 0; i < beats.length - 1; i++) {
    const b0 = beats[i], b1 = beats[i + 1];
    for (let k = 0; k < div; k++) out.push(b0 + (b1 - b0) * k / div);
  }
  out.push(beats[beats.length - 1]);
  return out;
}

// Display-space positions of the snap grid, warped through the same
// previewScale + pending anchors as the notes so they track live sync edits.
function beatDisplayPositions() {
  const times = snapGridTimes();
  if (!times.length) return [];
  const warp = buildTimeWarp(syncAnchors);
  return times.map(bt => warp(previewScale(bt)));
}

// Select every note-group whose chart time lies between the Shift-range pivot
// (last plain click) and the just-clicked note, inclusive.
function rangeSelect(t) {
  const anchor = selectionAnchor != null ? selectionAnchor : t;
  const lo = Math.min(anchor, t), hi = Math.max(anchor, t);
  for (const g of document.getElementById('tabsvg').querySelectorAll('.note-grp')) {
    const gt = parseFloat(g.dataset.t);
    if (gt >= lo - 1e-6 && gt <= hi + 1e-6) selectedTimes.add(gt);
  }
  selectionAnchor = anchor;
  updateSelectionInfo();
}

// ---- Guided "detect first note" flow (3 clicks) ----
// Always pins the CURRENT arrangement's clicked note to the marked audio
// point as a per-track pending anchor — same mechanism as Step 1's other
// controls (setTrackStart), just reached via "mark by ear, then click the
// note" instead of typing/dragging.
function firstNoteStatus(text) {
  const el = document.getElementById('firstNoteInfo');
  if (el) el.textContent = text;
  const btn = document.getElementById('detectFirstNote');
  if (btn) btn.classList.toggle('active-mode', firstNoteFlow !== null);
}
function startFirstNoteFlow() {
  if (!isGpJob()) return;
  if (firstNoteFlow) { cancelFirstNoteFlow(); return; }  // clicking again cancels
  firstNoteFlow = 'audio';
  firstNoteStatus('1) Clica na forma de onda onde COMEÇA o som da 1ª nota (clica de novo para ajustar).');
}
function cancelFirstNoteFlow() {
  firstNoteFlow = null;
  firstNoteStatus('Deteção cancelada.');
  if (arrangements.length) showArr(currentArr);
}
// Handle a click during the flow. Returns true if it consumed the click.
function firstNoteFlowClick(e, svg) {
  if (!firstNoteFlow) return false;
  const grp = e.target.closest('.note-grp');
  if (grp && firstNoteFlow === 'note') {
    // 3rd click: pin THIS note to the marked audio point as a pending anchor
    // for the current tab only. origT is the UNwarped previewScale position
    // (not buildTimeWarp(syncAnchors) of it) so re-running the flow on the
    // same note updates the same anchor slot instead of compounding into a
    // 2nd point (setAnchor matches by origT) — same convention as setTrackStart.
    const chartT = parseFloat(grp.dataset.t);
    const origT = previewScale(chartT);
    firstNoteFlow = null;
    setAnchor(origT, firstNoteAudioT + viewOrigin);
    renderAnchorsList();
    updatePendingChangesInfo();
    firstNoteStatus(`Início desta pista fixado em ${firstNoteAudioT.toFixed(2)}s — "Aplicar e reconstruir" para gravar.`);
    toast('Início atualizado', 'ok');
    showArr(currentArr);
    return true;
  }
  // 2nd click (or re-adjust): the point on the waveform where the note sounds.
  const rect = svg.getBoundingClientRect();
  firstNoteAudioT = Math.max(0, (e.clientX - rect.left - 30) / tabPx);
  audioSeek(firstNoteAudioT);  // move the playhead there to confirm by ear
  firstNoteFlow = 'note';
  firstNoteStatus(`2) Som marcado em ${firstNoteAudioT.toFixed(2)}s — clica na 1ª NOTA para a alinhar aí (ou clica noutro ponto para ajustar).`);
  showArr(currentArr);
  return true;
}

// Snap a display time to the nearest beat (from the cached grid), or — when
// snapDiv is 'cursor' — directly to the live playhead position, since that's
// a single point, not a grid (no nearest-neighbor search needed). This is
// what makes dragging reliably land on the cursor: 'tap'/'movefrom' modes
// already snapped a CLICK to the playhead, but a drag in 'drag'/'excerpt'
// mode only ever snapped to the beat grid, which is the "arrastar para o
// cursor nem sempre funciona" symptom. `bypass` (Alt held, or the snap
// toggle off) returns the raw value unchanged for free/fine placement.
function snapDisplay(dispT, bypass) {
  if (bypass || !snapToBeats) return dispT;
  if (snapDiv === 'cursor') return currentPlayheadT + viewOrigin;
  if (!snapPositions.length) return dispT;
  let best = dispT, bestD = Infinity;
  for (const bd of snapPositions) {
    const d = Math.abs(bd - dispT);
    if (d < bestD) { bestD = d; best = bd; }
  }
  return best;
}

// "Novo beat (detetar)": ask the backend for the recording's tempo from the
// clicked point and re-tempo the following notes to it. Two anchors — a fixed
// pivot at the click and the last note stretched by the detected factor — make
// _build_time_warp linearly re-space only [click, last]; nothing before moves.
async function reTempoFromHere(grp) {
  if (!selectedJob) return;
  const warp = buildTimeWarp(syncAnchors);
  const chartT = parseFloat(grp.dataset.t);
  // Anchor origins are UNwarped previewScale times (the warp's domain); displayed
  // positions come from warp() so the pivot stays put and the tail stretches
  // correctly even with pending anchors present.
  const origT = previewScale(chartT);
  const dispT = warp(origT);
  const notes = arrangements[currentArr] ? arrangements[currentArr].notes : [];
  const lastChartT = notes.length ? Math.max(...notes.map(n => n.time)) : chartT;
  const origLast = previewScale(lastChartT);
  const dispLast = warp(origLast);
  if (dispLast <= dispT + 0.01) { toast('é a última nota — nada para re-espaçar', 'err'); return; }
  const fromS = Math.max(0, dispT - viewOrigin);  // click's time in the recording
  // The chart's tempo as it plays RIGHT NOW at the click (authored spacing ×
  // tempo_scale × pending anchors). The factor is applied below as a relative
  // stretch of this timeline's tail, so this — not the GP header tempo — is what
  // it has to be measured against; it also centres the detector's tempo prior,
  // which otherwise defaults to 120 and reads a slow song at double time.
  const info = liveInfoAtTime(dispT, warp);
  const chartBpm = info && info.bpm ? info.bpm : null;
  toast('A detetar andamento…', 'ok');
  try {
    const r = await fetch(`/jobs/${selectedJob.id}/detect-tempo`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from_s: fromS, chart_bpm: chartBpm }),
    });
    const b = await r.json();
    if (!r.ok) { toast(b.detail || 'erro', 'err'); return; }
    const factor = b.suggested_factor;
    setAnchor(origT, dispT);                                     // fixed pivot at the click
    setAnchor(origLast, dispT + (dispLast - dispT) * factor);   // stretch the tail to the local BPM
    renderAnchorsList();
    updatePendingChangesInfo();
    showArr(currentArr);
    const ref = b.reference_bpm ? ` (partitura ${b.reference_bpm.toFixed(1)})` : '';
    toast(`Andamento: ${b.detected_bpm.toFixed(1)} BPM${ref} → ×${factor.toFixed(3)}`, 'ok');
  } catch { toast('falha na deteção', 'err'); }
}

function updateSelectionInfo() {
  const info = document.getElementById('selectionInfo');
  const clearBtn = document.getElementById('clearSelection');
  const n = selectedTimes.size;
  info.textContent = n ? `${n} nota(s) selecionada(s) — arrasta uma para mover todas em bloco` : '';
  clearBtn.hidden = n === 0;
  const copyBtn = document.getElementById('copyNotes');
  if (copyBtn) copyBtn.disabled = n === 0;
}

(() => {
  let dragging = null; // single note: { grps, startX, origT }
  let groupDrag = null; // selection drag: { startX, times }
  let rubberBand = null; // { startX }
  let lyricDrag = null; // lyric word drag: { el, startX, index }
  const svg = document.getElementById('tabsvg');
  const wrap = document.getElementById('tabwrap');

  // Auto-scroll #tabwrap horizontally while any drag/rubber-band gesture's
  // pointer nears the visible edge. Without this, none of them can ever
  // reach a note scrolled off-screen: the mouse itself is bounded by the
  // browser viewport, and #tabwrap's native overflow-x:auto never scrolls on
  // its own while a pointer-capture drag is in progress (the classic "box
  // selection only grabs what's currently visible" bug).
  const AUTO_SCROLL_EDGE_PX = 48;
  const AUTO_SCROLL_MAX_PX = 22;
  let autoScrollRAF = null;
  let lastClientX = 0, lastClientY = 0, lastAltKey = false;

  function activeGesture() { return rubberBand || groupDrag || dragging || lyricDrag; }

  function autoScrollStep() {
    if (!activeGesture()) { autoScrollRAF = null; return; }
    const rect = wrap.getBoundingClientRect();
    let dx = 0;
    if (lastClientX < rect.left + AUTO_SCROLL_EDGE_PX) {
      const t = (rect.left + AUTO_SCROLL_EDGE_PX - lastClientX) / AUTO_SCROLL_EDGE_PX;
      dx = -Math.ceil(AUTO_SCROLL_MAX_PX * Math.min(1, t));
    } else if (lastClientX > rect.right - AUTO_SCROLL_EDGE_PX) {
      const t = (lastClientX - (rect.right - AUTO_SCROLL_EDGE_PX)) / AUTO_SCROLL_EDGE_PX;
      dx = Math.ceil(AUTO_SCROLL_MAX_PX * Math.min(1, t));
    }
    if (dx !== 0) {
      wrap.scrollLeft = Math.max(0, wrap.scrollLeft + dx);
      // Re-run the gesture's own live update at the new scroll position — the
      // mouse hasn't moved, but the SVG has shifted under it (e.g. the
      // rubber-band box's SVG-local x/width must grow to keep tracking it).
      handlePointerMove(lastClientX, lastClientY, lastAltKey);
    }
    autoScrollRAF = requestAnimationFrame(autoScrollStep);
  }
  function startAutoScrollLoop() {
    if (!autoScrollRAF) autoScrollRAF = requestAnimationFrame(autoScrollStep);
  }
  function stopAutoScrollLoop() {
    if (autoScrollRAF) cancelAnimationFrame(autoScrollRAF);
    autoScrollRAF = null;
  }

  document.getElementById('clearSelection').addEventListener('click', () => {
    selectedTimes.clear();
    updateSelectionInfo();
    showArr(currentArr);
  });

  svg.addEventListener('pointerdown', e => {
    // Stop the browser's native text/drag selection (Shift+click is a classic
    // trigger for it) from highlighting the SVG's <text> labels — technique
    // letters, tuning names, bar numbers — while the custom note-selection/
    // drag logic below runs.
    e.preventDefault();
    // Guided "detect first note" flow intercepts all clicks while armed.
    if (firstNoteFlowClick(e, svg)) return;
    // Lyric word drag: grab a word on the tab to reposition it in time.
    const lw = e.target.closest('.lyric-word');
    if (lw) {
      const li = parseInt(lw.dataset.li, 10);
      lyricDrag = { el: lw, startX: e.clientX, index: li };
      lw.setPointerCapture(e.pointerId);
      return;
    }
    const grp = e.target.closest('.note-grp');
    // Multi-select (works in ANY mode — a modifier is unambiguous):
    // Shift+click selects the range from the pivot note to this one; Ctrl/Cmd+
    // click toggles a single note in/out of the selection.
    if (grp && e.shiftKey) {
      rangeSelect(parseFloat(grp.dataset.t));
      showArr(currentArr);
      return;
    }
    if (grp && (e.ctrlKey || e.metaKey)) {
      const t = parseFloat(grp.dataset.t);
      if (selectedTimes.has(t)) selectedTimes.delete(t); else selectedTimes.add(t);
      selectionAnchor = t;
      updateSelectionInfo();
      showArr(currentArr);
      return;
    }
    // Tap-sync mode: click a note to anchor it at the current playhead position.
    // The anchor ORIGIN must be the UNwarped previewScale time (the warp's
    // domain, same as 'drag' and the backend) — NOT warp(previewScale(...)),
    // which is only equal when there are no pending anchors and otherwise
    // corrupts the map (e.g. after a Step-1 "Início" anchor).
    if (syncMode === 'tap' && grp) {
      const origT = previewScale(parseFloat(grp.dataset.t));
      setAnchor(origT, currentPlayheadT + viewOrigin);  // move this note to the playhead
      renderAnchorsList();
      updatePendingChangesInfo();
      showArr(currentArr);
      return;
    }
    // Move-from-here: shift the clicked note and ALL following notes (in a block)
    // to the current playhead, leaving everything before untouched. Origins are
    // the UNwarped previewScale times (the warp's domain); targets are their
    // CURRENT displayed position + delta, so it composes with any pending anchors.
    if (syncMode === 'movefrom' && grp) {
      const warp = buildTimeWarp(syncAnchors);
      const clickedRaw = parseFloat(grp.dataset.t);
      const origClicked = previewScale(clickedRaw);
      const dispClicked = warp(origClicked);  // where the clicked note currently shows
      const notes = arrangements[currentArr] ? arrangements[currentArr].notes : [];
      const lastRaw = notes.length ? Math.max(...notes.map(n => n.time)) : clickedRaw;
      const origLast = previewScale(lastRaw);
      const dispLast = warp(origLast);
      if (dispLast <= dispClicked + 0.01) {
        toast('é a última nota — usa "Arrastar nota"', 'err');
        return;
      }
      const delta = (currentPlayheadT + viewOrigin) - dispClicked;  // brings clicked note to cursor
      // Pin the note immediately BEFORE the click at its current display, so the
      // region before the click stays put. Without this, when a prior anchor
      // (e.g. Step-1 "Início") already exists, adding only the clicked+last
      // anchors turns the uniform pre-click segment into an interpolated one and
      // drags the preceding notes along ("mover seguintes moved notes behind it").
      const priorTimes = notes.map(n => n.time).filter(t => t < clickedRaw - 1e-6);
      if (priorTimes.length) {
        const origPrev = previewScale(Math.max(...priorTimes));
        setAnchor(origPrev, warp(origPrev));  // hold everything up to here in place
      }
      setAnchor(origClicked, dispClicked + delta);  // clicked note lands on the playhead
      setAnchor(origLast, dispLast + delta);         // block end shifts by the same amount
      renderAnchorsList();
      updatePendingChangesInfo();
      showArr(currentArr);
      return;
    }
    // New beat (detect): measure the recording's tempo from the clicked point and
    // re-space the following notes to it. The click point is a fixed pivot
    // (identity) and the last note is stretched by the detected factor, so
    // _build_time_warp linearly re-tempos only [click, last]; nothing before moves.
    if (syncMode === 'newbeat' && grp) {
      reTempoFromHere(grp);
      return;
    }
    // Align-by-bar: click a note → popup with bar numbers (the note's bar
    // pre-selected) → align that bar to the cursor (or another track's same bar).
    if (syncMode === 'baralign' && grp) {
      openBarAlignPopup(parseFloat(grp.dataset.t), e.clientX, e.clientY);
      return;
    }
    // Tone change: click a note to switch to one of the extra tones from there.
    if (syncMode === 'tonechange' && grp) {
      placeToneChange(parseFloat(grp.dataset.t));
      return;
    }
    // Section marker: click a note to name a song-structure section starting there.
    if (syncMode === 'section' && grp) {
      placeSectionMarker(parseFloat(grp.dataset.t));
      return;
    }
    // Note editor: a SINGLE click on an existing note (by its exact string
    // within a chord) edits/removes it. A single click on EMPTY space does NOT
    // insert here — it falls through to the seek branch below, so clicking the
    // score to move the cursor keeps working in this mode too (matching every
    // other note-click mode). Inserting a new note is a DOUBLE click on empty
    // space (see the svg 'dblclick' handler), which is unambiguous.
    if (syncMode === 'editnotes') {
      const single = e.target.closest('.note-single');
      if (grp && single) {
        openNoteEditPopup(parseFloat(grp.dataset.t), parseInt(single.dataset.string, 10), e.clientX, e.clientY);
        return;
      }
      // empty space → fall through to the click-to-seek branch below
    }
    if (syncMode === 'excerpt' && !(grp && selectedTimes.has(parseFloat(grp.dataset.t)))) {
      // start a rubber-band selection (also when starting on an unselected note)
      const rect = svg.getBoundingClientRect();
      rubberBand = { startX: e.clientX - rect.left };
      const box = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      box.id = 'selectionBox';
      box.setAttribute('x', rubberBand.startX);
      box.setAttribute('y', '0');
      box.setAttribute('width', '0');
      box.setAttribute('height', String(tabH));
      svg.appendChild(box);
      svg.setPointerCapture(e.pointerId);
      return;
    }
    if (!grp) {
      // Click on empty staff/waveform → clear any selection and move the audio
      // (and playhead) there. The x-axis is recording time: rt = (x - 30) / tabPx.
      if (selectedTimes.size) { selectedTimes.clear(); selectionAnchor = null; updateSelectionInfo(); showArr(currentArr); }
      const rect = svg.getBoundingClientRect();
      audioSeek(Math.max(0, (e.clientX - rect.left - 30) / tabPx));
      return;
    }
    const t = parseFloat(grp.dataset.t);
    if (syncMode !== 'drag') {
      // Outside "Arrastar" (neutral / excerpt) a plain click on a note just
      // selects it (and sets the Shift-range pivot) — no anchor drag.
      selectedTimes.clear(); selectedTimes.add(t); selectionAnchor = t;
      updateSelectionInfo(); showArr(currentArr);
      return;
    }
    snapPositions = beatDisplayPositions();  // cache the snap grid for this drag
    if (selectedTimes.size > 1 && selectedTimes.has(t)) {
      // drag the whole selection together
      const grps = [...svg.querySelectorAll('.note-grp.selected')];
      groupDrag = { grps, startX: e.clientX, times: [...selectedTimes], origT: t };
      grps.forEach(g => g.setPointerCapture(e.pointerId));
      return;
    }
    dragging = { grp, startX: e.clientX, origT: t };
    grp.setPointerCapture(e.pointerId);
  });
  function handlePointerMove(clientX, clientY, altKey) {
    lastClientX = clientX; lastClientY = clientY; lastAltKey = altKey;
    if (lyricDrag) {
      const dx = clientX - lyricDrag.startX;
      lyricDrag.el.setAttribute('transform', `translate(${dx},0)`);
      return;
    }
    if (rubberBand) {
      const rect = svg.getBoundingClientRect();
      const x = clientX - rect.left;
      const box = document.getElementById('selectionBox');
      box.setAttribute('x', String(Math.min(rubberBand.startX, x)));
      box.setAttribute('width', String(Math.abs(x - rubberBand.startX)));
      return;
    }
    if (groupDrag) {
      // Snap the whole selection: the earliest note lands on a beat, the rest
      // shift rigidly with it. Alt bypasses the snap for free placement.
      const dx = clientX - groupDrag.startX;
      const warp = buildTimeWarp(syncAnchors);
      const startDisp = warp(previewScale(Math.min(...groupDrag.times)));
      const snapped = snapDisplay(startDisp + dx / tabPx, altKey);
      const sdx = (snapped - startDisp) * tabPx;
      groupDrag.grps.forEach(g => g.setAttribute('transform', `translate(${sdx},0)`));
      return;
    }
    if (!dragging) return;
    const dx = clientX - dragging.startX;
    const origDisp = buildTimeWarp(syncAnchors)(previewScale(dragging.origT));
    const snapped = snapDisplay(origDisp + dx / tabPx, altKey);
    dragging.grp.setAttribute('transform', `translate(${(snapped - origDisp) * tabPx},0)`);
  }
  svg.addEventListener('pointermove', e => {
    handlePointerMove(e.clientX, e.clientY, e.altKey);
    if (rubberBand || groupDrag || dragging || lyricDrag) startAutoScrollLoop();
  });
  svg.addEventListener('pointerup', e => {
    stopAutoScrollLoop();
    if (lyricDrag) {
      const dx = e.clientX - lyricDrag.startX;
      lyricDrag.el.removeAttribute('transform');
      const deltaS = dx / tabPx;
      if (Math.abs(deltaS) > 0.005) {
        lyricsEvents[lyricDrag.index].time = Math.max(0, lyricsEvents[lyricDrag.index].time + deltaS);
        renderLyricsRows();
        showArr(currentArr);
        updatePendingChangesInfo();
      }
      lyricDrag = null;
      return;
    }
    if (rubberBand) {
      const rect = svg.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const x1 = Math.min(rubberBand.startX, x), x2 = Math.max(rubberBand.startX, x);
      const t1 = xToTime(x1), t2 = xToTime(x2);  // bundle time, same space as previewScale
      document.getElementById('selectionBox')?.remove();
      rubberBand = null;
      if (x2 - x1 > 3) {
        const warp = buildTimeWarp(syncAnchors);
        for (const g of svg.querySelectorAll('.note-grp')) {
          const t = parseFloat(g.dataset.t);
          const dispT = warp(previewScale(t));
          if (dispT >= t1 && dispT <= t2) selectedTimes.add(t);
        }
        updateSelectionInfo();
        showArr(currentArr);
      }
      return;
    }
    if (groupDrag) {
      const dx = e.clientX - groupDrag.startX;
      groupDrag.grps.forEach(g => g.removeAttribute('transform'));
      if (Math.abs(dx) <= 3) {
        // A click (no real drag) on a selected note collapses the selection to
        // just that note (and sets it as the Shift-range pivot).
        selectedTimes.clear(); selectedTimes.add(groupDrag.origT);
        selectionAnchor = groupDrag.origT;
        updateSelectionInfo(); showArr(currentArr);
        groupDrag = null;
        return;
      }
      const warp = buildTimeWarp(syncAnchors);
      // anchors live in display coordinates (previewScale of the chart time)
      const dStart = previewScale(Math.min(...groupDrag.times));
      const dEnd = previewScale(Math.max(...groupDrag.times));
      // Snap the earliest selected note to a beat; shift the group by that delta.
      const snappedStart = snapDisplay(warp(dStart) + dx / tabPx, e.altKey);
      const snapDelta = snappedStart - warp(dStart);
      if (Math.abs(snapDelta) > 0.003) {
        setAnchor(dStart, warp(dStart) + snapDelta);
        if (dEnd !== dStart) setAnchor(dEnd, warp(dEnd) + snapDelta);
        renderAnchorsList();
        updatePendingChangesInfo();
        showArr(currentArr);
      }
      groupDrag = null;
      return;
    }
    if (!dragging) return;
    const dx = e.clientX - dragging.startX;
    dragging.grp.removeAttribute('transform');
    if (Math.abs(dx) <= 3) {
      // A click (no real drag) selects just this note and makes it the pivot.
      selectedTimes.clear(); selectedTimes.add(dragging.origT);
      selectionAnchor = dragging.origT;
      updateSelectionInfo(); showArr(currentArr);
      dragging = null;
      return;
    }
    const chart = previewScale(dragging.origT);  // display coordinates
    const origDisp = buildTimeWarp(syncAnchors)(chart);
    const target = snapDisplay(origDisp + dx / tabPx, e.altKey);
    // A real drag that actually changes the position becomes an anchor; a tiny
    // move that snaps back to the same beat leaves notes untouched.
    if (Math.abs(target - origDisp) > 0.003) {
      setAnchor(chart, target);
      renderAnchorsList();
      updatePendingChangesInfo();
      showArr(currentArr);
    }
    dragging = null;
  });
  // pointercancel (tab/window blur mid-drag, a touch gesture the browser
  // interrupts) never fires pointerup — without this, a stale dragging/
  // groupDrag/rubberBand/lyricDrag flag survives and misreads the NEXT
  // ordinary mouse move (no button held) as a continuing drag. Unlike
  // pointerup this only resets state — a cancelled gesture must not commit.
  svg.addEventListener('pointercancel', () => {
    stopAutoScrollLoop();
    if (lyricDrag) { lyricDrag.el.removeAttribute('transform'); lyricDrag = null; }
    if (rubberBand) { document.getElementById('selectionBox')?.remove(); rubberBand = null; }
    if (groupDrag) { groupDrag.grps.forEach(g => g.removeAttribute('transform')); groupDrag = null; }
    if (dragging) { dragging.grp.removeAttribute('transform'); dragging = null; }
  });
  // Insert a new note by DOUBLE-clicking empty staff space in "Editar notas"
  // mode — single click there now seeks (see the editnotes branch above), so
  // the insert gesture must be distinct. A double-click on an existing note is
  // ignored here (the single click already opened its edit popup).
  svg.addEventListener('dblclick', e => {
    if (syncMode !== 'editnotes') return;
    if (e.target.closest('.note-single')) return;
    const rect = svg.getBoundingClientRect();
    const clickY = e.clientY - rect.top;
    const string = Math.min(5, Math.max(0, Math.round((STAFF_SB - clickY) / STAFF_ROW)));
    openNoteEditPopup(nearestGridChartTime(e.clientX - rect.left), string, e.clientX, e.clientY);
  });
})();

// ---- Sync mode buttons ----
const SYNC_MODE_BUTTONS = [
  ['modeArrastar', 'drag'],
  ['modeMarcar', 'tap'],
  ['modeExcerto', 'excerpt'],
  ['modeMover', 'movefrom'],
  ['modeBeat', 'newbeat'],
  ['modeBarAlign', 'baralign'],
  ['modeTone', 'tonechange'],
  ['modeSection', 'section'],
  ['modeEditNotes', 'editnotes'],
];
const MODE_HELP = {
  drag: '<b>Arrastar:</b> arrasta uma nota para o instante da gravação onde ela deve tocar (encaixa no beat). As notas entre duas correções esticam/comprimem para acompanhar. Ideal para acertar um ponto que escorregou.',
  tap: '<b>Marcar no cursor:</b> dá play, e quando ouvires uma nota na gravação, clica nessa nota na partitura — ela ancora na posição do cursor. Alinhar a tocar.',
  excerpt: '<b>Excerto:</b> arrasta uma caixa por cima de várias notas e depois arrasta uma delas — movem-se todas em bloco. (Alternativa: Shift+clique numa nota e noutra para selecionar o intervalo.)',
  movefrom: '<b>Mover seguintes:</b> pausa a gravação no instante certo e clica na 1ª nota desalinhada — essa nota e TODAS as seguintes deslocam-se em bloco para o cursor. Para um trecho inteiro que entrou tarde/cedo.',
  newbeat: '<b>Corrigir daqui (detetar andamento) — o modo recomendado:</b> ouve até ao ponto onde a partitura começa a fugir da gravação e clica nessa nota. Mede o BPM real da gravação daí em diante e re-espaça só as notas seguintes. <b>Nada antes do clique se mexe</b>, por isso o que já estava bem fica intacto. Repete sempre que voltar a fugir — cada correção parte de onde a anterior deixou.',
  baralign: '<b>Alinhar por compasso:</b> pausa a gravação no instante certo e clica numa nota — abre um popup com o compasso da nota já escolhido. Confirma com "= cursor" e esse compasso alinha-se ao cursor (ou "= pista" para o mesmo compasso de outra pista). Faz-se várias vezes ao longo da música; cada correção arrasta as notas seguintes.',
  tonechange: '<b>Mudança de tom:</b> clica numa nota para trocar para um dos tons extra a partir daí.',
  section: '<b>Secção:</b> clica numa nota para nomear onde começa uma secção (intro/verso/refrão…). Nada a ver com sincronização — é para navegação e o Riff Repeater.',
  editnotes: '<b>Editar notas:</b> clica numa nota para a editar (traste, sustain, técnicas, bend/slide) ou remover; <b>duplo-clique</b> no pentagrama vazio insere uma nota nova, encaixada na grelha. Um clique simples no vazio move o cursor, como nos outros modos. Muda o CONTEÚDO da partitura — fica pendente até "Aplicar e reconstruir".',
  null: 'Nenhum modo ativo. Clica num modo acima. <b>Dica:</b> para um desvio uniforme em todo o trecho, usa antes o <b>Andamento (BPM)</b> — não precisa de âncoras.',
};
function setSyncMode(mode) {
  syncMode = mode;  // null = neutral: no mode highlighted, note-drag disabled
  SYNC_MODE_BUTTONS.forEach(([bid, bmode]) => {
    const b = document.getElementById(bid);
    if (!b) return;
    b.classList.toggle('active-mode', bmode === syncMode);
    b.setAttribute('aria-checked', String(bmode === syncMode));
  });
  // The "Modo" dropdown's trigger shows the active mode (or that none is).
  const activeBtn = SYNC_MODE_BUTTONS.find(([, bmode]) => bmode === syncMode);
  const src = activeBtn && document.getElementById(activeBtn[0]);
  const ico = document.getElementById('modeMenuIco');
  const lbl = document.getElementById('modeMenuLbl');
  if (ico) ico.innerHTML = icon(src ? src.dataset.ico : 'mouse', 'dd-ico');
  if (lbl) lbl.textContent = src ? src.dataset.name : 'Nenhum modo';
  document.getElementById('modeMenuBtn')?.classList.toggle('has-mode', !!src);
  const help = document.getElementById('modeHelp');
  if (help) help.innerHTML = MODE_HELP[mode] || MODE_HELP.null;
}

// The tool bar's dropdowns: the trigger toggles its menu; picking an item,
// Escape or a click outside closes it; arrow keys move between enabled items.
function wireDropdown(triggerId, menuId) {
  const trigger = document.getElementById(triggerId);
  const menu = document.getElementById(menuId);
  if (!trigger || !menu) return;
  const items = () => [...menu.querySelectorAll('button.dd-item:not(:disabled)')];
  const close = (refocus) => {
    if (menu.hidden) return;
    menu.hidden = true;
    trigger.setAttribute('aria-expanded', 'false');
    if (refocus) trigger.focus();
  };
  const open = () => {
    document.querySelectorAll('.dd-menu:not([hidden])').forEach(m => {
      if (m !== menu) m.hidden = true;
    });
    menu.hidden = false;
    trigger.setAttribute('aria-expanded', 'true');
    // The job view is a scrolling modal, so a menu near its bottom would open
    // past the edge: flip it upward when there is more room above, and cap
    // its height to the room it gets either way.
    const t = trigger.getBoundingClientRect();
    const box = (trigger.closest('.pv-center, .pv-inspector, .pv-scroll, .modal') || document.documentElement).getBoundingClientRect();
    const below = Math.min(window.innerHeight, box.bottom) - t.bottom - 12;
    const above = t.top - Math.max(0, box.top) - 12;
    const up = menu.scrollHeight > below && above > below;
    menu.classList.toggle('dd-up', up);
    menu.style.maxHeight = `${Math.max(160, up ? above : below)}px`;
    (menu.querySelector('.active-mode') || items()[0])?.focus();
  };
  trigger.addEventListener('click', () => (menu.hidden ? open() : close(false)));
  menu.addEventListener('click', e => { if (e.target.closest('button.dd-item')) close(false); });
  menu.addEventListener('keydown', e => {
    if (e.key === 'Escape') { e.preventDefault(); close(true); return; }
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    e.preventDefault();
    const list = items();
    const i = list.indexOf(document.activeElement);
    const next = e.key === 'ArrowDown' ? i + 1 : i - 1;
    list[(next + list.length) % list.length]?.focus();
  });
  document.addEventListener('pointerdown', e => {
    if (!menu.hidden && !menu.contains(e.target) && !trigger.contains(e.target)) close(false);
  });
}
wireDropdown('modeMenuBtn', 'modeMenu');
wireDropdown('notesMenuBtn', 'notesMenu');
wireDropdown('audioMenuBtn', 'audioMenu');
SYNC_MODE_BUTTONS.forEach(([id, mode]) => {
  document.getElementById(id)?.addEventListener('click', () => {
    // Clicking the active mode again DESELECTS it → neutral (no mode), rather
    // than falling back to "Arrastar". Selection is modifier-driven and stays.
    setSyncMode(syncMode === mode ? null : mode);
  });
});
setSyncMode(syncMode);  // show the help line for the initial mode
document.getElementById('snapBeats')?.addEventListener('change', e => {
  snapToBeats = e.target.checked;
  if (arrangements.length) showArr(currentArr);  // show/hide the grid
});
document.getElementById('snapDiv')?.addEventListener('change', e => {
  snapDiv = e.target.value === 'bars' ? 'bars' : Number(e.target.value);
  if (arrangements.length) showArr(currentArr);  // redraw the grid at the new resolution
});

// ---- Visual sync tool (GP jobs) ----
// Standard tuning (low E to high e): MIDI 40, 45, 50, 55, 59, 64
const STRING_MIDI = [40, 45, 50, 55, 59, 64];

function midiToHz(midi) {
  return 440 * Math.pow(2, (midi - 69) / 12);
}

let tickGain = 1.0;
document.getElementById('tickVolume')?.addEventListener('input', e => {
  tickGain = parseFloat(e.target.value);
});
document.getElementById('musicVolume')?.addEventListener('input', e => {
  if (playGain) playGain.gain.value = parseFloat(e.target.value);
});
document.getElementById('playbackSpeed')?.addEventListener('change', e => {
  const now = audioTime();          // capture position under the OLD rate first
  playbackRate = parseFloat(e.target.value);
  if (audioIsPlaying()) audioSeek(now);  // restart the source at the new rate
  else { const au = document.getElementById('syncAudio'); if (au) au.playbackRate = playbackRate; }
});

// ── Tone preview (test a CREATED tone's character on the score playback) ──────
// RockForge has no amp modelling, so this is an honest *character* approximation
// (clean / crunch / high-gain + brightness) via Web Audio waveshaping — NOT the
// real amp/cabinet sound (that only exists in-game / DLC Builder). The drive is
// derived from the tone's descriptors, its amp Gain knob, and any drive pedals.
let previewToneKey = '';
const _distCurves = {};
function distortionCurve(drive) {
  const bucket = Math.round(drive * 20);  // cache per 5% step (a synth has 100s of notes)
  if (_distCurves[bucket]) return _distCurves[bucket];
  const k = bucket / 20 * 100, n = 1024, curve = new Float32Array(n), deg = Math.PI / 180;
  for (let i = 0; i < n; i++) { const x = i * 2 / n - 1; curve[i] = (3 + k) * x * 20 * deg / (Math.PI + k * Math.abs(x)); }
  return (_distCurves[bucket] = curve);
}
function toneCharacter(tone) {
  if (!tone) return null;
  const d = (tone.descriptors || []).join(' ').toUpperCase();
  // Base drive from the gain category…
  let base = 0.12;
  if (d.includes('HIGH GAIN') || d.includes('DISTORTION') || d.includes('METAL')) base = 0.85;
  else if (d.includes('CRUNCH') || d.includes('OVERDRIVE') || d.includes('DRIVE')) base = 0.5;
  else if (d.includes('CLEAN')) base = 0.06;
  // …refined by the amp's actual knob values, so two tones of the SAME category
  // still sound different when their Gain / tone stack differ.
  let gain = null, treb = null, bass = null, pres = null;
  for (const [k, v] of Object.entries((tone.amp && tone.amp.knobs) || {})) {
    if (isNaN(+v)) continue;
    if (/gain|drive/i.test(k)) gain = +v;
    else if (/pres/i.test(k)) pres = +v;
    else if (/treb|high/i.test(k)) treb = +v;
    else if (/bass|low/i.test(k)) bass = +v;
  }
  let drive = gain != null ? base * 0.4 + (gain / 100) * 0.6 : base;
  const pedals = [...(tone.pre || []), ...(tone.post || []), ...(tone.racks || [])].filter(Boolean);
  if (pedals.some(p => /dist|overdrive|fuzz|metal|drive/i.test(p.key || ''))) drive += 0.18;
  drive = Math.max(0, Math.min(1, drive));
  // Brightness from the tone stack (treble/presence up, bass down) when present,
  // else the role — again so distinct tones read differently.
  let bright = d.includes('BASS') ? 0.25 : d.includes('LEAD') ? 0.7 : 0.5;
  if (treb != null || bass != null || pres != null) {
    const t = (treb ?? 50) / 100, b = (bass ?? 50) / 100, p = (pres ?? 50) / 100;
    bright = Math.max(0.1, Math.min(0.95, 0.35 + t * 0.4 + p * 0.2 - b * 0.15));
  }
  return { drive, bright };
}
let previewToneTouched = false;  // did the user pick a preview source themselves?

// The tone key active at a given CHART time, following the tones marked on the
// score: the last tone change at/before that time, else the base tone (or the
// first extra / first created tone). toneChanges[].time and note.time share the
// chart timeline, so this compares directly.
function activeToneKeyAt(chartTime) {
  let key = toneBase || toneNames[0] || (jobTones[0] && jobTones[0].key) || null;
  for (const c of toneChanges) {  // already time-sorted (see loadTones)
    if (c.time <= chartTime + 1e-6) key = c.name; else break;
  }
  return key;
}

// The character for the note at `chartTime`: none (plain voice), a single forced
// tone, or — in "follow the score" mode ('__follow__') — the tone marked at that
// point, so a chart with several tone changes mirrors each of them as it plays.
function toneCharForNote(chartTime) {
  if (!previewToneKey) return null;
  const key = previewToneKey === '__follow__' ? activeToneKeyAt(chartTime) : previewToneKey;
  return key ? toneCharacter(jobTones.find(t => t.key === key)) : null;
}

// Build one plucked note into `ctx` at `dest`, at the note's real pitch. Without
// a tone character it's the plain oscillator pluck (sawtooth+triangle through a
// lowpass); with one, it routes through a waveshaper (drive) and a brighter or
// darker filter to approximate that tone. Shared by the live tick and the
// offline synthesized-arrangement render so both sound the same.
// A plucked-string (Karplus-Strong) note buffer: a noise excitation fed through
// a short delay line with a averaging low-pass in the feedback loop, which is
// what makes it read as a real plucked guitar/bass string (harmonic-rich attack
// decaying to the fundamental) rather than a bare oscillator. `damping` sets the
// sustain. Baked-in attack/release fades avoid the noise-burst click and the
// truncation click at `dur`.
// Rendered buffers are cached per (pitch, duration, damping, sample rate): a
// guitar only has ~50 distinct pitches, and the DSP loop below runs ~10k
// iterations on the MAIN thread — regenerating it for every tick was a large
// per-note cost inside the animation frame, starving the playhead and adding
// GC pressure that glitches the audio. Rounding the pitch to 0.1 Hz is far
// finer than a semitone, so no note changes timbre.
const _karplusCache = new Map();

function karplusBuffer(ctx, hz, dur, damping) {
  const sr = ctx.sampleRate;
  const ck = `${sr}:${hz.toFixed(1)}:${dur.toFixed(3)}:${damping}`;
  const hit = _karplusCache.get(ck);
  if (hit) return hit;
  const N = Math.max(2, Math.round(sr / Math.max(20, hz)));
  const total = Math.max(1, Math.floor(dur * sr));
  const buf = ctx.createBuffer(1, total, sr);
  const out = buf.getChannelData(0);
  const ring = new Float32Array(N);
  let prev = 0;
  for (let i = 0; i < N; i++) { const w = Math.random() * 2 - 1; ring[i] = prev = prev * 0.5 + w * 0.5; }  // softened pick
  let pos = 0;
  for (let i = 0; i < total; i++) {
    const cur = ring[pos];
    out[i] = cur;
    ring[pos] = (cur + ring[(pos + 1) % N]) * 0.5 * damping;
    pos = (pos + 1) % N;
  }
  const atk = Math.min(total, Math.floor(sr * 0.002)), rel = Math.min(total, Math.floor(sr * 0.008));
  for (let i = 0; i < atk; i++) out[i] *= i / atk;
  for (let i = 0; i < rel; i++) out[total - 1 - i] *= i / rel;
  if (_karplusCache.size > 256) _karplusCache.clear();  // bounded; a song needs ~50
  _karplusCache.set(ck, buf);
  return buf;
}

// One shared guitar cabinet per audio context, as an EQ chain: a low-mid body
// bump, a mid scoop, and a speaker high-roll-off — the coloration that makes a
// signal read as "through an amp/cab" rather than a raw string. (A synthesized
// convolution IR was tried but only added fizz, since Karplus-Strong is already
// dark; a real captured IR could drop into a ConvolverNode here later.) Every
// note routes through it, so they share one physical cabinet like a real rig.
const _cabinets = new WeakMap();
function getCabinet(ctx) {
  let cab = _cabinets.get(ctx);
  if (cab) return cab;
  const input = ctx.createGain();
  const body = ctx.createBiquadFilter(); body.type = 'peaking'; body.frequency.value = 110; body.gain.value = 4; body.Q.value = 0.7;
  const scoop = ctx.createBiquadFilter(); scoop.type = 'peaking'; scoop.frequency.value = 900; scoop.gain.value = -3; scoop.Q.value = 0.9;
  const roll = ctx.createBiquadFilter(); roll.type = 'lowpass'; roll.frequency.value = 4000; roll.Q.value = 0.7;
  const makeup = ctx.createGain(); makeup.gain.value = 1.3;
  input.connect(body); body.connect(scoop); scoop.connect(roll); roll.connect(makeup); makeup.connect(ctx.destination);
  cab = { input };
  _cabinets.set(ctx, cab);
  return cab;
}

// Build one plucked note into `ctx`, at the note's real pitch, through the shared
// cabinet — so it sounds like a guitar playing that note. Without a tone it's a
// clean plucked string; with one, a waveshaper (drive) + brightness filter
// approximate the tone's character before the cabinet.
function voiceNote(ctx, dest, hz, t0, dur, peak, char) {  // dest kept for signature; routed via cabinet
  const src = ctx.createBufferSource();
  // 0.99: a plucky decay (attack emphasised) rather than a long sustain — reads
  // as a picked note. Lower strings (larger delay line) naturally ring longer.
  src.buffer = karplusBuffer(ctx, hz, dur, 0.99);
  const mk = char && char.drive > 0.03 ? 1 + char.drive * 0.8 : 1;  // makeup: distortion compresses
  const lvl = ctx.createGain(); lvl.gain.value = Math.max(0.0001, peak * mk) * 0.9;
  if (char && char.drive > 0.03) {
    const drv = ctx.createGain(); drv.gain.value = 1 + char.drive * 8;   // push into the shaper
    const ws = ctx.createWaveShaper(); ws.curve = distortionCurve(char.drive); ws.oversample = '2x';
    const bright = ctx.createBiquadFilter(); bright.type = 'lowpass'; bright.Q.value = 0.7;
    bright.frequency.value = Math.min(9000, 1500 + char.bright * 6000);   // tame fizz, follow brightness
    src.connect(drv); drv.connect(ws); ws.connect(bright); bright.connect(lvl);
  } else {
    src.connect(lvl);
  }
  // A selected tone goes through the cabinet (amped colour); "Voz simples" (no
  // tone) is a dry note tick straight out — no cabinet, no distortion.
  lvl.connect(char ? getCabinet(ctx).input : ctx.destination);
  src.start(t0); src.stop(t0 + dur + 0.05);
}

// Per-note "tick": a short plucked-string tone AT THE NOTE'S REAL PITCH, shaped
// by the preview tone active at this note's chart time (if any). Gain follows
// the Notas slider (0-200%).
function playNote(midi, chartTime) {
  if (!audioCtx || midi == null) return;
  voiceNote(audioCtx, audioCtx.destination, midiToHz(midi), audioCtx.currentTime,
    0.24, Math.max(0.0001, tickGain * 0.6), toneCharForNote(chartTime));
}

// Render one arrangement's notes to a clean AudioBuffer (offline), placing each
// note at the recording-clock time it currently occupies on screen —
// warp(previewScale(t)) - viewOrigin, parameterized by the arrangement's own
// pending sync so it's correct regardless of which tab is open. Used as a
// selectable "Lead/Rhythm (sintetizada)" audio source: an isolated clean
// reference of just that guitar's part, to check the sync of each arrangement
// against the recording by ear. Reflects the pending sync at the moment it's
// selected (re-pick the source to refresh after more edits).
async function synthesizeArrangement(kind) {
  const a = arrangements.find(x => x.kind === kind);
  if (!a || !a.notes || !a.notes.length) return null;
  const sr = 44100;
  const gp = isGpJob();
  const offs = a.tuning_offsets || [0, 0, 0, 0, 0, 0];
  const bScale = a.tempo_scale || 1;
  const tScale = (kind in tempoScaleByKind) ? tempoScaleByKind[kind] : bScale;
  const ratio = tScale / bScale;
  const warp = buildTimeWarp(syncAnchorsByKind[kind] || []);
  const pad = Math.max(offsetLive, MIN_LEAD);
  const events = [];
  let maxT = 0;
  for (const n of a.notes) {
    if (n.string < 0 || n.string > 5 || n.fret < 0) continue;
    // Same recording-clock position the note is drawn at (see previewScale /
    // timeToX): GP applies tempo/offset/anchor sync; audio-ML notes are already
    // at raw recording time.
    const tRec = gp ? warp((n.time - scoreShift) * ratio + pad) - viewOrigin : n.time;
    if (tRec < 0) continue;
    events.push({ t: tRec, chartT: n.time, midi: STRING_MIDI[n.string] + (offs[n.string] || 0) + n.fret });
    if (tRec > maxT) maxT = tRec;
  }
  if (!events.length) return null;
  const dur = maxT + 1.2;
  const OACtx = window.OfflineAudioContext || window.webkitOfflineAudioContext;
  const octx = new OACtx(1, Math.ceil(dur * sr), sr);
  const NOTE_LEN = 0.28;
  // The synthesized source carries the preview tone too, following the tones
  // marked on the score (per-note) when '__follow__' is selected.
  for (const ev of events)
    voiceNote(octx, octx.destination, midiToHz(ev.midi), ev.t, NOTE_LEN, 0.5,
      toneCharForNote(ev.chartT));
  return await octx.startRendering();
}

// ---- Fretboard (guitar neck) that lights up each note's (string, fret) as it
// plays, like Guitar Pro's fretboard view. Static neck is drawn once per
// showArr; a small overlay group is refreshed each frame with the active notes.
let fretboardOn = true;
const FB = { frets: 24, fw: 26, sh: 20, x0: 46, y0: 14 };
function fretXY(string, fret) {
  const y = FB.y0 + (5 - string) * FB.sh;             // string 5 (high e) on top
  const x = fret <= 0 ? FB.x0 - 6 : FB.x0 + (fret - 0.5) * FB.fw;  // open note at the nut
  return { x, y };
}
let _lastFretHTML = null;  // skip redundant #fretOverlay innerHTML churn (see updateFretboard)
function drawFretboard() {
  const svg = document.getElementById('fretboard');
  if (!svg) return;
  const wrap = document.getElementById('fretboardWrap');
  if (wrap) wrap.style.display = fretboardOn ? '' : 'none';
  if (!fretboardOn) { svg.innerHTML = ''; return; }
  const neckH = 5 * FB.sh, top = FB.y0, bottom = FB.y0 + neckH;
  const W = FB.x0 + FB.frets * FB.fw + 14, H = bottom + 26;
  svg.setAttribute('width', W); svg.setAttribute('height', H);
  const a = arrangements[currentArr];
  const offs = (a && a.tuning_offsets) || [0, 0, 0, 0, 0, 0];
  let s = `<rect x="${FB.x0}" y="${top}" width="${FB.frets * FB.fw}" height="${neckH}" fill="#3a2e24"/>`;
  const dot = (f, cy) => `<circle cx="${FB.x0 + (f - 0.5) * FB.fw}" cy="${cy}" r="4" fill="#6b5b4a"/>`;
  for (const f of [3, 5, 7, 9, 15, 17, 19, 21]) s += dot(f, top + neckH / 2);
  for (const f of [12, 24]) s += dot(f, top + neckH * 0.3) + dot(f, top + neckH * 0.7);  // octave markers
  for (const f of [3, 5, 7, 9, 12, 15, 17, 19, 21, 24])
    s += `<text x="${FB.x0 + (f - 0.5) * FB.fw}" y="${bottom + 16}" fill="#7d8aa5" font-size="10" text-anchor="middle">${f}</text>`;
  for (let f = 0; f <= FB.frets; f++) {
    const x = FB.x0 + f * FB.fw;
    s += `<line x1="${x}" y1="${top}" x2="${x}" y2="${bottom}" stroke="${f === 0 ? '#e8e8e8' : '#59606d'}" stroke-width="${f === 0 ? 4 : 1.5}"/>`;
  }
  for (let i = 0; i < 6; i++) {
    const y = FB.y0 + (5 - i) * FB.sh;
    s += `<line x1="${FB.x0}" y1="${y}" x2="${FB.x0 + FB.frets * FB.fw}" y2="${y}" stroke="#9aa1ae" stroke-width="${1 + (5 - i) * 0.35}"/>`;
    s += `<text x="${FB.x0 - 16}" y="${y + 4}" fill="${STRING_COLORS[i]}" font-size="12" font-weight="700" text-anchor="middle">${stringLabel(i, offs)}</text>`;
  }
  s += `<g id="fretOverlay"></g>`;
  svg.innerHTML = s;
  _lastFretHTML = null;  // overlay was just recreated empty — force the next fill
}
function updateFretboard(vtDisp, warp) {
  if (!fretboardOn) return;
  const ov = document.getElementById('fretOverlay');
  if (!ov) return;
  const notes = arrangements[currentArr] ? arrangements[currentArr].notes : [];
  warp = warp || buildTimeWarp(syncAnchors);  // reuse the frame's warp when given
  const ratio = tempoScaleLive / builtScale;
  let s = '';
  for (const n of notes) {
    if (n.string < 0 || n.string > 5 || n.fret < 0 || n.fret > FB.frets) continue;
    const on = warp(previewScale(n.time));
    const dur = Math.max((n.sustain || 0) * ratio, 0.16);  // light for the note's duration
    if (vtDisp < on - 0.03 || vtDisp > on + dur) continue;
    const { x, y } = fretXY(n.string, n.fret);
    s += `<circle cx="${x}" cy="${y}" r="9" fill="${STRING_COLORS[n.string]}" stroke="#fff" stroke-width="1.5"/>`;
    s += `<text x="${x}" y="${y + 4}" fill="#14151a" font-size="11" font-weight="700" text-anchor="middle">${n.fret}</text>`;
  }
  // At 60fps the set of currently-lit notes is unchanged across most frames;
  // only re-parse the overlay's DOM when the markup actually differs.
  if (s !== _lastFretHTML) { ov.innerHTML = s; _lastFretHTML = s; }
}
document.getElementById('showFretboard')?.addEventListener('change', e => {
  fretboardOn = e.target.checked;
  drawFretboard();
  if (fretboardOn) updateFretboard(playheadDisplay(audioTime()));
});

// Live BPM readout: the tempo of the measure under the playhead, measured on the
// beat spacing AS DISPLAYED — the built spacing (so it shows the score's real
// 93/186, switching exactly at the tempo-change bars) run through the pending
// tempo_scale and anchors, so it reads what you actually hear right now. Taking
// the raw interval instead made the label ignore every pending correction, and
// fed the re-tempo tool a reference tempo the chart was no longer playing at.
function liveInfoAtTime(vtDisp, warp) {
  const a = arrangements[currentArr];
  if (!a || !a.beats || a.beats.length < 2) return null;
  warp = warp || buildTimeWarp(syncAnchors);
  let idx = 0;
  for (let i = 0; i < a.beats.length - 1; i++) {
    if (warp(previewScale(a.beats[i])) <= vtDisp) idx = i; else break;
  }
  const iv = warp(previewScale(a.beats[idx + 1])) - warp(previewScale(a.beats[idx]));
  const bpm = iv > 0.01 ? 60 / iv : null;
  let measure = null;
  for (const b of (a.bars || [])) { if (b.time <= a.beats[idx] + 1e-6) measure = b.measure; else break; }
  return { bpm, measure };
}
function updateLiveBpm(vtDisp, warp) {
  const el = document.getElementById('liveBpm');
  if (!el) return;
  const info = liveInfoAtTime(vtDisp, warp);
  el.textContent = info && info.bpm ? `♩ = ${Math.round(info.bpm)}${info.measure ? ` · c.${info.measure}` : ''}` : '';
  updateLiveTone(vtDisp, warp);
}

// The tone key active at a display-time position, following the tones marked on
// the score (change markers are in chart time → warped to display like notes).
function activeToneKeyAtDisplay(vtDisp, warp) {
  warp = warp || buildTimeWarp(syncAnchors);
  let key = toneBase || toneNames[0] || (jobTones[0] && jobTones[0].key) || null;
  for (const c of toneChanges) {  // already time-sorted (see loadTones)
    if (warp(previewScale(c.time)) <= vtDisp) key = c.name; else break;
  }
  return key;
}

// The live "tom atual" label: which created tone plays at the playhead. Shown
// only when the song actually has tones assigned (a base or a change).
function updateLiveTone(vtDisp, warp) {
  const el = document.getElementById('liveTone');
  if (!el) return;
  if (!jobTones.length || !(toneBase || toneChanges.length)) { el.textContent = ''; return; }
  const key = activeToneKeyAtDisplay(vtDisp, warp);
  const name = key ? ((jobTones.find(t => t.key === key) || {}).name || key) : null;
  el.innerHTML = name ? `${icon('wave')}${esc(name)}` : '';
}

// ---- Stand-alone arrangement preview (synthesized from the chart, no
// recording) — lets the user audition the experimental Lead/Rhythm split in
// isolation. ----
let previewOscillators = [];
let previewStopTimer = null;

function stopArrangementPreview() {
  if (audioCtx) {
    const t = audioCtx.currentTime;
    for (const osc of previewOscillators) {
      try { osc.stop(t); } catch { /* already stopped */ }
    }
  }
  previewOscillators = [];
  if (previewStopTimer) { clearTimeout(previewStopTimer); previewStopTimer = null; }
  const btn = document.getElementById('previewArr');
  if (btn) btn.textContent = '▶ Pré-visualizar este arranjo';
}

function playArrangementPreview() {
  if (previewOscillators.length) { stopArrangementPreview(); return; }
  const a = arrangements[currentArr];
  if (!a || !a.notes.length) return;
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  audioCtx.resume();
  const t0 = audioCtx.currentTime + 0.1;
  for (const n of a.notes) {
    if (n.string < 0 || n.string > 5 || n.fret < 0) continue;
    const midi = STRING_MIDI[n.string] + (a.tuning_offsets[n.string] || 0) + n.fret;
    const hz = midiToHz(midi);
    const start = t0 + n.time;
    const dur = Math.min(Math.max(n.sustain || 0.12, 0.12), 2);
    const osc = audioCtx.createOscillator(), g = audioCtx.createGain();
    osc.frequency.value = hz;
    g.gain.setValueAtTime(0.0001, start);
    g.gain.exponentialRampToValueAtTime(Math.max(0.0001, tickGain), start + 0.005);
    g.gain.exponentialRampToValueAtTime(0.0001, start + dur);
    osc.connect(g); g.connect(audioCtx.destination);
    osc.start(start); osc.stop(start + dur + 0.02);
    previewOscillators.push(osc);
  }
  const totalMs = (Math.max(...a.notes.map(n => n.time + (n.sustain || 0))) + 0.6) * 1000;
  document.getElementById('previewArr').textContent = '■ Parar pré-visualização';
  previewStopTimer = setTimeout(stopArrangementPreview, totalMs);
}
document.getElementById('previewArr').addEventListener('click', playArrangementPreview);


// Preview where a chart time (already shifted to the built timeline, optionally
// sync-warped) would land on rebuild with the current live offset and tempo:
// the musical part (time past the built lead-in) is rescaled by
// tempoScaleLive/builtScale, then re-anchored to the new lead-in
// (max(offset_s, MIN_LEAD_S) — see gp_pipeline). The waveform stays fixed
// (it's the audio reference), so notes slide over it as these change.
// GP jobs sync the chart to the recording (offset/tempo/lead-in); audio-ML jobs
// have notes transcribed FROM the recording, so their times ARE recording time
// — no shifting, the viewer just draws/plays them straight.
function isGpJob() { return !!selectedJob && selectedJob.source_type === 'gp'; }

// Mirror of the backend's score shift: parse-time tempo_scale + the shift the
// build applies (max(offset, MIN_LEAD) + lead_in). Both halves must match
// gp_pipeline exactly, or the preview and the rebuild disagree by a constant.
// lead_in_s has no live control (commit-on-rebuild), so the built value is the
// live value.
function previewScale(t) {
  if (!isGpJob()) return t;  // audio-ML: raw recording-time positions
  const ratio = tempoScaleLive / builtScale;
  return (t - scoreShift) * ratio + Math.max(offsetLive, MIN_LEAD) + leadInBuilt;
}

// Audio→display mapping for the playhead: audio time s appears after the
// prepended silence (pad = max(0, MIN_LEAD - offset)); independent of tempo
// since the recording itself is the fixed reference.
function playheadDisplay(s) {
  if (!isGpJob()) return s;  // audio-ML: playhead is straight recording time
  return s + Math.max(0, MIN_LEAD - offsetLive);
}

// The x-axis is drawn in *recording* time (0s at the far left), while all the
// time math (previewScale, anchors, backend) stays in bundle time. viewOrigin
// is the bundle time that sits at the left edge — the lead-in silence — so the
// playhead starts at 0 instead of jumping in at the first note.
let viewOrigin = 0;
function timeToX(t) { return 30 + (t - viewOrigin) * tabPx; }
function xToTime(x) { return (x - 30) / tabPx + viewOrigin; }

// --- Web Audio transport (sample-accurate; <audio> element is the fallback) ---
function audioDuration() {
  if (playBuffer) return playBuffer.duration;
  const au = document.getElementById('syncAudio');
  return au && isFinite(au.duration) ? au.duration : (waveDuration || 0);
}

// Current recording time in seconds (0-based, un-padded) — the exact analogue
// of the old <audio>.currentTime, consumed by syncFrame/syncResetPointer.
function audioTime() {
  if (playBuffer)
    return playing
      ? playStartOffset + (audioCtx.currentTime - playStartCtx) * playbackRate
      : pausedAt;
  const au = document.getElementById('syncAudio');
  return au ? au.currentTime : 0;
}

function audioIsPlaying() {
  if (playBuffer) return playing;
  const au = document.getElementById('syncAudio');
  return !!au && !au.paused && !au.ended;
}

function startSyncLoop() {
  if (!syncRaf) syncRaf = requestAnimationFrame(syncFrame);
}

function onSourceEnded() {
  // Natural end only — manual stop()s clear onended first, so this never fires
  // for pause/seek. Park the transport at the end.
  playing = false;
  playSource = null;
  playFade = null;
  pausedAt = audioDuration();
  updatePlayBtn();
  updateTransportUI();
}

// Stop the current music source WITHOUT a click: fade its gain to 0 over
// AUDIO_FADE_S, then stop it just after the ramp (a hard stop() mid-waveform
// pops). onended is cleared first so this manual stop never triggers the
// natural-end handler. Detaches playSource/playFade immediately so callers can
// start a fresh source right away (the tails overlap into a clean crossfade).
function stopMusicSource() {
  if (!playSource) return;
  const src = playSource, fade = playFade;
  src.onended = null;
  const now = audioCtx ? audioCtx.currentTime : 0;
  if (fade && audioCtx) {
    try {
      fade.gain.cancelScheduledValues(now);
      fade.gain.setValueAtTime(fade.gain.value, now);
      fade.gain.linearRampToValueAtTime(0, now + AUDIO_FADE_S);
    } catch {}
    try { src.stop(now + AUDIO_FADE_S + 0.01); } catch {}
  } else {
    try { src.stop(); } catch {}
  }
  playSource = null;
  playFade = null;
}

function audioPlay() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  audioCtx.resume();
  if (!playGain) {
    playGain = audioCtx.createGain();
    playGain.connect(audioCtx.destination);
    const vol = parseFloat(document.getElementById('musicVolume')?.value || '1');
    playGain.gain.value = vol;
  }
  if (playBuffer) {
    if (playing) return;
    playSource = audioCtx.createBufferSource();
    playSource.buffer = playBuffer;
    playSource.playbackRate.value = playbackRate;
    // Route through a per-source fade gain and ramp it up, so the attack at the
    // seek offset doesn't click (see AUDIO_FADE_S).
    playFade = audioCtx.createGain();
    const t0 = audioCtx.currentTime;
    playFade.gain.setValueAtTime(0, t0);
    playFade.gain.linearRampToValueAtTime(1, t0 + AUDIO_FADE_S);
    playSource.connect(playFade);
    playFade.connect(playGain);
    playStartOffset = Math.min(Math.max(0, pausedAt), playBuffer.duration);
    playStartCtx = t0;
    playSource.onended = onSourceEnded;
    playSource.start(0, playStartOffset);
    playing = true;
  } else {
    const au = document.getElementById('syncAudio');
    if (au && au.src) { au.playbackRate = playbackRate; au.play(); }
  }
  startSyncLoop();
  updatePlayBtn();
}

function audioPause() {
  if (playBuffer) {
    if (!playing) return;
    pausedAt = audioTime();   // capture position before fading/stopping the source
    stopMusicSource();
    playing = false;
  } else {
    const au = document.getElementById('syncAudio');
    if (au) au.pause();
  }
  updatePlayBtn();
}

function audioToggle() {
  if (audioIsPlaying()) audioPause(); else audioPlay();
}

// SPACE = play/pause, like a media player. Ignored while typing (inputs,
// selects, editable text) so it doesn't hijack a real space character, and
// only when a job viewer with playback is open.
// Tab-viewer keyboard shortcuts (only while the sync panel is open and no text
// field is focused): Space play/pause, ←/→ scrub (Shift = bigger step), Home to
// the start, +/- zoom. Seeks go through audioSeek in recording-time, so they
// move the playhead visually even while paused.
document.addEventListener('keydown', e => {
  const el = document.activeElement;
  const tag = el && el.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (el && el.isContentEditable)) return;
  if (!selectedJob) return;
  const panel = document.getElementById('syncPanel');
  if (!panel || panel.style.display === 'none') return;
  if (e.code === 'Space' || e.key === ' ') {
    e.preventDefault();               // stop the page from scrolling on space
    if (tag === 'BUTTON') el.blur();  // don't let a focused button also fire on space
    audioToggle();
  } else if (e.key === 'ArrowRight') {
    e.preventDefault(); audioSeek(currentPlayheadT + (e.shiftKey ? 5 : 1));
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault(); audioSeek(Math.max(0, currentPlayheadT - (e.shiftKey ? 5 : 1)));
  } else if (e.key === 'Home') {
    e.preventDefault(); audioSeek(0);
  } else if (e.key === '+' || e.key === '=') {
    e.preventDefault(); setZoom(zoomLevel * 1.5);
  } else if (e.key === '-' || e.key === '_') {
    e.preventDefault(); setZoom(zoomLevel / 1.5);
  } else if ((e.ctrlKey || e.metaKey) && (e.key === 'c' || e.key === 'C') && isGpJob()) {
    e.preventDefault(); copySelectedNotes();
  } else if ((e.ctrlKey || e.metaKey) && (e.key === 'v' || e.key === 'V') && isGpJob()) {
    e.preventDefault(); pasteNotesAtCursor();
  }
});

// Hard stop used on job switch / detail close — no UI resume implied.
function stopPlayback() {
  stopMusicSource();
  playing = false;
  const au = document.getElementById('syncAudio');
  if (au) { try { au.pause(); } catch {} }
  if (syncRaf) { cancelAnimationFrame(syncRaf); syncRaf = null; }
}

function audioSeek(t) {
  t = Math.max(0, Math.min(t, audioDuration() || t));
  if (playBuffer) {
    const was = playing;
    if (playing) stopMusicSource();  // fade the outgoing source out (no seek click)
    playing = false;
    pausedAt = t;
    if (was) audioPlay();            // new source fades in → clean crossfade
  } else {
    const au = document.getElementById('syncAudio');
    if (au) au.currentTime = t;
  }
  seekPreview(t);
  syncResetPointer();
  updateTransportUI();
}

// Move the playhead + tick pointer to recording time t without touching audio
// transport — used both by audioSeek and live while dragging the seek bar.
function seekPreview(t) {
  const vt = playheadDisplay(t);
  currentPlayheadT = vt - viewOrigin;
  const ph = document.getElementById('playhead');
  if (ph) { const x = timeToX(vt); ph.setAttribute('x1', x); ph.setAttribute('x2', x); }
  updateFretboard(vt);  // scrubbing/pausing lights the neck at the cursor too
  updateLiveBpm(vt);
}

function fmtClock(s) {
  if (!isFinite(s) || s < 0) s = 0;
  const m = Math.floor(s / 60), sec = Math.floor(s % 60);
  return `${m}:${sec < 10 ? '0' : ''}${sec}`;
}

function updatePlayBtn() {
  const b = document.getElementById('playBtn');
  if (b) b.innerHTML = icon(audioIsPlaying() ? 'pause' : 'play');
}

function updateTransportUI() {
  const bar = document.getElementById('seekBar'), lbl = document.getElementById('timeLabel');
  const dur = audioDuration(), t = audioTime();
  if (bar) {
    bar.max = dur || 0;
    if (!seekDragging) bar.value = Math.min(t, dur || t);
  }
  if (lbl) lbl.textContent = `${fmtClock(t)} / ${fmtClock(dur)}`;
}

// Lyric-word highlight targets, resolved ONCE per score redraw instead of on
// every animation frame (showArr replaces the whole SVG, so the cache is
// invalidated there). `active` memoises the last state so a frame that changes
// nothing writes no attributes at all.
let _lyricWords = null;
function invalidateLyricWords() { _lyricWords = null; }
function lyricWordCache() {
  if (_lyricWords) return _lyricWords;
  _lyricWords = Array.from(document.querySelectorAll('.lyric-word'), lw => ({
    li: parseInt(lw.dataset.li, 10),
    txt: lw.querySelector('text'),
    ln: lw.querySelector('line'),
    active: null,
  }));
  return _lyricWords;
}

function syncResetPointer() {
  // Compare in display coordinates so the ticks follow the live preview
  // (tempo/offset/anchors), making alignment audible without a rebuild.
  const vt = playheadDisplay(audioTime());
  const notes = arrangements[currentArr] ? arrangements[currentArr].notes : [];
  const warp = buildTimeWarp(syncAnchors);
  tickIdx = notes.findIndex(n => warp(previewScale(n.time)) >= vt);
  if (tickIdx < 0) tickIdx = notes.length;
}

function syncFrame() {
  const ph = document.getElementById('playhead');
  if (!ph) { syncRaf = null; return; }
  // Playhead tracks the audio (and thus the waveform). It stays in audio
  // coordinates; tempo preview moves the notes over it, not the other way.
  const vtDisp = playheadDisplay(audioTime());  // bundle time (for tick compare)
  currentPlayheadT = vtDisp - viewOrigin;  // recording-time offset; used by showArr + tap-sync
  const x = timeToX(vtDisp);  // recording-time x — cursor sits at 0 when audio is at 0
  // Keep the view aligned with the music while playing — the waveform/notes
  // scroll under a centered playhead. syncFrame only runs while playing, so
  // when paused the view stays put and the user can scroll/inspect freely.
  // READ clientWidth BEFORE writing the playhead attributes: writing first
  // dirties layout, so the read forced a synchronous relayout of a SVG that can
  // be tens of thousands of px wide with ~10k children — every single frame.
  const wrap = document.getElementById('tabwrap');
  const halfView = wrap.clientWidth / 2;
  ph.setAttribute('x1', x); ph.setAttribute('x2', x);
  wrap.scrollLeft = Math.max(0, x - halfView);
  updateTransportUI();
  const notes = arrangements[currentArr] ? arrangements[currentArr].notes : [];
  const tickOn = document.getElementById('syncTick').checked;
  const warp = buildTimeWarp(syncAnchors);
  // Fire each note's tick when the playhead reaches its *previewed* display
  // position, so live tempo/offset/anchor edits are immediately audible.
  const arrNow = arrangements[currentArr];
  const offs = (arrNow && arrNow.tuning_offsets) || [0, 0, 0, 0, 0, 0];
  // Cap how many overdue ticks one frame may sound. playNote schedules at
  // audioCtx.currentTime ("now"), so if the main thread stalled (a redraw, GC),
  // draining the whole backlog started every missed note at the SAME sample
  // instant — a dozen summed voices clip the output as an audible burst of
  // noise. Past the cap the notes are skipped (tickIdx still advances) so the
  // tick stays in sync instead of machine-gunning the backlog.
  let sounded = 0;
  while (tickIdx < notes.length && warp(previewScale(notes[tickIdx].time)) <= vtDisp) {
    if (tickOn && sounded < MAX_TICKS_PER_FRAME) {
      const note = notes[tickIdx];
      if (note.string >= 0 && note.string <= 5 && note.fret >= 0) {
        playNote(STRING_MIDI[note.string] + (offs[note.string] || 0) + note.fret, note.time);
        sounded++;
      }
    }
    tickIdx++;
  }
  updateFretboard(vtDisp, warp);  // light up the notes sounding right now on the neck
  updateLiveBpm(vtDisp, warp);    // real-time BPM of the current measure
  // Highlight the lyric word under the playhead without redrawing the full SVG.
  // currentPlayheadT is the padded display time; lyric times are un-padded, so
  // shift them by leadInBuilt to compare in the same timeline.
  const recT = currentPlayheadT;
  // Cached per redraw (see showArr): re-running querySelectorAll + two
  // querySelector per word EVERY frame was ~1500 DOM queries per 16 ms on a
  // 500-word song. Also skipped entirely when the song has no lyrics.
  for (const w of lyricWordCache()) {
    const ev = lyricsEvents[w.li];
    if (!ev) continue;
    const active = recT >= ev.time + leadInBuilt && recT <= ev.time + ev.length + leadInBuilt;
    if (w.active === active) continue;  // only touch the DOM on a real change
    w.active = active;
    if (w.txt) {
      w.txt.setAttribute('fill', active ? '#ff7a45' : '#9aa0ad');
      w.txt.setAttribute('font-weight', active ? '700' : '400');
    }
    if (w.ln) w.ln.setAttribute('stroke', active ? '#ff7a45' : '#454852');
  }
  if (audioIsPlaying()) syncRaf = requestAnimationFrame(syncFrame);
  else { syncRaf = null; updatePlayBtn(); }
}

// rAF-coalesced full-score redraw: the live-preview sliders (tempo/offset) fire
// 'input' faster than the display refreshes, and each showArr() is a full SVG
// rebuild — so dragging them repaints many times per frame. Collapsing the
// edits within one frame into a single redraw removes the jank without changing
// the final drawn state (mirrors the note-drag path, which defers showArr to
// pointerup).
let _showArrRaf = null;
function requestShowArr() {
  if (_showArrRaf != null) return;
  _showArrRaf = requestAnimationFrame(() => {
    _showArrRaf = null;
    if (arrangements.length) showArr(currentArr);
  });
}

function setOffsetLive(v) {
  offsetLive = Math.max(0, v || 0);
  document.getElementById('syncOffset').value = offsetLive.toFixed(2);
  document.getElementById('syncOffsetRange').value = offsetLive;
  syncResetPointer();
  if (arrangements.length) showArr(currentArr);
  updatePendingChangesInfo();
}

function initSync(j) {
  const panel = document.getElementById('syncPanel');
  const isGp = j.source_type === 'gp';
  document.getElementById('detectTuningRow').style.display = isGp ? '' : 'none';
  document.getElementById('gpSyncControls').style.display = isGp ? '' : 'none';
  // The panel (playback + waveform) is shown for ALL job types; only the GP
  // sync controls (offset/tempo/anchors) are hidden for audio-ML jobs, whose
  // notes are already aligned to the recording they were transcribed from.
  panel.style.display = '';
  if (isGp) {
    // The offset (and thus the audio lead-in) is shared by all arrangements.
    // scoreShift must be the FULL built score shift the backend used —
    // max(offset_s, MIN_LEAD) + lead_in_s (gp_pipeline: score_shift = offset_s +
    // pad_start_s). Omitting lead_in_s here made previewScale un-shift by less
    // than the build shifted by, so any tempo change desynced the rebuild from
    // the preview by lead_in_s*(ratio-1) — a constant, in-game-only offset.
    leadInBuilt = j.lead_in_s || 0;
    scoreShift = Math.max(j.offset_s || 0, MIN_LEAD) + leadInBuilt;
    loadArrSync(0);  // tempo/anchors are per-arrangement; load the first tab's
  } else {
    // audio-ML: neutral sync so notes draw at their raw recording times.
    offsetLive = 0; leadInBuilt = 0; scoreShift = 0;
    tempoScaleLive = 1; builtScale = 1; syncAnchors = [];
  }
  // Reset the transport; decodeWaveform fills playBuffer for sample-accurate
  // playback (and falls back to the <audio> element if decode fails).
  stopPlayback();
  playBuffer = null; pausedAt = 0;
  document.getElementById('syncAudio').removeAttribute('src');
  currentPlayheadT = 0;
  if (isGp) {
    setOffsetLive(j.offset_s || 0);
    document.getElementById('leadInS').value = leadInBuilt.toFixed(1);
  }
  updatePlayBtn();
  updateTransportUI();
  // Reset the audio-source selection to the full mix SYNCHRONOUSLY, before
  // firing the two async calls below. decodeWaveform() and loadStems() both
  // run concurrently (neither is awaited) and loadStems() ALSO resets
  // audioSourceName once its own fetch resolves — without this, a stale
  // audioSourceName left over from a PREVIOUS job (e.g. "synth:Lead") could
  // still be set when decodeWaveform() reads it, so it decodes a synthesized
  // buffer; loadStems() then resets the dropdown back to "Mistura completa"
  // without re-decoding, leaving the synth buffer silently playing under a
  // selector that reads the full mix. Setting it here first closes that race.
  audioSourceName = '';
  const audioSourceSel = document.getElementById('audioSource');
  if (audioSourceSel) audioSourceSel.value = '';
  decodeWaveform(j.id);
  loadStems(j.id);
}

// Swap the per-arrangement sync state (tempo scale + pending drift anchors)
// into the live globals when the active tab changes. Does NOT redraw — the
// caller (showArr) renders right after.
function loadArrSync(i) {
  // Save the current arrangement's pending tempo before switching away.
  const prev = arrangements[currentArr];
  if (prev && Math.abs(tempoScaleLive - (prev.tempo_scale || 1)) > 0.0001) {
    tempoScaleByKind[prev.kind] = tempoScaleLive;
  }
  const a = arrangements[i];
  if (!a) return;
  builtScale = a.tempo_scale || 1;
  gpBpm = a.average_bpm ? a.average_bpm * builtScale : 0;
  tempoScaleLive = (a.kind in tempoScaleByKind) ? tempoScaleByKind[a.kind] : builtScale;
  syncAnchors = syncAnchorsByKind[a.kind] || (syncAnchorsByKind[a.kind] = []);
  updateTempoControls();
}

// Reflect tempoScaleLive in the BPM / % / range controls (no redraw).
function updateTempoControls() {
  const bpmEl = document.getElementById('tempoBpm');
  const rangeEl = document.getElementById('tempoRange');
  const pctEl = document.getElementById('tempoPct');
  if (gpBpm > 0) {
    const bpm = gpBpm / tempoScaleLive;
    bpmEl.value = bpm.toFixed(1);
    rangeEl.value = bpm;
  }
  // % of the GP's authored tempo (100% = unchanged; <100% = slower/stretched)
  pctEl.textContent = `${Math.round(100 / tempoScaleLive)}% do andamento do GP`;
}

// Set the previewed tempo scale for the CURRENT arrangement and redraw.
function setTempoLive(scale) {
  tempoScaleLive = Math.min(4, Math.max(0.25, scale || 1));
  const kind = currentKind();
  if (kind) tempoScaleByKind[kind] = tempoScaleLive;
  updateTempoControls();
  // Slider-driven: coalesce the expensive redraw to one per frame (the numeric
  // readouts above stay synchronous). syncResetPointer must run now so the tick
  // pointer is correct before the next frame's draw.
  if (arrangements.length) { syncResetPointer(); requestShowArr(); }
  updatePendingChangesInfo();
}

(function wireTempoControls() {
  const bpmEl = document.getElementById('tempoBpm');
  const rangeEl = document.getElementById('tempoRange');
  if (!bpmEl) return;
  const fromBpm = b => { if (gpBpm > 0 && b > 0) setTempoLive(gpBpm / b); };
  bpmEl.addEventListener('input', e => fromBpm(parseFloat(e.target.value)));
  rangeEl.addEventListener('input', e => fromBpm(parseFloat(e.target.value)));
  document.getElementById('tempoReset').addEventListener('click', () => setTempoLive(1));
})();

// Pin the CURRENT arrangement's first note to a target recording second as a
// pending anchor (a single anchor = a uniform shift for that arrangement's
// whole chart — see ArrangementSync in gp_pipeline.py). This is what Step 1
// ("Início da música") now writes for every edit — never the job-level
// offsetLive — so the start is independent per track. origT is the UNwarped
// previewScale position (like 'drag' mode, not 'tap' mode) so repeated calls
// from the slider/number field update the same anchor instead of compounding.
function setTrackStart(v) {
  const chartT = currentArrFirstNoteTime();
  if (chartT == null) return;
  const origT = previewScale(chartT);
  setAnchor(origT, Math.max(0, v) + viewOrigin);
  renderAnchorsList();
  updatePendingChangesInfo();
  requestShowArr();  // slider-driven: coalesce the redraw to one per frame
}

// Precisely place the CURRENT arrangement's first note. audioTime() is the
// sample-accurate, un-padded recording clock, so "Início = cursor" turns the
// live playhead into this track's start: scrub/click the waveform (zoom in
// for precision) or play to the first attack, then lock it. For a fine
// nudge, the "Segundo" number field steps by 0.01; or let onset detection
// propose a whole-job value via "✨ Sincronização automática" (Step 2).
(function wireFirstNoteTools() {
  const fromCursor = document.getElementById('offsetFromCursor');
  const detect = document.getElementById('detectFirstNote');
  const info = document.getElementById('firstNoteInfo');
  if (!fromCursor) return;

  fromCursor.addEventListener('click', () => {
    if (!isGpJob()) return;
    const t = audioTime();
    setTrackStart(t);
    info.textContent = `Início desta pista fixado na posição do cursor: ${t.toFixed(2)}s.`;
    toast('Início = posição do cursor', 'ok');
  });
  // (Fine ±0.01 nudges removed — the "Segundo" number field already steps by 0.01.)

  // Guided 3-click alignment: arm → click the waveform where the 1st note
  // sounds → click the 1st note to shift it (and all notes) there.
  detect.addEventListener('click', () => startFirstNoteFlow());
})();

(function wireDetectTuning() {
  const btn = document.getElementById('detectTuning');
  const info = document.getElementById('detectTuningInfo');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    if (!selectedJob) return;
    btn.disabled = true;
    info.textContent = 'A analisar a gravação…';
    try {
      const r = await fetch(`/jobs/${selectedJob.id}/detect-tuning`, { method: 'POST' });
      const b = await r.json();
      if (!r.ok) { info.textContent = ''; toast(b.detail || 'erro', 'err'); return; }
      centOffsetLive = b.suggested_cent_offset;
      const el = document.getElementById('centOffsetVal');
      if (el) el.textContent = centOffsetLive.toFixed(1);
      info.textContent =
        `Desvio detetado: ${b.suggested_cent_offset.toFixed(1)} cents. ` +
        `Aplica-se em "Aplicar e reconstruir". A afinação das cordas (drop/open) ` +
        `não é detetada — vem do ficheiro GP.`;
      toast('Afinação proposta — revê e aplica', 'ok');
    } catch {
      info.textContent = '';
      toast('falha na análise', 'err');
    } finally {
      btn.disabled = false;
    }
  });
})();

// Fetch + decode the recording into peak bins (max |amplitude| per 1/WAVE_HZ s)
// so the tab viewer can draw a waveform under the notes for visual alignment.
async function decodeWaveform(id) {
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    let audio;
    if (audioSourceName.startsWith('synth:')) {
      // A synthesized reference of one arrangement's notes (Lead/Rhythm),
      // rendered at the notes' current on-screen positions — no recording, so
      // no lead-in padding (the lead-in is already baked into the note times).
      audio = await synthesizeArrangement(audioSourceName.slice(6));
      if (!audio) {
        wavePeaks = null; playBuffer = null; waveDuration = 0;
        updateTransportUI();
        if (arrangements.length) showArr(currentArr);
        return;
      }
    } else {
      // The audio-source selector can swap the full mix for an isolated Demucs
      // stem (guitar/bass/…) so the user hears the notes more clearly while
      // fine-tuning sync. Stems share the recording clock, so the notes line up.
      const url = audioSourceName
        ? `/jobs/${id}/stem/${encodeURIComponent(audioSourceName)}`
        : `/jobs/${id}/source-audio`;
      const buf = await (await fetch(url)).arrayBuffer();
      audio = await audioCtx.decodeAudioData(buf);
      // Reflect the user's intro silence (lead_in_s) the bundle was built with:
      // prepend that much silence to the decoded buffer so the waveform shows it,
      // the notes sit after it, and playback runs through the silence first.
      if (leadInBuilt > 0) {
        const sr = audio.sampleRate, pad = Math.round(leadInBuilt * sr);
        const padded = audioCtx.createBuffer(audio.numberOfChannels, pad + audio.length, sr);
        for (let c = 0; c < audio.numberOfChannels; c++)
          padded.getChannelData(c).set(audio.getChannelData(c), pad);
        audio = padded;
      }
    }
    const ch = audio.getChannelData(0);
    const bins = Math.ceil(audio.duration * WAVE_HZ);
    const peaks = new Float32Array(bins);
    const per = audio.sampleRate / WAVE_HZ;
    for (let b = 0; b < bins; b++) {
      const start = Math.floor(b * per), end = Math.min(ch.length, Math.floor((b + 1) * per));
      let max = 0;
      for (let i = start; i < end; i++) { const v = Math.abs(ch[i]); if (v > max) max = v; }
      peaks[b] = max;
    }
    // normalize to the loudest peak so quiet recordings are still visible
    let gmax = 0;
    for (const p of peaks) if (p > gmax) gmax = p;
    if (gmax > 0) for (let b = 0; b < bins; b++) peaks[b] /= gmax;
    wavePeaks = peaks; waveDuration = audio.duration;
    playBuffer = audio;  // reuse the decoded buffer for sample-accurate playback
    updateTransportUI();
    if (arrangements.length) showArr(currentArr);
  } catch {
    // Unsupported codec etc.: skip the waveform and fall back to the <audio>
    // element for playback (seeking is then codec-imprecise, but it still plays).
    // A synthesized source has no URL, so there's nothing to fall back to.
    wavePeaks = null; playBuffer = null; waveDuration = 0;
    if (audioSourceName.startsWith('synth:')) { updateTransportUI(); return; }
    const au = document.getElementById('syncAudio');
    if (au) {
      au.preload = 'metadata';
      au.src = audioSourceName
        ? `/jobs/${id}/stem/${encodeURIComponent(audioSourceName)}`
        : `/jobs/${id}/source-audio`;
      au.onloadedmetadata = updateTransportUI;
    }
  }
}

// Build the waveform path data. The x-axis is recording time (0s at the left),
// so audio sample at display time s is just wavePeaks[s] — notes (placed by
// previewScale, mapped through timeToX) line up onto it as offset/tempo change.
function waveformPathData(W, px, H) {
  if (!wavePeaks) return '';
  const top = 14, bot = H - 59, mid = (top + bot) / 2, amp = (bot - top) / 2 * 0.92;
  let up = '', down = '';
  for (let x = 30; x <= W; x += 2) {
    const s = (x - 30) / px;  // recording time at this x
    let p = 0;
    if (s >= 0 && s < waveDuration) p = wavePeaks[Math.floor(s * WAVE_HZ)] || 0;
    up += `${x === 30 ? 'M' : 'L'}${x},${(mid - p * amp).toFixed(1)} `;
    down = `L${x},${(mid + p * amp).toFixed(1)} ` + down;
  }
  return up + down + 'Z';
}

// Colour + label the waveform by which audio source is playing, so it's obvious
// at a glance what you're hearing — the full mix, a separated stem, or a
// synthesized reference (a distinct colour per arrangement, so switching between
// "Lead (sintetizada)" and "Rhythm (sintetizada)" visibly changes the wave even
// though both are uniform-loudness blip forests).
function audioSourceStyle() {
  const n = audioSourceName;
  if (n.startsWith('synth:')) {
    const kind = n.slice(6);
    const palette = {
      Lead: '#a97bff', Rhythm: '#3fa7ff', Combo: '#ff8a5c',
      Combined: '#ff8a5c', Bass: '#5cc24a',
    };
    return { color: palette[kind] || '#a97bff', label: `${kind} (sintetizada)` };
  }
  if (n) return { color: '#3fb27f', label: STEM_LABELS[n] || n };
  return { color: '#2a6f97', label: 'Mistura completa' };
}

function waveformSvg(W, H, px) {
  if (!wavePeaks) return '';
  const st = audioSourceStyle();
  // A pill label near the top-left corner (time ~0) names the active source.
  const lw = st.label.length * 6.5 + 14;
  return (
    `<path id="wavepath" d="${waveformPathData(W, px, H)}" fill="${st.color}" opacity=".3"/>` +
    `<rect x="30" y="16" width="${lw.toFixed(0)}" height="17" rx="4" fill="#14151a" opacity=".72"/>` +
    `<circle cx="40" cy="24.5" r="4" fill="${st.color}"/>` +
    `<text x="48" y="28" fill="${st.color}" font-size="11" font-weight="700">${esc(st.label)}</text>`
  );
}


document.getElementById('syncOffset').addEventListener('input', e => setTrackStart(parseFloat(e.target.value) || 0));
document.getElementById('syncOffsetRange').addEventListener('input', e => setTrackStart(parseFloat(e.target.value) || 0));

// Seek bar: pause while scrubbing (so syncFrame doesn't fight the drag), preview
// the playhead live, and commit the seek + resume on release.
document.getElementById('seekBar').addEventListener('input', e => {
  if (!seekDragging) { seekDragging = true; seekWasPlaying = audioIsPlaying(); if (seekWasPlaying) audioPause(); }
  const t = parseFloat(e.target.value) || 0;
  pausedAt = t;
  seekPreview(t);
  const lbl = document.getElementById('timeLabel');
  if (lbl) lbl.textContent = `${fmtClock(t)} / ${fmtClock(audioDuration())}`;
});
document.getElementById('seekBar').addEventListener('change', e => {
  seekDragging = false;
  audioSeek(parseFloat(e.target.value) || 0);
  if (seekWasPlaying) audioPlay();
  seekWasPlaying = false;
});

// The tuning form no longer submits on its own — the single "Aplicar e
// reconstruir" button (applyAll) commits everything together.
document.getElementById('rebuildForm').addEventListener('submit', e => e.preventDefault());

let gpToken = null;

document.getElementById('gpInspectForm').addEventListener('submit', async e => {
  e.preventDefault();
  const r = await fetch('/gp/inspect', { method: 'POST', body: new FormData(e.target) });
  const b = await r.json();
  if (!r.ok) return toast(b.detail || 'erro');
  songsterrImported = false;
  applyInspectResult(b);
});

// Step 1's answer — from an uploaded file (/gp/inspect) or a tab built from
// Songsterr (/songsterr/import), which answers in the same shape.
function applyInspectResult(b) {
  gpToken = b.gp_token;
  const form = document.getElementById('gpJobForm');
  document.getElementById('gpMeta').textContent =
    `${b.title || '(sem título)'} — ${b.artist || '(sem banda)'} · ${b.tempo} BPM · letra no GP: ${b.has_lyrics ? 'sim' : 'não'}`;
  for (const name of ['lead_track', 'rhythm_track', 'combo_track', 'alt_lead_track', 'alt_rhythm_track']) {
    const sel = form.querySelector(`select[name=${name}]`);
    sel.innerHTML = '<option value="">—</option>' + b.tracks
      .filter(t => !t.is_percussion && t.string_count === 6)
      .map(t => `<option value="${t.index}">${t.index}: ${esc(t.name)}</option>`).join('');
  }
  // Auto-assign the first eligible track to Lead so step 2 has a sensible default.
  const firstTrack = (b.tracks || []).find(t => !t.is_percussion && t.string_count === 6);
  if (firstTrack) form.querySelector('select[name=lead_track]').value = String(firstTrack.index);
  if (b.title) form.querySelector('input[name=title]').value = b.title;
  if (b.artist) form.querySelector('input[name=artist]').value = b.artist;
  if (b.album) form.querySelector('input[name=album]').value = b.album;
  // Synced to an audio track in Guitar Pro 8: the file itself says where bar 1
  // is in that audio, so offer the exact value instead of asking for a guess.
  const embeddedRow = document.getElementById('gpEmbeddedAudioRow');
  embeddedRow.hidden = !b.embedded_audio;
  document.getElementById('useEmbeddedAudio').checked = !!b.embedded_audio;
  document.getElementById('gpEmbeddedAudioInfo').textContent = b.embedded_audio
    ? `(${b.embedded_audio.name}, ${(b.embedded_audio.size_bytes / 1048576).toFixed(1)} MB)` : '';
  applyEmbeddedAudioChoice();
  const syncHint = document.getElementById('gpSyncHint');
  if (b.sync_start_s != null) {
    form.querySelector('input[name=offset_s]').value = b.sync_start_s.toFixed(3);
    syncHint.textContent = `Este ficheiro foi sincronizado com o áudio no Guitar Pro 8 — o compasso 1 começa em ${b.sync_start_s.toFixed(3)} s desse áudio. ` +
      (b.embedded_audio
        ? 'Com o áudio do ficheiro GP (acima) o valor já está certo e as notas seguem o tempo variável do GP.'
        : 'Se a gravação que carregas é esse mesmo ficheiro de áudio, o valor já está certo e as notas seguem o tempo variável do GP.');
    syncHint.hidden = false;
  } else {
    syncHint.hidden = true;
  }
  setWizardStep(2);  // advance the wizard now that inspection succeeded
}

// "… ou importa a tab do Songsterr": the tab is rebuilt as a GP5 on the server
// and the wizard continues exactly as with an uploaded file. The same link
// then feeds step 3's Songsterr bar times — the tab and the times come from the
// same song, which is what makes measure N the same in both.
let songsterrImported = false;
async function importSongsterrTab() {
  const link = document.getElementById('songsterrImportLink').value.trim();
  const info = document.getElementById('songsterrImportInfo');
  const btn = document.getElementById('songsterrImportBtn');
  if (!link) { toast('Cola o link da música no Songsterr.'); return; }
  btn.disabled = true;
  info.textContent = 'A descarregar a tab do Songsterr e a criar o ficheiro Guitar Pro…';
  let b;
  try {
    b = await getJSON('/songsterr/import', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ song: link }),
    });
  } catch (err) {
    info.textContent = `Não consegui importar: ${err.message}`;
    return;
  } finally {
    btn.disabled = false;
  }
  info.textContent = b.import_warnings && b.import_warnings.length
    ? `Importada, com avisos: ${b.import_warnings.join('; ')}.` : 'Tab importada.';
  songsterrImported = true;
  applyInspectResult(b);
  // Step 3: the same song's per-measure times, ready to pick a video.
  document.getElementById('songsterrLink').value = link;
  document.getElementById('songsterrBlock').open = true;
  // …and the chosen video's audio, so the whole song comes from one link.
  if (await fetchSongsterrVideos()) downloadYtAudio();
}
document.getElementById('songsterrImportBtn').addEventListener('click', importSongsterrTab);
document.getElementById('songsterrImportLink').addEventListener('keydown', e => {
  // Inside step 1's form, Enter would submit the file inspect instead.
  if (e.key === 'Enter') { e.preventDefault(); importSongsterrTab(); }
});

document.getElementById('gpJobForm').addEventListener('submit', async e => {
  e.preventDefault();
  // Enter on an earlier step submits the shared form — treat it as "Seguinte"
  // so the job is only created from the final step.
  if (wizardStep < WIZARD_MAX) {
    if (validateWizardStep()) setWizardStep(wizardStep + 1);
    return;
  }
  // The form is `novalidate` because the browser's own check is silent here:
  // it refuses a bad field on an EARLIER (hidden) step without showing it, so
  // "Criar CDLC" just did nothing — a start time pre-filled with 3 decimals
  // against step="0.01" did exactly that. Take the user to the field instead.
  const bad = e.target.querySelector(':invalid');
  if (bad) {
    const pane = bad.closest('.wizard-pane');
    if (pane) setWizardStep(Number(pane.dataset.step));
    bad.reportValidity();
    return;
  }
  const f = new FormData(e.target);
  f.append('gp_token', gpToken);
  if (usingEmbeddedAudio()) { f.set('use_embedded_audio', 'true'); f.delete('audio'); }
  else {
    f.set('use_embedded_audio', 'false');
    if (ytAudio) { f.set('audio_token', ytAudio.token); f.delete('audio'); }
  }
  if (songsterrPoints) {
    f.set('bar_times', JSON.stringify(songsterrPoints));
    f.set('bar_times_source', `songsterr:${songsterrSong.song_id}:${songsterrSong.revision_id}`);
  }
  // Unchecked checkboxes are not sent; set the value explicitly so "off" sticks.
  f.set('import_mutes', e.target.querySelector('input[name=import_mutes]').checked);
  // The picked card's image never loaded: its cover is not there to download.
  const picked = wzAlbumCandidates[wzAlbumPick];
  if (picked && picked.cover_broken) f.delete('cover_url');
  const r = await fetch('/jobs/gp', { method: 'POST', body: f });
  const b = await r.json();
  if (!r.ok) { toast(b.detail || 'erro'); return; }
  // The cover is downloaded while the job is created; a failure there must
  // not lose the project, so it is reported here instead.
  if (f.get('cover_url') && !b.cover_art)
    toast('Projeto criado, mas não consegui descarregar a capa — escolhe outra na página Capa.');
  else toast('Projeto criado.', 'ok');
  closeNewJobModal();
  selectJob(b.id);
});

refreshJobs();
setInterval(refreshJobs, 5000);

// Local single-user setups (start.bat): tell the API this tab is still open so
// it can shut itself (and the worker/Redis it launched) down once the tab is
// CLOSED. A backgrounded/minimised tab has its timers throttled/frozen, so we
// mark it hidden (Page Visibility) — the server then suspends the idle-kill and
// only a real close (/closing beacon) stops it. No-op if idle_shutdown_s unset.
function ping(hidden) {
  const url = '/heartbeat' + (hidden ? '?hidden=1' : '');
  // A hidden tab may be frozen mid-fetch — sendBeacon is delivered reliably.
  if (hidden) { try { if (navigator.sendBeacon(url)) return; } catch {} }
  fetch(url, { method: 'POST' }).catch(() => {});
}
setInterval(() => ping(document.hidden), 4000);
ping(false);
// Fire immediately on tab hide/show and on wake/bfcache-restore, so the server
// learns the tab's state right away instead of waiting for the next interval.
document.addEventListener('visibilitychange', () => ping(document.hidden));
addEventListener('pageshow', () => ping(false));
// On tab close/navigate, beacon /closing so the server shuts down in ~3s
// instead of waiting the full idle window. A refresh reloads and sends the
// heartbeat above within the grace, which cancels the pending shutdown.
addEventListener('pagehide', () => { try { navigator.sendBeacon('/closing'); } catch {} });

