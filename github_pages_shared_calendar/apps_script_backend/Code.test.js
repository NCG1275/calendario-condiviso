const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const vm = require('node:vm');

const properties = new Map();
const scriptProperties = {
  getProperty(name) { return properties.get(name) || null; },
  setProperty(name, value) { properties.set(name, String(value)); },
  getProperties() { return Object.fromEntries(properties); },
  deleteProperty(name) { properties.delete(name); },
};

const context = vm.createContext({
  console,
  PropertiesService: { getScriptProperties: () => scriptProperties },
  LockService: {
    getScriptLock: () => ({ waitLock() {}, releaseLock() {} }),
  },
  Utilities: {
    DigestAlgorithm: { SHA_256: 'sha256' },
    Charset: { UTF_8: 'utf8' },
    getUuid: () => crypto.randomUUID(),
    computeDigest: (_algorithm, value) => [...crypto.createHash('sha256').update(value, 'utf8').digest()]
      .map((byte) => (byte > 127 ? byte - 256 : byte)),
  },
});

const source = fs.readFileSync(__dirname + '/Code.gs', 'utf8');
vm.runInContext(source, context);
context.getVerifiedUser_ = () => ({
  email: 'giannicola.aru@gmail.com',
  name: 'Gian Nicola Aru',
  picture: 'https://example.test/avatar.png',
});

const created = context.createDeviceSession_('google-id-token');
assert.match(created.sessionToken, /^[a-f0-9]{64}$/);
assert.ok(Date.parse(created.expiresAt) > Date.now() + 29 * 24 * 60 * 60 * 1000);
assert.equal([...properties.values()].some((value) => value.includes(created.sessionToken)), false);

const restored = context.getDeviceSessionUser_(created.sessionToken);
assert.equal(restored.email, 'giannicola.aru@gmail.com');
assert.equal(restored.name, 'Gian Nicola Aru');

for (let index = 0; index < 6; index += 1) context.createDeviceSession_('google-id-token');
assert.equal(properties.size, 5);

assert.equal(context.revokeDeviceSession_(created.sessionToken).revoked, true);
assert.throws(
  () => context.getDeviceSessionUser_(created.sessionToken),
  /Sessione dispositivo scaduta/
);
assert.throws(
  () => context.getDeviceSessionUser_('not-a-token'),
  /Sessione dispositivo scaduta/
);

console.log('Device session tests OK');

