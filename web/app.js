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
      txt.textContent = inp.files.length > 1
        ? T('{n} ficheiros ({first}, …)', { n: inp.files.length, first: inp.files[0].name }) : inp.files[0].name;
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
    d.classList.toggle('later', s > wizardStep);
  });
  const name = document.querySelector(`#wizardSteps .wz-dot[data-s="${wizardStep}"] .wz-lbl`)?.textContent || '';
  document.getElementById('wizardStepLabel').textContent =
    T('Passo {n} de {m} · {name}', { n: wizardStep, m: WIZARD_MAX, name });
  document.querySelector('#newJobOverlay .pv-scroll').scrollTop = 0;
  // Step 1 has no data yet → hide "Anterior"; last step swaps "Seguinte" for "Criar".
  document.getElementById('wizardPrev').style.visibility = wizardStep > 1 ? '' : 'hidden';
  document.getElementById('wizardNext').style.display = wizardStep < WIZARD_MAX ? '' : 'none';
  document.getElementById('wizardCreate').style.display = wizardStep < WIZARD_MAX ? 'none' : '';
  if (wizardStep === WIZARD_MAX) { maybeAutoAlbumSearch(); maybeAutoLyricsSearch(); }
}

// Validate the current step before advancing. Returns true if OK.
function validateWizardStep() {
  if (wizardStep === 1) {
    if (!document.querySelector('#gpInspectForm input[name=file]').files.length && !songsterrImported) {
      toast(T('Escolhe um ficheiro Guitar Pro, um PDF ou uma imagem da tab, ou importa a tab do Songsterr.')); return false;
    }
  } else if (wizardStep === 2) {
    const anyTrack = ['lead_track', 'rhythm_track', 'combo_track', 'alt_lead_track', 'alt_rhythm_track', 'bass_track']
      .some(n => document.querySelector(`#gpJobForm select[name=${n}]`).value !== '');
    if (!anyTrack) { toast(T('Atribui pelo menos uma pista.')); return false; }
  } else if (wizardStep === 3) {
    if (!usingEmbeddedAudio() && !ytAudio && !document.querySelector('#gpJobForm input[name=audio]').files.length) {
      toast(T('Escolhe a gravação (áudio) da música ou descarrega a do vídeo.')); return false;
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
  // The file's own recording is the right one; a download would be another.
  document.getElementById('ytBlock').hidden = usingEmbeddedAudio();
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
  alternative: T('vídeo alternativo'), backing: 'backing track', solo: 'solo', playthrough: 'playthrough',
};
function resetSongsterr() {
  songsterrSong = null; songsterrPoints = null;
  document.getElementById('songsterrBlock').open = false;  // an extra: closed unless wanted
  document.getElementById('songsterrLink').value = '';
  document.getElementById('songsterrVideo').hidden = true;
  document.getElementById('songsterrInfo').textContent = '';
}
function resetYtAudio() {
  ytAudio = null;
  document.getElementById('ytBlock').open = false;
  document.getElementById('ytLink').value = '';
  document.getElementById('ytAudioInfo').textContent = '';
  document.getElementById('ytCookies').value = '';
}
// The 11-character id of a YouTube video from a link (watch?v=, youtu.be/,
// shorts/, embed/, live/) or a bare id; null when there is none. Only the id
// is sent to the server, which builds the URL itself.
function youtubeVideoId(text) {
  const s = String(text || '').trim();
  const ID = /^[A-Za-z0-9_-]{11}$/;
  if (ID.test(s)) return s;
  let u;
  try { u = new URL(s.includes('://') ? s : `https://${s}`); } catch { return null; }
  const host = u.hostname.toLowerCase().replace(/^(www|m|music)\./, '');
  let id = null;
  if (host === 'youtu.be') id = u.pathname.split('/')[1];
  else if (host === 'youtube.com' || host === 'youtube-nocookie.com') {
    id = u.searchParams.get('v');
    if (!id) {
      const m = u.pathname.match(/^\/(?:shorts|embed|live|v)\/([^/?#]+)/);
      id = m && m[1];
    }
  }
  return id && ID.test(id) ? id : null;
}
// The Songsterr video whose times are in use, or null.
function songsterrChosenVideo() {
  const sel = document.getElementById('songsterrVideo');
  return songsterrSong && sel.value !== '' ? songsterrSong.videos[Number(sel.value)] : null;
}
function applySongsterrVideo() {
  const sel = document.getElementById('songsterrVideo');
  const info = document.getElementById('songsterrInfo');
  const v = songsterrSong && sel.value !== '' ? songsterrSong.videos[Number(sel.value)] : null;
  songsterrPoints = v ? v.points : null;
  if (v) {
    // The recording these times belong to is that video's audio: its link
    // goes to the download block, one click away.
    document.getElementById('ytLink').value = v.url;
    document.getElementById('ytBlock').open = true;
  }
  // Audio fetched for ANOTHER video does not match these times.
  if (ytAudio && v && ytAudio.videoId !== v.video_id) {
    ytAudio = null;
    document.getElementById('ytAudioInfo').textContent = '';
    applyEmbeddedAudioChoice();
  }
  if (!v) { info.textContent = T('Tempos do Songsterr não usados.'); return; }
  const start = v.points[0];
  // Bar 1's instant in THAT video — right as the start when the MP3 is the
  // whole video; a trimmed copy starts earlier, and the user adjusts.
  document.querySelector('#gpJobForm input[name=offset_s]').value = start.toFixed(3);
  info.innerHTML = `${icon('check')} ` + T('{n} compassos com tempo marcado.', { n: v.points.length }) + ' ' +
    T('Os tempos são do vídeo {link} — a gravação tem de ser o áudio desse vídeo (descarrega-o em "Não tens o áudio?", acima, ou carrega um MP3 convertido dele; o áudio do próprio Songsterr é outro e não bate).',
      { link: `<a href="${esc(v.url)}" target="_blank" rel="noopener">${esc(v.url)}</a>` }) + ' ' +
    T('O compasso 1 começa em <b>{s} s</b> desse vídeo; já pus esse valor em "Início da música".', { s: start.toFixed(3) }) + ' ' +
    T('Se o teu MP3 foi cortado no início, ajusta-o.');
}
document.getElementById('songsterrVideo').addEventListener('change', applySongsterrVideo);
document.getElementById('songsterrFetch').addEventListener('click', () => fetchSongsterrVideos());
async function fetchSongsterrVideos() {
  const link = document.getElementById('songsterrLink').value.trim();
  const info = document.getElementById('songsterrInfo');
  const sel = document.getElementById('songsterrVideo');
  if (!link) { toast(T('Cola o link da música no Songsterr.')); return; }
  info.textContent = T('a procurar no Songsterr…');
  try {
    songsterrSong = await getJSON(`/songsterr?song=${encodeURIComponent(link)}`);
  } catch (err) {
    songsterrSong = null; songsterrPoints = null; sel.hidden = true;
    info.textContent = T('Erro: {m}', { m: err.message || err });
    return;
  }
  sel.innerHTML = `<option value="">${T('— não usar os tempos do Songsterr —')}</option>` +
    songsterrSong.videos.map((v, i) =>
      `<option value="${i}">${esc(v.feature ? (SONGSTERR_FEATURES[v.feature] || v.feature) : T('Vídeo principal'))}` +
      ` · ${T('{n} compassos', { n: v.points.length })} · ${esc(v.url)}</option>`).join('');
  sel.value = '0';
  sel.hidden = false;
  applySongsterrVideo();
  return true;
}

async function downloadYtAudio() {
  const info = document.getElementById('ytAudioInfo');
  const videoId = youtubeVideoId(document.getElementById('ytLink').value);
  if (!videoId) {
    info.textContent = T('Cola o link de um vídeo do YouTube (youtube.com/watch?v=… ou youtu.be/…).');
    return;
  }
  const url = `https://youtu.be/${videoId}`;
  const btn = document.getElementById('ytAudioBtn');
  const browser = document.getElementById('ytCookies').value;
  btn.disabled = true;
  info.textContent = T('A descarregar o áudio de {url}… (pode demorar um minuto)', { url });
  try {
    const b = await getJSON('/youtube/audio', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video_id: videoId, cookies_browser: browser || null }),
    });
    ytAudio = { token: b.audio_token, videoId, name: b.name, size: b.size_bytes };
    const sv = songsterrChosenVideo();
    info.innerHTML = `${icon('check')} ` +
      T('Áudio do vídeo descarregado ({mb} MB) — vai ser usado como gravação; não precisas de carregar nenhum ficheiro.',
        { mb: (b.size_bytes / 1048576).toFixed(1) }) +
      (sv && sv.video_id !== videoId
        ? ' ' + T('<b>Atenção:</b> não é o vídeo dos tempos do Songsterr escolhidos, e esses tempos não vão bater com ele.')
        : '');
  } catch (err) {
    ytAudio = null;
    // The server's message already says what to do (install the JS runtime,
    // pick another browser, log in); only the always-true fallback is added.
    info.textContent = T('Não consegui descarregar: {m}. Também podes carregar um MP3 do vídeo.', { m: err.message });
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
  resetYtAudio();
  resetWizardAlbum();
  resetWizardLyrics();
  songsterrImported = false;
  document.getElementById('songsterrImportInfo').textContent = '';
  document.getElementById('pdfImportInfo').textContent = '';
  document.querySelectorAll('#newJobOverlay .file-drop').forEach(d => {
    d.classList.remove('has-file');
    const t = d.querySelector('.file-drop-text');
    if (t) t.textContent = t.dataset.default || t.textContent;
  });
  gpToken = null;
  setWizardStep(1);
}
// Anything chosen or typed would be lost, so leaving asks first (the page is
// full-screen now: "Voltar" is one click from throwing a half-made project away).
function wizardStarted() {
  return wizardStep > 1 || !!document.querySelector('#gpInspectForm input[name=file]').files.length
    || songsterrImported || !!document.getElementById('songsterrImportLink').value.trim();
}
async function closeNewJobModal() {
  if (wizardStarted() && !await confirmModal(T('Sair do novo projeto? O que escolheste e preencheste perde-se.'))) return;
  document.getElementById('newJobOverlay').hidden = true;
}
// The rail: a done step goes back to it; the next one is "Seguinte".
document.querySelectorAll('#wizardSteps .wz-dot').forEach(d => d.addEventListener('click', () => {
  const s = Number(d.dataset.s);
  if (s < wizardStep) setWizardStep(s);
  else if (s === wizardStep + 1) document.getElementById('wizardNext').click();
}));
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
  // A pre-release reads "v0.10.0 beta 1", not the bare PEP 440 "0.10.0b1".
  document.getElementById('appVersion').textContent = 'v' + d.version.replace(/b(\d+)$/, ' beta $1');
}).catch(() => {});

// ── Batch processing: several (GP, audio) pairs, created one job at a time ───
// No new backend endpoint — this loops the same /gp/inspect + /jobs/gp calls
// the single-project wizard makes, so each pair gets exactly the same
// auto-pick-tracks / metadata-fallback behavior as creating one job by hand.
let batchPairs = [];  // [{gp: File, audio: File|null, own: bool, ignored: File|null, status: 'pending'|'working'|'done'|'error', jobId, error}]
// /gp/inspect's answer per chosen GP file (read as soon as it is picked, so a
// file carrying its own audio is known before pairing): File → body | {error}.
const batchInspected = new Map();

function batchStem(f) { return f.name.replace(/\.[^.]+$/, '').toLowerCase(); }

// ownAudio(gp): the GP file carries its own recording (Guitar Pro 8). That one
// is used — it is the audio its sync points describe — and takes no recording
// from the list; a recording named like it is set aside (`ignored`) rather
// than handed to another song.
function pairBatchFiles(gpFiles, audioFiles, ownAudio = () => false) {
  const audioByStem = new Map(audioFiles.map(f => [batchStem(f), f]));
  const used = new Set();
  const pairs = gpFiles.map(gp => {
    const m = audioByStem.get(batchStem(gp));
    const matched = m && !used.has(m) ? m : null;
    if (matched) used.add(matched);
    if (ownAudio(gp)) return { gp, audio: null, own: true, ignored: matched, status: 'pending' };
    return { gp, audio: matched, own: false, ignored: null, status: 'pending' };
  });
  // Fill unmatched GP files with leftover audio files, in the order both were chosen.
  const leftover = audioFiles.filter(f => !used.has(f));
  let li = 0;
  for (const p of pairs) if (!p.own && !p.audio && li < leftover.length) p.audio = leftover[li++];
  return pairs;
}

const BATCH_STATUS = {
  pending: ['unk', 'clock', () => T('Por criar')],
  working: ['run', 'clock', () => T('A criar…')],
  done: ['ok', 'check', () => T('Criado')],
  error: ['err', 'x', () => T('Erro')],
};
function renderBatchPairs() {
  const el = document.getElementById('batchPairsList');
  const submitBtn = document.getElementById('batchSubmit');
  const summary = document.getElementById('batchSummary');
  if (!batchPairs.length) {
    el.innerHTML = `<span class="meta">${T('Escolhe os ficheiros GP e as gravações acima.')}</span>`;
    submitBtn.disabled = true;
    summary.textContent = T('Escolhe os ficheiros GP e as gravações acima.');
    return;
  }
  const reading = batchPairs.some(p => !batchInspected.has(p.gp));
  el.innerHTML = batchPairs.map(p => {
    const ins = batchInspected.get(p.gp);
    const target = !ins ? T('a ler o ficheiro…')
      : ins.error ? `<span style="color:#f08a8a">${T('não consegui ler o ficheiro ({e})', { e: esc(ins.error) })}</span>`
      : p.own ? `${icon('headphones')} ${T('o áudio que vem dentro do ficheiro GP')}` +
          (p.ignored ? ` (${T('{name} fica de fora', { name: esc(p.ignored.name) })})` : '')
      : p.audio ? esc(p.audio.name)
      : `<span style="color:#f08a8a">${T('sem gravação — não vai ser criado')}</span>`;
    const [cls, ico, label] = (!batchCreatable(p) && p.status === 'pending')
      ? ['warn', 'alert', () => T('Não vai ser criado')] : BATCH_STATUS[p.status] || BATCH_STATUS.pending;
    return `<div class="batch-row">
      <span class="pv-chip ${cls}">${icon(ico)}${label()}</span>
      <span class="batch-name" title="${esc(p.gp.name)}">${esc(p.gp.name)}</span>
      <span class="batch-arrow">${icon('forward')}</span>
      <span class="batch-target">${target}</span>
      ${p.error ? `<span class="batch-err">${esc(p.error)}</span>` : ''}
    </div>`;
  }).join('');
  const ready = batchPairs.filter(p => batchCreatable(p) && p.status === 'pending').length;
  const done = batchPairs.filter(p => p.status === 'done').length;
  summary.textContent = reading ? T('a ler os ficheiros…')
    : [ready ? T('{n} por criar', { n: ready }) : '', done ? (done === 1 ? T('1 criado') : T('{n} criados', { n: done })) : '']
      .filter(Boolean).join(' · ') || T('Nada para criar');
  submitBtn.disabled = reading || !ready;
}
function batchCreatable(p) {
  const ins = batchInspected.get(p.gp);
  return !!ins && !ins.error && (p.own || !!p.audio);
}

function openBatchModal() {
  document.getElementById('batchGpFiles').value = '';
  document.getElementById('batchAudioFiles').value = '';
  document.getElementById('batchArtist').value = '';
  document.getElementById('batchAlbum').value = '';
  document.getElementById('batchYear').value = '';
  batchPairs = [];
  batchInspected.clear();
  renderBatchPairs();
  document.getElementById('batchOverlay').hidden = false;
}
// Files chosen and not yet created would have to be picked again: ask first.
async function closeBatchModal() {
  const pending = batchPairs.some(p => (p.status === 'pending' && batchCreatable(p)) || p.status === 'working');
  if (pending && !await confirmModal(T('Sair do lote? Os projetos que ainda não foram criados perdem-se.'))) return;
  document.getElementById('batchOverlay').hidden = true;
}
document.getElementById('openBatchModal').addEventListener('click', openBatchModal);
document.getElementById('batchClose').addEventListener('click', closeBatchModal);
function refreshBatchPairing() {
  const gpFiles = [...document.getElementById('batchGpFiles').files];
  const audioFiles = [...document.getElementById('batchAudioFiles').files];
  const own = gp => !!batchInspected.get(gp)?.embedded_audio;
  batchPairs = gpFiles.length ? pairBatchFiles(gpFiles, audioFiles, own) : [];
  renderBatchPairs();
}
// Each GP file is read once, as soon as it is chosen (one at a time, like the
// submit): whether it carries its own audio decides the pairing.
async function inspectBatchGpFiles() {
  refreshBatchPairing();
  for (const gp of [...document.getElementById('batchGpFiles').files]) {
    if (batchInspected.has(gp)) continue;
    try {
      const form = new FormData();
      form.append('file', gp);
      batchInspected.set(gp, await getJSON('/gp/inspect', { method: 'POST', body: form }));
    } catch (e) {
      batchInspected.set(gp, { error: (e && e.message) || T('erro') });
    }
    refreshBatchPairing();
  }
}
document.getElementById('batchGpFiles').addEventListener('change', inspectBatchGpFiles);
document.getElementById('batchAudioFiles').addEventListener('change', refreshBatchPairing);

document.getElementById('batchSubmit').addEventListener('click', async () => {
  const submitBtn = document.getElementById('batchSubmit');
  submitBtn.disabled = true;
  const artist = document.getElementById('batchArtist').value.trim();
  const album = document.getElementById('batchAlbum').value.trim();
  const year = document.getElementById('batchYear').value.trim();
  let okCount = 0, errCount = 0;
  for (const p of batchPairs) {
    if (!batchCreatable(p) || p.status !== 'pending') continue;
    p.status = 'working';
    renderBatchPairs();
    try {
      const insBody = batchInspected.get(p.gp);
      const jobForm = new FormData();
      jobForm.append('gp_token', insBody.gp_token);
      if (p.own) jobForm.append('use_embedded_audio', 'true');
      else jobForm.append('audio', p.audio);
      // Where bar 1 sits in the file's own audio (GP8 sync), as the wizard offers.
      if (p.own && insBody.sync_start_s != null) jobForm.append('offset_s', insBody.sync_start_s.toFixed(3));
      if (artist) jobForm.append('artist', artist);
      if (album) jobForm.append('album', album);
      if (year) jobForm.append('year', year);
      // Track fields left blank on purpose: the backend's auto_pick_tracks
      // heuristic (name-based) fills Lead/Rhythm in, same as a lone-track pick
      // in the normal wizard when nothing is assigned.
      const jobR = await fetch('/jobs/gp', { method: 'POST', body: jobForm });
      const jobBody = await jobR.json();
      if (!jobR.ok) throw new Error(jobBody.detail || T('falha ao criar o projeto'));
      p.status = 'done';
      p.jobId = jobBody.id;
      okCount++;
    } catch (e) {
      p.status = 'error';
      p.error = (e && e.message) || T('erro');
      errCount++;
    }
    renderBatchPairs();
  }
  toast(errCount ? T('Lote concluído: {ok} criado(s), {err} com erro.', { ok: okCount, err: errCount })
    : T('Lote concluído: {ok} criado(s).', { ok: okCount }), errCount ? 'err' : 'ok');
  refreshJobs();
});

// ── Definições: a full-screen page, one section of the rail at a time ────────
const SETTINGS_PAGES = ['geral', 'software', 'ml', 'stems', 'volume', 'gpu'];
function showSettingsPage(name) {
  if (!SETTINGS_PAGES.includes(name)) name = 'geral';
  for (const el of document.querySelectorAll('[data-settings-page]')) el.hidden = el.dataset.settingsPage !== name;
  for (const b of document.querySelectorAll('[data-settings-tab]')) b.classList.toggle('active', b.dataset.settingsTab === name);
  try { localStorage.setItem('rf-settings-page', name); } catch { /* storage blocked */ }
}
for (const b of document.querySelectorAll('[data-settings-tab]'))
  b.addEventListener('click', () => showSettingsPage(b.dataset.settingsTab));

// What "Guardar" would send, and the same as last loaded/saved: the top bar
// counts the fields that differ, so leaving the page can warn about them.
function settingsPayload() {
  return {
    stem_separator: document.querySelector('input[name=sepBackend]:checked')?.value || 'demucs',
    banquet_repo: document.getElementById('sBanquetRepo').value.trim(),
    banquet_ckpt: document.getElementById('sBanquetCkpt').value.trim(),
    banquet_queries: document.getElementById('sBanquetQueries').value.trim(),
    loudness_target: parseFloat(document.getElementById('sLoudness').value),
    whisperx_compute_type: document.getElementById('sWhisperxCompute').value,
    ml_python: document.getElementById('sMlPython').value.trim(),
    rocksmith_dir: document.getElementById('sRocksmithDir').value.trim(),
    wwise_root: document.getElementById('sWwiseRoot').value.trim(),
    check_updates: document.getElementById('sCheckUpdates').checked,
  };
}
let settingsSaved = null;
function settingsChangeCount() {
  if (!settingsSaved) return 0;
  const now = settingsPayload();
  return Object.keys(now).filter(k => String(now[k]) !== String(settingsSaved[k])).length;
}
function updateSettingsDirty() {
  const n = settingsChangeCount();
  const chip = document.getElementById('settingsDirty');
  chip.hidden = !n;
  chip.textContent = n === 1 ? T('1 alteração por guardar') : T('{n} alterações por guardar', { n });
  if (n) document.getElementById('settingsInfo').textContent = '';
}
document.getElementById('settingsOverlay').addEventListener('input', updateSettingsDirty);
document.getElementById('settingsOverlay').addEventListener('change', updateSettingsDirty);

// The loudness target: a slider, the exact number and three presets, one value.
function setLoudnessField(v, from) {
  const n = document.getElementById('sLoudness'), r = document.getElementById('sLoudnessRange');
  if (from !== n) n.value = v;
  if (from !== r) r.value = v;
  for (const b of document.querySelectorAll('[data-loudness]'))
    b.classList.toggle('active', parseFloat(b.dataset.loudness) === parseFloat(v));
}
document.getElementById('sLoudness').addEventListener('input', e => setLoudnessField(e.target.value, e.target));
document.getElementById('sLoudnessRange').addEventListener('input', e => setLoudnessField(e.target.value, e.target));
for (const b of document.querySelectorAll('[data-loudness]'))
  b.addEventListener('click', () => { setLoudnessField(b.dataset.loudness); updateSettingsDirty(); });

function toggleBanquetConfig() {
  const on = document.querySelector('input[name=sepBackend]:checked')?.value === 'banquet';
  document.getElementById('banquetConfig').style.display = on ? '' : 'none';
}
// The settings page's ready / missing marks.
const OK_MARK = '<span style="color:#3fdc8a">✓</span>', BAD_MARK = '<span style="color:#e88">✗</span>';
function renderBanquetValidation(b) {
  document.getElementById('sVrepo').innerHTML = b.repo_ok ? OK_MARK : BAD_MARK;
  document.getElementById('sVckpt').innerHTML = b.ckpt_ok ? OK_MARK : BAD_MARK;
  document.getElementById('sVqueries').innerHTML = b.queries_ok ? OK_MARK : BAD_MARK;
  const names = b.query_names || [];
  document.getElementById('sQueryNames').textContent = names.length
    ? T('Stems detetados: {names}', { names: names.join(', ') }) : '';
}
// Which extras the interpreter that will actually RUN the ML has — asked of
// IT, in a subprocess, not of the API process (which must never import torch,
// and in the .exe is a different Python entirely).
function renderMlPythonInfo(i) {
  const el = document.getElementById('sMlPythonInfo');
  if (!el) return;
  if (!i.path) {
    // In the .exe there is no fallback: its own interpreter is the executable.
    el.innerHTML = i.frozen
      ? `<span style="color:#e0a54a">${T('Por definir — sem isto o .exe não faz stems, tom, letra nem «Corrigir daqui».')}</span>`
      : T('Vazio: usa o próprio Python do RockForge.');
    return;
  }
  if (!i.python_ok) {
    el.innerHTML = `${BAD_MARK} ${T('esse caminho não arrancou como Python — aponta ao <code>python.exe</code> do Python 3.11.')}`;
    return;
  }
  const auto = i.auto
    ? `<div>${T('Detetado sozinho: o Python dos componentes extra ({path}). Deixa o campo vazio para continuar a usá-lo.', { path: esc(i.path) })}</div>`
    : '';
  el.innerHTML = auto + `${OK_MARK} ${T('Python encontrado')} &nbsp; ` +
    `${i.ml_ok ? OK_MARK : BAD_MARK} <code>[ml]</code> (${T('stems, tom, «Corrigir daqui»')}) &nbsp; ` +
    `${i.lyrics_ok ? OK_MARK : BAD_MARK} <code>[lyrics]</code> (${T('letra')}) &nbsp; ` +
    `${i.torch_ok ? OK_MARK : BAD_MARK} PyTorch`;
}

function fillSettings(s) {
  for (const r of document.querySelectorAll('input[name=sepBackend]'))
    r.checked = r.value === (s.stem_separator || 'demucs');
  document.getElementById('sBanquetRepo').value = s.banquet_repo || '';
  document.getElementById('sBanquetCkpt').value = s.banquet_ckpt || '';
  document.getElementById('sBanquetQueries').value = s.banquet_queries || '';
  setLoudnessField(s.loudness_target ?? -12);
  document.getElementById('gpuOk').style.display = s.gpu_broken ? 'none' : '';
  document.getElementById('gpuBroken').style.display = s.gpu_broken ? '' : 'none';
  document.getElementById('sWhisperxCompute').value = s.whisperx_compute_type || '';
  document.getElementById('sMlPython').value = s.ml_python || '';
  renderMlPythonInfo(s.ml_python_info || {});
  document.getElementById('sRocksmithDir').value = s.rocksmith_dir || '';
  document.getElementById('sRocksmithDir').placeholder = s.rocksmith_dir_detected
    ? T('encontrada: {path}', { path: s.rocksmith_dir_detected })
    : 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\Rocksmith2014';
  document.getElementById('sWwiseRoot').value = s.wwise_root || '';
  document.getElementById('sWwiseRoot').placeholder = s.wwise_root_detected
    ? T('encontrada: {path}', { path: s.wwise_root_detected })
    : 'C:\\Program Files (x86)\\Audiokinetic\\Wwise2023.1.x';
  document.getElementById('sCheckUpdates').checked = s.check_updates !== false;
  toggleBanquetConfig();
  renderBanquetValidation(s.banquet || {});
  settingsSaved = settingsPayload();
  updateSettingsDirty();
}
// The external-software report. `found` is a TRI-STATE: null means "cannot be
// checked from here" (the CDLC loader patch — we don't know where the game is;
// a CUDA build of torch — only importing it would tell), which is a different
// and more honest answer than "missing", so it gets its own marker.
const SYS_STATE = {
  true: { cls: 'ok', ico: 'check', label: () => T('Instalado') },
  false: { cls: 'err', ico: 'x', label: () => T('Em falta') },
  null: { cls: 'unk', ico: 'info', label: () => T('Por confirmar') },
};

function renderSystemCheck(data) {
  const el = document.getElementById('sysCheck');
  if (!el) return;
  const reqs = data.requirements || [];
  const rows = reqs.map(r => {
    const st = SYS_STATE[String(r.found)] || SYS_STATE.null;
    // Only spell out the cost and the fix for what is actually missing or
    // unknown — a wall of install commands next to every ✅ is noise.
    const gap = r.found !== true;
    const why = gap
      ? `<div class="set-req-text"><b>${T('Sem ele:')}</b> ${esc(r.without_it)}</div>` +
        `<div class="set-code"><code>${esc(r.install)}</code>` +
        `<button type="button" data-copy="${esc(r.install)}" title="${T('Copiar')}" aria-label="${T('Copiar')}">${icon('copy')}</button></div>`
      : '';
    const flag = r.required ? `<span class="meta">${T('obrigatório')}</span>` : '';
    return `<div class="set-req${r.found === false ? ' missing' : ''}">
      <div class="set-req-ico ${st.cls}">${icon(st.ico)}</div>
      <div><div class="set-req-name">${esc(r.name)}${flag}</div>
        <div class="set-req-text">${esc(r.detail)}</div>${why}</div>
      <span class="pv-chip ${st.cls}">${st.label()}</span></div>`;
  });
  const missing = data.missing_required || [];
  const banner = missing.length
    ? `<div class="pv-hint" style="border-left-color:var(--err)">
         ${icon('alert')} ${T('Falta software <b>obrigatório</b> ({names}) — nenhum job vai chegar ao fim até o instalares.',
    { names: missing.map(esc).join(', ') })}</div>`
    : '';
  el.innerHTML = banner + rows.join('');
  const count = v => reqs.filter(r => r.found === v).length;
  const chip = (cls, ico, text) => `<span class="pv-chip ${cls}">${icon(ico)}${text}</span>`;
  const summary = [];
  if (count(true)) summary.push(chip('ok', 'check', T('{n} instaladas', { n: count(true) })));
  if (count(false)) summary.push(chip('err', 'x', T('{n} em falta', { n: count(false) })));
  if (count(null)) summary.push(chip('unk', 'info', T('{n} por confirmar', { n: count(null) })));
  document.getElementById('sysSummary').innerHTML = summary.join('');
  document.getElementById('sysRailDot').hidden = !missing.length;
}
document.getElementById('sysCheck').addEventListener('click', async e => {
  const b = e.target.closest('[data-copy]');
  if (!b) return;
  try { await navigator.clipboard.writeText(b.dataset.copy); toast(T('Copiado.'), 'ok'); }
  catch { toast(T('Não foi possível copiar.'), 'err'); }
});

async function loadSystemCheck() {
  const el = document.getElementById('sysCheck');
  if (el) el.textContent = T('a verificar…');
  document.getElementById('sysSummary').innerHTML = '';
  try {
    renderSystemCheck(await getJSON('/system-check'));
  } catch {
    if (el) el.textContent = T('não foi possível verificar (o servidor não respondeu)');
  }
}

async function openSettings(pageWanted) {
  document.getElementById('settingsInfo').textContent = '';
  try {
    fillSettings(await getJSON('/settings'));
  } catch { /* keep defaults */ }
  let page = 'geral';
  try { page = localStorage.getItem('rf-settings-page') || page; } catch { /* storage blocked */ }
  showSettingsPage(typeof pageWanted === 'string' ? pageWanted : page);
  document.getElementById('settingsOverlay').hidden = false;
  loadSystemCheck();
  pollComponents();
}

// ── Extra components: the .exe installs its own Python 3.11 with the ML,
// lyrics, PDF and YouTube packages, and Deno (infrastructure/components.py) ──
let compState = null;
let compTimer = null;
function compNames() {
  return {
    python: T('Python 3.11 (só do RockForge)'),
    ml: T('Análise de áudio (Demucs, librosa)'),
    lyrics: T('Deteção de letra (WhisperX)'),
    youtube: T('Áudio do YouTube (yt-dlp)'),
    pdf: T('Conversor de PDF (PDF-to-GP5)'),
    deno: T('Deno (para o YouTube)'),
  };
}
function compStepName(step) {
  return { python: 'Python', torch: 'PyTorch', packages: T('pacotes'), deno: 'Deno' }[step] || step || '…';
}
function renderComponents(c) {
  const card = document.getElementById('compCard');
  card.hidden = !c.supported;
  if (!c.supported) return;
  const running = c.status === 'running';
  const have = c.installed || {};
  const names = compNames();
  document.getElementById('compList').innerHTML = running ? '' : Object.keys(names).map(k =>
    `<div class="comp-item ${have[k] ? 'ok' : 'no'}">${icon(have[k] ? 'check' : 'x')}${esc(names[k])}</div>`).join('');
  document.getElementById('compNote').textContent = c.gpu
    ? T('Tens uma GPU NVIDIA: é instalado o PyTorch com CUDA (descarrega cerca de 3 GB).')
    : T('Sem GPU NVIDIA: é instalado o PyTorch para CPU (descarrega cerca de 1 GB). A análise funciona, só mais devagar.');
  document.getElementById('compInstall').disabled = running;
  document.getElementById('compInstallLbl').textContent = running ? T('A instalar…')
    : c.complete ? T('Reinstalar') : have.python ? T('Completar a instalação') : T('Instalar componentes extra');
  document.getElementById('compState').textContent = running
    ? T('passo: {step}', { step: compStepName(c.step) })
    : c.status === 'error' ? T('A instalação falhou: {error}', { error: c.error })
    : c.complete ? T('Tudo instalado.') : '';
  const log = document.getElementById('compLog');
  log.hidden = !(c.log && c.log.length);
  log.textContent = (c.log || []).join('\n');
  log.scrollTop = log.scrollHeight;
}
async function pollComponents() {
  clearTimeout(compTimer);
  let c;
  try { c = await getJSON('/components'); } catch { return; }
  const was = compState && compState.status;
  compState = c;
  renderComponents(c);
  renderHomeNotices();
  if (c.status === 'running') { compTimer = setTimeout(pollComponents, 2000); return; }
  if (was === 'running') {
    toast(c.status === 'done' ? T('Componentes extra instalados.') : T('A instalação dos componentes falhou.'),
      c.status === 'done' ? 'ok' : 'err');
    if (!document.getElementById('settingsOverlay').hidden) loadSystemCheck();
    loadHomeChecks();
  }
}
async function installComponents() {
  try {
    const r = await fetch('/components/install', { method: 'POST' });
    const b = await r.json();
    if (!r.ok) { toast(b.detail || T('erro'), 'err'); return; }
    compState = b;
    renderComponents(b);
    renderHomeNotices();
    compTimer = setTimeout(pollComponents, 1000);
  } catch { toast(T('O servidor não respondeu.'), 'err'); }
}
document.getElementById('compInstall').addEventListener('click', installComponents);

// ── Home notices: a newer version, missing components, no Wwise ─────────────
let updateInfo = null;
let wwiseFound = null;
function noticeDismissed(id) {
  try { return (JSON.parse(localStorage.getItem('rf-notice-dismissed') || '{}'))[id] === true; } catch { return false; }
}
function dismissNotice(id) {
  try {
    const all = JSON.parse(localStorage.getItem('rf-notice-dismissed') || '{}');
    all[id] = true;
    localStorage.setItem('rf-notice-dismissed', JSON.stringify(all));
  } catch { /* storage blocked: it comes back next time */ }
  renderHomeNotices();
}
function prettyVersion(v) {
  return String(v || '').replace(/^v/, '').replace(/[-.]?(?:beta|b)\.?(\d+)$/i, ' beta $1');
}
function renderHomeNotices() {
  const box = document.getElementById('homeNotices');
  const items = [];
  const notice = (cls, ico, html, actions) => items.push(
    `<div class="home-notice ${cls}">${icon(ico)}<div class="grow">${html}</div>${actions.join('')}</div>`);
  const u = updateInfo;
  if (u && u.newer && u.kind !== 'git' && !noticeDismissed('update:' + u.latest)) {
    notice('', 'download', T('Há uma versão nova do RockForge: <b>{latest}</b> (tens a {current}).',
      { latest: esc(prettyVersion(u.latest)), current: esc(prettyVersion(u.current)) }), [
      `<a class="pv-btn pv-primary" href="${esc(u.url)}" target="_blank" rel="noopener">${icon('download')}${T('Descarregar')}</a>`,
      `<button type="button" class="pv-btn" data-notice-dismiss="${esc('update:' + u.latest)}">${T('Mais tarde')}</button>`]);
  }
  const c = compState;
  if (c && c.supported && c.status === 'running') {
    notice('', 'download', T('A instalar os componentes extra (passo: {step})…', { step: esc(compStepName(c.step)) }),
      [`<button type="button" class="pv-btn" data-notice-act="components">${T('Ver')}</button>`]);
  } else if (c && c.supported && !c.complete && !c.declined) {
    notice('', 'package', T('Faltam os <b>componentes extra</b>: análise de áudio, deteção de tom e de letra, PDF e YouTube. O RockForge instala-os sozinho, numa pasta só sua.'), [
      `<button type="button" class="pv-btn pv-primary" data-notice-act="install">${T('Instalar agora')}</button>`,
      `<button type="button" class="pv-btn" data-notice-act="decline">${T('Agora não')}</button>`]);
  }
  if (c && c.supported && wwiseFound === false && !noticeDismissed('wwise')) {
    notice('warn', 'alert', T('O .psarc vai sair <b>sem som</b>: falta o <b>Wwise</b> (gratuito, da Audiokinetic, com conta). A licença não permite incluí-lo — instala o <b>Wwise 2023.1</b> pelo Audiokinetic Launcher (o 2024 e o 2025 não servem) e o RockForge encontra-o sozinho. Em Definições → Software vês o que foi encontrado.'), [
      `<a class="pv-btn" href="https://www.audiokinetic.com/download/" target="_blank" rel="noopener">${T('Descarregar o Wwise')}</a>`,
      `<button type="button" class="pv-btn" data-notice-dismiss="wwise">${T('Ocultar')}</button>`]);
  }
  box.innerHTML = items.join('');
  box.hidden = !items.length;
}
document.getElementById('homeNotices').addEventListener('click', async e => {
  const dismiss = e.target.closest('[data-notice-dismiss]');
  if (dismiss) { dismissNotice(dismiss.dataset.noticeDismiss); return; }
  const act = e.target.closest('[data-notice-act]');
  if (!act) return;
  if (act.dataset.noticeAct === 'install') { installComponents(); openSettings('software'); }
  else if (act.dataset.noticeAct === 'components') openSettings('software');
  else if (act.dataset.noticeAct === 'decline') {
    try { compState = await getJSON('/components/decline', { method: 'POST' }); } catch { /* offline */ }
    renderHomeNotices();
  }
});
async function loadHomeChecks() {
  if (!(compState && compState.supported)) return;
  try {
    const sys = await getJSON('/system-check');
    const w = (sys.requirements || []).find(r => r.key === 'wwise');
    wwiseFound = w ? w.found : null;
  } catch { wwiseFound = null; }
  renderHomeNotices();
}
async function loadUpdateInfo() {
  try { updateInfo = await getJSON('/update-check'); } catch { updateInfo = null; }
  renderHomeNotices();
}
loadUpdateInfo();
// The server asks GitHub at most once an hour; asking it again keeps a page left open all day
// up to date (an answer from its cache costs nothing).
setInterval(loadUpdateInfo, 3600 * 1000);
(async () => {
  try { compState = await getJSON('/components'); } catch { return; }
  renderHomeNotices();
  if (!compState.supported) return;
  loadHomeChecks();
  // The installer's «install the extra components» task: do it now.
  if (compState.auto_install && compState.status === 'idle' && !compState.complete) {
    installComponents();
    openSettings('software');
  } else if (compState.status === 'running') {
    pollComponents();
  }
})();
document.getElementById('sysCheckRefresh').addEventListener('click', loadSystemCheck);
async function closeSettings() {
  if (settingsChangeCount() && !await confirmModal(T('Há alterações por guardar nas definições. Sair sem guardar?'))) return;
  document.getElementById('settingsOverlay').hidden = true;
  gameDlc = null;  // the game folder may have just been set
  if (selectedJob) renderInstallRow(selectedJob);
}
document.getElementById('openSettings').addEventListener('click', openSettings);
document.querySelectorAll('[data-open-settings]').forEach(b => b.addEventListener('click', openSettings));
document.getElementById('settingsClose').addEventListener('click', closeSettings);
document.getElementById('gpuReset').addEventListener('click', async () => {
  try {
    const r = await fetch('/gpu-reset', { method: 'POST' });
    const b = await r.json();
    if (!r.ok) { toast(b.detail || T('erro'), 'err'); return; }
    fillSettings(b);
    toast(T('GPU reativada — a próxima deteção vai tentar a GPU.'), 'ok');
  } catch { toast(T('falha ao reativar a GPU'), 'err'); }
});
for (const r of document.querySelectorAll('input[name=sepBackend]'))
  r.addEventListener('change', toggleBanquetConfig);
document.getElementById('settingsSave').addEventListener('click', async () => {
  const payload = settingsPayload();
  const backend = payload.stem_separator;
  const b = await fetchOrToast('/settings', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  if (!b) return;
  fillSettings(b);  // re-renders ✓/✗ from the saved values
  loadSystemCheck();  // the ML rows follow the interpreter, so they change too
  const info = document.getElementById('settingsInfo');
  if (backend === 'banquet' && !b.banquet.ready)
    info.innerHTML = `<span style="color:#e0a54a">${T('Guardado — mas o Banquet ainda não está pronto (verifica os ✗ em Stems).')}</span>`;
  else
    info.textContent = T('Guardado.');
  toast(T('Definições guardadas.'), 'ok');
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
// The Partitura page's right-hand inspector: Sincronização | Secções | Letra.
function showInspector(name) {
  document.getElementById('inspSync').hidden = name !== 'sync';
  document.getElementById('inspSections').hidden = name !== 'sections';
  document.getElementById('inspLyrics').hidden = name !== 'lyrics';
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

// Each chart is named as Rocksmith names it in game ("LEAD 1", "LEAD 2",
// "RHYTHM", "COMBO"): /arrangements' game_name, numbered the way the PSARC's
// SongPartition is. The game's own words, so the same in every language.
const GAME_PATH = { Lead: 'LEAD', Rhythm: 'RHYTHM', Combined: 'COMBO', 'Alternate Lead': 'LEAD', 'Alternate Rhythm': 'RHYTHM', Bass: 'BASS' };
function arrLabel(kind) {
  const a = arrangements.find(x => x.kind === kind);
  return (a && a.game_name) || GAME_PATH[kind] || kind;
}
// A chart counts as in sync only when the user marked it. A file timed
// elsewhere (Guitar Pro 8's sync points, Songsterr's bar times) is a hint that
// it probably is, never the user's word: "está a verde, mas ainda não
// sincronizei nenhuma das pistas".
function arrSynced(a) { return !!a && !!a.sync_confirmed; }
function updateArrTabs() {
  document.querySelectorAll('#arrTabs button').forEach((btn, i) => {
    const a = arrangements[i];
    if (!a) return;
    const synced = arrSynced(a);
    btn.classList.toggle('synced', synced);
    btn.title = synced ? T('Pista sincronizada') : '';
    btn.innerHTML = `${synced ? icon('check') : ''}${esc(arrLabel(a.kind))} (${a.note_count}n/${a.chord_count}c)`;
  });
}

// Mark the song (arrangement = null: every chart) or ONE chart as in sync.
async function setSyncConfirmed(confirmed, arrangement = null) {
  if (!selectedJob) return;
  try {
    const j = await getJSON(`/jobs/${selectedJob.id}/sync-confirmed`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirmed, arrangement }),
    });
    selectedJob.sync_confirmed = j.sync_confirmed;
    selectedJob.sync_source = j.sync_source;
    selectedJob.synced_arrangements = j.synced_arrangements;
    for (const a of arrangements) a.sync_confirmed = (j.synced_arrangements || []).includes(a.kind);
    updateArrTabs();
    renderCompleteness(selectedJob);  // also re-sets the top bar's status chip
    refreshJobs();  // the project card's badge
  } catch (err) {
    toast(T('Não foi possível guardar: {m}', { m: err.message }));
  }
}

// What is known about the sync (JobOut.sync_source), for the badge on the
// project card, the Sincronização tab and the checklist. Only 'confirmed' is
// "synced"; 'gp'/'songsterr' say where the timing came from, as a hint.
const SYNC_SOURCE_TEXT = {
  confirmed: T('Marcada por ti como sincronizada.'),
  gp: T('O ficheiro traz os pontos de sincronização do Guitar Pro 8, por isso as notas devem seguir o áudio com que foi sincronizado. Ouve e, quando baterem, marca cada pista.'),
  songsterr: T('Temporizada pelos tempos de cada compasso do Songsterr. Ouve e, quando as notas baterem, marca cada pista.'),
  adjusted: T('Fizeste correções de início/andamento. Quando as notas baterem com a gravação, marca-a como sincronizada.'),
};
function isSynced(j) { return !!j && j.sync_source === 'confirmed'; }
// Each track is synchronised on its own, so the card speaks for the chart on
// screen: mark it (its tab turns green), and see how many are done.
function renderSyncState(j) {
  renderSyncMain(j);
  const card = document.getElementById('syncStateCard');
  if (!card) return;
  const a = arrangements[currentArr];
  const gp = !!j && j.source_type === 'gp' && j.status === 'completed' && !!a;
  card.hidden = !gp;
  if (!gp) return;
  const label = esc(arrLabel(a.kind));
  const marked = arrangements.filter(x => x.sync_confirmed).length;
  const whole = ['gp', 'songsterr'].includes(j.sync_source) ? `<br>${esc(SYNC_SOURCE_TEXT[j.sync_source])}` : '';
  const count = arrangements.length > 1
    ? `<br>${T('{n} de {m} pistas marcadas.', { n: marked, m: arrangements.length })}` : '';
  document.getElementById('syncStateText').innerHTML = (a.sync_confirmed
    ? `${icon('check')} ${T('Pista <b>{label}</b> marcada por ti como sincronizada.', { label })}`
    : T('Pista <b>{label}</b>: quando as notas baterem com a gravação, marca-a.', { label })) + whole + count;
  const btn = document.getElementById('syncStateBtn');
  btn.textContent = a.sync_confirmed ? T('Desmarcar esta pista') : T('Marcar esta pista como sincronizada');
  btn.onclick = () => setSyncConfirmed(!a.sync_confirmed, a.kind);
}

// "Instalar no jogo": the game's dlc folder is asked once (and again after
// Definições closes — the game folder may have just been set there).
let gameDlc = null;
async function renderInstallRow(j) {
  const row = document.getElementById('installRow');
  if (!row) return;
  row.hidden = !j.psarc_available;
  if (!j.psarc_available) return;
  if (gameDlc === null) {
    try { gameDlc = await getJSON('/game-dlc'); } catch { gameDlc = { dlc_dir: null, target: null }; }
  }
  if (!selectedJob || selectedJob.id !== j.id) return;
  const info = document.getElementById('installInfo');
  const label = document.getElementById('installBtnLabel');
  row.classList.toggle('in-game', j.in_game === 'this');
  if (!gameDlc.target) {
    info.textContent = T('Não encontrei a pasta do Rocksmith 2014 — indica-a em Definições → Geral.');
    label.textContent = T('Abrir Definições');
  } else if (j.in_game === 'this') {
    info.textContent = T('Esta versão está no jogo: {path}', { path: j.in_game_path });
    label.textContent = T('Reinstalar');
  } else if (j.in_game === 'older') {
    info.textContent = T('No jogo está uma versão anterior desta música ({path}) — instala esta para a substituir.', { path: j.in_game_path });
    label.textContent = T('Instalar esta versão');
  } else {
    info.textContent = T('Copia o PSARC para {dir} (fecha o jogo antes; para a música aparecer, reinicia-o).', { dir: gameDlc.target });
    label.textContent = T('Instalar no jogo');
  }
}
document.getElementById('installBtn').addEventListener('click', async () => {
  if (!selectedJob) return;
  if (gameDlc && !gameDlc.target) { showSettingsPage('geral'); openSettings(); return; }
  const btn = document.getElementById('installBtn');
  btn.disabled = true;
  try {
    const r = await getJSON(`/jobs/${selectedJob.id}/install`, { method: 'POST' });
    selectedJob = r.job;
    toast(r.removed ? T('Instalado em {path} (a cópia anterior, {old}, foi apagada).', { path: r.path, old: r.removed })
      : T('Instalado em {path}.', { path: r.path }), 'ok');
    for (const dup of r.duplicates)
      toast(T('Há outra cópia desta música em {path} — apaga-a, senão o jogo mostra-a duas vezes.', { path: dup }), 'err');
    renderInstallRow(selectedJob);
  } catch (e) {
    toast(e.message, 'err');
  } finally {
    btn.disabled = false;
  }
});

// "Verificar PSARC": the built file is read back and checked once per version
// (psarc/verify.py); the result is a row of "Antes de usar".
let psarcCheck = { id: null, data: null };
function psarcCheckRow(j) {
  if (psarcCheck.id !== j.id) {
    psarcCheck = { id: j.id, data: null };
    getJSON(`/jobs/${j.id}/psarc-check`)
      .then(d => { if (psarcCheck.id === j.id) psarcCheck.data = d; })
      .catch(e => { if (psarcCheck.id === j.id) psarcCheck.data = { failed: e.message }; })
      .finally(() => { if (selectedJob && selectedJob.id === j.id) renderCompleteness(selectedJob); });
  }
  const d = psarcCheck.data;
  if (!d) return { state: 'info', ico: 'clock', title: T('A verificar o PSARC…'), note: T('A ler o ficheiro construído e a confirmar as regras que já fizeram o jogo crashar.') };
  if (d.failed) return { state: 'info', ico: 'alert', title: T('PSARC não verificado'), note: d.failed };
  if (d.ok) return { state: 'ok', ico: 'check', title: T('PSARC verificado'),
    note: T('{n} pista(s) lida(s) do ficheiro, sem nenhuma das falhas conhecidas. Não substitui tocar no jogo.', { n: d.charts.length }) };
  const lines = d.problems.slice(0, 6).map(p => {
    const where = [p.arrangement, p.level != null ? T('nível {n}', { n: p.level }) : '', p.time != null ? `${p.time.toFixed(2)} s` : '']
      .filter(Boolean).join(' · ');
    return `${p.text}${p.count > 1 ? ` (×${p.count})` : ''}${where ? ` — ${where}` : ''}`;
  });
  if (d.problems.length > 6) lines.push(T('… e mais {n}', { n: d.problems.length - 6 }));
  return { state: 'err', ico: 'x', title: T('O PSARC tem falhas conhecidas'), short: T('falhas no PSARC'),
    note: lines.join(' · ') };
}

function renderCompleteness(j) {
  renderSyncState(j);
  const el = document.getElementById('completeness');
  if (!el) return;
  if (!(j.status === 'completed' && j.bundle_available)) { el.innerHTML = ''; return; }
  const isGp = j.source_type === 'gp';
  const rows = [];

  if (j.psarc_available) {
    rows.push({ state: 'ok', ico: 'check', title: T('PSARC jogável gerado'), note: T('.psarc pronto para o jogo.') });
    rows.push(psarcCheckRow(j));
  } else
    rows.push({ state: 'err', ico: 'x', title: T('PSARC não gerado'), short: T('gerar o PSARC (Wwise)'),
      note: T('Só saiu o bundle (DLC Builder). Falta o Wwise/.wem para produzir o .psarc jogável — vê o README.') });

  if (j.has_tones)
    rows.push({ state: 'ok', ico: 'check', title: T('Tons definidos'), note: T('O som in-game usa os teus tons.') });
  else
    rows.push({ state: 'info', ico: 'wave', title: T('Tons standard'), act: 'tones', actLabel: T('Criar tons próprios'),
      note: T('Não criaste tons: cada pista usa o tom por defeito do DLC Builder — Lead e Combo: Marshall Plexi; Rhythm: Orange AD50.') });

  if (j.cover_art)
    rows.push({ state: 'ok', ico: 'check', title: T('Capa do álbum'), note: T('Incluída no bundle.') });
  else
    rows.push({ state: 'warn', ico: 'image', title: T('Sem capa'), short: T('capa'), act: 'cover', actLabel: T('Carregar capa'),
      note: T('O albumArt fica vazio (sem arte no jogo).') });

  if (isGp) {
    if (j.sync_source === 'confirmed')
      rows.push({ state: 'ok', ico: 'check', title: T('Sincronização confirmada'), act: 'syncundo', actLabel: T('Desfazer'),
        note: T('Marcaste que as notas batem com a gravação.') });
    else if (j.sync_source === 'gp' || j.sync_source === 'songsterr')
      rows.push({ state: 'warn', ico: 'timer', short: T('confirmar a sincronização'),
        title: j.sync_source === 'gp' ? T('Temporizada no Guitar Pro — confirma') : T('Temporizada pelo Songsterr — confirma'),
        act: 'syncok', actLabel: T('Está sincronizada'), act2: 'sync', act2Label: T('Abrir partitura'),
        note: SYNC_SOURCE_TEXT[j.sync_source] });
    else if (j.sync_edited)
      rows.push({ state: 'ok', ico: 'check', title: T('Sincronização ajustada'), act: 'syncok', actLabel: T('Marcar como sincronizada'),
        note: T('Fizeste pelo menos uma correção de início/andamento.') });
    else
      rows.push({ state: 'warn', ico: 'timer', title: T('Confirmaste a sincronização?'), short: T('confirmar a sincronização'),
        act: 'syncok', actLabel: T('Está sincronizada'), act2: 'sync', act2Label: T('Abrir partitura'),
        note: T('Não há ajustes de início/andamento. Se já ouviste e as notas batem com a gravação (p. ex. vinha sincronizada do Guitar Pro), confirma aqui.') });
  }

  if (j.has_lyrics)
    rows.push({ state: 'ok', ico: 'check', title: T('Letra incluída'), note: T('A letra vai aparecer no jogo.') });
  else
    rows.push({ state: 'info', ico: 'mic', title: T('Letra (opcional)'), act: 'lyrics', actLabel: T('Detetar / editar'),
      note: T('Sem letra — o arranjo de vocais não é obrigatório.') });

  rows.push({ state: 'info', ico: 'key', title: T('AppID / propriedade'),
    note: T('O .psarc usa o AppID de uma DLC específica; o jogador tem de a possuir para a música aparecer na lista. Causa nº1 de "não aparece no jogo".') });

  const alerts = rows.filter(r => r.state === 'warn' || r.state === 'err');
  let html = `<div class="complete-card"><h4>${T('Antes de usar')}</h4>`;
  const parts = alerts.map(r => r.short || r.title.toLowerCase());
  if (alerts.length)
    html += `<div class="complete-banner">${icon('alert')} ${T('Ainda falta: <b>{parts}</b>. Podes descarregar na mesma, mas o PSARC fica mais pobre.', { parts: esc(parts.join(', ')) })}</div>`;
  setStatusChip(alerts.length ? 'warn' : 'ok',
    alerts.length ? T('Falta: {parts}', { parts: parts.join(', ') }) : T('Pronto a usar'), alerts.length ? 'alert' : 'check');
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
    title: T('Fonte de áudio (stems + sintetizada)'),
    body: T('<p>O dropdown "Fonte de áudio" tem três tipos de fonte:</p>') +
      T('<p><strong>Mistura completa</strong> — a gravação original.</p>') +
      T('<p><strong>… (sintetizada)</strong> — uma referência limpa das notas de cada arranjo (Lead/Rhythm), gerada a partir do próprio ficheiro. É uma guitarra <em>isolada</em> e limpa dessa faixa, útil para conferir o sync de cada arranjo por ouvido. Não precisa do Demucs e está sempre disponível. Reflete a sincronização pendente no momento em que a escolhes — volta a escolhê-la para atualizar depois de mais edições.</p>') +
      T('<p><strong>Stems separados</strong> (botão "Separar instrumentos") — usa o Demucs para separar a gravação real por instrumento (guitarra, baixo, voz, piano, outros; a bateria é descartada). Sola a <strong>guitarra</strong> para ouvir melhor as notas reais. <em>Limite honesto:</em> o Demucs separa por <em>tipo</em> de instrumento — a faixa "guitarra" é <strong>todas as guitarras misturadas</strong>; não é possível separar a Lead da Rhythm a partir da gravação. Requer o extra <code>[ml]</code> e demora alguns minutos.</p>')
  },
  'tone-preview': {
    title: T('Testar tom na partitura'),
    body: T('<p>Ouve os <strong>tons que criaste</strong> aplicados às notas (no tique por nota e na fonte "sintetizada"), para comparares o <em>carácter</em> — limpo, crunch, distorcido — sem teres de entrar no Rocksmith de cada vez que ajustas uma definição.</p>') +
      T('<p><strong>Voz simples (sem tom)</strong> = só o tique seco da nota, sem coloração. Ao escolher um tom, as notas passam por uma <strong>simulação de guitarra</strong>: corda dedilhada (Karplus-Strong) + distorção (conforme o ganho do tom) + cabine (EQ de corpo e corte de agudos).</p>') +
      T('<p><strong>Seguir partitura</strong>: se marcaste mudanças de tom na música, esta opção troca automaticamente de tom em cada ponto, tal como o criaste — e o <strong>tom atual aparece na partitura</strong> (etiqueta âmbar 🎸 em cada mudança + junto ao BPM). Ou escolhe um tom específico para o ouvir sozinho em toda a música. O seletor fica desativado até criares o primeiro tom.</p>') +
      T('<p>Nota: dois tons só soam <em>diferentes</em> se o gear diferir (ganho, EQ do amp, pedais). Dois tons com as <strong>mesmas definições</strong> soam iguais — é esperado. Em "Seguir partitura", se não marcaste nenhuma mudança, toca sempre o tom base.</p>') +
      T('<p><strong>Limite honesto:</strong> o RockForge <em>não</em> modela amplificadores. Isto é uma <strong>aproximação do carácter</strong> (ganho/distorção + brilho), calculada a partir dos descritores do tom, do knob de Gain do amp e dos pedais de drive — <strong>não é o som real</strong> do amp/cabine. O som verdadeiro só existe no jogo / DLC Builder, que gera o áudio a partir do gear que gravamos no bundle.</p>')
  },
  'tone-library': {
    title: T('Biblioteca de tons'),
    body: T('<p>Guarda um tom que afinaste (amp + cabine + efeitos) na <strong>biblioteca</strong> para o reutilizares noutros projetos, sem teres de o reconstruir a cada música — tal como a biblioteca de tons do DLC Builder.</p>') +
      T('<p><strong>★ Guardar na biblioteca</strong> guarda o tom em edição; <strong>⬇ Carregar</strong> adiciona o tom escolhido a este projeto (fica editável, e uma cópia — não afeta o original na biblioteca); 🗑 remove-o da biblioteca.</p>') +
      T('<p>A biblioteca é partilhada por todos os projetos (guardada em <code>work_dir/tone_library.json</code>). Guardar um tom com uma chave já existente substitui o anterior.</p>')
  },
  'tone-collection': {
    title: T('Tons das tuas músicas'),
    body: T('<p>Como no DLC Builder: o RockForge lê os ficheiros <code>.psarc</code> da tua pasta <code>dlc</code> do Rocksmith (oficiais e CDLC) e lista os tons de cada música — amplificador, cabine e efeitos com os valores exatos. <strong>Usar neste projeto</strong> copia o tom para este projeto (fica editável); <strong>★</strong> guarda-o na biblioteca.</p>') +
      T('<p>Os ficheiros só são <strong>lidos</strong>, nunca alterados, e só os manifestos (alguns KB), não o áudio. O resultado fica guardado: voltar a ler a pasta só abre os ficheiros novos ou alterados. Para incluir as músicas do disco (<code>songs.psarc</code>), indica a pasta do jogo em vez da pasta <code>dlc</code>.</p>') +
      T('<p>A pasta costuma ser <code>Steam\\steamapps\\common\\Rocksmith2014\\dlc</code>. Precisa do extra <code>[psarc]</code>, o mesmo que cria os PSARC.</p>')
  },
  'new-job': {
    title: T('Criar um novo projeto'),
    body: T(`<p><strong>A partir de Guitar Pro</strong>: notas, trastes, técnicas e secções vêm <b>exatas</b> do ficheiro GP3/GP4/GP5/GP7. Assistente de 4 passos: <b>Ficheiro</b> (escolhe o GP e inspeciona as pistas) → <b>Pistas</b> (atribui Lead/Rhythm/Combo) → <b>Gravação</b> (o áudio + o início aproximado) → <b>Detalhes</b> (título/banda, opcionais).</p>
<p>Os <b>tons</b>, a <b>capa</b> e a <b>sincronização fina</b> fazem-se depois de criar. A lista <b>"Antes de usar"</b>, na página Exportar, mostra o que ainda falta.</p>`)
  },
  'batch': {
    title: T('Processamento em lote'),
    body: T('<p>Cria vários projetos de uma vez a partir de vários ficheiros Guitar Pro + as gravações correspondentes — útil para converter um álbum inteiro sem repetir o assistente música a música.</p>') +
      T('<p><strong>Emparelhamento:</strong> cada ficheiro GP é associado à gravação com o <strong>mesmo nome</strong> (sem extensão) — ex. <code>faixa1.gp5</code> com <code>faixa1.mp3</code>. Quando não há correspondência pelo nome, o RockForge empareha pela <strong>ordem</strong> em que escolheste os ficheiros. Confirma a lista de pares antes de criar.</p>') +
      T('<p><strong>Pistas:</strong> cada projeto usa a mesma heurística automática do assistente normal (escolhe as pistas de 6 cordas pelo nome — "lead"/"rhythm" — e a de baixo, de 4 ou 5 cordas, chamada "bass" ou a única) em vez de perguntares música a música. Se uma escolha ficar errada, corrige depois em "Editar info" desse projeto (não precisas de recriar o lote todo).</p>') +
      T('<p>Banda/álbum/ano ficam <strong>partilhados</strong> por todos os pares; título/artista específicos vêm do próprio ficheiro GP ou das tags do áudio, como no assistente normal.</p>') +
      T('<p>Os projetos são criados um a um (mesmo caminho que criar um único projeto, repetido); acompanha o progresso na lista de pares e depois na lista de projetos.</p>')
  },
  'gp-format': {
    title: T('Formatos Guitar Pro suportados'),
    body: T('<p>Suportados: <strong>GP3, GP4, GP5</strong> (via PyGuitarPro) e <strong>GP7/GP8 (.gp)</strong> (parser GPIF nativo).<br><strong>Só GP6 (.gpx) não é suportado</strong> — exporta como GP5 ou GP7 no Guitar Pro ou TuxGuitar antes de importar.</p>')
  },
  'gp-offset': {
    title: T('Início da música na gravação (s)'),
    body: T('<p>O segundo em que a primeira nota é ouvida na tua gravação. A partitura e a letra são deslocadas para esse instante (a gravação fica intacta — o teu intro serve de lead-in).<br>Ouve a gravação, anota a que segundo entra a música e escreve esse valor. Se a partitura e o áudio ainda estiverem dessincronizados, ajusta o valor e reconstrói.<br>Mínimo de 2s de lead-in (exigido pelo DLC Builder); se puseres menos, o silêncio em falta é acrescentado automaticamente.</p>')
  },
  'lead-in': {
    title: T('Silêncio inicial (s)'),
    body: T('<p>Silêncio extra acrescentado mesmo no início, <strong>por cima</strong> do lead-in automático de 2s. Empurra a música inteira (áudio + notas + letra) para a frente em conjunto — útil para teres uns segundos de silêncio antes da música começar no jogo.<br>0 = nenhum. Podes alterar depois no painel de sincronização e reconstruir.</p>')
  },
  'lrc': {
    title: T('Letra sincronizada (LRC / UltraStar)'),
    body: T('<p>Para timing exato de letra usa um ficheiro <strong>LRC</strong> (<code>[mm:ss.xx]texto</code>) ou um <strong>.txt do UltraStar Creator</strong> (timing por sílaba, convertido automaticamente a partir do BPM/GAP do ficheiro).<br>A letra embutida no GP só tem tempo ao nível da linha; usa o painel "Letras" após a criação para afinar o timing por palavra.</p>')
  },
  'tuning': {
    title: T('Afinação e BPM'),
    body: T('<p>O <b>desvio</b> é quanto a gravação está afastada do Lá a 440 Hz, em cents (um cent é 1/100 de meio-tom): uma banda que afina a 432 Hz fica perto de −32. O jogo usa-o para o afinador te pedir a guitarra afinada como a gravação. É o mesmo em todas as pistas, porque a gravação é uma só.<br>"Detetar afinação" mede-o na gravação e preenche o campo; aplica-se em "Aplicar e reconstruir". Fica entre −50 e +50: mais do que isso já é outra nota.<br>A afinação das cordas (Drop D, Eb…) vem do ficheiro GP e muda-se em cada pista em "Editar info" → "Arranjos e afinação".</p>')
  },
  'sync-offset': {
    title: T('Sincronização — início e tique'),
    body: T('<p>Dá play à gravação: o cursor percorre as notas e ouves um <strong>tique</strong> em cada nota. Ajusta o slider "Início da música" até os tiques baterem certo com a gravação.<br><strong>Este valor é por pista</strong> — muda de separador (Lead/Rhythm/Combined) e o campo passa a mostrar e corrigir o início dessa pista, sem mexer nas outras. Útil quando o Lead e o Rhythm foram tabulados com um pickup/compasso de entrada diferente. A afinação continua partilhada por todos.<br>"Início = cursor" trava o valor na posição do leitor; "Detetar 1ª nota" é o mesmo fluxo guiado de 3 cliques. A correção fica pendente e grava com o botão normal "Aplicar e reconstruir".</p>')
  },
  'bar-sync': {
    title: T('Sincronizar por compasso'),
    body: T(`<p>Útil quando uma pista só entra a tocar mais tarde na música — por exemplo, o Rhythm tem compassos de silêncio no início e a primeira nota real coincide com o <b>compasso 7</b>. "Início desta pista" só alinha a 1ª nota; este painel deixa-te alinhar <b>qualquer compasso</b>, escolhido pelo número.</p>
<p><b>= cursor:</b> escolhe o compasso, dá play/pausa exatamente onde ele deve soar, e clica — o compasso escolhido (e tudo depois dele) alinha com o cursor.</p>
<p><b>Sincronizar com outra pista:</b> como o número do compasso é o mesmo em todas as pistas do ficheiro Guitar Pro (vêm da mesma partitura), se já tiveres o Lead bem sincronizado podes alinhar o compasso 7 do Rhythm diretamente com o compasso 7 do Lead — sem teres de ouvir/procurar à mão.</p>
<p><b>Andamento (BPM do compasso):</b> escreve o BPM que o compasso deve ter (vem preenchido com o atual) e, se quiseres, até que compasso aplicar — todos passam a esse BPM. O que vem depois <b>não muda de andamento</b>: só se desloca pela diferença, por isso cada compasso seguinte continua com o seu. O compasso fica marcado a âmbar na partitura, e "Guitar Pro com os andamentos corrigidos" (Exportar) grava-o no ficheiro.</p>
<p>Como as outras ferramentas de sincronização, cria uma correção pendente por pista — grava com "Aplicar e reconstruir".</p>`)
  },
  'sync-tempo': {
    title: T('Sincronização — andamento'),
    body: T('<p>Se a tabulatura e a gravação se vão afastando ao longo da música (o GP foi escrito num andamento ligeiramente diferente do que foi gravado), ajusta o <strong>andamento</strong>: estica/comprime a música toda de uma vez. As notas movem-se sobre a forma de onda para confirmares o alinhamento.</p>')
  },
  'beat-sync': {
    title: T('Sincronizar automaticamente (experimental)'),
    body: T('<p><b>Experimental — pode errar.</b> Para uma tab que não bate certo com a gravação porque o andamento da gravação varia: a gravação é analisada, e cada tempo da partitura é levado para onde as notas desse tempo soam — mantendo os tempos todos, pela ordem, e deixando o andamento mudar devagar. Como a partitura diz quantos tempos há, não pode ler a música ao dobro ou a metade.</p><p><b>Antes:</b> acerta o início do compasso de onde partes (Passo 1, ou "= cursor"), com uns décimos de segundo de folga, e o andamento aproximado. <b>Depois:</b> ouve. Os compassos onde as notas não bateram com o que se ouve ficam de fora (seguem os vizinhos) e aparecem em "Verifica de ouvido", com os primeiros a seguir a uma pausa — sem som, nada segura o andamento, e aí o alinhamento pode escorregar um tempo inteiro.</p><p>Tudo fica como correções pendentes (Passo 3), desfaz-se de uma vez com Ctrl+Z e só vai para o PSARC com "Aplicar e reconstruir". Precisa da análise de áudio (o extra [ml], ou os componentes extra no .exe). Testado em gravações sintéticas, ainda não em músicas reais — diz-nos como correu.</p>')
  },
  'attacks': {
    title: T('Ataques da gravação'),
    body: T('<p>Para uma tab cujo <b>ritmo</b> não bate com a gravação (comum nas tabs feitas à pressa): a gravação é analisada e cada <b>ataque</b> — o instante em que algo é tocado — fica marcado por cima da pauta. Os traços azuis são ataques com uma nota da pauta perto; a <b>laranja</b>, as diferenças: um círculo é uma nota sem ataque perto na gravação, um traço é um ataque forte sem nota na pauta. "Diferença anterior/seguinte" leva o cursor a cada uma, para ouvires e corrigires no editor de notas.</p><p>Não usa a amplitude do som, que quase não desce numa guitarra distorcida, mas o <b>fluxo espectral</b> (energia nova em cada 10 ms), que apanha cada palhetada. Em <b>Medir em</b> escolhes onde: num instrumento já separado (Áudio ▾ → Separar instrumentos) — por omissão a guitarra, e o baixo na pista Bass — ou na mistura, onde a bateria e a voz também dão ataques (sem nada separado, pede confirmação antes). A comparação segue a sincronização que está no ecrã, por isso sincroniza primeiro.</p><p>Limites: diz <b>quando</b> se toca, nunca que notas nem para que lado é a palhetada; o stem tem todas as guitarras juntas, por isso com dois guitarristas aparecem os ataques dos dois; a tolerância é de 60 ms. Não muda nada na partitura. Precisa da análise de áudio (o extra [ml], ou os componentes extra no .exe).</p>')
  },
  'tap-sync': {
    title: T('Marcar a ouvir'),
    body: T('<p>Para uma tab que nunca foi sincronizada — escrita à mão num só andamento, por exemplo no Songsterr — o mais fiável é <b>marcar tu</b> quando começa cada compasso, como as pessoas fazem no Songsterr para os vídeos.</p><p>Escolhe o compasso de onde partir (o 1 começa do início da gravação; os outros, do cursor — põe-no um pouco antes) e se tocas <b>em cada compasso</b> (no primeiro tempo) ou <b>em cada tempo</b> (mais toques, mais preciso). Carrega em "Começar a marcar", ouve e carrega em <b>B</b> (ou no botão grande) a tempo. Cada toque leva esse compasso para o instante em que tocaste, e a partitura acompanha enquanto tocas. <b>Backspace</b> tira o último toque; <b>Esc</b> termina. Podes parar a meio: o que vem depois do último toque mantém o seu andamento e só se desloca com ele.</p><p>Dica: abranda a reprodução no seletor de velocidade junto ao play (90%, 75%…) para marcar com calma — os toques ficam no tempo real da gravação. "Suavizar os toques" tira o tremor da mão (alinha cada toque com os vizinhos) sem apagar as mudanças de andamento.</p><p>Tudo fica como correções pendentes (aparecem no Passo 3 e desfazem-se com Ctrl+Z, de uma vez) até "Aplicar e reconstruir". Depois afina o que faltar com "Corrigir daqui" ou arrastando notas.</p>')
  },
  'auto-sync': {
    title: T('Sincronização automática'),
    body: T('<p>Deteta o andamento e o início da gravação (como o CDLC.AI) e propõe um ajuste. Os valores ficam em pré-visualização — confirma na partitura e clica em "Aplicar e reconstruir".<br><b>Dica importante:</b> se já tiveres corrido <b>"Separar instrumentos"</b>, a deteção do andamento passa a ser feita na <b>bateria isolada</b> — muito mais fiável em música rápida e densa (na mistura completa, o detetor de batidas engana-se no nível métrico). Separa primeiro para um resultado bem melhor.<br>Requer o extra <code>ml</code> (librosa). Refina depois com os modos manuais.</p>')
  },
  'auto-sync-dynamic': {
    title: T('Sincronização dinâmica (segue o andamento real)'),
    body: T('<p>A sincronização automática acima aplica UM andamento médio — não chega quando o tempo da gravação varia (o problema típico das tabs de IA). Esta segue a <b>curva de andamento real</b>: usa a grelha de batidas para o tempo local, e afina cada âncora encaixando as notas da própria tab nos ataques do áudio.<br><b>Corre "Separar instrumentos" primeiro:</b> a grelha de batidas passa a vir da <b>bateria isolada</b> e os ataques da <b>guitarra isolada</b> — muito mais fiável que a mistura completa (onde o detetor de batidas se engana no andamento). Sem separação, usa a mistura e avisa-te.<br><b>Começa na primeira nota:</b> define primeiro o início no Passo 1 (ou com "🎯 Detetar 1ª nota") — a primeira âncora é exatamente esse ponto e o alinhamento aplica-se daí para a frente.<br>Substitui as correções pendentes da pista atual por esta proposta; fica em pré-visualização — vê o <b>♩BPM por compasso</b> na partitura (âmbar = alterado pelas âncoras) e confirma com "Aplicar e reconstruir".<br><b>Limite honesto:</b> secções onde as notas da tab não batem com o áudio são assinaladas com ⚠ — aí o problema é o conteúdo da tab (notas/compassos errados), que nenhuma sincronização corrige; ajusta essas partes no Guitar Pro. Requer o extra <code>ml</code> (librosa).</p>')
  },
  'export-gp': {
    title: T('Exportar Guitar Pro corrigido'),
    body: T('<p>Escreve as correções de <b>andamento</b> que aceitaste numa <b>cópia</b> do teu ficheiro Guitar Pro, para a correção ficar permanente no próprio Guitar Pro e não só no RockForge. <b>O teu ficheiro original nunca é alterado.</b><br>Tudo o resto é preservado: notas, técnicas, afinação, faixas, secções, letra — e as mudanças de andamento que tu próprio tenhas escrito também sobrevivem.<br><b>Formatos:</b> <code>.gp3</code>/<code>.gp4</code>/<code>.gp5</code> e <code>.gp</code> (GP7/8). O <code>.gpx</code> (GP6) <b>não é escrito por ferramenta nenhuma</b> — nem o Guitar Pro o exporta para si próprio; exporta como GP5 ou GP7 primeiro.<br><b>Limite honesto:</b> os formatos binários (gp3/4/5) guardam o andamento como número <b>inteiro</b>, por isso 119,085 fica 119 — dizemos-te sempre o que foi mesmo escrito. O <code>.gp</code> mantém as casas decimais.<br><b>Só andamento:</b> um <b>salto</b> não é exprimível como mudança de BPM (seria preciso inserir/remover um compasso), por isso não vai no ficheiro — corrige esse no Guitar Pro.</p>')
  },
  'analyse-sync': {
    title: T('Analisar sincronização'),
    body: T('<p>Não corrige nada — <b>diagnostica</b>. Todas as outras ferramentas respondem "onde deve ficar cada nota"; esta responde <b>"que tipo de problema é este"</b>, que é o que decide a correção certa.<br>Encaixa as notas da tab nos ataques reais da gravação e analisa a curva de desvio:<br>• <b>Desvio progressivo</b> — a diferença cresce a um ritmo constante: o andamento da tab não é bem o da gravação. Corrige-se com um <b>BPM novo, só naquele troço</b>.<br>• <b>Salto</b> — a diferença dá um degrau: compasso a mais/menos, pausa em falta, repetição. <b>Nunca</b> se corrige com BPM — isso espalharia um erro local por música que estava correta.<br>• <b>Diferença estrutural</b> — as notas da tab não correspondem ao áudio ali; nenhuma correção temporal resolve, é o conteúdo que está errado.<br><b>Separa os instrumentos primeiro:</b> as notas são encaixadas nos ataques da <b>guitarra isolada</b>, bem mais fiável que a mistura.<br>Cada conclusão é aceite ou rejeitada individualmente e só entra em pré-visualização — o "Aplicar e reconstruir" continua a ser quem grava.<br><b>Limite honesto:</b> num trecho de ritmo muito regular, um compasso a mais/menos pode ser matematicamente indistinguível de notas em falta — aí verás "sincronizado" e notas sem par, não um salto.</p>')
  },
  'sync-from-stem': {
    title: T('Sincronizar pela bateria (IA)'),
    body: T('<p>O equivalente ao MIDI do RIPX, mas <b>feito dentro do RockForge</b> — sem exportares nada de um DAW. Corre um detetor de batidas <b>neural</b> (muito mais fiável que o automático normal em música rápida e densa, onde o detetor clássico se engana no nível métrico) sobre a gravação, deteta o <b>início de cada compasso</b> e alinha cada compasso da tab a esse tempo real — a mesma âncora-por-compasso do mapa de tempo MIDI.<br><b>Corre "Separar instrumentos" primeiro:</b> a deteção passa a ser feita na <b>bateria isolada</b> (o sinal de batida mais limpo); sem separação usa a mistura completa e avisa-te.<br>Respeita o <b>Passo 1</b> (fixa a 1.ª nota, o alinhamento cresce daí) e fica em pré-visualização — revê o <b>♩BPM por compasso</b> na partitura e confirma com "Aplicar e reconstruir".<br><b>Limite honesto:</b> é uma <b>estimativa neural</b>, forte mas não é verdade absoluta como um MIDI do RIPX conferido à mão — se falhar em material invulgar, importa o MIDI. Requer o extra <code>beatthis</code> (Beat This! + torch); pode demorar algum tempo.</p>')
  },
  'sync-from-midi': {
    title: T('Importar mapa de tempo (MIDI)'),
    body: T('<p>Quando a sincronização automática não fica perfeita, dá-lhe a <b>verdade em vez de uma estimativa</b>: um MIDI com o andamento por compasso (exportado do RIPX ou de qualquer DAW a partir da mesma gravação). Em vez de adivinhar o tempo pelo áudio, o RockForge lê o mapa de tempo do MIDI e alinha <b>cada compasso da tab ao seu tempo real</b> — uma âncora por compasso, o "BPM por compasso".<br>Continua a respeitar o <b>Passo 1</b>: fixa a 1.ª nota e o alinhamento cresce daí. Fica em pré-visualização — revê na partitura e confirma com "Aplicar e reconstruir".<br><b>Para resultar:</b> o MIDI tem de começar no 1.º compasso da tab (corta um intro que a tab não tenha) e ter a mesma estrutura de compassos. A precisão é a da deteção do RIPX. Só formato PPQ (o normal).</p>')
  },
  'highway-3d': {
    title: T('Pista 3D'),
    body: T('<p>As notas da pista escolhida a descer para as cordas, como no Rocksmith: cada corda na sua cor (Mi grave vermelho em cima) e uma linha até ao traste onde se toca. Como no Rocksmith, a nota não tem número: o número do traste no braço passa a âmbar e brilha à medida que se aproxima uma nota desse traste, e fica aceso enquanto ela soa ("Traste na nota" volta a pôr o número na nota). Quando a nota chega à corda, a corda brilha e a nota fica pousada nela enquanto soa.</p>') +
      T('<p>A afinação está escrita na pestana do headstock. Acordes têm moldura e nome; uma corda solta é uma barra ao longo da zona da mão (a faixa azul), que a câmara segue. As técnicas têm os símbolos do Rocksmith: ▼ hammer-on e ▲ pull-off na nota; por cima, laço = palm mute, anel com ponto = harmónico, olho = harmónico pinch, V largo = tapping, bloco com entalhe = slap, com bico = pop, chevrons ˄ = bend (um = meio tom, dois = um tom, três = mais); moldura dupla = acento; rasto ondulado = vibrato, em zigue-zague = tremolo picking; X = nota abafada.</p>') +
      T('<p><strong>Câmara:</strong> arrasta a pista para a rodar — para os lados até 120° de cada lado, e de rente à pista (0°) até vista de cima (90°); a roda do rato aproxima ou afasta, e um duplo clique (ou "Repor câmara") volta à vista inicial. Os mesmos três eixos estão em "Câmara", com controlos deslizantes, e a vista fica guardada para o próximo projeto.</p>') +
      T('<p>Segue a gravação e as correções de sincronização <strong>ainda por aplicar</strong>, tal como a partitura por baixo — serve para confirmar a sincronização a ver as notas chegar. Precisa de WebGL (aceleração gráfica) no browser.</p>')
  },
  'tab-viewer': {
    title: T('Partitura — legenda'),
    body: T('<p>● nota · ▮ nota de acorde (ligadas por barra vertical) · sigla sobreposta = técnica:<br>B bend · H hammer-on · P pull-off · S slide · HA harmónico · PM palm mute · V vibrato · T tapping · SL slap · PO pop · A acento<br>Passa o cursor sobre a nota para ver a lista completa.<br>Cor = corda (igual ao Rocksmith): <span style="color:#e6483c">E</span> <span style="color:#f5dc3c">A</span> <span style="color:#3f9bdc">D</span> <span style="color:#f0973c">G</span> <span style="color:#5cc24a">B</span> <span style="color:#b56cdc">e</span> (grave→agudo). Eixo X em segundos.</p>')
  },
  'sync-modes': {
    title: T('Modos de correção da partitura'),
    body: T(`<p><strong>Arrastar nota:</strong> arrasta uma nota horizontalmente para o instante correto — cria um ponto de correção; as notas entre pontos são esticadas/comprimidas.</p>
<p><strong>Encaixar nos tempos (beats):</strong> com o encaixe ligado, a nota salta de beat em beat (a grelha da partitura, mostrada com marcas no fundo) em vez de deslizar de forma contínua. Mantém <strong>Alt</strong> premido durante o arrasto para colocar livremente (afinação sub-beat). Escolhe <strong>"Cursor de reprodução"</strong> na grelha para arrastar a nota diretamente para a posição atual do leitor (em vez do beat mais próximo) — a forma mais fiável de alinhar com o cursor.</p>
<p><strong>Marcar no cursor:</strong> clica numa nota para a ancorar na posição atual do cursor de reprodução — útil para alinhar enquanto o áudio toca.</p>
<p><strong>Selecionar excerto:</strong> arrasta uma caixa sobre as notas e depois arrasta uma delas — o excerto move-se em bloco (também com encaixe nos beats).</p>
<p><strong>Mover seguintes:</strong> pausa o áudio no instante certo e clica na nota deslocada — essa nota e todas as seguintes deslocam-se em bloco para o cursor.</p>
<p><strong>Novo beat (detetar):</strong> clica numa nota onde o andamento muda — o RockForge mede o andamento da gravação a partir desse instante e re-espaça as notas seguintes.</p>
<p><strong>Alinhar compasso:</strong> pausa a gravação onde um compasso deve soar e clica numa nota — abre um popup com o número do compasso (o da nota, já escolhido). Confirma com "= cursor" e esse compasso alinha-se ao cursor, arrastando as notas seguintes; ou "= pista" para o alinhar ao mesmo compasso de outra pista já sincronizada. Feito várias vezes ao longo da música, corrige o desvio compasso a compasso.</p>
<p><strong>Secção:</strong> clica numa nota para nomear onde começa uma secção (intro/verso/refrão…) — nada a ver com sincronização, é só estrutura da música. Ver o painel "🏷️ Secções" abaixo.</p>
<p><strong>Editar notas:</strong> clica numa nota existente para a editar (traste, sustain, técnicas, bend, slide) ou removê-la; <strong>duplo-clique</strong> no pentagrama vazio insere uma nota nova, encaixada na grelha de sincronização (um clique simples no vazio move o cursor, como nos outros modos). Muda o <em>conteúdo</em> da partitura — as notas deixam de vir só do ficheiro Guitar Pro — e fica pendente (contorno tracejado verde-água) até "Aplicar e reconstruir".</p>`)
  },
  'sections': {
    title: T('Secções da música'),
    body: T('<p>Marca e nomeia a estrutura da música (intro/verso/refrão/solo…) diretamente na partitura — útil para navegar e para o <strong>Riff Repeater</strong> no jogo, sem teres de voltar ao Guitar Pro.</p>') +
      T('<p><strong>Adicionar:</strong> ativa o modo "Secção" e clica numa nota para a nomear, ou usa "+ Adicionar no cursor" para marcar a posição atual do leitor sem precisares de acertar numa nota.</p>') +
      T('<p><strong>Editar:</strong> a lista abaixo tem o tempo e o nome de cada secção editáveis diretamente — muda o número para reposicionar, o texto para renomear, ou remove-a.</p>') +
      T('<p>As secções são <strong>partilhadas por todos os arranjos</strong> (Lead/Rhythm/Combined) — tal como as mudanças de tom, marcadas uma vez e aplicadas a todos. Ficam em pré-visualização (etiqueta 🏷️ verde-água na partitura) até confirmares com "Aplicar e reconstruir"; sem qualquer edição, a música mantém as secções que já vinham do ficheiro Guitar Pro.</p>')
  },
  'lyrics': {
    title: T('Deteção automática de letra'),
    body: T('<p>Isola a voz com o Demucs e transcreve com o WhisperX — pode demorar alguns minutos (Demucs na CPU é lento).<br>Requer <code>pip install -e ".[lyrics]"</code>.<br>Depois podes editar palavras e tempos à mão, ou criar tudo manualmente sem detetar.</p>')
  },
  'album-lookup': {
    title: T('Álbum, ano e capa automáticos'),
    body: T('<p>Procura a música pelo <strong>título e banda</strong> no iTunes e no MusicBrainz (capas do Cover Art Archive) e mostra os álbuns onde ela aparece. <strong>Escolhes tu</strong> o certo: o clique preenche o álbum e o ano e usa essa capa.</p>') +
      T('<p>A pesquisa é por texto, por isso pode trazer versões de outros artistas, compilações ou reedições — cada cartão mostra a faixa encontrada e a fonte para o veres. "Sem capa" não usa imagem nenhuma. Precisa de internet; sem ela, preenche à mão como antes.</p>') +
      T('<p>A capa escolhida é descarregada quando o projeto é criado. Num projeto que já existe, usa "Procurar capa online" na página Capa.</p>')
  },
  'wz-lyrics': {
    title: T('Letra sincronizada (ao criar)'),
    body: T('<p>Procura a letra da música no <b>LRCLIB</b> (base aberta, sem conta) pelo título e pela banda — corre sozinha quando chegas a este passo. A melhor versão <b>com tempos</b> fica escolhida e entra logo no primeiro build; clica noutra para mudar, ou em "Escolhida ✓" para não usar nenhuma.</p>') +
      T('<p>Os tempos são os da gravação original. Se a tua versão tiver outra introdução, ajusta-os depois na página <b>Letra</b> ("1ª palavra = cursor", −/+, ou "Sincronizar com a gravação"). Se o ficheiro GP já trouxer letra, nada fica escolhido sozinho — uma letra daqui substituiria a do GP. Um ficheiro LRC carregado abaixo tem sempre prioridade.</p>') +
      T('<p>Remixes de fãs e músicas feitas por IA raramente estão no LRCLIB.</p>')
  },
  'insp-lyrics': {
    title: T('Acertar a letra na partitura'),
    body: T('<p>As mesmas edições da página <b>Letra</b>, ao lado das notas onde a ouves. Clica numa palavra na partitura para a escolher (arrastá-la também a move).</p>') +
      T('<p><b>Daqui em diante = cursor</b> — põe o cursor onde a palavra devia soar: ela vai para lá e todas as seguintes acompanham-na, as anteriores ficam onde estão. É a forma rápida de corrigir uma letra que sai do tempo a meio: vai de palavra em palavra onde começa a desviar. <b>Só esta = cursor</b> move apenas essa palavra; −/+ movem-na com as seguintes pelo passo indicado em cima.</p>') +
      T('<p><b>1ª palavra = cursor</b> e −/+ em "Letra toda" movem a letra inteira (adiantada ou atrasada por igual). Tudo fica pendente até "Aplicar e reconstruir".</p>') +
      T('<p><b>Acompanha as correções de sincronização da partitura</b> — quando a letra vem da própria pauta, está presa às notas: se corriges o início, o andamento ou arrastas notas, as palavras mudam com elas. Segue a pista indicada (a primeira: Lead, senão Rhythm, senão Combo). Vem desligado para uma letra do LRCLIB ou detetada na gravação, que está presa à gravação e não às notas.</p>')
  },
  'lyrics-lookup': {
    title: T('Procurar a letra e sincronizá-la'),
    body: T('<p>Procura a letra no <strong>LRCLIB</strong> (base de dados aberta de letras) pelo título e banda do projeto. Muitas letras vêm <strong>sincronizadas</strong> por linha; outras são <strong>só texto</strong>.</p>') +
      T('<p><strong>Usar</strong> carrega a letra sincronizada no editor com os tempos da versão em que foi feita (normalmente a oficial). Se a tua gravação é essa versão, já bate certo; se tem uma introdução diferente, <strong>1ª palavra = cursor</strong> (põe o cursor onde começa a voz) ou os botões −/+ deslocam a letra toda.</p>') +
      T('<p><strong>Sincronizar com a gravação</strong> usa o WhisperX para medir na voz da <em>tua</em> gravação o tempo de <em>cada palavra</em> da letra que está no editor — as palavras ficam as certas, só os tempos são medidos. Numa letra só texto procura na música inteira (menos fiável). Precisa dos extras <code>[ml,lyrics]</code> e demora alguns minutos.</p>') +
      T('<p>A letra fica pendente até "Aplicar e reconstruir". Remixes de fãs e músicas feitas por IA raramente estão no LRCLIB — aí usa "Detetar letra" ou escreve-a no editor.</p>')
  },
  'songsterr-import': {
    title: T('Importar a tab do Songsterr'),
    body: T('<p>Em vez de um ficheiro Guitar Pro, cola o link da música no <strong>Songsterr</strong>. O RockForge descarrega as pistas da tab e cria com elas um ficheiro Guitar Pro 5, que segue o caminho normal (escolhes as pistas no passo 2).</p>') +
      T('<p>No passo 3 aparecem os <strong>vídeos do YouTube</strong> dessa música com o tempo de cada compasso marcado por pessoas, e o áudio do vídeo escolhido é descarregado para ser a gravação (ou carregas um MP3 convertido dele). Com isso, as notas seguem a gravação compasso a compasso, sem acertos manuais.</p>') +
      T('<p>Limites: a API do Songsterr não é pública e pode mudar; as pistas de bateria ficam de fora; notas de ornamento (grace) não são incluídas. A letra vem quando a tab a tem, com cada sílaba na nota da pista em que está escrita (normalmente a da voz); se não tiver, procura-a no passo 4 ou na página Letra. O ficheiro criado pode ser exportado e aberto no Guitar Pro.</p>')
  },
  'pdf-import': {
    title: T('Converter um PDF ou uma imagem da tab'),
    body: T('<p>Em vez de um ficheiro Guitar Pro, escolhe o <strong>PDF</strong> da tablatura (uma tab em texto, ou exportada do Guitar Pro, MuseScore ou TuxGuitar) ou uma <strong>imagem</strong> dela (PNG, JPEG ou WebP). O RockForge converte-a num ficheiro Guitar Pro 5 com o conversor do <strong>PDF-to-GP5</strong>, e o assistente continua como com um ficheiro Guitar Pro.</p>') +
      T('<p>Várias pistas: escolhe vários ficheiros de uma vez, <strong>um por pista</strong>, pela ordem das pistas (até 7).</p>') +
      T('<p>Limites: a leitura de imagens (OCR) é experimental — lê os números, as linhas das cordas, as barras de compasso e as técnicas escritas (H/P, P.M., let ring, harmónicos), os slides, o vibrato, as ligaduras e os bends; numa tab sem notação rítmica o ritmo é estimado pelo espaçamento. Confere sempre as notas na partitura depois de criar o projeto. Precisa do conversor instalado (⚙️ Definições → Software externo).</p>')
  },
  'youtube-audio': {
    title: T('Áudio do vídeo do YouTube'),
    body: T('<p>Cola o link de um vídeo do YouTube com a música: o RockForge descarrega o áudio com o <strong>yt-dlp</strong> e usa-o como gravação do projeto — já não precisas de o converter à mão. Serve para qualquer ficheiro GP, também um feito por ti. A sincronização acerta-se depois na partitura.</p>') +
      T('<p>Com os <strong>tempos por compasso do Songsterr</strong> tem de ser o vídeo em que esses tempos foram marcados — ao escolheres o vídeo lá, o link aparece aqui sozinho.</p>') +
      T('<p><strong>Precisa de duas coisas instaladas:</strong> o yt-dlp com o solucionador do YouTube (<code>pip install -U "yt-dlp[default]"</code>) e um <strong>motor JavaScript</strong>, o Deno (<code>winget install DenoLand.Deno</code>; o Node também serve). O YouTube só entrega o áudio a quem resolver um desafio em JavaScript — sem o motor recusa, mesmo sem pedir login. Depois de instalar, reinicia o RockForge. ⚙️ Definições → Software externo mostra o que falta.</p>') +
      T('<p><strong>Se o YouTube pedir uma sessão</strong> ("confirma que não és um robô"), escolhe em "Sessão do browser" um browser onde tenhas o YouTube aberto. No Windows usa o <strong>Firefox</strong>: o yt-dlp não consegue ler a sessão do Chrome, do Edge nem dos outros baseados no Chromium.</p>') +
      T('<p>Se o YouTube mudar e os downloads falharem, atualizar o yt-dlp costuma resolver. Descarregar do YouTube vai contra os termos do YouTube fora das funções que ele oferece — usa só para uso pessoal, com música a que tens direito.</p>')
  },
  'cover-art': {
    title: T('Capa do álbum'),
    body: T('<p>Imagem JPG ou PNG incluída no bundle como <code>cover.*</code> e referenciada no <code>rockforge.rs2dlc</code> — usa-a como capa ao abrir o projeto no DLC Builder (que gera as texturas DDS do jogo).<br>O upload não reconstrói o bundle — clica em "Aplicar e reconstruir" na tab Partitura para incluir a capa.</p>')
  },
  'tones': {
    title: T('Tons (amp, cabine, efeitos)'),
    body: T(`<p>Define os tons da CDLC com <strong>gear real</strong> (amplificador, cabine e pedais/racks da biblioteca do Rocksmith). São gravados no <code>rockforge.rs2dlc</code> e no <code>.psarc</code>, por isso funcionam no jogo sem teres de os recriar no DLC Builder.</p>
<p><strong>Criar:</strong> clica em "+ Criar / editar tons", depois "+ Novo tom". Escolhe o amplificador e a cabine (obrigatórios) e adiciona efeitos opcionais. Cada botão de knob vem com o valor por defeito do catálogo.</p>
<p><strong>Atribuir:</strong> escolhe o <strong>Tom base</strong> (o que toca no início) e marca até <strong>4</strong> tons "extra" que poderás trocar ao longo da música.</p>
<p><strong>Trocar a meio:</strong> com o modo "Mudança de tom" ativo, clica numa nota na partitura para colocar lá uma troca para um dos tons extra.</p>
<p><strong>Por pista:</strong> no jogo os tons são <strong>por arranjo</strong>. Com "Mesmos tons em todas as pistas" marcado, todas usam o mesmo conjunto; desmarcado, cada pista (a que está aberta na partitura) tem o seu tom base, extras e trocas — o Lead pode ir para um tom de solo enquanto o Rhythm fica no crunch. Os tons criados são partilhados.</p>
<p>Só se aplicam a projetos de Guitar Pro. Sem tons definidos, o DLC Builder marca "tone missing" e resolves com a biblioteca dele.</p>`)
  },
  'tone-sections': {
    title: T('Sugestões de tom por secção'),
    body: T(`<p>O "Detetar tom" mede o som da guitarra <strong>ao longo da música</strong> (janelas de 4 s): onde está mais limpo, onde distorce mais. Aqui, esse som é lido contra o que <strong>cada pista toca</strong> em cada parte (as secções da música, ou grupos de 8 compassos):</p>
<ul><li><strong>Limpo</strong> — a gravação está limpa ali, ou a pista deixa soar acordes/arpejos sem palm mute;</li>
<li><strong>Solo</strong> — notas soltas com bends, vibrato, ligados ou na casa 12 e acima;</li>
<li><strong>Ritmo</strong> — acordes, palm mute.</li></ul>
<p>Para cada parte escolhe o tom mais parecido dessa família, e diz porquê e com que confiança. Uma parte onde a pista não toca mantém o tom anterior; partes seguidas com o mesmo tom juntam-se; cada pista fica com <strong>no máximo 4 tons</strong> (os espaços A–D do Rocksmith, com o base incluído para se poder voltar a ele).</p>
<p><strong>Limites honestos:</strong> a separação dá TODAS as guitarras juntas, por isso a diferença entre pistas vem da partitura, não do áudio. Os tons são escolhidos pelo <em>carácter</em> (distorção, brilho, graves) — não identificam o amplificador real. As partes e tempos são os da última reconstrução.</p>`) +
      T('<p><strong>Trocar os tons sugeridos:</strong> fica com os pontos onde a app troca de tom, mas com os tons que tu queres. Para cada tom sugerido escolhe outro — dos tons do projeto, da biblioteca ou dos teus PSARC (a lista de tons das tuas músicas) — e depois "Aplicar". Escolher o mesmo tom para dois sugeridos junta-os, e a troca entre eles desaparece.</p>')
  },
};

document.getElementById('infoClose').addEventListener('click', () => {
  document.getElementById('infoOverlay').hidden = true;
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') document.getElementById('infoOverlay').hidden = true;
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
  document.querySelector('#infoOverlay .modal').classList.remove('modal-keys');
  document.getElementById('infoOverlay').hidden = false;
});

// ── Keyboard shortcuts: the "?" list, and 1–9 for the modes ──────────────────
function showShortcuts() {
  const k = (...keys) => keys.map(x => `<kbd>${esc(x)}</kbd>`).join(' ');
  const modes = SYNC_MODE_BUTTONS.map(([id], i) =>
    `${k(modeKey(i))} ${esc(document.getElementById(id)?.dataset.name || '')}`).join(' · ');
  const groups = [
    [T('Reprodução'), [
      [k(T('Espaço')), T('play / pausa')],
      [`${k('←')} ${k('→')}`, T('recua / avança 1 s (com Shift, 5 s)')],
      [k('Home'), T('vai ao início')],
      [`${k('[')} ${k(']')}`, T('marca no cursor o início (A) / o fim (B) do trecho a repetir')],
      [k('L'), T('liga / desliga a repetição do trecho A–B')],
    ]],
    [T('Partitura'), [
      [`${k('1')}…${k('9')} ${k('0')}`, `${T('escolhe o modo (o mesmo número outra vez tira-o):')} ${modes}`],
      [`${k('+')} ${k('−')}`, T('zoom')],
      [T('Shift+clique'), T('seleciona da nota anterior até esta')],
      [T('Ctrl+clique'), T('junta ou tira uma nota da seleção')],
      [T('Alt a arrastar'), T('move sem encaixar na grelha')],
      [T('Duplo clique'), T('em "Editar notas", insere uma nota no espaço vazio')],
      [`${k('B')} · ${k('Backspace')} · ${k('Esc')}`, T('em "Marcar a ouvir": marca o compasso (ou tempo) · tira o último toque · termina')],
    ]],
    [T('Edição'), [
      [`${k('Delete')}`, T('apaga as notas selecionadas')],
      [`${k('Ctrl')}+${k('C')} · ${k('Ctrl')}+${k('V')}`, T('copia a seleção · cola no cursor')],
      [`${k('Ctrl')}+${k('Z')}`, T('desfaz (em qualquer página do projeto)')],
      [`${k('Ctrl')}+${k('Shift')}+${k('Z')} · ${k('Ctrl')}+${k('Y')}`, T('refaz')],
    ]],
    [T('Geral'), [
      [k('?'), T('esta lista')],
      [k('Esc'), T('fecha um menu, popup ou esta janela')],
    ]],
  ];
  document.getElementById('infoTitle').textContent = T('Atalhos de teclado');
  document.getElementById('infoBody').innerHTML =
    `<p>${T('Fora dos campos de texto. Os de reprodução, partitura e edição de notas valem na página Partitura.')}</p>` +
    groups.map(([title, rows]) => `<div class="keys-group">${esc(title)}</div><table class="keys-table">` +
      rows.map(([keys, what]) => `<tr><td>${keys}</td><td>${what}</td></tr>`).join('') + '</table>').join('');
  document.querySelector('#infoOverlay .modal').classList.add('modal-keys');
  document.getElementById('infoOverlay').hidden = false;
}
document.getElementById('shortcutsBtn').addEventListener('click', showShortcuts);
document.addEventListener('keydown', e => {
  if (e.key !== '?' || e.ctrlKey || e.metaKey || e.altKey) return;
  const el = document.activeElement;
  const tag = el && el.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (el && el.isContentEditable)) return;
  if (!selectedJob || document.getElementById('detailOverlay').hidden) return;
  if (document.querySelector('.modal-overlay:not([hidden]), .settings-view:not([hidden])')) return;
  e.preventDefault();
  showShortcuts();
});

let selectedJob = null, arrangements = [], currentArr = 0, pollTimer = null;
let arrangementsLoadedFor = null;  // job id whose chart+audio are already loaded (avoids re-decoding on every poll)
// Visual sync (GP): MIN_LEAD must match gp_pipeline.MIN_LEAD_S and MIN_OFFSET
// gp_pipeline.MIN_OFFSET_S (a GP whose bar 1 comes before the recording starts
// has a negative offset_s; the build pads the audio by that much more).
const MIN_LEAD = 2.0;
const MIN_OFFSET = -60.0;
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
// The band under the staff holds, top to bottom: the correction pins, the tone
// labels, the fret-hand positions (FHP) and the chord names.
const STAFF_H = 330, STAFF_SB = STAFF_H - 85, STAFF_ROW = 40, NOTE_R = 13;

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
// No mode on entry: a click on the score then just selects or seeks, and a mode
// is something the user picks ("sempre que entro … existe um modo que está
// selecionado e não devia" — "Corrigir daqui" used to be on by default, so the
// first click on a note re-timed the song). Back to none when a project closes.
let syncMode = null; // null | 'drag' | 'tap' | 'excerpt' | 'newbeat' | ...
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
// Lyrics timed on the SCORE (the GP file's own) are tied to its notes, so a
// sync correction of the chart — "Início", tempo, a dragged note — has to move
// them too; lyrics timed to the RECORDING (LRCLIB, detection) must stay put.
// The server says which (follow_chart); the Letra tab's checkbox can change it.
let lyricsFollowChart = false;
// serializeLyrics() of the rows as last loaded — what makes "Pendente: letra"
// mean changed since the build.
let lyricsBuilt = '[]';
// Tone editor state (GP jobs). jobTones: full gear dicts (see gear_catalogue
// .tone_from_dict); toneBase/toneNames reference them by key; toneChanges are
// the timed switches placed on the partitura ({time(bundle s), name(key)}).
let gearCatalogue = null;     // {amps, cabinets, pedals, racks, descriptors}
let jobTones = [];            // [{key,name,volume,descriptors,amp,cabinet,pre,post,racks}]
let toneBase = null;
let toneNames = [];
let toneChanges = [];
// Rocksmith's tones are per arrangement. The four globals above are the set
// being EDITED: the song's, or — once "Mesmos tons em todas as pistas" is
// unticked — the set of the chart on screen, swapped on every tab change the
// way syncAnchorsByKind is. The gear definitions (jobTones) stay shared.
let songToneSet = { tone_base: null, tone_names: [], tone_changes: [] };
let toneSetByKind = {};       // kind → its own set, only while tonesPerTrack
let tonesPerTrack = false;
let toneSetKind = null;       // whose set the globals hold (null = the song's)
let toneSuggestions = null;   // last GET /tone-suggestions answer
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
let centOffsetBuilt = 0;  // as the current build has it, for "Pendente"

// Safe in text AND in a quoted attribute: serialising a text node escapes only
// & < >, so a title like  x" onanimationstart="…  would close an attribute and
// add a handler (third-party text — GP files, Songsterr, LRCLIB, other people's
// CDLC tones — reaches dozens of value="…"/aria-label="…" sites).
const ESC_MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const esc = t => String(t ?? '').replace(/[&<>"']/g, c => ESC_MAP[c]);

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
  if (msg) toast(T('erro: {msg}', { msg }), 'err');
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
      el.textContent = T('Sem ligação ao RockForge — a app terminou ou perdeu-se a rede. Reinicia o start.bat e recarrega esta página.');
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

// Asks /jobs/<the project open now>/<path> every 3 s and hands each answer to
// onData(answer, jobId) until it returns true (finished). Bound to that
// project: opening another one, or closing it, stops it instead of polling —
// and drawing — the new project. A request that fails is skipped (offline: the
// banner says so). Returns the interval, for clearInterval.
function pollJob(path, onData) {
  const jobId = selectedJob?.id;
  const timer = setInterval(async () => {
    if (!selectedJob || selectedJob.id !== jobId) { clearInterval(timer); return; }
    let d;
    try { d = await getJSON(`/jobs/${jobId}/${path}`); } catch { return; }
    if (!selectedJob || selectedJob.id !== jobId) return;
    if (onData(d, jobId)) clearInterval(timer);
  }, 3000);
  return timer;
}

// getJSON for a button's request: a failure is shown as a toast (the server's
// own reason when it gave one) and answers null, so the caller just returns.
async function fetchOrToast(url, opts) {
  try {
    return await getJSON(url, opts);
  } catch (err) {
    toast(err.message || T('erro'));
    return null;
  }
}

// `okLabel` names a yes that is not a removal (the button then is not red).
function confirmModal(text, okLabel = null) {
  const overlay = document.getElementById('confirmOverlay');
  document.getElementById('confirmText').textContent = text;
  const ok = document.getElementById('confirmOk');
  ok.textContent = okLabel || T('Remover');
  ok.className = okLabel ? '' : 'danger';
  overlay.hidden = false;
  return new Promise(resolve => {
    const cleanup = result => { overlay.hidden = true; resolve(result); };
    document.getElementById('confirmOk').onclick = () => cleanup(true);
    document.getElementById('confirmCancel').onclick = () => cleanup(false);
    overlay.onclick = e => { if (e.target === overlay) cleanup(false); };
  });
}

function closeDetail() {
  stopPendingHistory();
  clearLoop(false);
  window.Highway3D?.close();  // nothing to draw once the project is closed
  hw3dLastSong = null;
  selectedJob = null;
  arrangementsLoadedFor = null;
  openJobId = null;
  clearTimeout(pollTimer);
  clearInterval(lyricsPollTimer);
  clearInterval(_toneDetectionPoll); _toneDetectionPoll = null;
  clearInterval(_stemsPoll); _stemsPoll = null;
  stopArrangementPreview();
  stopPlayback();
  playBuffer = null; playGain = null; pausedAt = 0; playing = false;
  const au = document.getElementById('syncAudio');
  if (au) { au.removeAttribute('src'); au.load(); }
  document.getElementById('detailOverlay').hidden = true;
  sectionShownFor = null;
  setSyncMode(null);
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
// Standard tuning (low E to high e) as MIDI: an open string's pitch is this
// + the arrangement's tuning offset; a note's adds its fret.
const STD_TUNING_MIDI = [40, 45, 50, 55, 59, 64];
// A bass (string_count 4) is E1 A1 D2 G2, an octave below — its offsets are
// measured from there, as the game does.
const BASS_TUNING_MIDI = [28, 33, 38, 43, 47, 52];
function isBassArr(a) { return !!a && a.string_count === 4; }
// A Guitar Pro track a Bass chart can be made from (5 strings fold onto 4).
function isBassTrackStrings(n) { return n === 4 || n === 5; }
function stringCount(a) { return isBassArr(a) ? 4 : 6; }
// The open string's real pitch. A very low bass is written an octave up at
// 220 Hz (DLC Builder's low-tuning fix, cent offset -1200): undo that here.
function openMidi(a, str) {
  const base = (isBassArr(a) ? BASS_TUNING_MIDI : STD_TUNING_MIDI)[str];
  const off = (a && a.tuning_offsets && a.tuning_offsets[str]) || 0;
  const fixed = isBassArr(a) && (a.cent_offset || 0) <= -1100 ? 12 : 0;
  return base + off - fixed;
}
// A note's pitch: an open string under a capo sounds at the capo.
function noteMidi(a, str, fret) { return openMidi(a, str) + (fret || (a && a.capo) || 0); }
// The staff keeps its height; a bass's four lines are spread over it.
function staffRow(a) { return isBassArr(a) ? STAFF_ROW * 5 / 3 : STAFF_ROW; }
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
  document.getElementById('metaHeadSub').textContent =
    [selectedJob.title, selectedJob.artist].filter(Boolean).join(' — ');
  metaSaved = metaValues();
  updateMetaDirty();
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
    const optsFor = keep => '<option value="">—</option>' + tr.tracks
      .filter(t => !t.is_percussion && keep(t.string_count))
      .map(t => `<option value="${t.index}">${t.index}: ${esc(t.name)}</option>`).join('');
    const opts = optsFor(n => n === 6);
    const bassOpts = optsFor(isBassTrackStrings);
    const SLOTS = [['lead', T('Pista {label}', { label: 'Lead' })], ['rhythm', T('Pista {label}', { label: 'Rhythm' })],
                   ['combo', T('Pista {label}', { label: 'Combo' })],
                   ['alt_lead', T('Pista Lead alternativo (no jogo: LEAD 2)')],
                   ['alt_rhythm', T('Pista Rhythm alternativo (no jogo: RHYTHM 2)')],
                   ['bass', T('Pista {label}', { label: 'Bass' })]];
    document.getElementById('metaTracks').innerHTML = SLOTS.map(([slot, label]) =>
      `<div class="field" style="flex:1 1 11rem"><label>${label}</label>
        <select data-slot="${slot}" style="width:100%">${slot === 'bass' ? bassOpts : opts}</select></div>`).join('');
    for (const [slot] of SLOTS) {
      const v = tr.assignment[slot];
      if (v !== null && v !== undefined)
        document.querySelector(`#metaTracks select[data-slot="${slot}"]`).value = String(v);
    }
    const presetOpts = Object.keys(TUNING_PRESETS)
      .map(n => `<option value="${n}">${n === 'Manter' ? T('Manter') : n}</option>`).join('');
    document.getElementById('metaTunings').innerHTML = arrs.map(a => {
      const ov = (tr.tuning_overrides || {})[a.kind];
      const std = isBassArr(a) ? BASS_TUNING_MIDI : STD_TUNING_MIDI;
      // A bass override is its four strings; the two it does not have follow string 3.
      const ovOff = ov && ov.map((m, i) => m - std[i]);
      const cur = ovOff ? _presetFromOffsets(ovOff.length === 4 ? [...ovOff, ovOff[3], ovOff[3]] : ovOff) :
                          _presetFromOffsets(a.tuning_offsets);
      return `<div class="field" style="flex:1 1 11rem"><label>${T('Afinação {arr}', { arr: esc(arrLabel(a.kind)) })}</label>
        <select data-kind="${esc(a.kind)}" style="width:100%">${presetOpts}</select></div>`
        .replace(`value="${cur}"`, `value="${cur}" selected`);
    }).join('');
    gp.style.display = '';
    metaSaved = metaValues();  // the loaded track map + tunings are the baseline
    updateMetaDirty();
  } catch { /* leave the GP section hidden on any error */ }
}
// Reached from onclick="openMetaEdit()" inside the job-row template strings,
// which ESLint cannot trace — inline handlers resolve through global scope, so
// say so explicitly instead of leaving it looking unused.
window.openMetaEdit = openMetaEdit;

// What the page holds now, split into what only needs a PATCH (the song's
// info) and what needs a rebuild (track map + tunings, GP jobs). Compared with
// what was loaded: the top bar counts the changes, the save button says when
// it will rebuild, and a save that touched no track/tuning no longer forks a
// rebuild just because the section was shown.
let metaSaved = null;
function metaValues() {
  const v = id => document.getElementById(id).value.trim();
  const info = { title: v('metaTitle'), artist: v('metaArtist'), album: v('metaAlbum'), year: v('metaYear') };
  const gp = {};
  if (document.getElementById('metaGp').style.display !== 'none') {
    for (const sel of document.querySelectorAll('#metaTracks select[data-slot]')) gp['t:' + sel.dataset.slot] = sel.value;
    for (const sel of document.querySelectorAll('#metaTunings select[data-kind]')) gp['u:' + sel.dataset.kind] = sel.value;
  }
  return { info, gp };
}
function metaChanges() {
  if (!metaSaved) return { info: 0, gp: 0 };
  const now = metaValues();
  const diff = (a, b) => Object.keys(a).filter(k => a[k] !== b[k]).length;
  return { info: diff(now.info, metaSaved.info), gp: diff(now.gp, metaSaved.gp) };
}
function updateMetaDirty() {
  const c = metaChanges(), n = c.info + c.gp;
  const chip = document.getElementById('metaDirty');
  chip.hidden = !n;
  chip.textContent = n === 1 ? T('1 alteração por guardar') : T('{n} alterações por guardar', { n });
  document.getElementById('metaSaveLabel').textContent = c.gp ? T('Guardar e reconstruir') : T('Guardar');
}
document.getElementById('metaOverlay').addEventListener('input', updateMetaDirty);
document.getElementById('metaOverlay').addEventListener('change', updateMetaDirty);
function closeMeta() { document.getElementById('metaOverlay').hidden = true; }
document.getElementById('metaClose').onclick = async () => {
  const c = metaChanges();
  if ((c.info || c.gp) && !await confirmModal(T('Sair sem guardar as alterações à informação da música?'))) return;
  closeMeta();
};
document.getElementById('metaSave').onclick = async () => {
  if (!selectedJob) return;
  const title = document.getElementById('metaTitle').value.trim();
  const artist = document.getElementById('metaArtist').value.trim();
  if (!title || !artist) { alert(T('Título e artista são obrigatórios.')); return; }
  const yearRaw = document.getElementById('metaYear').value.trim();
  const body = {
    title, artist,
    album: document.getElementById('metaAlbum').value.trim(),
    year: yearRaw ? parseInt(yearRaw, 10) : null,
  };
  const r = await fetch(`/jobs/${selectedJob.id}/metadata`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!r.ok) { alert(T('Erro ao guardar a informação.')); return; }
  selectedJob = await r.json();
  // GP: if the arrangements/tuning section is shown, a change there needs a full
  // rebuild (re-parse) — fork a new job with the new track map + tunings.
  const gp = document.getElementById('metaGp');
  if (gp.style.display !== 'none' && metaChanges().gp) {
    const tracks = {};
    for (const sel of document.querySelectorAll('#metaTracks select[data-slot]'))
      tracks[sel.dataset.slot] = sel.value === '' ? null : parseInt(sel.value, 10);
    const tuning_overrides = {};
    for (const sel of document.querySelectorAll('#metaTunings select[data-kind]')) {
      const off = TUNING_PRESETS[sel.value];
      if (off) tuning_overrides[sel.dataset.kind] = sel.dataset.kind === 'Bass'
        ? off.slice(0, 4).map((v, i) => BASS_TUNING_MIDI[i] + v)
        : off.map((v, i) => STD_TUNING_MIDI[i] + v);
    }
    const rr = await fetch(`/jobs/${selectedJob.id}/rebuild`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tracks, tuning_overrides }),
    });
    if (!rr.ok) { const e = await rr.json(); alert(e.detail || T('Erro ao reconstruir.')); return; }
    const nj = await rr.json();
    closeMeta();
    toast(T('Arranjos/afinação aplicados — a reconstruir.'), 'ok');
    refreshJobs(); selectJob(nj.id);
    offerDropPrevious(nj.id);
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
  if (j.status === 'failed') return ['err', T('Falhou'), 'x'];
  if (j.status === 'pending') return ['run', T('Na fila…'), 'clock'];
  if (j.status === 'running') return ['run', T('A construir…'), 'clock'];
  if (!j.bundle_available) return ['warn', T('Sem ficheiros'), 'alert'];
  const gaps = [];
  if (!j.psarc_available) gaps.push('PSARC');
  if (!j.cover_art) gaps.push(T('capa'));
  return gaps.length ? ['warn', T('Falta: {list}', { list: gaps.join(', ') }), 'alert'] : ['ok', T('Pronto a jogar'), 'check'];
}
function renderJobCards() {
  const grid = document.getElementById('jobsGrid');
  grid.querySelectorAll('.proj-card, .home-empty').forEach(el => el.remove());
  const q = (document.getElementById('jobSearch').value || '').trim().toLowerCase();
  const shown = jobsCache.filter(JOB_FILTERS[jobFilter])
    .filter(j => !q || `${j.title} ${j.artist}`.toLowerCase().includes(q));
  if (jobsCache.length && !shown.length) {
    grid.insertAdjacentHTML('beforeend', '<p class="home-empty">' + T('Nenhum projeto corresponde a este filtro.') + '</p>');
  }
  for (const j of shown) {
    const [kind, text, ico] = jobCardStatus(j);
    const card = document.createElement('article');
    card.className = 'proj-card';
    card.innerHTML = `
      <button type="button" class="proj-open" aria-label="${T('Abrir {title}', { title: esc(j.title) })}">
        <div class="proj-cover">${j.cover_art ? `<img src="/jobs/${j.id}/cover" alt="" loading="lazy">` : icon('music')}</div>
        <div class="proj-meta">
          <div class="proj-title">${esc(j.title)}</div>
          <div class="proj-artist">${esc(j.artist)}</div>
          <span class="pv-chip ${kind}">${icon(ico)}${esc(text)}</span>
          ${isSynced(j) ? `<span class="pv-chip ok" title="${esc(SYNC_SOURCE_TEXT[j.sync_source])}">${icon('timer')}${T('Sincronizada')}</span>` : ''}
          ${j.status === 'completed' && !j.has_tones ? `<span class="pv-chip unk" title="${esc(T('Sem tons teus: o tom por defeito do DLC Builder (Lead/Combo: Marshall Plexi; Rhythm: Orange AD50).'))}">${icon('wave')}${T('Tons standard')}</span>` : ''}
        </div>
      </button>
      <button type="button" class="proj-del" title="${T('Remover projeto')}" aria-label="${T('Remover {title}', { title: esc(j.title) })}">${icon('trash')}</button>`;
    card.querySelector('.proj-open').onclick = () => selectJob(j.id);
    const img = card.querySelector('.proj-cover img');
    if (img) img.onerror = () => { img.replaceWith(document.createRange().createContextualFragment(icon('music'))); };
    card.querySelector('.proj-del').onclick = async () => {
      const running = j.status === 'running';
      const msg = running
        ? T('O projeto "{title}" ainda está a correr. Forçar a remoção? Só o deves fazer se estiver encravado (o worker morreu ou pendurou) — apaga também o bundle gerado.', { title: j.title })
        : T('Remover o projeto "{title}"? Isto apaga também o bundle gerado.', { title: j.title });
      const ok = await confirmModal(msg);
      if (!ok) return;
      const url = running ? `/jobs/${j.id}?force=true` : `/jobs/${j.id}`;
      const r = await fetch(url, { method: 'DELETE' });
      if (!r.ok && r.status !== 204) { toast((await r.json()).detail || T('erro')); return; }
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
       <button type="button" onclick="openMetaEdit()" title="${T('Editar título, artista, álbum, ano')}">${icon('edit')}${T('Editar info')}</button>
       ${j.rebuilt_from ? `<button type="button" onclick="selectJob('${j.rebuilt_from}')" title="${T('Abrir a versão de onde esta foi reconstruída — a anterior nunca é apagada')}">${icon('undo')}${T('Versão anterior')}</button>` : ''}
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

// The project the user asked to see. A poll (or a slow first load) for another
// one that answers after the user moved on, or closed the project, must not
// reopen it, take over selectedJob or re-arm its own poll.
let openJobId = null;

async function selectJob(id, { poll = false, force = false } = {}) {
  if (!poll) openJobId = id;
  else if (openJobId !== id) return;
  let j;
  try {
    j = await getJSON(`/jobs/${id}`);
  } catch (err) {
    if (openJobId !== id) return;
    // Keep the poll alive across a blip: the banner already says the server is
    // unreachable, and dropping the timer here would leave a job that finished
    // meanwhile stuck showing "running" until the user clicks something.
    if (poll) { clearTimeout(pollTimer); pollTimer = setTimeout(() => selectJob(id, { poll }), 2500); }
    else toast(T('não foi possível abrir o projeto: {msg}', { msg: err.message }), 'err');
    return;
  }
  if (openJobId !== id) return;
  selectedJob = j;
  maybeDropPrevious(j);
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
      ? `<details class="pv-warn"><summary>${warns.length === 1 ? T('1 aviso técnico') : T('{n} avisos técnicos', { n: warns.length })}</summary>` +
        warns.map(w => `<div class="warnbox">${esc(w)}</div>`).join('') + '</details>'
      : '');

  if (j.status === 'completed' && j.bundle_available) renderCompleteness(j);
  else {
    renderCompleteness(j);
    if (j.status === 'failed') setStatusChip('err', T('Falhou'), 'x');
    else if (j.status === 'completed') setStatusChip('warn', T('Concluído sem ficheiros'), 'alert');
    else setStatusChip('run', j.status === 'pending' ? T('Na fila…') : `${T('A construir…')}${j.stage ? ` ${j.stage}` : ''}`, 'clock');
  }

  const dl = document.getElementById('downloads');
  dl.innerHTML = '';
  if (j.psarc_available)
    dl.innerHTML += `<a class="dl-card" href="/jobs/${j.id}/psarc">${icon('gamepad')}<b>${T('PSARC para o jogo')}</b><span>${T('pronto a copiar para a pasta dlc do Rocksmith')}</span></a>`;
  if (j.bundle_available)
    dl.innerHTML += `<a class="dl-card" href="/jobs/${j.id}/bundle">${icon('package')}<b>${T('Bundle DLC Builder')}</b><span>${T('XML, áudio e projeto .rs2dlc para abrir no DLC Builder')}</span></a>`;
  if (j.bundle_available && !j.psarc_available) dl.innerHTML += `<span class="meta">${T('PSARC requer Wwise — ver README')}</span>`;
  if (!j.bundle_available) dl.innerHTML = '<span class="meta">' + T('Os ficheiros aparecem aqui quando a construção terminar.') + '</span>';
  renderInstallRow(j);
  document.getElementById('noteCountsInfo').textContent =
    T('Notas por pista: {list}', { list: Object.entries(j.note_counts || {}).map(([k, v]) => `${k} ${v}`).join(' · ') || '—' });

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
        toast(T('erro a carregar arranjos: {msg}', { msg: (e && e.message) || e }));
      }
    }
  } else {
    arrangementsLoadedFor = null;
    setReviewReady(false);
    clearInterval(lyricsPollTimer);
    lyricsEvents = [];
    lyricsBuilt = '[]';
  }

  // Re-arm with setTimeout (not setInterval): the next poll is scheduled only
  // after this one finishes, so a slow render can't stack overlapping calls.
  if (openJobId !== id) return;
  clearTimeout(pollTimer);
  if (j.status === 'pending' || j.status === 'running')
    pollTimer = setTimeout(() => selectJob(id, { poll: true }), 2500);
  refreshJobs();
}

async function loadArrangements(id) {
  tapState = null;
  renderTapUi();
  stopPendingHistory();
  clearLoop(false);  // a loop belongs to the recording it was set on  // the previous version's steps do not apply to this one
  arrangements = await getJSON(`/jobs/${id}/arrangements`);
  syncAnchorsByKind = {};  // fresh pending corrections per arrangement
  tempoScaleByKind = {};
  resetLyricFollow();
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
  fhpByKind = {};
  for (const a of arrangements) {
    if (a.hand_positions_edited) fhpByKind[a.kind] = (a.hand_positions || []).map(h => ({ time: h.time, fret: h.fret, width: h.width }));
  }
  fhpBuilt = JSON.stringify(fhpByKind);
  closeFhpPopup();
  noteClipboard = [];  // avoid pasting a previous song's notes into this one
  resetAttacks();  // they were measured on another project's recording
  noteDeleteUndo = null;
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
    `<p class="meta">${T('offsets: [{offsets}] · desvio: <span id="centOffsetVal">{cents}</span> cents · BPM médio: {bpm}', { offsets: a0.tuning_offsets.join(', '), cents: a0.cent_offset.toFixed(1), bpm: a0.average_bpm.toFixed(1) })}</p>`;
  centOffsetBuilt = a0.cent_offset;
  document.getElementById('centOffsetInput').value = a0.cent_offset.toFixed(1);
  document.getElementById('detectTuningInfo').textContent = '';
  document.getElementById('arrTabs').innerHTML = arrangements.map((a, i) =>
    `<button type="button" class="${i ? '' : 'active'}" onclick="showArr(${i})"></button>`).join('');
  updateArrTabs();
  document.getElementById('applyToAllLabel').style.display = arrangements.length > 1 ? '' : 'none';
  document.getElementById('applyToAllChk').checked = false;
  initSync(selectedJob);
  showArr(0);
  if (hw3dOn) setHw3d(true);  // remembered on: open the highway on this project too
  document.getElementById('tabwrap').scrollLeft = 0;
  renderSectionsList();
  updateClipboardInfo();
  updateSelectionInfo();
  await loadLyrics(id);
  await loadTones(id);
  if (selectedJob && selectedJob.id === id) startPendingHistory();
  // Resume polling if tone detection is in progress.
  if (selectedJob && selectedJob.tone_detection_status === 'detecting') {
    document.getElementById('toneDetectionWrap').style.display = '';
    pollToneDetection();
  }
}

// String colors low E -> high e: red, yellow, blue, orange, green, purple.
const STRING_COLORS = ['#e6483c', '#f5dc3c', '#3f9bdc', '#f0973c', '#5cc24a', '#b56cdc'];
// Note names, so the staff can label each string with its REAL pitch =
// STD_TUNING_MIDI + the arrangement's tuning offset (e.g. Drop C# shows
// C# G# C# F# A# D# instead of E A D G B e).
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
  if (tapState && i !== currentArr) stopTapSync();  // the taps belong to the chart they were made on
  notePendingChange();
  if (i !== currentArr) { loadArrSync(i); stopArrangementPreview(); }  // tab change: swap in that chart's own sync state
  currentArr = i;
  if (switchToneSet()) renderToneSetUi();  // per-track tones follow the tab too
  mainSyncFollow();  // the other charts take what changed on the main one
  renderSyncState(selectedJob);  // the card speaks for the chart on screen
  lyricsFollowSync();  // lyrics timed on the score move with its pending sync
  for (const [idx, btn] of document.querySelectorAll('#arrTabs button').entries())
    btn.classList.toggle('active', idx === i);
  const a = arrangements[i];
  const applyKindEl = document.getElementById('applyKind');
  if (applyKindEl) applyKindEl.textContent = arrLabel(a.kind);
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
  const px = BASE_PX * zoomLevel, ROW = staffRow(a), R = NOTE_R, W = Math.max(900, dur * px + 60);
  const H = STAFF_H, SB = STAFF_SB;
  tabPx = px; tabH = H;
  svg.setAttribute('width', W);
  svg.setAttribute('height', H);  // includes the chord-name band below the staff
  let s = '';
  s += waveformSvg(W, H, px);  // audio reference, drawn behind staff + notes
  for (let str = 0; str < stringCount(a); str++) {
    const y = SB - str * ROW;
    s += `<line x1="30" y1="${y}" x2="${W-10}" y2="${y}" stroke="#3a3c45"/>`;
    s += `<text x="6" y="${y+5}" fill="${STRING_COLORS[str]}" font-size="15" font-weight="700">${stringLabel(str, a.tuning_offsets)}</text>`;
  }
  if (a.capo) {
    const topY = SB - (stringCount(a) - 1) * ROW;
    s += `<text x="4" y="${topY - 12}" fill="#e8b04a" font-size="11" font-weight="700">${esc(T('Capo {n}', { n: a.capo }))}</text>`;
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
    // The bar line and its number are a click target of their own, so a bar
    // can be aligned by its START in the "Alinhar compasso" mode even when no
    // note sits there (a rest, a held note from the bar before). Drawn before
    // the notes, so a note on the line still wins the click.
    s += `<rect class="bar-hit" data-t="${b.time}" x="${x - 6}" y="28" width="12" height="${SB - 28}" fill="transparent"/>`
      + `<rect class="bar-hit" data-t="${b.time}" x="${x}" y="30" width="30" height="16" fill="transparent"/>`;
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
    s += `<g class="lyric-word${e === lyricSelected ? ' sel' : ''}" data-li="${li}" style="cursor:grab">`;
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
  hw3dRefresh(a, notes);  // the 3D highway shows the same notes, on the same clock
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
  // The user's FHPs are checked against the notes: a note its hand position
  // does not frame gets a red ring (playable, but worth a look).
  const fhps = fhpList(a);
  const checkFhp = fhpEdited(a) && fhps.length > 0;
  let fk = 0;
  for (const g of groups) {
    const sel = selectedTimes.has(g.time) ? ' selected' : '';
    const dispT = warp(previewScale(g.time));
    while (checkFhp && fk + 1 < fhps.length && fhps[fk + 1].time <= g.time + FHP_MATCH_S) fk++;
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
      if (n.link_next) {  // runs on into the next note on the string: a tie-like arc over the held time
        const xe = x + Math.max(susW, 18);
        s += `<path d="M${x + R * 0.6},${y - R + 2} Q${(x + xe) / 2},${y - R - 12} ${xe},${y - R + 2}" fill="none" stroke="${color}" stroke-width="2"><title>${esc(T('Ligada à nota seguinte (sem nova palhetada)'))}</title></path>`;
      }
      const shape = n.chord
        ? `<rect class="note-shape" x="${x-R}" y="${y-R}" width="${R*2}" height="${R*2}" rx="4" fill="${color}"${tech ? ' stroke="#fff" stroke-width="2.5" stroke-dasharray="3,3"' : ''}/>`
        : `<circle class="note-shape" cx="${x}" cy="${y}" r="${R}" fill="${color}"${tech ? ' stroke="#fff" stroke-width="2.5" stroke-dasharray="3,3"' : ''}/>`;
      s += shape;
      if (pending) s += `<circle cx="${x}" cy="${y}" r="${R+3}" fill="none" stroke="#3ddcc4" stroke-width="1.5" stroke-dasharray="2,2"/>`;
      if (checkFhp && !fhpCovers(fhps[fk], n.fret)) {
        const h = fhps[fk];
        s += `<circle cx="${x}" cy="${y}" r="${R+4}" fill="none" stroke="#e6483c" stroke-width="2"><title>${esc(T('Fora da posição da mão (trastes {a}–{b})', { a: h.fret, b: h.fret + h.width - 1 }))}</title></circle>`;
      }
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
  // Arpeggios: the run of single notes the game draws as one chord shape — a
  // bracket in the chord-name row (chords end an arpeggio, so the two never
  // share it), with the chord it spells.
  for (const ap of (a.arpeggios || [])) {
    const x1 = timeToX(warp(previewScale(ap.start))), x2 = timeToX(warp(previewScale(ap.end)));
    if (x2 < 24 || x1 > W - 4) continue;
    s += `<path d="M${x1},${H - 24} L${x1},${H - 30} L${x2},${H - 30} L${x2},${H - 24}" fill="none" stroke="#ffd479" stroke-width="1.5" opacity=".8"/>`;
    s += `<text x="${x1 + 3}" y="${H - 12}" fill="#ffd479" font-size="12" font-style="italic">${esc(ap.name ? T('arpejo {nome}', { nome: ap.name }) : T('arpejo'))}<title>${esc(T('Arpejo: notas soltas deixadas a soar sobre a forma de um acorde — o jogo mostra a forma por cima delas.'))}</title></text>`;
  }
  if (attacksVisible()) s += attacksSvg(groups, warp, W, SB);
  s += fhpLaneSvg(a, fhps, warp, W, SB + 40);
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
  s += loopBandSvg(H);
  const phX = 30 + currentPlayheadT * tabPx;
  s += `<line id="playhead" x1="${phX}" y1="0" x2="${phX}" y2="${H}" stroke="#ff7a45" stroke-width="2" opacity=".9"/>`;
  // "Detect first note" marker: the recording point where the 1st note sounds.
  if (firstNoteFlow === 'note') {
    const mx = 30 + firstNoteAudioT * tabPx;
    s += `<line x1="${mx}" y1="0" x2="${mx}" y2="${H}" stroke="#3fdc8a" stroke-width="2" stroke-dasharray="5,3"/>`;
    s += `<text x="${mx+4}" y="52" fill="#3fdc8a" font-size="11" font-weight="700">${T('1ª nota')}</text>`;
  }
  svg.innerHTML = s;
  invalidateLyricWords();  // the nodes the playhead frame highlights were just replaced
  syncResetPointer();
  renderAnchorsList();
  updateSyncOffsetDisplay();
  updateBarSyncPanel();
  fillTapBars();
  fillAutoSyncBars();
  renderAttacksCard();
  renderEstimatedBars();
  updateNoteEditsInfo();
  updateDeleteNotesUi();
  updateFhpUi();
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
      slide_to: ov.slide_to_fret ?? -1,
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

// Fret-hand positions (FHPs, the game's "anchors"): where the hand sits, from
// one FHP to the next. A chart the user never touched gets the automatic ones
// (a.hand_positions, as built); once edited, fhpByKind[kind] holds ALL of that
// chart's FHPs, in the BUILT clock like the notes, carried through the pending
// sync only when sent (fhpForRebuild) — so they follow a correction the same
// rebuild applies. Always sent whole, seeded from the committed ones on load.
let fhpByKind = {};
let fhpBuilt = '{}';
let fhpContext = null;  // the open popup's {time, k}
const FHP_MATCH_S = 0.005;
function fhpList(a) { return (a && (fhpByKind[a.kind] || a.hand_positions)) || []; }
function fhpEdited(a) { return !!(a && fhpByKind[a.kind]); }
function fhpCovers(h, fret) { return fret <= 0 || (fret >= h.fret && fret < h.fret + h.width); }
// Chart `idx`'s time as it shows now (and as the next build places it).
function chartDisplayTime(idx, t) {
  return idx === currentArr ? buildTimeWarp(syncAnchors)(previewScale(t)) : arrangementDisplayTime(idx, t);
}
function fhpForRebuild() {
  const out = {};
  arrangements.forEach((a, idx) => {
    const list = fhpByKind[a.kind];
    if (!list || !list.length) return;
    out[a.kind] = list
      .map(h => ({ time: Math.max(0, Math.round(chartDisplayTime(idx, h.time) * 1000) / 1000), fret: h.fret, width: h.width }))
      .sort((x, y) => x.time - y.time);
  });
  return out;
}
function fhpLaneSvg(a, fhps, warp, W, y) {
  if (!fhps.length) return '';
  const edited = fhpEdited(a);
  const built = JSON.parse(fhpBuilt)[a.kind] || null;
  const pending = JSON.stringify(fhpByKind[a.kind] || null) !== JSON.stringify(built);
  const col = edited ? '#3ddcc4' : '#7d8aa5';
  const tip = edited ? T('Posições da mão (FHP) tuas') : T('Posições da mão (FHP) automáticas');
  let s = `<text x="2" y="${y + 12}" fill="${col}" font-size="10" font-weight="700">FHP<title>${esc(tip)}</title></text>`;
  const xs = fhps.map((h, k) => (k === 0 ? 30 : timeToX(warp(previewScale(h.time)))));
  fhps.forEach((h, k) => {
    const x1 = Math.max(30, xs[k]);
    const x2 = k + 1 < fhps.length ? xs[k + 1] : W - 10;
    if (x2 < 24 || x1 > W - 4) return;
    const last = h.fret + h.width - 1;
    const label = x2 - x1 > 38 ? `${h.fret}–${last}` : (x2 - x1 > 14 ? `${h.fret}` : '');
    s += `<g class="fhp-bar" data-k="${k}"><rect x="${x1 + 1}" y="${y}" width="${Math.max(3, x2 - x1 - 2)}" height="16" rx="3" fill="#1d2129" stroke="${col}" stroke-width="1"${pending ? ' stroke-dasharray="3,2"' : ''} opacity=".95"/>`
      + `<line x1="${x1 + 1}" y1="${y - 3}" x2="${x1 + 1}" y2="${y + 16}" stroke="${col}" stroke-width="2"/>`
      + (label ? `<text x="${x1 + 5}" y="${y + 12}" fill="${col}" font-size="11" font-weight="700">${label}</text>` : '')
      + `<title>${esc(T('Mão nos trastes {a}–{b}', { a: h.fret, b: last }))}</title></g>`;
  });
  return s;
}
// The chart's FHPs as an editable list (a copy of the automatic ones the first time).
function fhpEditable(a) {
  if (!fhpByKind[a.kind]) fhpByKind[a.kind] = (a.hand_positions || []).map(h => ({ time: h.time, fret: h.fret, width: h.width }));
  return fhpByKind[a.kind];
}
function updateFhpUi() {
  const a = arrangements[currentArr];
  const btn = document.getElementById('resetFhp');
  if (btn) btn.disabled = !fhpEdited(a);
}
function openFhpPopup(t, clientX, clientY, k = null) {
  const a = arrangements[currentArr];
  if (!a) return;
  const list = fhpList(a);
  if (k == null) {
    const at = list.findIndex(h => Math.abs(h.time - t) <= FHP_MATCH_S);
    if (at >= 0) k = at;
  }
  let fret, width;
  if (k != null && list[k]) {
    ({ fret, width } = list[k]);
    t = list[k].time;
  } else {
    // A new FHP from this note: the hand where its lowest fretted note is.
    const frets = a.notes.filter(n => Math.abs(n.time - t) < 0.03 && n.fret > 0).map(n => n.fret);
    const owner = list.filter(h => h.time <= t + FHP_MATCH_S).pop() || list[0];
    width = owner ? owner.width : 4;
    fret = frets.length ? Math.min(Math.min(...frets), 25 - width) : (owner ? owner.fret : 1);
  }
  fhpContext = { time: t, k };
  document.getElementById('fhpPopupTitle').textContent = k != null
    ? T('Posição da mão a partir de {t}s', { t: (chartDisplayTime(currentArr, t) - viewOrigin).toFixed(2) })
    : T('Nova posição da mão a partir desta nota');
  document.getElementById('fhpFret').value = fret;
  document.getElementById('fhpWidth').value = width;
  document.getElementById('fhpDelete').style.display = k != null ? '' : 'none';
  fhpRangeText();
  const pop = document.getElementById('fhpPopup');
  pop.hidden = false;
  const w = pop.offsetWidth, h = pop.offsetHeight;
  let x = clientX + 10, y = clientY + 10;
  if (x + w > window.innerWidth - 8) x = clientX - w - 10;
  if (y + h > window.innerHeight - 8) y = window.innerHeight - h - 8;
  pop.style.left = Math.max(8, x) + 'px';
  pop.style.top = Math.max(8, y) + 'px';
  document.getElementById('fhpFret').focus();
}
function fhpRangeText() {
  const fret = parseInt(document.getElementById('fhpFret').value, 10);
  const width = parseInt(document.getElementById('fhpWidth').value, 10);
  const ok = fret >= 1 && width >= 2 && width <= 12 && fret + width - 1 <= 24;
  document.getElementById('fhpRange').textContent = ok
    ? T('A mão cobre os trastes {a} a {b}.', { a: fret, b: fret + width - 1 })
    : T('Traste de 1 a 24, largura de 2 a 12, sem passar do traste 24.');
}
function closeFhpPopup() { document.getElementById('fhpPopup').hidden = true; fhpContext = null; }
(function wireFhpPopup() {
  const pop = document.getElementById('fhpPopup');
  if (!pop) return;
  document.getElementById('fhpFret').addEventListener('input', fhpRangeText);
  document.getElementById('fhpWidth').addEventListener('input', fhpRangeText);
  document.getElementById('fhpCancel').addEventListener('click', closeFhpPopup);
  document.getElementById('fhpSave').addEventListener('click', () => {
    const a = arrangements[currentArr];
    if (!fhpContext || !a) return;
    const fret = parseInt(document.getElementById('fhpFret').value, 10);
    const width = parseInt(document.getElementById('fhpWidth').value, 10);
    if (!(fret >= 1 && width >= 2 && width <= 12 && fret + width - 1 <= 24)) {
      toast(T('Traste de 1 a 24, largura de 2 a 12, sem passar do traste 24.'), 'err');
      return;
    }
    const list = fhpEditable(a);
    const at = fhpContext.k != null ? fhpContext.k : list.findIndex(h => Math.abs(h.time - fhpContext.time) <= FHP_MATCH_S);
    const h = { time: fhpContext.time, fret, width };
    if (at >= 0 && list[at]) list[at] = h; else list.push(h);
    list.sort((x, y) => x.time - y.time);
    closeFhpPopup();
    showArr(currentArr);
    updatePendingChangesInfo();
    toast(T('Posição da mão guardada — pendente até "Aplicar e reconstruir".'), 'ok');
  });
  document.getElementById('fhpDelete').addEventListener('click', () => {
    const a = arrangements[currentArr];
    if (!fhpContext || fhpContext.k == null || !a) return;
    const list = fhpEditable(a);
    list.splice(fhpContext.k, 1);
    // With none left the chart goes back to the automatic ones.
    if (!list.length) delete fhpByKind[a.kind];
    closeFhpPopup();
    showArr(currentArr);
    updatePendingChangesInfo();
    toast(list.length ? T('Posição da mão apagada — pendente até "Aplicar e reconstruir".')
      : T('Sem posições da mão tuas: a pista volta às automáticas.'), 'ok');
  });
  pop.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); document.getElementById('fhpSave').click(); }
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeFhpPopup(); });
  document.addEventListener('pointerdown', e => {
    if (!pop.hidden && !pop.contains(e.target) && !e.target.closest('#tabsvg')) closeFhpPopup();
  });
  document.getElementById('resetFhp')?.addEventListener('click', () => {
    const a = arrangements[currentArr];
    if (!a || !fhpByKind[a.kind]) return;
    delete fhpByKind[a.kind];
    showArr(currentArr);
    updatePendingChangesInfo();
    toast(T('Posições da mão desta pista de volta às automáticas — pendente até "Aplicar e reconstruir".'), 'ok');
  });
})();

function updateClipboardInfo() {
  const el = document.getElementById('clipboardInfo');
  const btn = document.getElementById('pasteNotes');
  if (!el || !btn) return;
  el.textContent = noteClipboard.length ? T('{n} nota(s) copiada(s)', { n: noteClipboard.length }) : '';
  btn.disabled = !noteClipboard.length;
}

// Copies the CURRENTLY SELECTED notes (selectedTimes, from Shift+click/
// Ctrl+click/Excerto — the same selection "Excerto" drag already uses) from
// this arrangement's live (pending-edits-merged) note list, normalized to
// relative offsets from the earliest copied note so paste can re-anchor them
// anywhere.
function copySelectedNotes() {
  if (!selectedTimes.size) { toast(T('seleciona notas primeiro (Shift+clique ou modo Excerto)'), 'err'); return; }
  const a = arrangements[currentArr];
  if (!a) return;
  const pendingOv = noteOverridesByKind[a.kind] || [];
  const merged = pendingOv.length ? mergeNoteOverrides(a.notes, pendingOv) : a.notes;
  const times = [...selectedTimes];
  const picked = merged.filter(n => times.some(t => Math.abs(t - n.time) < 0.03));
  if (!picked.length) { toast(T('nada selecionado para copiar'), 'err'); return; }
  const minTime = Math.min(...picked.map(n => n.time));
  noteClipboard = picked.map(n => ({
    dTime: n.time - minTime, string: n.string, fret: n.fret, sustain: n.sustain,
    techniques: (n.techniques || []).slice(), bend_semitones: n.bend_semitones || 0,
  }));
  updateClipboardInfo();
  toast(T('{n} nota(s) copiada(s).', { n: noteClipboard.length }), 'ok');
}

// Pastes the clipboard at the current playhead, snapped to the sync grid
// (nearestGridChartTime) — only the anchor note snaps; the rest keep their
// original relative spacing, so a copied riff's own rhythm is preserved.
function pasteNotesAtCursor() {
  if (!noteClipboard.length) { toast(T('nada copiado ainda'), 'err'); return; }
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
  toast(T('{n} nota(s) colada(s) — pendente até "Aplicar e reconstruir".', { n: noteClipboard.length }), 'ok');
}

// ---- Deleting notes: every selected note (Ctrl/Shift+click, Excerto) of this
// arrangement at once, from any mode — the single-note "Remover nota" needs
// the "Editar notas" popup one note at a time. Same primitive as that button
// (a deleted override), so it previews, rides "Aplicar e reconstruir" and
// round-trips like any note edit. The last delete can be undone: once a
// built note is gone from the score there is nothing left to click to bring
// it back, short of discarding EVERY edit of the track.
// {kind, prior: [{time, string, ov}]} — the override each deleted note had
// before (null = none). Undo restores exactly those slots, so an edit made
// AFTER the delete (elsewhere in the track) survives the undo.
let noteDeleteUndo = null;

// Removes one note of the CURRENT arrangement: a built note gets a deleted
// override (keyed on its own exact time, as the backend matches); a note that
// exists only as a pending insertion simply loses that insertion.
function deleteNoteAt(time, string) {
  const built = findBuiltNoteAt(time, string);
  if (built) {
    upsertNoteOverride({
      time: built.time, string, fret: 0, sustain: 0,
      techniques: [], bend_semitones: 0, slide_to_fret: null, deleted: true,
    });
    return;
  }
  const k = currentKind();
  const list = noteOverridesByKind[k] || [];
  const i = list.findIndex(o => o.string === string && Math.abs(o.time - time) < 0.03);
  if (i >= 0) list.splice(i, 1);
  // An empty list would still read as "Pendente: edições de notas".
  if (!list.length) delete noteOverridesByKind[k];
}

function updateDeleteNotesUi() {
  const n = selectedTimes.size;
  const del = document.getElementById('deleteNotes');
  if (del) del.disabled = n === 0;
  const btn = document.getElementById('deleteSelection');
  if (btn) btn.hidden = n === 0;
  const undo = document.getElementById('undoDeleteNotes');
  if (undo) undo.disabled = !noteDeleteUndo || noteDeleteUndo.kind !== currentKind();
}

function deleteSelectedNotes() {
  if (!selectedTimes.size) { toast(T('seleciona notas primeiro (Ctrl+clique, Shift+clique ou modo Excerto)'), 'err'); return; }
  const a = arrangements[currentArr];
  if (!a) return;
  const pendingOv = noteOverridesByKind[a.kind] || [];
  const merged = pendingOv.length ? mergeNoteOverrides(a.notes, pendingOv) : a.notes;
  const times = [...selectedTimes];
  const picked = merged.filter(n => times.some(t => Math.abs(t - n.time) < 0.03));
  if (!picked.length) { toast(T('nada selecionado para apagar'), 'err'); return; }
  const slot = n => pendingOv.find(o => o.string === n.string && Math.abs(o.time - n.time) < 0.03);
  noteDeleteUndo = {
    kind: a.kind,
    prior: picked.map(n => ({ time: n.time, string: n.string, ov: slot(n) ? JSON.parse(JSON.stringify(slot(n))) : null })),
  };
  for (const n of picked) deleteNoteAt(n.time, n.string);
  selectedTimes.clear();
  updateSelectionInfo();
  updatePendingChangesInfo();
  showArr(currentArr);
  toast(T('{n} nota(s) apagada(s) — Ctrl+Z desfaz; pendente até "Aplicar e reconstruir".', { n: picked.length }), 'ok');
}

function undoNoteDelete() {
  const u = noteDeleteUndo;
  if (!u) { toast(T('nada apagado para desfazer'), 'err'); return; }
  if (u.kind !== currentKind()) { toast(T('o último apagar foi na pista {kind} — muda para ela para desfazer', { kind: arrLabel(u.kind) }), 'err'); return; }
  const list = noteOverridesByKind[u.kind] || [];
  for (const p of u.prior) {
    const i = list.findIndex(o => o.string === p.string && Math.abs(o.time - p.time) < 0.03);
    if (i >= 0) list.splice(i, 1);
    if (p.ov) list.push(p.ov);
  }
  if (list.length) noteOverridesByKind[u.kind] = list;
  else delete noteOverridesByKind[u.kind];
  noteDeleteUndo = null;
  updatePendingChangesInfo();
  showArr(currentArr);
  toast(T('Notas repostas.'), 'ok');
}

document.getElementById('deleteNotes')?.addEventListener('click', deleteSelectedNotes);
document.getElementById('deleteSelection')?.addEventListener('click', deleteSelectedNotes);
document.getElementById('undoDeleteNotes')?.addEventListener('click', undoNoteDelete);
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
  kindEl.textContent = `(${arrLabel(currentKind()) || ''})`;
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
// ── Pista principal (the main chart for sync) ────────────────────────────────
// What the user changes on the main chart's sync (its "Início", tempo, any
// correction) reaches every other chart as the SAME change of time: main at
// 0 s → 1 s moves a chart whose first note is at 30 s to 31 s. The change is
// the map D (built time → where the main chart shows it now) before and after
// the edit; each other chart's display map G becomes (D_new ∘ D_old⁻¹) ∘ G,
// written back as that chart's own PENDING anchors — so it previews on its
// tab, can still be corrected there, and is committed by the rebuild
// (other_sync). Undoing on the main chart takes the others back.
let syncMain = null;          // kind of the main chart, or null
let mainFollowState = null;   // the main chart's pending sync as last carried
function mainSyncState() {
  const a = syncMain && arrangements.find(x => x.kind === syncMain);
  if (!a || !isGpJob()) return null;
  const ratio = tempoRatioOf(a);
  const anchors = (syncAnchorsByKind[a.kind] || []).map(p => p.slice());
  return { ratio, anchors, sig: JSON.stringify([ratio, anchors]) };
}
function mainSyncFn(st) {
  const warp = buildTimeWarp(st.anchors);
  const pad = livePad();
  return x => warp((x - scoreShift) * st.ratio + pad);
}
// Built times where D bends (its anchors, taken back through the tempo preview).
function mainSyncKinks(st) {
  const pad = livePad();
  return st.anchors.map(([o]) => (o - pad) / st.ratio + scoreShift);
}
function resetMainFollow() { mainFollowState = mainSyncState(); }
// The span of chart `idx` in its own preview coordinates (what anchors use).
function chartSpan(idx) {
  const a = arrangements[idx];
  const times = [...(a.beats || []), ...(a.bars || []).map(b => b.time), ...a.notes.map(n => n.time + (n.sustain || 0))];
  if (!times.length) return null;
  return [arrangementPreviewScale(idx, Math.min(...times)), arrangementPreviewScale(idx, Math.max(...times)) + 1];
}
// The anchors that make chart `idx`'s display map `delta ∘ G`. A uniform shift
// on a chart with at most one anchor stays ONE anchor on its first note (what
// its "Início" field edits); anything else pins both ends of the chart so the
// multi-anchor warp (identity outside its range) covers every note, plus every
// point where G or delta bends.
function followAnchors(idx, list, delta, kinks, shift) {
  const a = arrangements[idx];
  if (shift != null && list.length <= 1) {
    if (list.length === 1) {
      const [o, t] = list[0];
      return Math.abs(t + shift - o) < 1e-9 ? [] : [[o, t + shift]];
    }
    if (!a.notes.length || Math.abs(shift) < 1e-9) return [];
    const p = arrangementPreviewScale(idx, Math.min(...a.notes.map(n => n.time)));
    return [[p, p + shift]];
  }
  const span = chartSpan(idx);
  if (!span) return list;
  const G = buildTimeWarp(list);
  const pts = new Set(span);
  for (const [o] of list) if (o > span[0] && o < span[1]) pts.add(o);
  for (const y of kinks) {
    const p = invertIncreasing(G, y);
    if (p > span[0] && p < span[1]) pts.add(p);
  }
  const out = [...pts].sort((x, y) => x - y).map(p => [p, delta(G(p))]);
  return out.every(([o, t]) => Math.abs(t - o) < 1e-6) ? [] : out;
}
function mainSyncFollow() {
  if (!syncMain) { mainFollowState = null; return; }
  const now = mainSyncState();
  if (!now) return;
  const prev = mainFollowState;
  mainFollowState = now;
  if (!prev || prev.sig === now.sig) return;
  const dOld = mainSyncFn(prev), dNew = mainSyncFn(now);
  const uniform = prev.anchors.length <= 1 && now.anchors.length <= 1 && Math.abs(prev.ratio - now.ratio) < 1e-12;
  const shift = uniform ? dNew(scoreShift) - dOld(scoreShift) : null;
  const delta = uniform ? (y => y + shift) : (y => dNew(invertIncreasing(dOld, y)));
  const kinks = uniform ? [] : [...mainSyncKinks(prev), ...mainSyncKinks(now)].map(dOld);
  for (let i = 0; i < arrangements.length; i++) {
    const kind = arrangements[i].kind;
    if (kind === syncMain) continue;
    const list = syncAnchorsByKind[kind] || (syncAnchorsByKind[kind] = []);
    const next = followAnchors(i, list, delta, kinks, shift);
    list.splice(0, list.length, ...next);  // in place: syncAnchors may BE this array
  }
  renderAnchorsList();
  updatePendingChangesInfo();
}
// Every chart but the one on screen that has pending sync, for other_sync.
function otherPendingSync() {
  const out = {};
  for (const a of arrangements) {
    if (a.kind === currentKind()) continue;
    const anchors = syncAnchorsByKind[a.kind] || [];
    const scale = tempoScaleByKind[a.kind];
    const tempoChanged = scale != null && Math.abs(scale - (a.tempo_scale || 1)) > 1e-4;
    if (anchors.length || tempoChanged)
      out[a.kind] = { tempo_scale: tempoChanged ? scale : null, sync_anchors: anchors.map(p => p.slice()) };
  }
  return out;
}
function renderSyncMain(j) {
  const card = document.getElementById('syncMainCard');
  if (!card) return;
  const show = !!j && j.source_type === 'gp' && j.status === 'completed' && arrangements.length > 1;
  card.hidden = !show;
  if (!show) return;
  const sel = document.getElementById('syncMainSel');
  sel.innerHTML = '<option value="">' + T('— nenhuma (cada pista à parte) —') + '</option>' +
    arrangements.map(a => `<option value="${esc(a.kind)}">${esc(arrLabel(a.kind))}</option>`).join('');
  sel.value = syncMain || '';
  const kind = currentKind();
  document.getElementById('syncMainNote').textContent = !syncMain ? ''
    : kind === syncMain ? T('Esta é a pista principal: o que mudares aqui passa para as outras.')
      : T('Esta pista segue a {main}: o que mudares lá chega aqui. Podes também acertá-la à parte.', { main: arrLabel(syncMain) });
}
document.getElementById('syncMainSel').addEventListener('change', async e => {
  if (!selectedJob) return;
  const pick = e.target.value || null;
  try {
    const out = await getJSON(`/jobs/${selectedJob.id}/sync-main`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ arrangement: pick }),
    });
    selectedJob.sync_main = out.sync_main;
    syncMain = out.sync_main || null;
    resetMainFollow();  // only what changes from now on is carried
    renderSyncMain(selectedJob);
    toast(syncMain ? T('Pista principal: {main}.', { main: arrLabel(syncMain) }) : T('Sem pista principal.'), 'ok');
  } catch (err) {
    e.target.value = syncMain || '';
    toast(T('não foi possível guardar: {msg}', { msg: err.message }));
  }
});

function arrangementPreviewScale(idx, t) {
  if (!isGpJob()) return t;
  const a = arrangements[idx];
  if (!a) return t;
  return (t - scoreShift) * tempoRatioOf(a) + livePad();
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

// [3, 4, 5, 9] → [[3, 5], [9, 9]]
function barRanges(numbers) {
  const ranges = [];
  for (const n of numbers) {
    const last = ranges[ranges.length - 1];
    if (last && n === last[1] + 1) last[1] = n;
    else ranges.push([n, n]);
  }
  return ranges;
}

// Put the cursor on bar `measure` of the current arrangement (where it sits
// now, with the live sync) and bring it into view; the bar-sync selector
// follows, so "= cursor" works on it straight away.
function goToBar(measure) {
  const chartT = barChartTime(currentArr, measure);
  if (chartT == null) return;
  const displayT = arrangementDisplayTime(currentArr, chartT);
  audioSeek(Math.max(0, displayT - viewOrigin));
  const wrap = document.getElementById('tabwrap');
  wrap.scrollLeft = Math.max(0, timeToX(displayT) - wrap.clientWidth / 2);
  const barSel = document.getElementById('barSyncBar');
  if ([...barSel.options].some(o => o.value === String(measure))) {
    barSel.value = String(measure);
    barSel.dispatchEvent(new Event('change'));  // the bar-tempo controls follow it
  }
}

// The bars whose rhythm PDF-to-GP5 estimated from the note spacing when it
// converted this track (a part that prints rhythm elsewhere): one button per
// run of bars, each putting the cursor on its first bar — the ones to check
// before trusting the chart. Each pass of a repeated bar is a bar of its own.
function renderEstimatedBars() {
  const row = document.getElementById('barEstimatedRow');
  const list = document.getElementById('barEstimatedList');
  const bars = (arrangements[currentArr] && arrangements[currentArr].estimated_bars) || [];
  row.style.display = bars.length ? '' : 'none';
  const MAX_SHOWN = 40;
  const ranges = barRanges(bars);
  list.replaceChildren(...ranges.slice(0, MAX_SHOWN).map(([first, last]) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'secondary';
    btn.textContent = first === last ? String(first) : `${first}–${last}`;
    btn.title = T('Pôr o cursor no compasso {n}', { n: first });
    btn.addEventListener('click', () => goToBar(first));
    return btn;
  }));
  if (ranges.length > MAX_SHOWN) list.append('…');
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
  barSel.innerHTML = bars.map(b => `<option value="${b.measure}">${T('Compasso {n}', { n: b.measure })}</option>`).join('');
  if (bars.some(b => String(b.measure) === prevBar)) barSel.value = prevBar;
  const bpmInput = document.getElementById('barBpm');
  // Leave a value the user is typing alone; a redraw happens on every edit.
  if (bpmInput && document.activeElement !== bpmInput && barSel.value) {
    fillBarTempoControls(parseInt(barSel.value, 10), document.getElementById('barBpmTo'), bpmInput);
  }

  const others = arrangements.map((a, i) => ({ a, i })).filter(o => o.i !== currentArr);
  document.getElementById('barSyncRefRow').style.display = others.length ? '' : 'none';
  const refSel = document.getElementById('barSyncRefArr');
  const prevRef = refSel.value;
  refSel.innerHTML = others.map(o => `<option value="${o.i}">${esc(arrLabel(o.a.kind))}</option>`).join('');
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

// ---- Per-bar tempo: "mudar o BPM do compasso" ----
// Sets bars [from..to] to one BPM and moves EVERYTHING after them by the
// difference, so each later bar keeps its own tempo (a passage does not get
// re-timed just because an earlier bar was). Expressed as ordinary pending
// anchors — the same currency as every other sync tool — so it previews live,
// rides "Aplicar e reconstruir", is drawn in amber by barTempoTable and is what
// "Guitar Pro com os andamentos corrigidos" writes.

// Chart-time span of bars [fromM..toM]: from the first bar's downbeat to the
// next bar's; for the song's LAST bar (which has no next downbeat) to its own
// last beat, one beat short. Null when there is nothing to re-time.
function barSpan(a, fromM, toM) {
  const bars = a.bars || [], beats = a.beats || [];
  const i0 = bars.findIndex(b => b.measure === fromM);
  const i1 = bars.findIndex(b => b.measure === toM);
  if (i0 < 0 || i1 < i0) return null;
  const startT = bars[i0].time;
  let endT = i1 + 1 < bars.length ? bars[i1 + 1].time : null;
  if (endT == null) {
    const inLast = beats.filter(t => t >= bars[i1].time - 1e-6);
    if (inLast.length < 2) return null;
    endT = inLast[inLast.length - 1];
  }
  const n = beats.filter(t => t >= startT - 1e-6 && t < endT - 1e-6).length;
  return n > 0 && endT > startT ? { startT, endT, beats: n } : null;
}

// Where the chart ends, in chart time: the last beat, bar or note end.
function songEndChartTime(a) {
  let end = 0;
  for (const t of a.beats || []) end = Math.max(end, t);
  for (const b of a.bars || []) end = Math.max(end, b.time);
  for (const n of a.notes || []) end = Math.max(end, n.time + (n.sustain || 0));
  return end;
}

// The anchor list (pure) that gives the span [startO, endO] (warp-domain
// times, i.e. previewScale'd) `beats` beats at `bpm`, keeping everything before
// it where it is on screen and shifting everything after it by the difference.
// Pending anchors inside the span are superseded; the ones after it move with
// the tail. A LONE anchor is a uniform shift of the whole song, which stops
// being one as soon as a second anchor exists — so the song start is pinned
// with that same shift first, or the bars before this one would lose it.
function planBarRetempo(anchors, warp, p) {
  const EPS = 0.05;
  const startD = warp(p.startO), endD = warp(p.endO);
  const newEndD = startD + p.beats * 60 / p.bpm;
  const delta = newEndD - endD;
  const out = [];
  if (anchors.length === 1 && p.songStartO < p.startO - EPS
      && p.songStartO < anchors[0][0] - EPS) {
    out.push([p.songStartO, warp(p.songStartO)]);
  }
  for (const [o, t] of anchors) {
    if (o < p.startO - EPS) out.push([o, t]);
    else if (o > p.endO + EPS) out.push([o, t + delta]);
  }
  out.push([p.startO, startD], [p.endO, newEndD]);
  if (p.tailO > p.endO + EPS && !out.some(([o]) => Math.abs(o - p.tailO) < EPS)) {
    out.push([p.tailO, warp(p.tailO) + delta]);
  }
  out.sort((x, y) => x[0] - y[0]);
  return { anchors: out, delta };
}

// The bar's tempo as the score shows it now (pending edits included).
function barDisplayBpm(measure) {
  const a = arrangements[currentArr];
  const span = a && barSpan(a, measure, measure);
  if (!span) return null;
  const warp = buildTimeWarp(syncAnchors);
  const dur = warp(previewScale(span.endT)) - warp(previewScale(span.startT));
  return dur > 0.01 ? span.beats * 60 / dur : null;
}

const BAR_BPM_MIN = 10, BAR_BPM_MAX = 400;  // the Guitar Pro export's own bounds

function setBarsTempo(fromM, toM, bpm) {
  const a = arrangements[currentArr];
  if (!a || !isGpJob()) return { ok: false, why: T('sem partitura') };
  if (!(bpm >= BAR_BPM_MIN && bpm <= BAR_BPM_MAX)) {
    return { ok: false, why: T('o BPM tem de estar entre {min} e {max}', { min: BAR_BPM_MIN, max: BAR_BPM_MAX }) };
  }
  const span = barSpan(a, fromM, toM);
  if (!span) return { ok: false, why: T('esses compassos não têm tempos que se possam mudar') };
  const firstBar = (a.bars || [])[0];
  const plan = planBarRetempo(syncAnchors, buildTimeWarp(syncAnchors), {
    startO: previewScale(span.startT), endO: previewScale(span.endT), beats: span.beats, bpm,
    tailO: previewScale(songEndChartTime(a)),
    songStartO: previewScale(firstBar ? firstBar.time : span.startT),
  });
  // In place: syncAnchors IS this arrangement's entry in syncAnchorsByKind.
  syncAnchors.splice(0, syncAnchors.length, ...plan.anchors);
  renderAnchorsList();
  updatePendingChangesInfo();
  showArr(currentArr);
  return { ok: true, delta: plan.delta };
}

// ── "Marcar a ouvir": tap the bars (or beats) while the recording plays ──────
// For a tab that was never synced (one tempo for the whole song, written by
// ear): the human marks WHEN each bar starts, the way Songsterr's per-measure
// video times are marked — the thing that makes those tabs line up. Each tap
// becomes an ordinary pending anchor (that grid point's chart time → the
// instant tapped), so it previews live, rides "Aplicar e reconstruir", undo/
// redo and the main-chart propagation, with no backend change.
const TAP_SMOOTH_K = 2;  // neighbours on each side the jitter of a tap is averaged over

// Each tap moved onto the straight line through its neighbours (a local
// least-squares fit of time against tap number), so a hand's ±30 ms jitter
// does not shake every bar while a real tempo change, spread over several
// bars, still comes through.
function smoothTaps(times, k = TAP_SMOOTH_K) {
  if (times.length < 3) return times.slice();
  return times.map((_, i) => {
    const lo = Math.max(0, i - k), hi = Math.min(times.length - 1, i + k);
    let n = 0, sx = 0, sy = 0, sxx = 0, sxy = 0;
    for (let j = lo; j <= hi; j++) { n++; sx += j; sy += times[j]; sxx += j * j; sxy += j * times[j]; }
    const den = n * sxx - sx * sx;
    if (!den) return times[i];
    const b = (n * sxy - sx * sy) / den;
    return (sy - b * sx) / n + b * i;
  });
}

// The anchor list (pure) that puts each tapped grid point `p.points[i] =
// [origin, tapped]` (warp domain → display) where it was tapped: what comes
// before the first tap stays where it shows now (the song's start pinned
// there, as a lone "Início" anchor stops being a uniform shift once others
// exist), pending anchors inside the tapped span are superseded, and what
// comes after the last tap keeps its own timing, shifted by that tap's
// difference (the song's end pinned with it).
function planTaps(anchors, warp, p) {
  const EPS = 0.05;
  const pts = p.points;
  if (!pts.length) return anchors.map(a => a.slice());
  const firstO = pts[0][0], lastO = pts[pts.length - 1][0];
  const delta = pts[pts.length - 1][1] - warp(lastO);
  const out = [];
  if (p.songStartO < firstO - EPS && !anchors.some(([o]) => o < firstO - EPS)) {
    out.push([p.songStartO, warp(p.songStartO)]);
  }
  for (const [o, d] of anchors) {
    if (o < firstO - EPS) out.push([o, d]);
    else if (o > lastO + EPS) out.push([o, d + delta]);
  }
  for (const pt of pts) out.push(pt.slice());
  if (p.tailO > lastO + EPS && !out.some(([o]) => Math.abs(o - p.tailO) < EPS)) {
    out.push([p.tailO, warp(p.tailO) + delta]);
  }
  out.sort((x, y) => x[0] - y[0]);
  return out;
}

let tapState = null;  // {grid: [chart times], taps: [display times], base: [anchors], kind}

// The chart times the taps land on: each bar's downbeat from `fromM`, or
// every beat from that bar's downbeat.
function tapGrid(a, fromM, mode) {
  const bars = (a.bars || []).filter(b => b.measure >= fromM);
  if (!bars.length) return [];
  if (mode === 'bars') return bars.map(b => b.time);
  return (a.beats || []).filter(t => t >= bars[0].time - 1e-6);
}

// What the output latency hides: the sound at audioTime() reaches the ears
// that much later, so a tap in time with it lands that much late.
function tapLatency() {
  if (!playBuffer || !audioCtx) return 0;
  return ((audioCtx.outputLatency || 0) + (audioCtx.baseLatency || 0)) * playbackRate;
}

function applyTaps() {
  if (!tapState) return;
  const a = arrangements[currentArr];
  const smooth = document.getElementById('tapSmooth')?.checked !== false;
  const times = smooth ? smoothTaps(tapState.taps) : tapState.taps.slice();
  const warp = buildTimeWarp(tapState.base);
  const plan = planTaps(tapState.base, warp, {
    points: times.map((d, i) => [previewScale(tapState.grid[i]), d]),
    songStartO: previewScale((a.beats || [])[0] ?? tapState.grid[0]),
    tailO: previewScale(songEndChartTime(a)),
  });
  syncAnchors.splice(0, syncAnchors.length, ...plan);
  renderAnchorsList();
  updatePendingChangesInfo();
  showArr(currentArr);
  renderTapUi();
}

function startTapSync() {
  const a = arrangements[currentArr];
  if (!a || !isGpJob()) return;
  if (!playBuffer && !document.getElementById('syncAudio')?.src) {
    toast(T('A gravação ainda não carregou.'), 'err');
    return;
  }
  const fromM = parseInt(document.getElementById('tapFromBar').value, 10) || 1;
  const mode = document.getElementById('tapMode').value === 'beats' ? 'beats' : 'bars';
  const grid = tapGrid(a, fromM, mode);
  if (!grid.length) { toast(T('Esta pista não tem compassos para marcar.'), 'err'); return; }
  tapState = { grid, taps: [], base: syncAnchors.map(x => x.slice()), kind: a.kind, mode, fromM };
  const first = (a.bars || [])[0];
  if (first && fromM <= first.measure) audioSeek(0);  // the song's first bar: from the very start
  if (!audioIsPlaying()) audioPlay();
  renderTapUi();
}

function tapNow() {
  if (!tapState) return;
  if (!audioIsPlaying()) { toast(T('Dá play para marcar a ouvir.'), 'err'); return; }
  const d = playheadDisplay(Math.max(0, audioTime() - tapLatency()));
  const prev = tapState.taps[tapState.taps.length - 1];
  if (prev != null && d <= prev + 0.05) return;  // a double press
  tapState.taps.push(d);
  applyTaps();
  if (tapState.taps.length >= tapState.grid.length) stopTapSync();
}

function undoTap() {
  if (!tapState || !tapState.taps.length) return;
  tapState.taps.pop();
  applyTaps();
}

function stopTapSync() {
  if (!tapState) return;
  const n = tapState.taps.length;
  tapState = null;
  renderTapUi();
  notePendingChange();  // the whole run is one step of undo
  if (n) toast(T('{n} toque(s) aplicados — pendentes até "Aplicar e reconstruir".', { n }), 'ok');
}

function renderTapUi() {
  const card = document.getElementById('tapSyncCard');
  if (!card) return;
  const on = !!tapState;
  card.classList.toggle('tap-armed', on);
  document.getElementById('tapStart').hidden = on;
  document.getElementById('tapArmed').hidden = !on;
  for (const id of ['tapFromBar', 'tapMode']) document.getElementById(id).disabled = on;
  const st = document.getElementById('tapStatus');
  if (!on) { st.textContent = ''; return; }
  const a = arrangements[currentArr];
  const i = tapState.taps.length;
  const bar = (t) => {
    const b = (a.bars || []).filter(x => x.time <= t + 1e-6).pop();
    return b ? b.measure : '?';
  };
  const k = i + 1, n = tapState.grid.length;
  let txt = i >= n ? ''
    : tapState.mode === 'bars'
      ? T('Próximo toque: compasso {bar} ({k} de {n}).', { bar: bar(tapState.grid[i]), k, n })
      : T('Próximo toque: tempo {k} de {n}, no compasso {bar}.', { bar: bar(tapState.grid[i]), k, n });
  if (i >= 2) {
    const beats = (a.beats || []).filter(t => t >= tapState.grid[i - 2] - 1e-6 && t < tapState.grid[i - 1] - 1e-6).length || 1;
    const dt = tapState.taps[i - 1] - tapState.taps[i - 2];
    if (dt > 0) txt += ' ' + T('Último: ♩ = {bpm}.', { bpm: (beats * 60 / dt).toFixed(1) });
  }
  st.textContent = txt;
}

function fillTapBars() {
  const sel = document.getElementById('tapFromBar');
  if (!sel || tapState) return;
  const bars = (arrangements[currentArr] || {}).bars || [];
  const prev = parseInt(sel.value, 10);
  sel.innerHTML = bars.map(b => `<option value="${b.measure}">${b.measure}</option>`).join('');
  if (bars.some(b => b.measure === prev)) sel.value = String(prev);
}

(function wireTapSync() {
  document.getElementById('tapStart')?.addEventListener('click', startTapSync);
  // pointerdown, not click: a click fires on release, tens of ms after the press.
  document.getElementById('tapHit')?.addEventListener('pointerdown', e => { e.preventDefault(); tapNow(); });
  document.getElementById('tapUndo')?.addEventListener('click', undoTap);
  document.getElementById('tapStop')?.addEventListener('click', stopTapSync);
  document.getElementById('tapSmooth')?.addEventListener('change', () => { if (tapState) applyTaps(); });
  // Capture phase, ahead of the page's own keys: while marking, Backspace
  // takes the last tap back (not "delete the selected notes") and Esc ends.
  document.addEventListener('keydown', e => {
    if (!tapState || e.ctrlKey || e.metaKey || e.altKey) return;
    const el = e.target;
    if (el && (el.tagName === 'TEXTAREA' || (el.tagName === 'INPUT' && !['checkbox', 'radio', 'range'].includes(el.type)))) return;
    if (e.key === 'b' || e.key === 'B') { e.preventDefault(); e.stopPropagation(); if (!e.repeat) tapNow(); }
    else if (e.key === 'Backspace') { e.preventDefault(); e.stopPropagation(); undoTap(); }
    else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); stopTapSync(); }
  }, true);
})();

// ── "Sincronizar automaticamente" (EXPERIMENTAL) ─────────────────────────────
// The server moves each of the chart's beats to where the recording plays them,
// the tempo allowed to wander slowly (/detect-beat-sync). What comes back is
// treated exactly like taps: each bar's downbeat → its aligned instant, through
// planTaps, so it previews, rides "Aplicar e reconstruir" and is ONE undo step.
// Bars whose notes did not land on attacks are left out (the warp interpolates
// across them) and listed, with the first bars after a rest, to check by ear.
const AUTO_SYNC_MIN_SUPPORT = 0.5;  // mean attack strength under a bar's notes to trust it
let autoSyncBusy = false;

async function runAutoSync() {
  const a = arrangements[currentArr];
  if (!a || !isGpJob() || autoSyncBusy || tapState) return;
  const fromM = parseInt(document.getElementById('autoSyncFromBar').value, 10) || 1;
  const grid = tapGrid(a, fromM, 'beats');
  if (grid.length < 2) { toast(T('Esta pista não tem compassos para alinhar.'), 'err'); return; }
  const status = document.getElementById('autoSyncStatus');
  const btn = document.getElementById('autoSyncRun');
  const kind = a.kind;
  const base = syncAnchors.map(x => x.slice());
  const warp = buildTimeWarp(base);
  const off = recordingDisplay(0);  // display → seconds of the recording
  const rec = t => warp(previewScale(t)) - off;
  const noteTimes = [...new Set((a.notes || []).map(n => n.time))]
    .filter(t => t >= grid[0] - 1e-6).sort((x, y) => x - y);
  autoSyncBusy = true;
  btn.disabled = true;
  status.textContent = T('A analisar a gravação… (pode demorar um minuto)');
  renderAutoSyncCheck([]);
  let res;
  try {
    res = await getJSON(`/jobs/${selectedJob.id}/detect-beat-sync`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ beats: grid.map(rec), notes: noteTimes.map(rec) }),
    });
  } catch (e) {
    status.textContent = T('Não foi possível analisar: {msg}', { msg: e.message });
    return;
  } finally {
    autoSyncBusy = false;
    btn.disabled = false;
  }
  if (arrangements[currentArr]?.kind !== kind) { status.textContent = ''; return; }  // tab switched meanwhile
  const barAt = new Map((a.bars || []).map(b => [b.time.toFixed(6), b.measure]));
  const points = [], check = new Set(), bpms = [];
  // The bar holding each beat that follows a rest, and the bar after it.
  const downbeats = grid.map((t, i) => [i, barAt.get(t.toFixed(6))]).filter(([, m]) => m != null);
  for (const g of res.after_gap) {
    const k = downbeats.findLastIndex(([i]) => i <= g);
    for (const [, m] of downbeats.slice(Math.max(0, k), k + 2)) check.add(m);
  }
  let prev = null;
  grid.forEach((t, i) => {
    const m = barAt.get(t.toFixed(6));
    if (m == null) return;
    const s = res.support[i];
    if (res.times[i] >= res.duration) return;
    if (s == null) return;  // no note on it: the warp carries it
    if (s < AUTO_SYNC_MIN_SUPPORT) { check.add(m); return; }
    points.push([previewScale(t), res.times[i] + off]);
    if (prev) {
      const beats = grid.slice(prev.i, i).length;
      const dt = res.times[i] - res.times[prev.i];
      if (dt > 0) bpms.push(beats * 60 / dt);
    }
    prev = { i };
  });
  if (!points.length || res.evidence_after <= res.evidence_before * 1.02) {
    status.textContent = T('Não encontrei um alinhamento melhor do que o atual — nada foi mudado.');
    return;
  }
  const plan = planTaps(base, warp, {
    points,
    songStartO: previewScale((a.beats || [])[0] ?? grid[0]),
    tailO: previewScale(songEndChartTime(a)),
  });
  syncAnchors.splice(0, syncAnchors.length, ...plan);
  renderAnchorsList();
  updatePendingChangesInfo();
  showArr(currentArr);
  notePendingChange();
  const lo = Math.min(...bpms), hi = Math.max(...bpms);
  status.textContent = T('{n} compassos alinhados (♩ entre {lo} e {hi}). Ouve o resultado — um Ctrl+Z desfaz tudo; fica pendente até "Aplicar e reconstruir".', {
    n: points.length, lo: bpms.length ? lo.toFixed(1) : '—', hi: bpms.length ? hi.toFixed(1) : '—',
  });
  renderAutoSyncCheck([...check].sort((x, y) => x - y));
}

function renderAutoSyncCheck(bars) {
  const row = document.getElementById('autoSyncCheckRow');
  const list = document.getElementById('autoSyncCheckList');
  if (!row) return;
  row.hidden = !bars.length;
  list.replaceChildren(...barRanges(bars).slice(0, 40).map(([first, last]) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'secondary';
    b.textContent = first === last ? String(first) : `${first}–${last}`;
    b.title = T('Pôr o cursor no compasso {n}', { n: first });
    b.addEventListener('click', () => goToBar(first));
    return b;
  }));
}

function fillAutoSyncBars() {
  const sel = document.getElementById('autoSyncFromBar');
  if (!sel) return;
  const bars = (arrangements[currentArr] || {}).bars || [];
  const prev = parseInt(sel.value, 10);
  sel.innerHTML = bars.map(b => `<option value="${b.measure}">${b.measure}</option>`).join('');
  if (bars.some(b => b.measure === prev)) sel.value = String(prev);
}

document.getElementById('autoSyncRun')?.addEventListener('click', runAutoSync);

// ── The recording's attacks over the score ("Ataques da gravação") ───────────
// /detect-attacks says where the recording has attacks (seconds of the
// recording; measured on the separated guitar stem when there is one, else on
// the mix). They are drawn in the band above the staff and compared with the
// notes AS SHOWN NOW (pending edits and sync included), so a tab whose rhythm
// is wrong shows where: a note with no attack near it, or a strong attack with
// no note. A picture to check by ear — nothing in the chart changes.
const ATTACK_MATCH_S = 0.06;   // a note and an attack this close are one strike
const ATTACK_STRONG = 0.35;    // a weaker attack with no note is drawn but not counted (bleed, ghost strums)
let recAttacks = null;         // {job, source, attacks: [[seconds, strength], …], duration}
let attacksBusy = false;
let attackStats = null;        // {notes, matched, lonely, extra}
let attackDiffs = [];          // display times of the differences, for ◀ ▶
let attackSources = [];        // the separated instruments the attacks can be measured on
let attackSourceTouched = false;  // the user picked one: no default per chart any more

function resetAttacks() {
  recAttacks = null;
  attackStats = null;
  attackDiffs = [];
  attackSourceTouched = false;
  document.getElementById('attacksShow').checked = true;
  loadAttackSources();
  renderAttacksCard();
}

async function loadAttackSources() {
  const job = selectedJob && selectedJob.id;
  attackSources = [];
  fillAttackSources();
  if (!job) return;
  try {
    const d = await getJSON(`/jobs/${job}/attack-sources`);
    if (selectedJob && selectedJob.id === job) { attackSources = d.stems || []; fillAttackSources(); }
  } catch { /* the card can still measure the mix */ }
}

// The instrument a chart is compared with unless the user picked one: the
// separated bass for the Bass chart, the guitar for the others, else the mix.
function defaultAttackSource() {
  const a = arrangements[currentArr];
  const want = a && a.kind === 'Bass' ? 'bass' : 'guitar';
  return attackSources.includes(want) ? want : 'mix';
}

function fillAttackSources() {
  const sel = document.getElementById('attacksSource');
  if (!sel) return;
  const keep = attackSourceTouched ? sel.value : defaultAttackSource();
  const values = ['mix', ...attackSources];
  sel.innerHTML = values.map(v => `<option value="${esc(v)}">${esc(v === 'mix' ? T('Mistura completa') : (STEM_LABELS[v] || v))}</option>`).join('');
  sel.value = values.includes(keep) ? keep : 'mix';
}

function attacksVisible() {
  return !!(recAttacks && selectedJob && recAttacks.job === selectedJob.id
    && document.getElementById('attacksShow').checked);
}

// The comparison and its drawing, for the note groups showArr is drawing.
function attacksSvg(groups, warp, W, SB) {
  const off = recordingDisplay(0);  // seconds of the recording → display time
  const att = recAttacks.attacks;
  const used = new Array(att.length).fill(false);
  const lonely = [];
  let notes = 0, matched = 0, j = 0;
  const times = groups.map(g => warp(previewScale(g.time))).sort((x, y) => x - y);
  for (const t of times) {
    const rec = t - off;
    if (rec < 0 || rec > recAttacks.duration) continue;
    notes++;
    while (j < att.length && att[j][0] < rec - ATTACK_MATCH_S) j++;
    let hit = false;
    for (let k = j; k < att.length && att[k][0] <= rec + ATTACK_MATCH_S; k++) { used[k] = true; hit = true; }
    if (hit) matched++; else lonely.push(t);
  }
  const extra = [];
  let svg = '';
  const tick = T('Ataque na gravação'), lone = T('Ataque forte na gravação sem nota na partitura');
  att.forEach(([rec, str], k) => {
    const t = rec + off, x = timeToX(t);
    const strong = !used[k] && str >= ATTACK_STRONG;
    if (strong) extra.push(t);
    if (x < 24 || x > W - 4) return;
    const h = 4 + 9 * str;
    if (strong)
      svg += `<line x1="${x}" y1="29" x2="${x}" y2="${SB}" stroke="#ff9f43" stroke-width="1" stroke-dasharray="3,4" opacity=".45"/>`
        + `<line x1="${x}" y1="${29 - h}" x2="${x}" y2="29" stroke="#ff9f43" stroke-width="2.5"><title>${esc(lone)}</title></line>`;
    else
      svg += `<line x1="${x}" y1="${29 - h}" x2="${x}" y2="29" stroke="#5ec8f2" stroke-width="2" opacity="${used[k] ? 0.6 + 0.4 * str : 0.35}"><title>${esc(tick)}</title></line>`;
  });
  const noAttack = T('Nota sem ataque perto na gravação');
  for (const t of lonely) {
    const x = timeToX(t);
    if (x < 24 || x > W - 4) continue;
    svg += `<line x1="${x}" y1="29" x2="${x}" y2="${SB}" stroke="#ff9f43" stroke-width="1" stroke-dasharray="1,4" opacity=".55"/>`
      + `<circle cx="${x}" cy="22" r="4.5" fill="none" stroke="#ff9f43" stroke-width="2"><title>${esc(noAttack)}</title></circle>`;
  }
  attackStats = { notes, matched, lonely: lonely.length, extra: extra.length };
  attackDiffs = [...lonely, ...extra].sort((x, y) => x - y);
  return svg;
}

function renderAttacksCard() {
  const status = document.getElementById('attacksStatus');
  if (!status) return;
  const mine = recAttacks && selectedJob && recAttacks.job === selectedJob.id;
  document.getElementById('attacksRunLabel').textContent = mine ? T('Detetar outra vez') : T('Detetar ataques');
  document.getElementById('attacksShowLbl').hidden = !mine;
  const shown = attacksVisible();
  document.getElementById('attacksNav').hidden = !(shown && attackDiffs.length);
  const sel = document.getElementById('attacksSource');
  if (!attackSourceTouched && sel && sel.value !== defaultAttackSource()) sel.value = defaultAttackSource();
  if (attacksBusy) { status.textContent = T('A analisar a gravação… (pode demorar um minuto)'); return; }
  if (!mine) { status.textContent = ''; return; }
  const src = recAttacks.source;
  const where = src === 'mix'
    ? T('Medido na mistura completa — a bateria e a voz também contam. Para medir um só instrumento, separa os instrumentos (Áudio ▾ → Separar instrumentos) e deteta outra vez.')
    : src === 'guitar'
      ? T('Medido no stem de guitarra (todas as guitarras juntas).')
      : T('Medido no instrumento separado: {name}.', { name: STEM_LABELS[src] || src });
  const st = shown && attackStats ? attackStats : null;
  status.textContent = where + ' ' + (st
    ? T('Ataques: {n} · notas com um ataque perto: {ok} de {total} · notas sem ataque: {lonely} · ataques fortes sem nota: {extra}.', {
      n: recAttacks.attacks.length, ok: st.matched, total: st.notes, lonely: st.lonely, extra: st.extra,
    })
    : T('Ataques: {n}.', { n: recAttacks.attacks.length }));
}

async function runAttacks() {
  if (!selectedJob || !isGpJob() || attacksBusy) return;
  const job = selectedJob.id;
  const source = document.getElementById('attacksSource').value || 'mix';
  // Nothing separated yet: the mix is all there is, and its drums and voice
  // bury the differences — the user decides whether that is worth it.
  if (source === 'mix' && !attackSources.length && !await confirmModal(T(
    'Ainda não há instrumentos separados, por isso os ataques vão ser medidos na mistura completa: a bateria e a voz também contam, e as diferenças com a tab ficam pouco claras. Para medir um só instrumento, separa-os primeiro (Áudio ▾ → Separar instrumentos — demora alguns minutos). Medir na mistura mesmo assim?'), T('Medir na mistura'))) return;
  if (!selectedJob || selectedJob.id !== job || attacksBusy) return;
  attacksBusy = true;
  document.getElementById('attacksRun').disabled = true;
  renderAttacksCard();
  let res;
  try {
    res = await getJSON(`/jobs/${job}/detect-attacks?source=${encodeURIComponent(source)}`, { method: 'POST' });
  } catch (e) {
    attacksBusy = false;
    document.getElementById('attacksRun').disabled = false;
    renderAttacksCard();
    document.getElementById('attacksStatus').textContent = T('Não foi possível analisar: {msg}', { msg: e.message });
    return;
  }
  attacksBusy = false;
  document.getElementById('attacksRun').disabled = false;
  if (!selectedJob || selectedJob.id !== job) return;  // another project opened meanwhile
  recAttacks = { job, ...res };
  document.getElementById('attacksShow').checked = true;
  showArr(currentArr);
}

// The previous/next difference from the cursor: the cursor goes there and the
// view centres on it.
function goToAttackDiff(dir) {
  const now = playheadDisplay(audioTime());
  const t = dir > 0 ? attackDiffs.find(d => d > now + 0.02)
    : attackDiffs.findLast(d => d < now - 0.02);
  if (t == null) { toast(T('Sem diferenças nesse sentido.')); return; }
  audioSeek(Math.max(0, t - viewOrigin));
  const wrap = document.getElementById('tabwrap');
  wrap.scrollLeft = Math.max(0, timeToX(t) - wrap.clientWidth / 2);
}

document.getElementById('attacksRun')?.addEventListener('click', runAttacks);
document.getElementById('attacksShow')?.addEventListener('change', () => showArr(currentArr));
document.getElementById('attacksSource')?.addEventListener('change', () => { attackSourceTouched = true; });
document.getElementById('attacksPrev')?.addEventListener('click', () => goToAttackDiff(-1));
document.getElementById('attacksNext')?.addEventListener('click', () => goToAttackDiff(1));

function barTempoMessage(fromM, toM, bpm, delta) {
  const which = fromM === toM ? T('Compasso {n}', { n: fromM }) : T('Compassos {from}–{to}', { from: fromM, to: toM });
  const shift = Math.abs(delta) < 0.0005 ? T('o resto não se mexe')
    : delta > 0 ? T('o resto da música atrasa {s} s', { s: Math.abs(delta).toFixed(3) })
      : T('o resto da música adianta {s} s', { s: Math.abs(delta).toFixed(3) });
  return `${which}: ♩ = ${Number(bpm.toFixed(1))} BPM (${shift}).`;
}

// Fill a "até ao compasso" select with the bars from `fromM` on, and the BPM
// field with that bar's current tempo.
function fillBarTempoControls(fromM, toSel, bpmInput) {
  const bars = (arrangements[currentArr] || {}).bars || [];
  const prev = parseInt(toSel.value, 10);
  toSel.innerHTML = bars.filter(b => b.measure >= fromM)
    .map(b => `<option value="${b.measure}">${b.measure}</option>`).join('');
  toSel.value = String(prev >= fromM && bars.some(b => b.measure === prev) ? prev : fromM);
  const bpm = barDisplayBpm(fromM);
  bpmInput.value = bpm ? bpm.toFixed(1) : '';
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
    if (!alignBarTo(measure, currentPlayheadT + viewOrigin)) { toast(T('compasso não encontrado'), 'err'); return; }
    info.textContent = T('Compasso {n} alinhado com o cursor ({s}s).', { n: measure, s: currentPlayheadT.toFixed(2) });
    toast(T('Compasso {n} alinhado com o cursor', { n: measure }), 'ok');
  });

  fromRef.addEventListener('click', () => {
    if (!isGpJob()) return;
    const measure = parseInt(barSel.value, 10);
    const refIdx = parseInt(refSel.value, 10);
    if (isNaN(refIdx) || !arrangements[refIdx]) { toast(T('escolhe uma pista de referência'), 'err'); return; }
    const target = refBarTarget(refIdx, measure);
    if (target == null || !alignBarTo(measure, target)) {
      toast(T('compasso {n} não existe nas duas pistas', { n: measure }), 'err'); return;
    }
    const refKind = arrangements[refIdx].kind;
    info.textContent = T('Compasso {n} alinhado com o compasso {n} de {ref} ({s}s).', { n: measure, ref: arrLabel(refKind), s: (target - viewOrigin).toFixed(2) });
    toast(T('Compasso {n} sincronizado com {ref}', { n: measure, ref: arrLabel(refKind) }), 'ok');
  });

  const bpmInput = document.getElementById('barBpm');
  const toSel = document.getElementById('barBpmTo');
  const refreshTempo = () => fillBarTempoControls(parseInt(barSel.value, 10), toSel, bpmInput);
  barSel.addEventListener('change', refreshTempo);
  document.getElementById('barBpmApply').addEventListener('click', () => {
    const fromM = parseInt(barSel.value, 10), toM = parseInt(toSel.value, 10);
    const bpm = parseFloat(bpmInput.value);
    const r = setBarsTempo(fromM, toM, bpm);
    if (!r.ok) { toast(r.why, 'err'); return; }
    info.textContent = barTempoMessage(fromM, toM, bpm, r.delta);
    toast(info.textContent, 'ok');
  });
})();

// ---- Click-a-note bar-align popup ('baralign' mode) ----
// A faster entry to alignBarTo for doing MANY corrections: click a note, a
// small floating popup opens with the bar numbers (the note's own bar
// pre-selected); confirm "= cursor" (or "= pista") and that bar snaps to the
// cursor / the reference track, dragging the following notes into place.
function openBarAlignPopup(chartT, clientX, clientY) {
  const a = arrangements[currentArr];
  if (!a || !(a.bars && a.bars.length)) { toast(T('sem compassos nesta pista'), 'err'); return; }
  const pop = document.getElementById('barAlignPopup');
  const barSel = document.getElementById('baBar');
  barSel.innerHTML = a.bars.map(b => `<option value="${b.measure}">${T('Compasso {n}', { n: b.measure })}</option>`).join('');
  const containing = [...a.bars].filter(b => b.time <= chartT + 1e-6).pop();
  if (containing) barSel.value = String(containing.measure);
  fillBarTempoControls(parseInt(barSel.value, 10), document.getElementById('baBarTo'),
    document.getElementById('baBpm'));
  document.getElementById('baBpmInfo').textContent = '';
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
  const baBar = document.getElementById('baBar');
  baBar.addEventListener('change', () => fillBarTempoControls(parseInt(baBar.value, 10),
    document.getElementById('baBarTo'), document.getElementById('baBpm')));
  document.getElementById('baSetBpm').addEventListener('click', () => {
    const fromM = parseInt(baBar.value, 10);
    const toM = parseInt(document.getElementById('baBarTo').value, 10);
    const bpm = parseFloat(document.getElementById('baBpm').value);
    const r = setBarsTempo(fromM, toM, bpm);
    if (!r.ok) { toast(r.why, 'err'); return; }
    const msg = barTempoMessage(fromM, toM, bpm, r.delta);
    document.getElementById('baBpmInfo').textContent = msg;
    toast(msg, 'ok');
  });
  document.getElementById('baToCursor').addEventListener('click', () => {
    const m = parseInt(document.getElementById('baBar').value, 10);
    if (alignBarTo(m, currentPlayheadT + viewOrigin)) {
      toast(T('Compasso {n} alinhado ao cursor', { n: m }), 'ok');
      closeBarAlignPopup();
    }
  });
  document.getElementById('baToRef').addEventListener('click', () => {
    const m = parseInt(document.getElementById('baBar').value, 10);
    const refIdx = parseInt(document.getElementById('baRefArr').value, 10);
    const target = refBarTarget(refIdx, m);
    if (target == null) { toast(T('compasso {n} não existe nessa pista', { n: m }), 'err'); return; }
    if (alignBarTo(m, target)) {
      toast(T('Compasso {n} alinhado a {ref}', { n: m, ref: arrLabel(arrangements[refIdx].kind) }), 'ok');
      closeBarAlignPopup();
    }
  });
  // Dismiss on Escape or a click that's neither the popup nor a note (a note
  // click reopens/repositions it via the SVG handler).
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeBarAlignPopup(); });
  document.addEventListener('pointerdown', e => {
    if (!pop.hidden && !pop.contains(e.target) && !e.target.closest('.note-grp, .bar-hit')) closeBarAlignPopup();
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
    ? T('{mine} nesta pista ({kind}), {total} no total', { mine, kind: arrLabel(kind), total })
    : T('nenhuma');
  one.disabled = !mine;
  all.disabled = !total;
}

async function clearNoteEdits(everyArrangement) {
  const { mine, total, kind } = noteEditCounts();
  const n = everyArrangement ? total : mine;
  if (!n) return;
  const where = everyArrangement ? T('de todas as pistas') : T('da pista {kind}', { kind: arrLabel(kind) });
  if (!await confirmModal(
    T('Descartar {n} edição(ões) de notas {where}?\n\nInclui as que já foram aplicadas em reconstruções anteriores. As notas voltam ao que está no ficheiro Guitar Pro assim que fizeres "Aplicar e reconstruir".', { n, where }))) return;
  if (everyArrangement) noteOverridesByKind = {};
  else delete noteOverridesByKind[kind];
  noteDeleteUndo = null;  // nothing left for it to restore on top of
  updateNoteEditsInfo();
  updatePendingChangesInfo();
  showArr(currentArr);
  toast(T('{n} edição(ões) descartada(s) — pendente até "Aplicar e reconstruir".', { n }), 'ok');
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

  document.getElementById('nePopupTitle').textContent = base ? T('Editar nota') : T('Nova nota');
  const stringSel = document.getElementById('neString');
  stringSel.innerHTML = [0, 1, 2, 3, 4, 5].slice(0, stringCount(a))
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
    if (isNaN(fret) || fret < 0 || fret > 24) { toast(T('traste inválido (0-24)'), 'err'); return; }
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
    toast(T('Nota guardada — pendente até "Aplicar e reconstruir".'), 'ok');
  });
  document.getElementById('neDelete').addEventListener('click', () => {
    if (!neContext) return;
    upsertNoteOverride({
      time: neContext.time, string: neContext.string, fret: 0, sustain: 0,
      techniques: [], bend_semitones: 0, slide_to_fret: null, deleted: true,
    });
    closeNoteEditPopup();
    showArr(currentArr);
    toast(T('Nota removida — pendente até "Aplicar e reconstruir".'), 'ok');
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
      ? ` <span style="color:#e6483c" title="${T('Esta correção manda um ponto MAIS À FRENTE da partitura para um instante ANTERIOR ao da correção acima — impossível de aplicar. Corrige o valor ou remove uma delas.')}">${T('⚠ cruza a anterior')}</span>`
      : '';
    return `<div class="anchor-row"${crosses ? ' style="border-left:3px solid #e6483c;padding-left:.4rem"' : ''}>${T('Correção {i}:', { i: i + 1 })} ${o.toFixed(2)}s →
     <input type="number" step="0.01" value="${n.toFixed(2)}" data-i="${i}" class="anchor-edit" style="width:6rem">s
     <button type="button" data-i="${i}" class="anchor-remove">${T('remover')}</button>${warn}</div>`;
  }).join('') + `<div class="anchor-row">
     <button type="button" id="clearAnchors" class="secondary">${T('Limpar correções pendentes')}</button></div>`;
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
// One rebuild per click: a double-click used to fork two new versions.
let applyingAll = false;

async function applyAll() {
  if (!selectedJob || applyingAll) return;
  applyingAll = true;
  const applyBtn = document.getElementById('applyAll');
  applyBtn.disabled = true;
  try {
    await applyAllNow();
  } finally {
    applyingAll = false;
    applyBtn.disabled = false;
  }
}

async function applyAllNow() {
  mainSyncFollow();  // what the main chart changed must reach the others first
  lyricsFollowSync();  // the rows sent must carry every pending chart correction
  const applyToAll = document.getElementById('applyToAllChk').checked;
  const toneSets = toneSetsForRebuild();
  let b;
  try {
    b = await getJSON(`/jobs/${selectedJob.id}/rebuild`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cent_offset: centOffsetLive,
        offset_s: offsetLive,
        lead_in_s: Math.max(0, parseFloat(document.getElementById('leadInS').value) || 0),
        arrangement: currentKind(),
        tempo_scale: tempoScaleLive,
        sync_anchors: syncAnchors.length ? syncAnchors : null,
        apply_to_all: applyToAll,
        // Every OTHER chart's pending sync too — before, only the chart on screen
        // was committed and the rest was lost at the rebuild.
        other_sync: applyToAll ? null : otherPendingSync(),
        import_mutes: document.getElementById('muteChk').checked,
        dynamic_difficulty: document.getElementById('ddChk').checked,
        // null keeps the stored rows; [] drops them, so the build reads the GP
        // file's own lyrics again ("Voltar à letra da pauta").
        lyrics_events: lyricsEvents.length ? serializeLyrics() : (lyricsBackToScore ? [] : null),
        lyrics_follow_chart: isGpJob() ? lyricsFollowChart : null,
        // Send the FULL current tone state for GP jobs (even when empty) so that
        // clearing tones/changes actually persists — null would mean "keep the
        // old value". Non-GP jobs have no tones, so send null to skip the guard.
        tones: isGpJob() ? jobTones : null,
        tone_base: isGpJob() ? (toneSets.song.tone_base || '') : null,
        tone_names: isGpJob() ? toneSets.song.tone_names : null,
        tone_changes: isGpJob() ? toneSets.song.tone_changes : null,
        // Each chart's own set; {} = every chart uses the song's (the default).
        arrangement_tones: isGpJob() ? toneSets.perTrack : null,
        // Only sent once the user actually touches the section editor — untouched,
        // null leaves each arrangement's own GP-authored sections alone (unlike
        // tones, which never had a prior non-user-supplied default to lose).
        section_overrides: (isGpJob() && sectionsTouched) ? songSections : null,
        // Genuinely per-arrangement (unlike tone_changes/sections) — sent as
        // one dict covering every tab's pending edits from this session, same
        // no-prior-default reasoning as tone_changes (an untouched job sends {}).
        note_overrides: isGpJob() ? noteOverridesByKind : null,
        // Each chart's own FHPs, carried through its pending sync; {} = all automatic.
        hand_positions: isGpJob() ? fhpForRebuild() : null,
      }),
    });
  } catch (err) {
    toast(err.message || T('erro'));
    return;
  }
  toast(T('A reconstruir…'), 'ok');
  dropDraft(selectedJob.id);  // the new version is built with them
  stopPendingHistory();
  // Every chart's pending sync was sent (other_sync), so all of it is built.
  for (const list of Object.values(syncAnchorsByKind)) list.length = 0;
  syncAnchors.length = 0;
  tempoScaleByKind = {};
  resetMainFollow();
  // The rows just sent already carry the corrections; clearing the pending
  // sync must not carry them back before the new build's rows load.
  resetLyricFollow();
  noteOverridesByKind = {};  // baked into the new build regardless of applyToAll
  noteOverridesBuilt = '{}';
  fhpByKind = {};
  fhpBuilt = '{}';
  selectJob(b.id, { force: true });
  offerDropPrevious(b.id);
}
document.getElementById('applyAll').addEventListener('click', applyAll);

// Every rebuild makes a new version and keeps the old one. "Aplicar e
// reconstruir" asks whether the old one can go; the answer waits, per new
// version and in localStorage so it survives closing the app, until that
// version is BUILT — a failed rebuild keeps the old one
// (POST /jobs/{id}/drop-previous, which also moves the stems the new one uses).
const DROP_PREV_KEY = 'rf-drop-previous';
function dropPrevPending() {
  try { return JSON.parse(localStorage.getItem(DROP_PREV_KEY) || '{}') || {}; } catch { return {}; }
}
function setDropPrev(id, on) {
  try {
    const pending = dropPrevPending();
    if (on) pending[id] = 1; else delete pending[id];
    localStorage.setItem(DROP_PREV_KEY, JSON.stringify(pending));
  } catch { /* no storage: the old version simply stays */ }
}
async function offerDropPrevious(newId) {
  if (!(await confirmModal(T('Apagar a versão anterior deste projeto (e o PSARC dela) assim que a nova ficar pronta? Se a reconstrução falhar, a anterior fica.')))) return;
  setDropPrev(newId, true);
  try { maybeDropPrevious(await getJSON(`/jobs/${newId}`)); } catch { /* the poll tries again */ }
}
const droppingPrev = new Set();
async function maybeDropPrevious(j) {
  if (!j || !dropPrevPending()[j.id] || droppingPrev.has(j.id)) return;
  if (j.status === 'failed') {
    setDropPrev(j.id, false);
    toast(T('A reconstrução falhou — a versão anterior foi mantida.'));
    return;
  }
  if (j.status !== 'completed') return;
  setDropPrev(j.id, false);
  if (!j.rebuilt_from) return;
  droppingPrev.add(j.id);
  try {
    const out = await getJSON(`/jobs/${j.id}/drop-previous`, { method: 'POST' });
    if (selectedJob && selectedJob.id === out.id) { selectedJob = out; renderDetailHead(out); }
    toast(T('Versão anterior apagada.'), 'ok');
    refreshJobs();
  } catch (err) {
    toast(T('não foi possível apagar a versão anterior: {msg}', { msg: err.message }));
  } finally {
    droppingPrev.delete(j.id);
  }
}

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
  info.textContent = T('A recarregar…');
  reloadGpBtn.disabled = true;
  try {
    const fd = new FormData();
    fd.append('gp', file);
    // The file's own audio (GP8) is the one its sync points describe — used
    // unless unticked; a file without audio keeps the current recording.
    fd.append('use_embedded_audio', document.getElementById('reloadGpUseAudio').checked ? 'true' : 'false');
    const wasFromGp = !!selectedJob.recording_from_gp;
    const r = await fetch(`/jobs/${selectedJob.id}/reload-gp`, { method: 'POST', body: fd });
    const b = await r.json();
    if (r.ok) {
      toast(b.recording_from_gp && !wasFromGp
        ? T('GP recarregado com o áudio que vem dentro dele (o início passou para o do ficheiro) — a reconstruir…')
        : b.recording_from_gp ? T('GP recarregado, com o áudio dele — a reconstruir…') : T('GP recarregado — a reconstruir…'), 'ok');
      selectJob(b.id, { force: true });
      offerDropPrevious(b.id);
    }
    else toast(b.detail || T('erro ao recarregar o GP'));
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
  if (!a) { toast(T('abre um arranjo primeiro')); return; }
  const btn = document.getElementById('exportArrGpBtn');
  btn.disabled = true;
  try {
    const b = await getJSON(
      `/jobs/${selectedJob.id}/export-arrangement-gp?arrangement=${encodeURIComponent(a.kind)}`,
      { method: 'POST' });
    const notes = [T('<b>{n} nota(s)</b> em {m} compasso(s)', { n: b.notes_written, m: b.measures })];
    if (b.quantized) notes.push(T('{n} ajustada(s) à grelha (máx {ms} ms)', { n: b.quantized, ms: b.max_shift_ms }));
    if (b.notes_dropped) notes.push(T('{n} fora dos compassos, não escrita(s)', { n: b.notes_dropped }));
    document.getElementById('exportGpInfo').innerHTML =
      T('{notes} em <code>{file}</code>.', { notes: notes.join(' — '), file: esc(b.filename) }) + ' ' +
      esc(b.warnings.join(' '));
    const link = document.createElement('a');
    link.href = `/jobs/${selectedJob.id}/corrected-gp`;
    link.download = b.filename;
    link.click();
    toast(T('GP gerado: {n} nota(s).', { n: b.notes_written }), 'ok');
  } catch (err) {
    toast(T('falha ao gerar o GP: {msg}', { msg: err.message }));
  } finally {
    btn.disabled = false;
  }
});

document.getElementById('exportGpBtn').addEventListener('click', async () => {
  if (!selectedJob) return;
  const a = arrangements[currentArr];
  if (!a) { toast(T('abre um arranjo primeiro')); return; }
  const bars = retempoedBars(a);
  if (!bars.length) {
    toast(T('nenhum compasso mudou de andamento — não há nada para escrever no ficheiro GP'));
    return;
  }
  // The endpoint bounds BPM to (10, 400); a wild warp can push a bar outside it.
  // Drop those rather than letting the whole export 422, and say how many.
  const writable = bars.filter(b => b.bpm > GP_EXPORT_MIN_BPM && b.bpm < GP_EXPORT_MAX_BPM);
  const dropped = bars.length - writable.length;
  if (!writable.length) {
    toast(T('os andamentos corrigidos estão fora do intervalo que o Guitar Pro aceita (10-400 BPM)'));
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
    if (dropped) notes.push(T('{n} compasso(s) fora de 10-400 BPM ignorado(s)', { n: dropped }));
    if (rounded) notes.push(T('{n} arredondado(s) — este formato guarda o tempo como inteiro', { n: rounded }));
    document.getElementById('exportGpInfo').innerHTML =
      T('<b>{n} compasso(s)</b> escritos em <code>{file}</code>', { n: b.applied.length, file: esc(b.filename) }) +
      (notes.length ? ` — ${esc(notes.join('; '))}` : '') +
      T('. Só o <b>tempo</b> é exportável: um desfasamento constante continua a ser uma correção só do RockForge.');
    // Download the copy. Same-origin navigation, so the Basic-auth credentials
    // (when ROCKFORGE_API_TOKEN is set) ride along as on any other link.
    const link = document.createElement('a');
    link.href = `/jobs/${selectedJob.id}/corrected-gp`;
    link.download = b.filename;
    link.click();
    toast(T('GP corrigido: {n} compasso(s).', { n: b.applied.length }), 'ok');
  } catch (err) {
    toast(T('falha ao exportar o GP: {msg}', { msg: err.message }));
  } finally {
    btn.disabled = false;
  }
});

document.getElementById('exportSyncBtn').addEventListener('click', async () => {
  if (!selectedJob) return;
  try {
    const r = await fetch(`/jobs/${selectedJob.id}/sync-state`);
    const b = await r.json();
    if (!r.ok) { toast(b.detail || T('erro ao exportar sync')); return; }
    const name = (b.song || selectedJob.id).replace(/[^\w.-]+/g, '_');
    const blob = new Blob([JSON.stringify(b, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${name}.sync.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    toast(T('Sync exportado.'), 'ok');
  } catch { toast(T('erro ao exportar sync')); }
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
      { toast(T('ficheiro de sync inválido')); return; }
    const r = await fetch(`/jobs/${selectedJob.id}/import-sync`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const b = await r.json();
    if (r.ok) { toast(T('Sync importado — a reconstruir…'), 'ok'); selectJob(b.id, { force: true }); }
    else toast(b.detail || T('erro ao importar sync'));
  } catch { toast(T('erro ao ler o ficheiro de sync')); }
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
    songToneSet = cleanToneSet(t);
    toneSetByKind = {};
    for (const [kind, set] of Object.entries(t.arrangement_tones || {})) toneSetByKind[kind] = cleanToneSet(set);
  } catch {
    jobTones = []; songToneSet = cleanToneSet({}); toneSetByKind = {};
  }
  tonesPerTrack = Object.keys(toneSetByKind).length > 0;
  toneSetKind = null;
  toneSetToGlobals(songToneSet);
  switchToneSet();
  renderTonePanel();
  loadToneSuggestions(id);
}

// A tone set as stored ({tone_base, tone_names, tone_changes}), its changes
// kept sorted by time — the invariant every read path relies on (see
// activeToneKeyAt, called once per note in the synth render).
function cleanToneSet(t) {
  return {
    tone_base: (t && t.tone_base) || null,
    tone_names: ((t && t.tone_names) || []).slice(),
    tone_changes: ((t && t.tone_changes) || []).map(c => ({ time: +c.time, name: c.name }))
      .sort((a, b) => a.time - b.time),
  };
}
function toneSetFromGlobals() {
  return { tone_base: toneBase, tone_names: toneNames.slice(), tone_changes: toneChanges.slice() };
}
function toneSetToGlobals(set) {
  const c = cleanToneSet(set);
  toneBase = c.tone_base; toneNames = c.tone_names; toneChanges = c.tone_changes;
}
function stashToneSet() {
  if (toneSetKind) toneSetByKind[toneSetKind] = toneSetFromGlobals();
  else songToneSet = toneSetFromGlobals();
}
// Put the right set in the globals for the chart on screen. True when it changed.
function switchToneSet() {
  const want = tonesPerTrack ? currentKind() : null;
  if (want === toneSetKind) return false;
  stashToneSet();
  toneSetKind = want;
  toneSetToGlobals(want ? (toneSetByKind[want] || songToneSet) : songToneSet);
  return true;
}
// Any chart's tone set — the live globals for the one being edited.
function toneSetFor(kind) {
  if (!tonesPerTrack || !kind || kind === toneSetKind) return toneSetFromGlobals();
  return toneSetByKind[kind] || songToneSet;
}
// Turn per-track tones on (each chart starts from the song's set) or off (every
// chart takes the set of the one on screen).
function setTonesPerTrack(on) {
  if (on === tonesPerTrack) return;
  stashToneSet();
  if (on) {
    for (const a of arrangements) toneSetByKind[a.kind] = cleanToneSet(songToneSet);
  } else {
    songToneSet = cleanToneSet(toneSetFor(toneSetKind));
    toneSetByKind = {};
  }
  tonesPerTrack = on;
  toneSetKind = null;
  toneSetToGlobals(songToneSet);
  switchToneSet();
  renderTonePanel();
}
// What "Aplicar e reconstruir" sends: the song-level set plus, per track, its own.
function toneSetsForRebuild() {
  stashToneSet();
  const perTrack = {};
  if (tonesPerTrack) {
    for (const a of arrangements) {
      const set = toneSetByKind[a.kind] || songToneSet;
      perTrack[a.kind] = { tone_base: set.tone_base || null, tone_names: set.tone_names, tone_changes: set.tone_changes };
    }
  }
  return { song: songToneSet, perTrack };
}
// A tone removed from the project leaves every chart's set, not only the one on screen.
function forgetToneKey(key) {
  const drop = set => cleanToneSet({
    tone_base: set.tone_base === key ? null : set.tone_base,
    tone_names: set.tone_names.filter(k => k !== key),
    tone_changes: set.tone_changes.filter(c => c.name !== key),
  });
  stashToneSet();
  songToneSet = drop(songToneSet);
  for (const k of Object.keys(toneSetByKind)) toneSetByKind[k] = drop(toneSetByKind[k]);
  toneSetToGlobals(toneSetKind ? toneSetByKind[toneSetKind] : songToneSet);
}

// A project with no tone of its own: the build gives every chart DLC Builder's
// default for its path (gear/default_tones.py — Lead/Combo the lead route,
// Rhythm the rhythm one, the Bass its own). Said wherever tones are shown, so
// "no tones" never reads as "no sound".
function standardToneFor(kind) {
  if (/bass/i.test(kind || '')) return T('Bass (Eden WT550)');
  return /rhythm/i.test(kind || '') ? T('Rhythm (Orange AD50)') : T('Lead (Marshall Plexi)');
}
function standardTonesText() {
  const kinds = arrangements.length ? arrangements.map(a => a.kind) : ['Lead', 'Rhythm'];
  return kinds.map(k => `${arrangements.length ? esc(arrLabel(k)) + ': ' : ''}${standardToneFor(k)}`)
    .filter((v, i, all) => all.indexOf(v) === i).join(' · ');
}

// One card per project tone: its name, the gear it is built from and its
// character (the same drive estimate the preview voice uses), and its volume
// the way the tone editor shows it (higher = louder).
function toneCardHtml(t) {
  const cat = gearCatalogue || {};
  const gearName = (list, g) => g && g.key ? ((gearByKey(list, g.key) || {}).name || g.key) : '';
  const effects = [...(t.pre || []), ...(t.post || []), ...(t.racks || [])].filter(g => g && g.key)
    .map(g => gearName([...(cat.pedals || []), ...(cat.racks || [])], g));
  const gear = [gearName(cat.amps, t.amp), ...effects.slice(0, 2)].filter(Boolean).join(' · ');
  const ch = toneCharacter(t) || { drive: 0 };
  const kind = ch.drive < 0.3 ? { label: T('Limpo'), color: '#5bb8ff' }
    : ch.drive < 0.6 ? { label: T('Crunch'), color: '#e0a54a' }
      : { label: T('Distorção'), color: '#ff6b6b' };
  const vol = t.volume != null ? Math.round(-t.volume * 10) / 10 : null;
  return `<div class="tn-tone">
    <div class="tn-tone-name"><span class="tn-dot" style="background:${kind.color}"></span>${esc(t.name || t.key)}</div>
    ${gear ? `<div class="tn-tone-gear">${esc(gear)}</div>` : ''}
    <div class="tn-tags"><span class="tn-tag">${kind.label}</span>${vol != null ? `<span class="tn-tag">${T('Volume {v}', { v: vol })}</span>` : ''}</div>
  </div>`;
}

// A bundle-clock time as the recording's m:ss.t, the clock the score shows.
function fmtClockTenths(s) {
  if (!isFinite(s) || s < 0) s = 0;
  // Round first: 69.96 s must read 1:10.0, not 1:010.0 (9.96 is < 10, its
  // tenths are not) nor 0:60.0.
  const tenths = Math.round(s * 10);
  const m = Math.floor(tenths / 600), sec = (tenths - m * 600) / 10;
  return `${m}:${sec < 10 ? '0' : ''}${sec.toFixed(1)}`;
}

function renderTonePanel() {
  notePendingChange();
  if (toneSuggestions && toneSuggestions.tracks) renderToneSuggestions();
  const isGp = selectedJob && selectedJob.source_type === 'gp';
  document.getElementById('tonePanel').style.display = selectedJob ? '' : 'none';
  document.getElementById('detectTones').style.display = selectedJob ? '' : 'none';
  document.getElementById('openToneBuilder').style.display = isGp ? '' : 'none';
  if (!selectedJob) return;

  const chips = document.getElementById('toneChips');
  chips.innerHTML = jobTones.length
    ? jobTones.map(toneCardHtml).join('')
    : `<div class="tn-standard"><span class="pv-chip unk">${icon('wave')}${T('Tons standard')}</span>
       <span>${T('Sem tons teus, cada pista usa o tom por defeito do DLC Builder — {list}. Cria os teus em "+ Criar / editar tons".',
    { list: standardTonesText() })}</span></div>`;

  renderToneSetUi(false);
  renderToneChangesList();
  populatePreviewTones();
  renderToneSuggestions();
}

// The controls that show ONE chart's set (base, extras, changes, which track).
// No redraw of the score unless `redraw` — showArr calls this mid-draw.
function renderToneSetUi(withChanges = true) {
  if (!selectedJob) return;
  const multi = arrangements.length > 1;
  document.getElementById('toneTrackRow').hidden = !multi;
  document.getElementById('toneShared').checked = !tonesPerTrack;
  const tabs = document.getElementById('toneTrackTabs');
  tabs.hidden = !(multi && tonesPerTrack);
  tabs.innerHTML = arrangements.map((a, i) =>
    `<button type="button" role="tab" class="tn-tab" data-i="${i}" aria-selected="${i === currentArr}">${esc(arrLabel(a.kind))}</button>`).join('');

  const baseSel = document.getElementById('toneBaseSel');
  baseSel.innerHTML = `<option value="">${jobTones.length ? '—' : esc(T('Tom standard: {tone}', { tone: standardToneFor(currentKind()) }))}</option>` +
    jobTones.map(t => `<option value="${esc(t.key)}">${esc(t.name || t.key)}</option>`).join('');
  baseSel.value = toneBase || '';

  const extra = document.getElementById('toneExtraChecks');
  extra.innerHTML = jobTones.length
    ? jobTones.map(t => `<label class="tn-pill"><input type="checkbox" class="tone-extra" value="${esc(t.key)}" ${toneNames.includes(t.key) ? 'checked' : ''}> ${esc(t.name || t.key)}</label>`).join('')
    : `<span class="tn-empty">${T('Cria tons primeiro.')}</span>`;
  if (withChanges) renderToneChangesList(false);
}

document.getElementById('toneShared').addEventListener('change', e => {
  if (e.target.checked && tonesPerTrack) {
    const kind = currentKind();
    if (!confirm(T('Todas as pistas passam a usar os tons de {track}. Continuar?', { track: arrLabel(kind) }))) {
      e.target.checked = false; return;
    }
  }
  setTonesPerTrack(!e.target.checked);
  if (arrangements.length) showArr(currentArr);
});
document.getElementById('toneTrackTabs').addEventListener('click', e => {
  const tab = e.target.closest('.tn-tab');
  if (tab) showArr(parseInt(tab.dataset.i, 10) || 0);
});

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
  let html = `<option value="">${T('Voz simples (sem tom)')}</option>`;
  if (hasTones) {
    html += `<option value="__follow__">${T('Seguir partitura (tons marcados)')}</option>` +
      jobTones.map(t => `<option value="${esc(t.key)}">${esc(t.name || t.key)}</option>`).join('');
  }
  sel.innerHTML = html;
  sel.disabled = !hasTones;
  sel.title = hasTones ? '' : T('Cria um tom primeiro ("+ Criar / editar tons")');
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
  if (checked.length > 4) { e.target.checked = false; toast(T('Máximo de 4 tons extra.')); return; }
  toneNames = checked;
  if (arrangements.length) showArr(currentArr);
});

function renderToneChangesList(redraw = true) {
  const el = document.getElementById('toneChangesList');
  if (!toneChanges.length) {
    el.innerHTML = `<span class="tn-empty">${T('Sem mudanças de tom. Ativa o modo "Mudança de tom" e clica numa nota.')}</span>`;
  } else {
    const sorted = toneChanges;  // already time-sorted (see loadTones)
    el.innerHTML = sorted.map((c, i) => {
      const name = (jobTones.find(t => t.key === c.name) || {}).name || c.name;
      return `<div class="tn-change"><span class="tn-change-time" title="${c.time.toFixed(2)} s">${fmtClockTenths(c.time - viewOrigin)}</span>
        ${icon('forward')}<span class="tn-change-tone">${esc(name)}</span>
        <button type="button" class="secondary tone-change-rm" data-i="${i}">${T('Remover')}</button></div>`;
    }).join('');
    el.querySelectorAll('.tone-change-rm').forEach(b => b.addEventListener('click', () => {
      const target = sorted[parseInt(b.dataset.i, 10)];
      toneChanges = toneChanges.filter(c => c !== target);
      renderToneChangesList();
    }));
  }
  // Keep the on-score tone markers (amber 🎸) in sync with the changes list —
  // adding/removing a change (or deleting/renaming a tone) redraws the score.
  if (redraw && arrangements.length) showArr(currentArr);
}

function placeToneChange(chartTime) {
  if (!toneNames.length) { toast(T('Marca primeiro tons "extra" para poder trocar.')); return; }
  const opts = toneNames.map((k, i) => {
    const n = (jobTones.find(t => t.key === k) || {}).name || k;
    return `${i + 1}) ${n}`;
  }).join('\n');
  const pick = prompt(T('Trocar para qual tom?\n{opts}', { opts }), '1');
  if (pick === null) return;
  const idx = parseInt(pick, 10) - 1;
  if (isNaN(idx) || idx < 0 || idx >= toneNames.length) { toast(T('Escolha inválida.')); return; }
  toneChanges.push({ time: chartTime, name: toneNames[idx] });
  toneChanges.sort((a, b) => a.time - b.time);  // keep the sorted invariant (see loadTones)
  renderToneChangesList();
  toast(T('Mudança de tom adicionada.'), 'ok');
}

// ---- Section editor (song structure markers: intro/verso/refrão…) ----
// songSections is shared across every arrangement (like toneChanges) — see
// the state declaration above for why sectionsTouched gates the rebuild send.
function renderSectionsList() {
  notePendingChange();
  const el = document.getElementById('sectionsList');
  if (!el) return;
  if (!songSections.length) {
    el.innerHTML = `<span class="meta">${T('Sem secções. Usa "+ Adicionar no cursor" ou o modo "Secção" (clica numa nota).')}</span>`;
  } else {
    el.innerHTML = songSections.map((s, i) => `<div class="anchor-row">
      <input type="number" step="0.01" value="${s.time.toFixed(2)}" data-section-time="${i}" style="width:6rem">s
      <input type="text" value="${esc(s.name)}" data-section-name="${i}" style="width:10rem">
      <button type="button" class="section-rm" data-i="${i}">${T('remover')}</button></div>`).join('');
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
      songSections[i].name = inp.value.trim() || T('Secção');
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
  const name = prompt(T('Nome da secção:'), T('Nova secção'));
  if (name === null) return;
  songSections.push({ time: chartTime, name: name.trim() || T('Secção') });
  songSections.sort((a, b) => a.time - b.time);
  sectionsTouched = true;
  renderSectionsList();
  toast(T('Secção adicionada.'), 'ok');
}

document.getElementById('addSectionAtCursor')?.addEventListener('click', () => {
  if (!arrangements.length) return;
  songSections.push({ time: currentPlayheadT + viewOrigin, name: T('Nova secção') });
  songSections.sort((a, b) => a.time - b.time);
  sectionsTouched = true;
  renderSectionsList();
});

// ---- Tone builder modal ----
function openToneBuilder() {
  if (!selectedJob || selectedJob.source_type !== 'gp') { toast(T('Tons só se aplicam a projetos Guitar Pro.')); return; }
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
    : `<span class="meta">${T('Ainda sem tons.')}</span>`;
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
  if (!src) { toast(T('Escolhe um tom da biblioteca.')); return; }
  addToneToProject(src);
  toast(T('Tom carregado da biblioteca.'), 'ok');
});
// Copy a tone into this project. If the key already exists here, suffix it so
// the load never silently overwrites a tone the user already dialled.
function addToneToProject(src) {
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
  return tone;
}
document.getElementById('toneLibDelete').addEventListener('click', async () => {
  const key = document.getElementById('toneLibSelect').value;
  if (!key) { toast(T('Escolhe um tom da biblioteca.')); return; }
  const r = await fetch(`/tone-library/${encodeURIComponent(key)}`, { method: 'DELETE' });
  if (!r.ok) { toast(T('Não foi possível remover.')); return; }
  toneLibrary = (await r.json()).tones || [];
  populateToneLibSelect();
  toast(T('Removido da biblioteca.'), 'ok');
});
document.getElementById('teSaveLibrary').addEventListener('click', async () => {
  const tone = jobTones.find(t => t.key === editingToneKey);
  if (!tone) { toast(T('Guarda o tom primeiro (Guardar tom).')); return; }
  const r = await fetch('/tone-library', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(tone),
  });
  if (!r.ok) { toast(T('Não foi possível guardar na biblioteca.')); return; }
  toneLibrary = (await r.json()).tones || [];
  populateToneLibSelect();
  toast(T('Guardado na biblioteca.'), 'ok');
});

// ── The tones of the songs in the player's Rocksmith dlc folder ──
// (GET /tone-collection, DLC Builder's tone collection). The scan runs on the
// server; while it does, the list is polled and grows.
let toneCollTimer = null;
let toneCollSearchTimer = null;
// Opened to PICK one tone (a stand-in for a suggested tone) instead of adding
// tones to the project: the card's button picks it and the list closes.
let toneCollPick = null;
function openToneCollection(pick) {
  toneCollPick = pick && typeof pick.onPick === 'function' ? pick : null;
  const hint = document.getElementById('tcPickHint');
  hint.hidden = !toneCollPick;
  hint.textContent = toneCollPick ? T('Escolhe o tom que entra no lugar de «{name}».', { name: toneCollPick.label }) : '';
  document.getElementById('toneCollOverlay').hidden = false;
  refreshToneCollection(true);
}
function closeToneCollection() {
  document.getElementById('toneCollOverlay').hidden = true;
  clearTimeout(toneCollTimer);
  toneCollTimer = null;
  const pick = toneCollPick;
  toneCollPick = null;
  if (pick && pick.onClose) pick.onClose();
}
async function refreshToneCollection(fillFolder) {
  const q = document.getElementById('tcSearch').value;
  const artist = document.getElementById('tcArtist').value;
  let data;
  try {
    data = await getJSON(`/tone-collection?q=${encodeURIComponent(q)}&artist=${encodeURIComponent(artist)}`);
  } catch (e) {
    document.getElementById('tcStatus').textContent = T('Não foi possível ler a coleção: {msg}', { msg: e.message });
    return;
  }
  const folderEl = document.getElementById('tcFolder');
  if (fillFolder && !folderEl.value) folderEl.value = data.folder || data.suggested_folder || '';
  renderToneCollStatus(data);
  renderToneCollArtists(data.artists || []);
  renderToneCollList(data);
  clearTimeout(toneCollTimer);
  if (data.status.state === 'scanning' && !document.getElementById('toneCollOverlay').hidden)
    toneCollTimer = setTimeout(() => refreshToneCollection(false), 800);
}
function renderToneCollStatus(data) {
  const st = data.status || {};
  const el = document.getElementById('tcStatus');
  document.getElementById('tcScan').disabled = st.state === 'scanning';
  if (st.state === 'scanning') {
    el.textContent = st.total
      ? T('A ler {done} de {total} ficheiros… {name}', { done: st.done, total: st.total, name: st.current || '' })
      : T('A procurar ficheiros .psarc…');
  } else if (st.state === 'error') {
    el.textContent = T('A leitura falhou: {msg}', { msg: st.error || '' });
  } else if (data.scanned_at) {
    const when = new Date(data.scanned_at * 1000).toLocaleString();
    el.textContent = (data.unreadable
      ? T('{files} ficheiros lidos ({bad} sem leitura possível), {tones} tons · {when}', { files: data.files, bad: data.unreadable, tones: data.tones_total, when })
      : T('{files} ficheiros lidos, {tones} tons · {when}', { files: data.files, tones: data.tones_total, when }));
  } else {
    el.textContent = data.suggested_folder || data.folder
      ? T('Carrega em "Ler a pasta" para listar os tons das tuas músicas.')
      : T('Indica a pasta dlc do Rocksmith e carrega em "Ler a pasta".');
  }
}
function renderToneCollArtists(artists) {
  const sel = document.getElementById('tcArtist');
  const keep = sel.value;
  const option = (label, value) => {
    const o = document.createElement('option');
    o.textContent = label;
    o.value = value;
    return o;
  };
  sel.replaceChildren(option(T('Todos os artistas ({n})', { n: artists.length }), ''));
  for (const a of artists) sel.append(option(`${a.name} (${a.tones})`, a.name));
  sel.value = artists.some(a => a.name === keep) ? keep : '';
}
// A card's artist filters the list by that artist (same as picking it above).
function filterToneCollArtist(name) {
  const sel = document.getElementById('tcArtist');
  const opt = [...sel.options].find(o => o.value && o.value.localeCompare(name, undefined, { sensitivity: 'base' }) === 0);
  if (!opt) return;
  sel.value = opt.value;
  refreshToneCollection(false);
}
function renderToneCollList(data) {
  const list = document.getElementById('tcList');
  const count = document.getElementById('tcCount');
  list.replaceChildren();
  const shown = data.entries.length;
  count.textContent = !data.tones_total ? ''
    : shown < data.matched
      ? T('{n} tons encontrados — a mostrar {shown}; escreve mais para afinar.', { n: data.matched, shown })
      : (data.matched === 1 ? T('1 tom encontrado.') : T('{n} tons encontrados.', { n: data.matched }));
  for (const e of data.entries) {
    // Built with DOM calls: names come from other people's files.
    const card = document.createElement('div');
    card.className = 'lyr-card';
    const body = document.createElement('div');
    body.className = 'lyr-body';
    const title = document.createElement('b');
    title.textContent = e.name;
    const song = document.createElement('div');
    song.className = 'lyr-meta';
    song.append(e.song || '');
    if (e.artist) {
      const who = document.createElement('button');
      who.type = 'button';
      who.className = 'tc-artist';
      who.textContent = e.artist;
      who.title = T('Ver só os tons deste artista');
      who.addEventListener('click', () => filterToneCollArtist(e.artist));
      song.append(e.song ? ' — ' : '', who);
    }
    if (e.arrangements.length) song.append(` · ${e.arrangements.join(', ')}`);
    const gear = document.createElement('div');
    gear.className = 'lyr-preview';
    gear.textContent = [e.amp, e.cabinet, ...e.effects].filter(Boolean).join(' · ');
    body.append(title, song, gear);
    const use = document.createElement('button');
    use.type = 'button';
    use.textContent = toneCollPick ? T('Escolher este') : T('Usar neste projeto');
    use.addEventListener('click', () => takeCollectionTone(e.id, toneCollPick ? 'pick' : 'project', e));
    const lib = document.createElement('button');
    lib.type = 'button';
    lib.className = 'secondary';
    lib.title = T('Guardar na biblioteca');
    lib.setAttribute('aria-label', T('Guardar na biblioteca'));
    lib.innerHTML = icon('star');
    lib.addEventListener('click', () => takeCollectionTone(e.id, 'library'));
    card.append(body, use, lib);
    list.append(card);
  }
}
async function takeCollectionTone(id, where, row) {
  let tone;
  try {
    tone = (await getJSON(`/tone-collection/tone?id=${encodeURIComponent(id)}`)).tone;
  } catch (e) { toast(e.message); return; }
  if (where === 'pick' && toneCollPick) {
    toneCollPick.onPick(tone, row);
    closeToneCollection();
    return;
  }
  if (where === 'project') {
    addToneToProject(tone);
    toast(T('Tom adicionado ao projeto — fica pendente até "Aplicar e reconstruir".'), 'ok');
    return;
  }
  try {
    toneLibrary = (await getJSON('/tone-library', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(tone),
    })).tones || [];
  } catch (e) { toast(e.message); return; }
  populateToneLibSelect();
  toast(T('Guardado na biblioteca.'), 'ok');
}
document.getElementById('toneCollOpen').addEventListener('click', openToneCollection);
document.getElementById('toneCollClose').addEventListener('click', closeToneCollection);
document.getElementById('tcScan').addEventListener('click', async () => {
  const folder = document.getElementById('tcFolder').value.trim();
  try {
    await getJSON('/tone-collection/scan', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ folder }),
    });
  } catch (e) { toast(e.message); return; }
  refreshToneCollection(false);
});
document.getElementById('tcArtist').addEventListener('change', () => refreshToneCollection(false));
document.getElementById('tcSearch').addEventListener('input', () => {
  clearTimeout(toneCollSearchTimer);
  toneCollSearchTimer = setTimeout(() => refreshToneCollection(false), 250);
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
  if (q && !list.length) sel.innerHTML = `<option value="">${T('— sem resultados —')}</option>`;
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
    return `<div class="knob" data-min="${k.min}" data-max="${k.max}" data-step="${k.step}" data-default="${k.default}" title="${esc(T('{name} — arrasta para rodar, ou escreve o valor; duplo-clique repõe', { name: k.name }))}">
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
    ov += `<div class="oknob" data-i="${i}" title="${esc(T('{name} — arrasta ou escreve o valor', { name: kn.name }))}"
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
        <option value="pre">${T('Pré-pedal')}</option>
        <option value="post">${T('Pós-pedal')}</option>
        <option value="rack">Rack</option>
      </select>
      <input type="text" class="te-eff-search" placeholder="${T('procurar…')}" style="min-width:8rem;font-size:.8rem;padding:.22rem .45rem">
      <select class="te-eff-gear" style="min-width:11rem"></select>
      <button type="button" class="icon te-eff-rm">${T('remover')}</button>
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
  document.getElementById('teVolume').value = '18';
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
  // Shown like DLC Builder does, positive and louder upwards; stored negative.
  document.getElementById('teVolume').value = t.volume != null ? -t.volume : 18;
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
  if (!name) { toast(T('Dá um nome ao tom.')); return; }
  const ampKey = document.getElementById('teAmp').value;
  const cabKey = document.getElementById('teCab').value;
  if (!ampKey || !cabKey) { toast(T('Escolhe amplificador e cabine.')); return; }

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
    volume: -Math.min(36, Math.max(0.1, parseFloat(document.getElementById('teVolume').value) || 18)),
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
  toast(T('Tom guardado.'), 'ok');
});

document.getElementById('teDelete').addEventListener('click', () => {
  if (!editingToneKey) { document.getElementById('toneEditForm').style.display = 'none'; document.getElementById('toneEditEmpty').style.display = ''; return; }
  jobTones = jobTones.filter(t => t.key !== editingToneKey);
  forgetToneKey(editingToneKey);
  editingToneKey = null;
  document.getElementById('toneEditForm').style.display = 'none';
  document.getElementById('toneEditEmpty').style.display = '';
  renderToneListEditor();
  renderTonePanel();
  toast(T('Tom removido.'), 'ok');
});

// ---- Lyrics editor ----
function renderLyricsRows() {
  notePendingChange();
  document.getElementById('lyricsSyncRow').hidden = !lyricsEvents.length;
  document.getElementById('lyricsEmpty').hidden = lyricsEvents.length > 0;
  document.getElementById('lyricsCount').textContent = lyricsEvents.length
    ? T('{n} palavras', { n: lyricsEvents.length }) : '';
  const tb = document.getElementById('lyricsRows');
  tb.innerHTML = lyricsEvents.map((e, i) => `
    <tr data-i="${i}"${e.lineBreak ? ' class="ly-line-end"' : ''}>
      <td><input type="number" step="0.01" min="0" value="${e.time.toFixed(2)}" class="ly-time" aria-label="${T('Tempo (s)')}"><span class="ly-clock">${fmtClockTenths(e.time)}</span></td>
      <td><input type="text" value="${esc(e.lyric)}" class="ly-text" aria-label="${T('Palavra')}"></td>
      <td><input type="checkbox" class="ly-break" ${e.lineBreak ? 'checked' : ''} aria-label="${T('Fim de linha')}"></td>
      <td><input type="number" step="0.01" min="0.1" value="${e.length.toFixed(2)}" class="ly-length" aria-label="${T('Duração (s)')}"></td>
      <td><button type="button" class="icon ly-remove" title="${T('Remover')}" aria-label="${T('Remover')}">${icon('x')}</button></td>
    </tr>`).join('');
  tb.querySelectorAll('tr').forEach(tr => {
    const i = parseInt(tr.dataset.i, 10);
    const redraw = () => { if (arrangements.length) showArr(currentArr); updatePendingChangesInfo(); };
    tr.querySelector('.ly-time').addEventListener('change', e => {
      lyricsEvents[i].time = parseFloat(e.target.value) || 0;
      tr.querySelector('.ly-clock').textContent = fmtClockTenths(lyricsEvents[i].time);
      redraw();
    });
    // 'change' only (fires on blur/Enter) — an 'input' handler here rebuilt the
    // WHOLE score SVG on every keystroke, which froze typing on a long song.
    tr.querySelector('.ly-text').addEventListener('change', e => { lyricsEvents[i].lyric = e.target.value; redraw(); });
    tr.querySelector('.ly-break').addEventListener('change', e => {
      lyricsEvents[i].lineBreak = e.target.checked;
      tr.classList.toggle('ly-line-end', e.target.checked);
      redraw();
    });
    tr.querySelector('.ly-length').addEventListener('change', e => { lyricsEvents[i].length = Math.max(0.1, parseFloat(e.target.value) || 0.1); redraw(); });
    tr.querySelector('.ly-remove').addEventListener('click', () => { lyricsEvents.splice(i, 1); renderLyricsRows(); redraw(); });
  });
  renderInspLyrics();
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
  none: '', detecting: T('a iniciar (a carregar modelos ML)…'), normalizing: T('a normalizar áudio…'),
  separating: T('a isolar a voz (Demucs) — pode demorar vários minutos…'),
  transcribing: T('a transcrever (WhisperX)…'),
  aligning: T('a sincronizar a letra com a gravação (WhisperX)…'),
  ready: T('deteção concluída'), empty: T('nenhuma letra detetada'),
  unavailable: T('deteção indisponível (extra "lyrics" não instalado)'),
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
    logEl.textContent = T('a aguardar o worker…');
  } else {
    logEl.textContent = '';
  }
}

// Which chart the lyrics follow: the first in the build's own slot order — the
// same chart the build times the GP file's lyrics on (gp_pipeline's `first`).
const LYRIC_REF_ORDER = ['Lead', 'Rhythm', 'Combined', 'Alternate Lead', 'Alternate Rhythm', 'Bass'];
function lyricRefArr() {
  for (const k of LYRIC_REF_ORDER) {
    const i = arrangements.findIndex(a => a.kind === k);
    if (i >= 0) return i;
  }
  return arrangements.length ? 0 : -1;
}
// Lyric-clock padding of the BUILT bundle (lyric time + this = bundle time).
let lyricPadBuilt = 0;
// Built lyric time → where the reference chart's PENDING tempo/anchors put it,
// in the same (lyric) clock: the notes' preview (previewScale + the anchor
// warp) applied to the lyric's bundle time. Identity when nothing is pending.
// A snapshot: it reads the pending state now, not when it is called.
function lyricSyncMap() {
  const a = arrangements[lyricRefArr()];
  if (!isGpJob() || !a) return t => t;
  const ratio = tempoRatioOf(a);
  const warp = buildTimeWarp((syncAnchorsByKind[a.kind] || []).map(p => p.slice()));
  const shift = scoreShift, pad = lyricPadBuilt;
  const lead = livePad();
  const origin = Math.max(0, MIN_LEAD - offsetLive) + leadInBuilt;
  return t => warp((t + pad - shift) * ratio + lead) - origin;
}
function lyricSyncSig() {
  const a = arrangements[lyricRefArr()];
  if (!isGpJob() || !a) return '';
  return JSON.stringify([a.kind, a.tempo_scale || 1, tempoScaleByKind[a.kind] ?? null,
    syncAnchorsByKind[a.kind] || [], offsetLive, scoreShift, lyricPadBuilt]);
}
// x with f(x) = y for an increasing f (the sync maps are piecewise linear).
function invertIncreasing(f, y) {
  let lo = y - 1, hi = y + 1;
  for (let k = 0; k < 40 && f(lo) > y; k++) lo = y - 2 ** (k + 1);
  for (let k = 0; k < 40 && f(hi) < y; k++) hi = y + 2 ** (k + 1);
  for (let k = 0; k < 60; k++) {
    const mid = (lo + hi) / 2;
    if (f(mid) < y) lo = mid; else hi = mid;
  }
  return (lo + hi) / 2;
}
// The rows are always kept where they are SHOWN (every lyric tool works in that
// clock), so when the reference chart's pending sync changes they are carried
// from the old map to the new one: back through the old, forward through the
// new. Undoing a correction brings them back. Called before every redraw.
let lyricFollowSig = null, lyricFollowMap = t => t;
function resetLyricFollow() { lyricFollowSig = lyricSyncSig(); lyricFollowMap = lyricSyncMap(); }
function lyricsFollowSync() {
  const sig = lyricSyncSig();
  if (sig === lyricFollowSig) return;
  const prev = lyricFollowMap, next = lyricSyncMap();
  const baseline = !lyricFollowSig;  // nothing to carry from (not loaded yet)
  lyricFollowSig = sig; lyricFollowMap = next;
  if (baseline || !lyricsFollowChart || !lyricsEvents.length) return;
  for (const r of lyricsEvents) {
    const start = invertIncreasing(prev, r.time);
    const end = invertIncreasing(prev, r.time + r.length);
    r.time = Math.max(0, next(start));
    r.length = Math.max(0.05, next(end) - r.time);
  }
  renderLyricsRows();
  updatePendingChangesInfo();
}
function setLyricsFollowChart(on) {
  lyricsFollowChart = !!on;
  updateLyricFollowUi();
}
function updateLyricFollowUi() {
  const box = document.getElementById('ilFollowChart');
  if (!box) return;
  box.checked = lyricsFollowChart;
  box.disabled = !isGpJob();
  const a = arrangements[lyricRefArr()];
  document.getElementById('ilFollowRef').textContent = a ? T('(pista {track})', { track: arrLabel(a.kind) }) : '';
}
document.getElementById('ilFollowChart').addEventListener('change', e => setLyricsFollowChart(e.target.checked));

// "Voltar à letra da pauta": the editor's rows are dropped on the next rebuild
// and the build reads the lyrics from the GP file again — the way to get the
// score's own phrasing back after the rows replaced it.
let lyricsBackToScore = false;
document.getElementById('lyricsFromScore').addEventListener('click', async () => {
  if (!(await confirmModal(T('Descartar a letra do editor e voltar a lê-la do ficheiro Guitar Pro? Acontece em "Aplicar e reconstruir"; as edições feitas aqui perdem-se.')))) return;
  lyricsEvents = [];
  lyricSelected = null;
  lyricsBackToScore = true;
  setLyricsFollowChart(true);
  renderLyricsRows();
  updatePendingChangesInfo();
  document.getElementById('lyricsInfo').textContent =
    T('A letra da pauta volta a ser lida em "Aplicar e reconstruir".');
});

async function loadLyrics(id) {
  const r = await fetch(`/jobs/${id}/lyrics`);
  if (!r.ok) return;
  const body = await r.json();
  lyricsBackToScore = false;
  lyricsEvents = eventsToRows(body.events);
  lyricsBuilt = JSON.stringify(serializeLyrics());
  setLyricsFollowChart(body.follow_chart);
  resetLyricFollow();
  renderLyricsRows();
  updatePendingChangesInfo();
  document.getElementById('lyricsInfo').textContent = LYRICS_STATUS_LABEL[body.status] || '';
  updateLyricsProgress(body.status, body.log);
  clearInterval(lyricsPollTimer);
  if (LYRICS_DETECTING_STATUSES.has(body.status)) {
    const startedAt = Date.now();
    lyricsPollTimer = pollJob('lyrics', b => {
      let label = LYRICS_STATUS_LABEL[b.status] || '';
      const elapsed = Date.now() - _lyricsStatusSince;
      const stuckMs = LYRICS_STUCK_MS[b.status] || 8*60*1000;
      const isStuck = LYRICS_DETECTING_STATUSES.has(b.status) && elapsed > stuckMs;
      if (b.status === 'detecting' && !(b.log || []).length && Date.now() - startedAt > 30000)
        label += T(' — sem resposta do worker há mais de 30s; verifica logs/worker.log');
      if (isStuck)
        label += T(' — sem progresso há {min} min; verifica logs/worker.log', { min: Math.round(elapsed/60000) });
      document.getElementById('lyricsInfo').textContent = label;
      updateLyricsProgress(b.status, b.log, isStuck);
      if (LYRICS_DETECTING_STATUSES.has(b.status)) return false;
      lyricsEvents = eventsToRows(b.events);
      // A failed alignment must not cost the lyrics it was aligning: they
      // may exist only in the editor (loaded from LRCLIB, not yet rebuilt).
      if (lyricsBeforeAlign && b.status !== 'ready') {
        lyricsEvents = lyricsBeforeAlign;
        toast(T('A sincronização não correu — a letra ficou como estava. Vê o registo acima.'));
      } else {
        setLyricsFollowChart(b.follow_chart);  // detected/aligned: timed to the recording
      }
      lyricsBeforeAlign = null;
      resetLyricFollow();
      renderLyricsRows();
      return true;
    });
  }
}

async function detectLyrics() {
  if (!selectedJob) return;
  if (!await fetchOrToast(`/jobs/${selectedJob.id}/detect-lyrics`, { method: 'POST' })) return;
  toast(T('A detetar letra… (pode demorar)'), 'ok');
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

// Rounded to the second BEFORE splitting, or 119.6 s reads "1:60".
const fmtMinSec = s => {
  const whole = Math.round(s);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
};

// An LRC time tag, [mm:ss.xx], rounded to the hundredth before splitting so
// 59.997 s is [01:00.00], not [00:60.00].
const lrcTag = t => {
  const cs = Math.round(Math.max(0, t) * 100);
  const m = Math.floor(cs / 6000);
  return `[${String(m).padStart(2, '0')}:${((cs - m * 6000) / 100).toFixed(2).padStart(5, '0')}]`;
};

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

// One LRCLIB result's description — shared by the Letra page and the wizard.
// Built with DOM calls: every string here comes from a third party.
function lyricsCardBody(c, recordingS) {
  const body = document.createElement('div');
  body.className = 'lyr-body';
  const title = document.createElement('b');
  title.textContent = `${c.track} — ${c.artist}`;
  const meta = document.createElement('span');
  meta.className = 'lyr-meta';
  const badge = document.createElement('span');
  badge.className = 'lyr-badge ' + (c.synced ? 'synced' : 'plain');
  badge.textContent = c.instrumental ? T('instrumental') : c.synced ? T('sincronizada') : T('só texto');
  let len = '';
  if (c.duration) {
    len = fmtMinSec(c.duration);
    if (recordingS) {
      const gap = recordingS - c.duration;
      len += Math.abs(gap) < 2 ? T(' (igual à tua gravação)')
        : T(' (a tua gravação: {len}, {gap} s)', { len: fmtMinSec(recordingS), gap: `${gap > 0 ? '+' : '−'}${Math.round(Math.abs(gap))}` });
    }
  }
  meta.append(badge, [c.album, len].filter(Boolean).join(' · '));
  const preview = document.createElement('span');
  preview.className = 'lyr-preview';
  preview.textContent = (c.plain || '').split('\n').filter(Boolean).slice(0, 2).join('\n');
  body.append(title, meta, preview);
  return body;
}

function renderLyricsCandidates() {
  const el = document.getElementById('lyricsResults');
  el.replaceChildren();
  for (const c of lyricsCandidates) {
    const card = document.createElement('div');
    card.className = 'lyr-card';
    const body = lyricsCardBody(c, waveDuration);
    const acts = document.createElement('div');
    acts.className = 'lyr-acts';
    const btn = (label, fn) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'secondary'; b.textContent = label;
      b.addEventListener('click', fn);
      acts.append(b);
    };
    if (c.synced) btn(T('Usar'), () => useLyricsCandidate(c));
    else if (c.plain) btn(T('Sincronizar com a gravação'), () => alignLyrics(plainLines(c.plain), 'plain'));
    card.append(body, acts);
    el.append(card);
  }
}

document.getElementById('lyricsSearch').addEventListener('click', async () => {
  if (!selectedJob) return;
  const info = document.getElementById('lyricsSearchInfo');
  const btn = document.getElementById('lyricsSearch');
  btn.disabled = true;
  info.textContent = T('A procurar…');
  try {
    const q = `title=${encodeURIComponent(selectedJob.title || '')}&artist=${encodeURIComponent(selectedJob.artist || '')}`
      + (waveDuration ? `&duration=${waveDuration.toFixed(1)}` : '');
    const r = await getJSON(`/lyrics-lookup?${q}`);
    lyricsCandidates = r.candidates || [];
    info.textContent = lyricsCandidates.length
      ? T('{n} resultado(s) no LRCLIB — escolhe a versão da tua gravação.', { n: lyricsCandidates.length })
      : T('Nada encontrado no LRCLIB para "{title}" de {artist}. Remixes de fãs e músicas feitas por IA raramente lá estão — usa "Detetar letra" ou escreve-a no editor.',
        { title: r.searched_title, artist: r.searched_artist });
  } catch (err) {
    lyricsCandidates = [];
    info.textContent = T('Não consegui procurar agora ({err}).', { err: err.message });
  } finally {
    btn.disabled = false;
  }
  renderLyricsCandidates();
});

async function useLyricsCandidate(c) {
  if (lyricsEvents.length && !(await confirmModal(T('Substituir a letra que está no editor por esta?')))) return;
  try {
    const r = await getJSON('/lyrics/parse', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: c.synced, offset_s: 0 }),
    });
    lyricsEvents = eventsToRows(r.events);
    setLyricsFollowChart(false);  // an LRC is timed to a recording, not to the score
  } catch (err) {
    toast(T('Não foi possível usar esta letra: {err}', { err: err.message }));
    return;
  }
  renderLyricsRows();
  redrawScore();
  document.getElementById('lyricsSearchInfo').textContent =
    T('Letra carregada com os tempos do LRCLIB. Ouve-a na partitura: se estiver adiantada ou atrasada, usa "1ª palavra = cursor"; se sair do tempo a meio, "Sincronizar com a gravação".');
  toast(T('Letra carregada — "Aplicar e reconstruir" para a incluir.'), 'ok');
}

function shiftLyrics(delta) {
  if (!lyricsEvents.length || !Number.isFinite(delta) || !delta) return;
  const first = Math.min(...lyricsEvents.map(e => e.time));
  const d = Math.max(delta, -first);  // never before the recording starts
  for (const e of lyricsEvents) e.time = Math.round((e.time + d) * 1000) / 1000;
  renderLyricsRows();
  redrawScore();
  updatePendingChangesInfo();
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

// ── Letra next to the score (the Partitura inspector's "Letra" tab) ──────────
// The Letra page's timing tools, where the words are actually heard: click a
// word on the score and move it — alone, or with everything after it — to the
// cursor. Same rows, same clock (playhead minus leadInBuilt), so every edit
// here is an ordinary pending lyric edit ridden by "Aplicar e reconstruir".
// The selection is the ROW OBJECT, not its index: sorting or deleting rows
// renumbers them, and a reload replaces them (dropping the selection).
let lyricSelected = null;
const lyricCursorTime = () => Math.max(0, currentPlayheadT - leadInBuilt);
const ilStep = () => Math.abs(parseFloat(document.getElementById('ilShift').value) || 0.1);
const lyricsByTime = () => [...lyricsEvents].sort((a, b) => a.time - b.time);

function lyricsEdited() {
  renderLyricsRows();  // also refreshes this inspector
  redrawScore();
  updatePendingChangesInfo();
}

function selectLyric(e) {
  lyricSelected = e && lyricsEvents.includes(e) ? e : null;
  renderInspLyrics();
  redrawScore();
}

// Moves one word and every word from it onward by delta. Earlier words stay
// where they are, so the word cannot be pushed back past the one before it
// (that would reorder the lyric).
function shiftLyricsFrom(word, delta) {
  if (!lyricsEvents.includes(word) || !Number.isFinite(delta) || !delta) return false;
  const t0 = word.time;
  const earlier = lyricsEvents.filter(w => w.time < t0).map(w => w.time);
  const floor = earlier.length ? Math.max(...earlier) + 0.01 : 0;
  const d = Math.max(delta, floor - t0);
  if (!d) return false;
  for (const w of lyricsEvents) {
    if (w.time >= t0) w.time = Math.round((w.time + d) * 1000) / 1000;
  }
  return d !== delta;  // true when the move was limited
}

function renderInspLyrics() {
  const body = document.getElementById('inspLyrics');
  if (!body) return;
  updateLyricFollowUi();
  if (lyricSelected && !lyricsEvents.includes(lyricSelected)) lyricSelected = null;
  const words = lyricsEvents.filter(e => e.lyric.trim()).length;
  document.getElementById('ilCount').textContent = words ? T('{n} palavra(s)', { n: words }) : '';
  document.getElementById('ilEmpty').hidden = lyricsEvents.length > 0;
  document.getElementById('ilAllTools').hidden = !lyricsEvents.length;
  const e = lyricSelected;
  document.getElementById('ilNoSel').hidden = !!e;
  document.getElementById('ilSelTools').hidden = !e;
  document.getElementById('ilPickAtCursor').disabled = !lyricsEvents.length;
  if (!e) return;
  const set = (id, v) => {
    const el = document.getElementById(id);
    if (document.activeElement !== el) el.value = v;  // never under the user's typing
  };
  set('ilWord', e.lyric);
  set('ilTime', e.time.toFixed(2));
  document.getElementById('ilBreak').checked = !!e.lineBreak;
  const order = lyricsByTime();
  const i = order.indexOf(e);
  document.getElementById('ilPrev').disabled = i <= 0;
  document.getElementById('ilNext').disabled = i >= order.length - 1;
  document.getElementById('ilSelInfo').textContent =
    T('palavra {i} de {n} · {after} depois dela', { i: i + 1, n: order.length, after: order.length - i - 1 });
}

document.getElementById('ilOpenPage').addEventListener('click', ev => {
  ev.preventDefault();
  showSection('letras');
});
document.getElementById('ilFirstToCursor').addEventListener('click', () => {
  if (!lyricsEvents.length) return;
  shiftLyrics(lyricCursorTime() - Math.min(...lyricsEvents.map(e => e.time)));
});
document.getElementById('ilShiftBack').addEventListener('click', () => shiftLyrics(-ilStep()));
document.getElementById('ilShiftFwd').addEventListener('click', () => shiftLyrics(ilStep()));
document.getElementById('ilFromHere').addEventListener('click', () => {
  const e = lyricSelected;
  if (!e) return;
  if (shiftLyricsFrom(e, lyricCursorTime() - e.time)) {
    toast(T('A palavra não pode passar para antes da anterior — ficou logo a seguir a ela.'));
  }
  lyricsEdited();
});
document.getElementById('ilWordNudgeBack').addEventListener('click', () => {
  if (lyricSelected) { shiftLyricsFrom(lyricSelected, -ilStep()); lyricsEdited(); }
});
document.getElementById('ilWordNudgeFwd').addEventListener('click', () => {
  if (lyricSelected) { shiftLyricsFrom(lyricSelected, ilStep()); lyricsEdited(); }
});
document.getElementById('ilWordToCursor').addEventListener('click', () => {
  if (!lyricSelected) return;
  lyricSelected.time = Math.round(lyricCursorTime() * 1000) / 1000;
  lyricsEdited();
});
document.getElementById('ilTime').addEventListener('change', ev => {
  if (!lyricSelected) return;
  lyricSelected.time = Math.max(0, parseFloat(ev.target.value) || 0);
  lyricsEdited();
});
document.getElementById('ilWord').addEventListener('change', ev => {
  if (!lyricSelected) return;
  lyricSelected.lyric = ev.target.value;
  lyricsEdited();
});
document.getElementById('ilBreak').addEventListener('change', ev => {
  if (!lyricSelected) return;
  lyricSelected.lineBreak = ev.target.checked;
  lyricsEdited();
});
const stepLyric = dir => {
  const order = lyricsByTime();
  const next = order[order.indexOf(lyricSelected) + dir];
  if (next) selectLyric(next);
};
document.getElementById('ilPrev').addEventListener('click', () => stepLyric(-1));
document.getElementById('ilNext').addEventListener('click', () => stepLyric(1));
document.getElementById('ilRemove').addEventListener('click', () => {
  const e = lyricSelected;
  if (!e) return;
  const order = lyricsByTime();
  const i = order.indexOf(e);
  lyricsEvents.splice(lyricsEvents.indexOf(e), 1);
  lyricSelected = order[i + 1] || order[i - 1] || null;
  lyricsEdited();
});
// The word being sung at the cursor: the last one starting at or before it.
document.getElementById('ilPickAtCursor').addEventListener('click', () => {
  const t = lyricCursorTime();
  const order = lyricsByTime();
  selectLyric(order.filter(e => e.time <= t + 1e-6).pop() || order[0] || null);
});
document.getElementById('ilAddAtCursor').addEventListener('click', () => {
  const e = { time: Math.round(lyricCursorTime() * 1000) / 1000, length: 0.5, lyric: '', lineBreak: false };
  lyricsEvents.push(e);
  lyricSelected = e;
  lyricsEdited();
  document.getElementById('ilWord').focus();
});

async function alignLyrics(lines, what) {
  if (!selectedJob || !lines.length) return;
  const msg = what === 'plain'
    ? T('Esta letra não tem tempos: o WhisperX vai procurar cada palavra na voz da música inteira (alguns minutos, precisa dos extras ML). Continuar?')
    : T('O WhisperX vai medir na gravação o tempo de cada palavra desta letra (alguns minutos, precisa dos extras ML). Substitui os tempos atuais. Continuar?');
  if (!(await confirmModal(msg))) return;
  try {
    await getJSON(`/jobs/${selectedJob.id}/detect-lyrics`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ align_lines: lines }),
    });
  } catch (err) {
    toast(T('Não foi possível sincronizar: {err}', { err: err.message }));
    return;
  }
  toast(T('A sincronizar a letra com a gravação… (pode demorar)'), 'ok');
  lyricsBeforeAlign = lyricsEvents.map(e => ({ ...e }));
  await loadLyrics(selectedJob.id);
}
document.getElementById('lyricsAlign').addEventListener('click', () => alignLyrics(editorLines(), 'editor'));

// ── Tone detection ───────────────────────────────────────────────────────────

async function detectTones() {
  if (!selectedJob) return;
  if (!await fetchOrToast(`/jobs/${selectedJob.id}/detect-tones`, { method: 'POST' })) return;
  toast(T('A detetar tom… (pode demorar)'), 'ok');
  document.getElementById('toneDetectionWrap').style.display = '';
  document.getElementById('toneDetectionLog').textContent = T('a iniciar…');
  document.getElementById('toneDetectionResult').innerHTML = '';
  pollToneDetection();
}

let _toneDetectionPoll = null;
function pollToneDetection() {
  clearInterval(_toneDetectionPoll);
  _toneDetectionPoll = pollJob('detected-tones', (d, jobId) => {
    document.getElementById('toneDetectionLog').textContent = (d.log || []).join('\n');
    if (d.status === 'ready') {
      renderToneDetectionResult(d);
      loadToneSuggestions(jobId);
      loadAttackSources();  // the separation it ran left every instrument behind
      return true;
    }
    if (d.status === 'unavailable') {
      document.getElementById('toneDetectionResult').innerHTML =
        `<span class="meta" style="color:#e88">${T('Deteção falhou — vê o log acima.')}</span>`;
      return true;
    }
    return false;
  });
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
      `<span class="tone-cand-match" title="${T('Semelhança estimada com o gravado')}">${m}%</span>` +
      `<button type="button" class="secondary tone-cand-use" data-role="${esc(role)}" data-key="${esc(c.key)}">${T('usar')}</button></div>`;
  }).join('');
  const title = role === 'lead' ? T('Lead — tons semelhantes') : T('Rhythm — tons semelhantes');
  return `<div class="tone-cand-group"><div class="meta" style="margin:.4rem 0 .2rem">${esc(title)} ` +
    `<span class="meta">${T('(ordenados por semelhança)')}</span></div>${rows}</div>`;
}

function renderToneDetectionResult(d) {
  _lastToneDetection = d;
  const cat = d.category || '?';
  const catLabel = { clean: T('Limpo (Clean)'), crunch: 'Crunch', high_gain: T('Distorcido (High Gain)') }[cat] || cat;
  const p = d.profile || {};
  let profileHtml = '';
  if (p && (p.gain_level !== undefined)) {
    profileHtml = `<div class="tone-prof" style="margin-top:.4rem">` +
      _profileBar(T('Ganho/distorção'), p.gain_level) +
      _profileBar(T('Brilho'), p.brightness) +
      _profileBar(T('Graves'), p.low_end) +
      `</div>`;
  }
  const el = document.getElementById('toneDetectionResult');
  el.innerHTML =
    `<div style="margin-top:.3rem"><strong>${T('Categoria detetada:')}</strong> ${esc(catLabel)}</div>` +
    profileHtml +
    `<div class="anchor-row" style="margin-top:.4rem">` +
    `<button type="button" id="applyDetectedTones" class="secondary">${T('Aplicar melhores (Lead + Rhythm)')}</button></div>` +
    `<div class="meta" style="margin-top:.3rem">${T('Não encontraste o tom certo? Experimenta os semelhantes abaixo — cada um dá a sua % de semelhança com o gravado.')}</div>` +
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
  if (!tone) { toast(T('Tom não encontrado.')); return; }
  const prefix = role === 'lead' ? 'RFLead_' : 'RFRhythm_';
  jobTones = jobTones.filter(t => !t.key.startsWith(prefix));
  jobTones.push(tone);
  if (role === 'lead') toneBase = tone.key;
  toneNames = jobTones.map(t => t.key);
  renderTonePanel();
  toast(T('Tom "{name}" aplicado — "Aplicar e reconstruir" para gravar.', { name: tone.name || tone.key }), 'ok');
}

function applyDetectedTones(detected) {
  if (!detected.lead || !detected.rhythm) { toast(T('Sem tons detetados.')); return; }
  const lead = detected.lead;
  const rhythm = detected.rhythm;
  // Merge into current tones, replacing any existing RF-detected ones.
  jobTones = jobTones.filter(t => !t.key.startsWith('RF'));
  jobTones.push(lead, rhythm);
  toneBase = lead.key;
  toneNames = [lead.key, rhythm.key];
  renderTonePanel();
  toast(T('Tons sugeridos aplicados — "Aplicar e reconstruir" para gravar.'), 'ok');
}

document.getElementById('detectTones').addEventListener('click', detectTones);

// ── Tone suggestions per part of each track (GET /tone-suggestions) ──────────
// The recording's tone over time read against what each track PLAYS in each
// part (tone_analysis/sections.py). Computed from the current build.

const toneTrackOpen = {};  // kind → whether its suggestion card is unfolded (kept across re-renders)
const TONE_ROLE = {
  clean: { label: T('Limpo'), color: '#5bb8ff' },
  rhythm: { label: T('Ritmo'), color: '#e0a54a' },
  lead: { label: T('Solo'), color: '#ff6b6b' },
  silent: { label: T('Não toca'), color: '#3a3d48' },
};
const TONE_CONFIDENCE = { high: T('confiança alta'), medium: T('confiança média'), low: T('confiança baixa') };

function toneReasonText(r) {
  const pct = `${Math.round((Number(r.value) || 0) * 100)}%`;
  switch (r.code) {
    case 'gain': return T('distorção na gravação {pct}', { pct });
    case 'chords': return T('acordes em {pct} das notas', { pct });
    case 'palm_mute': return T('palm mute em {pct}', { pct });
    case 'lead': return T('bends/vibrato/ligados em {pct}', { pct });
    case 'high': return T('casa 12 ou acima em {pct}', { pct });
    case 'ring': return T('notas a soar (let ring) em {pct}', { pct });
    case 'no_audio': return T('a guitarra quase não se ouve aqui — usei o som geral da música');
    default: return r.code;
  }
}

// The user's stand-ins for suggested tones: {suggested key: {tone, source,
// label}}. The switch points stay the app's; only which tone plays at them
// changes. One map for every track, since the same preset is usually suggested
// on several. Kept with the project (PATCH /tone-swaps, read back with the
// suggestions), so leaving it does not lose them.
let toneSwaps = {};
let toneSwapsJob = null;
async function saveToneSwaps() {
  if (!selectedJob) return;
  try {
    await getJSON(`/jobs/${selectedJob.id}/tone-swaps`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ swaps: toneSwaps }),
    });
  } catch (e) { toast(T('Não foi possível guardar as trocas de tom: {msg}', { msg: e.message })); }
}

// A plan with its tone keys mapped through keyMap: names deduplicated, and a
// change to the tone already playing (two suggestions swapped for one tone)
// dropped. Pure.
function swapPlan(plan, keyMap) {
  const k = key => keyMap[key] || key;
  const names = [];
  for (const n of plan.names || []) { const m = k(n); if (!names.includes(m)) names.push(m); }
  const base = plan.base ? k(plan.base) : null;
  const changes = [];
  let current = base;
  for (const c of (plan.changes || []).slice().sort((x, y) => x.time - y.time)) {
    const m = k(c.name);
    if (m === current) continue;
    changes.push({ time: +c.time, name: m });
    current = m;
  }
  return { tone_base: base, tone_names: names, tone_changes: changes };
}

// Every distinct tone the plans suggest, in first-seen order.
function suggestedTones(tracks) {
  const seen = new Map();
  for (const t of tracks || []) for (const tone of t.tones || []) if (!seen.has(tone.key)) seen.set(tone.key, tone);
  return [...seen.values()];
}

// The picker of what plays in place of the suggested tone ``key`` (named ``name``):
// the same one map, whether it is picked above the tracks or in a part's row.
function toneSwapSelect(key, name) {
  const opts = (items, prefix) => items.map(t => `<option value="${prefix}${esc(t.key)}">${esc(t.name || t.key)}</option>`).join('');
  const sw = toneSwaps[key];
  const listed = sw && ((sw.source === 'project' && jobTones.some(t => t.key === sw.tone.key)) ||
    (sw.source === 'library' && toneLibrary.some(t => t.key === sw.tone.key)));
  const picked = sw && !listed
    ? `<option value="c:" selected>${esc(sw.label || sw.tone.name || sw.tone.key)}</option>` : '';
  return `<select class="ts-swap" data-key="${esc(key)}" data-label="${esc(name)}" aria-label="${esc(T('Trocar {name} por', { name }))}">
      <option value="">${esc(T('{name} (o sugerido)', { name }))}</option>${picked}
      ${jobTones.length ? `<optgroup label="${esc(T('Tons do projeto'))}">${opts(jobTones, 'p:')}</optgroup>` : ''}
      ${toneLibrary.length ? `<optgroup label="${esc(T('Biblioteca'))}">${opts(toneLibrary, 'l:')}</optgroup>` : ''}
      <option value="__coll__">${T('Dos teus PSARC…')}</option></select>`;
}

function toneSwapsHtml(tracks) {
  const rows = suggestedTones(tracks).map(s =>
    `<div class="ts-swap-row"><b>${esc(s.name || s.key)}</b>${toneSwapSelect(s.key, s.name || s.key)}</div>`).join('');
  return `<div class="ts-swaps"><div class="ts-swaps-intro">${T('Trocar os tons sugeridos — as trocas ficam nos mesmos pontos, com os tons que escolheres:')}</div><div class="ts-swap-grid">${rows}</div></div>`;
}

function wireToneSwaps(body) {
  body.querySelectorAll('.ts-swap').forEach(sel => {
    const key = sel.dataset.key;
    const sw = toneSwaps[key];
    if (sw && sw.source === 'project') sel.value = `p:${sw.tone.key}`;
    else if (sw && sw.source === 'library') sel.value = `l:${sw.tone.key}`;
    else sel.value = '';
    if (sw && !sel.value) sel.value = 'c:';  // its own option (a PSARC tone, or one no longer listed)
    sel.addEventListener('change', () => {
      const v = sel.value;
      if (v === '__coll__') {
        const label = sel.dataset.label;
        openToneCollection({
          label,
          onPick: (tone, row) => {
            toneSwaps[key] = { tone, source: 'collection', label: `${tone.name || tone.key} · ${row.song || ''}${row.artist ? ' — ' + row.artist : ''}` };
            saveToneSwaps();
          },
          onClose: renderToneSuggestions,
        });
        return;
      }
      if (v === 'c:') return;  // re-picking what is already chosen
      if (!v) delete toneSwaps[key];
      else if (v.startsWith('p:')) toneSwaps[key] = { tone: jobTones.find(t => t.key === v.slice(2)), source: 'project' };
      else if (v.startsWith('l:')) toneSwaps[key] = { tone: toneLibrary.find(t => t.key === v.slice(2)), source: 'library' };
      if (toneSwaps[key] && !toneSwaps[key].tone) delete toneSwaps[key];
      saveToneSwaps();
      renderToneSuggestions();
    });
  });
}

async function loadToneSuggestions(id) {
  toneSuggestions = null;
  if (toneSwapsJob !== id) { toneSwaps = {}; toneSwapsJob = id; }
  loadToneLibrary().then(() => { if (toneSuggestions) renderToneSuggestions(); });
  const card = document.getElementById('toneSuggestCard');
  if (!selectedJob || !isGpJob() || selectedJob.status !== 'completed') { card.hidden = true; return; }
  card.hidden = false;
  try {
    const r = await fetch(`/jobs/${id}/tone-suggestions`);
    if (selectedJob && selectedJob.id !== id) return;
    toneSuggestions = r.ok ? await r.json() : { error: r.status };
    if (toneSuggestions.swaps) toneSwaps = toneSuggestions.swaps;
  } catch {
    toneSuggestions = { error: 0 };
  }
  renderToneSuggestions();
}

function renderToneSuggestions() {
  const body = document.getElementById('toneSuggestBody');
  if (!body) return;
  const d = toneSuggestions;
  const top = document.getElementById('toneSuggestApplyAll');
  top.hidden = !(d && d.tracks && d.tracks.length);
  if (!d) { body.innerHTML = `<span class="tn-empty">${T('a carregar…')}</span>`; return; }
  if (d.error) {
    body.innerHTML = d.error === 409
      ? `<span class="tn-empty">${T('Clica em "Detetar tom": além do tom geral, mede o som da guitarra ao longo da música, e aqui aparece uma sugestão de tom para cada parte de cada pista.')}</span>`
      : `<span class="tn-empty" style="color:#e88">${T('Não foi possível calcular as sugestões.')}</span>`;
    return;
  }
  body.innerHTML = toneSwapsHtml(d.tracks) + d.tracks.map((t, ti) => toneTrackHtml(t, ti, d.timeline || [])).join('');
  wireToneSwaps(body);
  body.querySelectorAll('.ts-apply').forEach(btn => btn.addEventListener('click', e => {
    e.preventDefault();  // inside the <summary>: do not also fold the track
    applyToneSuggestion([d.tracks[parseInt(btn.dataset.i, 10)]]);
  }));
  body.querySelectorAll('details.ts-track').forEach(el => el.addEventListener('toggle', () => {
    toneTrackOpen[el.dataset.kind] = el.open;
  }));
  body.querySelectorAll('.ts-seg[data-t]').forEach(el => el.addEventListener('click', () => {
    audioSeek(Math.max(0, parseFloat(el.dataset.t) - viewOrigin));
  }));
}

function toneTrackHtml(t, ti, timeline) {
  const segs = t.segments || [];
  const t0 = segs.length ? segs[0].start : 0;
  const t1 = segs.length ? segs[segs.length - 1].end : 1;
  const span = Math.max(0.001, t1 - t0);
  const pct = x => ((x - t0) / span * 100).toFixed(3);
  // The recording's distortion over the same stretch, one bar per window.
  const inRange = timeline.filter(w => w[0] >= t0 && w[0] < t1);
  const bw = inRange.length ? Math.max(0.15, 100 / span * 0.9) : 0;
  // Scaled to the song's loudest-distortion window, so the rise and fall shows.
  const top = Math.max(0.3, ...timeline.map(w => Number(w[1]) || 0));
  const bars = inRange.map(w => {
    const h = Math.max(1, Math.round((Number(w[1]) || 0) / top * 28));
    return `<rect x="${pct(w[0])}" y="${30 - h}" width="${bw.toFixed(3)}" height="${h}" fill="${w[2] ? '#c85bff' : '#3a3d48'}"/>`;
  }).join('');
  const strip = segs.map(g => {
    const role = TONE_ROLE[g.role] || TONE_ROLE.silent;
    const w = ((g.end - g.start) / span * 100).toFixed(3);
    const tip = `${g.name} · ${fmtClock(g.start - viewOrigin)}–${fmtClock(g.end - viewOrigin)} · ${role.label}${g.tone_name ? ' · ' + g.tone_name : ''}`;
    return `<div class="ts-seg" data-t="${g.start}" style="width:${w}%;background:${role.color}" title="${esc(tip)}"><span>${esc(g.name)}</span></div>`;
  }).join('');
  const rows = toneRuns(segs).map(run => {
    const g = run[0], last = run[run.length - 1];
    const role = TONE_ROLE[g.role] || TONE_ROLE.silent;
    const name = run.length > 1 ? `${g.name}–${last.name}` : g.name;
    const when = `${fmtClock(g.start - viewOrigin)}–${fmtClock(last.end - viewOrigin)}`;
    const roleCell = `<span class="ts-role"><span class="ts-dot" style="background:${role.color}"></span>${role.label}</span>`;
    if (g.role === 'silent') {
      return `<div class="ts-row" role="row"><div class="ts-cols"><span class="ts-part" role="cell">${esc(name)}</span>` +
        `<span class="ts-when" role="cell">${when}</span><span role="cell">${roleCell}</span>` +
        `<span class="ts-tone" role="cell">—</span><span role="cell"></span></div>` +
        `<div class="ts-why">${T('não toca — mantém o tom anterior')}</div></div>`;
    }
    const matches = run.map(x => Math.round(x.match));
    const lo = Math.min(...matches), hi = Math.max(...matches);
    const conf = ['low', 'medium', 'high'].find(c => run.some(x => x.confidence === c)) || 'low';
    const why = runReasons(run).map(toneReasonText).join(' · ');
    // the suggested tone can be swapped right here: the same choice as above the tracks
    const suggested = g.tone_name || g.tone_key;
    return `<div class="ts-row" role="row"><div class="ts-cols"><span class="ts-part" role="cell">${esc(name)}</span>` +
      `<span class="ts-when" role="cell">${when}</span><span role="cell">${roleCell}</span>` +
      `<span class="ts-tone" role="cell">${toneSwapSelect(g.tone_key, suggested)}</span>` +
      `<span class="ts-match" role="cell">${lo === hi ? lo : `${lo}–${hi}`}%<span class="meta">${TONE_CONFIDENCE[conf]}</span></span></div>` +
      (why ? `<div class="ts-why">${T('porquê:')} ${esc(why)}</div>` : '') + '</div>';
  }).join('');
  const switches = (t.changes || []).length;
  const open = t.kind in toneTrackOpen ? toneTrackOpen[t.kind] : ti === 0;
  const legend = Object.values(TONE_ROLE).map(r => `<span><i style="background:${r.color}"></i>${r.label}</span>`).join('') +
    `<span><i style="background:#c85bff"></i>${T('Distorção da gravação')}</span>`;
  return `<details class="ts-track" data-kind="${esc(t.kind)}"${open ? ' open' : ''}>
    <summary>${icon('chev-down')}<span class="ts-track-name">${esc(arrLabel(t.kind))}</span>
      <span class="ts-track-meta">${T('{n} tom(ns), {m} troca(s)', { n: (t.names || []).length, m: switches })}</span>
      <button type="button" class="secondary tn-btn tn-push ts-apply" data-i="${ti}">${T('Aplicar a esta pista')}</button></summary>
    <div class="ts-body">
      <div>
        <svg class="ts-gain" viewBox="0 0 100 30" preserveAspectRatio="none" aria-label="${T('Distorção ao longo da música')}">${bars}</svg>
        <div class="ts-strip">${strip}</div>
      </div>
      <div class="ts-legend">${legend}</div>
      <div class="ts-table" role="table" aria-label="${T('Tom sugerido por parte')}">
        <div class="ts-cols ts-thead" role="row"><span role="columnheader">${T('Parte')}</span><span role="columnheader">${T('Quando')}</span>` +
        `<span role="columnheader">${T('Papel')}</span><span role="columnheader">${T('Tom sugerido')}</span><span role="columnheader">${T('Acerto')}</span></div>
        ${rows}
      </div>
    </div>
  </details>`;
}

// Consecutive parts with the same role and tone read as one line (the strip
// above still shows each part); the weakest confidence of the run is the one said.
function toneRuns(segs) {
  const runs = [];
  for (const g of segs) {
    const prev = runs.length ? runs[runs.length - 1][0] : null;
    if (prev && prev.role === g.role && prev.tone_key === g.tone_key) runs[runs.length - 1].push(g);
    else runs.push([g]);
  }
  return runs;
}
// A run's reasons: each code's value averaged over the parts that gave it.
function runReasons(run) {
  const acc = new Map();
  for (const g of run) for (const r of g.reasons || []) {
    const e = acc.get(r.code) || { code: r.code, sum: 0, n: 0 };
    e.sum += Number(r.value) || 0; e.n += 1; acc.set(r.code, e);
  }
  return [...acc.values()].map(e => ({ code: e.code, value: e.sum / e.n }));
}

// Bring a plan's tones into the project and make them the track's own set.
// With one chart the song-level set IS that chart's, so nothing goes per-track.
// A stand-in from the library or a PSARC is copied into the project (once; a
// different tone under the same key gets a suffixed copy). Returns its key.
function swapToneKey(sw) {
  if (sw.source === 'project' && jobTones.some(t => t.key === sw.tone.key)) return sw.tone.key;
  const same = jobTones.find(t => t.key === sw.tone.key);
  if (same && JSON.stringify(same) === JSON.stringify(sw.tone)) return same.key;
  const tone = JSON.parse(JSON.stringify(sw.tone));
  let n = 1;
  const base = tone.key;
  while (jobTones.some(t => t.key === tone.key)) tone.key = `${base}_${++n}`;
  jobTones.push(tone);
  sw.tone = tone;
  sw.source = 'project';
  return tone.key;
}
function applyToneSuggestion(plans) {
  const keyMap = {};
  for (const [key, sw] of Object.entries(toneSwaps)) keyMap[key] = swapToneKey(sw);
  if (Object.keys(keyMap).length) saveToneSwaps();  // they now point at the project's copies
  for (const p of plans) {
    for (const tone of p.tones || []) {
      if (!keyMap[tone.key] && !jobTones.some(t => t.key === tone.key)) jobTones.push(tone);
    }
  }
  const setOf = p => cleanToneSet(swapPlan(p, keyMap));
  if (arrangements.length <= 1) {
    toneSetToGlobals(setOf(plans[0]));
  } else {
    setTonesPerTrack(true);
    stashToneSet();
    for (const p of plans) toneSetByKind[p.kind] = setOf(p);
    toneSetKind = null;
    toneSetToGlobals(songToneSet);
    switchToneSet();
  }
  renderTonePanel();
  if (arrangements.length) showArr(currentArr);
  toast(plans.length > 1
    ? T('Tons sugeridos aplicados a todas as pistas — "Aplicar e reconstruir" para gravar.')
    : T('Tons sugeridos aplicados a {track} — "Aplicar e reconstruir" para gravar.', { track: arrLabel(plans[0].kind) }), 'ok');
}

document.getElementById('toneSuggestApplyAll').addEventListener('click', () => {
  if (toneSuggestions && toneSuggestions.tracks) applyToneSuggestion(toneSuggestions.tracks);
});

// ── Stem separation (selectable audio source for fine-tuning) ─────────────────

const STEM_LABELS = {
  guitar: T('Guitarra'), bass: T('Baixo'),
  vocals: T('Voz'), piano: T('Piano'), other: T('Outros'),
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
  let html = `<option value="">${T('Mistura completa')}</option>`;
  for (const a of arrangements) {
    const v = `synth:${a.kind}`;
    values.push(v);
    html += `<option value="${esc(v)}">${T('{track} (sintetizada)', { track: esc(arrLabel(a.kind)) })}</option>`;
  }
  if (vocalLine.notes.length) {
    const v = `synth:${VOICE_SOURCE}`;
    values.push(v);
    html += `<option value="${v}">${T('Voz (sintetizada)')}</option>`;
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
  if (!await fetchOrToast(`/jobs/${selectedJob.id}/separate-stems`, { method: 'POST' })) return;
  toast(T('A separar instrumentos… (pode demorar minutos)'), 'ok');
  document.getElementById('stemsStatus').textContent = T('a iniciar…');
  pollStems();
}

let _stemsPoll = null;
function pollStems() {
  clearInterval(_stemsPoll);
  _stemsPoll = pollJob('stems', d => {
    const st = document.getElementById('stemsStatus');
    if (d.status === 'ready') {
      availableStems = d.stems || [];
      populateAudioSources();
      loadAttackSources();
      st.textContent = T('{n} stems prontos (a guitarra é todas as guitarras juntas)', { n: availableStems.length });
      return true;
    }
    if (d.status === 'unavailable') {
      st.textContent = T('separação falhou — precisa do extra [ml] (Demucs).');
      st.style.color = '#e88';
      return true;
    }
    if (d.status && d.status !== 'none') {
      const label = { detecting: T('a iniciar'), normalizing: T('a normalizar áudio'),
        separating: T('a separar (Demucs)…') }[d.status] || d.status;
      st.textContent = label + '…';
    }
    return false;
  });
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
      document.getElementById('stemsStatus').textContent = T('separação em curso…');
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
    info.textContent = T('capa carregada — substitui o ficheiro para alterar.');
  } else {
    img.hidden = true;
    img.src = '';
    info.textContent = T('sem capa.');
  }
}

document.getElementById('coverArtFile').addEventListener('change', async ev => {
  if (!selectedJob) return;
  const file = ev.target.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  const b = await fetchOrToast(`/jobs/${selectedJob.id}/cover`, { method: 'POST', body: fd });
  if (!b) return;
  selectedJob.cover_art = b.cover_art;
  loadCoverArt(selectedJob);
  toast(T('Capa carregada — "Aplicar e reconstruir" para a incluir no bundle.'), 'ok');
  ev.target.value = '';
});

// ── Album, year and cover lookup (wizard step 4 + the Capa page) ──────────────
// /album-lookup asks iTunes and MusicBrainz/Cover Art Archive by title + band
// and returns candidates; the USER picks one — nothing is filled from a guess
// they cannot see. Each card shows the matched track and the source, so a
// wrong match (a cover version, a compilation) is visible before it is used.
const ALBUM_KIND = { album: T('álbum'), ep: 'EP', single: 'single', compilation: T('compilação') };
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
  const what = r.searched_title ? T('"{title}" de {artist}', { title: r.searched_title, artist: r.searched_artist }) : T('este título e banda');
  const down = (r.failures || []).length
    ? T(' (não consegui perguntar a {services}.)', { services: r.failures.map(f => f.split(':')[0]).join(', ') }) : '';
  return T('Nada encontrado para {what} no iTunes nem no MusicBrainz{down}. Remixes de fãs, versões e músicas feitas por IA não estão nestes catálogos — corrige o título/banda e procura de novo, ou carrega a capa à mão.',
    { what, down });
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
    card(-1, placeholder('x'), T('Sem capa'), [T('não usar nenhuma imagem')]);
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

// A card and an image from the computer are two answers to one question:
// choosing one drops the other (the server also lets the file win).
function clearWizardCoverFile() {
  const inp = document.getElementById('wzCoverFile');
  if (!inp.files.length) return;
  inp.value = '';
  inp.dispatchEvent(new Event('change'));
}
document.getElementById('wzCoverFile').addEventListener('change', ev => {
  if (!ev.target.files.length) return;
  wzAlbumPick = null;
  document.getElementById('wzCoverUrl').value = '';
  renderAlbumGrid(document.getElementById('wzAlbumResults'), wzAlbumCandidates, null,
    i => pickWizardAlbum(i), { withNone: true });
});

function pickWizardAlbum(idx, { fillEmptyOnly = false } = {}) {
  const form = document.getElementById('gpJobForm');
  clearWizardCoverFile();
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
  if (!title || !artist) { info.textContent = T('Preenche o título e a banda para procurar.'); return; }
  const btn = document.getElementById('wzAlbumSearch');
  btn.disabled = true;
  info.textContent = T('A procurar…');
  try {
    wzAlbumCandidates = await lookupAlbums(title, artist);
  } catch (err) {
    wzAlbumCandidates = [];
    info.textContent = T('Não consegui procurar agora ({msg}). Podes preencher à mão.', { msg: err.message });
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
  info.textContent = T('{n} resultado(s) — escolhe o álbum e a capa certos.', { n: wzAlbumCandidates.length });
  // Preselect the best guess but never overwrite what the user (or the GP
  // file) already typed; clicking a card is an explicit choice and does.
  // An image already chosen from the computer stays the cover.
  if (document.getElementById('wzCoverFile').files.length) {
    renderAlbumGrid(document.getElementById('wzAlbumResults'), wzAlbumCandidates, null,
      i => pickWizardAlbum(i), { withNone: true });
    return;
  }
  pickWizardAlbum(0, { fillEmptyOnly: true });
}
document.getElementById('wzAlbumSearch').addEventListener('click', searchWizardAlbum);

function maybeAutoAlbumSearch() {
  if (wzAlbumAutoDone) return;
  wzAlbumAutoDone = true;
  searchWizardAlbum();
}

// Wizard step 4: synced lyrics from LRCLIB, chosen BEFORE the project exists,
// so the first build already carries them. The chosen LRC text goes to
// /jobs/gp as ``lyrics_lrc`` — stored exactly like an uploaded LRC file (which
// still wins). The best synced result is preselected unless the GP file brings
// its own lyrics (an LRC would replace them) or an LRC file was chosen.
let wzLyricsCandidates = [];
let wzLyricsPick = -1;           // index into wzLyricsCandidates, -1 = none
let wzLyricsAutoDone = false;
let wzGpHasLyrics = false;       // set from /gp/inspect
// /pdf/import's estimated_bars (track index → bars whose rhythm the converter
// estimated), handed to /jobs/gp so the viewer can offer them for review.
let wzEstimatedBars = {};
let wzRecordingS = null;         // the chosen audio file's length, when known

function resetWizardLyrics() {
  wzLyricsCandidates = [];
  wzLyricsPick = -1;
  wzLyricsAutoDone = false;
  wzRecordingS = null;
  document.getElementById('wzLyricsResults').replaceChildren();
  document.getElementById('wzLyricsInfo').textContent = '';
  document.getElementById('wzLyricsLrc').value = '';
}

function wizardLrcFileChosen() {
  const f = document.querySelector('#gpJobForm input[name=lrc]');
  return !!(f && f.files && f.files.length);
}

function renderWizardLyrics() {
  const el = document.getElementById('wzLyricsResults');
  el.replaceChildren();
  wzLyricsCandidates.forEach((c, i) => {
    const card = document.createElement('div');
    card.className = 'lyr-card' + (i === wzLyricsPick ? ' picked' : '');
    const acts = document.createElement('div');
    acts.className = 'lyr-acts';
    if (c.synced) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = i === wzLyricsPick ? '' : 'secondary';
      b.textContent = i === wzLyricsPick ? T('Escolhida ✓') : T('Usar');
      b.addEventListener('click', () => pickWizardLyrics(i === wzLyricsPick ? -1 : i));
      acts.append(b);
    } else {
      const note = document.createElement('span');
      note.className = 'meta';
      note.textContent = c.plain ? T('sem tempos — sincroniza-a depois na página Letra') : '';
      acts.append(note);
    }
    card.append(lyricsCardBody(c, wzRecordingS), acts);
    el.append(card);
  });
}

function pickWizardLyrics(idx) {
  const c = wzLyricsCandidates[idx];
  wzLyricsPick = c && c.synced ? idx : -1;
  document.getElementById('wzLyricsLrc').value = wzLyricsPick >= 0 ? c.synced : '';
  const info = document.getElementById('wzLyricsInfo');
  if (wzLyricsPick < 0) info.textContent = T('Sem letra do LRCLIB — podes procurá-la depois na página Letra.');
  else if (wizardLrcFileChosen()) info.textContent = T('Escolheste também um ficheiro LRC: é esse que vai ser usado.');
  else info.textContent = T('Vai ser usada a letra de "{track}" ({album}). Os tempos são os da gravação original: ajusta-os depois na página Letra se a tua versão tiver outra introdução.',
    { track: c.track, album: c.album || 'LRCLIB' });
  renderWizardLyrics();
}

// Length of an audio file picked in step 3, read by the browser itself.
function audioFileDuration(file) {
  return new Promise(resolve => {
    if (!file) { resolve(null); return; }
    const url = URL.createObjectURL(file);
    const el = new Audio();
    const done = v => { URL.revokeObjectURL(url); resolve(v); };
    el.preload = 'metadata';
    el.onloadedmetadata = () => done(Number.isFinite(el.duration) ? el.duration : null);
    el.onerror = () => done(null);
    setTimeout(() => done(null), 4000);
    el.src = url;
  });
}

async function searchWizardLyrics() {
  const form = document.getElementById('gpJobForm');
  const title = form.querySelector('input[name=title]').value.trim();
  const artist = form.querySelector('input[name=artist]').value.trim();
  const info = document.getElementById('wzLyricsInfo');
  if (!title || !artist) { info.textContent = T('Preenche o título e a banda para procurar.'); return; }
  const btn = document.getElementById('wzLyricsSearch');
  btn.disabled = true;
  info.textContent = T('A procurar…');
  const audio = form.querySelector('input[name=audio]');
  try {
    // Inside the try: a recording the browser cannot read must not leave the
    // button disabled for good (the finally re-enables it).
    wzRecordingS = await audioFileDuration(audio && audio.files && audio.files[0]);
    const q = `title=${encodeURIComponent(title)}&artist=${encodeURIComponent(artist)}`
      + (wzRecordingS ? `&duration=${wzRecordingS.toFixed(1)}` : '');
    const r = await getJSON(`/lyrics-lookup?${q}`);
    wzLyricsCandidates = r.candidates || [];
    if (!wzLyricsCandidates.length) {
      pickWizardLyrics(-1);
      info.textContent = T('Nada encontrado no LRCLIB para "{title}" de {artist}. Podes carregar um LRC abaixo, ou tratar da letra depois de criar.',
        { title: r.searched_title, artist: r.searched_artist });
      return;
    }
  } catch (err) {
    wzLyricsCandidates = [];
    info.textContent = T('Não consegui procurar agora ({msg}). Podes tratar da letra depois de criar.', { msg: err.message });
    renderWizardLyrics();
    return;
  } finally {
    btn.disabled = false;
  }
  const best = wzLyricsCandidates.findIndex(c => c.synced);
  if (best >= 0 && !wzGpHasLyrics && !wizardLrcFileChosen()) {
    pickWizardLyrics(best);
  } else {
    wzLyricsPick = -1;
    document.getElementById('wzLyricsLrc').value = '';
    info.textContent = T('{n} resultado(s) no LRCLIB.', { n: wzLyricsCandidates.length }) + ' '
      + (wzGpHasLyrics ? T('A pauta já traz letra — escolhe uma daqui só se a quiseres substituir por esta, com tempos.')
        : best < 0 ? T('Nenhuma tem tempos — sincroniza-a depois na página Letra.') : T('Escolhe a versão da tua gravação.'));
    renderWizardLyrics();
  }
}
document.getElementById('wzLyricsSearch').addEventListener('click', searchWizardLyrics);
document.querySelector('#gpJobForm input[name=lrc]').addEventListener('change', () => {
  if (wzLyricsPick >= 0) pickWizardLyrics(wzLyricsPick);  // refresh which one will be used
});

function maybeAutoLyricsSearch() {
  if (wzLyricsAutoDone) return;
  wzLyricsAutoDone = true;
  searchWizardLyrics();
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
      info.textContent = T('A descarregar a capa…');
      const b = await getJSON(`/jobs/${selectedJob.id}/cover-from-url`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: c.cover_url }),
      });
      selectedJob.cover_art = b.cover_art;
      loadCoverArt(selectedJob);
      done.push(T('capa'));
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
      done.push(T('álbum e ano'));
    }
  } catch (err) {
    info.textContent = T('Não foi possível: {msg}', { msg: err.message });
    toast(T('Não foi possível aplicar: {msg}', { msg: err.message }));
    return;
  }
  info.textContent = done.length ? T('Aplicado: {what}.', { what: done.join(' + ') }) : T('Esse resultado não tem capa.');
  if (done.length) toast(T('Aplicado — "Aplicar e reconstruir" para o incluir no bundle.'), 'ok');
}

document.getElementById('capaSearch').addEventListener('click', async () => {
  if (!selectedJob) return;
  const info = document.getElementById('capaSearchInfo');
  const grid = document.getElementById('capaResults');
  const btn = document.getElementById('capaSearch');
  btn.disabled = true;
  info.textContent = T('A procurar…');
  try {
    capaCandidates = await lookupAlbums(selectedJob.title || '', selectedJob.artist || '');
  } catch (err) {
    capaCandidates = [];
    grid.replaceChildren();
    info.textContent = T('Não consegui procurar agora ({msg}).', { msg: err.message });
    return;
  } finally {
    btn.disabled = false;
  }
  info.textContent = capaCandidates.length
    ? T('{n} resultado(s) — clica no certo para o aplicar.', { n: capaCandidates.length })
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
  if (!lyricsEvents.length) { toast(T('Sem letras para exportar.')); return; }
  const sorted = [...lyricsEvents].sort((a, b) => a.time - b.time);
  let lines = [];
  let currentLine = [];
  for (const e of sorted) {
    const word = e.lyric.trim();
    if (!word) continue;
    if (!currentLine.length) currentLine = [e];
    else currentLine.push(e);
    if (e.lineBreak) {
      const text = currentLine.map(w => w.lyric.trim()).join(' ');
      lines.push(`${lrcTag(currentLine[0].time)}${text}`);
      currentLine = [];
    }
  }
  if (currentLine.length) {
    const text = currentLine.map(w => w.lyric.trim()).join(' ');
    lines.push(`${lrcTag(currentLine[0].time)}${text}`);
  }
  const lrc = lines.join('\n') + '\n';
  const blob = new Blob([lrc], { type: 'text/plain' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  const title = selectedJob ? (selectedJob.title || 'lyrics') : 'lyrics';
  a.download = `${title}.lrc`;
  a.click();
  URL.revokeObjectURL(a.href);
  toast(T('LRC exportado.'), 'ok');
});

function updatePendingChangesInfo() {
  const el = document.getElementById('pendingChangesInfo');
  if (!el) return;
  const parts = [];
  const builtOffset = selectedJob ? (selectedJob.offset_s || 0) : 0;
  if (Math.abs(offsetLive - builtOffset) > 0.01) parts.push(T('offset'));
  if (Math.abs(tempoScaleLive - builtScale) > 0.001) parts.push(T('andamento'));
  if (Math.abs(centOffsetLive - centOffsetBuilt) > 0.05) parts.push(T('desvio da afinação'));
  if (syncAnchors.length) parts.push(T('{n} ponto(s) de correção', { n: syncAnchors.length }));
  if (JSON.stringify(noteOverridesByKind) !== noteOverridesBuilt) parts.push(T('edições de notas'));
  if (JSON.stringify(fhpByKind) !== fhpBuilt) parts.push(T('posições da mão'));
  if (JSON.stringify(serializeLyrics()) !== lyricsBuilt) parts.push(T('letra'));
  el.textContent = parts.length ? T('Pendente: {changes}', { changes: parts.join(', ') }) : '';
  notePendingChange();
}

// ── Undo / redo of the pending edits ─────────────────────────────────────────
// One snapshot holds everything "Aplicar e reconstruir" would send — every
// chart's tempo and corrections, the note edits, the lyric rows, the sections,
// the tones, the build options — as plain data. An edit anywhere ends up
// calling notePendingChange (updatePendingChangesInfo, showArr and the tone,
// section and lyric panels' render do); 400 ms after the last one the state is
// compared with the newest snapshot and, when it differs, becomes a new step.
// Undo/redo restore a whole snapshot, so a step is whatever the user did
// between two pauses — a drag, a tempo change, a word typed — on any page.
const HIST_MAX = 100;
let pendingHist = [];        // JSON snapshots, oldest first
let pendingHistAt = -1;      // the one on screen
let pendingHistJob = null;   // the project version they belong to
let pendingTimer = null;
let restoringPending = false;
let pendingBase = null;      // the version as built: what a draft is compared with

function pendingSnapshot() {
  stashToneSet();  // the chart on screen's tone set back in its place
  const tempo = {};
  for (const a of arrangements) {
    const live = a.kind === currentKind() ? tempoScaleLive : tempoScaleByKind[a.kind];
    if (live != null && Math.abs(live - (a.tempo_scale || 1)) > 1e-4) tempo[a.kind] = live;
  }
  const anchors = {};
  for (const [kind, list] of Object.entries(syncAnchorsByKind)) {
    if (list.length) anchors[kind] = list.map(pt => pt.slice());
  }
  return {
    offset: offsetLive,
    cents: centOffsetLive,
    leadIn: document.getElementById('leadInS').value,
    mutes: document.getElementById('muteChk').checked,
    dd: document.getElementById('ddChk').checked,
    tempo, anchors,
    notes: JSON.parse(JSON.stringify(noteOverridesByKind)),
    fhp: JSON.parse(JSON.stringify(fhpByKind)),
    lyrics: lyricsEvents.map(r => ({ time: r.time, length: r.length, lyric: r.lyric, lineBreak: !!r.lineBreak })),
    lyricsBackToScore, lyricsFollowChart,
    sections: songSections.map(x => ({ time: x.time, name: x.name })),
    sectionsTouched,
    tones: JSON.parse(JSON.stringify({ jobTones, songToneSet, toneSetByKind, tonesPerTrack })),
  };
}

function restorePending(snap) {
  tapState = null;  // an undo while marking ends the marking
  renderTapUi();
  restoringPending = true;
  try {
    offsetLive = snap.offset;
    setCentOffsetLive(snap.cents);
    document.getElementById('leadInS').value = snap.leadIn;
    document.getElementById('muteChk').checked = snap.mutes;
    document.getElementById('ddChk').checked = snap.dd;
    tempoScaleByKind = { ...snap.tempo };
    syncAnchorsByKind = {};
    for (const [kind, list] of Object.entries(snap.anchors)) syncAnchorsByKind[kind] = list.map(pt => pt.slice());
    const a = arrangements[currentArr];
    if (a) {
      tempoScaleLive = (a.kind in tempoScaleByKind) ? tempoScaleByKind[a.kind] : builtScale;
      syncAnchors = syncAnchorsByKind[a.kind] || (syncAnchorsByKind[a.kind] = []);
      updateTempoControls();
    }
    noteOverridesByKind = JSON.parse(JSON.stringify(snap.notes));
    noteDeleteUndo = null;  // its record describes a state that is no longer on screen
    fhpByKind = JSON.parse(JSON.stringify(snap.fhp || {}));
    closeFhpPopup();
    lyricsEvents = snap.lyrics.map(r => ({ ...r }));
    lyricSelected = null;
    lyricsBackToScore = snap.lyricsBackToScore;
    setLyricsFollowChart(snap.lyricsFollowChart);
    songSections = snap.sections.map(x => ({ ...x }));
    sectionsTouched = snap.sectionsTouched;
    const t = JSON.parse(JSON.stringify(snap.tones));
    jobTones = t.jobTones; songToneSet = t.songToneSet; toneSetByKind = t.toneSetByKind;
    tonesPerTrack = t.tonesPerTrack;
    toneSetKind = null;
    toneSetToGlobals(songToneSet);
    switchToneSet();
    // The rows and the other charts already carry what the snapshot's sync
    // did to them: nothing may carry them again.
    resetMainFollow();
    resetLyricFollow();
    renderTonePanel();
    renderSectionsList();
    renderLyricsRows();
    renderAnchorsList();
    if (arrangements.length) showArr(currentArr);
    updatePendingChangesInfo();
  } finally {
    restoringPending = false;
  }
}

function notePendingChange() {
  if (restoringPending || !selectedJob || pendingHistJob !== selectedJob.id) return;
  clearTimeout(pendingTimer);
  pendingTimer = setTimeout(recordPending, 400);
}

function recordPending() {
  clearTimeout(pendingTimer);
  pendingTimer = null;
  if (restoringPending || !selectedJob || pendingHistJob !== selectedJob.id) return;
  if (tapState) return;  // a run of taps is recorded once, when it ends
  const snap = JSON.stringify(pendingSnapshot());
  if (snap === pendingHist[pendingHistAt]) return;
  pendingHist = pendingHist.slice(0, pendingHistAt + 1);
  pendingHist.push(snap);
  if (pendingHist.length > HIST_MAX) pendingHist.shift();
  pendingHistAt = pendingHist.length - 1;
  updateUndoButtons();
  saveDraft();
}

// ── Autosave: the pending edits survive closing the app ──────────────────────
// The snapshot on screen is kept in localStorage per project VERSION (a rebuild
// is a new version, built with them), so closing the tab, the app or the
// machine before "Aplicar e reconstruir" does not lose an afternoon of
// corrections. Reopening that version offers them back. Only this browser
// keeps them; nothing reaches the server until the rebuild.
const DRAFT_PREFIX = 'rf-draft:';
const DRAFT_MAX = 20;
function saveDraft() {
  if (!pendingHistJob || pendingHistAt < 0) return;
  const key = DRAFT_PREFIX + pendingHistJob;
  const snap = pendingHist[pendingHistAt];
  try {
    if (snap === pendingBase) { localStorage.removeItem(key); return; }
    localStorage.setItem(key, JSON.stringify({ t: Date.now(), snap }));
    pruneDrafts();
  } catch { /* no storage, or full: the edits simply are not kept */ }
}
function dropDraft(jobId) {
  try { localStorage.removeItem(DRAFT_PREFIX + jobId); } catch { /* no storage */ }
}
function pruneDrafts() {
  const drafts = [];
  for (let k = 0; k < localStorage.length; k++) {
    const key = localStorage.key(k);
    if (!key || !key.startsWith(DRAFT_PREFIX)) continue;
    let t = 0;
    try { t = JSON.parse(localStorage.getItem(key)).t || 0; } catch { /* unreadable: oldest */ }
    drafts.push([t, key]);
  }
  drafts.sort((a, b) => b[0] - a[0]);
  for (const [, key] of drafts.slice(DRAFT_MAX)) localStorage.removeItem(key);
}
async function offerDraft(jobId) {
  let draft = null;
  try { draft = JSON.parse(localStorage.getItem(DRAFT_PREFIX + jobId) || 'null'); } catch { /* unreadable */ }
  if (!draft || !draft.snap || draft.snap === pendingBase) return;
  const when = new Date(draft.t || Date.now()).toLocaleString(document.documentElement.lang || undefined);
  const yes = await confirmModal(T('Este projeto tem alterações por aplicar, guardadas automaticamente em {when}. Recuperá-las?', { when }));
  if (!selectedJob || selectedJob.id !== jobId || pendingHistJob !== jobId) return;
  if (!yes) { dropDraft(jobId); return; }
  try {
    restorePending(JSON.parse(draft.snap));
  } catch {
    toast(T('Não foi possível recuperar as alterações guardadas.'));
    dropDraft(jobId);
    return;
  }
  recordPending();  // a step of its own: undo goes back to the version as built
  toast(T('Alterações recuperadas — "Aplicar e reconstruir" para as guardar no projeto.'), 'ok');
}

// Called once a project version's charts, lyrics and tones are all loaded:
// what is on screen then is the first step, the one undo stops at.
function startPendingHistory() {
  clearTimeout(pendingTimer);
  pendingTimer = null;
  pendingHistJob = selectedJob ? selectedJob.id : null;
  pendingHist = pendingHistJob ? [JSON.stringify(pendingSnapshot())] : [];
  pendingHistAt = pendingHist.length - 1;
  pendingBase = pendingHist[0] || null;
  updateUndoButtons();
  if (pendingHistJob) offerDraft(pendingHistJob);
}
function stopPendingHistory() {
  clearTimeout(pendingTimer);
  pendingTimer = null;
  pendingHistJob = null;
  pendingHist = [];
  pendingHistAt = -1;
  pendingBase = null;
  updateUndoButtons();
}

function undoPending() {
  if (pendingTimer) recordPending();  // an edit not yet recorded is the step to undo
  if (pendingHistAt <= 0) return;
  pendingHistAt--;
  restorePending(JSON.parse(pendingHist[pendingHistAt]));
  updateUndoButtons();
  saveDraft();
}
function redoPending() {
  if (pendingTimer) recordPending();
  if (pendingHistAt >= pendingHist.length - 1) return;
  pendingHistAt++;
  restorePending(JSON.parse(pendingHist[pendingHistAt]));
  updateUndoButtons();
  saveDraft();
}
function updateUndoButtons() {
  const u = document.getElementById('undoBtn'), r = document.getElementById('redoBtn');
  if (u) u.disabled = pendingHistAt <= 0;
  if (r) r.disabled = pendingHistAt < 0 || pendingHistAt >= pendingHist.length - 1;
}
document.getElementById('undoBtn').addEventListener('click', undoPending);
document.getElementById('redoBtn').addEventListener('click', redoPending);
for (const id of ['leadInS', 'muteChk', 'ddChk'])
  document.getElementById(id).addEventListener('change', notePendingChange);
// Ctrl+Z / Ctrl+Shift+Z (or Ctrl+Y) on every page of an open project. Inside a
// text field they stay the field's own undo; a dialog on top keeps them too.
document.addEventListener('keydown', e => {
  if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
  const key = e.key.toLowerCase();
  if (key !== 'z' && key !== 'y') return;
  const el = document.activeElement;
  const tag = el && el.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (el && el.isContentEditable)) return;
  if (!selectedJob || document.getElementById('detailOverlay').hidden) return;
  if (document.querySelector('.modal-overlay:not([hidden]), .settings-view:not([hidden])')) return;
  e.preventDefault();
  if (key === 'y' || e.shiftKey) redoPending(); else undoPending();
});

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
  firstNoteStatus(T('1) Clica na forma de onda onde COMEÇA o som da 1ª nota (clica de novo para ajustar).'));
}
function cancelFirstNoteFlow() {
  firstNoteFlow = null;
  firstNoteStatus(T('Deteção cancelada.'));
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
    shiftTrackStart(origT, firstNoteAudioT + viewOrigin);
    renderAnchorsList();
    updatePendingChangesInfo();
    firstNoteStatus(T('Início desta pista fixado em {s}s — "Aplicar e reconstruir" para gravar.', { s: firstNoteAudioT.toFixed(2) }));
    toast(T('Início atualizado'), 'ok');
    showArr(currentArr);
    return true;
  }
  // 2nd click (or re-adjust): the point on the waveform where the note sounds.
  const rect = svg.getBoundingClientRect();
  firstNoteAudioT = Math.max(0, (e.clientX - rect.left - 30) / tabPx);
  audioSeek(firstNoteAudioT);  // move the playhead there to confirm by ear
  firstNoteFlow = 'note';
  firstNoteStatus(T('2) Som marcado em {s}s — clica na 1ª NOTA para a alinhar aí (ou clica noutro ponto para ajustar).', { s: firstNoteAudioT.toFixed(2) }));
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
  if (dispLast <= dispT + 0.01) { toast(T('é a última nota — nada para re-espaçar'), 'err'); return; }
  const fromS = Math.max(0, dispT - viewOrigin);  // click's time in the recording
  // The chart's tempo as it plays RIGHT NOW at the click (authored spacing ×
  // tempo_scale × pending anchors). The factor is applied below as a relative
  // stretch of this timeline's tail, so this — not the GP header tempo — is what
  // it has to be measured against; it also centres the detector's tempo prior,
  // which otherwise defaults to 120 and reads a slow song at double time.
  const info = liveInfoAtTime(dispT, warp);
  const chartBpm = info && info.bpm ? info.bpm : null;
  toast(T('A detetar andamento…'), 'ok');
  try {
    const r = await fetch(`/jobs/${selectedJob.id}/detect-tempo`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from_s: fromS, chart_bpm: chartBpm }),
    });
    const b = await r.json();
    if (!r.ok) { toast(b.detail || T('erro'), 'err'); return; }
    const factor = b.suggested_factor;
    setAnchor(origT, dispT);                                     // fixed pivot at the click
    setAnchor(origLast, dispT + (dispLast - dispT) * factor);   // stretch the tail to the local BPM
    renderAnchorsList();
    updatePendingChangesInfo();
    showArr(currentArr);
    const ref = b.reference_bpm ? ' ' + T('(partitura {bpm})', { bpm: b.reference_bpm.toFixed(1) }) : '';
    toast(T('Andamento: {bpm} BPM{ref} → ×{factor}', { bpm: b.detected_bpm.toFixed(1), ref, factor: factor.toFixed(3) }), 'ok');
  } catch { toast(T('falha na deteção'), 'err'); }
}

function updateSelectionInfo() {
  const info = document.getElementById('selectionInfo');
  const clearBtn = document.getElementById('clearSelection');
  const n = selectedTimes.size;
  info.textContent = n ? T('{n} nota(s) selecionada(s) — arrasta uma para mover todas em bloco', { n }) : '';
  clearBtn.hidden = n === 0;
  const copyBtn = document.getElementById('copyNotes');
  if (copyBtn) copyBtn.disabled = n === 0;
  updateDeleteNotesUi();
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
    // Align-by-bar on the bar line itself: the bar's start, with or without a
    // note there. Anywhere else on empty staff still seeks, as in every mode.
    const barHit = !grp && e.target.closest('.bar-hit');
    if (syncMode === 'baralign' && barHit) {
      openBarAlignPopup(parseFloat(barHit.dataset.t), e.clientX, e.clientY);
      return;
    }
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
        toast(T('é a última nota — usa "Arrastar nota"'), 'err');
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
    // Fret-hand position: click a note to start one there (or edit the one that
    // starts there), or the FHP band under the staff to edit that one.
    const fhpBar = !grp && e.target.closest('.fhp-bar');
    if (syncMode === 'fhp' && (grp || fhpBar)) {
      if (fhpBar) openFhpPopup(0, e.clientX, e.clientY, parseInt(fhpBar.dataset.k, 10));
      else openFhpPopup(parseFloat(grp.dataset.t), e.clientX, e.clientY);
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
      const word = lyricsEvents[lyricDrag.index];
      if (Math.abs(deltaS) > 0.005) word.time = Math.max(0, word.time + deltaS);
      // A click (or a drag) on a word opens its tools beside the score.
      lyricSelected = word;
      showInspector('lyrics');
      renderLyricsRows();
      showArr(currentArr);
      updatePendingChangesInfo();
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
    const arrNow = arrangements[currentArr];
    const string = Math.min(stringCount(arrNow) - 1,
      Math.max(0, Math.round((STAFF_SB - clickY) / staffRow(arrNow))));
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
  ['modeFhp', 'fhp'],
];
// The key that picks mode i: 1…9, then 0 for the tenth.
const modeKey = i => (i === 9 ? '0' : String(i + 1));
const MODE_HELP = {
  drag: T('<b>Arrastar:</b> arrasta uma nota para o instante da gravação onde ela deve tocar (encaixa no beat). As notas entre duas correções esticam/comprimem para acompanhar. Ideal para acertar um ponto que escorregou.'),
  tap: T('<b>Marcar no cursor:</b> dá play, e quando ouvires uma nota na gravação, clica nessa nota na partitura — ela ancora na posição do cursor. Alinhar a tocar.'),
  excerpt: T('<b>Excerto:</b> arrasta uma caixa por cima de várias notas e depois arrasta uma delas — movem-se todas em bloco. (Alternativa: Shift+clique numa nota e noutra para selecionar o intervalo.)'),
  movefrom: T('<b>Mover seguintes:</b> pausa a gravação no instante certo e clica na 1ª nota desalinhada — essa nota e TODAS as seguintes deslocam-se em bloco para o cursor. Para um trecho inteiro que entrou tarde/cedo.'),
  newbeat: T('<b>Corrigir daqui (detetar andamento) — o modo recomendado:</b> ouve até ao ponto onde a partitura começa a fugir da gravação e clica nessa nota. Mede o BPM real da gravação daí em diante e re-espaça só as notas seguintes. <b>Nada antes do clique se mexe</b>, por isso o que já estava bem fica intacto. Repete sempre que voltar a fugir — cada correção parte de onde a anterior deixou.'),
  baralign: T('<b>Alinhar por compasso:</b> pausa a gravação no instante certo e clica numa nota — ou na <b>linha/número do compasso</b>, para o alinhar pelo seu início mesmo sem notas — abre um popup com esse compasso já escolhido. Confirma com "= cursor" e esse compasso alinha-se ao cursor (ou "= pista" para o mesmo compasso de outra pista). Faz-se várias vezes ao longo da música; cada correção arrasta as notas seguintes. No mesmo popup, <b>Andamento</b> muda o BPM desse compasso (ou de vários seguidos) e o resto da música acompanha, cada compasso com o seu próprio andamento.'),
  tonechange: T('<b>Mudança de tom:</b> clica numa nota para trocar para um dos tons extra a partir daí.'),
  section: T('<b>Secção:</b> clica numa nota para nomear onde começa uma secção (intro/verso/refrão…). Nada a ver com sincronização — é para navegação e o Riff Repeater.'),
  editnotes: T('<b>Editar notas:</b> clica numa nota para a editar (traste, sustain, técnicas, bend/slide) ou remover; <b>duplo-clique</b> no pentagrama vazio insere uma nota nova, encaixada na grelha. Um clique simples no vazio move o cursor, como nos outros modos. Muda o CONTEÚDO da partitura — fica pendente até "Aplicar e reconstruir".'),
  fhp: T('<b>Posição da mão (FHP):</b> a faixa <b>FHP</b> por baixo da pauta mostra onde a mão fica no jogo, de uma posição até à seguinte (cinzento = automáticas, verde-água = tuas). Clica numa nota para pôr ali uma posição nova (ou mudar a que lá começa), ou clica numa barra da faixa para mudar o traste e a largura, ou apagá-la. A primeira edição copia as automáticas, para só mudares as que estão mal. Uma nota fora da sua posição fica com um anel vermelho. Fica pendente até "Aplicar e reconstruir".'),
  null: T('Nenhum modo ativo. Clica num modo acima. <b>Dica:</b> para um desvio uniforme em todo o trecho, usa antes o <b>Andamento (BPM)</b> — não precisa de âncoras.'),
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
  if (lbl) lbl.textContent = src ? src.dataset.name : T('Nenhum modo');
  document.getElementById('modeMenuBtn')?.classList.toggle('has-mode', !!src);
  document.getElementById('tabsvg')?.classList.toggle('mode-baralign', syncMode === 'baralign');
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
  // A panel with no item to focus (the Áudio sliders) leaves focus outside the
  // menu, where the menu's own Escape never hears it.
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !menu.hidden && !menu.contains(e.target)) close(true);
  });
}
wireDropdown('modeMenuBtn', 'modeMenu');
wireDropdown('notesMenuBtn', 'notesMenu');
wireDropdown('audioMenuBtn', 'audioMenu');
SYNC_MODE_BUTTONS.forEach(([id], i) => {
  const btn = document.getElementById(id);
  if (btn) btn.insertAdjacentHTML('beforeend', `<kbd class="dd-kbd" aria-hidden="true">${modeKey(i)}</kbd>`);
});
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
function activeToneKeyAt(chartTime, kind) {
  const set = toneSetFor(kind);  // that chart's own tones (see switchToneSet)
  let key = set.tone_base || set.tone_names[0] || (jobTones[0] && jobTones[0].key) || null;
  for (const c of set.tone_changes) {  // already time-sorted (see cleanToneSet)
    if (c.time <= chartTime + 1e-6) key = c.name; else break;
  }
  return key;
}

// The character for the note at `chartTime`: none (plain voice), a single forced
// tone, or — in "follow the score" mode ('__follow__') — the tone marked at that
// point, so a chart with several tone changes mirrors each of them as it plays.
function toneCharForNote(chartTime, kind) {
  if (!previewToneKey) return null;
  const key = previewToneKey === '__follow__' ? activeToneKeyAt(chartTime, kind) : previewToneKey;
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
let _karplusCacheSamples = 0;

// How long a previewed note sounds: its sustain as drawn on screen, never
// shorter than a pick (NOTE_MIN_S, about the length every note had before, so
// short notes sound as they did) and capped so one held note cannot hold a buffer of
// minutes. Rounded to 50 ms so held notes still share cached buffers.
const NOTE_MIN_S = 0.24, NOTE_MAX_S = 6;
function noteSoundLength(sustain) {
  if (!(sustain > NOTE_MIN_S)) return NOTE_MIN_S;
  return Math.min(NOTE_MAX_S, Math.round(sustain * 20) / 20);
}
// A held note must still ring at its end: Karplus-Strong loses `damping` once
// per period, so a fixed 0.99 silenced a high note within a few tenths of a
// second however long it was held. Pick the per-period loss that leaves about
// a quarter of the level at the end, never decaying faster than the plucky
// 0.99 a short note has always used (and still uses, unchanged).
function karplusDamping(hz, dur) {
  if (dur <= NOTE_MIN_S) return 0.99;
  return Math.min(0.9995, Math.max(0.99, Math.pow(0.25, 1 / (Math.max(20, hz) * dur))));
}

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
  // Bounded by count and by memory (held notes make longer buffers).
  if (_karplusCache.size > 256 || _karplusCacheSamples > 20e6) { _karplusCache.clear(); _karplusCacheSamples = 0; }
  _karplusCache.set(ck, buf);
  _karplusCacheSamples += total;
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
  // A short note keeps the plucky 0.99 decay (attack emphasised); a held one
  // decays slowly enough to ring for its whole length (karplusDamping).
  src.buffer = karplusBuffer(ctx, hz, dur, karplusDamping(hz, dur));
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
// `sustain` is the note's held time as drawn (seconds); a held note sounds
// for that long instead of as a pick.
function playNote(midi, chartTime, sustain = 0) {
  if (!audioCtx || midi == null) return;
  voiceNote(audioCtx, audioCtx.destination, midiToHz(midi), audioCtx.currentTime,
    noteSoundLength(sustain), Math.max(0.0001, tickGain * 0.6), toneCharForNote(chartTime));
}

// Render one arrangement's notes to a clean AudioBuffer (offline), placing each
// note at the recording-clock time it currently occupies on screen —
// warp(previewScale(t)) - viewOrigin, parameterized by the arrangement's own
// pending sync so it's correct regardless of which tab is open. Used as a
// selectable "Lead/Rhythm (sintetizada)" audio source: an isolated clean
// reference of just that guitar's part, to check the sync of each arrangement
// against the recording by ear. Reflects the pending sync at the moment it's
// selected (re-pick the source to refresh after more edits).
// The notes the GP lyrics are sung on (GET /jobs/{id}/vocal-line), as of the
// last build, in the lyrics' own clock — offered as "Voz (sintetizada)" so the
// rhythm the words follow can be heard against the recording.
let vocalLine = { notes: [], gp_has_lyrics: false };
const VOICE_SOURCE = 'Voz';
async function loadVocalLine(id) {
  vocalLine = { notes: [], gp_has_lyrics: false };
  try {
    const r = await fetch(`/jobs/${id}/vocal-line`);
    if (r.ok) vocalLine = await r.json();
  } catch { /* then the source is simply not offered */ }
  if (!selectedJob || selectedJob.id !== id) return;
  populateAudioSources();
  document.getElementById('lyricsFromScore').hidden = !(isGpJob() && vocalLine.gp_has_lyrics);
}

// The vocal line as a sung-like tone, not a plucked string: each note held for
// its written length, with a little vibrato. It sits where the lyrics are drawn
// (their clock + the built intro silence), so a word and its note sound
// together. A note with no pitch in the file plays an A4. The samples are
// computed directly, not through audio nodes: a few hundred scheduled
// oscillators took several times longer to render than the whole line needs.
async function synthesizeVoice() {
  const notes = vocalLine.notes || [];
  if (!notes.length) return null;
  const sr = 44100;
  const last = notes.reduce((m, n) => Math.max(m, n.time + n.length), 0);
  const buf = new AudioBuffer({
    length: Math.ceil((last + leadInBuilt + 1) * sr), sampleRate: sr, numberOfChannels: 1,
  });
  const out = buf.getChannelData(0);
  // The vocal line is the score's, so it follows the pending chart corrections.
  const follow = lyricSyncMap();
  for (const n of notes) {
    const hz = midiToHz(n.midi ?? 69);
    const start = follow(n.time);
    const dur = Math.max(0.08, follow(n.time + n.length) - start);
    const i0 = Math.round((start + leadInBuilt) * sr);
    const len = Math.min(Math.round(dur * sr), out.length - i0);
    const attack = 0.02 * sr, release = Math.min(0.06, dur / 3) * sr;
    let phase = 0;
    for (let k = 0; k < len; k++) {
      const t = k / sr;
      const vibrato = 1 + 0.006 * Math.sin(2 * Math.PI * 5.5 * t) * Math.min(1, t / 0.25);
      phase += 2 * Math.PI * hz * vibrato / sr;
      const env = Math.min(1, k / attack, (len - k) / release);
      // A soft vowel: the fundamental with a little of the 2nd and 3rd harmonic.
      out[i0 + k] += 0.3 * env * (Math.sin(phase) + 0.35 * Math.sin(2 * phase) + 0.12 * Math.sin(3 * phase));
    }
  }
  return buf;
}

async function synthesizeArrangement(kind) {
  if (kind === VOICE_SOURCE) return synthesizeVoice();
  const a = arrangements.find(x => x.kind === kind);
  if (!a || !a.notes || !a.notes.length) return null;
  const sr = 44100;
  const gp = isGpJob();
  const ratio = tempoRatioOf(a);
  const warp = buildTimeWarp(syncAnchorsByKind[kind] || []);
  const pad = livePad();  // previewScale's own shift
  const events = [];
  let maxT = 0;
  for (const n of a.notes) {
    if (n.string < 0 || n.string >= stringCount(a) || n.fret < 0) continue;
    // Same recording-clock position the note is drawn at (see previewScale /
    // timeToX): GP applies tempo/offset/anchor sync; audio-ML notes are already
    // at raw recording time.
    const at = t => (gp ? warp((t - scoreShift) * ratio + pad) - viewOrigin : t);
    const tRec = at(n.time);
    if (tRec < 0) continue;
    const len = noteSoundLength(n.sustain > 0 ? at(n.time + n.sustain) - tRec : 0);
    events.push({ t: tRec, chartT: n.time, midi: noteMidi(a, n.string, n.fret), len });
    if (tRec + len > maxT) maxT = tRec + len;
  }
  if (!events.length) return null;
  const dur = maxT + 0.5;
  const OACtx = window.OfflineAudioContext || window.webkitOfflineAudioContext;
  const octx = new OACtx(1, Math.ceil(dur * sr), sr);
  // The synthesized source carries the preview tone too, following the tones
  // marked on the score (per-note) when '__follow__' is selected.
  for (const ev of events)
    voiceNote(octx, octx.destination, midiToHz(ev.midi), ev.t, ev.len, 0.5,
      toneCharForNote(ev.chartT, kind));
  return await octx.startRendering();
}

// ---- Fretboard (guitar neck) that lights up each note's (string, fret) as it
// plays, like Guitar Pro's fretboard view. Static neck is drawn once per
// showArr; a small overlay group is refreshed each frame with the active notes.
let fretboardOn = true;
const FB = { frets: 24, fw: 26, sh: 20, x0: 46, y0: 14 };
function fretXY(string, fret) {
  const top = stringCount(arrangements[currentArr]) - 1;  // the highest string on top
  const y = FB.y0 + (top - string) * FB.sh;
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
  const a = arrangements[currentArr];
  const nStr = stringCount(a);
  const neckH = (nStr - 1) * FB.sh, top = FB.y0, bottom = FB.y0 + neckH;
  const W = FB.x0 + FB.frets * FB.fw + 14, H = bottom + 26;
  svg.setAttribute('width', W); svg.setAttribute('height', H);
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
  for (let i = 0; i < nStr; i++) {
    const y = FB.y0 + (nStr - 1 - i) * FB.sh;
    s += `<line x1="${FB.x0}" y1="${y}" x2="${FB.x0 + FB.frets * FB.fw}" y2="${y}" stroke="#9aa1ae" stroke-width="${1 + (nStr - 1 - i) * 0.35 + (isBassArr(a) ? 0.8 : 0)}"/>`;
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
    if (n.string < 0 || n.string >= stringCount(arrangements[currentArr]) || n.fret < 0
        || n.fret > FB.frets) continue;
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

// --- Pista 3D (web/highway3d.js, three.js loaded on first use) ---------------------------------
// Same clock as the score: each note at warp(previewScale(t)) — so pending
// tempo/anchor edits move it here too, live — and the playhead at
// playheadDisplay(audioTime()). The highway draws; it knows nothing about sync.
let hw3dOn = false;
try { hw3dOn = localStorage.getItem('rf-hw3d') === '1'; } catch { /* storage blocked: off */ }
let hw3dLastSong = null;
// The camera (degrees around, degrees up, distance) is remembered for the next project.
const HW3D_CAMERA = [['yaw', 'hw3dYaw'], ['pitch', 'hw3dPitch'], ['dist', 'hw3dDist']];
function hw3dCamera() {
  const cam = {};
  for (const [k, id] of HW3D_CAMERA) cam[k] = Number(document.getElementById(id).value);
  return cam;
}
function hw3dShowCamera(cam) {
  for (const [k, id] of HW3D_CAMERA) {
    const el = document.getElementById(id);
    if (Number.isFinite(cam[k])) el.value = cam[k];
    el.title = k === 'dist' ? String(Math.round(Number(el.value) * 10) / 10) : `${Math.round(Number(el.value))}°`;
  }
  try { localStorage.setItem('rf-hw3d-cam', JSON.stringify(hw3dCamera())); } catch { /* not remembered */ }
}
try { hw3dShowCamera(JSON.parse(localStorage.getItem('rf-hw3d-cam') || '{}') || {}); } catch { /* defaults */ }
function hw3dNow() { return { t: playheadDisplay(audioTime()), playing: audioIsPlaying() }; }
function hw3dRefresh(a, notes) {
  if (!hw3dOn || !window.Highway3D || !window.Highway3D.ready || !a) return;
  const warp = buildTimeWarp(syncAnchors);
  const at = t => warp(previewScale(t));
  const data = {
    notes: notes.map(n => {
      const t = at(n.time);
      return {
        t, sustain: n.sustain > 0 ? Math.max(0, at(n.time + n.sustain) - t) : 0,
        string: n.string, fret: n.fret, techniques: n.techniques || [],
        bend: n.bend_semitones || 0, slideTo: n.slide_to ?? -1, chordName: n.chord_name || '',
      };
    }),
    bars: (a.bars || []).map(b => ({ t: at(b.time), measure: b.measure })),
    beats: (a.beats || []).map(at),
    sections: songSections.map(sec => ({ t: at(sec.time), name: sec.name })),
    fhps: fhpList(a).map(h => ({ t: at(h.time), fret: h.fret, width: h.width })),
    tuning: a.tuning_offsets || [0, 0, 0, 0, 0, 0],
    strings: stringCount(a),
  };
  // showArr runs on every pending edit; rebuilding the lane only when something changed.
  const key = JSON.stringify(data);
  if (key === hw3dLastSong) return;
  hw3dLastSong = key;
  window.Highway3D.setSong(data);
}
async function setHw3d(on) {
  hw3dOn = on;
  try { localStorage.setItem('rf-hw3d', on ? '1' : '0'); } catch { /* not remembered */ }
  const wrap = document.getElementById('hw3dWrap');
  const msg = document.getElementById('hw3dMsg');
  document.getElementById('show3d').checked = on;
  wrap.hidden = !on;
  if (!window.Highway3D) return;
  if (!on) { window.Highway3D.close(); return; }
  msg.hidden = true;
  try {
    await window.Highway3D.open(wrap, hw3dNow, hw3dShowCamera);
    window.Highway3D.setOptions({ numbers: document.getElementById('hw3dNumbers').checked, ...hw3dCamera() });
    hw3dLastSong = null;
    if (arrangements.length) showArr(currentArr);
  } catch (err) {
    msg.textContent = err && err.message && err.message.includes('WebGL')
      ? err.message
      : T('Não consegui abrir a pista 3D: {msg}', { msg: (err && err.message) || err });
    msg.hidden = false;
  }
}
document.getElementById('show3d').addEventListener('change', e => setHw3d(e.target.checked));
document.getElementById('hw3dNumbers').addEventListener('change', e => window.Highway3D?.setOptions({ numbers: e.target.checked }));
for (const [, id] of HW3D_CAMERA) {
  document.getElementById(id).addEventListener('input', () => {
    hw3dShowCamera({});
    window.Highway3D?.setOptions(hw3dCamera());
  });
}
document.getElementById('hw3dCamReset').addEventListener('click', () => {
  const cam = window.Highway3D ? window.Highway3D.cameraDefault : { yaw: 0, pitch: 15, dist: 15 };
  hw3dShowCamera(cam);
  window.Highway3D?.setOptions(cam);
});
document.getElementById('hw3dFull').addEventListener('click', () => window.Highway3D?.fullscreen());

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
  el.textContent = info && info.bpm ? `♩ = ${Math.round(info.bpm)}${info.measure ? ` · ${T('c.{n}', { n: info.measure })}` : ''}` : '';
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
  if (!jobTones.length) {
    el.innerHTML = `${icon('wave')}${esc(T('Tom standard: {tone}', { tone: standardToneFor(currentKind()) }))}`;
    return;
  }
  if (!(toneBase || toneChanges.length)) { el.textContent = ''; return; }
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
  if (btn) btn.textContent = T('▶ Pré-visualizar este arranjo');
}

function playArrangementPreview() {
  if (previewOscillators.length) { stopArrangementPreview(); return; }
  const a = arrangements[currentArr];
  if (!a || !a.notes.length) return;
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  audioCtx.resume();
  const t0 = audioCtx.currentTime + 0.1;
  for (const n of a.notes) {
    if (n.string < 0 || n.string >= stringCount(a) || n.fret < 0) continue;
    const midi = noteMidi(a, n.string, n.fret);
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
  document.getElementById('previewArr').textContent = T('■ Parar pré-visualização');
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
  return (t - scoreShift) * ratio + livePad();
}
// The second half of that mirror: where the build would put the score's start
// with the live offset (max(offset, MIN_LEAD) + lead_in).
function livePad() { return Math.max(offsetLive, MIN_LEAD) + leadInBuilt; }
// Chart `a`'s pending tempo against the tempo it was built with (1 = unchanged),
// whichever tab is on screen.
function tempoRatioOf(a) {
  const built = a.tempo_scale || 1;
  return ((a.kind in tempoScaleByKind) ? tempoScaleByKind[a.kind] : built) / built;
}

// Audio→display mapping for the playhead: audio time s appears after the
// prepended silence (pad = max(0, MIN_LEAD - offset)); independent of tempo
// since the recording itself is the fixed reference.
function playheadDisplay(s) {
  if (!isGpJob()) return s;  // audio-ML: playhead is straight recording time
  return s + Math.max(0, MIN_LEAD - offsetLive);
}
// Display time of second `s` of the recording FILE (what the server measures):
// the decoded buffer starts with the build's intro silence (decodeWaveform).
function recordingDisplay(s) { return playheadDisplay(s + leadInBuilt); }

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
  // With the loop on, playing from outside it starts at A.
  if (loopOn && loopA != null && loopB != null) {
    const t = audioTime();
    if (t < loopA || t >= loopB) {
      if (playBuffer) pausedAt = loopA;
      else { const au = document.getElementById('syncAudio'); if (au) au.currentTime = loopA; }
    }
  }
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
  } else if (e.key >= '0' && e.key <= '9' && !e.ctrlKey && !e.metaKey && !e.altKey && isGpJob()) {
    const entry = SYNC_MODE_BUTTONS[e.key === '0' ? 9 : Number(e.key) - 1];
    const btn = entry && document.getElementById(entry[0]);
    if (btn && !btn.disabled && !btn.hidden) {
      e.preventDefault();
      setSyncMode(syncMode === entry[1] ? null : entry[1]);
    }
  } else if (e.key === '[' && !e.ctrlKey && !e.metaKey) {
    e.preventDefault(); setLoopPoint('a');
  } else if (e.key === ']' && !e.ctrlKey && !e.metaKey) {
    e.preventDefault(); setLoopPoint('b');
  } else if ((e.key === 'l' || e.key === 'L') && !e.ctrlKey && !e.metaKey && !e.altKey) {
    e.preventDefault(); toggleLoop();
  } else if (e.key === '+' || e.key === '=') {
    e.preventDefault(); setZoom(zoomLevel * 1.5);
  } else if (e.key === '-' || e.key === '_') {
    e.preventDefault(); setZoom(zoomLevel / 1.5);
  } else if ((e.ctrlKey || e.metaKey) && (e.key === 'c' || e.key === 'C') && isGpJob()) {
    e.preventDefault(); copySelectedNotes();
  } else if ((e.ctrlKey || e.metaKey) && (e.key === 'v' || e.key === 'V') && isGpJob()) {
    e.preventDefault(); pasteNotesAtCursor();
  } else if ((e.key === 'Delete' || e.key === 'Backspace') && isGpJob() && selectedTimes.size) {
    e.preventDefault(); deleteSelectedNotes();
  }
});

// ── A–B loop ─────────────────────────────────────────────────────────────────
// Practising or checking a passage: A and B are set at the cursor (recording
// time, the playhead's own clock), and while the loop is on playback stays
// inside them — reaching B goes back to A, and playing from outside starts at
// A. Paused, the cursor still moves freely. Belongs to the project open now.
let loopA = null, loopB = null, loopOn = false;
function setLoopPoint(which) {
  const t = Math.max(0, currentPlayheadT);
  const prev = which === 'a' ? loopA : loopB;
  if (which === 'a') loopA = t; else loopB = t;
  if (loopA != null && loopB != null) {
    if (loopB < loopA) [loopA, loopB] = [loopB, loopA];
    if (loopB - loopA < 0.2) {
      if (which === 'a') loopA = prev; else loopB = prev;
      toast(T('A e B têm de estar pelo menos 0,2 s afastados.'));
    } else if (prev == null) {
      loopOn = true;  // the second point placed: repeat it straight away
    }
  }
  updateLoopUi();
  redrawScore();
}
function toggleLoop() {
  if (loopA == null || loopB == null) { toast(T('Marca primeiro o início (A) e o fim (B) do trecho, no cursor.')); return; }
  loopOn = !loopOn;
  if (loopOn && audioIsPlaying()) keepInsideLoop();
  updateLoopUi();
  redrawScore();
}
function clearLoop(redraw = true) {
  loopA = loopB = null;
  loopOn = false;
  updateLoopUi();
  if (redraw) redrawScore();
}
// While the loop is on: back to A from outside it. True when it moved.
function keepInsideLoop() {
  if (!loopOn || loopA == null || loopB == null) return false;
  const t = audioTime();
  if (t >= loopA && t < loopB) return false;
  audioSeek(loopA);
  return true;
}
function updateLoopUi() {
  const a = document.getElementById('loopA'), b = document.getElementById('loopB');
  if (!a) return;
  a.classList.toggle('set', loopA != null);
  b.classList.toggle('set', loopB != null);
  a.title = loopA != null ? T('Início do trecho: {t} — clica para o mover para o cursor ([)', { t: fmtClockTenths(loopA) })
    : T('Início do trecho a repetir = cursor ([)');
  b.title = loopB != null ? T('Fim do trecho: {t} — clica para o mover para o cursor (])', { t: fmtClockTenths(loopB) })
    : T('Fim do trecho a repetir = cursor (])');
  document.getElementById('loopToggle').setAttribute('aria-pressed', loopOn ? 'true' : 'false');
  document.getElementById('loopClear').hidden = loopA == null && loopB == null;
}
// The loop on the score: a band from A to B, brighter while it repeats.
function loopBandSvg(H) {
  if (loopA == null && loopB == null) return '';
  const x = t => 30 + t * tabPx;
  let s = '';
  if (loopA != null && loopB != null)
    s += `<rect x="${x(loopA)}" y="0" width="${(loopB - loopA) * tabPx}" height="${H}" fill="#7c5cff" opacity="${loopOn ? 0.16 : 0.07}" pointer-events="none"/>`;
  for (const [t, label] of [[loopA, 'A'], [loopB, 'B']]) {
    if (t == null) continue;
    s += `<line x1="${x(t)}" y1="0" x2="${x(t)}" y2="${H}" stroke="#a98bff" stroke-width="1.5" stroke-dasharray="4,3" pointer-events="none"/>`;
    s += `<text x="${x(t) + 4}" y="14" fill="#c9b3ff" font-size="12" font-weight="700" pointer-events="none">${label}</text>`;
  }
  return s;
}
document.getElementById('loopA').addEventListener('click', () => setLoopPoint('a'));
document.getElementById('loopB').addEventListener('click', () => setLoopPoint('b'));
document.getElementById('loopToggle').addEventListener('click', toggleLoop);
document.getElementById('loopClear').addEventListener('click', () => clearLoop());

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
  if (loopOn && audioIsPlaying() && loopB != null && audioTime() >= loopB) keepInsideLoop();
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
      if (note.string >= 0 && note.string < stringCount(arrNow) && note.fret >= 0) {
        const at = warp(previewScale(note.time));
        const held = note.sustain > 0 ? warp(previewScale(note.time + note.sustain)) - at : 0;
        playNote(noteMidi(arrNow, note.string, note.fret), note.time, held);
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
  // Not clamped at 0: the job's offset_s may be negative (the GP's bar 1 before
  // the recording). Clamping it made the preview pad the audio by 2 s instead of
  // the built MIN_LEAD - offset_s, so the music ran ahead of the notes, and
  // "Aplicar e reconstruir" sent offset_s 0, losing the file's sync.
  offsetLive = Math.max(MIN_OFFSET, v || 0);
  document.getElementById('syncOffset').value = offsetLive.toFixed(2);
  document.getElementById('syncOffsetRange').value = Math.max(0, offsetLive);
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
    lyricPadBuilt = Math.max(0, MIN_LEAD - (j.offset_s || 0)) + leadInBuilt;
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
  syncMain = (j.sync_main && arrangements.some(a => a.kind === j.sync_main)) ? j.sync_main : null;
  resetMainFollow();
  decodeWaveform(j.id);
  loadStems(j.id);
  loadVocalLine(j.id);
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
  pctEl.textContent = T('{pct}% do andamento do GP', { pct: Math.round(100 / tempoScaleLive) });
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
// With other pending anchors (an auto-sync, taps, a bar alignment) the first
// note's anchor is only one point of a piecewise warp, so moving it alone
// stretched just the stretch up to the next anchor — "it only adjusts the
// first section". The start then moves the WHOLE chart: every anchor shifts by
// the same amount, with the chart's ends pinned so the warp (identity outside
// its range) still covers every note.
function planStartShift(anchors, warp, origT, target, span) {
  const EPS = 0.05;
  // None or one (a uniform shift wherever it sits): the start is one anchor.
  if (anchors.length <= 1) return [[origT, target]];
  const d = target - warp(origT);
  const out = anchors.map(([o, n]) => [o, n + d]);
  if (!out.some(([o]) => Math.abs(o - origT) < EPS)) out.push([origT, target]);
  if (out.length > 1 && span) {
    const [startO, endO] = span;
    if (!out.some(([o]) => o <= startO + EPS)) out.push([startO, warp(startO) + d]);
    if (!out.some(([o]) => o >= endO - EPS)) out.push([endO, warp(endO) + d]);
  }
  out.sort((x, y) => x[0] - y[0]);
  return out;
}
function shiftTrackStart(origT, target) {
  const plan = planStartShift(syncAnchors, buildTimeWarp(syncAnchors), origT, target, chartSpan(currentArr));
  syncAnchors.splice(0, syncAnchors.length, ...plan);
}
function setTrackStart(v) {
  const chartT = currentArrFirstNoteTime();
  if (chartT == null) return;
  shiftTrackStart(previewScale(chartT), Math.max(0, v) + viewOrigin);
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
    info.textContent = T('Início desta pista fixado na posição do cursor: {s}s.', { s: t.toFixed(2) });
    toast(T('Início = posição do cursor'), 'ok');
  });
  // (Fine ±0.01 nudges removed — the "Segundo" number field already steps by 0.01.)

  // Guided 3-click alignment: arm → click the waveform where the 1st note
  // sounds → click the 1st note to shift it (and all notes) there.
  detect.addEventListener('click', () => startFirstNoteFlow());
})();

// The recording's deviation from A440, edited in "Opções da construção" or
// filled by "Detetar afinação"; sent on every rebuild (±50, the API's bound).
function setCentOffsetLive(cents) {
  const v = Number.isFinite(cents) ? Math.max(-50, Math.min(50, cents)) : 0;
  centOffsetLive = Math.round(v * 10) / 10;
  document.getElementById('centOffsetInput').value = centOffsetLive.toFixed(1);
  updatePendingChangesInfo();
}
document.getElementById('centOffsetInput').addEventListener('change', e =>
  setCentOffsetLive(parseFloat(e.target.value)));

(function wireDetectTuning() {
  const btn = document.getElementById('detectTuning');
  const info = document.getElementById('detectTuningInfo');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    if (!selectedJob) return;
    btn.disabled = true;
    info.textContent = T('A analisar a gravação…');
    try {
      const r = await fetch(`/jobs/${selectedJob.id}/detect-tuning`, { method: 'POST' });
      const b = await r.json();
      if (!r.ok) { info.textContent = ''; toast(b.detail || T('erro'), 'err'); return; }
      setCentOffsetLive(b.suggested_cent_offset);
      info.textContent =
        T('Desvio detetado: {cents} cents. Aplica-se em "Aplicar e reconstruir". A afinação das cordas (drop/open) não é detetada — vem do ficheiro GP.',
          { cents: b.suggested_cent_offset.toFixed(1) });
      toast(T('Afinação proposta — revê e aplica'), 'ok');
    } catch {
      info.textContent = '';
      toast(T('falha na análise'), 'err');
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
      Combined: '#ff8a5c', Bass: '#5cc24a', [VOICE_SOURCE]: '#ff5fa2',
    };
    const label = kind === VOICE_SOURCE ? T('Voz (sintetizada)') : T('{name} (sintetizada)', { name: arrLabel(kind) });
    return { color: palette[kind] || '#a97bff', label };
  }
  if (n) return { color: '#3fb27f', label: STEM_LABELS[n] || n };
  return { color: '#2a6f97', label: T('Mistura completa') };
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

// A PDF or a picture of the tab (one per track, in order) goes to PDF-to-GP5's
// converter on the server, which answers like /gp/inspect.
const PDF_IMPORT_EXT = /\.(pdf|png|jpe?g|webp)$/i;
document.getElementById('gpInspectForm').addEventListener('submit', async e => {
  e.preventDefault();
  const files = [...e.target.querySelector('input[name=file]').files];
  if (files.length && files.every(f => PDF_IMPORT_EXT.test(f.name))) { importPdfTab(files); return; }
  if (files.length > 1) {
    toast(T('Escolhe só um ficheiro Guitar Pro. Vários ficheiros só para PDFs ou imagens da tab (um por pista).'));
    return;
  }
  const b = await fetchOrToast('/gp/inspect', { method: 'POST', body: new FormData(e.target) });
  if (!b) return;
  songsterrImported = false;
  applyInspectResult(b);
});

// Step 1's answer — from an uploaded file (/gp/inspect) or a tab built from
// Songsterr (/songsterr/import), which answers in the same shape.
function applyInspectResult(b) {
  gpToken = b.gp_token;
  wzGpHasLyrics = !!b.has_lyrics;
  wzEstimatedBars = b.estimated_bars || {};
  const form = document.getElementById('gpJobForm');
  document.getElementById('gpMeta').textContent =
    T('{title} — {artist} · {tempo} BPM · letra no GP: {lyrics}', {
      title: b.title || T('(sem título)'), artist: b.artist || T('(sem banda)'),
      tempo: b.tempo, lyrics: b.has_lyrics ? T('sim') : T('não'),
    });
  for (const name of ['lead_track', 'rhythm_track', 'combo_track', 'alt_lead_track', 'alt_rhythm_track']) {
    const sel = form.querySelector(`select[name=${name}]`);
    sel.innerHTML = '<option value="">—</option>' + b.tracks
      .filter(t => !t.is_percussion && t.string_count === 6)
      .map(t => `<option value="${t.index}">${t.index}: ${esc(t.name)}</option>`).join('');
  }
  // A Bass chart is made from a 4- or 5-string track (a 5-string folds onto 4).
  const bassTracks = (b.tracks || []).filter(t => !t.is_percussion && isBassTrackStrings(t.string_count));
  const bassSel = form.querySelector('select[name=bass_track]');
  bassSel.innerHTML = '<option value="">—</option>' + bassTracks
    .map(t => `<option value="${t.index}">${t.index}: ${esc(t.name)}</option>`).join('');
  // Auto-assign the first eligible track to Lead so step 2 has a sensible default,
  // and the bass the way the server would pick it (named "bass", else the only one).
  const firstTrack = (b.tracks || []).find(t => !t.is_percussion && t.string_count === 6);
  if (firstTrack) form.querySelector('select[name=lead_track]').value = String(firstTrack.index);
  const bassPick = bassTracks.find(t => /bass|baixo/i.test(t.name)) || (bassTracks.length === 1 ? bassTracks[0] : null);
  if (bassPick) bassSel.value = String(bassPick.index);
  if (b.title) form.querySelector('input[name=title]').value = b.title;
  if (b.artist) form.querySelector('input[name=artist]').value = b.artist;
  if (b.album) form.querySelector('input[name=album]').value = b.album;
  // Where the file came from when RockForge made it, and what that could not carry.
  const note = document.getElementById('gpImportNote');
  const noteParts = [];
  if (b.pdf_files && b.pdf_files.length) {
    noteParts.push(T('Convertido para Guitar Pro a partir de: {files}. Confere as notas e o ritmo na partitura.',
      { files: b.pdf_files.join(', ') }));
  }
  if (b.import_warnings && b.import_warnings.length) {
    noteParts.push(T('Avisos da conversão: {warnings}', { warnings: b.import_warnings.join('; ') }));
  }
  note.textContent = noteParts.join(' ');
  note.hidden = !noteParts.length;
  // Synced to an audio track in Guitar Pro 8: the file itself says where bar 1
  // is in that audio, so offer the exact value instead of asking for a guess.
  const embeddedRow = document.getElementById('gpEmbeddedAudioRow');
  embeddedRow.hidden = !b.embedded_audio;
  document.getElementById('useEmbeddedAudio').checked = !!b.embedded_audio;
  document.getElementById('gpEmbeddedAudioInfo').textContent = b.embedded_audio
    ? `(${b.embedded_audio.name}, ${(b.embedded_audio.size_bytes / 1048576).toFixed(1)} MB)` : '';
  applyEmbeddedAudioChoice();
  // The audio GP8 was synced to, when it is not inside the file: a YouTube
  // video (fetched like a Songsterr video) or a file elsewhere on the disk.
  if (b.backing_youtube_url && !b.embedded_audio) {
    document.getElementById('ytLink').value = b.backing_youtube_url;
    document.getElementById('ytBlock').open = true;
    downloadYtAudio();
  }
  const syncHint = document.getElementById('gpSyncHint');
  const where = b.embedded_audio
    ? (b.backing_disabled ? ' ' + T('A faixa de áudio está desligada no Guitar Pro, mas é o áudio com que o ficheiro foi sincronizado, por isso é usado.') : '')
    : b.backing_youtube_url
      ? ' ' + T('No Guitar Pro o áudio é o deste vídeo do YouTube ({url}) — estou a descarregá-lo em "Não tens o áudio?".', { url: b.backing_youtube_url })
      : b.backing_external_path
        ? ' ' + T('O áudio não vem dentro do ficheiro: o Guitar Pro usa «{path}». Carrega esse ficheiro abaixo.', { path: b.backing_external_path })
        : '';
  if (b.sync_start_s != null) {
    form.querySelector('input[name=offset_s]').value = b.sync_start_s.toFixed(3);
    const bar1 = b.sync_start_s >= 0
      ? T('começa em {s} s desse áudio', { s: b.sync_start_s.toFixed(3) })
      : T('começa {s} s antes de esse áudio começar', { s: (-b.sync_start_s).toFixed(3) });
    syncHint.textContent = T('Este ficheiro foi sincronizado com o áudio no Guitar Pro 8 — o compasso 1 {bar1}.', { bar1 }) + ' ' +
      (b.embedded_audio
        ? T('Com o áudio do ficheiro GP (acima) o valor já está certo e as notas seguem o tempo variável do GP.')
        : T('Se a gravação que carregas é esse mesmo ficheiro de áudio, o valor já está certo e as notas seguem o tempo variável do GP.')) +
      where;
    syncHint.hidden = false;
  } else {
    syncHint.textContent = where.trim();
    syncHint.hidden = !where;
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
  if (!link) { toast(T('Cola o link da música no Songsterr.')); return; }
  btn.disabled = true;
  info.textContent = T('A descarregar a tab do Songsterr e a criar o ficheiro Guitar Pro…');
  let b;
  try {
    b = await getJSON('/songsterr/import', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ song: link }),
    });
  } catch (err) {
    info.textContent = T('Não consegui importar: {msg}', { msg: err.message });
    return;
  } finally {
    btn.disabled = false;
  }
  info.textContent = b.import_warnings && b.import_warnings.length
    ? T('Importada, com avisos: {warnings}.', { warnings: b.import_warnings.join('; ') }) : T('Tab importada.');
  songsterrImported = true;
  applyInspectResult(b);
  // Step 3: the same song's per-measure times, ready to pick a video.
  document.getElementById('songsterrLink').value = link;
  document.getElementById('songsterrBlock').open = true;
  // …and the chosen video's audio, so the whole song comes from one link.
  if (await fetchSongsterrVideos()) downloadYtAudio();
}
document.getElementById('songsterrImportBtn').addEventListener('click', importSongsterrTab);

async function importPdfTab(files) {
  const info = document.getElementById('pdfImportInfo');
  const next = document.getElementById('wizardNext');
  info.textContent = T('A converter em Guitar Pro (pode demorar, sobretudo com imagens)…');
  next.disabled = true;
  const body = new FormData();
  files.forEach(f => body.append('files', f));
  let b;
  try {
    b = await getJSON('/pdf/import', { method: 'POST', body });
  } catch (err) {
    info.textContent = T('Não consegui converter: {msg}', { msg: err.message });
    return;
  } finally {
    next.disabled = false;
  }
  info.textContent = T('Convertido.');
  songsterrImported = false;
  applyInspectResult(b);
}
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
  if (Object.keys(wzEstimatedBars).length) f.set('estimated_bars', JSON.stringify(wzEstimatedBars));
  // The picked card's image never loaded: its cover is not there to download.
  const picked = wzAlbumCandidates[wzAlbumPick];
  if (picked && picked.cover_broken) f.delete('cover_url');
  const b = await fetchOrToast('/jobs/gp', { method: 'POST', body: f });
  if (!b) return;
  // The cover is downloaded while the job is created; a failure there must
  // not lose the project, so it is reported here instead.
  if (f.get('cover_url') && !b.cover_art)
    toast(T('Projeto criado, mas não consegui descarregar a capa — escolhe outra na página Capa.'));
  else toast(T('Projeto criado.'), 'ok');
  document.getElementById('newJobOverlay').hidden = true;  // created: nothing to lose
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

