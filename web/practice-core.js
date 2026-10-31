// Practice mode ("Tocar"): the guitar's pitch and attacks, and the judging of
// the chart's single notes against them. Pure code, no DOM and no Web Audio, so
// the same file runs in the AudioWorklet (practice-worklet.js loads it first:
// modules added to one worklet share its global scope), on the page (the judge)
// and under Node (tests/web/practice-core.test.mjs).
//
// The pitch is YIN (de Cheveigné & Kawahara 2002, "YIN, a fundamental frequency
// estimator for speech and music") on a low-passed, decimated copy of the input:
// a guitar's fundamental is at most ~1.3 kHz (fret 24 of the top string), so
// ~11-12 kHz of sample rate is plenty and it costs a sixteenth of the work.
// An attack is a jump of the short-term energy over the level just before it.
// A chord is judged from the spectrum: every 30 ms the tracker also hands out
// the magnitude spectrum of the last ~170 ms, and the notes the chord should
// have are fitted to it, with their neighbours a semitone or two away, by
// non-negative least squares — each note a comb of its harmonics.
(function (root) {
  'use strict';

  const YIN_THRESHOLD = 0.15;   // cumulative mean normalised difference under which a lag is a period
  const HOP_S = 0.005;          // one pitch reading every 5 ms
  const ONSET_RATIO = 2;        // the envelope over its quietest point 25-50 ms before
  const ONSET_GATE = 1e-5;      // mean square under which nothing counts (about -50 dBFS)
  const ONSET_REFRACTORY_S = 0.06;
  const SILENCE = 2e-6;         // mean square of a window too quiet to have a pitch
  const SPEC_N = 2048;          // spectrum window, decimated samples (~170 ms)
  const SPEC_EVERY = 6;         // a spectrum every 6 hops (30 ms)
  const SPEC_MAX_HZ = 3000;     // the bins handed out: fundamentals and their first harmonics

  // Magnitudes of the real input `x` (length a power of two), bins 0..n-1.
  function fftMag(x, n) {
    const N = x.length, re = Float64Array.from(x), im = new Float64Array(N);
    for (let i = 1, j = 0; i < N; i++) {
      let bit = N >> 1;
      for (; j & bit; bit >>= 1) j ^= bit;
      j ^= bit;
      if (i < j) { const t = re[i]; re[i] = re[j]; re[j] = t; }
    }
    for (let len = 2; len <= N; len <<= 1) {
      const ang = -2 * Math.PI / len, wr = Math.cos(ang), wi = Math.sin(ang);
      for (let i = 0; i < N; i += len) {
        let cr = 1, ci = 0;
        for (let k = 0; k < len / 2; k++) {
          const a = i + k, b = a + len / 2;
          const tr = re[b] * cr - im[b] * ci, ti = re[b] * ci + im[b] * cr;
          re[b] = re[a] - tr; im[b] = im[a] - ti;
          re[a] += tr; im[a] += ti;
          const nr = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = nr;
        }
      }
    }
    const out = new Float32Array(n);
    for (let k = 0; k < n; k++) out[k] = Math.hypot(re[k], im[k]);
    return out;
  }

  // One RBJ low-pass biquad (Audio EQ Cookbook), Q = 1/sqrt(2).
  function lowpass(fc, sr) {
    const w = 2 * Math.PI * fc / sr, c = Math.cos(w), al = Math.sin(w) / Math.SQRT2;
    const a0 = 1 + al;
    const b0 = (1 - c) / 2 / a0, b1 = (1 - c) / a0, b2 = b0;
    const a1 = -2 * c / a0, a2 = (1 - al) / a0;
    let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
    return x => {
      const y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2;
      x2 = x1; x1 = x; y2 = y1; y1 = y;
      return y;
    };
  }

  // The tracker: feed it the input samples (any block size) and it answers
  // one reading per hop. `t` of a reading is in input SAMPLES (the caller turns
  // it into seconds of its own clock): the middle of the window for the pitch,
  // the middle of the hop for the attack.
  function createTracker(sampleRate, opts = {}) {
    const minHz = Math.max(25, opts.minHz || 55);
    const maxHz = Math.min(2000, opts.maxHz || 1500);
    const dec = Math.max(1, Math.round(sampleRate / 11025));
    const dsr = sampleRate / dec;
    const f1 = lowpass(Math.min(4000, dsr * 0.36), sampleRate);
    const f2 = lowpass(Math.min(4000, dsr * 0.36), sampleRate);
    const tauMax = Math.ceil(dsr / minHz) + 2;
    const tauMin = Math.max(2, Math.floor(dsr / maxHz));
    const W = Math.max(tauMax, Math.round(dsr * 0.012));
    const N = W + tauMax;
    const hop = Math.max(1, Math.round(dsr * HOP_S));
    const ring = new Float32Array(N);  // the last N decimated samples, a ring
    const buf = new Float32Array(N);   // the same, oldest first, rebuilt for each reading
    const d = new Float32Array(tauMax + 1);
    let filled = 0, head = 0, phase = 0, sinceHop = 0, count = 0;  // count: decimated samples seen
    const energies = [];
    let hopEnergy = 0, lastOnset = -Infinity;
    const sRing = new Float32Array(SPEC_N), sBuf = new Float32Array(SPEC_N);
    const hann = Float32Array.from({ length: SPEC_N }, (_, i) => 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (SPEC_N - 1)));
    const specBins = Math.min(SPEC_N / 2, Math.floor(SPEC_MAX_HZ * SPEC_N / dsr) + 1);
    let sHead = 0, hops = 0;

    function yin() {
      for (let j = 0; j < N; j++) buf[j] = ring[(head + j) % N];
      let ms = 0;
      for (let j = 0; j < N; j++) ms += buf[j] * buf[j];
      ms /= N;
      if (ms < SILENCE) return { midi: NaN, clarity: 0, rms: Math.sqrt(ms) };
      d[0] = 0;
      for (let tau = 1; tau <= tauMax; tau++) {
        let s = 0;
        for (let j = 0; j < W; j++) { const v = buf[j] - buf[j + tau]; s += v * v; }
        d[tau] = s;
      }
      // cumulative mean normalised difference, in place
      let run = 0;
      d[0] = 1;
      for (let tau = 1; tau <= tauMax; tau++) {
        run += d[tau];
        d[tau] = run > 0 ? d[tau] * tau / run : 1;
      }
      let tau = -1;
      for (let k = tauMin; k <= tauMax; k++) {
        if (d[k] < YIN_THRESHOLD) {
          while (k + 1 <= tauMax && d[k + 1] < d[k]) k++;
          tau = k; break;
        }
      }
      if (tau < 0) return { midi: NaN, clarity: 0, rms: Math.sqrt(ms) };
      let t = tau;
      if (tau > 1 && tau < tauMax) {
        const a = d[tau - 1], b = d[tau], c = d[tau + 1];
        const den = a - 2 * b + c;
        if (den > 0) t = tau + 0.5 * (a - c) / den;
      }
      const hz = dsr / t;
      return { midi: 69 + 12 * Math.log2(hz / 440), clarity: 1 - d[tau], rms: Math.sqrt(ms) };
    }

    function process(input) {
      const out = [];
      for (let i = 0; i < input.length; i++) {
        const y = f2(f1(input[i]));
        if (++phase < dec) continue;
        phase = 0;
        ring[head] = y; head = (head + 1) % N;
        if (filled < N) filled++;
        sRing[sHead] = y; sHead = (sHead + 1) % SPEC_N;
        count++;
        hopEnergy += y * y;
        if (++sinceHop < hop) continue;
        sinceHop = 0;
        const e = hopEnergy / hop; hopEnergy = 0;
        energies.push(e);
        if (energies.length > 14) energies.shift();
        // The envelope: 20 ms of energy, longer than one period of a low string,
        // so the ripple of the wave itself never reads as an attack.
        const L = energies.length;
        const smooth = k => (energies[k] + energies[k - 1] + energies[k - 2] + energies[k - 3]) / 4;
        const endSample = count * dec;
        let onset = false;
        if (L >= 13) {
          const now = smooth(L - 1);
          let before = Infinity;
          for (let k = L - 10; k <= L - 5; k++) before = Math.min(before, smooth(k));
          if (now > ONSET_GATE && now > ONSET_RATIO * before + ONSET_GATE && now >= smooth(L - 2)) {
            // When: the first of the last four hops that carries the jump.
            let peak = 0;
            for (let k = L - 4; k < L; k++) peak = Math.max(peak, energies[k]);
            let first = L - 1;
            for (let k = L - 4; k < L; k++) if (energies[k] > 0.5 * peak) { first = k; break; }
            const tOn = endSample - (L - first) * hop * dec;
            if ((tOn - lastOnset) / sampleRate > ONSET_REFRACTORY_S) { onset = true; lastOnset = tOn; }
          }
        }
        let reading;
        if (filled < N) reading = { t: endSample, midi: NaN, clarity: 0, rms: Math.sqrt(e), onset, onsetT: onset ? lastOnset : null };
        else {
          const r = yin();
          reading = {
            t: endSample - (N / 2) * dec, midi: r.midi, clarity: r.clarity, rms: r.rms,
            onset, onsetT: onset ? lastOnset : null,
          };
        }
        if (++hops % SPEC_EVERY === 0 && count >= SPEC_N && opts.spectrum !== false) {
          for (let j = 0; j < SPEC_N; j++) sBuf[j] = sRing[(sHead + j) % SPEC_N] * hann[j];
          reading.spec = fftMag(sBuf, specBins);
          reading.specT = endSample - (SPEC_N / 2) * dec;  // the middle of its window
        }
        out.push(reading);
      }
      return out;
    }
    // A new pitch reads steady once most of the window holds it: about this long
    // after it was played (measured on note changes: 12-17 ms for a guitar).
    return { process, sampleRate, pitchLagS: 0.4 * N / dsr, specDf: dsr / SPEC_N };
  }

  // ---- judging ---------------------------------------------------------

  const EARLY_S = 0.12;        // how early a note may be played and still count
  const LATE_S = 0.15;         // how late
  const CENTS_OK = 60;         // pitch error still the right note (a little out of tune, a pick's sharp attack)
  const STABLE_FRAMES = 3;     // consecutive readings on the note (15 ms)
  const SAME_NOTE_GAP_S = 0.6; // the previous note on the same pitch rings this long: then an attack is needed
  const CHORD_S = 0.03;        // notes this close are a chord
  const SKIP = new Set(['mute', 'harmonic', 'pinchHarmonic']);  // their pitch is not the fret's

  // The notes to judge, from the chart as drawn: `notes` = [{key, time, string,
  // fret, techniques, bend_semitones}] with `time` already in display time,
  // `midiOf(note)` = its sounding MIDI pitch (cents included). Notes within
  // CHORD_S of each other are one chord target ({chord: true, notes}); muted
  // and harmonic notes are left out (their pitch is not the fret's) and counted.
  function practiceTargets(notes, midiOf) {
    const sorted = notes.slice().sort((a, b) => a.time - b.time);
    const groups = [];
    for (const n of sorted) {
      const g = groups[groups.length - 1];
      if (g && n.time - g[0].time <= CHORD_S) g.push(n); else groups.push([n]);
    }
    const out = [];
    let skipped = 0;
    for (const g of groups) {
      const playable = [];
      for (const n of g) {
        const tech = n.techniques || [];
        const midi = midiOf(n);
        if (tech.some(t => SKIP.has(t)) || !Number.isFinite(midi)) { skipped++; continue; }
        playable.push({ n, tech, midi });
      }
      if (!playable.length) continue;
      if (g.length > 1 && playable.length > 1) {
        out.push({
          chord: true, key: playable[0].n.key, time: g[0].time,
          notes: playable.map(({ n, midi }) => ({ key: n.key, string: n.string, fret: n.fret, midi })),
        });
        continue;
      }
      const { n, tech, midi } = playable[0];
      out.push({
        key: n.key, time: g[0].time, string: n.string, fret: n.fret, midi,
        bend: Math.max(0, n.bend_semitones || 0),
        legato: tech.includes('hammerOn') || tech.includes('pullOff') || tech.includes('tap'),
      });
    }
    for (let i = 0; i < out.length; i++) {
      const t = out[i], p = out[i - 1];
      // The window stops halfway to the neighbours, so one sound never counts for two notes.
      t.early = p ? Math.min(EARLY_S, (t.time - p.time) / 2) : EARLY_S;
      t.late = i + 1 < out.length ? Math.min(LATE_S, (out[i + 1].time - t.time) / 2) : LATE_S;
      t.next = i + 1 < out.length ? out[i + 1].time : null;
      if (t.chord) continue;
      // The same pitch still ringing from the previous note (or chord) would count: ask for a new attack.
      const prevPitches = p ? (p.chord ? p.notes.map(x => x.midi) : [p.midi]) : [];
      t.prevMidi = p && !p.chord ? p.midi : null;
      t.needsOnset = !!p && !t.legato && prevPitches.some(m => Math.abs(m - t.midi) < 0.5)
        && t.time - p.time < SAME_NOTE_GAP_S + p.late;
    }
    return { targets: out, skipped };
  }

  // ---- chords -----------------------------------------------------------

  const CHORD_HARMONICS = 10;
  const CHORD_PRESENT = 0.18;   // a note's weight against the chord's strongest one: below it, not heard
  const CHORD_WRONG = 0.3;      // a neighbour this strong (and stronger than the note) is what was played
  const CHORD_SPEC_FROM = 0.09; // spectra whose window starts after the attack transient
  const CHORD_SPEC_TO = 0.24;

  // The main lobe of a Hann window's spectrum, `x` bins from its centre.
  function hannLobe(x) {
    if (x >= 2) return 0;
    if (Math.abs(x - 1) < 1e-6) return 0.5;
    const sinc = x < 1e-6 ? 1 : Math.sin(Math.PI * x) / (Math.PI * x);
    return Math.abs(sinc / (1 - x * x));
  }

  // A note as a comb of harmonics over bins lo..hi of a spectrum with bins `df`
  // Hz apart: each harmonic 1/h, a little wide (±25 cents: a guitar is never
  // exactly in tune, and its harmonics run sharp), unit length.
  function noteAtom(midi, df, lo, hi) {
    const f0 = 440 * 2 ** ((midi - 69) / 12);
    const a = new Float64Array(hi - lo);
    for (let h = 1; h <= CHORD_HARMONICS; h++) {
      const c = h * f0 / df;
      if (c >= hi + 2) break;
      const spread = 0.0145 * h * f0 / df;
      for (let k = Math.max(lo, Math.floor(c - spread - 2)); k <= Math.min(hi - 1, Math.ceil(c + spread + 2)); k++) {
        const x = Math.max(0, Math.abs(k - c) - spread);
        a[k - lo] += hannLobe(x) / h;
      }
    }
    let norm = 0;
    for (const v of a) norm += v * v;
    norm = Math.sqrt(norm) || 1;
    for (let i = 0; i < a.length; i++) a[i] /= norm;
    return a;
  }

  // Which of the chord's notes sound in `spec` (magnitudes, bins `df` Hz apart).
  // Each expected note and its neighbours one and two semitones away are fitted
  // together (Lee & Seung's multiplicative update for non-negative least
  // squares), so a string on the wrong fret shows as its neighbour winning.
  // An octave of a note is not a candidate: a note an octave off is not told
  // apart. Answers, per expected MIDI note, {weight, heard} (heard = the
  // neighbour that won, or null).
  function chordNotesHeard(spec, df, expected) {
    const exp = expected.map(Math.round);
    const cand = [...new Set(exp.flatMap(m => [m - 2, m - 1, m, m + 1, m + 2]))].sort((a, b) => a - b);
    const lowHz = 440 * 2 ** ((cand[0] - 69) / 12);
    const lo = Math.max(1, Math.floor(lowHz * 0.9 / df) - 2), hi = spec.length;
    const atoms = cand.map(m => noteAtom(m, df, lo, hi));
    const A = atoms.length, L = hi - lo;
    const atx = new Float64Array(A), ata = Array.from({ length: A }, () => new Float64Array(A));
    for (let i = 0; i < A; i++) {
      for (let k = 0; k < L; k++) atx[i] += atoms[i][k] * spec[lo + k];
      for (let j = i; j < A; j++) {
        let v = 0;
        for (let k = 0; k < L; k++) v += atoms[i][k] * atoms[j][k];
        ata[i][j] = ata[j][i] = v;
      }
    }
    const w = new Float64Array(A).fill(1);
    for (let it = 0; it < 400; it++) {
      for (let i = 0; i < A; i++) {
        let den = 1e-12;
        for (let j = 0; j < A; j++) den += ata[i][j] * w[j];
        w[i] *= Math.max(0, atx[i]) / den;
      }
    }
    const weight = new Map(cand.map((m, i) => [m, w[i]]));
    const expSet = new Set(exp);
    const top = Math.max(1e-12, ...exp.map(m => weight.get(m)));
    return exp.map(m => {
      const own = weight.get(m) / top;
      let heard = null, best = 0;
      for (const d of [-2, -1, 1, 2]) {
        const n = m + d;
        if (expSet.has(n)) continue;
        const v = weight.get(n) / top;
        if (v > best) { best = v; heard = n; }
      }
      if (heard != null && best >= CHORD_WRONG && best > own) return { weight: own, heard };
      return { weight: own, heard: null };
    });
  }

  // Judge a chord target: an attack in its window, then the spectra just after
  // it. `spectra` = [{t, mag}] in display time (t = the middle of each window),
  // `df` their bin spacing. A wrong fret makes it wrong; a chord of four
  // strings or more may miss one in four and still count. Answers {result, dt, notes: [{key, status: 'ok' |
  // 'missing' | 'wrong', heard}]}.
  function judgeChord(target, frames, spectra, df, used) {
    const from = target.time - target.early, to = target.time + target.late;
    let on = null;
    for (const f of frames) {
      if (!f.onset || f.onsetT == null || used.has(f.onsetT)) continue;
      if (f.onsetT < from - 0.03 || f.onsetT > to) continue;
      if (on == null || Math.abs(f.onsetT - target.time) < Math.abs(on - target.time)) on = f.onsetT;
    }
    if (on == null) return { result: 'miss', dt: null, notes: target.notes.map(n => ({ key: n.key, status: 'missing', heard: null })) };
    used.add(on);
    // Windows that start after the strike and, where there is time, end before the next note.
    const halfWin = 0.085;
    const until = target.next != null ? Math.max(on + CHORD_SPEC_FROM, target.next - halfWin + 0.02) : Infinity;
    let use = spectra.filter(sp => sp.t >= on + CHORD_SPEC_FROM && sp.t <= Math.min(on + CHORD_SPEC_TO, until));
    if (!use.length) {
      const after = spectra.filter(sp => sp.t >= on + 0.05);
      if (after.length) use = [after[0]];
    }
    if (!use.length) return { result: 'hit', dt: on - target.time, notes: target.notes.map(n => ({ key: n.key, status: 'ok', heard: null })), unchecked: true };
    const mag = new Float64Array(use[0].mag.length);
    for (const sp of use) for (let k = 0; k < mag.length; k++) mag[k] += sp.mag[k] / use.length;
    const heard = chordNotesHeard(mag, df, target.notes.map(n => n.midi));
    const notes = target.notes.map((n, i) => {
      const h = heard[i];
      if (h.heard != null) return { key: n.key, status: 'wrong', heard: h.heard };
      return { key: n.key, status: h.weight >= CHORD_PRESENT ? 'ok' : 'missing', heard: null };
    });
    // A string that doubles another an octave (or two) lower is drowned in that
    // note's harmonics: not told apart, it counts as heard when the lower one is.
    notes.forEach((n, i) => {
      if (n.status !== 'missing') return;
      const m = Math.round(target.notes[i].midi);
      if (notes.some((o, j) => o.status === 'ok' && [12, 24, 36].includes(m - Math.round(target.notes[j].midi)))) {
        n.status = 'ok'; n.octave = true;
      }
    });
    // A wrong fret is a wrong chord; a string not heard is forgiven once in four.
    const wrong = notes.filter(n => n.status === 'wrong').length;
    const missing = notes.filter(n => n.status === 'missing').length;
    const allowed = target.notes.length >= 4 ? Math.floor(target.notes.length / 4) : 0;
    return { result: !wrong && missing <= allowed ? 'hit' : 'wrong', dt: on - target.time, notes };
  }

  // Cents from the target, folding a whole octave (YIN's usual slip on a low
  // string, and a guitar played an octave off is still that note); a bend
  // counts anywhere between the fret and its peak.
  function pitchError(target, midi) {
    const lo = target.midi, hi = target.midi + target.bend;
    let best = Infinity;
    for (const oct of [0, -12, 12]) {
      const m = midi + oct;
      const e = m < lo ? lo - m : m > hi ? m - hi : 0;
      if (e < best) best = e;
    }
    return best * 100;
  }

  // Judge one target against the readings (`frames`: [{t, midi, onset}] in
  // display time, in order). `used` = attack times already given to another
  // note; `pitchLag` = the tracker's pitchLagS. Answers {result: 'hit'|'wrong'|'miss', dt, heard}.
  function judgeTarget(target, frames, used, pitchLag = 0.015) {
    const from = target.time - target.early, to = target.time + target.late;
    let run = 0, runStart = null, hitAt = null;
    const heardCounts = new Map();
    for (const f of frames) {
      if (f.t < from - 0.05) continue;
      if (f.t > to + 0.05) break;
      if (!Number.isFinite(f.midi)) { run = 0; continue; }
      if (f.t >= from && f.t <= to) {
        const k = Math.round(f.midi);
        heardCounts.set(k, (heardCounts.get(k) || 0) + 1);
      }
      if (pitchError(target, f.midi) <= CENTS_OK) {
        if (run === 0) runStart = f.t;
        if (++run >= STABLE_FRAMES && runStart >= from - 0.05 && runStart <= to) { hitAt = runStart; break; }
      } else run = 0;
    }
    const onsets = frames.filter(f => f.onset && f.onsetT != null && f.onsetT >= from - 0.03 && f.onsetT <= to && !used.has(f.onsetT))
      .map(f => f.onsetT);
    if (target.needsOnset) {
      // The same pitch may still ring from the note before: what counts is an
      // attack in the window followed by the note.
      for (const on of onsets) {
        let k = 0;
        for (const f of frames) {
          if (f.t < on) continue;
          if (f.t > on + 0.12) break;
          if (Number.isFinite(f.midi) && pitchError(target, f.midi) <= CENTS_OK) { if (++k >= STABLE_FRAMES) break; } else k = 0;
        }
        if (k >= STABLE_FRAMES) { used.add(on); return { result: 'hit', dt: on - target.time, heard: null }; }
      }
      if (hitAt != null) return { result: 'miss', dt: null, heard: null, reason: 'no_attack' };
    } else if (hitAt != null) {
      // The attack just before the pitch settled is when it was played.
      let on = null;
      for (const o of onsets) if (o <= hitAt + 0.03 && o >= hitAt - 0.08 && (on == null || o > on)) on = o;
      if (on != null) used.add(on);
      return { result: 'hit', dt: (on != null ? on : hitAt - pitchLag) - target.time, heard: null };
    }
    // The note before may still ring here: its pitch is no wrong note unless it was played again.
    const ringing = target.prevMidi != null && !onsets.length ? Math.round(target.prevMidi) : null;
    let heard = null, most = 0;
    for (const [k, c] of heardCounts) if (k !== ringing && c > most) { most = c; heard = k; }
    if (heard != null && most >= STABLE_FRAMES) return { result: 'wrong', dt: null, heard };
    return { result: 'miss', dt: null, heard: null };
  }

  // Running totals over the judged notes.
  function practiceStats(results) {
    let hits = 0, wrong = 0, miss = 0, sumDt = 0, streak = 0, best = 0;
    for (const r of results) {
      if (r.result === 'hit') { hits++; sumDt += r.dt; streak++; if (streak > best) best = streak; }
      else { streak = 0; if (r.result === 'wrong') wrong++; else miss++; }
    }
    const judged = hits + wrong + miss;
    return {
      judged, hits, wrong, miss, streak, best,
      percent: judged ? Math.round(100 * hits / judged) : 0,
      meanDt: hits ? sumDt / hits : null,
    };
  }

  // The latency a calibration measured: each attack heard against the click it
  // answered (`clicks` and `onsets` in the same clock), the median of the
  // differences that make sense (an attack within 0.45 s after its click).
  function calibrate(clicks, onsets) {
    const diffs = [];
    for (const c of clicks) {
      let best = null;
      for (const o of onsets) {
        const d = o - c;
        if (d >= -0.02 && d <= 0.45 && (best == null || d < best)) best = d;
      }
      if (best != null) diffs.push(best);
    }
    if (diffs.length < Math.max(3, Math.ceil(clicks.length / 2))) return null;
    diffs.sort((a, b) => a - b);
    const med = diffs[Math.floor(diffs.length / 2)];
    const spread = diffs[Math.floor(diffs.length * 0.8)] - diffs[Math.floor(diffs.length * 0.2)];
    return { latency: med, spread, count: diffs.length };
  }

  const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
  function midiName(m) {
    const r = Math.round(m);
    return NOTE_NAMES[((r % 12) + 12) % 12] + (Math.floor(r / 12) - 1);
  }

  const api = {
    createTracker, practiceTargets, judgeTarget, judgeChord, chordNotesHeard, pitchError, practiceStats, calibrate, midiName,
    EARLY_S, LATE_S, CENTS_OK,
  };
  root.PracticeCore = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
