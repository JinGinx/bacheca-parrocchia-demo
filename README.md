# La Campana — build dimostrativa WebAssembly 0.4

Build funzionante per una sola Parrocchia. L’interfaccia è una web app; il core deterministico per calendario e validazione viene eseguito in **WebAssembly** nel browser. Il backend dimostrativo Python/SQLite gestisce login demo e salvataggio. Non sono previste newsletter o notifiche email.

## Avvio

```bash
cd parrocchia
python3 server.py
```

Aprire il live preview o `http://localhost:4173`. Area Parroco: PIN dimostrativo **2468**.

## Funzioni

- Pagine pubbliche: Inizio, Orari e calendario, Avvisi, Liturgia, Contatti, Privacy.
- Link copiabile e QR code generato nel browser e scaricabile in PNG.
- Pannello Parroco con salvataggio persistente SQLite.
- Creazione, modifica ed eliminazione di avvisi, appuntamenti e orari ricorrenti.
- Modifica di dati parrocchiali, liturgia, aspetto e informativa privacy.
- Bozze visibili solo nell’area gestionale; i contenuti pubblicati vengono esposti nella parte pubblica.
- **Rimuovi dati dimostrativi** elimina soltanto i record ancora marcati come demo; conserva quelli creati o aggiornati dal Parroco.
- WebAssembly calcola i giorni del mese e il primo giorno della settimana; valida date, orari e campi essenziali degli avvisi. In assenza del modulo, la UI segnala il fallback JavaScript.

## Build del modulo WebAssembly

Il `.wasm` già compilato è in `assets/parrocchia_core.wasm`. Per ricompilarlo:

```bash
npm install
npm run build:wasm
```

Il sorgente AssemblyScript è `wasm/core.ts`; `wasm/core.wat` è la rappresentazione testuale generata. I test unitari del modulo si eseguono con `npm run test:wasm`.

## Dati dimostrativi

Al primo avvio `server.py` crea `content.sqlite3` con una Parrocchia, orari, eventi, avvisi e riferimenti liturgici **fittizi**. Nell’area Parroco, sezione **Privacy e contenuti**, premi **Rimuovi dati dimostrativi** per cancellare i record demo rimasti e i campi di esempio non sostituiti. Dopo il deployment, rigenera il QR: quello della preview punta all’indirizzo temporaneo.

## Avvertenza di sicurezza — demo, non produzione

Il PIN `2468` è noto e mostrato nell’interfaccia; il server incluso è soltanto dimostrativo, non è un sistema di autenticazione pronto per un servizio ufficiale. Non inserire dati pastorali o personali e non condividere questa preview con i fedeli come sito ufficiale. Per la produzione sostituire il login con identità protetta e autenticazione forte, verificare autorizzazioni lato server, HTTPS, backup/esportazione e aggiornamenti; concordare informativa e fornitori con la Diocesi. Sono state verificate le funzioni di login, salvataggio, bozze, CRUD e cancellazione selettiva; non è stato eseguito un penetration test.
