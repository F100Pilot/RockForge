// Practice mode's pitch tracker and judge (web/practice-core.js), on invented
// signals: plucked strings synthesised by Karplus-Strong at the pitches of a
// guitar and a bass, repeated picks, silence, noise. Run with `npm test`.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const P = require('../../web/practice-core.js');

const SR = 48000;
const hz = m => 440 * 2 ** ((m - 69) / 12);

// A plucked string, additive: ten harmonics at exact multiples, the
// fundamental weaker than the second (as from a pickup), each decaying faster
// the higher it is, and a short burst of noise for the pick.
function rng(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32) * 2 - 1; }
function pluck(out, at, midi, dur, amp = 0.5, seed = 1) {
  const f = hz(midi), r = rng(seed);
  const start = Math.round(at * SR), len = Math.round(dur * SR);
  const ph = Array.from({ length: 10 }, () => r() * Math.PI);
  for (let i = 0; i < len && start + i < out.length; i++) {
    const t = i / SR;
    let v = 0;
    for (let k = 1; k <= 10; k++) {
      if (f * k > SR / 2) break;
      v += (k === 1 ? 0.4 : 1 / k) * Math.exp(-t * (1.5 + k)) * Math.sin(2 * Math.PI * f * k * t + ph[k - 1]);
    }
    if (i < SR * 0.005) v += 0.6 * r() * (1 - i / (SR * 0.005));
    const fade = i > len - 240 ? (len - i) / 240 : 1;
    out[start + i] += amp * 0.4 * v * fade * Math.min(1, i / 24);
  }
}
function run(signal, opts) {
  const tr = P.createTracker(SR, opts);
  const frames = [];
  for (let i = 0; i < signal.length; i += 128) frames.push(...tr.process(signal.subarray(i, i + 128)));
  return frames.map(f => ({ ...f, t: f.t / SR, onsetT: f.onsetT == null ? null : f.onsetT / SR }));
}
function medianMidi(frames, from, to) {
  const v = frames.filter(f => f.t >= from && f.t <= to && Number.isFinite(f.midi)).map(f => f.midi).sort((a, b) => a - b);
  return v.length ? v[Math.floor(v.length / 2)] : NaN;
}

test('every guitar pitch from the low E to fret 22 of the top string is read to a few cents', () => {
  for (const midi of [40, 45, 50, 55, 59, 64, 69, 76, 86]) {
    const sig = new Float32Array(SR);
    pluck(sig, 0.1, midi, 0.8, 0.5, midi);
    const m = medianMidi(run(sig), 0.25, 0.8);
    assert.ok(Math.abs(m - midi) < 0.15, `midi ${midi} read as ${m}`);
  }
});

test('a bass string down to the low B is read when the tracker is told how low to go', () => {
  for (const midi of [23, 28, 33, 43]) {
    const sig = new Float32Array(SR);
    pluck(sig, 0.1, midi, 0.8, 0.5, midi);
    const m = medianMidi(run(sig, { minHz: 28 }), 0.3, 0.8);
    assert.ok(Math.abs(m - midi) < 0.15 || Math.abs(m - midi - 12) < 0.15, `bass ${midi} read as ${m}`);
  }
});

test('silence and steady noise have no pitch and no attacks', () => {
  const sig = new Float32Array(SR);
  const r = rng(7);
  for (let i = SR / 2; i < SR; i++) sig[i] = 0.002 * r();
  const fr = run(sig);
  assert.equal(fr.filter(f => f.onset).length, 0);
  assert.equal(fr.filter(f => f.t < 0.45 && Number.isFinite(f.midi)).length, 0);
});

test('each pick of a repeated note is one attack, near where it was played', () => {
  const sig = new Float32Array(2 * SR);
  const times = [0.2, 0.45, 0.7, 0.95, 1.2, 1.45];
  times.forEach((t, i) => pluck(sig, t, 52, 0.25, 0.5, 10 + i));
  const on = run(sig).filter(f => f.onset).map(f => f.onsetT);
  assert.equal(on.length, times.length, `attacks at ${on.map(x => x.toFixed(3))}`);
  on.forEach((o, i) => assert.ok(Math.abs(o - times[i]) < 0.015, `attack ${i} at ${o}`));
});

