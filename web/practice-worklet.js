// Practice mode's audio thread: the guitar's input goes through the tracker
// (practice-core.js, added to the same worklet first, so PracticeCore is in
// this scope) and the readings go to the page in batches, each stamped in the
// AudioContext's clock — the clock the playback runs on.
/* global sampleRate, currentTime, registerProcessor, AudioWorkletProcessor */
class PracticeProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const o = (options && options.processorOptions) || {};
    this.tracker = PracticeCore.createTracker(sampleRate, { minHz: o.minHz });
    this.seen = 0;       // input samples processed
    this.base = 0;       // this.seen when the tracker started (its sample 0)
    this.batch = [];
    this.specs = [];     // [ctxTime of the window's middle, magnitudes] for the chords
    this.port.postMessage({ type: 'ready', pitchLag: this.tracker.pitchLagS });
    this.port.onmessage = e => {
      if (e.data && e.data.type === 'range') {
        this.tracker = PracticeCore.createTracker(sampleRate, { minHz: e.data.minHz });
        this.base = this.seen;
        this.port.postMessage({ type: 'ready', pitchLag: this.tracker.pitchLagS });
      }
    };
  }

  process(inputs) {
    // With nothing connected the input has no channels: the tracker is fed
    // silence, so its sample count stays the block count and the stamps right.
    const ch = (inputs[0] && inputs[0][0]) || (this.zeros ||= new Float32Array(128));
    const n = ch.length;
    // The block that starts at currentTime holds the samples seen .. seen + n;
    // the tracker counts its samples from its own start (base).
    const t0 = currentTime - (this.seen - this.base) / sampleRate;
    for (const f of this.tracker.process(ch)) {
      this.batch.push([
        t0 + f.t / sampleRate, f.midi, f.rms, f.onset ? t0 + f.onsetT / sampleRate : null,
      ]);
      if (f.spec) this.specs.push([t0 + f.specT / sampleRate, f.spec]);
    }
    this.seen += n;
    if (this.batch.length >= 4) {
      const spectra = this.specs;
      this.port.postMessage({ type: 'frames', frames: this.batch, spectra, df: this.tracker.specDf, now: currentTime },
        spectra.map(sp => sp[1].buffer));
      this.batch = []; this.specs = [];
    }
    return true;
  }
}
registerProcessor('rockforge-practice', PracticeProcessor);
