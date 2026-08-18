const CONFIG = {
  SHARED_CALENDAR_ID: '9d42da48ceb082c24d18a088c08edd6c0944d5e0abb0d620edcb9b6323f6d4da@group.calendar.google.com',
  GOOGLE_CLIENT_ID: '879487248442-q41p31thu716ffu9qctje1pm1pdn2ulo.apps.googleusercontent.com',
  ALLOWED_DOMAIN: '',
  ALLOWED_EMAILS: [
    'john.ncr24@gmail.com',
    'giannicola.aru@gmail.com',
    'silvic27@gmail.com',
    'mattia.cabianca@gmail.com',
    'cordalaura3@gmail.com',
    'micheladelrio@tiscali.it',
    'mdesogus.76@gmail.com',
    'paolomattana2@gmail.com',
    'femasillo78@gmail.com',
    'patrypitzalis@yahoo.it',
    'pirasdesi@gmail.com',
    'frapira73@gmail.com',
    'bpistincu@gmail.com',
    'plircr80@gmail.com',
    'dpuddu68@gmail.com',
    'smarta85@hotmail.it',
    'cris.tolu76@gmail.com',
    'elvy.vazz@gmail.com',
  ],
  OWNER_NAME_OVERRIDES: {
    'giannicola.aru@gmail.com': 'Gian Nicola Aru',
    'mattia.cabianca@gmail.com': 'Mattia Cabianca',
    'silvic27@gmail.com': 'Silvia Casula',
    'cordalaura3@gmail.com': 'Laura Corda',
    'micheladelrio@tiscali.it': 'Michela Del Rio',
    'mdesogus.76@gmail.com': 'Marco Desogus',
    'femasillo78@gmail.com': 'Federica Masillo',
    'paolomattana2@gmail.com': 'Paolo Mattana',
    'pirasdesi@gmail.com': 'Desiderio Piras',
    'frapira73@gmail.com': 'Francesca Piras',
    'plircr80@gmail.com': 'Riccardo Pili',
    'bpistincu@gmail.com': 'Barbara Pistincu',
    'patrypitzalis@yahoo.it': 'Patrizia Pitzalis',
    'dpuddu68@gmail.com': 'Daniela Puddu',
    'smarta85@hotmail.it': 'Marta Sanna',
    'cris.tolu76@gmail.com': 'Cristian Tolu',
    'elvy.vazz@gmail.com': 'Elvy',
  },
  SHIFT_CALENDAR_BY_OWNER_NAME: {
    'Gian Nicola Aru': 'Turni Aru',
    'Mattia Cabianca': 'Turni Cabianca',
    'Silvia Casula': 'Turni Casula',
    'Michela Del Rio': 'Turni Del Rio',
    'Federica Masillo': 'Turni Masillo',
    'Riccardo Pili': 'Turni Pili',
    'Francesca Piras': 'Turni Piras F',
    'Desiderio Piras': 'Turni Piras D',
    'Patrizia Pitzalis': 'Turni Pitzalis',
    'Marta Sanna': 'Turni Sanna',
    'Daniela Puddu': 'Turni Puddu',
  },
  LOOKAHEAD_DAYS: 730,
  DEVICE_SESSION_TTL_MS: 30 * 24 * 60 * 60 * 1000,
  DEVICE_SESSION_PROPERTY_PREFIX: 'PERSONAL_SHIFT_DEVICE_SESSION_',
  MAX_DEVICE_SESSIONS_PER_USER: 5,
};

function doGet(e) {
  const params = (e && e.parameter) || {};
  if (params.api === '1') {
    return handleApiGet_(params);
  }

  return ContentService.createTextOutput(
    'Apps Script backend attivo. Usa il frontend GitHub Pages.'
  ).setMimeType(ContentService.MimeType.TEXT);
}