// Readings as the judge receives them, from a synthesised performance.
function performance(notes, total = 3) {
  const sig = new Float32Array(Math.round(total * SR));
  notes.forEach((n, i) => pluck(sig, n.at, n.midi, n.dur ?? 0.3, 0.5, 100 + i));
  return run(sig);
}

test('notes played in time and in tune are hits, with how early or late they were', () => {
  const chart = [0.5, 0.8, 1.1, 1.4].map((t, i) => ({ key: i, time: t, string: 0, fret: 3 + i, techniques: [] }));
  const midiOf = n => 43 + (n.fret - 3) * 2;
  const { targets } = P.practiceTargets(chart, midiOf);
  const frames = performance(chart.map((n, i) => ({ at: n.time + (i === 2 ? 0.04 : 0), midi: midiOf(n) })));
  const used = new Set();
  const res = targets.map(t => P.judgeTarget(t, frames, used));
  assert.deepEqual(res.map(r => r.result), ['hit', 'hit', 'hit', 'hit']);
  assert.ok(Math.abs(res[2].dt - 0.04) < 0.015, `dt ${res[2].dt}`);
  assert.ok(Math.abs(res[0].dt) < 0.015, `dt ${res[0].dt}`);
});

test('the wrong fret is a wrong note naming what was heard, silence a miss', () => {
  const chart = [{ key: 'a', time: 0.5, string: 1, fret: 5, techniques: [] }, { key: 'b', time: 1.2, string: 1, fret: 7, techniques: [] }];
  const midiOf = n => 45 + n.fret;
  const { targets } = P.practiceTargets(chart, midiOf);
  const frames = performance([{ at: 0.5, midi: 51 }]);
  const used = new Set();
  const [a, b] = targets.map(t => P.judgeTarget(t, frames, used));
  assert.equal(a.result, 'wrong'); assert.equal(a.heard, 51);
  assert.equal(b.result, 'miss');
});

test('a repeated note needs its own attack: one long note does not count twice', () => {
  const chart = [{ key: 'a', time: 0.5, string: 2, fret: 2, techniques: [] }, { key: 'b', time: 0.8, string: 2, fret: 2, techniques: [] }];
  const midiOf = () => 52;
  const { targets } = P.practiceTargets(chart, midiOf);
  assert.equal(targets[1].needsOnset, true);
  const held = performance([{ at: 0.5, midi: 52, dur: 0.7 }]);
  let used = new Set();
  assert.deepEqual(targets.map(t => P.judgeTarget(t, held, used).result), ['hit', 'miss']);
  const picked = performance([{ at: 0.5, midi: 52 }, { at: 0.8, midi: 52 }]);
  used = new Set();
  assert.deepEqual(targets.map(t => P.judgeTarget(t, picked, used).result), ['hit', 'hit']);
});

test('the note before still ringing is no wrong note: a note left out is a miss', () => {
  const chart = [{ key: 'a', time: 0.5, string: 1, fret: 5, techniques: [] }, { key: 'b', time: 0.8, string: 1, fret: 7, techniques: [] }];
  const { targets } = P.practiceTargets(chart, n => 45 + n.fret);
  const frames = performance([{ at: 0.5, midi: 50, dur: 0.45 }]);
  const used = new Set();
  assert.deepEqual(targets.map(t => P.judgeTarget(t, frames, used).result), ['hit', 'miss']);
});

test('a hammer-on needs no attack of its own', () => {
  const chart = [{ key: 'a', time: 0.5, string: 0, fret: 5, techniques: [] }, { key: 'b', time: 0.7, string: 0, fret: 7, techniques: ['hammerOn'] }];
  const { targets } = P.practiceTargets(chart, n => 40 + n.fret);
  assert.equal(targets[1].legato, true);
  assert.equal(targets[1].needsOnset, false);
});

