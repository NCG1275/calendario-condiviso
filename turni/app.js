const CONFIG = {
  APPS_SCRIPT_API_URL: 'https://script.google.com/macros/s/AKfycbyOEuEFx70o0NRx4Caseht8gUNdMOHDYvYUbCdcaJBQEaREslUrfa5eV7GTXkDRvQcIUw/exec',
  GOOGLE_CLIENT_ID: '879487248442-q41p31thu716ffu9qctje1pm1pdn2ulo.apps.googleusercontent.com',
  JSONP_TIMEOUT_MS: 20000,
};

const EMBEDDED_MODE = new URLSearchParams(window.location.search).get('embedded') === '1';
if (EMBEDDED_MODE) document.documentElement.classList.add('embedded');

const COLOR_CLASSES = {
  '7': 'morning',
  '5': 'afternoon',
  '4': 'long',
  '9': 'night',
  '11': 'oncall',
};

const state = {
  idToken: '',
  user: null,
  ownerName: '',
  calendarName: '',
  events: [],
  visibleMonth: startOfMonth(new Date()),
  updatedAt: '',
  requestVersion: 0,
};

const els = {
  loginView: document.getElementById('loginView'),
  appView: document.getElementById('appView'),
  googleSignin: document.getElementById('googleSignin'),
  loginStatus: document.getElementById('loginStatus'),
  monthTitle: document.getElementById('monthTitle'),
  calendarName: document.getElementById('calendarName'),
  monthGrid: document.getElementById('monthGrid'),
  syncStatus: document.getElementById('syncStatus'),
  refreshButton: document.getElementById('refreshButton'),
  prevMonthButton: document.getElementById('prevMonthButton'),
  nextMonthButton: document.getElementById('nextMonthButton'),
  todayButton: document.getElementById('todayButton'),
  bottomPrevButton: document.getElementById('bottomPrevButton'),
  bottomNextButton: document.getElementById('bottomNextButton'),
  bottomTodayButton: document.getElementById('bottomTodayButton'),
  shiftCount: document.getElementById('shiftCount'),
  hourCount: document.getElementById('hourCount'),
  nightCount: document.getElementById('nightCount'),
  onCallCount: document.getElementById('onCallCount'),
  profileButton: document.getElementById('profileButton'),
  profilePicture: document.getElementById('profilePicture'),
  profileInitials: document.getElementById('profileInitials'),
  daySheet: document.getElementById('daySheet'),
  daySheetTitle: document.getElementById('daySheetTitle'),
  dayEventList: document.getElementById('dayEventList'),
  closeSheetButton: document.getElementById('closeSheetButton'),
  accountSheet: document.getElementById('accountSheet'),
  closeAccountButton: document.getElementById('closeAccountButton'),
  accountName: document.getElementById('accountName'),
  accountEmail: document.getElementById('accountEmail'),
  logoutButton: document.getElementById('logoutButton'),
};

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function addMonths(date, amount) {
  return new Date(date.getFullYear(), date.getMonth() + amount, 1);
}

function localDateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function eventDateKey(event) {
  return String(event.start || '').slice(0, 10);
}

function monthRange(month) {
  return {
    start: localDateKey(startOfMonth(month)),
    end: localDateKey(addMonths(month, 1)),
  };
}

function formatMonth(month) {
  const label = new Intl.DateTimeFormat('it-IT', { month: 'long', year: 'numeric' }).format(month);
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function formatDay(date) {
  return new Intl.DateTimeFormat('it-IT', { weekday: 'long', day: 'numeric', month: 'long' }).format(date);
}

function formatTime(value) {
  if (!String(value || '').includes('T')) return '';
  const date = new Date(value);
  return new Intl.DateTimeFormat('it-IT', { hour: '2-digit', minute: '2-digit' }).format(date);
}

function eventDuration(event) {
  if (!String(event.start || '').includes('T') || !String(event.end || '').includes('T')) return 0;
  const duration = (new Date(event.end).getTime() - new Date(event.start).getTime()) / 3600000;
  return Number.isFinite(duration) && duration > 0 && duration <= 24 ? duration : 0;
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function encodePayload(payload) {
  return btoa(unescape(encodeURIComponent(JSON.stringify(payload || {}))))
    .replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '');
}

function jsonpRequest(action, params = {}) {
  return new Promise((resolve, reject) => {
    const callbackName = `__personalShifts_${Date.now()}_${Math.floor(Math.random() * 10000)}`;
    const script = document.createElement('script');
    const url = new URL(CONFIG.APPS_SCRIPT_API_URL);
    url.searchParams.set('api', '1');
    url.searchParams.set('action', action);
    url.searchParams.set('callback', callbackName);
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, value);
    });

    let settled = false;
    const cleanup = () => {
      settled = true;
      window.clearTimeout(timeoutId);
      delete window[callbackName];
      script.remove();
    };
    const timeoutId = window.setTimeout(() => {
      if (settled) return;
      cleanup();
      reject(new Error('Connessione scaduta. Riprova tra poco.'));
    }, CONFIG.JSONP_TIMEOUT_MS);

    window[callbackName] = (response) => {
      cleanup();
      if (!response || response.ok !== true) {
        reject(new Error((response && response.error) || 'Turni non disponibili.'));
        return;
      }
      resolve(response.result);
    };
    script.onerror = () => {
      if (settled) return;
      cleanup();
      reject(new Error('Il calendario non è raggiungibile.'));
    };
    script.src = url.toString();
    document.body.appendChild(script);
  });
}

