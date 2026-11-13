# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/) — versioni [SemVer](https://semver.org/lang/it/).
La versione è in `app.json` (`versione`, e `algoritmo_firma.versione` per il generatore).

## [Non rilasciato]

## [1.1.0] - 2026-11-13
### Aggiunto
- Controllo aggiornamenti: all'avvio l'app legge da GitHub il numero dell'ultima versione e, se è più nuova, lo dice con un
  avviso e il pulsante «Scarica» (anche nella finestra Info). Non invia dati; si spegne dalle Impostazioni.
- `script/build-deb.sh`: crea il pacchetto `.deb` in `build/` (app e librerie Python incluse; nome e versione da `app.json`).
- Licenza GNU AGPL-3.0 (`LICENSE`), mostrata anche nella finestra Info.
- README in inglese, con la nota di copyright delle icone Lucide (ISC).
- Creatore di firme: casella «Sottolineato» (spenta in partenza) per avere o no la riga/lo svolazzo sotto il nome.
- Impostazioni: salvataggio predefinito (chiedi / crea sempre una copia / sovrascrivi sempre), nome della
  copia con `{data}`, formato della data, file recenti (ricorda / svuota), esporta e importa le firme in uno .zip.
- «Disegna»: firma a mano col mouse o la tavoletta grafica (spessore dalla velocità o dalla pressione),
  salvata in SVG vettoriale.
- Miniature delle pagine in una colonna a sinistra (F4 per mostrarle/nasconderle), sincronizzate con lo scorrimento.
- «Trova dove firmare» (Ctrl+F): cerca «Firma», «Il dichiarante», «Letto e sottoscritto»… e mette lì la firma
  predefinita; se trova più punti li propone in un menu, se non ne trova firma in fondo all'ultima pagina.
- «Sigla pagine» (Ctrl+Maiusc+S): sigla piccola a margine di ogni pagina, con posizione, larghezza ed
  esclusione dell'ultima pagina; si annulla in un colpo solo.
- Firma di più PDF insieme (menu Apri, schermata iniziale o trascinando più PDF): posizione automatica,
  in fondo all'ultima pagina o come nel documento aperto; nuovi file `_firmato.pdf` o sovrascrittura.
- Firma predefinita (★) nelle Impostazioni.
- Guida in alto sulla pagina («1 Trascina la tua firma · 2 Premi Salva» + «Trova dove firmare») finché il
  documento non ha firme.
- Uscendo o aprendo un altro file con firme non salvate: scelta «Salva… / Non salvare / Annulla».
- README per GitHub con screenshot (firma fittizia).
### Modificato
- L'app si chiama **Syglami-PDF** (prima «Sigla»): il nome è solo in `app.json` e da lì arriva a finestre, messaggi e lanciatore.
- Creatore di firme: G maiuscola corsiva ridisegnata all'italiana (quella di prima sembrava una S). Algoritmo firma 3.0.0.
- Finestra «Informazioni su Sigla» a dimensioni fisse (non ridimensionabile).
- Codice riorganizzato secondo i principi SOLID: `firma_pdf.py` diviso nel package `sigla/` (config, pdf,
  ui/tema, ui/scena, ui/widget, ui/dialoghi, ui/finestra, app); `firma_pdf.py` resta il punto d'avvio.
- Pannello «Nuova firma» con titolo e descrizione distinti nei riquadri; finestre di conferma con l'icona
  dell'app; pulsante «Nuova» evidenziato con discrezione; «Salva e chiudi» nelle Impostazioni.
- Interfaccia responsive: restringendo la finestra la barra passa a sole icone e poi raccoglie zoom e
  impostazioni nel menu «Altro» (nessun comando sparisce); le miniature si
  nascondono da sole e la pagina si riadatta alla larghezza finché non scegli uno zoom.
- Firme: «Nuova» apre un pannello con tre scelte (Importa, Genera, Disegna); «Gestisci» apre «Le mie firme»
  (rinomina, predefinita, rimuovi); clic destro su una firma per le stesse azioni. Le Impostazioni contengono
  solo la cartella predefinita.
