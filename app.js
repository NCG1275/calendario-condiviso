const CONFIG = {
  APPS_SCRIPT_API_URL: 'https://script.google.com/a/*/macros/s/AKfycbxkXeJXpPE2Vi_vJHXVHclo7YIOTlTp59qqq1NZeYD2ddxzZfcTF4O6aioumBTrYtlEyw/exec',
  GOOGLE_CLIENT_ID: '879487248442-q41p31thu716ffu9qctje1pm1pdn2ulo.apps.googleusercontent.com',
  INACTIVITY_TIMEOUT_MS: 60 * 1000,
};

const REQUEST_OPTIONS = [
  { value: 'FERIE', label: 'FERIE' },
  { value: 'L.104', label: 'L.104 : Legge 104' },
  { value: 'EMO', label: 'EMO : Emodinamica' },
  { value: 'PT', label: 'PT : Part-time' },
  { value: 'RS', label: 'RS : Riposo settimanale' },
  { value: 'CS', label: 'CS : Congedo straordinario' },
  { value: 'AGGPO', label: 'AGGPO : Aggiornamento Professionale Obbligatorio' },
  { value: 'AGGPF', label: 'AGGPF : Aggiornamento Professionale Facoltativo' },
  { value: '8-14 Lib.', label: '8-14 Lib. : Libero in fascia oraria' },
  { value: '14-20 Lib.', label: '14-20 Lib. : Libero in fascia oraria' },
  { value: '8-20 Lib.', label: '8-20 Lib. : Libero in fascia oraria' },
  { value: '20-08 Lib.', label: '20-08 Lib. : Libero in fascia oraria' },
];

const state = {
  idToken: '',
  user: null,
  events: [],
  visibleMonth: startOfMonth(new Date()),
  isAuthenticated: false,
  inactivityTimer: null,
  modalOriginalPayload: null,
};

const els = {
  signin: document.getElementById('signin'),
  status: document.getElementById('status'),
  appStatus: document.getElementById('appStatus'),
  welcomeScreen: document.getElementById('welcomeScreen'),
  appScreen: document.getElementById('appScreen'),
  logoutButton: document.getElementById('logoutButton'),
  userCard: document.getElementById('userCard'),
  userPicture: document.getElementById('userPicture'),
  userName: document.getElementById('userName'),
  monthGrid: document.getElementById('monthGrid'),
  calendarTitle: document.getElementById('calendarTitle'),
  requestModal: document.getElementById('requestModal'),
  modalTitle: document.getElementById('modalTitle'),
  modalEyebrow: document.getElementById('modalEyebrow'),
  modalMeta: document.getElementById('modalMeta'),
  modalTimestamps: document.getElementById('modalTimestamps'),
  openCreateModalButton: document.getElementById('openCreateModalButton'),
  closeModalButton: document.getElementById('closeModalButton'),
  eventForm: document.getElementById('eventForm'),
  eventId: document.getElementById('eventId'),
  summary: document.getElementById('summary'),
  summaryPickerButton: document.getElementById('summaryPickerButton'),
  summaryPicker: document.getElementById('summaryPicker'),
  summaryPickerOptions: document.getElementById('summaryPickerOptions'),
  summaryPickerClose: document.getElementById('summaryPickerClose'),
  start: document.getElementById('start'),
  end: document.getElementById('end'),
  description: document.getElementById('description'),
  saveButton: document.getElementById('saveButton'),
  deleteButton: document.getElementById('deleteButton'),
  resetButton: document.getElementById('resetButton'),
  prevMonthButton: document.getElementById('prevMonthButton'),
  nextMonthButton: document.getElementById('nextMonthButton'),
};

function setStatus(message, tone) {
  const className = 'status' + (tone ? ' ' + tone : '');
  [els.status, els.appStatus].forEach((element) => {
    if (!element) return;
    element.textContent = message;
    element.className = className + (element === els.appStatus ? ' app-status' : '');
  });
}

function resolveEventElement(target) {
  if (target instanceof Element) return target;
  if (target && target.parentElement instanceof Element) return target.parentElement;
  return null;
}

