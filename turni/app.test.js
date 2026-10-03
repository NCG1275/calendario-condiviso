const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

// Exercise the production monthly summary without starting OAuth or networking.
const source = fs.readFileSync(__dirname + '/app.js', 'utf8');
const context = vm.createContext({
  Intl, Date,
  COLOR_CLASSES: {},
  state: { visibleMonth: new Date(2026, 9, 1), events: [] },
  els: Object.fromEntries(['shiftCount', 'hourCount', 'projectHourCount', 'nightCount', 'onCallCount']
    .map((key) => [key, { textContent: '' }])),
});
for (const name of ['startOfMonth', 'addMonths', 'localDateKey', 'eventDateKey',
  'parseShiftEvent', 'formatHourTotal', 'onCallKind', 'renderSummary']) {
  const match = source.match(new RegExp('function ' + name + '\\([^]*?\\n\\}', 'm'));
  assert.ok(match, name);
  vm.runInContext(match[0], context);
}
const event = (summary, start = '2026-10-05') => ({ summary, start });
function check(events, expectedProjectHours, expectedHours) {
  context.state.events = events;
  vm.runInContext('renderSummary()', context);
  assert.equal(context.els.projectHourCount.textContent, expectedProjectHours);
  assert.equal(context.els.hourCount.textContent, expectedHours);
}
check([event('8-14** - SALA')], '6', '6');
check([event('8-20** - SALA')], '12', '12');
check([event('8-14** - SALA'), event('14-20 - SALA')], '6', '12');
check([event('8-14 - SALA'), event('14-20** - SALA')], '6', '12');
check([event('8-14** - SALA'), event('14-20** - SALA')], '12', '12');
check([event('8-20 - SALA'), event('REP GIORNO'), event('8-14** - SALA', '2026-09-30')], '0', '12');
check([event('8-15** - SALA')], '7', '7');
check([], '0', '0');
console.log('Personal project-hours summary tests OK');
