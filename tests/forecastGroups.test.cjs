const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
const Module = require('node:module');
const compiled = new Module('forecastGroups');
compiled._compile(ts.transpileModule(fs.readFileSync('src/lib/forecastGroups.ts', 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, 'forecastGroups.js');
const { groupForecasts, formatPeriod, formatCloudBases } = compiled.exports;
const row = (hour, overrides = {}) => ({
  time: `2026-09-07T${String(hour).padStart(2, '0')}:00:00Z`,
  airport: { icao: 'KCVO', name: 'Corvallis', distance: 0 },
  weather: { ceiling: 2200, lowest_cloud_base: 2200 },
  approaches: [{ id: 'S17', name: 'VOR RWY 17', chart: 'chart.pdf', faf: { msl: 2500, agl: 2250 } }],
  ...overrides,
});
test('combines consecutive matching displayed data without mutating input', () => {
  const rows = [row(17), row(15), row(16, { weather: { ceiling: 2200, lowest_cloud_base: 2200, temperature: 12 } })];
  const original = JSON.stringify(rows);
  const [group] = groupForecasts(rows, 'nbh');
  assert.equal(group.periods.length, 1);
  assert.equal(group.periods[0].start, row(15).time);
  assert.equal(group.periods[0].end, row(17).time);
  assert.equal(JSON.stringify(rows), original);
});
test('gaps and changes in ceiling or approach details split periods', () => {
  for (const changed of [
    { weather: { ceiling: 2100, lowest_cloud_base: 2200 } },
    { approaches: [{ ...row(15).approaches[0], chart: 'new.pdf' }] },
    { approaches: [{ ...row(15).approaches[0], faf: { msl: 2400, agl: 2150 } }] },
  ]) assert.equal(groupForecasts([row(15), row(16, changed), row(17)], 'nbh')[0].periods.length, 3);
  assert.equal(groupForecasts([row(15), row(17)], 'nbh')[0].periods.length, 2);
});
test('uses source cadence and keeps airports separate, nearest first', () => {
  assert.equal(groupForecasts([row(12), row(15)], 'nbs')[0].periods.length, 1);
  assert.equal(groupForecasts([row(12), row(15)], 'nbh')[0].periods.length, 2);
  assert.equal(groupForecasts([row(12), row(13)], 'metar')[0].periods.length, 2);
  const groups = groupForecasts([row(15, { airport: { icao: 'KEUG', name: 'Eugene', distance: 23 } }), row(15)], 'nbh');
  assert.deepEqual(groups.map(g => g.airport.icao), ['KCVO', 'KEUG']);
});
test('formats single times, UTC ranges and midnight dates', () => {
  assert.equal(formatPeriod(row(15).time, row(15).time, false).time, '15:00Z');
  assert.equal(formatPeriod(row(15).time, row(17).time, false).time, '15:00Z – 17:00Z');
  assert.match(formatPeriod(row(23).time, '2026-09-08T01:00:00Z', false).date, /Sep 7.*Sep 8/);
});
test('NBS combines 5 PM and 8 PM, extends to 11 PM, but preserves missing samples', () => {
  const [pair] = groupForecasts([row(17), row(20)], 'nbs');
  assert.equal(pair.periods.length, 1);
  assert.equal(pair.periods[0].start, row(17).time);
  assert.equal(pair.periods[0].end, row(20).time);
  const [extended] = groupForecasts([row(17), row(20), row(23)], 'nbs');
  assert.equal(extended.periods.length, 1);
  assert.equal(extended.periods[0].end, row(23).time);
  assert.equal(groupForecasts([row(17), row(23)], 'nbs')[0].periods.length, 2);
  assert.equal(groupForecasts([row(17), row(20, {
    weather: { ceiling: 1800, lowest_cloud_base: 1800 },
  })], 'nbs')[0].periods.length, 2);
});

test('KTMK NBS matching ceilings merge despite changing tooltip cloud bases', () => {
  const rows = [6, 9, 12, 15].map((hour, i) => row(hour, {
    weather: { ceiling: 1300, lowest_cloud_base: [900, 1000, 1100, 1300][i] },
  }));
  const [group] = groupForecasts(rows, 'nbs');
  assert.equal(group.periods.length, 1);
  assert.equal(group.periods[0].start, row(6).time);
  assert.equal(group.periods[0].end, row(15).time);
  assert.equal(formatCloudBases(group.periods[0].lowestCloudBases), 'LCB: 900–1,300 ft');
});