function setBusy(isBusy) {
  if (isBusy) {
    els.saveButton.disabled = true;
  } else {
    updateSaveButtonState();
  }
  els.openCreateModalButton.disabled = isBusy || !state.idToken;
}

function setSignedInUi(isSignedIn) {
  els.welcomeScreen.classList.toggle('hidden', isSignedIn);
  els.appScreen.classList.toggle('hidden', !isSignedIn);
  els.logoutButton.classList.toggle('hidden', !isSignedIn);
  els.userCard.classList.toggle('hidden', !isSignedIn);
}

function clearInactivityTimer() {
  if (state.inactivityTimer) {
    window.clearTimeout(state.inactivityTimer);
    state.inactivityTimer = null;
  }
}

function armInactivityTimer() {
  clearInactivityTimer();
  if (!state.isAuthenticated || !state.idToken) return;
  state.inactivityTimer = window.setTimeout(() => {
    logout('Sessione scaduta per inattività.');
  }, CONFIG.INACTIVITY_TIMEOUT_MS);
}

function registerActivity() {
  if (!state.isAuthenticated || !state.idToken) return;
  armInactivityTimer();
}

function renderSummaryPickerOptions() {
  els.summaryPickerOptions.innerHTML = REQUEST_OPTIONS.map((item) => (
    `<button type="button" class="picker-option${item.value === els.summary.value ? ' selected' : ''}" data-value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</button>`
  )).join('');
}

function openSummaryPicker() {
  if (els.summaryPickerButton.disabled) return;
  renderSummaryPickerOptions();
  els.summaryPicker.classList.remove('hidden');
}

function closeSummaryPicker() {
  els.summaryPicker.classList.add('hidden');
}

function setSummaryValue(value) {
  els.summary.value = value;
  syncSummaryPickerButton();
  updateSaveButtonState();
  closeSummaryPicker();
}

function showWelcome() {
  state.isAuthenticated = false;
  clearInactivityTimer();
  setSignedInUi(false);
  closeModal();
}

