# Calendario condiviso con GitHub Pages + Apps Script

Questa variante usa:

- `GitHub Pages` per il frontend statico
- `Google Apps Script` come backend
- `Google Calendar` come archivio eventi condiviso

## Perche' questa variante

La web app Apps Script ospitata direttamente da Google crea problemi con `Google Identity Services` nel browser a causa delle origin OAuth.

Con `GitHub Pages` invece:

- il frontend ha un dominio stabile
- puoi registrare l'origin corretta nel client OAuth Web
- il login Google funziona in modo molto piu' lineare

## Struttura

- `frontend/index.html`
- `frontend/app.js`
- `frontend/styles.css`
- `apps_script_backend/Code.gs`
- `apps_script_backend/appsscript.json`

## Flusso

1. L'utente apre la pagina su GitHub Pages
2. Fa login con Google
3. Il frontend ottiene un `idToken`
4. Il frontend chiama Apps Script tramite `JSONP`
5. Apps Script verifica il token e controlla l'ownership degli eventi

## Nota tecnica importante

Le chiamate tra GitHub Pages e Apps Script vengono fatte via `JSONP` per evitare i problemi CORS/origin del browser con Apps Script.

Per un calendario condiviso e un uso normale e' una soluzione pratica. Per payload enormi o API piu' evolute, in futuro converrebbe un backend diverso.

## Setup rapido

### 1. Backend Apps Script

1. Crea un progetto Apps Script nuovo
2. Copia dentro:
   - `apps_script_backend/Code.gs`
   - `apps_script_backend/appsscript.json`
3. In `Code.gs` imposta:
   - `SHARED_CALENDAR_ID`
   - `GOOGLE_CLIENT_ID`
4. Collega un progetto Google Cloud
5. Abilita `Google Calendar API`
6. Aggiungi `Calendar API` in `Services`
7. Esegui `doGet` una volta per autorizzare
8. Fai deploy come `Web app`
   - `Execute as`: `Me`
   - `Who has access`: `Anyone`

### Se compare l'errore su `UrlFetchApp.fetch`

Se in produzione vedi:

`Non disponi dell'autorizzazione necessaria per chiamare UrlFetchApp.fetch`

controlla prima queste due cose:

1. Il deployment attivo deve essere quello del backend in `apps_script_backend`, non una copia vecchia.
2. Dopo ogni modifica a `appsscript.json` o agli scope, bisogna eseguire una volta una funzione del progetto e poi creare un nuovo deployment.

Il backend verifica il `idToken` con le chiavi pubbliche Google e poi controlla `aud`, `iss`, `exp`, `email_verified` e whitelist email. Questa e' la strada piu' robusta.

### 2. Frontend GitHub Pages

1. Crea un repository GitHub dedicato
2. Carica il contenuto della cartella `frontend`
3. In `frontend/app.js` imposta:
   - `APPS_SCRIPT_API_URL`
   - `GOOGLE_CLIENT_ID`
4. In Google Cloud, nel client OAuth Web, aggiungi l'origin di GitHub Pages:
   - `https://TUO-USERNAME.github.io`
   - oppure `https://TUO-USERNAME.github.io/NOME-REPO` se necessario come redirect path lato hosting, ma l'origin da registrare e' solo il dominio base
5. In GitHub abilita `Pages`

## File da configurare

- backend:
  - `apps_script_backend/Code.gs`
- frontend:
  - `frontend/app.js`
