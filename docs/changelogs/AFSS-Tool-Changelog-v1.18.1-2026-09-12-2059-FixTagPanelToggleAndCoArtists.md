---
date_created: 2026-09-12 20:59:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-12 20:59:00
---

# v1.18.1 — Sortier-Studio: Tag-Panel-Toggle-Bugfix, Co-Artists lesbarer (2026-09-12)

- **Bugfix: "Tag ersetzen"-Panel ließ sich nicht schließen/öffnen** - die Panel-CSS setzte
  `display: flex` bedingungslos, was das `hidden`-Attribut (dessen Browser-Standard `display: none`
  ist) überschrieb. Panel war dadurch dauerhaft offen, der Toggle-Button-Klick änderte zwar das
  `hidden`-Attribut, hatte aber keine sichtbare Wirkung. Behoben mit einer expliziten
  `[hidden] { display: none; }`-Regel; die übrigen Menüs (Spalten-Auswahl, Lade-Hinweis) waren von
  diesem Bug nicht betroffen, da sie kein eigenes `display` setzen.
- **Mehrere Co-Artists pro Datei**: waren technisch schon länger unterstützt (die Datenbank erlaubt
  beliebig viele pro Datei), in der schmalen Tabellenspalte bei 3+ Einträgen aber schwer lesbar -
  die einzelnen Badges brachen unregelmäßig um. Jetzt sauber als Flex-Zeile mit Umbruch dargestellt,
  zusätzlich zeigt ein Hover-Tooltip auf der Zelle alle Namen kommasepariert auf einen Blick.

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