function setLoading(isLoading) {
  els.refreshButton.disabled = isLoading;
  els.refreshButton.classList.toggle('is-loading', isLoading);
  if (isLoading) els.syncStatus.textContent = 'Aggiornamento…';
}

async function loadMonth() {
  if (!state.idToken) return;
  const requestVersion = ++state.requestVersion;
  const range = monthRange(state.visibleMonth);
  setLoading(true);
  renderMonth();
  try {
    const data = await jsonpRequest('personalShifts', {
      idToken: state.idToken,
      payload: encodePayload(range),
    });
    if (requestVersion !== state.requestVersion) return;
    state.user = data.user || state.user;
    state.ownerName = data.ownerName || state.user?.name || '';
    state.calendarName = data.calendarName || 'Calendario personale';
    state.events = Array.isArray(data.events) ? data.events : [];
    state.updatedAt = data.updatedAt || new Date().toISOString();
    showApp();
    renderMonth();
  } catch (error) {
    if (requestVersion !== state.requestVersion) return;
    const message = error instanceof Error ? error.message : 'Turni non disponibili.';
    els.syncStatus.textContent = message;
    els.syncStatus.classList.add('is-error');
    if (els.appView.classList.contains('hidden')) {
      els.loginStatus.textContent = message;
      els.loginStatus.classList.add('is-error');
    }
  } finally {
    if (requestVersion === state.requestVersion) setLoading(false);
  }
}

function showApp() {
  els.loginView.classList.add('hidden');
  els.appView.classList.remove('hidden');
  els.calendarName.textContent = state.calendarName;
  els.accountName.textContent = state.ownerName || state.user?.name || 'Utente';
  els.accountEmail.textContent = state.user?.email || '';
  const picture = state.user?.picture || '';
  if (picture) els.profilePicture.src = picture;
  else els.profilePicture.removeAttribute('src');
  els.profilePicture.classList.toggle('hidden', !picture);
  const source = state.ownerName || state.user?.name || state.user?.email || 'U';
  els.profileInitials.textContent = source.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase();
}

function eventsByDay() {
  return state.events.reduce((grouped, event) => {
    const key = eventDateKey(event);
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(event);
    return grouped;
  }, {});
}

function parseShiftEvent(event) {
  const summary = String(event.summary || '').trim();
  const parts = summary.split(' - ');
  const rawShift = String(parts.shift() || '').trim();
  const flagged = rawShift.includes('**');
  const code = rawShift.replaceAll('**', '').trim().toUpperCase();
  const destination = parts.join(' - ').trim();
  const variants = {
    '8-14': { label: 'M', kind: 'morning' },
    '8-20': { label: 'MP', kind: 'morning-afternoon' },
    'R': { label: 'R', kind: 'rest' },
    '14-20': { label: 'P', kind: 'afternoon' },
    '20-24': { label: 'N', kind: 'night' },
    '0-8': { label: 'SN', kind: 'night' },
  };
  const recognized = Boolean(variants[code]);
  const variant = variants[code] || {
    label: code || 'Turno',
    kind: COLOR_CLASSES[String(event.colorId || '')] || 'other',
  };
  return { ...variant, code, destination, flagged, recognized, summary };
}

function onCallKind(event) {
  const summary = String(event.summary || '').trim().toUpperCase();
  if (summary === 'REP GIORNO') return 'day';
  if (summary === 'REP NOTTE') return 'night';
  return '';
}

function eventKind(event) {
  if (onCallKind(event)) return 'oncall';
  return parseShiftEvent(event).kind || COLOR_CLASSES[String(event.colorId || '')] || 'other';
}