function showApp() {
  state.isAuthenticated = true;
  setSignedInUi(true);
  armInactivityTimer();
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function getRequestLabel(value) {
  const match = REQUEST_OPTIONS.find((item) => item.value === value);
  return match ? match.label : '';
}

function syncSummaryPickerButton() {
  const label = getRequestLabel(els.summary.value) || 'Seleziona un tipo';
  els.summaryPickerButton.textContent = label;
  els.summaryPickerButton.classList.toggle('placeholder', !els.summary.value);
}

function formatDateTime(value) {
  return new Intl.DateTimeFormat('it-IT', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parseCalendarDate(value));
}

function normalizeDateTimeValue(value) {
  const raw = String(value || '').trim();
  if (!raw) return null;
  const parsed = parseCalendarDate(raw);
  const time = parsed.getTime();
  return Number.isNaN(time) ? null : time;
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

function parseCalendarDate(value) {
  const raw = String(value || '').trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    const [year, month, day] = raw.split('-').map(Number);
    return new Date(year, month - 1, day);
  }
  return new Date(raw);
}

function eventStartDate(event) {
  return parseCalendarDate(event.start);
}

function eventLastDate(event) {
  const date = parseCalendarDate(event.end);
  date.setDate(date.getDate() - 1);
  return date;
}

function formatMiniEvent(event, segmentType) {
  if (segmentType === 'middle') {
    return '';
  }
  if (segmentType === 'end') {
    return event.summary;
  }
  return event.summary;
}

function toInputDate(value) {
  if (!value) return '';
  const date = parseCalendarDate(value);
  return dayKeyFromDate(date);
}

function toInclusiveEndInputDate(value) {
  if (!value) return '';
  const date = parseCalendarDate(value);
  date.setDate(date.getDate() - 1);
  return dayKeyFromDate(date);
}

function fromInputDateStart(value) {
  return value ? String(value) : '';
}

function fromInputDateEndExclusive(value) {
  if (!value) return '';
  const date = parseCalendarDate(value);
  date.setDate(date.getDate() + 1);
  return dayKeyFromDate(date);
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
      reject(new Error('Calendario Google momentaneamente non raggiungibile.'));
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
  els.summary.value = '';
  state.modalOriginalPayload = null;
  syncSummaryPickerButton();
  els.saveButton.textContent = 'Salva';
  els.deleteButton.disabled = true;
  els.modalEyebrow.textContent = 'Nuova richiesta';
  els.modalTitle.textContent = 'Inserisci evento';
  els.modalMeta.textContent = '';
  els.modalMeta.classList.add('hidden');
  els.modalTimestamps.textContent = '';
  els.modalTimestamps.classList.add('hidden');
  setFormEditable(true);
  updateSaveButtonState();
}

function logout(message) {
  state.idToken = '';
  state.user = null;
  state.events = [];
  showWelcome();
  resetForm();
  els.events.innerHTML = '<div class="empty">Nessun evento caricato.</div>';
  els.monthGrid.innerHTML = '<div class="empty">Nessun evento caricato.</div>';
  setStatus(message || 'Accesso disconnesso.');
  els.saveButton.disabled = true;
  els.openCreateModalButton.disabled = true;
  closeModal();
  google.accounts.id.disableAutoSelect();
}

function openModal() {
  els.requestModal.classList.remove('hidden');
}

function closeModal() {
  closeSummaryPicker();
  els.requestModal.classList.add('hidden');
}

function setFormEditable(editable) {
  els.summary.disabled = !editable;
  els.summaryPickerButton.disabled = !editable || !state.idToken;
  els.start.disabled = !editable;
  els.end.disabled = !editable;
  els.description.disabled = !editable;
  els.deleteButton.disabled = !editable || !els.eventId.value;
  updateSaveButtonState();
}

function fillForm(event) {
  els.eventId.value = event.id;
  els.summary.value = event.summary || '';
  syncSummaryPickerButton();
  els.start.value = toInputDate(event.start);
  els.end.value = toInclusiveEndInputDate(event.end);
  els.description.value = event.description || '';
  state.modalOriginalPayload = getFormPayload();
  const owner = event.ownerName || 'Utente';
  els.saveButton.textContent = 'Aggiorna';
  els.modalEyebrow.textContent = event.canEdit ? 'Richiesta esistente' : 'Sola lettura';
  els.modalTitle.textContent = event.canEdit ? 'Modifica evento' : 'Evento in sola lettura';
  els.modalMeta.textContent = event.canEdit
    ? `Autore: ${owner}. Puoi modificare questa richiesta.`
    : `Autore: ${owner}. Puoi solo visualizzare questa richiesta.`;
  els.modalMeta.classList.remove('hidden');
  const stamps = [];
  const createdStamp = event.created ? formatDateTime(event.created) : '';
  const updatedStamp = event.updated ? formatDateTime(event.updated) : '';
  const createdRaw = normalizeDateTimeValue(event.created);
  const updatedRaw = normalizeDateTimeValue(event.updated);
  if (event.created) {
    stamps.push(`Creata: ${createdStamp}`);
  }
  if (event.updated) {
    const noRealModification = createdRaw !== null && updatedRaw !== null && Math.abs(updatedRaw - createdRaw) < 60000;
    stamps.push(`Modifica: ${noRealModification ? 'Nessuna' : updatedStamp}`);
  }
  if (stamps.length) {
    els.modalTimestamps.textContent = stamps.join(' • ');
    els.modalTimestamps.classList.remove('hidden');
  } else {
    els.modalTimestamps.textContent = '';
    els.modalTimestamps.classList.add('hidden');
  }
  setFormEditable(!!event.canEdit);
  openModal();
}

function prepareNewEventForDate(date) {
  resetForm();
  const key = dayKeyFromDate(date);
  els.start.value = key;
  els.end.value = key;
  openModal();
  els.summary.focus();
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
    const start = eventStartDate(event);
    const lastDay = eventLastDate(event);
    let cursor = new Date(start.getFullYear(), start.getMonth(), start.getDate());
    while (cursor <= lastDay) {
      const key = dayKeyFromDate(cursor);
      if (!eventsByDay.has(key)) {
        eventsByDay.set(key, []);
      }
      let segmentType = 'middle';
      const isStart = sameDay(cursor, start);
      const isEnd = sameDay(cursor, lastDay);
      if (isStart && isEnd) segmentType = 'single';
      else if (isStart) segmentType = 'start';
      else if (isEnd) segmentType = 'end';
      eventsByDay.get(key).push({ event, segmentType, startTime: eventStartDate(event).getTime() });
      cursor.setDate(cursor.getDate() + 1);
    }
  });

  const cells = [];
  for (let i = 0; i < 42; i += 1) {
    const cellDate = new Date(gridStart);
    cellDate.setDate(gridStart.getDate() + i);
    const key = dayKeyFromDate(cellDate);
    const dayEvents = (eventsByDay.get(key) || [])
      .slice()
      .sort((a, b) => a.startTime - b.startTime);
    const otherMonth = cellDate.getMonth() !== monthStart.getMonth();
    const classes = [
      'day-cell',
      otherMonth ? 'other-month' : '',
      sameDay(cellDate, today) ? 'today' : '',
    ].filter(Boolean).join(' ');

    const previews = dayEvents.slice(0, 8).map((entry) => {
      const event = entry.event;
      const mineClass = event.canEdit ? ' mine' : '';
      const segmentClass = ` segment-${entry.segmentType}`;
      return `<div role="button" tabindex="0" class="mini-event${mineClass}${segmentClass}" data-action="edit" data-id="${event.id}">${escapeHtml(formatMiniEvent(event, entry.segmentType))}</div>`;
    }).join('');

    cells.push(
      `<div class="${classes}" data-action="new-on-date" data-date="${key}">` +
        `<div class="day-head">` +
          `<div class="day-number">${cellDate.getDate()}</div>` +
        `</div>` +
        `<div class="day-events">${previews}</div>` +
      `</div>`
    );
  }

  const rows = [];
  for (let i = 0; i < cells.length; i += 7) {
    rows.push(`<div class="week-row">${cells.slice(i, i + 7).join('')}</div>`);
  }

  els.monthGrid.innerHTML = rows.join('');
}