- Creatore di firme: colore predefinito nero.
- «Salva» è attivo solo quando ci sono firme da salvare; pulsanti di salvataggio più chiari
  («Salva una copia firmata…», «Sovrascrivi l'originale»).
- Zoom da pulsanti e tastiera centrato sulla pagina (con Ctrl + rotella resta sotto il mouse).
### Corretto
- `install.sh` funziona anche dopo aver spostato o rinominato la cartella.
- Lanciatore rinominato in `syglami-pdf.desktop` (da `app.json`): la vecchia voce «Sigla» in «Mostra applicazioni» viene rimossa.
- Icona in «Mostra applicazioni»: il lanciatore indica il file dell'icona, così non resta vecchia o assente fino al riavvio della sessione.
- Finestra Info: il link GitHub non viene più tagliato con caratteri di sistema grandi (la finestra si allarga).
- Menu a tendina illeggibili (voce evidenziata bianca su bianco) con il tema scuro di sistema: l'app usa ora
  una propria tavolozza chiara; menu a tendina e calendario hanno uno stile dedicato.
- Titoli più piccoli del testo con caratteri di sistema grandi; Impostazioni con campi schiacciati;
  stella «★» nel nome in modalità firma; anteprima di luogo e data tagliata; finestra Info troppo stretta.
- Crash dopo il salvataggio dall'app (al ricaricamento del PDF).
- Testi tagliati con caratteri di sistema grandi (schermata iniziale, «Disegna») e trattini bassi tagliati nei campi.
- Creatore di firme: i pallini dei cursori (leggibilità, inclinazione, spessore) apparivano tagliati.
- Possibile chiusura improvvisa cliccando la ✕ di una firma.
- I PDF protetti da password perdevano la protezione dopo la firma: ora la mantengono.
- Il creatore di firme chiudeva l'app con nomi senza lettere disegnabili (es. solo «ò»); ogni errore imprevisto
  ora mostra un messaggio invece di chiudere l'app.
- Ridimensionando una firma con luogo/data più larghi della firma, la misura «saltava».
- Le firme trascinate in parte fuori dal foglio venivano salvate tagliate: ora restano dentro la pagina.
- Rimuovere nelle Impostazioni una firma già posizionata faceva fallire il salvataggio.
- Una configurazione danneggiata veniva sovrascritta perdendo l'elenco firme: ora ne viene salvata una copia.
- Pagine di grande formato con zoom alto occupavano centinaia di MB di memoria.
- Firma in blocco: modificare l'elenco durante il lavoro dava errore; sovrascrivendo il PDF aperto, la finestra
  mostrava ancora la versione vecchia.
- Il numero di pagina restava vuoto sulla pagina 1 appena aperto un documento.
- Un PDF aperto con password errata restava aperto in memoria.
- `app.json` con versione dell'app, versione dell'algoritmo di firma, autore e link GitHub.
- Finestra Info (icona «i» in basso a destra o F1) che mostra i dati di `app.json`.
- Algoritmo di firma «Mano Hershey» portato a 2.0.0 (le varianti generate per uno stesso seme cambiano).
- Creatore di firme: menu «Stile» (Corsivo, Calligrafico, Stampatello, Professionale, Elegante, Frettolosa, Sigla).
### Modificato
- Generatore di firme: ogni variante è una mano più riconoscibile (forma delle lettere, pressione della penna,
  ritmo, puntini). Le firme già salvate non cambiano; le varianti proposte per uno stesso nome sì.
### Corretto
- Generatore di firme: le maiuscole non si sovrappongono più alla lettera seguente e restano sul rigo.
### Rimosso
- Import automatico, al primo avvio, di una firma da un percorso fisso del computer dell'autore.

## [1.0.0] - 2026-11-11
### Aggiunto
- Apertura PDF da dialogo, file recenti o trascinamento; vista continua con zoom e navigazione pagine.
- Firme trascinabili sulla pagina, oppure clic sulla firma e poi sulla pagina (cursore a timbro con anteprima).
- Più firme per documento: sposta, ridimensiona, elimina, frecce per i ritocchi, annulla/ripeti.
- Luogo e data opzionali sopra la firma, memorizzati tra le sessioni.
- Firme vettoriali (SVG): import PNG/JPG con vettorizzazione, import SVG, creatore di firme "a mano".
- Salvataggio: sovrascrivi l'originale o salva come nuovo file (scrittura atomica); pagine ruotate supportate.
- Impostazioni: gestione firme e cartella predefinita; icona e lanciatore desktop.
