// Slowed playback that keeps the pitch ("Ao abrandar, manter o tom"). An
// AudioBufferSourceNode played below 1x lowers the pitch with the speed, which
// is in the way of exactly the listening this playback is slowed down for. Here
// the recording is time-stretched on the audio thread by WSOLA (Verhelst &
// Roelands 1993, "An overlap-add technique based on waveform similarity"):
// Hann-windowed frames of 40 ms laid 20 ms apart in the output, each taken from
// the recording 20 ms × speed after the previous one, moved by up to 12 ms to
// where the recording most resembles the natural continuation of the frame
// before — so the waveforms join without phase jumps. Every frame advances the
// read position by exactly hop × speed, so the read position never drifts from
// the recording's clock: at output sample j it is start + j × speed, within a
// frame (the tolerance), which is what keeps the cursor, the notes and the ticks
// (all on start + elapsed × speed) where the music is.
//
// The stretcher is pure code (no Web Audio), so it runs under Node too
// (tests/web/stretch.test.js). The processor part registers only in the worklet.
// The recording is sent once per decoded buffer to a "keeper" processor and kept
// in this scope's STORE: processors added by one worklet share its globals, so
// the node of each play — one per play/seek, so a seek crossfades like the
// buffer source did — only names it.
/* global sampleRate, currentTime, registerProcessor, AudioWorkletProcessor */
(function (root) {
  'use strict';

  const HOP_S = 0.02;        // synthesis hop; frames are twice as long, 50% overlap
  const SEEK_S = 0.012;      // how far a frame may move to match the one before

  // channels: Float32Array per channel (1 or more, same length). pos: where to
  // start, in seconds of the recording. rate: speed (0.5 = half speed).
  // A class, not closures: a new stretcher starts on every play and every seek,
  // and closures made per instance each started cold in V8 (three times slower
  // than the first instance, measured); methods share one prototype.
  class Stretcher {
    constructor(channels, sr, rate, pos) {
      this.channels = channels;
      this.len = channels[0].length;
      this.nch = channels.length;
      this.c0 = channels[0];
      this.c1 = this.nch > 1 ? channels[1] : null;
      this.sr = sr;
      this.rate = rate;
      const hs = Math.max(32, Math.round(sr * HOP_S));
      this.hs = hs;
      this.n = 2 * hs;
      this.seek = Math.max(2, Math.round(sr * SEEK_S));
      this.win = new Float32Array(this.n);
      // Periodic Hann: at 50% overlap the windows add up to exactly 1.
      for (let i = 0; i < this.n; i++) this.win[i] = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / this.n);
      this.acc = channels.map(() => new Float32Array(this.n));
      this.pend = channels.map(() => new Float32Array(hs));
      this.pendRead = hs;
      // Each frame's middle sits where the clock says: a sound inside the frame
      // then plays early in its second half and late in its first, never early
      // all through (from the frame's start it would be up to a frame early).
      this.nominal = pos * sr - hs * (1 - rate);
      this.natural = -1;       // where the previous frame would naturally go on
      this.lastStart = 0;
    }

    // How well the `hs` samples from `s` match the natural continuation of the
    // previous frame: normalised cross-correlation of the channels' sum, every
    // 4th sample (the precision a 20 ms overlap needs).
    score(s) {
      const { c0, c1, len, hs, natural } = this;
      let xy = 0, yy = 0;
      for (let i = 0; i < hs; i += 4) {
        const ka = natural + i, kb = s + i;
        const a = ka < len ? (c1 ? c0[ka] + c1[ka] : c0[ka]) : 0;
        const b = kb < len ? (c1 ? c0[kb] + c1[kb] : c0[kb]) : 0;
        xy += a * b; yy += b * b;
      }
      return yy > 1e-12 ? xy / Math.sqrt(yy) : 0;
    }

    bestStart(start) {
      if (this.natural < 0) return start;
      let best = start, top = start >= 0 ? this.score(start) : -Infinity;
      for (let d = -this.seek; d <= this.seek; d += 2) {
        const s = start + d;
        if (d === 0 || s < 0) continue;
        const v = this.score(s);
        if (v > top + 1e-9) { top = v; best = s; }
      }
      return best;
    }

    frame() {
      const s = this.bestStart(Math.round(this.nominal));
      const { hs, n, len, win } = this;
      this.lastStart = s;
      for (let c = 0; c < this.nch; c++) {
        const x = this.channels[c], a = this.acc[c];
        const lo = Math.max(0, -s), hi = Math.min(n, len - s);
        for (let i = lo; i < hi; i++) a[i] += x[s + i] * win[i];
        this.pend[c].set(a.subarray(0, hs));
        a.copyWithin(0, hs);
        a.fill(0, hs);
      }
      this.natural = s + hs;
      this.nominal += hs * this.rate;
      this.pendRead = 0;
    }

    // Writes `count` samples into each of `out` (Float32Array per output channel)
    // from `offset`; a mono recording goes to every output channel.
    render(out, offset, count) {
      const last = this.nch - 1;
      for (let k = 0; k < count; k++) {
        if (this.pendRead >= this.hs) this.frame();
        for (let oc = 0; oc < out.length; oc++) {
          out[oc][offset + k] = this.pend[oc < last ? oc : last][this.pendRead];
        }
        this.pendRead++;
      }
    }

    get hop() { return this.hs; }
    // Past the end of the recording, with the last frame played out.
    get ended() { return this.lastStart >= this.len; }
    // Where the read position is, in seconds of the recording.
    get position() { return this.nominal / this.sr; }
  }

  function createStretcher(channels, sr, { pos = 0, rate = 1 } = {}) {
    return new Stretcher(channels, sr, rate, pos);
  }

  const api = { createStretcher, HOP_S, SEEK_S };
  root.StretchCore = api;
  if (typeof module === 'object' && module.exports) module.exports = api;

  if (typeof registerProcessor === 'function') {
    const STORE = new Map();   // recording id → channels, shared by every node
    class StretchProcessor extends AudioWorkletProcessor {
      constructor(options) {
        super();
        const o = (options && options.processorOptions) || {};
        this.keeper = !!o.keeper;
        this.id = o.id;
        this.pos = o.pos || 0;
        this.rate = o.rate || 1;
        this.when = o.when || 0;
        this.stopAt = Infinity;
        this.st = null;
        this.endedSent = false;
        this.port.onmessage = e => {
          const d = e.data || {};
          if (d.type === 'data') STORE.set(d.id, d.channels);
          else if (d.type === 'free') STORE.delete(d.id);
          else if (d.type === 'stop') this.stopAt = d.at;
        };
      }

      process(inputs, outputs) {
        if (this.keeper) return true;
        const out = outputs[0];
        for (const ch of out) ch.fill(0);
        if (currentTime >= this.stopAt) return false;
        const n = out[0].length;
        let k0 = Math.ceil((this.when - currentTime) * sampleRate);
        if (k0 >= n) return true;
        k0 = Math.max(0, k0);
        if (!this.st) {
          const data = STORE.get(this.id);
          if (!data) return true;
          // Late data keeps the clock: start where the recording is by now.
          const late = Math.max(0, currentTime + k0 / sampleRate - this.when);
          this.st = StretchCore.createStretcher(data, sampleRate, { pos: this.pos + late * this.rate, rate: this.rate });
        }
        this.st.render(out, k0, n - k0);
        if (this.st.ended && !this.endedSent) {
          this.endedSent = true;
          this.port.postMessage({ type: 'ended' });
        }
        return true;
      }
    }
    registerProcessor('rf-stretch', StretchProcessor);
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
