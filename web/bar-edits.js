// Bars and beats inserted into or removed from a chart's grid — the viewer's
// copy of src/rockforge/domain/bar_edits.py (edit_grid), on the grid as the
// score shows it. The build resolves the same edit on its own grid; the viewer
// needs the same answer to send its other pending edits (notes, hand
// positions, sections, tone changes, lyrics) where they land after it. Pure
// code: it runs on the page and under Node (tests/web/bar-edits.test.js), and
// the two implementations are held to the same answers there and in
// tests/test_bar_edits.py.
(function (root) {
  'use strict';

  const EDGE_S = 0.001;

  // grid: [{time, measure}] (measure > 0 on a downbeat, -1 elsewhere; the last
  // downbeat is the closing bar line).
  function barSpan(grid, number) {
    const downs = [];
    grid.forEach((b, i) => { if (b.measure > 0) downs.push(i); });
    for (let k = 0; k < downs.length - 1; k++) {
      if (grid[downs[k]].measure === number) return [downs[k], downs[k + 1]];
    }
    throw new Error('no bar ' + number);
  }

  function renumber(grid, first) {
    let n = first;
    return grid.map(b => (b.measure > 0 ? { time: b.time, measure: n++ } : b));
  }

  function moved(grid, step, keepFrom) {
    const shift = step.insert ? step.length : -step.length;
    return grid.filter(b => b.time < step.start - EDGE_S)
      .concat(grid.filter(b => b.time >= keepFrom - EDGE_S)
        .map(b => ({ time: b.time + shift, measure: b.measure })));
  }

  function oneStep(grid, edit) {
    const downs = grid.filter(b => b.measure > 0);
    if (downs.length < 2) throw new Error('no complete bar');
    const first = downs[0].measure;
    if (edit.op === 'insert_bar') {
      const number = edit.bar > 0 ? edit.bar : first;
      const [s, e] = barSpan(grid, number);
      const length = grid[e].time - grid[s].time;
      const start = edit.bar > 0 ? grid[e].time : grid[s].time;
      const step = { start, length, insert: true };
      const add = grid.slice(s, e).map((b, k) => ({ time: start + b.time - grid[s].time, measure: k === 0 ? 1 : -1 }));
      const m = moved(grid, step, start);
      const cut = m.filter(b => b.time < start - EDGE_S).length;
      return { grid: renumber(m.slice(0, cut).concat(add, m.slice(cut)), first), step };
    }
    if (edit.op === 'remove_bar') {
      if (downs.length < 3) throw new Error('only bar');
      const [s, e] = barSpan(grid, edit.bar);
      const step = { start: grid[s].time, length: grid[e].time - grid[s].time, insert: false };
      return { grid: renumber(moved(grid, step, grid[e].time), first), step };
    }
    const [s, e] = barSpan(grid, edit.bar);
    const inside = grid.slice(s, e);
    const beat = edit.beat || 1;
    if (beat > inside.length) throw new Error('no beat ' + beat);
    const k = beat - 1;
    const here = inside[k].time;
    const next = k + 1 < inside.length ? inside[k + 1].time : grid[e].time;
    if (edit.op === 'insert_beat') {
      const step = { start: next, length: next - here, insert: true };
      const m = moved(grid, step, next);
      const cut = m.filter(b => b.time < next - EDGE_S).length;
      return { grid: m.slice(0, cut).concat([{ time: next, measure: -1 }], m.slice(cut)), step };
    }
    if (inside.length < 2) throw new Error('single beat');
    const step = { start: here, length: next - here, insert: false };
    const m = moved(grid, step, next);
    if (k === 0) {
      const cut = m.filter(b => b.time < here - EDGE_S).length;
      m[cut] = { time: m[cut].time, measure: edit.bar };
    }
    return { grid: m, step };
  }

  // {grid, steps} after the edit (repeated `count` times), or throws.
  function editGrid(grid, edit) {
    let g = grid.slice();
    const steps = [];
    for (let i = 0; i < (edit.count || 1); i++) {
      const r = oneStep(g, edit);
      g = r.grid;
      steps.push(r.step);
    }
    return { grid: g, steps };
  }

  // How a moment moves through the steps: `end` for a moment something stops
  // (a sustain's end), `drops` for one that goes with a removed stretch.
  function stepAt(step, t) {
    if (step.insert) return t >= step.start - EDGE_S ? t + step.length : t;
    if (t < step.start - EDGE_S) return t;
    if (t < step.start + step.length - EDGE_S) return step.start;
    return t - step.length;
  }
  function stepEnd(step, t) {
    if (step.insert) return t > step.start + EDGE_S ? t + step.length : t;
    if (t <= step.start + EDGE_S) return t;
    if (t <= step.start + step.length + EDGE_S) return step.start;
    return t - step.length;
  }
  function stepDrops(step, t) {
    return !step.insert && t >= step.start - EDGE_S && t < step.start + step.length - EDGE_S;
  }
  // The steps of several edits as one map.
  function timeMap(steps) {
    return {
      at: t => steps.reduce((x, s) => stepAt(s, x), t),
      end: t => steps.reduce((x, s) => stepEnd(s, x), t),
      drops: t => {
        let x = t;
        for (const s of steps) {
          if (stepDrops(s, x)) return true;
          x = stepAt(s, x);
        }
        return false;
      },
    };
  }

  const api = { editGrid, timeMap, EDGE_S };
  root.BarEdits = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
