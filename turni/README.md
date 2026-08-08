# I miei turni

PWA in sola lettura che mostra, mese per mese, gli eventi pubblicati da
`planner_turni_web` nei calendari Google personali `Turni …`.

## Flusso

1. L’utente accede con Google dalla pagina GitHub Pages `/turni/`.
2. Il frontend invia l’ID token all’Apps Script esistente.
3. Apps Script verifica l’email nella whitelist e ricava il nome del medico.
4. Il backend individua il calendario personale associato e restituisce solo
   gli eventi compresi nel mese richiesto.

La pagina principale apre la vista in un pannello interno e le inoltra in
memoria il token Google già verificato tramite `postMessage` limitato alla
stessa origine. Il token non viene salvato in `localStorage` o nell’URL e non è
quindi necessario ripetere il login.

## Codifica delle celle

La cella usa il colore del turno principale: `M` (8–14) giallo, `MP` (8–20)
rosa, `R` verde, `P` (14–20) arancio, `N` (20–24) e `SN` (0–8) blu. La marcatura
`**` resta visibile accanto alla sigla. Le destinazioni sono mostrate come badge;
`repD` occupa la metà superiore grigia e `repN` quella inferiore.

## Configurazione Apps Script

Distribuire la versione aggiornata di `github_pages_shared_calendar/apps_script_backend/Code.gs`.
Il mapping predefinito associa i nomi già presenti in `OWNER_NAME_OVERRIDES` ai
calendari broadcast noti.

Per sovrascrivere o ampliare le associazioni senza modificare il codice, creare
una Script Property chiamata `SHIFT_CALENDAR_MAP_JSON`. Il valore deve essere un
oggetto JSON con email come chiave e nome esatto del calendario come valore:

```json
{"utente@example.com":"Turni Cognome"}
```

Anche whitelist e nomi possono essere spostati fuori dal codice impostando le
Script Properties `ALLOWED_EMAILS_JSON` (array JSON) e
`OWNER_NAME_OVERRIDES_JSON` (oggetto JSON). Finché non vengono impostate, il
backend usa i valori già presenti nella configurazione attuale.

L’account che pubblica la Web App Apps Script deve poter leggere i calendari
personali configurati.

## Pubblicazione

La cartella `turni` viene pubblicata automaticamente insieme al repository
GitHub Pages e sarà disponibile nel percorso `/turni/`.
