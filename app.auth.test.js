const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

async function check(source) {
  const storage = new Map();
  let timers = 0, prompts = 0, bootstrapCalls = 0, shared = 0;
  const els = Object.fromEntries(['saveButton', 'openCreateModalButton', 'personalShiftsButton', 'groupShiftsButton'].map(k => [k, {}]));
  const context = vm.createContext({
    Date, URL, console, CONFIG: { DEVICE_SESSION_STORAGE_KEY: 'test-device', CREDENTIAL_STALE_MS: 1, APPS_SCRIPT_API_URL: 'https://example.test/exec', JSONP_TIMEOUT_MS: 20000 },
    state: { idToken: '', deviceSessionToken: '', isAuthenticated: true, events: [] }, els,
    localStorage: { getItem: k => storage.get(k), setItem: (k,v) => storage.set(k,v), removeItem: k => storage.delete(k) },
    window: { clearTimeout() {}, setTimeout() { timers++; } },
    google: { accounts: { id: { prompt() { prompts++; }, initialize() { throw Error('Unexpected Google login'); } } } },
    showWelcome() {}, resetForm() {}, renderSummaryPickerOptions() {}, closeModal() {},
    showOperationModal() {}, hideOperationModal() {},
    loadBootstrap: async () => { bootstrapCalls++; return true; },
    sharePersonalShiftsAuth() { shared++; },
  });
  function use(name) {
    const match = source.match(new RegExp('(?:async )?function ' + name + '\\([^]*?\\n\\}', 'm'));
    assert.ok(match, name); vm.runInContext(match[0], context);
  }
  for (const name of ['hasAuthentication', 'readDeviceSession', 'saveDeviceSession', 'clearDeviceSession',
    'clearInactivityTimer', 'armInactivityTimer', 'refreshGoogleCredentialIfNeeded', 'registerActivity', 'initGoogleIdentity']) use(name);
  const session = { sessionToken: 'synthetic-session', expiresAt: new Date(Date.now()+30*86400000).toISOString() };
  context.saveDeviceSession(session);
  await context.initGoogleIdentity();
  assert.equal(context.state.deviceSessionToken, session.sessionToken);
  assert.equal(bootstrapCalls, 1); assert.equal(shared, 1);
  for (let i=0;i<100;i++) context.registerActivity();
  assert.equal(timers,0); assert.equal(prompts,0);
  assert.equal(context.hasAuthentication(),true);
  assert.equal([...storage.values()].some(v=>v.includes('Google')),false);
  context.clearDeviceSession(); assert.equal(context.readDeviceSession(),null);
  context.saveDeviceSession({sessionToken:'expired',expiresAt:'2000-01-01T00:00:00Z'});
  assert.equal(context.readDeviceSession(),null);
  assert.equal(storage.size,0);
  // A response arriving after logout must not restore the UI.
  let resolveRequest, shows = 0;
  context.state.deviceSessionToken = session.sessionToken;
  context.jsonpRequest = () => new Promise(resolve => { resolveRequest=resolve; });
  context.setBusy = context.setStatus = () => {};
  context.showApp = () => { shows++; };
  use('loadBootstrap');
  const pending = context.loadBootstrap();
  context.clearDeviceSession();
  resolveRequest({user:{name:'Test'},events:[]});
  assert.equal(await pending,false); assert.equal(shows,0);
  let requestUrl;
  context.document = {
    createElement: () => ({ remove() {} }),
    body: { appendChild(script) {
      requestUrl = new URL(script.src);
      context.window[requestUrl.searchParams.get('callback')]({ ok: true, result: {} });
    } },
  };
  context.state.deviceSessionToken = session.sessionToken;
  use('jsonpRequest');
  await context.jsonpRequest('create', { idToken: 'synthetic-Google-credential' });
  assert.equal(requestUrl.searchParams.get('sessionToken'), session.sessionToken);
  assert.equal(requestUrl.searchParams.has('idToken'),false);
  await context.jsonpRequest('createDeviceSession', { idToken: 'synthetic-Google-credential' });
  assert.equal(requestUrl.searchParams.has('sessionToken'),false);
  assert.equal(requestUrl.searchParams.get('idToken'),'synthetic-Google-credential');
  // Logout during session creation must not silently sign the user back in.
  let resolveSession, revoked = '';
  context.state.deviceSessionToken = '';
  context.state.isAuthenticated = false;
  context.jsonpRequest = (action, params) => action === 'createDeviceSession'
    ? new Promise(resolve => { resolveSession = resolve; })
    : (revoked = params.sessionToken, Promise.resolve({}));
  use('onGoogleCredential');
  const signingIn = context.onGoogleCredential({credential:'synthetic-Google-credential'});
  context.state.idToken = '';
  resolveSession(session);
  await signingIn;
  assert.equal(context.state.deviceSessionToken,'');
  assert.equal(revoked,session.sessionToken);
}
(async()=>{
  await check(fs.readFileSync(__dirname+'/app.js','utf8'));
  await check(fs.readFileSync(__dirname+'/github_pages_shared_calendar/frontend/app.js','utf8'));
  console.log('Persistent restore, no inactivity timers/Google refresh, expiry and logout race checks OK in both frontends');
})().catch(error=>{console.error(error);process.exitCode=1;});