function handleApiGet_(params) {
  const callback = sanitizeCallback_(params.callback);
  if (!callback) {
    return jsonpErrorOutput_('Callback mancante o non valida.');
  }

  try {
    const action = String(params.action || '').trim();
    const idToken = String(params.idToken || '').trim();
    const sessionToken = String(params.sessionToken || '').trim();
    const payload = parsePayload_(params.payload || '');
    let result;

    switch (action) {
      case 'bootstrap':
        result = getBootstrapData_(idToken);
        break;
      case 'create':
        result = createOwnedEvent_(payload, idToken);
        break;
      case 'update':
        result = updateOwnedEvent_(payload, idToken);
        break;
      case 'delete':
        result = deleteOwnedEvent_(String(params.eventId || payload.id || ''), idToken);
        break;
      case 'personalShifts':
        result = getPersonalShifts_(payload, idToken, sessionToken);
        break;
      case 'createDeviceSession':
        result = createDeviceSession_(idToken);
        break;
      case 'revokeDeviceSession':
        result = revokeDeviceSession_(sessionToken);
        break;
      default:
        throw new Error('Azione non supportata.');
    }

    return jsonpSuccessOutput_(callback, result);
  } catch (error) {
    return jsonpErrorOutput_(String(error && error.message ? error.message : error), callback);
  }
}

function getPersonalShifts_(payload, idToken, sessionToken) {
  const user = sessionToken ? getDeviceSessionUser_(sessionToken) : getVerifiedUser_(idToken);
  const range = validateShiftRange_(payload);
  const ownerName = resolveOwnerName_(user.email, user.name);
  const calendarSummary = resolveShiftCalendarSummary_(user.email, ownerName);
  const calendarId = findCalendarIdBySummary_(calendarSummary);
  const response = Calendar.Events.list(calendarId, {
    singleEvents: true,
    showDeleted: false,
    orderBy: 'startTime',
    timeMin: range.start.toISOString(),
    timeMax: range.end.toISOString(),
    maxResults: 500,
  });

  return {
    user: user,
    ownerName: ownerName,
    calendarName: calendarSummary,
    range: { start: payload.start, end: payload.end },
    updatedAt: new Date().toISOString(),
    events: (response.items || [])
      .filter(function(item) { return item.status !== 'cancelled'; })
      .map(mapShiftEventForClient_),
  };
}

function createDeviceSession_(idToken) {
  const user = getVerifiedUser_(idToken);
  const token = createDeviceSessionToken_();
  const tokenHash = hashDeviceSessionToken_(token);
  const now = Date.now();
  const expiresAt = now + CONFIG.DEVICE_SESSION_TTL_MS;

  withRequestLock_(function() {
    const sessions = readDeviceSessions_();
    pruneDeviceSessions_(sessions, now);
    sessions[tokenHash] = {
      email: user.email,
      name: user.name,
      picture: user.picture,
      createdAt: now,
      expiresAt: expiresAt,
    };
    limitDeviceSessionsForUser_(sessions, user.email);
    writeDeviceSessions_(sessions);
  });

  return { sessionToken: token, expiresAt: new Date(expiresAt).toISOString() };
}

function getDeviceSessionUser_(sessionToken) {
  const tokenHash = hashDeviceSessionToken_(sessionToken);
  const now = Date.now();
  const sessions = readDeviceSessions_();
  const session = sessions[tokenHash];
  if (!session || Number(session.expiresAt || 0) <= now) {
    if (session) {
      withRequestLock_(function() {
        const currentSessions = readDeviceSessions_();
        delete currentSessions[tokenHash];
        pruneDeviceSessions_(currentSessions, now);
        writeDeviceSessions_(currentSessions);
      });
    }
    throw new Error('Sessione dispositivo scaduta. Accedi di nuovo.');
  }

  return validateAuthorizedUser_({
    email: session.email,
    name: session.name,
    picture: session.picture,
  });
}

