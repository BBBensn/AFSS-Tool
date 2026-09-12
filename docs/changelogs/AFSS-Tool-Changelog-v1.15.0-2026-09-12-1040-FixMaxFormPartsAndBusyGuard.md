---
date_created: 2026-09-12 10:40:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-12 10:40:00
---

# v1.15.0 — Sortier-Studio: zweite Formular-Limit-Ursache gefunden, Doppel-Klick-Schutz (2026-09-12)

- **Zweite, tatsächliche Root Cause gefunden**: v1.14.0 hat `MAX_FORM_MEMORY_SIZE` (Gesamtgröße)
  aufgehoben, aber es gibt noch ein zweites, unabhängiges Werkzeug-Limit: `MAX_FORM_PARTS`
  (Standard 1000 Felder), das **nur** für `multipart/form-data` gilt - und genau das sendet das
  Sortier-Studio-JS, weil es Aktionen über `fetch()` mit einem `FormData`-Objekt abschickt (Browser
  kodieren das immer als multipart, nicht als das für normale `<form>`-Submits übliche
  `application/x-www-form-urlencoded`). Bei einer Auswahl von mehr als 1000 Dateien - z.B. "Alle"
  in der großen `all`-Ansicht - fällt Werkzeug beim Überschreiten **stillschweigend** auf ein leeres
  Formular zurück (`silent=True`), statt einen Fehler zu werfen: der Klick tat sichtbar gar nichts,
  ganz ohne Fehlermeldung, exakt das zuletzt beschriebene Verhalten. Mit einem Regressionstest
  abgesichert, der den Fehler zuerst nachstellt (schlägt ohne Fix fehl) und dann die Behebung
  bestätigt (1500 Dateien über einen echten multipart-Request korrekt zugeordnet).
- **Doppel-Klick-Schutz + Lade-Hinweis**: Bisher gab es beim Speichern keinerlei sichtbares
  Feedback - ein ungeduldiger zweiter Klick (naheliegend, wenn nichts sichtbar passiert) löste eine
  zusätzliche, parallele Anfrage aus. Jetzt blockiert ein `isBusy`-Flag jede weitere Aktion, solange
  eine noch läuft (verifiziert: 3 schnelle Klicks erzeugen nur eine einzige Anfrage), und ein
  Hinweistext ("⏳ Wird gespeichert...") macht sichtbar, dass etwas passiert.
- **Dev-Server läuft jetzt `threaded=True`**: eine einzelne große Anfrage blockierte bisher den
  kompletten (einzigen) Worker-Thread - jede andere Anfrage musste warten, was sich wie ein
  hängender Server anfühlte.
- Per Browser-Test mit ~16.000 Dateien verifiziert: eine komplette Bibliotheks-weite Auswahl
  ("Alle setzen" über alle 4 Platten) wird jetzt korrekt und mit sichtbarem Feedback verarbeitet.

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
