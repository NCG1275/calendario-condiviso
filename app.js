const CONFIG = {
  APPS_SCRIPT_API_URL: 'https://script.google.com/a/*/macros/s/AKfycbyOJSMFJHRR1oBF5jYHmancEcNkeXxs0_Byjb5IpfetdIf8gi36n1YafyDbo5s0fQH-bg/exec',
  GOOGLE_CLIENT_ID: '879487248442-q41p31thu716ffu9qctje1pm1pdn2ulo.apps.googleusercontent.com',
};

const state = {
  idToken: '',
  user: null,
  events: [],
};

const els = {
  signin: document.getElementById('signin'),
  status: document.getElementById('status'),
  userCard: document.getElementById('userCard'),
  userPicture: document.getElementById('userPicture'),
  userName: document.getElementById('userName'),
  userEmail: document.getElementById('userEmail'),
  events: document.getElementById('events'),
  eventForm: document.getElementById('eventForm'),
  eventId: document.getElementById('eventId'),
  summary: document.getElementById('summary'),
  start: document.getElementById('start'),
  end: document.getElementById('end'),
  location: document.getElementById('location'),
  description: document.getElementById('description'),
  saveButton: document.getElementById('saveButton'),
  deleteButton: document.getElementById('deleteButton'),
  refreshButton: document.getElementById('refreshButton'),
  resetButton: document.getElementById('resetButton'),
};

function setStatus(message, tone) {
  els.status.textContent = message;
  els.status.className = 'status' + (tone ? ' ' + tone : '');
}

function setBusy(isBusy) {
  els.saveButton.disabled = isBusy || !state.idToken;
  els.refreshButton.disabled = isBusy || !state.idToken;
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function formatDateTime(value) {
  return new Intl.DateTimeFormat('it-IT', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function toInputDateTime(value) {
  if (!value) return '';
  const date = new Date(value);
  const pad = (n) => String(n).padStart(2, '0');
  return [
    date.getFullYear(), '-',
    pad(date.getMonth() + 1), '-',
    pad(date.getDate()), 'T',
    pad(date.getHours()), ':',
    pad(date.getMinutes()),
  ].join('');
}

function fromInputDateTime(value) {
  return value ? new Date(value).toISOString() : '';
}

function encodePayload(payload) {
  const json = JSON.stringify(payload || {});
  return btoa(unescape(encodeURIComponent(json)))
    .replaceAll('+', '-')
    .replaceAll('/', '_')
    .replaceAll('=', '');
}

function jsonpRequest(action, params = {}) {
  return new Promise((resolve, reject) => {
    const callbackName = '__calendarCb_' + Date.now() + '_' + Math.floor(Math.random() * 10000);
    const script = document.createElement('script');
    const url = new URL(CONFIG.APPS_SCRIPT_API_URL);

    url.searchParams.set('api', '1');
    url.searchParams.set('action', action);
    url.searchParams.set('callback', callbackName);

    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, value);
      }
    });

    let settled = false;
    window[callbackName] = (response) => {
      settled = true;
      cleanup();
      if (!response || response.ok !== true) {
        reject(new Error((response && response.error) || 'Errore API.'));
        return;
      }
      resolve(response.result);
    };

    script.onerror = () => {
      if (settled) return;
      cleanup();
      reject(new Error('Impossibile raggiungere il backend Apps Script.'));
    };

    function cleanup() {
      delete window[callbackName];
      script.remove();
    }

    script.src = url.toString();
    document.body.appendChild(script);
  });
}

function resetForm() {
  els.eventForm.reset();
  els.eventId.value = '';
  els.saveButton.textContent = 'Salva';
  els.deleteButton.disabled = true;
}

function fillForm(event) {
  els.eventId.value = event.id;
  els.summary.value = event.summary || '';
  els.start.value = toInputDateTime(event.start);
  els.end.value = toInputDateTime(event.end);
  els.location.value = event.location || '';
  els.description.value = event.description || '';
  els.saveButton.textContent = 'Aggiorna';
  els.deleteButton.disabled = !event.canEdit;
}

