// The viewer's copy of the bar/beat edits (web/bar-edits.js) gives the same
// answers as the build's (src/rockforge/domain/bar_edits.py): the same cases as
// tests/test_bar_edits.py. Run with `npm test`.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const B = require('../../web/bar-edits.js');

function grid(bars = 3, beats = 4, start = 2.0, beatS = 0.5) {
  const g = [];
  for (let b = 0; b < bars; b++) {
    for (let k = 0; k < beats; k++) g.push({ time: start + (b * beats + k) * beatS, measure: k === 0 ? b + 1 : -1 });
  }
  g.push({ time: start + bars * beats * beatS, measure: bars + 1 });
  return g;
}
const shape = g => g.map(b => [Math.round(b.time * 1e6) / 1e6, b.measure]);
const steps = r => r.steps.map(s => [Math.round(s.start * 1e6) / 1e6, Math.round(s.length * 1e6) / 1e6, s.insert]);

test('a bar inserted after a bar copies its beats and moves what follows', () => {
  const g = grid().slice(0, 4).concat(
    [{ time: 4.0, measure: 2 }, { time: 4.6, measure: -1 }, { time: 5.2, measure: -1 }],
    [0, 1, 2, 3].map(k => ({ time: 5.8 + 0.5 * k, measure: k === 0 ? 3 : -1 })),
    [{ time: 7.8, measure: 4 }]);
  const r = B.editGrid(g, { op: 'insert_bar', bar: 2 });
  assert.deepEqual(steps(r), [[5.8, 1.8, true]]);
  assert.deepEqual(shape(r.grid).slice(4, 12), [
    [4.0, 2], [4.6, -1], [5.2, -1], [5.8, 3], [6.4, -1], [7.0, -1], [7.6, 4], [8.1, -1]]);
  assert.deepEqual(shape(r.grid).at(-1), [9.6, 5]);
});

test('a bar inserted before bar 1 takes bar 1\'s length', () => {
  const r = B.editGrid(grid(), { op: 'insert_bar', bar: 0, count: 2 });
  assert.deepEqual(steps(r), [[2, 2, true], [2, 2, true]]);
  assert.deepEqual(r.grid.filter(b => b.measure > 0).map(b => b.measure), [1, 2, 3, 4, 5, 6]);
});

test('a removed bar brings the rest back by its length', () => {
  const r = B.editGrid(grid(), { op: 'remove_bar', bar: 2 });
  assert.deepEqual(steps(r), [[4, 2, false]]);
  assert.deepEqual(shape(r.grid), [[2, 1], [2.5, -1], [3, -1], [3.5, -1], [4, 2], [4.5, -1], [5, -1], [5.5, -1], [6, 3]]);
});

test('a beat inserted or removed changes only its bar', () => {
  const added = B.editGrid(grid(), { op: 'insert_beat', bar: 1, beat: 4 });
  assert.deepEqual(steps(added), [[4, 0.5, true]]);
  assert.deepEqual(shape(added.grid).slice(0, 6), [[2, 1], [2.5, -1], [3, -1], [3.5, -1], [4, -1], [4.5, 2]]);
  const gone = B.editGrid(grid(), { op: 'remove_beat', bar: 2, beat: 1 });
  assert.deepEqual(steps(gone), [[4, 0.5, false]]);
  assert.deepEqual(shape(gone.grid).slice(3, 8), [[3.5, -1], [4, 2], [4.5, -1], [5, -1], [5.5, 3]]);
});

test('an edit that names nothing is refused', () => {
  for (const e of [{ op: 'remove_bar', bar: 9 }, { op: 'insert_beat', bar: 1, beat: 5 }, { op: 'insert_bar', bar: 4 }]) {
    assert.throws(() => B.editGrid(grid(), e));
  }
  assert.throws(() => B.editGrid(grid(1), { op: 'remove_bar', bar: 1 }));
});

test('the time map moves starts, ends and drops like the build', () => {
  const ins = B.timeMap(B.editGrid(grid(), { op: 'insert_bar', bar: 1 }).steps);
  assert.equal(ins.at(3.5), 3.5);
  assert.equal(ins.at(4.0), 6.0);
  assert.equal(ins.end(4.0), 4.0);   // a note ending on the line is not stretched
  assert.equal(ins.end(4.5), 6.5);
  const rem = B.timeMap(B.editGrid(grid(), { op: 'remove_bar', bar: 2 }).steps);
  assert.ok(rem.drops(4.0) && rem.drops(5.9) && !rem.drops(6.0) && !rem.drops(3.9));
  assert.equal(rem.at(6.0), 4.0);
  assert.equal(rem.end(4.5), 4.0);   // cut where the removed bar began
  assert.equal(rem.end(7.0), 5.0);
});
