---
date_created: 2026-09-12 12:25:00
type: changelog
tags:
  - project
  - changelog
date_modified: 2026-09-12 12:25:00
---

# v1.17.0 — Sortier-Studio: neue Kategorie "Studio", ein-/ausblendbare Spalten (2026-09-12)

- **Neue Kategorie "Studio"** (Produzent, im Unterschied zu Provider als Vertrieb): eigene Toolbox-
  Box zwischen Provider und Collection mit Autocomplete/"Neu anlegen"/"Entfernen", genau wie bei
  Artist/Provider - eigener `config/studios.json`-Store, eigene `studios`-Tabelle,
  `media_items.studio_id`-Spalte. Ist Teil von "Alles setzen". Studio wird (noch) nicht automatisch
  aus Ordnernamen aufgelöst wie Artist/Provider - reine manuelle Zuordnung im Sortier-Studio.
- **Ein-/ausblendbare Tabellen-Spalten**: neues Menü (▤-Icon neben dem Kopfzeilen-Pin) listet alle
  optionalen Spalten (Artist, Studio, Collection, Provider, Status, Co-Artists, Titel-Override,
  Tags) mit Checkboxen zum Ein-/Ausblenden - Einstellung wird gemerkt (localStorage). Löst das vom
  Nutzer selbst vorausgesehene Problem, dass mit jeder neuen Kategorie die Tabelle irgendwann nicht
  mehr in die Breite passt. Studio startet standardmäßig ausgeblendet, da seltener gebraucht als die
  anderen Felder.
- **UI-Aufräumen**: "Ansicht"-Box (enthielt bisher nur das Filterfeld mit doppeltem Titel/Sublabel)
  zu einer einzigen "Filtern"-Box zusammengefasst, Suchfeld zentriert.

**Wichtig für den Nutzer:** laufende `afss dashboard`-Session neu starten.