function renderEvents() {
  if (!state.events.length) {
    els.events.innerHTML = '<div class="empty">Nessun evento nei prossimi 60 giorni.</div>';
    return;
  }

  els.events.innerHTML = state.events.map((event) => {
    const owner = event.ownerName || event.ownerEmail || 'Utente';
    return (
      '<article class="event">' +
        '<h3>' + escapeHtml(event.summary) + '</h3>' +
        '<div class="meta">' +
          '<div><span class="pill">' + (event.canEdit ? 'Tuo evento' : 'Solo lettura') + '</span></div>' +
          '<div><strong>Da:</strong> ' + escapeHtml(formatDateTime(event.start)) + '</div>' +
          '<div><strong>A:</strong> ' + escapeHtml(formatDateTime(event.end)) + '</div>' +
          '<div><strong>Proprietario:</strong> ' + escapeHtml(owner) + '</div>' +
          (event.location ? '<div><strong>Luogo:</strong> ' + escapeHtml(event.location) + '</div>' : '') +
        '</div>' +
        (event.description ? '<div>' + escapeHtml(event.description) + '</div>' : '') +
        (event.canEdit ? '<div class="actions"><button type="button" data-action="edit" data-id="' + event.id + '">Modifica</button></div>' : '') +
      '</article>'
    );
  }).join('');
}

function loadBootstrap() {
  if (!state.idToken) return;
  setBusy(true);
  setStatus('Caricamento eventi...');
  jsonpRequest('bootstrap', { idToken: state.idToken })
    .then((data) => {
      state.user = data.user;
      state.events = data.events || [];
      els.userCard.classList.remove('hidden');
      els.userPicture.src = data.user.picture || '';
      els.userName.textContent = data.user.name || 'Utente';
      els.userEmail.textContent = data.user.email || '';
      renderEvents();
      setStatus('Eventi caricati.', 'ok');
      setBusy(false);
    })
    .catch((error) => {
      setBusy(false);
      setStatus(error.message, 'error');
    });
}

function getFormPayload() {
  return {
    id: els.eventId.value,
    summary: els.summary.value,
    start: fromInputDateTime(els.start.value),
    end: fromInputDateTime(els.end.value),
    location: els.location.value,
    description: els.description.value,
    timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Rome',
  };
}

function saveEvent(event) {
  event.preventDefault();
  const payload = getFormPayload();
  const action = payload.id ? 'update' : 'create';
  setBusy(true);
  setStatus(action === 'create' ? 'Creazione evento...' : 'Aggiornamento evento...');
  jsonpRequest(action, {
    idToken: state.idToken,
    payload: encodePayload(payload),
  })
    .then(() => {
      resetForm();
      loadBootstrap();
    })
    .catch((error) => {
      setBusy(false);
      setStatus(error.message, 'error');
    });
}

function deleteCurrentEvent() {
  const eventId = els.eventId.value;
  if (!eventId) return;
  if (!confirm('Eliminare questo evento?')) return;
  setBusy(true);
  setStatus('Eliminazione evento...');
  jsonpRequest('delete', {
    idToken: state.idToken,
    eventId: eventId,
  })
    .then(() => {
      resetForm();
      loadBootstrap();
    })
    .catch((error) => {
      setBusy(false);
      setStatus(error.message, 'error');
    });
}

function onGoogleCredential(response) {
  state.idToken = response.credential;
  els.saveButton.disabled = false;
  els.refreshButton.disabled = false;
  loadBootstrap();
}

function initGoogleIdentity() {
  google.accounts.id.initialize({
    client_id: CONFIG.GOOGLE_CLIENT_ID,
    callback: onGoogleCredential,
    auto_select: false,
  });

  google.accounts.id.renderButton(els.signin, {
    theme: 'outline',
    size: 'large',
    shape: 'pill',
    text: 'signin_with',
  });
}

document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-action="edit"]');
  if (!button) return;
  const selected = state.events.find((item) => item.id === button.dataset.id);
  if (!selected) return;
  fillForm(selected);
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

els.eventForm.addEventListener('submit', saveEvent);
els.deleteButton.addEventListener('click', deleteCurrentEvent);
els.refreshButton.addEventListener('click', loadBootstrap);
els.resetButton.addEventListener('click', resetForm);
window.addEventListener('load', initGoogleIdentity);