function revokeDeviceSession_(sessionToken) {
  if (!sessionToken) return { revoked: true };
  const tokenHash = hashDeviceSessionToken_(sessionToken);
  withRequestLock_(function() {
    const sessions = readDeviceSessions_();
    delete sessions[tokenHash];
    pruneDeviceSessions_(sessions, Date.now());
    writeDeviceSessions_(sessions);
  });
  return { revoked: true };
}

function createDeviceSessionToken_() {
  return (Utilities.getUuid() + Utilities.getUuid()).replace(/-/g, '');
}

function hashDeviceSessionToken_(sessionToken) {
  const token = String(sessionToken || '').trim();
  if (!/^[a-fA-F0-9]{64}$/.test(token)) {
    throw new Error('Sessione dispositivo scaduta. Accedi di nuovo.');
  }
  return Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256,
    token,
    Utilities.Charset.UTF_8
  ).map(function(byte) {
    return ('0' + ((byte + 256) % 256).toString(16)).slice(-2);
  }).join('');
}

function readDeviceSessions_() {
  const stored = PropertiesService.getScriptProperties().getProperties();
  const sessions = {};
  Object.keys(stored).forEach(function(name) {
    if (name.indexOf(CONFIG.DEVICE_SESSION_PROPERTY_PREFIX) !== 0) return;
    const tokenHash = name.slice(CONFIG.DEVICE_SESSION_PROPERTY_PREFIX.length);
    try {
      const session = JSON.parse(stored[name]);
      if (session && typeof session === 'object' && !Array.isArray(session)) {
        sessions[tokenHash] = session;
      }
    } catch (error) {
      // Una singola sessione corrotta non deve bloccare quelle valide.
    }
  });
  return sessions;
}

function writeDeviceSessions_(sessions) {
  const properties = PropertiesService.getScriptProperties();
  const stored = properties.getProperties();
  Object.keys(stored).forEach(function(name) {
    if (name.indexOf(CONFIG.DEVICE_SESSION_PROPERTY_PREFIX) !== 0) return;
    const tokenHash = name.slice(CONFIG.DEVICE_SESSION_PROPERTY_PREFIX.length);
    if (!sessions[tokenHash]) properties.deleteProperty(name);
  });
  Object.keys(sessions).forEach(function(tokenHash) {
    properties.setProperty(
      CONFIG.DEVICE_SESSION_PROPERTY_PREFIX + tokenHash,
      JSON.stringify(sessions[tokenHash])
    );
  });
}

function pruneDeviceSessions_(sessions, now) {
  Object.keys(sessions).forEach(function(tokenHash) {
    if (Number((sessions[tokenHash] || {}).expiresAt || 0) <= now) {
      delete sessions[tokenHash];
    }
  });
}

function limitDeviceSessionsForUser_(sessions, email) {
  const normalizedEmail = String(email || '').trim().toLowerCase();
  const matching = Object.keys(sessions)
    .filter(function(tokenHash) {
      return String((sessions[tokenHash] || {}).email || '').trim().toLowerCase() === normalizedEmail;
    })
    .sort(function(left, right) {
      return Number((sessions[right] || {}).createdAt || 0) - Number((sessions[left] || {}).createdAt || 0);
    });
  matching.slice(CONFIG.MAX_DEVICE_SESSIONS_PER_USER).forEach(function(tokenHash) {
    delete sessions[tokenHash];
  });
}

function validateShiftRange_(payload) {
  const startText = String((payload || {}).start || '').trim();
  const endText = String((payload || {}).end || '').trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(startText) || !/^\d{4}-\d{2}-\d{2}$/.test(endText)) {
    throw new Error('Intervallo mensile non valido.');
  }
  const start = new Date(startText + 'T00:00:00+01:00');
  const end = new Date(endText + 'T00:00:00+01:00');
  const days = (end.getTime() - start.getTime()) / (24 * 60 * 60 * 1000);
  if (!Number.isFinite(days) || days <= 0 || days > 62) {
    throw new Error('Intervallo mensile non valido.');
  }
  return { start: start, end: end };
}

