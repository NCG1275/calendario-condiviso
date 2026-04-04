const CONFIG = {
  APPS_SCRIPT_API_URL: 'https://script.google.com/a/*/macros/s/AKfycbzypzAaUvDi9f6mu3ExITk2WkYPI0-g09snUodeUGZCveKouvbhmgfJlCVhmqrkk9wY1w/exec',
  GOOGLE_CLIENT_ID: '879487248442-q41p31thu716ffu9qctje1pm1pdn2ulo.apps.googleusercontent.com',
};

const state = {
  idToken: '',
  user: null,
  events: [],
  visibleMonth: startOfMonth(new Date()),
};

const els = {
  signin: document.getElementById('signin'),
  status: document.getElementById('status'),
  logoutButton: document.getElementById('logoutButton'),
  userCard: document.getElementById('userCard'),
  userPicture: document.getElementById('userPicture'),
  userName: document.getElementById('userName'),
  userEmail: document.getElementById('userEmail'),
  events: document.getElementById('events'),
  monthGrid: document.getElementById('monthGrid'),
  calendarTitle: document.getElementById('calendarTitle'),
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
  prevMonthButton: document.getElementById('prevMonthButton'),
  nextMonthButton: document.getElementById('nextMonthButton'),
};

function setStatus(message, tone) {
  els.status.textContent = message;
  els.status.className = 'status' + (tone ? ' ' + tone : '');
}

function setBusy(isBusy) {
  els.saveButton.disabled = isBusy || !state.idToken;
  els.refreshButton.disabled = isBusy || !state.idToken;
}

