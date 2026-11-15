// The time-stretcher behind slowed playback that keeps the pitch
// (web/stretch-worklet.js), on invented signals: steady tones, tone bursts at
// known instants. Run with `npm test`.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const S = require('../../web/stretch-worklet.js');

const SR = 44100;

function tone(seconds, hz, amp = 0.5) {
  const x = new Float32Array(Math.round(seconds * SR));
  for (let i = 0; i < x.length; i++) x[i] = amp * Math.sin(2 * Math.PI * hz * i / SR);
  return x;
}

function stretch(channels, opts, seconds, outChannels = channels.length) {
  const st = S.createStretcher(channels, SR, opts);
  const n = Math.round(seconds * SR);
  const out = Array.from({ length: outChannels }, () => new Float32Array(n));
  for (let k = 0; k < n; k += 128) st.render(out, k, Math.min(128, n - k));
  return out;
}

// Frequency from the rising zero crossings of x[from..to).
function frequency(x, from, to) {
  let first = -1, last = -1, count = 0;
  for (let i = from + 1; i < to; i++) {
    if (x[i - 1] < 0 && x[i] >= 0) {
      if (first < 0) first = i; else count++;
      last = i;
    }
  }
  return count / ((last - first) / SR);
}

function rms(x, from, to) {
  let s = 0;
  for (let i = from; i < to; i++) s += x[i] * x[i];
  return Math.sqrt(s / (to - from));
}

test('slowed down, a tone keeps its pitch', () => {
  for (const rate of [0.5, 0.75, 0.9]) {
    const [out] = stretch([tone(6, 440)], { pos: 0.5, rate }, 3);
    const f = frequency(out, Math.round(0.1 * SR), Math.round(2.9 * SR));
    assert.ok(Math.abs(f - 440) < 2, `rate ${rate}: ${f.toFixed(1)} Hz`);
  }
});

test('a steady tone stays steady: the frames join without cancelling', () => {
  for (const rate of [0.5, 0.75]) {
    const [out] = stretch([tone(6, 330)], { pos: 0, rate }, 3);
    const w = Math.round(0.01 * SR);
    const mean = rms(out, Math.round(0.1 * SR), Math.round(2.9 * SR));
    for (let i = Math.round(0.1 * SR); i + w < Math.round(2.9 * SR); i += w) {
      const r = rms(out, i, i + w);
      assert.ok(Math.abs(r - mean) / mean < 0.1, `rate ${rate} at ${(i / SR).toFixed(2)} s: ${r} vs ${mean}`);
    }
    assert.ok(Math.abs(mean - 0.5 / Math.SQRT2) < 0.03, `level ${mean}`);
  }
});

test('what plays at each instant is where the clock says: start + elapsed × speed', () => {
  // A burst every 0.4 s, each at its own pitch, over silence.
  const x = new Float32Array(10 * SR);
  const bursts = [];
  for (let t = 0.3, i = 0; t < 9.5; t += 0.4, i++) {
    const at = Math.round(t * SR), hz = 300 + 40 * (i % 7);
    for (let k = 0; k < 0.12 * SR; k++) x[at + k] = 0.6 * Math.exp(-k / (0.03 * SR)) * Math.sin(2 * Math.PI * hz * k / SR);
    bursts.push(t);
  }
  for (const rate of [0.5, 0.75]) {
    const pos = 1.25;
    const seconds = 5;
    const [out] = stretch([x], { pos, rate }, seconds);
    // Each burst's onset in the output: the first 5 ms window loud again after silence.
    const w = Math.round(0.005 * SR);
    const onsets = [];
    let quiet = true;
    for (let i = 0; i + w < out.length; i += w) {
      const r = rms(out, i, i + w);
      if (quiet && r > 0.05) { onsets.push(i / SR); quiet = false; } else if (r < 0.005) quiet = true;
    }
    const expected = bursts.filter(t => t > pos + 0.01 && (t - pos) / rate < seconds - 0.2).map(t => (t - pos) / rate);
    assert.equal(onsets.length, expected.length, `rate ${rate}: ${onsets} vs ${expected}`);
    // In seconds of the recording, as the cursor reads them.
    onsets.forEach((t, i) => assert.ok(Math.abs(t - expected[i]) * rate < 0.01, `rate ${rate}: ${t} vs ${expected[i]}`));
  }
});

test('it starts where it is asked to, and a mono recording reaches both outputs', () => {
  const x = new Float32Array(4 * SR);
  x.set(tone(2, 220).subarray(0), 0);
  x.set(tone(2, 660), 2 * SR);
  const [l, r] = stretch([x], { pos: 2.2, rate: 0.5 }, 1, 2);
  assert.ok(Math.abs(frequency(l, Math.round(0.05 * SR), Math.round(0.9 * SR)) - 660) < 3);
  assert.deepEqual(r, l);
});

test('past the end it says so and plays silence', () => {
  const st = S.createStretcher([tone(0.5, 440)], SR, { pos: 0.3, rate: 0.5 });
  const out = [new Float32Array(SR)];
  st.render(out, 0, SR);
  assert.ok(st.ended);
  assert.ok(rms(out[0], Math.round(0.6 * SR), SR) === 0);
});