function resolveShiftCalendarSummary_(email, ownerName) {
  const overrides = getJsonScriptProperty_('SHIFT_CALENDAR_MAP_JSON', {});
  const configured = String((overrides || {})[String(email || '').toLowerCase()] || '').trim();
  if (configured) return configured;

  const fallback = CONFIG.SHIFT_CALENDAR_BY_OWNER_NAME || {};
  const summary = String(fallback[ownerName] || '').trim();
  if (!summary) {
    throw new Error('Nessun calendario turni associato a questo account.');
  }
  return summary;
}

function findCalendarIdBySummary_(summary) {
  let pageToken = '';
  do {
    const options = { maxResults: 250, showHidden: true };
    if (pageToken) options.pageToken = pageToken;
    const response = Calendar.CalendarList.list(options);
    const match = (response.items || []).find(function(item) {
      return String(item.summary || '').trim().toLowerCase() === String(summary).trim().toLowerCase();
    });
    if (match && match.id) return match.id;
    pageToken = String(response.nextPageToken || '');
  } while (pageToken);
  throw new Error('Calendario non disponibile: ' + summary + '.');
}

function mapShiftEventForClient_(event) {
  const privateProperties = ((event.extendedProperties || {}).private || {});
  return {
    id: event.id || '',
    summary: event.summary || 'Turno',
    description: event.description || '',
    location: event.location || '',
    colorId: String(event.colorId || ''),
    start: (event.start && (event.start.dateTime || event.start.date)) || '',
    end: (event.end && (event.end.dateTime || event.end.date)) || '',
    updated: event.updated || '',
    dayName: privateProperties.plannerDayName || '',
    slotKey: privateProperties.plannerSlotKey || '',
  };
}

function getBootstrapData_(idToken) {
  const user = getVerifiedUser_(idToken);
  const now = new Date();
  const min = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const max = new Date(min.getTime() + CONFIG.LOOKAHEAD_DAYS * 24 * 60 * 60 * 1000);
  return {
    user: user,
    config: { lookaheadDays: CONFIG.LOOKAHEAD_DAYS },
    events: listEvents_(user.email, min, max),
  };
}

function createOwnedEvent_(payload, idToken) {
  const user = getVerifiedUser_(idToken);
  validatePayload_(payload);
  const ownerName = resolveOwnerName_(user.email, user.name);

  return withRequestLock_(function() {
    assertNoDuplicateRequest_(payload, user.email);

    const event = {
      summary: payload.summary.trim(),
      description: String(payload.description || '').trim(),
      location: String(payload.location || '').trim(),
      start: buildAllDayDateObject_(payload.start),
      end: buildAllDayDateObject_(payload.end),
      extendedProperties: {
        private: {
          ownerEmail: user.email,
          ownerName: ownerName,
        },
      },
    };

    const created = Calendar.Events.insert(event, CONFIG.SHARED_CALENDAR_ID);
    return mapEventForClient_(created, user.email);
  });
}

function updateOwnedEvent_(payload, idToken) {
  const user = getVerifiedUser_(idToken);
  validatePayload_(payload, true);
  const ownerName = resolveOwnerName_(user.email, user.name);

  return withRequestLock_(function() {
    const existing = Calendar.Events.get(CONFIG.SHARED_CALENDAR_ID, payload.id);
    assertOwnership_(existing, user.email);
    assertNoDuplicateRequest_(payload, user.email, payload.id);

    const updatedEvent = {
      summary: payload.summary.trim(),
      description: String(payload.description || '').trim(),
      location: String(payload.location || '').trim(),
      start: buildAllDayDateObject_(payload.start),
      end: buildAllDayDateObject_(payload.end),
      extendedProperties: existing.extendedProperties || {
        private: {
          ownerEmail: user.email,
          ownerName: ownerName,
        },
      },
    };
    updatedEvent.extendedProperties.private = updatedEvent.extendedProperties.private || {};
    updatedEvent.extendedProperties.private.ownerEmail = user.email;
    updatedEvent.extendedProperties.private.ownerName = ownerName;

    const updated = Calendar.Events.update(updatedEvent, CONFIG.SHARED_CALENDAR_ID, payload.id);
    return mapEventForClient_(updated, user.email);
  });
}

