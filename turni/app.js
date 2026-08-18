const CONFIG = {
  APPS_SCRIPT_API_URL: 'https://script.google.com/macros/s/AKfycbyOEuEFx70o0NRx4Caseht8gUNdMOHDYvYUbCdcaJBQEaREslUrfa5eV7GTXkDRvQcIUw/exec',
  GOOGLE_CLIENT_ID: '879487248442-q41p31thu716ffu9qctje1pm1pdn2ulo.apps.googleusercontent.com',
  JSONP_TIMEOUT_MS: 20000,
  DEVICE_SESSION_STORAGE_KEY: 'planner-turni-device-session-v1',
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
  deviceSessionToken: '',
  user: null,
  ownerName: '',
  calendarName: '',
  events: [],
  visibleMonth: startOfMonth(new Date()),
  updatedAt: '',
  requestVersion: 0,
};

const els = {
  sessionSplash: document.getElementById('sessionSplash'),
  sessionSplashStatus: document.getElementById('sessionSplashStatus'),
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

const SESSION_SPLASH_MINIMUM_MS = 1500;
let sessionSplashShownAt = performance.now();
let sessionSplashHideTimer = 0;

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
  const first = startOfMonth(month);
  const mondayOffset = (first.getDay() + 6) % 7;
  const gridStart = new Date(first.getFullYear(), first.getMonth(), 1 - mondayOffset);
  const gridEnd = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + 42);
  return {
    start: localDateKey(gridStart),
    end: localDateKey(gridEnd),
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

function showSessionSplash(message = 'Ripristino della sessione…') {
  window.clearTimeout(sessionSplashHideTimer);
  sessionSplashShownAt = performance.now();
  els.sessionSplashStatus.textContent = message;
  els.sessionSplash.setAttribute('aria-busy', 'true');
  els.sessionSplash.classList.remove('is-hidden');
  document.body.classList.add('splash-active');
}

function hideSessionSplash(minimumVisibleMs = 0) {
  window.clearTimeout(sessionSplashHideTimer);
  const remaining = Math.max(0, minimumVisibleMs - (performance.now() - sessionSplashShownAt));
  sessionSplashHideTimer = window.setTimeout(() => {
    els.sessionSplash.setAttribute('aria-busy', 'false');
    els.sessionSplash.classList.add('is-hidden');
    document.body.classList.remove('splash-active');
  }, remaining);
}

function readDeviceSession() {
  try {
    const saved = JSON.parse(localStorage.getItem(CONFIG.DEVICE_SESSION_STORAGE_KEY) || '{}');
    const expiresAt = Date.parse(saved.expiresAt || '');
    if (!saved.sessionToken || !Number.isFinite(expiresAt) || expiresAt <= Date.now()) {
      localStorage.removeItem(CONFIG.DEVICE_SESSION_STORAGE_KEY);
      return null;
    }
    return saved;
  } catch (error) {
    try {
      localStorage.removeItem(CONFIG.DEVICE_SESSION_STORAGE_KEY);
    } catch (storageError) {
      // Il browser puo disabilitare lo spazio locale in modalita privata.
    }
    return null;
  }
}

function saveDeviceSession(session) {
  localStorage.setItem(CONFIG.DEVICE_SESSION_STORAGE_KEY, JSON.stringify({
    sessionToken: session.sessionToken,
    expiresAt: session.expiresAt,
  }));
}

function clearDeviceSession() {
  try {
    localStorage.removeItem(CONFIG.DEVICE_SESSION_STORAGE_KEY);
  } catch (error) {
    // Lo stato in memoria viene comunque eliminato.
  }
  state.deviceSessionToken = '';
}

async function logoutStandalone(message = 'Sessione terminata. Accedi per continuare.') {
  const sessionToken = state.deviceSessionToken;
  clearDeviceSession();
  if (window.google?.accounts?.id) google.accounts.id.disableAutoSelect();
  state.idToken = '';
  state.user = null;
  state.events = [];
  closeSheet(els.accountSheet);
  els.appView.classList.add('hidden');
  els.loginView.classList.remove('hidden');
  els.loginStatus.textContent = message;
  if (sessionToken) {
    jsonpRequest('revokeDeviceSession', { sessionToken }).catch(() => {});
  }
  initializeGoogleIdentity();
}

async function loadMonth() {
  if (!state.idToken && !state.deviceSessionToken) return false;
  const requestVersion = ++state.requestVersion;
  const range = monthRange(state.visibleMonth);
  setLoading(true);
  renderMonth();
  try {
    const data = await jsonpRequest('personalShifts', {
      idToken: state.deviceSessionToken ? '' : state.idToken,
      sessionToken: state.deviceSessionToken,
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
    return true;
  } catch (error) {
    if (requestVersion !== state.requestVersion) return;
    const message = error instanceof Error ? error.message : 'Turni non disponibili.';
    if (state.deviceSessionToken && message === 'Sessione dispositivo scaduta. Accedi di nuovo.') {
      clearDeviceSession();
      state.user = null;
      state.events = [];
      els.appView.classList.add('hidden');
      els.loginView.classList.remove('hidden');
      els.loginStatus.textContent = message;
      initializeGoogleIdentity();
      return false;
    }
    els.syncStatus.textContent = message;
    els.syncStatus.classList.add('is-error');
    if (els.appView.classList.contains('hidden')) {
      els.loginStatus.textContent = message;
      els.loginStatus.classList.add('is-error');
    }
    return false;
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
    '8-14': { label: 'M', kind: 'morning', hours: 6 },
    '8-15': { label: 'M', kind: 'morning', hours: 7 },
    '8-16': { label: 'M', kind: 'morning', hours: 8 },
    '8-20': { label: 'MP', kind: 'morning-afternoon', hours: 12 },
    'R': { label: 'R', kind: 'rest', hours: 0 },
    'RS': { label: 'RS', kind: 'rest', hours: 0 },
    'RO': { label: 'RO', kind: 'rest-ordinary', hours: 7.36 },
    'RF': { label: 'RF', kind: 'rest-holiday', hours: 7.36 },
    'F': { label: 'F', kind: 'leave', hours: 7.36 },
    'PT': { label: 'PT', kind: 'zero-hours', hours: 0 },
    'CSM': { label: 'CSM', kind: 'leave-motivated', hours: 7.36 },
    'CSNM': { label: 'CSNM', kind: 'leave-unmotivated', hours: 7.36 },
    'CS': { label: 'CS', kind: 'leave-motivated', hours: 7.36 },
    'C': { label: 'C', kind: 'leave-motivated', hours: 7.36 },
    'AGGPF': { label: 'AGGPF', kind: 'training-optional', hours: 7.36 },
    'AGGPO': { label: 'AGGPO', kind: 'training-required', hours: 7.36 },
    'AGGP': { label: 'AGGP', kind: 'training-required', hours: 7.36 },
    'AF': { label: 'AF', kind: 'training-optional', hours: 7.36 },
    'AO': { label: 'AO', kind: 'training-required', hours: 7.36 },
    'M': { label: 'M', kind: 'illness', hours: 7.36 },
    'L.104': { label: 'L.104', kind: 'law-104', hours: 7.36 },
    'L': { label: 'L', kind: 'law-104', hours: 7.36 },
    '14-20': { label: 'P', kind: 'afternoon', hours: 6 },
    '20-24': { label: 'N', kind: 'night', hours: 4 },
    '0-8': { label: 'SN', kind: 'night', hours: 8 },
  };
  const recognized = Boolean(variants[code]);
  const variant = variants[code] || {
    label: code || 'Turno',
    kind: COLOR_CLASSES[String(event.colorId || '')] || 'other',
  };
  return { ...variant, code, destination, flagged, recognized, summary };
}

function weeklyShiftHours(sunday, grouped) {
  let total = 0;
  for (let offset = -6; offset <= 0; offset += 1) {
    const date = new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() + offset);
    const events = grouped[localDateKey(date)] || [];
    total += events
      .filter((event) => !onCallKind(event))
      .map(parseShiftEvent)
      .filter((shift) => shift.recognized)
      .reduce((dayTotal, shift) => dayTotal + shift.hours, 0);
  }
  return total;
}

function formatHourTotal(hours) {
  const rounded = Math.round(hours * 100) / 100;
  return (Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(2).replace(/0+$/, '')).replace('.', ',');
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
  const today = new Date();
  const todayKey = localDateKey(today);
  const currentWeekStart = new Date(
    today.getFullYear(),
    today.getMonth(),
    today.getDate() - ((today.getDay() + 6) % 7),
  );
  const currentWeekEnd = new Date(
    currentWeekStart.getFullYear(),
    currentWeekStart.getMonth(),
    currentWeekStart.getDate() + 7,
  );
  const first = startOfMonth(month);
  const mondayOffset = (first.getDay() + 6) % 7;
  const gridStart = new Date(first.getFullYear(), first.getMonth(), 1 - mondayOffset);
  const cells = [];
  let hasCurrentWeek = false;

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
    const isCurrentWeek = date >= currentWeekStart && date < currentWeekEnd;
    if (isCurrentWeek) hasCurrentWeek = true;
    const shiftClass = primaryShift ? ` shift-cell-${primaryShift.kind}` : '';
    const shiftCodeSize = primaryShift && primaryShift.label.length >= 4
      ? ' shift-code-wide'
      : primaryShift && primaryShift.label.length > 1 ? ' shift-code-compact' : '';
    const shiftLabel = primaryShift
      ? `<span class="shift-code${shiftCodeSize}${primaryShift.flagged ? ' is-flagged' : ''}"><span class="shift-code-label">${escapeHtml(primaryShift.label)}</span>${primaryShift.flagged ? '<b class="shift-flag">**</b>' : ''}</span>`
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
    const isSunday = index % 7 === 6;
    const weekHours = isSunday ? weeklyShiftHours(date, grouped) : 0;
    const weekHoursLabel = formatHourTotal(weekHours);
    const weekTotal = isSunday ? `<span class="weekly-hours" title="Ore lavorate da lunedì a domenica"><b>Σ</b><span>${weekHoursLabel}h</span></span>` : '';
    const repDay = dayOnCall ? '<span class="on-call-half on-call-day"><b>repD</b></span>' : '';
    const repNight = nightOnCall ? '<span class="on-call-half on-call-night"><b>repN</b></span>' : '';
    cells.push(`
      <button class="day-cell${shiftClass}${outside ? ' is-outside' : ''}${key === todayKey ? ' is-today' : ''}${isCurrentWeek ? ' is-current-week' : ''}${events.length ? ' has-events' : ''}${isSunday ? ' has-week-total' : ''}"
        type="button" data-date="${key}" style="--week-column: ${index % 7}" aria-label="${escapeHtml(formatDay(date))}, ${events.length} turni${isSunday ? `, ${weekHoursLabel} ore nella settimana` : ''}">
        ${repDay}${repNight}
        <span class="day-number">${date.getDate()}</span>
        ${weekTotal}
        <span class="destination-badges">${destinations}</span>
        ${shiftLabel}
        <span class="calendar-entries">${calendarEntryHtml}${calendarOverflow}</span>
      </button>`);
  }
  els.monthGrid.innerHTML = cells.join('');
  els.monthGrid.classList.toggle('has-current-week', hasCurrentWeek);
  renderSummary();

  if (state.updatedAt) {
    const updated = new Intl.DateTimeFormat('it-IT', { hour: '2-digit', minute: '2-digit' }).format(new Date(state.updatedAt));
    els.syncStatus.textContent = `Aggiornato alle ${updated}`;
    els.syncStatus.classList.remove('is-error');
  }
}

function renderSummary() {
  const start = localDateKey(startOfMonth(state.visibleMonth));
  const end = localDateKey(addMonths(state.visibleMonth, 1));
  const events = state.events.filter((event) => {
    const key = eventDateKey(event);
    return key >= start && key < end;
  });
  const shifts = events
    .filter((event) => !onCallKind(event))
    .map(parseShiftEvent)
    .filter((shift) => shift.recognized);
  const hours = shifts.reduce((total, shift) => total + shift.hours, 0);
  els.shiftCount.textContent = String(shifts.filter((shift) => shift.code !== '0-8').length);
  els.hourCount.textContent = formatHourTotal(hours);
  els.nightCount.textContent = String(shifts.filter((shift) => shift.code === '20-24').length);
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

async function onGoogleCredential(response) {
  state.idToken = response.credential || '';
  els.loginStatus.textContent = 'Accesso verificato. Carico i tuoi turni…';
  els.loginStatus.classList.remove('is-error');
  try {
    const session = await jsonpRequest('createDeviceSession', { idToken: state.idToken });
    if (session?.sessionToken && session?.expiresAt) {
      saveDeviceSession(session);
      state.deviceSessionToken = session.sessionToken;
      state.idToken = '';
    }
  } catch (error) {
    // Durante un rilascio graduale il token Google corrente resta utilizzabile.
  }
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
  if (state.deviceSessionToken || initializeGoogleIdentity.initialized) return;
  if (!window.google?.accounts?.id) {
    window.setTimeout(initializeGoogleIdentity, 100);
    return;
  }
  google.accounts.id.initialize({
    client_id: CONFIG.GOOGLE_CLIENT_ID,
    callback: onGoogleCredential,
    auto_select: true,
  });
  initializeGoogleIdentity.initialized = true;
  google.accounts.id.renderButton(els.googleSignin, {
    theme: 'outline', size: 'large', shape: 'pill', text: 'signin_with', width: 280,
  });
  google.accounts.id.prompt();
}

async function initializeStandalone() {
  const savedSession = readDeviceSession();
  if (savedSession) {
    state.deviceSessionToken = savedSession.sessionToken;
    showSessionSplash('Ripristino della sessione…');
    els.loginStatus.textContent = 'Ripristino della sessione…';
    const loaded = await loadMonth();
    hideSessionSplash(SESSION_SPLASH_MINIMUM_MS);
    if (loaded || state.deviceSessionToken) return;
  }
  hideSessionSplash();
  initializeGoogleIdentity();
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
  logoutStandalone();
});

document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  closeSheet(els.daySheet);
  closeSheet(els.accountSheet);
});

renderMonth();
if (EMBEDDED_MODE) {
  hideSessionSplash();
  els.loginStatus.textContent = 'Apertura dei tuoi turni…';
  notifyParent('planner-turni-ready');
  ['pointerdown', 'touchstart', 'keydown'].forEach((eventName) => {
    document.addEventListener(eventName, () => notifyParent('planner-activity'), { passive: true });
  });
} else {
  initializeStandalone().catch(() => {
    hideSessionSplash();
    initializeGoogleIdentity();
  });
}
if ('serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    const hadController = Boolean(navigator.serviceWorker.controller);
    let refreshing = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (!hadController || refreshing) return;
      refreshing = true;
      showSessionSplash('Aggiornamento dell’app…');
      window.setTimeout(() => window.location.reload(), 350);
    });
    try {
      const registration = await navigator.serviceWorker.register('./service-worker.js?v=180826.8', {
        updateViaCache: 'none',
      });
      await registration.update();
    } catch {
      // L'app resta utilizzabile online anche se il service worker non è disponibile.
    }
  });
}