function setSignedInUi(isSignedIn) {
  els.logoutButton.classList.toggle('hidden', !isSignedIn);
  els.signin.classList.toggle('hidden', isSignedIn);
  els.userCard.classList.toggle('hidden', !isSignedIn);
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

function formatMonthTitle(date) {
  return new Intl.DateTimeFormat('it-IT', {
    month: 'long',
    year: 'numeric',
  }).format(date);
}

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function addMonths(date, delta) {
  return new Date(date.getFullYear(), date.getMonth() + delta, 1);
}

function sameDay(a, b) {
  return a.getFullYear() === b.getFullYear()
    && a.getMonth() === b.getMonth()
    && a.getDate() === b.getDate();
}

function dayKeyFromDate(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function eventStartDate(event) {
  return new Date(event.start);
}

function formatMiniEvent(event) {
  const start = eventStartDate(event);
  const time = new Intl.DateTimeFormat('it-IT', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(start);
  return `${time} ${event.summary}`;
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

function logout() {
  state.idToken = '';
  state.user = null;
  state.events = [];
  setSignedInUi(false);
  resetForm();
  els.events.innerHTML = '<div class="empty">Nessun evento caricato.</div>';
  els.monthGrid.innerHTML = '<div class="empty">Nessun evento caricato.</div>';
  setStatus('Accesso disconnesso.');
  els.saveButton.disabled = true;
  els.refreshButton.disabled = true;
  google.accounts.id.disableAutoSelect();
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

function prepareNewEventForDate(date) {
  resetForm();
  const start = new Date(date.getFullYear(), date.getMonth(), date.getDate(), 9, 0, 0);
  const end = new Date(date.getFullYear(), date.getMonth(), date.getDate(), 10, 0, 0);
  els.start.value = toInputDateTime(start.toISOString());
  els.end.value = toInputDateTime(end.toISOString());
  els.summary.focus();
}

function renderEvents() {
  const month = state.visibleMonth.getMonth();
  const year = state.visibleMonth.getFullYear();
  const monthEvents = state.events.filter((event) => {
    const start = eventStartDate(event);
    return start.getMonth() === month && start.getFullYear() === year;
  });

  if (!monthEvents.length) {
    els.events.innerHTML = '<div class="empty">Nessun evento nel mese selezionato.</div>';
    return;
  }

  els.events.innerHTML = monthEvents.map((event) => {
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

function renderMonthGrid() {
  const monthStart = state.visibleMonth;
  const gridStart = new Date(monthStart);
  const weekday = (monthStart.getDay() + 6) % 7;
  gridStart.setDate(monthStart.getDate() - weekday);

  const monthLabel = formatMonthTitle(monthStart);
  els.calendarTitle.textContent = monthLabel.charAt(0).toUpperCase() + monthLabel.slice(1);

  const today = new Date();
  const eventsByDay = new Map();
  state.events.forEach((event) => {
    const key = dayKeyFromDate(eventStartDate(event));
    if (!eventsByDay.has(key)) {
      eventsByDay.set(key, []);
    }
    eventsByDay.get(key).push(event);
  });

  const cells = [];
  for (let i = 0; i < 42; i += 1) {
    const cellDate = new Date(gridStart);
    cellDate.setDate(gridStart.getDate() + i);
    const key = dayKeyFromDate(cellDate);
    const dayEvents = (eventsByDay.get(key) || [])
      .slice()
      .sort((a, b) => new Date(a.start) - new Date(b.start));
    const otherMonth = cellDate.getMonth() !== monthStart.getMonth();
    const classes = [
      'day-cell',
      otherMonth ? 'other-month' : '',
      sameDay(cellDate, today) ? 'today' : '',
    ].filter(Boolean).join(' ');

    const previews = dayEvents.slice(0, 3).map((event) => {
      const mineClass = event.canEdit ? ' mine' : '';
      return `<div class="mini-event${mineClass}" data-action="edit" data-id="${event.id}">${escapeHtml(formatMiniEvent(event))}</div>`;
    }).join('');

    const more = dayEvents.length > 3
      ? `<div class="day-count">+${dayEvents.length - 3} altri</div>`
      : `<div class="day-count">${dayEvents.length ? `${dayEvents.length} eventi` : '\u00a0'}</div>`;

    cells.push(
      `<div class="${classes}" data-action="new-on-date" data-date="${key}">` +
        `<div class="day-head">` +
          `<div class="day-number">${cellDate.getDate()}</div>` +
          `${more}` +
        `</div>` +
        `<div class="day-events">${previews}</div>` +
      `</div>`
    );
  }

  els.monthGrid.innerHTML = cells.join('');
}

function loadBootstrap() {
  if (!state.idToken) return;
  setBusy(true);
  setStatus('Caricamento eventi...');
  jsonpRequest('bootstrap', { idToken: state.idToken })
    .then((data) => {
      const hadEventsLoaded = state.events.length > 0;
      state.user = data.user;
      state.events = data.events || [];
      setSignedInUi(true);
      els.userPicture.src = data.user.picture || '';
      els.userName.textContent = data.user.name || 'Utente';
      els.userEmail.textContent = data.user.email || '';
      if (!hadEventsLoaded) {
        state.visibleMonth = startOfMonth(new Date());
      }
      renderMonthGrid();
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
  if (button) {
    event.stopPropagation();
    const selected = state.events.find((item) => item.id === button.dataset.id);
    if (!selected) return;
    fillForm(selected);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    return;
  }

  const dayCell = event.target.closest('[data-action="new-on-date"]');
  if (!dayCell) return;
  const dateParts = dayCell.dataset.date.split('-').map(Number);
  prepareNewEventForDate(new Date(dateParts[0], dateParts[1] - 1, dateParts[2]));
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

els.eventForm.addEventListener('submit', saveEvent);
els.deleteButton.addEventListener('click', deleteCurrentEvent);
els.refreshButton.addEventListener('click', loadBootstrap);
els.resetButton.addEventListener('click', resetForm);
els.logoutButton.addEventListener('click', logout);
els.prevMonthButton.addEventListener('click', () => {
  state.visibleMonth = addMonths(state.visibleMonth, -1);
  renderMonthGrid();
  renderEvents();
});
els.nextMonthButton.addEventListener('click', () => {
  state.visibleMonth = addMonths(state.visibleMonth, 1);
  renderMonthGrid();
  renderEvents();
});
window.addEventListener('load', initGoogleIdentity);