function renderMonth() {
  const month = state.visibleMonth;
  const grouped = eventsByDay();
  const todayKey = localDateKey(new Date());
  const first = startOfMonth(month);
  const mondayOffset = (first.getDay() + 6) % 7;
  const gridStart = new Date(first.getFullYear(), first.getMonth(), 1 - mondayOffset);
  const cells = [];

  els.monthTitle.textContent = formatMonth(month);
  for (let index = 0; index < 42; index += 1) {
    const date = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + index);
    const key = localDateKey(date);
    const events = grouped[key] || [];
    const dayOnCall = events.find((event) => onCallKind(event) === 'day');
    const nightOnCall = events.find((event) => onCallKind(event) === 'night');
    const shifts = events.filter((event) => !onCallKind(event));
    const parsedShifts = shifts.map(parseShiftEvent);
    const primaryShift = parsedShifts.find((shift) => shift.recognized) || null;
    const calendarEntries = parsedShifts.filter((shift) => !shift.recognized);
    const outside = date.getMonth() !== month.getMonth();
    const shiftClass = primaryShift ? ` shift-cell-${primaryShift.kind}` : '';
    const shiftLabel = primaryShift
      ? `<span class="shift-code shift-code-${primaryShift.label.toLowerCase()}">${escapeHtml(primaryShift.label)}${primaryShift.flagged ? '<b>**</b>' : ''}</span>`
      : '';
    const destinations = parsedShifts
      .filter((shift) => shift.recognized)
      .filter((shift) => shift.destination)
      .map((shift) => `<span class="destination-badge">${escapeHtml(shift.destination)}</span>`)
      .join('');
    const calendarEntryHtml = calendarEntries.slice(0, 2)
      .map((entry) => `<span class="calendar-entry">${escapeHtml(entry.summary)}</span>`)
      .join('');
    const calendarOverflow = calendarEntries.length > 2
      ? `<span class="calendar-entry calendar-entry-more">+${calendarEntries.length - 2}</span>`
      : '';
    const repDay = dayOnCall ? '<span class="on-call-half on-call-day"><b>repD</b></span>' : '';
    const repNight = nightOnCall ? '<span class="on-call-half on-call-night"><b>repN</b></span>' : '';
    cells.push(`
      <button class="day-cell${shiftClass}${outside ? ' is-outside' : ''}${key === todayKey ? ' is-today' : ''}${events.length ? ' has-events' : ''}"
        type="button" data-date="${key}" aria-label="${escapeHtml(formatDay(date))}, ${events.length} turni">
        ${repDay}${repNight}
        <span class="day-number">${date.getDate()}</span>
        <span class="destination-badges">${destinations}</span>
        ${shiftLabel}
        <span class="calendar-entries">${calendarEntryHtml}${calendarOverflow}</span>
      </button>`);
  }
  els.monthGrid.innerHTML = cells.join('');
  renderSummary();

  if (state.updatedAt) {
    const updated = new Intl.DateTimeFormat('it-IT', { hour: '2-digit', minute: '2-digit' }).format(new Date(state.updatedAt));
    els.syncStatus.textContent = `Aggiornato alle ${updated}`;
    els.syncStatus.classList.remove('is-error');
  }
}

function renderSummary() {
  const events = state.events;
  const shifts = events.filter((event) => !onCallKind(event));
  const hours = shifts.reduce((total, event) => total + eventDuration(event), 0);
  els.shiftCount.textContent = String(shifts.length);
  els.hourCount.textContent = Number.isInteger(hours) ? String(hours) : hours.toFixed(1).replace('.', ',');
  els.nightCount.textContent = String(shifts.filter((event) => eventKind(event) === 'night').length);
  els.onCallCount.textContent = String(events.filter((event) => Boolean(onCallKind(event))).length);
}

function openDay(dateKey) {
  const [year, month, day] = dateKey.split('-').map(Number);
  const date = new Date(year, month - 1, day);
  const events = eventsByDay()[dateKey] || [];
  els.daySheetTitle.textContent = formatDay(date);
  els.dayEventList.innerHTML = events.length ? events.map((event) => {
    const start = formatTime(event.start);
    const end = formatTime(event.end);
    const times = start && end ? `${start}–${end}` : 'Giornata intera';
    const details = [event.location, event.description].filter(Boolean).map(escapeHtml).join(' · ');
    return `<article class="day-event shift-border-${eventKind(event)}">
      <div><span class="event-time">${times}</span><h3>${escapeHtml(event.summary)}</h3></div>
      ${details ? `<p>${details}</p>` : ''}
    </article>`;
  }).join('') : '<div class="empty-day"><strong>Nessun turno</strong><span>Questa giornata è libera.</span></div>';
  els.daySheet.classList.remove('hidden');
}