function deleteOwnedEvent_(eventId, idToken) {
  const user = getVerifiedUser_(idToken);
  if (!eventId) {
    throw new Error('ID evento mancante.');
  }
  const existing = Calendar.Events.get(CONFIG.SHARED_CALENDAR_ID, eventId);
  assertOwnership_(existing, user.email);
  Calendar.Events.remove(CONFIG.SHARED_CALENDAR_ID, eventId);
  return { ok: true, id: eventId };
}

function listEvents_(currentEmail, timeMin, timeMax) {
  const response = Calendar.Events.list(CONFIG.SHARED_CALENDAR_ID, {
    singleEvents: true,
    orderBy: 'startTime',
    timeMin: timeMin.toISOString(),
    timeMax: timeMax.toISOString(),
    maxResults: 2500,
  });

  const items = response.items || [];
  return items
    .filter(function(item) {
      return item.status !== 'cancelled';
    })
    .map(function(item) {
      return mapEventForClient_(item, currentEmail);
    });
}

function mapEventForClient_(event, currentEmail) {
  const ownerEmail =
    (((event.extendedProperties || {}).private || {}).ownerEmail || '').toLowerCase();
  const storedOwnerName =
    (((event.extendedProperties || {}).private || {}).ownerName || '').trim();
  const ownerName = resolveOwnerName_(ownerEmail, storedOwnerName);
  return {
    id: event.id,
    summary: event.summary || '(Senza titolo)',
    description: event.description || '',
    location: event.location || '',
    start: (event.start && (event.start.dateTime || event.start.date)) || '',
    end: (event.end && (event.end.dateTime || event.end.date)) || '',
    created: event.created || '',
    updated: event.updated || '',
    ownerEmail: ownerEmail,
    ownerName: ownerName,
    canEdit: ownerEmail === String(currentEmail || '').toLowerCase(),
  };
}

function resolveOwnerName_(email, fallbackName) {
  const normalizedEmail = String(email || '').trim().toLowerCase();
  const overrides = getJsonScriptProperty_('OWNER_NAME_OVERRIDES_JSON', CONFIG.OWNER_NAME_OVERRIDES || {});
  if (normalizedEmail && overrides[normalizedEmail]) {
    return String(overrides[normalizedEmail] || '').trim();
  }
  return String(fallbackName || '').trim();
}

function getVerifiedUser_(idToken) {
  if (!idToken) {
    throw new Error('Utente non autenticato.');
  }

  const response = UrlFetchApp.fetch(
    'https://oauth2.googleapis.com/tokeninfo?id_token=' + encodeURIComponent(idToken),
    { muteHttpExceptions: true }
  );

  if (response.getResponseCode() !== 200) {
    throw new Error('Token Google non valido.');
  }

  return validateTokenInfo_(JSON.parse(response.getContentText()));
}

function validateTokenInfo_(tokenInfo) {
  const info = tokenInfo || {};
  if (String(info.aud || '').trim() !== CONFIG.GOOGLE_CLIENT_ID) {
    throw new Error('Client OAuth non autorizzato.');
  }

  const iss = String(info.iss || '').trim();
  if (iss && iss !== 'https://accounts.google.com' && iss !== 'accounts.google.com') {
    throw new Error('Token Google non valido.');
  }

  const exp = Number(info.exp || 0);
  if (!exp || exp * 1000 <= Date.now()) {
    throw new Error('Token Google non valido.');
  }

  const emailVerified = info.email_verified;
  if (emailVerified !== true && emailVerified !== 'true') {
    throw new Error('Token Google non valido.');
  }

  const email = String(info.email || '').trim().toLowerCase();
  if (!email) {
    throw new Error('Email utente non disponibile.');
  }

  return validateAuthorizedUser_({
    email: email,
    name: String(info.name || '').trim(),
    picture: String(info.picture || '').trim(),
  });
}