function loadBootstrap() {
  if (!state.idToken) return;
  registerActivity();
  setBusy(true);
  setStatus('Caricamento eventi...');
  jsonpRequest('bootstrap', { idToken: state.idToken })
    .then((data) => {
      const hadEventsLoaded = state.events.length > 0;
      state.user = data.user;
      state.events = data.events || [];
      showApp();
      els.userPicture.src = data.user.picture || '';
      els.userName.textContent = data.user.name || 'Utente';
      if (!hadEventsLoaded) {
        state.visibleMonth = startOfMonth(new Date());
      }
      renderMonthGrid();
      setStatus('');
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
    summary: String(els.summary.value || '').trim(),
    start: fromInputDateStart(els.start.value),
    end: fromInputDateEndExclusive(els.end.value),
    description: els.description.value,
    timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Rome',
  };
}

function comparablePayload(payload) {
  return JSON.stringify({
    id: String(payload.id || ''),
    summary: String(payload.summary || '').trim(),
    start: String(payload.start || ''),
    end: String(payload.end || ''),
    description: String(payload.description || '').trim(),
  });
}

function formHasRealChanges() {
  if (!els.eventId.value || !state.modalOriginalPayload) return true;
  return comparablePayload(getFormPayload()) !== comparablePayload(state.modalOriginalPayload);
}

function updateSaveButtonState() {
  if (!state.idToken || els.summary.disabled) {
    els.saveButton.disabled = true;
    return;
  }
  if (!els.eventId.value) {
    els.saveButton.disabled = false;
    return;
  }
  els.saveButton.disabled = !formHasRealChanges();
}

function saveEvent(event) {
  event.preventDefault();
  registerActivity();
  const payload = getFormPayload();
  if (!payload.summary) {
    setStatus('Seleziona un tipo di richiesta.', 'error');
    return;
  }
  if (!payload.start || !payload.end) {
    setStatus('Seleziona il giorno iniziale e finale.', 'error');
    return;
  }
  if (payload.id && !formHasRealChanges()) {
    setStatus('');
    return;
  }
  const action = payload.id ? 'update' : 'create';
  setBusy(true);
  setStatus(action === 'create' ? 'Creazione evento...' : 'Aggiornamento evento...');
  jsonpRequest(action, {
    idToken: state.idToken,
    payload: encodePayload(payload),
  })
    .then(() => {
      resetForm();
      closeModal();
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
  registerActivity();
  setBusy(true);
  setStatus('Eliminazione evento...');
  jsonpRequest('delete', {
    idToken: state.idToken,
    eventId: eventId,
  })
    .then(() => {
      resetForm();
      closeModal();
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
  els.openCreateModalButton.disabled = false;
  loadBootstrap();
}

function initGoogleIdentity() {
  showWelcome();
  resetForm();
  renderSummaryPickerOptions();
  closeModal();
  els.saveButton.disabled = true;
  els.openCreateModalButton.disabled = true;
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
  registerActivity();
  const target = resolveEventElement(event.target);
  if (!target) return;
  const button = target.closest('[data-action="edit"]');
  if (button) {
    event.stopPropagation();
    const selected = state.events.find((item) => item.id === button.dataset.id);
    if (!selected) return;
    fillForm(selected);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    return;
  }

  const dayCell = target.closest('[data-action="new-on-date"]');
  if (!dayCell) return;
  const dateParts = dayCell.dataset.date.split('-').map(Number);
  prepareNewEventForDate(new Date(dateParts[0], dateParts[1] - 1, dateParts[2]));
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

document.addEventListener('keydown', (event) => {
  registerActivity();
  const targetElement = resolveEventElement(event.target);
  const target = targetElement ? targetElement.closest('[data-action="edit"]') : null;
  if (!target) return;
  if (event.key !== 'Enter' && event.key !== ' ') return;
  event.preventDefault();
  const selected = state.events.find((item) => item.id === target.dataset.id);
  if (!selected) return;
  fillForm(selected);
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

document.addEventListener('input', registerActivity, true);
document.addEventListener('pointerdown', registerActivity, true);
document.addEventListener('touchstart', registerActivity, { passive: true });

els.eventForm.addEventListener('submit', saveEvent);
['input', 'change'].forEach((eventName) => {
  els.start.addEventListener(eventName, updateSaveButtonState);
  els.end.addEventListener(eventName, updateSaveButtonState);
  els.description.addEventListener(eventName, updateSaveButtonState);
});
els.summaryPickerButton.addEventListener('click', openSummaryPicker);
els.summaryPickerClose.addEventListener('click', closeSummaryPicker);
els.summaryPicker.addEventListener('click', (event) => {
  if (event.target === els.summaryPicker) {
    closeSummaryPicker();
    return;
  }
  const option = resolveEventElement(event.target)?.closest('.picker-option');
  if (option) {
    setSummaryValue(option.dataset.value || '');
  }
});
els.deleteButton.addEventListener('click', deleteCurrentEvent);
els.resetButton.addEventListener('click', () => {
  resetForm();
  openModal();
});
els.openCreateModalButton.addEventListener('click', () => {
  resetForm();
  openModal();
});
els.closeModalButton.addEventListener('click', closeModal);
els.logoutButton.addEventListener('click', logout);
els.prevMonthButton.addEventListener('click', () => {
  state.visibleMonth = addMonths(state.visibleMonth, -1);
  renderMonthGrid();
});
els.nextMonthButton.addEventListener('click', () => {
  state.visibleMonth = addMonths(state.visibleMonth, 1);
  renderMonthGrid();
});
els.requestModal.addEventListener('click', (event) => {
  if (event.target === els.requestModal) {
    closeModal();
  }
});
window.addEventListener('load', initGoogleIdentity);

