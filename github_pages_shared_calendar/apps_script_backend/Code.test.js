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