function validateAuthorizedUser_(user) {
  const email = String((user || {}).email || '').trim().toLowerCase();
  if (!email) {
    throw new Error('Email utente non disponibile.');
  }

  const configuredAllowedEmails = getJsonScriptProperty_('ALLOWED_EMAILS_JSON', CONFIG.ALLOWED_EMAILS || []);
  const allowedEmails = Array.isArray(configuredAllowedEmails)
    ? configuredAllowedEmails.map(function(item) {
        return String(item || '').trim().toLowerCase();
      }).filter(Boolean)
    : [];
  if (allowedEmails.length && allowedEmails.indexOf(email) === -1) {
    throw new Error('Questo account non è autorizzato ad accedere.');
  }

  if (CONFIG.ALLOWED_DOMAIN) {
    const domain = email.split('@')[1] || '';
    if (domain !== CONFIG.ALLOWED_DOMAIN) {
      throw new Error('Dominio email non autorizzato.');
    }
  }

  return {
    email: email,
    name: String((user || {}).name || '').trim(),
    picture: String((user || {}).picture || '').trim(),
  };
}

function getJsonScriptProperty_(name, fallbackValue) {
  const raw = PropertiesService.getScriptProperties().getProperty(name) || '';
  if (!raw) return fallbackValue;
  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error(name + ' non è un JSON valido.');
  }
}

function assertOwnership_(event, email) {
  const ownerEmail =
    (((event.extendedProperties || {}).private || {}).ownerEmail || '').toLowerCase();
  if (!ownerEmail || ownerEmail !== String(email || '').toLowerCase()) {
    throw new Error('Puoi modificare solo i tuoi eventi.');
  }
}

function withRequestLock_(callback) {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    return callback();
  } finally {
    lock.releaseLock();
  }
}

function assertNoDuplicateRequest_(payload, ownerEmail, excludedEventId) {
  const requestedType = normalizeRequestType_(payload.summary);
  const requestedStart = isoDateOnly_(payload.start);
  const requestedEnd = isoDateOnly_(payload.end);
  const normalizedOwnerEmail = String(ownerEmail || '').trim().toLowerCase();
  const excludedId = String(excludedEventId || '').trim();
  let pageToken = '';

  do {
    const options = {
      singleEvents: true,
      timeMin: new Date(requestedStart + 'T00:00:00Z').toISOString(),
      timeMax: new Date(requestedEnd + 'T00:00:00Z').toISOString(),
      maxResults: 2500,
      showDeleted: false,
    };
    if (pageToken) {
      options.pageToken = pageToken;
    }

    const response = Calendar.Events.list(CONFIG.SHARED_CALENDAR_ID, options);
    const items = response.items || [];

    for (let i = 0; i < items.length; i += 1) {
      const existing = items[i];
      if (existing.status === 'cancelled') continue;
      if (excludedId && String(existing.id || '') === excludedId) continue;
      if (normalizeRequestType_(existing.summary) !== requestedType) continue;

      const existingOwnerEmail =
        (((existing.extendedProperties || {}).private || {}).ownerEmail || '')
          .trim()
          .toLowerCase();
      if (!existingOwnerEmail || existingOwnerEmail !== normalizedOwnerEmail) continue;

      const existingStartValue =
        existing.start && (existing.start.date || existing.start.dateTime);
      const existingEndValue =
        existing.end && (existing.end.date || existing.end.dateTime);
      if (!existingStartValue || !existingEndValue) continue;

      const existingStart = isoDateOnly_(existingStartValue);
      const existingEnd = isoDateOnly_(existingEndValue);
      if (requestedStart < existingEnd && existingStart < requestedEnd) {
        const duplicateDay = requestedStart > existingStart ? requestedStart : existingStart;
        throw new Error(
          'Richiesta non salvata: una richiesta identica è già stata salvata per il giorno ' +
          formatItalianDate_(duplicateDay) +
          '.'
        );
      }
    }

    pageToken = String(response.nextPageToken || '');
  } while (pageToken);
}