// Read all published calendars, including colleagues without personal-login mappings.
let calendarReads = 0;
context.Calendar = {
  CalendarList: { list(options) {
    calendarReads += 1;
    return options.pageToken ? { items: [{ id: 'unmapped', summary: 'Turni Del Rio' }, { id: 'missing', summary: 'Turni Corda' }] }
      : { items: [{ id: 'aru', summary: 'Turni Aru' }, { id: 'private', summary: 'Calendario privato' }, { id: 'revoked', summary: 'Turni Masillo' }], nextPageToken: 'next' };
  } },
  Events: { list(id, options) {
    assert.notEqual(id, 'private');
    assert.notEqual(id, 'revoked');
    assert.equal(options.timeMin, '2026-10-26T00:00:00+02:00');
    assert.equal(options.timeMax, '2026-11-02T00:00:00+01:00');
    if (id === 'missing') throw new Error('Calendar unavailable');
    if (options.pageToken) return { items: [{ summary: '14-20', start: { date: '2026-10-27' } }] };
    return { items: [
      { id: 'secret-id', description: 'private', summary: '8-14** - SALA', start: { dateTime: '2026-10-26T08:00:00+01:00' } },
      { summary: 'R', start: { date: '2026-11-02' } },
      { summary: 'R', status: 'cancelled', start: { date: '2026-10-27' } },
    ], nextPageToken: 'more' };
  } },
};
const group = context.getGroupShifts_({ start: '2026-10-26', end: '2026-11-02' }, 'token', '');
assert.equal(calendarReads, 2);
assert.equal(group.colleagues.map(c => c.name).join(','), 'Aru,Cabianca,Casula,Corda,Del Rio,Desogus,Mattana,Pili,Piras D,Piras F,Pistincu,Pitzalis,Puddu,Sanna,Tolu');
assert.equal(group.colleagues[0].events.length, 2);
assert.equal(group.colleagues.find(c => c.name === 'Corda').unavailable, true);
assert.equal(group.colleagues.find(c => c.name === 'Corda').unpublished, false);
assert.equal(group.colleagues.find(c => c.name === 'Mattana').unpublished, true);
assert.equal(group.colleagues.find(c => c.name === 'Mattana').unavailable, false);
assert.equal(group.colleagues.find(c => c.name === 'Aru').unpublished, false);
assert.equal(JSON.stringify(group).includes('secret-id'), false);
assert.equal(JSON.stringify(group).includes('description'), false);
assert.throws(() => context.getGroupShifts_({ start: '2026-10-26', end: '2026-11-03' }, 'token', ''), /settimanale/);
const validSession = context.createDeviceSession_('token');
assert.equal(context.getGroupShifts_({ start: '2026-10-26', end: '2026-11-02' }, '', validSession.sessionToken).colleagues.length, 15);
context.getVerifiedUser_ = () => { throw new Error('Utente non autenticato.'); };
const readsBefore = calendarReads;
assert.throws(() => context.getGroupShifts_({ start: '2026-10-26', end: '2026-11-02' }, '', ''), /non autenticato/);
assert.throws(() => context.getGroupShifts_({ start: '2026-10-26', end: '2026-11-02' }, '', 'invalid'), /Sessione dispositivo scaduta/);
assert.equal(calendarReads, readsBefore);
console.log('Authenticated group shifts, pagination, partial failures and privacy tests OK');

// A persistent session can access shared requests, but ownership still applies.
context.listEvents_ = () => [];
assert.equal(context.getBootstrapData_('', validSession.sessionToken).user.email, 'giannicola.aru@gmail.com');
for (const operation of [
  () => context.getBootstrapData_('google-token', 'invalid'),
  () => context.createOwnedEvent_({}, 'google-token', 'invalid'),
  () => context.updateOwnedEvent_({}, 'google-token', 'invalid'),
  () => context.deleteOwnedEvent_('event', 'google-token', 'invalid'),
]) assert.throws(operation, /Sessione dispositivo scaduta/);
context.validatePayload_ = () => {};
context.assertNoDuplicateRequest_ = () => {};
let writes = 0;
context.Calendar.Events.get = () => ({ extendedProperties: { private: { ownerEmail: 'other@example.test' } } });
context.Calendar.Events.update = () => { writes++; };
context.Calendar.Events.remove = () => { writes++; };
assert.throws(() => context.updateOwnedEvent_({ id: 'foreign' }, '', validSession.sessionToken), /permess|tuoi|autorizzat/i);
assert.throws(() => context.deleteOwnedEvent_('foreign', '', validSession.sessionToken), /permess|tuoi|autorizzat/i);
assert.equal(writes, 0);
context.Calendar.Events.insert = event => { writes++; return { ...event, id: 'own' }; };
context.Calendar.Events.get = () => ({ extendedProperties: { private: { ownerEmail: 'giannicola.aru@gmail.com' } } });
context.Calendar.Events.update = event => { writes++; return { ...event, id: 'own' }; };
const ownPayload = { id: 'own', summary: 'FERIE', start: '2026-11-02', end: '2026-11-03' };
assert.equal(context.createOwnedEvent_(ownPayload, '', validSession.sessionToken).canEdit, true);
assert.equal(context.updateOwnedEvent_(ownPayload, '', validSession.sessionToken).canEdit, true);
assert.equal(context.deleteOwnedEvent_('own', '', validSession.sessionToken).ok, true);
assert.equal(writes, 3);
context.revokeDeviceSession_(validSession.sessionToken);
assert.throws(() => context.getBootstrapData_('', validSession.sessionToken), /Sessione dispositivo scaduta/);
console.log('Persistent shared-calendar sessions, revocation and ownership checks OK');