function closeSheet(sheet) {
  sheet.classList.add('hidden');
}

function changeMonth(amount) {
  state.visibleMonth = addMonths(state.visibleMonth, amount);
  state.events = [];
  state.updatedAt = '';
  loadMonth();
}

function goToday() {
  state.visibleMonth = startOfMonth(new Date());
  state.events = [];
  state.updatedAt = '';
  loadMonth();
}

function onGoogleCredential(response) {
  state.idToken = response.credential || '';
  els.loginStatus.textContent = 'Accesso verificato. Carico i tuoi turni…';
  els.loginStatus.classList.remove('is-error');
  loadMonth().catch(() => {});
}

function resetEmbeddedSession() {
  ++state.requestVersion;
  state.idToken = '';
  state.user = null;
  state.events = [];
  els.appView.classList.add('hidden');
  els.loginView.classList.remove('hidden');
  els.loginStatus.textContent = 'Sessione terminata nel calendario condiviso.';
}

function notifyParent(type) {
  if (!EMBEDDED_MODE || window.parent === window) return;
  window.parent.postMessage({ type }, window.location.origin);
}

window.addEventListener('message', (event) => {
  if (!EMBEDDED_MODE || event.origin !== window.location.origin || event.source !== window.parent) return;
  if (event.data?.type === 'planner-logout') {
    resetEmbeddedSession();
    return;
  }
  if (event.data?.type !== 'planner-shared-auth') return;
  const nextToken = String(event.data.idToken || '');
  if (!nextToken) return;
  const shouldLoad = nextToken !== state.idToken || !state.user;
  state.idToken = nextToken;
  els.loginStatus.textContent = 'Sessione condivisa. Carico i tuoi turni…';
  if (shouldLoad) loadMonth().catch(() => {});
});

function initializeGoogleIdentity() {
  if (!window.google?.accounts?.id) {
    window.setTimeout(initializeGoogleIdentity, 100);
    return;
  }
  google.accounts.id.initialize({
    client_id: CONFIG.GOOGLE_CLIENT_ID,
    callback: onGoogleCredential,
    auto_select: false,
  });
  google.accounts.id.renderButton(els.googleSignin, {
    theme: 'outline', size: 'large', shape: 'pill', text: 'signin_with', width: 280,
  });
}

els.monthGrid.addEventListener('click', (event) => {
  const button = event.target.closest('[data-date]');
  if (button) openDay(button.dataset.date);
});
els.prevMonthButton.addEventListener('click', () => changeMonth(-1));
els.nextMonthButton.addEventListener('click', () => changeMonth(1));
els.bottomPrevButton.addEventListener('click', () => changeMonth(-1));
els.bottomNextButton.addEventListener('click', () => changeMonth(1));
els.todayButton.addEventListener('click', goToday);
els.bottomTodayButton.addEventListener('click', goToday);
els.refreshButton.addEventListener('click', loadMonth);
els.closeSheetButton.addEventListener('click', () => closeSheet(els.daySheet));
els.daySheet.addEventListener('click', (event) => { if (event.target === els.daySheet) closeSheet(els.daySheet); });
els.profileButton.addEventListener('click', () => els.accountSheet.classList.remove('hidden'));
els.closeAccountButton.addEventListener('click', () => closeSheet(els.accountSheet));
els.accountSheet.addEventListener('click', (event) => { if (event.target === els.accountSheet) closeSheet(els.accountSheet); });
els.logoutButton.addEventListener('click', () => {
  google.accounts.id.disableAutoSelect();
  state.idToken = '';
  state.user = null;
  state.events = [];
  closeSheet(els.accountSheet);
  els.appView.classList.add('hidden');
  els.loginView.classList.remove('hidden');
  els.loginStatus.textContent = 'Sessione terminata. Accedi per continuare.';
});

document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  closeSheet(els.daySheet);
  closeSheet(els.accountSheet);
});

renderMonth();
if (EMBEDDED_MODE) {
  els.loginStatus.textContent = 'Apertura dei tuoi turni…';
  notifyParent('planner-turni-ready');
  ['pointerdown', 'touchstart', 'keydown'].forEach((eventName) => {
    document.addEventListener(eventName, () => notifyParent('planner-activity'), { passive: true });
  });
} else {
  initializeGoogleIdentity();
}
if ('serviceWorker' in navigator) window.addEventListener('load', () => navigator.serviceWorker.register('./service-worker.js'));