function normalizeRequestType_(value) {
  return String(value || '').trim().toUpperCase();
}

function formatItalianDate_(isoDate) {
  const parts = String(isoDate || '').split('-');
  if (parts.length !== 3) return String(isoDate || '');
  return parts[2] + '/' + parts[1] + '/' + parts[0];
}

function validatePayload_(payload, requireId) {
  if (!payload || typeof payload !== 'object') {
    throw new Error('Dati evento mancanti.');
  }
  if (requireId && !payload.id) {
    throw new Error('ID evento mancante.');
  }
  if (!String(payload.summary || '').trim()) {
    throw new Error('Titolo obbligatorio.');
  }
  if (!payload.start || !payload.end) {
    throw new Error('Giorni obbligatori.');
  }
  const start = new Date(payload.start);
  const end = new Date(payload.end);
  if (isNaN(start.getTime()) || isNaN(end.getTime())) {
    throw new Error('Date non valide.');
  }
  if (end <= start) {
    throw new Error('Il giorno finale deve essere successivo al giorno iniziale.');
  }
}

function buildAllDayDateObject_(value) {
  return {
    date: isoDateOnly_(value),
  };
}

function isoDateOnly_(value) {
  const date = new Date(value);
  if (isNaN(date.getTime())) {
    throw new Error('Data non valida.');
  }
  const year = String(date.getUTCFullYear());
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  return year + '-' + month + '-' + day;
}

function buildDateTimeObject_(value, timeZone) {
  return {
    dateTime: new Date(value).toISOString(),
    timeZone: timeZone || Session.getScriptTimeZone() || 'Europe/Rome',
  };
}

function parsePayload_(encodedPayload) {
  const source = String(encodedPayload || '').trim();
  if (!source) {
    return {};
  }
  const decoded = Utilities.newBlob(
    Utilities.base64DecodeWebSafe(source)
  ).getDataAsString('utf-8');
  return JSON.parse(decoded);
}

function sanitizeCallback_(callback) {
  const value = String(callback || '').trim();
  if (!/^[A-Za-z_$][A-Za-z0-9_$\.]{0,80}$/.test(value)) {
    return '';
  }
  return value;
}

function jsonpSuccessOutput_(callback, result) {
  const body = callback + '(' + JSON.stringify({ ok: true, result: result }) + ');';
  return ContentService.createTextOutput(body).setMimeType(ContentService.MimeType.JAVASCRIPT);
}

function jsonpErrorOutput_(message, callback) {
  const cb = callback || 'console.error';
  const body = cb + '(' + JSON.stringify({ ok: false, error: String(message || 'Errore') }) + ');';
  return ContentService.createTextOutput(body).setMimeType(ContentService.MimeType.JAVASCRIPT);
}

function testUrlFetchAuth() {
  const response = UrlFetchApp.fetch('https://www.googleapis.com/oauth2/v1/certs');
  Logger.log(response.getResponseCode());
}

function testCalendarAuth() {
  const cal = CalendarApp.getCalendarById(CONFIG.SHARED_CALENDAR_ID);
  Logger.log(cal ? cal.getName() : 'Calendario non trovato');
}

function showAuthUrl() {
  const authInfo = ScriptApp.getAuthorizationInfo(ScriptApp.AuthMode.FULL);
  Logger.log(authInfo.getAuthorizationStatus());
  Logger.log(authInfo.getAuthorizationUrl());
}
