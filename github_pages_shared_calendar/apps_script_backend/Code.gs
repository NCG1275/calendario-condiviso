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
  LOOKAHEAD_DAYS: 730,
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
      default:
        throw new Error('Azione non supportata.');
    }

    return jsonpSuccessOutput_(callback, result);
  } catch (error) {
    return jsonpErrorOutput_(String(error && error.message ? error.message : error), callback);
  }
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
}

function updateOwnedEvent_(payload, idToken) {
  const user = getVerifiedUser_(idToken);
  validatePayload_(payload, true);
  const ownerName = resolveOwnerName_(user.email, user.name);

  const existing = Calendar.Events.get(CONFIG.SHARED_CALENDAR_ID, payload.id);
  assertOwnership_(existing, user.email);

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
  const overrides = CONFIG.OWNER_NAME_OVERRIDES || {};
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

  const allowedEmails = Array.isArray(CONFIG.ALLOWED_EMAILS)
    ? CONFIG.ALLOWED_EMAILS.map(function(item) {
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
    name: String(info.name || '').trim(),
    picture: String(info.picture || '').trim(),
  };
}

function assertOwnership_(event, email) {
  const ownerEmail =
    (((event.extendedProperties || {}).private || {}).ownerEmail || '').toLowerCase();
  if (!ownerEmail || ownerEmail !== String(email || '').toLowerCase()) {
    throw new Error('Puoi modificare solo i tuoi eventi.');
  }
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