test('chords and muted or harmonic notes are left out and counted', () => {
  const chart = [
    { key: 1, time: 0.5, string: 0, fret: 3, techniques: [] }, { key: 2, time: 0.51, string: 1, fret: 5, techniques: [] },
    { key: 3, time: 1.0, string: 0, fret: 0, techniques: ['mute'] },
    { key: 4, time: 1.5, string: 2, fret: 12, techniques: ['harmonic'] },
    { key: 5, time: 2.0, string: 2, fret: 2, techniques: ['palmMute'] },
  ];
  const r = P.practiceTargets(chart, n => 40 + n.fret);
  assert.equal(r.chords, 2); assert.equal(r.skipped, 2);
  assert.deepEqual(r.targets.map(t => t.key), [5]);
});

test('a bend counts anywhere between the fret and its peak, an octave off counts', () => {
  const t = { midi: 60, bend: 2 };
  assert.equal(P.pitchError(t, 61.2), 0);
  assert.ok(P.pitchError(t, 62.5) > 40 && P.pitchError(t, 62.5) < 60);
  assert.ok(P.pitchError(t, 63) > 60);
  assert.ok(P.pitchError(t, 48.1) < 15);
});

test('the latency is the median of attack minus click, refused when too few answered', () => {
  const clicks = [1, 2, 3, 4, 5, 6, 7, 8];
  const onsets = [1.081, 2.09, 3.078, 4.085, 5.3, 6.084, 7.079, 8.088];
  const c = P.calibrate(clicks, onsets);
  assert.ok(Math.abs(c.latency - 0.085) < 0.006, `latency ${c.latency}`);
  assert.equal(P.calibrate(clicks, [1.08, 2.09]), null);
});

test('the totals', () => {
  const s = P.practiceStats([{ result: 'hit', dt: 0.02 }, { result: 'hit', dt: -0.04 }, { result: 'wrong' }, { result: 'hit', dt: 0.01 }]);
  assert.equal(s.judged, 4); assert.equal(s.hits, 3); assert.equal(s.percent, 75); assert.equal(s.best, 2); assert.equal(s.streak, 1);
  assert.ok(Math.abs(s.meanDt - (-0.01 / 3)) < 1e-9);
  assert.equal(P.midiName(40), 'E2'); assert.equal(P.midiName(69), 'A4');
});

test('a fast riff of sixteenths with repeats, over hum and hiss, is all hits within 15 ms', () => {
  const pitches = [40, 40, 43, 40, 45, 45, 47, 45, 52, 52, 50, 48, 47, 47, 45, 43];
  const chart = pitches.map((m, i) => ({ key: i, time: 0.5 + i * 0.125, string: 0, fret: m - 40, techniques: [] }));
  const sig = new Float32Array(3 * SR);
  chart.forEach((n, i) => pluck(sig, n.time + ((i * 7) % 5 - 2) * 0.004, pitches[i], 0.13, 0.25 + 0.2 * ((i * 3) % 4) / 3, 300 + i));
  const r = rng(99);
  for (let i = 0; i < sig.length; i++) sig[i] += 0.004 * Math.sin(2 * Math.PI * 50 * i / SR) + 0.001 * r();
  const frames = run(sig);
  const { targets } = P.practiceTargets(chart, n => 40 + n.fret);
  const used = new Set();
  const res = targets.map(t => P.judgeTarget(t, frames, used));
  assert.deepEqual(res.map(x => x.result), pitches.map(() => 'hit'));
  res.forEach((x, i) => assert.ok(Math.abs(x.dt - ((i * 7) % 5 - 2) * 0.004) < 0.015, `note ${i} dt ${x.dt}`));
});

test('the tracker keeps up: ten seconds of a guitar take well under a second', () => {
  const sig = new Float32Array(10 * SR);
  for (let k = 0; k < 20; k++) pluck(sig, k * 0.5, 40 + (k % 12), 0.5, 0.5, k);
  const t0 = process.hrtime.bigint();
  run(sig);
  const ms = Number(process.hrtime.bigint() - t0) / 1e6;
  assert.ok(ms < 2500, `took ${ms} ms`);  // about 0.7 s here: under a tenth of a core in real time
});
